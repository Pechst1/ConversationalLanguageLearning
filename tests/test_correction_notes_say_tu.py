"""#784: the French notes of the shared corrector speak to the learner with «tu».

#762 put every French rule card in tu and gave the cards a register guard
(`tests/test_wp_l10_rule_cards.py::vous_address`). The correction notes are the other
French text the app writes to the learner about a rule, and nothing walked them: the
tense note still said «gardez le même temps». This walks every French string of every
note table in `correction_contract` (the rule table, the spelling notes, the
contraction note) with the same guard, so a note written in vous fails here.
"""

from __future__ import annotations

from app.services import correction_contract
from tests.test_wp_l10_rule_cards import vous_address


def _french_notes() -> list[tuple[str, str]]:
    """``(where, text)`` for every French string that sits next to an en/de one."""

    found: list[tuple[str, str]] = []
    seen: set[int] = set()

    def walk(node, where: str) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, dict):
            if isinstance(node.get("fr"), str) and ("en" in node or "de" in node):
                found.append((where, node["fr"]))
            for key, value in node.items():
                walk(value, f"{where}.{key}")
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value, f"{where}[]")

    for name, value in vars(correction_contract).items():
        if isinstance(value, dict):
            walk(value, name)
    return found


def test_the_walk_reaches_the_rule_table():
    notes = dict(_french_notes())
    assert "_RULE_TEXT.FR_TENSE_PC.note" in notes, sorted(notes)[:10]
    assert len([where for where in notes if where.startswith("_RULE_TEXT.")]) >= 40


def test_every_french_correction_note_says_tu():
    slips = [f"{where}: {hits} in «{text}»" for where, text in _french_notes() for hits in [vous_address(text)] if hits]
    assert not slips, "A French correction note says vous to the learner:\n" + "\n".join(slips)


def test_the_tense_note_keeps_the_tense_in_tu():
    note = correction_contract._RULE_TEXT["FR_TENSE_PC"]["note"]["fr"]
    assert "garde le même temps" in note, note
