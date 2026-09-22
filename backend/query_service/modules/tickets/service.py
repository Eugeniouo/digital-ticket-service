import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends

from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.ticket_status_history import (
    TicketStatusChange,
    TicketStatusChangeReason,
    TicketStatusHistory,
)
from query_service.modules.notifications.service import NotificationService
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.slots.exceptions import SlotNotFoundError
from query_service.modules.slots.repository import SlotsRepository
from query_service.modules.tickets.exceptions import (
    DepartmentNotFoundError,
    InactiveServiceError,
    InvalidTicketStateError,
    MissingSlotIdError,
    ServiceNotFoundError,
    SlotFullError,
    SlotServiceMismatchError,
    TicketNotFoundError,
    UnexpectedSlotIdError,
)
from query_service.modules.tickets.priority import (
    QUEUE_TIMEZONE,
    compute_priority_key,
    is_queue_eligible,
    now_in_queue_tz,
)
from query_service.modules.tickets.queue_rules import load_queue_rules
from query_service.modules.tickets.repository import TicketRepository, TicketStatusHistoryRepository
from query_service.modules.tickets.schema import TicketCreateRequest, TicketResponse, TicketStatusHistoryResponse
from query_service.settings import settings

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(
        self,
        repository: TicketRepository = Depends(),
        service_repo: ServiceRepository = Depends(),
        slots_repo: SlotsRepository = Depends(),
        notifications: NotificationService = Depends(),
        history_repo: TicketStatusHistoryRepository = Depends(),
    ) -> None:
        self.repository = repository
        # TODO: we should not import repositories from other services directly - it can avoid necessary business logic
        self.service_repo = service_repo
        self.slots_repo = slots_repo
        self.notifications = notifications
        self.history_repo = history_repo

    async def record_status_change(self, ticket: Ticket, change: TicketStatusChange) -> None:
        if change.old_status == change.new_status:
            return

        history = TicketStatusHistory(
            ticket_id=ticket.id,
            old_status=change.old_status,
            new_status=change.new_status,
            reason=change.reason,
            staff_id=change.staff_id,
            window_id=change.window_id,
        )
        await self.history_repo.create(history)

    async def issue_ticket(
        self,
        department_id: UUID,
        request: TicketCreateRequest,
        staff_id: UUID | None = None,
    ) -> TicketResponse:
        service = await self.service_repo.get_by_id(request.service_id)

        if not service or service.department_id != department_id:
            raise ServiceNotFoundError
        if not service.is_active:
            raise InactiveServiceError
        if request.source == TicketSource.WEB and not request.slot_id:
            raise MissingSlotIdError
        if request.source != TicketSource.WEB and request.slot_id is not None:
            raise UnexpectedSlotIdError

        effective_start = now_in_queue_tz()
        slot_id: UUID | None = None

        if request.source == TicketSource.WEB and request.slot_id is not None:
            slot = await self.slots_repo.get_slot_in_department(department_id, request.slot_id)

            if slot is None:
                raise SlotNotFoundError
            if slot.service_id != request.service_id:
                raise SlotServiceMismatchError
            reserved = await self.slots_repo.try_increment_booked(request.slot_id)
            if not reserved:
                raise SlotFullError

            # slot_date/slot_time are wall-clock in queue timezone (Europe/Moscow by default)
            effective_start = datetime.combine(slot.slot_date, slot.slot_time, tzinfo=QUEUE_TIMEZONE)
            slot_id = request.slot_id

        priority_key = compute_priority_key(effective_start)

        prefix = service.kind.value
        next_number = await self.repository.get_next_ticket_number(department_id, prefix)
        ticket_label = f"{prefix}-{next_number:03d}"

        ticket_data = Ticket(
            department_id=department_id,
            service_id=request.service_id,
            slot_id=slot_id,
            source=request.source,
            priority_key=priority_key,
            ticket_label=ticket_label,
        )

        created_ticket = await self.repository.create(ticket_data)

        await self.record_status_change(
            created_ticket,
            TicketStatusChange(
                old_status=None,
                new_status=TicketStatus.QUEUED,
                reason=TicketStatusChangeReason.ISSUED,
                staff_id=staff_id,
            ),
        )

        return TicketResponse.model_validate(created_ticket)

    async def list_incomplete(self, department_id: UUID) -> list[TicketResponse]:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError

        tickets = await self.repository.list_incomplete(department_id)

        return [TicketResponse.model_validate(ticket) for ticket in tickets]

    async def get_ticket_info(self, department_id: UUID, ticket_id: UUID) -> TicketResponse:
        await self.expire_web_noshows(department_id)

        ticket = await self.repository.get_by_id(ticket_id)
        if not ticket or ticket.department_id != department_id:
            raise TicketNotFoundError

        estimated_wait_minutes = await self.estimate_wait_minutes(ticket)

        rules = await load_queue_rules(self.repository.session, department_id)
        if ticket.status == TicketStatus.QUEUED and is_queue_eligible(ticket.source, ticket.priority_key, rules):
            tickets_ahead = await self.repository.count_tickets_before(ticket)
            if tickets_ahead <= settings.notify_approaching_ahead:
                await self._enqueue_approaching(ticket, estimated_wait_minutes)

        response_data = TicketResponse.model_validate(ticket)
        response_data.estimated_wait_time = estimated_wait_minutes

        return response_data

    async def estimate_wait_minutes(self, ticket: Ticket) -> int:
        """Wait estimate for a queued ticket. Zero if not eligible."""
        rules = await load_queue_rules(self.repository.session, ticket.department_id)
        if ticket.status != TicketStatus.QUEUED or not is_queue_eligible(ticket.source, ticket.priority_key, rules):
            return 0

        service = await self.service_repo.get_by_id(ticket.service_id)
        duration = service.duration_time if service is not None else 10

        return await self.repository.count_tickets_before(ticket) * duration

    async def _enqueue_approaching(self, ticket: Ticket, estimated_wait_time: int) -> None:
        try:
            await self.notifications.enqueue_approaching(ticket, estimated_wait_time)
        except Exception:
            logger.exception("notification enqueue failed")

    async def cancel_ticket(self, department_id: UUID, ticket_id: UUID) -> TicketResponse:
        ticket = await self.repository.get_by_id_locked(ticket_id)

        if not ticket or ticket.department_id != department_id:
            raise TicketNotFoundError

        # CALLED / SERVING do their own thing, so for now we just avoid race conditions and cancel only queued types.
        if ticket.status != TicketStatus.QUEUED:
            raise InvalidTicketStateError

        slot_id = ticket.slot_id
        old_status = ticket.status
        ticket.status = TicketStatus.CANCELED
        ticket.canceled_at = datetime.now(UTC)
        await self.record_status_change(
            ticket,
            TicketStatusChange(
                old_status=old_status,
                new_status=TicketStatus.CANCELED,
                reason=TicketStatusChangeReason.CANCELED,
            ),
        )
        await self.repository.save()

        await self.release_slot(slot_id)

        return TicketResponse.model_validate(ticket)

    async def release_slot(self, slot_id: UUID | None) -> None:
        """Release booked slots."""
        if slot_id is not None:
            await self.slots_repo.try_decrement_booked(slot_id)

    async def expire_web_noshows(self, department_id: UUID) -> None:
        tickets = await self.repository.select_locked_web_noshows(department_id)
        if not tickets:
            return

        now = datetime.now(UTC)
        slot_ids: list[UUID] = []
        for ticket in tickets:
            old_status = ticket.status
            ticket.status = TicketStatus.CANCELED
            ticket.canceled_at = now
            await self.record_status_change(
                ticket,
                TicketStatusChange(
                    old_status=old_status,
                    new_status=TicketStatus.CANCELED,
                    reason=TicketStatusChangeReason.NOSHOW,
                ),
            )
            if ticket.slot_id is not None:
                slot_ids.append(ticket.slot_id)

        await self.repository.save()

        for slot_id in slot_ids:
            await self.release_slot(slot_id)

    async def requeue(
        self,
        ticket: Ticket,
        elapsed_seconds: int = 0,
        change: TicketStatusChange | None = None,
    ) -> Ticket:
        """Return CALLED/SERVING ticket to QUEUED. Caller must hold FOR UPDATE."""
        if ticket.status not in (TicketStatus.CALLED, TicketStatus.SERVING):
            raise InvalidTicketStateError

        if change is None:
            change = TicketStatusChange(
                old_status=ticket.status,
                new_status=TicketStatus.QUEUED,
                reason=TicketStatusChangeReason.REQUEUED,
                window_id=ticket.window_id,
            )
        else:
            change = TicketStatusChange(
                old_status=ticket.status,
                new_status=TicketStatus.QUEUED,
                reason=change.reason,
                staff_id=change.staff_id,
                window_id=change.window_id if change.window_id is not None else ticket.window_id,
            )

        ticket.status = TicketStatus.QUEUED
        ticket.window_id = None
        ticket.called_at = None
        ticket.started_at = None
        ticket.priority_key = max(0, ticket.priority_key - elapsed_seconds)

        await self.record_status_change(ticket, change)
        await self.repository.save()
        return ticket


class TicketStatusHistoryService:
    def __init__(
        self,
        history_repo: TicketStatusHistoryRepository = Depends(),
        ticket_repo: TicketRepository = Depends(),
    ) -> None:
        self.history_repo = history_repo
        self.ticket_repo = ticket_repo

    async def get_history(self, department_id: UUID, ticket_id: UUID) -> list[TicketStatusHistoryResponse]:
        ticket = await self.ticket_repo.get_by_id(ticket_id)

        if not ticket or ticket.department_id != department_id:
            raise TicketNotFoundError

        history = await self.history_repo.list_by_ticket_id(ticket_id)

        return [TicketStatusHistoryResponse.model_validate(h) for h in history]
