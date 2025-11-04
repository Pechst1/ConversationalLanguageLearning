"""Application configuration management."""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import AnyUrl, Field
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
        default_factory=lambda: ["http://localhost", "http://localhost:3000"],
        description="Allowed CORS origins",
    )

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    PRIMARY_LLM_PROVIDER: str = Field("openai", description="Preferred LLM provider key")
    SECONDARY_LLM_PROVIDER: Optional[str] = Field(
        "anthropic", description="Fallback LLM provider key"
    )
    OPENAI_MODEL: str = Field("gpt-4o-mini", description="Default OpenAI chat model")
    OPENAI_API_BASE: Optional[AnyUrl] = Field(
        None, description="Override base URL for OpenAI-compatible endpoints"
    )
    ANTHROPIC_MODEL: str = Field("claude-3-5-sonnet", description="Default Anthropic model")
    ANTHROPIC_API_BASE: Optional[AnyUrl] = Field(
        None, description="Override base URL for Anthropic endpoints"
    )
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(30.0, description="Timeout for LLM HTTP calls")
    LLM_MAX_RETRIES: int = Field(3, description="Retry attempts for failed LLM calls")
    FRENCH_NLP_MODEL: str = Field(
        "fr_core_news_sm",
        description="spaCy model used for French linguistic analysis",
    )

    CELERY_BROKER_URL: Optional[AnyUrl] = None
    CELERY_RESULT_BACKEND: Optional[AnyUrl] = None

    # Developer convenience: optionally auto-create users on first login attempt
    AUTO_CREATE_USERS_ON_LOGIN: bool = Field(
        False,
        description="If true, /auth/login will create the user on-the-fly when not found (dev only)",
    )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""

    return Settings()


settings = get_settings()
