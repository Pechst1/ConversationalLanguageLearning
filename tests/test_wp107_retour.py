"""The owner's B1 return: same-form traps, production and learner language."""
from types import SimpleNamespace

import pytest

from app.services import grammar_items, journey_content, journey_planner
from app.services.grammar_units import french_rule
from app.services.item_bank import public_item
from app.services.journey_contracts import CapabilityKey, ScenarioBrief, TargetKind, TargetRef
from app.services.journey_rhythm import RHYTHM_BUDGET_SECONDS
from tests.test_journey_content import _user
from tests.test_wpl6_rhythm import _plan
from tests.wp93_briefs import engine_brief


def si_brief():
    return {
        "concept_id": 107, "level": "B1", "title_fr": "Si et le futur",
        "detectors": [r"\bsi\b"], "stability": 1,
        "examples": ["Si je finis tôt, je t'appellerai."],
        "contrast_pairs": [
            {"right": "Si je finis tôt, je t'appellerai.", "wrong": "Si je finirai tôt, je t'appellerai."},
            {"right": "Si tu viens, nous sortirons.", "wrong": "Si tu viendrais, nous sortirons."},
            {"right": "Si elle arrive, je partirai.", "wrong": "Si elle arrive, je partais."},
        ],
    }


def test_b1_recognition_has_no_unrelated_scene_distractor():
    task = grammar_items.recognise_item(si_brief(), sentences=["Bonjour !", "Le café est ouvert."], language="fr")
    assert task is not None
    assert all(option["text_fr"].startswith("Si ") for option in task.options)
    assert {option["text_fr"] for option in task.options} == {
        "Si je finis tôt, je t'appellerai.", "Si je finirai tôt, je t'appellerai."
    }


def test_b1_rule_has_one_warmup_then_at_least_sixty_percent_written_production():
    tasks = grammar_items.guided_items(si_brief(), sentences=["Bonjour !"], language="fr")
    assert tasks[0].task_type == "choice"
    assert all(task.task_type in {"transform", "short_answer"} for task in tasks[1:])
    assert sum(task.task_type in {"transform", "short_answer"} for task in tasks) / len(tasks) >= .6


def test_b1_due_rule_is_produced_even_at_low_stability():
    task = grammar_items.review_item(si_brief(), sentences=[], language="fr", day_key="day-2")
    assert task is not None and task.task_type == "transform"


def test_french_word_bank_does_not_fall_back_to_its_english_prompt():
    item = public_item({
        "prompt": "Build the sentence.", "meaning_cue": "I am here.",
        "answer_tokens": ["Je", "suis", "ici", "."],
        "tokens": ["ici", "suis", "Je", "."],
    }, "fr")
    assert item["meaning_cue"] is None
    assert item["prompt"] == item["goal_native"]
    assert item["prompt"].startswith("Remettez")


def test_b1_cloze_without_a_foreign_gloss_uses_the_actual_scene_sentence():
    target = TargetRef(kind=TargetKind.VOCABULARY, id="word", label_fr="emporter", label_native=None)
    task = journey_planner.practice_task("short_answer", target=target,
        scenario=engine_brief(level_band="B1", control_language="fr"),
        affordances=[], optional=False, learner_text=None, pool=[],
        sentences=["Je vais emporter mon café."])
    assert task is not None and task.prompt_fr == "Je vais … mon café."
    assert task.accepted_answers == ["emporter"]


def test_v1_si_rule_uses_the_authored_french_v2_rule():
    rule = french_rule(SimpleNamespace(external_id="FR_B1_COND_001", source_refs={},
        anchor_examples="Si je finis tôt, je t'appellerai.", core_rule="English rule"))
    assert rule and rule.startswith("Condition réelle")


@pytest.mark.parametrize("rhythm,budget", RHYTHM_BUDGET_SECONDS.items())
@pytest.mark.parametrize("audio", [False, True])
def test_b1_rhythm_recall_mix_is_at_least_sixty_percent_production(rhythm, budget, audio):
    plan = _plan(budget, scenario=engine_brief(level_band="B1", control_language="fr"), audio_available=audio)
    plan.validate()
    tasks = [step.private_task for step in plan.steps if step.kind == "recall"]
    assert tasks, rhythm
    assert sum(task.task_type in {"short_answer", "transform", "dictation"} for task in tasks) / len(tasks) >= .6
    scene_at = next(step.ordinal for step in plan.steps if step.kind == "scene")
    assert all(step.ordinal < scene_at for step in plan.steps if step.kind == "recall" and step.private_task.task_type == "choice")


@pytest.mark.parametrize("key", [CapabilityKey.ORDER_AT_CAFE, CapabilityKey.ARRANGE_MEETING, CapabilityKey.EXPLAIN_DELAY])
@pytest.mark.parametrize("native", ["en", "de", "fr"])
def test_b1_authored_families_are_b1_with_french_chrome(db_session, key, native):
    user = _user(db_session, cefr="B1.1", native=native)
    brief = journey_content.resolve_scenario_brief(db_session, user=user, scenario_key=key, allow_generation=False, bind_serial=False)
    assert isinstance(brief, ScenarioBrief)
    assert brief.level_band == "B1"
    assert brief.control_language == "fr"
    assert journey_content.resolve_level_fit(user=user, brief=brief).note_native is None
    assert journey_content.validate_scenario_brief(brief, rules=journey_content.scenario_content_rules(key, level_band="B1")) == []
