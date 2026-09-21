from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.ticket_status_history import TicketStatusHistory
from query_service.database.models.window import Window
from query_service.modules.analytics.compute import CompletedVisit, HistoryPoint, WindowRef


class AnalyticsRepository:
    """Read-only queries for one department day."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_department(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def list_completed(
        self,
        department_id: UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> list[CompletedVisit]:
        stmt = (
            select(Ticket, Slot.slot_date, Slot.slot_time)
            .outerjoin(Slot, Slot.id == Ticket.slot_id)
            .where(
                Ticket.department_id == department_id,
                Ticket.status == TicketStatus.COMPLETED,
                Ticket.completed_at >= day_start,
                Ticket.completed_at < day_end,
            )
        )
        result = await self.session.execute(stmt)
        visits: list[CompletedVisit] = []
        for ticket, slot_date, slot_time in result.all():
            completed_at = ticket.completed_at
            if completed_at is None:
                continue

            visits.append(
                CompletedVisit(
                    ticket_id=ticket.id,
                    source=ticket.source,
                    started_at=ticket.started_at,
                    completed_at=completed_at,
                    slot_date=slot_date,
                    slot_time=slot_time,
                ),
            )

        return visits

    async def count_arrivals(
        self,
        department_id: UUID,
        day: date,
        day_start: datetime,
        day_end: datetime,
    ) -> dict[TicketSource, int]:
        """Appointments by slot date; QR and walk-in by the moment the ticket was issued."""
        web_stmt = (
            select(func.count())
            .select_from(Ticket)
            .join(Slot, Slot.id == Ticket.slot_id)
            .where(
                Ticket.department_id == department_id,
                Ticket.source == TicketSource.WEB,
                Slot.slot_date == day,
            )
        )
        live_stmt = (
            select(Ticket.source, func.count())
            .where(
                Ticket.department_id == department_id,
                Ticket.source.in_((TicketSource.QR, TicketSource.WALK_IN)),
                Ticket.created_at >= day_start,
                Ticket.created_at < day_end,
            )
            .group_by(Ticket.source)
        )

        counts: dict[TicketSource, int] = {TicketSource.WEB: int(await self.session.scalar(web_stmt) or 0)}
        result = await self.session.execute(live_stmt)
        for source, count in result.all():
            counts[TicketSource(source)] = int(count)

        return counts

    async def list_history(
        self,
        department_id: UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> list[HistoryPoint]:
        """Journal rows needed to rebuild intervals that overlap the day.

        An event inside a one-day margin is not enough on its own: `started` can be
        older, a ticket can still be SERVING with no fresh event, and the last visit
        stored on the ticket row can span the day without a journal row inside it.
        Requeue drops `started_at`, so a serving stretch of several days that was
        later returned to the queue is visible only when one of its events falls
        inside the margin.
        """
        ticket_ids = await self._history_ticket_ids(department_id, day_start, day_end)
        if not ticket_ids:
            return []

        stmt = (
            select(TicketStatusHistory)
            .where(TicketStatusHistory.ticket_id.in_(ticket_ids))
            .order_by(
                TicketStatusHistory.ticket_id,
                TicketStatusHistory.changed_at,
                TicketStatusHistory.id,
            )
        )
        rows = await self.session.scalars(stmt)
        return [
            HistoryPoint(
                ticket_id=row.ticket_id,
                new_status=row.new_status,
                reason=row.reason,
                window_id=row.window_id,
                changed_at=row.changed_at,
                id=row.id,
            )
            for row in rows.all()
        ]

    async def list_windows(self, department_id: UUID) -> list[WindowRef]:
        stmt = select(Window.id, Window.label).where(Window.department_id == department_id).order_by(Window.label, Window.id)
        result = await self.session.execute(stmt)
        return [WindowRef(window_id=window_id, label=label) for window_id, label in result.all()]

    async def _history_ticket_ids(
        self,
        department_id: UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> set[UUID]:
        margin_start = day_start - timedelta(days=1)
        margin_end = day_end + timedelta(days=1)
        touched = (
            select(TicketStatusHistory.ticket_id)
            .join(Ticket, Ticket.id == TicketStatusHistory.ticket_id)
            .where(
                Ticket.department_id == department_id,
                TicketStatusHistory.changed_at >= margin_start,
                TicketStatusHistory.changed_at < margin_end,
            )
        )
        serving = select(Ticket.id).where(
            Ticket.department_id == department_id,
            Ticket.status == TicketStatus.SERVING,
        )
        # Last visit on the ticket row overlaps the day even if both journal
        # endpoints lie outside the one-day margin.
        spanning = select(Ticket.id).where(
            Ticket.department_id == department_id,
            Ticket.status.in_((TicketStatus.SERVING, TicketStatus.COMPLETED)),
            Ticket.started_at.is_not(None),
            Ticket.started_at < day_end,
            or_(Ticket.completed_at.is_(None), Ticket.completed_at > day_start),
        )
        ids: set[UUID] = set()
        for stmt in (touched, serving, spanning):
            ids.update((await self.session.scalars(stmt)).all())

        return ids
