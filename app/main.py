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
from app.services import story_correspondence

tags_metadata: list[dict[str, str]] = [
    {"name": "auth", "description": "Register users and issue authentication tokens."},
    {"name": "users", "description": "Manage learner profiles and preferences."},
    {"name": "vocabulary", "description": "Browse curated vocabulary collections."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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

    # --- WP-69 schema guard (begin) ---------------------------------------
    # Production refuses to start while the database is behind the migration
    # head this image ships; other environments log it loudly.
    if getattr(settings, "SCHEMA_GUARD_ENABLED", True):
        from app.db.schema_guard import run_startup_guard

        await run_startup_guard(app, app_env=settings.APP_ENV)
    # --- WP-69 schema guard (end) -----------------------------------------

    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    # WP-66 ⋈ WP-64. «Jour de lettre» shipped behind one registration point and
    # nobody had called it, so the shape could never be dealt. This is that call:
    # the daily journey now asks the Courrier for the letter this learner already
    # owes an answer to, and answering it in the journey finishes that letter.
    # Registration is idempotent and costs nothing — the provider only ever reads,
    # and only when a session is handed to it.
    story_correspondence.install_letter_provider()

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

    # --- WP-72 legal pages (begin) ---------------------------------------
    # Public /privacy and /terms on the API host (the App Store Connect privacy
    # URL) and the sign-up consent record under /api/v1/legal/consent.
    from app.api.legal import api_router as legal_api_router
    from app.api.legal import public_router as legal_public_router

    app.include_router(legal_public_router)
    app.include_router(legal_api_router, prefix=settings.API_V1_STR)
    # --- WP-72 legal pages (end) -----------------------------------------

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
        # --- WP-69 schema guard (begin) -----------------------------------
        if getattr(settings, "SCHEMA_GUARD_ENABLED", True):
            from app.db.schema_guard import check_schema

            schema = check_schema(db)
            if schema.is_behind:
                logger.error("Readiness check failed: {}", schema.message())
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="database schema behind",
                )
        # --- WP-69 schema guard (end) -------------------------------------
        return {"status": "ready"}

    return app


app = create_app()
