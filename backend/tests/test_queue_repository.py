from __future__ import annotations

from datetime import UTC
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.tickets.service import TicketService
from query_service.modules.windows.exceptions import (
    EmptyQueueError,
    TicketAlreadyInProgressError,
    WindowClosedError,
    WindowHasNoServicesError,
)
from query_service.modules.windows.repository import WindowsRepository
from query_service.modules.windows.service import WindowsService


@pytest.fixture
def call_next_service() -> tuple[WindowsService, Mock, Mock]:
    repository = Mock(spec=WindowsRepository)
    repository.get_in_department = AsyncMock()
    repository.lock_window = AsyncMock()
    repository.ticket_exists_for_window = AsyncMock(return_value=False)
    repository.find_next_eligible_ticket = AsyncMock()
    repository.save = AsyncMock()

    tickets = Mock(spec=TicketService)
    tickets.expire_web_noshows = AsyncMock()
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


@pytest.fixture
def open_window() -> Window:
    service_id = uuid4()

    return cast(
        Window,
        SimpleNamespace(
            id=uuid4(),
            department_id=uuid4(),
            status=WindowStatus.OPEN,
            services=[
                SimpleNamespace(id=service_id),
            ],
            current_operator_id=None,
        ),
    )


@pytest.mark.asyncio
async def test_call_next_raises_when_window_disappeared_after_lock(
    call_next_service: tuple[WindowsService, Mock, Mock],
    open_window: Window,
) -> None:
    svc, repository, tickets = call_next_service

    repository.get_in_department.return_value = open_window
    repository.lock_window.return_value = None

    with pytest.raises(EmptyQueueError):
        await svc.call_next(open_window.department_id, open_window.id)

    tickets.expire_web_noshows.assert_awaited_once()
    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_rechecks_window_status_after_lock(
    call_next_service: tuple[WindowsService, Mock, Mock],
    open_window: Window,
) -> None:
    svc, repository, _tickets = call_next_service

    repository.get_in_department.return_value = open_window
    repository.lock_window.return_value = cast(
        Window,
        SimpleNamespace(
            id=open_window.id,
            department_id=open_window.department_id,
            status=WindowStatus.CLOSED,
            services=open_window.services,
        ),
    )

    with pytest.raises(WindowClosedError):
        await svc.call_next(open_window.department_id, open_window.id)

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_rejects_active_ticket(
    call_next_service: tuple[WindowsService, Mock, Mock],
    open_window: Window,
) -> None:
    svc, repository, _tickets = call_next_service

    repository.get_in_department.return_value = open_window
    repository.lock_window.return_value = open_window
    repository.ticket_exists_for_window.return_value = True

    with pytest.raises(TicketAlreadyInProgressError):
        await svc.call_next(open_window.department_id, open_window.id)

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_rejects_window_without_services(
    call_next_service: tuple[WindowsService, Mock, Mock],
    open_window: Window,
) -> None:
    svc, repository, _tickets = call_next_service

    empty_window = cast(
        Window,
        SimpleNamespace(
            id=open_window.id,
            department_id=open_window.department_id,
            status=WindowStatus.OPEN,
            services=[],
        ),
    )

    repository.get_in_department.return_value = empty_window
    repository.lock_window.return_value = empty_window

    with pytest.raises(WindowHasNoServicesError):
        await svc.call_next(empty_window.department_id, empty_window.id)

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_raises_when_no_matching_ticket_exists(
    call_next_service: tuple[WindowsService, Mock, Mock],
    open_window: Window,
) -> None:
    svc, repository, _tickets = call_next_service

    repository.get_in_department.return_value = open_window
    repository.lock_window.return_value = open_window
    repository.find_next_eligible_ticket.return_value = None

    with pytest.raises(EmptyQueueError):
        await svc.call_next(open_window.department_id, open_window.id)

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_marks_selected_ticket_as_called(
    call_next_service: tuple[WindowsService, Mock, Mock],
    open_window: Window,
) -> None:
    svc, repository, _tickets = call_next_service

    ticket = cast(
        Ticket,
        SimpleNamespace(
            id=uuid4(),
            status=TicketStatus.QUEUED,
            window_id=None,
            called_at=None,
        ),
    )

    repository.get_in_department.return_value = open_window
    repository.lock_window.return_value = open_window
    repository.find_next_eligible_ticket.return_value = ticket

    result = await svc.call_next(open_window.department_id, open_window.id)

    assert result is ticket
    assert ticket.status == TicketStatus.CALLED
    assert ticket.window_id == open_window.id
    assert ticket.called_at is not None
    assert ticket.called_at.tzinfo == UTC
    repository.save.assert_awaited_once()
