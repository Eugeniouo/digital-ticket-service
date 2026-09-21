from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, or_
from sqlalchemy.sql.elements import ColumnElement

from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketSource
from query_service.modules.tickets.queue_rules import QueueRules
from query_service.settings import settings

# Начало отсчета, отсчет от UTC
PRIORITY_ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)

QUEUE_TIMEZONE = ZoneInfo(settings.queue_timezone)


def now_in_queue_tz() -> datetime:
    return datetime.now(QUEUE_TIMEZONE)


def to_priority_seconds(moment: datetime) -> int:
    """Seconds from PRIORITY_ANCHOR for an aware (or queue-tz naive) datetime."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=QUEUE_TIMEZONE)
    return int((moment.astimezone(UTC) - PRIORITY_ANCHOR).total_seconds())


def now_priority_seconds() -> int:
    return to_priority_seconds(now_in_queue_tz())


def compute_priority_key(effective_start: datetime) -> int:
    """Store slot start / arrival as seconds from PRIORITY_ANCHOR.

    Source bonus is not stored. Assign order subtracts the current department bonus.
    """
    return to_priority_seconds(effective_start)


def effective_priority(priority_key: int, source: TicketSource, rules: QueueRules) -> int:
    """Sort key: lower value is served first."""
    return priority_key - rules.bonus(source)


def is_web_noshow(priority_key: int, rules: QueueRules, now_seconds: int | None = None) -> bool:
    """WEB ticket whose slot start + max_wait is already in the past."""
    now = now_priority_seconds() if now_seconds is None else now_seconds
    threshold = now - rules.max_wait_web

    return priority_key < threshold


def is_queue_eligible(
    source: TicketSource,
    priority_key: int,
    rules: QueueRules,
    now_seconds: int | None = None,
) -> bool:
    """Same eligibility rules as assign_next (live always; WEB due and not no-show)."""
    now = now_priority_seconds() if now_seconds is None else now_seconds

    if source in (TicketSource.QR, TicketSource.WALK_IN):
        return True
    if source != TicketSource.WEB:
        return False

    due = priority_key <= now
    not_expired = priority_key >= now - rules.max_wait_web

    return due and not_expired


def overdue_live_rank(
    source: TicketSource,
    priority_key: int,
    rules: QueueRules,
    now_seconds: int | None = None,
) -> int:
    """0 = overdue live (anti-starvation), 1 = normal. Matches assign_next ORDER BY."""
    now = now_priority_seconds() if now_seconds is None else now_seconds

    if source == TicketSource.QR and priority_key < now - rules.max_wait_qr:
        return 0
    if source == TicketSource.WALK_IN and priority_key < now - rules.max_wait_walk_in:
        return 0

    return 1


def effective_priority_sql(rules: QueueRules) -> ColumnElement[int]:
    return Ticket.priority_key - case(
        (Ticket.source == TicketSource.WEB, rules.bonus_web),
        (Ticket.source == TicketSource.QR, rules.bonus_qr),
        (Ticket.source == TicketSource.WALK_IN, rules.bonus_walk_in),
        else_=0,
    )


def queue_eligible_sql(now_seconds: int, rules: QueueRules) -> ColumnElement[bool]:
    web_due = Ticket.priority_key <= now_seconds
    web_not_expired = Ticket.priority_key >= now_seconds - rules.max_wait_web

    return or_(
        Ticket.source.in_((TicketSource.QR, TicketSource.WALK_IN)),
        and_(Ticket.source == TicketSource.WEB, web_due, web_not_expired),
    )


def web_noshow_sql(now_seconds: int, rules: QueueRules) -> ColumnElement[bool]:
    return and_(
        Ticket.source == TicketSource.WEB,
        Ticket.priority_key < now_seconds - rules.max_wait_web,
    )


def overdue_live_sql(now_seconds: int, rules: QueueRules) -> ColumnElement[int]:
    return case(
        (
            and_(
                Ticket.source == TicketSource.QR,
                Ticket.priority_key < now_seconds - rules.max_wait_qr,
            ),
            0,
        ),
        (
            and_(
                Ticket.source == TicketSource.WALK_IN,
                Ticket.priority_key < now_seconds - rules.max_wait_walk_in,
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
