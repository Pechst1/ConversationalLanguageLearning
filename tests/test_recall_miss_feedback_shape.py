"""#146 / #86 / #167 - every missed recall answer returns one feedback shape.

The shape is verdict (the outcome), the learner's text, the correct text and a
one-line reason. A picked answer (choice, classify, listen_tap) used to get a
correction only when it happened to be a span edit of the French the learner
wrote, so a wrong tap came back as a bare «Noch nicht».
"""
from __future__ import annotations

import pytest

from app.services import journey_planner as planner
from app.services.journey_contracts import TaskOutcome
from tests.test_wp78_practice_day import POOL, _evaluate


def _wrong_option(task) -> str:
    return next(o["id"] for o in task.options if o["id"] != task.correct_option_id)


def _picked_tasks(language: str):
    for target in POOL:
        for task in (
            planner.build_listen_tap_task(target=target, pool=POOL, optional=False, control_language=language),
            planner.build_classify_task(target=target, optional=False, control_language=language),
        ):
            if task is not None:
                yield task


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_a_wrong_pick_always_carries_the_correct_text_and_a_reason(language: str) -> None:
    seen = 0
    for task in _picked_tasks(language):
        seen += 1
        result = _evaluate(task, option_id=_wrong_option(task))
        assert result.outcome is TaskOutcome.NOT_YET
        correction = result.correction
        assert correction is not None, f"{task.task_type} {task.prompt_fr!r}: a miss with no correction"
        assert correction.span_fr.strip(), "the learner's text"
        assert correction.corrected_fr.strip(), "the correct text"
        assert correction.note_native.strip(), "a one-line reason"
        assert correction.span_fr != correction.corrected_fr
        # The reason is a reason, not the question asked again (the old note).
        assert correction.note_native.strip() != task.instruction_native.strip()
    assert seen >= 4


def test_a_word_drill_miss_shows_the_french_word_with_its_gloss() -> None:
    task = planner.build_listen_tap_task(target=POOL[5], pool=POOL, optional=False, control_language="en")
    assert task is not None
    result = _evaluate(task, option_id=_wrong_option(task))
    assert result.correction is not None
    # «brouillard = fog»: the French word is on screen after the miss (#167).
    assert "brouillard" in result.correction.corrected_fr
    assert "fog" in result.correction.note_native
    # #167 (22 and 30 Oct): «to write → coopérative» drew the tapped meaning as French
    # to fix. A missed meaning is its own kind: the screen shows the word, no arrow.
    assert result.correction.kind == "meaning"
    public = _public(task, _wrong_option(task))
    assert public is not None and public.kind == "meaning"
    assert public.corrected_fr == "brouillard"


def test_only_a_meaning_drill_miss_is_a_meaning() -> None:
    for task in _picked_tasks("en"):
        result = _evaluate(task, option_id=_wrong_option(task))
        assert result.correction is not None
        assert (result.correction.kind == "meaning") is (task.task_type == "listen_tap"), task.task_type


def test_a_right_pick_has_no_correction() -> None:
    for task in _picked_tasks("en"):
        result = _evaluate(task, option_id=task.correct_option_id)
        assert result.outcome is TaskOutcome.MET
        assert result.correction is None


# --- #154: a miss is tagged from the unit's own error categories ------------


def _Unit(external_id: str, name: str):
    from app.db.models.grammar import GrammarConcept

    return GrammarConcept(external_id=external_id, name=name, category="Tenses")


@pytest.mark.parametrize("external_id", ["FR2_A21_PC_AVOIR", "FR2_A22_FUTUR_SIMPLE", "FR2_A21_PC_ETRE"])
def test_a_form_unit_is_never_tagged_with_the_tense_contrast(external_id: str) -> None:
    from app.services.grammar_feedback import infer_grammar_profile

    profile = infer_grammar_profile(_Unit(external_id, "Passé composé avec avoir"))
    assert profile.key == "tense_form"
    assert "background" not in profile.label.lower()
    assert "scene" not in profile.repair.lower()


@pytest.mark.parametrize("external_id", ["FR2_A22_IMP_VS_PC", "FR_B1_TENSE_001"])
def test_the_contrast_unit_keeps_its_tense_choice_tag(external_id: str) -> None:
    from app.services.grammar_feedback import infer_grammar_profile

    assert infer_grammar_profile(_Unit(external_id, "Imparfait ou passé composé")).key == "tense_aspect"


