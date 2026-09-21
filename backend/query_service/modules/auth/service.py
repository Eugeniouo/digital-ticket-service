from uuid import UUID

from fastapi import Depends

from query_service.database.models.staff import Staff, StaffRole
from query_service.modules.auth.exceptions import (
    DepartmentNotFoundError,
    InactiveStaffError,
    InvalidCredentialsError,
    InvalidStaffDepartmentError,
    StaffCreateForbiddenError,
    StaffNotFoundError,
)
from query_service.modules.auth.repository import StaffRepository
from query_service.modules.auth.schema import StaffCreateRequest, StaffDTO, TokenResponse
from query_service.modules.auth.security import create_access_token, hash_password, verify_password


def staff_to_dto(staff: Staff) -> StaffDTO:
    """Map a staff row to the API DTO."""
    return StaffDTO(
        id=staff.id,
        username=staff.username,
        display_name=staff.display_name,
        role=staff.role,
        department_id=staff.department_id,
        is_active=staff.is_active,
    )


class AuthService:
    """Sign-in and staff account management."""

    def __init__(self, repository: StaffRepository = Depends()) -> None:
        self.repository = repository

    async def sign_in(self, username: str, password: str) -> TokenResponse:
        username = username.strip().lower()
        password = password.strip()

        staff = await self.repository.get_by_username(username)
        if staff is None or not verify_password(password, staff.password_hash):
            raise InvalidCredentialsError
        if not staff.is_active:
            raise InactiveStaffError

        token = create_access_token(staff.id, staff.role, staff.department_id)
        return TokenResponse(access_token=token, staff=staff_to_dto(staff))

    async def list_staff(self, actor: Staff) -> list[StaffDTO]:
        if actor.role == StaffRole.ROOT:
            rows = await self.repository.list_all()
        else:
            rows = await self.repository.list_by_department(actor.department_id)  # type: ignore[arg-type]

        return [staff_to_dto(row) for row in rows]

    async def create_staff(self, actor: Staff, payload: StaffCreateRequest) -> StaffDTO:
        department_id = payload.department_id
        self._validate_role_department(payload.role, department_id)
        self._authorize_create(actor, payload.role, department_id)

        if department_id is not None and not await self.repository.department_exists(department_id):
            raise DepartmentNotFoundError

        staff = Staff(
            username=payload.username.strip().lower(),
            display_name=payload.display_name.strip(),
            password_hash=hash_password(payload.password.strip()),
            role=payload.role,
            department_id=department_id,
        )
        created = await self.repository.add(staff)

        return staff_to_dto(created)

    async def change_password(self, actor: Staff, staff_id: UUID, password: str) -> None:
        target = await self.repository.get_by_id(staff_id)
        if target is None:
            raise StaffNotFoundError

        self._authorize_manage(actor, target)
        target.password_hash = hash_password(password.strip())
        await self.repository.save()

    def _validate_role_department(self, role: StaffRole, department_id: UUID | None) -> None:
        if role == StaffRole.ROOT and department_id is not None:
            raise InvalidStaffDepartmentError
        if role != StaffRole.ROOT and department_id is None:
            raise InvalidStaffDepartmentError

    def _authorize_create(self, actor: Staff, role: StaffRole, department_id: UUID | None) -> None:
        if actor.role == StaffRole.ROOT:
            return
        if actor.role != StaffRole.ADMIN:
            raise StaffCreateForbiddenError
        if role == StaffRole.ROOT:
            raise StaffCreateForbiddenError
        if department_id != actor.department_id:
            raise StaffCreateForbiddenError

    def _authorize_manage(self, actor: Staff, target: Staff) -> None:
        if actor.role == StaffRole.ROOT:
            return
        if actor.role != StaffRole.ADMIN:
            raise StaffCreateForbiddenError
        if target.role == StaffRole.ROOT:
            raise StaffCreateForbiddenError
        if target.department_id != actor.department_id:
            raise StaffCreateForbiddenError
