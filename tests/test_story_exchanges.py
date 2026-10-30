"""A story scene is a conversation, not one line (2026-09-25).

The rhythm plans a reply's exchanges (``RhythmCaps.max_turns``). Until the last
one, ``turn_plan.keep_talking`` is set: the character answers and moves the scene
on, the respond step stays open, and no ending is written. The tutor grades the
objective across the whole conversation. Fake provider only, never a paid call.
"""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import UUID

from app.services import living_story as engine
from app.services.journey_contracts import (
    LEGER_SCENE_EXCHANGES,
    MAX_RESPOND_TURNS,
    MIN_SCENE_EXCHANGES,
    RHYTHM_CAPS,
    SCENE_QUESTION_GRACE,
    rhythm_caps,
)
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
    # #378: at least MIN_SCENE_EXCHANGES from Régulier up; Léger keeps its five minutes.
    assert rhythm_caps(300).max_turns == 2 and LEGER_SCENE_EXCHANGES == 1
    assert rhythm_caps(600).max_turns == 3
    assert rhythm_caps(1200).max_turns == 4
    assert rhythm_caps(1800).max_turns == 4
    assert all(caps.max_turns <= MAX_RESPOND_TURNS for caps in RHYTHM_CAPS.values())
    assert all(caps.max_turns >= MIN_SCENE_EXCHANGES for budget, caps in RHYTHM_CAPS.items() if budget > 300)


def test_keep_talking_until_the_last_exchange():
    three = _task(3)
    assert [engine.keeps_talking(three, index) for index in range(4)] == [True, True, False, False]
    assert engine.keeps_talking(_task(1), 0) is False


def test_a_wording_question_takes_the_turn_instead():
    assert engine.keeps_talking(_task(3), 0, self_repair=object()) is False


