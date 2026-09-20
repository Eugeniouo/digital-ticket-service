from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from query_service.database.models.staff import Staff
from query_service.modules.auth.dependencies import require_admin, require_department_staff
from query_service.modules.issues.exceptions import (
    DepartmentNotFoundError,
    InvalidIssueStateError,
    IssueNotFoundError,
)
from query_service.modules.issues.schema import IssueCreateRequest, IssueResponse
from query_service.modules.issues.service import IssuesService

router = APIRouter()


@router.post(
    "",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Department not found"}},
    summary="Report an issue",
)
async def create_issue(
    department_id: UUID,
    payload: IssueCreateRequest,
    svc: IssuesService = Depends(),
    staff: Staff = Depends(require_department_staff),
) -> IssueResponse:
    try:
        return await svc.report_issue(department_id, staff.id, payload)

    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.get(
    "",
    response_model=list[IssueResponse],
    responses={404: {"description": "Department not found"}},
    summary="Get the list of all problems",
)
async def list_issues(
    department_id: UUID,
    svc: IssuesService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> list[IssueResponse]:
    try:
        return await svc.get_department_issue(department_id)

    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.post(
    "/{issue_id}:resolve",
    response_model=IssueResponse,
    responses={
        404: {"description": "Department or issue not found"},
        409: {"description": "Issue is already resolved"},
    },
    summary="Resolve an issue",
)
async def resolve_issue(
    department_id: UUID,
    issue_id: UUID,
    svc: IssuesService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> IssueResponse:
    try:
        return await svc.resolve_issue(department_id, issue_id)

    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc

    except IssueNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found in this department",
        ) from exc

    except InvalidIssueStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Issue is already resolved",
        ) from exc
