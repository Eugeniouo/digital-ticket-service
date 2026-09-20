from datetime import date, datetime, time, timedelta
from uuid import UUID

from fastapi import Depends

from query_service.database.models.slot import Slot
from query_service.modules.slots.exceptions import (
    DepartmentNotFoundError,
    DuplicateSlotError,
    InvalidCapacityError,
    NoWindowsForServiceError,
    ServiceNotInDepartmentError,
    ServiceNotOnWindowError,
    SlotHasBookingsError,
    SlotNotFoundError,
    WindowNotInDepartmentError,
)
from query_service.modules.slots.repository import SlotsRepository
from query_service.modules.slots.schema import (
    SlotCreateRequestDTO,
    SlotDTO,
    SlotGenerateRequestDTO,
    SlotGenerateResponseDTO,
    SlotUpdateRequestDTO,
)


def slot_to_dto(slot: Slot) -> SlotDTO:
    return SlotDTO.model_validate(slot)


def _iter_slot_times(open_time: time, close_time: time, duration_minutes: int) -> list[time]:
    """Build same-day times: open inclusive, close exclusive."""
    if duration_minutes <= 0:
        return []
    if close_time <= open_time:
        return []

    times: list[time] = []
    cursor = datetime.combine(date.min, open_time)
    end = datetime.combine(date.min, close_time)
    step = timedelta(minutes=duration_minutes)
    while cursor < end:
        times.append(cursor.time())
        cursor += step
    return times


class SlotsService:
    """Slot catalog and day generation for a department."""

    def __init__(self, repository: SlotsRepository = Depends()) -> None:
        self.repository = repository

    async def _require_department(self, department_id: UUID) -> None:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError

    async def list_slots(
        self,
        department_id: UUID,
        *,
        slot_date: date,
        service_id: UUID,
        window_id: UUID | None = None,
    ) -> list[SlotDTO]:
        await self._require_department(department_id)
        slots = await self.repository.list_slots(
            department_id,
            slot_date=slot_date,
            service_id=service_id,
            window_id=window_id,
        )
        return [slot_to_dto(slot) for slot in slots]

    async def get_slot(self, department_id: UUID, slot_id: UUID) -> SlotDTO:
        slot = await self.repository.get_slot_in_department(department_id, slot_id)
        if slot is None:
            raise SlotNotFoundError
        return slot_to_dto(slot)

    async def create_slot(self, department_id: UUID, payload: SlotCreateRequestDTO) -> SlotDTO:
        await self._require_department(department_id)

        service = await self.repository.get_service_in_department(department_id, payload.service_id)
        if service is None or not service.is_active:
            raise ServiceNotInDepartmentError

        window = await self.repository.get_window_in_department(department_id, payload.window_id)
        if window is None:
            raise WindowNotInDepartmentError

        if not await self.repository.window_has_service(payload.window_id, payload.service_id):
            raise ServiceNotOnWindowError

        existing = await self.repository.find_slot(
            payload.window_id,
            payload.service_id,
            payload.slot_date,
            payload.slot_time,
        )
        if existing is not None:
            raise DuplicateSlotError

        slot = Slot(
            window_id=payload.window_id,
            service_id=payload.service_id,
            slot_date=payload.slot_date,
            slot_time=payload.slot_time,
            capacity=payload.capacity,
            booked_count=0,
        )
        await self.repository.add(slot)
        return slot_to_dto(slot)

    async def update_slot(
        self,
        department_id: UUID,
        slot_id: UUID,
        payload: SlotUpdateRequestDTO,
    ) -> SlotDTO:
        slot = await self.repository.get_slot_in_department(department_id, slot_id)
        if slot is None:
            raise SlotNotFoundError

        if payload.capacity < slot.booked_count:
            raise InvalidCapacityError

        slot.capacity = payload.capacity
        await self.repository.save()
        return slot_to_dto(slot)

    async def delete_slot(self, department_id: UUID, slot_id: UUID) -> None:
        slot = await self.repository.get_slot_in_department(department_id, slot_id)
        if slot is None:
            raise SlotNotFoundError

        if slot.booked_count > 0:
            raise SlotHasBookingsError

        await self.repository.delete(slot)

    async def generate(self, department_id: UUID, payload: SlotGenerateRequestDTO) -> SlotGenerateResponseDTO:
        department = await self.repository.get_department(department_id)
        if department is None:
            raise DepartmentNotFoundError

        service = await self.repository.get_service_in_department(department_id, payload.service_id)
        if service is None or not service.is_active:
            raise ServiceNotInDepartmentError

        windows = await self.repository.list_windows_with_service(department_id, payload.service_id)
        if not windows:
            raise NoWindowsForServiceError

        slot_times = _iter_slot_times(department.open_time, department.close_time, payload.duration)
        window_ids = [window.id for window in windows]
        existing = await self.repository.list_existing_times(
            service_id=payload.service_id,
            slot_date=payload.slot_date,
            window_ids=window_ids,
        )

        to_create: list[Slot] = []
        skipped = 0
        for window in windows:
            for slot_time in slot_times:
                if (window.id, slot_time) in existing:
                    skipped += 1
                    continue
                to_create.append(
                    Slot(
                        window_id=window.id,
                        service_id=payload.service_id,
                        slot_date=payload.slot_date,
                        slot_time=slot_time,
                        capacity=payload.capacity,
                        booked_count=0,
                    ),
                )

        created_slots = await self.repository.add_many(to_create)
        return SlotGenerateResponseDTO(
            created=len(created_slots),
            skipped=skipped,
            slots=[slot_to_dto(slot) for slot in created_slots],
        )
