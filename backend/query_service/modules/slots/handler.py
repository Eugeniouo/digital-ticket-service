from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from query_service.database.models.staff import Staff
from query_service.modules.auth.dependencies import require_admin
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
from query_service.modules.slots.schema import (
    SlotCreateRequestDTO,
    SlotDTO,
    SlotGenerateRequestDTO,
    SlotGenerateResponseDTO,
    SlotUpdateRequestDTO,
)
from query_service.modules.slots.service import SlotsService

router = APIRouter()


@router.get(
    "",
    response_model=list[SlotDTO],
    responses={404: {"description": "Department not found"}},
)
async def list_slots(
    department_id: UUID,
    slot_date: date = Query(...),
    service_id: UUID = Query(...),
    window_id: UUID | None = Query(None),
    svc: SlotsService = Depends(),
) -> list[SlotDTO]:
    try:
        return await svc.list_slots(
            department_id,
            slot_date=slot_date,
            service_id=service_id,
            window_id=window_id,
        )
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.get(
    "/{slot_id}",
    response_model=SlotDTO,
    responses={404: {"description": "Slot not found in this department"}},
)
async def get_slot(
    department_id: UUID,
    slot_id: UUID,
    svc: SlotsService = Depends(),
) -> SlotDTO:
    try:
        return await svc.get_slot(department_id, slot_id)
    except SlotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found in this department",
        ) from exc


@router.post(
    "",
    response_model=SlotDTO,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Department not found"},
        400: {"description": "Service or window invalid for this department"},
        409: {"description": "Slot already exists"},
    },
)
async def create_slot(
    department_id: UUID,
    payload: SlotCreateRequestDTO,
    svc: SlotsService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> SlotDTO:
    try:
        return await svc.create_slot(department_id, payload)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc
    except ServiceNotInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service not found or inactive in this department",
        ) from exc
    except WindowNotInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Window not found in this department",
        ) from exc
    except ServiceNotOnWindowError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service is not bound to this window",
        ) from exc
    except DuplicateSlotError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot already exists for this window, service, date and time",
        ) from exc


@router.patch(
    "/{slot_id}",
    response_model=SlotDTO,
    responses={
        404: {"description": "Slot not found in this department"},
        400: {"description": "Capacity is less than booked_count"},
    },
)
async def update_slot(
    department_id: UUID,
    slot_id: UUID,
    payload: SlotUpdateRequestDTO,
    svc: SlotsService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> SlotDTO:
    try:
        return await svc.update_slot(department_id, slot_id, payload)
    except SlotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found in this department",
        ) from exc
    except InvalidCapacityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Capacity cannot be less than booked_count",
        ) from exc


@router.delete(
    "/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Slot not found in this department"},
        409: {"description": "Slot has bookings"},
    },
)
async def delete_slot(
    department_id: UUID,
    slot_id: UUID,
    svc: SlotsService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> None:
    try:
        await svc.delete_slot(department_id, slot_id)
    except SlotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found in this department",
        ) from exc
    except SlotHasBookingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot cannot be deleted while it has bookings",
        ) from exc


@router.post(
    ":generate",
    response_model=SlotGenerateResponseDTO,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Department not found"},
        400: {"description": "Service invalid or no windows offer it"},
    },
)
async def generate_slots(
    department_id: UUID,
    payload: SlotGenerateRequestDTO,
    svc: SlotsService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> SlotGenerateResponseDTO:
    try:
        return await svc.generate(department_id, payload)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc
    except ServiceNotInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service not found or inactive in this department",
        ) from exc
    except NoWindowsForServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No windows in this department offer the service",
        ) from exc
