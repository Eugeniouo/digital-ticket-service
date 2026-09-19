from datetime import UTC, datetime

from query_service.database.models.ticket import TicketSource

# Якорь в UTC timezone-aware
PRIORITY_ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)

# Фора в секундах (конфигурируется)
BONUS_SECONDS = {
    TicketSource.WEB: 300,  # 5 минут форы для предзаписи
    TicketSource.QR: 0,
    TicketSource.WALK_IN: 0,
}

MAX_WAIT_SECONDS = {
    TicketSource.WEB: 15 * 60,
    TicketSource.QR: 20 * 60,
    TicketSource.WALK_IN: 20 * 60,
}


def compute_priority_key(source: TicketSource, effective_start: datetime) -> int:
    """Вычисляет priority_key. Чем меньше значение, тем выше приоритет."""
    if effective_start.tzinfo is None:
        effective_start = effective_start.replace(tzinfo=UTC)

    base_seconds = int((effective_start - PRIORITY_ANCHOR).total_seconds())
    bonus = BONUS_SECONDS.get(source, 0)

    return base_seconds - bonus
