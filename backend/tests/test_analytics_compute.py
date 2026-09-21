from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from query_service.database.models.ticket import TicketSource, TicketStatus
from query_service.database.models.ticket_status_history import TicketStatusChangeReason
from query_service.modules.analytics.compute import (
    CompletedVisit,
    HistoryPoint,
    WindowRef,
    build_day_analytics,
    day_bounds,
    schedule_open_seconds,
)
from query_service.modules.analytics.schema import DayAnalyticsResponse

MOSCOW = ZoneInfo("Europe/Moscow")
DAY = date(2026, 9, 20)
NEXT_DAY = datetime(2026, 9, 21, 15, tzinfo=MOSCOW)
DEPT = UUID(int=1)
WINDOW_A = UUID(int=10)
WINDOW_B = UUID(int=11)


def at(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute, second), tzinfo=MOSCOW)


def visit(
    ticket_id: UUID,
    source: TicketSource,
    started: datetime | None,
    completed: datetime,
    *,
    called: datetime | None = None,
    slot_day: date | None = None,
    slot_at: time | None = None,
) -> CompletedVisit:
    return CompletedVisit(
        ticket_id=ticket_id,
        source=source,
        started_at=started,
        called_at=called,
        completed_at=completed,
        slot_date=slot_day,
        slot_time=slot_at,
    )


def event(  # noqa: PLR0917
    ticket_id: UUID,
    status: TicketStatus,
    reason: TicketStatusChangeReason,
    moment: datetime,
    event_id: int,
    window_id: UUID | None = None,
) -> HistoryPoint:
    return HistoryPoint(
        ticket_id=ticket_id,
        new_status=status,
        reason=reason,
        window_id=window_id,
        changed_at=moment,
        id=UUID(int=event_id),
    )


def report(
    *,
    day: date = DAY,
    open_at: time = time(9),
    close_at: time = time(18),
    now: datetime = NEXT_DAY,
    completed: Sequence[CompletedVisit] = (),
    history: Sequence[HistoryPoint] = (),
    sources: Mapping[TicketSource, int] | None = None,
    windows: Sequence[WindowRef] | None = None,
) -> DayAnalyticsResponse:
    return build_day_analytics(
        department_id=DEPT,
        day=day,
        timezone_name="Europe/Moscow",
        tz=MOSCOW,
        open_time=open_at,
        close_time=close_at,
        now=now,
        completed=completed,
        history=history,
        source_counts={} if sources is None else sources,
        windows=(WindowRef(WINDOW_A, "1"),) if windows is None else windows,
    )


def test_day_bounds_follow_department_timezone() -> None:
    start, end = day_bounds(date(2026, 9, 21), MOSCOW)

    assert start == datetime(2026, 9, 20, 21, tzinfo=UTC)
    assert end - start == timedelta(days=1)


def test_hourly_axis_is_every_clock_hour() -> None:
    ticket = UUID(int=100)
    done = report(
        completed=[visit(ticket, TicketSource.WALK_IN, at(DAY, 18, 5), at(DAY, 18, 10))],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY, 18, 0), 1),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 18, 5), 2, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 18, 10), 3, WINDOW_A),
        ],
    )

    assert [item.hour for item in done.hourly] == list(range(24))
    assert sum(item.served_count for item in done.hourly) == done.served_count == 1
    assert done.hourly[18].served_count == 1
    assert done.hourly[9].served_count == 0
    assert done.hourly[0].served_count == 0


def test_wait_includes_the_gap_between_call_and_start() -> None:
    ticket = UUID(int=101)
    done = report(
        completed=[visit(ticket, TicketSource.QR, at(DAY, 10, 7), at(DAY, 10, 10))],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY, 10, 0), 1),
            event(ticket, TicketStatus.CALLED, TicketStatusChangeReason.CALLED, at(DAY, 10, 4), 2, WINDOW_A),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 10, 7), 3, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 10, 10), 4, WINDOW_A),
        ],
    )

    assert done.avg_wait_seconds == 7 * 60
    assert done.max_wait_seconds == 7 * 60
    assert done.avg_service_seconds == 3 * 60


def test_web_wait_starts_at_the_slot_not_at_booking() -> None:
    ticket = UUID(int=102)
    booked = DAY - timedelta(days=3)
    done = report(
        completed=[
            visit(
                ticket,
                TicketSource.WEB,
                at(DAY, 10, 7),
                at(DAY, 10, 20),
                slot_day=DAY,
                slot_at=time(10, 0),
            ),
        ],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(booked, 12, 0), 1),
            event(ticket, TicketStatus.CALLED, TicketStatusChangeReason.CALLED, at(DAY, 10, 5), 2, WINDOW_A),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 10, 7), 3, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 10, 20), 4, WINDOW_A),
        ],
    )

    assert done.avg_wait_seconds == 7 * 60
    assert done.avg_service_seconds == 13 * 60


