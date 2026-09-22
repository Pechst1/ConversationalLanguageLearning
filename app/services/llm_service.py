"""LLM service with provider fallback and cost tracking."""
from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, TypeVar

import httpx
from loguru import logger

from app.config import settings

_T = TypeVar("_T")

_AUDIO_EXTENSION_BY_MIME = {
    "audio/aac": "aac",
    "audio/flac": "flac",
    "audio/m4a": "m4a",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/webm": "webm",
    "audio/x-flac": "flac",
    "audio/x-m4a": "m4a",
    "audio/x-wav": "wav",
}
_AUDIO_MIME_BY_EXTENSION = {
    extension: mime_type for mime_type, extension in _AUDIO_EXTENSION_BY_MIME.items()
}
_AUDIO_MIME_BY_EXTENSION.update({"m4a": "audio/mp4", "mp3": "audio/mpeg"})


def _audio_upload_metadata(
    filename: str | None,
    content_type: str | None,
) -> tuple[str, str]:
    """Return safe multipart metadata without lying about iOS MP4 recordings."""
    mime_type = (content_type or "").partition(";")[0].strip().lower()
    extension = _AUDIO_EXTENSION_BY_MIME.get(mime_type)

    if not extension and filename:
        candidate = filename.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)
        if len(candidate) == 2:
            candidate_extension = candidate[-1].lower()
            candidate_mime = _AUDIO_MIME_BY_EXTENSION.get(candidate_extension)
            if candidate_mime:
                extension = candidate_extension
                mime_type = candidate_mime

    if not extension:
        # Preserve the historical default for internal callers that do not provide metadata.
        extension = "webm"
        mime_type = "audio/webm"

    return f"audio.{extension}", mime_type


@dataclass
class LLMResult:
    """Structured response returned by the :class:`LLMService`."""

    provider: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    raw_response: dict[str, Any]


class LLMProviderError(RuntimeError):
    """Raised when a provider returns an error response.

    ``retryable`` is true only for failures a second attempt can fix: timeouts,
    dropped connections, HTTP 429 and 5xx. A 400/401/403/404 is our request or
    our key, and asking again only pays again.
    """

    def __init__(
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class ProviderCircuitOpenError(LLMProviderError):
    """The provider failed repeatedly; calls are refused until it cools down."""


# ---------------------------------------------------------------------------
# WP-70 — prices. Every priced call must carry a price; an unknown model is
# billed at the highest known rate (and logged once), never at $0.
# ---------------------------------------------------------------------------

#: US$ per 1,000 tokens. Sources: the rates this table already carried, plus the
#: OpenAI list prices for the gpt-5 family members the config can select
#: (gpt-5: $1.25/$10 per 1M; gpt-5-nano: $0.05/$0.40 per 1M). ``gpt-5.5`` — the
#: premium Feuilleton script model in render.yaml — has no price documented
#: anywhere in this repository, so it deliberately falls through to the
#: conservative rate below rather than being guessed.
TEXT_PRICES_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "gpt-5": {"prompt": 0.00125, "completion": 0.01},
    "gpt-5-mini": {"prompt": 0.00025, "completion": 0.002},
    "gpt-5-nano": {"prompt": 0.00005, "completion": 0.0004},
    "gpt-5.4-mini": {"prompt": 0.00075, "completion": 0.0045},
    "gpt-5.4-nano": {"prompt": 0.0002, "completion": 0.00125},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
}

#: OpenAI speech, US$ per 1,000 input characters (tts-1 $15/1M, tts-1-hd $30/1M).
TTS_PRICES_PER_1K_CHARS: dict[str, float] = {
    "tts-1": 0.015,
    "tts-1-hd": 0.030,
}

#: OpenAI transcription, US$ per minute of audio (mirrors transcription_cost.py).
TRANSCRIPTION_PRICES_PER_MINUTE: dict[str, float] = {"whisper-1": 0.006}

