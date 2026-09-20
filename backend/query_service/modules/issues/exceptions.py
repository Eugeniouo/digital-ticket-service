class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class IssueNotFoundError(Exception):
    """Issue does not exist in the given department."""


class InvalidIssueStateError(Exception):
    """Action cannot be performed due to the current issue status."""
