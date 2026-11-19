"""Round 4 · a night run ends with a written day whenever a draft had only soft faults.

Third real-model walk (19 Nov, B1): one night of six ended ``unavailable`` after three
critic refusals with ``"kept": null``; every other night needed 2–3 attempts, and one of
them served a draft the critic had refused for storytelling while its outcome line still
said ``"kept": null``. The critic's stored readings (``journey_story_critic_review``) show
why the lost night was lost: all three drafts had ``honours_choices: false`` (Lila knows
an address she was never given; Marin reads the learner's airline mail; the learner's
agreed talk with Gus put off) — correctness, never served. The «stage tomorrow's hook in
the scene, not only in the checklist» issue that opened each refusal is the ``hook`` item,
which the verdict never refuses for.

These guards play the night with the split writer's fake and a scripted critic.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from app.services import story_split
from app.services.journey_latency import prefetch_scene_for
from app.services.season.director import StoryReview, review_verdict
from tests import test_journey_end_to_end as support
from tests.test_p11_night_run_lands import _outcome, _Writer, night  # noqa: F401 - fixture
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_story_split import _learner_on_gap_day, split_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

_PASS = {
    "hook": True, "stakes": True, "value_turn": True, "meaningful_change": True, "advances_thread": True,
    "in_character": True, "spoils_next_tentpole": False, "honours_choices": True, "obstacle_faced": True,
    "reads_like_people": True, "one_plain_question": True, "moves_on": True, "remembers": True,
    "change_summary": "avant → après", "issues": [], "accepted": True,
}
#: The walk's g1.1 final reading (B1, 14:28): refused for how the page reads, served.
SOFT = {
    **_PASS,
    "reads_like_people": False,
    "one_plain_question": False,
    "accepted": False,
    "issues": [
        "Remove the caption saying Lila is waiting and convey her presence with the coffees visually.",
        "Put Lila’s plain question about the learner’s flight in the final panel, rather than only in the turn metadata.",
    ],
}
#: A storytelling refusal with the hook complaint the walk's refusals opened on.
SOFT_HOOK = {
    **_PASS,
    "hook": False,
    "meaningful_change": False,
    "accepted": False,
    "issues": [
        "Stage tomorrow’s ticket problem and Lila’s promised help in the story rather than only in the checklist.",
        "Let the day end with something different from how it began.",
    ],
}
#: The walk's lost night (B1 g1.2, 14:37, third reading): knowledge the learner never gave.
HARD = {
    **_PASS,
    "honours_choices": False,
    "remembers": False,
    "accepted": False,
    "issues": [
        "Remove the learner’s airline email from Marin’s phone unless the learner has explicitly shared it.",
        "Let Lila convey the ticket information she heard, rather than giving Marin unexplained access to information previously known only to Lila and the notary.",
    ],
}


class _Critic(_Writer):
    """The split fake with a critic that answers from a script (the last answer repeats)."""

    def __init__(self, readings: list[dict]) -> None:
        super().__init__()
        self.readings = list(readings)
        self.read = 0

    def generate_chat_completion(self, messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "StoryReview":
            reading = self.readings[min(self.read, len(self.readings) - 1)]
            self.read += 1
            return SimpleNamespace(content=json.dumps(reading), model="fake-critic", provider="test", total_tokens=30, cost=0.0)
        return super().generate_chat_completion(messages, **kwargs)


def _run(assembled_client, db_session, night, caplog, readings):  # noqa: F811
    writer = night(_Critic(readings))
    user = _learner_on_gap_day(assembled_client, db_session)
    with caplog.at_level(logging.INFO, logger="app.services.journey_latency"):
        status = prefetch_scene_for(db_session, user)
    return status, _outcome(caplog), writer


def test_soft_refusals_on_every_draft_still_write_the_day_and_say_which(
    assembled_client, db_session, journey_enabled, clock, night, caplog  # noqa: F811
):
    status, outcome, _ = _run(assembled_client, db_session, night, caplog, [SOFT])
    assert status == "prefetched"
    kept = outcome["kept"]
    assert isinstance(kept, dict), f"a served refused draft is named, got {kept!r}"
    assert kept["as"] == "critic_override" and kept["attempt"] == 1
    assert "reads_like_people" in kept["why"] and "storytelling" in kept["why"]
    assert outcome["refusals"][0]["failed"] == ["reads_like_people", "one_plain_question"]


def test_a_soft_first_draft_is_kept_when_every_later_draft_is_hard(
    assembled_client, db_session, journey_enabled, clock, night, caplog  # noqa: F811
):
    status, outcome, _ = _run(assembled_client, db_session, night, caplog, [SOFT_HOOK, HARD])
    assert status == "prefetched"
    kept = outcome["kept"]
    assert isinstance(kept, dict) and kept["as"] == "critic_kept" and kept["attempt"] == 0, kept
    assert "meaningful_change" in kept["why"] and "checklist" in kept["issue"]
    assert [row["class"] for row in outcome["refusals"]][1:] == ["story_critic_correctness"] * (len(outcome["refusals"]) - 1)


def test_a_hard_fault_on_every_draft_is_never_served(
    assembled_client, db_session, journey_enabled, clock, night, caplog  # noqa: F811
):
    status, outcome, _ = _run(assembled_client, db_session, night, caplog, [HARD])
    assert status == "unavailable"
    assert outcome["kept"] is None
    assert len(outcome["refusals"]) == outcome["attempts"] >= 2
    assert all(row["class"] == "story_critic_correctness" for row in outcome["refusals"])
    assert all(row["failed"] == ["honours_choices", "remembers"] for row in outcome["refusals"]), outcome["refusals"]


def test_the_hook_item_alone_never_refuses_a_page():
    from app.services.season.director import verdict_failures

    hook_only = StoryReview(**{**_PASS, "hook": False, "issues": ["Stage tomorrow’s hook in the scene."]})
    assert review_verdict(hook_only) is True
    assert verdict_failures(StoryReview(**HARD)) == ["honours_choices", "remembers"]


def test_a_plan_without_lead_id_is_read_from_its_task_without_a_model_call():
    """B1 night of 19 Nov (14:29): «lead_id: Field required» on the attempt's last plan."""

    plan = {
        "location_id": "le_mistral",
        "cast": ["marin_leveque", "lila_bonnet"],
        "beats": ["Lila waits.", "Lila asks."],
        "change": {"before": "a", "after": "b"},
        "question": "What will you do about the flight?",
        "task": "Lila veut savoir ce que tu fais de ton billet.",
    }
    assert story_split.PagePlan.model_validate(plan).lead_id == "lila_bonnet", "the one the task names"
    unnamed = {**plan, "task": "On veut savoir ce que tu fais de ton billet."}
    assert story_split.PagePlan.model_validate(unnamed).lead_id == "marin_leveque", "else the first of the cast"
    given = {**plan, "lead_id": "marin_leveque"}
    assert story_split.PagePlan.model_validate(given).lead_id == "marin_leveque", "a given lead is kept"
