class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class WindowNotFoundError(Exception):
    """Window does not exist in the given department."""


class WindowClosedError(Exception):
    """Call-next is only allowed on an open window."""


class EmptyQueueError(Exception):
    """No queued ticket matches this window's services."""


class WindowHasNoServicesError(Exception):
    """Call-next needs at least one service bound to the window."""


class NoTicketInProgressError(Exception):
    """Window has no called or serving ticket to complete."""


class NoCalledTicketError(Exception):
    """Window has no CALLED ticket to start serving."""


class TicketAlreadyInProgressError(Exception):
    """Window already has a called or serving ticket."""


class ServiceNotInDepartmentError(Exception):
    """A service does not belong to this department."""


class DuplicateWindowLabelError(Exception):
    """Window label is already used in this department."""


class WindowHasActiveTicketError(Exception):
    """Window cannot be closed while a ticket is called or serving."""


class WindowOccupiedError(Exception):
    """Another operator already sits at this window."""


class OperatorOnDifferentWindowError(Exception):
    """Operator already sits at another window."""


class OperatorNotSeatedError(Exception):
    """Operator is not seated at this window."""


class ServicesNotAllowedError(Exception):
    """Open services must be a non-empty subset of the window catalog."""


class OpenServicesWouldBeEmptyError(Exception):
    """Catalog change would leave an open window with no shift services."""
