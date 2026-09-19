from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.tickets.priority import (
    BONUS_SECONDS,
    MAX_WAIT_SECONDS,
    now_priority_seconds,
)
from query_service.modules.windows.exceptions import TicketAlreadyInProgressError
from query_service.modules.windows.repository import WindowsRepository
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class QueueContext:
    department: Department
    other_department: Department
    service: Service
    other_service: Service
    window: Window
    other_window: Window


@pytest_asyncio.fixture
async def queue_context(dbsession: AsyncSession) -> QueueContext:
    department = Department(
        name=f"Test department {uuid4()}",
        address="Test address",
        open_time=time(8, 0),
        close_time=time(20, 0),
        is_active=True,
    )

    other_department = Department(
        name=f"Other department {uuid4()}",
        address="Other test address",
        open_time=time(8, 0),
        close_time=time(20, 0),
        is_active=True,
    )

    dbsession.add_all([department, other_department])
    await dbsession.flush()

    service = Service(
        department_id=department.id,
        name=f"Test service {uuid4()}",
        duration_time=10,
        is_active=True,
    )

    other_service = Service(
        department_id=department.id,
        name=f"Other service {uuid4()}",
        duration_time=10,
        is_active=True,
    )

    dbsession.add_all([service, other_service])
    await dbsession.flush()

    window = Window(
        department_id=department.id,
        label=f"Window {uuid4()}",
        status=WindowStatus.OPEN,
        services=[service],
    )

    other_window = Window(
        department_id=department.id,
        label=f"Other window {uuid4()}",
        status=WindowStatus.OPEN,
        services=[service],
    )

    dbsession.add_all([window, other_window])
    await dbsession.flush()

    return QueueContext(
        department=department,
        other_department=other_department,
        service=service,
        other_service=other_service,
        window=window,
        other_window=other_window,
    )


def make_ticket(
    *,
    department_id: UUID,
    service_id: UUID,
    source: TicketSource,
    priority_key: int,
    created_at: datetime,
    status: TicketStatus = TicketStatus.QUEUED,
    slot_id: UUID | None = None,
    window_id: UUID | None = None,
    label: str | None = None,
) -> Ticket:
    return Ticket(
        department_id=department_id,
        service_id=service_id,
        source=source,
        priority_key=priority_key,
        ticket_label=label or f"Ticket {uuid4()}",
        status=status,
        created_at=created_at,
        slot_id=slot_id,
        window_id=window_id,
    )


@pytest.mark.asyncio
async def test_assign_next_ticket_chooses_lowest_priority_key(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()
    created_at = datetime.now(UTC)

    worse = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 200,
        created_at=created_at,
        label="worse-priority",
    )

    better = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 100,
        created_at=created_at + timedelta(seconds=1),
        label="better-priority",
    )

    dbsession.add_all([worse, better])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.ticket_label == "better-priority"
    assert selected.id == better.id

    assert selected.status == TicketStatus.CALLED
    assert selected.window_id == queue_context.window.id
    assert selected.called_at is not None

    assert worse.status == TicketStatus.QUEUED


@pytest.mark.asyncio
async def test_assign_next_ticket_uses_created_at_as_tie_breaker(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()
    priority_key = now + 100

    older_created_at = datetime.now(UTC) - timedelta(minutes=5)
    newer_created_at = datetime.now(UTC) - timedelta(minutes=1)

    newer = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=priority_key,
        created_at=newer_created_at,
        label="newer",
    )

    older = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=priority_key,
        created_at=older_created_at,
        label="older",
    )

    dbsession.add_all([newer, older])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == older.id
    assert selected.ticket_label == "older"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [TicketSource.QR, TicketSource.WALK_IN],
)
async def test_assign_next_ticket_accepts_live_ticket_sources(
    dbsession: AsyncSession,
    queue_context: QueueContext,
    source: TicketSource,
) -> None:
    now = now_priority_seconds()

    ticket = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=source,
        priority_key=now + 100,
        created_at=datetime.now(UTC),
        label=f"live-{source}",
    )

    dbsession.add(ticket)
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == ticket.id
    assert selected.status == TicketStatus.CALLED


@pytest.mark.asyncio
async def test_assign_next_ticket_ignores_wrong_service(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()
    created_at = datetime.now(UTC)

    wrong_service = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.other_service.id,
        source=TicketSource.QR,
        priority_key=now - 100,
        created_at=created_at,
        label="wrong-service",
    )

    correct_service = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 100,
        created_at=created_at + timedelta(seconds=1),
        label="correct-service",
    )

    dbsession.add_all([wrong_service, correct_service])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == correct_service.id
    assert selected.ticket_label == "correct-service"
    assert wrong_service.status == TicketStatus.QUEUED


@pytest.mark.asyncio
async def test_assign_next_ticket_ignores_other_department(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()
    created_at = datetime.now(UTC)

    # Намеренно используем service из целевого department:
    # так тестируем именно Ticket.department_id == locked.department_id.
    wrong_department = make_ticket(
        department_id=queue_context.other_department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now - 100,
        created_at=created_at,
        label="wrong-department",
    )

    correct_department = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 100,
        created_at=created_at + timedelta(seconds=1),
        label="correct-department",
    )

    dbsession.add_all([wrong_department, correct_department])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == correct_department.id
    assert wrong_department.status == TicketStatus.QUEUED


