from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.ticket_status_history import TicketStatusChangeReason
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.tickets.service import TicketService
from query_service.modules.windows.exceptions import (
    EmptyQueueError,
    TicketAlreadyInProgressError,
    WindowClosedError,
    WindowHasNoServicesError,
    WindowNotFoundError,
)
from query_service.modules.windows.repository import WindowsRepository
from query_service.modules.windows.service import WindowsService


@pytest.fixture
def service() -> tuple[WindowsService, Mock, Mock]:
    repository = Mock(spec=WindowsRepository)
    repository.get_in_department = AsyncMock()
    repository.lock_window = AsyncMock()
    repository.ticket_exists_for_window = AsyncMock(return_value=False)
    repository.find_next_eligible_ticket = AsyncMock()
    repository.save = AsyncMock()
    repository.get_in_progress_ticket_locked = AsyncMock()

    tickets = Mock(spec=TicketService)
    tickets.expire_web_noshows = AsyncMock()
    tickets.requeue = AsyncMock()
    tickets.release_slot = AsyncMock()
    tickets.record_status_change = AsyncMock()

    notifications = Mock()
    notifications.enqueue_called = AsyncMock()
    notifications.enqueue_approaching_for_services = AsyncMock()

    svc = WindowsService(
        repository=cast(WindowsRepository, repository),
        tickets=cast(TicketService, tickets),
        notifications=notifications,
    )

    return svc, repository, tickets


