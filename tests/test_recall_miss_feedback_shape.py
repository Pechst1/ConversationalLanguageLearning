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
