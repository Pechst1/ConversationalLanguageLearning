"""Journey observability and honest duration reporting (WP-11).

These tests hold three lines that matter more than event volume:

* a retried request never becomes a second completion,
* no learner utterance can reach telemetry under any key, and
* ``active_seconds`` is measured or ``None`` — never an estimate wearing a
  measurement's clothes.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import journey_events
from app.services.journey_contracts import JourneyEventName, effect_source_key
from app.services.journey_events import (
    JOURNEY_ENTITY_TYPE,
    MIN_DIGEST_SAMPLE,
    dedup_key,
    format_journey_digest,
    journey_daily_rollup,
    measure_journey_active_seconds,
    measure_journey_duration,
    provider_timer,
    record_generation_fallback,
    record_journey_event,
    record_provider_failed,
    record_resume_conflict,
    sanitize_metadata,
)
from app.services.pilot_events import PilotEventService, format_daily_digest

LEARNER_ANSWER = "Je voudrais un café en terrasse, s'il vous plaît."


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_events(db_session: Session):
    """Each test owns the ledger; the table is shared across the session engine."""

    db_session.query(PilotEvent).delete()
    db_session.commit()
    yield
    db_session.rollback()
    db_session.query(PilotEvent).delete()
    db_session.commit()


def make_user(db: Session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
    )
    db.add(user)
    db.flush()
    return user


def emit(
    db: Session,
    name: JourneyEventName,
    *,
    user_id,
    journey_id,
    at: datetime | None = None,
    **metadata,
) -> PilotEvent | None:
    """Emit exactly the way WP-02's ``_emit`` does, then pin the instant."""

    event = record_journey_event(
        db,
        event_name=str(name),
        user_id=user_id,
        source_key=effect_source_key(journey_id=journey_id, effect=str(name)),
        metadata={"journey_id": str(journey_id), **metadata},
    )
    if event is not None and at is not None:
        event.occurred_at = at
    return event


BASE = datetime(2026, 9, 5, 8, 0, tzinfo=UTC)


def seconds(offset: float) -> datetime:
    return BASE + timedelta(seconds=offset)


def build_journey(
    db: Session,
    user: User,
    *,
    journey_id=None,
    timezone: str = "Europe/Paris",
    finish: JourneyEventName | None = JourneyEventName.COMPLETED,
    start_offset: float = 0.0,
) -> str:
    """A realistic five-step café day: 264s of plan, real gaps between steps."""

    journey_id = journey_id or uuid.uuid4()
    common = {
        "timezone": timezone,
        "local_date": "2026-09-05",
        "level_band": "A1",
        "input_mode": "text",
        "budget_seconds": 300,
        "scenario_key": "order_at_cafe",
    }
    emit(db, JourneyEventName.CREATED, user_id=user.id, journey_id=journey_id,
         at=seconds(start_offset), **common)
    emit(db, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id,
         at=seconds(start_offset + 4), estimated_active_seconds=264, **common)
    plan = [("scene", 39), ("recall", 34), ("respond", 120), ("resolution", 52)]
    moment = start_offset + 4
    for ordinal, (kind, estimate) in enumerate(plan):
        moment += estimate
        emit(
            db,
            JourneyEventName.STEP_COMPLETED,
            user_id=user.id,
            journey_id=journey_id,
            at=seconds(moment),
            step_id=f"step-{ordinal}",
            step_kind=kind,
            ordinal=ordinal,
            estimated_seconds=estimate,
            **common,
        )
    if finish is not None:
        emit(db, finish, user_id=user.id, journey_id=journey_id, at=seconds(moment + 2),
             finish_kind="complete" if finish is JourneyEventName.COMPLETED else "early",
             **common)
    db.flush()
    return str(journey_id)


# --------------------------------------------------------------------------
# 1. The frozen call site
# --------------------------------------------------------------------------

