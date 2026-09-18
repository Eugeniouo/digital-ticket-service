from importlib import import_module


def load_all_models() -> None:
    """Import models so metadata is registered for Alembic and tests."""
    for name in ("dummy", "department"):
        import_module(f"query_service.database.models.{name}")
