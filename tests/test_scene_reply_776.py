"""Live walk of 14 Nov 2026 (#776, root cause #145): T5 day A, «Le Mistral», A1.1 day 33.

The learner wrote «Non, je ne veux pas que tu pars à Berlin. Je suis triste parce que je ai peur
de rester seul au Mistral.» The header said «Exchange 1 of 2». Lila answered with four lines,
the last two «Je comprends. Viens, tu vas voir une chose.» and «Viens. Tu vas voir une chose.»,
and the day closed: the second exchange never came.

Two flaws, one cause: nothing held the scene's reply to what the scene had already said or
was about to say.

* The plan counted exchanges the page plays only on some routes (a deflection asked again, the
  scene's own extra question when the model writes one) and showed that count as the total.
* The closer was told «do not say any of page_goes_on first», and nothing checked that it did
  not: its line said the page's next line again.
"""

from __future__ import annotations

import re
import unicodedata
from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services.journey_contracts import StepKind
from app.services.season import runtime
from app.services.season.closing import ClosingLine, SceneClosing
from app.services.season.turns import ReplyChoice
from tests.test_season_story_qa import _record
from tests.test_tentpole_pricing import _plan, _step, tentpole

WALK_REPLY = (
    "Non, je ne veux pas que tu pars à Berlin. Je suis triste parce que je ai peur de rester seul au Mistral."
)
WALK_ACK = "Tu as peur de rester seul au Mistral."
#: What the closer wrote on the walk, before the page's own «Viens. Tu vas voir une chose.».
WALK_CLOSE = "Je comprends. Viens, tu vas voir une chose."


def _words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^\w\s]", " ", folded.replace("’", "'")).split()


def _same_line(left: str, right: str) -> bool:
    """The same words up to punctuation and case, or one line said whole inside the other."""

    a, b = _words(left), _words(right)
    short, long = sorted((a, b), key=len)
    if not short:
        return False
    if a == b:
        return True
    return len(short) >= 3 and any(long[i : i + len(short)] == short for i in range(len(long) - len(short) + 1))


def _repeated_pairs(lines: list[str]) -> list[tuple[str, str]]:
    return [
        (lines[i], lines[j])
        for i in range(len(lines))
        for j in range(i + 1, len(lines))
        if _same_line(lines[i], lines[j])
    ]


@pytest.fixture
def model(monkeypatch):
    """Stands in for the reader and the closer. No paid call."""

    state = SimpleNamespace(choice=None, closing=SceneClosing(), closing_calls=0)

    def classify(db, user, **kwargs):
        return state.choice

    def json_call(system, payload, schema, usage, **kwargs):
        assert schema is SceneClosing
        state.closing_calls += 1
        return state.closing, None

    monkeypatch.setattr(runtime, "classify", classify)
    monkeypatch.setattr(engine, "_json_call", json_call)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    runtime._ROUTE_CACHE.clear()
    return state


def _planned(segment: str, day: int):
    """The day as the planner serves it: the brief, the public prompt and the private task."""

    brief = tentpole(segment, day, band="A1", language="en")
    respond = _step(_plan(brief), StepKind.RESPOND)
    return brief, respond.public_prompt, respond.private_task


def _play(brief, task, replies: list[str]) -> list:
    """Every exchange the scene plays for ``replies``, until it closes."""

    history: list[dict] = []
    played = []
    for turn_index, text in enumerate(replies):
        evaluation = runtime.evaluate_tentpole_turn(
            None,
            user=None,
            scenario=brief,
            task=SimpleNamespace(max_turns=task.max_turns, opening_line_fr=task.opening_line_fr),
            answer=SimpleNamespace(text=text, is_blank=False),
            turn_index=turn_index,
            assistance="none",
            history=history,
        )
        played.append(evaluation)
        _record(history, text, evaluation)
        if not evaluation.needs_repair:
            break
    return played


def _walk_choice() -> ReplyChoice:
    # The walk: an honest «I don't want you to go», read as the turn's «Honest want».
    return ReplyChoice(reply_id="b", confidence=0.9, clear=True, ack_fr=WALK_ACK, learner_intent="no")


# ---------------------------------------------------------------------------
# «Exchange N of M»: the total is what the scene plays
# ---------------------------------------------------------------------------


def test_the_walks_total_is_the_exchanges_the_scene_plays(model):
    brief, prompt, task = _planned("t5", 1)
    assert [turn["id"] for turn in brief.story_context["season"]["turns"]] == ["va.a.turn1"]
    model.choice = _walk_choice()
    played = _play(brief, task, [WALK_REPLY, "Je ne sais pas."])
    assert played[-1].needs_repair is False, "the walk's reply closes the day"
    assert prompt["max_turns"] <= len(played), (
        f"«Exchange 1 of {prompt['max_turns']}» on a scene that plays {len(played)} exchange(s)"
    )


