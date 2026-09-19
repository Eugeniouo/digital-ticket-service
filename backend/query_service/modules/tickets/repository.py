from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.ticket_labels import TicketCounter
from query_service.modules.tickets.exceptions import TicketNotFoundError


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

    async def count_tickets_before(self, target_ticket: Ticket) -> int:
        """
        Считает количество талонов в статусе QUEUED перед нами.
        Благодаря priority_key нам не нужно джойнить таблицу Slot
        или проверять даты, это все учтено в самом ключе.
        """
        stmt = select(func.count(Ticket.id)).where(
            Ticket.department_id == target_ticket.department_id,
            Ticket.status == TicketStatus.QUEUED,
            Ticket.id != target_ticket.id,
            or_(
                Ticket.priority_key < target_ticket.priority_key,
                (Ticket.priority_key == target_ticket.priority_key) & (Ticket.created_at < target_ticket.created_at),
            ),
        )

        return await self.session.scalar(stmt) or 0

    async def get_next_ticket_number(self, department_id: UUID, prefix: str) -> int:
        """
        Атомарно получает следующий номер талона для конкретного отделения, дня и префикса.
        """
        today = datetime.now(UTC).date()

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

    async def requeue_ticket(self, ticket_id: UUID, elapsed_seconds: int = 0) -> Ticket:
        """Возврат в QUEUED. Клиент не теряет место, a сдвигается вперед на потраченное время."""
        ticket = await self.get_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError

        ticket.status = TicketStatus.QUEUED
        ticket.window_id = None

        new_key = ticket.priority_key - elapsed_seconds
        ticket.priority_key = max(0, new_key)

        await self.session.flush()
        return ticket
