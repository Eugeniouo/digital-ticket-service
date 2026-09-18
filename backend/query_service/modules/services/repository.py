from uuid import UUID

from fastapi import Depends
from query_service.database.dependencies import get_db_session
from query_service.database.models.service import Service
from sqlalchemy.ext.asyncio import AsyncSession


class ServiceRepository:
    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_by_id(self, service_id: UUID) -> Service | None:
        return await self.session.get(Service, service_id)
