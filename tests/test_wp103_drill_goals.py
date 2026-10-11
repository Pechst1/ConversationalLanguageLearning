"""WP-103 T3 «Retour d'essai» — every drill says what to produce.

The owner's day 2: the Rappel showed «Build the sentence. Some chips are not
needed.» over «Une petite table blanche est dans la cuisine» — with no meaning and
no source, so the learner had no idea *which* sentence. Now a word bank, tiles, an
unscramble or a transform carries ``goal_native`` (the meaning to build, or which
line of the scene), and ``source_fr`` when it starts from a shown sentence; the
plan contract refuses a goal-less drill.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.schemas.daily_journey import JourneyCorrection, RecallPrompt
from app.services import grammar_items
from app.services import journey_planner as planner
from app.services.journey_contracts import (
    GOAL_REQUIRED_RECALL_FORMATS,
    StepKind,
    TargetKind,
    TargetRef,
    recall_goal_gap,
)
from app.services.rule_cards import rule_card_for
from app.services.scene_items import SceneLine, build_line_unscramble_task, line_meanings

KITCHEN = "Une petite table blanche est dans la cuisine."


def _owner_brief(stability: float = 5.0) -> dict:
    """FR_A1_NOUN_001 as the owner met it: the catalogue's anchor (no translation)
    and the authored card, whose example is translated."""

    return {
        "concept_id": 11,
        "title_fr": "Le genre des noms",
        "title_native": "Noun gender",
        "detectors": [r"\bune petite\b"],
        "noun_phrase": True,
        "examples": [KITCHEN, "Une petite table blanche, près de la fenêtre."],
        "contrast_pairs": [{"wrong": "une petit table", "right": "une petite table"}],
        "pattern_forms": [],
        "rule_short_native": "The noun decides.",
        "stability": stability,
        "rule_card": rule_card_for("FR_A1_NOUN_001"),
    }


def test_the_owners_word_bank_names_the_sentence_it_builds():
    task = grammar_items.build_item(_owner_brief(), sentences=[], language="en")
    assert task is not None and task.task_type in {"word_bank", "tiles"}
    # The untranslated kitchen anchor is not posed: nobody could say what it means.
    assert task.solution_fr == "Une petite table blanche, près de la fenêtre."
    assert task.goal_native == 'Build: "A small white table, by the window."'
    # German learners read the goal in German.
    german = grammar_items.build_item(_owner_brief(), sentences=[], language="de")
    assert german.goal_native == "Bau den Satz: „Ein kleiner weißer Tisch, am Fenster.“"


def test_a_scene_line_with_its_translation_can_be_the_build():
    task = grammar_items.build_item(
        _owner_brief(), sentences=[KITCHEN], language="en",
        meanings={KITCHEN: "A small white table is in the kitchen."},
    )
    assert task.solution_fr == KITCHEN
    assert task.goal_native == 'Build: "A small white table is in the kitchen."'


def test_the_rappel_transform_starts_from_its_source():
    task = grammar_items.transform_item(_owner_brief(), language="en")
    assert task.source_fr == task.prompt_fr == "une petit table"
    assert task.goal_native.startswith("Correct the sentence")


@pytest.mark.parametrize("stability", [4.0, 6.0, 9.0])
def test_every_rappel_drill_that_needs_a_goal_has_one(stability):
    for day in range(8):
        task = grammar_items.review_item(
            _owner_brief(stability), sentences=[KITCHEN], language="en", day_key=str(day)
        )
        assert task is not None
        if task.task_type in GOAL_REQUIRED_RECALL_FORMATS:
            assert task.goal_native


def test_vocabulary_drills_carry_their_goal_and_a_gloss_less_bank_is_not_posed():
    glossed = TargetRef(kind=TargetKind.VOCABULARY, id="v1", label_fr="l'addition maintenant",
                        label_native="the bill now")
    bank = planner.build_word_bank_task(
        target=glossed, affordances=["Un café au comptoir ?"], optional=False, control_language="en"
    )
    assert bank.goal_native == 'Build: "the bill now"'
    bare = replace(glossed, label_native=None)
    assert planner.build_word_bank_task(
        target=bare, affordances=["Un café au comptoir ?"], optional=False, control_language="en"
    ) is None
    unscramble = planner.build_unscramble_task(
        target=TargetRef(kind=TargetKind.VOCABULARY, id="v2", label_fr="café", label_native="coffee"),
        sentences=["Je voudrais un café au comptoir."], optional=False, control_language="en",
        meanings={"Je voudrais un café au comptoir.": "I would like a coffee at the counter."},
    )
    assert unscramble.goal_native == 'Rebuild the sentence from the scene: "I would like a coffee at the counter."'
    without = planner.build_unscramble_task(
        target=TargetRef(kind=TargetKind.VOCABULARY, id="v2", label_fr="café", label_native="coffee"),
        sentences=["Je voudrais un café au comptoir."], optional=False, control_language="en",
    )
    assert without.goal_native == "Rebuild the sentence from today's scene that has «café» in it."


def test_a_line_rebuilt_from_the_scene_names_its_speaker_and_meaning():
    scenario = SimpleNamespace(
        story_context={"draft": {"panels": [{"dialogue": [
            {"character_id": "marin_leveque", "text_fr": "Il reste une place ici.", "text_native": "There is a seat left here."},
        ]}]}},
        character_id="marin_leveque", opening_line_fr="",
    )
    meanings = line_meanings(scenario)
    task = build_line_unscramble_task(
        target=TargetRef(kind=TargetKind.VOCABULARY, id="v3", label_fr="une place", label_native="a seat"),
        line=SceneLine("marin_leveque", "Il reste une place ici.", "panel:0:line:0"),
        speaker_name="Marin Lévêque", optional=True, control_language="en",
        meaning=meanings["Il reste une place ici."],
    )
    assert task.goal_native == 'Rebuild what Marin said: "There is a seat left here."'


def test_the_plan_contract_refuses_a_drill_without_a_goal():
    task = grammar_items.build_item(_owner_brief(), sentences=[], language="en")
    step = SimpleNamespace(kind=StepKind.RECALL, private_task=task)
    assert recall_goal_gap(step) is None
    goalless = SimpleNamespace(kind=StepKind.RECALL, private_task=replace(task, goal_native=None))
    assert "goal_native" in recall_goal_gap(goalless)


def test_the_public_prompt_carries_goal_and_source():
    prompt = RecallPrompt.model_validate(
        {
            "task_type": "transform",
            "instruction_native": "Correct this sentence.",
            "prompt_fr": "une petit table",
            "options": [],
            "target": {"kind": "grammar", "id": "11", "label_fr": "", "label_native": None},
            "optional": False,
            "goal_native": "Correct the sentence: fix the part that breaks today's rule, keep the rest.",
            "source_fr": "une petit table",
        }
    )
    dumped = prompt.model_dump(mode="json")
    assert dumped["goal_native"].startswith("Correct the sentence") and dumped["source_fr"] == "une petit table"


def test_a_journey_correction_has_one_note_per_issue():
    correction = JourneyCorrection(
        span_fr="ton place", corrected_fr="ta place",
        note_native="Place is feminine: ta place. Place is feminine: ta place.",
    )
    assert correction.notes_native == ["Place is feminine: ta place."]
