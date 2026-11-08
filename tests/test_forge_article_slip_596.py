"""#596 / #146: a La Forge miss whose only difference is the article names the noun.

Walk 8 Nov: «Marin cherche le clé.» for «Marin cherche la clé.» was answered with the
day's rule card («Regel: Le, la, l', les» and its «J'aime café» example); nothing said
that «clé» is feminine. The same for «la téléphone» and «Le lits». A lone article
slip is a gender slip or a number slip, and the note names which, in the learner's
language. A gap the learner typed never reads «gewählt» / «chose».
"""
from __future__ import annotations

import pytest

from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierCorrectionService

ARTICLES = "FR2_A1_ARTICLES"
CARD_EXAMPLE = "J'aime café"


def _concept() -> GrammarConcept:
    return GrammarConcept(id=9, external_id=ARTICLES, name="Le, la, l', les", level="A1", category="Articles")


def _miss(learner: str, target: str, language: str, *, choices: list[str] | None = None) -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {
        "id": "a1",
        "prompt": "Welcher Satz sagt: „Marin sucht den Schlüssel.“?",
        "correct_answer": target,
        "lesson_external_id": ARTICLES,
        "explanation": f"✗ {CARD_EXAMPLE}. → ✓ J'aime le café.",
        **({"choices": choices} if choices else {}),
    }
    result = service._correct_recognize(_concept(), "fill", {"items": [item]}, {"answers": {"a1": learner}})
    [erratum] = result["errata"]
    return erratum


def _text(erratum: dict) -> str:
    return f"{erratum['why_wrong']} {erratum['repair_hint']}"


@pytest.mark.parametrize(
    ("learner", "target", "language", "marker"),
    [
        ("Marin cherche le clé.", "Marin cherche la clé.", "de", "weiblich"),
        ("Marin cherche le clé.", "Marin cherche la clé.", "en", "feminine"),
        ("Marin cherche le clé.", "Marin cherche la clé.", "fr", "féminin"),
        ("la téléphone", "le téléphone", "de", "männlich"),
        ("la téléphone", "le téléphone", "en", "masculine"),
        ("Le lits", "Les lits", "de", "Plural"),
        ("Le lits", "Les lits", "en", "plural"),
    ],
)
def test_a_lone_article_miss_names_the_nouns_gender_or_number(
    learner: str, target: str, language: str, marker: str
) -> None:
    erratum = _miss(learner, target, language)
    text = _text(erratum)
    assert marker in text, text
    assert CARD_EXAMPLE not in text, text
    # the key's own phrase is shown, so the learner reads the noun with its article
    article_and_noun = " ".join(target.rstrip(".").split()[-2:]).lower()
    assert article_and_noun in text.lower(), text


@pytest.mark.parametrize("language", ["de", "en"])
def test_a_miss_that_is_not_an_article_slip_keeps_the_rule_card(language: str) -> None:
    erratum = _miss("Marin cherche une clé.", "Marin cherche la clé.", language)
    assert "weiblich" not in _text(erratum) and "feminine" not in _text(erratum)


@pytest.mark.parametrize(
    ("learner", "target", "marker"),
    [
        ("Un table", "Une table", "feminine"),
        ("Une livre", "Un livre", "masculine"),
        ("Un lits", "Des lits", "plural"),
        ("Les lit", "Le lit", "singular"),
        ("Les lit", "La lit", "singular"),
    ],
)
def test_gender_and_number_are_told_apart_for_each_kind_of_article(learner: str, target: str, marker: str) -> None:
    text = _text(_miss(learner, target, "en"))
    assert marker in text, text
    assert CARD_EXAMPLE not in text, text


def test_a_definite_for_an_indefinite_article_is_not_called_a_gender_slip() -> None:
    text = _text(_miss("Un clé", "La clé", "en"))
    assert "feminine" not in text and "plural" not in text, text


@pytest.mark.parametrize(
    ("language", "forbidden"),
    [("de", "gewählt"), ("en", "chose"), ("fr", "choisi")],
)
@pytest.mark.parametrize("lesson", [True, False])
def test_a_typed_gap_never_reads_chosen(language: str, forbidden: str, lesson: bool) -> None:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {"id": "g1", "prompt": "Ich habe ____ Hunger.", "correct_answer": "some"}
    if lesson:
        item["lesson_external_id"] = ARTICLES
    result = service._correct_recognize(_concept(), "fill", {"items": [item]}, {"answers": {"g1": "somes"}})
    [erratum] = result["errata"]
    assert forbidden not in _text(erratum), _text(erratum)
    assert "somes" in erratum["why_wrong"], erratum["why_wrong"]


def test_a_picked_option_still_reads_chosen() -> None:
    erratum = _miss("une", "la", "de", choices=["la", "une", "les"])
    assert "gewählt" in erratum["why_wrong"], erratum["why_wrong"]
