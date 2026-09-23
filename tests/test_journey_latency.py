"""WP-26 — prefetch, the hot path, telemetry and the release gate.

The five things the acceptance criteria turn on:

1. the prefetch is idempotent — a second run inside the same story revision and
   prompt version pays nothing;
2. a stale cache key is *discarded*, never served;
3. the flag and the cohort each refuse the paid call on their own;
4. a valid prefetch is served by the hot path, exactly once, and the draft is
   never generated twice;
5. every measured request leaves a durable row, and the digest and the gate are
   computed from those rows rather than asserted.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import journey_latency
from app.services.journey_contracts import (
    ContentUnavailable,
    InputMode,
    ResponseTask,
    ScenarioBrief,
)
from app.services.journey_latency import (
    LATENCY_EVENT,
    PHASE_DRAFT,
    PHASE_RECAP,
    PHASE_RESPOND,
    PREFETCH_CONSUMED_EVENT,
    PREFETCH_DISCARDED_EVENT,
    PREFETCH_EVENT,
    evaluate_gate,
    format_latency_lines,
    latency_rollup,
    measure_phase,
    prefetch_enabled_for,
    prefetch_scene_for,
    record_latency,
    scene_cache_key,
    sweep_expired_prefetches,
    take_prefetched_scene,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# The pilot ledger's day is a Europe/Berlin calendar day (`pilot_events._day_bounds`).
# Asking for the host's local date (or the UTC date) instead made these tests fail
# between 00:00 and 02:00 Berlin time — or, on a UTC CI runner, 22:00-24:00 UTC.
def _pilot_today():
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def make_user(db: Session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_brief(key: str = "story_test") -> ScenarioBrief:
    return ScenarioBrief(
        scenario_key=key,
        content_version="living-story-v2",
        title_fr="Le pain du matin",
        objective_key=key,
        objective_native="Ask for bread.",
        level_band="A1",
        character_id="amina",
        character_name="Amina",
        location_id="boulangerie",
        location_name="La boulangerie",
        image_url=None,
        setup_fr="Tu entres.",
        setup_native="You walk in.",
        opening_line_fr="Bonjour !",
        response_task=ResponseTask(
            objective_native="Ask for bread.",
            character_id="amina",
            character_name="Amina",
            opening_line_fr="Bonjour !",
        ),
        estimated_seconds=270,
        control_language="en",
        story_context={
            "version": "living-story-v2",
            "generation_usage": [{"stage": "SceneDraft", "cost_usd": 0.004}],
        },
    )



@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (journey_latency, __import__("app.services.daily_journey", fromlist=["x"])):
        monkeypatch.setattr(
            module.settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True, raising=False
        )
        monkeypatch.setattr(
            module.settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False
        )
        monkeypatch.setattr(
            module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False
        )
        monkeypatch.setattr(
            module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False
        )
        monkeypatch.setattr(module.settings, "APP_ENV", "test", raising=False)


@pytest.fixture()
def revision(monkeypatch: pytest.MonkeyPatch):
    """A settable story revision, so a test can move the thread under a cache."""

    state = {"value": "rev-1"}
    import app.services.living_story as living_story

    monkeypatch.setattr(
        living_story, "story_revision", lambda db, user: state["value"], raising=False
    )
    return state


@pytest.fixture()
def generated(monkeypatch: pytest.MonkeyPatch):
    """Counts every call the prefetch makes to the paid generator."""

    calls: dict[str, Any] = {"count": 0, "result": make_brief()}
    import app.services.living_story as living_story

    def fake_generate_scene(db, *, user, input_mode):
        calls["count"] += 1
        return calls["result"]

    monkeypatch.setattr(living_story, "generate_scene", fake_generate_scene)
    return calls


# ---------------------------------------------------------------------------
# 1. The cache key (WP-14C)
# ---------------------------------------------------------------------------


def test_cache_key_changes_with_story_revision(
    db_session: Session, enabled: None, revision
) -> None:
    user = make_user(db_session, "key-revision@example.com")
    first = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    revision["value"] = "rev-2"
    second = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    assert first and second and first != second


def test_cache_key_changes_with_prompt_version(
    db_session: Session, enabled: None, revision, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.living_story as living_story

    user = make_user(db_session, "key-prompt@example.com")
    first = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    monkeypatch.setattr(living_story, "VERSION", "living-story-v3")
    assert scene_cache_key(db_session, user, input_mode=InputMode.TEXT) != first


def test_cache_key_changes_with_learner_context(
    db_session: Session, enabled: None, revision
) -> None:
    user = make_user(db_session, "key-learner@example.com")
    first = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    user.cefr_estimate = "B1"
    db_session.commit()
    assert scene_cache_key(db_session, user, input_mode=InputMode.TEXT) != first


def test_cache_key_is_none_without_the_engine(
    db_session: Session, enabled: None, revision, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "key-noengine@example.com")
    monkeypatch.setattr(
        journey_latency.settings, "ATELIER_STORY_ENGINE_ENABLED", False, raising=False
    )
    assert scene_cache_key(db_session, user, input_mode=InputMode.TEXT) is None


# ---------------------------------------------------------------------------
# 2. Gating
# ---------------------------------------------------------------------------


def test_prefetch_refused_when_the_flag_is_off(
    db_session: Session, enabled: None, revision, generated, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "gate-flag@example.com")
    monkeypatch.setattr(
        journey_latency.settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", False, raising=False
    )
    assert prefetch_enabled_for(user) is False
    assert prefetch_scene_for(db_session, user) == "skipped_disabled"
    assert generated["count"] == 0


def test_prefetch_refused_outside_the_cohort(
    db_session: Session, enabled: None, revision, generated, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.daily_journey as daily_journey

    user = make_user(db_session, "gate-cohort@example.com")
    monkeypatch.setattr(
        daily_journey.settings,
        "ATELIER_DAILY_JOURNEY_COHORT",
        "someone-else@example.com",
        raising=False,
    )
    assert prefetch_enabled_for(user) is False
    assert prefetch_scene_for(db_session, user) == "skipped_disabled"
    assert generated["count"] == 0


def test_prefetch_refused_when_the_story_engine_is_off(
    db_session: Session, enabled: None, revision, generated, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "gate-engine@example.com")
    monkeypatch.setattr(
        journey_latency.settings, "ATELIER_STORY_ENGINE_ENABLED", False, raising=False
    )
    assert prefetch_scene_for(db_session, user) == "skipped_disabled"
    assert generated["count"] == 0


def test_prefetch_respects_the_weekly_cost_guardrail(
    db_session: Session, enabled: None, revision, generated, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "gate-budget@example.com")
    monkeypatch.setattr(
        journey_latency.settings,
        "PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD",
        1.0,
        raising=False,
    )
    db_session.add(
        PilotEvent(
            user_id=user.id,
            event_type="journey_story_scene_cost",
            payload={},
            cost_usd=1.5,
            occurred_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    assert prefetch_scene_for(db_session, user) == "skipped_budget"
    assert generated["count"] == 0


# ---------------------------------------------------------------------------
# 3. Idempotency and staleness
# ---------------------------------------------------------------------------


def test_prefetch_is_idempotent_for_the_same_key(
    db_session: Session, enabled: None, revision, generated
) -> None:
    user = make_user(db_session, "idempotent@example.com")
    assert prefetch_scene_for(db_session, user) == "prefetched"
    assert prefetch_scene_for(db_session, user) == "cached"
    assert prefetch_scene_for(db_session, user) == "cached"
    assert generated["count"] == 1
    rows = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == PREFETCH_EVENT, PilotEvent.user_id == user.id)
    ).all()
    assert len(rows) == 1


def test_a_moved_story_revision_repays_and_discards_the_old_scene(
    db_session: Session, enabled: None, revision, generated
) -> None:
    user = make_user(db_session, "moved@example.com")
    assert prefetch_scene_for(db_session, user) == "prefetched"
    revision["value"] = "rev-2"
    # A different key is genuinely a different scene, so it is generated once.
    assert prefetch_scene_for(db_session, user) == "prefetched"
    assert generated["count"] == 2

    served = take_prefetched_scene(db_session, user)
    db_session.commit()
    assert served is not None
    discarded = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == PREFETCH_DISCARDED_EVENT, PilotEvent.user_id == user.id)
    ).all()
    # The rev-1 entry never reaches a learner; its spend is billed on the discard.
    assert len(discarded) == 1
    assert discarded[0].payload["reason"] == "stale_cache_key"
    assert discarded[0].cost_usd == pytest.approx(0.004)


def test_a_stale_prefetch_is_never_served(
    db_session: Session, enabled: None, revision, generated
) -> None:
    user = make_user(db_session, "stale@example.com")
    assert prefetch_scene_for(db_session, user) == "prefetched"
    revision["value"] = "rev-2"
    assert take_prefetched_scene(db_session, user) is None


def test_a_prefetch_is_served_exactly_once(
    db_session: Session, enabled: None, revision, generated
) -> None:
    user = make_user(db_session, "once@example.com")
    prefetch_scene_for(db_session, user)
    first = take_prefetched_scene(db_session, user)
    db_session.commit()
    assert first is not None
    assert take_prefetched_scene(db_session, user) is None
    consumed = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == PREFETCH_CONSUMED_EVENT, PilotEvent.user_id == user.id)
    ).all()
    assert len(consumed) == 1


def test_an_expired_prefetch_is_swept_and_billed(
    db_session: Session, enabled: None, revision, generated
) -> None:
    user = make_user(db_session, "expired@example.com")
    prefetch_scene_for(db_session, user)
    row = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == PREFETCH_EVENT, PilotEvent.user_id == user.id)
    ).one()
    row.occurred_at = datetime.now(UTC) - timedelta(days=5)
    db_session.commit()

    assert take_prefetched_scene(db_session, user) is None
    assert sweep_expired_prefetches(db_session) >= 1
    assert sweep_expired_prefetches(db_session) == 0
    discarded = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == PREFETCH_DISCARDED_EVENT, PilotEvent.user_id == user.id)
    ).all()
    assert [row.payload["reason"] for row in discarded] == ["expired"]
    assert discarded[0].cost_usd == pytest.approx(0.004)


def test_an_unreadable_prefetch_is_discarded_not_raised(
    db_session: Session, enabled: None, revision, generated
) -> None:
    user = make_user(db_session, "unreadable@example.com")
    prefetch_scene_for(db_session, user)
    row = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == PREFETCH_EVENT, PilotEvent.user_id == user.id)
    ).one()
    row.payload = {**row.payload, "brief": {"not": "a brief"}}
    db_session.commit()
    assert take_prefetched_scene(db_session, user) is None


def test_an_unavailable_provider_stores_nothing(
    db_session: Session, enabled: None, revision, generated
) -> None:
    user = make_user(db_session, "unavailable@example.com")
    generated["result"] = ContentUnavailable(reason="story_provider_failed")
    assert prefetch_scene_for(db_session, user) == "unavailable"
    assert (
        db_session.scalars(
            select(PilotEvent).where(PilotEvent.event_type == PREFETCH_EVENT, PilotEvent.user_id == user.id)
        ).all()
        == []
    )


# ---------------------------------------------------------------------------
# 4. The hot path through the journey service
# ---------------------------------------------------------------------------


def test_the_draft_serves_a_prefetched_scene_without_generating(
    db_session: Session, enabled: None, revision, generated, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_run_generation` must take the warm scene and never call the adapter."""

    from app.schemas.daily_journey import JourneyCreateRequest
    from app.services.daily_journey import DailyJourneyService
    from tests.test_daily_journey_state import build_adapters

    user = make_user(db_session, "hotpath@example.com")
    assert prefetch_scene_for(db_session, user) == "prefetched"

    adapter_calls = {"count": 0}

    class CountingContent:
        is_stub = True

        def describe_available_scenario(self, db, *, user, input_mode):
            return make_brief()

        def build_scenario_context(self, db, *, user, scenario_key=None, input_mode=None):
            adapter_calls["count"] += 1
            return ContentUnavailable(reason="should_not_be_called")

    service = DailyJourneyService(db_session, build_adapters(content=CountingContent()))
    try:
        service.create_journey(
            user,
            JourneyCreateRequest(
                mutation_id=uuid.uuid4().hex,
                timezone="Europe/Paris",
                budget_seconds=300,
                preferred_input_mode=InputMode.TEXT,
            ),
        )
    except Exception as exc:
        # Downstream planning may still refuse this synthetic brief; what this
        # test pins is that the *content adapter* was never asked to generate.
        assert exc is not None
    assert adapter_calls["count"] == 0
    assert service.draft_prefetch_hit is True
    assert generated["count"] == 1