def test_a_met_first_reply_keeps_the_conversation_open(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    # The fake model says something new at each exchange: one that said its previous
    # line again would be refused as a repeat of the thread (#349).
    fresh = iter(f"Alors, parlons du point {n}. Qu'en pensez-vous ?" for n in range(1, 20))
    original = provider.generate_chat_completion

    def say_something_new(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "VoiceReply":
            provider.voice = {**provider.voice, "reply_fr": next(fresh)}
        return original(messages, **kwargs)

    provider.generate_chat_completion = say_something_new
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
    assert "On se dit bonjour" not in (result["character_reply_fr"] or ""), (
        "no etiquette question stacked on the character's own next question"
    )
    voice = [data for schema, data in provider.calls if schema == "VoiceReply"]
    assert voice[-1]["turn_plan"]["keep_talking"] is True

    # Answer until the step closes. Every reply of this fake asks the learner
    # something, so (#378) the scene takes the answer past the plan, up to the grace.
    for _ in range(MAX_RESPOND_TURNS + SCENE_QUESTION_GRACE):
        current = d.current()
        if current is None or current["kind"] != "respond":
            break
        _, _, reply = harness._respond(assembled_client, d, current)
        assert reply.status_code == 200, reply.text
        following = reply.json()["next_turn"]
        if following is None:
            break
        prompt = following["prompt"]
        assert prompt["turn_index"] < prompt["max_turns"], "the counter never reads «4 of 3»"
    voice = [data for schema, data in provider.calls if schema == "VoiceReply"]
    assert voice[-1]["turn_plan"]["keep_talking"] is False
    assert len(jobs) == 1, "one ending, after the last exchange"
    assert len(voice) == step["prompt"]["max_turns"] + SCENE_QUESTION_GRACE


# ---------------------------------------------------------------------------
# #378 · the scene listens: three exchanges, and it never closes on its own question
# ---------------------------------------------------------------------------

#: The live walk of 30 Oct 2026, Nº 17: Lila's one reply, which closed the scene
#: (in the fake scene's «vous»).
LILA_ASKS = "Fatigué de Berlin, je comprends. Et ce restaurant vous fait peur ?"
LILA_SETTLES = "D'accord, pas le restaurant. On ira au café, alors."


def _scripted_voice(provider, lines):
    """The fake voice says ``lines`` in order (then the last one again, made new)."""

    original = provider.generate_chat_completion

    def speak(messages, **kwargs):
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] == "VoiceReply":
            # Keyed by the exchange, so a soft-rejected retry says the same line again.
            index = len(data["data"].get("history") or [])
            line = lines[index] if index < len(lines) else f"Bon, on avance, point {index}."
            provider.voice = {**provider.voice, "reply_fr": line}
        return original(messages, **kwargs)

    provider.generate_chat_completion = speak


def _play(assembled_client, d, answers):
    """Answer the respond step with ``answers`` until it closes; the replies."""

    results = []
    for text in answers:
        current = d.current()
        if current is None or current["kind"] != "respond":
            break
        _, _, reply = harness._respond(assembled_client, d, current, text=text)
        assert reply.status_code == 200, reply.text
        results.append(reply.json())
        if reply.json()["next_turn"] is None:
            break
    return results


def test_the_last_planned_exchange_that_asks_waits_for_the_answer(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    """Golden transcript (#378): on the last planned exchange Lila asks «Et ce
    restaurant te fait peur ?». The scene does not close under it: the learner
    answers, Lila takes the answer, and only then is the ending written."""

    d = driver(assembled_client, db_session)
    step = harness._to_respond(d)
    planned = step["prompt"]["max_turns"]
    assert planned >= MIN_SCENE_EXCHANGES
    fillers = [f"Alors, et le point {n} ?" for n in range(1, planned)]
    _scripted_voice(provider, [*fillers, LILA_ASKS, LILA_SETTLES])
    answers = [
        *(f"Oui, le point {n} me va." for n in range(1, planned)),
        "Je veux retourner le deux décembre, parce que je suis fatigué de Berlin.",
        "Non, le restaurant ne me fait pas peur. Je préfère le café.",
    ]
    results = _play(assembled_client, d, answers)

    assert len(results) == planned + 1, "one more exchange: the answer to Lila's question"
    asked = results[planned - 1]
    assert asked["character_reply_fr"] == LILA_ASKS
    assert asked["next_turn"] is not None, "the scene stays open under Lila's question"
    assert asked["next_turn"]["prompt"]["max_turns"] == planned + 1
    assert results[-1]["character_reply_fr"] == LILA_SETTLES
    assert results[-1]["next_turn"] is None, "a statement closes the scene"
    assert len(jobs) == 1, "one ending, after the question was answered"

    stored = db_session.get(harness.DailyJourneyStep, UUID(step["id"]))
    ledger = stored.private_task["ledger"]
    lila = [row for row in ledger["asked"] if row["text_fr"] == "Et ce restaurant vous fait peur ?"]
    assert lila and lila[0]["answered_at"] == planned, "the ledger records the answer"
    assert ledger["open_for_learner"] is None


def test_a_scene_that_keeps_asking_still_ends_after_the_grace(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    d = driver(assembled_client, db_session)
    step = harness._to_respond(d)
    planned = step["prompt"]["max_turns"]
    _scripted_voice(provider, [f"D'accord. Et la question {n} ?" for n in range(1, 20)])
    results = _play(assembled_client, d, [f"Réponse numéro {n}." for n in range(1, 20)])
    assert len(results) == planned + SCENE_QUESTION_GRACE
    assert results[-1]["next_turn"] is None
    assert len(jobs) == 1


def test_the_learners_question_reaches_the_voice_first(
    assembled_client, db_session, journey_enabled, clock, provider, jobs
):
    """The character answers the learner's question: the voice lane is told it."""

    d = driver(assembled_client, db_session)
    harness._to_respond(d)
    _scripted_voice(provider, ["Oui, j'ai un chat. Il s'appelle Pablo. Et vous, vous venez ?"])
    _play(assembled_client, d, ["Je viens samedi. Vous avez un chat ?"])
    voice = [data for schema, data in provider.calls if schema == "VoiceReply"]
    assert voice[-1]["turn_plan"]["learner_asked"] == "Vous avez un chat ?"
    assert voice[-1]["ledger"]["learner_asked"] == "Vous avez un chat ?"
    assert "turn_plan.learner_asked" in engine_voice_prompt()


def engine_voice_prompt() -> str:
    from app.services.story_lanes import VOICE

    return VOICE
