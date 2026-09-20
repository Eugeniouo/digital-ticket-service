from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    String,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .department import Department
    from .window import Window


class StaffRole(StrEnum):
    OPERATOR = "operator"  # оператор за окном
    ADMIN = "admin"  # руководитель/менеджер отделения
    ROOT = "root"  # сервисный пользователь


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    username: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    role: Mapped[StaffRole] = mapped_column(
        Enum(
            StaffRole,
            name="staff_role",
            values_callable=lambda members: [item.value for item in members],
        ),
        nullable=False,
    )

    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("department.id"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    department: Mapped[Department | None] = relationship()

    windows: Mapped[list[Window]] = relationship(
        back_populates="current_operator",
    )

    __table_args__ = (
        CheckConstraint(
            "(role IN ('operator', 'admin') AND department_id IS NOT NULL) OR (role = 'root' AND department_id IS NULL)",
            name="ck_staff_role_department",
        ),
    )