# ---------------------------------------------------------------------------
# 5. Telemetry, the digest line and the gate
# ---------------------------------------------------------------------------


def _seed(db: Session, user: User, phase: str, seconds: float, **extra: Any) -> None:
    record_latency(db, user=user, phase=phase, seconds=seconds, **extra)
    db.commit()


def test_a_measured_phase_persists_one_row(db_session: Session) -> None:
    user = make_user(db_session, "measured@example.com")
    with measure_phase(db_session, user=user, phase=PHASE_DRAFT) as timing:
        timing.prefetch_hit = True
    rows = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == LATENCY_EVENT, PilotEvent.user_id == user.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["phase"] == PHASE_DRAFT
    assert rows[0].payload["prefetch_hit"] is True
    assert rows[0].payload["outcome"] == "ok"


def test_a_failed_phase_is_recorded_and_re_raised(db_session: Session) -> None:
    user = make_user(db_session, "measured-fail@example.com")
    with pytest.raises(RuntimeError):
        with measure_phase(db_session, user=user, phase=PHASE_RESPOND):
            raise RuntimeError("boom")
    row = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == LATENCY_EVENT, PilotEvent.user_id == user.id)
    ).one()
    assert row.payload["outcome"] == "failed"


def test_rollup_reports_percentiles_and_the_prefetch_hit_rate(
    db_session: Session,
) -> None:
    user = make_user(db_session, "rollup@example.com")
    for index in range(10):
        _seed(db_session, user, PHASE_DRAFT, 1.0 + index * 0.1, prefetch_hit=index < 8)
    for index in range(10):
        _seed(db_session, user, PHASE_RESPOND, 2.0 + index * 0.1)
        _seed(db_session, user, PHASE_RECAP, 0.2)

    today = _pilot_today()
    rollup = latency_rollup(db_session, today, user_id=user.id)
    draft = rollup["phases"][PHASE_DRAFT]
    assert draft["samples"] == 10
    assert draft["p50_seconds"] is not None
    assert draft["p95_seconds"] <= 2.0
    assert rollup["prefetch"]["draft_requests"] == 10
    assert rollup["prefetch"]["hit_rate"] == pytest.approx(0.8)

    verdict = evaluate_gate(rollup)
    assert verdict["status"] == "pass", verdict

    lines = format_latency_lines(rollup)
    assert lines[0].startswith("Journey latency")
    assert any("draft: n=10" in line for line in lines)
    assert any("served warm (80%)" in line for line in lines)
    assert lines[-1] == "  release gate: PASS"


