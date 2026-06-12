"""Authentication service layer."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.config import settings
from app.db.models.user import RefreshToken, User
from app.schemas import Token, UserCreate


class EmailAlreadyExistsError(ValueError):
    """Raised when attempting to register with an email that already exists."""


class InvalidCredentialsError(ValueError):
    """Raised when authentication credentials are invalid."""


class AuthService:
    """Encapsulates user registration and authentication logic."""

    def __init__(self, db: Session):
        self.db = db

    def register_user(self, payload: UserCreate) -> User:
        """Create a new user in the database."""

        existing_user = self.db.scalar(select(User).where(User.email == payload.email))
        if existing_user:
            raise EmailAlreadyExistsError("A user with this email already exists.")

        normalized_parts: list[str] = []
        seen: set[str] = set()
        for item in (payload.interests or "").split(","):
            normalized = item.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            normalized_parts.append(normalized)
        normalized_interests = ",".join(normalized_parts)

        user = User(
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name,
            native_language=payload.native_language,
            target_language=payload.target_language,
            proficiency_level=payload.proficiency_level,
            interests=normalized_interests[:500],
            daily_goal_minutes=payload.daily_goal_minutes,
            daily_goal_xp=payload.daily_goal_xp,
            new_words_per_day=payload.new_words_per_day,
            default_vocab_direction=payload.default_vocab_direction,
            notifications_enabled=payload.notifications_enabled,
            practice_reminders=payload.practice_reminders,
            reminder_time=payload.reminder_time,
            streak_notifications=payload.streak_notifications,
            weekly_email_summary=payload.weekly_email_summary,
            achievement_notifications=payload.achievement_notifications,
            preferred_session_time=payload.preferred_session_time,
            theme=payload.theme,
            font_size=payload.font_size,
            voice_input_enabled=payload.voice_input_enabled,
            text_to_speech_enabled=payload.text_to_speech_enabled,
            tts_speed=payload.tts_speed,
            auto_play_pronunciation=payload.auto_play_pronunciation,
            grammar_correction_level=payload.grammar_correction_level,
            show_grammar_explanations=payload.show_grammar_explanations,
        )

        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EmailAlreadyExistsError("A user with this email already exists.") from exc
        self.db.refresh(user)
        return user

    def authenticate_user(self, email: str, password: str) -> User:
        """Validate credentials and return the associated user."""

        user = self.db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Incorrect email or password")
        return user

    @staticmethod
    def hash_token(token: str) -> str:
        """Return a stable non-reversible digest for token storage."""

        return sha256(token.encode("utf-8")).hexdigest()

    def create_tokens(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> Token:
        """Generate access and refresh tokens for a user."""

        user_id = uuid.UUID(str(user.id))
        auth_version = int(user.auth_version or 0)
        refresh_token_id = uuid.uuid4()
        access = create_access_token(str(user_id), auth_version=auth_version)
        refresh = create_refresh_token(str(user_id), auth_version=auth_version, token_id=str(refresh_token_id))
        self.db.add(
            RefreshToken(
                id=refresh_token_id,
                user_id=user_id,
                token_hash=self.hash_token(refresh),
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                user_agent=user_agent[:255] if user_agent else None,
                ip_address=ip_address[:64] if ip_address else None,
            )
        )
        self.db.commit()
        return Token(access_token=access, refresh_token=refresh)

    def rotate_refresh_token(
        self,
        refresh_token: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> Token:
        """Validate, revoke, and replace a refresh token."""

        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidCredentialsError("Refresh token required")
        user_id = uuid.UUID(str(payload.get("sub")))
        user = self.db.get(User, user_id)
        if not user or not user.is_active:
            raise InvalidCredentialsError("Invalid refresh token")
        token_version = int(payload.get("av") or 0)
        if token_version != int(user.auth_version or 0):
            raise InvalidCredentialsError("Refresh token has been revoked")

        now = datetime.now(timezone.utc)
        token_record = self.db.scalar(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.token_hash == self.hash_token(refresh_token),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        if not token_record:
            raise InvalidCredentialsError("Invalid refresh token")

        token_record.revoked_at = now
        token_record.last_used_at = now
        self.db.add(token_record)
        return self.create_tokens(user, user_agent=user_agent, ip_address=ip_address)

    def revoke_refresh_token(self, refresh_token: str | None) -> None:
        """Revoke one refresh token when it is known."""

        if not refresh_token:
            return
        token_record = self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == self.hash_token(refresh_token))
        )
        if token_record and not token_record.revoked_at:
            token_record.revoked_at = datetime.now(timezone.utc)
            self.db.add(token_record)
            self.db.commit()

    def revoke_all_refresh_tokens(self, user: User) -> None:
        """Invalidate every active refresh token for a user."""

        now = datetime.now(timezone.utc)
        tokens = self.db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        ).all()
        for token in tokens:
            token.revoked_at = now
            self.db.add(token)
        self.db.commit()


def handle_email_exists(error: EmailAlreadyExistsError) -> None:
    """Raise an HTTP 400 error for duplicate email attempts."""

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    ) from error


def handle_invalid_credentials(error: InvalidCredentialsError) -> None:
    """Raise an HTTP 401 error for invalid login attempts."""

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(error),
        headers={"WWW-Authenticate": "Bearer"},
    ) from error
