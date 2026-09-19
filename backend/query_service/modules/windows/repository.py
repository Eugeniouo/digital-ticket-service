from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import instance_state, set_committed_value

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.tickets.priority import BONUS_SECONDS, MAX_WAIT_SECONDS, now_priority_seconds
from query_service.modules.windows.exceptions import (
    ServiceNotInDepartmentError,
    TicketAlreadyInProgressError,
)


class WindowsRepository:
    """Database access for windows, their services, and queue assignment."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_department(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def list_by_department(self, department_id: UUID) -> list[Window]:
        result = await self.session.scalars(
            select(Window)
            .where(Window.department_id == department_id)
            .options(selectinload(Window.services))
            .order_by(Window.label, Window.id),
        )
        return list(result.all())

    async def get_in_department(self, department_id: UUID, window_id: UUID) -> Window | None:
        return await self.session.scalar(
            select(Window).where(Window.id == window_id, Window.department_id == department_id).options(selectinload(Window.services))
        )

    async def label_exists(self, department_id: UUID, label: str) -> bool:
        window_id = await self.session.scalar(
            select(Window.id).where(Window.department_id == department_id, Window.label == label),
        )
        return window_id is not None

    async def add(self, window: Window, service_ids: list[UUID]) -> Window:
        self.session.add(window)
        await self.replace_services(window, service_ids)
        await self.session.flush()
        return window

    async def update(
        self,
        window: Window,
        *,
        status: WindowStatus | None = None,
        service_ids: list[UUID] | None = None,
    ) -> Window:
        if status is not None:
            window.status = status
        if service_ids is not None:
            await self.replace_services(window, service_ids)
        await self.session.flush()
        return window

    async def replace_services(self, window: Window, service_ids: list[UUID]) -> None:
        unique_ids = list(dict.fromkeys(service_ids))
        new_services: list[Service] = []
        if unique_ids:
            services = list(
                await self.session.scalars(
                    select(Service).where(
                        Service.id.in_(unique_ids),
                        Service.department_id == window.department_id,
                    ),
                ),
            )
            if len(services) != len(unique_ids):
                raise ServiceNotInDepartmentError
            by_id = {service.id: service for service in services}
            new_services = [by_id[service_id] for service_id in unique_ids]

        # TODO: выглядит как костыль
        if "services" not in instance_state(window).dict:
            set_committed_value(window, "services", [])
        window.services = new_services

    async def ticket_exists_for_window(self, window_id: UUID) -> bool:
        ticket_id = await self.session.scalar(
            select(Ticket.id).where(
                Ticket.window_id == window_id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            ),
        )
        return ticket_id is not None

    async def assign_next_ticket(self, window: Window) -> Ticket | None:
        # Serialize call-next on this window (two parallel calls must not both pass empty in-progress)
        await self.session.scalar(select(Window.id).where(Window.id == window.id).with_for_update())

        in_progress = await self.session.scalar(
            select(Ticket.id).where(
                Ticket.window_id == window.id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            ),
        )
        if in_progress is not None:
            raise TicketAlreadyInProgressError

        service_ids = [service.id for service in window.services]
        if not service_ids:
            return None

        now_seconds = now_priority_seconds()
        web_bonus = BONUS_SECONDS[TicketSource.WEB]
        web_max_wait = MAX_WAIT_SECONDS[TicketSource.WEB]
        qr_max_wait = MAX_WAIT_SECONDS[TicketSource.QR]
        walk_in_max_wait = MAX_WAIT_SECONDS[TicketSource.WALK_IN]

        # WEB: due (slot started) and not past no-show window. Live tickets always eligible.
        web_due = Ticket.priority_key <= now_seconds - web_bonus
        web_not_expired = Ticket.priority_key >= now_seconds - web_max_wait - web_bonus
        eligible = or_(
            Ticket.source.in_((TicketSource.QR, TicketSource.WALK_IN)),
            and_(Ticket.source == TicketSource.WEB, web_due, web_not_expired),
        )

        # Anti-starvation: overdue live queue ahead of normal order (do not rewrite priority_key)
        overdue_live = case(
            (
                and_(
                    Ticket.source == TicketSource.QR,
                    Ticket.priority_key < now_seconds - qr_max_wait,
                ),
                0,
            ),
            (
                and_(
                    Ticket.source == TicketSource.WALK_IN,
                    Ticket.priority_key < now_seconds - walk_in_max_wait,
                ),
                0,
            ),
            else_=1,
        )

        ticket = await self.session.scalar(
            select(Ticket)
            .where(
                Ticket.department_id == window.department_id,
                Ticket.status == TicketStatus.QUEUED,
                Ticket.service_id.in_(service_ids),
                eligible,
            )
            .order_by(overdue_live.asc(), Ticket.priority_key.asc(), Ticket.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True),
        )
        if ticket is None:
            return None

        ticket.status = TicketStatus.CALLED
        ticket.window_id = window.id
        ticket.called_at = datetime.now(UTC)
        await self.session.flush()
        return ticket

    async def complete_current_ticket(self, window: Window) -> Ticket | None:
        ticket = await self.session.scalar(
            select(Ticket)
            .where(
                Ticket.window_id == window.id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            )
            .order_by(Ticket.called_at, Ticket.id)
            .limit(1)
            .with_for_update(),
        )
        if ticket is None:
            return None

        ticket.status = TicketStatus.COMPLETED
        ticket.completed_at = datetime.now(UTC)
        await self.session.flush()
        return ticket
