from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from query_service.database.models.ticket import TicketSource
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
