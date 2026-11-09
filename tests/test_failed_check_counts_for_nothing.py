"""#333: a check that did not run counts for nothing, on every surface that judges free text.

The client is forced to fail the way a provider fails (an error, a timeout, an empty answer).
Whatever the surface: the answer reads ``not_checked``, no level moves, no gold or token is
minted, and only the fixes the rules really found are kept (owner decision D4). A control beside
each guard shows the same path paying when the model did answer, so these can't pass by the path
simply being dead.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

import app.services.journal as journal_module
import app.services.missions as missions_module
from app.config import settings
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.gold import GoldLedgerEntry
from app.db.models.journal import JournalEntry
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import gold_ledger, verdicts
from app.services.atelier_rewards import AtelierRewardService
from app.services.cefr_progress import CEFRProgressService
from app.services.journey_contracts import TaskOutcome
from app.services.llm_service import LLMProviderError, LLMResult
from app.services.missions import MissionConversationService
from app.services.story_correspondence import answer_letter_from_journey
from tests.test_forge_check_failure import _free_text_answer
from tests.test_journal_api import (  # noqa: F401
    _email,
    _FakeChecker,
    _seed_scene,
    journal_client,
    login,
)
from tests.test_model_failure_is_not_a_result_333 import _letter

#: Exact walk text from #333 and #250. The first has real mistakes no rule sees, so the old
#: «No corrections found» read as a clean verdict; the second has one a rule does see.
UNSEEN_BY_RULES = "Je pas ai beaucoup bagages aujourd'hui, mais je viens chez toi samedi soir."
SEEN_BY_RULES = "Je suis tres content de venir chez toi samedi soir avec mon ami Marin."


class _Client:
    """The model client, forced to answer one way."""

    def __init__(self, *, error: Exception | None = None, content: str = "") -> None:
        self.error = error
        self.content = content
        self.calls = 0

    def _answer(self, *_a, **_k) -> LLMResult:
        self.calls += 1
        if self.error:
            raise self.error
        return LLMResult(
            provider="stub", model="stub", content=self.content, prompt_tokens=1, completion_tokens=1,
            total_tokens=2, cost=0.0, raw_response={},
        )

    generate_error_detection = _answer
    generate_chat_completion = _answer


#: (client arguments, the call it reads as, the failure class it reads as)
FAILURES = [
    pytest.param({"error": LLMProviderError("down")}, "failed", "provider_error", id="raises"),
    pytest.param({"error": TimeoutError("read timed out")}, "failed", "timeout", id="times-out"),
    pytest.param({"content": ""}, "empty", "invalid_output", id="comes-back-empty"),
]


def _a_grade(text: str, *, verdict: str = "accepted", errata: list | None = None) -> str:
    return json.dumps(
        {
            "verdict": verdict, "score_0_4": 4, "corrected_answer": text, "objective_progress": [], "concept_hits": [],
            "missing_targets": [], "errata": errata or [], "vocabulary_links": [], "why": "", "repair": "",
        }
    )


@pytest.fixture(autouse=True)
def gold_on(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")


@pytest.fixture()
def tokens(monkeypatch):
    """The letters a logo token was minted for."""

    minted: list = []
    monkeypatch.setattr(
        AtelierRewardService, "mint_logo_token_for_mission", lambda self, mission: minted.append(mission.id) or []
    )
    return minted


def _gold(db, user_id) -> list[GoldLedgerEntry]:
    db.flush()
    return list(db.scalars(select(GoldLedgerEntry).where(GoldLedgerEntry.user_id == user_id)))


def _owner_of(db, mission_id) -> User:
    return db.get(User, db.get(RealWorldMission, UUID(mission_id)).user_id)


def _scores(db, user) -> list[float]:
    return CEFRProgressService(db)._recent_scores(user=user, start=datetime(2000, 1, 1, tzinfo=UTC))


def _begin(client, monkeypatch):
    """A letter written with the model off, so the failure under test starts at the correction."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    return _letter(client, monkeypatch)


# --- Le Courrier ------------------------------------------------------------------------------


