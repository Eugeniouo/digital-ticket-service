from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from query_service.database.models.ticket import TicketSource, TicketStatus
from query_service.database.models.ticket_status_history import TicketStatusChangeReason
from query_service.modules.analytics.schema import (
    HOURS_IN_DAY,
    AppealChannel,
    AppealSourceCount,
    DayAnalyticsResponse,
    HourlyServed,
    WindowLoad,
)

_RATIO_QUANTUM = Decimal("0.0001")
_QUEUE_ENTRY = frozenset(
    {
        TicketStatusChangeReason.ISSUED,
        TicketStatusChangeReason.REQUEUED,
        TicketStatusChangeReason.REDIRECTED,
    },
)
_SOURCE_CHANNELS: tuple[tuple[TicketSource, AppealChannel], ...] = (
    (TicketSource.WEB, "appointment"),
    (TicketSource.QR, "qr"),
    (TicketSource.WALK_IN, "walk-in"),
)


@dataclass(frozen=True, slots=True)
class CompletedVisit:
    """One ticket finished inside the requested day."""

    ticket_id: UUID
    source: TicketSource
    started_at: datetime | None
    completed_at: datetime
    slot_date: date | None
    slot_time: time | None


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    """One status-journal row used to rebuild wait and service intervals."""

    ticket_id: UUID
    new_status: TicketStatus
    reason: TicketStatusChangeReason
    window_id: UUID | None
    changed_at: datetime
    id: UUID


@dataclass(frozen=True, slots=True)
class WindowRef:
    """Window identity for the load table."""

    window_id: UUID
    label: str


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Half-open calendar day `[start, end)` in the department timezone."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def schedule_open_seconds(
    day: date,
    open_time: time,
    close_time: time,
    tz: ZoneInfo,
    now: datetime,
) -> int:
    """Seconds of the department schedule that have already elapsed on `day`.

    Today is clipped to `now`. Any other day uses the whole schedule: a future
    day is empty because nothing was served, not because the shift length is zero.
    """
    day_start, day_end = day_bounds(day, tz)
    visible_end = _visible_until(day_start, day_end, now.astimezone(tz))
    if visible_end <= day_start:
        return 0

    total = 0
    for start, end in _schedule_intervals(day, open_time, close_time, tz):
        total += _elapsed_seconds(start, min(end, visible_end))

    return total


def build_day_analytics(
    *,
    department_id: UUID,
    day: date,
    timezone_name: str,
    tz: ZoneInfo,
    open_time: time,
    close_time: time,
    now: datetime,
    completed: Sequence[CompletedVisit],
    history: Sequence[HistoryPoint],
    source_counts: Mapping[TicketSource, int],
    windows: Sequence[WindowRef],
) -> DayAnalyticsResponse:
    """Aggregate one department day. Durations are whole seconds, half-up."""
    now_local = now.astimezone(tz)
    day_start, day_end = day_bounds(day, tz)
    visible_end = _visible_until(day_start, day_end, now_local)
    on_day = [ticket for ticket in completed if ticket.completed_at.astimezone(tz).date() == day]
    grouped = _group_history(history)

    waits = _wait_samples(on_day, grouped, tz)
    services = _service_samples(on_day)
    open_seconds = schedule_open_seconds(day, open_time, close_time, tz, now_local)
    served_by_window = _serving_seconds(grouped, day_start, visible_end, now_local)

    return DayAnalyticsResponse(
        department_id=department_id,
        date=day,
        timezone=timezone_name,
        served_count=len(on_day),
        avg_wait_seconds=_average_half_up(waits),
        max_wait_seconds=max(waits) if waits else None,
        avg_service_seconds=_average_half_up(services),
        hourly=_hourly(on_day, tz),
        sources=_sources(source_counts),
        windows=_window_loads(windows, served_by_window, open_seconds),
    )


def _visible_until(day_start: datetime, day_end: datetime, now: datetime) -> datetime:
    """End of the already-elapsed part of this calendar day."""
    if day_start <= now < day_end:
        return now

    return day_end


