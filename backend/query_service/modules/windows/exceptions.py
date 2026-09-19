class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class WindowNotFoundError(Exception):
    """Window does not exist in the given department."""


class WindowClosedError(Exception):
    """Call-next is only allowed on an open window."""


class EmptyQueueError(Exception):
    """No queued ticket matches this window's services."""


class NoTicketInProgressError(Exception):
    """Window has no called or serving ticket to complete."""


class TicketAlreadyInProgressError(Exception):
    """Window already has a called or serving ticket."""


class ServiceNotInDepartmentError(Exception):
    """A service does not belong to this department."""


class DuplicateWindowLabelError(Exception):
    """Window label is already used in this department."""


class WindowHasActiveTicketError(Exception):
    """Window cannot be closed while a ticket is called or serving."""
