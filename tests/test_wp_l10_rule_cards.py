"""WP-L10 — the rule card v2 content is complete, well-formed and served."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from app.services.rule_cards import _cards, rule_card_for

ROOT = Path(__file__).resolve().parents[1]
SHAPES = {"square", "circle", "circles", "triangle", "none"}
MARK = re.compile(r"\[[^\]]+\]")


def _catalogue_ids(levels: set[str]) -> set[str]:
    with (ROOT / "templates" / "french_core_grammar_v1.tsv").open(encoding="utf-8") as handle:
        return {row["external_id"] for row in csv.DictReader(handle, delimiter="\t") if row["cefr_level"] in levels}


def _balanced(text: str) -> bool:
    depth = {"[": 0, "{": 0}
    for char in text:
        if char in "[{":
            if any(depth.values()):
                return False
            depth[char] += 1
        elif char == "]":
            depth["["] -= 1
        elif char == "}":
            depth["{"] -= 1
        if min(depth.values()) < 0:
            return False
    return not any(depth.values())


def test_every_a1_and_a2_concept_has_a_card():
    assert _catalogue_ids({"A1", "A2"}) <= set(_cards())


def test_every_card_is_complete_in_english_and_german():
    for external_id, card in _cards().items():
        assert MARK.search(card["example"]["fr"]), external_id
        for field in ("rule", "more"):
            for language in ("en", "de"):
                assert card[field][language].strip(), (external_id, field, language)
        for language in ("en", "de"):
            assert card["example"]["tr"][language].strip(), (external_id, language)
        # One sentence, short: the owner's rule card has no text wall.
        assert len(card["rule"]["en"].split()) <= 20, external_id
        assert card["contrast"]["wrong"] and MARK.search(card["contrast"]["right"]), external_id


def test_markup_is_balanced_and_patterns_are_drawable():
    for external_id, card in _cards().items():
        pattern = card["pattern"]
        strings = [card["example"]["fr"], card["contrast"]["wrong"], card["contrast"]["right"]]
        if pattern["kind"] == "rows":
            assert pattern["rows"], external_id
            for row in pattern["rows"]:
                assert row["shape"] in SHAPES, (external_id, row)
                strings.append(row["fr"])
        else:
            assert pattern["kind"] == "table" and len(pattern["rows"]) == 6, external_id
            strings.extend(row["fr"] for row in pattern["rows"])
            assert pattern["note"]["en"] and pattern["note"]["de"], external_id
        for text in strings:
            assert _balanced(text), (external_id, text)


def test_a_concept_without_a_card_keeps_the_legacy_panel():
    assert rule_card_for(None) is None
    assert rule_card_for("FR_C1_SYN_001") is None
    assert rule_card_for("FR_A1_NOUN_001")["speaker"] == "margaux_barman"


def test_the_card_travels_with_the_serialized_concept():
    from types import SimpleNamespace

    from app.services.atelier import serialize_concept

    concept = SimpleNamespace(
        id=1, external_id="FR_A1_VERB_001", name="Present tense core verbs", level="A1",
        category="Verbs", subskill="present", core_rule="", main_traps="", anchor_examples="",
        exercise_tags=[], is_foundation=True,
    )
    data = serialize_concept(concept)
    assert data["rule_card"]["pattern"]["kind"] == "table"
    assert data["rule_card"]["pattern"]["verb"] == "habiter"
