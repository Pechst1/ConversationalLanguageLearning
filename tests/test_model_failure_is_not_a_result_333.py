"""#333: a model call that failed or came back empty is never shown as a result.

One guard per model-backed Courrier path, driven through the code that already exists with the
client forced to fail the way a provider fails (an error, a timeout). The Forge check and the
Journal correction hold the same rule in tests/test_forge_check_failure.py and
tests/test_journal.py; this file holds the Courrier's two calls, which share one screen.
"""
from __future__ import annotations

import pytest

import app.services.missions as missions_module
from app.db.models.mission import RealWorldMissionTurn
from app.services.llm_service import LLMProviderError
from app.services.news_service import NewsService
from tests.test_missions import _fake_france_context, _token

TEXT = "Je pas ai beaucoup bagages aujourdhui."


class _ClientDown:
    """The model client forced to fail with ``error``."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def generate_error_detection(self, *_a, **_k):
        self.calls += 1
        raise self.error

    def generate_chat_completion(self, *_a, **_k):
        self.calls += 1
        raise self.error


FAILURES = [
    pytest.param(LLMProviderError("down"), id="provider-error"),
    pytest.param(TimeoutError("read timed out"), id="timeout"),
]


def _letter(client, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    created = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": "ad_hoc", "use_news": False},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    return headers, created.json()["mission"]["id"]


@pytest.mark.parametrize("error", FAILURES)
def test_a_failed_courrier_call_is_unchecked_and_unanswered_not_clean(client, db_session, monkeypatch, error):
    down = _ClientDown(error)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    headers, mission_id = _letter(client, monkeypatch)
    # The letter exists; from here on every model call of the turn fails.
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: down)

    response = client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": TEXT, "mode": "chat"}, headers=headers)

    assert response.status_code == 200, f"the failed call took the whole turn down: {response.text}"
    body = response.json()
    correction = body["correction"]
    assert down.calls >= 1
    assert correction["verdict"] != "accepted", "a call that never ran was reported as a clean verdict"
    assert correction["correction_debug"]["fallback_used"] is True
    assert all(item.get("assessed") is False for item in correction["objective_progress"])
    # The reply call failed the same way: no stock line is stored as the correspondent's turn.
    assert body["assistant_turn"] == {}
    assert body["outcome"]["reply_state"] == "pending"
    assert [turn.get("reply_state") for turn in body["mission"]["turns"] if turn["role"] == "user"] == ["pending"]
    db_session.expire_all()
    assert db_session.query(RealWorldMissionTurn).filter(RealWorldMissionTurn.role == "assistant").count() == 0
