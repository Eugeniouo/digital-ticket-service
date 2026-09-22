from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from query_service.database.models.staff import Staff, StaffRole
from query_service.modules.auth.dependencies import get_current_staff
from query_service.modules.auth.exceptions import (
    DepartmentNotFoundError,
    DuplicateUsernameError,
    InactiveStaffError,
    InvalidCredentialsError,
    InvalidStaffDepartmentError,
    StaffCreateForbiddenError,
    StaffNotFoundError,
)
from query_service.modules.auth.schema import (
    SignInRequest,
    StaffCreateRequest,
    StaffDTO,
    StaffPasswordChangeRequest,
    TokenResponse,
)
from query_service.modules.auth.service import AuthService, staff_to_dto

auth_router = APIRouter()
staff_router = APIRouter()


@auth_router.post("/signin", response_model=TokenResponse)
async def sign_in(
    payload: SignInRequest,
    svc: AuthService = Depends(),
) -> TokenResponse:
    try:
        return await svc.sign_in(payload.username, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        ) from exc
    except InactiveStaffError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff account is inactive",
        ) from exc


@auth_router.get("/me", response_model=StaffDTO)
async def me(
    staff: Staff = Depends(get_current_staff),
) -> StaffDTO:
    return staff_to_dto(staff)


@staff_router.get("", response_model=list[StaffDTO])
async def list_staff(
    staff: Staff = Depends(get_current_staff),
    svc: AuthService = Depends(),
) -> list[StaffDTO]:
    if staff.role not in (StaffRole.ADMIN, StaffRole.ROOT):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return await svc.list_staff(staff)


@staff_router.post("", response_model=StaffDTO, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffCreateRequest,
    staff: Staff = Depends(get_current_staff),
    svc: AuthService = Depends(),
) -> StaffDTO:
    if staff.role not in (StaffRole.ADMIN, StaffRole.ROOT):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        return await svc.create_staff(staff, payload)
    except StaffCreateForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from exc
    except InvalidStaffDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Root user cannot do this action",
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        ) from exc
    except DuplicateUsernameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc


@staff_router.patch(
    "/{staff_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def change_staff_password(
    staff_id: UUID,
    payload: StaffPasswordChangeRequest,
    staff: Staff = Depends(get_current_staff),
    svc: AuthService = Depends(),
) -> None:
    if staff.role not in (StaffRole.ADMIN, StaffRole.ROOT):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        await svc.change_password(staff, staff_id, payload.password)
    except StaffCreateForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from exc
    except StaffNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found") from exc


# TODO: deactivate user
# TODO: change role, department
# TODO: delete
