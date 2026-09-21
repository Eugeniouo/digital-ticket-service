from datetime import time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RuleSeconds = Annotated[int, Field(ge=0, le=86400)]


class DepartmentDTO(BaseModel):
    """Public department information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str
    open_time: time
    close_time: time
    is_active: bool


class DepartmentCreateRequestDTO(BaseModel):
    """Payload for creating a department."""

    name: str = Field(min_length=1)
    address: str = Field(min_length=1)
    open_time: time
    close_time: time
    is_active: bool = True


class QueueRulesDTO(BaseModel):
    """Department queue priority coefficients, in seconds."""

    bonus_web: RuleSeconds
    bonus_qr: RuleSeconds
    bonus_walk_in: RuleSeconds
    max_wait_web: RuleSeconds
    max_wait_qr: RuleSeconds
    max_wait_walk_in: RuleSeconds


class QueueRulesUpdateDTO(BaseModel):
    """Partial update of department queue priority coefficients."""

    model_config = ConfigDict(extra="forbid")

    bonus_web: int | None = Field(default=None, ge=0, le=86400)
    bonus_qr: int | None = Field(default=None, ge=0, le=86400)
    bonus_walk_in: int | None = Field(default=None, ge=0, le=86400)
    max_wait_web: int | None = Field(default=None, ge=0, le=86400)
    max_wait_qr: int | None = Field(default=None, ge=0, le=86400)
    max_wait_walk_in: int | None = Field(default=None, ge=0, le=86400)
