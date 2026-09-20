import asyncio
import logging
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from query_service.database.models.notification_outbox import NotificationOutbox, NotificationOutboxStatus
from query_service.integrations.notifications.exceptions import NotificationDeliveryError
from query_service.integrations.notifications.factory import create_notification_adapter
from query_service.integrations.notifications.port import NotificationGateway, NotificationMessage
from query_service.modules.notifications.repository import NotificationRepository
from query_service.settings import Settings, settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
DELAY_SECONDS = 60


def _calculate_retry_delay(attempts: int) -> int:
    return min(DELAY_SECONDS, 2**attempts)


async def deliver_row(
    row: NotificationOutbox,
    adapter: NotificationGateway,
    timeout_seconds: float,
    max_attempts: int,
) -> None:
    """Send one outbox row and update status. Caller holds the row lock."""
    now = datetime.now(UTC)

    try:
        message = NotificationMessage.model_validate(row.payload)
        await asyncio.wait_for(adapter.send(message), timeout=timeout_seconds)
    except ValidationError as exc:
        row.attempts += 1
        row.last_error = str(exc)
        row.status = NotificationOutboxStatus.FAILED
        return
    except TimeoutError:
        _mark_attempt(row, now, max_attempts, "timeout")
        return
    except NotificationDeliveryError as exc:
        _mark_attempt(row, now, max_attempts, str(exc))
        return
    except Exception as exc:
        _mark_attempt(row, now, max_attempts, str(exc))
        return

    row.status = NotificationOutboxStatus.SENT
    row.sent_at = now
    row.last_error = None


def _mark_attempt(
    row: NotificationOutbox,
    now: datetime,
    max_attempts: int,
    error: str,
) -> None:
    row.attempts += 1
    row.last_error = error

    if row.attempts >= max_attempts:
        row.status = NotificationOutboxStatus.FAILED
        return

    row.next_attempt_at = now + timedelta(seconds=_calculate_retry_delay(row.attempts))


async def process_due_rows(
    session: AsyncSession,
    adapter: NotificationGateway,
    settings: Settings,
) -> None:
    """Claim due pending rows and try to deliver them. Caller commits."""
    repository = NotificationRepository(session)

    rows = await repository.claim_due(BATCH_SIZE)

    for row in rows:
        await deliver_row(
            row,
            adapter,
            timeout_seconds=settings.notify_timeout_seconds,
            max_attempts=settings.notify_max_attempts,
        )

    await session.flush()


async def drain() -> None:
    """Open a session, deliver outbox rows that are in the due state, and commit."""
    # Reuse one engine per worker process if Postgres connect churn shows up.
    engine = create_async_engine(str(settings.db_url), echo=settings.db_echo)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    adapter = create_notification_adapter(settings)

    try:
        async with session_factory() as session:
            await process_due_rows(session, adapter, settings)
            # separate commit from processing rows, so we can rollback
            await session.commit()

    except Exception:
        # Do not re-raise. Beat already schedules the next drain. Celery retries would duplicate drain tasks.
        logger.exception("while trying to drain, notification worker failed unexpectedly")

    finally:
        await engine.dispose()
