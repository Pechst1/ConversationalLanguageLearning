"""WP-128 — fit the core day to the chosen time.

The selected rhythm budgets the *recommended core path* — the story and its
practice. The drill's words, a letter, La Forge and the «Lecture» carry their
own estimates and are never folded into it. The estimate is level-aware (the
reading prior, the page's prose factor and the reply's composition are the
band's), a page that cannot fit is a flagged *longer day* rather than a cut
one, and every surface shows the same core number. Estimation is never
enforcement: nothing is timed, cut or penalised.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import journey_events
from app.services import journey_planner as planner
from app.services.daily_journey import _plan_time_budget
from app.services.journey_contracts import DayShape, StepKind
from app.services.journey_day_shapes import DayShapeInputs
from tests import experience_walk
from tests.test_journey_end_to_end import (
    Clock,  # noqa: F401 - fixture type
    Driver,
    assembled_client,  # noqa: F401 - fixture
    clock,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    learner_id,
    register,
    seed_due_vocabulary,
)
from tests.test_journey_planner import _candidate
from tests.wp93_briefs import engine_brief, engine_draft

BANDS = ("A1", "A2", "B1", "B2", "C1")
DICE = DayShapeInputs(user_id="wp128", local_date=date(2026, 10, 4))


def _queue(count: int = 16) -> list:
    words = [
        ("la clé", "the key"), ("la chaise", "the chair"), ("la porte", "the door"),
        ("un café", "a coffee"), ("le zinc", "the counter"), ("la pluie", "the rain"),
        ("le carnet", "the notebook"), ("la lettre", "the letter"), ("le canal", "the canal"),
        ("la vitre", "the window pane"), ("le voisin", "the neighbour"), ("la cave", "the cellar"),
        ("une idée", "an idea"), ("le marché", "the market"), ("la photo", "the photo"),
        ("le billet", "the ticket"),
    ]
    return [
        _candidate(identifier=f"w{index}", label_fr=fr, label_native=native, priority=20 - index)
        for index, (fr, native) in enumerate(words[:count])
    ]


def _day(band: str, budget: int = 600, **extra):
    return planner.plan_journey(
        scenario=extra.pop("scenario", None) or engine_brief(level_band=band),
        candidates=extra.pop("candidates", None) or _queue(),
        budget_seconds=budget,
        practice=True,
        dice=DICE,
        day_shape=DayShape.STANDARD,
        **extra,
    )


# ---------------------------------------------------------------------------
# 1. The level-aware prior, its bound, and the page factor calibrated with it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("band", "prior"), [("A1", 0.75), ("A2", 0.60), ("B1", 0.45), ("B2", 0.38), ("C1", 0.32)]
)
def test_the_reading_prior_is_the_bands(band: str, prior: float) -> None:
    assert planner.reading_prior(band) == prior
    assert planner.reading_prior(f"{band}.2") == prior
    # Untrusted, or trusted with no per-token measurement: the band's prior.
    assert planner.PacingProfile().effective_seconds_per_token(band) == prior
    assert planner.PacingProfile(step_multiplier=1.2, observations=5).effective_seconds_per_token(band) == prior
    assert planner.reading_prior(None) == planner.DEFAULT_SECONDS_PER_TOKEN


def test_a_measured_pace_is_bounded_by_the_widened_band() -> None:
    assert planner.SECONDS_PER_TOKEN_BOUNDS == (0.25, 1.0)
    slow = planner.PacingProfile(seconds_per_token=1.6, observations=3)
    fast = planner.PacingProfile(seconds_per_token=0.1, observations=3)
    assert slow.effective_seconds_per_token("A1") == 1.0
    assert fast.effective_seconds_per_token("C1") == 0.25
    # Two noisy days are not trusted at all.
    assert planner.PacingProfile(seconds_per_token=1.6, observations=2).effective_seconds_per_token("C1") == 0.32
    # The slowest trusted A1 reader reads a page at 2.0 s a word — 30 wpm, the
    # walk Timer's A1 «struggling» learner (45 wpm / 1.4 ≈ 32 wpm).
    assert 1.0 * planner.page_reading_factor("A1") == pytest.approx(60 / (45 / 1.4), rel=0.1)


@pytest.mark.parametrize("band", BANDS)
def test_prior_times_page_factor_is_the_timers_prose_pace(band: str) -> None:
    """The prior and the factor are calibrated together, against the walk's
    independent Timer — never against the planner's own estimate."""

    number = experience_walk.band_number(band)
    timer = 60 / experience_walk.FR_READ_WPM[number]
    if number <= 2:  # A1–A2 half-glance at each line's gloss
        timer += 0.5 * 60 / experience_walk.NATIVE_READ_WPM
    page = planner.reading_prior(band) * planner.page_reading_factor(band)
    assert page == pytest.approx(timer, rel=0.1), (band, page, timer)
    # The review's priors with the old constant factor would have counted the
    # French twice above A1 (B2: 0.38 × 2.0 = 0.76 s a word, against 0.43).
    if band in ("B2", "C1"):
        assert planner.reading_prior(band) * planner.PAGE_READING_FACTOR > 1.5 * timer


