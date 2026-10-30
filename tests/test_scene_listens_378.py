"""#378 / #145: the daily scene listens (owner decision 2026-10-30, «Kern zuerst»).

The live walk of 30 Oct (Nº 17, A1.1, real model) took one reply. Lila answered it
with «Et ce restaurant te fait peur ?» and the scene closed under the question;
the «To be continued» line quoted «Je serai chez moi après quatorze heures.», a
sentence nobody said. What these tests pin, with no model call:

* a generated scene plans at least ``MIN_SCENE_EXCHANGES`` exchanges from
  Régulier up (``LEGER_SCENE_EXCHANGES`` on Léger, never one), the first day and a
  day with a new rule included;
* the scene ledger records what was asked and what was answered;
* a reply that still asks keeps the scene open, at most ``SCENE_QUESTION_GRACE``
  exchanges past the plan;
* the scene's last line never ends on a question;
* a tomorrow-hook quotes only the learner's own words.

The full respond flow (the golden transcript of the walk) is in
tests/test_story_exchanges.py.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.services import living_story as engine
from app.services import scene_ledger
from app.services.journey_contracts import (
    LEGER_SCENE_EXCHANGES,
    MIN_SCENE_EXCHANGES,
    RHYTHM_BUDGETS,
    SCENE_QUESTION_GRACE,
    StepKind,
)
from app.services.journey_planner import plan_journey, scene_exchange_floor
from tests.test_journey_planner import SCENE_FITTING, _brief, _response_task

OPENING = "Tu vas dire quoi pour ta date et ton retour ?"
LEARNER = "Je veux retourner le deux decembre, parce que je suis fatigue de Berlin."
LILA = "« Deux », oui, je le note dans ma tête. Et ce restaurant te fait peur ?"


def _generated(**overrides):
    """A story-engine scene: its brief carries the draft the engine wrote."""

    return _brief(
        **{
            "story_context": {"draft": {"panels": [], "opening_line_fr": OPENING}},
            "response_task": _response_task(max_turns=4, opening_line_fr=OPENING),
            **overrides,
        }
    )


# ---------------------------------------------------------------------------
# At least three exchanges
# ---------------------------------------------------------------------------


def _respond(plan):
    return next(step for step in plan.steps if step.kind is StepKind.RESPOND)


def _floor(budget):
    return LEGER_SCENE_EXCHANGES if budget <= 300 else MIN_SCENE_EXCHANGES


@pytest.mark.parametrize("budget", RHYTHM_BUDGETS)
def test_a_generated_scene_has_three_exchanges_from_regulier_up(budget):
    plan = plan_journey(scenario=_generated(), candidates=[SCENE_FITTING], budget_seconds=budget)
    assert _respond(plan).public_prompt["max_turns"] >= _floor(budget)


@pytest.mark.parametrize("band", ["A1", "A2", "B1", "B2"])
@pytest.mark.parametrize("budget", RHYTHM_BUDGETS)
def test_a_practice_day_keeps_its_exchanges_at_every_band(budget, band):
    plan = plan_journey(
        scenario=_generated(level_band=band), candidates=[SCENE_FITTING], budget_seconds=budget, practice=True
    )
    assert _respond(plan).public_prompt["max_turns"] >= _floor(budget)


@pytest.mark.parametrize("budget", [300, 600])
def test_the_first_day_of_a_generated_scene_keeps_its_exchanges(budget):
    plan = plan_journey(
        scenario=_generated(), candidates=[SCENE_FITTING], first_day=True, budget_seconds=budget
    )
    assert _respond(plan).public_prompt["max_turns"] >= _floor(budget)


def test_an_authored_scene_keeps_its_own_count():
    authored = _brief()
    assert scene_exchange_floor(authored, authored.response_task) == 1
    assert scene_exchange_floor(_generated(), _generated().response_task) == MIN_SCENE_EXCHANGES
    assert scene_exchange_floor(_generated(), _generated().response_task, 300) == LEGER_SCENE_EXCHANGES
    choice = _generated(response_task=_response_task(max_turns=4, min_turns=4))
    assert scene_exchange_floor(choice, choice.response_task) == 4


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


def test_the_ledger_of_the_walk():
    """The walk's one exchange: the opening question is answered by the learner,
    Lila's question is open, the learner asked nothing."""

    ledger = scene_ledger.build(
        opening_line_fr=OPENING, history=[{"learner": LEARNER, "character": LILA}]
    )
    assert ledger["exchanges"] == 1
    assert [(row["by"], row["text_fr"], row["at"], row["answered_at"]) for row in ledger["asked"]] == [
        ("character", OPENING, 0, 0),
        ("character", "Et ce restaurant te fait peur ?", 1, None),
    ]
    assert ledger["open_for_learner"] == "Et ce restaurant te fait peur ?"
    assert ledger["learner_asked"] is None

    answered = scene_ledger.build(
        opening_line_fr=OPENING,
        history=[{"learner": LEARNER, "character": LILA}],
        learner_text="Non, il ne me fait pas peur.",
    )
    assert answered["open_for_learner"] is None
    assert answered["asked"][-1]["answered_at"] == 1


