"""Authentication service layer."""
from __future__ import annotations

import hmac
import logging
import secrets
import smtplib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.models.user import RefreshToken, User
from app.schemas import Token, UserCreate

logger = logging.getLogger(__name__)


class EmailAlreadyExistsError(ValueError):
    """Raised when attempting to register with an email that already exists."""


class InvalidCredentialsError(ValueError):
    """Raised when authentication credentials are invalid."""


class InvalidPasswordResetTokenError(ValueError):
    """Raised when a password reset token is invalid or expired."""


# WP-71: a refresh that raced a rotation (ten requests waking after the access
# token expired, a keychain write that lost to the next launch) arrives with the
# predecessor a few seconds late. Inside this window it gets the same successor
# the winner holds; after it, a replayed rotated token revokes its family.
REFRESH_TOKEN_GRACE_SECONDS = 30
_GRACE_CHAIN_MAX_HOPS = 5

# WP-71: the six-digit code typed on the phone.
PASSWORD_RESET_CODE_TTL_MINUTES = 15
PASSWORD_RESET_CODE_MAX_ATTEMPTS = 5
# A fresh code is not issued more often than this, so "request, guess five
# times, request again" cannot walk the million codes at request speed.
PASSWORD_RESET_CODE_COOLDOWN_SECONDS = 60

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", ""}  # noqa: S104 - host names, not a bind


def normalize_email(email: str | None) -> str:
    """The one email normal form: surrounding space stripped, lowercased."""

    return (email or "").strip().lower()


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; every comparison here is in UTC."""

    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class PasswordResetRequestResult:
    """Result of a password reset request."""

    reset_token: str | None = None
    reset_url: str | None = None
    reset_code: str | None = None


def _default_vocab_direction_for(native_language: str | None) -> str:
    """Gloss direction must follow the learner's own language, not the German import default."""
    code = (native_language or "").strip().lower()[:2]
    return f"fr_to_{code}" if code in {"de", "en"} else "fr_to_en"


