from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from query_service.database.models.staff import StaffRole

MAX_POSSIBLE_NAME = 50
MAX_POSSIBLE_PASSWORD = 128


class StaffDTO(BaseModel):
    """Staff as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    role: StaffRole
    department_id: UUID | None
    is_active: bool


class SignInRequest(BaseModel):
    """Login payload."""

    username: str = Field(min_length=1, max_length=MAX_POSSIBLE_NAME)
    password: str = Field(min_length=1, max_length=MAX_POSSIBLE_PASSWORD)


class TokenResponse(BaseModel):
    """JWT issued after a successful sign-in."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    staff: StaffDTO


class StaffCreateRequest(BaseModel):
    """Create a staff account."""

    # perform strip for UX convenience outside of validation
    username: str = Field(min_length=1, max_length=MAX_POSSIBLE_NAME)
    password: str = Field(min_length=1, max_length=MAX_POSSIBLE_PASSWORD)
    role: StaffRole
    department_id: UUID | None = None