def test_the_gate_fails_a_slow_draft(db_session: Session) -> None:
    user = make_user(db_session, "gate-slow@example.com")
    for _ in range(12):
        _seed(db_session, user, PHASE_DRAFT, 21.0, prefetch_hit=False)
        _seed(db_session, user, PHASE_RESPOND, 3.0)
        _seed(db_session, user, PHASE_RECAP, 0.2)
    rollup = latency_rollup(
        db_session, _pilot_today(), user_id=user.id
    )
    verdict = evaluate_gate(rollup)
    assert verdict["status"] == "fail"
    assert any("draft p95" in reason for reason in verdict["reasons"])
    assert any("prefetch hit rate" in reason for reason in verdict["reasons"])
    assert format_latency_lines(rollup)[-1].startswith("  release gate: FAIL")


def test_the_gate_refuses_to_pass_on_thin_data(db_session: Session) -> None:
    user = make_user(db_session, "gate-thin@example.com")
    _seed(db_session, user, PHASE_DRAFT, 0.2, prefetch_hit=True)
    rollup = latency_rollup(
        db_session, _pilot_today(), user_id=user.id
    )
    verdict = evaluate_gate(rollup)
    assert verdict["status"] == "insufficient_data"
    assert format_latency_lines(rollup)[-1].startswith(
        "  release gate: insufficient data"
    )


def test_the_digest_line_survives_an_empty_day(db_session: Session) -> None:
    user = make_user(db_session, "empty-day@example.com")
    rollup = latency_rollup(
        db_session, _pilot_today(), user_id=user.id
    )
    lines = format_latency_lines(rollup)
    assert "  draft: no measured requests" in lines
    assert "  prefetch: no measured drafts" in lines
