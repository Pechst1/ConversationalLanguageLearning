"""#1119: La Forge rejected «quarante neuf» under «What is off» with the learner's own line.

Live walk of 28 Nov 2026 (production, A1.1, day 46), La Forge, review «Numbers 0–69 and
prices»: «Gus paid 49 euros for the painting.» answered «Gus a payé quarante neuf euros
pour le tableau.» (hyphen missing). The card said «Not yet · Find it yourself first» over a
«What is off» box that repeated the sentence unchanged, no word marked, no reason; «Show
the solution» then printed «Corrected line» with no note about the hyphen.

The model's reading never reached the card: «quarante neuf» -> «quarante-neuf» was read as
two accepted spellings of one number (``spelling_variants._number_variant`` took any
hyphen in a number as optional), and the same change read off the right sentence as two
words gone and one come (``correction_contract.changes_what_was_said``). Every fix was
refused, the corrected line became the learner's own, and nothing was left to mark. The
key knows better: a line that is an accepted answer but for a hyphen has that hyphen as
its one issue, as an accent is (#297).
"""
from __future__ import annotations

import pytest

from app.services import solution_gate
from app.services.forge_grading import refine_production_correction
from app.services.spelling_variants import is_variant_edit

LEARNER = "Gus a payé quarante neuf euros pour le tableau."
KEY = "Gus a payé quarante-neuf euros pour le tableau."
HYPHEN = {"en": "hyphen", "de": "bindestrich", "fr": "trait d’union"}

#: What a model may send back for the line: the narrow fix, the right sentence alone, the
#: whole line as one fix, or «right».
MODEL_READINGS = {
    "narrow_fix": {
        "verdict": "partial",
        "score_0_4": 2,
        "corrected_answer": KEY,
        "errata": [{"learner_text": "quarante neuf", "corrected_target": "quarante-neuf", "why_wrong": "Write it with a hyphen.", "display_label": "Numbers"}],
    },
    "sentence_only": {"verdict": "incorrect", "score_0_4": 1, "corrected_answer": KEY, "errata": []},
    "whole_line": {
        "verdict": "partial",
        "score_0_4": 2,
        "corrected_answer": KEY,
        "errata": [{"learner_text": LEARNER, "corrected_target": KEY, "why_wrong": "Corrected line.", "display_label": "Numbers"}],
    },
    "said_right": {"verdict": "correct", "score_0_4": 4, "corrected_answer": LEARNER, "errata": []},
}


def _relecture(reading: str, language: str) -> dict:
    return refine_production_correction(
        dict(MODEL_READINGS[reading]), learner_text=LEARNER, accepted=[KEY], language=language
    )


@pytest.mark.parametrize("language", ["en", "de", "fr"])
@pytest.mark.parametrize("reading", sorted(MODEL_READINGS))
def test_named(reading: str, language: str) -> None:
    refined = _relecture(reading, language)
    assert refined["verdict"] not in {"correct", "accepted"}, f"{reading}: «quarante neuf» passed"
    assert refined["corrected_answer"] == KEY
    [erratum] = refined["errata"]
    assert (erratum["learner_text"], erratum["corrected_target"]) == ("quarante neuf", "quarante-neuf"), erratum
    why = erratum["why_wrong"]
    assert "quarante-neuf" in why and HYPHEN[language] in why.lower(), f"{reading}/{language}: the reason does not name the hyphen: {why!r}"


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize("reading", sorted(MODEL_READINGS))
def test_marked(reading: str, language: str) -> None:
    """While the solution waits: the number is marked, a reason is given, no key shown."""

    marked = solution_gate.mark(_relecture(reading, language), chance=True, language=language)
    view = solution_gate.learner_view(marked, answer_payload={"text": LEARNER})
    assert view["errata"], f"{reading}: the «What is off» box had nothing to say"
    assert [mark["text"] for mark in view["marks"]] == ["quarante neuf"], view["marks"]
    for erratum in view["errata"]:
        hint = erratum["hint"]
        assert hint and hint.strip() != LEARNER, f"{reading}: the box is the learner's own line"
        assert HYPHEN[language] in hint.lower(), f"{reading}/{language}: the hint does not say a hyphen is missing: {hint!r}"
        assert "quarante-neuf" not in hint, "the solution waits"


def test_no_variant() -> None:
    assert not is_variant_edit("quarante neuf", "quarante-neuf")
    assert not is_variant_edit("dix sept", "dix-sept")
    # The two accepted spellings stay untouched (the 1990 reform).
    assert is_variant_edit("vingt et un", "vingt-et-un")
    assert is_variant_edit("deux cents", "deux-cents")
    assert is_variant_edit("trente et une", "trente-et-une")


def test_reform_ok() -> None:
    refined = refine_production_correction(
        {"verdict": "correct", "score_0_4": 4, "corrected_answer": "J'ai vingt-et-un ans.", "errata": []},
        learner_text="J'ai vingt-et-un ans.",
        accepted=["J'ai vingt et un ans."],
        language="en",
    )
    assert not any("hyphen" in str(item.get("why_wrong") or "").lower() for item in refined.get("errata") or [])
