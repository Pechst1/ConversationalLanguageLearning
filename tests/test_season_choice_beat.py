"""Night shift #264: a choice beat reflects what the learner chose.

Live walk 21-22 Oct. On Lila's «Une clé pour moi ?» the learner tapped «Pas encore»;
the recap then offered «One line to say aloud: Donner une clé à Lila» (the other
card), and Camille was shown answering a choice made to Lila, with «Lila : » printed
inside the line. Second variant: «Non, je ne pense pas que c'est Marin» was met by
«C'est Marin, je pense.» to say aloud.

The mechanism: the line to repeat was the *task's* scripted example, fixed when the
question was posed, so nothing the learner did could change it; and a reaction named
its speaker with a text prefix whenever it was not the scene's own character, instead
of the speaker of the turn being answered. Pinned here:

1. what the learner chose (a card, or a free reply the page clearly heard) is kept
   with the exchange as the sentence to say, and that is the line the recap offers;
2. a turn's reaction names no one inside the line when the turn's own addressee
   speaks it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import spoken_reply
from app.services.season import runtime
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.season.runtime import projected_turns, turn_example
from app.services.season.turns import ReplyChoice
from tests.test_season_story_qa import _record, _say, _scenario


@pytest.fixture
def offline(monkeypatch):
    real = runtime.classify

    def classify(db, user, **kwargs):
        kwargs["use_model"] = False
        return real(db, user, **kwargs)

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    monkeypatch.setattr(spoken_reply.settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)
    runtime._ROUTE_CACHE.clear()
    yield


def _key_day():
    season = load_season("s1")
    page = resolve_day(season, "t2", "b", flags=effective_flags(season, {}, seed="x"), band="A2", language="de")
    scenario = _scenario(page)
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    index = next(i for i, turn in enumerate(turns) if turn["id"].startswith("b.key"))
    return scenario, turns, index


def _the_step_after(history, turn):
    """The step as the journey stores it: the example fixed when the question was posed."""

    return SimpleNamespace(
        private_task={
            "turns": list(history),
            "response_task": {"suggested_response_fr": turn_example(turn)},
        }
    )


def _choose(label):
    scenario, turns, index = _key_day()
    history: list[dict] = []
    for exchange in range(index):
        said = str(turns[exchange]["replies"][0]["examples"][0])
        _record(history, said, _say(scenario, said, history, exchange))
    evaluation = _say(scenario, label, history, index)
    _record(history, label, evaluation)
    return scenario, turns, index, history, evaluation


@pytest.mark.parametrize("label", ["Lui faire un double", "Pas encore"])
def test_the_line_to_say_aloud_is_the_card_the_learner_tapped(offline, label):
    _scenario_, turns, index, history, evaluation = _choose(label)
    line = spoken_reply.repeat_line_for(_the_step_after(history, turns[index]))
    assert line == label, f"tapped «{label}», the recap offers «{line}» to say aloud"


def test_a_reaction_spoken_by_the_turns_addressee_names_no_one_in_the_line(offline):
    _scenario_, turns, index, history, evaluation = _choose("Pas encore")
    assert turns[index]["to"] == "lila_bonnet"
    assert "Pas encore. D'accord." in evaluation.character_reply_fr
    assert "Lila :" not in evaluation.character_reply_fr, evaluation.character_reply_fr
    assert [line["speaker_id"] for line in evaluation.reply_lines] == ["lila_bonnet"]


def test_a_free_reply_the_page_heard_is_said_as_the_route_it_took(monkeypatch, offline):
    """«Non, ce n'est pas lui» routed to the page's «no» reply must not be answered by
    the page's first example, which says the opposite."""

    season = load_season("s1")
    page = resolve_day(season, "t1", "a", flags=effective_flags(season, {}, seed="x"), band="A1", language="de")
    scenario = _scenario(page)
    turn = projected_turns(page)[0]
    other = next(reply for reply in turn["replies"] if reply["examples"][0] != turn_example(turn))

    def classify(db, user, **kwargs):
        return ReplyChoice(reply_id=other["id"], confidence=1.0, clear=True)

    monkeypatch.setattr(runtime, "classify", classify)
    scenario.character_id = turn["to"]
    history: list[dict] = []
    text = "Je ne sais pas comment le dire."
    evaluation = _say(scenario, text, history, 0)
    _record(history, text, evaluation)
    # The conversation closes on this turn; the step still holds the question's example.
    line = spoken_reply.repeat_line_for(_the_step_after(history, turn))
    assert line == other["examples"][0], (line, other["examples"][0])
    assert line != turn_example(turn)
