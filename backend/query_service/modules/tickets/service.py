from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends

from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.modules.services.repository import ServiceRepository
from query_service.modules.slots.exceptions import SlotNotFoundError
from query_service.modules.slots.repository import SlotsRepository
from query_service.modules.tickets.exceptions import (
    InactiveServiceError,
    InvalidTicketStateError,
    MissingSlotIdError,
    ServiceNotFoundError,
    SlotFullError,
    SlotServiceMismatchError,
    TicketNotFoundError,
    UnexpectedSlotIdError,
)
from query_service.modules.tickets.priority import (
    QUEUE_TIMEZONE,
    compute_priority_key,
    is_queue_eligible,
    now_in_queue_tz,
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

    async def release_slot(self, slot_id: UUID | None) -> None:
        if slot_id is not None:
            await self.slots_repo.try_decrement_booked(slot_id)

    async def expire_web_noshows(self, department_id: UUID) -> None:
        tickets = await self.repository.lock_web_noshows(department_id)
        if not tickets:
            return

        now = datetime.now(UTC)
        slot_ids: list[UUID] = []
        for ticket in tickets:
            ticket.status = TicketStatus.CANCELED
            ticket.canceled_at = now
            if ticket.slot_id is not None:
                slot_ids.append(ticket.slot_id)

        await self.repository.save()

        for slot_id in slot_ids:
            await self.release_slot(slot_id)

    async def requeue(self, ticket: Ticket, elapsed_seconds: int = 0) -> Ticket:
        """Return CALLED/SERVING ticket to QUEUED. Caller must hold FOR UPDATE."""
        if ticket.status not in (TicketStatus.CALLED, TicketStatus.SERVING):
            raise InvalidTicketStateError

        ticket.status = TicketStatus.QUEUED
        ticket.window_id = None
        ticket.called_at = None
        ticket.started_at = None
        ticket.priority_key = max(0, ticket.priority_key - elapsed_seconds)

        await self.repository.save()
        return ticket

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
        if request.source != TicketSource.WEB and request.slot_id is not None:
            raise UnexpectedSlotIdError

        effective_start = now_in_queue_tz()
        slot_id: UUID | None = None

        if request.source == TicketSource.WEB and request.slot_id is not None:
            slot = await self.slots_repo.get_slot_in_department(department_id, request.slot_id)

            if slot is None:
                raise SlotNotFoundError

            if slot.service_id != request.service_id:
                raise SlotServiceMismatchError

            reserved = await self.slots_repo.try_increment_booked(request.slot_id)
            if not reserved:
                raise SlotFullError

            # slot_date/slot_time are wall-clock in queue timezone (Europe/Moscow by default)
            effective_start = datetime.combine(slot.slot_date, slot.slot_time, tzinfo=QUEUE_TIMEZONE)
            slot_id = request.slot_id

        priority_key = compute_priority_key(request.source, effective_start)

        prefix = self._get_category_prefix(service.name)
        next_number = await self.repository.get_next_ticket_number(department_id, prefix)
        ticket_label = f"{prefix}-{next_number:03d}"

        ticket_data = Ticket(
            department_id=department_id,
            service_id=request.service_id,
            slot_id=slot_id,
            source=request.source,
            priority_key=priority_key,
            ticket_label=ticket_label,
        )

        created_ticket = await self.repository.create(ticket_data)

        return TicketResponse.model_validate(created_ticket)

    async def get_ticket_info(self, department_id: UUID, ticket_id: UUID) -> TicketResponse:
        await self.expire_web_noshows(department_id)

        ticket = await self.repository.get_by_id(ticket_id)
        if not ticket or ticket.department_id != department_id:
            raise TicketNotFoundError

        estimated_wait_minutes = 0

        # ETA only for live-eligible QUEUED tickets; same service + order as assign_next
        if ticket.status == TicketStatus.QUEUED and is_queue_eligible(ticket.source, ticket.priority_key):
            tickets_ahead = await self.repository.count_tickets_before(ticket)

            service = await self.service_repo.get_by_id(ticket.service_id)
            avg_service_time = service.duration_time if service else 10

            estimated_wait_minutes = tickets_ahead * avg_service_time

        response_data = TicketResponse.model_validate(ticket)
        response_data.estimated_wait_time = estimated_wait_minutes

        return response_data

    async def cancel_ticket(self, department_id: UUID, ticket_id: UUID) -> TicketResponse:
        ticket = await self.repository.get_by_id_for_update(ticket_id)

        if not ticket or ticket.department_id != department_id:
            raise TicketNotFoundError

        # Only QUEUED: refuse if already called/serving (avoids race with call-next)
        if ticket.status != TicketStatus.QUEUED:
            raise InvalidTicketStateError

        slot_id = ticket.slot_id
        ticket.status = TicketStatus.CANCELED
        ticket.canceled_at = datetime.now(UTC)
        await self.repository.save()

        await self.release_slot(slot_id)

        return TicketResponse.model_validate(ticket)
