from enum import StrEnum
from pathlib import Path
from tempfile import gettempdir

from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

TEMP_DIR = Path(gettempdir())


class LogLevel(StrEnum):
    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class AdapterType(StrEnum):
    DEMO = "demo"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = False

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO

    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "query_service"
    db_pass: str = "query_service"  # noqa: S105
    db_base: str = "query_service"
    db_echo: bool = False

    # Defaults for new departments. Live rules are stored on department rows.
    queue_timezone: str = "Europe/Moscow"
    queue_bonus_web: int = 300
    queue_bonus_qr: int = 0
    queue_bonus_walk_in: int = 0
    queue_max_wait_web: int = 900
    queue_max_wait_qr: int = 1200
    queue_max_wait_walk_in: int = 1200

    # Notifications
    notify_adapter: str = AdapterType.DEMO
    notify_timeout_seconds: float = 2.0
    notify_poll_interval_seconds: float = 2.0
    notify_max_attempts: int = 5
    notify_approaching_ahead: int = 2
    notify_force_failure: bool = False
    celery_broker_url: str = "redis://localhost:6379/0"

    jwt_secret: str = ""
    jwt_ttl_seconds: int = 43200  # 12 hours
    bootstrap_username: str = ""
    bootstrap_password: str = ""
    seed_api_url: str = "http://127.0.0.1:8000"

    cors_origins: list[str] = ["http://localhost:4173"]

    frontend_origin: str = "http://localhost:4173"
    visitor_path: str = "/src/visitor.html"

    @property
    def db_url(self) -> URL:
        """
        Assemble database URL from settings.

        :return: database URL.
        """
        return URL.build(
            scheme="postgresql+asyncpg",
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            path=f"/{self.db_base}",
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QUERY_SERVICE_",
        env_file_encoding="utf-8",
    )


settings = Settings()
