"""Night shift #558 (child of #145): a scene closes from where it stopped, and the
line to say aloud is a whole, corrected sentence of the scene.

Live walk 6 Nov 2026, T4 day B at Le Mistral (Gus, Margaux, Odile). The learner's last
reply to Margaux was «Oui, un peu. Tu as menti pendant trois ans a ma grand-mere. Mais
je veux comprendre pourquoi tu as fait ca.» Margaux answered; then the page played its
authored tail: Gus «Quarante-deux euros. Et un ticket de métro.», Marin «C'est un bon
ticket. Il est neuf !», Lila «Elle te donne l'appartement… et le feu avec.» Marin and
Lila were not in the room, and none of it follows the conversation. «One line to say
aloud» then offered «Un peu. Tu dois dire.»: the routed reply's A1 example, a fragment.
Seen again 8 Nov (the learner's own sentence, mistakes kept) and 10 Nov («Non, reste
avec moi.», a sentence the learner did not write).

The mechanisms:

1. the closing beats were the page's tail, the movements after the page's *last* turn,
   whatever turn the conversation closed on. When the day's rhythm closes the reply
   before Romy's question and Lila's «choix», the epilogue of that choice played, with
   its own cast, after Margaux's answer;
2. the line to repeat was the routed reply's authored example, never checked to be a
   whole sentence nor to be what the learner said.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import spoken_reply
from app.services.season import runtime
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.season.runtime import (
    SEASON_CONTEXT_KEY,
    evaluate_tentpole_turn,
    page_tail,
    projected_turns,
)
from app.services.sentence_line import sentences

FIRST = "Non, je ne suis pas en colère. Je comprends."
LAST_REPLY = (
    "Oui, un peu. Tu as menti pendant trois ans a ma grand-mere. Mais je veux comprendre pourquoi tu as fait ca."
)


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


def _le_mistral():
    """T4 day B as the walk had it: the letter trusted to Margaux, at A1."""

    season = load_season("s1")
    flags = effective_flags(season, {"s1.letter_trusted_to": "margaux"}, seed="x")
    page = resolve_day(season, "t4", "b", flags=flags, band="A1", language="en")
    turns = projected_turns(page)
    scenario = SimpleNamespace(
        story_context={
            "scene_id": "walk-558",
            SEASON_CONTEXT_KEY: {
                "id": "s1",
                "kind": "tentpole",
                "page": page,
                "turns": turns,
                "tail": page_tail(page),
                "ending": {},
                "position": {"key": "t4:b"},
            },
        },
        character_id="augustin_de_roncourt",
        title_fr=page["title_fr"],
    )
    return scenario, turns


def _say(scenario, text, history, turn_index, planned):
    evaluation = evaluate_tentpole_turn(
        None,
        user=None,
        scenario=scenario,
        task=SimpleNamespace(max_turns=planned),
        answer=SimpleNamespace(text=text, is_blank=False),
        turn_index=turn_index,
        assistance="none",
        history=history,
    )
    history.append(
        {
            "learner": text,
            "character": evaluation.character_reply_fr,
            "free": bool(evaluation.needs_repair and not evaluation.turn_consumed),
            **({"route": dict(evaluation.route)} if evaluation.route else {}),
        }
    )
    return evaluation


def _in_the_room(turns, reached):
    """Everyone the conversation has shown, up to the turn it closed on: who is framed in
    each question and its lead-in, and who speaks in the replies it played."""

    people: set[str] = set()

    def visit(panel):
        people.update(str(who) for who in panel.get("in_frame") or [])
        people.update(str(line.get("who")) for line in panel.get("lines") or [] if line.get("kind") == "speech")

    for turn in turns[: reached + 1]:
        for panel in [*(turn.get("lead_in") or []), turn.get("panel") or {}]:
            visit(panel)
        for reply in turn.get("replies") or []:
            for panel in reply.get("beats") or []:
                visit(panel)
        for panel in turn.get("after") or []:
            visit(panel)
    return people


def test_early_close_cast(offline):
    """Closed on Margaux's turn: no epilogue of the questions it did not reach."""

    scenario, turns = _le_mistral()
    assert [turn["id"] for turn in turns] == ["b.turn1", "b.turn2", "b.turn3r", "b.choix"]
    history: list[dict] = []
    _say(scenario, FIRST, history, 0, planned=2)
    closing = _say(scenario, LAST_REPLY, history, 1, planned=2)
    assert closing.needs_repair is False, "the day's rhythm closes the reply on Margaux's turn"

    speakers = [line["speaker_id"] for line in closing.reply_lines]
    room = _in_the_room(turns, reached=1)
    strangers = sorted({who for who in speakers if who not in room})
    assert not strangers, f"{strangers} speak in a scene they are not in: {speakers}"
    said = closing.character_reply_fr
    assert "Quarante-deux euros" not in said and "ticket" not in said, said
    # What does play answers the last exchange: Margaux's own reaction to «un peu».
    assert speakers == ["margaux_barman"], speakers


