"""WP-125A — letter omissions are not language errors (owner decision 6, 2026-10-04).

A suggested word the learner did not use in a Courrier letter is an unobserved
learning opportunity: no erratum, no lower verdict, no lapse, no schedule change.
A genuinely wrong use of the word, or an omitted communicative requirement, still
counts. Replay is idempotent, and a German learner reads no English.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import story_correspondence as courrier
from app.services.learner_copy import learner_text
from app.services.news_service import NewsService
from app.services.vocabulary_credit import VocabularyCreditService

WITH_WORD = "Bonjour, je viens constater le problème demain matin et je vous écris ensuite."
WITHOUT_WORD = "Bonjour, je viens voir le problème demain matin et je vous écris ensuite."
WRONG_USE = "Bonjour, je viens feststellen le problème demain matin et je vous écris ensuite."

_PROGRESS_FIELDS = (
    "stability", "difficulty", "scheduled_days", "reps", "lapses", "state", "phase",
    "interval_days", "due_at", "next_review_date", "correct_count", "incorrect_count",
    "times_seen", "times_used_correctly", "times_used_incorrectly",
)


async def _no_news(self, interests=None, limit=3, prefer_paris=True):  # noqa: ARG001
    return {"mode": "none", "digest": "", "items": [], "fetched_at": None, "source_policy": "test"}


def _grader(*, communicative_met: bool):
    """A stand-in corrector: grades the letter's non-vocabulary objectives and
    finds no language error — the only variable left is the suggested word."""

    def _llm_correction(self, *, user, mission, text, mode):  # noqa: ARG001
        progress = [
            {"id": item["id"], "label": item.get("label") or "", "met": communicative_met, "note": "ok"}
            for item in mission.objectives or []
            if not str(item.get("id") or "").startswith("vocabulary_")
        ]
        return {
            "verdict": "accepted" if communicative_met else "needs_revision",
            "score_0_4": 4 if communicative_met else 1,
            "corrected_answer": text,
            "objective_progress": progress,
            "concept_hits": [],
            "missing_targets": [],
            "errata": [],
            "vocabulary_links": [],
            "_fallback_used": False,
            "_model": "stub",
        }

    return _llm_correction


def _learner(client: TestClient, db_session, *, native: str = "en") -> tuple[User, dict[str, str]]:
    email = f"{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "wp125a-secure", "target_language": "fr", "native_language": native},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "wp125a-secure"}).json()["access_token"]
    user = db_session.get(User, UUID(str(decode_token(token)["sub"])))
    assert user is not None
    return user, {"Authorization": f"Bearer {token}"}


def _word(db_session) -> VocabularyWord:
    word = VocabularyWord(
        language="fr", word="constater", normalized_word="constater", frequency_rank=80,
        german_translation="feststellen", english_translation="to notice",
        example_sentence="Je constate que le rendez-vous a changé.",
        direction="fr_to_de", deck_name="French 5000", is_anki_card=True,
    )
    db_session.add(word)
    db_session.commit()
    return word


def _letter(client: TestClient, headers: dict[str, str], word: VocabularyWord) -> str:
    response = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": "ad_hoc", "preferred_vocabulary_ids": [word.id], "use_news": False},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    mission = response.json()["mission"]
    assert any(item.get("word_id") == word.id for item in mission.get("target_vocabulary") or [])
    return mission["id"]


def _answer(client: TestClient, headers: dict[str, str], mission_id: str, text: str) -> tuple[dict, dict]:
    submit = client.post(f"/api/v1/missions/{mission_id}/submit", json={"text": text, "mode": "writing"}, headers=headers)
    assert submit.status_code == 200, submit.text
    complete = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers)
    assert complete.status_code == 200, complete.text
    return submit.json(), complete.json()["recap"]


def _snapshot(db_session, user: User, word: VocabularyWord) -> dict[str, Any] | None:
    db_session.expire_all()
    row = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id)
        .one_or_none()
    )
    return None if row is None else {field: getattr(row, field) for field in _PROGRESS_FIELDS}


def _vocab_errata(db_session, user: User, word: VocabularyWord) -> list[UserError]:
    db_session.expire_all()
    return [
        row for row in db_session.query(UserError).filter(UserError.user_id == user.id).all()
        if getattr(row, "linked_word_id", None) == word.id or (getattr(row, "source_payload", None) or {}).get("word_id") == word.id
    ]


def test_equivalent_successful_letters_get_the_same_verdict_with_or_without_the_word(
    client: TestClient, db_session, monkeypatch
):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)
    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _grader(communicative_met=True))
    word = _word(db_session)
    results = {}
    for label, text in (("with", WITH_WORD), ("without", WITHOUT_WORD)):
        _, headers = _learner(client, db_session)
        submit, recap = _answer(client, headers, _letter(client, headers, word), text)
        results[label] = (submit["correction"], recap)

    for label, (correction, recap) in results.items():
        assert correction["verdict"] == "accepted", label
        assert correction["errata"] == [], label
        assert not any(str(t["external_id"]).startswith("VOCAB_") for t in correction["missing_targets"]), label
        assert recap["outcome"] == "kept", label
    assert results["with"][1]["branch_outcome"]["label"] == results["without"][1]["branch_outcome"]["label"]
    assert results["with"][1]["measured"]["objectives_met"] == results["without"][1]["measured"]["objectives_met"]
    unused = next(
        item for item in results["without"][1]["objective_results"] if item["id"] == f"vocabulary_{word.id}"
    )
    assert unused["met"] is False and unused["observed"] is False


def test_omission_opens_no_erratum_no_lapse_and_keeps_the_schedule(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)
    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _grader(communicative_met=True))
    word = _word(db_session)
    user, headers = _learner(client, db_session)
    # A word already in review, due in nine days.
    progress = VocabularyCreditService(db_session).progress_service.record_context_credit(
        user=user, word=word, event_type="produced_correct", now=datetime.now(UTC) - timedelta(days=2)
    )
    progress.due_at = datetime.now(UTC) + timedelta(days=9)
    db_session.add(progress)
    db_session.commit()
    before = _snapshot(db_session, user, word)

    submit, recap = _answer(client, headers, _letter(client, headers, word), WITHOUT_WORD)

    events = [e for e in submit["correction"]["vocabulary_events"] if e["word_id"] == word.id]
    assert [e["event_type"] for e in events] == ["unused_target"]
    assert events[0]["policy"] == "letter-omission-v1"
    assert submit["errata"] == []
    assert _vocab_errata(db_session, user, word) == []
    assert recap["vocabulary_credit"]["missed_target"] == 0
    assert recap["vocabulary_credit"]["produced_incorrect"] == 0
    assert recap["vocabulary_credit"]["unobserved"] == 1
    assert recap["measured"]["repairs"] == 0
    assert _snapshot(db_session, user, word) == before


def test_omission_of_a_new_word_creates_no_progress_row(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)
    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _grader(communicative_met=True))
    word = _word(db_session)
    user, headers = _learner(client, db_session)
    _answer(client, headers, _letter(client, headers, word), WITHOUT_WORD)
    assert _snapshot(db_session, user, word) is None


def test_a_missed_target_from_a_letter_is_read_as_unobserved_by_the_credit_service(db_session):
    """Defence in depth: an older payload or a provider's own ``missed_target``
    for a mission still charges no lapse and opens no erratum."""

    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="x", native_language="de")
    db_session.add(user)
    word = _word(db_session)
    result = VocabularyCreditService(db_session).apply(
        user=user, word=word, event_type="missed_target", source_type="mission"
    )
    assert result.credit_kind == "unobserved"
    assert result.erratum_id is None
    assert _snapshot(db_session, user, word) is None


def test_wrong_use_is_still_flagged(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)
    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _grader(communicative_met=True))
    word = _word(db_session)
    user, headers = _learner(client, db_session, native="de")

    submit, _recap = _answer(client, headers, _letter(client, headers, word), WRONG_USE)

    correction = submit["correction"]
    assert correction["verdict"] == "partial"
    assert any(e["word_id"] == word.id and e["event_type"] == "produced_incorrect" for e in correction["vocabulary_events"])
    assert any(item.get("linked_word_id") == word.id for item in correction["errata"])
    assert _vocab_errata(db_session, user, word)
    snapshot = _snapshot(db_session, user, word)
    assert snapshot is not None and snapshot["times_used_incorrectly"] >= 1


def test_an_omitted_communicative_requirement_still_decides_the_outcome(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)
    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _grader(communicative_met=False))
    word = _word(db_session)
    outcomes = {}
    for label, text in (("with", WITH_WORD), ("without", WITHOUT_WORD)):
        _, headers = _learner(client, db_session)
        _, recap = _answer(client, headers, _letter(client, headers, word), text)
        outcomes[label] = recap["outcome"]
    assert outcomes["without"] != "kept"
    # The suggested word neither rescues nor sinks the communicative verdict.
    assert outcomes["with"] == outcomes["without"]


def test_outcome_from_objectives_ignores_suggested_words():
    objectives = [
        {"id": "real_world_task", "required": True, "kind": "communication"},
        {"id": "vocabulary_7", "required": False, "kind": "vocabulary"},
    ]
    kept = {"real_world_task": {"met": True}, "vocabulary_7": {"met": False, "observed": False}}
    assert courrier.outcome_from_objectives(objectives=objectives, progress_by_id=kept) == "kept"
    for vocab_met in (True, False):
        progress = {"real_world_task": {"met": False}, "vocabulary_7": {"met": vocab_met}}
        assert courrier.outcome_from_objectives(objectives=objectives, progress_by_id=progress) == "missed"


def test_journey_answer_marks_an_unused_word_unobserved_in_the_learners_language():
    rows = courrier.objective_progress_from_journey(
        objectives=[
            {"id": "real_world_task", "required": True, "label": "Répondre"},
            {"id": "vocabulary_7", "required": False, "kind": "vocabulary", "word_id": 7,
             "label": "Placer « constater » naturellement"},
        ],
        outcome="met",
        language="de",
    )
    vocab = next(row for row in rows if row["id"] == "vocabulary_7")
    assert vocab["observed"] is False
    assert vocab["note"] == learner_text("mission.vocabulary_unused", "de", word="constater")


def test_replay_is_idempotent(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)
    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _grader(communicative_met=True))
    word = _word(db_session)
    user, headers = _learner(client, db_session)
    mission_id = _letter(client, headers, word)

    first = client.post(f"/api/v1/missions/{mission_id}/submit", json={"text": WITHOUT_WORD, "mode": "writing"}, headers=headers)
    again = client.post(f"/api/v1/missions/{mission_id}/submit", json={"text": WITHOUT_WORD, "mode": "writing"}, headers=headers)
    other = client.post(
        f"/api/v1/missions/{mission_id}/submit",
        json={"text": "Je confirme aussi que je passe vers dix heures demain.", "mode": "writing"},
        headers=headers,
    )
    assert first.status_code == again.status_code == other.status_code == 200
    assert len(again.json()["mission"]["attempts"]) == 1
    # One unobserved event per word per letter, whatever the number of drafts.
    unused = [
        event
        for response in (first, other)
        for event in response.json()["correction"]["vocabulary_events"]
        if event["word_id"] == word.id and event["event_type"] == "unused_target"
    ]
    assert len(unused) == 1

    done = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers)
    redo = client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers)
    assert done.status_code == redo.status_code == 200
    assert done.json()["recap"]["outcome"] == redo.json()["recap"]["outcome"] == "kept"
    assert done.json()["recap"]["vocabulary_credit"] == redo.json()["recap"]["vocabulary_credit"]
    assert _vocab_errata(db_session, user, word) == []
    assert _snapshot(db_session, user, word) is None

    # Re-processing the stored correction writes nothing new either.
    from app.db.models.mission import RealWorldMission

    db_session.expire_all()
    mission = db_session.get(RealWorldMission, UUID(mission_id))
    service = missions_module.MissionCorrectionService(db_session, llm_service=None)
    for attempt in mission.attempts:
        assert service.persist_errata(
            user=user, mission=mission, correction=attempt.correction_payload, mode="writing", source_id=str(attempt.id)
        ) == []
    assert _vocab_errata(db_session, user, word) == []
    assert _snapshot(db_session, user, word) is None


def test_a_german_learner_reads_no_english(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)
    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _grader(communicative_met=True))
    word = _word(db_session)
    _, headers = _learner(client, db_session, native="de")

    unused, _ = _answer(client, headers, _letter(client, headers, word), WITHOUT_WORD)
    _, headers = _learner(client, db_session, native="de")
    wrong, _ = _answer(client, headers, _letter(client, headers, word), WRONG_USE)
    _, headers = _learner(client, db_session, native="de")
    used, _ = _answer(client, headers, _letter(client, headers, word), WITH_WORD)

    def _note(submit: dict) -> str:
        return next(
            item["note"] for item in submit["correction"]["objective_progress"] if item["id"] == f"vocabulary_{word.id}"
        )

    assert _note(unused) == learner_text("mission.vocabulary_unused", "de", word="constater")
    assert _note(used) == learner_text("mission.vocabulary_used", "de", word="constater")
    erratum = next(item for item in wrong["correction"]["errata"] if item.get("linked_word_id") == word.id)
    assert erratum["why_wrong"] == learner_text(
        "mission.vocabulary_translation_why", "de", word="constater", meaning="feststellen"
    )
    assert erratum["repair_hint"] == learner_text("mission.vocabulary_translation_hint", "de", word="constater")
    shown = json.dumps(
        [unused["correction"]["objective_progress"], wrong["correction"]["errata"], used["correction"]["objective_progress"]],
        ensure_ascii=False,
    )
    for english in ("You used", "Try to work", "Use target word", "the mission target", "did not appear"):
        assert english not in shown


def test_a_partly_met_journey_turn_is_partial_with_or_without_the_word():
    objectives = [
        {"id": "real_world_task", "required": True, "label": "Répondre"},
        {"id": "vocabulary_7", "required": False, "kind": "vocabulary", "word_id": 7,
         "label": "Placer « constater » naturellement"},
    ]
    outcomes = set()
    for produced in ((), ("vocabulary:7",)):
        rows = courrier.objective_progress_from_journey(
            objectives=objectives, outcome="partially_met", produced_target_ids=produced
        )
        outcomes.add(courrier.outcome_from_objectives(
            objectives=objectives, progress_by_id={row["id"]: row for row in rows}
        ))
    assert outcomes == {"partial"}
