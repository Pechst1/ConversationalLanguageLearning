"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1 import api_router
from app.config import settings

tags_metadata: list[dict[str, str]] = [
    {"name": "auth", "description": "Register users and issue authentication tokens."},
    {"name": "users", "description": "Manage learner profiles and preferences."},
    {"name": "vocabulary", "description": "Browse curated vocabulary collections."},
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate production settings and report optional-service gaps at startup."""

    if settings.APP_ENV.strip().lower() == "production":
        if settings.AUTO_CREATE_USERS_ON_LOGIN:
            raise RuntimeError("AUTO_CREATE_USERS_ON_LOGIN must be false in production.")
        if settings.PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE:
            raise RuntimeError("PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE must be false in production.")
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required for password reset in production.")

    if settings.SERIAL_WORLD_ENABLED and (
        not settings.ATELIER_LLM_ENABLED or not settings.OPENAI_API_KEY
    ):
        logger.warning(
            "Serial World is enabled but the Feuilleton story LLM is not fully configured; "
            "serial episodes after the opener will enter delayed state until OPENAI_API_KEY and "
            "OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL are configured."
        )

    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Conversational practice platform for language learners.",
        version="0.1.0",
        openapi_tags=tags_metadata,
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.GRAPHIC_NOVEL_IMAGE_STORAGE == "local":
        settings.GRAPHIC_NOVEL_LOCAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        app.mount(
            settings.GRAPHIC_NOVEL_LOCAL_IMAGE_URL_PREFIX.rstrip("/"),
            StaticFiles(directory=str(settings.GRAPHIC_NOVEL_LOCAL_IMAGE_DIR)),
            name="graphic_novel_images",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=jsonable_encoder({"detail": exc.errors(), "message": "Validation failed"}),
        )

    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    def ready(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
        """Report readiness only when the primary datastore is reachable."""

        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.error("Readiness check failed: database unavailable")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            ) from exc
        return {"status": "ready"}

    return app


app = create_app()
