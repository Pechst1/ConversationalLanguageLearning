"""Pilot P0, walk of 17 Nov (A1, Lila): the second letter of a thread got no reply twice.

The server answered in time (every call under 2 s, status 200). At A1 both reply drafts
used a tense the band has not met (a futur simple), the voice guard vetoed both, and the
reply became the authored acknowledgement. That line is not stored as the character's turn
(#397/#333), so the thread only said «Lila hat auf diese Nachricht noch nicht geantwortet»:
a silent thread, though the character had something to say.

The acknowledgement is still not a turn (the letter is not answered and never closes
«kept»), but the thread now carries it on the unanswered message as ``held_reply``, in the
correspondent's register, so the learner reads it in the same request.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.services.missions import (
    MissionConversationService,
    MissionCorrectionService,
    is_stock_reply,
)
from app.services.news_service import NewsService
from tests.test_missions import _fake_france_context, _token

#: A reply the A1 voice guard always vetoes: «viendras» is a futur simple.
VETOED = "D'accord. Tu viendras au café demain ?"


class _AlwaysFuture:
    def __init__(self) -> None:
        self.calls = 0

    def generate_chat_completion(self, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return SimpleNamespace(content=VETOED)


def _setup(client: TestClient, monkeypatch) -> tuple[dict[str, str], str, _AlwaysFuture]:
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    created = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": "ad_hoc", "use_news": False},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    mission_id = created.json()["mission"]["id"]

    def unassessed(self, **_kw):
        return {
            "verdict": "accepted",
            "score_0_4": 3,
            "corrected_answer": "",
            "objective_progress": [],
            "concept_hits": [],
            "missing_targets": [],
            "errata": [],
            "vocabulary_links": [],
        }

    monkeypatch.setattr(MissionCorrectionService, "correct_submission", unassessed)
    llm = _AlwaysFuture()
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: llm)
    monkeypatch.setattr(missions_module, "_learner_level_code", lambda db, user: "A1")
    monkeypatch.setattr(missions_module, "_record_mission_llm_cost", lambda *a, **k: None)
    return headers, mission_id, llm


def _user_turns(mission: dict) -> list[dict]:
    return [turn for turn in mission["turns"] if turn["role"] == "user"]


def test_a_vetoed_reply_leaves_the_acknowledgement_on_the_thread(client, monkeypatch):
    headers, mission_id, llm = _setup(client, monkeypatch)

    response = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je mange une soupe avec Marin ce soir.", "mode": "chat"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert llm.calls == 2, "the reply was asked for and rewritten once"
    # #397 stands: the line nobody wrote is not the correspondent's turn.
    assert body["assistant_turn"] == {}
    assert body["outcome"]["reply_state"] == "pending"
    held = _user_turns(body["mission"])[-1].get("held_reply")
    assert held and is_stock_reply(held), f"the thread is silent on the unanswered message: {held!r}"
    assert body["outcome"].get("held_reply") == held

    reloaded = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()
    reloaded = reloaded.get("mission", reloaded)
    assert _user_turns(reloaded)[-1].get("held_reply") == held, "a reload loses the acknowledgement"


def test_asking_again_that_is_vetoed_again_still_holds_the_acknowledgement(client, monkeypatch):
    headers, mission_id, _llm = _setup(client, monkeypatch)
    sent = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je mange une soupe avec Marin ce soir.", "mode": "chat"},
        headers=headers,
    ).json()
    turn_id = _user_turns(sent["mission"])[-1]["id"]

    retried = client.post(f"/api/v1/missions/{mission_id}/turns/{turn_id}/reply", headers=headers)

    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["outcome"]["reply_state"] == "pending"
    assert is_stock_reply(body["outcome"].get("held_reply"))
    assert is_stock_reply(_user_turns(body["mission"])[-1].get("held_reply"))


def test_an_answered_message_holds_nothing(client, monkeypatch):
    headers, mission_id, _llm = _setup(client, monkeypatch)
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_kw: "Bonne idée, la soupe de Marin est bonne.")

    body = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je mange une soupe avec Marin ce soir.", "mode": "chat"},
        headers=headers,
    ).json()

    assert "held_reply" not in _user_turns(body["mission"])[-1]
    assert "held_reply" not in body["outcome"]
