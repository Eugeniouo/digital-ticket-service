from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from query_service.database.models.service import ServiceKind


class ServiceDTO(BaseModel):
    """Service as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    name: str
    kind: ServiceKind
    duration_time: int
    is_active: bool


class ServiceCreateRequestDTO(BaseModel):
    """Payload for creating a service in a department."""

    name: str = Field(min_length=1)
    kind: ServiceKind
    duration_time: int = Field(default=10, gt=0)
    is_active: bool = True


class ServiceUpdateRequestDTO(BaseModel):
    """Payload for updating a service. Omitted fields stay unchanged."""

    name: str | None = Field(default=None, min_length=1)
    kind: ServiceKind | None = None
    duration_time: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
