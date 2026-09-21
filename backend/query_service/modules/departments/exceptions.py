class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class DuplicateDepartmentCodeError(Exception):
    """Department short code already exists."""


class InvalidQrBaseUrlError(Exception):
    """Frontend origin is not an HTTP(S) URL with a host."""
