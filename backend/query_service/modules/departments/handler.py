from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from query_service.database.models.department import Department
from query_service.modules.departments.schema import DepartmentDTO
from query_service.modules.departments.service import DepartmentService

router = APIRouter()


@router.get("", response_model=list[DepartmentDTO])
async def get_departments(service: DepartmentService = Depends()) -> list[Department]:
    """Return all departments, including inactive ones, ordered by name and ID."""
    return await service.get_all()


@router.get("/{department_id}", response_model=DepartmentDTO, responses={404: {"description": "Department not found"}})
async def get_department(department_id: UUID, service: DepartmentService = Depends()) -> Department:
    department = await service.get_by_id(department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department
