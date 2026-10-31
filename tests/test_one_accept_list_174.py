"""#174 / #380: a right answer is judged against every right way to say it.

La Forge's free sentence round judged «Nous préférons Le Mistral, Lila.» against
the one example «On préfère …» (the nightly story score, PR #422, still counted it
wrong), and the journey's recall refused «un appart» for «flat, apartment» (walk
31 Oct). One accept-list now widens the stored answers: the other «we» when the
English says «we», and a noun's other right word, the article following its
gender.
"""
from __future__ import annotations

import pytest

from app.services.answer_acceptance import judge, noun_variants, on_nous_variants, widened_answers
from app.services.atelier import _accepted_answers
from app.services.forge_grading import LOCAL_RIGHT, production_local_check


def _payload(prompt: str, example: str) -> dict:
    return {"round": "sentence", "items": [{"id": "x", "type": "translate", "prompt": prompt, "example_answer": example}]}


@pytest.mark.parametrize(
    "prompt,example,answer",
    [
        ("We prefer Le Mistral, Lila.", "On préfère Le Mistral, Lila.", "Nous préférons Le Mistral, Lila."),
        ("We prefer Le Mistral, Lila.", "On préfère Le Mistral, Lila.", "nous préférons le Mistral, Lila"),
        ("We don't drink water.", "On ne boit pas d'eau.", "Nous ne buvons pas d'eau."),
        ("I am at the Mistral with Marin and we drink coffee.",
         "Je suis au Mistral avec Marin et on boit du café.", "Je suis au Mistral avec Marin et nous buvons du café."),
        ("We leave the cat at Lila's.", "Nous laissons le chat chez Lila.", "On laisse le chat chez Lila."),
        ("They look for the post office.", "Ils cherchent la poste.", "Ils cherchent le bureau de poste."),
        ("Marin has a painting in the living room.", "Marin a un tableau dans le salon.",
         "Marin a une peinture dans le salon."),
    ],
)
def test_a_free_sentence_that_is_another_right_way_is_right_before_the_model_reads_it(prompt, example, answer):
    accepted = _accepted_answers(_payload(prompt, example))
    assert production_local_check(None, answer, example, accepted)["local_status"] == LOCAL_RIGHT


@pytest.mark.parametrize(
    "prompt,example,answer",
    [
        ("We prefer Le Mistral, Lila.", "On préfère Le Mistral, Lila.", "Nous préfère Le Mistral, Lila."),
        ("We prefer Le Mistral, Lila.", "On préfère Le Mistral, Lila.", "On préférons Le Mistral, Lila."),
        ("We look for our watch.", "Nous cherchons notre montre.", "On cherche notre montre."),
        ("I prefer Le Mistral.", "Je préfère Le Mistral.", "Nous préférons Le Mistral."),
        ("They look for the post office.", "Ils cherchent la poste.", "Ils cherchent la bureau de poste."),
        ("Marin has a black painting.", "Marin a un tableau noir.", "Marin a une peinture noir."),
    ],
)
def test_a_wrong_sentence_stays_wrong(prompt, example, answer):
    accepted = _accepted_answers(_payload(prompt, example))
    assert production_local_check(None, answer, example, accepted)["local_status"] != LOCAL_RIGHT


def test_the_recall_takes_un_appart_for_appartement():
    assert judge("un appart", ["appartement"], article_optional=True).correct
    assert judge("l'appart", ["l'appartement"], article_optional=True).correct
    assert not judge("une appart", ["appartement"], article_optional=True).correct
    miss = judge("une maison", ["appartement"], article_optional=True)
    assert not miss.correct and miss.expected == "appartement", "a miss names the item's own answer"


def test_the_other_we_follows_the_verb():
    assert on_nous_variants("On préfère le café.") == ["nous préférons le café"]
    assert on_nous_variants("Nous préférons le café.") == ["on préfère le café"]
    assert on_nous_variants("On se lève tôt.") == ["nous nous levons tôt"]
    assert on_nous_variants("Nous nous appelons demain.") == ["on s'appelle demain"]
    assert on_nous_variants("Il nous voit.") == [], "an object «nous» is not the subject"


def test_a_noun_swap_follows_the_gender_and_never_redoes_an_adjective():
    assert noun_variants("Ils cherchent la poste.") == ["ils cherchent le bureau de poste"]
    assert noun_variants("Marin a un tableau noir.") == []
    assert widened_answers(["On cherche sa montre."], english="We look for our watch.") == ["On cherche sa montre."]


def test_a_phone_may_be_a_portable():
    # Walk 24 Oct (a1-de): «Margaux hat ein Handy im Wohnzimmer» refused «un portable».
    assert judge("Margaux a un portable dans le salon.", ["Margaux a un téléphone dans le salon."]).correct
