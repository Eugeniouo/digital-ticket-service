from datetime import date, time
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.dependencies import get_db_session
from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.slot import Slot
from query_service.database.models.window import Window, WindowService


class SlotsRepository:
    """Database access for slots."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def get_department(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def get_service_in_department(self, department_id: UUID, service_id: UUID) -> Service | None:
        return await self.session.scalar(
            select(Service).where(
                Service.id == service_id,
                Service.department_id == department_id,
            ),
        )

    async def get_window_in_department(self, department_id: UUID, window_id: UUID) -> Window | None:
        return await self.session.scalar(
            select(Window).where(
                Window.id == window_id,
                Window.department_id == department_id,
            ),
        )

    async def window_has_service(self, window_id: UUID, service_id: UUID) -> bool:
        row_id = await self.session.scalar(
            select(WindowService.window_id).where(
                WindowService.window_id == window_id,
                WindowService.service_id == service_id,
            ),
        )
        return row_id is not None

    async def list_windows_with_service(self, department_id: UUID, service_id: UUID) -> list[Window]:
        result = await self.session.scalars(
            select(Window)
            .join(WindowService, WindowService.window_id == Window.id)
            .where(
                Window.department_id == department_id,
                WindowService.service_id == service_id,
            )
            .order_by(Window.label, Window.id),
        )
        return list(result.all())

    async def list_slots(
        self,
        department_id: UUID,
        *,
        slot_date: date,
        service_id: UUID,
        window_id: UUID | None = None,
    ) -> list[Slot]:
        stmt = (
            select(Slot)
            .join(Window, Window.id == Slot.window_id)
            .where(
                Window.department_id == department_id,
                Slot.slot_date == slot_date,
                Slot.service_id == service_id,
            )
            .order_by(Slot.slot_time, Slot.window_id)
        )
        if window_id is not None:
            stmt = stmt.where(Slot.window_id == window_id)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_slot_in_department(self, department_id: UUID, slot_id: UUID) -> Slot | None:
        return await self.session.scalar(
            select(Slot)
            .join(Window, Window.id == Slot.window_id)
            .where(
                Slot.id == slot_id,
                Window.department_id == department_id,
            ),
        )

    async def get_by_id(self, slot_id: UUID) -> Slot | None:
        return await self.session.get(Slot, slot_id)

    async def find_slot(
        self,
        window_id: UUID,
        service_id: UUID,
        slot_date: date,
        slot_time: time,
    ) -> Slot | None:
        return await self.session.scalar(
            select(Slot).where(
                Slot.window_id == window_id,
                Slot.service_id == service_id,
                Slot.slot_date == slot_date,
                Slot.slot_time == slot_time,
            ),
        )

    async def list_existing_times(
        self,
        *,
        service_id: UUID,
        slot_date: date,
        window_ids: list[UUID],
    ) -> set[tuple[UUID, time]]:
        if not window_ids:
            return set()
        result = await self.session.execute(
            select(Slot.window_id, Slot.slot_time).where(
                Slot.service_id == service_id,
                Slot.slot_date == slot_date,
                Slot.window_id.in_(window_ids),
            ),
        )
        return {(row.window_id, row.slot_time) for row in result.all()}

    async def add(self, slot: Slot) -> Slot:
        self.session.add(slot)
        await self.session.flush()
        return slot

    async def add_many(self, slots: list[Slot]) -> list[Slot]:
        if not slots:
            return []
        self.session.add_all(slots)
        await self.session.flush()
        return slots

    async def delete(self, slot: Slot) -> None:
        await self.session.delete(slot)
        await self.session.flush()

    async def flush(self) -> None:
        await self.session.flush()

    async def try_increment_booked(self, slot_id: UUID) -> bool:
        """Atomically book one seat. Returns False if full or missing."""
        result = await self.session.execute(
            update(Slot)
            .where(
                Slot.id == slot_id,
                Slot.booked_count < Slot.capacity,
            )
            .values(booked_count=Slot.booked_count + 1)
            .returning(Slot.id),
        )
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    async def try_decrement_booked(self, slot_id: UUID) -> bool:
        """Atomically free one seat. Returns False if already zero or missing."""
        result = await self.session.execute(
            update(Slot)
            .where(
                Slot.id == slot_id,
                Slot.booked_count > 0,
            )
            .values(booked_count=Slot.booked_count - 1)
            .returning(Slot.id),
        )
        await self.session.flush()
        return result.scalar_one_or_none() is not None
