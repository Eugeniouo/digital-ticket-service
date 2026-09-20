from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from query_service.database.models.window import WindowStatus


class WindowDTO(BaseModel):
    """Window as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    label: str
    status: WindowStatus
    service_ids: list[UUID]
    current_operator_id: UUID | None = None


class WindowCreateRequestDTO(BaseModel):
    """Payload for creating a window."""

    label: str = Field(min_length=1, max_length=100)
    service_ids: list[UUID] = Field(default_factory=list)


class WindowUpdateRequestDTO(BaseModel):
    """Payload for updating a window. Omitted fields stay unchanged."""

    status: WindowStatus | None = None
    service_ids: list[UUID] | None = None


class WindowRedirectRequestDTO(BaseModel):
    """Payload for redirecting the current ticket to another service."""

    service_id: UUID
