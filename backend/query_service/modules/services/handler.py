from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from query_service.database.models.staff import Staff
from query_service.modules.auth.dependencies import require_admin
from query_service.modules.services.exceptions import DepartmentNotFoundError, ServiceNotFoundError
from query_service.modules.services.schema import (
    ServiceCreateRequestDTO,
    ServiceDTO,
    ServiceUpdateRequestDTO,
)
from query_service.modules.services.service import ServicesService

router = APIRouter()


@router.get(
    "",
    response_model=list[ServiceDTO],
    responses={404: {"description": "Department not found"}},
)
async def list_services(
    department_id: UUID,
    svc: ServicesService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> list[ServiceDTO]:
    try:
        return await svc.list_services(department_id)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.get(
    "/active",
    response_model=list[ServiceDTO],
    responses={404: {"description": "Department not found"}},
)
async def list_active_services(
    department_id: UUID,
    svc: ServicesService = Depends(),
) -> list[ServiceDTO]:
    try:
        return await svc.list_active_services(department_id)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.get(
    "/{service_id}",
    response_model=ServiceDTO,
    responses={404: {"description": "Service not found in this department"}},
)
async def get_service(
    department_id: UUID,
    service_id: UUID,
    svc: ServicesService = Depends(),
) -> ServiceDTO:
    try:
        return await svc.get_service(department_id, service_id)
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found in this department",
        ) from exc


@router.post(
    "",
    response_model=ServiceDTO,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Department not found"}},
)
async def create_service(
    department_id: UUID,
    payload: ServiceCreateRequestDTO,
    svc: ServicesService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> ServiceDTO:
    try:
        return await svc.create_service(department_id, payload)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.patch(
    "/{service_id}",
    response_model=ServiceDTO,
    responses={404: {"description": "Service not found in this department"}},
)
async def update_service(
    department_id: UUID,
    service_id: UUID,
    payload: ServiceUpdateRequestDTO,
    svc: ServicesService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> ServiceDTO:
    try:
        return await svc.update_service(department_id, service_id, payload)
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found in this department",
        ) from exc
