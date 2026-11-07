"""#449 / #146: a La Forge miss explains the slip that was made, not the rule card.

Walk 1 Nov: «Je lui vois demain.» for «Je vois Marc demain. → Je le vois demain.»
was answered with the card of «Deux pronoms ensemble» (the order of two pronouns) and
its «Je lui le donne» example. The slip was direct vs indirect object. Walk 2 Nov:
«Je ai» for «J'ai» was answered with être vs avoir. The slip decides the note; the
rule card is the fallback for a miss with no category.
"""
from __future__ import annotations

import pytest

from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierCorrectionService

PRONOUNS = "FR2_B11_DOUBLE_PRONOUNS"
AVOIR = "FR2_A11_AVOIR"
RULE_CARD_MARKERS = ("me/te", "ordre fixe", "fixed order", "feste Reihenfolge", "Le lui")


def _concept(external_id: str, name: str) -> GrammarConcept:
    return GrammarConcept(id=7, external_id=external_id, name=name, level="B1", category="Pronouns")


def _transform_miss(learner: str, language: str) -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {
        "id": "t1",
        "type": "directed_rewrite",
        "instruction": "Replace 'Marc' with 'le', the direct object pronoun.",
        "source": "Je vois Marc demain.",
        "expected_answer": "Je le vois demain.",
    }
    result = service._correct_transform_rule_based(
        _concept(PRONOUNS, "Deux pronoms ensemble"), {"items": [item]}, {"answers": {"t1": learner}}
    )
    [erratum] = result["errata"]
    return erratum


@pytest.mark.parametrize(
    ("language", "marker"),
    [("fr", "COD"), ("en", "direct object"), ("de", "direktes Objekt")],
)
def test_lui_for_le_is_explained_as_direct_vs_indirect_object(language: str, marker: str) -> None:
    erratum = _transform_miss("Je lui vois demain.", language)
    text = f"{erratum['why_wrong']} {erratum['repair_hint']}"
    assert marker in text, text
    assert not any(card in text for card in RULE_CARD_MARKERS), text
    assert erratum["task_error_type"] != "word_order"


def test_le_for_lui_is_the_same_slip_the_other_way_round() -> None:
    service = AtelierCorrectionService(None)
    service.explanation_language = "fr"
    item = {
        "id": "t2",
        "type": "contrast_rewrite",
        "source": "Nous parlons à Paul ce soir.",
        "expected_answer": "Nous lui parlons ce soir.",
    }
    result = service._correct_transform_rule_based(
        _concept(PRONOUNS, "Deux pronoms ensemble"), {"items": [item]}, {"answers": {"t2": "Nous le parlons ce soir."}}
    )
    [erratum] = result["errata"]
    assert "COI" in erratum["why_wrong"], erratum["why_wrong"]
    assert "ordre fixe" not in erratum["why_wrong"]


def test_a_slip_with_no_category_still_gets_the_rule_card() -> None:
    erratum = _transform_miss("Je regarde demain.", "fr")
    assert "COD" not in erratum["why_wrong"]
    assert erratum["why_wrong"].startswith("Tu as écrit"), erratum["why_wrong"]
    # the card is the fallback, after the exact difference
    assert len(erratum["why_wrong"]) > len("Tu as écrit «regarde» ; ici, c’est «le».")


@pytest.mark.parametrize(
    ("language", "marker"),
    [("fr", "apostrophe"), ("en", "apostrophe"), ("de", "Apostroph")],
)
def test_je_ai_is_the_elision_not_etre_versus_avoir(language: str, marker: str) -> None:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {
        "id": "f1",
        "prompt": "Ich habe ein rotes Fahrrad",
        "correct_answer": "J'ai un vélo rouge.",
        "lesson_external_id": AVOIR,
    }
    result = service._correct_recognize(
        _concept(AVOIR, "Avoir"), "fill", {"items": [item]}, {"answers": {"f1": "Je ai un vélo rouge."}}
    )
    [erratum] = result["errata"]
    text = f"{erratum['why_wrong']} {erratum['repair_hint']}"
    assert marker in text, text
    assert "Je suis 20 ans" not in text


def test_french_copy_keeps_the_french_space_in_quotes_and_before_colons() -> None:
    """#452: «x» with no inner space, or a bare «:», in a fr row of the learner copy."""

    import re

    from app.services.learner_copy import LEARNER_COPY

    bare = re.compile(r"«[^\s\u00a0]|[^\s\u00a0]»|[^\s\u00a0:]:(?:\s|$)")
    bad = {key: row["fr"] for key, row in LEARNER_COPY.items() if row.get("fr") and bare.search(row["fr"])}
    assert not bad, bad


def test_the_miss_line_quotes_the_slip_with_the_french_space() -> None:
    from app.services.forge_grading import describe_diff, token_diff

    line = describe_diff(token_diff("Je regarde demain.", "Je le vois demain."), "fr")
    assert "« regarde »" in line, line
