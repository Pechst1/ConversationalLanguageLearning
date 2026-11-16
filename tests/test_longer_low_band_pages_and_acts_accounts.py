"""Owner decisions of 16 Nov 2026 («zu kurz, nicht fesselnd»).

A. An A1 and an A2 page is one panel and one exchange longer, modestly: the words per
   line stay (``season.director.LEVEL_SHAPES``), the planner asks one exchange more and
   gives it back before the day gets longer or loses an act
   (``journey_planner.low_band_extra_exchanges``).
B. «Le soir» (Phase 2, ``ATELIER_STORY_ACTS``) is switched on first for named accounts
   only (``ATELIER_STORY_ACTS_ACCOUNTS``) while the switch stays off for everyone else,
   and every place that asks «does this day have acts» reads ``story_acts.acts_enabled_for``.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.services import journey_planner as planner
from app.services import spend_guard, story_acts, story_split
from app.services.journey_contracts import (
    MAX_PLANNED_RESPOND_TURNS,
    MAX_RESPOND_TURNS,
    MIN_SCENE_EXCHANGES,
    ActRole,
    act_roles,
)
from app.services.journey_latency import take_prefetched_scene
from app.services.season.director import LEVEL_SHAPES, level_shape
from tests import test_story_acts_night as night_support
from tests.test_story_acts_night import _learner, _page
from tests.test_wp129_practice import _day, _recalls, _respond

night = night_support.night


# ---------------------------------------------------------------------------
# A. Longer A1 and A2 pages
# ---------------------------------------------------------------------------


def test_a1_and_a2_pages_have_one_panel_and_one_exchange_more_and_the_same_lines():
    assert {band: (shape["panels"], shape["exchanges"], shape["max_words_per_line"]) for band, shape in LEVEL_SHAPES.items()} == {
        "A1": ("4-5", "2-3", 8),
        "A2": ("5-6", "3", 12),
        "B1": ("4-6", "2-3", 16),
        "B2": ("4-6", "2-3", 22),
        "C1": ("5-6", "3", 28),
    }


@pytest.mark.parametrize(("band", "panels"), [("A1", "4-5"), ("A2", "5-6"), ("B1", "4-6")])
def test_the_page_writer_is_asked_for_the_band_s_panels(band, panels):
    context = {"level": band, "season_script": {"brief": {"level": level_shape(band)}}}
    assert f"- {panels} panels." in story_split.author_system(context)


@pytest.mark.parametrize(
    ("band", "budget", "exchanges"),
    [
        # Régulier with practice at its floor: no room, the exchange is given back.
        ("A1", 600, MIN_SCENE_EXCHANGES),
        ("A2", 600, MIN_SCENE_EXCHANGES),
        ("A1", 1200, MAX_PLANNED_RESPOND_TURNS),
        ("A2", 1800, MAX_PLANNED_RESPOND_TURNS),
        ("B1", 600, MIN_SCENE_EXCHANGES),  # B1 up as before
        ("B1", 1200, MAX_RESPOND_TURNS),
    ],
)
def test_a_low_band_scene_keeps_one_exchange_more_and_practice_gives_way(band, budget, exchanges):
    plan = _day(band, budget)
    plan.validate()
    assert _respond(plan).public_prompt["max_turns"] == exchanges, plan.rationale
    assert not plan.longer_day, plan.rationale
    assert plan.budget_seconds == budget and plan.estimated_active_seconds <= budget, plan.rationale
    assert len(_recalls(plan)) >= 3, plan.rationale


def test_an_act_at_a_low_band_has_one_exchange_more_unless_it_costs_the_day_an_act():
    a2 = planner.nominal_act_brief("A2", ActRole.SOIR)
    b1 = planner.nominal_act_brief("B1", ActRole.SOIR)
    assert planner.act_turns(a2, a2.response_task, 1800) == MIN_SCENE_EXCHANGES + 1
    assert planner.act_turns(a2, a2.response_task, 1800, plain=True) == MIN_SCENE_EXCHANGES
    assert planner.act_turns(b1, b1.response_task, 1800) == MIN_SCENE_EXCHANGES
    # A slow A1 learner still gets «Le soir» on Intensif: the act keeps its three.
    slow = planner.PacingProfile(seconds_per_token=0.9, step_multiplier=1.2, observations=5)
    assert planner.acts_to_write(budget_seconds=1800, band="A1", pace=slow) == act_roles(2)
    for band in ("A1", "A2"):
        assert planner.acts_to_write(budget_seconds=1800, band=band) == act_roles(2)


# ---------------------------------------------------------------------------
# B. «Le soir» for named accounts while the switch is off
# ---------------------------------------------------------------------------


def test_a_listed_account_gets_acts_with_the_switch_off_and_nobody_else_does(db_session, night, monkeypatch):
    owner, tester = _learner(db_session), _learner(db_session)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "*")
    # As production: the journey for everyone, the acts' switch off.
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "*")
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_ACCOUNTS", f"someone@example.com, {owner.email.upper()} ")

    assert story_acts.acts_enabled_for(owner)
    assert not story_acts.acts_enabled_for(tester), "the cohort only counts with the switch on"
    assert spend_guard.acts_learner(owner) and not spend_guard.acts_learner(tester), "the caps follow"

    # The night writes the owner's «Le soir» and the morning takes it; the tester's
    # night writes the page alone.
    page = _page(db_session, owner)
    assert story_acts.roles_to_write(db_session, owner) == ["soir", "cote"]
    assert story_acts.write_act(db_session, owner, prefetch_id=str(page.id), role="soir") == "prefetched"
    assert [str(act.role) for act in story_acts.take_acts(db_session, owner, take_prefetched_scene(db_session, owner))] == ["soir"]
    other = _page(db_session, tester)
    assert story_acts.write_act(db_session, tester, prefetch_id=str(other.id), role="soir") == "skipped_disabled"
    assert night["acts"] == ["soir"]

    # By user id as well.
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_ACCOUNTS", str(tester.id))
    assert story_acts.acts_enabled_for(tester) and not story_acts.acts_enabled_for(owner)


def test_the_accounts_list_names_accounts_only(db_session, night, monkeypatch):
    user = _learner(db_session)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    for value in ("", "*", " , ", "other@example.com"):
        monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_ACCOUNTS", value)
        assert not story_acts.acts_enabled_for(user), value


def test_the_global_switch_works_as_before(db_session, night, monkeypatch):
    user = _learner(db_session)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_ACCOUNTS", "")
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "*")
    assert story_acts.acts_enabled_for(user)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "other@example.com")
    assert not story_acts.acts_enabled_for(user)
    # A listed account with the switch on: the list and the cohort both count.
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_ACCOUNTS", user.email)
    assert story_acts.acts_enabled_for(user)


def test_a_listed_account_still_needs_the_prefetch(db_session, night, monkeypatch):
    user = _learner(db_session)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_ACCOUNTS", user.email)
    assert story_acts.acts_enabled_for(user)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", False)
    assert not story_acts.acts_enabled_for(user), "the acts are written by the night's prefetch"


def test_the_blueprint_declares_the_list_for_the_dashboard_on_both_services():
    from pathlib import Path

    import yaml

    blueprint = yaml.safe_load((Path(__file__).resolve().parents[1] / "render.yaml").read_text())
    for name in ("atelier-api", "atelier-worker"):
        service = next(row for row in blueprint["services"] if row.get("name") == name)
        [entry] = [row for row in service["envVars"] if row.get("key") == "ATELIER_STORY_ACTS_ACCOUNTS"]
        assert entry == {"key": "ATELIER_STORY_ACTS_ACCOUNTS", "sync": False}, name


def _warmups(plan) -> int:
    kinds = [step.kind.value for step in plan.steps]
    return kinds[: kinds.index("scene")].count("recall")


@pytest.mark.parametrize("band", ["A1", "A2"])
def test_a_regulier_day_with_practice_at_its_floor_gives_the_exchange_back(band, monkeypatch):
    """Owner 2026-11-16 (CI on f13d7ba1): the exchange more may cost plain practice
    items only — never the budget, the rule, the desk, nor the Rappel below what a
    Léger day has. A Régulier day with practice has no such room: it is the day it
    was without the exchange."""

    plan = _day(band, 600)
    monkeypatch.setattr(planner, "LOW_BAND_EXTRA_EXCHANGES", 0)
    plain = _day(band, 600)
    plan.validate()
    assert plan.budget_seconds == 600 and plan.estimated_active_seconds <= 600
    assert [step.kind for step in plan.steps] == [step.kind for step in plain.steps]
    assert _respond(plan).public_prompt["max_turns"] == _respond(plain).public_prompt["max_turns"]
    assert _warmups(plan) > planner.rhythm_caps(300).max_warmups or _warmups(plan) == _warmups(plain)


@pytest.mark.parametrize("band", ["A1", "A2"])
def test_a_regulier_day_with_nothing_to_give_keeps_the_exchange_when_it_fits(band):
    from tests.test_wp129_practice import engine_brief

    plan = planner.plan_journey(scenario=engine_brief(level_band=band), candidates=[], budget_seconds=600)
    plain = planner._plan_journey_once(
        scenario=engine_brief(level_band=band), candidates=[], budget_seconds=600, story_extra=False
    )
    assert plan.estimated_active_seconds <= 600 and not plan.longer_day
    with_extra = planner._plan_journey_once(scenario=engine_brief(level_band=band), candidates=[], budget_seconds=600)
    expected = _respond(with_extra if with_extra.estimated_active_seconds <= 600 else plain)
    assert _respond(plan).public_prompt["max_turns"] == expected.public_prompt["max_turns"]


def test_the_exchange_is_refused_when_it_would_cost_a_step_or_the_rappel():
    plain = _day("A2", 600)
    keeps = planner._keeps_the_day
    turns = planner._first_reply_turns(plain) + 1
    # A candidate that dropped the warm-ups to Léger's or lost a non-item step fails.
    from dataclasses import replace

    respond = _respond(plain)
    longer = replace(respond, public_prompt={**respond.public_prompt, "max_turns": turns})
    steps = [longer if step is respond else step for step in plain.steps]
    assert keeps(replace(plain, steps=steps), plain, wanted=turns)
    no_warmups = [step for i, step in enumerate(steps) if not (step.kind.value == "recall" and i < 4)]
    assert not keeps(replace(plain, steps=no_warmups), plain, wanted=turns)
    over = replace(plain, steps=steps, estimated_active_seconds=601)
    assert not keeps(over, plain, wanted=turns)


def test_leger_and_b1_never_take_the_extra_exchange():
    for band in ("A1", "A2", "B1"):
        assert _day(band, 300).budget_seconds == 300
    for budget in (600, 1200, 1800):
        assert _day("B1", budget).budget_seconds == budget
