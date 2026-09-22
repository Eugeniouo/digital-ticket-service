import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends

from query_service.database.models.service import Service
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.ticket_status_history import TicketStatusChange, TicketStatusChangeReason
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.notifications.service import NotificationService
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.tickets.exceptions import InactiveServiceError
from query_service.modules.tickets.priority import compute_priority_key, now_in_queue_tz
from query_service.modules.tickets.schema import TicketResponse
from query_service.modules.tickets.service import TicketService
from query_service.modules.windows.exceptions import (
    DepartmentNotFoundError,
    DuplicateWindowLabelError,
    EmptyQueueError,
    NoCalledTicketError,
    NoTicketInProgressError,
    OpenServicesWouldBeEmptyError,
    OperatorNotSeatedError,
    OperatorOnDifferentWindowError,
    ServiceNotInDepartmentError,
    ServicesNotAllowedError,
    TicketAlreadyInProgressError,
    WindowClosedError,
    WindowHasActiveTicketError,
    WindowHasNoServicesError,
    WindowNotFoundError,
    WindowOccupiedError,
)
from query_service.modules.windows.repository import WindowsRepository
from query_service.modules.windows.schema import (
    WindowCreateRequestDTO,
    WindowDTO,
    WindowOpenRequestDTO,
    WindowQueueResponse,
    WindowRedirectRequestDTO,
    WindowUpdateRequestDTO,
)

logger = logging.getLogger(__name__)


def window_to_dto(window: Window) -> WindowDTO:
    """Map a window row to the API DTO."""
    return WindowDTO(
        id=window.id,
        department_id=window.department_id,
        label=window.label,
        status=window.status,
        service_ids=[service.id for service in window.services],
        open_service_ids=[service.id for service in window.open_services],
        current_operator_id=window.current_operator_id,
    )


def _open_service_ids(window: Window) -> list[UUID]:
    return [service.id for service in window.open_services]