def test_a_deflection_asked_again_still_plays_under_the_same_total(model):
    """The exchange the page plays only after a deflection is past the plan, never promised."""

    brief, prompt, task = _planned("t5", 1)
    model.choice = ReplyChoice(reply_id="d", confidence=0.9, clear=True)
    played = _play(brief, task, ["Et Marin ? Et le Mistral ?", "Et Marin ?"])
    assert [evaluation.needs_repair for evaluation in played] == [True, False], "asked again, once"
    assert prompt["max_turns"] <= len(played)


def test_a_page_that_asks_once_promises_no_question_the_model_may_not_write(model):
    """T4 day A: the scene's own extra question comes only when the reader writes one that
    holds. Without it the day closes on the first reply, so the total may not count it."""

    brief, prompt, task = _planned("t4", 1)
    turn = brief.story_context["season"]["turns"][0]
    model.choice = ReplyChoice(reply_id=str(turn["fallback"]), confidence=0.6, clear=True, listen_fr=None)
    played = _play(brief, task, ["Le feu est en haut, chez Odile.", "Oui."])
    assert played[-1].needs_repair is False
    assert prompt["max_turns"] <= len(played), (
        f"«Exchange 1 of {prompt['max_turns']}» on a scene that plays {len(played)} exchange(s)"
    )


def test_the_extra_question_still_gets_its_answer(model):
    """The total no longer counts it, and the scene still asks it and takes the answer."""

    brief, _prompt, task = _planned("t4", 1)
    turn = brief.story_context["season"]["turns"][0]
    model.choice = ReplyChoice(
        reply_id=str(turn["fallback"]), confidence=0.6, clear=True, listen_fr="Et toi, tu crois Margaux ?"
    )
    played = _play(brief, task, ["Le feu est en haut, chez Odile.", "Oui, je crois Margaux."])
    assert [evaluation.needs_repair for evaluation in played] == [True, False]


def test_a_page_every_route_plays_whole_keeps_its_total():
    _brief, prompt, task = _planned("t4", 2)
    assert prompt["max_turns"] == task.max_turns == 4


# ---------------------------------------------------------------------------
# A reply never says the same line twice
# ---------------------------------------------------------------------------


def test_the_walks_close_does_not_say_the_pages_next_line_first(model):
    brief, _prompt, task = _planned("t5", 1)
    model.choice = _walk_choice()
    model.closing = SceneClosing(lines=[ClosingLine(who="lila_bonnet", text_fr=WALK_CLOSE)])
    evaluation = _play(brief, task, [WALK_REPLY])[0]
    assert evaluation.needs_repair is False and model.closing_calls == 1
    said = [line["text_fr"] for line in evaluation.reply_lines if line.get("speaker_id") != "caption"]
    assert "Viens. Tu vas voir une chose." in said, "the page's own line stays, word for word"
    assert _repeated_pairs(said) == [], said


def test_a_close_that_holds_is_still_played(model):
    brief, _prompt, task = _planned("t5", 1)
    model.choice = _walk_choice()
    model.closing = SceneClosing(lines=[ClosingLine(who="lila_bonnet", text_fr="Moi aussi, j'ai peur.")])
    evaluation = _play(brief, task, [WALK_REPLY])[0]
    said = [line["text_fr"] for line in evaluation.reply_lines]
    assert "Moi aussi, j'ai peur." in said


@pytest.mark.parametrize(
    ("line", "others"),
    [
        (WALK_CLOSE, ["Viens. Tu vas voir une chose."]),
        ("Viens. Tu vas voir une chose.", [WALK_CLOSE]),
        ("D'accord, merci !", ["D'accord. Merci."]),
        ("tu as peur de rester seul au mistral", [WALK_ACK]),
    ],
)
def test_the_guard_catches_a_line_said_again_up_to_punctuation_and_case(line, others):
    from app.services.lane_guards import repeated_line

    assert repeated_line(line, others) is not None


@pytest.mark.parametrize(
    ("line", "others"),
    [
        ("Moi aussi, j'ai peur.", ["Viens. Tu vas voir une chose."]),
        ("Merci.", ["Merci, Lila. Vraiment."]),  # a short habit inside a longer line
        ("Je comprends.", [WALK_CLOSE]),
    ],
)
def test_the_guard_leaves_different_lines_alone(line, others):
    from app.services.lane_guards import repeated_line

    assert repeated_line(line, others) is None