def test_the_frozen_call_site_records_through_the_existing_pilot_ledger(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-callsite@example.com")
    journey_id = uuid.uuid4()

    event = record_journey_event(
        db_session,
        event_name=str(JourneyEventName.CREATED),
        user_id=user.id,
        source_key=effect_source_key(journey_id=journey_id, effect="journey_created"),
        metadata={"journey_id": str(journey_id), "level_band": "A1", "timezone": "Europe/Paris"},
    )

    assert isinstance(event, PilotEvent)
    assert event.event_type == "journey_created"
    assert event.entity_type == JOURNEY_ENTITY_TYPE
    assert event.entity_id == str(journey_id)
    assert event.payload["schema_version"] == journey_events.JOURNEY_EVENT_SCHEMA_VERSION
    assert event.payload["level_band"] == "A1"
    # It is a real PilotEvent row, not a parallel table.
    db_session.flush()
    assert db_session.query(PilotEvent).count() == 1


def test_recording_never_commits_the_callers_transaction(db_session: Session) -> None:
    """The state machine owns the transaction; telemetry may not close it."""

    user = make_user(db_session, "wp11-nocommit@example.com")
    db_session.commit()
    journey_id = uuid.uuid4()

    record_journey_event(
        db_session,
        event_name=str(JourneyEventName.STARTED),
        user_id=user.id,
        source_key=effect_source_key(journey_id=journey_id, effect="journey_started"),
        metadata={"journey_id": str(journey_id)},
    )
    db_session.rollback()

    assert db_session.query(PilotEvent).count() == 0


def test_an_unfrozen_event_name_is_refused_rather_than_invented(db_session: Session) -> None:
    user = make_user(db_session, "wp11-unknown@example.com")

    assert (
        record_journey_event(
            db_session,
            event_name="journey_vibes",
            user_id=user.id,
            source_key="journey:x:journey_vibes",
            metadata={},
        )
        is None
    )
    db_session.flush()
    assert db_session.query(PilotEvent).count() == 0


def test_every_frozen_event_name_is_recordable(db_session: Session) -> None:
    user = make_user(db_session, "wp11-allnames@example.com")
    journey_id = uuid.uuid4()
    for name in JourneyEventName:
        assert emit(db_session, name, user_id=user.id, journey_id=journey_id) is not None
    db_session.flush()
    stored = {row.event_type for row in db_session.query(PilotEvent).all()}
    assert stored == {str(name) for name in JourneyEventName}


# --------------------------------------------------------------------------
# 2. Deduplication
# --------------------------------------------------------------------------

def test_a_retried_finish_is_a_retry_not_a_second_completion(db_session: Session) -> None:
    user = make_user(db_session, "wp11-dupe@example.com")
    journey_id = uuid.uuid4()

    first = emit(db_session, JourneyEventName.COMPLETED, user_id=user.id, journey_id=journey_id,
                 finish_kind="complete")
    db_session.flush()
    second = emit(db_session, JourneyEventName.COMPLETED, user_id=user.id, journey_id=journey_id,
                  finish_kind="complete")
    db_session.flush()

    assert second is first
    assert db_session.query(PilotEvent).filter(
        PilotEvent.event_type == "journey_completed"
    ).count() == 1
    assert first.payload["repeats"] == 1
    assert "last_repeat_at" in first.payload


def test_duplicates_collapse_across_a_commit_boundary(db_session: Session) -> None:
    """A retry arriving as a separate HTTP request still cannot double-count."""

    user = make_user(db_session, "wp11-dupe-commit@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.COMPLETED, user_id=user.id, journey_id=journey_id)
    db_session.commit()
    emit(db_session, JourneyEventName.COMPLETED, user_id=user.id, journey_id=journey_id)
    db_session.commit()

    rows = db_session.query(PilotEvent).filter(
        PilotEvent.event_type == "journey_completed"
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["repeats"] == 1


def test_distinct_steps_and_help_kinds_stay_distinct(db_session: Session) -> None:
    """Dedup must not erase genuinely different observations."""

    user = make_user(db_session, "wp11-discriminators@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         step_id="step-0")
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         step_id="step-1")
    emit(db_session, JourneyEventName.HELP_USED, user_id=user.id, journey_id=journey_id,
         step_id="step-1", help_kind="hint")
    emit(db_session, JourneyEventName.HELP_USED, user_id=user.id, journey_id=journey_id,
         step_id="step-1", help_kind="translation")
    emit(db_session, JourneyEventName.HELP_USED, user_id=user.id, journey_id=journey_id,
         step_id="step-1", help_kind="hint")  # the duplicate
    db_session.flush()

    assert db_session.query(PilotEvent).filter(
        PilotEvent.event_type == "journey_step_completed"
    ).count() == 2
    assert db_session.query(PilotEvent).filter(
        PilotEvent.event_type == "journey_help_used"
    ).count() == 2


def test_two_journeys_never_share_a_dedup_identity(db_session: Session) -> None:
    user = make_user(db_session, "wp11-two-journeys@example.com")
    first, second = uuid.uuid4(), uuid.uuid4()

    emit(db_session, JourneyEventName.COMPLETED, user_id=user.id, journey_id=first)
    emit(db_session, JourneyEventName.COMPLETED, user_id=user.id, journey_id=second)
    db_session.flush()

    assert db_session.query(PilotEvent).filter(
        PilotEvent.event_type == "journey_completed"
    ).count() == 2


def test_another_learners_event_cannot_absorb_this_learners_completion(
    db_session: Session,
) -> None:
    """Dedup is scoped by journey identity, which is scoped by owner."""

    alice = make_user(db_session, "wp11-alice@example.com")
    bob = make_user(db_session, "wp11-bob@example.com")
    alice_journey, bob_journey = uuid.uuid4(), uuid.uuid4()

    emit(db_session, JourneyEventName.COMPLETED, user_id=alice.id, journey_id=alice_journey)
    emit(db_session, JourneyEventName.COMPLETED, user_id=bob.id, journey_id=bob_journey)
    db_session.flush()

    owners = {
        str(row.user_id): row.entity_id
        for row in db_session.query(PilotEvent).all()
    }
    assert owners == {str(alice.id): str(alice_journey), str(bob.id): str(bob_journey)}


def test_a_paused_journey_separates_repeats_once_a_revision_is_supplied(
    db_session: Session,
) -> None:
    """pause → resume → pause is two pauses when the revision distinguishes them."""

    user = make_user(db_session, "wp11-pause@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.PAUSED, user_id=user.id, journey_id=journey_id, revision=4)
    emit(db_session, JourneyEventName.PAUSED, user_id=user.id, journey_id=journey_id, revision=4)
    emit(db_session, JourneyEventName.PAUSED, user_id=user.id, journey_id=journey_id, revision=9)
    db_session.flush()

    rows = db_session.query(PilotEvent).filter(PilotEvent.event_type == "journey_paused").all()
    assert len(rows) == 2
    assert sorted(row.payload.get("repeats", 0) for row in rows) == [0, 1]


def test_dedup_key_is_the_source_key_plus_the_declared_discriminators() -> None:
    key = dedup_key(
        "journey_help_used",
        "journey:J1:journey_help_used",
        {"step_id": "S2", "help_kind": "hint"},
    )
    assert key == "journey:J1:journey_help_used|step_id=S2|help_kind=hint"
    assert dedup_key("journey_completed", "journey:J1:journey_completed", {"x": 1}) == (
        "journey:J1:journey_completed"
    )


# --------------------------------------------------------------------------
# 3. Payload discipline
# --------------------------------------------------------------------------

def test_a_learner_answer_can_never_appear_in_an_event_payload(db_session: Session) -> None:
    """The headline privacy guarantee, attempted under every allow-listed key."""

    user = make_user(db_session, "wp11-privacy@example.com")
    journey_id = uuid.uuid4()

    hostile = {
        "answer": LEARNER_ANSWER,
        "learner_text": LEARNER_ANSWER,
        "transcript": LEARNER_ANSWER,
        "email": user.email,
        "audio_url": "https://example.test/recording.mp3",
        "notes": "the learner mentioned their address",
    }
    # …and the same content pushed into keys that ARE allow-listed.
    for allowed in ("reason", "failure_reason", "provider", "content_version", "step_id",
                    "scenario_key", "level_band", "help_kind", "timezone", "local_date"):
        hostile[allowed] = LEARNER_ANSWER

    event = emit(
        db_session,
        JourneyEventName.STEP_COMPLETED,
        user_id=user.id,
        journey_id=journey_id,
        **hostile,
    )
    db_session.flush()

    serialized = repr(event.payload)
    assert LEARNER_ANSWER not in serialized
    assert "café" not in serialized
    assert user.email not in serialized
    assert "recording.mp3" not in serialized
    # Only the key names survive, so a producer mistake is visible without a leak.
    assert set(event.payload["dropped_metadata_keys"]) >= {"answer", "learner_text", "transcript"}
    for row in db_session.query(PilotEvent).all():
        assert LEARNER_ANSWER not in repr(row.payload)


def test_the_documented_fields_are_kept(db_session: Session) -> None:
    user = make_user(db_session, "wp11-fields@example.com")
    journey_id = uuid.uuid4()

    event = emit(
        db_session,
        JourneyEventName.STEP_COMPLETED,
        user_id=user.id,
        journey_id=journey_id,
        step_id="step-2",
        step_kind="respond",
        ordinal=2,
        level_band="A1",
        input_mode="voice",
        budget_seconds=300,
        estimated_seconds=120,
        assistance="translation",
        outcome="partially_met",
        evidence_ref="dj-abc123",
        cost_ref="atelier-gen-77",
        timezone="Pacific/Auckland",
        local_date="2026-09-05",
    )

    payload = event.payload
    assert payload["step_kind"] == "respond"
    assert payload["ordinal"] == 2
    assert payload["level_band"] == "A1"
    assert payload["input_mode"] == "voice"
    assert payload["budget_seconds"] == 300
    assert payload["estimated_seconds"] == 120
    assert payload["assistance"] == "translation"
    assert payload["outcome"] == "partially_met"
    assert payload["evidence_ref"] == "dj-abc123"
    assert payload["cost_ref"] == "atelier-gen-77"
    assert "dropped_metadata_keys" not in payload


def test_a_caller_cannot_forge_the_reserved_bookkeeping_fields(db_session: Session) -> None:
    user = make_user(db_session, "wp11-reserved@example.com")
    journey_id = uuid.uuid4()

    event = emit(
        db_session,
        JourneyEventName.COMPLETED,
        user_id=user.id,
        journey_id=journey_id,
        repeats=99,
        dedup_key="anything",
        schema_version=42,
    )
    assert event.payload.get("repeats") is None
    assert event.payload["schema_version"] == journey_events.JOURNEY_EVENT_SCHEMA_VERSION
    assert event.payload["dedup_key"].startswith("journey:")


def test_sanitize_metadata_reports_names_never_values() -> None:
    clean, dropped = sanitize_metadata({"answer": LEARNER_ANSWER, "ordinal": 3, "outcome": "met"})
    assert clean == {"ordinal": 3, "outcome": "met"}
    assert dropped == ["answer"]


# --------------------------------------------------------------------------
# 4. Duration measurement
# --------------------------------------------------------------------------

def test_active_seconds_is_measured_from_the_servers_own_timestamps(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-duration@example.com")
    journey_id = build_journey(db_session, user)

    measurement = measure_journey_duration(db_session, journey_id=journey_id)

    # 39 + 34 + 120 + 52 step gaps, then 2s to the finish event.
    assert measurement.measurable is True
    assert measurement.active_seconds == 247
    assert measurement.counted_segments == 5
    assert measurement.idle_excluded_seconds == 0
    assert measurement.away_excluded_seconds == 0
    # The 4s of plan generation is preparation, not learner time.
    assert measurement.preparation_wait_seconds == 4.0


def test_time_away_while_paused_is_excluded_entirely(db_session: Session) -> None:
    user = make_user(db_session, "wp11-paused-gap@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id, at=seconds(0))
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(30), step_id="step-0", estimated_seconds=39)
    emit(db_session, JourneyEventName.PAUSED, user_id=user.id, journey_id=journey_id,
         at=seconds(40), revision=3)
    # Four hours in the background.
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(40 + 4 * 3600 + 25), step_id="step-1", estimated_seconds=34)
    db_session.flush()

    measurement = measure_journey_duration(db_session, journey_id=journey_id)

    assert measurement.active_seconds == 30 + 10
    assert measurement.away_excluded_seconds == 4 * 3600 + 25
    assert measurement.idle_excluded_seconds == 0


def test_an_idle_stretch_is_capped_not_counted_as_work(db_session: Session) -> None:
    """A learner who walks away without pausing does not earn 20 minutes of study."""

    user = make_user(db_session, "wp11-idle@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id, at=seconds(0))
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(1200), step_id="step-0", step_kind="recall", estimated_seconds=34)
    db_session.flush()

    measurement = measure_journey_duration(db_session, journey_id=journey_id)

    # 34s estimate → a 102s ceiling (raised to the 60s floor is not needed here).
    assert measurement.active_seconds == 102
    assert measurement.idle_excluded_seconds == 1200 - 102


def test_provider_waiting_is_reported_apart_from_learner_time(db_session: Session) -> None:
    """A slow provider must be distinguishable from a slow learner."""

    user = make_user(db_session, "wp11-provider@example.com")
    slow, quick = uuid.uuid4(), uuid.uuid4()

    for journey_id, wait_ms in ((slow, 9000.0), (quick, 0.0)):
        emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id,
             at=seconds(0))
        emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
             at=seconds(30), step_id="step-0", estimated_seconds=120,
             provider_wait_ms=wait_ms)
    db_session.flush()

    slow_measure = measure_journey_duration(db_session, journey_id=slow)
    quick_measure = measure_journey_duration(db_session, journey_id=quick)

    assert quick_measure.active_seconds == 30
    assert quick_measure.provider_wait_seconds == 0.0
    # Same 30 seconds of wall clock, but 9 of them were the model, not the learner.
    assert slow_measure.active_seconds == 21
    assert slow_measure.provider_wait_seconds == 9.0


def test_client_timings_are_diagnostic_and_cannot_move_active_seconds(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-client@example.com")
    honest, lying = uuid.uuid4(), uuid.uuid4()

    for journey_id, client in (
        (honest, None),
        (lying, {"foreground_ms": 5_000, "background_ms": 999_000, "idle_ms": 900_000}),
    ):
        emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id,
             at=seconds(0))
        extra = {"client": client} if client else {}
        emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
             at=seconds(45), step_id="step-0", estimated_seconds=120, **extra)
    db_session.flush()

    honest_measure = measure_journey_duration(db_session, journey_id=honest)
    lying_measure = measure_journey_duration(db_session, journey_id=lying)

    assert honest_measure.active_seconds == lying_measure.active_seconds == 45
    # Kept, visible, and never used for the number that reaches the recap.
    assert lying_measure.client_reported == {
        "background_ms": 999_000.0,
        "foreground_ms": 5_000.0,
        "idle_ms": 900_000.0,
    }
    assert honest_measure.client_reported == {}


def test_unmeasurable_stays_none_and_never_becomes_the_estimate(db_session: Session) -> None:
    user = make_user(db_session, "wp11-unmeasurable@example.com")
    empty = uuid.uuid4()
    never_started = uuid.uuid4()

    assert measure_journey_active_seconds(db_session, journey_id=empty) is None
    assert measure_journey_duration(db_session, journey_id=empty).reason == "no_events"

    emit(db_session, JourneyEventName.CREATED, user_id=user.id, journey_id=never_started,
         at=seconds(0), estimated_active_seconds=264)
    emit(db_session, JourneyEventName.GENERATION_FALLBACK, user_id=user.id,
         journey_id=never_started, at=seconds(2), reason="provider_timeout")
    db_session.flush()

    measurement = measure_journey_duration(db_session, journey_id=never_started)
    # There is a plan estimate on the row; it must not be borrowed.
    assert measurement.active_seconds is None
    assert measurement.measurable is False


def test_the_finish_instant_closes_the_last_open_segment(db_session: Session) -> None:
    user = make_user(db_session, "wp11-until@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id, at=seconds(0))
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(60), step_id="step-0", estimated_seconds=120)
    db_session.flush()

    assert measure_journey_active_seconds(db_session, journey_id=journey_id) == 60
    assert (
        measure_journey_active_seconds(db_session, journey_id=journey_id, until=seconds(95))
        == 95
    )


def test_insertion_order_cannot_distort_an_interval(db_session: Session) -> None:
    """Events are sequenced by their instant, not by the order rows were added."""

    user = make_user(db_session, "wp11-order@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id, at=seconds(0))
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(50), step_id="step-0", estimated_seconds=120)
    late = emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id,
                journey_id=journey_id, step_id="step-1", estimated_seconds=34)
    late.occurred_at = seconds(20)  # written last, happened second
    db_session.flush()

    measurement = measure_journey_duration(db_session, journey_id=journey_id)
    assert measurement.active_seconds == 50
    assert measurement.counted_segments == 2


