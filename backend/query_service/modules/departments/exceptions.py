class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class DuplicateDepartmentCodeError(Exception):
    """Department short code already exists."""


class InvalidQrBaseUrlError(Exception):
    """QR base URL is not a public HTTPS origin."""
