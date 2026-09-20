from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends

from query_service.database.models.issue import Issue, IssueStatus
from query_service.modules.issues.exceptions import (
    DepartmentNotFoundError,
    InvalidIssueStateError,
    IssueNotFoundError,
)
from query_service.modules.issues.repository import IssuesRepository
from query_service.modules.issues.schema import IssueCreateRequest, IssueResponse


class IssuesService:
    def __init__(self, repository: IssuesRepository = Depends()) -> None:
        self.repository = repository

    async def _validate_department(self, department_id: UUID) -> None:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError

    async def report_issue(
        self,
        department_id: UUID,
        reporter_id: UUID,
        payload: IssueCreateRequest,
    ) -> IssueResponse:
        await self._validate_department(department_id)

        issue_model = Issue(
            department_id=department_id,
            reporter_id=reporter_id,
            message=payload.message,
        )
        created_issue = await self.repository.create(issue_model)

        return IssueResponse.model_validate(created_issue)

    async def get_department_issue(self, department_id: UUID) -> list[IssueResponse]:
        await self._validate_department(department_id)

        issues = await self.repository.list_by_department(department_id)

        return [IssueResponse.model_validate(issue) for issue in issues]

    async def resolve_issue(self, department_id: UUID, issue_id: UUID) -> IssueResponse:
        await self._validate_department(department_id)

        issue = await self.repository.get_by_id(issue_id)
        if issue is None or issue.department_id != department_id:
            raise IssueNotFoundError
        if issue.status != IssueStatus.OPEN:
            raise InvalidIssueStateError

        issue.status = IssueStatus.RESOLVED
        issue.resolved_at = datetime.now(UTC)
        await self.repository.save()

        return IssueResponse.model_validate(issue)