def test_early_appointment_contributes_zero_wait() -> None:
    ticket = UUID(int=103)
    done = report(
        completed=[
            visit(ticket, TicketSource.WEB, at(DAY, 9, 50), at(DAY, 10, 5), slot_day=DAY, slot_at=time(10, 0)),
        ],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY - timedelta(days=1), 9, 0), 1),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 9, 50), 2, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 10, 5), 3, WINDOW_A),
        ],
    )

    assert done.served_count == 1
    assert done.avg_wait_seconds == 0
    assert done.max_wait_seconds == 0


def test_web_without_slot_is_served_but_excluded_from_wait() -> None:
    ticket = UUID(int=104)
    done = report(
        completed=[visit(ticket, TicketSource.WEB, at(DAY, 10, 5), at(DAY, 10, 10))],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY, 10, 0), 1),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 10, 5), 2, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 10, 10), 3, WINDOW_A),
        ],
    )

    assert done.served_count == 1
    assert done.avg_wait_seconds is None
    assert done.max_wait_seconds is None
    assert done.avg_service_seconds == 5 * 60


def test_requeue_wait_and_service_use_the_last_visit_only() -> None:
    ticket = UUID(int=105)
    done = report(
        completed=[visit(ticket, TicketSource.WALK_IN, at(DAY, 9, 40), at(DAY, 9, 50))],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY, 9, 0), 1),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 9, 10), 2, WINDOW_A),
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.REQUEUED, at(DAY, 9, 20), 3, WINDOW_A),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 9, 40), 4, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 9, 50), 5, WINDOW_A),
        ],
    )

    assert done.avg_wait_seconds == 20 * 60
    assert done.avg_service_seconds == 10 * 60
    assert done.windows[0].served_seconds == 20 * 60


def test_redirect_wait_starts_when_the_client_was_sent_back() -> None:
    ticket = UUID(int=106)
    done = report(
        completed=[visit(ticket, TicketSource.WALK_IN, at(DAY, 11, 30), at(DAY, 11, 40))],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY - timedelta(days=2), 8, 0), 1),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 11, 0), 2, WINDOW_A),
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.REDIRECTED, at(DAY, 11, 10), 3, WINDOW_A),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 11, 30), 4, WINDOW_B),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 11, 40), 5, WINDOW_B),
        ],
        windows=(WindowRef(WINDOW_A, "1"), WindowRef(WINDOW_B, "2")),
    )

    assert done.avg_wait_seconds == 20 * 60
    assert done.windows[0].served_seconds == 10 * 60
    assert done.windows[1].served_seconds == 10 * 60


def test_average_rounds_half_up() -> None:
    first = UUID(int=107)
    second = UUID(int=108)
    done = report(
        completed=[
            visit(first, TicketSource.QR, at(DAY, 10, 0, 1), at(DAY, 10, 0, 2)),
            visit(second, TicketSource.QR, at(DAY, 11, 0, 2), at(DAY, 11, 0, 4)),
        ],
        history=[
            event(first, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY, 10, 0, 0), 1),
            event(first, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 10, 0, 1), 2, WINDOW_A),
            event(first, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 10, 0, 2), 3, WINDOW_A),
            event(second, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY, 11, 0, 0), 4),
            event(second, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 11, 0, 2), 5, WINDOW_A),
            event(second, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 11, 0, 4), 6, WINDOW_A),
        ],
    )

    assert done.avg_wait_seconds == 2
    assert done.max_wait_seconds == 2
    assert done.avg_service_seconds == 2
    assert sum(item.served_count for item in done.hourly) == 2


def test_empty_day_has_null_durations_and_a_full_chart() -> None:
    done = report(sources={TicketSource.QR: 3})

    assert done.served_count == 0
    assert done.avg_wait_seconds is None
    assert done.max_wait_seconds is None
    assert done.avg_service_seconds is None
    assert [item.hour for item in done.hourly] == list(range(24))
    assert sum(item.served_count for item in done.hourly) == 0
    assert [item.source for item in done.sources] == ["appointment", "qr", "walk-in"]
    assert [item.count for item in done.sources] == [0, 3, 0]
    assert done.windows[0].served_seconds == 0
    assert done.windows[0].schedule_open_seconds == 9 * 3600
    assert done.windows[0].load_ratio == 0


def test_completion_on_another_day_is_ignored() -> None:
    ticket = UUID(int=109)
    other = DAY - timedelta(days=1)
    done = report(completed=[visit(ticket, TicketSource.QR, at(other, 10, 0), at(other, 10, 5))])

    assert done.served_count == 0
    assert done.avg_service_seconds is None
    assert sum(item.served_count for item in done.hourly) == 0


def test_segment_crossing_midnight_is_split_between_days() -> None:
    ticket = UUID(int=110)
    history = [
        event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 23, 30), 1, WINDOW_A),
        event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY + timedelta(days=1), 0, 30), 2, WINDOW_A),
    ]

    first = report(history=history)
    second = report(day=DAY + timedelta(days=1), history=history)

    assert first.windows[0].served_seconds == 30 * 60
    assert second.windows[0].served_seconds == 30 * 60


