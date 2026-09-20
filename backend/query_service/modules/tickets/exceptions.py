class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class TicketNotFoundError(Exception):
    """Ticket does not exist."""


class ServiceNotFoundError(Exception):
    """Service does not exist."""


class InactiveServiceError(Exception):
    """Service is currently inactive and cannot accept tickets."""


class InvalidTicketStateError(Exception):
    """Action cannot be performed due to the current ticket status."""


class MissingSlotIdError(Exception):
    """Slot ID is required for this ticket source."""


class UnexpectedSlotIdError(Exception):
    """Slot ID is not allowed for this ticket source."""


class SlotServiceMismatchError(Exception):
    """Slot belongs to a different service than the ticket request."""


class SlotFullError(Exception):
    """Slot has no remaining capacity."""
