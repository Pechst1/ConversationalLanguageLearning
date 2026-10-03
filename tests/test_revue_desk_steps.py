# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""WP-121/122 follow-up «Le bureau»: the Revue's other desks as one optional journey step.

* ``journey_day_shapes.choose_desk``: each desk (``relecture`` · ``radio`` ·
  ``correcteur``) at most once an ISO week, on or after its seeded weekday, at most
  one a day, only on an ordinary day — never a tentpole, the Papier day or a short
  day — and only when its flag is on and its offer is non-empty.
* The planner: one optional ``desk`` step after the ending and before the «Lecture»,
  inside the budget; the day gives up one ordinary recall for it; a classic day,
  the Papier day, a tentpole and the first day never hold one.
* WP-121 A.4: a recall card kept in a Papier carries ``met.place_label_fr``.
* A whole season with every desk on offer: the rule holds day by day.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.config import settings
from app.schemas.daily_journey import DeskPrompt, RecallPrompt
from app.services import journey_planner as planner
from app.services.journey_contracts import DESK_KINDS, DayShape, StepKind, rhythm_caps
from app.services.journey_day_shapes import (
    DESK_SHAPES,
    DayShapeInputs,
    choose_day_shape,
    choose_desk,
    desk_weekday,
    due_desks,
)
from tests.test_journey_planner import _brief, _candidate
from tests.test_season_one import (  # noqa: F401 - fixtures
    _play,
    assembled_client,
    clock,
    journey_enabled,
    season_on,
    support,
)
from tests.test_wpl6_rhythm import _queue
from tests.wp93_briefs import engine_brief

MONDAY = date(2026, 10, 5)
ALL = set(DESK_KINDS)
RELECTURE = {
    "session_id": str(uuid.uuid4()),
    "week": "2026-W34",
    "kind": "question",
    "dossier_title_fr": "La grève des éboueurs",
    "prompt_fr": "Qui paie quand la ville s'arrête ?",
    "place_label_fr": "Le marché d'Aligre",
    "plate_url": None,
    "closed_at": "2026-08-20T10:00:00+00:00",
}


def _offer(desk: str) -> dict:
    if desk == "relecture":
        return planner.desk_offer("relecture", title_fr=RELECTURE["dossier_title_fr"], relecture=RELECTURE)
    return planner.desk_offer(desk, title_fr="La grève des éboueurs", dossier_id="evergreen-greve", seconds=50)


def _inputs(day: date, user_id: str = "learner-desk", **extra) -> DayShapeInputs:
    return DayShapeInputs(user_id=user_id, local_date=day, **extra)


def _deal_weeks(user_id: str, weeks: int = 4, *, offered=ALL, tentpoles=(), shapes=None) -> dict[date, str | None]:
    """Walk ``weeks`` weeks day by day the way the service does: what was dealt
    earlier this ISO week is not dealt again."""

    dealt: dict[date, str | None] = {}
    for offset in range(7 * weeks):
        day = MONDAY + timedelta(days=offset)
        monday = day - timedelta(days=day.weekday())
        this_week = {desk for when, desk in dealt.items() if desk and monday <= when < day}
        shape = (shapes or {}).get(day, DayShape.STANDARD)
        dealt[day] = choose_desk(
            _inputs(day, user_id, tentpole=day in tentpoles),
            shape=shape,
            offered=offered,
            dealt_this_week=this_week,
        )
    return dealt


# ---------------------------------------------------------------------------
# 1. The rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("user_id", [f"learner-{n}" for n in range(12)])
def test_each_desk_at_most_once_a_week_and_never_two_a_day(user_id: str) -> None:
    dealt = _deal_weeks(user_id)
    weeks: dict[tuple[int, int], list[str]] = {}
    for day, desk in dealt.items():
        if desk:
            weeks.setdefault(day.isocalendar()[:2], []).append(desk)
    for week, desks in weeks.items():
        # choose_desk returns one desk a day, so «never two a day» is by type;
        # once a week each, and every offered desk does land in a full week.
        assert sorted(desks) == sorted(set(desks)), (week, desks)
        assert set(desks) == ALL, (week, desks)
    for day, desk in dealt.items():
        if desk:
            assert day.weekday() >= desk_weekday(_inputs(day, user_id), desk)


