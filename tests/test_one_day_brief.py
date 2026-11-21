# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""S1.1 «one day brief» (shadow stage): the day's rule, decided once and stored.

The brief is built where the day is planned, stored in ``plan_selection["brief"]``
behind ``DAY_BRIEF_ENABLED``, read back by ``day_brief.for_day`` (an older day
falls back to its stored introduction, then its RULE step) and never rebuilt.
The choosers that still pick «today's rule» on their own are compared with it
and log one ``day_brief_disagreement`` warning when they differ. Nothing reads
the brief for the learner yet: with the flag off, nothing is built or stored.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.services import day_brief
from app.services.atelier import AtelierScheduler
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from app.services.vocabulary_pace import JOURNEY_NEW_WORDS_KEY
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    enabled,
    make_user,
)
from tests.test_wp_s4_one_picker import v2  # noqa: F401 - fixture

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


@pytest.fixture()
def brief_on(monkeypatch):
    monkeypatch.setattr(settings, "DAY_BRIEF_ENABLED", True)


def _rule_step(concept_id: int, *, review: bool = False) -> SimpleNamespace:
    prompt = {"concept_id": concept_id, "title_native": "x"}
    if review:
        prompt["review"] = True
    return SimpleNamespace(kind="rule", public_prompt=prompt)


def _plan(*steps) -> SimpleNamespace:
    return SimpleNamespace(steps=[SimpleNamespace(kind="scene", public_prompt={}), *steps])


def _day(db: Session) -> tuple:
    user = make_user(db, f"brief-{uuid.uuid4().hex[:8]}@example.com")
    upcoming = AtelierScheduler(db).next_new_concepts(user, limit=3, language="fr")
    assert len(upcoming) >= 2
    journey = SimpleNamespace(id=uuid.uuid4(), local_date=date(2026, 11, 16), plan_selection={}, steps=[])
    return user, upcoming, journey


def _scenario(introduce: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        story_context={
            "grammar": {
                "focus": {"unit_id": str(introduce), "woven": True} if introduce else None,
                "plan": {"introduce": str(introduce) if introduce else None, "weave": ["7"]},
            }
        }
    )


# ---------------------------------------------------------------------------
# What the brief holds for each kind of day
# ---------------------------------------------------------------------------


def test_introduce_day(db_session: Session, v2) -> None:
    user, upcoming, journey = _day(db_session)
    rule = upcoming[1]
    brief = day_brief.build(
        db_session, user, journey=journey, plan=_plan(_rule_step(rule.id)), scenario=_scenario(rule.id), now=NOW
    )
    assert brief.rule.role == day_brief.ROLE_INTRODUCE
    assert brief.rule.concept_id == rule.id
    assert brief.rule.external_id == rule.external_id
    assert brief.review_concept_ids == ()
    # La Forge opens on the day's rule, not on the quota's first one.
    assert brief.forge_anchor == rule.id
    assert brief.scene_grammar.present and brief.scene_grammar.introduce == rule.id
    assert brief.words == {"batch_day": "2026-11-16", "reservation_key": JOURNEY_NEW_WORDS_KEY}
    # It survives the JSON column.
    assert day_brief.DayBrief.from_json(brief.to_json()) == brief


def test_review_day(db_session: Session, v2) -> None:
    user, upcoming, journey = _day(db_session)
    known = upcoming[0]
    brief = day_brief.build(
        db_session, user, journey=journey, plan=_plan(_rule_step(known.id, review=True)), scenario=_scenario(), now=NOW
    )
    assert brief.rule.role == day_brief.ROLE_REVIEW
    assert brief.rule.concept_id == known.id
    assert brief.review_concept_ids == (known.id,)
    assert brief.introduced_concept_id is None
    assert brief.forge_anchor == known.id


def test_day_with_no_rule(db_session: Session, v2) -> None:
    user, _upcoming, journey = _day(db_session)
    brief = day_brief.build(db_session, user, journey=journey, plan=_plan(), scenario=SimpleNamespace(), now=NOW)
    assert brief.rule == day_brief.BriefRule()
    assert brief.rule.role == day_brief.ROLE_NONE
    assert brief.review_concept_ids == ()
    # A page with no grammar plan (shared page, authored day) is «not known», not «no rule».
    assert brief.scene_grammar.present is False
    assert "rule" in brief.to_json() and brief.to_json()["rule"]["role"] == "none"


