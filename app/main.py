"""FastAPI application factory."""
from fastapi import FastAPI

from app.api.v1 import api_router
from app.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(title=settings.PROJECT_NAME)
    app.include_router(api_router, prefix=settings.API_V1_STR)
    return app


app = create_app()
