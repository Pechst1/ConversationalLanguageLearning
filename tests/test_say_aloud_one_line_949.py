"""#949 (child of #145): «One line to say aloud» is one short sentence, never the whole reply.

Live walk 20 Nov (A1.1, day 38): after the scene's last reply the card offered the learner's
fourth reply verbatim, 21 words, two sentences, a vocative and a joke about a cat:
«Oui, il ne veut plus boire, il prend son bain avec moi. Maintenant, Lila, je pense que je
garde la carte de ma grand-mère.» Seen again 21 Nov with the learner's slip in it: «Non,
Bastien est pas un ami. Je garde la banquette et je dis à Bastien de partir.» («n'» missing,
and the scene gave no correction for it).

The line is picked from the learner's text, which has no length; it has to be cut down to one
sentence an A1 learner can say once, and a sentence that drops «ne» is not a model.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from app.services import spoken_reply

WALK_20_NOV = (
    "Oui, il ne veut plus boire, il prend son bain avec moi. "
    "Maintenant, Lila, je pense que je garde la carte de ma grand-mère."
)
WALK_21_NOV = "Non, Bastien est pas un ami. Je garde la banquette et je dis à Bastien de partir."

#: The scene of 20 Nov, as the learner wrote it: four replies, the cat, then the decision.
SCENE_20_NOV = (
    "Bonjour Lila. Je vais bien, merci.",
    "Mon chat s'appelle Minou. Il est petit.",
    "Il boit du lait le matin.",
    WALK_20_NOV,
)


@pytest.fixture(autouse=True)
def spoken_on(monkeypatch):
    monkeypatch.setattr(spoken_reply.settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)
    monkeypatch.setattr(spoken_reply.settings, "STORY_SCENE_RECORD", True)


def _step(*said, suggested=""):
    turns = []
    for item in said:
        learner, corrected = item if isinstance(item, tuple) else (item, None)
        turn = {"learner": learner, "character": "Ah ?"}
        if corrected:
            turn["correction"] = {"corrected_fr": corrected}
        turns.append(turn)
    return SimpleNamespace(private_task={"turns": turns, "response_task": {"suggested_response_fr": suggested}})


def _sentences(line: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?…])\s+", line.strip()) if part]


def _assert_one_short_sentence(line: str | None) -> None:
    assert line, "the card hid: the learner said a whole sentence it could have offered"
    assert len(line.split()) <= 10, f"{len(line.split())} words to say aloud at A1: «{line}»"
    assert len(_sentences(line)) == 1, f"{len(_sentences(line))} sentences to say aloud: «{line}»"


#: A line written before the learner spoke, about something they never brought up, so the
#: card falls back to what they said (#558).
SCRIPTED = "Ça va, merci. Un peu triste."


def test_the_walk_of_20_nov_offers_one_short_sentence_not_the_whole_reply():
    """The learner's own fourth reply, with no correction needed: one sentence of it."""

    line = spoken_reply.repeat_line_for(_step(*SCENE_20_NOV, suggested=SCRIPTED))
    _assert_one_short_sentence(line)
    assert line != WALK_20_NOV


def test_the_walk_of_20_nov_as_shown_corrected_is_cut_down_too():
    """The same reply handed in as the correction the margin showed (no change needed)."""

    shown = SimpleNamespace(corrected_fr=WALK_20_NOV)
    line = spoken_reply.repeat_line_for(_step(*SCENE_20_NOV), shown)
    _assert_one_short_sentence(line)


def test_the_sentence_offered_is_the_one_about_the_scenes_question():
    """The question was written to elicit a line about the card; the learner decided the other
    way, so their own sentence is the line: the decision, not the cat's bath, and not «Lila»."""

    line = spoken_reply.repeat_line_for(_step(*SCENE_20_NOV, suggested="Non, je ne garde pas la carte."))
    _assert_one_short_sentence(line)
    assert "garde la carte de ma grand-mère" in line
    assert "Lila" not in line


def test_the_walk_of_21_nov_never_offers_the_slip():
    """«Bastien est pas un ami» drops «ne»: it is not the model line, the decision is."""

    line = spoken_reply.repeat_line_for(_step(WALK_21_NOV, suggested="Oui, Bastien est un ami."))
    _assert_one_short_sentence(line)
    assert "est pas" not in line
    assert line == "Je garde la banquette."


def test_a_short_sentence_still_stands_whole():
    step = _step("Oui, je reste ici ce soir.", suggested=SCRIPTED)
    assert spoken_reply.repeat_line_for(step) == "Oui, je reste ici ce soir."
