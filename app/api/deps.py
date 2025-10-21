"""Shared API dependencies."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import InvalidTokenError, decode_token
from app.db.models.user import User
from app.db.session import SessionLocal
from app.schemas import TokenPayload
from app.services.llm_service import LLMService
from app.services.progress import ProgressService
from app.services.session_service import SessionService
from app.core.conversation import ConversationGenerator
from app.core.error_detection import ErrorDetector

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

_llm_service_singleton: LLMService | None = None
_error_detector_singleton: ErrorDetector | None = None


def get_db() -> Session:
    """Yield a database session for request lifetime."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Resolve the authenticated user from the Authorization header."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise InvalidTokenError("Token must be an access token")
        token_data = TokenPayload.model_validate(payload)
    except (InvalidTokenError, ValidationError, ValueError, KeyError) as exc:
        raise credentials_exception from exc

    user_id = uuid.UUID(str(token_data.sub))
    user = db.get(User, user_id)
    if not user:
        raise credentials_exception
    return user


def get_llm_service() -> LLMService:
    """Return a cached LLM service instance or raise if unavailable."""

    global _llm_service_singleton
    if _llm_service_singleton is None:
        try:
            _llm_service_singleton = LLMService()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM providers are not configured",
            ) from exc
    return _llm_service_singleton


def get_error_detector(
    llm_service: LLMService = Depends(get_llm_service),
) -> ErrorDetector:
    """Return a cached error detector bound to the LLM service."""

    global _error_detector_singleton
    if _error_detector_singleton is None:
        _error_detector_singleton = ErrorDetector(llm_service=llm_service)
    return _error_detector_singleton


def get_session_service(
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
    error_detector: ErrorDetector = Depends(get_error_detector),
) -> SessionService:
    """Assemble the session service with request-scoped dependencies."""

    progress_service = ProgressService(db)
    conversation_generator = ConversationGenerator(
        progress_service=progress_service, llm_service=llm_service
    )
    return SessionService(
        db,
        progress_service=progress_service,
        conversation_generator=conversation_generator,
        error_detector=error_detector,
        llm_service=llm_service,
    )
