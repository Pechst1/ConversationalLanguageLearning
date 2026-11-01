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

from app.services.journey_learning import (
    Correction,
    select_foreground_correction,
    validate_correction,
)

INTONATION = "Vous êtes disponible jeudi matin ?"
INVERSION_NOTE = "Inversion is required here."
SUIS_NOTE = "It is “est”, not “suis”. You wrote «suis», the form for «je»; this subject requires «est»."

# (label, learner text, span, replacement, note): the learner's French is right, or the
# "fix" puts a form on a subject it does not belong to.
NOT_A_MISTAKE = [
    ("intonation -> inversion", INTONATION, INTONATION, "Êtes-vous disponible jeudi matin ?", INVERSION_NOTE),
    ("intonation -> inversion, span only", INTONATION, "Vous êtes", "Êtes-vous", INVERSION_NOTE),
    ("intonation -> est-ce que", INTONATION, INTONATION, "Est-ce que vous êtes disponible jeudi matin ?", INVERSION_NOTE),
    ("est-ce que -> inversion", "Est-ce que vous êtes libre ?", "Est-ce que vous êtes", "Êtes-vous", "Use inversion."),
    ("je suis -> est", "Je suis fatigue de Berlin.", "suis", "est", SUIS_NOTE),
    ("subject swapped", "Je suis fatigue de Berlin.", "Je suis", "Il est", "x"),
]

# A real slip must still be shown whatever the subject is.
REAL_MISTAKES = [
    ("feminine participle", "Ma grand-mère est mort.", "est mort", "est morte", "A grandmother is feminine: «morte»."),
    ("marie et moi", "Marie et moi suis contents.", "suis", "sommes", "With «Marie et moi» the verb is «sommes»."),
    ("avoir froid", "Je suis froid.", "suis froid", "ai froid", "Cold is felt with «avoir»."),
]


def test_right_kept() -> None:
    """None of these is a mistake: the gate and the foreground pick both drop them."""

    user = SimpleNamespace(address_preference=None, grammar_correction_level="standard")
    shown = []
    for label, text, span, fix, note in NOT_A_MISTAKE:
        correction = Correction(span_fr=span, corrected_fr=fix, note_native=note)
        foreground, background = select_foreground_correction(
            user=user, learner_text=text, candidates=[correction]
        )
        if validate_correction(correction, text) or foreground is not None or background:
            shown.append(label)
    assert shown == [], f"a right sentence was corrected: {shown}"


def test_slip_kept() -> None:
    dropped = [
        label
        for label, text, span, fix, note in REAL_MISTAKES
        if not validate_correction(Correction(span_fr=span, corrected_fr=fix, note_native=note), text)
    ]
    assert dropped == [], f"a real slip was dropped: {dropped}"
