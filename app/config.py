"""Application configuration management."""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    PROJECT_NAME: str = "Conversational Language Learning"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field(..., description="JWT secret key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    DATABASE_URL: AnyUrl = Field(
        "postgresql+psycopg2://postgres:postgres@localhost:5432/language_learning",
        description="SQLAlchemy database URL",
    )

    REDIS_URL: AnyUrl = Field(
        "redis://localhost:6379/0", description="Redis connection string for cache and Celery"
    )

    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Allowed CORS origins",
    )

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    PRIMARY_LLM_PROVIDER: str = Field("openai", description="Preferred LLM provider key")
    SECONDARY_LLM_PROVIDER: Optional[str] = Field(
        "anthropic", description="Fallback LLM provider key"
    )
    OPENAI_MODEL: str = Field("gpt-5-mini", description="Default OpenAI text model")
    OPENAI_ERROR_DETECTION_MODEL: str = Field(
        "gpt-5-mini",
        description="OpenAI model for exercise correction and error detection",
    )
    OPENAI_MISSION_FAST_MODEL: str = Field(
        "gpt-4o-mini",
        description="Fast OpenAI model for near-real-time mission chat replies",
    )
    MISSION_CHAT_TIMEOUT_SECONDS: float = Field(
        2.0,
        description="Short timeout for mission chat replies before falling back locally",
    )
    PERPLEXITY_API_KEY: Optional[str] = Field(None, description="API key for Perplexity search (optional)")
    SUBSTACK_FEED_URLS: str = Field(
        "",
        description="Comma-separated Substack RSS feed URLs for live content mode (optional)",
    )
    ELEVENLABS_API_KEY: Optional[str] = Field(None, description="API key for ElevenLabs TTS (optional)")
    TTS_PROVIDER: str = Field("openai", description="Default TTS provider (openai, elevenlabs)")
    OPENAI_API_BASE: Optional[AnyUrl] = Field(
        None, description="Override base URL for OpenAI-compatible endpoints"
    )
    ANTHROPIC_MODEL: str = Field("claude-3-5-sonnet", description="Default Anthropic model")
    ANTHROPIC_API_BASE: Optional[AnyUrl] = Field(
        None, description="Override base URL for Anthropic endpoints"
    )
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(90.0, description="Timeout for LLM HTTP calls")
    LLM_MAX_RETRIES: int = Field(3, description="Retry attempts for failed LLM calls")
    FRENCH_NLP_MODEL: str = Field(
        "fr_core_news_sm",
        description="spaCy model used for French linguistic analysis",
    )



    # Web Push
    VAPID_SUBJECT: str = "mailto:admin@example.com"
    VAPID_PRIVATE_KEY: Optional[str] = None
    VAPID_PUBLIC_KEY: Optional[str] = None

    CELERY_BROKER_URL: Optional[AnyUrl] = None
    CELERY_RESULT_BACKEND: Optional[AnyUrl] = None

    # Developer convenience: optionally auto-create users on first login attempt
    AUTO_CREATE_USERS_ON_LOGIN: bool = Field(
        False,
        description="If true, /auth/login will create the user on-the-fly when not found (dev only)",
    )
    SESSION_INLINE_MOMENTS_ENABLED: bool = Field(
        True,
        description="Enable inline grammar and vocabulary learning moments inside sessions",
    )
    ATELIER_LLM_ENABLED: bool = Field(
        True,
        description="Use LLM-backed generation and correction for Atelier when a provider is configured.",
    )
    ATELIER_EXERCISE_LLM_MODEL: str = Field(
        "gpt-4o-mini",
        description="Fast model for generating Atelier exercise payloads.",
    )
    ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS: float = Field(
        60.0,
        description="Single-attempt timeout for Atelier exercise generation.",
    )
    ATELIER_CORRECTION_LLM_ENABLED: bool = Field(
        True,
        description="Use LLM-backed Atelier correction for live submits, with deterministic fallback on provider failure.",
    )
    ATELIER_CORRECTION_LLM_MODEL: str = Field(
        "gpt-5.4-nano",
        description="Fast model for low-latency Atelier submit corrections.",
    )
    ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS: float = Field(
        5.0,
        description="Short single-attempt timeout for optional Atelier LLM correction before deterministic fallback.",
    )
    ATELIER_CORRECTION_LLM_MAX_TOKENS: int = Field(
        900,
        description="Output token cap for live Atelier LLM correction.",
    )
    ATELIER_CORRECTION_LLM_REASONING_EFFORT: Optional[str] = Field(
        None,
        description="Optional reasoning_effort override for Atelier correction models that support it.",
    )
    OPENAI_IMAGE_MODEL: str = Field("gpt-image-2", description="Default OpenAI image model")
    OPENAI_IMAGE_QUALITY: str = Field("medium", description="Default OpenAI image generation quality")
    OPENAI_IMAGE_SIZE: str = Field("1024x1024", description="Default OpenAI image generation size")
    OPENAI_IMAGE_TIMEOUT_SECONDS: float = Field(240.0, description="Timeout for OpenAI image generation calls")
    OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL: str = Field(
        "gpt-5.4-mini",
        description="OpenAI model for standard Feuilleton story/script generation",
    )
    OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL: str = Field(
        "gpt-5.5",
        description="OpenAI model for premium Feuilleton story/script generation",
    )
    GRAPHIC_NOVEL_DEFAULT_PANEL_COUNT: int = Field(6, description="Default Feuilleton panel count")
    GRAPHIC_NOVEL_IMAGE_COST_USD_PER_PANEL: float = Field(
        0.053,
        description="Estimated image-generation cost per 1024x1024 medium gpt-image-2 panel",
    )
    GRAPHIC_NOVEL_IMAGE_CONCURRENCY: int = Field(
        3,
        description="Maximum number of Feuilleton panel images to generate concurrently",
    )
    GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED: bool = Field(
        False,
        description="Generate Feuilleton panel images through OpenAI. When false, deterministic SVG panels are used.",
    )
    GRAPHIC_NOVEL_DEMO_SCRIPT_ENABLED: bool = Field(
        False,
        description="Dev/QA only: generate a deterministic Feuilleton script when the story LLM is disabled.",
    )
    SERIAL_WORLD_ENABLED: bool = Field(
        False,
        description="Enable the serial Missions x Feuilleton spine. Defaults dark for staged rollout.",
    )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("OPENAI_API_BASE", "ANTHROPIC_API_BASE", mode="before")
    @classmethod
    def blank_urls_to_none(cls, value: object) -> object:
        """Treat blank optional URL settings as unset."""

        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""

    return Settings()


settings = get_settings()
