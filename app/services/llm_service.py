"""LLM service with provider fallback and cost tracking."""
from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

import httpx
from loguru import logger
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from app.config import settings

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
    """Raised when a provider returns an error response."""


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

    COST_PER_1K_TOKENS: ClassVar[dict[str, dict[str, float]]] = {
        "gpt-5-mini": {"prompt": 0.00025, "completion": 0.002},
        "gpt-5.4-mini": {"prompt": 0.00075, "completion": 0.0045},
        "gpt-5.4-nano": {"prompt": 0.0002, "completion": 0.00125},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    }

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
        model_rates = self.COST_PER_1K_TOKENS.get(model or self.model, {"prompt": 0.0, "completion": 0.0})
        prompt_cost = (usage.get("prompt_tokens", 0) / 1000) * model_rates["prompt"]
        completion_cost = (usage.get("completion_tokens", 0) / 1000) * model_rates["completion"]
        return round(prompt_cost + completion_cost, 6)

    @staticmethod
    def _uses_completion_token_limit(model: str) -> bool:
        """Newer OpenAI reasoning models reject the legacy max_tokens field."""

        return model.startswith("gpt-5")

    def generate(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        disable_retries = bool(kwargs.pop("disable_retries", False))
        if disable_retries:
            return self._generate_once(messages, **kwargs)
        return self._generate_with_retries(messages, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _generate_with_retries(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        return self._generate_once(messages, **kwargs)

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
        with httpx.Client(base_url=self.base_url, timeout=request_timeout) as client:
            response = client.post("/chat/completions", json=payload, headers=self._build_headers())

        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                error_msg = response.text

            # Escape braces to prevent log format errors
            safe_error_msg = str(error_msg).replace("{", "{{").replace("}", "}}")
            
            logger.error("OpenAI returned error", status=response.status_code, body=safe_error_msg)
            raise LLMProviderError(f"OpenAI error {response.status_code}: {safe_error_msg}")

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
        """Transcribe audio using OpenAI Whisper."""
        upload_filename, upload_content_type = _audio_upload_metadata(filename, content_type)
        with httpx.Client(base_url=self.base_url, timeout=self.request_timeout) as client:
            files = {"file": (upload_filename, file, upload_content_type)}
            data = {"model": "whisper-1"}
            response = client.post("/audio/transcriptions", files=files, data=data, headers={"Authorization": f"Bearer {self.api_key}"})

        if response.status_code >= 400:
            logger.error(f"OpenAI Whisper error: status={response.status_code} body={response.text}")
            raise LLMProviderError(f"OpenAI Whisper error {response.status_code}: {response.text}")

        return response.json().get("text", "")

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
        attempts = 3
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(base_url=self.base_url, timeout=60.0) as client:
                    response = client.post(
                        "/audio/speech",
                        json=payload,
                        headers=self._build_headers(),
                    )
            except httpx.HTTPError as exc:
                last_error = LLMProviderError(f"OpenAI TTS transport error: {exc}")
            else:
                if response.status_code < 400:
                    logger.info("TTS generation success", chars=len(text), voice=voice, model=model)
                    return response.content
                logger.error("OpenAI TTS error", status=response.status_code, body=response.text)
                last_error = LLMProviderError(
                    f"OpenAI TTS error {response.status_code}: {response.text}"
                )
                if response.status_code < 500:
                    break
            if attempt < attempts:
                time.sleep(0.6 * attempt)

        raise last_error or LLMProviderError("OpenAI TTS error")

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

    name: str = "anthropic"

    COST_PER_1K_TOKENS: ClassVar[dict[str, dict[str, float]]] = {
        "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    }

    def generate(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        disable_retries = bool(kwargs.pop("disable_retries", False))
        if disable_retries:
            return self._generate_once(messages, **kwargs)
        return self._generate_with_retries(messages, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _generate_with_retries(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> LLMResult:
        return self._generate_once(messages, **kwargs)

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
        with httpx.Client(base_url=self.base_url, timeout=request_timeout) as client:
            response = client.post("/messages", json=payload, headers=headers)

        if response.status_code >= 400:
            logger.error("Anthropic returned error", status=response.status_code, body=response.text)
            raise LLMProviderError(f"Anthropic error {response.status_code}: {response.text}")

        data = response.json()
        contents = data.get("content", [])
        content_chunks = [chunk.get("text", "") for chunk in contents if chunk.get("type") == "text"]
        content = "\n".join(filter(None, content_chunks)).strip()
        if not content:
            raise LLMProviderError("Anthropic response did not include content")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        cost_info = self.COST_PER_1K_TOKENS.get(payload["model"], {"prompt": 0.0, "completion": 0.0})
        cost = round((prompt_tokens / 1000) * cost_info["prompt"] + (completion_tokens / 1000) * cost_info["completion"], 6)

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
                logger.warning("LLM provider failure", provider=provider.name, error=str(exc))
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


__all__ = ["LLMService", "LLMResult", "LLMProviderError"]
