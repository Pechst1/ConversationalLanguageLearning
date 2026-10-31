"""#380 / #174: an item with an English prompt accepts every correct translation.

Seen in the live walk of 30 Oct 2026: «We prefer Le Mistral, Lila.» wanted «On
préfère» and refused the standard «Nous préférons»; «They look for the post office,
Marin.» wanted «la poste» and refused «le bureau de poste». The key was one French
sentence and the English gloss (the only thing the learner reads) names neither
«on» nor «nous», neither «la poste» nor «le bureau de poste». A miss that lands
outside the rule's own forms must also say what differs in the learner's text,
not recite the day's rule.
"""

from __future__ import annotations

import pytest

from app.services import item_bank as ib
from app.services.atelier import AtelierCorrectionService

ER = "FR2_A11_ER_VERBS"
LE_LA = "FR2_A11_LE_LA"


def _bank_item(unit: str, *, startswith: str) -> ib.BankItem:
    bank = ib.default_bank()
    for seed in range(600):
        for item in bank.generate(unit, 12, seed=seed):
            if item.sentence.startswith(startswith):
                return item
    raise AssertionError(f"no item of {unit} starting {startswith!r}")


def _concept(external_id: str):
    from app.db.models.grammar import GrammarConcept

    return GrammarConcept(id=1, external_id=external_id, name="Rule of the day", level="A1", category="Grammar")


def _grade(unit: str, item: dict, answer: str, language: str = "en") -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    return service._correct_recognize(_concept(unit), "fill", {"items": [item]}, {"answers": {item["id"]: answer}})


@pytest.fixture(scope="module")
def prefer_on() -> dict:
    bank_item = _bank_item(ER, startswith="On préfère")
    payload = ib.fill_item(bank_item, lesson_external_id=ER)
    assert payload is not None
    assert payload["meaning"].startswith("We prefer")
    return payload


@pytest.fixture(scope="module")
def post_office() -> dict:
    bank_item = _bank_item(LE_LA, startswith="Je cherche la poste")
    payload = ib.fill_item(bank_item, lesson_external_id=LE_LA)
    assert payload is not None
    return payload


def test_we_prefer_accepts_nous_as_well_as_on(prefer_on: dict) -> None:
    for answer in ("Nous préférons", "nous préférons.", "On préfère"):
        result = _grade(ER, prefer_on, answer)
        assert result["verdict"] == "correct", (answer, result["errata"])


def test_nous_without_accents_is_not_called_wrong_for_the_pronoun(prefer_on: dict) -> None:
    result = _grade(ER, prefer_on, "Nous preferons")
    assert result["verdict"] == "correct"
    assert result["accent_notes"], "the accent slip is named, not hidden"


def test_a_nous_key_accepts_on_too() -> None:
    bank_item = _bank_item(ER, startswith="Nous cherchons")
    payload = ib.fill_item(bank_item, lesson_external_id=ER)
    assert payload is not None
    assert _grade(ER, payload, "On cherche")["verdict"] == "correct"


def test_post_office_accepts_le_bureau_de_poste(post_office: dict) -> None:
    for answer in ("la poste", "le bureau de poste", "Le bureau de poste."):
        result = _grade(LE_LA, post_office, answer)
        assert result["verdict"] == "correct", (answer, result["errata"])


def test_a_wrong_pronoun_is_still_wrong(prefer_on: dict) -> None:
    for answer in ("Vous préférez", "Ils préfèrent", "Nous préfère", "On préférons"):
        assert _grade(ER, prefer_on, answer)["verdict"] == "incorrect", answer


def test_a_wrong_gender_article_is_still_wrong(post_office: dict) -> None:
    assert _grade(LE_LA, post_office, "le poste")["verdict"] == "incorrect"


def test_a_miss_outside_the_rule_says_what_differs_not_the_rule(post_office: dict) -> None:
    result = _grade(LE_LA, post_office, "la gare")
    [erratum] = result["errata"]
    why = erratum["why_wrong"]
    assert "la gare" in why and "la poste" in why
    assert "the rule is not what differs" in why.lower()
    explanation = str(post_office.get("explanation") or "")
    assert not explanation or explanation not in why


def test_a_miss_inside_the_rule_still_cites_the_rule(post_office: dict) -> None:
    [erratum] = _grade(LE_LA, post_office, "le poste")["errata"]
    assert "the rule is not what differs" not in erratum["why_wrong"].lower()


def test_a_wrong_pronoun_miss_names_the_pronoun_not_the_ending_rule(prefer_on: dict) -> None:
    [erratum] = _grade(ER, prefer_on, "Vous préférez")["errata"]
    assert "Vous préférez" in erratum["why_wrong"]
    assert "the rule is not what differs" in erratum["why_wrong"].lower()


def test_every_we_item_lists_nous_and_on() -> None:
    """The structural guard: the English «we» does not choose between the two."""

    import re

    bank = ib.default_bank()
    checked = 0
    for unit in ib.template_units():
        for seed in range(4):
            for item in bank.generate(unit, 10, seed=seed):
                subject = re.split(r"[\s,]", item.sentence)[0].lower()
                if subject not in {"on", "nous"} or not item.en.startswith("We ") or re.search(r"\b(our|us)\b", item.en):
                    continue
                if ", nous" in item.sentence.lower() or item.sentence.lower().startswith("nous,"):
                    continue
                if not item.target.lower().startswith(("on ", "nous ")):
                    continue  # the pronoun is printed beside the gap, so the gap cannot change it
                starts = {re.split(r"[\s,]", answer)[0].lower() for answer in item.accepted}
                assert {"on", "nous"} <= starts, (item.sentence, item.accepted)
                checked += 1
    assert checked > 20
