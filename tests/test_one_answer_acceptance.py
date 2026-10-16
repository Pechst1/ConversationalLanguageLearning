"""Root cause #174 — a right answer is judged against one stored string.

Guard: every exercise path that grades a typed or built French line judges it
against the item's whole list of right answers through
``answer_acceptance.judge``. A table of correct variants must pass on each path,
and a miss whose target form is right must never cite the concept's rule.
"""
from __future__ import annotations

import pytest

from app.services.answer_acceptance import item_keys, judge, order_variants
from app.services.atelier import AtelierCorrectionService
from app.services.forge_grading import matches_accepted, production_local_check
from tests.test_atelier import _concept

TARGET = "Ils sont au marché du canal avec Marin."
TILES = ["Ils", "sont", "au", "marché", "du", "canal", "avec", "Marin", "."]

# The table of correct variants the Done-when names.
VARIANTS = [
    pytest.param("Ils sont au marché du canal avec Marin.", id="the key"),
    pytest.param("ils sont au marché du canal avec Marin", id="lowercase, no final period"),
    pytest.param("Ils sont au marché du canal avec Marin !", id="other final mark"),
    pytest.param("Ils sont au marché du canal avec Marin .", id="space before the period"),
]
# Only a tile build has no free word choice, so only it takes the other orders.
ORDERS = [
    pytest.param("Ils sont avec Marin au marché du canal.", id="other correct word order"),
    pytest.param("ILS SONT AVEC MARIN AU MARCHÉ DU CANAL", id="other order, capitals"),
]
APOSTROPHE_TARGET = "J'habite à Metz, c'est une petite ville."


def _item(**extra):
    return {
        "id": "build-1",
        "answer_tokens": TILES,
        "tokens": TILES,
        "correct_answer": TARGET,
        "lesson_external_id": "FR_A2_NEG_001",
        **extra,
    }


def _correct(db_session, mode, item, answer):
    concept = _concept(db_session, "FR_A2_NEG_001")
    return AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode=mode,
        exercise_id="FR_A2_NEG_001:guard",
        prompt_payload={"items": [item]},
        answer_payload={"answers": {item["id"]: answer}},
    )


@pytest.mark.parametrize("answer", [*VARIANTS, *ORDERS])
def test_a_tile_build_accepts_every_correct_variant(db_session, answer):
    learner = answer.split() if answer.count(" ") else [answer]
    correction = _correct(db_session, "word_bank", _item(), learner)
    assert correction["verdict"] == "correct", correction["errata"]
    assert correction["errata"] == []


@pytest.mark.parametrize("answer", VARIANTS)
def test_a_typed_rewrite_accepts_every_correct_variant(db_session, answer):
    concept = _concept(db_session, "FR_A2_NEG_001")
    item = {"id": "t1", "source": "Ils est au marché.", "expected_answer": TARGET}
    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="FR_A2_NEG_001:guard-t",
        prompt_payload={"items": [item]},
        answer_payload={"answers": {"t1": answer}},
    )
    assert correction["verdict"] == "correct", correction["errata"]


@pytest.mark.parametrize("answer", VARIANTS)
def test_free_use_recognises_every_correct_variant(answer):
    assert matches_accepted(answer, [TARGET])
    assert production_local_check(None, answer, TARGET, [TARGET])["local_status"] == "right"


@pytest.mark.parametrize(
    "answer",
    [
        "J'habite à Metz, c'est une petite ville.",
        "J’habite à Metz, c’est une petite ville.",
        "j‘habite à Metz c‘est une petite ville",
        "J' habite à Metz, c' est une petite ville",
    ],
)
def test_straight_and_typographic_apostrophes_are_one_answer(answer):
    assert judge(answer, [APOSTROPHE_TARGET], typo=False).correct
    assert matches_accepted(answer, [APOSTROPHE_TARGET])


@pytest.mark.parametrize("answer", ["Tu viens ?", "tu viens?", "Tu viens", "Tu viens ?"])
def test_a_question_mark_with_or_without_the_space_is_one_answer(answer):
    assert judge(answer, ["Tu viens ?"], typo=False).correct


def test_a_missing_accent_on_a_word_the_item_does_not_test_is_accepted_and_named():
    verdict = judge("elle prefere Marin", ["Elle préfère Marin."], typo=False)
    assert verdict.correct and verdict.accent_slip


def test_an_item_lists_its_variants_and_a_tile_build_its_other_orders():
    assert order_variants(TARGET) == ["ils sont avec marin au marché du canal"]
    keys = item_keys({"accepted_answers": ["Ils sont au canal."]}, TARGET, tiles=True)
    assert TARGET in keys and "Ils sont au canal." in keys
    assert any("avec marin au" in key for key in keys)
    # Never invented for a sentence it cannot read safely.
    assert order_variants("Je suis à côté de Marin au marché.") == []
    assert order_variants("Il mange une pomme.") == []


def test_other_words_are_still_wrong():
    assert not judge("Ils sont avec Marie au marché du canal.", item_keys(_item(), TARGET, tiles=True), typo=False).correct


def test_an_order_only_miss_never_cites_the_rule(db_session):
    # Not an adjunct order the item knows: the words are right, the order is not.
    item = _item(correct_answer="Ils sont jeunes à Metz.", answer_tokens=["Ils", "sont", "jeunes", "à", "Metz", "."])
    correction = _correct(db_session, "word_bank", item, ["jeunes", "Ils", "sont", "à", "Metz"])
    assert correction["verdict"] != "correct"
    assert correction["errata"], "the miss is still a miss"
    for erratum in correction["errata"]:
        said = f"{erratum['why_wrong']} {erratum['repair_hint']} {erratum['display_label']}".casefold()
        assert "regel" not in said and "rule" not in said and "règle" not in said
        assert "order" in said or "reihenfolge" in said or "ordre" in said


def test_a_wrong_form_still_cites_the_rule(db_session):
    item = _item(correct_answer="Ils sont jeunes.", answer_tokens=["Ils", "sont", "jeunes", "."])
    correction = _correct(db_session, "word_bank", item, ["Ils", "est", "jeunes"])
    assert correction["verdict"] != "correct"