def test_full_close_tail(offline):
    """A conversation that reaches the last question still plays the page's ending."""

    scenario, turns = _le_mistral()
    history: list[dict] = []
    _say(scenario, FIRST, history, 0, planned=6)
    _say(scenario, LAST_REPLY, history, 1, planned=6)
    _say(scenario, str(turns[2]["replies"][0]["examples"][0]), history, 2, planned=6)
    label = str(turns[3]["replies"][0]["examples"][0])
    closing = _say(scenario, label, history, 3, planned=6)
    assert closing.needs_repair is False
    assert "Quarante-deux euros" in closing.character_reply_fr


def test_say_aloud_whole(offline):
    """The line to say aloud is a whole, corrected sentence of the learner's reply."""

    scenario, _turns = _le_mistral()
    history: list[dict] = []
    _say(scenario, FIRST, history, 0, planned=2)
    _say(scenario, LAST_REPLY, history, 1, planned=2)
    correction = SimpleNamespace(span_fr="a ma grand-mere", corrected_fr="à ma grand-mère")
    history[-1]["correction"] = {"span_fr": correction.span_fr, "corrected_fr": correction.corrected_fr}
    step = SimpleNamespace(private_task={"turns": history, "response_task": {"suggested_response_fr": "Oui, un peu."}})

    line = spoken_reply.repeat_line_for(step, correction)

    assert line != "Un peu. Tu dois dire.", "the routed reply's fragment is not a sentence to repeat"
    assert line == "Tu as menti pendant trois ans à ma grand-mère.", line
    assert all(len(part.split()) >= 3 for part in sentences(line)), line


def _routed_step(said: str, say_fr: str):
    return SimpleNamespace(
        private_task={
            "turns": [{"learner": said, "character": "…", "route": {"turn": "b.turn2", "reply": "a_little", "say_fr": say_fr}}],
            "response_task": {},
        }
    )


def test_no_fragment(offline):
    """«Oui, un peu.» holds no whole sentence; the route's «Un peu. Tu dois dire.» is
    not one either: no line rather than a fragment."""

    assert spoken_reply.repeat_line_for(_routed_step("Oui, un peu.", "Un peu. Tu dois dire.")) is None
    # A whole route example says something the learner did not («Oui.» is not «il
    # fallait le dire»): no line either (review of #673).
    assert spoken_reply.repeat_line_for(_routed_step("Oui.", "Un peu, il fallait le dire.")) is None


def test_missed_slip(offline):
    """8 Nov: the margin flagged only «lappartement»; the line kept «a ma grand-mere»."""

    said = "Je pense a ma grand-mere parce que lappartement…"
    step = SimpleNamespace(
        private_task={
            "turns": [{"learner": said, "character": "…", "route": {"turn": "b.turn2", "reply": "a", "say_fr": "Je pense à elle."}}],
            "response_task": {},
        }
    )
    line = spoken_reply.repeat_line_for(step, SimpleNamespace(span_fr="lappartement", corrected_fr="l'appartement"))
    assert line == "Je pense à ma grand-mère parce que l'appartement…", line