def test_a_finish_boundary_before_the_last_event_contributes_nothing(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-skew@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id, at=seconds(0))
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(50), step_id="step-0", estimated_seconds=120)
    db_session.flush()

    measurement = measure_journey_duration(db_session, journey_id=journey_id, until=seconds(30))
    assert measurement.skewed_segments == 1
    assert measurement.active_seconds == 50


def test_provider_timer_measures_a_call_in_milliseconds() -> None:
    with provider_timer() as wait:
        pass
    assert wait.elapsed_ms >= 0.0


# --------------------------------------------------------------------------
# 5. Typed constructors for the unproduced events
# --------------------------------------------------------------------------

def test_the_typed_constructors_write_the_frozen_names(db_session: Session) -> None:
    user = make_user(db_session, "wp11-constructors@example.com")
    journey_id = uuid.uuid4()

    fallback = record_generation_fallback(
        db_session,
        user_id=user.id,
        journey_id=journey_id,
        reason="model_output_unusable",
        scenario_key="order_at_cafe",
        provider="openai",
        provider_wait_ms=4200.0,
        attempt=2,
    )
    failed = record_provider_failed(
        db_session,
        user_id=user.id,
        journey_id=journey_id,
        provider="openai",
        failure_reason="TimeoutError",
        provider_wait_ms=30000.0,
        attempt=1,
    )
    conflict = record_resume_conflict(
        db_session,
        user_id=user.id,
        journey_id=journey_id,
        conflict_kind="version_conflict",
        expected_revision=3,
        current_revision=7,
    )
    db_session.flush()

    assert fallback.event_type == "journey_generation_fallback"
    assert fallback.payload["authored_fallback"] is True
    assert fallback.payload["provider_wait_ms"] == 4200.0
    assert failed.event_type == "journey_provider_failed"
    assert failed.payload["failure_reason"] == "TimeoutError"
    assert conflict.event_type == "journey_resume_conflict"
    assert conflict.payload["current_revision"] == 7