#: US$ per generated image at the app's default 1024px medium quality. The
#: gpt-image rate is ``GRAPHIC_NOVEL_IMAGE_COST_USD_PER_PANEL`` (the documented
#: gpt-image-2.5 price, same list price for -flare and -sunburst); dall-e-3 is
#: the standard 1024x1024 list price used by the story visualisations.
IMAGE_PRICES_PER_IMAGE: dict[str, float] = {
    "gpt-image": float(getattr(settings, "GRAPHIC_NOVEL_IMAGE_COST_USD_PER_PANEL", 0.053) or 0.053),
    "dall-e-3": 0.04,
}

#: A dated snapshot ("gpt-4o-mini-2024-07-18", "claude-3-5-sonnet-20241022",
#: "...-latest") is priced as its family. Only a date or "latest" suffix counts:
#: "gpt-5.5" must never be priced as "gpt-5".
_SNAPSHOT_SUFFIX = re.compile(r"^-(\d{4}-\d{2}-\d{2}|\d{8}|latest|preview)$")

_unknown_price_lock = threading.Lock()
_unknown_price_logged: set[str] = set()


def _log_unknown_price_once(kind: str, model: str, fallback: Any) -> None:
    key = f"{kind}:{model}"
    with _unknown_price_lock:
        if key in _unknown_price_logged:
            return
        _unknown_price_logged.add(key)
    logger.warning(
        "No {} price for model {!r}; billing it at the highest known rate {} until it is added",
        kind,
        model,
        fallback,
    )


def _lookup_price(table: dict[str, _T], model: str) -> _T | None:
    normalized = (model or "").strip().lower()
    if normalized in table:
        return table[normalized]
    best: str | None = None
    for key in table:
        if normalized.startswith(key) and _SNAPSHOT_SUFFIX.match(normalized[len(key):]):
            if best is None or len(key) > len(best):
                best = key
    return table[best] if best is not None else None


def conservative_text_price() -> dict[str, float]:
    """The highest known per-token rates, billed for a model with no price."""

    return {
        "prompt": max(rates["prompt"] for rates in TEXT_PRICES_PER_1K_TOKENS.values()),
        "completion": max(rates["completion"] for rates in TEXT_PRICES_PER_1K_TOKENS.values()),
    }


def text_price_for(model: str) -> tuple[dict[str, float], bool]:
    """``(rates per 1K tokens, known)`` for a chat model."""

    rates = _lookup_price(TEXT_PRICES_PER_1K_TOKENS, model)
    if rates is not None:
        return rates, True
    fallback = conservative_text_price()
    _log_unknown_price_once("text", model, fallback)
    return fallback, False


def estimate_text_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates, _known = text_price_for(model)
    cost = (max(0, int(prompt_tokens or 0)) / 1000) * rates["prompt"] + (
        max(0, int(completion_tokens or 0)) / 1000
    ) * rates["completion"]
    return round(cost, 6)


def estimate_tts_cost_usd(model: str, char_count: int) -> float:
    """Declared estimate for ``char_count`` synthesised characters on ``model``."""

    rate = _lookup_price(TTS_PRICES_PER_1K_CHARS, model)
    if rate is None:
        rate = max(TTS_PRICES_PER_1K_CHARS.values())
        _log_unknown_price_once("tts", model, rate)
    return round(max(0, int(char_count or 0)) / 1000.0 * rate, 6)


def estimate_image_cost_usd(model: str, images: int = 1) -> float:
    """Declared estimate for ``images`` generated images on ``model``."""

    normalized = (model or "").strip().lower()
    rate = IMAGE_PRICES_PER_IMAGE["gpt-image"] if normalized.startswith("gpt-image") else _lookup_price(
        IMAGE_PRICES_PER_IMAGE, normalized
    )
    if rate is None:
        rate = max(IMAGE_PRICES_PER_IMAGE.values())
        _log_unknown_price_once("image", model, rate)
    return round(max(0, int(images or 0)) * rate, 6)


# ---------------------------------------------------------------------------
# WP-70 — retries under one deadline, and a circuit breaker per provider.
# ---------------------------------------------------------------------------


def _status_error(provider_label: str, status_code: int, message: str) -> LLMProviderError:
    return LLMProviderError(
        f"{provider_label} error {status_code}: {message}",
        status_code=status_code,
        retryable=status_code == 429 or status_code >= 500,
    )