def _schedule_intervals(
    day: date,
    open_time: time,
    close_time: time,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    """Working intervals of `day`. A shift that crosses midnight is split in two.

    `close_time == open_time` follows the same split and therefore covers 24 hours.
    """
    if close_time > open_time:
        return [
            (
                datetime.combine(day, open_time, tzinfo=tz),
                datetime.combine(day, close_time, tzinfo=tz),
            ),
        ]

    day_start, day_end = day_bounds(day, tz)
    intervals: list[tuple[datetime, datetime]] = []
    morning_end = datetime.combine(day, close_time, tzinfo=tz)
    if morning_end > day_start:
        intervals.append((day_start, morning_end))

    evening_start = datetime.combine(day, open_time, tzinfo=tz)
    if day_end > evening_start:
        intervals.append((evening_start, day_end))

    return intervals


def _hourly(completed: Sequence[CompletedVisit], tz: ZoneInfo) -> list[HourlyServed]:
    """24 bars, hour 0 first. Hours with nobody served stay at zero."""
    counts = [0] * HOURS_IN_DAY
    for ticket in completed:
        counts[ticket.completed_at.astimezone(tz).hour] += 1

    return [HourlyServed(hour=hour, served_count=count) for hour, count in enumerate(counts)]


def _sources(source_counts: Mapping[TicketSource, int]) -> list[AppealSourceCount]:
    return [AppealSourceCount(source=channel, count=source_counts.get(source, 0)) for source, channel in _SOURCE_CHANNELS]


def _window_loads(
    windows: Sequence[WindowRef],
    served_by_window: Mapping[UUID, int],
    open_seconds: int,
) -> list[WindowLoad]:
    loads: list[WindowLoad] = []
    for window in sorted(windows, key=lambda item: (item.label, item.window_id)):
        served_seconds = served_by_window.get(window.window_id, 0)
        loads.append(
            WindowLoad(
                window_id=window.window_id,
                label=window.label,
                served_seconds=served_seconds,
                schedule_open_seconds=open_seconds,
                load_ratio=_load_ratio(served_seconds, open_seconds),
            ),
        )

    return loads


def _wait_samples(
    completed: Sequence[CompletedVisit],
    grouped: Mapping[UUID, Sequence[HistoryPoint]],
    tz: ZoneInfo,
) -> list[int]:
    samples: list[int] = []
    for ticket in completed:
        events = grouped.get(ticket.ticket_id)
        if not events:
            continue

        value = _last_wait_seconds(ticket, events, tz)
        if value is not None:
            samples.append(value)

    return samples


def _service_samples(completed: Sequence[CompletedVisit]) -> list[int]:
    samples: list[int] = []
    for ticket in completed:
        if ticket.started_at is None:
            continue
        samples.append(_elapsed_seconds(ticket.started_at, ticket.completed_at))

    return samples


def _last_wait_seconds(
    ticket: CompletedVisit,
    events: Sequence[HistoryPoint],
    tz: ZoneInfo,
) -> int | None:
    """Wait of the visit that finished the ticket, from queue entry until service start."""
    if not events:
        return None

    completed_index = _rfind_status(events, len(events) - 1, TicketStatus.COMPLETED)
    if completed_index is None or completed_index == 0:
        return None

    started_index = _rfind_status(events, completed_index - 1, TicketStatus.SERVING)
    if started_index is None or started_index == 0:
        return None

    entry_index = _rfind_reason(events, started_index - 1, _QUEUE_ENTRY)
    if entry_index is None:
        return None

    return _wait_from_entry(ticket, events[entry_index], events[started_index].changed_at, tz)


def _wait_from_entry(
    ticket: CompletedVisit,
    entry: HistoryPoint,
    started_at: datetime,
    tz: ZoneInfo,
) -> int | None:
    """Appointment wait starts at the slot, not at the moment of booking."""
    anchor = entry.changed_at
    if entry.reason == TicketStatusChangeReason.ISSUED and ticket.source == TicketSource.WEB:
        if ticket.slot_date is None or ticket.slot_time is None:
            return None
        anchor = datetime.combine(ticket.slot_date, ticket.slot_time, tzinfo=tz)

    return _elapsed_seconds(anchor, started_at)


def _rfind_status(events: Sequence[HistoryPoint], start: int, status: TicketStatus) -> int | None:
    for index in range(start, -1, -1):
        if events[index].new_status == status:
            return index

    return None


def _rfind_reason(
    events: Sequence[HistoryPoint],
    start: int,
    reasons: frozenset[TicketStatusChangeReason],
) -> int | None:
    for index in range(start, -1, -1):
        if events[index].reason in reasons:
            return index

    return None


def _serving_seconds(
    grouped: Mapping[UUID, Sequence[HistoryPoint]],
    bound_start: datetime,
    bound_end: datetime,
    now: datetime,
) -> dict[UUID, int]:
    """Every serving segment overlapping the day, including ones cleared off the ticket."""
    totals: dict[UUID, int] = {}
    for events in grouped.values():
        for index, event in enumerate(events):
            if event.new_status != TicketStatus.SERVING or event.window_id is None:
                continue

            segment_end = events[index + 1].changed_at if index + 1 < len(events) else now
            seconds = _overlap_seconds(event.changed_at, segment_end, bound_start, bound_end)
            if seconds == 0:
                continue

            totals[event.window_id] = totals.get(event.window_id, 0) + seconds

    return totals


def _group_history(events: Sequence[HistoryPoint]) -> dict[UUID, list[HistoryPoint]]:
    grouped: dict[UUID, list[HistoryPoint]] = {}
    for event in events:
        grouped.setdefault(event.ticket_id, []).append(event)

    for points in grouped.values():
        points.sort(key=_history_order)

    return grouped


def _history_order(point: HistoryPoint) -> tuple[datetime, UUID]:
    return point.changed_at, point.id


def _overlap_seconds(start: datetime, end: datetime, bound_start: datetime, bound_end: datetime) -> int:
    return _elapsed_seconds(max(start, bound_start), min(end, bound_end))


def _elapsed_seconds(start: datetime, end: datetime) -> int:
    delta = (end - start).total_seconds()
    if delta <= 0:
        return 0

    return int(delta + 0.5)


def _average_half_up(values: Sequence[int]) -> int | None:
    if not values:
        return None

    total = sum(values)
    count = len(values)
    return (total + count // 2) // count


def _load_ratio(served_seconds: int, open_seconds: int) -> float | None:
    if open_seconds <= 0:
        return None

    ratio = (Decimal(served_seconds) / Decimal(open_seconds)).quantize(_RATIO_QUANTUM, rounding=ROUND_HALF_UP)
    return float(ratio)