def _require_seated(window: Window, operator_id: UUID) -> None:
    if window.current_operator_id != operator_id:
        raise OperatorNotSeatedError


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
        notifications: NotificationService = Depends(),
    ) -> None:
        self.repository = repository
        self.tickets = tickets
        self.services = services
        self.notifications = notifications

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
        window = await self.repository.get_in_department_locked(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        label = payload.label
        if label is not None and label != window.label:
            if await self.repository.label_exists(department_id, label, exclude_window_id=window.id):
                raise DuplicateWindowLabelError
        else:
            label = None

        if label is not None:
            window.label = label

        if payload.service_ids is not None:
            services = await self.repository.resolve_services_in_department(department_id, payload.service_ids)
            if services is None:
                raise ServiceNotInDepartmentError

            remaining: list[Service] | None = None

            if window.status == WindowStatus.OPEN:
                allowed_ids = {service.id for service in services}
                remaining = [service for service in window.open_services if service.id in allowed_ids]

                if not remaining:
                    raise OpenServicesWouldBeEmptyError

            await self.repository.replace_catalog_services(window, services)
            if remaining is not None:
                await self.repository.replace_open_services(window, remaining)

        await self.repository.save()
        return window_to_dto(window)

    async def open_window(
        self,
        department_id: UUID,
        window_id: UUID,
        payload: WindowOpenRequestDTO,
        operator_id: UUID,
    ) -> WindowDTO:
        window = await self.repository.get_in_department_locked(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        allowed = list(window.services)
        allowed_by_id = {service.id: service for service in allowed}

        if payload.open_service_ids is None:
            open_services = allowed
        else:
            unique_ids = list(dict.fromkeys(payload.open_service_ids))
            if not unique_ids or any(service_id not in allowed_by_id for service_id in unique_ids):
                raise ServicesNotAllowedError

            open_services = [allowed_by_id[service_id] for service_id in unique_ids]

        if not open_services:
            raise ServicesNotAllowedError

        if window.current_operator_id is not None and window.current_operator_id != operator_id:
            raise WindowOccupiedError

        seated_at = await self.repository.get_by_operator(operator_id)
        if seated_at is not None and seated_at.id != window.id:
            raise OperatorOnDifferentWindowError

        window.status = WindowStatus.OPEN
        window.current_operator_id = operator_id
        await self.repository.replace_open_services(window, open_services)
        await self.repository.save()

        return window_to_dto(window)

    async def close_window(
        self,
        department_id: UUID,
        window_id: UUID,
        operator_id: UUID,
    ) -> WindowDTO:
        window = await self.repository.get_in_department_locked(department_id, window_id)
        if window is None:
            raise WindowNotFoundError
        _require_seated(window, operator_id)

        if await self.repository.ticket_exists_for_window(window.id):
            raise WindowHasActiveTicketError

        window.status = WindowStatus.CLOSED
        window.current_operator_id = None
        await self.repository.replace_open_services(window, [])
        await self.repository.save()

        return window_to_dto(window)

    async def get_queue(
        self,
        department_id: UUID,
        window_id: UUID,
        operator_id: UUID,
    ) -> WindowQueueResponse:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError
        _require_seated(window, operator_id)

        current = await self.repository.get_in_progress_ticket(window)
        upcoming = await self.repository.list_eligible_queued(window, _open_service_ids(window))

        current_dto = TicketResponse.model_validate(current) if current is not None else None
        upcoming_dtos = [TicketResponse.model_validate(ticket) for ticket in upcoming]
        return WindowQueueResponse(current=current_dto, upcoming=upcoming_dtos)

    async def call_next(self, department_id: UUID, window_id: UUID, operator_id: UUID) -> Ticket:
        """
        Call-next moves the queue on a given window.
        By moving a queue, we run a lot of checks, so everything stays consistent and avoids data races.
        """
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError
        _require_seated(window, operator_id)

        await self.tickets.expire_web_noshows(department_id)
        locked = await self.repository.lock_window(window.id)
        if locked is None:
            raise WindowNotFoundError
        _require_seated(locked, operator_id)
        if locked.status != WindowStatus.OPEN:
            raise WindowClosedError
        if await self.repository.ticket_exists_for_window(locked.id):
            raise TicketAlreadyInProgressError

        service_ids = _open_service_ids(locked)
        if not service_ids:
            raise WindowHasNoServicesError

        ticket = await self.repository.find_next_eligible_ticket(locked, service_ids)
        if ticket is None:
            raise EmptyQueueError

        old_status = ticket.status
        ticket.status = TicketStatus.CALLED
        ticket.window_id = locked.id
        ticket.called_at = datetime.now(UTC)
        await self.tickets.record_status_change(
            ticket,
            TicketStatusChange(
                old_status=old_status,
                new_status=TicketStatus.CALLED,
                reason=TicketStatusChangeReason.CALLED,
                staff_id=locked.current_operator_id,
                window_id=locked.id,
            ),
        )
        await self.repository.save()

        await self._enqueue_after_call(ticket, locked)

        return ticket

    async def _enqueue_after_call(self, ticket: Ticket, window: Window) -> None:
        try:
            await self.notifications.enqueue_called(ticket, window)

            service_ids = _open_service_ids(window)
            await self.notifications.enqueue_approaching_for_services(window.department_id, service_ids)
        except Exception:
            logger.exception("notification enqueue failed")

    async def start(self, department_id: UUID, window_id: UUID, operator_id: UUID) -> Ticket:
        window = await self._get_seated_window(department_id, window_id, operator_id)

        ticket = await self.repository.get_called_ticket_locked(window)
        if ticket is None:
            raise NoCalledTicketError

        old_status = ticket.status
        ticket.status = TicketStatus.SERVING
        ticket.started_at = datetime.now(UTC)
        await self.tickets.record_status_change(
            ticket,
            TicketStatusChange(
                old_status=old_status,
                new_status=TicketStatus.SERVING,
                reason=TicketStatusChangeReason.STARTED,
                staff_id=window.current_operator_id,
                window_id=window.id,
            ),
        )
        await self.repository.save()

        return ticket

    async def mark_no_show(self, department_id: UUID, window_id: UUID, operator_id: UUID) -> Ticket:
        window = await self._get_seated_window(department_id, window_id, operator_id)

        ticket = await self.repository.get_called_ticket_locked(window)
        if ticket is None:
            raise NoCalledTicketError

        slot_id = ticket.slot_id
        old_status = ticket.status
        ticket.status = TicketStatus.CANCELED
        ticket.canceled_at = datetime.now(UTC)
        await self.tickets.record_status_change(
            ticket,
            TicketStatusChange(
                old_status=old_status,
                new_status=TicketStatus.CANCELED,
                reason=TicketStatusChangeReason.NOSHOW,
                staff_id=window.current_operator_id,
                window_id=window.id,
            ),
        )
        await self.repository.save()
        await self.tickets.release_slot(slot_id)
        await self._enqueue_after_noshow(ticket, window)

        return ticket

    async def _enqueue_after_noshow(self, ticket: Ticket, window: Window) -> None:
        try:
            await self.notifications.enqueue_noshow(ticket, window)
        except Exception:
            logger.exception("notification enqueue failed")

    async def complete(self, department_id: UUID, window_id: UUID, operator_id: UUID) -> Ticket:
        window = await self._get_seated_window(department_id, window_id, operator_id)

        ticket = await self.repository.get_in_progress_ticket_locked(window)
        if ticket is None:
            raise NoTicketInProgressError

        old_status = ticket.status
        ticket.status = TicketStatus.COMPLETED
        ticket.completed_at = datetime.now(UTC)
        await self.tickets.record_status_change(
            ticket,
            TicketStatusChange(
                old_status=old_status,
                new_status=TicketStatus.COMPLETED,
                reason=TicketStatusChangeReason.COMPLETED,
                staff_id=window.current_operator_id,
                window_id=window.id,
            ),
        )
        await self.repository.save()

        return ticket

    async def requeue(self, department_id: UUID, window_id: UUID, operator_id: UUID) -> Ticket:
        window = await self._get_seated_window(department_id, window_id, operator_id)
        ticket = await self.repository.get_in_progress_ticket_locked(window)
        if ticket is None:
            raise NoTicketInProgressError

        elapsed = _elapsed_at_window_seconds(ticket)

        return await self.tickets.requeue(
            ticket,
            elapsed,
            TicketStatusChange(
                new_status=TicketStatus.QUEUED,
                reason=TicketStatusChangeReason.REQUEUED,
                staff_id=window.current_operator_id,
                window_id=window.id,
            ),
        )

    async def redirect(
        self,
        department_id: UUID,
        window_id: UUID,
        payload: WindowRedirectRequestDTO,
        operator_id: UUID,
    ) -> Ticket:
        window = await self._get_seated_window(department_id, window_id, operator_id)
        ticket = await self.repository.get_in_progress_ticket_locked(window)
        if ticket is None:
            raise NoTicketInProgressError
        service = await self.services.get_by_id(payload.service_id)
        if service is None or service.department_id != department_id:
            raise ServiceNotInDepartmentError
        if not service.is_active:
            raise InactiveServiceError

        # Keep the channel from issue. The lines below overwrite source and slot_id.
        if ticket.origin_source is None:
            ticket.origin_source = ticket.source
        if ticket.origin_slot_id is None:
            ticket.origin_slot_id = ticket.slot_id

        # We drop the appointment and become walk-in for the new service
        slot_id = ticket.slot_id
        ticket.service_id = payload.service_id
        ticket.slot_id = None
        ticket.source = TicketSource.WALK_IN
        ticket.priority_key = compute_priority_key(now_in_queue_tz())

        elapsed = _elapsed_at_window_seconds(ticket)
        requeued = await self.tickets.requeue(
            ticket,
            elapsed,
            TicketStatusChange(
                new_status=TicketStatus.QUEUED,
                reason=TicketStatusChangeReason.REDIRECTED,
                staff_id=window.current_operator_id,
                window_id=window.id,
            ),
        )

        await self.tickets.release_slot(slot_id)

        return requeued

    async def _get_seated_window(self, department_id: UUID, window_id: UUID, operator_id: UUID) -> Window:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError
        _require_seated(window, operator_id)
        return window
