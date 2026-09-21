from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from query_service.database.models.staff import StaffRole

MIN_USERNAME = 3
MAX_USERNAME = 40
USERNAME_PATTERN = r"^[a-z0-9._-]+$"
MAX_DISPLAY_NAME = 100
MIN_PASSWORD = 8
MAX_PASSWORD = 128


def _strip(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_username(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


Password = Annotated[
    str,
    BeforeValidator(_strip),
    Field(min_length=MIN_PASSWORD, max_length=MAX_PASSWORD),
]
DisplayName = Annotated[
    str,
    BeforeValidator(_strip),
    Field(min_length=1, max_length=MAX_DISPLAY_NAME),
]
SignInUsername = Annotated[
    str,
    BeforeValidator(_normalize_username),
    Field(min_length=MIN_USERNAME, max_length=MAX_USERNAME, pattern=USERNAME_PATTERN),
]
CreateUsername = Annotated[
    str,
    BeforeValidator(_strip),
    Field(min_length=MIN_USERNAME, max_length=MAX_USERNAME, pattern=USERNAME_PATTERN),
]


class StaffDTO(BaseModel):
    """Staff as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    role: StaffRole
    department_id: UUID | None
    is_active: bool


class SignInRequest(BaseModel):
    """Login payload."""

    username: SignInUsername
    password: Password


class TokenResponse(BaseModel):
    """JWT issued after a successful sign-in."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    staff: StaffDTO


class StaffCreateRequest(BaseModel):
    """Create a staff account."""

    username: CreateUsername
    display_name: DisplayName
    password: Password
    role: StaffRole
    department_id: UUID | None = None


class StaffPasswordChangeRequest(BaseModel):
    """Set a new password for a staff account."""

    password: Password
