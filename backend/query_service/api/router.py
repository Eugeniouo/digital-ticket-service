from fastapi.routing import APIRouter

from query_service.api import monitoring
from query_service.modules import departments, services, slots, windows
from query_service.modules.auth.handler import auth_router, staff_router
from query_service.modules.tickets.handler import router as tickets_router

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(staff_router, prefix="/staff", tags=["staff"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(services.router, prefix="/departments/{department_id}/services", tags=["services"])
api_router.include_router(windows.router, prefix="/departments/{department_id}/windows", tags=["windows"])
api_router.include_router(slots.router, prefix="/departments/{department_id}/slots", tags=["slots"])
api_router.include_router(tickets_router, prefix="/departments/{department_id}/tickets", tags=["tickets"])
