"""#174: a right answer is judged against one stored string. This stage: the journey's
typed recall shares La Forge's list of right answers.

Walk 31 Oct (a2-en, day 1, pre-scene recall): «How do you say "flat, apartment" in
French?» refused «un appart», and the fix read «un appart → appartement», dropping the
article. La Forge already took «un appart» (``answer_acceptance.widened_answers``, #380);
the journey graded the same word against its one stored key. Every typed recall now uses
that list, and a bare noun's fix keeps the article the learner gave, in the noun's gender.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import journey_learning
from app.services import journey_planner as planner
from app.services.answer_acceptance import noun_with_learner_article, widened_answers
from app.services.atelier import _accepted_answers as forge_accepted_answers
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from tests.test_journey_planner import _brief

ENGLISH_A2 = SimpleNamespace(native_language="en", cefr_estimate="A2.1", proficiency_level="A2")


def _target(label_fr: str, label_native: str | None, kind: TargetKind = TargetKind.VOCABULARY) -> TargetRef:
    return TargetRef(kind=kind, id="t1", label_fr=label_fr, label_native=label_native)


def _recall(label_fr: str, label_native: str) -> RecallTask:
    """The walk's item: the planner's own «How do you say …?»."""

    task = planner.build_recall_task(
        target=_target(label_fr, label_native),
        scenario=_brief(control_language="en", level_band="A2"),
        affordances=[],
        optional=False,
    )
    assert task is not None and task.task_type == "short_answer"
    return task


def _typed(target: TargetRef, key: str) -> RecallTask:
    return RecallTask(
        task_type="short_answer",
        instruction_native="Write it in French.",
        prompt_fr=None,
        options=[],
        accepted_answers=[key],
        estimated_seconds=0,
        target=target,
        optional=False,
        solution_fr=key,
    )


def _grade(task: RecallTask, text: str):
    return journey_learning.evaluate_recall(
        None,
        user=ENGLISH_A2,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        assistance=AssistanceLevel.NONE,
    )


def test_the_walk_s_un_appart_is_right() -> None:
    task = _recall("appartement", "flat, apartment")
    assert task.instruction_native == 'How do you say "flat, apartment" in French?'
    for typed in ("un appart", "Un appart", "l'appart", "l’appart", "appart", "un appartement", "appartement"):
        evaluation = _grade(task, typed)
        assert evaluation.outcome is TaskOutcome.MET, typed
        assert evaluation.correction is None, typed
    # A miss is still a miss: another word is not the word.
    for typed in ("une maison", "un studio", "maison"):
        assert _grade(task, typed).outcome is TaskOutcome.NOT_YET, typed


@pytest.mark.parametrize(
    ("key", "gloss", "other"),
    [
        ("appartement", "flat, apartment", "un appart"),
        ("un appartement", "flat", "un appart"),
        ("la poste", "the post office", "le bureau de poste"),
        ("le restaurant", "the restaurant", "le resto"),
        ("Nous préférons Le Mistral, Lila.", "We prefer Le Mistral, Lila.", "On préfère Le Mistral, Lila."),
        ("On va au marché.", "We are going to the market.", "Nous allons au marché."),
    ],
)
def test_a_typed_recall_takes_every_right_answer_la_forge_takes(key: str, gloss: str, other: str) -> None:
    """One accept-list: what La Forge accepts for an item, the journey accepts for the
    same French and the same English."""

    forge = forge_accepted_answers({"accepted_answers": [key], "prompt": gloss})
    assert widened_answers([key], english=gloss) == forge
    task = _typed(_target(key, gloss), key)
    journey = journey_learning._accepted_answers(task)
    assert set(forge) <= set(journey), (forge, journey)
    assert _grade(task, other).outcome is TaskOutcome.MET, other


def test_an_erratum_or_a_rule_never_trades_on_for_nous() -> None:
    """An erratum's label is its explanation and a grammar target's is the rule's title:
    neither is the prompt, and the item asks for its own form («on va»)."""

    explanation = "With «on» (we), the verb takes the il/elle form: «on va»."
    erratum = _typed(_target("on va", explanation, TargetKind.ERROR), "on va")
    assert _grade(erratum, "on va").outcome is TaskOutcome.MET
    assert _grade(erratum, "nous allons").outcome is TaskOutcome.NOT_YET
    rule = _typed(_target("On va au marché.", "On: we in everyday French", TargetKind.GRAMMAR), "On va au marché.")
    assert _grade(rule, "Nous allons au marché.").outcome is TaskOutcome.NOT_YET


def test_a_rewrite_is_never_answered_by_the_sentence_it_asks_to_change() -> None:
    """A widened answer that is the rewrite's own source («Nous allons…» as the other
    «we» of «On va…») is no answer to «change it»."""

    task = RecallTask(
        task_type="transform",
        instruction_native='Say it with "on": change "Nous allons".',
        prompt_fr="Nous allons au marché.",
        source_fr="Nous allons au marché.",
        options=[],
        accepted_answers=["On va au marché."],
        estimated_seconds=0,
        target=_target("Nous allons au marché.", "We are going to the market."),
        optional=False,
        solution_fr="On va au marché.",
    )
    accepted = journey_learning._accepted_answers(task)
    assert "On va au marché." in accepted
    assert all(text.lower().rstrip(".") != "nous allons au marché" for text in accepted), accepted
    assert _grade(task, "On va au marché.").outcome is TaskOutcome.MET
    assert _grade(task, "Nous allons au marché.").outcome is TaskOutcome.NOT_YET


def test_a_bare_noun_s_fix_keeps_the_article_the_learner_gave() -> None:
    task = _recall("appartement", "flat, apartment")
    for typed, fix in (("une maison", "un appartement"), ("un studio", "un appartement"), ("la maison", "l'appartement")):
        correction = _grade(task, typed).correction
        assert correction is not None, typed
        assert (correction.span_fr, correction.corrected_fr) == (typed, fix)
        # «It is 1 word long» would contradict the two words of the fix.
        assert "1 word long" not in correction.note_native, correction.note_native
    # No article given, none added; the item's hint stays the note.
    correction = _grade(task, "maison").correction
    assert correction is not None and correction.corrected_fr == "appartement"
    assert correction.note_native == task.hint_native


def test_the_article_follows_the_noun_s_gender_and_only_when_it_is_known() -> None:
    assert noun_with_learner_article("appartement", "une maison") == "un appartement"
    assert noun_with_learner_article("maison", "un appart") == "une maison"
    assert noun_with_learner_article("maison", "le appart") == "la maison"
    assert noun_with_learner_article("appartement", "la maison") == "l'appartement"
    assert noun_with_learner_article("Appartement", "Une maison") == "un appartement"
    # «l'» or «le» before an h or a y depends on an aspirated h or a consonant y
    # («le héros», «le yaourt», never «l'yaourt»): no definite article is guessed.
    assert noun_with_learner_article("héros", "la fille") is None
    assert noun_with_learner_article("héros", "une fille") == "un héros"
    assert noun_with_learner_article("yaourt", "la glace") is None
    assert noun_with_learner_article("yaourt", "une glace") == "un yaourt"
    # The key already has its article, is not one noun, or the learner gave none.
    assert noun_with_learner_article("l'appartement", "une maison") is None
    assert noun_with_learner_article("bureau de poste", "une maison") is None
    assert noun_with_learner_article("appartement", "maison") is None
    assert noun_with_learner_article("appartement", "des maisons") is None
    assert noun_with_learner_article("xylozorb", "un truc") is None
