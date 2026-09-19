class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class SlotNotFoundError(Exception):
    """Slot does not exist in the given department."""


class ServiceNotInDepartmentError(Exception):
    """Service does not belong to this department or is inactive."""


class WindowNotInDepartmentError(Exception):
    """Window does not belong to this department."""


class ServiceNotOnWindowError(Exception):
    """Service is not bound to the window."""


class DuplicateSlotError(Exception):
    """Slot already exists for this window, service, date and time."""


class SlotHasBookingsError(Exception):
    """Slot cannot be deleted while booked_count > 0."""


class InvalidCapacityError(Exception):
    """New capacity is less than current booked_count."""


class NoWindowsForServiceError(Exception):
    """No windows in the department offer this service."""
