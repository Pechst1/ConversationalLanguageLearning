"""Phase 2 «Folge in Akten», PR 1 — the contract and the planner.

A day may play one to three acts: each act is what the whole episode is today
(the scene's page, the reply's conversation, the ending), played back to back.
The rhythm caps them (Léger and Régulier one, Soutenu two, Intensif three), the
planner prices every act with the clock it prices the rest of the day with, and
a fifth of the day stays for practice. Nothing passes acts yet — the night
writes them in the next PR, behind ``ATELIER_STORY_ACTS`` — so every day today
is a one-act day, planned exactly as before.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.services import journey_planner as planner
from app.services.daily_journey import DailyJourneyService
from app.services.journey_contracts import (
    ACT_SHAPES,
    MIN_SCENE_EXCHANGES,
    RHYTHM_BUDGETS,
    ActBrief,
    ActRole,
    DayShape,
    InputMode,
    StepKind,
    act_roles,
    act_shape,
    act_story_ceiling,
    rhythm_caps,
)
from app.services.journey_day_shapes import DayShapeInputs
from tests.test_daily_journey_state import build_adapters
from tests.test_journey_events import make_user
from tests.test_journey_planner import _candidate
from tests.test_wpl6_rhythm import _queue
from tests.wp93_briefs import engine_brief, engine_draft

DICE = DayShapeInputs(user_id="acts", local_date=date(2026, 11, 2))
STORY = (StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION)
#: Each later act has its own lead: «À côté» Margaux at the counter, «Le soir» Marin.
LEADS = {"cote": ("margaux_barman", "Margaux"), "soir": ("marin_leveque", "Marin")}
#: A page far longer than any act's shape: 60 panels, and 150 — a page that no
#: day of acts could hold even beside the first act alone.
LONG_PAGE = engine_draft()["panels"] * 12
ENDLESS_PAGE = engine_draft()["panels"] * 30


def _act(role: str, band: str = "B1", **draft: object) -> ActBrief:
    """A later act as the night writes it: its own lead, place and page."""

    character_id, name = LEADS[role]
    base = engine_brief(level_band=band, draft=engine_draft(character_id=character_id, **draft))
    task = replace(base.response_task, character_id=character_id, character_name=name)
    scenario = replace(
        base,
        scenario_key=f"engine:act-{role}",
        title_fr=f"Acte {role}",
        character_id=character_id,
        character_name=name,
        response_task=task,
    )
    return ActBrief(role=ActRole(role), scenario=scenario)


def _day(band: str, budget: int, **extra):
    return planner.plan_journey(
        scenario=extra.pop("scenario", None) or engine_brief(level_band=band),
        candidates=extra.pop("candidates", None) or _queue(rhythm_caps(budget).candidate_limit),
        budget_seconds=budget,
        practice=True,
        dice=DICE,
        day_shape=extra.pop("day_shape", DayShape.STANDARD),
        **extra,
    )


def _story(plan) -> list[int]:
    return [index for index, step in enumerate(plan.steps) if step.kind in STORY]


def _three_acts(band: str = "B1"):
    return _day(band, 1800, acts=[_act("cote", band), _act("soir", band)])


# ---------------------------------------------------------------------------
# 1. The contract
# ---------------------------------------------------------------------------


def test_the_rhythm_caps_the_acts_and_keeps_a_fifth_for_practice() -> None:
    assert [rhythm_caps(budget).max_acts for budget in RHYTHM_BUDGETS] == [1, 1, 2, 3]
    assert act_roles(1) == (ActRole.FIL,)
    assert act_roles(2) == (ActRole.FIL, ActRole.SOIR)
    assert act_roles(3) == (ActRole.FIL, ActRole.COTE, ActRole.SOIR)
    assert act_story_ceiling(1800) == 24 * 60
    assert act_story_ceiling(1200) == 16 * 60


def test_a_later_act_has_a_shorter_page() -> None:
    assert act_shape("B1", ActRole.FIL) == ACT_SHAPES["B1"]
    assert (act_shape("B1", ActRole.COTE).panels, act_shape("B1", ActRole.COTE).words) == (7, 212)
    assert (act_shape("B1", ActRole.SOIR).panels, act_shape("B1", ActRole.SOIR).words) == (6, 175)
    # Never under four panels; C2 reads as C1, an unknown band as B1.
    assert act_shape("A1", ActRole.SOIR).panels == 4
    assert act_shape("C2", ActRole.FIL) == ACT_SHAPES["C1"]
    assert act_shape(None, ActRole.FIL) == ACT_SHAPES["B1"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda plan: replace(plan, practice=False), "only a practice day plays more than one act"),
        (lambda plan: replace(plan, budget_seconds=1200), "at most 2 act(s)"),
        (lambda plan: replace(plan, longer_day=True), "a longer day plays one act"),
        (lambda plan: replace(plan, day_shape=DayShape.SHORT), "a short day plays one act"),
        (lambda plan: replace(plan, acts=list(reversed(plan.acts))), "in that order"),
        (lambda plan: replace(plan, acts=plan.acts[:1]), "in that order"),
        (lambda plan: replace(plan, acts=[]), "a later act needs its own brief"),
    ],
)
def test_a_day_of_acts_is_held_to_its_shape(mutate, message: str) -> None:
    plan = _three_acts()
    plan.validate()
    with pytest.raises(ValueError, match=message.replace("(", r"\(").replace(")", r"\)")):
        mutate(plan).validate()


def _renumbered(plan, steps):
    return replace(plan, steps=[replace(step, ordinal=index) for index, step in enumerate(steps)])


def test_nothing_sits_between_two_acts() -> None:
    plan = _three_acts()
    story = _story(plan)
    steps = list(plan.steps)
    practice = next(index for index in range(story[-1] + 1, len(steps)) if steps[index].kind is StepKind.RECALL)
    item = steps.pop(practice)
    steps.insert(story[2] + 1, item)  # straight after the first act's ending
    with pytest.raises(ValueError, match="nothing between them"):
        _renumbered(plan, steps).validate()


def test_each_act_carries_its_number_and_only_the_story_belongs_to_one() -> None:
    plan = _three_acts()
    story = _story(plan)
    steps = list(plan.steps)
    steps[story[4]] = replace(steps[story[4]], act=3)  # act 2's reply, numbered 3
    with pytest.raises(ValueError, match="carry its number"):
        _renumbered(plan, steps).validate()
    steps = list(plan.steps)
    recall = next(index for index, step in enumerate(steps) if step.kind is StepKind.RECALL)
    steps[recall] = replace(steps[recall], act=2)
    with pytest.raises(ValueError, match="only a scene, a reply or an ending"):
        _renumbered(plan, steps).validate()


def test_the_acts_never_take_more_than_four_fifths_of_the_day() -> None:
    plan = _three_acts()
    story = _story(plan)
    steps = list(plan.steps)
    spent = sum(steps[index].estimated_seconds for index in story)
    scene = steps[story[3]]
    steps[story[3]] = replace(scene, estimated_seconds=scene.estimated_seconds + act_story_ceiling(1800) - spent + 1)
    with pytest.raises(ValueError, match="the rest is practice"):
        _renumbered(plan, steps).validate()


# ---------------------------------------------------------------------------
# 2. The planner: a one-act day is today's day
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("budget", RHYTHM_BUDGETS)
@pytest.mark.parametrize("band", ["A1", "B1"])
def test_a_day_without_acts_is_planned_exactly_as_before(band: str, budget: int) -> None:
    assert _day(band, budget, acts=[]) == _day(band, budget)
    assert _day(band, budget).acts == []
    assert all(step.act == 1 for step in _day(band, budget).steps)


@pytest.mark.parametrize(
    ("budget", "shape"),
    [(300, DayShape.STANDARD), (600, DayShape.STANDARD), (1800, DayShape.SHORT)],
)
def test_acts_a_day_cannot_play_leave_it_the_one_act_day(budget: int, shape: DayShape) -> None:
    plain = _day("B1", budget, day_shape=shape)
    handed = _day("B1", budget, day_shape=shape, acts=[_act("cote"), _act("soir")])
    handed.validate()
    assert handed.acts == []
    assert [(step.kind, step.estimated_seconds, step.public_prompt) for step in handed.steps] == [
        (step.kind, step.estimated_seconds, step.public_prompt) for step in plain.steps
    ]
    assert "acts set aside" in handed.rationale


# ---------------------------------------------------------------------------
# 3. The planner: two and three acts
# ---------------------------------------------------------------------------


def test_b1_intensif_plays_three_acts_back_to_back() -> None:
    plan = _three_acts()
    plan.validate()
    assert plan.act_count == 3
    assert [act.role for act in plan.acts] == [ActRole.COTE, ActRole.SOIR]
    story = _story(plan)
    assert [plan.steps[index].kind for index in story] == list(STORY) * 3
    assert story == list(range(story[0], story[0] + 9)), "nothing between the acts"
    assert [plan.steps[index].act for index in story] == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    after = [step.kind for step in plan.steps[story[-1] + 1 :]]
    assert after and all(kind in (StepKind.RECALL, StepKind.DESK, StepKind.RULE, StepKind.READ) for kind in after)
    assert sum(plan.steps[index].estimated_seconds for index in story) <= act_story_ceiling(1800)
    assert plan.estimated_active_seconds <= 1800
    # Each act talks with its own lead; the later acts' replies ask for nothing.
    replies = [step for step in plan.steps if step.kind is StepKind.RESPOND]
    assert [reply.private_task.character_id for reply in replies] == [
        "lila_bonnet", "margaux_barman", "marin_leveque",
    ]
    assert all(reply.public_prompt["targets"] == [] for reply in replies[1:])


def test_on_a_day_of_acts_a_longer_rhythm_buys_an_act_not_a_fourth_exchange() -> None:
    one = _day("B1", 1800)
    three = _three_acts()
    turns = lambda plan: [s.public_prompt["max_turns"] for s in plan.steps if s.kind is StepKind.RESPOND]  # noqa: E731
    assert turns(one) == [4]
    assert turns(three) == [MIN_SCENE_EXCHANGES] * 3
    assert [s.private_task.max_turns for s in three.steps if s.kind is StepKind.RESPOND] == [MIN_SCENE_EXCHANGES] * 3


def test_a_later_act_shows_the_app_the_first_acts_keys_and_no_more() -> None:
    plan = _three_acts()
    for kind in STORY:
        keys = [set(step.public_prompt) for step in plan.steps if step.kind is kind]
        assert keys[1] == keys[0] and keys[2] == keys[0], kind


def test_soutenu_plays_le_soir_and_gives_up_a_cote() -> None:
    plan = _day("B1", 1200, acts=[_act("cote"), _act("soir")])
    plan.validate()
    assert [act.role for act in plan.acts] == [ActRole.SOIR]
    assert "act «cote» given up" in plan.rationale


def test_what_does_not_fit_goes_a_cote_first() -> None:
    long_cote = _day("B1", 1800, acts=[_act("cote", panels=LONG_PAGE), _act("soir")])
    assert [act.role for act in long_cote.acts] == [ActRole.SOIR]
    # «À côté» goes first even when «Le soir» is the long one.
    long_soir = _day("B1", 1800, acts=[_act("cote"), _act("soir", panels=LONG_PAGE)])
    assert [act.role for act in long_soir.acts] == [ActRole.SOIR]
    # «À côté» is never played without «Le soir», which ends on the day's hook.
    endless_soir = _day("B1", 1800, acts=[_act("cote"), _act("soir", panels=ENDLESS_PAGE)])
    assert endless_soir.acts == []
    assert _day("B1", 1800, acts=[_act("cote")]).acts == []


def test_an_act_that_cannot_end_is_set_aside() -> None:
    broken = _act("cote")
    broken = replace(
        broken,
        scenario=replace(
            broken.scenario,
            response_task=replace(broken.scenario.response_task, opening_line_fr=""),
        ),
    )
    plan = _day("B1", 1800, acts=[broken, _act("soir")])
    plan.validate()
    assert [act.role for act in plan.acts] == [ActRole.SOIR]
    assert "act «cote» set aside: response_task_has_no_opening_line" in plan.rationale


@pytest.fixture
def a_long_rule(monkeypatch):
    """Today's unit, with a card long enough (800 s) that three acts leave it no
    room and two do."""

    guided = [
        step.private_task for step in _day("B2", 1200).steps if step.kind is StepKind.RECALL
    ][:2]
    card = {"example": {"fr": "Je suis là."}, "rule": {"en": "Être: je suis, tu es."}}

    def items(brief, **kwargs):
        if not brief:
            return None, 0, []
        return card, 800, [(task, 20) for task in guided]

    monkeypatch.setattr(planner, "_introduction_items", items)
    monkeypatch.setattr(
        planner.grammar_items, "grammar_target",
        lambda brief: _candidate(kind=planner.TargetKind.GRAMMAR, identifier="1", label_fr="être").target,
    )
    monkeypatch.setattr(planner, "_rule_step", lambda ordinal, **kw: planner.PlannedStep(
        ordinal=ordinal, kind=StepKind.RULE, estimated_seconds=kw["cost"], public_prompt={"concept_id": 1},
    ))
    return {"concept_id": 1, "detectors": []}


def test_the_day_gives_up_an_act_before_its_rule(a_long_rule) -> None:
    plan = _day("B1", 1800, acts=[_act("cote"), _act("soir")], introduction=a_long_rule)
    plan.validate()
    assert StepKind.RULE in [step.kind for step in plan.steps]
    assert not plan.longer_day
    assert [act.role for act in plan.acts] == [ActRole.SOIR]
    assert "3 acts would cost the day its rule" in plan.rationale


# ---------------------------------------------------------------------------
# 4. The night: never more acts than the morning can play
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("band", "soutenu", "intensif"),
    [("A1", 1, 2), ("A2", 1, 2), ("B1", 2, 3), ("B2", 2, 3), ("C1", 2, 3)],
)
def test_the_night_writes_the_acts_the_day_can_play(band: str, soutenu: int, intensif: int) -> None:
    """The acts doc's table («Wie lang»): the conversation takes A1 and A2 so
    long that Intensif plays two acts there, three from B1."""

    assert planner.acts_to_write(budget_seconds=300, band=band) == (ActRole.FIL,)
    assert planner.acts_to_write(budget_seconds=600, band=band) == (ActRole.FIL,)
    assert planner.acts_to_write(budget_seconds=1200, band=band) == act_roles(soutenu)
    assert planner.acts_to_write(budget_seconds=1800, band=band) == act_roles(intensif)


def test_a_slow_a1_learner_gets_two_acts_on_intensif() -> None:
    slow = planner.PacingProfile(seconds_per_token=0.9, step_multiplier=1.2, observations=5)
    assert planner.acts_to_write(budget_seconds=1800, band="A1", pace=slow) == act_roles(2)
    plan = _day("A1", 1800, pace=slow, acts=[_act("cote", "A1"), _act("soir", "A1")])
    plan.validate()
    assert plan.act_count == 2


def test_a_learner_slower_still_gets_fewer_acts() -> None:
    slowest = planner.PacingProfile(seconds_per_token=0.6, step_multiplier=1.35, observations=5)
    assert planner.acts_to_write(budget_seconds=1800, band="B1", pace=slowest) == act_roles(2)
    assert planner.acts_to_write(budget_seconds=1200, band="B1", pace=slowest) == act_roles(1)
    # Two measured days are not trusted: the band's prior plans.
    untrusted = replace(slowest, observations=2)
    assert planner.acts_to_write(budget_seconds=1800, band="B1", pace=untrusted) == act_roles(3)


def test_the_night_prices_an_act_as_the_morning_will() -> None:
    """The nominal act is a generated page of the act's shape, priced by the
    planner's own functions: three exchanges, the page's words and panels."""

    for role in (ActRole.FIL, ActRole.COTE, ActRole.SOIR):
        brief = planner.nominal_act_brief("B1", role)
        shape = act_shape("B1", role)
        page = planner.scene_page(brief)
        assert len(page) == shape.panels
        assert sum(len(text.split()) for text in planner.page_texts(page)) == shape.words
        priced = planner.price_act(
            ActBrief(role=role, scenario=brief), budget_seconds=1800,
            spt=planner.reading_prior("B1"), multiplier=1.0, audio=False, band="B1",
        )
        assert priced.turns == MIN_SCENE_EXCHANGES


# ---------------------------------------------------------------------------
# 5. Persisting a day of acts
# ---------------------------------------------------------------------------


def _persisted(db: Session, plan, email: str) -> DailyJourney:
    user = make_user(db, email)
    journey = DailyJourney(id=uuid.uuid4(), user_id=user.id, local_date=date(2026, 11, 2), budget_seconds=1800)
    db.add(journey)
    db.flush()
    DailyJourneyService(db, build_adapters())._persist_plan(journey, plan.scenario, plan, InputMode.TEXT)
    return journey


def test_a_later_acts_steps_keep_their_act_and_brief(db_session: Session) -> None:
    plan = _three_acts()
    journey = _persisted(db_session, plan, "acts-persist@example.com")
    steps = sorted(journey.steps, key=lambda step: step.ordinal)
    story = [step for step in steps if step.kind in {str(kind) for kind in STORY}]
    assert [step.kind for step in story] == [str(kind) for kind in STORY] * 3
    first, later = story[:3], story[3:]
    # The day's pinned brief stays the first act's, alone under its key.
    assert first[0].private_task["scenario_brief"]["scenario_key"] == "engine:la-cle-oubliee"
    assert all("act" not in step.private_task for step in first)
    assert sum(1 for step in steps if "scenario_brief" in (step.private_task or {})) == 1
    assert [step.private_task["act"] for step in later] == [2, 2, 2, 3, 3, 3]
    assert [step.private_task["act_role"] for step in later] == ["cote"] * 3 + ["soir"] * 3
    assert later[0].private_task["act_brief"]["scenario_key"] == "engine:act-cote"
    assert later[3].private_task["act_brief"]["scenario_key"] == "engine:act-soir"
    assert later[1].private_task["response_task"]["character_id"] == "margaux_barman"
    assert [entry["role"] for entry in journey.plan_selection["acts"]] == ["cote", "soir"]
    # The app's prompts carry no act key until its own change reads one.
    assert all("act" not in (step.public_prompt or {}) for step in steps)


def test_a_one_act_day_is_stored_exactly_as_before(db_session: Session) -> None:
    journey = _persisted(db_session, _day("B1", 1800), "acts-one@example.com")
    assert "acts" not in journey.plan_selection
    assert all(
        "act" not in (step.private_task or {}) and "act_brief" not in (step.private_task or {})
        for step in journey.steps
    )
