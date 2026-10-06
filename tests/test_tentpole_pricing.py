"""Tentpole pricing (2026-10-06) — an authored page is priced from its own text.

The walk's day 27 (T4 day B «Le silence de Margaux», A1 Régulier) planned 530 s
and was read in 1,175 s: the four exchanges were priced with a twelve-word
answer each while Margaux's first answer is 101 words, the ending caption
(31 words) as ten seconds, and the page review as its line alone.

* Every authored exchange is priced from the page: the reaction the learner
  reads (the replies' beats, their mean), the turn's ``after``, the next
  question and its lead-in — and, on the exchange the conversation closes on,
  the page's tail instead. The runtime closes the conversation at the plan's
  ``max_turns`` (``season.runtime.evaluate_tentpole_turn``), so the plan prices
  exactly the exchanges the learner is asked.
* The resolution is the page's own «À suivre…» caption and its translation.
* An honest core that exceeds the rhythm is a flagged longer day (WP-128) —
  never a cut page.
* A generated (non-authored) A1/A2 day keeps WP-129's two-exchange core.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.services import journey_planner as planner
from app.services.journey_contracts import DayShape, StepKind
from app.services.journey_day_shapes import DayShapeInputs
from app.services.season import runtime
from app.services.season.clock import Position
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.world import season_world_bible
from tests.test_journey_planner import _candidate
from tests.wp93_briefs import engine_brief

DICE = DayShapeInputs(user_id="tentpole", local_date=date(2026, 10, 6))


def tentpole(segment: str = "t4", day: int = 2, band: str = "A1", language: str = "de"):
    """The real authored brief ``season.runtime.tentpole_brief`` builds — no DB."""

    season = load_season("s1")
    seg = next(s for s in season.segments if s.id == segment)
    pos = Position(
        season_id="s1", segment=seg, segment_index=season.segments.index(seg),
        day_in_segment=day, season_day=10,
    )
    today = runtime.Today(
        season=season, pos=pos, state={"id": "s1"},
        flags=effective_flags(season, {"id": "s1"}, seed="tp"),
        seed="tp", band=band, language=language, local_date=DICE.local_date,
    )
    world = season_world_bible("s1")
    context = {
        "world": {**world, "locations": world["setting"]["recurring_locations"]},
        "level": band, "thread_id": "tentpole", "control_language": language,
    }
    brief = runtime.tentpole_brief(today, context)
    assert brief is not None
    return brief


def _words() -> list:
    words = [("la clé", "the key"), ("la chaise", "the chair"), ("la poche", "the pocket"),
             ("le sac", "the bag"), ("le parapluie", "the umbrella"), ("la pluie", "the rain")]
    return [
        _candidate(identifier=f"w{index}", label_fr=fr, label_native=native, priority=20 - index)
        for index, (fr, native) in enumerate(words)
    ]


def _plan(scenario, budget: int = 600):
    return planner.plan_journey(
        scenario=scenario, candidates=_words(), budget_seconds=budget, practice=True,
        dice=DICE, day_shape=DayShape.STANDARD,
    )


def _step(plan, kind: StepKind):
    return next(step for step in plan.steps if step.kind is kind)


# ---------------------------------------------------------------------------
# 1. An authored exchange is priced from what the page says
# ---------------------------------------------------------------------------


def test_each_exchange_carries_the_lines_the_learner_reads_after_it() -> None:
    brief = tentpole()
    exchanges = planner.authored_turns(brief)
    assert [turn.kind for turn in exchanges] == ["reply", "reply", "reply", "card"]
    # Margaux tells the night of the fire after the first reply: about a hundred words.
    assert exchanges[0].going_on >= 90
    # The last exchange is followed by the page's tail, never by a next question.
    assert exchanges[-1].going_on == 0 and exchanges[-1].closing > 0


def test_a_long_reaction_costs_its_reading_at_the_bands_prose_pace() -> None:
    task = engine_brief().response_task
    short = [planner.AuthoredExchange("reply", 5, going_on=10, closing=10)] * 3
    long = [planner.AuthoredExchange("reply", 5, going_on=110, closing=10), *short[1:]]
    kwargs = {"turns": 3, "spt": 0.75, "multiplier": 1.0, "band": "A1"}
    extra = planner.respond_seconds(task, authored=long, **kwargs) - planner.respond_seconds(
        task, authored=short, **kwargs
    )
    # 100 more words at A1: 0.75 s × the page factor 2.0 = 150 s.
    assert extra == pytest.approx(100 * 0.75 * planner.page_reading_factor("A1"), abs=1)


def test_the_exchange_the_conversation_closes_on_reads_the_tail_not_the_next_question() -> None:
    task = engine_brief().response_task
    authored = [
        planner.AuthoredExchange("reply", 5, going_on=10, closing=10),
        planner.AuthoredExchange("reply", 5, going_on=200, closing=20),
        planner.AuthoredExchange("reply", 5, going_on=10, closing=10),
    ]
    kwargs = {"spt": 0.75, "multiplier": 1.0, "band": "A1", "authored": authored}
    # Two planned exchanges: the second closes the conversation (season.runtime),
    # so it reads its reaction and the tail (20 words), not 200.
    two = planner.respond_seconds(task, turns=2, **kwargs)
    three = planner.respond_seconds(task, turns=3, **kwargs)
    assert three - two > 150


def test_a_bare_kind_and_words_pair_keeps_the_old_twelve_word_answer() -> None:
    task = engine_brief().response_task
    kwargs = {"turns": 2, "spt": 0.75, "multiplier": 1.0, "band": "A1"}
    assert planner.respond_seconds(task, authored=[("reply", 5), ("card", 6)], **kwargs) == (
        planner.respond_seconds(
            task, authored=[planner.AuthoredExchange("reply", 5), planner.AuthoredExchange("card", 6)],
            **kwargs,
        )
    )


def test_the_ending_is_priced_from_the_pages_own_caption() -> None:
    brief = tentpole()
    caption, summary = planner.authored_ending(brief)
    assert "À suivre" in caption and summary
    outcome = planner.default_outcome_key(brief)
    seconds = planner.resolution_seconds(brief, outcome, spt=0.75, multiplier=1.0)
    # 31 words at A1 prose pace + 29 native words + closing: the Timer read 55 s.
    assert 45 <= seconds <= 75, seconds
    # A generated day keeps its own ending's price.
    generated = engine_brief(level_band="A1")
    assert planner.authored_ending(generated) is None


def test_the_respond_step_prices_every_answer_of_t4_day_b() -> None:
    brief = tentpole()
    plan = _plan(brief)
    respond = _step(plan, StepKind.RESPOND)
    # The page's whole conversation is the core: its last turn is «Le choix».
    assert respond.public_prompt["max_turns"] == 4
    # The walk's Timer read the four exchanges in 530–880 s (average learner);
    # the old estimate was 327–386 s.
    assert respond.estimated_seconds >= 480, respond.estimated_seconds


# ---------------------------------------------------------------------------
# 2. An honest core past the rhythm is a flagged longer day, never cut
# ---------------------------------------------------------------------------


def test_t4_day_b_at_a1_regulier_is_a_flagged_longer_day_with_its_whole_page() -> None:
    plan = _plan(tentpole(band="A1"))
    plan.validate()
    assert plan.longer_day, plan.rationale
    assert plan.core_seconds() > plan.budget_seconds
    assert _step(plan, StepKind.RESPOND).public_prompt["max_turns"] == 4
    # The longer estimate is the one surfaces print before Start.
    assert planner.story_alone_seconds(tentpole(band="A1")) > 600


@pytest.mark.parametrize("band", ["A1", "A2", "B1", "B2", "C1"])
@pytest.mark.parametrize("key", ["t1.a", "t1.b", "t2.b", "t3.b", "t4.a", "t4.b", "t6.b", "t8.b"])
def test_every_tentpole_fits_or_is_flagged(band: str, key: str) -> None:
    segment, day = key.split(".")
    plan = _plan(tentpole(segment, 1 if day == "a" else 2, band=band, language="de" if band < "B" else "en"))
    plan.validate()
    assert plan.longer_day or plan.core_seconds() <= plan.budget_seconds, (key, band)


# ---------------------------------------------------------------------------
# 3. WP-129's owner decision is untouched on a generated A1/A2 day
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["A1", "A2"])
def test_a_generated_a1_a2_regulier_day_keeps_its_two_exchange_core(band: str) -> None:
    scenario = engine_brief(level_band=band)
    assert planner.authored_turns(scenario) == []
    plan = _plan(scenario)
    assert _step(plan, StepKind.RESPOND).public_prompt["max_turns"] == 2
    assert not plan.longer_day
    assert sum(1 for step in plan.steps if step.kind is StepKind.RECALL) >= 6


def test_an_authored_minimum_is_still_never_cut_below_its_routing_turn() -> None:
    brief = tentpole(band="A2")
    assert brief.response_task.min_turns == 4
    capped = replace(brief, response_task=replace(brief.response_task, max_turns=6))
    plan = _plan(capped)
    assert _step(plan, StepKind.RESPOND).public_prompt["max_turns"] >= 4