# --------------------------------------------------------------------------
# 6. Digest
# --------------------------------------------------------------------------

def test_the_digest_reconstructs_a_sample_day_without_double_counting_retries(
    db_session: Session,
) -> None:
    day = date(2026, 9, 5)
    users = [make_user(db_session, f"wp11-day-{index}@example.com") for index in range(6)]

    for index, user in enumerate(users[:5]):
        build_journey(db_session, user, start_offset=index * 600)
    # One learner stops early and asks for help twice.
    early_user = users[5]
    early_journey = uuid.uuid4()
    common = {"timezone": "Europe/Paris", "local_date": "2026-09-05", "level_band": "A1"}
    emit(db_session, JourneyEventName.CREATED, user_id=early_user.id, journey_id=early_journey,
         at=seconds(4000), **common)
    emit(db_session, JourneyEventName.STARTED, user_id=early_user.id, journey_id=early_journey,
         at=seconds(4002), **common)
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=early_user.id,
         journey_id=early_journey, at=seconds(4050), step_id="step-0", step_kind="scene",
         ordinal=0, estimated_seconds=39, **common)
    emit(db_session, JourneyEventName.HELP_USED, user_id=early_user.id, journey_id=early_journey,
         at=seconds(4060), step_id="step-1", help_kind="hint", **common)
    emit(db_session, JourneyEventName.HELP_USED, user_id=early_user.id, journey_id=early_journey,
         at=seconds(4065), step_id="step-1", help_kind="translation", **common)
    emit(db_session, JourneyEventName.ENDED_EARLY, user_id=early_user.id,
         journey_id=early_journey, at=seconds(4090), finish_kind="early", **common)
    # Three retried requests for the same completion.
    for _ in range(3):
        emit(db_session, JourneyEventName.ENDED_EARLY, user_id=early_user.id,
             journey_id=early_journey, finish_kind="early", **common)
    db_session.commit()

    report = journey_daily_rollup(db_session, day)

    assert report["sample"]["journeys"] == 6
    assert report["sample"]["learners"] == 6
    assert report["sample"]["insufficient_data"] is False
    assert report["funnel"] == {
        "denominator": 6,
        "created": 6,
        "started": 6,
        "completed": 5,
        "ended_early": 1,
        "still_open": 0,
        "completion_rate": pytest.approx(0.8333, abs=1e-4),
        "early_stop_rate": pytest.approx(0.1667, abs=1e-4),
    }
    assert report["reliability"]["duplicate_requests_collapsed"] == 3
    assert report["help"]["events"] == 2
    assert report["help"]["journeys_using_help"] == 1
    assert report["help"]["by_kind"] == {"hint": 1, "translation": 1}
    assert report["step_drop_off"]["by_ordinal"][0]["journeys_completing_step"] == 6
    assert report["step_drop_off"]["by_ordinal"][-1]["journeys_completing_step"] == 5
    assert report["active_duration"]["measured"] == 6
    assert report["active_duration"]["seconds"]["p50"] == 247


