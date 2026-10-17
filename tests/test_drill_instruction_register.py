"""#196: the French instructions on drill, recall and Forge items say tu, never vous.

#185 put the app's voice on one setting (`address.LEARNER_ADDRESS`), but the exercise
instructions are literals in the item builders, so the setting never reached them and
«Corrigez cette phrase.» kept the vous the rest of the app had left. This scans every
French instruction table of those builders: an imperative in -ez at the start of a
sentence, or vous / votre / vos, fails.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "app" / "services"
BUILDERS = ["grammar_items.py", "scene_items.py", "forge_grading.py", "item_bank.py", "learner_model.py"]

#: `"fr": "…"` (an instruction table row) and `"fill": "…"`-style French cue templates.
FR_VALUE = re.compile(r'"fr":\s*"((?:[^"\\]|\\.)*)"')
IMPERATIVE_EZ = re.compile(r"(?:^|[.!?:»]\s+|\}\s+)[A-ZÉÈ][a-zéèêàçùô]+ez\b")
VOUS = re.compile(r"\b(?:à vous|votre|vos)\b", re.IGNORECASE)
NOT_IMPERATIVES = {"Chez", "Assez"}


@pytest.mark.parametrize("name", BUILDERS)
def test_french_instruction_tables_say_tu(name: str) -> None:
    found: list[str] = []
    for value in FR_VALUE.findall((ROOT / name).read_text(encoding="utf-8")):
        hit = IMPERATIVE_EZ.search(value)
        if (hit and hit.group().split()[-1] not in NOT_IMPERATIVES) or VOUS.search(value):
            found.append(value)
    assert not found, f"{name}: vous register in a French instruction: {found}"


def test_the_guard_catches_the_old_wording() -> None:
    assert IMPERATIVE_EZ.search("Corrigez cette phrase.")
    assert IMPERATIVE_EZ.search("{scene} Écrivez une courte phrase")
    assert not IMPERATIVE_EZ.search("Corrige cette phrase.")
    assert VOUS.search("Écris une phrase à vous.")