def test_the_three_spread_over_the_week_and_a_late_desk_waits() -> None:
    day = MONDAY + timedelta(days=4)  # Friday: every weekday has come
    due = due_desks(_inputs(day), shape=DayShape.STANDARD)
    assert set(due) == ALL
    assert list(due) == sorted(due, key=lambda desk: (desk_weekday(_inputs(day), desk), DESK_KINDS.index(desk)))
    # Nothing is due before its weekday.
    for desk in DESK_KINDS:
        weekday = desk_weekday(_inputs(MONDAY), desk)
        if weekday:
            assert desk not in due_desks(_inputs(MONDAY + timedelta(days=weekday - 1)), shape=DayShape.STANDARD)


@pytest.mark.parametrize("shape", [shape for shape in DayShape if shape not in DESK_SHAPES])
def test_never_on_the_papier_day_or_a_short_day(shape: DayShape) -> None:
    assert DayShape.REVUE not in DESK_SHAPES and DayShape.SHORT not in DESK_SHAPES
    for offset in range(7):
        assert choose_desk(_inputs(MONDAY + timedelta(days=offset)), shape=shape, offered=ALL) is None


def test_never_on_a_tentpole_and_a_tentpole_moves_the_desk_later() -> None:
    sunday = MONDAY + timedelta(days=6)
    assert choose_desk(_inputs(sunday, tentpole=True), shape=DayShape.STANDARD, offered=ALL) is None
    every_weekday = {MONDAY + timedelta(days=n) for n in range(5)}
    dealt = _deal_weeks("learner-desk", weeks=1, tentpoles=every_weekday)
    landed = [day for day, desk in dealt.items() if desk]
    assert landed and all(day not in every_weekday for day in landed)
    assert len(landed) == 2  # Saturday and Sunday: one a day, the third waits for next week


def test_the_papier_day_is_skipped_and_the_desk_lands_on_the_next_ordinary_day() -> None:
    papier = {MONDAY + timedelta(days=n): DayShape.REVUE for n in range(7) if n != 6}
    dealt = _deal_weeks("learner-desk", weeks=1, shapes=papier)
    assert [day for day, desk in dealt.items() if desk] == [MONDAY + timedelta(days=6)]


def test_flag_off_or_empty_offer_never_deals() -> None:
    assert all(desk is None for desk in _deal_weeks("learner-desk", offered=set()).values())
    only_radio = _deal_weeks("learner-desk", offered={"radio"})
    assert {desk for desk in only_radio.values() if desk} == {"radio"}
    # The offer is asked lazily, in order, and only for a due desk.
    asked: list[str] = []
    friday = MONDAY + timedelta(days=4)
    choose_desk(_inputs(friday), shape=DayShape.STANDARD, offered=lambda desk: asked.append(desk) or False)
    assert asked == list(due_desks(_inputs(friday), shape=DayShape.STANDARD))
    assert choose_desk(_inputs(friday), shape=DayShape.STANDARD, offered=ALL, dealt_this_week=ALL) is None


def test_the_desk_never_touches_the_day_shape_dice() -> None:
    for offset in range(14):
        day = MONDAY + timedelta(days=offset)
        assert choose_day_shape(_inputs(day)) == choose_day_shape(_inputs(day))


# ---------------------------------------------------------------------------
# 2. The planner
# ---------------------------------------------------------------------------


def _plan(budget: int, *, scenario=None, shape: DayShape = DayShape.STANDARD, **extra):
    return planner.plan_journey(
        scenario=scenario or engine_brief(),
        candidates=_queue(rhythm_caps(budget).candidate_limit),
        budget_seconds=budget,
        practice=extra.pop("practice", True),
        dice=_inputs(date(2026, 9, 29)),
        day_shape=shape,
        **extra,
    )


@pytest.mark.parametrize("desk", DESK_KINDS)
@pytest.mark.parametrize("budget", [600, 1200, 1800])
def test_one_optional_desk_after_the_ending_for_one_ordinary_recall(desk: str, budget: int) -> None:
    without = _plan(budget)
    plan = _plan(budget, desk=_offer(desk))
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    assert kinds.count(StepKind.DESK) == 1
    at = kinds.index(StepKind.DESK)
    assert at > kinds.index(StepKind.RESOLUTION)
    assert all(kind is StepKind.RECALL for kind in kinds[kinds.index(StepKind.RESOLUTION) + 1 : at])
    assert all(kind is StepKind.READ for kind in kinds[at + 1 :])
    step = plan.steps[at]
    assert step.optional and step.private_task is None and step.target is None
    prompt = DeskPrompt.model_validate(step.public_prompt)
    assert prompt.desk == desk
    if desk == "relecture":
        assert prompt.relecture is not None and prompt.relecture.session_id == RELECTURE["session_id"]
    else:
        assert prompt.dossier_id == "evergreen-greve"
    # The day gives up one ordinary recall for it, and stays inside the budget.
    recalls = lambda p: sum(1 for s in p.steps if s.kind is StepKind.RECALL)  # noqa: E731
    assert recalls(plan) <= recalls(without) - 1
    assert len(plan.steps) <= len(without.steps)
    assert plan.estimated_active_seconds <= budget
    assert "desk planned" in plan.rationale


