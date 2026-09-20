from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.issue import Issue


class IssuesRepository:
    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_department(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def get_by_id(self, issue_id: UUID) -> Issue | None:
        return await self.session.get(Issue, issue_id)

    async def create(self, issue: Issue) -> Issue:
        self.session.add(issue)
        await self.session.flush()
        await self.session.refresh(issue)
        return issue

    async def save(self) -> None:
        await self.session.flush()

    async def list_by_department(self, department_id: UUID) -> list[Issue]:
        stmt = select(Issue).where(Issue.department_id == department_id).order_by(Issue.created_at.desc())
        result = await self.session.scalars(stmt)
        return list(result.all())
