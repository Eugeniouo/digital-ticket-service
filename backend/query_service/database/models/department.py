from datetime import time
from uuid import UUID, uuid4

from query_service.database.base import Base
from sqlalchemy import String, Time, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column


class Department(Base):
    """Postal department and its daily opening hours."""

    __tablename__ = "department"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String)
    open_time: Mapped[time] = mapped_column(Time)
    close_time: Mapped[time] = mapped_column(Time)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
