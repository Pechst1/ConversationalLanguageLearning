"""#1067: La Forge's typed gap told «Tu a dit» «Another word of the line differs, not only
the rule's form», though «a → as» is the avoir rule's own form.

Explore walk 25 Nov 2026 (``a2-en``, day 1, «Passé composé with avoir», Level 3). The
gap «___ bonjour à Margaux samedi dernier.» («You said hello to Margaux last Saturday.»)
had two choices, «Tu as dit» / «Tu as dire», and declared ``target_span`` «Tu as dit».
``_miss_outside_the_rule`` guessed the rule's form from the words the choices share, so
«tu» and «as» counted as fixed and a learner without «as» was judged outside the rule:
the slip note («With «tu», «avoir» is «as», not «a».») was skipped. On day 2 the same
slip on an item with three choices («tu es étudié» among them) was named right.

What the rule is about is read from the span the item declares: a slip of form inside it
(another form of the same word: «a» for «as») is the rule's. A different word («la gare»
for «la poste», #380) is still «Another word …».
"""
from __future__ import annotations

import pytest

from app.services.atelier import AtelierCorrectionService

UNIT = "FR2_A21_PASSE_COMPOSE_AVOIR"

WALK_ITEM = {
    "id": "forge-1067-tu-as-dit",
    "prompt": "___ bonjour à Margaux samedi dernier.",
    "meaning": "You said hello to Margaux last Saturday.",
    "choices": ["Tu as dit", "Tu as dire"],
    "accepted_answers": ["Tu as dit"],
    "target_span": "Tu as dit",
    "lesson_external_id": UNIT,
}

#: The words the why must say, per explanation language.
NAMED = {
    "en": ("«tu»", "«as»", "«a»"),
    "de": ("«tu»", "«as»", "«a»"),
}


def _concept():
    from app.db.models.grammar import GrammarConcept

    return GrammarConcept(id=1, external_id=UNIT, name="Passé composé with avoir", level="A2", category="Grammar")


def _grade(answer: str, language: str) -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    result = service._correct_recognize(
        _concept(), "fill", {"items": [dict(WALK_ITEM)]}, {"answers": {WALK_ITEM["id"]: answer}}
    )
    assert result["verdict"] == "incorrect", result
    [erratum] = result["errata"]
    return erratum


@pytest.mark.parametrize("language", ["en", "de"])
def test_a_slip_inside_the_declared_span_is_named_as_the_rules_form(language: str) -> None:
    erratum = _grade("Tu a dit", language)
    why = erratum["why_wrong"]
    assert "another word of the line differs" not in why.lower(), f"«Tu a dit» was blamed on another word: {why}"
    assert "ein anderes wort der zeile" not in why.lower(), why
    for word in NAMED[language]:
        assert word in why, f"the why does not name {word}: {why}"


def test_the_right_line_is_still_right() -> None:
    service = AtelierCorrectionService(None)
    service.explanation_language = "en"
    result = service._correct_recognize(
        _concept(), "fill", {"items": [dict(WALK_ITEM)]}, {"answers": {WALK_ITEM["id"]: "Tu as dit"}}
    )
    assert result["verdict"] == "correct", result


def test_another_word_in_the_span_is_still_another_word() -> None:
    """«Vous avez dit»: the subject is another word, not a form of «tu» (#380 stays)."""

    why = _grade("Vous avez dit", "en")["why_wrong"]
    assert "another word of the line differs" in why.lower(), why
