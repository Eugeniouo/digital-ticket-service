from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .department import Department
    from .service import Service
    from .slot import Slot
    from .window import Window


# Перечисления относятся к типу данных - существуют в слое базы данных.
class TicketSource(StrEnum):
    WEB = "web"
    QR = "qr"
    WALK_IN = "walk-in"


class TicketStatus(StrEnum):
    QUEUED = "queued"
    CALLED = "called"
    SERVING = "serving"
    COMPLETED = "completed"
    CANCELED = "canceled"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("department.id"),
        nullable=False,
    )

    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("service.id"),
        nullable=False,
    )

    window_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("window.id"),
    )

    slot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("slot.id"),
    )

    source: Mapped[TicketSource] = mapped_column(
        Enum(
            TicketSource,
            name="ticket_source",
            # типизация для Enum типа
            values_callable=lambda members: [item.value for item in members],
        ),
        nullable=False,
    )

    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda members: [item.value for item in members],
        ),
        nullable=False,
        default=TicketStatus.QUEUED,
        server_default=TicketStatus.QUEUED.value,
    )

    # TODO: рассмотреть другую структуру данных для Priority Key (bigint???)
    priority_key: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ticket_label: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    called_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    slot: Mapped[Slot | None] = relationship(
        back_populates="tickets",
    )

    window: Mapped[Window | None] = relationship(
        back_populates="tickets",
    )

    department: Mapped[Department] = relationship()
    service: Mapped[Service] = relationship()
