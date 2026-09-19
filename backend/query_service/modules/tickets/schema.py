from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from query_service.database.models.ticket import TicketSource, TicketStatus


class TicketResponse(BaseModel):
    """Ticket as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    service_id: UUID
    window_id: UUID | None
    slot_id: UUID | None
    status: TicketStatus
    source: TicketSource
    ticket_label: str
    created_at: datetime
    called_at: datetime | None
    started_at: datetime | None = None
    completed_at: datetime | None
    canceled_at: datetime | None
    estimated_wait_time: int | None = None


class TicketCreateRequest(BaseModel):
    """Ticket Create Request."""

    model_config = ConfigDict(from_attributes=True)

    service_id: UUID
    source: TicketSource
    slot_id: UUID | None = None