def test_past_day_does_not_absorb_serving_after_midnight() -> None:
    ticket = UUID(int=111)
    now = at(DAY + timedelta(days=1), 0, 30)
    history = [event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 23, 30), 1, WINDOW_A)]

    done = report(now=now, history=history)

    assert done.windows[0].served_seconds == 30 * 60


def test_current_day_open_segment_stops_at_now() -> None:
    ticket = UUID(int=112)
    today = date(2026, 9, 21)
    now = at(today, 10, 20)
    done = report(
        day=today,
        now=now,
        history=[event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(today, 10, 0), 1, WINDOW_A)],
    )

    assert done.served_count == 0
    assert done.windows[0].served_seconds == 20 * 60
    assert done.windows[0].schedule_open_seconds == 80 * 60
    assert done.windows[0].load_ratio == 0.25


def test_future_day_keeps_the_schedule_and_counts_real_rows() -> None:
    today = date(2026, 9, 21)
    tomorrow = date(2026, 9, 22)
    empty = report(day=tomorrow, now=at(today, 12, 0))
    ticket = UUID(int=113)
    with_row = report(
        day=tomorrow,
        now=at(today, 12, 0),
        history=[
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(tomorrow, 10, 0), 1, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(tomorrow, 10, 1), 2, WINDOW_A),
        ],
    )

    assert empty.windows[0].schedule_open_seconds == 9 * 3600
    assert empty.windows[0].load_ratio == 0
    assert with_row.windows[0].served_seconds == 60


def test_work_before_opening_does_not_invent_a_denominator() -> None:
    today = date(2026, 9, 21)
    ticket = UUID(int=114)
    done = report(
        day=today,
        now=at(today, 7, 0),
        completed=[visit(ticket, TicketSource.QR, at(today, 6, 20), at(today, 6, 30))],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(today, 6, 0), 1),
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(today, 6, 20), 2, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(today, 6, 30), 3, WINDOW_A),
        ],
    )

    assert done.served_count == 1
    assert done.hourly[6].served_count == 1
    assert done.windows[0].served_seconds == 10 * 60
    assert done.windows[0].schedule_open_seconds == 0
    assert done.windows[0].load_ratio is None


def test_overnight_and_degenerate_schedules() -> None:
    past = datetime(2026, 9, 21, 12, tzinfo=MOSCOW)

    assert schedule_open_seconds(DAY, time(22), time(6), MOSCOW, past) == 8 * 3600
    assert schedule_open_seconds(date(2026, 9, 21), time(22), time(6), MOSCOW, at(date(2026, 9, 21), 3)) == 3 * 3600
    assert schedule_open_seconds(DAY, time(9), time(9), MOSCOW, past) == 24 * 3600


def test_load_ratio_rounds_half_up_to_four_digits() -> None:
    ticket = UUID(int=115)
    done = report(
        open_at=time(9, 0, 0),
        close_at=time(9, 0, 6),
        history=[
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 9, 0, 0), 1, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 9, 0, 1), 2, WINDOW_A),
        ],
    )

    assert done.windows[0].schedule_open_seconds == 6
    assert done.windows[0].served_seconds == 1
    assert done.windows[0].load_ratio == 0.1667


def test_completion_without_start_counts_the_call() -> None:
    ticket = UUID(int=117)
    done = report(
        completed=[visit(ticket, TicketSource.WALK_IN, None, at(DAY, 10, 12), called=at(DAY, 10, 4))],
        history=[
            event(ticket, TicketStatus.QUEUED, TicketStatusChangeReason.ISSUED, at(DAY, 10, 0), 1),
            event(ticket, TicketStatus.CALLED, TicketStatusChangeReason.CALLED, at(DAY, 10, 4), 2, WINDOW_A),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 10, 12), 3, WINDOW_A),
        ],
    )

    assert done.served_count == 1
    assert done.avg_wait_seconds == 4 * 60
    assert done.max_wait_seconds == 4 * 60
    assert done.avg_service_seconds == 8 * 60
    assert done.windows[0].served_seconds == 8 * 60


def test_windows_are_ordered_by_label_and_idle_ones_stay() -> None:
    ticket = UUID(int=116)
    done = report(
        windows=(WindowRef(WINDOW_B, "B"), WindowRef(WINDOW_A, "A")),
        history=[
            event(ticket, TicketStatus.SERVING, TicketStatusChangeReason.STARTED, at(DAY, 10, 0), 1, WINDOW_B),
            event(ticket, TicketStatus.COMPLETED, TicketStatusChangeReason.COMPLETED, at(DAY, 10, 1), 2, WINDOW_B),
        ],
    )

    assert [item.label for item in done.windows] == ["A", "B"]
    assert done.windows[0].served_seconds == 0
    assert done.windows[1].served_seconds == 60
    assert done.windows[0].schedule_open_seconds == done.windows[1].schedule_open_seconds
