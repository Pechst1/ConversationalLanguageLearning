"""#579: a recall answer has one verdict, and the note agrees with it.

Walk 7 Nov: «une letre» for «letter» (key «la lettre», article optional) showed
«Not yet» with «Right — small typo: «lettre».» and the fix «une letre → la lettre».
`evaluate_recall` decided `is_correct` with one call of the acceptance contract
and took the note from a second call with other options. One answer, one `judge`.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

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


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"one-verdict-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _letter_task() -> RecallTask:
    return RecallTask(
        task_type="short_answer",
        instruction_native="Type the French word.",
        prompt_fr="How do you say «letter» in French?",
        options=[],
        # The gloss shown has no article, the key has one: the article is optional.
        target=TargetRef(kind=TargetKind.VOCABULARY, id="letter", label_fr="la lettre", label_native="letter"),
        optional=False,
        accepted_answers=["la lettre"],
        solution_fr="la lettre",
    )


def _evaluate(db_session, user, text: str):
    return evaluate_recall(
        db_session,
        user=user,
        task=_letter_task(),
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        assistance=AssistanceLevel.NONE,
    )


@pytest.mark.parametrize("text", ["une letre", "une lettre", "la letre", "lettre"], ids=range(4))
def test_met(db_session, text):
    assert _evaluate(db_session, _user(db_session), text).outcome is TaskOutcome.MET


def test_typo_note(db_session):
    evaluation = _evaluate(db_session, _user(db_session), "une letre")
    assert evaluation.outcome is TaskOutcome.MET
    assert evaluation.slip_kind == "typo"
    assert "lettre" in (evaluation.slip_note_native or "")
    correction = evaluation.correction
    assert correction is None or "une" not in correction.span_fr.split(), (
        "a hit offers no fix that rewrites the learner's right «une»"
    )


@pytest.mark.parametrize(
    "text",
    [
        "une letre", "la letre", "lettre", "letre", "le lettre", "une lettre", "un lettre", "l'lettre",
        "une lètre", "la lettré", "la lettres", "une maison", "une lettr", "les lettres", "la leetre",
    ],
    ids=range(15),
)
def test_no_right(db_session, text):
    evaluation = _evaluate(db_session, _user(db_session), text)
    if evaluation.outcome is TaskOutcome.NOT_YET and evaluation.correction is not None:
        note = evaluation.correction.note_native or ""
        assert not note.startswith("Right"), f"«Not yet» must not open with «Right»: {note!r}"
