from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import Boolean, Integer, String, Time, UniqueConstraint, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .service import Service
    from .window import Window


def _new_department_code() -> str:
    return uuid4().hex[:8].upper()


class Department(Base):
    __tablename__ = "department"
    __table_args__ = (UniqueConstraint("code", name="uq_department_code"),)

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=_new_department_code,
    )

    address: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    # TODO: store a timezone on each department. The calendar day, slots, and ticket numbers use settings.queue_timezone.
    open_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    close_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    queue_bonus_web: Mapped[int] = mapped_column(Integer, nullable=False, default=300, server_default="300")
    queue_bonus_qr: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    queue_bonus_walk_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    queue_max_wait_web: Mapped[int] = mapped_column(Integer, nullable=False, default=900, server_default="900")
    queue_max_wait_qr: Mapped[int] = mapped_column(Integer, nullable=False, default=1200, server_default="1200")
    queue_max_wait_walk_in: Mapped[int] = mapped_column(Integer, nullable=False, default=1200, server_default="1200")

    services: Mapped[list[Service]] = relationship(
        back_populates="department",
        lazy="selectin",
    )

    windows: Mapped[list[Window]] = relationship(
        back_populates="department",
        lazy="selectin",
    )
