from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.ticket_labels import TicketCounter
from query_service.modules.tickets.exceptions import InvalidTicketStateError, TicketNotFoundError
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

    async def create(self, ticket: Ticket) -> Ticket:
        self.session.add(ticket)
        await self.session.flush()
        await self.session.refresh(ticket)

        return ticket

    async def get_by_id(self, ticket_id: UUID) -> Ticket | None:
        return await self.session.get(Ticket, ticket_id)

    async def get_by_id_for_update(self, ticket_id: UUID) -> Ticket | None:
        return await self.session.scalar(select(Ticket).where(Ticket.id == ticket_id).with_for_update())

    async def update_status(self, ticket_id: UUID, status: TicketStatus) -> Ticket:
        ticket = await self.get_by_id(ticket_id)

        if not ticket:
            raise TicketNotFoundError

        ticket.status = status

        now = datetime.now(UTC)
        if status == TicketStatus.CANCELED:
            ticket.canceled_at = now
        elif status == TicketStatus.CALLED:
            ticket.called_at = now
        elif status == TicketStatus.SERVING:
            ticket.started_at = now
        elif status == TicketStatus.COMPLETED:
            ticket.completed_at = now

        await self.session.flush()
        await self.session.refresh(ticket)

        return ticket

    async def expire_web_noshows(self, department_id: UUID) -> list[UUID]:
        """Cancel QUEUED WEB tickets past no-show. Returns slot_ids to free."""
        now_seconds = now_priority_seconds()

        tickets = list(
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
        if not tickets:
            return []

        now = datetime.now(UTC)
        slot_ids: list[UUID] = []
        for ticket in tickets:
            ticket.status = TicketStatus.CANCELED
            ticket.canceled_at = now
            if ticket.slot_id is not None:
                slot_ids.append(ticket.slot_id)

        await self.session.flush()

        return slot_ids

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

    async def requeue_ticket(self, ticket: Ticket, elapsed_seconds: int = 0) -> Ticket:
        """Возврат в QUEUED. Клиент не теряет место, a сдвигается вперед на потраченное время.

        Caller must hold the ticket row locked (FOR UPDATE).
        """
        if ticket.status not in (TicketStatus.CALLED, TicketStatus.SERVING):
            raise InvalidTicketStateError

        ticket.status = TicketStatus.QUEUED
        ticket.window_id = None
        ticket.called_at = None
        ticket.started_at = None
        ticket.priority_key = max(0, ticket.priority_key - elapsed_seconds)

        await self.session.flush()
        return ticket
