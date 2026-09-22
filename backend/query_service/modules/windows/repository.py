from uuid import UUID

from fastapi import Depends
from sqlalchemy import Select, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket, TicketStatus
from query_service.database.models.window import Window, WindowOpenService, WindowService
from query_service.modules.tickets.priority import (
    effective_priority_sql,
    now_priority_seconds,
    overdue_live_sql,
    queue_eligible_sql,
    ticket_matches_window_sql,
)
from query_service.modules.tickets.queue_rules import load_queue_rules

_WINDOW_LOAD = (selectinload(Window.services), selectinload(Window.open_services))


class WindowsRepository:
    """Database access for windows, their services, and queue queries."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def save(self) -> None:
        await self.session.flush()

    async def get_department(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    # Window rows

    async def list_by_department(self, department_id: UUID) -> list[Window]:
        result = await self.session.scalars(
            select(Window).where(Window.department_id == department_id).options(*_WINDOW_LOAD).order_by(Window.label, Window.id),
        )
        return list(result.all())

    async def get_in_department(self, department_id: UUID, window_id: UUID) -> Window | None:
        return await self.session.scalar(
            select(Window).where(Window.id == window_id, Window.department_id == department_id).options(*_WINDOW_LOAD),
        )

    async def get_in_department_locked(self, department_id: UUID, window_id: UUID) -> Window | None:
        return await self.session.scalar(
            select(Window).where(Window.id == window_id, Window.department_id == department_id).options(*_WINDOW_LOAD).with_for_update(),
        )

    async def lock_window(self, window_id: UUID) -> Window | None:
        return await self.session.scalar(
            select(Window).where(Window.id == window_id).options(*_WINDOW_LOAD).with_for_update(),
        )

    async def get_by_operator(self, operator_id: UUID) -> Window | None:
        return await self.session.scalar(
            select(Window).where(Window.current_operator_id == operator_id),
        )

    async def label_exists(
        self,
        department_id: UUID,
        label: str,
        *,
        exclude_window_id: UUID | None = None,
    ) -> bool:
        stmt = select(Window.id).where(Window.department_id == department_id, Window.label == label)
        if exclude_window_id is not None:
            stmt = stmt.where(Window.id != exclude_window_id)

        window_id = await self.session.scalar(stmt)
        return window_id is not None

    # Catalog and shift services

    async def resolve_services_in_department(
        self,
        department_id: UUID,
        service_ids: list[UUID],
    ) -> list[Service] | None:
        """Load services by id in department order. None if any id is missing."""
        unique_ids = list(dict.fromkeys(service_ids))
        if not unique_ids:
            return []

        services = list(
            await self.session.scalars(
                select(Service).where(
                    Service.id.in_(unique_ids),
                    Service.department_id == department_id,
                ),
            ),
        )
        if len(services) != len(unique_ids):
            return None

        by_id = {service.id: service for service in services}
        return [by_id[service_id] for service_id in unique_ids]

    async def _replace_window_services(
        self,
        model: type[WindowService] | type[WindowOpenService],
        window: Window,
        services: list[Service],
    ) -> None:
        # this allows us to delete and insert a given thing
        await self.session.execute(delete(model).where(model.window_id == window.id))
        if services:
            await self.session.execute(
                insert(model),
                [{"window_id": window.id, "service_id": service.id} for service in services],
            )

        await self.session.flush()
        # TODO: refactor this. We're trying to map model name by hardcoding it's attr, I don't think it's the best approach.
        attr = "services" if model is WindowService else "open_services"
        await self.session.refresh(window, attribute_names=[attr])

    async def replace_catalog_services(self, window: Window, services: list[Service]) -> None:
        await self._replace_window_services(WindowService, window, services)

    async def replace_open_services(self, window: Window, services: list[Service]) -> None:
        await self._replace_window_services(WindowOpenService, window, services)

    async def add(self, window: Window, services: list[Service]) -> Window:
        self.session.add(window)
        await self.session.flush()
        await self.replace_catalog_services(window, services)
        await self.session.refresh(window, attribute_names=["open_services"])
        return window

    # Queue

    async def ticket_exists_for_window(self, window_id: UUID) -> bool:
        ticket_id = await self.session.scalar(
            select(Ticket.id).where(
                Ticket.window_id == window_id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            ),
        )
        return ticket_id is not None

    async def _eligible_queued_stmt(self, window: Window, service_ids: list[UUID]) -> Select[tuple[Ticket]]:
        now_seconds = now_priority_seconds()
        rules = await load_queue_rules(self.session, window.department_id)
        eligible = queue_eligible_sql(now_seconds, rules)
        overdue_live = overdue_live_sql(now_seconds, rules)
        effective = effective_priority_sql(rules)

        return (
            select(Ticket)
            .outerjoin(Slot, Ticket.slot_id == Slot.id)
            .where(
                Ticket.department_id == window.department_id,
                Ticket.status == TicketStatus.QUEUED,
                Ticket.service_id.in_(service_ids),
                eligible,
                ticket_matches_window_sql(window.id),
            )
            .order_by(overdue_live.asc(), effective.asc(), Ticket.created_at.asc())
        )

    async def find_next_eligible_ticket(self, window: Window, service_ids: list[UUID]) -> Ticket | None:
        """Select next QUEUED ticket for this window. Caller must hold the window lock."""
        stmt = await self._eligible_queued_stmt(window, service_ids)
        return await self.session.scalar(stmt.limit(1).with_for_update(skip_locked=True, of=Ticket))

    async def list_eligible_queued(self, window: Window, service_ids: list[UUID]) -> list[Ticket]:
        """Eligible QUEUED tickets in the same order as call-next. No row locks."""
        if not service_ids:
            return []

        stmt = await self._eligible_queued_stmt(window, service_ids)
        return list((await self.session.scalars(stmt)).all())

    async def get_in_progress_ticket(self, window: Window) -> Ticket | None:
        return await self.session.scalar(
            select(Ticket)
            .where(
                Ticket.window_id == window.id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            )
            .order_by(Ticket.called_at, Ticket.id)
            .limit(1),
        )

    async def get_in_progress_ticket_locked(self, window: Window) -> Ticket | None:
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

    async def get_called_ticket_locked(self, window: Window) -> Ticket | None:
        return await self.session.scalar(
            select(Ticket)
            .where(
                Ticket.window_id == window.id,
                Ticket.status == TicketStatus.CALLED,
            )
            .order_by(Ticket.called_at, Ticket.id)
            .limit(1)
            .with_for_update(),
        )
