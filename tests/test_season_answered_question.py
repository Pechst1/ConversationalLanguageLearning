"""Walk 21 Oct (#262): the scene re-asks a question the learner has just answered.

Camille asked «Qu'est-ce que vous gardez ?», heard «Je garde la cuisine… je ne veux pas
vendre les meubles», said «Vous voulez garder la cuisine et les meubles. C'est noté.» and,
in the same turn, «Pardon ? Qu'est-ce que vous gardez, ici ?». Lila asked «Tu restes
combien de temps ?», heard «Je reste trois jours, parce que je dois décider si je vends
le café.» and answered «Je demande : combien de temps tu restes ?».

Why the code allowed it: a turn knows a closed set of authored replies, and «this reply
matches none of them» (``clear=False``) was the only test for «ask again». A real answer
that is simply not one of the authored ones (a concrete duration, a kitchen) was treated
like a name alone or a greeting. Whether the learner ANSWERED the question is now read
separately (``answers_question``), and only a reply that does not answer is asked again.
"""

from __future__ import annotations

import pytest

from app.services.season import runtime
from app.services.season.runtime import ASK_AGAIN
from app.services.season.turns import ReplyChoice
from tests.test_season_story_qa import _record, _say, _scenario


@pytest.fixture
def reading(monkeypatch):
    """A scripted model reading: ``reading.choice`` is what the classifier returns."""

    state = type("Reading", (), {"choice": None})()

    def classify(db, user, **kwargs):
        return state.choice

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    yield state


def _t2b_scenario():
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day

    season = load_season("s1")
    page = resolve_day(season, "t2", "b", flags=effective_flags(season, {}, seed="x"), band="A1", language="en")
    scenario = _scenario(page)
    return scenario, scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]


def _flat(evaluation) -> str:
    """A short reason: pytest drops a long one from its summary line."""

    return "re-asked" if evaluation.route["reply"] == ASK_AGAIN else "advanced"


def _said(evaluation) -> str:
    return " ".join(line["text_fr"] for line in evaluation.reply_lines).casefold()


def test_a_full_answer_that_fits_no_authored_reply_is_not_asked_again(reading):
    scenario, turns = _t2b_scenario()
    turn = turns[0]
    scenario.character_id = turn["to"]
    reading.choice = ReplyChoice(
        reply_id=str(turn["fallback"]),
        confidence=0.3,
        clear=False,
        ack_fr="Vous voulez garder la cuisine et les meubles. C'est noté.",
    )
    evaluation = _say(scenario, "Je garde la cuisine… je ne veux pas vendre les meubles", [], 0)
    assert evaluation.route["reply"] != ASK_AGAIN, _flat(evaluation)
    assert evaluation.turn_consumed is True, "the beat advances after one answer"
    assert evaluation.reply_lines[0]["text_fr"] == "Vous voulez garder la cuisine et les meubles. C'est noté."
    said = _said(evaluation)
    assert "pardon" not in said and "gardez" not in said and "garder quelque chose" not in said


def test_a_duration_that_fits_no_authored_reply_is_not_asked_again(reading):
    scenario, turns = _t2b_scenario()
    history: list[dict] = []
    scenario.character_id = turns[0]["to"]
    reading.choice = ReplyChoice(reply_id="d", confidence=0.9)
    first = _say(scenario, "Rien. Je vends.", history, 0)
    _record(history, "Rien. Je vends.", first)
    assert first.route == {"turn": turns[0]["id"], "reply": "d"}
    turn = turns[1]
    scenario.character_id = turn["to"]
    reading.choice = ReplyChoice(
        reply_id=str(turn["fallback"]), confidence=0.3, clear=False, ack_fr="Tu es fatigué après ce long voyage."
    )
    text = "Je reste trois jours, parce que je dois décider si je vends le café."
    evaluation = _say(scenario, text, history, 1)
    assert evaluation.route["reply"] != ASK_AGAIN, _flat(evaluation)
    assert evaluation.turn_consumed is True
    said = _said(evaluation)
    assert "je demande" not in said and "combien de temps" not in said and "pardon" not in said


def test_a_reply_that_does_not_answer_is_still_asked_again(reading):
    scenario, turns = _t2b_scenario()
    turn = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"][0]
    scenario.character_id = turn["to"]
    for text in ("Je m'appelle Vincent.", "Bonjour !", "Qu'est-ce que vous gardez, vous ?", "Il pleut beaucoup."):
        runtime._ROUTE_CACHE.clear()
        reading.choice = ReplyChoice(reply_id=str(turn["fallback"]), confidence=0.2, clear=False)
        evaluation = _say(scenario, text, [], 0)
        assert evaluation.route == {"turn": turn["id"], "reply": ASK_AGAIN}, _flat(evaluation)
        assert evaluation.turn_consumed is False


def test_the_offline_matcher_hears_the_same_answers(monkeypatch):
    """No model (the fake provider, an outage): the matcher finds no authored reply, and the
    scene still hears a reply that answers the question."""

    real = runtime.classify
    monkeypatch.setattr(runtime, "classify", lambda db, user, **kw: real(db, user, **{**kw, "use_model": False}))
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    scenario, turns = _t2b_scenario()
    scenario.character_id = turns[0]["to"]
    history: list[dict] = []
    first = _say(scenario, "Je garde la cuisine… je ne veux pas vendre les meubles", history, 0)
    assert first.route["reply"] != ASK_AGAIN and first.turn_consumed is True, _flat(first)
    _record(history, "Je garde la cuisine… je ne veux pas vendre les meubles", first)
    scenario.character_id = turns[1]["to"]
    second = _say(scenario, "Je reste trois jours, parce que je dois décider si je vends le café.", history, 1)
    assert second.route["reply"] != ASK_AGAIN and second.turn_consumed is True, _flat(second)
