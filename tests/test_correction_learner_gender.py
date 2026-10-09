"""A correction never gives the learner a gender they did not give (2026-10-09 walk).

«Je suis là pour l'appartement d'Odile» is correct French; the live grader offered
«je suis venu pour l'appartement d'Odile» as «more natural» — a man's sentence.
"""

from __future__ import annotations

import pytest

from app.services.journey_learning import introduced_learner_gender


@pytest.mark.parametrize(
    ("learner", "corrected", "hits"),
    [
        ("Je suis là pour l'appartement d'Odile.", "je suis venu pour l'appartement d'Odile", ["venu"]),
        ("je suis la pour la cle", "Je suis arrivée pour la clé", ["arrivée"]),
        ("je me sens mal", "je me sens vraiment perdu", ["perdu"]),
        ("j'etais pret", "J'étais prête", ["prête"]),
    ],
)
def test_a_rewrite_that_agrees_for_the_learner_is_caught(learner, corrected, hits):
    assert introduced_learner_gender(learner, corrected) == hits


@pytest.mark.parametrize(
    ("learner", "corrected"),
    [
        # The learner's own form is theirs to keep (accents folded).
        ("Je suis venue pour l'appartement", "Je suis venue pour l'appartement d'Odile"),
        ("je suis arrivee hier", "Je suis arrivée hier."),
        # Not an agreement: a place, a noun, an invariable word.
        ("je suis la", "Je suis là pour la clé."),
        ("je suis ne a paris", "Je suis né à Paris."),
        ("je suis etudiant", "Je suis étudiant en droit."),
        ("Bonjour, je m'appelle Vincent.", "Bonjour, je m'appelle Vincent."),
    ],
)
def test_the_learners_own_gender_and_neutral_rewrites_pass(learner, corrected):
    assert introduced_learner_gender(learner, corrected) == []


def test_a_neutral_learner_is_not_corrected_into_a_gender_but_a_feminine_one_is():
    from app.db.models.user import User
    from app.services.journey_learning import Correction, select_foreground_correction

    text = "je suis allé au marché"
    agreement = Correction(span_fr="je suis allé", corrected_fr="je suis allée", note_native="Agreement")
    neutral = User(email="n@example.com", hashed_password="t", address_preference="neutral")
    feminine = User(email="f@example.com", hashed_password="t", address_preference="feminine")
    assert select_foreground_correction(user=neutral, learner_text=text, candidates=[agreement])[0] is None
    assert select_foreground_correction(user=feminine, learner_text=text, candidates=[agreement])[0] == agreement
