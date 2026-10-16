"""Story models per step (plan decisions 9 and 10): the providers speak to the
Claude 5 and gpt-6 families correctly, and the story engine names a model only
where a setting asks for one."""
from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.services import living_story, llm_service
from app.services.llm_service import (
    ANTHROPIC_JSON_INSTRUCTION,
    ANTHROPIC_MIN_MAX_TOKENS,
    AnthropicProvider,
    LLMProviderError,
    LLMResult,
    OpenAIProvider,
    estimate_text_cost_usd,
    reset_circuit_breakers,
    text_price_for,
)


@pytest.fixture(autouse=True)
def _fresh_breakers():
    reset_circuit_breakers()
    yield
    reset_circuit_breakers()


class _Response:
    def __init__(self, body: dict[str, Any], status_code: int = 200) -> None:
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self) -> dict[str, Any]:
        return self._body


def _capture(monkeypatch, body: dict[str, Any]) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, path: str, **kwargs: Any) -> _Response:
            sent.append(kwargs["json"])
            return _Response(body)

    monkeypatch.setattr(llm_service.httpx, "Client", FakeClient)
    return sent


def _claude(text: str, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": text},
        ],
        "stop_reason": stop_reason,
        "usage": {"input_tokens": 2000, "output_tokens": 1000},
    }


def _anthropic() -> AnthropicProvider:
    return AnthropicProvider(api_key="k", model="claude-haiku-5-5", base_url="https://story-models.invalid/a")


def test_every_story_model_is_priced() -> None:
    for model in ("claude-haiku-5-5", "claude-sonnet-5-5", "gpt-6-luna", "gpt-6.1-sol", "gpt-5.5"):
        _rates, known = text_price_for(model)
        assert known, model
    # Haiku 5.5: $0.10 in and $0.50 out per 1M tokens.
    assert estimate_text_cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.6)


def test_a_claude_call_sends_effort_and_json_and_no_temperature(monkeypatch) -> None:
    sent = _capture(monkeypatch, _claude('```json\n{"title_fr": "Le quai"}\n```'))
    result = _anthropic().generate(
        [{"role": "user", "content": "Écris la page."}],
        system="Director.",
        temperature=0.55,
        max_tokens=5000,
        response_format={"type": "json_object"},
        reasoning_effort="minimal",
    )
    payload = sent[0]
    assert "temperature" not in payload
    assert payload["max_tokens"] == ANTHROPIC_MIN_MAX_TOKENS
    assert payload["output_config"] == {"effort": "low"}
    assert payload["system"] == f"Director.\n\n{ANTHROPIC_JSON_INSTRUCTION}"
    assert "response_format" not in payload
    # The thinking block is skipped and the fence around the JSON is dropped.
    assert result.content == '{"title_fr": "Le quai"}'
    assert result.cost == pytest.approx(estimate_text_cost_usd("claude-haiku-5-5", 2000, 1000))
    assert result.cost > 0


def test_a_claude_effort_is_passed_through_and_an_unknown_one_dropped(monkeypatch) -> None:
    sent = _capture(monkeypatch, _claude("Bonjour"))
    _anthropic().generate([{"role": "user", "content": "x"}], reasoning_effort="high")
    _anthropic().generate([{"role": "user", "content": "x"}], reasoning_effort="adaptive")
    assert sent[0]["output_config"] == {"effort": "high"}
    assert "output_config" not in sent[1]


def test_a_claude_refusal_is_an_error_not_an_answer(monkeypatch) -> None:
    _capture(monkeypatch, {"content": [], "stop_reason": "refusal", "usage": {}})
    with pytest.raises(LLMProviderError, match="refusal"):
        _anthropic().generate([{"role": "user", "content": "x"}])


def test_a_claude_answer_cut_off_reads_as_truncated() -> None:
    result = LLMResult(
        provider="anthropic",
        model="claude-haiku-5-5",
        content='{"title_fr": "Le q',
        prompt_tokens=1,
        completion_tokens=16000,
        total_tokens=16001,
        cost=0.0,
        raw_response=_claude('{"title_fr": "Le q', stop_reason="max_tokens") | {"usage": {"output_tokens": 16000}},
    )
    details = living_story._finish_details(result)
    assert details["finish_reason"] == "length"
    assert details["completion_tokens"] == 16000


