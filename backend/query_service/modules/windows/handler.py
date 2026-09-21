from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from query_service.database.models.staff import Staff
from query_service.modules.auth.dependencies import require_admin, require_department_staff, require_operator
from query_service.modules.tickets.exceptions import InactiveServiceError, InvalidTicketStateError
from query_service.modules.tickets.schema import TicketResponse
from query_service.modules.windows.exceptions import (
    DepartmentNotFoundError,
    DuplicateWindowLabelError,
    EmptyQueueError,
    NoCalledTicketError,
    NoTicketInProgressError,
    OperatorOnDifferentWindowError,
    ServiceNotInDepartmentError,
    TicketAlreadyInProgressError,
    WindowClosedError,
    WindowHasActiveTicketError,
    WindowHasNoServicesError,
    WindowNotFoundError,
    WindowOccupiedError,
)
from query_service.modules.windows.schema import (
    WindowCreateRequestDTO,
    WindowDTO,
    WindowRedirectRequestDTO,
    WindowUpdateRequestDTO,
)
from query_service.modules.windows.service import WindowsService

router = APIRouter()


@router.get("", response_model=list[WindowDTO], responses={404: {"description": "Department not found"}})
async def list_windows(
    department_id: UUID,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_department_staff),
) -> list[WindowDTO]:
    try:
        return await svc.list_windows(department_id)

    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc


@router.post(
    "",
    response_model=WindowDTO,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Department not found"},
        400: {"description": "Service not found in this department"},
        409: {"description": "Window label already exists in this department"},
    },
)
async def create_window(
    department_id: UUID,
    payload: WindowCreateRequestDTO,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_admin),
) -> WindowDTO:
    try:
        return await svc.create_window(department_id, payload)

    except DepartmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found") from exc

    except ServiceNotInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service not found in this department",
        ) from exc

    except DuplicateWindowLabelError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Window label already exists in this department",
        ) from exc


@router.patch(
    "/{window_id}",
    response_model=WindowDTO,
    responses={
        404: {"description": "Window not found in this department"},
        409: {"description": "Window has an active ticket, is occupied, or operator already sits elsewhere"},
    },
)
async def update_window(
    department_id: UUID,
    window_id: UUID,
    payload: WindowUpdateRequestDTO,
    svc: WindowsService = Depends(),
    staff: Staff = Depends(require_operator),
) -> WindowDTO:
    try:
        return await svc.update_window(department_id, window_id, payload, operator_id=staff.id)

    except WindowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Window not found in this department",
        ) from exc

    except ServiceNotInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service not available in this department",
        ) from exc

    except WindowHasActiveTicketError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Window has an active ticket and cannot be closed",
        ) from exc

    except WindowOccupiedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Window is already occupied by another operator",
        ) from exc

    except OperatorOnDifferentWindowError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operator already sits at another window",
        ) from exc


@router.post(
    "/{window_id}:call-next",
    response_model=TicketResponse,
    responses={
        404: {"description": "Window not found in this department"},
        409: {
            "description": "Window is closed, a ticket is already in progress, or the matching queue is empty.",
        },
    },
)
async def call_next(
    department_id: UUID,
    window_id: UUID,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_operator),
) -> TicketResponse:
    try:
        return TicketResponse.model_validate(await svc.call_next(department_id, window_id))

    except WindowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Window not found in this department",
        ) from exc

    except WindowClosedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Window is closed") from exc

    except WindowHasNoServicesError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Window has no services configured",
        ) from exc

    except TicketAlreadyInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Window already has a ticket in progress",
        ) from exc

    except EmptyQueueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No queued ticket for this window",
        ) from exc


@router.post(
    "/{window_id}:start",
    response_model=TicketResponse,
    responses={
        404: {"description": "Window not found in this department"},
        409: {"description": "No called ticket at this window to start serving"},
    },
)
async def start(
    department_id: UUID,
    window_id: UUID,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_operator),
) -> TicketResponse:
    try:
        return TicketResponse.model_validate(await svc.start(department_id, window_id))

    except WindowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Window not found in this department",
        ) from exc

    except NoCalledTicketError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No called ticket at this window to start serving",
        ) from exc


@router.post(
    "/{window_id}:noshow",
    response_model=TicketResponse,
    responses={
        404: {"description": "Window not found in this department"},
        409: {"description": "No called ticket at this window to mark as no-show"},
    },
)
async def mark_no_show(
    department_id: UUID,
    window_id: UUID,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_operator),
) -> TicketResponse:
    try:
        return TicketResponse.model_validate(await svc.mark_no_show(department_id, window_id))

    except WindowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Window not found in this department",
        ) from exc

    except NoCalledTicketError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No called ticket at this window to mark as no-show",
        ) from exc


@router.post(
    "/{window_id}:complete",
    response_model=TicketResponse,
    responses={
        404: {"description": "Window not found in this department"},
        409: {"description": "No ticket in progress at this window"},
    },
)
async def complete(
    department_id: UUID,
    window_id: UUID,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_operator),
) -> TicketResponse:
    try:
        return TicketResponse.model_validate(await svc.complete(department_id, window_id))

    except WindowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Window not found in this department",
        ) from exc

    except NoTicketInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No ticket in progress at this window",
        ) from exc


@router.post(
    "/{window_id}:requeue",
    response_model=TicketResponse,
    responses={
        404: {"description": "Window not found in this department"},
        409: {"description": "No ticket in progress at this window"},
    },
)
async def requeue(
    department_id: UUID,
    window_id: UUID,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_operator),
) -> TicketResponse:
    try:
        return TicketResponse.model_validate(await svc.requeue(department_id, window_id))

    except WindowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Window not found in this department",
        ) from exc

    except (NoTicketInProgressError, InvalidTicketStateError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No ticket in progress at this window",
        ) from exc


@router.post(
    "/{window_id}:redirect",
    response_model=TicketResponse,
    responses={
        404: {"description": "Window not found in this department"},
        400: {"description": "Service not in department or inactive"},
        409: {"description": "No ticket in progress at this window"},
    },
)
async def redirect(
    department_id: UUID,
    window_id: UUID,
    payload: WindowRedirectRequestDTO,
    svc: WindowsService = Depends(),
    _staff: Staff = Depends(require_operator),
) -> TicketResponse:
    try:
        return TicketResponse.model_validate(await svc.redirect(department_id, window_id, payload))

    except WindowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Window not found in this department",
        ) from exc

    except ServiceNotInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service not found in this department",
        ) from exc

    except InactiveServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested service is currently inactive",
        ) from exc

    except (NoTicketInProgressError, InvalidTicketStateError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No ticket in progress at this window",
        ) from exc
