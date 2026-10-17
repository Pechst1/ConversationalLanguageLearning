"""#193 / #93: a correction must be about the sentence the learner wrote.

Live walk 2026-10-17 (A1.1, day 6): «Ma grand-mère est mort» got «est → es» with the
note «after 'tu' you must use 'es'». There is no «tu» in the sentence, and the real
slip («Je suis froid» for «J'ai froid») was missed. #93 (live walk 2026-10-12): the
correct intonation question «Vous êtes disponible jeudi matin ?» was marked wrong.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.answer_acceptance import (
    correction_is_grounded,
    is_real_correction,
    known_slip,
)

TEXT = "Je suis froid et un peu triste. Ma grand-mère est mort et je ne sais pas quoi faire avec le studio."
NOTE = "It is \"es\", not \"est\". 'est' is the third-person form; after 'tu' you must use 'es'."


def _payload(learner_text: str) -> dict:
    return {
        "learner_text": learner_text,
        "history": [],
        "scene": {},
        "story": {"learner": {"address": "neutral"}, "level": "A1", "commitments": []},
        "targets": [],
        "turn_plan": {},
    }


def test_est_to_es_after_a_noun_is_not_grounded():
    assert not correction_is_grounded(TEXT, "est", "es", NOTE)
    # even without the note, «es» needs a «tu» in front of the span
    assert not correction_is_grounded(TEXT, "est", "es")
    assert correction_is_grounded("Tu est content.", "est", "es")


def test_a_span_not_in_the_sentence_is_not_grounded():
    assert not correction_is_grounded(TEXT, "tu est", "tu es")
    assert correction_is_grounded(TEXT, "Ma grand-mère est mort", "Ma grand-mère est morte")


def test_the_tutor_drops_est_to_es_and_offers_j_ai_froid():
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=["Je suis froid"],
        correction_span_fr="est",
        correction_fr="es",
        correction_note_native=NOTE,
    )
    lanes.validate_tutor(verdict, _payload(TEXT))
    assert verdict.correction_span_fr.lower() == "je suis froid"
    assert verdict.correction_fr == "J'ai froid"
    assert "es" not in (verdict.correction_note_native or "").split()


def test_a_real_correction_in_the_sentence_still_stands():
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=["Je veux une café."],
        correction_span_fr="une café",
        correction_fr="un café",
        correction_note_native="Café is masculine.",
    )
    lanes.validate_tutor(verdict, _payload("Je veux une café."))
    assert verdict.correction_fr == "un café"


def test_known_slip_is_j_ai_froid():
    assert known_slip("Je suis froid") == (
        "Je suis froid",
        "J'ai froid",
        "In French you «have» cold, hunger or thirst: j'ai froid, not je suis froid.",
    )
    assert known_slip("Ma grand-mère est mort") is None


def test_the_scene_turn_applies_the_same_guard():
    assert engine.correction_is_grounded is correction_is_grounded


@pytest.mark.parametrize(
    "corrected",
    ["Êtes-vous disponible jeudi matin ?", "Est-ce que vous êtes disponible jeudi matin ?"],
)
def test_an_intonation_question_is_never_an_erratum(corrected):
    """#93: no correction, and so nothing saved, for a valid intonation question."""

    learner = "Vous êtes disponible jeudi matin ?"
    assert not is_real_correction(learner, corrected)
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=[learner],
        correction_span_fr=learner,
        correction_fr=corrected,
        correction_note_native="Inversion is required.",
    )
    lanes.validate_tutor(verdict, _payload(learner))
    assert verdict.correction_fr is None and verdict.correction_span_fr is None
