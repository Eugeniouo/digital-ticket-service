from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class NotificationOutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )

    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id"),
        nullable=False,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    status: Mapped[NotificationOutboxStatus] = mapped_column(
        Enum(
            NotificationOutboxStatus,
            name="notification_outbox_status",
            values_callable=lambda members: [item.value for item in members],
        ),
        nullable=False,
        default=NotificationOutboxStatus.PENDING,
        server_default=NotificationOutboxStatus.PENDING.value,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_error: Mapped[str | None] = mapped_column(
        String,
    )

    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    __table_args__ = (
        Index(
            "ix_notification_outbox_due",
            "status",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )
