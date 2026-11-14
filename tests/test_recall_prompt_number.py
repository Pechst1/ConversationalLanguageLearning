"""#746: «How do you say "eggs" in French?» is answered by the plural.

Live walk 13 Nov (day 32, A1.1): «les oeufs» was «Not yet» with «Same word, different
form: «oeuf», not «oeufs»», because the item's one stored string is «un œuf» and the
accept-list was widened from that string alone, never from the number the prompt
asks for (#174). The appeal upheld it six seconds later.
"""
from __future__ import annotations

import pytest

from app.services import journey_planner as planner
from app.services.answer_acceptance import feedback_note, judge
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_learning import evaluate_recall
from tests.test_journey_planner import _brief

EGGS = TargetRef(kind=TargetKind.VOCABULARY, id="word-oeuf", label_fr="un œuf", label_native="eggs")


def _task(target: TargetRef = EGGS):
    task = planner.build_recall_task(target=target, scenario=_brief(), affordances=[], optional=False)
    assert task is not None and task.task_type == "short_answer"
    assert task.instruction_native == f'How do you say "{target.label_native}" in French?'
    return task


@pytest.mark.parametrize("answer", ["les oeufs", "les œufs", "des œufs", "œufs", "un œuf"])
def test_the_plural_answers_a_plural_prompt(db_session, answer: str) -> None:
    task = _task()
    verdict = evaluate_recall(
        db_session,
        user=None,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=answer),
        assistance=AssistanceLevel.NONE,
    )
    assert verdict.outcome is TaskOutcome.MET, f"«{answer}» for «eggs» was judged {verdict.outcome.value}"
    assert verdict.correction is None, f"«{answer}» got a correction: {verdict.correction}"


@pytest.mark.parametrize("answer", ["les oeufs", "les œufs", "des œufs"])
def test_no_form_note_against_the_prompts_number(answer: str) -> None:
    from app.services.journey_learning import _accepted_answers

    verdict = judge(answer, _accepted_answers(_task()), article_optional=True)
    note = feedback_note(verdict, "en")
    assert verdict.correct, f"«{answer}»: {note}"
    assert verdict.note != "form", f"«{answer}» was told: {note}"


def test_a_plural_is_still_wrong_for_a_singular_prompt(db_session) -> None:
    """The widening follows the prompt: «egg» does not open «les œufs»."""

    task = _task(TargetRef(kind=TargetKind.VOCABULARY, id="word-oeuf", label_fr="un œuf", label_native="egg"))
    verdict = evaluate_recall(
        db_session,
        user=None,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="les œufs"),
        assistance=AssistanceLevel.NONE,
    )
    assert verdict.outcome is not TaskOutcome.MET


def test_french_plurals() -> None:
    from app.services.answer_acceptance import plural_noun_answers

    assert set(plural_noun_answers("un œuf")) == {"les œufs", "des œufs", "œufs"}
    assert "les journaux" in plural_noun_answers("le journal")
    assert "des gâteaux" in plural_noun_answers("un gâteau")
    assert "les bus" in plural_noun_answers("le bus")
    assert plural_noun_answers("je mange un œuf") == []
