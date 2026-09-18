from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .service import Service
    from .ticket import Ticket
    from .window import Window


class Slot(Base):
    __tablename__ = "slot"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    window_id: Mapped[UUID] = mapped_column(
        ForeignKey("window.id"),
        nullable=False,
    )

    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("service.id"),
        nullable=False,
    )

    slot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    slot_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    booked_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )  # TODO: Предусмотреть Race Condition, когда два клиента одновременно бронируют слот

    service: Mapped[Service] = relationship(
        back_populates="slots",
    )

    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="slot",
        lazy="selectin",
    )

    window: Mapped[Window] = relationship(
        back_populates="slots",
    )

    __table_args__ = (
        UniqueConstraint(
            "window_id",
            "service_id",
            "slot_date",
            "slot_time",
            name="uq_slot_window_service_datetime",
        ),
        CheckConstraint(
            "capacity > 0",
            name="ck_slot_capacity_positive",
        ),
        CheckConstraint(
            "booked_count >= 0",
            name="ck_slot_booked_count_non_negative",
        ),
        CheckConstraint(
            "booked_count <= capacity",
            name="ck_slot_booked_count_lte_capacity",
        ),
    )
