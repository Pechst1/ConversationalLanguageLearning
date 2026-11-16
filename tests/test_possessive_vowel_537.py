"""#537 - «ma amie» is explained with the vowel, not with «the owner vs the thing owned».

Live walk 5 Nov 2026: the possessives rule card showed «ma sœur» and then «Wrong: ma
amie. Right: mon amie» with the exception nowhere in its headline rule; the recall drill
«Which one is right? mon amie / ma amie» answered a miss with the unit's one-line rule
(«follow the thing owned, not the owner»), and a Forge item «ma affiche / mon affiche»
quoted the same line.

ROOT CAUSE: a unit has one `rule_short`, and every miss on every one of its traps (the
vowel, the masculine noun, leur/leurs) was explained with it. The reason that belongs to
the trap (`traps[].why` on the unit's rule card) was authored and never read.
"""
from __future__ import annotations

import pytest

from app.services import grammar_items, grammar_units
from app.services.rule_cards import rule_card_for
from tests.test_recall_miss_feedback_shape import _wrong_option
from tests.test_wp78_practice_day import _evaluate
from tests.test_wp129_practice import concept

UNIT = "FR2_A11_POSSESSIVES"
VOWEL = {"en": r"vowel", "de": r"vokal", "fr": r"voyelle"}
OWNER = {"en": "not the owner", "de": "nicht nach dem besitzer", "fr": "pas avec le possesseur"}


def _mentions_vowel(text: str, language: str) -> bool:
    import re

    return re.search(VOWEL[language], text, re.IGNORECASE) is not None


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_the_rule_card_names_the_vowel_exception(language: str) -> None:
    card = rule_card_for(UNIT)
    assert card is not None
    rule = card["rule"][language]
    assert _mentions_vowel(rule, language), f"the card's rule never names the vowel exception: {rule!r}"
    assert "mon" in rule and "amie" in rule, "the rule shows the exception with the card's own example"


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_a_miss_on_mon_amie_is_explained_with_the_vowel(language: str) -> None:
    unit = grammar_units.unit_brief(concept(UNIT, 537), control_language=language)
    pair = next(p for p in unit["contrast_pairs"] if p["wrong"] == "ma amie")
    task = grammar_items.choose_item(unit, language=language, pair=pair)
    assert task is not None
    assert {o["text_fr"] for o in task.options} == {"ma amie", "mon amie"}
    result = _evaluate(task, option_id=_wrong_option(task))
    assert result.correction is not None
    note = result.correction.note_native
    assert _mentions_vowel(note, language), f"the miss on «ma amie» is explained with: {note!r}"
    assert OWNER[language] not in note.lower(), f"…and the reason points at the owner: {note!r}"


def test_every_trap_of_the_unit_keeps_its_own_reason() -> None:
    """Not only the vowel: «sa livre» is explained by the noun's gender."""

    unit = grammar_units.unit_brief(concept(UNIT, 537), control_language="en")
    pair = next(p for p in unit["contrast_pairs"] if p["wrong"] == "Marie cherche sa livre.")
    task = grammar_items.choose_item(unit, language="en", pair=pair)
    result = _evaluate(task, option_id=_wrong_option(task))
    assert "masculine" in result.correction.note_native.lower(), result.correction.note_native
    assert not _mentions_vowel(result.correction.note_native, "en")


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_the_one_line_rule_names_the_exception_too(language: str) -> None:
    """The hint and the Forge quote `rule_short`: it must not teach the opposite of the card."""

    unit = grammar_units.unit_brief(concept(UNIT, 537), control_language=language)
    assert _mentions_vowel(unit["rule_short_native"], language), unit["rule_short_native"]


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_the_forge_explains_ma_affiche_with_the_vowel(language: str) -> None:
    """Same slip on a Forge repair item built from the bank («ma affiche → mon affiche»)."""

    from app.services.atelier import AtelierCorrectionService

    item = {
        "id": "fr2-a11-possessives-repair-0",
        "bank_unit": UNIT,
        "type": "rewrite",
        "source": "Je cherche ma affiche.",
        "expected_answer": "Je cherche mon affiche.",
    }
    service = AtelierCorrectionService.__new__(AtelierCorrectionService)
    service.explanation_language = language
    why = service._why_for(concept(UNIT, 537), item)
    assert _mentions_vowel(why, language), f"the Forge explains «ma affiche» with: {why!r}"
    assert OWNER[language] not in why.lower(), why
