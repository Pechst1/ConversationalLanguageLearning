"""Word help: a word's meaning in its sentence (``POST /api/v1/atelier/gloss``).

The word-help sheet looks a tapped word up in the catalogue first; a news word or an
inflected form misses it («grévistes», «reviennent»), and the sheet used to translate
the whole line instead. ``/atelier/gloss`` reads the word in its sentence and answers
with its dictionary form, a short meaning in the learner's own language and the
sentence's translation. The model is a fake here: no paid call.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.atelier import get_atelier_user
from app.main import create_app
from app.services import llm_service as llm_module


class _Learner:
    def __init__(self, native: str) -> None:
        self.native_language = native


@pytest.fixture()
def learner() -> _Learner:
    return _Learner("de")


@pytest.fixture()
def gloss_client(learner: _Learner) -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_atelier_user] = lambda: learner
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def calls(monkeypatch) -> list[dict]:
    """The fake model: records each call and answers like the real one, as JSON."""

    seen: list[dict] = []

    def fake(self, messages, **kwargs):
        seen.append({"messages": messages, **kwargs})
        asked = json.loads(messages[0]["content"])
        return SimpleNamespace(
            content=json.dumps(
                {
                    "lemma": "gréviste",
                    "gloss": "  die  Streikenden ",
                    "translation": f"[{asked['word']}] Eine Erklärung der Streikenden.",
                }
            )
        )

    monkeypatch.setattr(llm_module.LLMService, "generate_chat_completion", fake, raising=False)
    return seen


def _sentence() -> str:
    # A sentence of its own per test: the cache is process-wide.
    return f"Une déclaration des grévistes ({uuid.uuid4().hex[:6]})."


def test_the_word_is_glossed_in_its_sentence_in_the_learners_language(gloss_client, calls) -> None:
    sentence = _sentence()
    response = gloss_client.post("/api/v1/atelier/gloss", json={"word": "grévistes", "sentence": sentence})

    assert response.status_code == 200
    assert response.json() == {
        "lemma": "gréviste",
        "gloss": "die Streikenden",
        "language": "de",
        "translation": "[grévistes] Eine Erklärung der Streikenden.",
    }
    (call,) = calls
    assert json.loads(call["messages"][0]["content"]) == {"word": "grévistes", "sentence": sentence}
    assert "German" in call["system_prompt"]
    assert call["temperature"] == 0.0
    assert call["response_format"] == {"type": "json_object"}
    assert call["request_timeout"] <= 10


def test_the_same_word_in_the_same_sentence_is_asked_once(gloss_client, calls) -> None:
    sentence = _sentence()
    first = gloss_client.post("/api/v1/atelier/gloss", json={"word": "grévistes", "sentence": sentence}).json()
    again = gloss_client.post("/api/v1/atelier/gloss", json={"word": "Grévistes", "sentence": sentence}).json()
    other = gloss_client.post("/api/v1/atelier/gloss", json={"word": "grévistes", "sentence": _sentence()}).json()

    assert again == first
    assert other["gloss"] == "die Streikenden"
    assert len(calls) == 2, "the cached answer is served; another sentence is asked"


def test_english_is_the_floor(gloss_client, calls, learner) -> None:
    learner.native_language = "fr"
    body = gloss_client.post("/api/v1/atelier/gloss", json={"word": "plagiat", "sentence": _sentence()}).json()

    assert body["language"] == "en"
    assert "English" in calls[-1]["system_prompt"]


@pytest.mark.parametrize("content", ["not json", "[]", json.dumps({"lemma": "x", "gloss": 3})])
def test_an_unreadable_answer_is_empty_and_never_cached(gloss_client, monkeypatch, content) -> None:
    seen: list[int] = []

    def unreadable(self, messages, **kwargs):
        seen.append(1)
        return SimpleNamespace(content=content)

    monkeypatch.setattr(llm_module.LLMService, "generate_chat_completion", unreadable, raising=False)
    sentence = _sentence()
    for _ in range(2):
        body = gloss_client.post("/api/v1/atelier/gloss", json={"word": "grévistes", "sentence": sentence}).json()
        assert body["gloss"] == ""
        assert body["language"] == "de"
    assert len(seen) == 2


def test_a_failing_model_is_an_empty_answer_not_an_error(gloss_client, monkeypatch) -> None:
    def down(self, messages, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm_module.LLMService, "generate_chat_completion", down, raising=False)
    response = gloss_client.post("/api/v1/atelier/gloss", json={"word": "grévistes", "sentence": _sentence()})

    assert response.status_code == 200
    assert response.json() == {"lemma": "", "gloss": "", "language": "de", "translation": ""}
