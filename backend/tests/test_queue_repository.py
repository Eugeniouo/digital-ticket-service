from __future__ import annotations

from datetime import UTC
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.windows.exceptions import (
    TicketAlreadyInProgressError,
    WindowClosedError,
    WindowHasNoServicesError,
)
from query_service.modules.windows.repository import WindowsRepository
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def repository() -> tuple[WindowsRepository, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)

    repo = WindowsRepository(
        session=cast(AsyncSession, session),
    )

    return repo, session


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
        ),
    )


@pytest.mark.asyncio
async def test_assign_next_ticket_returns_none_when_window_disappeared(
    repository: tuple[WindowsRepository, AsyncMock],
    open_window: Window,
) -> None:
    repo, session = repository

    session.scalar.return_value = None

    result = await repo.assign_next_ticket(open_window)

    assert result is None
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_next_ticket_rechecks_window_status_after_lock(
    repository: tuple[WindowsRepository, AsyncMock],
    open_window: Window,
) -> None:
    repo, session = repository

    locked_window = cast(
        Window,
        SimpleNamespace(
            id=open_window.id,
            department_id=open_window.department_id,
            status=WindowStatus.CLOSED,
            services=open_window.services,
        ),
    )

    session.scalar.return_value = locked_window

    with pytest.raises(WindowClosedError):
        await repo.assign_next_ticket(open_window)

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_next_ticket_rejects_active_ticket(
    repository: tuple[WindowsRepository, AsyncMock],
    open_window: Window,
) -> None:
    repo, session = repository

    locked_window = cast(
        Window,
        SimpleNamespace(
            id=open_window.id,
            department_id=open_window.department_id,
            status=WindowStatus.OPEN,
            services=open_window.services,
        ),
    )

    session.scalar.side_effect = [
        locked_window,
        uuid4(),  # уже есть CALLED/SERVING ticket
    ]

    with pytest.raises(TicketAlreadyInProgressError):
        await repo.assign_next_ticket(open_window)

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_next_ticket_rejects_window_without_services(
    repository: tuple[WindowsRepository, AsyncMock],
    open_window: Window,
) -> None:
    repo, session = repository

    locked_window = cast(
        Window,
        SimpleNamespace(
            id=open_window.id,
            department_id=open_window.department_id,
            status=WindowStatus.OPEN,
            services=[],
        ),
    )

    session.scalar.side_effect = [
        locked_window,
        None,
    ]

    with pytest.raises(WindowHasNoServicesError):
        await repo.assign_next_ticket(open_window)

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_next_ticket_returns_none_when_no_matching_ticket_exists(
    repository: tuple[WindowsRepository, AsyncMock],
    open_window: Window,
) -> None:
    repo, session = repository

    locked_window = cast(
        Window,
        SimpleNamespace(
            id=open_window.id,
            department_id=open_window.department_id,
            status=WindowStatus.OPEN,
            services=open_window.services,
        ),
    )

    session.scalar.side_effect = [
        locked_window,
        None,
        None,
    ]

    result = await repo.assign_next_ticket(open_window)

    assert result is None
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_next_ticket_marks_selected_ticket_as_called(
    repository: tuple[WindowsRepository, AsyncMock],
    open_window: Window,
) -> None:
    repo, session = repository

    locked_window = cast(
        Window,
        SimpleNamespace(
            id=open_window.id,
            department_id=open_window.department_id,
            status=WindowStatus.OPEN,
            services=open_window.services,
        ),
    )

    ticket = cast(
        Ticket,
        SimpleNamespace(
            id=uuid4(),
            status=TicketStatus.QUEUED,
            window_id=None,
            called_at=None,
        ),
    )

    session.scalar.side_effect = [
        locked_window,
        None,
        ticket,
    ]

    result = await repo.assign_next_ticket(open_window)

    assert result is ticket
    assert ticket.status == TicketStatus.CALLED
    assert ticket.window_id == open_window.id

    assert ticket.called_at is not None
    assert ticket.called_at.tzinfo == UTC

    session.flush.assert_awaited_once()
