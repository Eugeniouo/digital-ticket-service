from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from query_service.database.models.department import Department
from query_service.database.models.staff import Staff
from query_service.modules.auth.dependencies import require_root
from query_service.modules.departments.exceptions import DepartmentNotFoundError
from query_service.modules.departments.schema import DepartmentCreateRequestDTO, DepartmentDTO
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
