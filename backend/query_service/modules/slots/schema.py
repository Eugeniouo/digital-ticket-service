from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SlotDTO(BaseModel):
    """Slot as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    window_id: UUID
    service_id: UUID
    slot_date: date
    slot_time: time
    capacity: int
    booked_count: int


class SlotCreateRequestDTO(BaseModel):
    """Payload for creating a single slot."""

    window_id: UUID
    service_id: UUID
    slot_date: date
    slot_time: time
    capacity: int = Field(default=1, gt=0)


class SlotUpdateRequestDTO(BaseModel):
    """Payload for updating a slot. Omitted fields stay unchanged."""

    capacity: int = Field(gt=0)


class SlotGenerateRequestDTO(BaseModel):
    """Payload for generating slots for a day and service."""

    service_id: UUID
    slot_date: date
    capacity: int = Field(default=1, gt=0)
    duration: int = Field(gt=0, description="Slot step in minutes")


class SlotGenerateResponseDTO(BaseModel):
    """Result of slot generation."""

    created: int
    skipped: int
    slots: list[SlotDTO]