def test_the_desk_comes_before_the_lecture() -> None:
    from tests.test_wp93_day_rebalance import _relecture

    plan = _plan(1800, desk=_offer("radio"), reading=_relecture())
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    assert kinds[-1] is StepKind.READ and kinds[-2] is StepKind.DESK


@pytest.mark.parametrize("shape", [DayShape.REVUE, DayShape.SHORT])
def test_no_desk_on_the_papier_day_or_a_short_day(shape: DayShape) -> None:
    plan = _plan(1200, shape=shape, desk=_offer("radio"))
    assert StepKind.DESK not in [step.kind for step in plan.steps]


@pytest.mark.parametrize("reason", ["season_tentpole", "first_day"])
def test_no_desk_on_a_tentpole_or_the_first_day(reason: str) -> None:
    plan = _plan(1200, shape_reason=reason, desk=_offer("correcteur"))
    assert StepKind.DESK not in [step.kind for step in plan.steps]
    first = _plan(1200, first_day=True, desk=_offer("correcteur"))
    assert StepKind.DESK not in [step.kind for step in first.steps]


def test_a_classic_day_never_holds_a_desk_and_the_validator_says_why() -> None:
    classic = _plan(300, scenario=_brief(), practice=False, desk=_offer("radio"))
    assert StepKind.DESK not in [step.kind for step in classic.steps]
    plan = _plan(1200, desk=_offer("radio"))
    desk = next(step for step in plan.steps if step.kind is StepKind.DESK)
    with pytest.raises(ValueError, match="optional"):
        replace(plan, steps=[replace(s, optional=False) if s is desk else s for s in plan.steps]).validate()
    twice = [*plan.steps, replace(desk, ordinal=len(plan.steps))]
    with pytest.raises(ValueError, match="at most one desk"):
        replace(plan, steps=twice).validate()
    unnamed = [replace(s, public_prompt={**s.public_prompt, "desk": "kiosque"}) if s is desk else s for s in plan.steps]
    with pytest.raises(ValueError, match="names its desk"):
        replace(plan, steps=unnamed).validate()
    early = [s for s in plan.steps if s is not desk]
    early.insert(0, desk)
    early = [replace(step, ordinal=index) for index, step in enumerate(early)]
    with pytest.raises(ValueError):
        replace(plan, steps=early).validate()


def test_a_desk_the_budget_cannot_hold_is_skipped_with_a_note() -> None:
    plan = _plan(300, desk=_offer("correcteur"))
    if StepKind.DESK not in [step.kind for step in plan.steps]:
        assert "desk correcteur skipped" in plan.rationale or "desk skipped" in plan.rationale
    assert plan.estimated_active_seconds <= 300


def test_a_desk_offer_without_its_target_is_no_desk() -> None:
    assert StepKind.DESK not in [s.kind for s in _plan(1200, desk=planner.desk_offer("radio", title_fr="x")).steps]
    assert StepKind.DESK not in [s.kind for s in _plan(1200, desk=planner.desk_offer("relecture", title_fr="x")).steps]
    assert StepKind.DESK not in [s.kind for s in _plan(1200, desk={"desk": "kiosque"}).steps]


# ---------------------------------------------------------------------------
# 3. WP-121 A.4 — «vu au …» on a recall card kept in a Papier
# ---------------------------------------------------------------------------


def test_a_papier_word_carries_its_place_line_on_the_recall_prompt() -> None:
    line = "vu au marché d'Aligre, semaine 41"
    queue = _queue(rhythm_caps(600).candidate_limit)
    queue = [replace(c, metadata={**c.metadata, "place_label_fr": line}) for c in queue]
    plan = planner.plan_journey(
        scenario=engine_brief(), candidates=queue, budget_seconds=600, practice=True,
        dice=_inputs(date(2026, 9, 29)), day_shape=DayShape.STANDARD,
    )
    recalls = [s for s in plan.steps if s.kind is StepKind.RECALL and s.target and s.target.kind == "vocabulary"]
    placed = [s for s in recalls if s.public_prompt.get("met")]
    assert placed, "a kept word's recall shows where it was met"
    assert all(s.public_prompt["met"] == {"place_label_fr": line} for s in placed)
    wire = RecallPrompt.model_validate(placed[0].public_prompt).model_dump(mode="json")
    assert wire["met"] == {"place_label_fr": line}
    # Any other card: no key at all on the wire.
    plain = planner.recall_met(_candidate())
    assert plain == {}
    bare = RecallPrompt.model_validate({**placed[0].public_prompt, "met": None}).model_dump(mode="json")
    assert "met" not in bare


