import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Depends

from query_service.database.models import NotificationOutbox, Ticket, Window
from query_service.database.models.notification_outbox import NotificationOutboxStatus
from query_service.integrations.notifications.port import (
    NotificationEvent,
    NotificationMessage,
)
from query_service.modules.notifications.repository import NotificationRepository
from query_service.modules.tickets.repository import TicketRepository
from query_service.settings import settings

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        repository: NotificationRepository = Depends(),
        tickets: TicketRepository = Depends(),
    ) -> None:
        self.repository = repository
        self.tickets = tickets

    async def enqueue_called(self, ticket: Ticket, window: Window) -> None:
        if ticket.called_at is None:
            return

        message_id = uuid4()
        message = NotificationMessage(
            id=message_id,
            event_type=NotificationEvent.TICKET_CALLED,
            ticket_id=ticket.id,
            ticket_label=ticket.ticket_label,
            department_id=ticket.department_id,
            window_label=window.label,
        )

        await self._insert(
            message,
            idempotency_key=f"{ticket.id}:{NotificationEvent.TICKET_CALLED}:{ticket.called_at.isoformat()}",
        )

    async def enqueue_noshow(self, ticket: Ticket, window: Window) -> None:
        if ticket.canceled_at is None:
            return

        message_id = uuid4()
        message = NotificationMessage(
            id=message_id,
            event_type=NotificationEvent.TICKET_NOSHOW,
            ticket_id=ticket.id,
            ticket_label=ticket.ticket_label,
            department_id=ticket.department_id,
            window_label=window.label,
        )

        await self._insert(
            message,
            idempotency_key=f"{ticket.id}:{NotificationEvent.TICKET_NOSHOW}:{ticket.canceled_at.isoformat()}",
        )

    async def enqueue_approaching(self, ticket: Ticket, estimated_wait_time: int) -> None:
        message_id = uuid4()
        message = NotificationMessage(
            id=message_id,
            event_type=NotificationEvent.QUEUE_APPROACHING,
            ticket_id=ticket.id,
            ticket_label=ticket.ticket_label,
            department_id=ticket.department_id,
            estimated_wait_time=estimated_wait_time,
        )

        await self._insert(
            message,
            idempotency_key=f"{ticket.id}:{NotificationEvent.QUEUE_APPROACHING}",
        )

    async def enqueue_approaching_for_services(
        self,
        department_id: UUID,
        service_ids: list[UUID],
    ) -> None:
        if not service_ids:
            return

        queued = await self.tickets.list_eligible_queued(department_id, service_ids)

        # TODO: Avoid N+1 count_tickets_before over the full queue. This runs inside call_next with the window locked.
        for ticket in queued:
            tickets_ahead = await self.tickets.count_tickets_before(ticket)

            if tickets_ahead <= settings.notify_approaching_ahead:
                await self.enqueue_approaching(ticket, tickets_ahead)

    async def _insert(self, message: NotificationMessage, idempotency_key: str) -> None:
        # TODO: Add a periodic job to delete old sent/failed outbox rows for cleanup.
        row = NotificationOutbox(
            id=message.id,
            # Preferably, do not change the format of idempotency key, because it will no longer be valid.
            # TODO: If the format must change, delete or truncate old outbox rows first. Do not put that cleanup in a schema migration.
            idempotency_key=idempotency_key,
            event_type=message.event_type,
            ticket_id=message.ticket_id,
            payload=message.model_dump(mode="json"),
            status=NotificationOutboxStatus.PENDING,
            attempts=0,
            next_attempt_at=datetime.now(UTC),
        )

        await self.repository.insert_ignore(row)
