from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from query_service.database.models.ticket import Ticket
from query_service.database.models.window import Window
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
    repository.assign_next_ticket = AsyncMock()

    tickets = Mock(spec=TicketService)
    tickets.expire_web_noshows = AsyncMock()

    svc = WindowsService(
        repository=cast(WindowsRepository, repository),
        tickets=cast(TicketService, tickets),
    )

    return svc, repository, tickets


@pytest.mark.asyncio
async def test_call_next_returns_next_ticket(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()

    window = cast(Window, SimpleNamespace(id=window_id))
    ticket = cast(Ticket, SimpleNamespace(id=uuid4()))

    repository.get_in_department.return_value = window
    repository.assign_next_ticket.return_value = ticket

    result = await svc.call_next(department_id, window_id)

    assert result is ticket

    repository.get_in_department.assert_awaited_once_with(
        department_id,
        window_id,
    )
    tickets.expire_web_noshows.assert_awaited_once_with(
        department_id,
    )
    repository.assign_next_ticket.assert_awaited_once_with(
        window,
    )


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
    repository.assign_next_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_next_raises_when_queue_is_empty(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()

    window = cast(Window, SimpleNamespace(id=window_id))

    repository.get_in_department.return_value = window
    repository.assign_next_ticket.return_value = None

    with pytest.raises(EmptyQueueError):
        await svc.call_next(department_id, window_id)

    tickets.expire_web_noshows.assert_awaited_once_with(
        department_id,
    )
    repository.assign_next_ticket.assert_awaited_once_with(
        window,
    )


@pytest.mark.parametrize(
    "repository_error",
    [
        WindowClosedError,
        WindowHasNoServicesError,
        TicketAlreadyInProgressError,
    ],
)
@pytest.mark.asyncio
async def test_call_next_propagates_repository_errors(
    service: tuple[WindowsService, Mock, Mock],
    repository_error: type[Exception],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()

    window = cast(Window, SimpleNamespace(id=window_id))

    repository.get_in_department.return_value = window
    repository.assign_next_ticket.side_effect = repository_error()

    with pytest.raises(repository_error):
        await svc.call_next(department_id, window_id)

    tickets.expire_web_noshows.assert_awaited_once_with(department_id)
    repository.assign_next_ticket.assert_awaited_once_with(window)


@pytest.mark.asyncio
async def test_call_next_expires_web_no_shows_before_assigning_ticket(
    service: tuple[WindowsService, Mock, Mock],
) -> None:
    svc, repository, tickets = service

    department_id = uuid4()
    window_id = uuid4()

    window = cast(Window, SimpleNamespace(id=window_id))
    ticket = cast(Ticket, SimpleNamespace(id=uuid4()))

    repository.get_in_department.return_value = window
    repository.assign_next_ticket.return_value = ticket

    call_order: list[str] = []

    async def expire_web_noshows(department_id: UUID) -> None:
        call_order.append("expire")

    async def assign_next_ticket(current_window: Window) -> Ticket:
        call_order.append("assign")
        return ticket

    tickets.expire_web_noshows.side_effect = expire_web_noshows
    repository.assign_next_ticket.side_effect = assign_next_ticket

    result = await svc.call_next(department_id, window_id)

    assert result is ticket
    assert call_order == ["expire", "assign"]
