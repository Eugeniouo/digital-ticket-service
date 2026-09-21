from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from query_service.database.models.department import Department
from query_service.database.models.staff import Staff
from query_service.modules.auth.dependencies import require_admin, require_root
from query_service.modules.departments.exceptions import DepartmentNotFoundError
from query_service.modules.departments.schema import (
    DepartmentCreateRequestDTO,
    DepartmentDTO,
    QueueRulesDTO,
    QueueRulesUpdateDTO,
)
from query_service.modules.departments.service import DepartmentService

router = APIRouter()


@router.get("", response_model=list[DepartmentDTO])
async def get_departments(svc: DepartmentService = Depends()) -> list[Department]:
    """Return all departments, including inactive ones, ordered by name and ID."""
    return await svc.get_all()


@router.post("", response_model=DepartmentDTO, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreateRequestDTO,
    svc: DepartmentService = Depends(),
    _staff: Staff = Depends(require_root),
) -> Department:
    return await svc.create(payload)


@router.get("/{department_id}", response_model=DepartmentDTO, responses={404: {"description": "Department not found"}})
async def get_department(department_id: UUID, svc: DepartmentService = Depends()) -> Department:
    try:
        return await svc.get_by_id(department_id)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.get(
    "/{department_id}/queue-rules",
    response_model=QueueRulesDTO,
    responses={404: {"description": "Department not found"}},
    summary="Queue priority rules for the department head",
)
async def get_queue_rules(
    department_id: UUID,
    svc: DepartmentService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> QueueRulesDTO:
    try:
        return await svc.get_queue_rules(department_id)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.patch(
    "/{department_id}/queue-rules",
    response_model=QueueRulesDTO,
    responses={404: {"description": "Department not found"}},
    summary="Update queue priority rules for the department",
)
async def update_queue_rules(
    department_id: UUID,
    payload: QueueRulesUpdateDTO,
    svc: DepartmentService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> QueueRulesDTO:
    try:
        return await svc.update_queue_rules(department_id, payload)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc
