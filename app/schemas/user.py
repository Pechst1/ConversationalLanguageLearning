"""Pydantic models for user API interactions."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.config import settings

Theme = Literal["light", "dark", "system"]
FontSize = Literal["small", "medium", "large"]
# Registration derives the gloss direction from the learner's own language
# (``_default_vocab_direction_for``), so ``fr_to_en`` is the default for every
# English native — the majority. Leaving it out of this literal made the
# settings page's save payload a guaranteed 422 for those accounts: they could
# not change a single preference. Keep both language pairs in both directions.
VocabDirection = Literal["fr_to_de", "de_to_fr", "fr_to_en", "en_to_fr", "mixed"]
GrammarCorrectionLevel = Literal["strict", "moderate", "lenient"]
ProficiencyLevel = Literal["beginner", "A1", "A2", "B1", "B2", "C1", "C2"]
# How the story engine addresses the learner. "neutral" is the default and means
# gender-neutral phrasing with no gendered endearments and never an inclusive dot.
AddressPreference = Literal["feminine", "masculine", "neutral"]


# WP-71. bcrypt reads 72 bytes and bcrypt 5 raises past that, so a longer new
# password was a 500. Counted in UTF-8 bytes: «é» is two, most emoji four.
PASSWORD_MAX_BYTES = 72
PASSWORD_TOO_LONG_MESSAGE = (
    f"Password is too long: at most {PASSWORD_MAX_BYTES} bytes "
    "(accented letters count as two, emoji as four)."
)


def normalize_email_input(value: Any) -> Any:
    """Emails are matched without case: strip and lowercase before validation."""

    if isinstance(value, str):
        return value.strip().lower()
    return value


def check_new_password_bytes(value: str) -> str:
    """Refuse a new password bcrypt could not hash in full."""

    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(PASSWORD_TOO_LONG_MESSAGE)
    return value


class UserBase(BaseModel):
    """Shared properties of user representations."""

    email: EmailStr
    full_name: str | None = None
    native_language: str = Field(default="en", max_length=10)
    target_language: str = Field(default="fr", max_length=10)
    proficiency_level: str = Field(default="beginner", max_length=20)
    cefr_estimate: str = Field(default="A1.1", max_length=10)
    cefr_target_level: str = Field(default="A1.2", max_length=10)
    cefr_estimate_payload: dict[str, Any] | None = Field(default_factory=dict)
    interests: str = Field(
        default="",
        max_length=500,
        description="Comma-separated interest topics for personalized content",
    )
    learning_motivation: str = Field(default="", max_length=80)
    speaking_comfort: str = Field(default="warming_up", max_length=20)
    daily_goal_minutes: int = Field(default=15, ge=0)
    daily_goal_xp: int = Field(default=50, ge=0)
    new_words_per_day: int = Field(default=10, ge=1)
    # None = derive from native_language at registration (fr_to_de only for German natives).
    default_vocab_direction: str | None = Field(default=None, max_length=20)
    
    # Notifications
    notifications_enabled: bool = True
    practice_reminders: bool = True
    reminder_time: str = Field(default="09:00", max_length=10)
    streak_notifications: bool = True
    weekly_email_summary: bool = True
    achievement_notifications: bool = True
    serial_edition_notifications: bool = True
    preferred_session_time: time | None = None

    # Appearance
    theme: str = Field(default="system", max_length=20)
    font_size: str = Field(default="medium", max_length=20)

    # Audio
    voice_input_enabled: bool = True
    text_to_speech_enabled: bool = True
    tts_speed: str = Field(default="1.0", max_length=10)
    auto_play_pronunciation: bool = True

    # Grammar
    grammar_correction_level: str = Field(default="moderate", max_length=20)
    show_grammar_explanations: bool = True


#: WP-75. The one onboarding question left on sign-up: «Nouveau / Quelques
#: bases / À l'aise». It is a declaration, not a measurement, so it only ever
#: sets the *declared* level (``proficiency_level``) and the honest floor of
#: the estimate; a placement or the learner's own journeys move it from there.
StartingPoint = Literal["new", "some", "comfortable"]
STARTING_POINT_LEVELS: dict[str, str] = {"new": "A1", "some": "A2", "comfortable": "B1"}
#: The estimate a declaration starts at: the floor of the declared band.
STARTING_POINT_ESTIMATES: dict[str, tuple[str, str]] = {
    "new": ("A1.1", "A1.2"),
    "some": ("A2.1", "A2.2"),
    "comfortable": ("B1.1", "B1.2"),
}


class UserCreate(UserBase):
    """Schema for user registration input.

    WP-75: email and password are the only required fields. Every profile field
    has a default (``UserBase``) and moves to Réglages; ``starting_point`` is
    the one question sign-up still asks.
    """

    password: str = Field(min_length=8, max_length=128)
    starting_point: StartingPoint | None = None

    _normalize_email = field_validator("email", mode="before")(normalize_email_input)
    _password_bytes = field_validator("password")(check_new_password_bytes)

    @field_validator("native_language", mode="before")
    @classmethod
    def _native_language_default(cls, value: Any) -> Any:
        # The client sends its interface language; an empty value is "not said".
        if value is None or (isinstance(value, str) and not value.strip()):
            return "en"
        return value

    @model_validator(mode="after")
    def _apply_starting_point(self) -> UserCreate:
        """«Nouveau / Quelques bases / À l'aise» → A1 / A2 / B1.

        Only when the client did not state a level itself: an explicit
        ``proficiency_level`` (every pre-WP-75 client) wins, and so does an
        explicit ``cefr_estimate``.
        """

        point = self.starting_point
        if point is None:
            return self
        explicit = self.model_fields_set
        if "proficiency_level" not in explicit:
            self.proficiency_level = STARTING_POINT_LEVELS[point]
            if "cefr_estimate" not in explicit:
                estimate, target = STARTING_POINT_ESTIMATES[point]
                self.cefr_estimate = estimate
                if "cefr_target_level" not in explicit:
                    self.cefr_target_level = target
        return self


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr
    # Not held to the 72-byte rule: an account created under bcrypt 4 may have a
    # longer password, and checking it compares the prefix bcrypt stored.
    password: str = Field(max_length=1024)

    _normalize_email = field_validator("email", mode="before")(normalize_email_input)


class PasswordResetRequest(BaseModel):
    """Request a password reset code (and link, where a public app URL exists)."""

    email: EmailStr

    _normalize_email = field_validator("email", mode="before")(normalize_email_input)


class PasswordResetRequestResponse(BaseModel):
    """Enumeration-safe password reset request response."""

    message: str
    # Dev/test only (PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE); never in production.
    reset_token: str | None = None
    reset_url: str | None = None
    reset_code: str | None = None


class PasswordResetConfirm(BaseModel):
    """Confirm a password reset with a one-time link token, or email plus code.

    The six-digit code is the phone path (WP-71): no web host or universal link
    is needed. The link token stays accepted for emails already sent.
    """

    token: str | None = Field(default=None, min_length=16, max_length=256)
    email: EmailStr | None = None
    code: str | None = Field(default=None, pattern=r"^\s*\d{6}\s*$")
    new_password: str = Field(min_length=8, max_length=128)

    _normalize_email = field_validator("email", mode="before")(normalize_email_input)
    _password_bytes = field_validator("new_password")(check_new_password_bytes)

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def token_or_code(self) -> PasswordResetConfirm:
        if self.token:
            return self
        if self.email and self.code:
            return self
        raise ValueError("Provide either a reset token, or the email and the six-digit code.")


class UserRead(UserBase):
    """Schema returned after user registration or retrieval."""

    id: uuid.UUID
    is_active: bool
    is_verified: bool
    subscription_tier: str
    subscription_expires_at: datetime | None
    role: str = "user"
    total_xp: int
    level: int
    current_streak: int
    longest_streak: int
    last_activity_date: date | None
    serial_onboarding_seen: bool = False
    address_preference: AddressPreference = "neutral"

    model_config = ConfigDict(from_attributes=True)

    # Rows written before the column existed can still read back NULL; a profile
    # read must never 500 over an unset preference.
    @field_validator("address_preference", mode="before")
    @classmethod
    def default_address_preference(cls, value: Any) -> Any:
        return value or "neutral"


class UserUpdate(BaseModel):
    """Schema for partial updates to the current user profile."""

    full_name: str | None = Field(default=None, max_length=255)
    native_language: str | None = Field(default=None, max_length=10)
    target_language: str | None = Field(default=None, max_length=10)
    proficiency_level: str | None = Field(default=None, max_length=20)
    cefr_target_level: str | None = Field(default=None, max_length=10)
    interests: str | None = Field(default=None, max_length=500)
    learning_motivation: str | None = Field(default=None, max_length=80)
    speaking_comfort: str | None = Field(default=None, max_length=20)
    daily_goal_minutes: int | None = Field(default=None, ge=0)
    daily_goal_xp: int | None = Field(default=None, ge=0)
    new_words_per_day: int | None = Field(default=None, ge=1)
    default_vocab_direction: str | None = Field(default=None, max_length=20)
    
    notifications_enabled: bool | None = None
    practice_reminders: bool | None = None
    reminder_time: str | None = Field(default=None, max_length=10)
    streak_notifications: bool | None = None
    weekly_email_summary: bool | None = None
    achievement_notifications: bool | None = None
    serial_edition_notifications: bool | None = None
    preferred_session_time: time | None = None

    theme: str | None = Field(default=None, max_length=20)
    font_size: str | None = Field(default=None, max_length=20)

    voice_input_enabled: bool | None = None
    text_to_speech_enabled: bool | None = None
    tts_speed: str | None = Field(default=None, max_length=10)
    auto_play_pronunciation: bool | None = None

    grammar_correction_level: str | None = Field(default=None, max_length=20)
    show_grammar_explanations: bool | None = None

    address_preference: AddressPreference | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ensure_payload_not_empty(self) -> UserUpdate:
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one field must be provided")
        return self


class UserSettingsRead(BaseModel):
    """Current account, learning, notification, appearance, audio, and grammar settings."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    native_language: str
    target_language: str
    proficiency_level: str
    cefr_estimate: str = "A1.1"
    cefr_target_level: str = "A1.2"
    cefr_estimate_payload: dict[str, Any] | None = Field(default_factory=dict)
    interests: str
    learning_motivation: str
    speaking_comfort: str

    daily_goal_minutes: int
    daily_goal_xp: int
    new_words_per_day: int
    default_vocab_direction: str
    preferred_session_time: time | None = None

    notifications_enabled: bool
    practice_reminders: bool
    reminder_time: str
    streak_notifications: bool
    weekly_email_summary: bool
    achievement_notifications: bool
    serial_edition_notifications: bool
    #: WP-80: the IANA zone the reminder time is in.
    timezone: str | None = "Europe/Paris"

    theme: str
    font_size: str

    voice_input_enabled: bool
    text_to_speech_enabled: bool
    tts_speed: str
    auto_play_pronunciation: bool

    grammar_correction_level: str
    show_grammar_explanations: bool

    address_preference: AddressPreference = "neutral"

    # WP-49: read-only deployment facts the client needs before it offers a
    # feature. Not on the user row; never accepted by the update payload.
    episode_audio_enabled: bool = Field(default_factory=lambda: bool(settings.ATELIER_EPISODE_AUDIO_ENABLED))

    role: str
    is_active: bool
    is_verified: bool
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("address_preference", mode="before")
    @classmethod
    def default_address_preference(cls, value: Any) -> Any:
        return value or "neutral"


class UserSettingsUpdate(BaseModel):
    """Partial settings update payload for the current user."""

    full_name: str | None = Field(default=None, max_length=255)
    native_language: str | None = Field(default=None, max_length=10)
    target_language: str | None = Field(default=None, max_length=10)
    proficiency_level: ProficiencyLevel | None = None
    cefr_target_level: str | None = Field(default=None, pattern=r"^(A1\.1|A1\.2|A2\.1|A2\.2|B1\.1|B1\.2|B2\.1|B2\.2)$")
    interests: str | None = Field(default=None, max_length=500)
    learning_motivation: str | None = Field(default=None, max_length=80)
    speaking_comfort: Literal["warming_up", "ready", "confident"] | None = None

    daily_goal_minutes: int | None = Field(default=None, ge=0, le=240)
    daily_goal_xp: int | None = Field(default=None, ge=0, le=2000)
    new_words_per_day: int | None = Field(default=None, ge=1, le=100)
    default_vocab_direction: VocabDirection | None = None
    preferred_session_time: time | None = None

    notifications_enabled: bool | None = None
    practice_reminders: bool | None = None
    # \d{2}:\d{2} accepted "25:99" and stored it as the daily reminder.
    reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    streak_notifications: bool | None = None
    weekly_email_summary: bool | None = None
    achievement_notifications: bool | None = None
    serial_edition_notifications: bool | None = None
    #: WP-80: an IANA zone name; anything else is refused, never guessed.
    timezone: str | None = Field(default=None, max_length=64)

    theme: Theme | None = None
    font_size: FontSize | None = None

    voice_input_enabled: bool | None = None
    text_to_speech_enabled: bool | None = None
    tts_speed: str | None = Field(default=None, pattern=r"^(0\.[5-9]|1(\.[0-5])?)$")
    auto_play_pronunciation: bool | None = None

    grammar_correction_level: GrammarCorrectionLevel | None = None
    show_grammar_explanations: bool | None = None

    address_preference: AddressPreference | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("native_language", "target_language")
    @classmethod
    def normalize_language_code(cls, value: str | None) -> str | None:
        return value.lower() if value else value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        from app.services.streak import valid_timezone

        zone = valid_timezone(value)
        if zone is None:
            raise ValueError("timezone must be an IANA zone name, e.g. Europe/Paris")
        return zone

    @model_validator(mode="after")
    def ensure_payload_not_empty(self) -> UserSettingsUpdate:
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one field must be provided")
        return self


class UserPasswordChange(BaseModel):
    """Password change payload for the current user."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    _password_bytes = field_validator("new_password")(check_new_password_bytes)


class UserEmailChange(BaseModel):
    """Email change payload for the current user."""

    current_password: str
    new_email: EmailStr

    _normalize_email = field_validator("new_email", mode="before")(normalize_email_input)
