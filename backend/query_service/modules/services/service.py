from uuid import UUID

from fastapi import Depends

from query_service.database.models.service import Service
from query_service.modules.services.exceptions import DepartmentNotFoundError, ServiceNotFoundError
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.services.schema import (
    ServiceCreateRequestDTO,
    ServiceDTO,
    ServiceUpdateRequestDTO,
)


def service_to_dto(service: Service) -> ServiceDTO:
    return ServiceDTO.model_validate(service)


class ServicesService:
    """Department service catalog."""

    def __init__(self, repository: ServiceRepository = Depends()) -> None:
        self.repository = repository

    async def _require_department(self, department_id: UUID) -> None:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError

    async def list_services(self, department_id: UUID) -> list[ServiceDTO]:
        await self._require_department(department_id)
        services = await self.repository.list_by_department(department_id)
        return [service_to_dto(service) for service in services]

    async def list_active_services(self, department_id: UUID) -> list[ServiceDTO]:
        await self._require_department(department_id)
        services = await self.repository.list_active_by_department(department_id)
        return [service_to_dto(service) for service in services]

    async def get_service(self, department_id: UUID, service_id: UUID) -> ServiceDTO:
        service = await self.repository.get_in_department(department_id, service_id)
        if service is None:
            raise ServiceNotFoundError
        return service_to_dto(service)

    async def create_service(self, department_id: UUID, payload: ServiceCreateRequestDTO) -> ServiceDTO:
        await self._require_department(department_id)
        service = Service(
            department_id=department_id,
            name=payload.name,
            duration_time=payload.duration_time,
            is_active=payload.is_active,
        )
        await self.repository.add(service)
        return service_to_dto(service)

    async def update_service(
        self,
        department_id: UUID,
        service_id: UUID,
        payload: ServiceUpdateRequestDTO,
    ) -> ServiceDTO:
        service = await self.repository.get_in_department(department_id, service_id)
        if service is None:
            raise ServiceNotFoundError

        if payload.name is not None:
            service.name = payload.name
        if payload.duration_time is not None:
            service.duration_time = payload.duration_time
        if payload.is_active is not None:
            service.is_active = payload.is_active

        await self.repository.save()
        return service_to_dto(service)