def test_the_learners_question_is_open_until_the_character_replies():
    ledger = scene_ledger.build(
        opening_line_fr=OPENING, history=[], learner_text="Le deux décembre. Tu as un chat ?"
    )
    assert ledger["learner_asked"] == "Tu as un chat ?"
    # Learners drop the «?»: a sentence that opens like a question still asks.
    assert scene_ledger.learner_question("pourquoi tu restes a Paris") == "pourquoi tu restes a Paris"
    assert scene_ledger.learner_question("Je reste à Paris.") is None
    replied = scene_ledger.build(
        opening_line_fr=OPENING,
        history=[{"learner": "Tu as un chat ?", "character": "Oui, il s'appelle Pablo."}],
    )
    assert replied["learner_asked"] is None
    assert replied["asked"][-1] == {"by": "learner", "text_fr": "Tu as un chat ?", "at": 0, "answered_at": 0}


def test_the_plan_keeps_talking_until_its_last_exchange():
    task = _response_task(max_turns=3, opening_line_fr=OPENING)
    assert engine.keeps_talking(task, 0) is True
    assert engine.keeps_talking(task, 2) is False


# ---------------------------------------------------------------------------
# The scene ends only once its question is answered
# ---------------------------------------------------------------------------


def test_a_reply_that_asks_keeps_the_scene_open_within_the_grace():
    task = replace(_response_task(), max_turns=1)
    # The walk: one planned exchange, Lila asks → open.
    assert engine.keeps_talking(task, 0, reply_fr=LILA) is True
    assert engine.keeps_talking(task, 0, reply_fr="D'accord, je note.") is False
    assert engine.keeps_talking(task, 0) is False, "before the reply, the plan decides"
    last = task.max_turns + SCENE_QUESTION_GRACE - 1
    assert engine.keeps_talking(task, last - 1, reply_fr=LILA) is True
    assert engine.keeps_talking(task, last, reply_fr=LILA) is False, "the grace has an end"
    # The app's wording question takes the turn instead (WP-36).
    assert engine.keeps_talking(task, 0, reply_fr=LILA, self_repair=object()) is False


def test_a_question_inside_a_reply_still_asks():
    assert scene_ledger.character_question("Tu as peur ? Moi aussi, un peu.") == "Tu as peur ?"
    assert scene_ledger.character_question("Je note. « On y va ? »") == "« On y va ? »"
    assert scene_ledger.character_question("D'accord. On y va.") is None


def test_the_last_line_never_ends_on_a_question():
    assert scene_ledger.without_trailing_question("D'accord. On ira au café. Tu viens ?") == (
        "D'accord. On ira au café."
    )
    assert scene_ledger.without_trailing_question("Tu viens ?") == "Tu viens ?"
    assert scene_ledger.without_trailing_question("Bon. À demain.") == "Bon. À demain."


# ---------------------------------------------------------------------------
# The hook quotes only what was said
# ---------------------------------------------------------------------------


def _live(**commitment):
    return {
        "commitments": [{"id": "e1:commitment:0", "status": "open", "witnesses": ["lila_bonnet"], **commitment}],
        "planted": [{"id": "e2:plant", "text_fr": "La vieille clé bleue du compteur.", "status": "open",
                     "character_id": "lila_bonnet"}],
    }


def test_a_promise_is_quoted_in_the_learners_own_words():
    live = _live(text_fr="Je serai chez moi après quatorze heures.", source_quote="Je rentre après deux heures.")
    candidates = engine.teaser_candidates(live, {})
    promise = next(row for row in candidates if row["kind"] == "commitment")
    assert promise["text_fr"] == "Je rentre après deux heures."
    text = engine.compose_teaser(promise, character_id="lila_bonnet", register="tu")
    assert "« Je rentre après deux heures. »" in text
    assert "quatorze" not in text


def test_the_walks_hook_is_not_written():
    """The 30 Oct hook: a model restatement with no words of the learner's behind it."""

    live = _live(text_fr="Je serai chez moi après quatorze heures.")
    candidates = engine.teaser_candidates(live, {})
    assert all(row["kind"] != "commitment" for row in candidates)
    teaser = engine.next_teaser(
        live, {}, character_id="lila_bonnet", register="tu", date="2026-10-30", seed="t"
    )
    assert teaser is not None and "quatorze" not in teaser["text_fr"]


def test_a_detail_is_told_not_quoted():
    plant = next(row for row in engine.teaser_candidates(_live(), {}) if row["kind"] == "plant")
    for variant in range(2):
        text = engine.compose_teaser(plant, character_id="lila_bonnet", register="tu", variant=variant)
        assert "«" not in text and "La vieille clé bleue du compteur." in text
