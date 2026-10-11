"""EXERCISE-QA 2026-10-03 — one answer-acceptance contract, run through the real graders.

``app/services/answer_acceptance.py`` decides what is typography and what is
French. This table is the contract: every row is a tricky answer a real learner
types (an iPhone's U+2018/U+2019, a German keyboard without «œ», a missing
accent, one slipped letter, a dropped elision) and the verdict the product owes
them. It runs through the contract itself **and** through every grader that
takes a typed answer and is routed through it:

* the journey's recall grader (``journey_learning.answer_matches``: short
  answer, transform, the Rappel's coach scene);
* the erratum review (``error_memory.review_answer_repairs``);
* l'Éclair's server check (``eclair.grade_answers``).
"""
from __future__ import annotations

import unicodedata

import pytest

from app.services.answer_acceptance import (
    feedback_note,
    fold_typography,
    is_typo_of,
    judge,
    on_nous_variants,
    question_variants,
)
from app.services.eclair import grade_answers
from app.services.error_memory import review_answer_repairs
from app.services.journey_learning import answer_matches, fold_for_comparison

NFD = unicodedata.normalize("NFD", "école")

#: (learner answer, accepted answer, accepted?, note) — note is the verdict's
#: ``note`` (``None``: nothing to say). Lenient accents, typo tolerance on: the
#: defaults every typed-answer surface uses.
TRICKY: list[tuple[str, str, bool, str | None]] = [
    # -- typography never counts -------------------------------------------
    ("S’il vous plaît", "s'il vous plaît", True, None),
    ("s‘il vous plaît", "s'il vous plaît", True, None),
    ("s`il vous plaît", "s'il vous plaît", True, None),
    ("j' aime le café", "J'aime le café.", True, None),
    ("Où est la gare ?", "où est la gare", True, None),
    ("Où est la gare ?", "Où est la gare ?", True, None),
    ("«Bonjour»", "Bonjour", True, None),
    ("Est -ce que tu viens?", "Est-ce que tu viens ?", True, None),
    ("est‑ce que tu viens", "Est-ce que tu viens ?", True, None),
    (NFD, "école", True, None),
    ("  BONJOUR   Madame ", "Bonjour madame", True, None),
    # -- ligatures: a German keyboard has no «œ» ---------------------------
    ("soeur", "sœur", True, None),
    ("coeur", "cœur", True, None),
    ("un oeuf", "un œuf", True, None),
    ("sur", "sœur", False, None),
    # -- accents: lenient on spelling, strict on grammar ---------------------
    ("tres bien", "très bien", True, "accent"),
    ("francais", "français", True, "accent"),
    ("ecole", "école", True, "accent"),
    ("fenetre", "fenêtre", True, "accent"),
    ("il a mange", "il a mangé", False, "accent"),
    ("ou est la gare", "où est la gare", False, "accent"),
    ("a la gare", "à la gare", False, "accent"),
    ("Il à mangé", "Il a mangé", False, "accent"),
    ("la-bas", "là-bas", True, "accent"),
    # -- one typo, never another form ----------------------------------------
    ("beacoup", "beaucoup", True, "typo"),
    ("appartment", "appartement", True, "typo"),
    ("bonjur", "bonjour", True, "typo"),
    ("un apartement", "un appartement", True, "typo"),
    ("je parles", "je parle", False, "form"),
    ("nous vendions", "nous vendons", False, "form"),
    ("elle est allé", "elle est allée", False, "form"),
    ("une petit maison", "une petite maison", False, "form"),
    ("nous mangons", "nous mangeons", False, "form"),
    ("les enfants mange", "les enfants mangent", False, "form"),
    ("chasse", "chaise", False, None),
    ("Je ne bois pas du café", "Je ne bois pas de café", False, "form"),
    ("Si tu viendras, je partirai", "Si tu viens, je partirai", False, None),
    # -- elision is French ----------------------------------------------------
    ("je aime le café", "j'aime le café", False, "elision"),
    ("le arbre", "l'arbre", False, "elision"),
]


@pytest.mark.parametrize(("answer", "accepted", "ok", "note"), TRICKY, ids=[row[0] for row in TRICKY])
def test_the_contract(answer, accepted, ok, note):
    verdict = judge(answer, [accepted])
    assert verdict.correct is ok, verdict
    assert verdict.note == note, verdict
    assert verdict.expected == accepted


@pytest.mark.parametrize(("answer", "accepted", "ok", "note"), TRICKY, ids=[row[0] for row in TRICKY])
def test_the_journey_recall_grader_keeps_the_contract(answer, accepted, ok, note):
    del note
    assert answer_matches(answer, [accepted]) is ok


@pytest.mark.parametrize(("answer", "accepted", "ok", "note"), TRICKY, ids=[row[0] for row in TRICKY])
def test_the_erratum_review_keeps_the_contract(answer, accepted, ok, note):
    del note
    assert review_answer_repairs(answer, accepted) is ok


def test_the_journey_still_accepts_a_word_inside_a_sentence_but_not_a_rewrite():
    assert answer_matches("C'est un appartement.", ["un appartement"])
    assert answer_matches("l’appartement", ["appartement"])
    assert answer_matches("oui, la clé", ["la clé"])
    # A whole sentence is graded as a sentence: padding it does not pass.
    assert not answer_matches("Je ne bois pas du café de café", ["Je ne bois pas de café"])
    # A give-up sentence that happens to hold the word is not the word.
    assert not answer_matches("euh je ne sais pas", ["pas"])
    # A contained word keeps the accent rule: «a» is not «à».
    assert not answer_matches("je vais a Paris", ["à Paris"])


