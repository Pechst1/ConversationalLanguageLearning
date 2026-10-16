"""The generated ending is the character's own line, and its summary tells the story.

Vincent, 2026-10-16, «Le papier sous la porte · 9/9»: Romy's bubble read «Romy sourit à
ton « avis », puis regarde Margaux. « Oui… » » and the summary under it told the learner
«Tu n'as pas demandé ce que la lettre annonce».
"""

import pytest

from app.services import lane_guards, story_lanes
from app.services.living_story import StoryUnavailable

SHOWN = (
    "Romy sourit à ton « avis », puis regarde Margaux. « Oui, elle a peur de perdre son "
    "café. Je comprends mieux. » La lettre reste sur la caisse ; elle n'a pas encore "
    "répondu à ta question sur ce qu'elle annonce."
)
GRADED = (
    "Romy comprend que tu demandes son avis et explique que Margaux a peur de perdre son "
    "café. Tu n'as pas demandé ce que la lettre annonce concrètement, et Romy ne répond "
    "donc pas à cette question."
)
SPOKEN = "Ton avis compte, tu sais. Margaux a peur de perdre son café : je comprends mieux, maintenant."
PLAIN = "Romy comprend que Margaux a peur de perdre son café, et elle garde la lettre pour la lui montrer."


def test_the_shipped_ending_is_refused():
    assert lane_guards.ending_voice_issue(SHOWN, PLAIN, "Romy Tremblay")


def test_a_summary_that_grades_the_learner_is_refused():
    assert lane_guards.ending_voice_issue(SPOKEN, GRADED, "Romy Tremblay")
    assert lane_guards.ending_voice_issue(SPOKEN, "You didn't ask what the letter says.", "Romy")
    assert lane_guards.ending_voice_issue(SPOKEN, "Du hast nicht gefragt, was im Brief steht.", "Romy")


def test_her_own_line_and_a_plain_summary_pass():
    assert lane_guards.ending_voice_issue(SPOKEN, PLAIN, "Romy Tremblay") is None
    # A quoted word without her name outside it is still her line.
    assert lane_guards.ending_voice_issue("«Pas de fête», elle a dit. Moi, j'y crois.", PLAIN, "Romy") is None


def test_the_check_raises_with_a_hint():
    with pytest.raises(StoryUnavailable) as caught:
        lane_guards.check_ending_voice(SHOWN, PLAIN, "Romy Tremblay")
    assert "speech bubble" in str(caught.value.hint)


def test_the_story_lane_asks_for_one_ending_in_her_voice():
    assert "speech bubble" in story_lanes.STORY
    assert "never says what the learner" in story_lanes.STORY
    assert "tells a different ending" in story_lanes.STORY_CRITIC