@pytest.mark.parametrize(("client_args", "call", "failure"), FAILURES)
def test_a_letter_nobody_read_counts_for_nothing(client, db_session, monkeypatch, tokens, client_args, call, failure):
    headers, mission_id = _begin(client, monkeypatch)
    down = _Client(**client_args)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: down)

    response = client.post(f"/api/v1/missions/{mission_id}/submit", json={"text": UNSEEN_BY_RULES, "mode": "writing"}, headers=headers)
    assert response.status_code == 200, response.text
    assert down.calls >= 1
    body = response.json()
    check = body["check"]
    assert (check["outcome"], check["checked_by"], check["call"], check["failure"]) == (
        "not_checked", "none", call, failure,
    )
    assert check["counts"] is False and check["retryable"] is True
    assert body["correction"]["verdict"] == "unassessed"
    assert not body["correction"]["score_0_4"]

    done = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers)
    assert done.status_code == 200, done.text

    db_session.expire_all()
    mission = db_session.get(RealWorldMission, UUID(mission_id))
    user = db_session.get(User, mission.user_id)
    assert mission.status == "completed", "a letter can always be finished (D5)"
    assert (mission.recap_payload.get("debrief") or mission.recap_payload)["measured"].get("unchecked") is True
    assert _gold(db_session, user.id) == []
    assert tokens == []
    assert _scores(db_session, user) == [], "a score nobody gave reached the average that gates a level"
    assert db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == "verdict_check_failed", PilotEvent.user_id == user.id)
    ).first(), "the failure left no line for the next walk to read"


def test_a_letter_the_model_read_still_pays(client, db_session, monkeypatch, tokens):
    headers, mission_id = _begin(client, monkeypatch)
    up = _Client(content=_a_grade(UNSEEN_BY_RULES))
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: up)

    response = client.post(f"/api/v1/missions/{mission_id}/submit", json={"text": UNSEEN_BY_RULES, "mode": "writing"}, headers=headers)
    assert response.json()["check"]["counts"] is True
    assert client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers).status_code == 200

    db_session.expire_all()
    user = _owner_of(db_session, mission_id)
    assert [entry.source_kind for entry in _gold(db_session, user.id)] == [gold_ledger.SOURCE_LETTER]
    assert tokens, "the control: a letter the model read mints its token"
    assert _scores(db_session, user) == [4.0]


def test_rule_fixes_are_a_basic_check_and_never_a_score(client, db_session, monkeypatch):
    """D4: «tres» is a real fix. It is listed and filed, and it is still no verdict."""

    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(error=LLMProviderError("down")))
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: "Ah bon ? Raconte-moi.")

    body = client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": SEEN_BY_RULES, "mode": "chat"}, headers=headers).json()

    check = body["check"]
    assert (check["outcome"], check["checked_by"], check["counts"]) == ("not_checked", "rules", False)
    assert [(edit["span"], edit["replacement"]) for edit in check["edits"]] == [("tres", "très")]
    assert "très" in check["corrected"]
    assert body["correction"]["verdict"] == "unassessed", "a rule fix read as a «partial» that pays"
    assert not body["correction"]["score_0_4"]
    assert body["correction"]["persistence"]["repair_count"] == 1, "the rule's real fix goes in the errata"


def test_asking_again_files_no_mistake_twice_and_then_counts(client, db_session, monkeypatch, tokens):
    """D5: «Check again» that succeeds before the letter closes counts normally."""

    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(error=LLMProviderError("down")))
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: "Ah bon ? Raconte-moi.")
    first = client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": SEEN_BY_RULES, "mode": "chat"}, headers=headers).json()
    assert first["correction"]["persistence"]["repair_count"] == 1
    turn_id = first["user_turn"]["id"]

    still_down = client.post(f"/api/v1/missions/{mission_id}/turns/{turn_id}/correction", headers=headers).json()
    assert still_down["check"]["counts"] is False and still_down["errata"] == []

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(content=_a_grade(SEEN_BY_RULES)))
    again = client.post(f"/api/v1/missions/{mission_id}/turns/{turn_id}/correction", headers=headers).json()
    assert again["check"]["counts"] is True and again["check"]["outcome"] != "not_checked"
    assert again["errata"] == [], "the rule's fix was filed the first time; a retry counted it twice"
    assert again["correction"]["persistence"]["repair_count"] == 1

    assert client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers).status_code == 200
    db_session.expire_all()
    recap = db_session.get(RealWorldMission, UUID(mission_id)).recap_payload
    assert not (recap.get("debrief") or recap)["measured"].get("unchecked")
    assert tokens


