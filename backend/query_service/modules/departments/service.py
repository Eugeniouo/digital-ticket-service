from uuid import UUID

from fastapi import Depends

from query_service.database.models.department import Department
from query_service.modules.departments.exceptions import DepartmentNotFoundError
from query_service.modules.departments.repository import DepartmentRepository
from query_service.modules.departments.schema import DepartmentCreateRequestDTO


class DepartmentService:
    """Department logic."""

    def __init__(self, repository: DepartmentRepository = Depends()) -> None:
        self.repository = repository

    async def get_all(self) -> list[Department]:
        return await self.repository.get_all()

    async def get_by_id(self, department_id: UUID) -> Department:
        department = await self.repository.get_by_id(department_id)
        # Падаем с ошибкой на уровне сервиса вместо хэндлера
        if department is None:
            raise DepartmentNotFoundError
        return department

    async def create(self, payload: DepartmentCreateRequestDTO) -> Department:
        department = Department(
            name=payload.name,
            address=payload.address,
            open_time=payload.open_time,
            close_time=payload.close_time,
            is_active=payload.is_active,
        )
        return await self.repository.add(department)
