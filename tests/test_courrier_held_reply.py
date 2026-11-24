"""Pilot P0, walk of 17 Nov (A1, Lila), then #1025 (live walk 23 Nov, child of #333).

17 Nov: the second letter of a thread got no reply twice. Both A1 reply drafts used a
tense the band has not met (a futur simple), the voice guard vetoed both, and the thread
only said «Lila hat auf diese Nachricht noch nicht geantwortet». The fix of the day sent
the stock acknowledgement on the unanswered message as ``held_reply`` and the page printed
it in Lila's voice.

23 Nov: that line is what the learner read as Lila's answer to a real reply — «Lila :
« Merci pour ton message, je l'ai bien lu. Je te réponds vite. »» — above «Ask again»,
which then brought the real answer. A line nobody wrote, in a character's mouth, is a
failed model call shown as a result (#333). The server no longer hands it to the page:
the message is marked ``reply_state: pending`` and nothing else, and the page says
honestly that nobody answered yet, with «Ask again».
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.db.models.mission import RealWorldMission
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


def _strings(value) -> list[str]:  # type: ignore[no-untyped-def]
    """Every string anywhere in a response the page reads."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _assert_no_stock_line(body: dict, where: str) -> None:
    stock = [text for text in _strings(body) if is_stock_reply(text) or "je l'ai bien lu" in text]
    assert not stock, f"{where}: the stock line reaches the page as the character's words: {stock!r}"


def _assert_pending(body: dict, mission: dict, where: str) -> None:
    assert body["outcome"]["reply_state"] == "pending", where
    assert not body["outcome"].get("reply_text"), where
    assert _user_turns(mission)[-1].get("reply_state") == "pending", f"{where}: «Ask again» is not offered"
    assert not [turn for turn in mission["turns"] if turn["role"] == "assistant"], where


def test_a_vetoed_reply_shows_nobody_answered_not_the_stock_line(client, monkeypatch):
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
    _assert_pending(body, body["mission"], "send")
    _assert_no_stock_line(body, "send")

    reloaded = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()
    _assert_no_stock_line(reloaded, "reload")
    reloaded = reloaded.get("mission", reloaded)
    assert _user_turns(reloaded)[-1].get("reply_state") == "pending", "a reload loses «Ask again»"


class _Down:
    def generate_chat_completion(self, **_kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutError("provider down")


def test_a_failed_reply_call_shows_nobody_answered_not_the_stock_line(client, db_session, monkeypatch):
    """#1025 as walked: «Un mot de Lila» in tu, and the reply call fails twice."""

    headers, mission_id, _llm = _setup(client, monkeypatch)
    mission = db_session.get(RealWorldMission, UUID(mission_id))
    prompt = dict(mission.prompt_payload or {})
    prompt["messenger"] = {**(prompt.get("messenger") or {}), "contact_name": "Lila", "target_register": "tu / registre familier"}
    prompt["serial_character_id"] = "lila_bonnet"
    prompt["target_register"] = "tu / registre familier"
    mission.prompt_payload = prompt
    db_session.add(mission)
    db_session.commit()
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Down())

    body = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Non, je ne veux pas que tu apportes quelque chose.", "mode": "chat"},
        headers=headers,
    ).json()

    _assert_pending(body, body["mission"], "send")
    _assert_no_stock_line(body, "send")


def test_asking_again_that_fails_again_still_shows_nobody_answered(client, monkeypatch):
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
    _assert_pending(body, body["mission"], "ask again")
    _assert_no_stock_line(body, "ask again")


def test_an_answered_message_is_not_pending(client, monkeypatch):
    headers, mission_id, _llm = _setup(client, monkeypatch)
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_kw: "Bonne idée, la soupe de Marin est bonne.")

    body = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je mange une soupe avec Marin ce soir.", "mode": "chat"},
        headers=headers,
    ).json()

    assert "reply_state" not in _user_turns(body["mission"])[-1]
    assert body["outcome"].get("reply_state") != "pending"
    _assert_no_stock_line(body, "answered")