def test_the_same_page_costs_a_beginner_more_than_an_advanced_reader() -> None:
    seconds = [
        planner.scene_seconds(
            engine_brief(level_band=band), spt=planner.reading_prior(band), multiplier=1.0, band=band
        )
        for band in BANDS
    ]
    assert seconds == sorted(seconds, reverse=True), seconds
    # A1's reply is composed at 5 words a minute; C1's at 19.
    task = engine_brief().response_task
    replies = [
        planner.respond_seconds(task, turns=3, spt=planner.reading_prior(b), multiplier=1.0, band=b)
        for b in BANDS
    ]
    assert replies == sorted(replies, reverse=True), replies
    assert replies[0] > 2 * replies[-1]


def test_an_authored_choice_is_priced_as_a_tap_not_a_sentence() -> None:
    task = engine_brief().response_task
    composed = planner.respond_seconds(task, turns=2, spt=0.75, multiplier=1.0, band="A1")
    tapped = planner.respond_seconds(
        task, turns=2, spt=0.75, multiplier=1.0, band="A1",
        authored=[("reply", 5), ("card", 6)],
    )
    assert tapped < composed - 60


# ---------------------------------------------------------------------------
# 2. Fitting the core: trim intake first, never the story
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", BANDS)
def test_an_ordinary_day_fits_its_rhythm_at_every_band(band: str) -> None:
    for budget in (300, 600, 1200):
        plan = _day(band, budget)
        plan.validate()
        assert plan.longer_day or plan.core_seconds() <= budget, (band, budget)
        if plan.longer_day:
            # Only a slow band on the shortest rhythm.
            assert (band, budget) in {("A1", 300), ("A2", 300)}, (band, budget)


def test_a_beginners_ten_minutes_are_mostly_the_story_and_the_practice_gives_way() -> None:
    a1, b2 = _day("A1"), _day("B2")
    recalls = lambda plan: sum(1 for step in plan.steps if step.kind is StepKind.RECALL)  # noqa: E731
    assert recalls(a1) < recalls(b2), "the slow band defers intake, the story stays"
    for plan in (a1, b2):
        kinds = [step.kind for step in plan.steps]
        assert kinds.count(StepKind.SCENE) == 1 and kinds.count(StepKind.RESPOND) == 1
        respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
        assert respond.public_prompt["repair_allowed"] is True, "required repair is never trimmed"
    # The page is never cut: the scene step carries the whole page at any rhythm.
    for budget in (300, 600):
        scene = next(step for step in _day("A1", budget).steps if step.kind is StepKind.SCENE)
        assert scene.public_prompt["setup_fr"] == engine_brief().setup_fr


def test_due_review_is_kept_before_new_intake() -> None:
    due = [_candidate(identifier=f"d{i}", label_fr=fr, label_native=n, priority=30 - i) for i, (fr, n) in
           enumerate([("la clé", "the key"), ("la chaise", "the chair")])]
    new = _candidate(identifier="n1", label_fr="le zinc", label_native="the counter", is_new=True)
    plan = _day("A1", 600, candidates=[*due, new])
    practised = [step.target.id for step in plan.steps if step.kind is StepKind.RECALL and step.target]
    assert practised, plan.rationale
    if "n1" in practised:
        assert {"d0", "d1"} <= set(practised), "a new word only after the due ones"


