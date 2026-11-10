"""Red-thread design: the day's question, once more and simpler.

On a contract day a reply that does not answer the day's question used to be met with
whatever the reply lane wrote next. With ``STORY_CONTRACT_REASK`` the character puts
the same question once more, in the simpler French the contract wrote for it
(``turns[].ask_again_fr``): never over a question the learner asked, never twice, and
not on the last turn. Off, the reply lane's own reply stands.

Fake models only: nothing is spent.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.season import day_contract
from app.services.season.format import load_season
from tests import test_journey_end_to_end as support
from tests.test_contract_stand_in import _learner
from tests.test_day_contract_ending import contract_on  # noqa: F401 - fixture
from tests.test_season_one import TurnScript, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

LANES = pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)
AGAIN = "Alors ? Lequel reste ?"


@pytest.fixture
def reask_on(monkeypatch, contract_on):  # noqa: F811
    monkeypatch.setattr(settings, "STORY_CONTRACT_REASK", True, raising=False)


def _plan() -> dict:
    return {day_contract.ASK_AGAIN_KEY: AGAIN}


def _ask(**change):
    given = {"outcome": "not_yet", "turns_left": 2, "learner_asked": None, "history": []}
    return day_contract.reask(_plan(), **{**given, **change})


def test_a_reply_that_missed_the_question_hears_it_once_more():
    assert _ask() == AGAIN


@pytest.mark.parametrize(
    "change",
    [
        {"outcome": "met"},
        {"outcome": "partially_met"},
        {"turns_left": 0},
        {"learner_asked": "C'est quoi, un canapé ?"},
        {"history": [{"learner": "Bonjour.", "character": "Alors ?  lequel reste ?"}]},
    ],
    ids=["answered", "half-answered", "last-turn", "the-learner-asked", "asked-already"],
)
def test_and_never_otherwise(change):
    assert _ask(**change) is None


def test_a_day_without_the_simpler_question_is_left_alone():
    assert day_contract.reask({}, outcome="not_yet", turns_left=2, learner_asked=None, history=[]) is None
    assert day_contract.reask(None, outcome="not_yet", turns_left=2, learner_asked=None, history=[]) is None


def test_the_turn_carries_the_question_only_with_the_flag(monkeypatch, contract_on):  # noqa: F811
    season = load_season("s1")
    ctx = {"position": {"segment": "g3"}, "checklist": {"premise_id": "les_canapes"}, "required_premise": "les_canapes"}
    assert day_contract.ASK_AGAIN_KEY not in day_contract.for_turn(season, ctx, band="A1")
    monkeypatch.setattr(settings, "STORY_CONTRACT_REASK", True, raising=False)
    beat = next(row for row in season.gaps["g3"].days if row.premise == "les_canapes")
    assert day_contract.for_turn(season, ctx, band="A1")[day_contract.ASK_AGAIN_KEY] == beat.contract.turns[0].ask_again_fr


def test_a_simpler_question_is_a_question():
    season = load_season("s1")
    for gap_id in ("g3", "g4"):
        for beat in season.gaps[gap_id].days:
            again = beat.contract.turns[0].ask_again_fr
            # A day with a silent lead has none, and is left to the reply lane.
            assert not again or "?" in again, (beat.premise, again)


# --- a whole day -------------------------------------------------------------------


def _misses_first(provider, monkeypatch):
    """The fake tutor: the learner's first reply does not answer the question."""

    reply = provider.generate_chat_completion
    verdicts: list[str] = []

    def answer(messages, **kwargs):
        response = reply(messages, **kwargs)
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] != "TutorVerdict":
            return response
        verdicts.append("not_yet" if not verdicts else "met")
        value = {**json.loads(response.content), "outcome": verdicts[-1]}
        if verdicts[-1] == "not_yet":
            value["evidence_quotes"] = []
        return SimpleNamespace(**{**vars(response), "content": json.dumps(value, ensure_ascii=False)})

    monkeypatch.setattr(provider, "generate_chat_completion", answer)
    return verdicts


def _replies(d, provider, answers: list[str]) -> list[str]:
    provider.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Vous avez parlé.")
    d.create()
    assert d.journey["status"] == "active", d.journey
    said = iter(answers)
    results = d.play(answer=lambda _step: next(said, answers[-1]))
    return [str(row.get("character_reply_fr") or "") for row in results]


@LANES
def test_the_character_asks_the_days_question_again_not_a_new_one(
    assembled_client, db_session, journey_enabled, clock, season_on, reask_on, monkeypatch  # noqa: F811
):
    _misses_first(season_on, monkeypatch)
    d, _user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    beat = next(row for row in load_season("s1").gaps["g3"].days if row.premise == "les_canapes")
    again = beat.contract.turns[0].ask_again_fr
    replies = _replies(d, season_on, ["Il pleut.", "Le deux."])
    # The fake reply lane says «D'accord.» to everything.
    assert replies == [again, "D'accord.", "D'accord."]


@LANES
def test_off_the_reply_lanes_own_reply_stands(
    assembled_client, db_session, journey_enabled, clock, season_on, contract_on, monkeypatch  # noqa: F811
):
    _misses_first(season_on, monkeypatch)
    d, _user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    replies = _replies(d, season_on, ["Il pleut.", "Le deux."])
    assert replies == ["D'accord.", "D'accord.", "D'accord."]