def test_a_thin_day_is_reported_as_insufficient_data_not_as_a_rate(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-thin@example.com")
    build_journey(db_session, user)
    db_session.commit()

    report = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert report["sample"]["insufficient_data"] is True
    assert report["sample"]["minimum_for_rates"] == MIN_DIGEST_SAMPLE
    assert report["funnel"]["completion_rate"] is None
    assert report["funnel"]["completed"] == 1  # raw counts still shown
    digest = "\n".join(format_journey_digest(report))
    assert "INSUFFICIENT DATA" in digest
    assert "n=1 started" in digest


def test_an_empty_day_is_empty_not_broken(db_session: Session) -> None:
    report = journey_daily_rollup(db_session, date(2026, 9, 5))
    assert report["sample"] == {
        "journeys": 0,
        "learners": 0,
        "events": 0,
        "events_without_a_learner": 0,
        "events_without_a_journey": 0,
        "minimum_for_rates": MIN_DIGEST_SAMPLE,
        "insufficient_data": True,
    }
    assert report["active_duration"]["measured"] == 0
    assert "none measurable" in "\n".join(format_journey_digest(report))


def test_a_partial_day_counts_the_journey_that_is_still_open(db_session: Session) -> None:
    user = make_user(db_session, "wp11-partial@example.com")
    build_journey(db_session, user, finish=None)
    db_session.commit()

    report = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert report["funnel"]["started"] == 1
    assert report["funnel"]["completed"] == 0
    assert report["funnel"]["still_open"] == 1
    # Nothing finished, so there is no completed-journey duration to report.
    assert report["active_duration"]["denominator"] == 0
    assert report["active_duration"]["measured"] == 0


def test_unknown_cost_is_reported_as_unknown_never_as_zero(db_session: Session) -> None:
    user = make_user(db_session, "wp11-cost@example.com")
    journey_id = uuid.uuid4()
    common = {"timezone": "Europe/Paris"}

    emit(db_session, JourneyEventName.CREATED, user_id=user.id, journey_id=journey_id,
         at=seconds(0), **common)
    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id,
         at=seconds(3), cost_usd=0.0214, cost_ref="journey-gen-1", **common)
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(60), step_id="step-0", **common)
    db_session.commit()

    report = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert report["cost"]["events_with_known_cost"] == 1
    assert report["cost"]["events_with_unknown_cost"] == 2
    assert report["cost"]["known_cost_usd"] == pytest.approx(0.0214)
    assert report["cost"]["coverage"] == pytest.approx(1 / 3, abs=1e-4)
    digest = "\n".join(format_journey_digest(report))
    assert "1 known / 2 unknown" in digest
    assert "unknown is not zero" in digest


