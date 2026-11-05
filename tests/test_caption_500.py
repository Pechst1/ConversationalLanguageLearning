"""#500 / #145: the caption under the scene's input follows the character's latest turn.

The live walk of 3 Nov 2026 (A1.1, day 22): Lila asked «Quelle photo va au milieu ?
Et pourquoi celle-là ?», then «Pourquoi cette photo ?», then said she did not know
the man with the key, and the caption under the input stayed on the opening task
(«Lila asks which photo goes in the centre.») through every exchange. The prompt's
``objective_native`` is the caption; it was written for the opening question and
carried over unchanged to every later turn.

What these tests pin, with the fake provider and no model call:

* after each exchange the next prompt's caption is derived from the character's
  reply, so it changes with her last question;
* a reply that asks nothing no longer shows the opening task (a neutral line);
* the caption is in the learner's language;
* a season page's own next task (``next_task_native``) still wins.
"""

from __future__ import annotations

from tests import test_wp87_lanes as harness
from tests.test_living_story import driver
from tests.test_story_exchanges import _play, _scripted_voice

assembled_client = harness.assembled_client
journey_enabled = harness.journey_enabled
clock = harness.clock
provider = harness.provider
jobs = harness.jobs

PHOTO = "Ah, Napoléon au milieu ! Pourquoi cette photo ?"
KEY = "Je ne connais pas cet homme. Mais pourquoi la clé ?"
NO_QUESTION = "Je ne sais pas qui c'est. On verra plus tard."


def test_caption_follows_question(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    d = driver(assembled_client, db_session)
    step = harness._to_respond(d)
    opening = step["prompt"]["objective_native"]
    _scripted_voice(provider, [PHOTO, KEY, NO_QUESTION])
    results = _play(
        assembled_client,
        d,
        ["Non, je préfère la photo de mon chat Napoléon.", "Qui est l'homme avec la clé ?", "Merci."],
    )
    captions = [r["next_turn"]["prompt"]["objective_native"] for r in results if r["next_turn"]]
    assert len(captions) >= 2, "a three-exchange scene hands over at least two later prompts"

    assert opening not in captions, "the opening task is not the caption of a later question"
    assert "Pourquoi cette photo" in captions[0]
    assert "la clé" in captions[1] and "Pourquoi cette photo" not in captions[1]
    assert len(set(captions)) == len(captions), "the caption changes with the character's last question"


def test_caption_drops_old_question(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    """Lila answers the off-script question without asking anything back: the
    caption must not go on naming the photo question she asked two turns before."""

    d = driver(assembled_client, db_session)
    harness._to_respond(d)
    _scripted_voice(provider, [PHOTO, NO_QUESTION, "Bon, on avance, point 2."])
    results = _play(
        assembled_client,
        d,
        ["Non, je préfère la photo de mon chat Napoléon.", "Qui est l'homme avec la clé ?"],
    )
    asked, silent = (r["next_turn"]["prompt"]["objective_native"] for r in results[:2])
    assert "Pourquoi cette photo" in asked
    assert "Pourquoi cette photo" not in silent and "photo" not in silent.lower()
    assert "?" not in silent, "a turn that asks nothing is captioned with no question"
