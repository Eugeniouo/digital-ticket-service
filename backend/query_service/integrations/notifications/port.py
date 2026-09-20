from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationEvent(StrEnum):
    TICKET_CALLED = "ticket.called"
    QUEUE_APPROACHING = "queue.approaching"


class NotificationMessage(BaseModel):
    """Payload sent to a notification gateway."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: NotificationEvent
    ticket_id: UUID
    ticket_label: str
    department_id: UUID
    window_label: str | None = None
    estimated_wait_time: int | None = None


class NotificationGateway(Protocol):
    async def send(self, message: NotificationMessage) -> None:
        """Deliver one notification. Raise NotificationDeliveryError on failure."""
