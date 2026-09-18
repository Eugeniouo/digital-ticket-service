from datetime import time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
