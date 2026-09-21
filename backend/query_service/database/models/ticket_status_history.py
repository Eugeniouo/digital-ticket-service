from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from query_service.database.base import Base
from query_service.database.models.ticket import TicketStatus
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class TicketStatusChangeReason(StrEnum):
    ISSUED = "issued"
    CALLED = "called"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELED = "canceled"
    NOSHOW = "noshow"
    REQUEUED = "requeued"
    REDIRECTED = "redirected"


class TicketStatusHistory(Base):
    __tablename__ = "ticket_status_history"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )

    old_status: Mapped[TicketStatus | None] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda members: [item.value for item in members],
            create_constraint=False,
        ),
        nullable=True,
    )

    new_status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda members: [item.value for item in members],
            create_constraint=False,
        ),
        nullable=False,
    )

    reason: Mapped[TicketStatusChangeReason] = mapped_column(
        Enum(
            TicketStatusChangeReason,
            name="ticket_status_change_reason",
            values_callable=lambda members: [item.value for item in members],
        ),
        nullable=False,
    )

    staff_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
    )

    window_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("window.id", ondelete="SET NULL"),
        nullable=True,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_ticket_status_history_ticket_id_changed_at_id",
            "ticket_id",
            "changed_at",
            "id",
        ),
    )
