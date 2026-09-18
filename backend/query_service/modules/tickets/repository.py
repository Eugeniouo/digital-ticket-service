from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.ticket_labels import TicketCounter
from query_service.modules.tickets.exceptions import SlotNotFoundError, TicketNotFoundError


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
        Сравнивает время создания для QR/WALK_IN и время слота для WEB.
        """
        if target_ticket.source == TicketSource.WEB:
            slot = target_ticket.slot

            if not slot:
                slot = await self.session.get(Slot, target_ticket.slot_id)

            if not slot:
                raise SlotNotFoundError

            target_dt = datetime.combine(slot.slot_date, slot.slot_time).replace(tzinfo=UTC)
        else:
            target_dt = target_ticket.created_at

        target_date = target_dt.date()
        target_time = target_dt.time()

        stmt = (
            select(func.count(Ticket.id))
            .outerjoin(Ticket.slot)
            .where(
                Ticket.department_id == target_ticket.department_id,
                Ticket.status == TicketStatus.QUEUED,
                Ticket.id != target_ticket.id,
                or_(
                    (Ticket.source.in_([TicketSource.QR, TicketSource.WALK_IN])) & (Ticket.created_at < target_dt),
                    (Ticket.source == TicketSource.WEB)
                    & or_(Slot.slot_date < target_date, (Slot.slot_date == target_date) & (Slot.slot_time < target_time)),
                ),
            )
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
                current_value=1,  # Если записи нет, начнем с 1
            )
            # Формируем запрос INSERT ON CONFLICT
            .on_conflict_do_update(
                index_elements=["department_id", "date", "prefix"],
                set_={"current_value": TicketCounter.current_value + 1},
            )
            .returning(TicketCounter.current_value)
        )

        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one()
