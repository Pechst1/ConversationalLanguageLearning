"""Owner decision 2026-10-08 — a word kept at an inflected form keeps its scene card.

The in-context card (the kept word's own line, blanked) blanks the form **as it was in
the line** and expects that form, with the lemma as the hint: «Vous _____ d'où ?
(venir)» takes «venez». The lemma typed there is wrong French and is refused with a
specific note. The context-free rungs, the evidence and the SRS item stay the lemma's;
the form is stored as context. An old kept word without a stored form has it derived
from its line, or keeps no scene card — never a broken blank.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db.models.progress import UserVocabularyProgress
from app.db.models.vocabulary import VocabularyWord
from app.services.answer_acceptance import feedback_note, judge_in_line
from app.services.recall_ladder import card_ladder, in_line_answer, scene_form

VENIR = SimpleNamespace(word="venir", example_sentence="Il va venir demain.")


def _progress(**fields):
    base = {"reps": 0, "lapses": 0, "stability": None, "context": None}
    return SimpleNamespace(**{**base, **fields})


# -- the blank -----------------------------------------------------------------------


def test_a_kept_form_is_blanked_as_it_was_in_the_line_with_the_lemma_as_hint():
    kept = {"sentence_fr": "Vous venez d'où ?", "surface_fr": "venez", "speaker_id": "odile", "line_key": "p1:l0"}
    card = card_ladder(_progress(context=kept), VENIR, level="A1")
    assert card["ladder"] == "scene"
    assert card["scene_cue"] == {
        "sentence_fr": "Vous _____ d'où ?",
        "speaker_id": "odile",
        "line_key": "p1:l0",
        "expected_fr": "venez",
        "hint_fr": "venir",
    }


def test_a_form_equal_to_the_lemma_has_no_hint():
    form = scene_form("Tu as vu la serrure ?", "la serrure", "serrure")
    assert form["sentence_fr"] == "Tu as vu la _____ ?"
    assert (form["expected_fr"], form["hint_fr"]) == ("serrure", None)


@pytest.mark.parametrize(
    ("line", "lemma", "stored", "blanked", "expected", "accepted"),
    [
        # Elided: the blank is the word, the clitic stays; «j'étais» is accepted too.
        ("J'étais là hier.", "être", "étais", "J'_____ là hier.", "étais", ["étais", "j'étais"]),
        # The iOS apostrophe in the line.
        ("J’étais là hier.", "être", "étais", "J’_____ là hier.", "étais", ["étais", "j'étais"]),
        # The elided article before a noun: the lemma itself, no hint.
        ("L'appartement est grand.", "appartement", "appartement", "L'_____ est grand.", "appartement",
         ["appartement", "l'appartement"]),
        # Sentence-initial capital: blanked as printed, expected in lower case.
        ("Venez ici !", "venir", "Venez", "_____ ici !", "venez", ["venez"]),
    ],
)
def test_elided_apostrophe_and_capitalised_forms(line, lemma, stored, blanked, expected, accepted):
    form = scene_form(line, lemma, stored)
    assert form["sentence_fr"] == blanked
    assert form["expected_fr"] == expected
    assert form["accepted"] == accepted


def test_an_old_kept_word_without_a_stored_form_has_it_derived_from_its_line():
    old = {"sentence_fr": "Vous venez d'où ?"}  # kept before the form was stored
    card = card_ladder(_progress(context=old), VENIR, level="A1")
    assert card["ladder"] == "scene"
    assert (card["scene_cue"]["sentence_fr"], card["scene_cue"]["expected_fr"], card["scene_cue"]["hint_fr"]) == (
        "Vous _____ d'où ?", "venez", "venir",
    )
    etre = scene_form("Il était une fois.", "être")
    assert (etre["sentence_fr"], etre["expected_fr"]) == ("Il _____ une fois.", "était")


@pytest.mark.parametrize(
    ("line", "lemma"),
    [
        ("J'étais là, il est parti.", "être"),  # two forms of «être»: ambiguous
        ("Nous allons au marché et vous allez où ?", "aller"),
        ("Personne ne répond.", "venir"),  # the lemma is not in the line at all
    ],
)
def test_an_old_kept_word_that_cannot_be_derived_keeps_no_scene_card(line, lemma):
    assert scene_form(line, lemma) is None
    card = card_ladder(_progress(context={"sentence_fr": line}), SimpleNamespace(word=lemma, example_sentence=""),
                       level="A1")
    assert card["ladder"] != "scene" and card["scene_cue"] is None


def test_a_form_twice_in_the_line_is_never_a_blank_with_the_answer_still_showing():
    assert scene_form("Venez, venez vite !", "venir", "venez") is None


def test_the_context_free_rungs_keep_the_lemma():
    kept = {"sentence_fr": "Vous venez d'où ?", "surface_fr": "venez"}
    later = card_ladder(_progress(reps=3, stability=1.0, context=kept), VENIR, level="A1")
    assert later["ladder"] == "recognition" and later["scene_cue"] is None
    assert in_line_answer(_progress(reps=3, stability=1.0, context=kept), VENIR) is None


def test_a_rescue_in_the_words_own_line_cues_the_form():
    kept = {"sentence_fr": "Vous venez d'où ?", "surface_fr": "venez"}
    rescued = card_ladder(_progress(reps=9, lapses=5, context=kept), VENIR, level="A1")
    cue = rescued["rescue_cue"]
    assert rescued["ladder"] == "rescue"
    assert (cue["sentence_fr"], cue["first_letter"], cue["length"], cue["expected_fr"], cue["hint_fr"]) == (
        "Vous _____ d'où ?", "v", 5, "venez", "venir",
    )


# -- the grade -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "correct"),
    [
        ("venez", True),
        ("Venez", True),
        (" venez ", True),
        ("venir", False),
        ("allez", False),
    ],
)
def test_the_line_takes_the_form_that_fits(answer, correct):
    assert judge_in_line(answer, ["venez"], lemma="venir").correct is correct


def test_the_lemma_in_the_line_is_refused_with_the_specific_note():
    verdict = judge_in_line("venir", ["venez"], lemma="venir")
    assert (verdict.correct, verdict.note, verdict.expected) == (False, "line_form", "venez")
    assert feedback_note(verdict, "en") == "Right word — the line needs the form «venez»."
    assert "«venez»" in feedback_note(verdict, "de")


def test_elision_smart_quotes_and_accents_follow_the_one_contract():
    accepted = scene_form("J’étais là hier.", "être", "étais")["accepted"]
    assert judge_in_line("étais", accepted, lemma="être").correct
    assert judge_in_line("j’étais", accepted, lemma="être").correct, "the iOS apostrophe folds"
    assert judge_in_line("j‘étais", accepted, lemma="être").correct, "U+2018 folds too"
    lenient = judge_in_line("etais", accepted, lemma="être")
    assert lenient.correct and lenient.accent_slip, "an accent slip is accepted and named"
    assert judge_in_line("être", accepted, lemma="être").note == "line_form"


# -- end to end: keep → store → ladder → drill → grade -------------------------------


def _catalogue_word(db_session, lemma: str, english: str) -> VocabularyWord:
    row = db_session.query(VocabularyWord).filter(VocabularyWord.language == "fr", VocabularyWord.word == lemma).first()
    if row is None:
        row = VocabularyWord(language="fr", word=lemma, normalized_word=lemma, english_translation=english)
        db_session.add(row)
        db_session.commit()
    elif not row.english_translation:
        row.english_translation = english
        db_session.commit()
    return row


def test_venez_kept_from_its_line_is_the_lemmas_card_asked_and_graded_at_its_form(client: TestClient, db_session):
    from tests.test_wp115a_vocabulary_memory import _login

    headers, user = _login(client, db_session)
    venir = _catalogue_word(db_session, "venir", "to come")

    kept = client.post(
        "/api/v1/vocabulary/keep",
        headers=headers,
        json={"term": "venez", "surface": "venez", "sentence": "Vous venez d'où ?", "speaker_id": "odile",
              "line_key": "p1:l0"},
    )
    assert kept.status_code == 200, kept.text
    assert (kept.json()["word_id"], kept.json()["word"], kept.json()["surface"]) == (venir.id, "venir", "venez")

    # The SRS item is the lemma's; the form is context, not a new vocabulary item.
    db_session.expire_all()
    rows = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id).all()
    assert [row.word_id for row in rows] == [venir.id]
    assert rows[0].context["surface_fr"] == "venez"
    assert db_session.query(VocabularyWord).filter(VocabularyWord.word == "venez").count() == 0

    deck = client.get("/api/v1/vocabulary/due-context?due_limit=10&new_limit=10", headers=headers).json()
    cards = [
        item for bucket in ("due_words", "fragile_words", "new_words", "linked_words", "topic_compatible_words")
        for item in deck.get(bucket, []) if item["word_id"] == venir.id
    ]
    assert cards, deck
    assert cards[0]["ladder"] == "scene"
    assert cards[0]["scene_cue"]["sentence_fr"] == "Vous _____ d'où ?"
    assert (cards[0]["scene_cue"]["expected_fr"], cards[0]["scene_cue"]["hint_fr"]) == ("venez", "venir")

    wrong = client.post(
        "/api/v1/anki/review", headers=headers,
        json={"word_id": venir.id, "rating": 2, "format": "cloze", "answer_text": "venir"},
    )
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["correct"] is False
    assert wrong.json()["expected"] == "venez"
    assert "«venez»" in wrong.json()["note_native"]

    right = client.post(
        "/api/v1/anki/review", headers=headers,
        json={"word_id": venir.id, "rating": 0, "format": "cloze", "answer_text": "venez"},
    )
    assert right.status_code == 200, right.text
    assert right.json()["correct"] is True


def test_a_context_free_rung_of_a_kept_form_is_answered_with_the_lemma(client: TestClient, db_session):
    from tests.test_wp115a_vocabulary_memory import _login

    headers, user = _login(client, db_session)
    venir = _catalogue_word(db_session, "venir", "to come")
    assert client.post(
        "/api/v1/vocabulary/keep", headers=headers,
        json={"term": "venez", "surface": "venez", "sentence": "Vous venez d'où ?"},
    ).status_code == 200
    db_session.expire_all()
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=venir.id).one()
    progress.reps, progress.stability = 3, 6.0  # past its scene reviews: production
    db_session.commit()
    typed = client.post(
        "/api/v1/anki/review", headers=headers,
        json={"word_id": venir.id, "rating": 2, "format": "typed", "answer_text": "venir"},
    )
    assert typed.json()["correct"] is True, typed.text
