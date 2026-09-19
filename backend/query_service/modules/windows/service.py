from uuid import UUID

from fastapi import Depends

from query_service.database.models.ticket import Ticket
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.windows.exceptions import (
    DepartmentNotFoundError,
    DuplicateWindowLabelError,
    EmptyQueueError,
    NoTicketInProgressError,
    WindowClosedError,
    WindowHasActiveTicketError,
    WindowNotFoundError,
)
from query_service.modules.windows.repository import WindowsRepository
from query_service.modules.windows.schema import WindowCreateRequestDTO, WindowDTO, WindowUpdateRequestDTO


def window_to_dto(window: Window) -> WindowDTO:
    """Map a window row to the API DTO."""
    return WindowDTO(
        id=window.id,
        department_id=window.department_id,
        label=window.label,
        status=window.status,
        service_ids=[service.id for service in window.services],
    )


class WindowsService:
    """Create, update, and operate department windows."""

    def __init__(self, repository: WindowsRepository = Depends()) -> None:
        self.repository = repository

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
        window = await self.repository.get_in_department(department_id, window_id)
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
        if window.status != WindowStatus.OPEN:
            raise WindowClosedError

        ticket = await self.repository.assign_next_ticket(window)
        if ticket is None:
            raise EmptyQueueError
        return ticket

    async def complete(self, department_id: UUID, window_id: UUID) -> Ticket:
        window = await self.repository.get_in_department(department_id, window_id)
        if window is None:
            raise WindowNotFoundError

        ticket = await self.repository.complete_current_ticket(window)
        if ticket is None:
            raise NoTicketInProgressError
        return ticket