def test_own_words(offline):
    """10 Nov: «Non, reste avec moi.» was offered for a reply the learner never wrote."""

    said = "Reste à la table, Gus. Je dois lire la lettre de ma grand-mère…"
    step = SimpleNamespace(
        private_task={
            "turns": [{"learner": said, "character": "…", "route": {"turn": "a.t", "reply": "stay", "say_fr": "Non, reste avec moi."}}],
            "response_task": {},
        }
    )
    assert spoken_reply.repeat_line_for(step) == "Reste à la table, Gus."


@pytest.mark.parametrize(
    ("said", "span", "fixed", "expected"),
    [
        ("Je reste ici, tu est gentil.", "est", "es", "Je reste ici, tu es gentil."),
        ("Je pars a Paris demain.", "a", "à", "Je pars à Paris demain."),
        ("Je vais a la gare.", "a", "à", "Je vais à la gare."),
        ("Elle mange une pomme et il parle a sa mere.", "a", "à", "Elle mange une pomme et il parle à sa mère."),
    ],
)
def test_a_margin_correction_changes_a_whole_word_only(offline, said, span, fixed, expected):
    """Review of #673: the span «est» or «a» was replaced as a substring, so «reste»
    became «rese» and «pars» became «pàrs» in the line the learner repeats aloud."""

    step = _routed_step(said, "Non, reste avec moi.")
    line = spoken_reply.repeat_line_for(step, SimpleNamespace(span_fr=span, corrected_fr=fixed))
    assert line == expected, line


@pytest.mark.parametrize("said", ["Merci beaucoup Gus.", "Un peu."])
def test_a_route_example_never_speaks_for_a_reply_that_said_something_else(offline, said):
    """10 Nov: «Non, reste avec moi.» was offered after a reply that never said it."""

    assert spoken_reply.repeat_line_for(_routed_step(said, "Non, reste avec moi.")) is None


def test_the_learners_own_line_is_offered_corrected(offline):
    """11 Nov, L'escalier: the learner's own reply came back with its mistakes
    («parce que il est mouillé») as the line to repeat."""

    said = "Non, ne le garde pas ! Il est sale parce que il est mouillé."
    step = SimpleNamespace(
        private_task={
            "turns": [{"learner": said, "character": "…"}],
            "response_task": {"suggested_response_fr": "Je le garde parce qu'il est important."},
        }
    )
    line = spoken_reply.repeat_line_for(step)
    assert line is not None and "parce que il" not in line, line
    assert "parce qu'il est mouillé" in line, line


def test_the_closing_reaction_never_ends_on_a_question_the_scene_cannot_take(offline, monkeypatch):
    """#378, live walk 30 Oct: Lila answered the one reply the scene took with «« Deux »,
    oui, je le note dans ma tête. Et ce restaurant te fait peur ?», and the scene closed
    under that question: the learner could never answer it. On the exchange the
    conversation closes on, the reaction keeps what it says and drops what it asks."""

    walk_ack = "« Deux », oui, je le note dans ma tête. Et ce restaurant te fait peur ?"
    offline_classify = runtime.classify

    def classify(db, user, **kwargs):
        return offline_classify(db, user, **kwargs).model_copy(update={"ack_fr": walk_ack})

    monkeypatch.setattr(runtime, "classify", classify)
    scenario, _turns = _le_mistral()
    history: list[dict] = []
    first = _say(scenario, FIRST, history, 0, planned=2)
    # Mid-scene the question stays: the scene still takes an answer.
    assert "te fait peur ?" in first.character_reply_fr
    closing = _say(scenario, LAST_REPLY, history, 1, planned=2)
    assert closing.needs_repair is False
    said = closing.character_reply_fr
    assert "te fait peur" not in said, f"the scene closes under a question it cannot take: {said!r}"
    assert "je le note dans ma tête" in said, said
    asked = [line["text_fr"] for line in closing.reply_lines if line["text_fr"].rstrip(" »\"").endswith("?")]
    assert not asked, asked
