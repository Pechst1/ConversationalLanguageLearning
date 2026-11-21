"""#774 - a miss on «Est-ce que il pleut ?» names the que → qu' elision, not the rule headline.

Live walk 14 Nov 2026 (A1.1 day 33): recall «Which one is right?», picked «Est-ce que il
pleut ?». The note said «To ask a yes/no question, raise your voice at the end, or start
with est-ce que.» - the unit's headline, which the learner had followed. What was wrong
(«que» drops its vowel before «il») was never said.

ROOT CAUSE (child of #146, sibling of #537): a ✗/✓ pair is explained only by a matching
``traps[].why`` on the unit's rule card. The card's lead pair (``contrast``) had no place
for a reason, and it is the pair the choice item is built from first, so its miss always
fell back to the unit's one-line rule. 137 cards' lead pairs had no reason at all, though
for an elision slip the answer fold already knows what changed.
"""
from __future__ import annotations

import re

import pytest

from app.services import grammar_items, grammar_units
from app.services.rule_cards import rule_card_for
from tests.test_recall_miss_feedback_shape import _wrong_option
from tests.test_wp78_practice_day import _evaluate
from tests.test_wp129_practice import concept

UNIT = "FR2_A11_QUESTIONS"
VOWEL = {"en": r"vowel", "de": r"vokal", "fr": r"voyelle"}
HEADLINE = {"en": "your voice", "de": "stimme", "fr": "voix"}


def _miss_note(external_id: str, wrong: str, language: str) -> str:
    unit = grammar_units.unit_brief(concept(external_id, 774), control_language=language)
    pair = next(p for p in unit["contrast_pairs"] if p["wrong"] == wrong)
    task = grammar_items.choose_item(unit, language=language, pair=pair)
    assert task is not None
    result = _evaluate(task, option_id=_wrong_option(task))
    assert result.correction is not None
    return result.correction.note_native


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_est_ce_que_il_miss(language: str) -> None:
    note = _miss_note(UNIT, "Est-ce que il pleut ?", language)
    assert "qu'" in note and re.search(VOWEL[language], note, re.IGNORECASE), (
        f"the miss on «Est-ce que il pleut ?» never names que → qu' before a vowel: {note!r}"
    )
    assert HEADLINE[language] not in note.lower(), f"…it restates the rule's headline: {note!r}"


def test_lead_pair_why() -> None:
    """The recall drill builds its first choice from the card's lead pair: that pair has a why."""

    card = rule_card_for(UNIT)
    assert card is not None
    unit = grammar_units.unit_brief(concept(UNIT, 774), control_language="de")
    lead = unit["contrast_pairs"][0]
    assert lead["wrong"] == grammar_items.plain(card["contrast"]["wrong"])
    assert lead.get("why"), f"the card's lead pair {lead['wrong']!r} has no reason of its own"


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_derived_elision(language: str) -> None:
    """The same slip on another card, whose lead pair has no authored why: «parce que il pleut»."""

    note = _miss_note("FR2_A12_CONNECTORS", "parce que il pleut", language)
    assert "qu'il" in note and re.search(VOWEL[language], note, re.IGNORECASE), note


def test_no_made_up_reason() -> None:
    """Only an elision is derived; any other slip keeps the card's own reason or none."""

    assert grammar_units.trap_reason("FR2_A11_ETRE", "Ils est à Lyon.", "Ils sont à Lyon.") is None


#: Cards whose lead ✗/✓ pair still has no reason (authored or an elision) on 14 Nov 2026.
#: A miss on such a pair falls back to the unit's one-line rule (#146). Lower it as
#: reasons are authored; a new card must not add to it.
UNEXPLAINED_LEAD_PAIRS = 137


def test_unexplained_ratchet() -> None:
    from app.services.rule_cards import _cards

    unexplained = sorted(
        external_id
        for external_id, card in _cards().items()
        if isinstance(card.get("contrast"), dict)
        and not grammar_units.trap_reason(external_id, card["contrast"]["wrong"], card["contrast"]["right"])
    )
    assert "FR2_A11_QUESTIONS" not in unexplained
    assert len(unexplained) <= UNEXPLAINED_LEAD_PAIRS, (
        f"{len(unexplained)} cards' lead pairs have no reason (was {UNEXPLAINED_LEAD_PAIRS}): {unexplained}"
    )
