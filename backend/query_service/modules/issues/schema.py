from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from query_service.database.models.issue import IssueStatus


class IssueCreateRequest(BaseModel):
    """Payload for issue creation."""

    message: str = Field(..., min_length=1, description="issue description")


class IssueResponse(BaseModel):
    """API responce with issue data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    reporter_id: UUID | None
    message: str
    status: IssueStatus
    created_at: datetime
    resolved_at: datetime | None