@pytest.mark.asyncio
async def test_call_next_returns_next_ticket(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()
    service_id = uuid4()

    window = cast(
        Window,
        SimpleNamespace(
            id=window_id,
            department_id=department_id,
            status=WindowStatus.OPEN,
            services=[SimpleNamespace(id=service_id)],
            current_operator_id=None,
        ),
    )
    ticket = cast(
        Ticket,
        SimpleNamespace(id=uuid4(), status=TicketStatus.QUEUED, window_id=None, called_at=None),
    )

    repository.get_in_department.return_value = window
    repository.lock_window.return_value = window
    repository.find_next_eligible_ticket.return_value = ticket

    result = await svc.call_next(department_id, window_id)

    assert result is ticket
    repository.get_in_department.assert_awaited_once_with(department_id, window_id)
    tickets.expire_web_noshows.assert_awaited_once_with(department_id)
    repository.find_next_eligible_ticket.assert_awaited_once_with(window, [service_id])
    repository.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_next_succeeds_when_notification_enqueue_fails(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, _tickets = service

    department_id = uuid4()
    window_id = uuid4()
    service_id = uuid4()

    window = cast(
        Window,
        SimpleNamespace(
            id=window_id,
            department_id=department_id,
            status=WindowStatus.OPEN,
            services=[SimpleNamespace(id=service_id)],
            current_operator_id=None,
        ),
    )
    ticket = cast(
        Ticket,
        SimpleNamespace(id=uuid4(), status=TicketStatus.QUEUED, window_id=None, called_at=None),
    )

    repository.get_in_department.return_value = window
    repository.lock_window.return_value = window
    repository.find_next_eligible_ticket.return_value = ticket
    cast(Mock, svc.notifications).enqueue_called.side_effect = RuntimeError("outbox unavailable")

    result = await svc.call_next(department_id, window_id)

    assert result is ticket
    assert ticket.status == TicketStatus.CALLED
    repository.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_next_raises_when_window_not_found(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()

    repository.get_in_department.return_value = None

    with pytest.raises(WindowNotFoundError):
        await svc.call_next(department_id, window_id)

    tickets.expire_web_noshows.assert_not_awaited()
    repository.lock_window.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_raises_when_queue_is_empty(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()
    service_id = uuid4()

    window = cast(
        Window,
        SimpleNamespace(
            id=window_id,
            department_id=department_id,
            status=WindowStatus.OPEN,
            services=[SimpleNamespace(id=service_id)],
            current_operator_id=None,
        ),
    )

    repository.get_in_department.return_value = window
    repository.lock_window.return_value = window
    repository.find_next_eligible_ticket.return_value = None

    with pytest.raises(EmptyQueueError):
        await svc.call_next(department_id, window_id)

    tickets.expire_web_noshows.assert_awaited_once_with(department_id)
    repository.find_next_eligible_ticket.assert_awaited_once_with(window, [service_id])


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        ("closed", WindowClosedError),
        ("no_services", WindowHasNoServicesError),
        ("in_progress", TicketAlreadyInProgressError),
    ],
)
@pytest.mark.asyncio
async def test_call_next_raises_guard_errors(
    service: tuple[WindowsService, Mock, Mock],
    setup: str,
    error: type[Exception],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()
    service_id = uuid4()

    services = [] if setup == "no_services" else [SimpleNamespace(id=service_id)]
    status = WindowStatus.CLOSED if setup == "closed" else WindowStatus.OPEN

    window = cast(
        Window,
        SimpleNamespace(
            id=window_id,
            department_id=department_id,
            status=status,
            services=services,
        ),
    )

    repository.get_in_department.return_value = window
    repository.lock_window.return_value = window
    repository.ticket_exists_for_window.return_value = setup == "in_progress"

    with pytest.raises(error):
        await svc.call_next(department_id, window_id)

    tickets.expire_web_noshows.assert_awaited_once_with(department_id)
    repository.find_next_eligible_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_expires_web_no_shows_before_assigning_ticket(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()
    service_id = uuid4()

    window = cast(
        Window,
        SimpleNamespace(
            id=window_id,
            department_id=department_id,
            status=WindowStatus.OPEN,
            services=[SimpleNamespace(id=service_id)],
            current_operator_id=None,
        ),
    )
    ticket = cast(
        Ticket,
        SimpleNamespace(id=uuid4(), status=TicketStatus.QUEUED, window_id=None, called_at=None),
    )

    repository.get_in_department.return_value = window
    repository.lock_window.return_value = window
    repository.find_next_eligible_ticket.return_value = ticket

    call_order: list[str] = []

    async def expire_web_noshows(department_id: UUID) -> None:
        call_order.append("expire")

    async def find_next_eligible_ticket(current_window: Window, service_ids: list[UUID]) -> Ticket:
        call_order.append("assign")
        return ticket

    tickets.expire_web_noshows.side_effect = expire_web_noshows
    repository.find_next_eligible_ticket.side_effect = find_next_eligible_ticket

    result = await svc.call_next(department_id, window_id)

    assert result is ticket
    assert call_order == ["expire", "assign"]


@pytest.mark.asyncio
async def test_requeue_uses_ticket_service(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()
    window = cast(Window, SimpleNamespace(id=window_id, current_operator_id=None))
    ticket = cast(
        Ticket,
        SimpleNamespace(id=uuid4(), called_at=None),
    )
    requeued = cast(Ticket, SimpleNamespace(id=ticket.id, status="queued"))

    repository.get_in_department.return_value = window
    repository.get_in_progress_ticket_locked.return_value = ticket
    tickets.requeue.return_value = requeued

    result = await svc.requeue(department_id, window_id)

    assert result is requeued
    tickets.requeue.assert_awaited_once_with(
        ticket,
        0,
        reason=TicketStatusChangeReason.REQUEUED,
        staff_id=None,
        window_id=window_id,
    )


@pytest.mark.asyncio
async def test_redirect_converts_to_walk_in_and_releases_slot(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    from query_service.database.models.ticket import TicketSource
    from query_service.modules.windows.schema import WindowRedirectRequestDTO

    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()
    service_id = uuid4()
    slot_id = uuid4()

    window = cast(Window, SimpleNamespace(id=window_id, current_operator_id=None))
    ticket = cast(
        Ticket,
        SimpleNamespace(
            id=uuid4(),
            called_at=None,
            slot_id=slot_id,
            service_id=uuid4(),
            source=TicketSource.WEB,
            priority_key=1000,
        ),
    )
    requeued = cast(Ticket, SimpleNamespace(id=ticket.id, source=TicketSource.WALK_IN))

    repository.get_in_department.return_value = window
    repository.get_in_progress_ticket_locked.return_value = ticket

    services = Mock()
    services.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=service_id, department_id=department_id, is_active=True),
    )
    svc.services = services

    tickets.requeue.return_value = requeued

    result = await svc.redirect(
        department_id,
        window_id,
        WindowRedirectRequestDTO(service_id=service_id),
    )

    assert result is requeued
    assert ticket.service_id == service_id
    assert ticket.slot_id is None
    assert ticket.source == TicketSource.WALK_IN
    tickets.release_slot.assert_awaited_once_with(slot_id)
    tickets.requeue.assert_awaited_once_with(
        ticket,
        0,
        reason=TicketStatusChangeReason.REDIRECTED,
        staff_id=None,
        window_id=window_id,
    )


def _ticket_service_with_history() -> tuple[TicketService, Mock]:
    history_repo = Mock()
    history_repo.create = AsyncMock()
    svc = TicketService(
        repository=Mock(),
        service_repo=Mock(),
        slots_repo=Mock(),
        notifications=Mock(),
        history_repo=history_repo,
    )
    return svc, history_repo


@pytest.mark.asyncio
async def test_record_status_change_writes_history_row() -> None:
    svc, history_repo = _ticket_service_with_history()
    ticket_id = uuid4()
    window_id = uuid4()
    ticket = cast(Ticket, SimpleNamespace(id=ticket_id))

    await svc.record_status_change(
        ticket,
        TicketStatus.QUEUED,
        TicketStatus.CALLED,
        TicketStatusChangeReason.CALLED,
        staff_id=None,
        window_id=window_id,
    )

    history_repo.create.assert_awaited_once()
    row = history_repo.create.await_args.args[0]
    assert row.ticket_id == ticket_id
    assert row.old_status == TicketStatus.QUEUED
    assert row.new_status == TicketStatus.CALLED
    assert row.reason == TicketStatusChangeReason.CALLED
    assert row.window_id == window_id


@pytest.mark.asyncio
async def test_record_status_change_skips_when_status_unchanged() -> None:
    svc, history_repo = _ticket_service_with_history()
    ticket = cast(Ticket, SimpleNamespace(id=uuid4()))

    await svc.record_status_change(
        ticket,
        TicketStatus.QUEUED,
        TicketStatus.QUEUED,
        TicketStatusChangeReason.CALLED,
    )

    history_repo.create.assert_not_awaited()
