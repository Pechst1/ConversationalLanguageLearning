"""#590 (children of #333 and #145): a learner message nobody answered is never closed as «Promise kept».

Live walk 8 Nov: three messages to Camille, the reply provider failed on the last two, and
«Finish» still printed «Promise kept · Camille is pleased with you». The verdict was taken
from the corrector's per-objective flags alone; the thread had no state saying which learner
message was answered, so neither the page nor the debrief could tell.

The thread now carries that state (`reply_state: "pending"` on the learner's unanswered turn),
the reply can be asked for again from that turn, and a letter finished with an unanswered
message is not scored, not rewarded and does not move the correspondent.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.services.missions import (
    MissionConversationService,
    MissionCorrectionService,
    _unassessed_acknowledgement,
)
from app.services.news_service import NewsService
from tests.test_missions import _fake_france_context, _token

MESSAGES = [
    "Non, je n'ai pas la bonne rue, je cherche le colis.",
    "J'aime les dinosaures et la pizza. Et vous, qu'est-ce que vous aimez ?",
    "Mon numéro de suivi est 12345, pouvez-vous vérifier le colis demain matin ?",
]
CAMILLE = "Ah d'accord ! Donnez-moi le numéro de suivi."


def _stock() -> str:
    return _unassessed_acknowledgement(SimpleNamespace(prompt_payload={}))


def _setup(client: TestClient, monkeypatch) -> tuple[dict[str, str], str]:
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    created = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": "ad_hoc", "use_news": False},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    mission = created.json()["mission"]

    def every_objective_met(self, **_kw):
        return {
            "verdict": "accepted",
            "score_0_4": 4,
            "corrected_answer": "",
            "objective_progress": [
                {"id": item["id"], "label": "x", "met": True, "assessed": True} for item in mission["objectives"]
            ],
            "concept_hits": [],
            "missing_targets": [],
            "errata": [],
            "vocabulary_links": [],
        }

    monkeypatch.setattr(MissionCorrectionService, "correct_submission", every_objective_met)
    return headers, mission["id"]


def _send(client, headers, mission_id, text):
    response = client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": text, "mode": "chat"}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _provider_answers(monkeypatch, replies: list[str]) -> None:
    answers = iter(replies)
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_kw: next(answers))


def _user_turns(mission: dict) -> list[dict]:
    return [turn for turn in mission["turns"] if turn["role"] == "user"]


def test_the_thread_says_which_learner_message_nobody_answered(client, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [CAMILLE, _stock(), _stock()])

    answered = _send(client, headers, mission_id, MESSAGES[0])
    second = _send(client, headers, mission_id, MESSAGES[1])
    third = _send(client, headers, mission_id, MESSAGES[2])

    assert _user_turns(answered["mission"])[0].get("reply_state") != "pending"
    assert _user_turns(second["mission"])[-1].get("reply_state") == "pending", "message 2 is silently unanswered"
    # Reloading the thread tells the same story: the state is stored, not a toast.
    reloaded = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()
    mission = reloaded.get("mission", reloaded)
    states = [turn.get("reply_state") for turn in _user_turns(mission)]
    assert states[-1] == "pending", states
    assert states[0] != "pending", states
    assert third["outcome"]["reply_state"] == "pending"


def test_a_letter_finished_on_an_unanswered_message_is_not_promise_kept(client, db_session, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [CAMILLE, _stock(), _stock()])
    for text in MESSAGES:
        _send(client, headers, mission_id, text)

    response = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers)

    assert response.status_code == 200, response.text
    recap = response.json()["recap"]
    assert recap["outcome"] != "kept", "the letter closed «Promise kept» with two messages unanswered"
    assert recap["courrier_outcome"] != "kept"
    assert recap["measured"]["reply_pending"] is True
    assert recap["minted_collectibles"] == [], "a token was minted for an unanswered exchange"
    db_session.expire_all()
    assert db_session.get(RealWorldMission, UUID(mission_id)).outcome != "kept"


def test_the_reply_can_be_asked_for_again_from_the_unanswered_turn(client, db_session, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [CAMILLE, _stock(), "Très bien, je regarde demain matin.", "unused"])
    _send(client, headers, mission_id, MESSAGES[0])
    second = _send(client, headers, mission_id, MESSAGES[1])
    turn_id = _user_turns(second["mission"])[-1]["id"]

    retried = client.post(f"/api/v1/missions/{mission_id}/turns/{turn_id}/reply", headers=headers)

    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["assistant_turn"]["text"] == "Très bien, je regarde demain matin."
    assert "reply_state" not in body["outcome"]
    assert all(turn.get("reply_state") != "pending" for turn in _user_turns(body["mission"]))
    db_session.expire_all()
    assert db_session.query(RealWorldMissionTurn).filter(RealWorldMissionTurn.role == "assistant").count() == 2


def test_an_answered_letter_is_still_kept(client, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [CAMILLE, "Parfait, merci.", "Très bien."])
    for text in MESSAGES:
        _send(client, headers, mission_id, text)

    recap = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers).json()["recap"]

    assert recap["outcome"] == "kept"
    assert not recap["measured"].get("reply_pending")
