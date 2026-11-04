"""#519: «Correct this sentence.» over the single word «vingt-un».

A ✗/✓ pair from a unit's traps is not always a sentence: the numbers units pair
«vingt-un» with «vingt et un». The transform item printed the pair's ✗ side under
the fixed task line «Correct this sentence.» with nothing to correct but a bare
word. The task line now follows the shape of what is printed: a sentence is
corrected; a bare number says what to write («Write 21 in French.»); any other bare
form is a form to correct.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import grammar_items, grammar_units

UNITS = Path(grammar_units.__file__).resolve().parents[1] / "data" / "grammar_review"
NUMBER_UNITS = ("FR2_A11_NUMBERS", "FR2_A12_NUMBERS_BIG")
SENTENCE_TASK = {
    "en": "Correct this sentence.",
    "de": "Korrigiere diesen Satz.",
    "fr": "Corrige cette phrase.",
}


def _brief(external_id: str, language: str = "en") -> dict:
    data = json.loads((UNITS / "units_A1.json").read_text(encoding="utf-8"))
    row = next(unit for unit in data["units"] if unit["external_id"] == external_id)
    concept = SimpleNamespace(
        id=1,
        external_id=external_id,
        level="A1",
        main_traps=row["main_traps"],
        subskill=row["subskill"],
        anchor_examples=row.get("anchor_examples"),
        source_refs={},
        catalog_version="test",
    )
    return grammar_units.unit_brief(concept, control_language=language)


def _every_transform(brief: dict, language: str = "en") -> list:
    """Every transform the drill can pose for the unit: one per pair, every entry point."""

    tasks = []
    for pair in brief["contrast_pairs"]:
        single = {**brief, "contrast_pairs": [pair]}
        for review in (False, True):
            task = grammar_items.transform_item(single, language=language, review=review)
            if task is not None:
                tasks.append(task)
    tasks += [
        task
        for task in grammar_items.guided_items(brief, sentences=[], language=language)
        if task.task_type == "transform"
    ]
    assert tasks, "the unit poses no transform at all: the test would pass for nothing"
    return tasks


@pytest.mark.parametrize("external_id", NUMBER_UNITS)
@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_correct_this_sentence_never_sits_over_a_bare_word(external_id: str, language: str) -> None:
    for task in _every_transform(_brief(external_id, language), language):
        if task.instruction_native == SENTENCE_TASK[language]:
            words = str(task.prompt_fr or "").split()
            assert len(words) >= 2, (
                f"«{task.instruction_native}» sits over the bare word {task.prompt_fr!r}"
            )


def test_no_unit_in_the_catalogue_corrects_a_sentence_that_is_a_word() -> None:
    """The cause was shared: any unit with a one-word ✗ gets the sentence task line."""

    checked = 0
    for path in sorted(UNITS.glob("units_*.json")):
        for row in json.loads(path.read_text(encoding="utf-8"))["units"]:
            concept = SimpleNamespace(
                id=1,
                external_id=row["external_id"],
                level=row.get("level") or path.stem.split("_")[-1],
                main_traps=row.get("main_traps"),
                subskill=row.get("subskill"),
                anchor_examples=row.get("anchor_examples"),
                source_refs={},
                catalog_version="test",
            )
            brief = grammar_units.unit_brief(concept, control_language="en")
            for pair in brief["contrast_pairs"]:
                task = grammar_items.transform_item({**brief, "contrast_pairs": [pair]}, language="en")
                if task is None:
                    continue
                checked += 1
                if task.instruction_native == SENTENCE_TASK["en"]:
                    assert len(str(task.prompt_fr).split()) >= 2, (
                        f"{row['external_id']}: «{task.instruction_native}» over {task.prompt_fr!r}"
                    )
    assert checked > 20


def test_the_vingt_un_item_says_what_to_write() -> None:
    tasks = [task for task in _every_transform(_brief("FR2_A11_NUMBERS")) if task.prompt_fr == "vingt-un"]
    assert tasks, "the numbers unit no longer poses «vingt-un»"
    for task in tasks:
        assert task.instruction_native == "Write 21 in French.", task.instruction_native
        assert task.solution_fr == "vingt et un"


def test_the_task_line_for_a_number_follows_the_learner_language() -> None:
    (de,) = [t for t in _every_transform(_brief("FR2_A11_NUMBERS", "de"), "de") if t.prompt_fr == "vingt-un"][:1]
    (fr,) = [t for t in _every_transform(_brief("FR2_A11_NUMBERS", "fr"), "fr") if t.prompt_fr == "vingt-un"][:1]
    assert "21" in de.instruction_native and "Französisch" in de.instruction_native
    assert "21" in fr.instruction_native and "français" in fr.instruction_native


def test_a_bare_form_that_is_not_a_number_is_a_form_not_a_sentence() -> None:
    brief = {
        "concept_id": 7,
        "level": "A1",
        "title_fr": "Le pluriel",
        "contrast_pairs": [{"wrong": "chevals", "right": "chevaux"}],
    }
    task = grammar_items.transform_item(brief, language="en")
    assert task is not None
    assert task.instruction_native != SENTENCE_TASK["en"]
    assert "form" in task.instruction_native.lower()
    assert task.accepted_answers == ["chevaux"]


def test_a_real_sentence_keeps_the_sentence_task() -> None:
    brief = {
        "concept_id": 7,
        "level": "A1",
        "title_fr": "Le verbe",
        "contrast_pairs": [{"wrong": "Je suis trente ans.", "right": "J'ai trente ans."}],
    }
    task = grammar_items.transform_item(brief, language="en")
    assert task is not None
    assert task.instruction_native == SENTENCE_TASK["en"]
    assert task.prompt_fr == "Je suis trente ans."
