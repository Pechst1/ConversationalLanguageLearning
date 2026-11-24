"""#1045: La Forge's repair box refused the corrected line without its accent with a bare
«Not quite — try the line again.»

Live walk 24 Nov 2026 (A1.1, day 42), La Forge item 4/4 (review «il y a»). The learner
wrote «Il y a du pain, du confiture et un cafe chaud.»; the sheet listed «du → de la
confiture» and «cafe → café». The corrected line retyped without the «é» was «Not
quite», with nothing to say that only the accent was missing. The repair judge
(``_repair_is_right``) asked the one contract (``judge_repair``), which names the accent
(``note="accent"``, «cafe» for «café»), and kept only its yes or no.

The repair now keeps what the judge said: a missing accent the correction asked for is
still a miss, named («café»); an accent the learner had right in their own line and only
dropped while copying is accepted, with the same note.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.user import User
from app.services.atelier import AtelierCorrectionService
from app.services.forge_grading import strip_accents

LEARNER = "Il y a du pain, du confiture et un cafe chaud."
CORRECTED = "Il y a du pain, de la confiture et un café chaud."


def _miss(db_session, learner: str = LEARNER, corrected: str = CORRECTED, errata: list | None = None):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="sentence", mode="free",
        exercise_id="forge-1045", verdict="partial", score_0_4=2,
        answer_payload={"text": learner},
        prompt_payload={},
        correction_payload={
            "assessment_status": "checked",
            "verdict": "partial",
            "corrected_answer": corrected,
            "errata": errata if errata is not None else [
                {"learner_text": "du confiture", "corrected_target": "de la confiture", "task_error_type": "grammar"},
                {"learner_text": "cafe", "corrected_target": "café", "task_error_type": "orthography"},
            ],
        },
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def _repair(db_session, attempt, typed: str) -> dict:
    updated = AtelierCorrectionService(db_session).record_micro_repair(attempt=attempt, text=typed, erratum_index=0)
    return updated.correction_payload["micro_repairs"]["0"]


def test_the_corrected_line_without_its_accents_names_the_accent(db_session):
    record = _repair(db_session, _miss(db_session), strip_accents(CORRECTED))
    said = " ".join(str(record.get(key) or "") for key in ("note", "expected_word"))
    accepted_with_note = record["status"] == "ok" and record.get("note") == "accent"
    assert accepted_with_note or "café" in said, (
        f"«{strip_accents(CORRECTED)}» was «{record['status']}» with nothing about the accent: {record}"
    )
    # The accent was one of the fixes: it is still a miss, and it says which word.
    assert record["status"] == "no"
    assert record.get("note") == "accent" and record.get("expected_word") == "café", record


def test_cafe_for_cafe_with_its_accent_names_cafe(db_session):
    typed = "Il y a du pain, de la confiture et un cafe chaud."
    record = _repair(db_session, _miss(db_session), typed)
    assert record["status"] == "no"
    assert record.get("expected_word") == "café" and record.get("learner_word") == "cafe", record


def test_an_accent_the_learner_had_right_and_dropped_in_the_copy_is_accepted_with_a_note(db_session):
    learner = "Il y a du pain, du confiture et un café chaud."
    attempt = _miss(
        db_session,
        learner=learner,
        errata=[{"learner_text": "du confiture", "corrected_target": "de la confiture", "task_error_type": "grammar"}],
    )
    record = _repair(db_session, attempt, "Il y a du pain, de la confiture et un cafe chaud.")
    assert record["status"] == "ok", record
    assert record.get("note") == "accent" and record.get("expected_word") == "café", record


@pytest.mark.parametrize(
    "typed",
    [CORRECTED, "il y a du pain, de la confiture et un café chaud"],
)
def test_the_right_line_is_right_with_nothing_to_say(db_session, typed):
    record = _repair(db_session, _miss(db_session), typed)
    assert record["status"] == "ok"
    assert not record.get("note"), record


def test_a_wrong_word_is_still_a_bare_miss(db_session):
    record = _repair(db_session, _miss(db_session), "Il y a du pain, du confiture et un café chaud.")
    assert record["status"] == "no"
    assert record.get("note") != "accent", record