def test_a_gpt6_model_gets_none_for_minimal_and_no_temperature(monkeypatch) -> None:
    sent = _capture(
        monkeypatch,
        {"choices": [{"message": {"content": "Bonjour"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    )
    provider = OpenAIProvider(api_key="k", model="gpt-5-mini", base_url="https://story-models.invalid/o")
    provider.generate([{"role": "user", "content": "x"}], model="gpt-6-luna", max_tokens=900, reasoning_effort="minimal")
    provider.generate([{"role": "user", "content": "x"}], model="gpt-5-mini", max_tokens=900, reasoning_effort="minimal")
    assert sent[0]["reasoning_effort"] == "none"
    assert sent[0]["max_completion_tokens"] == 900
    assert "temperature" not in sent[0]
    assert sent[1]["reasoning_effort"] == "minimal"


# ---------------------------------------------------------------------------
# the engine's routing
# ---------------------------------------------------------------------------


@pytest.fixture()
def story_models(monkeypatch):
    def configure(**values: Any) -> None:
        for key in (
            "STORY_WRITER_MODEL",
            "STORY_WRITER_REASONING_EFFORT",
            "STORY_CRITIC_MODEL",
            "STORY_CRITIC_REASONING_EFFORT",
            "STORY_LIVE_MODEL",
        ):
            monkeypatch.setattr(settings, key, values.get(key))
        monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", values.get("ANTHROPIC_API_KEY"))

    return configure


def _critic_schema():
    from app.services.season.director import StoryReview

    return StoryReview


def test_unset_story_models_name_no_model(story_models) -> None:
    story_models()
    assert living_story.story_route(living_story.SceneDraft) == (None, None)
    with living_story.written_ahead_of_time():
        assert living_story.story_route(living_story.SceneDraft) == (None, None)
        assert living_story.story_route(_critic_schema()) == (None, None)


def test_a_page_written_ahead_of_time_uses_the_writer_and_the_critic(story_models) -> None:
    story_models(
        STORY_WRITER_MODEL="claude-haiku-5-5",
        STORY_WRITER_REASONING_EFFORT="medium",
        STORY_CRITIC_MODEL="gpt-6.1-sol",
        STORY_LIVE_MODEL="gpt-6-luna",
        ANTHROPIC_API_KEY="k",
    )
    with living_story.written_ahead_of_time():
        assert living_story.story_route(living_story.SceneDraft) == ("claude-haiku-5-5", "medium")
        assert living_story.story_route(_critic_schema()) == ("gpt-6.1-sol", None)
        assert living_story.story_route(living_story.SemanticTurn) == ("gpt-6-luna", None)
    # A learner waiting: the live model, whatever the step.
    assert living_story.story_route(living_story.SceneDraft) == ("gpt-6-luna", None)
    assert living_story.story_route(_critic_schema()) == ("gpt-6-luna", None)


def test_a_claude_writer_without_a_key_falls_to_the_live_model(story_models) -> None:
    story_models(STORY_WRITER_MODEL="claude-haiku-5-5", STORY_LIVE_MODEL="gpt-6-luna")
    with living_story.written_ahead_of_time():
        assert living_story.story_route(living_story.SceneDraft) == ("gpt-6-luna", None)


def test_json_call_names_the_routed_model_and_effort(story_models, monkeypatch) -> None:
    import time

    from app.services.season.turns import ReplyChoice

    story_models(STORY_LIVE_MODEL="gpt-6-luna")
    calls: list[dict[str, Any]] = []

    class Fake:
        def generate_chat_completion(self, messages, **kwargs):
            calls.append(kwargs)
            return LLMResult(
                provider="openai",
                model=kwargs.get("model", "default"),
                content='{"reply_id": "r1"}',
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                cost=0.0,
                raw_response={},
            )

    monkeypatch.setattr(living_story, "_client", lambda: Fake())
    parsed, usage = living_story._json_call("S", {"x": 1}, ReplyChoice, deadline=time.monotonic() + 30)
    assert parsed.reply_id == "r1"
    assert calls[0]["model"] == usage["model"] == "gpt-6-luna"
    assert calls[0]["reasoning_effort"] == "low"

    story_models()
    calls.clear()
    living_story._json_call("S", {"x": 1}, ReplyChoice, deadline=time.monotonic() + 30)
    assert "model" not in calls[0]


def test_a_page_written_ahead_of_time_gets_the_gate_one_limits(story_models, monkeypatch) -> None:
    """Gate 1 (2026-10-15): under the live 35 s / 5,000-token limits every new writer
    lost every page; the prefetch keeps nobody waiting, so it gets the room."""

    import time

    from app.services.living_story import SceneDraft

    story_models()
    calls: list[dict[str, Any]] = []

    class Fake:
        def generate_chat_completion(self, messages, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("stop here")

    monkeypatch.setattr(living_story, "_client", lambda: Fake())

    def call(**extra) -> dict[str, Any]:
        calls.clear()
        with pytest.raises((RuntimeError, living_story.StoryUnavailable)):
            living_story._json_call("S", {"x": 1}, SceneDraft, deadline=time.monotonic() + 600, **extra)
        return calls[0]

    live = call()
    assert (live["request_timeout"], live["max_tokens"]) == (35, 5000)
    with living_story.written_ahead_of_time():
        ahead = call()
        # A worker thread is told, as it is told the route.
        told_live = call(ahead=False)
    assert (ahead["request_timeout"], ahead["max_tokens"]) == (150, 16000)
    assert (told_live["request_timeout"], told_live["max_tokens"]) == (35, 5000)
    assert call(ahead=True)["request_timeout"] == 150


def test_the_ahead_budget_still_holds_two_attempts() -> None:
    attempts = settings.ATELIER_STORY_MAX_ATTEMPTS
    assert living_story.AHEAD_REQUEST_TIMEOUT_SECONDS * attempts <= living_story.AHEAD_OPERATION_BUDGET_SECONDS
