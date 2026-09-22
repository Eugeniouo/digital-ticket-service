from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .department import Department


class TicketCounter(Base):
    __tablename__ = "ticket_counter"

    # Для 1 отделения, 1 дня и 1 префикса будет только 1 запись
    __table_args__ = (UniqueConstraint("department_id", "date", "prefix", name="uq_ticket_counter_department_date_prefix"),)

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("department.id"),
        nullable=False,
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    prefix: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    current_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    department: Mapped[Department] = relationship()
