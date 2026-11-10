"""Package V stage 1: no rule and no model edit turns one accepted spelling into another.

A learner who writes «ognon» or «cout» wrote French the 1990 rectifications made right,
and French schools teach. The rule pass «corrected» them anyway (it restored the
circumflex of «plait», «chaine», «aout»), and the check every model edit passes let
«week-end» -> «weekend» through in either direction. The list is
``tests/verdict_corpus/valid_variants.txt``; each pair is tried both ways.

No model call is made anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import correction_contract as cc
from app.services.spelling_variants import is_variant_edit

CORPUS = Path(__file__).parent / "verdict_corpus" / "valid_variants.txt"


def _pairs() -> list[tuple[str, str, str]]:
    rows = []
    for raw in CORPUS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        first, second, sentence = (part.strip() for part in line.split("|"))
        assert "{}" in sentence, line
        rows.append((first, second, sentence))
    return rows


PAIRS = _pairs()
FORMS = [(form, sentence) for first, second, sentence in PAIRS for form in (first, second)]
SWAPS = [(a, b, s) for first, second, s in PAIRS for a, b in ((first, second), (second, first))]


def test_the_corpus_holds_the_named_pairs():
    words = {form for form, _ in FORMS}
    assert {"ognon", "oignon", "cout", "coût", "ile", "île", "évènement", "événement", "weekend", "week-end"} <= words
    assert len(PAIRS) >= 40


@pytest.mark.parametrize(("form", "sentence"), FORMS, ids=[form for form, _ in FORMS])
def test_the_rule_pass_leaves_either_spelling_alone(form, sentence):
    text = sentence.format(form)
    edits = cc.deterministic_edits(text)
    assert edits == [], [(edit.span, edit.replacement, edit.rule_id) for edit in edits]
    assert cc.repair_text(text) == text


@pytest.mark.parametrize(("wrong", "right", "sentence"), SWAPS, ids=[f"{a}->{b}" for a, b, _ in SWAPS])
def test_no_model_edit_swaps_one_spelling_for_the_other(wrong, right, sentence):
    text = sentence.format(wrong)
    assert is_variant_edit(wrong, right)
    verdict = cc.verify_edit(text, wrong, right, f"On écrit « {right} ».")
    assert not verdict.ok and verdict.reason == "valid_variant"
    # A model's whole corrected line that only swaps the spelling changes nothing either.
    checked = cc.verify_correction(text, sentence.format(right), [])
    assert checked.corrected == text, checked
    assert [item for item in checked.errata if item.get("corrected_target") == right] == []


@pytest.mark.parametrize(
    ("span", "fix"),
    [
        # Real mistakes stay mistakes: the gate is for two right spellings only.
        ("sur", "sûr"),
        ("du", "dû"),
        ("mur", "mûr"),
        ("tres", "très"),
        ("ecole", "école"),
        ("grand mère", "grand-mère"),
        ("la", "le"),
        ("cest", "c’est"),
        ("dejeuner", "déjeuner"),
        ("Noel", "Noël"),
    ],
)
def test_a_real_fix_is_not_a_variant(span, fix):
    assert not is_variant_edit(span, fix)


@pytest.mark.parametrize(
    ("span", "fix"),
    [
        ("c'est", "c’est"),  # the two apostrophes
        ("Ça va ?", "Ça va?"),  # the space before «?»
        ("Ça va ?", "Ça va ?"),
    ],
)
def test_typography_alone_is_a_variant(span, fix):
    assert is_variant_edit(span, fix)
