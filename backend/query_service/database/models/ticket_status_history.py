from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from query_service.database.base import Base
from query_service.database.models.ticket import TicketStatus
from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


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
        index=True,
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

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    note: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
