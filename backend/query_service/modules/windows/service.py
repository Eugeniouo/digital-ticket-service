from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends

from query_service.database.models.ticket import Ticket
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.slots.repository import SlotsRepository
from query_service.modules.tickets.exceptions import InactiveServiceError
from query_service.modules.tickets.service import TicketService
from query_service.modules.windows.exceptions import (
    DepartmentNotFoundError,
    DuplicateWindowLabelError,
    EmptyQueueError,
    NoCalledTicketError,
    NoTicketInProgressError,
    ServiceNotInDepartmentError,
    WindowHasActiveTicketError,
    WindowNotFoundError,
)
from query_service.modules.windows.repository import WindowsRepository
from query_service.modules.windows.schema import (
    WindowCreateRequestDTO,
    WindowDTO,
    WindowRedirectRequestDTO,
    WindowUpdateRequestDTO,
)


def window_to_dto(window: Window) -> WindowDTO:
    """Map a window row to the API DTO."""
    return WindowDTO(
        id=window.id,
        department_id=window.department_id,
        label=window.label,
        status=window.status,
        service_ids=[service.id for service in window.services],
    )


def _elapsed_at_window_seconds(ticket: Ticket) -> int:
    if ticket.called_at is None:
        return 0
    return max(0, int((datetime.now(UTC) - ticket.called_at).total_seconds()))


class WindowsService:
    """Create, update, and operate department windows."""

    def __init__(
        self,
        repository: WindowsRepository = Depends(),
        tickets: TicketService = Depends(),
        services: ServiceRepository = Depends(),
        slots: SlotsRepository = Depends(),
    ) -> None:
        self.repository = repository
        self.tickets = tickets
        self.services = services
        self.slots = slots

    async def list_windows(self, department_id: UUID) -> list[WindowDTO]:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError

        windows = await self.repository.list_by_department(department_id)
        return [window_to_dto(window) for window in windows]

    async def create_window(self, department_id: UUID, payload: WindowCreateRequestDTO) -> WindowDTO:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError
        if await self.repository.label_exists(department_id, payload.label):
            raise DuplicateWindowLabelError

        window = Window(
            department_id=department_id,
            label=payload.label,
            status=WindowStatus.CLOSED,
        )
        await self.repository.add(window, payload.service_ids)
        return window_to_dto(window)

    async def update_window(
        self,
        department_id: UUID,
        window_id: UUID,
        payload: WindowUpdateRequestDTO,
    ) -> WindowDTO:
        # Lock window before close check so call-next cannot sneak an active ticket in
        window = await self.repository.get_in_department_for_update(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        if payload.status == WindowStatus.CLOSED and await self.repository.ticket_exists_for_window(window.id):
            raise WindowHasActiveTicketError

        await self.repository.update(
            window,
            status=payload.status,
            service_ids=payload.service_ids,
        )

        return window_to_dto(window)

    async def call_next(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        await self.tickets.expire_web_noshows(department_id)

        # OPEN / empty-services / in-progress re-checked under FOR UPDATE in assign_next_ticket
        ticket = await self.repository.assign_next_ticket(window)
        if ticket is None:
            raise EmptyQueueError

        return ticket

    async def start(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.start_current_ticket(window)
        if ticket is None:
            raise NoCalledTicketError

        return ticket

    async def complete(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.complete_current_ticket(window)
        if ticket is None:
            raise NoTicketInProgressError

        return ticket

    async def requeue(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.get_in_progress_ticket_for_update(window)
        if ticket is None:
            raise NoTicketInProgressError

        elapsed = _elapsed_at_window_seconds(ticket)

        return await self.tickets.repository.requeue_ticket(ticket, elapsed)

    async def redirect(
        self,
        department_id: UUID,
        window_id: UUID,
        payload: WindowRedirectRequestDTO,
    ) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.get_in_progress_ticket_for_update(window)
        if ticket is None:
            raise NoTicketInProgressError

        service = await self.services.get_by_id(payload.service_id)
        if service is None or service.department_id != department_id:
            raise ServiceNotInDepartmentError
        if not service.is_active:
            raise InactiveServiceError

        # We drop slot so another window can pick WEB type request after change
        slot_id = ticket.slot_id
        ticket.service_id = payload.service_id
        ticket.slot_id = None

        elapsed = _elapsed_at_window_seconds(ticket)
        requeued = await self.tickets.repository.requeue_ticket(ticket, elapsed)

        if slot_id is not None:
            await self.slots.try_decrement_booked(slot_id)

        return requeued
