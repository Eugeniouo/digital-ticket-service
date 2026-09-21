from uuid import UUID

from fastapi import Depends

from query_service.database.models.department import Department
from query_service.modules.departments.exceptions import DepartmentNotFoundError
from query_service.modules.departments.qr import department_qr_payload, render_qr_svg
from query_service.modules.departments.repository import DepartmentRepository
from query_service.modules.departments.schema import (
    DepartmentCreateRequestDTO,
    DepartmentQrDTO,
    QueueRulesDTO,
    QueueRulesUpdateDTO,
)
from query_service.modules.tickets.queue_rules import QueueRules, default_queue_rules, queue_rules_from_department


def _queue_rules_dto(department: Department) -> QueueRulesDTO:
    rules: QueueRules = queue_rules_from_department(department)

    return QueueRulesDTO(
        bonus_web=rules.bonus_web,
        bonus_qr=rules.bonus_qr,
        bonus_walk_in=rules.bonus_walk_in,
        max_wait_web=rules.max_wait_web,
        max_wait_qr=rules.max_wait_qr,
        max_wait_walk_in=rules.max_wait_walk_in,
    )


class DepartmentService:
    """Department logic."""

    def __init__(self, repository: DepartmentRepository = Depends()) -> None:
        self.repository = repository

    async def get_all(self) -> list[Department]:
        return await self.repository.get_all()

    async def get_by_id(self, department_id: UUID) -> Department:
        department = await self.repository.get_by_id(department_id)
        # Падаем с ошибкой на уровне сервиса вместо хэндлера
        if department is None:
            raise DepartmentNotFoundError
        return department

    async def create(self, payload: DepartmentCreateRequestDTO) -> Department:
        rules = default_queue_rules()

        department = Department(
            code=payload.code,
            address=payload.address,
            open_time=payload.open_time,
            close_time=payload.close_time,
            is_active=payload.is_active,
            queue_bonus_web=rules.bonus_web,
            queue_bonus_qr=rules.bonus_qr,
            queue_bonus_walk_in=rules.bonus_walk_in,
            queue_max_wait_web=rules.max_wait_web,
            queue_max_wait_qr=rules.max_wait_qr,
            queue_max_wait_walk_in=rules.max_wait_walk_in,
        )

        return await self.repository.add(department)

    async def get_qr(self, department_id: UUID, base_url: str) -> DepartmentQrDTO:
        department = await self.get_by_id(department_id)
        payload = department_qr_payload(base_url, department.id)

        return DepartmentQrDTO(
            department_id=department.id,
            code=department.code,
            address=department.address,
            payload=payload,
            svg=render_qr_svg(payload),
        )

    async def get_queue_rules(self, department_id: UUID) -> QueueRulesDTO:
        department = await self.get_by_id(department_id)

        return _queue_rules_dto(department)

    async def update_queue_rules(self, department_id: UUID, payload: QueueRulesUpdateDTO) -> QueueRulesDTO:
        department = await self.get_by_id(department_id)

        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(department, f"queue_{field}", value)

        await self.repository.save()

        return _queue_rules_dto(department)
