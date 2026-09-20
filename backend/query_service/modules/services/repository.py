from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.service import Service


class ServiceRepository:
    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_by_id(self, service_id: UUID) -> Service | None:
        return await self.session.get(Service, service_id)

    async def get_department(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def get_in_department(self, department_id: UUID, service_id: UUID) -> Service | None:
        return await self.session.scalar(
            select(Service).where(
                Service.id == service_id,
                Service.department_id == department_id,
            ),
        )

    async def list_by_department(self, department_id: UUID) -> list[Service]:
        result = await self.session.scalars(
            select(Service).where(Service.department_id == department_id).order_by(Service.name, Service.id),
        )
        return list(result.all())

    async def list_active_by_department(self, department_id: UUID) -> list[Service]:
        result = await self.session.scalars(
            select(Service)
            .where(
                Service.department_id == department_id,
                Service.is_active.is_(True),
            )
            .order_by(Service.name, Service.id),
        )
        return list(result.all())

    async def add(self, service: Service) -> Service:
        self.session.add(service)
        await self.session.flush()
        return service

    async def save(self) -> None:
        await self.session.flush()
