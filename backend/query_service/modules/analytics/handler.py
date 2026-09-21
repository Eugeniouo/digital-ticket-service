from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from query_service.database.models.staff import Staff
from query_service.modules.analytics.exceptions import DepartmentNotFoundError
from query_service.modules.analytics.schema import DayAnalyticsResponse
from query_service.modules.analytics.service import AnalyticsService
from query_service.modules.auth.dependencies import require_admin

router = APIRouter()


@router.get(
    "",
    response_model=DayAnalyticsResponse,
    responses={404: {"description": "Department not found"}},
    summary="Day analytics for the department head",
)
async def get_day_analytics(
    department_id: UUID,
    day: Annotated[
        date | None,
        Query(alias="date", description="Calendar day in the department timezone. Defaults to today."),
    ] = None,
    svc: AnalyticsService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> DayAnalyticsResponse:
    """Served clients, wait, service time, arrivals, and window load for one day."""
    try:
        return await svc.get_day_analytics(department_id, day)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc
