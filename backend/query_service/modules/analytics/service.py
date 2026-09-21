from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends

from query_service.modules.analytics.compute import build_day_analytics, day_bounds
from query_service.modules.analytics.exceptions import DepartmentNotFoundError
from query_service.modules.analytics.repository import AnalyticsRepository
from query_service.modules.analytics.schema import DayAnalyticsResponse
from query_service.settings import settings


class AnalyticsService:
    """Day analytics for one department."""

    def __init__(self, repository: AnalyticsRepository = Depends()) -> None:
        self.repository = repository

    async def get_day_analytics(self, department_id: UUID, day: date | None) -> DayAnalyticsResponse:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError

        tz = ZoneInfo(settings.queue_timezone)
        now = datetime.now(tz)
        if day is None:
            day = now.date()

        day_start, day_end = day_bounds(day, tz)
        return build_day_analytics(
            department_id=department_id,
            day=day,
            timezone_name=settings.queue_timezone,
            tz=tz,
            open_time=department.open_time,
            close_time=department.close_time,
            now=now,
            completed=await self.repository.list_completed(department_id, day_start, day_end),
            history=await self.repository.list_history(department_id, day_start, day_end),
            source_counts=await self.repository.count_arrivals(department_id, day, day_start, day_end),
            windows=await self.repository.list_windows(department_id),
        )