@pytest.mark.asyncio
async def test_assign_next_ticket_ignores_ticket_for_another_window_slot(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()

    slot = Slot(
        window_id=queue_context.other_window.id,
        service_id=queue_context.service.id,
        slot_date=date.today(),
        slot_time=time(12, 0),
        capacity=1,
        booked_count=0,
    )

    dbsession.add(slot)
    await dbsession.flush()

    # WEB должен быть eligible, иначе тест проверял бы сразу две разные причины.
    web_bonus = BONUS_SECONDS[TicketSource.WEB]
    web_max_wait = MAX_WAIT_SECONDS[TicketSource.WEB]

    web_priority = now - web_bonus - web_max_wait // 2

    wrong_window = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.WEB,
        priority_key=web_priority,
        created_at=datetime.now(UTC),
        slot_id=slot.id,
        label="other-window-slot",
    )

    no_slot = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 100,
        created_at=datetime.now(UTC) + timedelta(seconds=1),
        label="no-slot",
    )

    dbsession.add_all([wrong_window, no_slot])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == no_slot.id
    assert wrong_window.status == TicketStatus.QUEUED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [TicketStatus.COMPLETED, TicketStatus.CANCELED],
)
async def test_assign_next_ticket_ignores_non_queued_ticket(
    dbsession: AsyncSession,
    queue_context: QueueContext,
    status: TicketStatus,
) -> None:
    now = now_priority_seconds()
    created_at = datetime.now(UTC)

    non_queued = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now - 100,
        created_at=created_at,
        status=status,
        label=f"non-queued-{status}",
    )

    queued = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 100,
        created_at=created_at + timedelta(seconds=1),
        status=TicketStatus.QUEUED,
        label="queued",
    )

    dbsession.add_all([non_queued, queued])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == queued.id
    assert non_queued.status == status


@pytest.mark.asyncio
async def test_assign_next_ticket_accepts_due_web_ticket(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()

    web_bonus = BONUS_SECONDS[TicketSource.WEB]
    web_max_wait = MAX_WAIT_SECONDS[TicketSource.WEB]

    # Находимся внутри диапазона:
    # priority <= now - bonus       -> ticket due
    # priority >= now - max - bonus -> ticket not expired
    priority_key = now - web_bonus - web_max_wait // 2

    ticket = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.WEB,
        priority_key=priority_key,
        created_at=datetime.now(UTC),
        label="web-due",
    )

    dbsession.add(ticket)
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == ticket.id
    assert selected.status == TicketStatus.CALLED


@pytest.mark.asyncio
async def test_assign_next_ticket_rejects_web_noshow(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()

    web_bonus = BONUS_SECONDS[TicketSource.WEB]
    web_max_wait = MAX_WAIT_SECONDS[TicketSource.WEB]

    priority_key = now - web_max_wait - web_bonus - 1

    ticket = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.WEB,
        priority_key=priority_key,
        created_at=datetime.now(UTC),
        label="web-noshow",
    )

    dbsession.add(ticket)
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is None
    assert ticket.status == TicketStatus.QUEUED


@pytest.mark.asyncio
async def test_assign_next_ticket_returns_none_when_no_eligible_tickets(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()

    wrong_service = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.other_service.id,
        source=TicketSource.QR,
        priority_key=now,
        created_at=datetime.now(UTC),
        label="wrong-service",
    )

    web_bonus = BONUS_SECONDS[TicketSource.WEB]
    web_max_wait = MAX_WAIT_SECONDS[TicketSource.WEB]

    expired_web = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.WEB,
        priority_key=now - web_max_wait - web_bonus - 1,
        created_at=datetime.now(UTC),
        label="expired-web",
    )

    completed = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now - 100,
        created_at=datetime.now(UTC),
        status=TicketStatus.COMPLETED,
        label="completed",
    )

    dbsession.add_all([wrong_service, expired_web, completed])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is None

    assert wrong_service.status == TicketStatus.QUEUED
    assert expired_web.status == TicketStatus.QUEUED
    assert completed.status == TicketStatus.COMPLETED


@pytest.mark.asyncio
async def test_assign_next_ticket_rejects_second_call_while_ticket_is_active(
    dbsession: AsyncSession,
    queue_context: QueueContext,
) -> None:
    now = now_priority_seconds()

    first = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 100,
        created_at=datetime.now(UTC),
        label="first",
    )

    second = make_ticket(
        department_id=queue_context.department.id,
        service_id=queue_context.service.id,
        source=TicketSource.QR,
        priority_key=now + 200,
        created_at=datetime.now(UTC) + timedelta(seconds=1),
        label="second",
    )

    dbsession.add_all([first, second])
    await dbsession.flush()

    repository = WindowsRepository(dbsession)

    selected = await repository.assign_next_ticket(queue_context.window)

    assert selected is not None
    assert selected.id == first.id

    with pytest.raises(TicketAlreadyInProgressError):
        await repository.assign_next_ticket(queue_context.window)

    assert first.status == TicketStatus.CALLED
    assert second.status == TicketStatus.QUEUED
