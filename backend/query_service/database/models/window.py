from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import (
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .department import Department
    from .service import Service
    from .slot import Slot
    from .staff import Staff
    from .ticket import Ticket


class WindowStatus(StrEnum):
    CLOSED = "closed"
    OPEN = "open"


class WindowService(Base):
    """Services a window is allowed to serve."""

    __tablename__ = "window_service"

    window_id: Mapped[UUID] = mapped_column(
        ForeignKey("window.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("service.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (Index("ix_window_service_service_id", "service_id"),)


class WindowOpenService(Base):
    """Services selected for the current open shift."""

    __tablename__ = "window_open_service"

    window_id: Mapped[UUID] = mapped_column(
        ForeignKey("window.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("service.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        Index("ix_window_open_service_service_id", "service_id"),
        ForeignKeyConstraint(
            ["window_id", "service_id"],
            ["window_service.window_id", "window_service.service_id"],
            ondelete="CASCADE",
            name="fk_window_open_service_catalog",
        ),
    )


class Window(Base):
    __tablename__ = "window"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("department.id"),
        nullable=False,
    )

    label: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    status: Mapped[WindowStatus] = mapped_column(
        Enum(
            WindowStatus,
            name="window_status",
            values_callable=lambda members: [item.value for item in members],
        ),
        nullable=False,
        default=WindowStatus.CLOSED,
        server_default=WindowStatus.CLOSED.value,
    )

    current_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
    )

    department: Mapped[Department] = relationship(
        back_populates="windows",
    )

    current_operator: Mapped[Staff | None] = relationship(
        back_populates="windows",
    )

    services: Mapped[list[Service]] = relationship(
        secondary="window_service",
        back_populates="windows",
        lazy="selectin",
    )

    open_services: Mapped[list[Service]] = relationship(
        secondary="window_open_service",
        lazy="selectin",
    )

    slots: Mapped[list[Slot]] = relationship(
        back_populates="window",
        lazy="selectin",
    )

    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="window",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "id",
            "department_id",
            name="uq_window_id_department",
        ),
        UniqueConstraint(
            "department_id",
            "label",
            name="uq_window_department_label",
        ),
        Index(
            "uq_window_current_operator",
            "current_operator_id",
            unique=True,
            postgresql_where=text("current_operator_id IS NOT NULL"),
        ),
    )
