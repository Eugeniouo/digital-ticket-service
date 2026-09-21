class InvalidCredentialsError(Exception):
    """Username or password is wrong."""


class InactiveStaffError(Exception):
    """Staff account is disabled."""


class DuplicateUsernameError(Exception):
    """Username is already taken."""


class InvalidStaffDepartmentError(Exception):
    """Root cannot do this action."""


class StaffCreateForbiddenError(Exception):
    """Caller cannot create this staff role or department."""


class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class StaffNotFoundError(Exception):
    """Staff account does not exist."""
