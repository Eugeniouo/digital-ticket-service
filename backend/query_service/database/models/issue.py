from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class IssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("department.id"),
        nullable=False,
    )

    reporter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
    )

    message: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    status: Mapped[IssueStatus] = mapped_column(
        Enum(
            IssueStatus,
            name="issue_status",
            values_callable=lambda members: [item.value for item in members],
        ),
        nullable=False,
        default=IssueStatus.OPEN,
        server_default=IssueStatus.OPEN.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
