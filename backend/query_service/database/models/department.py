from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import Boolean, String, Time, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .service import Service
    from .window import Window


class Department(Base):
    __tablename__ = "department"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    address: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

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

    services: Mapped[list[Service]] = relationship(
        back_populates="department",
        lazy="selectin",
    )

    windows: Mapped[list[Window]] = relationship(
        back_populates="department",
        lazy="selectin",
    )
