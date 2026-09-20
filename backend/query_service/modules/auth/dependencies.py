from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from query_service.database.models.staff import Staff, StaffRole
from query_service.modules.auth.repository import StaffRepository
from query_service.modules.auth.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_optional_staff(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)], repository: StaffRepository = Depends()
) -> Staff | None:
    if creds is None or creds.scheme.lower() != "bearer":
        return None

    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None

    staff_id = payload.get("sub")
    if not isinstance(staff_id, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        staff = await repository.get_by_id(UUID(staff_id))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None
    if staff is None or not staff.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return staff


async def get_current_staff(staff: Staff | None = Depends(get_optional_staff)) -> Staff:
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return staff


async def require_operator(department_id: UUID, staff: Staff = Depends(get_current_staff)) -> Staff:
    if staff.role != StaffRole.OPERATOR or staff.department_id != department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return staff


async def require_admin(department_id: UUID, staff: Staff = Depends(get_current_staff)) -> Staff:
    if staff.role == StaffRole.ROOT:
        return staff
    if staff.role != StaffRole.ADMIN or staff.department_id != department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return staff


async def require_root(staff: Staff = Depends(get_current_staff)) -> Staff:
    if staff.role != StaffRole.ROOT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return staff


async def require_department_staff(department_id: UUID, staff: Staff = Depends(get_current_staff)) -> Staff:
    if staff.role == StaffRole.ROOT:
        return staff
    if staff.role in (StaffRole.OPERATOR, StaffRole.ADMIN) and staff.department_id == department_id:
        return staff

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
