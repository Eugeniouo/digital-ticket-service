from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.ticket_status_history import TicketStatusChangeReason, TicketStatusHistory
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.analytics.compute import day_bounds
from query_service.modules.analytics.repository import AnalyticsRepository
from sqlalchemy.ext.asyncio import AsyncSession

MOSCOW = ZoneInfo("Europe/Moscow")
DAY = date(2026, 9, 21)


async def _office(session: AsyncSession, name: str) -> tuple[Department, Service, Window]:
    department = Department(
        address="Street",
        open_time=time(9),
        close_time=time(18),
        is_active=True,
    )
    session.add(department)
    await session.flush()

    service = Service(department_id=department.id, name=f"Service {uuid4()}", duration_time=10, is_active=True)
    session.add(service)
    await session.flush()

    window = Window(department_id=department.id, label="1", status=WindowStatus.CLOSED)
    session.add(window)
    await session.flush()

    return department, service, window


def _ticket(
    department_id: UUID,
    service_id: UUID,
    source: TicketSource,
    label: str,
    created_at: datetime,
    *,
    status: TicketStatus = TicketStatus.QUEUED,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    canceled_at: datetime | None = None,
    slot_id: UUID | None = None,
) -> Ticket:
    return Ticket(
        department_id=department_id,
        service_id=service_id,
        slot_id=slot_id,
        source=source,
        status=status,
        priority_key=1,
        ticket_label=label,
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        canceled_at=canceled_at,
    )


async def test_completed_follow_the_department_day(dbsession: AsyncSession) -> None:
    department, service, window = await _office(dbsession, "Moscow")
    other, other_service, _other_window = await _office(dbsession, "Other")
    slot = Slot(window_id=window.id, service_id=service.id, slot_date=DAY, slot_time=time(10, 0))
    dbsession.add(slot)
    await dbsession.flush()

    # 23:30 UTC on the 20th is 02:30 on the 21st in Moscow.
    completed_at = datetime(2026, 9, 20, 23, 30, tzinfo=UTC)
    started_at = datetime(2026, 9, 20, 23, 20, tzinfo=UTC)
    ours = _ticket(
        department.id,
        service.id,
        TicketSource.WEB,
        "A-001",
        datetime(2026, 9, 19, 9, 0, tzinfo=UTC),
        status=TicketStatus.COMPLETED,
        started_at=started_at,
        completed_at=completed_at,
        slot_id=slot.id,
    )
    canceled = _ticket(
        department.id,
        service.id,
        TicketSource.QR,
        "A-002",
        completed_at,
        status=TicketStatus.CANCELED,
        completed_at=completed_at,
        canceled_at=completed_at,
    )
    foreign = _ticket(
        other.id,
        other_service.id,
        TicketSource.QR,
        "B-001",
        completed_at,
        status=TicketStatus.COMPLETED,
        started_at=started_at,
        completed_at=completed_at,
    )
    dbsession.add_all([ours, canceled, foreign])
    await dbsession.flush()

    repository = AnalyticsRepository(dbsession)
    start, end = day_bounds(DAY, MOSCOW)
    previous_start, previous_end = day_bounds(date(2026, 9, 20), MOSCOW)

    found = await repository.list_completed(department.id, start, end)
    previous = await repository.list_completed(department.id, previous_start, previous_end)

    assert [item.ticket_id for item in found] == [ours.id]
    assert found[0].slot_date == DAY
    assert found[0].slot_time == time(10, 0)
    assert found[0].source == TicketSource.WEB
    assert previous == []


async def test_arrivals_use_slot_date_for_appointments_and_issue_time_otherwise(dbsession: AsyncSession) -> None:
    department, service, window = await _office(dbsession, "Arrivals")
    today_slot = Slot(window_id=window.id, service_id=service.id, slot_date=DAY, slot_time=time(10, 0))
    tomorrow_slot = Slot(window_id=window.id, service_id=service.id, slot_date=date(2026, 9, 22), slot_time=time(10, 0))
    dbsession.add_all([today_slot, tomorrow_slot])
    await dbsession.flush()

    start, end = day_bounds(DAY, MOSCOW)
    booked_for_today = _ticket(
        department.id,
        service.id,
        TicketSource.WEB,
        "W-1",
        datetime(2026, 9, 20, 9, 0, tzinfo=MOSCOW),
        status=TicketStatus.CANCELED,
        canceled_at=datetime(2026, 9, 20, 12, 0, tzinfo=MOSCOW),
        slot_id=today_slot.id,
    )
    booked_on_today_for_tomorrow = _ticket(
        department.id,
        service.id,
        TicketSource.WEB,
        "W-2",
        datetime(2026, 9, 21, 12, 0, tzinfo=MOSCOW),
        slot_id=tomorrow_slot.id,
    )
    live_qr = _ticket(department.id, service.id, TicketSource.QR, "Q-1", datetime(2026, 9, 21, 15, 0, tzinfo=MOSCOW))
    canceled_qr = _ticket(
        department.id,
        service.id,
        TicketSource.QR,
        "Q-2",
        datetime(2026, 9, 21, 16, 0, tzinfo=MOSCOW),
        status=TicketStatus.CANCELED,
        canceled_at=datetime(2026, 9, 21, 16, 5, tzinfo=MOSCOW),
    )
    next_midnight = _ticket(department.id, service.id, TicketSource.WALK_IN, "L-1", end)
    dbsession.add_all([booked_for_today, booked_on_today_for_tomorrow, live_qr, canceled_qr, next_midnight])
    await dbsession.flush()

    repository = AnalyticsRepository(dbsession)
    today = await repository.count_arrivals(department.id, DAY, start, end)
    tomorrow_start, tomorrow_end = day_bounds(date(2026, 9, 22), MOSCOW)
    tomorrow = await repository.count_arrivals(department.id, date(2026, 9, 22), tomorrow_start, tomorrow_end)

    assert today[TicketSource.WEB] == 1
    assert today[TicketSource.QR] == 2
    assert today.get(TicketSource.WALK_IN, 0) == 0
    assert tomorrow[TicketSource.WEB] == 1
    assert tomorrow[TicketSource.WALK_IN] == 1
    assert tomorrow.get(TicketSource.QR, 0) == 0


