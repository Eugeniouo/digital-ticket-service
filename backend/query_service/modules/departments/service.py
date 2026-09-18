from uuid import UUID

from fastapi import Depends

from query_service.database.models.department import Department
from query_service.modules.departments.repository import DepartmentRepository


class DepartmentService:
    """Read department information."""

    def __init__(self, repository: DepartmentRepository = Depends()) -> None:
        self.repository = repository

    async def get_all(self) -> list[Department]:
        return await self.repository.get_all()

    async def get_by_id(self, department_id: UUID) -> Department | None:
        return await self.repository.get_by_id(department_id)
