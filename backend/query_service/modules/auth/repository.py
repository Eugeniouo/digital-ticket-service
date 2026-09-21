from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.staff import Staff
from query_service.modules.auth.exceptions import DuplicateUsernameError


class StaffRepository:
    """Database access for staff accounts."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_by_id(self, staff_id: UUID) -> Staff | None:
        return await self.session.get(Staff, staff_id)

    async def get_by_username(self, username: str) -> Staff | None:
        return await self.session.scalar(select(Staff).where(Staff.username == username))

    async def department_exists(self, department_id: UUID) -> bool:
        department_pk = await self.session.scalar(select(Department.id).where(Department.id == department_id))
        return department_pk is not None

    async def list_all(self) -> list[Staff]:
        result = await self.session.scalars(select(Staff).order_by(Staff.username, Staff.id))
        return list(result.all())

    async def list_by_department(self, department_id: UUID) -> list[Staff]:
        result = await self.session.scalars(
            select(Staff).where(Staff.department_id == department_id).order_by(Staff.username, Staff.id),
        )
        return list(result.all())

    async def add(self, staff: Staff) -> Staff:
        self.session.add(staff)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateUsernameError from exc

        return staff

    async def save(self) -> None:
        await self.session.flush()
