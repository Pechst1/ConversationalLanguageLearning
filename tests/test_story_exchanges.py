"""A story scene is a conversation, not one line (2026-09-25).

The rhythm plans a reply's exchanges (``RhythmCaps.max_turns``). Until the last
one, ``turn_plan.keep_talking`` is set: the character answers and moves the scene
on, the respond step stays open, and no ending is written. The tutor grades the
objective across the whole conversation. Fake provider only, never a paid call.
"""

from __future__ import annotations

from dataclasses import replace

from app.services import living_story as engine
from app.services.journey_contracts import MAX_RESPOND_TURNS, RHYTHM_CAPS, rhythm_caps
from tests import test_wp87_lanes as harness
from tests.test_living_story import driver

assembled_client = harness.assembled_client
journey_enabled = harness.journey_enabled
clock = harness.clock
provider = harness.provider
jobs = harness.jobs


def _task(max_turns: int):
    from tests.test_journey_planner import _response_task

    return replace(_response_task(), max_turns=max_turns)


def test_the_rhythm_sets_the_exchanges():
    assert rhythm_caps(300).max_turns == 2
    assert rhythm_caps(600).max_turns == 3
    assert rhythm_caps(1200).max_turns == 4
    assert rhythm_caps(1800).max_turns == 4
    assert all(caps.max_turns <= MAX_RESPOND_TURNS for caps in RHYTHM_CAPS.values())


def test_keep_talking_until_the_last_exchange():
    three = _task(3)
    assert [engine.keeps_talking(three, index) for index in range(4)] == [True, True, False, False]
    assert engine.keeps_talking(_task(1), 0) is False


def test_a_wording_question_takes_the_turn_instead():
    assert engine.keeps_talking(_task(3), 0, self_repair=object()) is False


def test_a_met_first_reply_keeps_the_conversation_open(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    d = driver(assembled_client, db_session)
    step = harness._to_respond(d)
    assert step["prompt"]["max_turns"] >= 2

    _, _, first = harness._respond(assembled_client, d, step)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["task_outcome"] == "met"
    assert result["next_turn"] is not None, "the scene goes on after a good first reply"
    assert result["next_turn"]["prompt"]["turn_index"] == 1
    assert not jobs, "no ending is written while the conversation is open"
    voice = [data for schema, data in provider.calls if schema == "VoiceReply"]
    assert voice[-1]["turn_plan"]["keep_talking"] is True

    # Answer until the step closes: the last exchange ends the scene.
    for _ in range(MAX_RESPOND_TURNS):
        current = d.current()
        if current is None or current["kind"] != "respond":
            break
        _, _, reply = harness._respond(assembled_client, d, current)
        assert reply.status_code == 200, reply.text
        if reply.json()["next_turn"] is None:
            break
    voice = [data for schema, data in provider.calls if schema == "VoiceReply"]
    assert voice[-1]["turn_plan"]["keep_talking"] is False
    assert len(jobs) == 1, "one ending, after the last exchange"
    assert len(voice) == step["prompt"]["max_turns"]