async def test_redirect_keeps_the_channel_from_issue(dbsession: AsyncSession) -> None:
    department, service, window = await _office(dbsession, "Redirect")
    slot = Slot(window_id=window.id, service_id=service.id, slot_date=DAY, slot_time=time(10, 0))
    dbsession.add(slot)
    await dbsession.flush()

    start, end = day_bounds(DAY, MOSCOW)
    appointment = _ticket(
        department.id,
        service.id,
        TicketSource.WALK_IN,
        "W-9",
        datetime(2026, 9, 19, 9, 0, tzinfo=MOSCOW),
        slot_id=None,
    )
    appointment.origin_source = TicketSource.WEB
    appointment.origin_slot_id = slot.id
    qr = _ticket(
        department.id,
        service.id,
        TicketSource.WALK_IN,
        "Q-9",
        datetime(2026, 9, 21, 15, 0, tzinfo=MOSCOW),
    )
    qr.origin_source = TicketSource.QR
    dbsession.add_all([appointment, qr])
    await dbsession.flush()

    counts = await AnalyticsRepository(dbsession).count_arrivals(department.id, DAY, start, end)

    assert counts[TicketSource.WEB] == 1
    assert counts[TicketSource.QR] == 1
    assert counts.get(TicketSource.WALK_IN, 0) == 0


async def test_history_keeps_a_start_older_than_the_one_day_margin(dbsession: AsyncSession) -> None:
    department, service, window = await _office(dbsession, "Margin")
    started_at = datetime(2026, 9, 19, 15, 0, tzinfo=UTC)
    completed_at = datetime(2026, 9, 20, 23, 30, tzinfo=UTC)
    ticket = _ticket(
        department.id,
        service.id,
        TicketSource.QR,
        "M-1",
        started_at,
        status=TicketStatus.COMPLETED,
        started_at=started_at,
        completed_at=completed_at,
    )
    dbsession.add(ticket)
    await dbsession.flush()
    dbsession.add_all(
        [
            TicketStatusHistory(
                ticket_id=ticket.id,
                old_status=TicketStatus.CALLED,
                new_status=TicketStatus.SERVING,
                reason=TicketStatusChangeReason.STARTED,
                window_id=window.id,
                changed_at=started_at,
            ),
            TicketStatusHistory(
                ticket_id=ticket.id,
                old_status=TicketStatus.SERVING,
                new_status=TicketStatus.COMPLETED,
                reason=TicketStatusChangeReason.COMPLETED,
                window_id=window.id,
                changed_at=completed_at,
            ),
        ],
    )
    await dbsession.flush()

    start, end = day_bounds(DAY, MOSCOW)
    rows = await AnalyticsRepository(dbsession).list_history(department.id, start, end)
    starts = [row for row in rows if row.new_status == TicketStatus.SERVING]

    assert len(starts) == 1
    assert starts[0].changed_at == started_at
    assert starts[0].window_id == window.id


async def test_history_includes_a_visit_that_spans_the_day_without_events_inside_it(dbsession: AsyncSession) -> None:
    department, service, window = await _office(dbsession, "Span")
    started_at = datetime(2026, 9, 17, 21, 0, tzinfo=UTC)
    completed_at = datetime(2026, 9, 24, 21, 0, tzinfo=UTC)
    ticket = _ticket(
        department.id,
        service.id,
        TicketSource.WALK_IN,
        "S-1",
        started_at,
        status=TicketStatus.COMPLETED,
        started_at=started_at,
        completed_at=completed_at,
    )
    dbsession.add(ticket)
    await dbsession.flush()
    dbsession.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            old_status=TicketStatus.CALLED,
            new_status=TicketStatus.SERVING,
            reason=TicketStatusChangeReason.STARTED,
            window_id=window.id,
            changed_at=started_at,
        ),
    )
    await dbsession.flush()

    start, end = day_bounds(DAY, MOSCOW)
    rows = await AnalyticsRepository(dbsession).list_history(department.id, start, end)

    assert [row.changed_at for row in rows if row.new_status == TicketStatus.SERVING] == [started_at]
