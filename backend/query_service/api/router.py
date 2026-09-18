from fastapi.routing import APIRouter

from query_service.api import monitoring
from query_service.modules import departments, dummy

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(dummy.router, prefix="/dummy", tags=["dummy"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