def test_an_introducing_card_is_the_rule_beside_a_review(db_session: Session, v2) -> None:
    user, upcoming, journey = _day(db_session)
    plan = _plan(_rule_step(upcoming[1].id), _rule_step(upcoming[0].id, review=True))
    brief = day_brief.build(db_session, user, journey=journey, plan=plan, scenario=_scenario(), now=NOW)
    assert brief.rule.role == day_brief.ROLE_INTRODUCE and brief.rule.concept_id == upcoming[1].id
    assert brief.review_concept_ids == (upcoming[0].id,)


def test_day_one_stores_its_brief_where_the_day_is_planned(db_session: Session, v2, enabled, brief_on) -> None:
    user = make_user(db_session, f"brief-day1-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    stored = (row.plan_selection or {}).get(day_brief.BRIEF_KEY)
    assert isinstance(stored, dict) and stored["version"] == day_brief.BRIEF_VERSION
    brief = day_brief.for_day(row)
    assert brief is not None and not brief.legacy
    assert brief.local_date == row.local_date.isoformat()
    # The brief's rule is the plan's: the stored introduction, else the card's own step.
    expected, _reviews = day_brief.rule_from_steps(row.steps)
    assert brief.rule.concept_id == expected.concept_id
    assert brief.rule.role == expected.role
    introduction = (row.plan_selection or {}).get("introduction") or {}
    if brief.rule.role == day_brief.ROLE_INTRODUCE:
        assert brief.rule.concept_id == int(introduction["concept_id"])


# ---------------------------------------------------------------------------
# Reading an older day, and never rebuilding
# ---------------------------------------------------------------------------


def test_older_journey_falls_back_to_introduction_then_rule_step() -> None:
    journey = SimpleNamespace(
        id=uuid.uuid4(),
        local_date=date(2026, 11, 1),
        plan_selection={"introduction": {"concept_id": 11, "title_native": "x"}},
        steps=[_rule_step(11)],
    )
    brief = day_brief.for_day(journey)
    assert brief.legacy and brief.rule.role == day_brief.ROLE_INTRODUCE
    assert brief.rule.concept_id == 11 and brief.rule.source == day_brief.SOURCE_LEGACY_INTRODUCTION
    assert brief.forge_anchor == 11

    journey.plan_selection = {"introduction": None}
    journey.steps = [_rule_step(12, review=True)]
    brief = day_brief.for_day(journey)
    assert brief.rule.role == day_brief.ROLE_REVIEW and brief.rule.concept_id == 12
    assert brief.rule.source == day_brief.SOURCE_LEGACY_RULE_STEP
    assert brief.review_concept_ids == (12,)

    journey.steps = []
    brief = day_brief.for_day(journey)
    assert brief.rule.role == day_brief.ROLE_NONE and brief.rule.concept_id is None
    assert journey.plan_selection == {"introduction": None}, "reading never writes a brief"
    assert day_brief.for_day(None) is None


def test_the_brief_is_never_rebuilt_for_an_existing_journey(
    db_session: Session, v2, enabled, brief_on, monkeypatch
) -> None:
    user = make_user(db_session, f"brief-keep-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    before = dict(row.plan_selection[day_brief.BRIEF_KEY])

    def refuse(*_args, **_kwargs):
        raise AssertionError("the brief was rebuilt for a journey that already exists")

    monkeypatch.setattr(day_brief, "build", refuse)
    monkeypatch.setattr(day_brief, "store", refuse)
    service.get_today(user)
    service.snapshot(row)
    day_brief.for_day(row)
    db_session.refresh(row)
    assert row.plan_selection[day_brief.BRIEF_KEY] == before


# ---------------------------------------------------------------------------
# Flag off: today's code path, nothing built, stored or compared
# ---------------------------------------------------------------------------


def test_flag_off_builds_stores_and_compares_nothing(db_session: Session, v2, enabled, monkeypatch) -> None:
    monkeypatch.setattr(settings, "DAY_BRIEF_ENABLED", False)
    touched: list[str] = []

    def refuse(name):
        def call(*_args, **_kwargs):
            touched.append(name)
            raise AssertionError(f"day_brief.{name} ran with the flag off")

        return call

    for name in ("build", "store", "stored", "shadow_planning"):
        monkeypatch.setattr(day_brief, name, refuse(name))
    user = make_user(db_session, f"brief-off-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201
    service.get_today(user)
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert day_brief.BRIEF_KEY not in (row.plan_selection or {})
    assert touched == []
    assert day_brief.shadow(row, "any", 1, field="forge_anchor") is False
    assert day_brief.shadow_today(db_session, user, "any", 1, field="forge_anchor") is False


# ---------------------------------------------------------------------------
# Shadow comparison
# ---------------------------------------------------------------------------


def test_a_chooser_that_disagrees_logs_one_structured_warning(brief_on, caplog) -> None:
    brief = day_brief.DayBrief(
        local_date="2026-11-16",
        rule=day_brief.BriefRule(role=day_brief.ROLE_INTRODUCE, source=day_brief.SOURCE_PLAN_RULE, concept_id=5),
        forge_anchor=5,
    )
    journey = SimpleNamespace(id=uuid.uuid4(), local_date=date(2026, 11, 16), plan_selection={})
    day_brief.store(journey, brief)
    caplog.set_level(logging.WARNING, logger=day_brief.__name__)

    assert day_brief.shadow(journey, "forge_picker._anchor", 5, field="forge_anchor") is False
    assert day_brief.shadow(journey, "daily_journey._introduction_for_today", {"concept_id": 5}, field="introduced_concept_id") is False
    assert day_brief.shadow(journey, "daily_journey._page_review_for_today", None, field="review_concept_ids") is False
    assert not [r for r in caplog.records if getattr(r, "event_name", None) == day_brief.SHADOW_EVENT]

    assert day_brief.shadow(journey, "forge_picker._anchor", 9, field="forge_anchor") is True
    assert day_brief.shadow(journey, "daily_journey._page_review_for_today", [9, 4], field="review_concept_ids") is True
    events = [r for r in caplog.records if getattr(r, "event_name", None) == day_brief.SHADOW_EVENT]
    assert [(r.chooser, r.chooser_value, r.brief_value) for r in events] == [
        ("forge_picker._anchor", 9, 5),
        ("daily_journey._page_review_for_today", [4, 9], []),
    ]
    assert all(r.journey_id == str(journey.id) for r in events)

    # An older day without a stored brief is never compared.
    older = SimpleNamespace(id=uuid.uuid4(), local_date=date(2026, 11, 1), plan_selection={})
    assert day_brief.shadow(older, "forge_picker._anchor", 9, field="forge_anchor") is False


def test_scene_grammar_reads_the_served_page() -> None:
    grammar = day_brief.scene_grammar_of(_scenario(42))
    assert grammar == day_brief.SceneGrammar(present=True, introduce=42, woven=True, weave=(7,))
    provenance_only = SimpleNamespace(story_context={"source": {"grammar_plan": {"introduce": None, "weave": []}}})
    assert day_brief.scene_grammar_of(provenance_only) == day_brief.SceneGrammar(present=True)
    assert day_brief.scene_grammar_of(SimpleNamespace(story_context={})) == day_brief.SceneGrammar()


def test_the_forge_step_is_compared_with_the_stored_brief(
    db_session: Session, v2, enabled, brief_on, caplog
) -> None:
    """A read-time chooser (the folded Forge step) against the brief stored at planning."""

    from app.db.models.daily_journey import DailyJourneyStep

    user = make_user(db_session, f"brief-shadow-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    upcoming = AtelierScheduler(db_session).next_new_concepts(user, limit=4, language="fr")
    folded = DailyJourneyStep(
        journey_id=row.id, ordinal=99, kind="forge", status="pending", estimated_seconds=300,
        public_prompt={"concept_id": upcoming[0].id, "budget_seconds": 300},
    )
    db_session.add(folded)
    db_session.commit()
    db_session.refresh(row)
    shown = service._forge_prompt_view(row, folded)["concept_id"]
    stored = dict(row.plan_selection[day_brief.BRIEF_KEY])

    # The brief agrees with the step: nothing is logged.
    row.plan_selection = {**row.plan_selection, day_brief.BRIEF_KEY: {**stored, "forge_anchor": shown}}
    flag_modified(row, "plan_selection")
    caplog.set_level(logging.WARNING, logger=day_brief.__name__)
    caplog.clear()
    service._forge_prompt_view(row, folded)
    assert not [r for r in caplog.records if getattr(r, "event_name", None) == day_brief.SHADOW_EVENT]

    # The brief names another rule: one event, and the step's own answer is unchanged.
    other = next(concept.id for concept in upcoming if concept.id != shown)
    row.plan_selection = {**row.plan_selection, day_brief.BRIEF_KEY: {**stored, "forge_anchor": other}}
    flag_modified(row, "plan_selection")
    assert service._forge_prompt_view(row, folded)["concept_id"] == shown
    events = [r for r in caplog.records if getattr(r, "event_name", None) == day_brief.SHADOW_EVENT]
    assert [(r.chooser, r.chooser_value, r.brief_value) for r in events] == [
        ("daily_journey._forge_prompt_view", shown, other)
    ]
