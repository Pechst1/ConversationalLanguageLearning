"""#271 / #146: a word-bank miss that breaks the order the rule teaches cites the rule.

Walk 2026-10-21: «Tu peux le me prêter demain ?» for «Tu peux me le prêter demain ?»
was marked «Ordre des mots» in the unit «Deux pronoms ensemble». The order of the two
pronouns IS the day's rule. Whether a reordering is the rule or just other words
moving is decided from the rule's own elements (the pronoun cluster, the ne … pas
frame), by one function both word-bank paths use, whether or not the item carries a
``target_span``.
"""
from __future__ import annotations

import pytest

from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierCorrectionService, _join_french_tokens, _tokenize_french_sentence

PRONOUNS = "FR2_B11_DOUBLE_PRONOUNS"
NEGATION = "FR2_A21_PC_NEGATION"
WORD_ORDER_LABELS = {"Ordre des mots", "Word order", "Wortstellung"}


def _concept(external_id: str, name: str = "Deux pronoms ensemble") -> GrammarConcept:
    return GrammarConcept(id=7, external_id=external_id, name=name, level="B1", category="Pronouns")


def _item(sentence: str, *, span: str | None = None, lesson: str | None = None) -> dict:
    answer = _tokenize_french_sentence(sentence)
    item = {
        "id": "fallback-bank-1",
        "prompt": "Build the full French sentence.",
        "tokens": sorted(answer),
        "answer_tokens": answer,
        "correct_answer": _join_french_tokens(answer),
    }
    if span:
        item["target_span"] = span
    if lesson:
        item["lesson_external_id"] = lesson
    return item


def _miss(concept: GrammarConcept, item: dict, learner: str, language: str) -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    tokens = _tokenize_french_sentence(learner)
    result = service._correct_recognize(concept, "word_bank", {"items": [item]}, {"answers": {item["id"]: tokens}})
    assert result["verdict"] == "incorrect"
    [erratum] = result["errata"]
    return erratum


@pytest.mark.parametrize("language", ["fr", "de", "en"])
@pytest.mark.parametrize("lesson", [None, PRONOUNS])
def test_swapping_the_two_pronouns_cites_the_rule_and_its_order(language: str, lesson: str | None) -> None:
    item = _item("Tu peux me le prêter demain ?", lesson=lesson)
    erratum = _miss(_concept(PRONOUNS), item, "Tu peux le me prêter demain ?", language)
    assert erratum["task_error_type"] != "word_order", erratum
    assert erratum["display_label"] not in WORD_ORDER_LABELS, erratum
    # The order the rule fixes (me/te/nous/vous before le/la/les) is named.
    assert "me/te" in erratum["why_wrong"], erratum["why_wrong"]
    assert "me le" in erratum["corrected_target"]


@pytest.mark.parametrize("language", ["fr", "de", "en"])
def test_moving_only_other_words_is_still_word_order(language: str) -> None:
    item = _item("Tu peux me le prêter demain ?")
    erratum = _miss(_concept(PRONOUNS), item, "Demain tu peux me le prêter ?", language)
    assert erratum["task_error_type"] == "word_order", erratum
    assert erratum["display_label"] in WORD_ORDER_LABELS


def test_le_lui_and_lui_en_are_ordered_by_the_same_rule() -> None:
    erratum = _miss(_concept(PRONOUNS), _item("Je le lui envoie ce soir."), "Je lui le envoie ce soir.", "fr")
    assert erratum["task_error_type"] != "word_order"
    erratum = _miss(_concept(PRONOUNS), _item("Je lui en parle demain."), "Je en lui parle demain.", "fr")
    assert erratum["task_error_type"] != "word_order"


def test_ne_pas_around_the_verb_is_the_rule_not_word_order() -> None:
    concept = _concept(NEGATION, "La négation au passé composé")
    item = _item("Je n'ai pas mangé de pain.")
    broken = _miss(concept, item, "Je ne pas ai mangé de pain.", "fr")
    assert broken["task_error_type"] != "word_order", broken
    moved = _miss(concept, item, "De pain je n'ai pas mangé.", "fr")
    assert moved["task_error_type"] == "word_order", moved


def test_a_unit_that_does_not_teach_an_order_keeps_word_order() -> None:
    concept = _concept("FR2_A11_ETRE", "Je suis, tu es")
    erratum = _miss(concept, _item("Ils sont au marché avec Marin."), "Ils sont avec Marin au marché.", "fr")
    assert erratum["task_error_type"] == "word_order"


def test_the_shown_correction_keeps_the_space_before_a_question_mark() -> None:
    erratum = _miss(_concept(PRONOUNS), _item("Tu peux me le prêter demain ?"), "Tu peux le me prêter demain ?", "fr")
    assert erratum["corrected_target"].endswith("demain ?"), erratum["corrected_target"]
    assert erratum["learner_text"].endswith("demain ?"), erratum["learner_text"]
