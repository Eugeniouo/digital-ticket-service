from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import instance_state, set_committed_value

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.tickets.priority import (
    now_priority_seconds,
    overdue_live_sql,
    queue_eligible_sql,
    ticket_matches_window_sql,
)
from query_service.modules.windows.exceptions import (
    ServiceNotInDepartmentError,
    TicketAlreadyInProgressError,
    WindowClosedError,
    WindowHasNoServicesError,
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

    async def get_in_department_for_update(self, department_id: UUID, window_id: UUID) -> Window | None:
        return await self.session.scalar(
            select(Window)
            .where(Window.id == window_id, Window.department_id == department_id)
            .options(selectinload(Window.services))
            .with_for_update(),
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
        # Lock full window row; re-check OPEN after lock (close ↔ call-next race)
        locked = await self.session.scalar(
            select(Window).where(Window.id == window.id).options(selectinload(Window.services)).with_for_update(),
        )
        if locked is None:
            return None
        if locked.status != WindowStatus.OPEN:
            raise WindowClosedError

        in_progress = await self.session.scalar(
            select(Ticket.id).where(
                Ticket.window_id == locked.id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            ),
        )
        if in_progress is not None:
            raise TicketAlreadyInProgressError

        service_ids = [service.id for service in locked.services]
        if not service_ids:
            raise WindowHasNoServicesError

        now_seconds = now_priority_seconds()
        eligible = queue_eligible_sql(now_seconds)
        overdue_live = overdue_live_sql(now_seconds)

        ticket = await self.session.scalar(
            select(Ticket)
            .outerjoin(Slot, Ticket.slot_id == Slot.id)
            .where(
                Ticket.department_id == locked.department_id,
                Ticket.status == TicketStatus.QUEUED,
                Ticket.service_id.in_(service_ids),
                eligible,
                ticket_matches_window_sql(locked.id),
            )
            .order_by(overdue_live.asc(), Ticket.priority_key.asc(), Ticket.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True, of=Ticket),
        )
        if ticket is None:
            return None

        ticket.status = TicketStatus.CALLED
        ticket.window_id = locked.id
        ticket.called_at = datetime.now(UTC)
        await self.session.flush()

        return ticket

    async def get_in_progress_ticket_for_update(self, window: Window) -> Ticket | None:
        return await self.session.scalar(
            select(Ticket)
            .where(
                Ticket.window_id == window.id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            )
            .order_by(Ticket.called_at, Ticket.id)
            .limit(1)
            .with_for_update(),
        )

    async def start_current_ticket(self, window: Window) -> Ticket | None:
        ticket = await self.session.scalar(
            select(Ticket)
            .where(
                Ticket.window_id == window.id,
                Ticket.status == TicketStatus.CALLED,
            )
            .order_by(Ticket.called_at, Ticket.id)
            .limit(1)
            .with_for_update(),
        )
        if ticket is None:
            return None

        ticket.status = TicketStatus.SERVING
        ticket.started_at = datetime.now(UTC)
        await self.session.flush()

        return ticket

    async def complete_current_ticket(self, window: Window) -> Ticket | None:
        ticket = await self.get_in_progress_ticket_for_update(window)
        if ticket is None:
            return None

        ticket.status = TicketStatus.COMPLETED
        ticket.completed_at = datetime.now(UTC)
        await self.session.flush()

        return ticket
