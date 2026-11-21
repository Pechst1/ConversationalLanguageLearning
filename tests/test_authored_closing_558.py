"""Walk of 6 Nov (#558): how an authored day closes, and who speaks in it.

After the learner's last reply to Margaux («Oui, un peu. Tu as menti pendant trois ans a ma
grand-mere. Mais je veux comprendre pourquoi tu as fait ca.») the thread went on with Gus
«Quarante-deux euros. Et un ticket de métro.», Marin «C'est un bon ticket. Il est neuf !» and
Lila «Elle te donne l'appartement… et le feu avec.» None of it followed the conversation, and
Marin had not been in the scene.

Those lines are the page's plot, «Later. The chairs are up» in its art, so they stay. What was
missing was the conversation's end and the sign that the page had moved on.

Owner decision of 9 Nov 2026: a page that asks only once (T4 day A) asks one more, written from
what the learner said.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services import scene_ledger
from app.services.season import closing, runtime
from app.services.season.closing import ClosingLine, SceneClosing
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.season.turns import CAPTION_SPEAKER, ReplyChoice, reaction_lines
from tests.test_season_story_qa import _record, _scenario

WALK_MARGAUX = "Oui, un peu. Tu as menti pendant trois ans a ma grand-mere. Mais je veux comprendre pourquoi tu as fait ca."
WALK_FIRE = "Le feu est en haut, chez Odile. Gus dit en bas, mais il ne sais pas. Margaux a raison."
#: A close as the model might write it. No question: the conversation is ending.
CLOSE_LINE = "Parce qu'Odile me l'a demandé. Voilà."


def _page(tentpole, day, flags=None):
    season = load_season("s1")
    return resolve_day(season, tentpole, day, flags=flags or effective_flags(season, {}, seed="x"), band="A1", language="en")


def _say(scenario, text, history, turn_index, *, max_turns=6):
    return runtime.evaluate_tentpole_turn(
        None,
        user=None,
        scenario=scenario,
        task=SimpleNamespace(max_turns=max_turns, opening_line_fr=None),
        answer=SimpleNamespace(text=text, is_blank=False),
        turn_index=turn_index,
        assistance="none",
        history=history,
    )


@pytest.fixture
def model(monkeypatch):
    """Stands in for the two calls: the reader's answer and the closer's."""

    state = SimpleNamespace(choice=None, closing=SceneClosing(), closing_calls=0, fails=False, payloads=[])

    def classify(db, user, **kwargs):
        return state.choice

    def json_call(system, payload, schema, usage, **kwargs):
        assert schema is SceneClosing
        state.closing_calls += 1
        state.payloads.append(payload)
        if state.fails:
            raise engine.StoryUnavailable("model down")
        return state.closing, None

    monkeypatch.setattr(runtime, "classify", classify)
    monkeypatch.setattr(engine, "_json_call", json_call)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    runtime._ROUTE_CACHE.clear()
    return state


def _t4b_last_reply(model):
    """The walk: T4 B, with the day planned to close on the reply to Margaux."""

    scenario = _scenario(_page("t4", "b"))
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    scenario.character_id = turns[1]["to"]
    history = [
        {
            "learner": "Oui, je savais.",
            "character": "D'accord. D'accord. Je te crois.",
            "route": {"turn": turns[0]["id"], "reply": "a"},
            "lines": [{"speaker_id": "augustin_de_roncourt", "text_fr": "D'accord."}],
        }
    ]
    model.choice = ReplyChoice(reply_id="a_little", confidence=0.8, clear=True, learner_intent="yes")
    return scenario, turns, history


def _said(evaluation):
    return [(line["speaker_id"], line["text_fr"]) for line in evaluation.reply_lines]


# ---------------------------------------------------------------------------
# The walk: the conversation ends, then the page moves on and says so
# ---------------------------------------------------------------------------


def test_the_conversation_ends_from_what_was_said_then_the_page_moves_on(model):
    scenario, _turns, history = _t4b_last_reply(model)
    model.closing = SceneClosing(lines=[ClosingLine(who="margaux_barman", text_fr=CLOSE_LINE)], learner_intent="yes")
    evaluation = _say(scenario, WALK_MARGAUX, history, 1, max_turns=2)
    said = _said(evaluation)
    close = said.index(("margaux_barman", CLOSE_LINE))
    cut = said.index((CAPTION_SPEAKER, "Plus tard. Les chaises sont sur les tables."))
    gus = said.index(("augustin_de_roncourt", "Quarante-deux euros. Et un ticket de métro."))
    marin = said.index(("marin_leveque", "C'est un bon ticket. Il est neuf !"))
    assert close < cut < gus < marin, said
    assert (CAPTION_SPEAKER, "Dans l'escalier, chez Odile.") in said
    assert evaluation.needs_repair is False
    assert evaluation.consequence is not None


def test_the_closer_is_told_what_it_ends_and_what_comes_after(model):
    scenario, _turns, history = _t4b_last_reply(model)
    _say(scenario, WALK_MARGAUX, history, 1, max_turns=2)
    payload = model.payloads[0]
    assert payload["learner_text"] == WALK_MARGAUX
    assert payload["ledger"]["last_turn"]["intent"] == "yes"
    assert payload["just_said"], "the authored reaction was played first"
    assert "Quarante-deux euros" in payload["page_goes_on"]
    room = {person["id"]: person for person in payload["in_the_room"]}
    assert "margaux_barman" in room
    assert "marin_leveque" not in room, "Marin is on the page after this, not in the conversation"
    assert room["margaux_barman"]["address"] in ("tu", "vous")


@pytest.mark.parametrize("fails", [True, False], ids=["model down", "nothing to add"])
def test_without_a_written_close_the_page_goes_on_as_authored(model, fails):
    scenario, _turns, history = _t4b_last_reply(model)
    model.fails = fails
    said = _said(_say(scenario, WALK_MARGAUX, history, 1, max_turns=2))
    assert ("marin_leveque", "C'est un bon ticket. Il est neuf !") in said
    assert (CAPTION_SPEAKER, "Plus tard. Les chaises sont sur les tables.") in said


@pytest.mark.parametrize(
    ("who", "text"),
    [
        ("marin_leveque", "C'est un bon ticket."),  # not in the room yet
        ("margaux_barman", "Tu as dit : « je vends le café »."),  # words they never wrote
        ("margaux_barman", "Le 14 juillet, je pars."),  # a date nothing in the scene holds
        ("margaux_barman", "Demande à Fernand, il sait."),  # a name nothing in the scene holds
        ("margaux_barman", "Pourquoi tu demandes ça ?"),  # the conversation is ending
        ("margaux_barman", "Vous avez raison."),  # she says «tu» here
    ],
    ids=["absent speaker", "unsaid quote", "new date", "new name", "a question", "wrong register"],
)
def test_a_close_that_does_not_hold_is_not_played(model, who, text):
    scenario, _turns, history = _t4b_last_reply(model)
    scenario.story_context[runtime.SEASON_CONTEXT_KEY]["registers"] = {"margaux_barman": "tu"}
    model.closing = SceneClosing(lines=[ClosingLine(who=who, text_fr=text)])
    said = [text_fr for _who, text_fr in _said(_say(scenario, WALK_MARGAUX, history, 1, max_turns=2))]
    assert text not in said


@pytest.mark.parametrize(
    "text",
    [
        CLOSE_LINE,
        "Un peu, oui. Je comprends.",
        "Je comprends… Mais ce n'est pas facile.",
        "Trois ans. Oui. C'est long.",
        "Ta grand-mère savait. Moi aussi.",
    ],
)
def test_a_natural_close_is_played(model, text):
    """The must-pass side: a check here must not flatten the writing."""

    scenario, _turns, history = _t4b_last_reply(model)
    scenario.story_context[runtime.SEASON_CONTEXT_KEY]["registers"] = {"margaux_barman": "tu"}
    model.closing = SceneClosing(lines=[ClosingLine(who="margaux_barman", text_fr=text)])
    assert ("margaux_barman", text) in _said(_say(scenario, WALK_MARGAUX, history, 1, max_turns=2))


def test_a_card_tap_or_a_reprise_plays_the_page_as_written(model):
    scenario, _turns, history = _t4b_last_reply(model)
    scenario.story_context[runtime.SEASON_CONTEXT_KEY]["reprise"] = {"token": "x"}
    _say(scenario, WALK_MARGAUX, history, 1, max_turns=2)
    assert model.closing_calls == 0


# ---------------------------------------------------------------------------
# Everyone after the last exchange is here, or the page says they came
# ---------------------------------------------------------------------------


def _pages():
    season = load_season("s1")
    base = effective_flags(season, {}, seed="x")
    variants = [base]
    for spec in season.flags:
        for value in spec.values if isinstance(spec.values, list) else [True, False]:
            variants.append({**base, spec.id: value})
    seen = set()
    for tentpole in season.tentpoles:
        for day in "ab":
            for flags in variants:
                page = resolve_day(season, tentpole, day, flags=flags, band="A1", language="en")
                if page is None:
                    continue
                key = (tentpole, day, tuple(panel.get("id") for panel in runtime.page_tail(page)))
                if key not in seen:
                    seen.add(key)
                    yield tentpole, day, page


def test_nobody_speaks_after_the_last_exchange_from_a_scene_they_are_not_in():
    """The guard behind the walk, on every authored page: a speaker not yet heard on the page
    comes in behind a caption, in that panel or an earlier one of the tail."""

    missing = []
    for tentpole, day, page in _pages():
        turns = runtime.projected_turns(page)
        heard = set(closing.present_in(runtime.project(page)["scene_panels"]))
        for turn in turns:
            heard |= set(closing.present_in([turn.get("panel")], turn.get("lead_in"), turn.get("after")))
            heard.add(str(turn.get("to") or ""))
            for reply in turn.get("replies") or []:
                heard |= set(closing.present_in(reply.get("beats")))
        moved = False
        for panel in closing.with_cuts("s1", page, runtime.page_tail(page)):
            lines = panel.get("lines") or []
            moved = moved or any(line.get("kind") == "caption" and line.get("cut") for line in lines)
            for line in lines:
                who = str(line.get("who") or "")
                if line.get("kind") == "speech" and who not in heard and not moved:
                    missing.append((tentpole, day, panel.get("id"), who))
    assert not missing, f"a speaker comes in with nothing to say so: {missing}"


def test_a_message_the_page_shows_is_shown():
    """T3 A: Gus's «C'est qui ?» answers a text the thread never showed."""

    page = _page("t3", "a")
    tail = closing.with_cuts("s1", page, runtime.page_tail(page))
    lines = reaction_lines(tail, addressee="augustin_de_roncourt")
    assert lines[0] == {"speaker_id": CAPTION_SPEAKER, "speaker_name": "", "text_fr": "Plus tard, le long du canal."}
    assert lines[1]["text_fr"] == "SMS : Viens demain, au bureau. Pas un mot à Gus."
    assert lines[2]["text_fr"] == "C'est qui ?"


def test_a_caption_is_never_part_of_what_anyone_says():
    page = _page("t4", "b")
    tail = closing.with_cuts("s1", page, runtime.page_tail(page))
    from app.services.season.turns import reaction_text

    assert "Plus tard" not in reaction_text(tail, addressee="margaux_barman", labelled=False)


def test_the_cuts_name_panels_that_exist():
    """A panel renamed in the season file must not silently lose its caption."""

    season = load_season("s1")
    cuts = closing._cuts("s1")
    for tentpole, days in cuts.items():
        if tentpole.startswith("_"):
            continue
        for day, panels in days.items():
            known = set()
            for _t, _d, page in _pages():
                if page.get("tentpole") == tentpole and page.get("day") == day:
                    known |= {panel.get("id") for panel in runtime.page_tail(page)}
            assert set(panels) <= known, (tentpole, day, set(panels) - known)
    assert season.id == "s1"


# ---------------------------------------------------------------------------
# A page that asks only once asks one more
# ---------------------------------------------------------------------------


LISTEN = "Et toi, tu crois Margaux ?"


def _t4a(model, *, listen=LISTEN):
    scenario = _scenario(_page("t4", "a"))
    turn = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"][0]
    scenario.character_id = turn["to"]
    model.choice = ReplyChoice(
        reply_id=str(turn["fallback"]), confidence=0.6, clear=True, ack_fr="En haut, chez Odile ?", listen_fr=listen
    )
    return scenario, turn


def test_the_page_that_asks_once_asks_one_more_from_what_was_written(model):
    scenario, turn = _t4a(model)
    evaluation = _say(scenario, WALK_FIRE, [], 0, max_turns=2)
    assert evaluation.needs_repair is True and evaluation.consequence is None
    said = _said(evaluation)
    assert said[0][1] == "En haut, chez Odile ?"
    assert said[-1] == (turn["to"], LISTEN), "the scene's question comes last"
    assert evaluation.route["reply"] == str(turn["fallback"])
    assert model.closing_calls == 0


def test_the_answer_closes_the_day_with_the_pages_route_kept(model):
    scenario, turn = _t4a(model)
    history: list[dict] = []
    first = _say(scenario, WALK_FIRE, history, 0, max_turns=2)
    _record(history, WALK_FIRE, first)
    model.closing = SceneClosing(
        lines=[ClosingLine(who=str(turn["to"]), text_fr="Bon. On verra bien.")],
        learner_intent="yes",
        learned=[],
    )
    second = _say(scenario, "Oui, je crois Margaux.", history, 1, max_turns=2)
    assert second.needs_repair is False and second.consequence is not None
    details = second.consequence.details
    assert [row["turn_id"] for row in details["season_turns"]] == [turn["id"]], "one route, the page's"
    assert details["season_turns"][0]["reply_id"] == str(turn["fallback"])
    assert details["evidence_quotes"] == [WALK_FIRE, "Oui, je crois Margaux."]
    assert (str(turn["to"]), "Bon. On verra bien.") in _said(second)
    assert second.route["reply"] == runtime.HEARD
    assert second.heard == {"intent": "yes"}
    assert model.closing_calls == 1


def test_a_gate_on_a_page_that_asks_once_keeps_what_the_first_reply_expressed(model):
    """The first reply decides a gate, and the day closes one exchange later. No page has this
    shape today (T5 A's gate takes two exchanges), so its turn is shaped for the test."""

    scenario = _scenario(_page("t5", "a"))
    season_ctx = scenario.story_context[runtime.SEASON_CONTEXT_KEY]
    turn = season_ctx["turns"][0]
    assert turn.get("gate")
    turn["replies"] = [{**reply, "repeat_once": False} for reply in turn["replies"]]
    scenario.character_id = turn["to"]
    model.choice = ReplyChoice(
        reply_id=str(turn["fallback"]), expresses="romance", confidence=0.9, clear=True, listen_fr="Et Berlin, alors ?"
    )
    history: list[dict] = []
    first = _say(scenario, "Je reste pour toi.", history, 0, max_turns=2)
    _record(history, "Je reste pour toi.", first)
    second = _say(scenario, "Je ne sais pas.", history, 1, max_turns=2)
    assert second.consequence.details["season_turns"][0]["signal"] == "romance"


@pytest.mark.parametrize(
    "listen",
    [
        None,  # the reader had nothing to ask
        "Tu as raison.",  # not a question
        "Tu dis : « je vends le café » ?",  # words they never wrote
    ],
    ids=["nothing", "not a question", "unsaid quote"],
)
def test_without_a_question_that_holds_the_page_closes_on_this_reply(model, listen):
    scenario, _turn = _t4a(model, listen=listen)
    evaluation = _say(scenario, WALK_FIRE, [], 0, max_turns=2)
    assert evaluation.needs_repair is False and evaluation.consequence is not None


def test_a_day_planned_before_this_keeps_its_one_exchange(model):
    scenario, _turn = _t4a(model)
    evaluation = _say(scenario, WALK_FIRE, [], 0, max_turns=1)
    assert evaluation.needs_repair is False and evaluation.consequence is not None


@pytest.mark.parametrize(("tentpole", "day"), [("t3", "a"), ("t4", "a"), ("t7", "b"), ("t8", "a")])
def test_the_pages_that_ask_only_once(tentpole, day):
    assert runtime.asks_only_once(runtime.projected_turns(_page(tentpole, day)))


@pytest.mark.parametrize(("tentpole", "day"), [("t1", "a"), ("t4", "b"), ("t5", "a"), ("t7", "a")])
def test_a_page_with_more_to_ask_gets_nothing_extra(tentpole, day):
    assert not runtime.asks_only_once(runtime.projected_turns(_page(tentpole, day)))


def test_the_reader_is_told_only_on_such_a_page():
    from app.services.season.turns import classifier_payload

    _, turn = None, runtime.projected_turns(_page("t4", "a"))[0]
    ledger = scene_ledger.build(opening_line_fr="Le feu ?", history=[], learner_text=WALK_FIRE)
    assert classifier_payload(turn, WALK_FIRE, [], ledger=ledger, one_exchange=True)["scene"]["one_exchange"] is True
    assert "one_exchange" not in classifier_payload(turn, WALK_FIRE, [], ledger=ledger)["scene"]
