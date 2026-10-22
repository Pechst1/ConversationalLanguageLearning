"""STORY-LISTENS (2026-10-12): an authored tentpole page hears what the learner wrote.

The owner's iPhone test: «the story is extremely deterministic and does not respond
to what I write». On a tentpole page the learner's words only picked one of the
authored replies, and an off-script reply on a turn without an authored «ask again»
line silently played the fallback, as if the learner had said it. Pinned here:

1. the reply classifier's ``ack_fr`` — one line answering the learner's own words —
   is played first, in the addressee's voice, before the authored reaction;
2. an acknowledgement in the wrong register, too long, in another language or
   echoing the learner's sentence is dropped, never served;
3. an unclear reply on a turn with no authored «ask again» line is asked again with
   the turn's own question, once;
4. the classifier sees the speaker's register, the band and each reply's reaction,
   so its line fits what is played after it.
"""

from __future__ import annotations

import pytest

from app.services.journey_contracts import TaskOutcome
from app.services.season import runtime
from app.services.season.runtime import ASK_AGAIN, projected_turns
from app.services.season.turns import (
    ReplyChoice,
    classifier_payload,
    clean_ack,
    generic_ask_again_panel,
    turn_address,
)
from tests.test_season_story_qa import _page, _record, _say, _scenario


@pytest.fixture
def reading(monkeypatch):
    """A scripted model reading: ``reading.choice`` is what the classifier returns."""

    state = type("Reading", (), {"choice": None, "calls": []})()

    def classify(db, user, **kwargs):
        state.calls.append(kwargs)
        if not kwargs.get("use_model", True):
            return runtime.ReplyChoice(reply_id=str(kwargs["turn"].get("fallback")), confidence=0.0, clear=False)
        return state.choice

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    yield state


def test_the_addressee_first_answers_what_the_learner_wrote(reading):
    scenario = _scenario(_page())
    reading.choice = ReplyChoice(
        reply_id="a", confidence=0.9, ack_fr="De Berlin, sous cette pluie ? Vous êtes courageux."
    )
    evaluation = _say(scenario, "Je viens de Berlin. Odile est ma grand-mère.", [], 0)
    assert {k: evaluation.route[k] for k in ("turn", "reply")} == {"turn": "a.turn1", "reply": "a"}
    assert evaluation.route["say_fr"], "what the learner meant is kept as a sentence to say"
    first = evaluation.reply_lines[0]
    assert first["speaker_id"] == "augustin_de_roncourt"
    assert first["text_fr"] == "De Berlin, sous cette pluie ? Vous êtes courageux."
    assert evaluation.character_reply_fr.startswith("De Berlin")
    # The authored reaction still plays after it.
    assert len(evaluation.reply_lines) > 1


def test_a_line_in_the_wrong_register_is_never_served(reading):
    scenario = _scenario(_page())
    reading.choice = ReplyChoice(reply_id="a", confidence=0.9, ack_fr="Tu viens de loin, toi.")
    evaluation = _say(scenario, "Odile est ma grand-mère.", [], 0)
    assert "Tu viens de loin" not in evaluation.character_reply_fr


def test_clean_ack_guards():
    assert clean_ack("Enchanté, Vincent.", learner_text="Je suis Vincent", address="vous") == "Enchanté, Vincent."
    assert clean_ack("Vous êtes qui ?", learner_text="x", address="tu") is None
    assert clean_ack("Ton nom ?", learner_text="x", address="vous") is None
    assert clean_ack("Vous deux, venez !", learner_text="x", address="tu") == "Vous deux, venez !"
    assert clean_ack("I am happy to meet you, really.", learner_text="x", address=None) is None
    assert clean_ack("Je viens pour l'appartement de ma grand-mère.", learner_text="je viens pour l'appartement de ma grand-mère", address=None) is None
    assert clean_ack("mot " * 30, learner_text="x", address=None) is None
    assert clean_ack(None, learner_text="x", address=None) is None
    assert clean_ack("Bonjour {name}", learner_text="x", address=None) is None


def test_an_unclear_reply_without_an_authored_line_is_asked_again_once(reading):
    page = _page()
    scenario = _scenario(page)
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    turns[0] = {key: value for key, value in turns[0].items() if key != "ask_again"}
    reading.choice = ReplyChoice(
        reply_id=str(turns[0]["fallback"]), confidence=0.2, clear=False, ack_fr="Un touriste ? Ici ?"
    )
    history: list[dict] = []
    first = _say(scenario, "Je suis touriste.", history, 0)
    assert first.route == {"turn": "a.turn1", "reply": ASK_AGAIN}
    assert first.turn_consumed is False
    said = [line["text_fr"] for line in first.reply_lines]
    assert said[0] == "Un touriste ? Ici ?"
    assert said[-1].startswith("Pardon ?") and said[-1].endswith("?")
    _record(history, "Je suis touriste.", first)
    second = _say(scenario, "Il pleut.", history, 0)
    assert second.route["reply"] != ASK_AGAIN and second.turn_consumed is True