@pytest.fixture
def a_rule(monkeypatch):
    """Today's unit: a card and two guided items (taken from a real plan)."""

    guided = [
        step.private_task for step in _day("B2", 1200).steps if step.kind is StepKind.RECALL
    ][:2]
    card = {"example": {"fr": "Je suis là."}, "rule": {"en": "Être: je suis, tu es."}}

    def items(brief, **kwargs):
        if not brief:
            return None, 0, []
        return card, 40, [(task, 20) for task in guided]

    monkeypatch.setattr(planner, "_introduction_items", items)
    monkeypatch.setattr(
        planner.grammar_items, "grammar_target",
        lambda brief: _candidate(kind=planner.TargetKind.GRAMMAR, identifier="1", label_fr="être").target,
    )
    monkeypatch.setattr(planner, "_rule_step", lambda ordinal, **kw: planner.PlannedStep(
        ordinal=ordinal, kind=StepKind.RULE, estimated_seconds=kw["cost"], public_prompt={"concept_id": 1},
    ))
    return {"concept_id": 1, "detectors": []}


def test_the_new_rule_takes_the_replys_extra_turns_before_it_is_deferred(a_rule) -> None:
    plain = _day("A1", 600)
    with_rule = _day("A1", 600, introduction=a_rule)
    with_rule.validate()
    assert StepKind.RULE in [step.kind for step in with_rule.steps]
    turns = lambda plan: next(s for s in plan.steps if s.kind is StepKind.RESPOND).public_prompt["max_turns"]  # noqa: E731
    assert turns(with_rule) < turns(plain), with_rule.rationale
    assert "so the new rule fits the budget" in with_rule.rationale
    assert not with_rule.longer_day and with_rule.core_seconds() <= 600


def test_a_rule_that_cannot_fit_is_a_longer_day_of_story_and_rule(a_rule) -> None:
    plan = _day("A1", 300, introduction=a_rule)
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    assert plan.longer_day and StepKind.RULE in kinds
    scene_at = kinds.index(StepKind.SCENE)
    assert all(kind in (StepKind.RULE, StepKind.RECALL) for kind in kinds[:scene_at])
    assert kinds[scene_at:] == [StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION]
    assert "longer day" in plan.rationale


def test_a_page_too_long_for_the_rhythm_is_a_flagged_longer_day_never_cut() -> None:
    draft = engine_draft()
    long_panels = [
        {**panel, "narration_fr": " ".join(["Le canal est gris et la pluie tombe encore."] * 12)}
        for panel in draft["panels"]
    ]
    long = engine_brief(draft={**draft, "panels": long_panels}, level_band="A1")
    assert planner.story_alone_seconds(long) > 600
    plan = _day("A1", 600, scenario=long)
    plan.validate()
    assert plan.longer_day
    assert [step.kind for step in plan.steps] == [StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION]
    assert plan.steps[0].estimated_seconds == planner.scene_seconds(
        long, spt=0.75, multiplier=1.0, band="A1"
    ), "the whole page is priced, and planned"
    assert plan.core_seconds() > plan.budget_seconds
    assert "longer day" in plan.rationale
    # The flag is a contract: a longer day carries no practice and no extension.
    padded = replace(plan, steps=[*plan.steps[:1], replace(plan.steps[0], kind=StepKind.RECALL, ordinal=1)])
    with pytest.raises(ValueError):
        padded.validate()


# ---------------------------------------------------------------------------
# 3. One shared estimate: the core, and extensions of their own
# ---------------------------------------------------------------------------


def test_the_core_leaves_the_optional_extensions_out() -> None:
    reading = {
        "variant": "relecture", "title_fr": "Hier", "status": "ready", "audio_available": False,
        "texts_fr": planner.page_texts(engine_draft()["panels"]), "panel_count": len(engine_draft()["panels"]),
    }
    plan = _day("B1", 1200, reading=reading)
    plan.validate()
    read = [step for step in plan.steps if step.kind is StepKind.READ]
    assert read, plan.rationale
    assert plan.core_seconds() == plan.estimated_active_seconds - read[0].estimated_seconds
    assert plan.extension_seconds() == {"reading": read[0].estimated_seconds}
    stored = _plan_time_budget(plan)
    assert stored == {
        "budget_seconds": 1200,
        "core_seconds": plan.core_seconds(),
        "longer_day": False,
        "extensions": {"reading": read[0].estimated_seconds},
    }


def test_the_extensions_are_priced_on_their_own() -> None:
    assert planner.word_drill_seconds(0) == 0
    assert planner.word_drill_seconds(10) == 10 * planner.WORD_CARD_SECONDS
    assert planner.word_drill_seconds(400) == planner.WORD_DRILL_MAX_CARDS * planner.WORD_CARD_SECONDS
    letters = [planner.letter_seconds(band) for band in BANDS]
    assert letters == sorted(letters, reverse=True), letters
    assert 120 <= letters[0] <= 420 and letters[-1] >= 60


