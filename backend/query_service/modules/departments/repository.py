from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.modules.departments.exceptions import DuplicateDepartmentCodeError


class DepartmentRepository:
    """Database queries for departments."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_all(self) -> list[Department]:
        result = await self.session.scalars(select(Department).order_by(Department.code, Department.id))
        return list(result.all())

    async def get_by_id(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def add(self, department: Department) -> Department:
        self.session.add(department)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateDepartmentCodeError from exc
        return department

    async def save(self) -> None:
        await self.session.flush()
