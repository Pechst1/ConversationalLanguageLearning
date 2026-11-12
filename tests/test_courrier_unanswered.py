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


# -- a gap in the middle (the review of the first attempt at #590) -------------------------
#
# The reply provider fails on the SECOND message only; the learner writes on and the third is
# answered. The letter must still say message 2 went unanswered, and must not close kept.


def _fail_on_second(client, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [CAMILLE, _stock(), "Très bien."])
    sent = [_send(client, headers, mission_id, text) for text in MESSAGES]
    return headers, mission_id, sent


def test_a_gap_before_an_answered_message_stays_visible_on_the_thread(client, monkeypatch):
    headers, mission_id, sent = _fail_on_second(client, monkeypatch)

    states = [turn.get("reply_state") for turn in _user_turns(sent[-1]["mission"])]
    assert states == [None, "pending", None], f"message 2 lost its «not answered» line: {states}"
    reloaded = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()
    reloaded = reloaded.get("mission", reloaded)
    assert [turn.get("reply_state") for turn in _user_turns(reloaded)] == [None, "pending", None]


def test_a_letter_with_a_gap_in_the_middle_is_not_kept_and_mints_no_token(client, db_session, monkeypatch):
    headers, mission_id, _sent = _fail_on_second(client, monkeypatch)

    recap = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers).json()["recap"]

    assert recap["outcome"] != "kept", "«Promise kept» with message 2 unanswered"
    assert recap["courrier_outcome"] != "kept"
    assert recap["measured"]["reply_pending"] is True
    assert recap["minted_collectibles"] == []


def test_the_message_written_past_can_be_asked_again_and_the_letter_is_then_kept(client, db_session, monkeypatch):
    headers, mission_id, sent = _fail_on_second(client, monkeypatch)
    second_id = _user_turns(sent[-1]["mission"])[1]["id"]
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_kw: "Pas de souci, on regarde ça ensemble.")

    retried = client.post(f"/api/v1/missions/{mission_id}/turns/{second_id}/reply", headers=headers)

    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["assistant_turn"]["text"] == "Pas de souci, on regarde ça ensemble."
    assert "reply_state" not in body["outcome"]
    # The answer sits directly after the message it answers, and nothing is pending any more.
    roles = [(turn["role"], turn["turn_index"]) for turn in body["mission"]["turns"]]
    assert [role for role, _ in roles] == ["user", "assistant", "user", "assistant", "user", "assistant"], roles
    assert [index for _, index in roles] == sorted(index for _, index in roles)
    assert all(turn.get("reply_state") != "pending" for turn in body["mission"]["turns"])

    recap = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers).json()["recap"]
    assert recap["outcome"] == "kept"
    assert not recap["measured"].get("reply_pending")


def test_asking_again_for_an_earlier_message_answers_it_from_the_thread_as_it_stood(client, monkeypatch):
    headers, mission_id, sent = _fail_on_second(client, monkeypatch)
    second_id = _user_turns(sent[-1]["mission"])[1]["id"]
    seen: list[int | None] = []

    def respond(self, **kwargs):
        seen.append(kwargs.get("through_turn_index"))
        return "Réponse."

    monkeypatch.setattr(MissionConversationService, "respond", respond)
    client.post(f"/api/v1/missions/{mission_id}/turns/{second_id}/reply", headers=headers)

    assert seen == [3], "the retry for message 2 must not read what the learner wrote after it"


# #693 — live walk 11 Nov: Lila never answered, «Ask again» was pressed, and the thread read
# exactly as before: the learner could not tell whether the retry had run, failed or was still
# going. A failed ask is now a fact of the learner's turn (how many times the correspondent was
# asked, and when last), so the thread itself says a retry ran and failed, also after a reload.


