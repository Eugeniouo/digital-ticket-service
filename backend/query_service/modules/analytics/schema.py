from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

AppealChannel = Literal["appointment", "qr", "walk-in"]
HOURS_IN_DAY = 24


class HourlyServed(BaseModel):
    """One bar of the served-by-hour chart."""

    hour: int = Field(ge=0, le=HOURS_IN_DAY - 1)
    served_count: int = Field(ge=0)


class AppealSourceCount(BaseModel):
    """How many appeals arrived through one channel."""

    source: AppealChannel
    count: int = Field(ge=0)


class WindowLoad(BaseModel):
    """Service time against the department schedule, shared by every window."""

    window_id: UUID
    label: str
    served_seconds: int = Field(ge=0)
    schedule_open_seconds: int = Field(ge=0)
    load_ratio: float | None = None


class DayAnalyticsResponse(BaseModel):
    """Analytics of one department calendar day for the branch head.

    `hourly` is the served-count chart: always hours 0 through 23 in the
    department timezone, in that order, with explicit zeros. It is actual
    completions, not a forecast of the remaining hours.
    """

    department_id: UUID
    date: date
    timezone: str
    served_count: int = Field(ge=0)
    avg_wait_seconds: int | None = Field(default=None, ge=0)
    max_wait_seconds: int | None = Field(default=None, ge=0)
    avg_service_seconds: int | None = Field(default=None, ge=0)
    hourly: list[HourlyServed]
    sources: list[AppealSourceCount]
    windows: list[WindowLoad]

    @model_validator(mode="after")
    def chart_axes_are_complete(self) -> Self:
        """Reject a partial day chart before it reaches the client."""
        hours = [item.hour for item in self.hourly]
        if hours != list(range(HOURS_IN_DAY)):
            raise ValueError("hourly must list hours 0 through 23 in order")

        channels = [item.source for item in self.sources]
        if channels != ["appointment", "qr", "walk-in"]:
            raise ValueError("sources must list appointment, qr, and walk-in")

        return self
