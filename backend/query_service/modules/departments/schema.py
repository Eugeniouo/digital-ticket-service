from datetime import time
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DepartmentDTO(BaseModel):
    """Public department information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str
    open_time: time
    close_time: time
    is_active: bool
