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
    ids=["cle-de", "cle-en", "cle-fr", "tel-de", "tel-en", "lits-de", "lits-en"],
)
def test_names_noun(
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
def test_other_miss_keeps_card(language: str) -> None:
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
    ids=["une", "un", "des", "le", "la"],
)
def test_kind(learner: str, target: str, marker: str) -> None:
    text = _text(_miss(learner, target, "en"))
    assert marker in text, text
    assert CARD_EXAMPLE not in text, text


def test_def_vs_indef() -> None:
    text = _text(_miss("Un clé", "La clé", "en"))
    assert "feminine" not in text and "plural" not in text, text


@pytest.mark.parametrize(
    ("language", "forbidden"),
    [("de", "gewählt"), ("en", "chose"), ("fr", "choisi")],
    ids=["de", "en", "fr"],
)
@pytest.mark.parametrize("lesson", [True, False])
def test_typed_gap(language: str, forbidden: str, lesson: bool) -> None:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {"id": "g1", "prompt": "Ich habe ____ Hunger.", "correct_answer": "some"}
    if lesson:
        item["lesson_external_id"] = ARTICLES
    result = service._correct_recognize(_concept(), "fill", {"items": [item]}, {"answers": {"g1": "somes"}})
    [erratum] = result["errata"]
    assert forbidden not in _text(erratum), _text(erratum)
    assert "somes" in erratum["why_wrong"], erratum["why_wrong"]


def test_pick_chosen() -> None:
    erratum = _miss("une", "la", "de", choices=["la", "une", "les"])
    assert "gewählt" in erratum["why_wrong"], erratum["why_wrong"]


# Review of attempt 1 (#603): the noun is read at the slip's own position in the key.


@pytest.mark.parametrize(
    ("learner", "target", "language", "phrase", "marker", "not_noun"),
    [
        ("Il voit le chat et la chien.", "Il voit le chat et le chien.", "en", "le chien", "masculine", "chat"),
        ("Il voit le chat et la chien.", "Il voit le chat et le chien.", "de", "le chien", "männlich", "chat"),
        ("La table et les lit.", "La table et le lit.", "en", "le lit", "singular", "table"),
        ("La table et le lits.", "La table et les lits.", "de", "les lits", "Plural", "table"),
        ("Le lit et le table.", "Le lit et la table.", "en", "la table", "feminine", "lit»"),
    ],
    ids=["chien-en", "chien-de", "lit-en", "lits-de", "table-en"],
)
def test_repeated_article(learner: str, target: str, language: str, phrase: str, marker: str, not_noun: str) -> None:
    text = _text(_miss(learner, target, language))
    assert f"«{phrase}»" in text, text
    assert marker in text, text
    assert not_noun not in text, text


@pytest.mark.parametrize("language", ["de", "en"])
@pytest.mark.parametrize("adjective", ["petite", "grande"])
def test_adjective_is_not_the_noun(language: str, adjective: str) -> None:
    text = _text(_miss(f"Marin cherche le {adjective} clé.", f"Marin cherche la {adjective} clé.", language))
    assert "«clé»" in text and "la clé" in text, text
    assert f"«{adjective}»" not in text and f"la {adjective}" not in text, text


def test_a_slip_with_no_noun_after_it_falls_back_to_the_card() -> None:
    text = _text(_miss("Je le vois.", "Je la vois.", "en"))
    assert "feminine" not in text, text


def _judge(sentence: str, corrected: str, language: str) -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {
        "id": "j1",
        "prompt": sentence,
        "source_fr": sentence,
        "labels": ["Correct", "À corriger"],
        "correct_label": "À corriger",
        "correct_answer": "À corriger",
        "classify_kind": "judgement",
        "lesson_external_id": ARTICLES,
        "repair_hint": "✗ Je lui le donne. → ✓ Je le lui donne.",
        "follow_up_key": {"corrected_fr": corrected},
    }
    result = service._correct_recognize(_concept(), "classify", {"items": [item]}, {"answers": {"j1": "Correct"}})
    [erratum] = result["errata"]
    return erratum


@pytest.mark.parametrize("language", ["fr", "de", "en"])
def test_judge_miss_names_the_elision(language: str) -> None:
    text = _text(_judge("Il me en a parlé.", "Il m'en a parlé.", language))
    assert "m'" in text, text
    assert "Je lui le donne" not in text, text


@pytest.mark.parametrize("language", ["de", "en"])
def test_judge_miss_names_the_gender(language: str) -> None:
    text = _text(_judge("Marin cherche le clé.", "Marin cherche la clé.", language))
    assert ("weiblich" if language == "de" else "feminine") in text, text
    assert "Je lui le donne" not in text, text


def test_judge_miss_without_a_slip_keeps_the_card() -> None:
    erratum = _judge("Je lui le donne.", "Je le lui donne.", "en")
    assert "Je lui le donne" in _text(erratum), _text(erratum)
