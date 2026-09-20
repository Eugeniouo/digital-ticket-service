from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends

from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.tickets.exceptions import InactiveServiceError
from query_service.modules.tickets.priority import compute_priority_key, now_in_queue_tz
from query_service.modules.tickets.service import TicketService
from query_service.modules.windows.exceptions import (
    DepartmentNotFoundError,
    DuplicateWindowLabelError,
    EmptyQueueError,
    NoCalledTicketError,
    NoTicketInProgressError,
    ServiceNotInDepartmentError,
    TicketAlreadyInProgressError,
    WindowClosedError,
    WindowHasActiveTicketError,
    WindowHasNoServicesError,
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
    ) -> None:
        self.repository = repository
        self.tickets = tickets
        self.services = services

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

        services = await self.repository.resolve_services_in_department(department_id, payload.service_ids)
        if services is None:
            raise ServiceNotInDepartmentError

        window = Window(
            department_id=department_id,
            label=payload.label,
            status=WindowStatus.CLOSED,
        )
        await self.repository.add(window, services)
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

        services = None
        if payload.service_ids is not None:
            services = await self.repository.resolve_services_in_department(department_id, payload.service_ids)
            if services is None:
                raise ServiceNotInDepartmentError

        await self.repository.update(
            window,
            status=payload.status,
            services=services,
        )

        return window_to_dto(window)

    async def call_next(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        await self.tickets.expire_web_noshows(department_id)

        # Re-lock and re-check OPEN (close ↔ call-next race)
        locked = await self.repository.lock_window(window.id)
        if locked is None:
            raise EmptyQueueError
        if locked.status != WindowStatus.OPEN:
            raise WindowClosedError
        if await self.repository.ticket_exists_for_window(locked.id):
            raise TicketAlreadyInProgressError

        service_ids = [service.id for service in locked.services]
        if not service_ids:
            raise WindowHasNoServicesError

        ticket = await self.repository.find_next_eligible_ticket(locked, service_ids)
        if ticket is None:
            raise EmptyQueueError

        ticket.status = TicketStatus.CALLED
        ticket.window_id = locked.id
        ticket.called_at = datetime.now(UTC)
        await self.repository.save()

        return ticket

    async def start(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.get_called_ticket_for_update(window)
        if ticket is None:
            raise NoCalledTicketError

        ticket.status = TicketStatus.SERVING
        ticket.started_at = datetime.now(UTC)
        await self.repository.save()

        return ticket

    async def complete(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.get_in_progress_ticket_for_update(window)
        if ticket is None:
            raise NoTicketInProgressError

        ticket.status = TicketStatus.COMPLETED
        ticket.completed_at = datetime.now(UTC)
        await self.repository.save()

        return ticket

    async def requeue(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.get_in_progress_ticket_for_update(window)
        if ticket is None:
            raise NoTicketInProgressError

        elapsed = _elapsed_at_window_seconds(ticket)

        return await self.tickets.requeue(ticket, elapsed)

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

        # We drop the appointment and become walk-in for the new service
        slot_id = ticket.slot_id
        ticket.service_id = payload.service_id
        ticket.slot_id = None
        ticket.source = TicketSource.WALK_IN
        ticket.priority_key = compute_priority_key(TicketSource.WALK_IN, now_in_queue_tz())

        elapsed = _elapsed_at_window_seconds(ticket)
        requeued = await self.tickets.requeue(ticket, elapsed)

        await self.tickets.release_slot(slot_id)

        return requeued