def _transport_error(provider_label: str, exc: httpx.HTTPError) -> LLMProviderError:
    kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "transport error"
    return LLMProviderError(f"{provider_label} {kind}: {exc}", retryable=True)


class CircuitBreaker:
    """Open after ``threshold`` consecutive provider failures, for ``open_seconds``.

    A failure is a *call* that ended on a retryable error (timeout, connection,
    429, 5xx) after its retries — a 4xx proves the provider is up and resets the
    count. While open, calls are refused at once, so a provider outage costs a
    learner a fast fallback instead of a 90-second wait on every request. After
    the cool-down one call is let through; its failure re-opens the breaker.
    State is per process (each uvicorn worker keeps its own).
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._open_until = 0.0

    @staticmethod
    def _threshold() -> int:
        return max(1, int(getattr(settings, "LLM_CIRCUIT_BREAKER_THRESHOLD", 5) or 5))

    @staticmethod
    def _open_seconds() -> float:
        return max(0.0, float(getattr(settings, "LLM_CIRCUIT_BREAKER_OPEN_SECONDS", 60.0) or 0.0))

    def before_call(self) -> None:
        with self._lock:
            remaining = self._open_until - time.monotonic()
        if remaining > 0:
            raise ProviderCircuitOpenError(
                f"{self.name} circuit open for another {remaining:.0f}s after repeated failures",
                retryable=False,
            )

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._open_until = 0.0

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold():
                self._open_until = time.monotonic() + self._open_seconds()
                opened = True
            else:
                opened = False
        if opened:
            logger.warning(
                "LLM circuit for {} opened after {} consecutive failures",
                self.name,
                self._consecutive_failures,
            )

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._open_until > time.monotonic()


_breakers_lock = threading.Lock()
_breakers: dict[str, CircuitBreaker] = {}


def circuit_breaker_for(name: str) -> CircuitBreaker:
    with _breakers_lock:
        breaker = _breakers.get(name)
        if breaker is None:
            breaker = _breakers[name] = CircuitBreaker(name)
        return breaker


def reset_circuit_breakers() -> None:
    """Close every breaker (tests, and an operator who knows the outage ended)."""

    with _breakers_lock:
        _breakers.clear()


#: The first retry waits 1 s, then 2 s, 4 s … capped at 8 s — the old tenacity curve.
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_MAX_SECONDS = 8.0
#: No attempt is started with less than this left on the deadline.
_MIN_ATTEMPT_SECONDS = 1.0


def call_with_retries(
    attempt: Callable[[float], _T],
    *,
    breaker: CircuitBreaker,
    attempts: int,
    deadline_seconds: float,
    backoff_base_seconds: float = _BACKOFF_BASE_SECONDS,
    sleep: Callable[[float], None] | None = None,
) -> _T:
    """Run ``attempt(timeout)`` until it succeeds, under one total deadline.

    Only :class:`LLMProviderError` with ``retryable`` set is retried; any other
    error is raised at once. Each attempt is handed the time still left on the
    deadline as its timeout, and no retry is started (or slept towards) that
    could not finish inside it — ``attempts × request_timeout`` is gone.
    """

    breaker.before_call()
    total_attempts = max(1, int(attempts or 1))
    deadline = max(_MIN_ATTEMPT_SECONDS, float(deadline_seconds or 0.0))
    started = time.monotonic()
    last_error: LLMProviderError | None = None
    for index in range(1, total_attempts + 1):
        remaining = deadline - (time.monotonic() - started)
        if remaining <= 0 or (index > 1 and remaining < _MIN_ATTEMPT_SECONDS):
            break
        try:
            result = attempt(remaining)
        except LLMProviderError as exc:
            last_error = exc
            if not exc.retryable:
                # The provider answered; the request was wrong. Not an outage.
                breaker.record_success()
                raise
            if index == total_attempts:
                break
            wait = min(_BACKOFF_MAX_SECONDS, backoff_base_seconds * (2 ** (index - 1)))
            if (time.monotonic() - started) + wait + _MIN_ATTEMPT_SECONDS > deadline:
                break
            logger.warning(
                "{} attempt {}/{} failed, retrying in {:.0f}s: {}",
                breaker.name,
                index,
                total_attempts,
                wait,
                str(exc)[:200],
            )
            (sleep or time.sleep)(wait)
            continue
        breaker.record_success()
        return result
    breaker.record_failure()
    raise last_error or LLMProviderError(
        f"{breaker.name}: deadline of {deadline:.0f}s exhausted", retryable=True
    )


class BaseLLMProvider(Protocol):
    """Protocol shared by provider implementations."""

    name: str

    def generate(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:  # pragma: no cover - interface definition
        """Generate a chat completion."""


@dataclass
class OpenAIProvider:
    """Generate chat completions using the OpenAI API."""

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    request_timeout: float = 30.0
    max_retries: int = 3

    name: str = "openai"

    #: WP-70: one shared table (unknown models are priced conservatively, never $0).
    COST_PER_1K_TOKENS: ClassVar[dict[str, dict[str, float]]] = TEXT_PRICES_PER_1K_TOKENS

    @property
    def breaker(self) -> CircuitBreaker:
        return circuit_breaker_for(f"{self.name}@{self.base_url}")

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Optionally set organization header when supplied
        if settings and getattr(settings, "OPENAI_ORG_ID", None):  # type: ignore[truthy-bool]
            headers["OpenAI-Organization"] = settings.OPENAI_ORG_ID  # type: ignore[attr-defined]
        return headers

    def _estimate_cost(self, usage: dict[str, Any], model: str | None = None) -> float:
        return estimate_text_cost_usd(
            model or self.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )

    @staticmethod
    def _uses_completion_token_limit(model: str) -> bool:
        """Newer OpenAI reasoning models reject the legacy max_tokens field."""

        return model.startswith("gpt-5")

    def generate(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        """One chat completion, retried only on retryable errors.

        ``request_timeout`` is the call's *total* budget (WP-70): every attempt
        gets what is left of it. ``max_retries`` — ``LLM_MAX_RETRIES`` — is the
        total number of attempts, the first included (the old tenacity policy
        stopped after 3); ``disable_retries`` makes it one.
        """

        disable_retries = bool(kwargs.pop("disable_retries", False))
        deadline = float(kwargs.pop("request_timeout", None) or self.request_timeout)
        return call_with_retries(
            lambda remaining: self._generate_once(messages, request_timeout=remaining, **kwargs),
            breaker=self.breaker,
            attempts=1 if disable_retries else self.max_retries,
            deadline_seconds=deadline,
        )

    def _generate_once(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        model = kwargs.get("model", self.model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
        }
        if not self._uses_completion_token_limit(model):
            payload["temperature"] = kwargs.get("temperature", 0.7)
        if "response_format" in kwargs:
            payload["response_format"] = kwargs["response_format"]
        if "max_tokens" in kwargs:
            if self._uses_completion_token_limit(model):
                payload["max_completion_tokens"] = kwargs["max_tokens"]
            else:
                payload["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("reasoning_effort"):
            payload["reasoning_effort"] = kwargs["reasoning_effort"]

        request_timeout = kwargs.get("request_timeout", self.request_timeout)
        try:
            with httpx.Client(base_url=self.base_url, timeout=request_timeout) as client:
                response = client.post("/chat/completions", json=payload, headers=self._build_headers())
        except httpx.HTTPError as exc:
            raise _transport_error("OpenAI", exc) from exc

        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                error_msg = response.text

            # Escape braces to prevent log format errors
            safe_error_msg = str(error_msg).replace("{", "{{").replace("}", "}}")

            logger.error("OpenAI returned error", status=response.status_code, body=safe_error_msg)
            raise _status_error("OpenAI", response.status_code, safe_error_msg)

        data = response.json()
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content")
        if not content:
            raise LLMProviderError("OpenAI response did not include content")

        usage = data.get("usage", {})
        result = LLMResult(
            provider=self.name,
            model=payload["model"],
            content=content.strip(),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)),
            cost=self._estimate_cost(usage, payload["model"]),
            raw_response=data,
        )
        logger.info(
            "OpenAI completion success",
            model=result.model,
            tokens=result.total_tokens,
            cost=result.cost,
        )
        return result

    def transcribe_audio(
        self,
        file: Any,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Transcribe audio using OpenAI Whisper.

        Retried (WP-70 policy) only when the upload is bytes — a file object
        cannot be re-sent — and only on a retryable error.
        """
        upload_filename, upload_content_type = _audio_upload_metadata(filename, content_type)

        def attempt(timeout: float) -> str:
            try:
                with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
                    files = {"file": (upload_filename, file, upload_content_type)}
                    data = {"model": "whisper-1"}
                    response = client.post(
                        "/audio/transcriptions",
                        files=files,
                        data=data,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
            except httpx.HTTPError as exc:
                raise _transport_error("OpenAI Whisper", exc) from exc

            if response.status_code >= 400:
                logger.error(f"OpenAI Whisper error: status={response.status_code} body={response.text}")
                raise _status_error("OpenAI Whisper", response.status_code, response.text)

            return response.json().get("text", "")

        return call_with_retries(
            attempt,
            breaker=self.breaker,
            attempts=self.max_retries if isinstance(file, bytes | bytearray) else 1,
            deadline_seconds=self.request_timeout,
        )

    #: One deadline for a spoken line, retries included (it was 3 × 60 s).
    TTS_DEADLINE_SECONDS: ClassVar[float] = 60.0

    def text_to_speech(
        self,
        text: str,
        voice: str = "nova",
        model: str = "tts-1-hd",
    ) -> bytes:
        """Generate speech audio from text using OpenAI TTS."""
        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }

        # A spoken turn has no second chance on screen: a transient 5xx or a
        # dropped socket used to leave the learner with a silent character, so
        # retry briefly before giving up (kept short to stay inside a live call).
        def attempt(timeout: float) -> bytes:
            try:
                with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
                    response = client.post(
                        "/audio/speech",
                        json=payload,
                        headers=self._build_headers(),
                    )
            except httpx.HTTPError as exc:
                raise _transport_error("OpenAI TTS", exc) from exc
            if response.status_code >= 400:
                logger.error("OpenAI TTS error", status=response.status_code, body=response.text)
                raise _status_error("OpenAI TTS", response.status_code, response.text)
            logger.info("TTS generation success", chars=len(text), voice=voice, model=model)
            return response.content

        return call_with_retries(
            attempt,
            breaker=self.breaker,
            attempts=3,
            deadline_seconds=self.TTS_DEADLINE_SECONDS,
            backoff_base_seconds=0.6,
        )

