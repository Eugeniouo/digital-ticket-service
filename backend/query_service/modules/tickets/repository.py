from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.ticket_labels import TicketCounter
from query_service.modules.tickets.priority import (
    now_in_queue_tz,
    now_priority_seconds,
    overdue_live_rank,
    overdue_live_sql,
    queue_eligible_sql,
    web_noshow_sql,
)


class TicketRepository:
    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, ticket: Ticket) -> Ticket:
        await self.session.refresh(ticket)
        return ticket

    async def create(self, ticket: Ticket) -> Ticket:
        self.session.add(ticket)
        await self.session.flush()
        await self.session.refresh(ticket)

        return ticket

    async def get_by_id(self, ticket_id: UUID) -> Ticket | None:
        return await self.session.get(Ticket, ticket_id)

    async def get_by_id_for_update(self, ticket_id: UUID) -> Ticket | None:
        return await self.session.scalar(select(Ticket).where(Ticket.id == ticket_id).with_for_update())

    async def lock_web_noshows(self, department_id: UUID) -> list[Ticket]:
        """Lock QUEUED WEB tickets past no-show for this department."""
        now_seconds = now_priority_seconds()

        return list(
            await self.session.scalars(
                select(Ticket)
                .where(
                    Ticket.department_id == department_id,
                    Ticket.status == TicketStatus.QUEUED,
                    web_noshow_sql(now_seconds),
                )
                .with_for_update(skip_locked=True),
            ),
        )

    async def count_tickets_before(self, target_ticket: Ticket) -> int:
        """
        Count QUEUED tickets ahead for the same service, using assign_next order:
        eligible only, then overdue_live, priority_key, created_at.
        """
        now_seconds = now_priority_seconds()
        overdue = overdue_live_sql(now_seconds)
        target_rank = overdue_live_rank(target_ticket.source, target_ticket.priority_key, now_seconds)

        ahead = or_(
            overdue < target_rank,
            and_(
                overdue == target_rank,
                Ticket.priority_key < target_ticket.priority_key,
            ),
            and_(
                overdue == target_rank,
                Ticket.priority_key == target_ticket.priority_key,
                Ticket.created_at < target_ticket.created_at,
            ),
        )

        stmt = select(func.count(Ticket.id)).where(
            Ticket.department_id == target_ticket.department_id,
            Ticket.service_id == target_ticket.service_id,
            Ticket.status == TicketStatus.QUEUED,
            Ticket.id != target_ticket.id,
            queue_eligible_sql(now_seconds),
            ahead,
        )

        return await self.session.scalar(stmt) or 0

    async def get_next_ticket_number(self, department_id: UUID, prefix: str) -> int:
        """
        Атомарно получает следующий номер талона для конкретного отделения, дня и префикса.
        """
        # Calendar day in queue timezone (not UTC) so series matches wall-clock queue day
        today = now_in_queue_tz().date()

        stmt = (
            insert(TicketCounter)
            .values(
                department_id=department_id,
                date=today,
                prefix=prefix,
                current_value=1,
            )
            .on_conflict_do_update(
                index_elements=["department_id", "date", "prefix"],
                set_={"current_value": TicketCounter.current_value + 1},
            )
            .returning(TicketCounter.current_value)
        )

        result = await self.session.execute(stmt)
        await self.session.flush()

        return result.scalar_one()
