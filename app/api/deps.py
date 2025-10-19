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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


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
