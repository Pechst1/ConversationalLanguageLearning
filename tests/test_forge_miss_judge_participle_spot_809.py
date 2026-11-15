"""#809 (root cause #146): three La Forge misses that still fell back to the rule card.

#799 made one classifier (``forge_grading.slip_kind``) name a slip on a choice gap. Three
paths did not reach it on the walk of 15 Nov 2026:

1. a judged sentence («Margaux cherche la téléphone.» sorted «Correct») was explained by
   the card's first trap «✗ J'aime café.», because the classifier was never fed the diff
   between the shown sentence and its right form;
2. «tu as écrivé» for «tu as écrit» was explained with the regular «-é/-i/-u» rule that
   produced «écrivé»: the classifier had no participle kind;
3. «La bague est neuve.» for «Le bague est nouvelle.» (the article fixed, another word
   changed) was labelled «Determiner choice», the category the learner got right.
"""
from __future__ import annotations

import pytest

from app.services import item_bank as ib
from app.services.forge_grading import slip_kind, slip_note, token_diff


def _concept(external_id: str, name: str, level: str, category: str):
    from app.db.models.grammar import GrammarConcept

    return GrammarConcept(external_id=external_id, name=name, level=level, category=category)


def _service(db_session, language: str = "en"):
    from app.services.atelier import AtelierCorrectionService

    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    return service


# -- 1. a judged sentence goes through the same classifier as a gap --------------


def test_a_judged_wrong_sentence_names_the_noun_like_a_choice_gap(db_session):
    concept = _concept("FR2_A11_LE_LA", "Le, la, l', les", "A1", "Articles")
    item = ib.judgement_item("judge", "Margaux cherche la téléphone.", fix="Margaux cherche le téléphone.")
    item["lesson_external_id"] = "FR2_A11_LE_LA"
    erratum = _service(db_session)._recognize_erratum(concept, "classify", item, "Correct", "À corriger")

    gap_note = slip_note(
        token_diff("Margaux cherche la téléphone.", "Margaux cherche le téléphone.", positions=True),
        "en",
        "Margaux cherche le téléphone.",
    )
    # the same text a choice gap gives for «la restaurant»
    assert gap_note and gap_note[0] == "«téléphone» is masculine in French: «le téléphone», not «la téléphone».", gap_note
    assert gap_note[0] in erratum["why_wrong"], erratum
    assert "J'aime" not in f"{erratum['why_wrong']} {erratum['repair_hint']}", erratum
    assert erratum["corrected_target"] == "Margaux cherche le téléphone."


# -- 2. an irregular participle is named as one ----------------------------------


def test_the_classifier_has_a_participle_kind():
    assert slip_kind("écrivé", "écrit") == "participle"
    assert slip_kind("prendu", "pris") == "participle"
    assert slip_kind("finé", "fini") == "participle"
    # agreement and person are not participle slips
    assert slip_kind("écrite", "écrit") is None
    assert slip_kind("est", "es") == "person"
    assert slip_kind("mange", "mangé") is None


def test_a_regularised_participle_names_the_irregular_one(db_session):
    concept = _concept("FR2_A21_PC_AVOIR", "Passé composé avec avoir", "A2", "Tenses")
    item = {
        "id": "gap", "prompt": "L'été dernier, ___ un article.", "choices": ["tu as écrit", "tu as écrire"],
        "correct_answer": "tu as écrit", "lesson_external_id": "FR2_A21_PC_AVOIR", "bank_unit": "FR2_A21_PC_AVOIR",
    }
    erratum = _service(db_session)._recognize_erratum(concept, "fill", item, "tu as écrivé", "tu as écrit")
    text = f"{erratum['why_wrong']} {erratum['repair_hint']}"
    assert "«écrire»" in erratum["why_wrong"] and "irregular" in erratum["why_wrong"], erratum
    assert "«écrit»" in erratum["why_wrong"] and "«écrivé»" in erratum["why_wrong"], erratum
    assert "-é/-i/-u" not in text, erratum


# -- 3. a fix that changed another word is named as such -------------------------


def test_a_spot_fix_that_changed_another_word_is_not_labelled_with_the_fixed_category(db_session):
    concept = _concept("FR2_A11_LE_LA", "Le, la, l', les", "A1", "Articles")
    item = {
        "id": "repair", "type": "rewrite", "instruction": "Fix the one mistake.", "instruction_key": "forge.transform",
        "source": "Le bague est nouvelle.", "source_fr": "Le bague est nouvelle.", "wrong_span": "Le bague",
        "expected_answer": "La bague est nouvelle.", "meaning": "The ring is new.", "bank_unit": "FR2_A11_LE_LA",
    }
    correction = _service(db_session)._correct_transform_rule_based(
        concept, {"items": [item]}, {"answers": {"repair": "La bague est neuve."}}
    )
    (erratum,) = correction["errata"]
    assert erratum["display_label"] != "Determiner choice", erratum
    why = erratum["why_wrong"]
    assert "fixed" in why and "«le» → «la»" in why, erratum
    assert "«neuve»" in why and "«nouvelle»" in why, erratum
    assert "J'aime" not in f"{why} {erratum['repair_hint']}", erratum


# -- guard: every A1–A2 judge item through the gap's classifier ------------------


def _judge_cases():
    bank = ib.default_bank()
    cases = []
    for unit in ib.template_units():
        if str(ib.unit_row(unit).get("level") or "") not in {"A1", "A2"}:
            continue
        for item in bank.generate(unit, 6, seed="guard-809"):
            if not item.wrong_sentences:
                continue
            judged = ib.classify_item(item, show_correct=False, lesson_external_id=unit)
            if judged:
                cases.append(pytest.param(unit, judged, id=judged["id"]))
    return cases


_CASES = _judge_cases()


def test_the_guard_covers_the_bank():
    assert len(_CASES) > 100


@pytest.mark.parametrize(("unit", "item"), _CASES)
def test_every_judged_sentence_is_explained_like_a_gap(db_session, unit, item):
    concept = _concept(unit, unit, str(ib.unit_row(unit).get("level") or "A1"), "")
    wrong, right = item["source_fr"], item["follow_up_key"]["corrected_fr"]
    service = _service(db_session)
    erratum = service._recognize_erratum(concept, "classify", item, "Correct", "À corriger")
    named = slip_note(token_diff(wrong, right, positions=True), "en", right)
    if named:
        assert named[0] in erratum["why_wrong"] and erratum["repair_hint"] == named[1], (wrong, right, erratum)
    else:
        # no named slip: the card's example is the one fitting this miss, never one
        # crossing out the form the right sentence needed.
        assert erratum["repair_hint"] in {service._repair_for(concept, wrong, right), item.get("repair_hint")}, (
            wrong, right, erratum,
        )
