"""#542 / #543: a drill's instruction comes from the task the item declares.

La Forge's transform items carry ``type: directed_rewrite | contrast_rewrite |
repair_rewrite``. The goal line («Corrige l'erreur dans la phrase.») used to be
picked from the item's *shape* (a ``source`` and an ``expected_answer``), so a
correct sentence that is to be rewritten with a pronoun was announced as a
mistake to fix in German and French chrome.
"""
from __future__ import annotations

import pytest

from app.services.atelier import ATELIER_EXERCISE_RESPONSE_FORMAT, AtelierExerciseGenerator
from app.services.item_bank import public_item, with_goal

from .test_atelier_transform_produce_fixes import _PROFILE_CONCEPT_SPECS, _concept

#: The lines that tell a learner a sentence holds an error.
ERROR_INSTRUCTIONS = (
    "Corrige l’erreur",
    "Corrige l'erreur",
    "Korrigiere den Fehler",
    "Correct this sentence",
    "Fix it",
)

LANGUAGES = ("en", "de", "fr")


def _says_error(text: object) -> bool:
    folded = str(text or "").casefold()
    return any(phrase.casefold() in folded for phrase in ERROR_INSTRUCTIONS)


def _fallback_items(db_session) -> list[dict]:
    generator = AtelierExerciseGenerator(db_session)
    items: list[dict] = []
    for spec in _PROFILE_CONCEPT_SPECS.values():
        items.extend(generator._fallback_transform_items(_concept(**spec), ["unused"], prefix="t"))
    return items


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_error_goal(db_session, language: str) -> None:
    items = _fallback_items(db_session)
    assert {item["type"] for item in items} == {"directed_rewrite", "contrast_rewrite", "repair_rewrite"}

    for item in items:
        served = public_item(item, language)
        lines = [served.get("goal_native"), served.get("instruction")]
        if item["type"] == "repair_rewrite":
            continue
        assert not any(_says_error(line) for line in lines), (
            f"{item['instruction_key']} is a {item['type']} (its source is right) but the "
            f"{language} learner is told {lines!r}"
        )


@pytest.mark.parametrize("language", ("de", "fr"))
def test_rewrite_goal(db_session, language: str) -> None:
    by_key = {item["instruction_key"]: item for item in _fallback_items(db_session)}

    rewrite = public_item(by_key["atelier.transform.pronoun_choice.1"], language)
    repair = public_item(by_key["atelier.transform.pronoun_choice.3"], language)

    assert rewrite["goal_native"] == {"de": "Schreib den Satz um.", "fr": "Récris la phrase."}[language]
    assert _says_error(repair["goal_native"])
    assert rewrite["goal_native"] != repair["goal_native"]


def test_kind_has_goal() -> None:
    from app.services import item_bank

    table = getattr(item_bank, "TASK_GOAL_KINDS", {})
    schema = ATELIER_EXERCISE_RESPONSE_FORMAT["json_schema"]["schema"]["$defs"]["transform_item"]
    kinds = schema["properties"]["type"]["enum"]

    assert kinds
    for kind in kinds:
        assert kind in table, f"the transform kind {kind!r} has no entry in the goal table"
        assert table[kind] in item_bank._GOALS, kind
        assert set(item_bank._GOALS[table[kind]]) == set(LANGUAGES)
    assert set(table) == set(kinds)


def test_no_guess() -> None:
    bare = {"id": "x", "source": "Je vois Marc demain.", "expected_answer": "Je le vois demain."}

    for language in LANGUAGES:
        served = with_goal(bare, language)
        assert not _says_error(served.get("goal_native")), language
