from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from query_service.database.models.department import Department
from query_service.database.models.ticket import TicketSource
from query_service.settings import settings


@dataclass(frozen=True, slots=True)
class QueueRules:
    bonus_web: int
    bonus_qr: int
    bonus_walk_in: int
    max_wait_web: int
    max_wait_qr: int
    max_wait_walk_in: int

    def bonus(self, source: TicketSource) -> int:
        if source == TicketSource.WEB:
            return self.bonus_web
        if source == TicketSource.QR:
            return self.bonus_qr
        if source == TicketSource.WALK_IN:
            return self.bonus_walk_in
        return 0

    def max_wait(self, source: TicketSource) -> int:
        if source == TicketSource.WEB:
            return self.max_wait_web
        if source == TicketSource.QR:
            return self.max_wait_qr
        if source == TicketSource.WALK_IN:
            return self.max_wait_walk_in
        return 0


def default_queue_rules() -> QueueRules:
    return QueueRules(
        bonus_web=settings.queue_bonus_web,
        bonus_qr=settings.queue_bonus_qr,
        bonus_walk_in=settings.queue_bonus_walk_in,
        max_wait_web=settings.queue_max_wait_web,
        max_wait_qr=settings.queue_max_wait_qr,
        max_wait_walk_in=settings.queue_max_wait_walk_in,
    )


def queue_rules_from_department(department: Department) -> QueueRules:
    return QueueRules(
        bonus_web=department.queue_bonus_web,
        bonus_qr=department.queue_bonus_qr,
        bonus_walk_in=department.queue_bonus_walk_in,
        max_wait_web=department.queue_max_wait_web,
        max_wait_qr=department.queue_max_wait_qr,
        max_wait_walk_in=department.queue_max_wait_walk_in,
    )


async def load_queue_rules(session: AsyncSession, department_id: UUID) -> QueueRules:
    department = await session.get(Department, department_id)
    if department is None:
        return default_queue_rules()

    return queue_rules_from_department(department)
