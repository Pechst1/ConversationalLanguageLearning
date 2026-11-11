"""The reply check is a veto, on a whole generated day, and it costs no new model call.

The story-truth decision (11 Nov 2026): a reply that goes against the scene's record (it
asks an answered question again, joins the learner's refusal of the character's own
proposal, quotes words they never wrote…) is re-rolled once with the reason. If the
re-roll does it too, the authored line plays (``scene_exit.reaction``), in the
character's register, and the tutor's verdict stands. The reply is never served with the
offending part cut out, and the turn never makes a third reply call.

Calls per learner turn on a generated day, counted here with the fake provider:

* main (``STORY_SCENE_RECORD`` off): 2, a TutorVerdict and a VoiceReply;
* the record on, a reply that passes: 2, the same calls (the turn is read by the
  VoiceReply the turn already makes: ``learner_intent``);
* the record on, a vetoed reply: 3 at most, the one re-roll (then the authored line).

Fake models only: nothing is spent.
"""

from __future__ import annotations

import json
from collections import Counter
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import scene_exit
from tests import test_journey_end_to_end as support
from tests.test_contract_stand_in import _learner
from tests.test_day_contract_ending import contract_on  # noqa: F401 - fixture
from tests.test_season_one import TurnScript, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

LANES = pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)

#: #591 (live walk 8 Nov), exact: Camille proposes, the learner refuses and asks why, and
#: Camille joined the refusal of her own proposal and skipped the question.
PROPOSES = "Bon. L'appartement paie d'abord mon grand-père. Tu es d'accord, non ?"
REFUSES = "Non, je ne suis pas daccord. Pourquoi le appartement paie grand-pere dabord ?"
ECHO = "Je ne suis pas d'accord non plus. Mais pourquoi cette question ?"


def _scripted_voice(provider, monkeypatch, lines: list[str]) -> list[str]:
    """The fake reply lane says ``lines`` in order, then «D'accord.»; every model call's
    schema is recorded, in order."""

    reply = provider.generate_chat_completion
    said = iter(lines)
    schemas: list[str] = []

    def answer(messages, **kwargs):
        response = reply(messages, **kwargs)
        data = json.loads(messages[0]["content"])
        schemas.append(data["output_schema"]["title"])
        if schemas[-1] != "VoiceReply":
            return response
        value = {**json.loads(response.content), "reply_fr": next(said, "D'accord.")}
        return SimpleNamespace(**{**vars(response), "content": json.dumps(value, ensure_ascii=False)})

    monkeypatch.setattr(provider, "generate_chat_completion", answer)
    return schemas


def _day(d, provider, answers: list[str]) -> list[dict]:
    provider.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Vous avez parlé.")
    d.create()
    assert d.journey["status"] == "active", d.journey
    said = iter(answers)
    return d.play(answer=lambda _step: next(said, answers[-1]))


def _per_turn(schemas: list[str]) -> list[Counter]:
    """The reply calls of each learner turn: a TutorVerdict opens each turn."""

    turns: list[Counter] = []
    for schema in schemas:
        if schema == "TutorVerdict":
            turns.append(Counter())
        if turns and schema in ("TutorVerdict", "VoiceReply"):
            turns[-1][schema] += 1
    return turns


@LANES
@pytest.mark.parametrize("record", [False, True], ids=["main", "record"])
def test_a_turn_makes_the_same_calls_with_the_record(
    record, assembled_client, db_session, journey_enabled, clock, season_on, contract_on, monkeypatch  # noqa: F811
):
    monkeypatch.setattr(settings, "STORY_SCENE_RECORD", record)
    schemas = _scripted_voice(season_on, monkeypatch, [])
    d, _user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    results = _day(d, season_on, ["Le rouge.", "Oui, je le garde.", "Merci."])
    turns = _per_turn(schemas)
    assert len(turns) == len(results) == 3
    assert all(turn == Counter({"TutorVerdict": 1, "VoiceReply": 1}) for turn in turns), turns
    # Once a day, off the learner's wait: the ending and its critic.
    assert Counter(schemas)["StoryTurn"] == 1 and Counter(schemas)["TurnReview"] == 1


@LANES
def test_camille_does_not_echo_the_learners_refusal(
    assembled_client, db_session, journey_enabled, clock, season_on, contract_on, monkeypatch  # noqa: F811
):
    """#591 on a whole day: the echo comes back on the re-roll, so the authored line plays.
    Main served the echo; the stack before the decision served it trimmed («Mais pourquoi
    cette question ?»), which still skipped the learner's question."""

    schemas = _scripted_voice(season_on, monkeypatch, [PROPOSES, ECHO, ECHO])
    d, _user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    results = _day(d, season_on, ["Je ne sais pas.", REFUSES, "Bon."])
    replies = [str(row.get("character_reply_fr") or "") for row in results]
    assert replies[0] == PROPOSES
    assert "pas d'accord" not in replies[1].casefold()
    assert "pourquoi cette question" not in replies[1].casefold()
    # The authored reaction to a «non», in the character's register (``scene_exit``).
    authored = {line for lines in scene_exit._REACTIONS["no"].values() for line in lines}
    assert replies[1].split(" ", 1)[1] in authored, replies[1]
    turns = _per_turn(schemas)
    # The vetoed turn: one re-roll, never a third reply call. The others: main's two calls.
    assert turns[1] == Counter({"TutorVerdict": 1, "VoiceReply": 2}), turns
    assert turns[0] == turns[2] == Counter({"TutorVerdict": 1, "VoiceReply": 1}), turns
    # The verdict and the correction stand: the tutor read the reply. The line is labelled
    # authored, never shown as the character's live answer.
    assert results[1]["task_outcome"] == "met"
    assert results[1]["check"]["corrected"]
    assert results[1]["reply_source"] == "authored"
    assert results[0]["reply_source"] == results[2]["reply_source"] == "model"