@dataclass
class ElevenLabsProvider:
    """Generate speech audio using the ElevenLabs API."""

    api_key: str
    base_url: str = "https://api.elevenlabs.io/v1"
    request_timeout: float = 30.0

    name: str = "elevenlabs"

    def text_to_speech(
        self,
        text: str,
        voice: str = "Rachel",  # Default voice ID or name to be mapped
        model: str = "eleven_turbo_v2_5",
    ) -> bytes:
        """Generate speech audio from text."""
        # Map common names to ID if needed (for now assume voice is ID or name)
        # For simplicity, we pass voice directly. User should pass valid Voice ID.
        # Fallback to a clear default if 'nova' (OpenAI default) is passed by mistake
        if voice == "nova":
            voice = "JBFqnCBsd6RMkjVDRZzb" # Example ID (George) or Rachel: "21m00Tcm4TlvDq8ikWAM"
        
        # Determine voice ID (using a basic mapping or pass-through)
        voice_id = voice
        if voice == "Rachel":
            voice_id = "21m00Tcm4TlvDq8ikWAM"
        if voice == "Nicole":
            voice_id = "piTKgcLEGmPE4e6mEKli"  # Smooth female

        payload = {
            "text": text,
            "model_id": model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }

        with httpx.Client(base_url=self.base_url, timeout=self.request_timeout) as client:
            # Stream endpoint is /text-to-speech/{voice_id}/stream, but regular is /text-to-speech/{voice_id}
            # We use non-streaming for simplicity unless streaming is requested.
            # Using /stream is usually better for latency if client plays immediately.
            # But here we return bytes.
            response = client.post(
                f"/text-to-speech/{voice_id}",
                json=payload,
                headers=headers,
            )

        if response.status_code >= 400:
            logger.error("ElevenLabs TTS error", status=response.status_code, body=response.text)
            raise LLMProviderError(f"ElevenLabs TTS error {response.status_code}: {response.text}")

        logger.info("ElevenLabs TTS success", chars=len(text), voice=voice, model=model)
        return response.content

