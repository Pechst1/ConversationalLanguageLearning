"""#750 (root cause #145): the learner speaks to Marin, Lila answers as if she were Marin,
and the closing panel says «Marin agrees to help you look for your key» under Lila's line.

The scene record now holds whom the learner addressed (``ledger.addressed``), the voice and
actor prompts read it, and the ending's summary may not make that person act.
"""
from __future__ import annotations

import pytest

from app.services import lane_guards, living_story, scene_ledger, story_lanes

LAST_REPLY = "Mais j'ai perdu mon clé. Marin, tu peux m'aider à trouver mon clé ?"
ROOM = ["lila", "marin"]


def test_the_record_knows_whom_the_learner_spoke_to():
    ledger = scene_ledger.build(opening_line_fr="Tu veux une pizza ?", history=[], learner_text=LAST_REPLY, in_the_room=ROOM)
    assert ledger["addressed"] == {"id": "marin", "name": "Marin"}


@pytest.mark.parametrize(
    "text",
    [
        "Lila, tu peux m'aider ?",  # the scene's own character is not «someone else»
        "Je vais chez Marin demain.",  # a name in the sentence is no address
        "Oui, d'accord.",
    ],
)
def test_nobody_else_is_addressed(text):
    ledger = scene_ledger.build(opening_line_fr="Tu veux une pizza ?", history=[], learner_text=text, in_the_room=ROOM)
    assert ledger["addressed"] is None


def test_someone_not_in_the_room_is_not_addressed():
    ledger = scene_ledger.build(opening_line_fr="Salut !", history=[], learner_text=LAST_REPLY, in_the_room=["lila"])
    assert ledger["addressed"] is None


def test_the_summary_may_not_make_the_addressed_person_act_under_the_characters_line():
    addressed = {"id": "marin", "name": "Marin"}
    issue = lane_guards.summary_speaker_issue("Marin agrees to help you look for your key.", "Lila Bonnet", addressed)
    assert issue and "Marin" in issue
    assert lane_guards.summary_speaker_issue("Lila says Marin will help you look for the key.", "Lila Bonnet", addressed) is None
    assert lane_guards.summary_speaker_issue("Marin agrees to help you.", "Lila Bonnet", None) is None
    with pytest.raises(living_story.StoryUnavailable):
        lane_guards.check_ending_voice(
            "Je cherche ta clé avec toi.", "Marin agrees to help you look for your key.", "Lila", addressed
        )


def test_both_prompts_tell_the_character_never_to_answer_as_the_addressed_person():
    assert "ledger.addressed" in story_lanes.voice_prompt()
    assert "ledger.addressed" in living_story.ACTOR
    # With the scene record off, the prompts are what main had.
    assert "ledger.addressed" not in story_lanes.VOICE_MAIN
    assert "ledger.addressed" not in living_story.ACTOR_MAIN