def test_provider_waiting_appears_in_the_digest_with_its_denominator(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-digest-wait@example.com")
    journey_id = uuid.uuid4()

    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=journey_id,
         at=seconds(0), timezone="Europe/Paris")
    emit(db_session, JourneyEventName.STEP_COMPLETED, user_id=user.id, journey_id=journey_id,
         at=seconds(40), step_id="step-0", provider_wait_ms=12500.0, timezone="Europe/Paris")
    db_session.commit()

    report = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert report["provider_wait"]["events_with_measurement"] == 1
    assert report["provider_wait"]["events_without_measurement"] == 1
    assert report["provider_wait"]["total_seconds"] == pytest.approx(12.5)
    assert "median 12500ms" in "\n".join(format_journey_digest(report))


# --------------------------------------------------------------------------
# 7. Day and timezone attribution
# --------------------------------------------------------------------------

def test_a_day_is_the_learners_day_in_the_journeys_own_timezone(
    db_session: Session,
) -> None:
    """20:30 UTC is still 5 September in Paris and already 6 September in Auckland."""

    paris_user = make_user(db_session, "wp11-paris@example.com")
    auckland_user = make_user(db_session, "wp11-auckland@example.com")
    instant = datetime(2026, 9, 5, 20, 30, tzinfo=UTC)

    emit(db_session, JourneyEventName.STARTED, user_id=paris_user.id,
         journey_id=uuid.uuid4(), at=instant, timezone="Europe/Paris")
    emit(db_session, JourneyEventName.STARTED, user_id=auckland_user.id,
         journey_id=uuid.uuid4(), at=instant, timezone="Pacific/Auckland")
    db_session.commit()

    fifth = journey_daily_rollup(db_session, date(2026, 9, 5))
    sixth = journey_daily_rollup(db_session, date(2026, 9, 6))

    assert fifth["sample"]["events"] == 1
    assert fifth["sample"]["learners"] == 1
    assert sixth["sample"]["events"] == 1
    assert sixth["sample"]["learners"] == 1
    assert fifth["attribution"]["events_attributed_by_fallback_zone"] == 0


