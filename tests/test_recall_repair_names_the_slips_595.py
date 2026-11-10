"""#595 — a recall repair names what differs, never the word the learner got right.

Day 1 the learner wrote «Nous somes à l’hôtel avec Lila.»; day 2 recall asks them to
write it right: the item's part is «sommes» and its whole sentence is the key. The
walk typed «Nous sommes a l hotel avec Lila.» (the rule's word fixed, accents and
apostrophe missing) and read «→ sommes»: the fix shown was the stored part, built apart
from the verdict. The correction is now built from the same reading as the verdict
(root cause #174: the acceptance contract and the shown fix were made separately).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_learning import evaluate_recall

SOURCE = "Nous somes à l’hôtel avec Lila."
WHOLE = "Nous sommes à l’hôtel avec Lila."


def _user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"repair-595-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="beginner",
    )
    db.add(user)
    db.commit()
    return user


def _task(*, keys: list[str], task_type: str = "short_answer") -> RecallTask:
    return RecallTask(
        task_type=task_type,
        instruction_native="Schreib richtig, was du gesagt hast.",
        prompt_fr=SOURCE,
        options=[],
        target=TargetRef(kind=TargetKind.ERROR, id="err-somes", label_fr="sommes"),
        optional=False,
        accepted_answers=keys,
        hint_native="Es ist 1 Wort lang und beginnt mit „s“.",
        solution_fr="sommes",
        source_fr=SOURCE,
        slip_fr="somes",
    )


def _grade(db: Session, text: str, keys: list[str]):
    return evaluate_recall(
        db,
        user=_user(db),
        task=_task(keys=keys),
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        assistance=AssistanceLevel.NONE,
    )


KEYS = [["sommes", WHOLE], [WHOLE, "sommes"], ["sommes"]]
KEY_IDS = ["part_then_line", "line_then_part", "part_only"]


@pytest.mark.parametrize("keys", KEYS, ids=KEY_IDS)
@pytest.mark.parametrize("typed", ["Nous sommes à l'hôtel avec Lila.", "Nous sommes à l’hôtel avec Lila."], ids=["straight", "curly"])
def test_whole_line_met_whatever_key_holds(db_session, keys, typed):
    assert _grade(db_session, typed, keys).outcome is TaskOutcome.MET


@pytest.mark.parametrize("keys", KEYS, ids=KEY_IDS)
@pytest.mark.parametrize("typed", ["Nous sommes a l hotel avec Lila.", "Nous sommes a l'hotel avec Lila."], ids=["spaced", "apostrophe"])
def test_part_right_other_slips_named(db_session, keys, typed):
    evaluation = _grade(db_session, typed, keys)
    assert evaluation.outcome is TaskOutcome.NOT_YET, "«a» is not «à»: a grammar accent"
    correction = evaluation.correction
    assert correction is not None
    # The fix is the whole line, never the learner's own right word...
    assert correction.corrected_fr != "sommes", correction
    assert "à" in correction.corrected_fr and "hôtel" in correction.corrected_fr, correction
    # ...and the note says what differs (the item's «1 word long» hint would contradict it).
    assert "1 Wort" not in correction.note_native, correction
    assert "à" in correction.note_native, correction


@pytest.mark.parametrize("keys", KEYS, ids=KEY_IDS)
def test_spelling_accent_alone_met(db_session, keys):
    # Only «hotel» for «hôtel» and a spaced elision differ: a spelling accent (#562).
    assert _grade(db_session, "Nous sommes à l hotel avec Lila.", keys).outcome is TaskOutcome.MET


@pytest.mark.parametrize("keys", KEYS, ids=KEY_IDS)
def test_part_alone_still_right(db_session, keys):
    assert _grade(db_session, "sommes", keys).outcome is TaskOutcome.MET
    assert _grade(db_session, "Nous sommes", keys).outcome is TaskOutcome.MET


@pytest.mark.parametrize("keys", KEYS, ids=KEY_IDS)
def test_wrong_part_corrected_as_part(db_session, keys):
    correction = _grade(db_session, "somme", keys).correction
    assert correction is not None
    assert (correction.span_fr, correction.corrected_fr) == ("somme", "sommes")


@pytest.mark.parametrize("keys", KEYS, ids=KEY_IDS)
def test_wrong_word_corrected_on_whole_line(db_session, keys):
    correction = _grade(db_session, "Nous êtes à l'hôtel avec Lila.", keys).correction
    assert correction is not None
    assert correction.corrected_fr == "Nous sommes à l'hôtel avec Lila."


def test_a_missed_rewrite_keeps_its_hint_as_the_why(db_session: Session) -> None:
    """#606 walk: only a part-keyed repair drops «It is 1 word long». A rewrite's hint
    is about the sentence, and without it the miss has no why (tests/walk_checks.py)."""

    hint = "Schreib den Satz mit «elle»."
    task = RecallTask(
        task_type="transform",
        instruction_native="Schreib den Satz um.",
        prompt_fr="Il a chaud.",
        options=[],
        target=TargetRef(kind=TargetKind.ERROR, id="err-rewrite", label_fr="elle"),
        optional=False,
        accepted_answers=["Elle a chaud."],
        hint_native=hint,
        solution_fr="Elle a chaud.",
        source_fr="Il a chaud.",
    )
    result = evaluate_recall(
        db_session,
        user=_user(db_session),
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Il ont chaud."),
        assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is not TaskOutcome.MET
    assert result.correction is not None
    assert hint in (result.correction.note_native or "")