def test_the_service_reads_the_place_line_from_the_card(db_session) -> None:
    from app.db.models.progress import UserVocabularyProgress
    from app.db.models.user import User
    from app.db.models.vocabulary import VocabularyWord
    from app.services.daily_journey import DailyJourneyService

    user = User(email=f"desk-{uuid.uuid4()}@example.com", hashed_password="x")
    db_session.add(user)
    word = VocabularyWord(word="la poubelle", normalized_word="poubelle", language="fr")
    other = VocabularyWord(word="le trottoir", normalized_word="trottoir", language="fr")
    db_session.add_all([word, other])
    db_session.flush()
    context = {"places": [{"place_id": "aligre", "place_name_fr": "Le marché d'Aligre", "week": "2026-W41", "session_id": "s"}]}
    db_session.add_all([
        UserVocabularyProgress(user_id=user.id, word_id=word.id, context=context),
        UserVocabularyProgress(user_id=user.id, word_id=other.id, context={"sentence": "x"}),
    ])
    db_session.flush()
    service = DailyJourneyService(db_session, adapters=None)  # type: ignore[arg-type]
    out = service._with_place_lines(user, [
        _candidate(identifier=str(word.id)), _candidate(identifier=str(other.id)), _candidate(identifier="w-none"),
    ])
    assert out[0].metadata["place_label_fr"] == "vu au marché d'Aligre, semaine 41"
    assert "place_label_fr" not in out[1].metadata and "place_label_fr" not in out[2].metadata


# ---------------------------------------------------------------------------
# 4. A whole season with every desk on offer
# ---------------------------------------------------------------------------


def test_a_whole_season_deals_each_desk_at_most_once_a_week(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch
) -> None:
    from app.db.models.daily_journey import DailyJourney
    from app.services.daily_journey import DailyJourneyService
    from app.services.revue import encounter as revue_encounter
    from app.services.revue.evergreen import load_evergreens
    from app.services.season.runtime import is_tentpole

    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    # Desks ride on the practice day (the production default; off in this module by conftest).
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    kiosk = load_evergreens()[:3]
    monkeypatch.setattr(revue_encounter, "available_dossiers", lambda period, db=None: list(kiosk))
    monkeypatch.setattr(DailyJourneyService, "_desk_offer", lambda self, user, desk, day: _offer(desk))
    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    d = support.Driver(
        assembled_client,
        support.register(assembled_client, f"s1-desk-{uuid.uuid4()}@example.com", cefr="A2.1"),
        db=db_session,
    )
    days: list[dict] = []
    for _day in range(28):
        journey = _play(d, provider, clock, "Odile, c'est ma grand-mère.")
        row = db_session.get(DailyJourney, uuid.UUID(journey["id"]))
        selection = row.plan_selection if isinstance(row.plan_selection, dict) else {}
        scene = next((s for s in row.steps if s.kind == "scene"), None)
        brief = ((scene.private_task or {}).get("scenario_brief") or {}) if scene else {}
        desks = [step["prompt"]["desk"] for step in journey["steps"] if step["kind"] == "desk"]
        days.append({
            "date": row.local_date,
            "shape": selection.get("day_shape"),
            "desks": desks,
            "tentpole": is_tentpole(brief.get("story_context") if isinstance(brief, dict) else None),
            "budget": row.budget_seconds,
            "why": [line for line in str(selection.get("rationale") or "").split(";") if "desk" in line][:3],
        })
    assert sum(1 for row in days if row["desks"]) >= 4, [
        (row["shape"], row["budget"], row["why"]) for row in days[:8]
    ]
    weeks: dict[tuple[int, int], list[str]] = {}
    for row in days:
        assert len(row["desks"]) <= 1, row
        if row["desks"]:
            assert row["shape"] not in ("revue", "short"), row
            assert not row["tentpole"], row
        weeks.setdefault(row["date"].isocalendar()[:2], []).extend(row["desks"])
    for week, desks in weeks.items():
        assert len(desks) == len(set(desks)), (week, desks)