def test_an_event_without_a_timezone_snapshot_is_counted_as_such(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-nozone@example.com")
    emit(db_session, JourneyEventName.STARTED, user_id=user.id, journey_id=uuid.uuid4(),
         at=datetime(2026, 9, 5, 12, 0, tzinfo=UTC))
    db_session.commit()

    report = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert report["sample"]["events"] == 1
    assert report["attribution"]["events_attributed_by_fallback_zone"] == 1
    assert "fell back to Europe/Berlin" in "\n".join(format_journey_digest(report))


def test_an_event_written_by_another_producer_still_counts(db_session: Session) -> None:
    """WP-03 already writes fallback/provider events with its own entity type.

    Those rows carry no journey id, so they must count for reliability without
    inflating the funnel or crashing the day.
    """

    user = make_user(db_session, "wp11-foreign@example.com")
    event = PilotEventService(db_session).record(
        "journey_generation_fallback",
        user_id=user.id,
        entity_type="daily_journey_content",
        entity_id="order_at_cafe",
        payload={"attempts": 3, "rejections": ["attempt 1: unusable model output"]},
    )
    event.occurred_at = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
    db_session.commit()

    report = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert report["reliability"]["generation_fallbacks"] == 1
    assert report["sample"]["events_without_a_journey"] == 1
    assert report["sample"]["journeys"] == 0
    assert report["funnel"]["created"] == 0
    assert report["cost"]["events_with_unknown_cost"] == 1


def test_a_nonsense_timezone_is_dropped_rather_than_trusted(db_session: Session) -> None:
    user = make_user(db_session, "wp11-badzone@example.com")
    event = emit(db_session, JourneyEventName.STARTED, user_id=user.id,
                 journey_id=uuid.uuid4(), at=seconds(0), timezone="Mars/Olympus Mons")
    db_session.flush()
    assert "timezone" not in event.payload
    assert "timezone" in event.payload["dropped_metadata_keys"]


# --------------------------------------------------------------------------
# 8. Ownership, deletion, and backward compatibility
# --------------------------------------------------------------------------

def test_a_rollup_filtered_to_one_learner_excludes_another_learners_journey(
    db_session: Session,
) -> None:
    alice = make_user(db_session, "wp11-owner-a@example.com")
    bob = make_user(db_session, "wp11-owner-b@example.com")
    build_journey(db_session, alice)
    build_journey(db_session, bob, start_offset=900)
    db_session.commit()

    only_alice = journey_daily_rollup(db_session, date(2026, 9, 5), user_id=alice.id)
    both = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert only_alice["sample"]["journeys"] == 1
    assert only_alice["funnel"]["completed"] == 1
    assert both["sample"]["journeys"] == 2


def test_a_deleted_learners_events_survive_and_are_counted_without_an_owner(
    db_session: Session,
) -> None:
    """``pilot_events.user_id`` is ON DELETE SET NULL; the day must still add up."""

    user = make_user(db_session, "wp11-deleted@example.com")
    journey_id = build_journey(db_session, user)
    db_session.commit()

    for row in db_session.query(PilotEvent).all():
        row.user_id = None
    db_session.commit()

    report = journey_daily_rollup(db_session, date(2026, 9, 5))

    assert report["sample"]["learners"] == 0
    assert report["sample"]["events_without_a_learner"] == 7
    assert report["funnel"]["completed"] == 1
    # The duration evidence is still reconstructable from the journey identity.
    assert measure_journey_active_seconds(db_session, journey_id=journey_id) == 247


def test_the_existing_pilot_rollup_and_digest_still_work(db_session: Session) -> None:
    """Non-journey pilot reporting is unchanged and gains an additive section."""

    user = make_user(db_session, "wp11-backcompat@example.com")
    service = PilotEventService(db_session)
    legacy = service.record("plan_started", user_id=user.id, entity_type="atelier")
    legacy.occurred_at = datetime(2026, 9, 5, 9, 30, tzinfo=UTC)
    crash = service.record("client_crash", user_id=user.id, entity_type="client", cost_usd=0.01)
    crash.occurred_at = datetime(2026, 9, 5, 9, 31, tzinfo=UTC)
    build_journey(db_session, user)
    db_session.commit()

    report = service.daily_rollup(date(2026, 9, 5), user_id=user.id)

    assert report["users"][0]["events"]["plan_started"] == 1
    assert report["users"][0]["events"]["client_crash"] == 1
    assert report["totals"]["failures"] == 1
    assert report["totals"]["cost_usd"] == pytest.approx(0.01)
    # The journey events are ordinary pilot events too.
    assert report["users"][0]["events"]["journey_completed"] == 1
    assert report["journey"]["funnel"]["completed"] == 1

    digest = format_daily_digest(report)
    assert "wp11-backcompat@example.com" in digest
    assert "Daily journey · 2026-09-05" in digest
    assert LEARNER_ANSWER not in digest


def test_a_journey_provider_failure_counts_as_a_failure_in_the_existing_totals(
    db_session: Session,
) -> None:
    user = make_user(db_session, "wp11-failures@example.com")
    failure = record_provider_failed(
        db_session,
        user_id=user.id,
        journey_id=uuid.uuid4(),
        provider="openai",
        failure_reason="TimeoutError",
    )
    berlin_noon = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
    failure.occurred_at = berlin_noon
    db_session.commit()

    report = PilotEventService(db_session).daily_rollup(date(2026, 9, 5), user_id=user.id)
    assert report["totals"]["failures"] == 1
