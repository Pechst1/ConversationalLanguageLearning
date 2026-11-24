"""#1044: La Forge said «3 corrections», listed one and left «je ai» (twice) unmarked.

Live walk 24 Nov 2026 (A1.1, day 42), La Forge item 2/4 (avoir). The learner wrote
«Romy demande combien annees je ai. Je ai soixante-deux ans.» The model listed three
fixes: «combien annees» -> «quel âge», and «je ai» -> «j'ai» once for each place it
stands. A stretch that stands twice was never placed (an erratum carries no offset),
so neither «je ai» was marked, the line the gaps make was never built, and the model's
rewrite was then refused as a whole: the sheet printed the learner's own line as its
correction. The count came from the errata (3), the list from the notes (one per
issue) and the marks from what could be placed (1).
"""
from __future__ import annotations

import difflib
import re

LEARNER = "Romy demande combien annees je ai. Je ai soixante-deux ans."
MODEL_LINE = "Romy demande quel âge j'ai. J'ai soixante-deux ans."
#: The sheet's «One possible answer»: a rewrite past the listed fixes.
WALK_LINE = "Romy demande ton âge. J'ai soixante-deux ans."
AGE_NOTE = "“Combien d’années” asks for a number of years; this context asks for age, so use “quel âge”."
ELISION_NOTE = "Before a vowel, «je» becomes «j'»: «j'ai»."


def _erratum(wrong: str, fix: str, note: str) -> dict:
    return {
        "item_id": "", "display_label": "Grammar", "learner_text": wrong, "corrected_target": fix,
        "why_wrong": note, "repair_hint": "", "severity": 2, "task_error_type": "grammar",
    }


def _model_result(line: str = MODEL_LINE) -> dict:
    return {
        "verdict": "partial",
        "score_0_4": 2.0,
        "errata": [
            _erratum("combien annees", "quel âge", AGE_NOTE),
            _erratum("je ai", "j'ai", ELISION_NOTE),
            _erratum("Je ai", "J'ai", ELISION_NOTE),
        ],
        "corrected_answer": line,
        "missing_targets": [],
        "lexical_gaps": [],
    }


def _refined(line: str = MODEL_LINE) -> dict:
    from app.services.forge_grading import refine_production_correction

    return refine_production_correction(
        _model_result(line), learner_text=LEARNER, accepted=["J'ai soixante-deux ans."], language="en"
    )


def _changed_learner_words(line: str, corrected: str) -> list[tuple[int, int]]:
    """Character spans of the learner's words that the corrected line changes."""

    words = [(match.start(), match.end(), match.group().lower()) for match in re.finditer(r"[^\s.,!?]+", line)]
    fixed = [match.group().lower() for match in re.finditer(r"[^\s.,!?]+", corrected)]
    matcher = difflib.SequenceMatcher(a=[word for _s, _e, word in words], b=fixed, autojunk=False)
    changed: list[tuple[int, int]] = []
    for tag, a0, a1, _b0, _b1 in matcher.get_opcodes():
        if tag != "equal":
            changed.extend((words[at][0], words[at][1]) for at in range(a0, a1))
    return changed


def test_every_changed_word_is_marked_in_the_repair_view() -> None:
    from app.services.atelier import repair_parts
    from app.services.solution_gate import marks_for

    refined = _refined()
    corrected = str(refined["corrected_answer"])
    assert corrected.strip() != LEARNER, f"the sheet printed the learner's own line as its correction: «{corrected}»"

    parts = repair_parts(LEARNER, refined["errata"])
    assert parts is not None, "the corrections could not be placed: the line is retyped whole, nothing is marked"
    marked = [(mark["start"], mark["end"]) for mark in marks_for(LEARNER, refined["errata"])]
    unmarked = [
        LEARNER[start:end]
        for start, end in _changed_learner_words(LEARNER, corrected)
        if not any(a <= start and end <= b for a, b in marked)
    ]
    assert not unmarked, f"changed but not marked: {unmarked} (marks: {[LEARNER[a:b] for a, b in marked]})"
    # «je ai» -> «j'ai» is marked both times it stands.
    assert [LEARNER[a:b].lower() for a, b in marked].count("je ai") == 2, [LEARNER[a:b] for a, b in marked]


def test_filling_every_gap_gives_the_printed_line() -> None:
    from app.services.atelier import repair_line_from_parts

    refined = _refined()
    filled = repair_line_from_parts(LEARNER, refined["errata"])
    assert filled == refined["corrected_answer"], (filled, refined["corrected_answer"])


def test_a_rewrite_past_the_listed_fixes_is_never_the_learners_own_line() -> None:
    """The walk's sheet printed «Romy demande combien annees je ai…» back as the correction."""

    refined = _refined(WALK_LINE)
    assert refined["corrected_answer"] == WALK_LINE, refined["corrected_answer"]


def test_a_stretch_named_once_where_it_stands_twice_is_still_not_guessed() -> None:
    """One «partie» -> «parti» in «Elle est partie et il est partie» could be either."""

    from app.services.atelier import repair_parts

    assert repair_parts("Elle est partie et il est partie", [_erratum("partie", "parti", "x")]) is None
    both = repair_parts("Elle est partie et il est partie", [_erratum("partie", "parti", "x")] * 2)
    assert both is not None and [part["wrong"] for part in both if "wrong" in part] == ["partie", "partie"]
