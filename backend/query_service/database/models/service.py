from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from department import Department
    from slot import Slot
    from window import Window


class Service(Base):
    __tablename__ = "service"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("department.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    duration_time: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    department: Mapped[Department] = relationship(
        back_populates="services",
    )

    slots: Mapped[list[Slot]] = relationship(
        back_populates="service",
        lazy="selectin",
    )

    windows: Mapped[list[Window]] = relationship(
        secondary="window_service",
        back_populates="services",
        lazy="selectin",
    )
