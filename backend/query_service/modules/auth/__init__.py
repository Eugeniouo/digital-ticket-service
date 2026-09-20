"""Staff authentication and account API."""

from query_service.modules.auth.handler import auth_router, staff_router

__all__ = ["auth_router", "staff_router"]
