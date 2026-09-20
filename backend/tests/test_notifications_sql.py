from __future__ import annotations

from datetime import UTC, datetime, time
from types import SimpleNamespace
from uuid import uuid4

from query_service.database.models.department import Department
from query_service.database.models.notification_outbox import NotificationOutboxStatus
from query_service.database.models.service import Service
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.window import Window, WindowStatus
from query_service.integrations.notifications.exceptions import NotificationDeliveryError
from query_service.integrations.notifications.port import NotificationEvent, NotificationMessage
from query_service.modules.notifications.repository import NotificationRepository
from query_service.modules.notifications.service import NotificationService
from query_service.modules.notifications.worker import process_due_rows
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.slots.repository import SlotsRepository
from query_service.modules.tickets.priority import now_priority_seconds
from query_service.modules.tickets.repository import TicketRepository
from query_service.modules.tickets.service import TicketService
from query_service.modules.windows.repository import WindowsRepository
from query_service.modules.windows.service import WindowsService
from query_service.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession


def _make_windows_service(dbsession: AsyncSession) -> WindowsService:
    ticket_repo = TicketRepository(dbsession)
    notifications = NotificationService(
        repository=NotificationRepository(dbsession),
        tickets=ticket_repo,
    )

    return WindowsService(
        repository=WindowsRepository(dbsession),
        tickets=TicketService(
            repository=ticket_repo,
            service_repo=ServiceRepository(dbsession),
            slots_repo=SlotsRepository(dbsession),
            notifications=notifications,
        ),
        services=ServiceRepository(dbsession),
        notifications=notifications,
    )


async def _seed_queue(dbsession: AsyncSession) -> tuple[Department, Service, Window, Ticket]:
    department = Department(
        name=f"Notify department {uuid4()}",
        address="Test address",
        open_time=time(8, 0),
        close_time=time(20, 0),
        is_active=True,
    )
    dbsession.add(department)
    await dbsession.flush()

    service = Service(
        department_id=department.id,
        name=f"Notify service {uuid4()}",
        duration_time=10,
        is_active=True,
    )
    dbsession.add(service)
    await dbsession.flush()

    window = Window(
        department_id=department.id,
        label=f"Window {uuid4()}",
        status=WindowStatus.OPEN,
        services=[service],
    )
    dbsession.add(window)
    await dbsession.flush()

    ticket = Ticket(
        department_id=department.id,
        service_id=service.id,
        source=TicketSource.WALK_IN,
        priority_key=now_priority_seconds(),
        ticket_label="N1",
        status=TicketStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    dbsession.add(ticket)
    await dbsession.flush()

    return department, service, window, ticket


async def test_call_next_keeps_ticket_when_adapter_fails(dbsession: AsyncSession) -> None:
    department, _service, window, ticket = await _seed_queue(dbsession)
    service = _make_windows_service(dbsession)

    selected = await service.call_next(department.id, window.id)

    assert selected.id == ticket.id
    assert selected.status == TicketStatus.CALLED

    async def send(_message: NotificationMessage) -> None:
        raise NotificationDeliveryError("unavailable")

    await process_due_rows(dbsession, SimpleNamespace(send=send), settings)

    await dbsession.refresh(ticket)
    rows = await NotificationRepository(dbsession).list_for_ticket(ticket.id)
    called_rows = [row for row in rows if row.event_type == NotificationEvent.TICKET_CALLED]

    assert ticket.status == TicketStatus.CALLED
    assert len(called_rows) == 1
    assert called_rows[0].status != NotificationOutboxStatus.SENT
    assert called_rows[0].status == NotificationOutboxStatus.PENDING


async def test_enqueue_approaching_is_idempotent(dbsession: AsyncSession) -> None:
    _department, _service, _window, ticket = await _seed_queue(dbsession)
    notifications = NotificationService(
        repository=NotificationRepository(dbsession),
        tickets=TicketRepository(dbsession),
    )

    await notifications.enqueue_approaching(ticket, 1)
    await notifications.enqueue_approaching(ticket, 5)

    rows = await notifications.repository.list_for_ticket(ticket.id)

    assert len(rows) == 1
    assert rows[0].event_type == NotificationEvent.QUEUE_APPROACHING
    assert rows[0].payload["estimated_wait_time"] == 1