def test_a_reply_asked_again_that_fails_again_says_so_on_the_thread(client, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [_stock(), _stock(), "Merci, à demain !"])
    sent = _send(client, headers, mission_id, MESSAGES[0])
    turn_id = _user_turns(sent["mission"])[-1]["id"]
    assert _user_turns(sent["mission"])[-1].get("reply_attempts") == 1, "the first failed ask left no trace"

    retried = client.post(f"/api/v1/missions/{mission_id}/turns/{turn_id}/reply", headers=headers)

    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["outcome"]["reply_state"] == "pending"
    assert body["outcome"].get("reply_attempts") == 2, "«Ask again» ran and failed, but the answer reads as before it"
    asked = _user_turns(body["mission"])[-1]
    assert asked["reply_state"] == "pending"
    assert asked.get("reply_attempts") == 2, "the thread does not say the retry ran and failed"
    assert asked.get("reply_asked_at"), "the thread does not say when the correspondent was last asked"
    reloaded = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()
    reloaded = reloaded.get("mission", reloaded)
    assert _user_turns(reloaded)[-1].get("reply_attempts") == 2, "a reload forgets the failed retry"

    answered = client.post(f"/api/v1/missions/{mission_id}/turns/{turn_id}/reply", headers=headers).json()

    assert answered["assistant_turn"]["text"] == "Merci, à demain !"
    assert "reply_state" not in answered["outcome"]
    assert "reply_attempts" not in _user_turns(answered["mission"])[-1], "an answered message still reads as failed"


# #693 review of #701: the ask counter is server-owned. It lived in the turn's audio_payload,
# which the send path fills from the client's `transcript_metadata`, and was read with a bare
# int(): `{"reply_asks": {"count": "x"}}` made the send, the mission and «today» answer 500, and
# `{"count": 5}` made a first send read as «Asked again … still cannot answer».


def _send_with_metadata(client, headers, mission_id, text, metadata):
    return client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": text, "mode": "chat", "transcript_metadata": metadata},
        headers=headers,
    )


def test_a_client_written_ask_counter_cannot_break_the_courrier(client, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [_stock()])

    sent = _send_with_metadata(client, headers, mission_id, MESSAGES[0], {"reply_asks": {"count": "x"}})

    assert sent.status_code == 200, f"a client-written ask counter broke the send: {sent.status_code}"
    assert sent.json()["outcome"].get("reply_attempts") == 1
    mission = client.get(f"/api/v1/missions/{mission_id}", headers=headers)
    assert mission.status_code == 200, f"one bad turn locks the learner out of the letter: {mission.status_code}"
    today = client.get("/api/v1/missions/today", headers=headers)
    assert today.status_code == 200, f"one bad turn takes the whole Courrier down: {today.status_code}"


def test_a_client_cannot_make_a_first_send_read_as_a_failed_retry(client, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    _provider_answers(monkeypatch, [_stock()])

    sent = _send_with_metadata(
        client, headers, mission_id, MESSAGES[0], {"reply_asks": {"count": 5}, "source": "keyboard"}
    )

    assert sent.status_code == 200, sent.text
    assert sent.json()["outcome"].get("reply_attempts") == 1, "the client wrote the server's ask counter"
    turn = _user_turns(sent.json()["mission"])[-1]
    assert turn.get("reply_attempts") == 1, "«Ask again» never ran, yet the thread says it ran and failed"
    assert turn["audio_payload"].get("source") == "keyboard", "the client's own metadata was dropped too"


def test_a_stored_counter_that_is_not_a_count_reads_as_asked_once():
    from app.services.missions import note_unanswered_ask, unanswered_fields

    for bad in ("x", None, -4, [1], {"n": 1}, True):
        turn = SimpleNamespace(audio_payload={"reply_asks": {"count": bad, "last_at": 7}}, created_at=None)
        assert unanswered_fields(turn, None)["reply_attempts"] == 1, bad
        assert note_unanswered_ask(turn) == 1, bad
    assert unanswered_fields(SimpleNamespace(audio_payload="oops", created_at=None), None)["reply_attempts"] == 1
