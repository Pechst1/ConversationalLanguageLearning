"""#176 / #146: a free-use item has one prompt, built from one item record.

Walk 2026-10-16 to 2026-10-20: La Forge showed Margaux's «Qu'est-ce que tu me
racontes ?» above the task «Antworte auf Französisch: „Er ist nett.“». The coach's
line came from a list of generic openers (``forge_coaches.json``) and the task from
the item, chosen independently, so a learner could not tell whether to answer
Margaux or to translate. A character line is shown only when it is the question the
item itself asks (its own ``ask``, or the question in its sentence); otherwise the
item has no line.
"""
from __future__ import annotations

import pytest

from app.services import forge_coaches as fc
from app.services import item_bank as ib

REQUIREMENT = {"label": "X", "target_count": 1}


def _units() -> list[str]:
    return sorted({unit for family in fc._data()["families"] for unit in family["units"]})


def _own_questions(item) -> set[tuple[str, str]]:
    """The (French, English) questions the item itself carries."""

    found: set[tuple[str, str]] = set()
    if item.ask:
        found.add((item.ask["fr"], item.ask["en"]))
    for text, english in ((item.sentence, item.en),):
        split, split_en = fc._split_question(fc._strip_vocative(text, french=True)), fc._split_question(
            fc._strip_vocative(english, french=False)
        )
        if split and split_en:
            found.add((split[0], split_en[0]))
    return found


def test_a_coach_line_is_always_the_question_of_the_item_it_comes_with() -> None:
    checked = scenes = 0
    stray: list[str] = []
    for unit in _units():
        coach = fc.coach_for_unit(unit)
        for item in ib.default_bank().generate(unit, 12, seed=f"one-prompt:{unit}", detector=ib.unit_detector(unit)):
            built = ib.output_item(item, round_name="conversation", requirement=REQUIREMENT, coach=coach)
            checked += 1
            if built is None:  # (the next test holds that it always has a prompt)
                continue
            if "scene" not in built:
                # No line at all: a plain «say it» task, with no character byline.
                assert "character" not in built and "«" not in built["prompt"], (unit, built["prompt"])
                continue
            scenes += 1
            line = built["scene"]["lines"][0]
            if (line["fr"], line["en"]) not in {(fr, en) for fr, en in _own_questions(item)}:
                stray.append(f"{unit}: {line['fr']} -> {built['example_answer']}")
    assert checked > 100 and scenes > 20
    assert stray == [], "a character line that is not the item's own question:\n" + "\n".join(stray[:10])


@pytest.mark.parametrize("unit", ["FR2_A21_PC_AVOIR", "FR2_A11_JE_VOUDRAIS"])
def test_a_unit_whose_items_ask_no_question_still_has_a_free_use_prompt(unit: str) -> None:
    coach = fc.coach_for_unit(unit)
    for item in ib.default_bank().generate(unit, 10, seed=f"plain:{unit}", detector=ib.unit_detector(unit)):
        built = ib.output_item(item, round_name="conversation", requirement=REQUIREMENT, coach=coach)
        assert built is not None and built["example_answer"]
        assert built["type"] == "conversation_turn"



def _strong_brief(unit: str) -> dict:
    return {
        "concept_id": 4242,
        "external_id": unit,
        "title_fr": unit,
        "stability": 12.0,
        "rule_short_native": "The unit's rule.",
    }


def test_every_coach_unit_keeps_its_rappel_free_use_and_a_line_is_the_items_own_question() -> None:
    """Night-shift review of #258: dropping the generic openers left 59 of the 78
    coach units with no Rappel scene at all (``coach_scene_review_task`` returned
    ``None``), so a strong unit never got its free-use re-use check. Every unit now
    poses the scene when an item asks its own question, and otherwise the plain task,
    and a posed character line is always the question of the item it is posed with."""

    from app.services.journey_learning import coach_scene_review_task

    silent: list[str] = []
    stray: list[str] = []
    for unit in _units():
        coach = fc.coach_for_concept(unit)
        posed = 0
        for day in range(1, 29):
            if posed == 3:  # (three posed days per unit keep the sweep fast; a silent unit tries all 28)
                break
            day_key = f"2026-10-{day:02d}"
            task = coach_scene_review_task(_strong_brief(unit), language="en", day_key=day_key)
            if task is None:
                continue
            posed += 1
            assert task.evidence_format == "conversation" and task.accepted_answers, unit
            assert task.hint_native == "The unit's rule.", unit
            if not task.prompt_fr:
                assert "talking to you" not in task.instruction_native, (unit, task.instruction_native)
                continue
            candidates = ib.default_bank().generate(
                unit, 24, seed=f"rappel-scene|{unit}|{day_key}", detector=ib.unit_detector(unit)
            )
            pairs = {
                (f"{coach['name']} : « {line['fr']} »", scene["reply"])
                for item in candidates
                if (scene := fc.mini_scene(item, coach)) is not None
                for line in scene["lines"][:1]
                if (line["fr"], line["en"]) in _own_questions(item)
            }
            if (task.prompt_fr, task.solution_fr) not in pairs:
                stray.append(f"{unit} {day_key}: {task.prompt_fr} -> {task.solution_fr}")
        if not posed:
            silent.append(unit)
    assert silent == [], f"units whose Rappel poses no free use on any of 28 days: {silent}"
    assert stray == [], "a character line that is not the item's own question:\n" + "\n".join(stray[:10])
