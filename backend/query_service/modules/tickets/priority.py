from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, or_
from sqlalchemy.sql.elements import ColumnElement

from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketSource
from query_service.settings import settings

# Начало отсчета, отсчет от UTC
PRIORITY_ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)

QUEUE_TIMEZONE = ZoneInfo(settings.queue_timezone)

BONUS_SECONDS = {
    TicketSource.WEB: settings.queue_bonus_web,
    TicketSource.QR: settings.queue_bonus_qr,
    TicketSource.WALK_IN: settings.queue_bonus_walk_in,
}

MAX_WAIT_SECONDS = {
    TicketSource.WEB: settings.queue_max_wait_web,
    TicketSource.QR: settings.queue_max_wait_qr,
    TicketSource.WALK_IN: settings.queue_max_wait_walk_in,
}


def now_in_queue_tz() -> datetime:
    return datetime.now(QUEUE_TIMEZONE)


def to_priority_seconds(moment: datetime) -> int:
    """Seconds from PRIORITY_ANCHOR for an aware (or queue-tz naive) datetime."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=QUEUE_TIMEZONE)
    return int((moment.astimezone(UTC) - PRIORITY_ANCHOR).total_seconds())


def now_priority_seconds() -> int:
    return to_priority_seconds(now_in_queue_tz())


def compute_priority_key(source: TicketSource, effective_start: datetime) -> int:
    """Вычисляет priority_key. Чем меньше значение, тем выше приоритет."""
    base_seconds = to_priority_seconds(effective_start)
    bonus = BONUS_SECONDS.get(source, 0)
    return base_seconds - bonus


def is_web_noshow(priority_key: int, now_seconds: int | None = None) -> bool:
    """WEB ticket whose slot start + max_wait is already in the past."""
    now = now_priority_seconds() if now_seconds is None else now_seconds
    threshold = now - MAX_WAIT_SECONDS[TicketSource.WEB] - BONUS_SECONDS[TicketSource.WEB]

    return priority_key < threshold


def is_queue_eligible(source: TicketSource, priority_key: int, now_seconds: int | None = None) -> bool:
    """Same eligibility rules as assign_next (live always; WEB due and not no-show)."""
    now = now_priority_seconds() if now_seconds is None else now_seconds

    if source in (TicketSource.QR, TicketSource.WALK_IN):
        return True
    if source != TicketSource.WEB:
        return False

    web_bonus = BONUS_SECONDS[TicketSource.WEB]
    web_max_wait = MAX_WAIT_SECONDS[TicketSource.WEB]
    due = priority_key <= now - web_bonus
    not_expired = priority_key >= now - web_max_wait - web_bonus

    return due and not_expired


def overdue_live_rank(source: TicketSource, priority_key: int, now_seconds: int | None = None) -> int:
    """0 = overdue live (anti-starvation), 1 = normal. Matches assign_next ORDER BY."""
    now = now_priority_seconds() if now_seconds is None else now_seconds

    if source == TicketSource.QR and priority_key < now - MAX_WAIT_SECONDS[TicketSource.QR]:
        return 0
    if source == TicketSource.WALK_IN and priority_key < now - MAX_WAIT_SECONDS[TicketSource.WALK_IN]:
        return 0

    return 1


def queue_eligible_sql(now_seconds: int) -> ColumnElement[bool]:
    web_bonus = BONUS_SECONDS[TicketSource.WEB]
    web_max_wait = MAX_WAIT_SECONDS[TicketSource.WEB]

    web_due = Ticket.priority_key <= now_seconds - web_bonus
    web_not_expired = Ticket.priority_key >= now_seconds - web_max_wait - web_bonus

    return or_(
        Ticket.source.in_((TicketSource.QR, TicketSource.WALK_IN)),
        and_(Ticket.source == TicketSource.WEB, web_due, web_not_expired),
    )


def web_noshow_sql(now_seconds: int) -> ColumnElement[bool]:
    threshold = now_seconds - MAX_WAIT_SECONDS[TicketSource.WEB] - BONUS_SECONDS[TicketSource.WEB]

    return and_(
        Ticket.source == TicketSource.WEB,
        Ticket.priority_key < threshold,
    )


def overdue_live_sql(now_seconds: int) -> ColumnElement[int]:
    return case(
        (
            and_(
                Ticket.source == TicketSource.QR,
                Ticket.priority_key < now_seconds - MAX_WAIT_SECONDS[TicketSource.QR],
            ),
            0,
        ),
        (
            and_(
                Ticket.source == TicketSource.WALK_IN,
                Ticket.priority_key < now_seconds - MAX_WAIT_SECONDS[TicketSource.WALK_IN],
            ),
            0,
        ),
        else_=1,
    )


def ticket_matches_window_sql(window_id: UUID) -> ColumnElement[bool]:
    """Live tickets (no slot) or WEB appointments pinned to this window.

    Caller must OUTER JOIN Slot on Ticket.slot_id.
    """
    return or_(Ticket.slot_id.is_(None), Slot.window_id == window_id)
