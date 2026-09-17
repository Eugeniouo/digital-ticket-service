from fastapi import FastAPI

from query_service.api.router import api_router
from query_service.lifespan import lifespan_setup
from query_service.log import configure_logging


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    configure_logging()
    app = FastAPI(
        title="query_service",
        lifespan=lifespan_setup,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Main router for the API.
    app.include_router(router=api_router, prefix="/api")

    return app
