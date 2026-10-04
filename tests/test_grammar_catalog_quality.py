"""Content program 2026-10-03: the fr-core-v2 catalogue holds its own promises.

Every unit is reviewed, carries a regex detector that recognises its own x-ray
sentence and anchors, marks only spans that occur in its x-ray sentence, points
at prerequisites that exist, sorts sub-band before teaching order, and has an
authored rule card with a rule in every learner language.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from app.services.grammar_catalog import detector_matches, parse_detector
from app.services.rule_cards import rule_card_for

ROOT = Path(__file__).resolve().parents[1]
TSV = ROOT / "templates" / "french_core_grammar_v2.tsv"
SUB_BANDS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2", "C1.1", "C1.2")


def _rows() -> list[dict[str, str]]:
    with TSV.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _split(value: str, separator: str = " | ") -> list[str]:
    return [item.strip() for item in str(value or "").split(separator) if item.strip()]


ROWS = _rows()
REVIEWED = [row for row in ROWS if row["review_status"] == "reviewed"]
IDS = {row["external_id"] for row in ROWS}


def _bracket_balance(text: str) -> bool:
    depth = {"[": 0, "{": 0}
    closing = {"]": "[", "}": "{"}
    for char in text:
        if char in depth:
            depth[char] += 1
        elif char in closing:
            depth[closing[char]] -= 1
            if depth[closing[char]] < 0:
                return False
    return all(value == 0 for value in depth.values())


@pytest.mark.parametrize("row", REVIEWED, ids=lambda row: row["external_id"])
def test_a_reviewed_detector_recognises_its_own_sentences(row):
    detector = parse_detector(row["detector"])
    assert detector and detector["kind"] == "regex", "every reviewed unit is regex-detected (D9)"
    re.compile(detector["pattern"])
    for sentence in [row["xray_sentence"], *_split(row["anchor_examples"])]:
        assert detector_matches(detector, sentence), sentence


@pytest.mark.parametrize("row", REVIEWED, ids=lambda row: row["external_id"])
def test_xray_marks_occur_in_the_xray_sentence(row):
    sentence = row["xray_sentence"].casefold()
    for item in _split(row["xray_marks"], "||"):
        token = item.split("=>", 1)[0].strip().casefold()
        position = 0
        for piece in re.split(r"\.\.\.|…", token):
            piece = piece.strip()
            if not piece:
                continue
            found = sentence.find(piece, position)
            assert found >= 0, f"{token!r} not in {row['xray_sentence']!r}"
            position = found + len(piece)


def test_every_reference_resolves():
    for row in ROWS:
        for ref in _split(row["prerequisites"]) + _split(row["contrast_partners"]):
            assert ref in IDS, (row["external_id"], ref)


def test_sub_bands_are_on_the_scale_and_lead_the_order():
    assert {row["sub_band"] for row in ROWS} <= set(SUB_BANDS)
    keys = [(SUB_BANDS.index(row["sub_band"]), int(row["teaching_order"])) for row in ROWS]
    assert keys == sorted(keys)


@pytest.mark.parametrize("row", REVIEWED, ids=lambda row: row["external_id"])
def test_a_reviewed_unit_has_a_complete_authored_card(row):
    card = rule_card_for(row["external_id"])
    assert card, "authored rule card"
    assert card["example"]["fr"]
    for locale in ("en", "de", "fr"):
        assert (card.get("rule") or {}).get(locale), locale
        assert (card.get("more") or {}).get(locale), locale
    assert card.get("contrast", {}).get("wrong") and card["contrast"].get("right")
    assert card.get("examples") and card.get("traps") and card.get("how")
    french = [card["example"]["fr"], card["contrast"]["right"],
              *[example["fr"] for example in card["examples"]],
              *[trap["right"] for trap in card["traps"]]]
    for text in french:
        assert _bracket_balance(text), text