def test_a_card_tap_plays_the_page_as_written(reading):
    scenario = _scenario(_page())
    turn = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"][0]
    turn["choice"] = True
    label = str(turn["replies"][0]["id"])
    reading.choice = ReplyChoice(reply_id="a", ack_fr="Ne devrait jamais être lu.")
    evaluation = _say(scenario, label, [], 0)
    assert "jamais" not in evaluation.character_reply_fr


def test_generic_ask_again_needs_a_question():
    turn = {"id": "x", "to": "lila_bonnet", "panel": {"lines": [{"who": "lila_bonnet", "kind": "speech", "text_fr": "Bon."}]}}
    assert generic_ask_again_panel(turn) is None
    turn["panel"]["lines"].append({"who": "lila_bonnet", "kind": "speech", "text_fr": "Tu restes ?", "text_native": "Bleibst du?"})
    panel = generic_ask_again_panel(turn)
    assert panel["lines"][0]["text_fr"] == "Pardon ? Tu restes ?"
    assert panel["lines"][0]["text_native"] == "Bleibst du?"


def test_the_classifier_sees_register_band_and_each_reaction():
    turn = projected_turns(_page())[0]
    payload = classifier_payload(turn, "Bonjour", [], band="a2")
    assert payload["scene"]["address"] == "vous" == turn_address(turn)
    assert payload["scene"]["band"] == "a2"
    assert all("reaction" in reply for reply in payload["replies"])
    assert any(reply["reaction"] for reply in payload["replies"])


def test_a_question_back_is_asked_again_on_every_authored_page(offline_matcher):
    """The walkthrough's day 2: «Qui êtes-vous ? Je ne connais pas Odile.» played
    Camille's «"Pas encore" ?» — words the learner never wrote. Read by the matcher,
    a reply that expresses no route is asked again on every page's first turn."""

    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day

    season = load_season("s1")
    checked = 0
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            page = resolve_day(season, tentpole.id, day.day, flags=effective_flags(season, {}, seed="x"), band="A2", language="en")
            if page is None:
                continue
            scenario = _scenario(page)
            turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
            if not turns:
                continue
            turn = turns[0]
            scenario.character_id = turn.get("to") or scenario.character_id
            if turn.get("from_solve") or ((turn.get("gate") or turn.get("convince")) and not turn.get("ask_again")):
                continue
            if not turn.get("ask_again") and generic_ask_again_panel(turn) is None:
                continue
            evaluation = _say(scenario, "Qui êtes-vous ? Je ne connais pas cette personne.", [], 0)
            # Either an authored route heard it (T1's Gus has a reply for «who are
            # you?»), or the scene asks again — never the fallback in its place.
            heard = evaluation.outcome is TaskOutcome.MET
            assert heard or evaluation.route["reply"] == ASK_AGAIN, (
                tentpole.id, day.day, turn.get("id"), evaluation.character_reply_fr
            )
            checked += 1
    assert checked >= 8


@pytest.fixture
def offline_matcher(monkeypatch):
    real = runtime.classify

    def classify(db, user, **kwargs):
        kwargs["use_model"] = False
        return real(db, user, **kwargs)

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    yield


def test_a_question_back_on_a_posed_solve_is_asked_again_not_quoted(offline_matcher):
    """Walk #78: «Qui êtes-vous ? Je ne connais pas Odile.» to Lila's «Tu me prêtes
    une clé ?» played the fallback «"Pas encore" ?» — words the learner never wrote."""

    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day

    season = load_season("s1")
    page = resolve_day(season, "t2", "b", flags=effective_flags(season, {}, seed="x"), band="A2", language="de")
    scenario = _scenario(page)
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    index = next(i for i, turn in enumerate(turns) if turn["id"].startswith("b.key"))
    turn = turns[index]
    scenario.character_id = turn.get("to") or scenario.character_id
    history: list[dict] = []
    for exchange in range(index):
        evaluation = _say(scenario, str(turns[exchange]["replies"][0]["examples"][0]), history, exchange)
        _record(history, str(turns[exchange]["replies"][0]["examples"][0]), evaluation)
    evaluation = _say(scenario, "Qui êtes-vous ? Je ne connais pas Odile.", history, index)
    assert evaluation.route == {"turn": turn["id"], "reply": ASK_AGAIN}, evaluation.character_reply_fr
    assert "Pas encore" not in evaluation.character_reply_fr
    assert {card["id"] for card in evaluation.next_choices} == {"double", "pas_encore"}, "the cards stay"