@dataclass
class AnthropicProvider:
    """Generate chat completions using the Anthropic API."""

    api_key: str
    model: str
    base_url: str = "https://api.anthropic.com/v1"
    request_timeout: float = 30.0
    max_retries: int = 3

    name: str = "anthropic"

    #: WP-70: one shared table (unknown models are priced conservatively, never $0).
    COST_PER_1K_TOKENS: ClassVar[dict[str, dict[str, float]]] = TEXT_PRICES_PER_1K_TOKENS

    @property
    def breaker(self) -> CircuitBreaker:
        return circuit_breaker_for(f"{self.name}@{self.base_url}")

    def generate(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        """Same policy as :meth:`OpenAIProvider.generate`."""

        disable_retries = bool(kwargs.pop("disable_retries", False))
        deadline = float(kwargs.pop("request_timeout", None) or self.request_timeout)
        return call_with_retries(
            lambda remaining: self._generate_once(messages, request_timeout=remaining, **kwargs),
            breaker=self.breaker,
            attempts=1 if disable_retries else self.max_retries,
            deadline_seconds=deadline,
        )

    def _generate_once(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 512),
            "messages": [
                {"role": message["role"], "content": message["content"]}
                for message in messages
            ],
        }
        payload["temperature"] = kwargs.get("temperature", 0.7)
        if "system" in kwargs:
            payload["system"] = kwargs["system"]
        if "response_format" in kwargs:
            payload["response_format"] = kwargs["response_format"]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        request_timeout = kwargs.get("request_timeout", self.request_timeout)
        try:
            with httpx.Client(base_url=self.base_url, timeout=request_timeout) as client:
                response = client.post("/messages", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise _transport_error("Anthropic", exc) from exc

        if response.status_code >= 400:
            logger.error("Anthropic returned error", status=response.status_code, body=response.text)
            raise _status_error("Anthropic", response.status_code, response.text)

        data = response.json()
        contents = data.get("content", [])
        content_chunks = [chunk.get("text", "") for chunk in contents if chunk.get("type") == "text"]
        content = "\n".join(filter(None, content_chunks)).strip()
        if not content:
            raise LLMProviderError("Anthropic response did not include content")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        cost = estimate_text_cost_usd(payload["model"], prompt_tokens, completion_tokens)

        result = LLMResult(
            provider=self.name,
            model=payload["model"],
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            raw_response=data,
        )
        logger.info(
            "Anthropic completion success",
            model=result.model,
            tokens=result.total_tokens,
            cost=result.cost,
        )
        return result


class LLMService:
    """Coordinate chat completion requests across providers."""

    def __init__(
        self,
        providers: Sequence[BaseLLMProvider] | None = None,
        primary: str | None = None,
        secondary: str | None = None,
    ) -> None:
        if providers is not None:
            self._providers = list(providers)
        else:
            self._providers = self._build_default_providers()
        if not self._providers:
            raise ValueError("LLMService requires at least one provider")

        self._providers_by_name = {provider.name: provider for provider in self._providers}
        resolved_primary = primary or settings.PRIMARY_LLM_PROVIDER
        resolved_secondary = secondary or settings.SECONDARY_LLM_PROVIDER
        self._provider_order = self._build_order(resolved_primary, resolved_secondary)

    def _build_default_providers(self) -> list[BaseLLMProvider]:
        provider_list: list[BaseLLMProvider] = []
        if settings.OPENAI_API_KEY:
            provider_list.append(
                OpenAIProvider(
                    api_key=settings.OPENAI_API_KEY,
                    model=settings.OPENAI_MODEL,
                    base_url=settings.OPENAI_API_BASE or "https://api.openai.com/v1",
                    request_timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
                    max_retries=settings.LLM_MAX_RETRIES,
                )
            )
        if settings.ANTHROPIC_API_KEY:
            provider_list.append(
                AnthropicProvider(
                    api_key=settings.ANTHROPIC_API_KEY,
                    model=settings.ANTHROPIC_MODEL,
                    base_url=settings.ANTHROPIC_API_BASE or "https://api.anthropic.com/v1",
                    request_timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
                    max_retries=settings.LLM_MAX_RETRIES,
                )
            )

        if settings.ELEVENLABS_API_KEY:
            provider_list.append(
                ElevenLabsProvider(
                    api_key=settings.ELEVENLABS_API_KEY,
                )
            )
        return provider_list

    def _build_order(self, primary: str | None, secondary: str | None) -> list[BaseLLMProvider]:
        ordered: list[BaseLLMProvider] = []
        seen: set[str] = set()

        def maybe_add(name: str | None) -> None:
            if not name:
                return
            provider = self._providers_by_name.get(name)
            if provider and provider.name not in seen:
                ordered.append(provider)
                seen.add(provider.name)

        maybe_add(primary)
        maybe_add(secondary)
        for provider in self._providers:
            if provider.name in seen:
                continue
            ordered.append(provider)
        return ordered

    def generate_chat_completion(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        request_timeout: float | None = None,
        disable_retries: bool = False,
        reasoning_effort: str | None = None,
        max_provider_attempts: int | None = None,
    ) -> LLMResult:
        """Generate a chat completion using the configured providers."""

        errors: list[str] = []
        providers = self._provider_order if max_provider_attempts is None else self._provider_order[:max(1, max_provider_attempts)]
        for provider in providers:
            if not hasattr(provider, "generate"):
                continue
            payload_kwargs: dict[str, Any] = {
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            # Only OpenAI chat supports response_format in our usage
            if response_format and provider.name == "openai":
                payload_kwargs["response_format"] = response_format
            if model and provider.name == "openai":
                payload_kwargs["model"] = model
            elif model:
                payload_kwargs["model"] = model
            if request_timeout is not None:
                payload_kwargs["request_timeout"] = request_timeout
            if disable_retries:
                payload_kwargs["disable_retries"] = True
            if reasoning_effort:
                payload_kwargs["reasoning_effort"] = reasoning_effort
            if system_prompt and provider.name == "anthropic":
                payload_kwargs["system"] = system_prompt
            provider_messages = messages
            if system_prompt and provider.name == "openai":
                provider_messages = [{"role": "system", "content": system_prompt}, *messages]
            try:
                result = provider.generate(provider_messages, **payload_kwargs)
                logger.debug(
                    "LLM provider success",
                    provider=provider.name,
                    tokens=result.total_tokens,
                    cost=result.cost,
                )
                return result
            except Exception as exc:  # pragma: no cover - defensive logging path
                logger.warning(
                    "LLM provider failure ({}): {}", provider.name, str(exc)[:300]
                )
                errors.append(f"{provider.name}: {exc}")
                continue
        raise LLMProviderError("; ".join(errors))

    def generate_error_detection(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        request_timeout: float | None = None,
        disable_retries: bool = False,
        reasoning_effort: str | None = None,
    ) -> LLMResult:
        """Generate error detection using the dedicated error detection model.
        
        Uses the configured correction model for better grammar analysis.
        """
        errors: list[str] = []
        for provider in self._provider_order:
            if not hasattr(provider, "generate"):
                continue
            payload_kwargs: dict[str, Any] = {
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            # Use the error detection model if available for OpenAI
            if provider.name == "openai":
                payload_kwargs["model"] = model or settings.OPENAI_ERROR_DETECTION_MODEL
                if response_format:
                    payload_kwargs["response_format"] = response_format
                # gpt-5 class models bill reasoning against the completion
                # ceiling: with no effort set they burned the whole budget and
                # returned empty content, so every detection call raised and the
                # spoken session silently reported zero mistakes.
                if not reasoning_effort and OpenAIProvider._uses_completion_token_limit(
                    str(payload_kwargs["model"])
                ):
                    payload_kwargs["reasoning_effort"] = "minimal"
            elif model:
                payload_kwargs["model"] = model
            if request_timeout is not None:
                payload_kwargs["request_timeout"] = request_timeout
            if disable_retries:
                payload_kwargs["disable_retries"] = True
            if reasoning_effort:
                payload_kwargs["reasoning_effort"] = reasoning_effort
            
            if system_prompt and provider.name == "anthropic":
                payload_kwargs["system"] = system_prompt
            
            provider_messages = messages
            if system_prompt and provider.name == "openai":
                provider_messages = [{"role": "system", "content": system_prompt}, *messages]
            
            try:
                result = provider.generate(provider_messages, **payload_kwargs)
                logger.debug(
                    "Error detection LLM success",
                    provider=provider.name,
                    model=result.model,
                    tokens=result.total_tokens,
                    cost=result.cost,
                )
                return result
            except Exception as exc:
                logger.warning("Error detection LLM failure", provider=provider.name, error=str(exc))
                errors.append(f"{provider.name}: {exc}")
                continue
        raise LLMProviderError("; ".join(errors))

    def transcribe_audio(
        self,
        file: Any,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Transcribe audio using the primary provider (must be OpenAI)."""
        # Find OpenAI provider
        openai_provider = next((p for p in self._providers if isinstance(p, OpenAIProvider)), None)
        if not openai_provider:
            raise LLMProviderError("OpenAI provider not configured for transcription")
        
        return openai_provider.transcribe_audio(
            file,
            filename=filename,
            content_type=content_type,
        )

    def text_to_speech(
        self,
        text: str,
        voice: str = "nova",
        model: str | None = None,
        provider: str | None = None,
    ) -> bytes:
        """Generate speech audio from text using configured provider."""
        target_provider = provider or settings.TTS_PROVIDER
        
        if target_provider == "elevenlabs":
            el_provider = next((p for p in self._providers if isinstance(p, ElevenLabsProvider)), None)
            if not el_provider:
                logger.warning("ElevenLabs provider requested but not configured, falling back to OpenAI")
                target_provider = "openai"
            else:
                # Default ElevenLabs model
                model = model or "eleven_turbo_v2_5"
                # Map OpenAI voice names to ElevenLabs if necessary
                el_voice = "Rachel" if voice in [
                    "alloy", "echo", "fable", "nova", "onyx", "shimmer"
                ] else voice
                try:
                    return el_provider.text_to_speech(text, voice=el_voice, model=model)
                except Exception as exc:
                    # A spoken session is worthless without a voice: an ElevenLabs
                    # outage or plan limit must degrade to the other provider
                    # instead of 500ing the whole turn.
                    logger.warning("ElevenLabs TTS failed, falling back to OpenAI: {}", exc)
                    target_provider = "openai"
                    model = None

        if target_provider == "openai":
            openai_provider = next((p for p in self._providers if isinstance(p, OpenAIProvider)), None)
            if not openai_provider:
                raise LLMProviderError("OpenAI provider not configured for TTS")
            
            model = model or "tts-1-hd"
            return openai_provider.text_to_speech(text, voice=voice, model=model)

        raise LLMProviderError(f"Unsupported TTS provider: {target_provider}")


__all__ = [
    "CircuitBreaker",
    "IMAGE_PRICES_PER_IMAGE",
    "LLMProviderError",
    "LLMResult",
    "LLMService",
    "ProviderCircuitOpenError",
    "TEXT_PRICES_PER_1K_TOKENS",
    "TRANSCRIPTION_PRICES_PER_MINUTE",
    "TTS_PRICES_PER_1K_CHARS",
    "call_with_retries",
    "circuit_breaker_for",
    "conservative_text_price",
    "estimate_image_cost_usd",
    "estimate_text_cost_usd",
    "estimate_tts_cost_usd",
    "reset_circuit_breakers",
    "text_price_for",
]
