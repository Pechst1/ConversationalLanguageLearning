"""#1068: the scene card's three corrections went to the first apostrophes.

Explore walk 25 Nov (a2-en, fake provider). Day 2, scene «La lettre», to Camille: the
card showed «→ j'ai», «l appartement → l'appartement», «et j ai → et j'ai»; «au hopital
→ à l'hôpital» was never shown. Day 1, to Margaux: «très», «j'ai», «clé» shown, «a le
notaire → au notaire» not.

``_with_basic_check`` adds the model-free edits by ``(-severity, start)`` up to three.
A fix folded into an accent kept the accent's rank (#1047: «a le» -> «au» was ranked as
the «à» accent, «au hopital» -> «à l'hôpital» as the «ô»), so every edit of the reply had
the same rank and the places went by position; a second «j ai» counted as a new slip.

Pinned with the tutor stubbed (no model): grammar edits before spelling ones, and one
place per kind of slip.
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


@pytest.mark.parametrize("tutor", [(), (TUTOR_J_AI,)], ids=["fake-tutor-none", "tutor-j-ai"])
def test_day2_card_shows_the_hopital_and_one_j_ai(tutor):
    """#1068 done-when: the day-2 reply shows «à l'hôpital», and «j'ai» once."""
    shown = _card(DAY2_CAMILLE, *tutor)

    assert len(shown) == lanes.TUTOR_MAX_CORRECTIONS, shown
    assert ("au hopital", "à l'hôpital") in shown, f"«au hopital» left off the card: {shown}"
    apostrophes = [pair for pair in shown if "'" in pair[1] and "hôpital" not in pair[1]]
    assert len(apostrophes) == 1, f"one missing apostrophe takes {len(apostrophes)} places: {shown}"


def test_day1_card_shows_au_notaire():
    """#1068 done-when: «a le notaire» -> «au» is among the three, ahead of the accents."""
    shown = _card(DAY1_MARGAUX)

    assert ("a le", "au") in shown, f"«a le notaire» left off the card: {shown}"
    assert shown[0] == ("a le", "au"), shown
    accents = [pair for pair in shown if pair[1] in {"très", "clé"}]
    assert len(accents) == 1, f"one missing accent takes {len(accents)} places: {shown}"


def test_one_place_per_kind_leaves_room_for_the_rest():
    """A slip written three times is one place; the other two go to other slips."""
    text = "J ai faim, j ai soif et j ai sommeil. Je suis tres fatigue."
    shown = _card(text)

    assert sum(1 for _span, fixed in shown if fixed.lower() == "j'ai") == 1, shown
    assert ("tres", "très") in shown, shown