# --- #86: a grammar choice keeps the unit's rule as its reason ---------------


def _choice_task(rule: str | None):
    from app.services import grammar_items
    from tests.test_wp107_retour import si_brief

    brief = si_brief()
    if rule:
        brief["rule_short_native"] = rule
    task = grammar_items.choose_item(brief, language="fr")
    assert task is not None and task.task_type == "choice"
    return task


def test_a_wrong_grammar_choice_keeps_the_rule_as_its_reason() -> None:
    task = _choice_task("Après si, le verbe reste au présent.")
    result = _evaluate(task, option_id=_wrong_option(task))
    assert result.correction is not None
    assert result.correction.note_native == "Après si, le verbe reste au présent."


def test_a_choice_without_a_rule_names_the_right_answer() -> None:
    from dataclasses import replace

    task = replace(_choice_task(None), hint_native=None)
    result = _evaluate(task, option_id=_wrong_option(task))
    assert result.correction is not None
    assert "Si je finis tôt, je t'appellerai." in result.correction.note_native
    assert result.correction.note_native.strip() != task.instruction_native.strip()


def test_a_wrong_who_said_names_the_right_speaker() -> None:
    from dataclasses import replace

    base = _choice_task(None)
    task = replace(
        base,
        task_type="who_said",
        hint_native=None,
        options=[{"id": "opt_a", "text_fr": "Romy"}, {"id": "opt_b", "text_fr": "Gus"}],
        correct_option_id="opt_a",
        accepted_answers=["Romy"],
        solution_fr="Romy",
    )
    result = _evaluate(task, option_id="opt_b")
    assert result.outcome is TaskOutcome.NOT_YET
    assert result.correction is not None
    assert "Romy" in result.correction.note_native


# --- #86 (17 Oct re-test): the reason must survive the public layer ----------


def _public(task, option_id: str):
    """What the learner's screen gets: the evaluator's correction after the public check.

    A tap sends an option id and no text, so the public layer used to compare the
    correction with an empty string and drop the reason of every wrong tap.
    """
    from app.services.daily_journey import DailyJourneyService
    from app.services.journey_contracts import AttemptAnswer, InputMode
    from app.services.journey_learning import recall_learner_text

    result = _evaluate(task, option_id=option_id)
    answer = AttemptAnswer(mode=InputMode.TEXT, text="", option_id=option_id)
    return DailyJourneyService._public_correction(result.correction, recall_learner_text(task, answer))


def test_a_wrong_tap_reaches_the_screen_with_its_reason_in_every_pick_type() -> None:
    for task in _picked_tasks("en"):
        public = _public(task, _wrong_option(task))
        assert public is not None, f"{task.task_type}: the reason was dropped"
        assert public.note_native.strip()


def test_a_wrong_recall_choice_names_the_rule_order_on_a_b1_double_pronoun_unit() -> None:
    from app.services import grammar_items

    brief = {
        "concept_id": 5, "external_id": "FR2_B11_DOUBLE_PRON", "level": "B1.1",
        "title_native": "Double pronouns", "title_fr": "Deux pronoms",
        "recognition_pair": ("Je le lui donne.", ["Je lui le donne."]),
        "rule_card": {"rule": {"fr": "Le pronom COD précède le COI.", "en": "Direct before indirect."}},
        "detectors": [], "contrast_pairs": [],
    }
    task = grammar_items.recognise_item(brief, sentences=[], language="fr")
    assert task is not None
    public = _public(task, _wrong_option(task))
    assert public is not None
    assert public.span_fr == "Je lui le donne." and public.corrected_fr == "Je le lui donne."
    assert public.note_native == "Le pronom COD précède le COI."


def test_a_vocabulary_choice_miss_names_the_word_not_the_letter_clue() -> None:
    """#178 follow-up: a vocabulary choice's hint is the first-letter clue
    («… ça commence par « s »»), not a reason. Only a grammar choice keeps its hint."""
    from dataclasses import replace

    from app.services.journey_contracts import TargetKind

    base = _choice_task(None)
    task = replace(
        base,
        hint_native="C'est 7 mots et ça commence par « S ».",
        target=replace(base.target, kind=TargetKind.VOCABULARY),
    )
    result = _evaluate(task, option_id=_wrong_option(task))
    assert result.correction is not None
    assert "commence par" not in result.correction.note_native
    assert "Si je finis tôt, je t'appellerai." in result.correction.note_native
