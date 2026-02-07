"""LLM service with provider fallback and cost tracking."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional, Protocol, Sequence

import httpx
from loguru import logger
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from app.config import settings


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
    raw_response: Dict[str, Any]


class LLMProviderError(RuntimeError):
    """Raised when a provider returns an error response."""


class BaseLLMProvider(Protocol):
    """Protocol shared by provider implementations."""

    name: str

    def generate(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> LLMResult:  # pragma: no cover - interface definition
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

    COST_PER_1K_TOKENS: ClassVar[Dict[str, Dict[str, float]]] = {
        "gpt-4o-mini": {"prompt": 0.0006, "completion": 0.0024},
        "gpt-4o": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    }

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Optionally set organization header when supplied
        if settings and getattr(settings, "OPENAI_ORG_ID", None):  # type: ignore[truthy-bool]
            headers["OpenAI-Organization"] = settings.OPENAI_ORG_ID  # type: ignore[attr-defined]
        return headers

    def _estimate_cost(self, usage: Dict[str, Any]) -> float:
        model_rates = self.COST_PER_1K_TOKENS.get(self.model, {"prompt": 0.0, "completion": 0.0})
        prompt_cost = (usage.get("prompt_tokens", 0) / 1000) * model_rates["prompt"]
        completion_cost = (usage.get("completion_tokens", 0) / 1000) * model_rates["completion"]
        return round(prompt_cost + completion_cost, 6)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def generate(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> LLMResult:
        payload: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": list(messages),
            "temperature": kwargs.get("temperature", 0.7),
        }
        if "response_format" in kwargs:
            payload["response_format"] = kwargs["response_format"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        with httpx.Client(base_url=self.base_url, timeout=self.request_timeout) as client:
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
            cost=self._estimate_cost(usage),
            raw_response=data,
        )
        logger.info(
            "OpenAI completion success",
            model=result.model,
            tokens=result.total_tokens,
            cost=result.cost,
        )
        return result

    def transcribe_audio(self, file: Any) -> str:
        """Transcribe audio using OpenAI Whisper."""
        with httpx.Client(base_url=self.base_url, timeout=self.request_timeout) as client:
            files = {"file": ("audio.webm", file, "audio/webm")}
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
        with httpx.Client(base_url=self.base_url, timeout=60.0) as client:
            response = client.post(
                "/audio/speech",
                json=payload,
                headers=self._build_headers(),
            )

        if response.status_code >= 400:
            logger.error("OpenAI TTS error", status=response.status_code, body=response.text)
            raise LLMProviderError(f"OpenAI TTS error {response.status_code}: {response.text}")

        logger.info("TTS generation success", chars=len(text), voice=voice, model=model)
        return response.content

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
        if voice == "Rachel": voice_id = "21m00Tcm4TlvDq8ikWAM"
        if voice == "Nicole": voice_id = "piTKgcLEGmPE4e6mEKli" # Smooth female

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

    COST_PER_1K_TOKENS: ClassVar[Dict[str, Dict[str, float]]] = {
        "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def generate(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> LLMResult:
        payload: Dict[str, Any] = {
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

        with httpx.Client(base_url=self.base_url, timeout=self.request_timeout) as client:
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
        providers: Optional[Sequence[BaseLLMProvider]] = None,
        primary: Optional[str] = None,
        secondary: Optional[str] = None,
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

    def _build_default_providers(self) -> List[BaseLLMProvider]:
        provider_list: List[BaseLLMProvider] = []
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

    def _build_order(self, primary: Optional[str], secondary: Optional[str]) -> List[BaseLLMProvider]:
        ordered: List[BaseLLMProvider] = []
        seen: set[str] = set()

        def maybe_add(name: Optional[str]) -> None:
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
        messages: Sequence[Dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        response_format: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResult:
        """Generate a chat completion using the configured providers."""

        errors: List[str] = []
        for provider in self._provider_order:
            payload_kwargs: Dict[str, Any] = {
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            # Only OpenAI chat supports response_format in our usage
            if response_format and provider.name == "openai":
                payload_kwargs["response_format"] = response_format
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
                logger.exception("LLM provider failure", provider=provider.name)
                errors.append(f"{provider.name}: {exc}")
                continue
        raise LLMProviderError("; ".join(errors))

    def generate_error_detection(
        self,
        messages: Sequence[Dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
        response_format: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResult:
        """Generate error detection using the dedicated error detection model.
        
        Uses a stronger model (gpt-4o by default) for better grammar analysis.
        """
        errors: List[str] = []
        for provider in self._provider_order:
            payload_kwargs: Dict[str, Any] = {
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            # Use the error detection model if available for OpenAI
            if provider.name == "openai":
                payload_kwargs["model"] = settings.OPENAI_ERROR_DETECTION_MODEL
                if response_format:
                    payload_kwargs["response_format"] = response_format
            
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
                logger.exception("Error detection LLM failure", provider=provider.name)
                errors.append(f"{provider.name}: {exc}")
                continue
        raise LLMProviderError("; ".join(errors))

    def transcribe_audio(self, file: Any) -> str:
        """Transcribe audio using the primary provider (must be OpenAI)."""
        # Find OpenAI provider
        openai_provider = next((p for p in self._providers if isinstance(p, OpenAIProvider)), None)
        if not openai_provider:
            raise LLMProviderError("OpenAI provider not configured for transcription")
        
        return openai_provider.transcribe_audio(file)

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
                if voice in ["alloy", "echo", "fable", "nova", "onyx", "shimmer"]:
                    voice = "Rachel" # Fallback to default EL voice
                return el_provider.text_to_speech(text, voice=voice, model=model)

        if target_provider == "openai":
            openai_provider = next((p for p in self._providers if isinstance(p, OpenAIProvider)), None)
            if not openai_provider:
                raise LLMProviderError("OpenAI provider not configured for TTS")
            
            model = model or "tts-1-hd"
            return openai_provider.text_to_speech(text, voice=voice, model=model)

        raise LLMProviderError(f"Unsupported TTS provider: {target_provider}")


__all__ = ["LLMService", "LLMResult", "LLMProviderError"]
