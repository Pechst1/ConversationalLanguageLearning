"""Application configuration management."""
from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    APP_ENV: str = Field("development", description="Runtime environment name, e.g. development/staging/production.")
    PROJECT_NAME: str = "Conversational Language Learning"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field(..., description="JWT secret key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = Field(
        60,
        description="How long one-time password reset links remain valid.",
    )
    PASSWORD_RESET_BASE_URL: str = Field(
        "http://localhost:3000/auth/forgot-password",
        description="Frontend URL used as the base for password reset links.",
    )
    PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE: bool = Field(
        False,
        description="Dev/test only: include the raw reset token in the API response.",
    )
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True

    DATABASE_URL: AnyUrl = Field(
        "postgresql+psycopg2://postgres:postgres@localhost:5432/language_learning",
        description="SQLAlchemy database URL",
    )

    REDIS_URL: AnyUrl = Field(
        "redis://localhost:6379/0", description="Redis connection string for cache and Celery"
    )

    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "capacitor://localhost",
            "ionic://localhost",
        ],
        description="Allowed CORS origins",
    )

    OPENAI_API_KEY: str | None = None
    OPENAI_ORG_ID: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    PRIMARY_LLM_PROVIDER: str = Field("openai", description="Preferred LLM provider key")
    SECONDARY_LLM_PROVIDER: str | None = Field(
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
    PERPLEXITY_API_KEY: str | None = Field(None, description="API key for Perplexity search (optional)")
    SUBSTACK_FEED_URLS: str = Field(
        "",
        description="Comma-separated Substack RSS feed URLs for live content mode (optional)",
    )
    ELEVENLABS_API_KEY: str | None = Field(None, description="API key for ElevenLabs TTS (optional)")
    TTS_PROVIDER: str = Field("openai", description="Default TTS provider (openai, elevenlabs)")
    OPENAI_API_BASE: AnyUrl | None = Field(
        None, description="Override base URL for OpenAI-compatible endpoints"
    )
    ANTHROPIC_MODEL: str = Field("claude-3-5-sonnet", description="Default Anthropic model")
    ANTHROPIC_API_BASE: AnyUrl | None = Field(
        None, description="Override base URL for Anthropic endpoints"
    )
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(90.0, description="Timeout for LLM HTTP calls")
    LLM_MAX_RETRIES: int = Field(3, description="Retry attempts for failed LLM calls")
    # ---- WP-70: resilience, rate limits, spend ceiling (begin) -------------
    # LLM_MAX_RETRIES above is the total attempt count per call (first try
    # included); only timeouts, connection errors, 429 and 5xx are retried, all
    # inside the call's one request_timeout deadline.
    LLM_CIRCUIT_BREAKER_THRESHOLD: int = Field(
        5,
        ge=1,
        description="Consecutive failed provider calls (after retries) that open the circuit.",
    )
    LLM_CIRCUIT_BREAKER_OPEN_SECONDS: float = Field(
        60.0,
        ge=0,
        description="How long an open provider circuit refuses calls before letting one through.",
    )
    RATE_LIMIT_ENABLED: bool = Field(True, description="Master switch for the WP-70 rate limits.")
    RATE_LIMIT_AUTH_MAX_REQUESTS: int = Field(
        10, ge=0, description="Per-IP requests to one auth door (login/register/reset) per window. 0 = off."
    )
    RATE_LIMIT_AUTH_WINDOW_SECONDS: int = Field(60, ge=1)
    RATE_LIMIT_PAID_MAX_REQUESTS: int = Field(
        60, ge=0, description="Per-learner requests to paid routes per window. 0 = off."
    )
    RATE_LIMIT_PAID_WINDOW_SECONDS: int = Field(60, ge=1)
    RATE_LIMIT_TRUSTED_PROXY_HOPS: int = Field(
        1,
        ge=0,
        description="Proxies we run in front of the API (Render = 1); the client IP is that many X-Forwarded-For entries from the right. 0 = trust only the socket peer.",
    )
    RATE_LIMIT_EXEMPT_PEERS: str = Field(
        "testclient",
        description="Comma-separated raw ASGI peers never limited (Starlette's TestClient reports 'testclient', which no socket can).",
    )
    USER_DAILY_SPEND_CAP_USD: float = Field(
        0.50,
        ge=0,
        description="Per-learner spend per UTC day across the cost ledgers; paid routes answer 429 daily_budget_reached beyond it. 0 = off. A normal day costs ~US$0.05.",
    )
    # ---- WP-70 (end) -------------------------------------------------------
    FRENCH_NLP_MODEL: str = Field(
        "fr_core_news_sm",
        description="spaCy model used for French linguistic analysis",
    )



    # Web Push
    VAPID_SUBJECT: str = "mailto:admin@example.com"
    VAPID_PRIVATE_KEY: str | None = None
    VAPID_PUBLIC_KEY: str | None = None
    APNS_TEAM_ID: str | None = Field(
        None,
        description="Apple Developer team identifier used to sign APNs provider tokens.",
    )
    APNS_KEY_ID: str | None = Field(
        None,
        description="Apple Push Notifications authentication key identifier.",
    )
    APNS_PRIVATE_KEY: str | None = Field(
        None,
        description="Contents of the APNs .p8 private key; escaped newlines are accepted.",
    )
    APNS_BUNDLE_ID: str = Field(
        "com.pixellab.feuilleton",
        description="iOS application bundle identifier/APNs topic.",
    )
    APNS_USE_SANDBOX: bool = Field(
        True,
        description="Send native notifications through Apple's development APNs host.",
    )
    PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD: float = Field(
        2.0,
        ge=0,
        description="Admin dashboard warning threshold for weekly Serial spend per learner.",
    )

    CELERY_BROKER_URL: AnyUrl | None = None
    CELERY_RESULT_BACKEND: AnyUrl | None = None

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
        "gpt-5-mini",
        description="Fast capable model for generating Atelier exercise payloads.",
    )
    ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS: float = Field(
        90.0,
        description="Single-attempt timeout for Atelier exercise generation before deterministic fallback.",
    )
    ATELIER_EXERCISE_LLM_REASONING_EFFORT: str | None = Field(
        "minimal",
        description="Optional reasoning_effort override for Atelier exercise models that support it.",
    )
    ATELIER_EXERCISE_CRITIQUE_ENABLED: bool = Field(
        True,
        description="Use an AI critic to validate generated Atelier exercise payloads before serving them.",
    )
    ATELIER_CRITIQUE_LLM_MODEL: str = Field(
        "gpt-5-mini",
        description="Fast model for AI critique of generated Atelier exercises.",
    )
    ATELIER_CRITIQUE_LLM_TIMEOUT_SECONDS: float = Field(
        45.0,
        description="Single-attempt timeout for Atelier exercise critique.",
    )
    ATELIER_CRITIQUE_LLM_MAX_TOKENS: int = Field(
        1200,
        description="Output token cap for Atelier exercise critique.",
    )
    ATELIER_CRITIQUE_LLM_REASONING_EFFORT: str | None = Field(
        "minimal",
        description="Optional reasoning_effort override for Atelier critique models that support it.",
    )
    ATELIER_FORGE_ENABLED: bool = Field(
        True,
        description=(
            "WP-S3 La Forge: new séances are composed by the forge (staircase per rule, "
            "item-level evidence, reprise, interleaving). False keeps the legacy ladder."
        ),
    )
    ATELIER_BACKGROUND_PREGENERATION_ENABLED: bool = Field(
        True,
        description="Pre-generate the learner's next Atelier session in the background.",
    )
    ATELIER_ITEM_BANK_ENABLED: bool = Field(
        True,
        description=(
            "WP-S2 La Forge: build each séance concept's exercises from the generative item bank "
            "(app/data/grammar_templates) — no LLM on start, no sentence twice in 7 days — before the "
            "shared LLM pool and the curated fallback."
        ),
    )
    ATELIER_POOL_SETS_PER_BAND: int = Field(
        3,
        description="WP-S2: vetted shared LLM pool sets kept per (unit, learner band) by the batch pre-generation job.",
    )
    ATELIER_POOL_BACKGROUND_TOPUP_ENABLED: bool = Field(
        False,
        description="WP-S2: top up a thin shared LLM pool in the background after a séance starts (off the request path).",
    )
    ATELIER_LLM_FAILURE_BACKOFF_SECONDS: float = Field(
        120.0,
        description="How long Atelier skips live exercise generation after a provider outage.",
    )
    ATELIER_CORRECTION_LLM_ENABLED: bool = Field(
        True,
        description="Use AI assessment for open answers; provider failure saves them unassessed. Keyed drills retain deterministic checking.",
    )
    ATELIER_CORRECTION_LLM_MODEL: str = Field(
        "gpt-5-mini",
        description="Fast model for low-latency Atelier submit corrections.",
    )
    ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS: float = Field(
        60.0,
        description="Single-attempt deadline for a complete paragraph assessment; provider failure remains unassessed.",
    )
    ATELIER_CORRECTION_LLM_MAX_TOKENS: int = Field(
        5000,
        description="Output token cap for live Atelier LLM correction.",
    )
    ATELIER_CORRECTION_LLM_REASONING_EFFORT: str | None = Field(
        "low",
        description="Optional reasoning_effort override for Atelier correction models that support it.",
    )
    OPENAI_IMAGE_MODEL: str = Field("gpt-image-2.5-flare", description="Default OpenAI image model (gpt-image-2.5-flare: the fast, high-quality everyday model; gpt-image-2.5-sunburst is the most capable one, same list price)")
    OPENAI_IMAGE_QUALITY: str = Field("medium", description="Default OpenAI image generation quality")
    OPENAI_IMAGE_SIZE: str = Field("1024x1024", description="Default OpenAI image generation size")
    OPENAI_IMAGE_TIMEOUT_SECONDS: float = Field(240.0, description="Timeout for OpenAI image generation calls")
    OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL: str = Field(
        "gpt-5-mini",
        description="OpenAI model for standard Feuilleton story/script generation",
    )
    OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL: str = Field(
        "gpt-4o",
        description="OpenAI model for premium Feuilleton story/script generation",
    )
    GRAPHIC_NOVEL_DEFAULT_PANEL_COUNT: int = Field(6, description="Default Feuilleton panel count")
    GRAPHIC_NOVEL_IMAGE_COST_USD_PER_PANEL: float = Field(
        0.053,
        description="Estimated image-generation cost per 1024x1024 medium gpt-image-2.5 panel",
    )
    GRAPHIC_NOVEL_IMAGE_CONCURRENCY: int = Field(
        3,
        description="Maximum number of Feuilleton panel images to generate concurrently",
    )
    GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED: bool = Field(
        False,
        description="Generate Feuilleton panel images through OpenAI. When false, deterministic SVG panels are used.",
    )
    # "local" by default: inlining base64 panels made every episode payload ~64 MB.
    # Production sets "s3"; "data_uri" remains available for tests/one-off tooling.
    GRAPHIC_NOVEL_IMAGE_STORAGE: str = Field(
        "local",
        description="Feuilleton image persistence mode: data_uri, local, or s3.",
    )
    GRAPHIC_NOVEL_LOCAL_IMAGE_DIR: Path = Field(
        Path(__file__).resolve().parent.parent / "var" / "graphic-novel-images",
        description="Directory for locally persisted Feuilleton panel images.",
    )
    GRAPHIC_NOVEL_LOCAL_IMAGE_URL_PREFIX: str = Field(
        "/media/graphic-novel",
        description="Public URL prefix mounted for locally persisted Feuilleton panel images.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_BUCKET: str | None = Field(
        None,
        description="S3-compatible bucket for persisted Feuilleton panel images.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_KEY_PREFIX: str = Field(
        "graphic-novel",
        description="Object key prefix for persisted Feuilleton panel images.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_REGION: str | None = Field(
        None,
        description="S3 region for Feuilleton panel image storage.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_ENDPOINT_URL: str | None = Field(
        None,
        description="Optional S3-compatible endpoint URL for Feuilleton panel image storage.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_ACCESS_KEY_ID: str | None = Field(
        None,
        description="Optional S3 access key for Feuilleton panel image storage.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_SECRET_ACCESS_KEY: str | None = Field(
        None,
        description="Optional S3 secret key for Feuilleton panel image storage.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_PUBLIC_BASE_URL: str | None = Field(
        None,
        description="Optional public base URL for S3-compatible Feuilleton panel images.",
    )
    GRAPHIC_NOVEL_IMAGE_S3_ACL: str | None = Field(
        None,
        description="Optional object ACL for S3-compatible Feuilleton panel images.",
    )
    GRAPHIC_NOVEL_DEMO_SCRIPT_ENABLED: bool = Field(
        False,
        description="Dev/QA only: generate a deterministic Feuilleton script when the story LLM is disabled.",
    )
    FEUILLETON_AUDIO_ENABLED: bool = Field(
        False,
        description="Generate pre-rendered serial Feuilleton narration/audio for panel captions and dialogue.",
    )
    FEUILLETON_AUDIO_TTS_MODEL: str = Field(
        "tts-1-hd",
        description="TTS model used when serial Feuilleton audio generation is enabled.",
    )
    FEUILLETON_AUDIO_COST_USD_PER_1K_CHARS: float = Field(
        0.015,
        description="Estimated TTS cost per 1,000 characters for serial Feuilleton audio rollups.",
    )
    FEUILLETON_AUDIO_MAX_CHARS_PER_SCENE: int = Field(
        2400,
        description="Maximum serial Feuilleton text-to-speech characters generated per scene.",
    )
    ATELIER_EPISODE_AUDIO_ENABLED: bool = Field(
        False,
        description=(
            "WP-32: synthesize the daily journey's scene as a radio episode for the "
            "opt-in listening-first cycle. Dark by default — with this off nothing is "
            "read, no speech call is made, and the scene is read as text as before."
        ),
    )
    SERIAL_WORLD_ENABLED: bool = Field(
        False,
        description="Enable the serial Missions x Feuilleton spine. Defaults dark for staged rollout.",
    )
    SERIAL_PHONE_CALL_MISSIONS_ENABLED: bool = Field(
        False,
        description="Enable experimental phone-call mission formats inside the serial planner.",
    )
    ATELIER_DAILY_JOURNEY_ENABLED: bool = Field(
        True,
        description=(
            "Enable the Atelier V2 five-minute daily journey. Owner decision 2026-09-10: "
            "the journey is the product's daily Séance, so it defaults ON and the legacy "
            "drill loop becomes «Plus de pratique». The server response stays "
            "authoritative, and already-created journeys keep draining if it is ever "
            "switched off again. Who actually gets it is still ATELIER_DAILY_JOURNEY_COHORT: "
            "outside production an empty cohort means everyone, in production it means "
            "nobody until the list says '*' or names them (journey_enabled_for)."
        ),
    )
    ATELIER_STORY_ENGINE_ENABLED: bool = Field(
        True, description="Generate new daily situations and semantic responses from shared serial state."
    )
    ATELIER_STORY_MAX_ATTEMPTS: int = Field(2, ge=1, le=3)
    ATELIER_STORY_TURN_LANES_ENABLED: bool = Field(
        True,
        description=(
            "WP-87: grade and answer a story turn in two small parallel lanes (tutor, "
            "voice) and write the ending, bookkeeping and critic in a third lane after "
            "the response. Off restores the single ACTOR + CRITIC turn."
        ),
    )
    # ---- WP-78: a real day's worth of practice -------------------------------
    ATELIER_JOURNEY_PRACTICE_DAY_ENABLED: bool = Field(
        True,
        description=(
            "WP-78: plan each daily journey as a practice day — quick recall items "
            "(matching pairs, read-and-tap, unscramble, …) before the scene, between "
            "the scene and the reply, and one after it — inside the same stated "
            "budget. Off restores the pre-WP-78 day (scene, at most two recalls, "
            "reply, ending). Journeys already planned keep the shape they were built with."
        ),
    )
    # ---- WP-69: never lose a day (begin) -----------------------------------
    ATELIER_JOURNEY_AUTHORED_FALLBACK_ENABLED: bool = Field(
        True,
        description=(
            "When the story engine cannot write today's scene (both attempts rejected, "
            "provider down, story conflict), serve an authored scene for the learner's "
            "band instead of an 'unavailable' day. Recorded in "
            "plan_selection.generation_fallback only; the learner is not told. Off "
            "restores the pre-WP-69 honest dead end."
        ),
    )
    SCHEMA_GUARD_ENABLED: bool = Field(
        True,
        description=(
            "At startup compare the database's alembic revision with the migration head. "
            "APP_ENV=production refuses to start when they differ; other environments "
            "log loudly. /ready answers 503 while the database is behind."
        ),
    )
    # ---- WP-69 (end) -------------------------------------------------------
    # ---- WP-75: a win before an account (begin) ----------------------------
    ATELIER_JOURNEY_FIRST_DAY_AUTHORED_ENABLED: bool = Field(
        True,
        description=(
            "A learner with no completed day gets an authored first day for their "
            "band — the café at Le Mistral, two quick recall items, one reply, the "
            "cast introduced — with no model call, so it is ready the moment it is "
            "asked for. The story engine takes over from day 2. Off restores the "
            "pre-WP-75 first day (generated like any other)."
        ),
    )
    # ---- WP-75 (end) -------------------------------------------------------

    ATELIER_DAILY_JOURNEY_COHORT: str = Field(
        "",
        description="Comma-separated user emails or ids allowed into the V2 pilot.",
    )

    # ---- WP-26: latency as a product feature -----------------------------
    ATELIER_JOURNEY_PREFETCH_ENABLED: bool = Field(
        True,
        description=(
            "Generate the next journey scene ahead of time so the draft is served warm. "
            "Off means the previous behaviour exactly: generate on the request. The "
            "beat still refuses anyone outside ATELIER_DAILY_JOURNEY_COHORT and anyone "
            "already at the weekly cost guardrail."
        ),
    )
    ATELIER_JOURNEY_PREFETCH_TTL_SECONDS: int = Field(
        26 * 3600,
        ge=300,
        le=7 * 24 * 3600,
        description=(
            "How long a prefetched scene may wait to be served. Longer than a day so an "
            "overnight run still covers a late session; a scene older than this is "
            "discarded and its spend billed on the discard row."
        ),
    )
    ATELIER_JOURNEY_PREFETCH_MAX_LEARNERS: int = Field(
        25,
        ge=0,
        le=500,
        description="Hard bound on how many learners one prefetch beat may pay for.",
    )
    ATELIER_JOURNEY_PREFETCH_ACTIVE_DAYS: int = Field(
        7,
        ge=1,
        le=90,
        description="Only learners with a journey event this recent are prefetched for.",
    )

    # ---- WP-31: rehearsing a real upcoming situation ---------------------
    ATELIER_REHEARSAL_WEEKLY_CAP: int = Field(
        2,
        ge=0,
        le=14,
        description=(
            "How many rehearsals («Répétition») one learner may start in a rolling "
            "seven days. Each one pays for a scene generation and a debrief correction, "
            "so this is a hard cost bound, not a nudge: at the cap the learner is told "
            "in French how long until the next one. 0 switches the feature off — the "
            "page then explains why rather than 500-ing."
        ),
    )

    # ---- WP-34: bring your own French ------------------------------------
    ATELIER_INTAKE_ENABLED: bool = Field(
        True,
        description=(
            "Whether a learner may hand the app a real document — pasted text or a "
            "photograph — and get it read, glossed and turned into one Courrier task. "
            "Off means the page says so in French; it never 500s."
        ),
    )
    ATELIER_INTAKE_WEEKLY_CAP: int = Field(
        5,
        ge=0,
        le=50,
        description=(
            "How many artefacts one learner may submit in a rolling seven days. Each "
            "one pays for exactly one model call, so this is the volume half of the "
            "cost bound. 0 switches intake off for everybody."
        ),
    )
    ATELIER_INTAKE_WEEKLY_COST_CEILING_USD: float = Field(
        0.50,
        ge=0.0,
        description=(
            "The money half of the same bound: once a learner's intake calls have cost "
            "this much in a rolling seven days, the next submission is refused in French "
            "rather than paid for. 0.0 removes the money ceiling and leaves only the count."
        ),
    )
    ATELIER_INTAKE_VISION_MODEL: str = Field(
        "gpt-4o-mini",
        description=(
            "The vision-capable model a photographed artefact is read with. It must accept "
            "OpenAI-shaped image_url content blocks; an Anthropic-primary deployment needs "
            "the block adapter written out in WP-34-INTAKE.md before it can read photos."
        ),
    )
    ATELIER_INTAKE_TEXT_MODEL: str = Field(
        "gpt-4o-mini",
        description="The model a pasted (already textual) artefact is structured with.",
    )
    ATELIER_INTAKE_MAX_IMAGE_BYTES: int = Field(
        4_000_000,
        ge=10_000,
        le=20_000_000,
        description=(
            "Hard ceiling on one uploaded photograph. A learner-controlled payload sizes a "
            "paid request, so the bound is enforced before a byte reaches the provider."
        ),
    )
    ATELIER_INTAKE_MAX_TOKENS: int = Field(
        1600,
        ge=400,
        le=8000,
        description="Completion budget for the one intake call. Low values starve gpt-5 reasoning models of content.",
    )
    ATELIER_INTAKE_TIMEOUT_SECONDS: float = Field(
        45.0,
        gt=0,
        description="Request timeout for the one intake call. A timeout is «non lu», never a fabricated reading.",
    )

    # ---- WP-L2: the syllabus ---------------------------------------------------
    ATELIER_GRAMMAR_CATALOG_VERSION: str = Field(
        "v1",
        description=(
            "WP-L2: which curated French grammar catalogue is seeded and served. "
            "'v1' = templates/french_core_grammar_v1.tsv (54 coarse concepts, the "
            "current product). 'v2' = templates/french_core_grammar_v2.tsv "
            "(fr-core-v2: ~150 units A1–B2 with sub-bands, prerequisites and "
            "localized rules); switching seeds v2, archives v1 and copies each "
            "learner's v1 progress onto the v2 unit that replaces it."
        ),
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

    @field_validator("GRAPHIC_NOVEL_IMAGE_STORAGE")
    @classmethod
    def validate_graphic_novel_image_storage(cls, value: str) -> str:
        """Restrict Feuilleton image storage to the supported backends."""

        normalized = value.strip().lower()
        if normalized not in {"data_uri", "local", "s3"}:
            raise ValueError("GRAPHIC_NOVEL_IMAGE_STORAGE must be one of: data_uri, local, s3")
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""

    return Settings()


settings = get_settings()
