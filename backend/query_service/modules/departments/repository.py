from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department


class DepartmentRepository:
    """Database queries for departments."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_all(self) -> list[Department]:
        result = await self.session.scalars(select(Department).order_by(Department.name, Department.id))
        return list(result.all())

    async def get_by_id(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def add(self, department: Department) -> Department:
        self.session.add(department)
        await self.session.flush()
        return department

    async def save(self) -> None:
        await self.session.flush()