def test_one_unread_message_holds_the_letter_back_even_when_others_were_read(client, db_session, monkeypatch, tokens):
    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: "Ah bon ? Raconte-moi.")
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(content=_a_grade(UNSEEN_BY_RULES)))
    client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": UNSEEN_BY_RULES, "mode": "chat"}, headers=headers)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(error=TimeoutError("read timed out")))
    client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": SEEN_BY_RULES, "mode": "chat"}, headers=headers)

    assert client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers).status_code == 200

    db_session.expire_all()
    recap = db_session.get(RealWorldMission, UUID(mission_id)).recap_payload
    assert (recap.get("debrief") or recap)["measured"].get("unchecked") is True
    assert tokens == []


def test_the_thread_carries_each_messages_check(client, db_session, monkeypatch):
    """The screen reads the state from the thread, so it stands after a reload."""

    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: "Ah bon ? Raconte-moi.")
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(error=TimeoutError("read timed out")))
    client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": SEEN_BY_RULES, "mode": "chat"}, headers=headers)

    mission = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()["mission"]
    mine, theirs = [turn for turn in mission["turns"] if turn["role"] == "user"], [
        turn for turn in mission["turns"] if turn["role"] == "assistant"
    ]
    assert (mine[0]["check"]["outcome"], mine[0]["check"]["checked_by"]) == ("not_checked", "rules")
    assert mine[0]["check"]["failure"] == "timeout" and mine[0]["check"]["retryable"] is True
    assert all("check" not in turn for turn in theirs), "a reply from the correspondent is not judged"


def test_a_reply_that_only_says_the_message_back_is_no_reply(client, db_session, monkeypatch):
    """D6: judging whether a reply ignores the message needs a model; an echo needs none."""

    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(content=_a_grade(UNSEEN_BY_RULES)))
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: f"  {UNSEEN_BY_RULES.upper()} ")

    body = client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": UNSEEN_BY_RULES, "mode": "chat"}, headers=headers).json()

    assert body["assistant_turn"] == {}
    assert body["outcome"]["reply_state"] == "pending"
    assert missions_module.is_echo_reply("Je viens !", "je viens") is True
    assert missions_module.is_echo_reply("Ah, tu viens ?", "Je viens.") is False
    assert missions_module.is_echo_reply("", "") is False


def test_an_old_row_that_stored_a_rule_partial_pays_nothing(db_session):
    """Letters written before this: the word says «partial», the debug says nobody read it."""

    from tests.test_gold_ledger import NOW
    from tests.test_gold_ledger import _user as gold_user

    user = gold_user(db_session)
    attempt = SimpleNamespace(
        id=uuid4(), verdict="partial", created_at=NOW, mode="writing", answer_payload={},
        correction_payload={"verdict": "partial", "correction_debug": {"fallback_used": True}},
    )
    gold_ledger.record_letter(db_session, user=user, mission=SimpleNamespace(id=uuid4()), attempts=[attempt], now=NOW)
    assert _gold(db_session, user.id) == []


# --- A letter answered inside the day's journey --------------------------------------------------


def _waiting_letter(db, user) -> RealWorldMission:
    mission = RealWorldMission(
        user_id=user.id, status="in_progress", cadence="ad_hoc", mission_type="message", title="Lettre",
        brief="Réponds à la lettre.", selected_concept_ids=[], target_errata_ids=[], target_vocabulary_ids=[],
        source_snapshot={}, objectives=[{"id": "a", "label": "Répondre", "required": True}], prompt_payload={},
        recap_payload={},
    )
    db.add(mission)
    db.commit()
    return mission


def test_a_journey_answer_nobody_read_closes_the_letter_with_no_verdict(db_session, monkeypatch, tokens):
    from tests.test_gold_ledger import _user as gold_user

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = gold_user(db_session)
    mission = _waiting_letter(db_session, user)

    answer_letter_from_journey(
        db_session, user=user, mission_id=mission.id, learner_text=UNSEEN_BY_RULES,
        outcome=TaskOutcome.PARTIALLY_MET.value, check_failure="TimeoutError: read timed out",
    )

    db_session.expire_all()
    row = db_session.scalars(select(RealWorldMissionAttempt).where(RealWorldMissionAttempt.mission_id == mission.id)).one()
    assert (row.verdict, row.score_0_4) == ("unassessed", 0.0)
    assert not verdicts.from_courrier(row.correction_payload).counts
    assert (mission.recap_payload.get("debrief") or mission.recap_payload)["measured"].get("unchecked") is True
    assert tokens == []
    assert _scores(db_session, user) == []


