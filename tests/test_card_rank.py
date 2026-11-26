"""#1068: the scene card's three corrections went to the first apostrophes.

Explore walk 25 Nov (a2-en, fake provider). Day 2, scene «La lettre», to Camille: the
card showed «→ j'ai», «l appartement → l'appartement», «et j ai → et j'ai»; «au hopital
→ à l'hôpital» was never shown. Day 1, to Margaux: «très», «j'ai», «clé» shown, «a le
notaire → au notaire» not.

``_with_basic_check`` added the model-free edits by ``(-severity, start)`` up to three.
A fix composed of two (a fold) kept the rank of its first part, so «a le» -> «au» ranked
as the «à» accent and «au hopital» -> «à l'hôpital» as the «ô»: every edit of the reply
had the same rank and the places went by position; a second «j ai» counted as a new slip.

Attempt 1 (#1073) made «one place per kind of slip» a filter and left places empty while
distinct slips stayed unshown («le appartement de Odile … que il» showed one of three).
Pinned here, with the tutor stubbed (no model): grammar before spelling, one place per
kind first, the free places then filled, and only a true repeat (the same correction
already on the card) dropped.
"""

from __future__ import annotations

import pytest

from app.services import story_lanes as lanes

#: Day 2's reply, word for word.
DAY2_CAMILLE = (
    "Non, je ne vend pas maintenant. Hier soir j ai dormi dans l appartement et j ai trouve des "
    "photos de ma grand-mere. C est plus simple pour vous, peut-etre. Pourquoi votre grand-pere veut "
    "tout l immeuble ? Ce matin je suis allé au hopital pour ma soeur."
)
#: Day 1's reply to Margaux, word for word.
DAY1_MARGAUX = (
    "Non, ce soir je monte pas. Je suis tres fatigue et j ai un peu peur. Pourquoi elle ne donnait "
    "jamais la cle ? Demain je vais a le notaire avec ma soeur. Tu connais Solvel ?"
)
#: The tutor's «j'ai», as a model would mark the first one.
TUTOR_J_AI = {"span_fr": "j ai", "corrected_fr": "j'ai", "note_native": "An apostrophe is missing: « j'ai ».",
              "rule_id": None}


def _payload(text: str, *, level: str = "A2") -> dict:
    return {
        "learner_text": text,
        "history": [],
        "scene": {},
        "story": {"learner": {"address": "neutral"}, "level": level, "commitments": [], "control_language": "en"},
        "targets": [],
        "turn_plan": {},
    }


def _card(text: str, *corrections: dict) -> list[tuple[str, str]]:
    verdict = lanes.TutorVerdict.model_validate(
        {"outcome": "met", "evidence_quotes": [text[:40]], "corrections": list(corrections)}
    )
    lanes.validate_tutor(verdict, _payload(text))
    return [(c.span_fr, c.corrected_fr) for c in verdict.corrections]


@pytest.mark.parametrize("tutor", [(), (TUTOR_J_AI,)], ids=["fake", "j-ai"])
def test_day2_card(tutor):
    """#1068 done-when: the day-2 reply shows «à l'hôpital», and «j'ai» once."""
    shown = _card(DAY2_CAMILLE, *tutor)

    assert len(shown) == lanes.TUTOR_MAX_CORRECTIONS, shown
    assert ("au hopital", "à l'hôpital") in shown, f"«au hopital» left off the card: {shown}"
    j_ai = [pair for pair in shown if pair[1].casefold().endswith("j'ai")]
    assert len(j_ai) == 1, f"one missing «j'ai» takes {len(j_ai)} places: {shown}"


def test_day1_card():
    """#1068 done-when: «a le notaire» -> «au» is among the three, ahead of the accents."""
    shown = _card(DAY1_MARGAUX)

    assert ("a le", "au") in shown, f"«a le notaire» left off the card: {shown}"
    assert shown[0] == ("a le", "au"), f"a contraction is shown after a spelling fix: {shown}"
    accents = [pair for pair in shown if pair[1] in {"très", "clé"}]
    assert len(accents) == 1, f"one kind of accent slip takes {len(accents)} places: {shown}"


def test_a_slip_written_three_times_is_one_place():
    """The same correction three times is one place; the other places go to other slips."""
    text = "J ai faim, j ai soif et j ai sommeil. Je suis tres fatigue."
    shown = _card(text)

    j_ai = [pair for pair in shown if pair[1].casefold().endswith("j'ai")]
    assert len(j_ai) == 1, f"«j'ai» takes {len(j_ai)} places: {shown}"
    assert ("tres", "très") in shown, shown


def test_three_elisions_in_three_words_fill_three_places():
    """#1073 review: three elisions in three words are three slips, not one kind shown once."""
    text = "Bonjour, je visite le appartement de Odile demain. Je pense que il est grand."
    shown = _card(text)

    fixed = {pair[1].split()[-1] for pair in shown}
    assert fixed == {"l'appartement", "d'Odile", "qu'il"}, f"distinct slips left off the card: {shown}"


def test_two_elisions_in_two_words_fill_two_places():
    """#1073 review: «le aime» and «la école» are both shown."""
    text = "Bonjour Odile, je le aime beaucoup, ton cadeau. Je cherche la école de Paul."
    shown = _card(text)

    fixed = {pair[1].split()[-1] for pair in shown}
    assert fixed == {"l'aime", "l'école"}, f"a distinct slip left off the card: {shown}"


def test_free_places_are_filled():
    """#1073 review: with more distinct slips than places, no place is left empty."""
    text = (
        "Hier soir, je suis arrive au Mistral avec la cle de ma grand-mère. Gus m a demande qui j etais, "
        "et Margaux m a donne la cle."
    )
    shown = _card(text)

    assert len(shown) == lanes.TUTOR_MAX_CORRECTIONS, f"a place left empty: {shown}"
    assert len({pair[1].split()[-1].casefold() for pair in shown}) == len(shown), f"a repeat on the card: {shown}"
