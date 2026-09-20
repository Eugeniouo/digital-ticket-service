from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from query_service.database.models.staff import Staff, StaffRole
from query_service.database.models.ticket import TicketSource
from query_service.modules.auth.dependencies import get_optional_staff
from query_service.modules.slots.exceptions import SlotNotFoundError
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
from query_service.modules.tickets.schema import TicketCreateRequest, TicketResponse
from query_service.modules.tickets.service import TicketService

router = APIRouter(tags=["Tickets"])


def _ensure_walk_in_operator(
    department_id: UUID,
    payload: TicketCreateRequest,
    staff: Staff | None,
) -> None:
    if payload.source != TicketSource.WALK_IN:
        return
    if staff is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if staff.role != StaffRole.OPERATOR or staff.department_id != department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Service or slot not found in this department"},
        400: {"description": "Service inactive, missing/unexpected slot_id, or slot/service mismatch"},
        409: {"description": "Slot is full"},
    },
    summary="Issue a new ticket",
)
async def create_ticket(
    department_id: UUID,
    payload: TicketCreateRequest,
    svc: TicketService = Depends(),
    staff: Staff | None = Depends(get_optional_staff),
) -> TicketResponse:
    """
    Issue a new ticket for a specific service.
    Supports generation via QR code, Walk-In, or Web (Appointment).
    If the source is 'web', providing a valid slot_id is mandatory.
    """
    _ensure_walk_in_operator(department_id, payload, staff)

    try:
        return await svc.issue_ticket(department_id, payload)

    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found in this department",
        ) from exc

    except SlotNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found in this department",
        ) from exc

    except InactiveServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested service is currently inactive",
        ) from exc

    except MissingSlotIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot ID is required for web appointments",
        ) from exc

    except UnexpectedSlotIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot ID is only allowed for web appointments",
        ) from exc

    except SlotServiceMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot does not belong to the requested service",
        ) from exc

    except SlotFullError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot has no remaining capacity",
        ) from exc


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    responses={
        404: {"description": "Ticket not found in this department"},
    },
    summary="Get ticket details",
)
async def get_ticket(
    department_id: UUID,
    ticket_id: UUID,
    svc: TicketService = Depends(),
) -> TicketResponse:
    """
    Retrieve current information about a ticket including its status,
    assigned window, queue source, and estimated wait time.
    """
    try:
        return await svc.get_ticket_info(department_id, ticket_id)

    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found in this department",
        ) from exc


@router.post(
    "/{ticket_id}:cancel",
    response_model=TicketResponse,
    responses={
        404: {"description": "Ticket not found in this department"},
        409: {"description": "Ticket cannot be canceled in its current state"},
    },
    summary="Cancel a ticket",
)
async def cancel_ticket(
    department_id: UUID,
    ticket_id: UUID,
    svc: TicketService = Depends(),
) -> TicketResponse:
    """
    Cancel a queued ticket.
    A ticket cannot be canceled after it was called, completed, or already canceled.
    """
    try:
        return await svc.cancel_ticket(department_id, ticket_id)

    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found in this department",
        ) from exc

    except InvalidTicketStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket is not queued and cannot be canceled",
        ) from exc
