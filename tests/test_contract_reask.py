"""Red-thread design: the day's question, once more and simpler.

On a contract day a reply that does not answer the day's question used to be met with
whatever the reply lane wrote next. With ``STORY_CONTRACT_REASK`` the character puts
the same question once more, in the simpler French the contract wrote for it
(``turns[].ask_again_fr``): never over a question the learner asked, never twice, and
not on the last turn. Off, the reply lane's own reply stands.

With ``STORY_SCENE_RECORD`` on (production), «answered» is read from the scene record and
nothing else (``scene_ledger``): a «non» is an answer (#467), whatever the tutor made of
it. The tests of main's rule (the tutor's ``not_yet`` and the history) run with the
record off.

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
def record_off(monkeypatch):
    monkeypatch.setattr(settings, "STORY_SCENE_RECORD", False)


@pytest.fixture
def reask_on(monkeypatch, contract_on):  # noqa: F811
    monkeypatch.setattr(settings, "STORY_CONTRACT_REASK", True, raising=False)


def _plan() -> dict:
    return {day_contract.ASK_AGAIN_KEY: AGAIN}


def _ask(**change):
    given = {"outcome": "not_yet", "turns_left": 2, "learner_asked": None, "history": []}
    return day_contract.reask(_plan(), **{**given, **change})


def test_a_reply_that_missed_the_question_hears_it_once_more(record_off):
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
def test_and_never_otherwise(change, record_off):
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
    assembled_client, db_session, journey_enabled, clock, season_on, reask_on, record_off, monkeypatch  # noqa: F811
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


# --- the scene record decides «answered» (STORY_SCENE_RECORD) ---------------------------

OPENING = "Tu en penses quoi ? Lequel reste ?"


def _record(*exchanges: tuple[str, str], now: str | None = None) -> dict:
    from app.services import scene_ledger

    return scene_ledger.build(
        opening_line_fr=OPENING,
        history=[{"learner": learner, "character": character} for learner, character in exchanges],
        learner_text=now,
    )


def _asked(ledger: dict, *, history: list | None = None, **change):
    given = {"outcome": "not_yet", "turns_left": 2, "learner_asked": ledger.get("learner_asked"), "history": history or []}
    return day_contract.reask(_plan(), **{**given, **change}, ledger=ledger)


@pytest.mark.parametrize(
    "said",
    [
        # #467 (live walk 2 Nov): a clear «non», then the learner's own idea.
        "Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon.",
        "Non.",
        "Oui.",
        "Le deux.",
    ],
)
def test_an_answered_day_question_is_never_asked_again(said):
    # The tutor read every one of these as missing the objective («not_yet»): main asked
    # the day's question again over a «non». The record says it was answered.
    assert _asked(_record(now=said)) is None
    assert _asked(_record((said, "D'accord."), now="Je ne sais pas.")) is None


def test_the_record_not_the_tutor_says_answered():
    # A learner who only asked has not answered: the question stays open, and the
    # character answers theirs first (``learner_asked``) rather than asking again.
    ledger = _record(now="C'est quoi, un canapé ?")
    assert ledger["learner_asked"] and _asked(ledger) is None
    # The verdict plays no part with the record on: «met» does not close an open question.
    left_behind = _record(("Pourquoi ?", "Parce qu'il est grand. Tu as vu la cuisine ?"), now="Oui.")
    assert _asked(left_behind, outcome="met") == AGAIN


def test_a_day_question_left_behind_is_asked_once_in_its_simpler_words():
    reply = "Parce qu'il est grand. Tu as vu la cuisine ?"
    ledger = _record(("Pourquoi ?", reply), now="Oui, elle est belle.")
    assert _asked(ledger) == AGAIN
    # Once asked again, never twice: the record holds the simpler question now.
    again = _record(("Pourquoi ?", reply), ("Oui, elle est belle.", AGAIN), now="Euh, la cuisine ?")
    assert _asked(again, learner_asked=None) is None
    # Nor when the character asked it again in their own words.
    own_words = _record(("Pourquoi ?", reply), ("Oui.", "Bon. Et lequel reste, alors ?"), now="Euh.")
    assert _asked(own_words, learner_asked=None) is None


def test_a_record_with_no_question_has_nothing_to_ask_again():
    from app.services import scene_ledger

    ledger = scene_ledger.build(opening_line_fr="Bonjour.", history=[], learner_text="Bonjour.")
    assert _asked(ledger) is None
    assert _asked({}) is None


def _voice_says(provider, monkeypatch, lines: list[str]) -> None:
    """The fake reply lane says ``lines`` in turn, then «D'accord.»."""

    reply = provider.generate_chat_completion
    said = iter(lines)

    def answer(messages, **kwargs):
        response = reply(messages, **kwargs)
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] != "VoiceReply":
            return response
        value = {**json.loads(response.content), "reply_fr": next(said, "D'accord.")}
        return SimpleNamespace(**{**vars(response), "content": json.dumps(value, ensure_ascii=False)})

    monkeypatch.setattr(provider, "generate_chat_completion", answer)


@LANES
def test_a_no_is_never_met_with_the_days_question_again(
    assembled_client, db_session, journey_enabled, clock, season_on, reask_on, monkeypatch  # noqa: F811
):
    # #467: the tutor misses the first reply, a «non». Main asked the question again.
    _misses_first(season_on, monkeypatch)
    d, _user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    replies = _replies(d, season_on, ["Non, je ne veux pas.", "Le deux."])
    assert replies == ["D'accord.", "D'accord.", "D'accord."]


@LANES
def test_the_day_question_left_behind_comes_back_once(
    assembled_client, db_session, journey_enabled, clock, season_on, reask_on, monkeypatch  # noqa: F811
):
    _voice_says(season_on, monkeypatch, ["Parce qu'il est grand. Tu as vu la cuisine ?"])
    d, _user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    beat = next(row for row in load_season("s1").gaps["g3"].days if row.premise == "les_canapes")
    again = beat.contract.turns[0].ask_again_fr
    replies = _replies(d, season_on, ["Pourquoi ?", "Oui, elle est belle.", "Euh, la cuisine ?"])
    assert replies[1] == again
    assert replies.count(again) == 1, replies