class AuthService:
    """Encapsulates user registration and authentication logic."""

    def __init__(self, db: Session):
        self.db = db

    def register_user(self, payload: UserCreate) -> User:
        """Create a new user in the database."""

        email = normalize_email(payload.email)
        existing_user = self.db.scalar(select(User).where(func.lower(User.email) == email).limit(1))
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
            email=email,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name,
            native_language=payload.native_language,
            target_language=payload.target_language,
            proficiency_level=payload.proficiency_level,
            cefr_estimate=payload.cefr_estimate,
            cefr_target_level=payload.cefr_target_level,
            cefr_estimate_payload=payload.cefr_estimate_payload or {},
            interests=normalized_interests[:500],
            learning_motivation=payload.learning_motivation,
            speaking_comfort=payload.speaking_comfort,
            daily_goal_minutes=payload.daily_goal_minutes,
            daily_goal_xp=payload.daily_goal_xp,
            # Stored for WP-L6, which makes it the vocabulary pace.
            new_words_per_day=payload.new_words_per_day,
            default_vocab_direction=payload.default_vocab_direction
            or _default_vocab_direction_for(payload.native_language),
            notifications_enabled=payload.notifications_enabled,
            practice_reminders=payload.practice_reminders,
            reminder_time=payload.reminder_time,
            streak_notifications=payload.streak_notifications,
            weekly_email_summary=payload.weekly_email_summary,
            achievement_notifications=payload.achievement_notifications,
            serial_edition_notifications=payload.serial_edition_notifications,
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

    def users_with_email(self, email: str, *, active_only: bool = False) -> list[User]:
        """Every account whose email matches without case, exact spelling first.

        Normally zero or one. Accounts created before WP-71 may differ only by
        case, so callers get a list and decide, never a scalar_one() that 500s.
        """

        normalized = normalize_email(email)
        if not normalized:
            return []
        query = select(User).where(func.lower(User.email) == normalized)
        if active_only:
            query = query.where(User.is_active.is_(True))
        users = list(self.db.scalars(query).all())
        users.sort(key=lambda user: (user.email != normalized, str(user.created_at or "")))
        return users

    def authenticate_user(self, email: str, password: str) -> User:
        """Validate credentials and return the associated user."""

        for user in self.users_with_email(email):
            if verify_password(password, user.hashed_password):
                return user
        raise InvalidCredentialsError("Incorrect email or password")

    def request_password_reset(self, email: str) -> PasswordResetRequestResult:
        """Issue a six-digit code (and a link token) when the account exists.

        The code is what a learner types on the phone. The email carries a link
        as well only when a public app URL is configured: a localhost link in a
        learner's inbox is a dead end.
        """

        candidates = self.users_with_email(email, active_only=True)
        if not candidates:
            return PasswordResetRequestResult()
        user = candidates[0]

        now = datetime.now(UTC)
        last_requested = _as_utc(user.password_reset_requested_at)
        if (
            user.password_reset_code_hash
            and last_requested
            and now - last_requested < timedelta(seconds=PASSWORD_RESET_CODE_COOLDOWN_SECONDS)
        ):
            # The previous code is seconds old and still valid: no second email.
            return PasswordResetRequestResult()

        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        reset_url = self.build_password_reset_url(token)
        user.password_reset_token_hash = self.hash_token(token)
        user.password_reset_code_hash = self.hash_reset_code(user, code)
        user.password_reset_code_attempts = 0
        user.password_reset_requested_at = now
        self.db.add(user)
        self.db.commit()

        public_url = reset_url if self.reset_url_is_public() else None
        self._deliver_password_reset(user, code=code, reset_url=public_url)
        if settings.PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE:
            return PasswordResetRequestResult(reset_token=token, reset_url=reset_url, reset_code=code)
        return PasswordResetRequestResult()

    def confirm_password_reset(self, token: str, new_password: str) -> User:
        """Consume a one-time reset token, set a new password, and revoke sessions."""

        token_hash = self.hash_token(token.strip())
        user = self.db.scalar(
            select(User).where(
                User.password_reset_token_hash == token_hash,
                User.is_active.is_(True),
            ).limit(1)
        )
        if not user or not self._password_reset_token_is_fresh(user.password_reset_requested_at):
            raise InvalidPasswordResetTokenError("Invalid or expired password reset link.")

        return self._complete_password_reset(user, new_password)

    def confirm_password_reset_code(self, email: str, code: str, new_password: str) -> User:
        """Consume a six-digit code: 15 minutes, five attempts, one use."""

        now = datetime.now(UTC)
        code = (code or "").strip()
        for user in self.users_with_email(email, active_only=True):
            if not user.password_reset_code_hash:
                continue
            requested_at = _as_utc(user.password_reset_requested_at)
            attempts = int(user.password_reset_code_attempts or 0)
            expired = not requested_at or now > requested_at + timedelta(
                minutes=PASSWORD_RESET_CODE_TTL_MINUTES
            )
            if expired or attempts >= PASSWORD_RESET_CODE_MAX_ATTEMPTS:
                self._clear_reset_code(user)
                self.db.commit()
                continue
            if hmac.compare_digest(user.password_reset_code_hash, self.hash_reset_code(user, code)):
                return self._complete_password_reset(user, new_password)
            user.password_reset_code_attempts = attempts + 1
            if user.password_reset_code_attempts >= PASSWORD_RESET_CODE_MAX_ATTEMPTS:
                self._clear_reset_code(user)
            self.db.add(user)
            self.db.commit()
        raise InvalidPasswordResetTokenError("Invalid or expired password reset code.")

    def _clear_reset_code(self, user: User) -> None:
        user.password_reset_code_hash = None
        user.password_reset_code_attempts = 0
        self.db.add(user)

    def _complete_password_reset(self, user: User, new_password: str) -> User:
        """Set the password, spend both the link and the code, end every session."""

        user.hashed_password = get_password_hash(new_password)
        user.password_updated_at = datetime.now(UTC)
        user.password_reset_token_hash = None
        user.password_reset_code_hash = None
        user.password_reset_code_attempts = 0
        user.password_reset_requested_at = None
        user.auth_version = int(user.auth_version or 0) + 1
        self.db.add(user)
        self.db.commit()
        self.revoke_all_refresh_tokens(user)
        return user

    @staticmethod
    def hash_reset_code(user: User, code: str) -> str:
        """Keyed digest of a reset code, bound to the account.

        A bare sha256 of six digits is reversed by a table of a million entries;
        keyed with SECRET_KEY and the user id, a leaked column reveals nothing.
        """

        message = f"{user.id}:{(code or '').strip()}".encode()
        return hmac.new(settings.SECRET_KEY.encode("utf-8"), message, sha256).hexdigest()

    @staticmethod
    def reset_url_is_public() -> bool:
        """True when PASSWORD_RESET_BASE_URL points somewhere a phone can open."""

        try:
            parsed = urlparse(settings.PASSWORD_RESET_BASE_URL or "")
        except ValueError:
            return False
        host = (parsed.hostname or "").lower()
        return parsed.scheme in {"http", "https"} and host not in _LOCAL_HOSTS and not host.endswith(".local")

    @staticmethod
    def build_password_reset_url(token: str) -> str:
        """Build the frontend reset URL with the raw token as a query parameter."""

        parsed = urlparse(settings.PASSWORD_RESET_BASE_URL)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["token"] = token
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _password_reset_token_is_fresh(self, requested_at: datetime | None) -> bool:
        if not requested_at:
            return False
        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=UTC)
        expires_at = requested_at + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES)
        return expires_at >= datetime.now(UTC)

    @staticmethod
    def password_reset_email(user: User, *, code: str, reset_url: str | None) -> EmailMessage:
        """The reset email, in the learner's own language, code first."""

        language = (user.native_language or "en").strip().lower()[:2]
        ttl = PASSWORD_RESET_CODE_TTL_MINUTES
        link_ttl = settings.PASSWORD_RESET_TOKEN_TTL_MINUTES
        if language == "de":
            subject = f"{code} – dein Code für L’Atelier"
            lines = [
                "Dein Code zum Zurücksetzen des Passworts:",
                "",
                f"    {code}",
                "",
                f"Gib ihn in der App ein. Er gilt {ttl} Minuten und nur einmal.",
            ]
            link_lines = ["", f"Oder öffne diesen Link ({link_ttl} Minuten gültig):", reset_url or ""]
            footer = "Du hast das nicht angefordert? Dann ignoriere diese E-Mail."
        elif language == "fr":
            subject = f"{code} – votre code L’Atelier"
            lines = [
                "Votre code pour choisir un nouveau mot de passe :",
                "",
                f"    {code}",
                "",
                f"Saisissez-le dans l’application. Valable {ttl} minutes, une seule fois.",
            ]
            link_lines = ["", f"Ou ouvrez ce lien (valable {link_ttl} minutes) :", reset_url or ""]
            footer = "Vous n’avez rien demandé ? Ignorez simplement ce message."
        else:
            subject = f"{code} – your L’Atelier code"
            lines = [
                "Your code to reset your password:",
                "",
                f"    {code}",
                "",
                f"Enter it in the app. It works once, for {ttl} minutes.",
            ]
            link_lines = ["", f"Or open this link (valid for {link_ttl} minutes):", reset_url or ""]
            footer = "Didn't ask for this? You can ignore this email."

        body = [*lines, *(link_lines if reset_url else []), "", footer]
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM_EMAIL or ""
        message["To"] = user.email
        message.set_content("\n".join(body))
        return message

    def _deliver_password_reset(self, user: User, *, code: str, reset_url: str | None) -> bool:
        """Send a reset email when SMTP is configured; otherwise log a safe hint."""

        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            logger.info("Password reset requested for %s, but SMTP is not configured.", user.email)
            return False

        message = self.password_reset_email(user, code=code, reset_url=reset_url)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        except Exception:  # pragma: no cover - network/email provider failure
            logger.exception("Password reset email delivery failed for %s", user.email)
            return False
        return True

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

        token, _record = self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        self.db.commit()
        return token

    def _issue_tokens(
        self,
        user: User,
        *,
        family_id: uuid.UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[Token, RefreshToken]:
        """Mint a pair and stage its refresh record; the caller commits."""

        user_id = uuid.UUID(str(user.id))
        auth_version = int(user.auth_version or 0)
        refresh_token_id = uuid.uuid4()
        # Whole seconds: the JWT `exp` claim is whole seconds, and the grace path
        # re-mints this exact token from the stored row (see _remint_refresh).
        expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        access = create_access_token(str(user_id), auth_version=auth_version)
        refresh = create_refresh_token(
            str(user_id),
            auth_version=auth_version,
            token_id=str(refresh_token_id),
            expires_at=expires_at,
        )
        record = RefreshToken(
            id=refresh_token_id,
            user_id=user_id,
            token_hash=self.hash_token(refresh),
            expires_at=expires_at,
            family_id=family_id or refresh_token_id,
            user_agent=user_agent[:255] if user_agent else None,
            ip_address=ip_address[:64] if ip_address else None,
        )
        self.db.add(record)
        return Token(access_token=access, refresh_token=refresh), record

    def rotate_refresh_token(
        self,
        refresh_token: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> Token:
        """Validate, revoke, and replace a refresh token.

        One live token rotates to exactly one successor. The predecessor,
        presented again within REFRESH_TOKEN_GRACE_SECONDS, is answered with that
        same successor (and a fresh access token) — the ten requests that woke
        together after the access token expired all stay signed in. Presented
        after the window, it revokes the whole family: that is a replay.
        """

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

        now = datetime.now(UTC)
        # FOR UPDATE: concurrent presentations of one token queue here, so only
        # the first rotates and the rest read the successor it committed.
        token_record = self.db.scalar(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.token_hash == self.hash_token(refresh_token),
            )
            .with_for_update()
        )
        if not token_record or _as_utc(token_record.expires_at) <= now:
            raise InvalidCredentialsError("Invalid refresh token")

        if token_record.revoked_at is None:
            token, successor = self._issue_tokens(
                user,
                family_id=token_record.family_id or token_record.id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            token_record.revoked_at = now
            token_record.rotated_at = now
            token_record.last_used_at = now
            token_record.replaced_by_id = successor.id
            self.db.add(token_record)
            self.db.commit()
            return token

        rotated_at = _as_utc(token_record.rotated_at)
        if rotated_at is None or token_record.replaced_by_id is None:
            # Revoked by logout or a password change, not by rotation.
            raise InvalidCredentialsError("Invalid refresh token")

        if now - rotated_at <= timedelta(seconds=REFRESH_TOKEN_GRACE_SECONDS):
            granted = self._grace_successor_token(user, token_record, now)
            if granted is not None:
                return granted
            raise InvalidCredentialsError("Invalid refresh token")

        logger.warning(
            "Rotated refresh token replayed %ss after rotation; revoking its family for user %s.",
            int((now - rotated_at).total_seconds()),
            user.id,
        )
        self._revoke_family(token_record.family_id or token_record.id, now)
        self.db.commit()
        raise InvalidCredentialsError("Invalid refresh token")

    def _grace_successor_token(self, user: User, record: RefreshToken, now: datetime) -> Token | None:
        """The live successor of a just-rotated token, as the winner received it."""

        successor: RefreshToken | None = record
        for _ in range(_GRACE_CHAIN_MAX_HOPS):
            if successor is None or successor.replaced_by_id is None:
                return None
            successor = self.db.get(RefreshToken, successor.replaced_by_id)
            if successor is None:
                return None
            if successor.revoked_at is None:
                break
            # The winner already rotated again inside the window: follow it, but
            # only along rotations — a logout ends the chain.
            if successor.rotated_at is None:
                return None
        else:
            return None
        if successor is None or successor.revoked_at is not None:
            return None
        if _as_utc(successor.expires_at) <= now:
            return None

        refresh = self._remint_refresh(user, successor)
        if refresh is None:
            return None
        access = create_access_token(str(user.id), auth_version=int(user.auth_version or 0))
        return Token(access_token=access, refresh_token=refresh)

    def _remint_refresh(self, user: User, record: RefreshToken) -> str | None:
        """Rebuild a stored refresh token from its claims; None if it would differ."""

        refresh = create_refresh_token(
            str(user.id),
            auth_version=int(user.auth_version or 0),
            token_id=str(record.id),
            expires_at=_as_utc(record.expires_at),
        )
        if not hmac.compare_digest(self.hash_token(refresh), record.token_hash):
            # A row minted before WP-71 (fractional expiry) cannot be rebuilt.
            return None
        return refresh

    def _revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        tokens = self.db.scalars(
            select(RefreshToken).where(
                or_(RefreshToken.family_id == family_id, RefreshToken.id == family_id),
                RefreshToken.revoked_at.is_(None),
            )
        ).all()
        for token in tokens:
            token.revoked_at = now
            self.db.add(token)

    def revoke_refresh_token(self, refresh_token: str | None) -> None:
        """Revoke one refresh token when it is known."""

        if not refresh_token:
            return
        token_record = self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == self.hash_token(refresh_token))
        )
        if token_record and not token_record.revoked_at:
            token_record.revoked_at = datetime.now(UTC)
            self.db.add(token_record)
            self.db.commit()

    def revoke_all_refresh_tokens(self, user: User) -> None:
        """Invalidate every active refresh token for a user."""

        now = datetime.now(UTC)
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
