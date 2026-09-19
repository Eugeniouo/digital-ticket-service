from uuid import UUID

from fastapi import Depends

from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.slots.repository import SlotsRepository
from query_service.modules.tickets.exceptions import (
    InactiveServiceError,
    InvalidTicketStateError,
    MissingSlotIdError,
    ServiceNotFoundError,
    SlotFullError,
    SlotNotFoundError,
    SlotServiceMismatchError,
    TicketNotFoundError,
)
from query_service.modules.tickets.repository import TicketRepository
from query_service.modules.tickets.schema import TicketCreateRequest, TicketResponse


class TicketService:
    def __init__(
        self,
        repository: TicketRepository = Depends(),
        service_repo: ServiceRepository = Depends(),
        slots_repo: SlotsRepository = Depends(),
    ) -> None:
        self.repository = repository
        self.service_repo = service_repo
        self.slots_repo = slots_repo

    def _get_category_prefix(self, service_name: str) -> str:
        """Determines the ticket prefix based on the service name."""
        name = service_name.lower()

        if "посылк" in name:
            return "П"
        if "пенси" in name or "пособи" in name:
            return "С"
        if "платеж" in name or "перевод" in name:
            return "К"
        if "письм" in name:
            return "М"

        return "У"

    async def issue_ticket(self, department_id: UUID, request: TicketCreateRequest) -> TicketResponse:
        service = await self.service_repo.get_by_id(request.service_id)

        if not service or service.department_id != department_id:
            raise ServiceNotFoundError

        if not service.is_active:
            raise InactiveServiceError

        if request.source == TicketSource.WEB and not request.slot_id:
            raise MissingSlotIdError

        if request.source == TicketSource.WEB and request.slot_id is not None:
            slot = await self.slots_repo.get_slot_in_department(department_id, request.slot_id)
            if slot is None:
                raise SlotNotFoundError
            if slot.service_id != request.service_id:
                raise SlotServiceMismatchError
            reserved = await self.slots_repo.try_increment_booked(request.slot_id)
            if not reserved:
                raise SlotFullError

        prefix = self._get_category_prefix(service.name)
        next_number = await self.repository.get_next_ticket_number(department_id, prefix)
        ticket_label = f"{prefix}-{next_number:03d}"

        priority_map = {TicketSource.WEB: 100, TicketSource.QR: 50, TicketSource.WALK_IN: 10}

        ticket_data = Ticket(
            department_id=department_id,
            service_id=request.service_id,
            slot_id=request.slot_id,
            source=request.source,
            priority_key=priority_map.get(request.source, 10),
            ticket_label=ticket_label,
        )

        created_ticket = await self.repository.create(ticket_data)

        return TicketResponse.model_validate(created_ticket)

    async def get_ticket_info(self, department_id: UUID, ticket_id: UUID) -> TicketResponse:
        ticket = await self.repository.get_by_id(ticket_id)

        if not ticket or ticket.department_id != department_id:
            raise TicketNotFoundError

        estimated_wait_minutes = 0
        if ticket.status == TicketStatus.QUEUED:
            tickets_ahead = await self.repository.count_tickets_before(ticket)

            service = await self.service_repo.get_by_id(ticket.service_id)
            avg_service_time = service.duration_time if service else 10

            estimated_wait_minutes = tickets_ahead * avg_service_time

        response_data = TicketResponse.model_validate(ticket)
        response_data.estimated_wait_time = estimated_wait_minutes

        return response_data

    async def cancel_ticket(self, department_id: UUID, ticket_id: UUID) -> TicketResponse:
        ticket = await self.repository.get_by_id(ticket_id)

        if not ticket or ticket.department_id != department_id:
            raise TicketNotFoundError

        if ticket.status in (TicketStatus.SERVING, TicketStatus.COMPLETED, TicketStatus.CANCELED):
            raise InvalidTicketStateError

        slot_id = ticket.slot_id
        updated_ticket = await self.repository.update_status(ticket_id, TicketStatus.CANCELED)

        if slot_id is not None:
            await self.slots_repo.try_decrement_booked(slot_id)

        return TicketResponse.model_validate(updated_ticket)
