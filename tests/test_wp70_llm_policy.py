"""WP-70 — the LLM wrapper: retry only what a retry can fix, under one deadline,
behind a circuit breaker, and never bill a priced call at $0."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any

import httpx
import pytest

from app.config import settings
from app.services import llm_service
from app.services.llm_service import (
    TEXT_PRICES_PER_1K_TOKENS,
    AnthropicProvider,
    LLMProviderError,
    LLMService,
    OpenAIProvider,
    ProviderCircuitOpenError,
    call_with_retries,
    circuit_breaker_for,
    conservative_text_price,
    estimate_image_cost_usd,
    estimate_text_cost_usd,
    estimate_tts_cost_usd,
    reset_circuit_breakers,
    text_price_for,
)


class _Clock:
    """A monotonic clock the test moves by hand; sleeping advances it."""

    def __init__(self) -> None:
        self.now = 1_000.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture(autouse=True)
def _fresh_breakers() -> Generator[None, None, None]:
    reset_circuit_breakers()
    yield
    reset_circuit_breakers()


@pytest.fixture()
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(llm_service.time, "monotonic", fake.monotonic)
    monkeypatch.setattr(llm_service.time, "sleep", fake.sleep)
    return fake


class _Response:
    def __init__(self, status_code: int, body: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._body = body or {}
        self.text = str(self._body)
        self.content = b"audio"

    def json(self) -> dict[str, Any]:
        return self._body


def _completion(model: str) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": "Bonjour"}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        "model": model,
    }


def _scripted_client(monkeypatch, script: list[Any], clock: _Clock | None = None, spend: float = 0.1):  # type: ignore[no-untyped-def]
    """Patch ``httpx.Client`` to play ``script`` (responses or exceptions) in order."""

    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.timeout = kwargs.get("timeout")

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, path: str, **kwargs: Any) -> _Response:
            calls.append({"path": path, "timeout": self.timeout})
            step = script[min(len(calls), len(script)) - 1]
            if clock is not None:
                # A timeout burns the whole attempt; anything else is quick.
                clock.now += self.timeout if isinstance(step, httpx.TimeoutException) else spend
            if isinstance(step, Exception):
                raise step
            return step

    monkeypatch.setattr(llm_service.httpx, "Client", FakeClient)
    return calls


def _provider(**kwargs: Any) -> OpenAIProvider:
    return OpenAIProvider(api_key="test-key", model="gpt-5-mini", base_url=f"https://wp70.invalid/{id(kwargs)}", **kwargs)


# ---------------------------------------------------------------------------
# which errors are retried
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_a_4xx_is_never_retried(monkeypatch, clock, status_code: int) -> None:
    calls = _scripted_client(monkeypatch, [_Response(status_code, {"error": {"message": "no"}})], clock)
    with pytest.raises(LLMProviderError) as error:
        _provider(max_retries=3).generate([{"role": "user", "content": "x"}])
    assert len(calls) == 1
    assert error.value.retryable is False
    assert error.value.status_code == status_code
    assert clock.slept == []


@pytest.mark.parametrize(
    "failure",
    [
        _Response(429, {"error": {"message": "slow down"}}),
        _Response(500, {"error": {"message": "oops"}}),
        _Response(503, {"error": {"message": "overloaded"}}),
        httpx.ConnectError("refused"),
        httpx.ReadError("reset"),
    ],
)
def test_retryable_failures_are_retried_then_succeed(monkeypatch, clock, failure) -> None:  # type: ignore[no-untyped-def]
    calls = _scripted_client(monkeypatch, [failure, _Response(200, _completion("gpt-5-mini"))], clock)
    result = _provider(max_retries=3).generate([{"role": "user", "content": "x"}])
    assert result.content == "Bonjour"
    assert len(calls) == 2
    assert clock.slept == [1.0]


def test_empty_content_is_not_retried(monkeypatch, clock) -> None:
    """Token starvation is deterministic: a second attempt only pays twice."""

    calls = _scripted_client(monkeypatch, [_Response(200, {"choices": [{"message": {"content": ""}}]})], clock)
    with pytest.raises(LLMProviderError):
        _provider(max_retries=3).generate([{"role": "user", "content": "x"}])
    assert len(calls) == 1


def test_llm_max_retries_is_read(monkeypatch, clock) -> None:
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)
    service = LLMService()
    openai = next(p for p in service._providers if isinstance(p, OpenAIProvider))
    anthropic = next(p for p in service._providers if isinstance(p, AnthropicProvider))
    assert openai.max_retries == 2
    assert anthropic.max_retries == 2

    calls = _scripted_client(monkeypatch, [_Response(502)], clock)
    with pytest.raises(LLMProviderError):
        openai.generate([{"role": "user", "content": "x"}])
    assert len(calls) == 2


def test_disable_retries_means_one_attempt(monkeypatch, clock) -> None:
    calls = _scripted_client(monkeypatch, [_Response(500)], clock)
    with pytest.raises(LLMProviderError):
        _provider(max_retries=5).generate([{"role": "user", "content": "x"}], disable_retries=True)
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# one deadline across attempts
# ---------------------------------------------------------------------------


def test_a_timed_out_attempt_spends_the_whole_deadline(monkeypatch, clock) -> None:
    """The old policy could wait 3 × 90 s; the deadline is now the call's, not the attempt's."""

    calls = _scripted_client(monkeypatch, [httpx.ReadTimeout("stalled")], clock)
    started = clock.now
    with pytest.raises(LLMProviderError) as error:
        _provider(max_retries=3, request_timeout=90.0).generate([{"role": "user", "content": "x"}])
    assert error.value.retryable is True
    assert len(calls) == 1
    assert clock.now - started <= 90.0 + 1e-6


def test_every_attempt_gets_only_what_is_left(monkeypatch, clock) -> None:
    calls = _scripted_client(
        monkeypatch, [_Response(503), _Response(503), _Response(200, _completion("gpt-5-mini"))], clock, spend=5.0
    )
    started = clock.now
    _provider(max_retries=3).generate([{"role": "user", "content": "x"}], request_timeout=30.0)
    timeouts = [call["timeout"] for call in calls]
    assert timeouts[0] == pytest.approx(30.0)
    assert timeouts[1] == pytest.approx(30.0 - 5.0 - 1.0)
    assert timeouts[2] == pytest.approx(30.0 - 5.0 - 1.0 - 5.0 - 2.0)
    assert clock.now - started <= 30.0


def test_no_retry_is_started_that_cannot_finish(monkeypatch, clock) -> None:
    calls = _scripted_client(monkeypatch, [_Response(500)], clock, spend=9.5)
    with pytest.raises(LLMProviderError):
        _provider(max_retries=5).generate([{"role": "user", "content": "x"}], request_timeout=10.0)
    assert len(calls) == 1  # 9.5 s spent + a 1 s back-off would leave nothing to run in


def test_speech_has_one_60_second_deadline_not_three(monkeypatch, clock) -> None:
    calls = _scripted_client(monkeypatch, [httpx.ReadTimeout("stalled")], clock)
    started = clock.now
    with pytest.raises(LLMProviderError):
        _provider().text_to_speech("Bonjour")
    assert len(calls) == 1
    assert clock.now - started <= 60.0 + 1e-6


def test_speech_retries_a_5xx_but_not_a_4xx(monkeypatch, clock) -> None:
    calls = _scripted_client(monkeypatch, [_Response(502), _Response(200)], clock)
    assert _provider().text_to_speech("Bonjour") == b"audio"
    assert len(calls) == 2

    calls = _scripted_client(monkeypatch, [_Response(400), _Response(200)], clock)
    with pytest.raises(LLMProviderError):
        _provider().text_to_speech("Bonjour")
    assert len(calls) == 1


def test_transcription_retries_bytes_only(monkeypatch, clock) -> None:
    calls = _scripted_client(monkeypatch, [_Response(503), _Response(200, {"text": "salut"})], clock)
    assert _provider(max_retries=3).transcribe_audio(b"audio", content_type="audio/webm") == "salut"
    assert len(calls) == 2

    class Stream:
        def read(self) -> bytes:  # pragma: no cover - never read by the fake client
            return b""

    calls = _scripted_client(monkeypatch, [_Response(503), _Response(200, {"text": "salut"})], clock)
    with pytest.raises(LLMProviderError):
        _provider(max_retries=3).transcribe_audio(Stream(), content_type="audio/webm")
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# the circuit breaker
# ---------------------------------------------------------------------------


def test_the_breaker_opens_after_consecutive_failures_and_recovers(monkeypatch, clock) -> None:
    monkeypatch.setattr(settings, "LLM_CIRCUIT_BREAKER_THRESHOLD", 2, raising=False)
    monkeypatch.setattr(settings, "LLM_CIRCUIT_BREAKER_OPEN_SECONDS", 60.0, raising=False)
    provider = _provider(max_retries=1)
    calls = _scripted_client(monkeypatch, [_Response(500)], clock)
    for _ in range(2):
        with pytest.raises(LLMProviderError):
            provider.generate([{"role": "user", "content": "x"}])
    assert len(calls) == 2

    with pytest.raises(ProviderCircuitOpenError):
        provider.generate([{"role": "user", "content": "x"}])
    assert len(calls) == 2, "an open circuit must not reach the provider"

    clock.now += 61
    calls = _scripted_client(monkeypatch, [_Response(200, _completion("gpt-5-mini"))], clock)
    assert provider.generate([{"role": "user", "content": "x"}]).content == "Bonjour"
    assert not provider.breaker.is_open


def test_a_4xx_resets_the_failure_count(monkeypatch, clock) -> None:
    monkeypatch.setattr(settings, "LLM_CIRCUIT_BREAKER_THRESHOLD", 2, raising=False)
    provider = _provider(max_retries=1)
    _scripted_client(monkeypatch, [_Response(500), _Response(400), _Response(500)], clock)
    for _ in range(3):
        with pytest.raises(LLMProviderError):
            provider.generate([{"role": "user", "content": "x"}])
    assert not provider.breaker.is_open


def test_an_open_openai_circuit_falls_back_to_the_next_provider(monkeypatch) -> None:
    class Secondary:
        name = "anthropic"

        def generate(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            return llm_service.LLMResult("anthropic", "claude-3-5-sonnet", "Salut", 1, 1, 2, 0.01, {})

    primary = _provider()
    breaker = primary.breaker
    monkeypatch.setattr(settings, "LLM_CIRCUIT_BREAKER_THRESHOLD", 1, raising=False)
    breaker.record_failure()
    assert breaker.is_open
    service = LLMService(providers=[primary, Secondary()], primary="openai", secondary="anthropic")
    assert service.generate_chat_completion([{"role": "user", "content": "x"}]).content == "Salut"


def test_call_with_retries_does_not_touch_non_provider_errors(clock) -> None:
    breaker = circuit_breaker_for("wp70-direct")
    attempts: list[float] = []

    def attempt(timeout: float) -> None:
        attempts.append(timeout)
        raise ValueError("a bug, not an outage")

    with pytest.raises(ValueError):
        call_with_retries(attempt, breaker=breaker, attempts=3, deadline_seconds=10)
    assert len(attempts) == 1


# ---------------------------------------------------------------------------
# prices: nothing priced is ever $0
# ---------------------------------------------------------------------------


def _configured_text_models() -> set[str]:
    names = {
        "OPENAI_MODEL",
        "OPENAI_ERROR_DETECTION_MODEL",
        "OPENAI_MISSION_FAST_MODEL",
        "ATELIER_EXERCISE_LLM_MODEL",
        "ATELIER_CRITIQUE_LLM_MODEL",
        "ATELIER_CORRECTION_LLM_MODEL",
        "OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL",
        "OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL",
        "ATELIER_INTAKE_VISION_MODEL",
        "ATELIER_INTAKE_TEXT_MODEL",
        "ANTHROPIC_MODEL",
    }
    # render.yaml / .env.example select these in production.
    return {str(getattr(settings, name)) for name in names} | {"gpt-5.4-mini", "gpt-5.5", "gpt-5", "gpt-5-nano"}


@pytest.mark.parametrize("model", sorted(_configured_text_models()))
def test_every_configured_text_model_is_priced(model: str) -> None:
    assert estimate_text_cost_usd(model, 1000, 1000) > 0


def test_a_priced_call_never_records_zero(monkeypatch, clock) -> None:
    for model in sorted(_configured_text_models()):
        if model.startswith("claude"):
            continue
        _scripted_client(monkeypatch, [_Response(200, _completion(model))], clock)
        result = _provider().generate([{"role": "user", "content": "x"}], model=model)
        assert result.cost > 0, model


def test_an_unknown_model_is_billed_at_the_highest_known_rate_and_logged_once(monkeypatch) -> None:
    warnings: list[str] = []

    class _Logger:
        def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
            warnings.append(message)

    monkeypatch.setattr(llm_service, "logger", _Logger())
    rates, known = text_price_for("gpt-9-ultra")
    text_price_for("gpt-9-ultra")
    assert known is False
    assert rates == conservative_text_price()
    assert rates["prompt"] >= max(r["prompt"] for r in TEXT_PRICES_PER_1K_TOKENS.values())
    assert rates["completion"] >= max(r["completion"] for r in TEXT_PRICES_PER_1K_TOKENS.values())
    assert len(warnings) == 1


def test_snapshots_price_as_their_family_but_a_new_version_does_not() -> None:
    assert text_price_for("gpt-4o-mini-2024-07-18") == (TEXT_PRICES_PER_1K_TOKENS["gpt-4o-mini"], True)
    assert text_price_for("claude-3-5-sonnet-20241022")[1] is True
    # gpt-5.5 is not gpt-5: it has no documented price, so it is billed conservatively.
    assert text_price_for("gpt-5.5") == (conservative_text_price(), False)


def test_speech_transcription_and_images_are_priced() -> None:
    assert estimate_tts_cost_usd("tts-1-hd", 1000) == pytest.approx(0.03)
    assert estimate_tts_cost_usd("tts-1", 1000) == pytest.approx(0.015)
    assert estimate_tts_cost_usd("eleven_turbo_v2_5", 1000) > 0
    assert estimate_image_cost_usd("gpt-image-2.5-flare") == pytest.approx(
        float(settings.GRAPHIC_NOVEL_IMAGE_COST_USD_PER_PANEL)
    )
    assert estimate_image_cost_usd("dall-e-3") == pytest.approx(0.04)
    assert estimate_image_cost_usd("some-new-image-model") > 0
    assert llm_service.TRANSCRIPTION_PRICES_PER_MINUTE["whisper-1"] > 0
