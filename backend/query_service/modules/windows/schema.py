from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from query_service.database.models.window import WindowStatus
from query_service.modules.tickets.schema import TicketResponse


class WindowDTO(BaseModel):
    """Window as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    label: str
    status: WindowStatus
    service_ids: list[UUID]
    open_service_ids: list[UUID] = Field(default_factory=list)
    current_operator_id: UUID | None = None


class WindowCreateRequestDTO(BaseModel):
    """Payload for creating a window."""

    label: str = Field(min_length=1, max_length=100)
    service_ids: list[UUID] = Field(default_factory=list)


class WindowUpdateRequestDTO(BaseModel):
    """Admin catalog update. Omitted fields stay unchanged."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    service_ids: list[UUID] | None = None


class WindowOpenRequestDTO(BaseModel):
    """Operator shift open. Omitted open_service_ids means all allowed services."""

    open_service_ids: list[UUID] | None = None


class WindowQueueResponse(BaseModel):
    """Tickets at this window: current plus call-next order."""

    current: TicketResponse | None = None
    upcoming: list[TicketResponse]


class WindowRedirectRequestDTO(BaseModel):
    """Payload for redirecting the current ticket to another service."""

    service_id: UUID
