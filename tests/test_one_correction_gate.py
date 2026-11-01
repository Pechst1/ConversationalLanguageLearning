"""#174 / #93: the journey's correction gate is the one correction check.

A correction is shown, and saved as an erratum, only when the learner's own words
prove it. Every other surface (the story lane, the audio studio, the Courrier, the
Journal contract) already runs ``correction_contract.verify_edit``; the journey's
``validate_correction`` (the gate of the conversation tutor, the recall step and the
Journal) only looked at the span being there. So the tutor could mark the correct
«Vous êtes disponible jeudi matin ?» wrong and file «Êtes-vous …» as an erratum
(live walk, 12 Oct), or tell a correct «je suis fatigue» «suis -> est» (30 Oct).

The table below pins both directions: what is not a mistake is dropped, a real slip
survives.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.journey_learning import (
    Correction,
    select_foreground_correction,
    validate_correction,
)

INTONATION = "Vous êtes disponible jeudi matin ?"
INVERSION_NOTE = "Inversion is required here."
SUIS_NOTE = "It is “est”, not “suis”. You wrote «suis», the form for «je»; this subject requires «est»."

# (learner text, span, replacement, note): the learner's French is right, or the
# "fix" puts a form on a subject it does not belong to.
NOT_A_MISTAKE = [
    pytest.param(INTONATION, INTONATION, "Êtes-vous disponible jeudi matin ?", INVERSION_NOTE, id="intonation->inversion"),
    pytest.param(INTONATION, "Vous êtes", "Êtes-vous", INVERSION_NOTE, id="intonation->inversion, span only"),
    pytest.param(INTONATION, INTONATION, "Est-ce que vous êtes disponible jeudi matin ?", INVERSION_NOTE, id="intonation->est-ce que"),
    pytest.param("Est-ce que vous êtes libre ?", "Est-ce que vous êtes", "Êtes-vous", "Use inversion.", id="est-ce que->inversion"),
    pytest.param("Je suis fatigue de Berlin.", "suis", "est", SUIS_NOTE, id="je suis->est"),
    pytest.param("Je suis fatigue de Berlin.", "Je suis", "Il est", "x", id="subject swapped"),
]

# A real slip must still be shown whatever the subject is.
REAL_MISTAKES = [
    pytest.param("Ma grand-mère est mort.", "est mort", "est morte", "A grandmother is feminine: «morte»."),
    pytest.param("Marie et moi suis contents.", "suis", "sommes", "With «Marie et moi» the verb is «sommes»."),
    pytest.param("Je suis froid.", "suis froid", "ai froid", "Cold is felt with «avoir»."),
]


@pytest.mark.parametrize(("text", "span", "fix", "note"), NOT_A_MISTAKE)
def test_a_right_sentence_is_never_corrected(text: str, span: str, fix: str, note: str) -> None:
    correction = Correction(span_fr=span, corrected_fr=fix, note_native=note)
    assert validate_correction(correction, text) is False
    user = SimpleNamespace(address_preference=None, grammar_correction_level="standard")
    foreground, background = select_foreground_correction(user=user, learner_text=text, candidates=[correction])
    assert foreground is None
    assert background == []


@pytest.mark.parametrize(("text", "span", "fix", "note"), REAL_MISTAKES)
def test_a_real_slip_is_still_corrected(text: str, span: str, fix: str, note: str) -> None:
    assert validate_correction(Correction(span_fr=span, corrected_fr=fix, note_native=note), text) is True
