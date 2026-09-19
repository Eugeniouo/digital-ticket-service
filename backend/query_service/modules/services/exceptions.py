class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class ServiceNotFoundError(Exception):
    """Service does not exist in the given department."""
