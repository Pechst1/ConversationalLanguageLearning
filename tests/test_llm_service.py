import pytest

from app.services.llm_service import LLMProviderError, LLMResult, LLMService


class StubProvider:
    def __init__(self, name: str, response: LLMResult | None = None, should_fail: bool = False):
        self.name = name
        self._response = response
        self.should_fail = should_fail
        self.recorded_messages = None
        self.recorded_kwargs = None

    def generate(self, messages, **kwargs):
        self.recorded_messages = list(messages)
        self.recorded_kwargs = kwargs
        if self.should_fail:
            raise LLMProviderError(f"{self.name} failure")
        return self._response


@pytest.fixture()
def sample_result() -> LLMResult:
    return LLMResult(
        provider="stub",
        model="test-model",
        content="Bonjour !",
        prompt_tokens=10,
        completion_tokens=8,
        total_tokens=18,
        cost=0.002,
        raw_response={"usage": {"prompt_tokens": 10, "completion_tokens": 8}},
    )


def test_llm_service_prefers_primary_provider(sample_result):
    primary = StubProvider("openai", response=sample_result)
    fallback = StubProvider("anthropic", response=sample_result)

    service = LLMService(providers=[primary, fallback], primary="openai")
    result = service.generate_chat_completion(
        [{"role": "user", "content": "Parlons de voyage."}],
        system_prompt="You are a friendly tutor.",
    )

    assert result.provider == "stub"
    assert primary.recorded_messages[0]["role"] == "system"
    assert "temperature" in primary.recorded_kwargs


def test_llm_service_falls_back_on_error(sample_result):
    failing = StubProvider("openai", should_fail=True)
    fallback_result = LLMResult(
        provider="stub",
        model="test-model",
        content="Salut !",
        prompt_tokens=12,
        completion_tokens=6,
        total_tokens=18,
        cost=0.003,
        raw_response={},
    )
    fallback = StubProvider("anthropic", response=fallback_result)

    service = LLMService(providers=[failing, fallback], primary="openai")
    result = service.generate_chat_completion([
        {"role": "user", "content": "Comment ça va ?"}
    ], temperature=0.2)

    assert result.content == "Salut !"
    assert fallback.recorded_kwargs["temperature"] == 0.2


def test_llm_service_forwards_request_timeout(sample_result):
    primary = StubProvider("openai", response=sample_result)

    service = LLMService(providers=[primary], primary="openai")
    service.generate_chat_completion(
        [{"role": "user", "content": "Vite, s'il te plait."}],
        request_timeout=4.5,
    )

    assert primary.recorded_kwargs["request_timeout"] == 4.5


def test_chat_completion_forwards_low_latency_options(sample_result):
    primary = StubProvider("openai", response=sample_result)

    service = LLMService(providers=[primary], primary="openai")
    service.generate_chat_completion(
        [{"role": "user", "content": "Génère un exercice."}],
        model="gpt-4o-mini",
        request_timeout=8.0,
        disable_retries=True,
        reasoning_effort="low",
    )

    assert primary.recorded_kwargs["model"] == "gpt-4o-mini"
    assert primary.recorded_kwargs["request_timeout"] == 8.0
    assert primary.recorded_kwargs["disable_retries"] is True
    assert primary.recorded_kwargs["reasoning_effort"] == "low"


def test_error_detection_forwards_low_latency_options(sample_result):
    primary = StubProvider("openai", response=sample_result)

    service = LLMService(providers=[primary], primary="openai")
    service.generate_error_detection(
        [{"role": "user", "content": "Corrige cette phrase."}],
        model="gpt-4o-mini",
        request_timeout=3.5,
        disable_retries=True,
        reasoning_effort="none",
    )

    assert primary.recorded_kwargs["model"] == "gpt-4o-mini"
    assert primary.recorded_kwargs["request_timeout"] == 3.5
    assert primary.recorded_kwargs["disable_retries"] is True
    assert primary.recorded_kwargs["reasoning_effort"] == "none"


def test_llm_service_raises_when_all_providers_fail(sample_result):
    failing_primary = StubProvider("openai", should_fail=True)
    failing_secondary = StubProvider("anthropic", should_fail=True)

    service = LLMService(providers=[failing_primary, failing_secondary], primary="openai")

    with pytest.raises(LLMProviderError):
        service.generate_chat_completion([
            {"role": "user", "content": "Quel temps fait-il ?"}
        ])
