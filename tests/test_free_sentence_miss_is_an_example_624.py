"""#624: a missed free sentence is never «rewritten» into the model sentence.

Walk 2026-11-09, recall step 8 of 8, «Écris une phrase à toi qui utilise : Deux
pronoms ensemble». The learner wrote «Les photos de ma grand-mère, je lui les envoie
demain.» and the miss card drew «~~Les photos…~~ → Ton livre ? Je te le rends demain,
et je lui en parle.»: the rule card's example sentence shown as the fix of a sentence
about photos.

A free sentence has no single right answer; the model sentence is one example of
the rule, not the learner's sentence made right. The correction carries that
relation (``kind == "example"``), the same way a wrong tap carries ``pick`` and a
wrong meaning ``meaning`` (#240, #167), so the screen draws no strike-through and
no arrow, and nothing files «learner sentence -> model sentence» as an error to
repair later.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import grammar_items, journey_learning
from app.services.daily_journey import DailyJourneyService
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    TaskOutcome,
)
from tests.test_wp129_practice import brief, concept

UNIT = "FR2_B11_DOUBLE_PRONOUNS"
LEARNER = "Les photos de ma grand-mère, je lui les envoie demain."
MODEL = "Ton livre ? Je te le rends demain, et je lui en parle."


def _miss(language: str, text: str = LEARNER):
    task = grammar_items.free_sentence_item(brief(UNIT, 7), language=language)
    assert task is not None and task.solution_fr == MODEL
    db = SimpleNamespace(get=lambda _cls, _id: concept(UNIT, 7))
    user = SimpleNamespace(native_language=language, ui_language=language)
    result = journey_learning.evaluate_recall(
        db,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        assistance=AssistanceLevel.NONE,
    )
    return task, result


@pytest.mark.parametrize("language", ["fr", "de", "en"])
def test_a_missed_free_sentence_shows_the_model_as_an_example_not_as_its_fix(language: str) -> None:
    _task, result = _miss(language)
    assert result.outcome is TaskOutcome.NOT_YET
    assert result.correction is not None
    assert result.correction.corrected_fr == MODEL, "the model is still shown"
    # The screen draws «A → B» for an edit only: the model must not be one.
    assert result.correction.kind == "example", (
        f"the learner's sentence is shown rewritten into the model: "
        f"{result.correction.span_fr!r} -> {result.correction.corrected_fr!r} ({result.correction.kind})"
    )
    public = DailyJourneyService._public_correction(result.correction, LEARNER)
    assert public is not None and public.kind == "example"
    assert public.corrected_fr == MODEL


def test_the_rule_stays_the_reason_of_a_missed_free_sentence() -> None:
    _task, result = _miss("fr")
    assert result.correction is not None
    assert "le lui donne" in result.correction.note_native


def _filed(db_session, correction) -> int:
    from uuid import uuid4

    from app.db.models.error import UserError
    from app.services.journey_contracts import ResponseEvaluation
    from app.services.journey_learning import (
        JOURNEY_SOURCE_TYPE,
        apply_learning_evidence,
        ensure_journey_learning_session,
    )
    from tests.test_wp_l1_journey_grammar import _user

    user = _user(db_session)
    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=uuid4(),
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.NOT_YET,
            assistance=AssistanceLevel.NONE,
            observations=[],
            correction=correction,
        ),
        modality=InputMode.TEXT,
    )
    return (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id, UserError.source_type == JOURNEY_SOURCE_TYPE)
        .count()
    )


def test_a_model_example_is_not_filed_as_an_error_to_repair(db_session) -> None:
    """«Photos sentence -> model sentence» is not French the learner got wrong:
    drilled later it would ask them to rewrite one sentence into another."""
    from app.services.journey_contracts import Correction

    edit = Correction(span_fr="au le café", corrected_fr="au café", note_native="Au = à + le.")
    assert _filed(db_session, edit) == 1, "control: a real edit is still filed"
    example = Correction(span_fr=LEARNER, corrected_fr=MODEL, note_native="Ordre.", kind="example")
    assert _filed(db_session, example) == 0