def test_a_journey_answer_the_scene_graded_is_not_taken_for_a_failed_check(db_session, monkeypatch, tokens):
    """The row holds no corrector verdict, only the scene's reading. That is a check that ran."""

    from tests.test_gold_ledger import _user as gold_user

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = gold_user(db_session)
    mission = _waiting_letter(db_session, user)

    answer_letter_from_journey(
        db_session, user=user, mission_id=mission.id, learner_text=UNSEEN_BY_RULES, outcome=TaskOutcome.MET.value,
    )

    db_session.expire_all()
    row = db_session.scalars(select(RealWorldMissionAttempt).where(RealWorldMissionAttempt.mission_id == mission.id)).one()
    assert verdicts.from_courrier(row.correction_payload).counts is True
    assert not (mission.recap_payload.get("debrief") or mission.recap_payload)["measured"].get("unchecked")
    assert tokens, "a letter the scene graded is finished as it always was"
    assert _scores(db_session, user) == [4.0]


# --- La Forge --------------------------------------------------------------------------------


@pytest.mark.parametrize(("client_args", "_call", "_failure"), FAILURES)
def test_a_forge_answer_nobody_read_counts_for_nothing(db_session, monkeypatch, client_args, _call, _failure):
    user, _session, _forge, service, attempt, _view = _free_text_answer(db_session, monkeypatch)
    service.llm_service = _Client(**client_args)

    failed = service.run_ai_review_for_attempt(attempt.id)

    assert failed.verdict == "needs_review" and not failed.score_0_4
    check = verdicts.from_forge(failed.correction_payload, text="", verdict=failed.verdict)
    assert (check.outcome.value, check.counts) == ("not_checked", False)
    assert _scores(db_session, user) == []
    # The local reading wrote a pending entry while the model ran; the failure voids it.
    assert [entry.state for entry in _gold(db_session, user.id)] == ["void"]
    assert db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == "verdict_check_failed", PilotEvent.user_id == user.id)
    ).first()


def test_no_raised_level_is_shown_until_the_answer_is_settled(db_session, monkeypatch):
    """WP-S1: the provisional step still picks the next item. The learner doesn't see it."""

    from app.core.forge import Rung

    _user, _session, forge, service, attempt, view = _free_text_answer(db_session, monkeypatch)
    rule = view["rules"][0]
    assert rule["rung"] == int(Rung.FREE_USE), "the next item is chosen from the step"
    assert rule["shown_rung"] == int(Rung.PRODUCE), "the level printed is the one before it"

    service.run_ai_review_for_attempt(attempt.id)

    settled = forge.view(user=_user, session=_session)["rules"][0]
    assert settled["rung"] == settled["shown_rung"] == int(Rung.PRODUCE)


# --- Le Journal ------------------------------------------------------------------------------


@pytest.fixture()
def journal_ready(db_engine):
    JournalEntry.__table__.create(bind=db_engine, checkfirst=True)


@pytest.mark.parametrize(("client_args", "_call", "_failure"), FAILURES)
def test_a_journal_entry_nobody_read_is_not_stored_as_checked(
    journal_ready, journal_client, db_session, monkeypatch, client_args, _call, _failure  # noqa: F811
):
    down = _FakeChecker()
    forced = _Client(**client_args)
    down.generate_error_detection = forced.generate_error_detection
    monkeypatch.setattr(journal_module._JournalCorrector, "_get_llm_service", lambda self: down)
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]

    response = journal_client.post(f"/api/v1/journal/{entry_id}/write", headers=headers, json={"text": UNSEEN_BY_RULES})

    assert response.status_code == 200, response.text
    assert forced.calls >= 1
    db_session.expire_all()
    entry = db_session.get(JournalEntry, UUID(entry_id))
    assert entry.assessment_status == "unavailable", "a row no model read was stored as «checked»"
    assert entry.vocabulary_credit["status"] == "skipped"
    check = verdicts.from_journal(entry.correction, text=UNSEEN_BY_RULES)
    assert (check.outcome.value, check.counts) == ("not_checked", False)