def test_fold_for_comparison_spells_ligatures_out():
    assert fold_for_comparison("Ma sœur") == fold_for_comparison("ma soeur") == "ma soeur"
    assert fold_for_comparison("cœur") != fold_for_comparison("cur")


def test_an_accent_erratum_is_not_repaired_by_retyping_the_error():
    assert not review_answer_repairs("probleme", "problème", "probleme")
    assert review_answer_repairs("problème", "problème", "probleme")
    assert review_answer_repairs("Problème !", "problème", "probleme")
    # Any other erratum stays lenient about accents it is not about.
    assert review_answer_repairs("un probleme serieux", "un problème sérieux", "une problème sérieux")


def test_the_erratum_review_matches_on_word_boundaries_not_substrings():
    assert review_answer_repairs("Hier, je suis allé au marché.", "je suis allé")
    assert not review_answer_repairs("jesuisallé", "je suis allé")


def test_eclair_keeps_the_accent_of_a_minimal_pair():
    items = [{"id": "1", "concept_id": 1, "correct_answer": "Il a mangé."}]
    assert grade_answers(items, [{"id": "1", "answer": "Il a mangé."}])[0]["correct"]
    assert grade_answers(items, [{"id": "1", "answer": "Il a mangé."}])[0]["correct"]
    assert not grade_answers(items, [{"id": "1", "answer": "Il à mangé."}])[0]["correct"]


# -- optional articles --------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "accepted", "ok", "note"),
    [
        ("clé", "la clé", True, None),
        ("une clé", "la clé", True, None),
        ("la cle", "la clé", True, "accent"),
        ("le clé", "la clé", False, "gender"),
        ("appartement", "un appartement", True, None),
        ("l’appartement", "un appartement", True, None),
        ("une appartement", "un appartement", False, "gender"),
        ("le appartement", "un appartement", False, "elision"),
    ],
)
def test_an_optional_article_may_be_left_out_never_wrong(answer, accepted, ok, note):
    verdict = judge(answer, [accepted], article_optional=True)
    assert verdict.correct is ok, verdict
    assert verdict.note == note


def test_without_article_optional_the_article_is_part_of_the_answer():
    assert not judge("clé", ["la clé"]).correct


# -- strict items ---------------------------------------------------------------


def test_an_item_about_accents_grades_them_strictly():
    assert not judge("francais", ["français"], accents="strict").correct
    assert not judge("commencons", ["commençons"], accents="strict").correct
    assert judge("commençons", ["commençons"], accents="strict").correct


# -- accepted alternatives -------------------------------------------------------


def test_question_variants():
    assert set(question_variants("Est-ce que tu viens ?")) == {"tu viens", "viens-tu"}
    assert "a-t-il faim" in question_variants("Il a faim ?")
    assert "aime-t-elle le café" in question_variants("Elle aime le café ?")
    assert question_variants("Je ne sais pas.") == []
    variants = question_variants("Est-ce que tu viens ?")
    assert judge("Viens-tu ?", ["Est-ce que tu viens ?"], alternatives=variants).correct


def test_on_nous_variants():
    assert on_nous_variants("On va au marché") == ["nous allons au marché"]
    assert on_nous_variants("nous mangeons ici") == ["on mange ici"]
    assert judge("Nous allons au marché.", ["On va au marché."], alternatives=on_nous_variants("On va au marché.")).correct


# -- the typo rule in isolation ---------------------------------------------------


@pytest.mark.parametrize(
    ("learner", "target", "typo"),
    [
        ("beacoup", "beaucoup", True),
        ("aprtement", "appartement", False),  # two edits
        ("parles", "parle", False),  # an ending
        ("vendions", "vendons", False),  # a tense
        ("chasse", "chaise", False),  # another word
        ("suis", "sui", False),  # too short to forgive
    ],
)
def test_is_typo_of(learner, target, typo):
    assert is_typo_of(learner, target) is typo


# -- feedback -----------------------------------------------------------------------


def test_every_verdict_note_has_a_why_in_three_languages():
    cases = [
        judge("tres bien", ["très bien"]),
        judge("beacoup", ["beaucoup"]),
        judge("il a mange", ["il a mangé"]),
        judge("je parles", ["je parle"]),
        judge("je aime", ["j'aime"]),
        judge("le clé", ["la clé"], article_optional=True),
    ]
    for verdict in cases:
        for language in ("en", "de", "fr"):
            note = feedback_note(verdict, language)
            assert note and "{" not in note, (verdict, language)
    assert feedback_note(judge("très bien", ["très bien"]), "de") is None
    assert "Akzent" in feedback_note(judge("tres bien", ["très bien"]), "de")


def test_typography_fold_keeps_accents():
    assert fold_typography("Où est l’hôtel ?") == "où est l'hôtel"
    assert fold_typography("ou est l'hotel") != fold_typography("Où est l'hôtel")


def test_an_apostrophe_typed_as_a_space_is_typography_but_not_a_dropped_elision():
    assert judge("Un cafe, s il vous plait.", ["un café, s'il vous plaît"]).correct
    assert judge("j aime le café", ["j'aime le café"]).correct
    assert not judge("je aime le café", ["j'aime le café"]).correct
