from datetime import time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

RuleSeconds = Annotated[int, Field(ge=0, le=86400)]

MIN_DEPARTMENT_CODE = 3
MAX_DEPARTMENT_CODE = 16
DEPARTMENT_CODE_PATTERN = r"^[0-9A-Z]+$"


def _normalize_department_code(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper()
    return value


DepartmentCode = Annotated[
    str,
    BeforeValidator(_normalize_department_code),
    Field(min_length=MIN_DEPARTMENT_CODE, max_length=MAX_DEPARTMENT_CODE, pattern=DEPARTMENT_CODE_PATTERN),
]


class DepartmentDTO(BaseModel):
    """Public department information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    address: str
    open_time: time
    close_time: time
    is_active: bool


class DepartmentCreateRequestDTO(BaseModel):
    """Payload for creating a department."""

    code: DepartmentCode
    address: str = Field(min_length=1)
    open_time: time
    close_time: time
    is_active: bool = True


class DepartmentQrDTO(BaseModel):
    """QR poster payload for a department."""

    department_id: UUID
    code: str
    address: str
    payload: str
    svg: str


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
