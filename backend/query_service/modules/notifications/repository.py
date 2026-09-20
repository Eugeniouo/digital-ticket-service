from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.notification_outbox import NotificationOutbox, NotificationOutboxStatus


class NotificationRepository:
    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def insert_ignore(self, row: NotificationOutbox) -> None:
        """Insert an outbox row. Skip when the idempotency key already exists."""
        stmt = (
            insert(NotificationOutbox)
            .values(
                id=row.id,
                idempotency_key=row.idempotency_key,
                event_type=row.event_type,
                ticket_id=row.ticket_id,
                payload=row.payload,
                status=row.status,
                attempts=row.attempts,
                next_attempt_at=row.next_attempt_at,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )

        await self.session.execute(stmt)
        await self.session.flush()

    async def claim_due(self, limit: int) -> list[NotificationOutbox]:
        now = datetime.now(UTC)

        result = await self.session.scalars(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == NotificationOutboxStatus.PENDING,
                NotificationOutbox.next_attempt_at <= now,
            )
            .order_by(NotificationOutbox.created_at, NotificationOutbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True),  # Avoid race conditions with multiple workers
        )

        return list(result.all())

    async def save(self) -> None:
        await self.session.flush()

    async def list_for_ticket(self, ticket_id: UUID) -> list[NotificationOutbox]:
        result = await self.session.scalars(
            select(NotificationOutbox)
            .where(NotificationOutbox.ticket_id == ticket_id)
            .order_by(NotificationOutbox.created_at, NotificationOutbox.id),
        )

        return list(result.all())