def test_home_the_plan_and_the_ending_carry_the_same_core(
    assembled_client: TestClient, journey_enabled: None, clock, db_session: Session  # noqa: F811
) -> None:
    email = "wp128-shared@example.com"
    headers = register(assembled_client, email)
    seed_due_vocabulary(db_session, learner_id(db_session, email), (("la clé", "the key"), ("le zinc", "the counter")))
    driver = Driver(assembled_client, headers, db=db_session)
    offer = driver.today()
    home = offer["time_estimate"]
    assert home["basis"] == "forecast"
    assert home["core_seconds"] == offer["available"]["estimated_seconds"]
    kinds = {item["kind"] for item in home["extensions"]}
    assert {"letter", "forge"} <= kinds, home
    assert all(item["seconds"] > 0 for item in home["extensions"])

    journey = driver.create(expect=(201,))
    planned = journey["time_estimate"]
    assert planned["basis"] == "plan"
    in_day = sum(item["seconds"] for item in planned["extensions"] if item["in_day"])
    assert planned["core_seconds"] + in_day == journey["estimated_active_seconds"]
    today = driver.today()
    assert today["time_estimate"]["core_seconds"] == planned["core_seconds"], "Home says the plan's number"
    assert today["journey"]["time_estimate"] == planned
    # The optional words never change the core.
    words = [item for item in today["time_estimate"]["extensions"] if item["kind"] == "words"]
    assert not words or words[0]["in_day"] is False

    driver.play(answer="Bonjour, je voudrais un café au comptoir, s'il vous plaît.")
    assert driver.finish("complete").status_code == 200
    assert driver.journey["recap"]["estimated_core_seconds"] == planned["core_seconds"]


# ---------------------------------------------------------------------------
# 4. Estimate against measurement — never enforcement
# ---------------------------------------------------------------------------


def test_the_estimate_and_the_measurement_are_reported_side_by_side() -> None:
    journey = SimpleNamespace(
        id="j1", local_date=date(2026, 10, 4), level_band="A1", budget_seconds=600,
        estimated_active_seconds=640,
        plan_selection={"time_budget": {"core_seconds": 560, "longer_day": False, "extensions": {"reading": 80}}},
    )
    measured = journey_events.JourneyDuration(
        journey_id="j1", active_seconds=700, measurable=True, idle_excluded_seconds=40,
        provider_wait_seconds=3.5,
    )
    row = journey_events.estimate_row(journey, measured)
    assert row["estimated_core_seconds"] == 560
    assert row["measured_active_seconds"] == 700
    assert row["error_share"] == pytest.approx(0.25)
    assert row["provider_wait_seconds"] == 3.5 and row["idle_excluded_seconds"] == 40
    unmeasured = journey_events.estimate_row(
        journey, journey_events.JourneyDuration(journey_id="j1", active_seconds=None, measurable=False)
    )
    assert unmeasured["error_share"] is None and unmeasured["measured_active_seconds"] is None
    section = journey_events._estimate_error_section([row, unmeasured])
    assert section["by_band"]["A1"]["days"] == 1
    assert section["by_band"]["A1"]["over_by_20_percent"] == 1
    # Every event of the day carries the core it was planned at.
    metadata = journey_events.journey_event_metadata(journey)
    assert metadata["estimated_core_seconds"] == 560 and metadata["longer_day"] is False
    clean, rejected = journey_events.sanitize_metadata(metadata)
    assert clean["estimated_core_seconds"] == 560 and "estimated_core_seconds" not in rejected


def test_a_slower_learner_gets_a_shorter_plan_not_a_timer() -> None:
    prior = _day("A2", 600)
    slow = _day("A2", 600, pace=planner.PacingProfile(step_multiplier=1.35, observations=5))
    assert slow.core_seconds() <= 600
    for plan in (prior, slow):
        # The page and the reply are whole either way …
        assert [s.kind for s in plan.steps].count(StepKind.SCENE) == 1
        # … and nothing on the wire times an answer.
        wire = json.dumps([step.public_prompt for step in plan.steps], default=str)
        for key in ("deadline", "time_limit", "timeout", "seconds_left"):
            assert key not in wire
    assert planner.graded_interactions(slow) <= planner.graded_interactions(prior)
