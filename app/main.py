"""FastAPI application factory."""
from __future__ import annotations

from typing import List

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1 import api_router
from app.config import settings


tags_metadata: List[dict[str, str]] = [
    {"name": "auth", "description": "Register users and issue authentication tokens."},
    {"name": "users", "description": "Manage learner profiles and preferences."},
    {"name": "vocabulary", "description": "Browse curated vocabulary collections."},
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Conversational practice platform for language learners.",
        version="0.1.0",
        openapi_tags=tags_metadata,
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({"detail": exc.errors(), "message": "Validation failed"}),
        )

    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.on_event("startup")
    async def _warn_serial_story_llm_missing() -> None:
        if settings.SERIAL_WORLD_ENABLED and (not settings.ATELIER_LLM_ENABLED or not settings.OPENAI_API_KEY):
            logger.warning(
                "Serial World is enabled but the Feuilleton story LLM is not fully configured; "
                "serial episodes after the opener will enter delayed state until OPENAI_API_KEY and "
                "OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL are configured."
            )

    return app


app = create_app()
