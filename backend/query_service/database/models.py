from query_service.database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import String


def load_all_models() -> None:
    """Import models so metadata is registered for Alembic and tests."""


class DummyModel(Base):
    """Model for demo purpose as a database table."""

    __tablename__ = "dummy_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(length=200))
