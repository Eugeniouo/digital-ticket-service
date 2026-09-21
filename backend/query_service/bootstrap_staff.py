"""Create the initial root staff account from environment variables."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from query_service.database.models.staff import Staff, StaffRole
from query_service.modules.auth.security import hash_password
from query_service.settings import settings

logger = logging.getLogger(__name__)


async def bootstrap_root() -> None:
    username = settings.bootstrap_username.strip()
    password = settings.bootstrap_password.strip()
    if not username or not password:
        logger.warning("root username or password are not set. ensure you have them in env")
        return

    engine = create_async_engine(str(settings.db_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            existing = await session.scalar(select(Staff).where(Staff.username == username))
            if existing is not None:
                return

            session.add(
                Staff(
                    username=username,
                    display_name=username,
                    password_hash=hash_password(password),
                    role=StaffRole.ROOT,
                    department_id=None,
                ),
            )
            await session.commit()
            logger.info(f"bootstrap root {username} created")
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(bootstrap_root())


if __name__ == "__main__":
    main()
