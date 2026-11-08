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



def test_a_noun_swap_never_changes_another_word_or_sense():
    # Review on #424: agreement further on, a verb homograph, a word with another sense.
    assert noun_variants("Le miroir est petit.") == []
    assert noun_variants("Marin a un tableau très ancien.") == []
    assert not judge("Je portable à ma mère.", ["Je téléphone à ma mère."], typo=False).correct
    assert not judge("Je mange un miroir.", ["Je mange une glace."], typo=False).correct


# ---------------------------------------------------------------------------
# #592: «X et moi» is «we» too (live walk 8 Nov 2026, the «On = we» drill)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "Romy et moi envoyons une lettre.",
        "Romy et moi, nous envoyons une lettre.",
        "Romy et moi, on envoie une lettre.",
    ],
    ids=["no_pronoun", "nous", "on"],
)
def test_on_drill_takes_nous_for_x_and_i(answer):
    # The prompt says «Romy and I send a letter.», never «with on»; the key is the
    # rule's «on» form. Every right way to say «we» counts.
    payload = _payload("Say it in French: “Romy and I send a letter.”", "Romy et moi, on envoie une lettre.")
    accepted = _accepted_answers(payload)
    assert production_local_check(None, answer, "Romy et moi, on envoie une lettre.", accepted)["local_status"] == LOCAL_RIGHT, accepted


@pytest.mark.parametrize(
    "answer",
    [
        "Romy et moi envoie une lettre.",  # the «on» verb form with a plural subject
        "Romy et moi, on envoyons une lettre.",
        "Romy envoyons une lettre.",  # «et moi» dropped: not «we»
    ],
    ids=["on_verb_form", "on_plural", "no_et_moi"],
)
def test_nous_for_x_and_i_stays_exact(answer):
    payload = _payload("Say it in French: “Romy and I send a letter.”", "Romy et moi, on envoie une lettre.")
    accepted = _accepted_answers(payload)
    assert production_local_check(None, answer, "Romy et moi, on envoie une lettre.", accepted)["local_status"] != LOCAL_RIGHT


def test_other_we_follows_x_et_moi():
    from_on = on_nous_variants("Romy et moi, on envoie une lettre.")
    assert "romy et moi, nous envoyons une lettre" in from_on
    assert "romy et moi envoyons une lettre" in from_on
    assert "romy et moi, on envoie une lettre" in on_nous_variants("Romy et moi envoyons une lettre.")
    assert "romy et moi, on envoie une lettre" in on_nous_variants("Romy et moi, nous envoyons une lettre.")
    assert on_nous_variants("Il parle à Romy et moi.") == [], "an object «moi» is not the subject"


def test_no_on_drill_rejects_nous():
    # A table over the rule's drills: whatever the bank generates, the «nous» way of
    # the same sentence is accepted wherever the English says «we» or «X and I».
    from app.services.item_bank import default_bank

    bank = default_bank()
    checked = 0
    for seed in ("a", "b", "c"):
        for item in bank.generate("FR2_A11_ON_NOUS", 40, seed=seed):
            accepted = widened_answers(item.accepted, english=item.en)
            for key in item.accepted:
                for variant in on_nous_variants(key):
                    checked += 1
                    assert judge(variant, accepted).correct, (item.en, key, variant)
    assert checked > 20


def test_on_drill_key_has_a_line_without_on():
    # The bank conjugates the verb, so its key holds the «nous» way as well as the
    # rule's «on» one (#592): a frame that writes «et moi» or «Nous,» itself says so.
    import re

    from app.services.item_bank import default_bank

    for seed in ("a", "b"):
        for item in default_bank().generate("FR2_A11_ON_NOUS", 40, seed=seed):
            assert any(not re.search(r"\bon\b", key.lower()) for key in item.accepted), (item.en, item.accepted)