# --- The scene (the lanes and the season page fail for real in test_wp87_lanes, test_season_one) -


def _the_scene_reply_pays(db, *, check_failure: str | None) -> list[GoldLedgerEntry]:
    from dataclasses import replace

    from tests.test_gold_ledger import _journey, _pay_reply, _reply
    from tests.test_gold_ledger import _user as gold_user

    user = gold_user(db)
    journey, steps = _journey("respond")
    _pay_reply(db, user, journey, steps[0], replace(_reply(), check_failure=check_failure))
    return _gold(db, user.id)


def test_a_scene_reply_nobody_read_pays_nothing(db_session):
    assert _the_scene_reply_pays(db_session, check_failure=None), "the control: a read reply pays"
    assert _the_scene_reply_pays(db_session, check_failure="TimeoutError: read timed out") == []


def test_the_season_tutor_that_failed_is_not_a_tutor_that_found_nothing():
    from app.services import story_lanes

    assert not story_lanes.MarginFailure("TimeoutError: x"), "callers that only ask «is there a correction?» still work"
    assert story_lanes.split_margin(story_lanes.MarginFailure("TimeoutError: x")) == (None, "TimeoutError: x")
    assert story_lanes.split_margin(None) == (None, None)


# --- The level ---------------------------------------------------------------------------------


def test_the_level_average_reads_only_what_was_checked(db_session):
    from app.db.models.graphic_novel import GraphicNovelAttempt, GraphicNovelScene
    from tests.test_gold_ledger import _user as gold_user

    user = gold_user(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], quote_payload={}, recap_payload={})
    mission = RealWorldMission(
        user_id=user.id, status="in_progress", cadence="ad_hoc", mission_type="message", title="L", brief="B",
        selected_concept_ids=[], target_errata_ids=[], target_vocabulary_ids=[], source_snapshot={}, objectives=[],
        prompt_payload={}, recap_payload={},
    )
    scene = GraphicNovelScene(user_id=user.id, title="S", brief="B", status="ready", cache_key=str(uuid4()), prompt_version="test", image_model="test", image_quality="test")
    db_session.add_all([session, mission, scene])
    db_session.flush()

    def forge(verdict, score, **payload):
        db_session.add(
            AtelierAttempt(
                atelier_session_id=session.id, user_id=user.id, concept_id=None, round="sentence", mode="sentence",
                exercise_id=str(uuid4()), prompt_payload={}, answer_payload={},
                correction_payload={"verdict": verdict, **payload}, verdict=verdict, score_0_4=score,
            )
        )

    def letter(verdict, score, **payload):
        db_session.add(
            RealWorldMissionAttempt(
                mission_id=mission.id, user_id=user.id, mode="writing", answer_payload={},
                correction_payload={"verdict": verdict, **payload}, verdict=verdict, score_0_4=score,
            )
        )

    def panel(verdict, score, **payload):
        db_session.add(
            GraphicNovelAttempt(
                scene_id=scene.id, user_id=user.id, task_id=str(uuid4()), task_type="short_sentence", answer_payload={},
                correction_payload={"verdict": verdict, **payload}, verdict=verdict, score_0_4=score,
            )
        )

    # Read, by a key or a model.
    forge("correct", 4.0, assessment_status="checked")
    letter("partial", 3.0, correction_debug={"fallback_used": False})
    panel("branch", 4.0)
    # Never read.
    forge("needs_review", 0.0, assessment_status="unavailable")
    forge("partial", 2.0, assessment_status="provisional")
    forge("accepted", 3.0, correction_debug={"fallback_used": True}, corrected_answer="x")  # an old row
    letter("partial", 3.0, correction_debug={"fallback_used": True})  # an old row
    letter("unassessed", 0.0, correction_debug={"fallback_used": True})
    panel("needs_review", 0.0)
    panel("unassessed", 0.0)
    db_session.flush()

    assert sorted(_scores(db_session, user)) == [3.0, 4.0, 4.0]
