"""State-machine behaviour: dates, timezones, claims and recovery (WP-02).

These exercise the service directly so the clock can be frozen. HTTP-level
behaviour lives in ``tests/test_daily_journey_api.py``.
"""
from __future__ import annotations

import importlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.services.daily_journey as journey_module
from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User
from app.schemas.daily_journey import JourneyCreateRequest, JourneyFinishRequest
from app.services import journey_conversation, journey_planner
from app.services.daily_journey import (
    DailyJourneyService,
    local_date_for,
    resolve_timezone,
)
from app.services.daily_journey_adapters import (
    JourneyAdapters,
    _MissingCapabilitiesAdapter,
    _MissingContentAdapter,
    _MissingEventsAdapter,
    _MissingLearningAdapter,
)
from app.services.journey_contracts import (
    MAX_RESPOND_TURNS,
    ContentUnavailable,
    InputMode,
)


def build_adapters(**overrides: Any) -> JourneyAdapters:
    members: dict[str, Any] = {
        "content": _MissingContentAdapter(),
        # WP-04 has landed and there is no planner stub: the real planner is
        # always the one under test.
        "planner": journey_planner,
        "learning": _MissingLearningAdapter(),
        "conversation": journey_conversation,
        "capabilities": _MissingCapabilitiesAdapter(),
        "events": _MissingEventsAdapter(),
    }
    members.update(overrides)
    return JourneyAdapters(**members)


class HealthyPreviewFailingGeneration:
    """Preview is provider-free and works; the full brief cannot be built."""

    is_stub = True

    def describe_available_scenario(self, db: Any, *, user: Any, input_mode: Any) -> Any:
        return _MissingContentAdapter().build_scenario_context(
            db, user=user, input_mode=input_mode
        )

    def build_scenario_context(
        self, db: Any, *, user: Any, scenario_key: Any = None, input_mode: Any = None
    ) -> ContentUnavailable:
        return ContentUnavailable(reason="provider_timeout", retry_after_seconds=30)


@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        journey_module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        journey_module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False
    )


def make_user(db: Session, email: str, *, native_language: str = "en") -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="x",
        native_language=native_language,
        target_language="fr",
        proficiency_level="beginner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def correct_recall_input(db: Session, step_id: str) -> dict[str, Any]:
    """The right answer, read from the private task no client ever receives."""

    from app.db.models.daily_journey import DailyJourneyStep

    step = db.get(DailyJourneyStep, uuid.UUID(step_id))
    assert step is not None
    task = dict(step.private_task or {}).get("recall_task", {})
    if task.get("correct_option_id"):
        return {"mode": "choice", "option_id": task["correct_option_id"]}
    if task.get("correct_tile_order"):
        return {"mode": "tiles", "tile_ids": list(task["correct_tile_order"])}
    accepted = task.get("accepted_answers") or [""]
    return {"mode": "text", "text": accepted[0]}


def _step_model():
    from app.db.models.daily_journey import DailyJourneyStep

    return DailyJourneyStep


def _private_task(db: Session, step_id: str) -> dict[str, Any]:
    step = db.get(_step_model(), uuid.UUID(step_id))
    assert step is not None
    return dict(step.private_task or {})


def _response_task(payload: dict[str, Any]):
    from app.services.daily_journey import _response_task_from_json

    return _response_task_from_json(payload)


def create_request(timezone: str = "Europe/Paris") -> JourneyCreateRequest:
    return JourneyCreateRequest(
        mutation_id=uuid.uuid4().hex,
        timezone=timezone,
        budget_seconds=300,
        preferred_input_mode=InputMode.TEXT,
    )


def freeze(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    monkeypatch.setattr(journey_module, "_utcnow", lambda: moment)


# ---------------------------------------------------------------------------
# Timezone and local date
# ---------------------------------------------------------------------------


def test_an_unknown_timezone_falls_back_to_utc_not_to_a_hardcoded_city() -> None:
    assert resolve_timezone("Europe/Paris") == "Europe/Paris"
    assert resolve_timezone("Mars/Olympus_Mons") == "UTC"
    assert resolve_timezone("") == "UTC"
    assert resolve_timezone(None) == "UTC"
    assert resolve_timezone("not a zone") == "UTC"


def test_local_date_follows_the_learners_zone_not_the_servers() -> None:
    instant = datetime(2026, 9, 5, 23, 30, tzinfo=UTC)
    assert local_date_for("UTC", now=instant).isoformat() == "2026-09-05"
    assert local_date_for("Pacific/Auckland", now=instant).isoformat() == "2026-09-06"
    assert local_date_for("America/Los_Angeles", now=instant).isoformat() == "2026-09-05"


def test_local_date_is_stable_across_a_dst_transition() -> None:
    # Europe/Paris springs forward at 01:00 UTC on 2026-03-29.
    before = datetime(2026, 3, 29, 0, 30, tzinfo=UTC)
    after = datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    assert local_date_for("Europe/Paris", now=before).isoformat() == "2026-03-29"
    assert local_date_for("Europe/Paris", now=after).isoformat() == "2026-03-29"


def test_yesterdays_active_journey_resumes_before_today_is_created(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "state-midnight@example.com")
    service = DailyJourneyService(db_session, build_adapters())

    yesterday = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)
    freeze(monkeypatch, yesterday)
    first, code = service.create_journey(user, create_request())
    assert code == 201
    assert first.local_date.isoformat() == "2026-09-04"

    # Midnight passes. Nothing is silently reset.
    freeze(monkeypatch, yesterday + timedelta(days=1))
    envelope = service.get_today(user)
    assert envelope.local_date.isoformat() == "2026-09-05"
    assert envelope.journey is not None
    assert envelope.journey.id == first.id
    assert envelope.journey.local_date.isoformat() == "2026-09-04"
    assert envelope.available is None

    second, code = service.create_journey(user, create_request())
    assert code == 200
    assert second.id == first.id
    assert [step.id for step in second.steps] == [step.id for step in first.steps]


def test_todays_journey_is_created_once_yesterdays_is_finished(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "state-nextday@example.com")
    service = DailyJourneyService(db_session, build_adapters())

    freeze(monkeypatch, datetime(2026, 9, 4, 18, 0, tzinfo=UTC))
    first, _ = service.create_journey(user, create_request())
    service.finish(
        user,
        uuid.UUID(first.id),
        JourneyFinishRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=first.revision,
            finish_kind="early",
        ),
    )

    freeze(monkeypatch, datetime(2026, 9, 5, 8, 0, tzinfo=UTC))
    second, code = service.create_journey(user, create_request())
    assert code == 201
    assert second.id != first.id
    assert second.local_date.isoformat() == "2026-09-05"

    # A second create on the same date returns the same journey, not a third one.
    third, code = service.create_journey(user, create_request())
    assert code == 200
    assert third.id == second.id
    assert db_session.query(DailyJourney).filter(DailyJourney.user_id == user.id).count() == 2


def test_a_timezone_change_never_rekeys_an_open_journey(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "state-travel@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    freeze(monkeypatch, datetime(2026, 9, 5, 12, 0, tzinfo=UTC))

    first, _ = service.create_journey(user, create_request("Europe/Paris"))
    moved, code = service.create_journey(user, create_request("Pacific/Auckland"))

    assert code == 200
    assert moved.id == first.id
    assert moved.timezone == "Europe/Paris"
    assert moved.local_date == first.local_date
    assert db_session.query(DailyJourney).filter(DailyJourney.user_id == user.id).count() == 1


# ---------------------------------------------------------------------------
# Generation claims and recovery
# ---------------------------------------------------------------------------


def test_failed_generation_is_honestly_unavailable_and_retry_reuses_the_id(
    db_session: Session, enabled: None
) -> None:
    user = make_user(db_session, "state-unavailable@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(content=HealthyPreviewFailingGeneration())
    )

    snapshot, code = service.create_journey(user, create_request())
    assert code == 200
    assert snapshot.status == "unavailable"
    assert snapshot.steps == []
    assert snapshot.retry is not None
    assert snapshot.retry.allowed is True
    assert snapshot.retry.after_seconds == 30

    row = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert row is not None and row.unavailable_reason == "provider_timeout"

    # The content service recovers; the retry reuses the same journey id.
    from app.schemas.daily_journey import JourneyRetryRequest

    healthy = DailyJourneyService(db_session, build_adapters())
    recovered, code = healthy.retry_journey(
        user,
        uuid.UUID(snapshot.id),
        JourneyRetryRequest(mutation_id=uuid.uuid4().hex),
    )
    assert code == 201
    assert recovered.id == snapshot.id
    assert recovered.status == "active"
    assert len(recovered.steps) == 4


def test_an_expired_generation_claim_is_recoverable(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "state-claim@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    now = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    snapshot, _ = service.create_journey(user, create_request())

    # Simulate a worker that crashed mid-generation.
    row = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert row is not None
    row.status = "preparing"
    row.generation_claim_id = uuid.uuid4().hex
    row.generation_claimed_at = now
    db_session.commit()

    # A duplicate create while the claim is live is told to wait.
    waiting, code = service.create_journey(user, create_request())
    assert code == 202
    assert waiting.status == "preparing"
    assert waiting.retry is not None and waiting.retry.allowed is True

    # Once the claim expires, the same journey id is prepared again.
    freeze(
        monkeypatch,
        now + timedelta(seconds=journey_module.GENERATION_CLAIM_TTL_SECONDS + 5),
    )
    recovered, code = service.create_journey(user, create_request())
    assert code == 200
    assert recovered.id == snapshot.id
    assert recovered.status == "active"
    # Step ids survive the recovery: a retry never re-plans an existing plan.
    assert [step.id for step in recovered.steps] == [step.id for step in snapshot.steps]


def test_bounded_retries_stop_promising_a_journey_that_cannot_be_built(
    db_session: Session, enabled: None
) -> None:
    from fastapi import HTTPException

    from app.schemas.daily_journey import JourneyRetryRequest

    user = make_user(db_session, "state-bounded@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(content=HealthyPreviewFailingGeneration())
    )
    snapshot, _ = service.create_journey(user, create_request())
    journey_id = uuid.UUID(snapshot.id)

    last = snapshot
    for _ in range(journey_module.MAX_GENERATION_ATTEMPTS):
        try:
            last, _ = service.retry_journey(
                user, journey_id, JourneyRetryRequest(mutation_id=uuid.uuid4().hex)
            )
        except HTTPException as exc:
            assert exc.status_code == 503
            assert exc.detail["code"] == "generation_unavailable"
            break
    else:  # pragma: no cover - the loop must hit the bound
        pytest.fail("retries were not bounded")

    row = db_session.get(DailyJourney, journey_id)
    assert row is not None
    assert row.status == "unavailable"
    assert row.generation_attempts >= journey_module.MAX_GENERATION_ATTEMPTS


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_only_one_open_journey_per_learner_is_storable(
    db_session: Session, enabled: None
) -> None:
    """The partial unique index, exercised on the test database.

    NOTE: this proves the SQLite partial index. The PostgreSQL
    ``postgresql_where`` variant is not exercised here — see the WP-02 handoff.
    """

    user = make_user(db_session, "state-oneopen@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    first, _ = service.create_journey(user, create_request())

    intruder = DailyJourney(
        user_id=user.id,
        local_date=datetime(2026, 1, 1).date(),
        timezone="UTC",
        status="active",
        revision=1,
        scenario_snapshot={},
    )
    db_session.add(intruder)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert (
        db_session.query(DailyJourney).filter(DailyJourney.user_id == user.id).count()
        == 1
    )
    assert db_session.get(DailyJourney, uuid.UUID(first.id)) is not None


def test_one_journey_per_learner_per_local_date_is_storable(
    db_session: Session, enabled: None
) -> None:
    user = make_user(db_session, "state-onedate@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    first, _ = service.create_journey(user, create_request())
    service.finish(
        user,
        uuid.UUID(first.id),
        JourneyFinishRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=first.revision,
            finish_kind="early",
        ),
    )

    duplicate = DailyJourney(
        user_id=user.id,
        local_date=first.local_date,
        timezone="UTC",
        status="completed",
        revision=1,
        scenario_snapshot={},
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_an_active_journey_keeps_its_pinned_content_version(
    db_session: Session, enabled: None
) -> None:
    """A server-side prompt bump must not strand or rewrite an open journey."""

    class BumpedContent(_MissingContentAdapter):
        def build_scenario_context(self, db, *, user, scenario_key=None, input_mode=None):
            brief = super().build_scenario_context(
                db, user=user, scenario_key=scenario_key, input_mode=input_mode
            )
            from dataclasses import replace

            return replace(brief, content_version="journey-content-stub-v99")

    user = make_user(db_session, "state-pinned@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())
    assert created.scenario.content_version == "journey-content-stub-v0"

    bumped = DailyJourneyService(db_session, build_adapters(content=BumpedContent()))
    reread = bumped.get_journey(user, uuid.UUID(created.id))
    assert reread.scenario.content_version == "journey-content-stub-v0"
    assert [step.id for step in reread.steps] == [step.id for step in created.steps]


def test_ending_early_marks_unfinished_steps_skipped_not_completed(
    db_session: Session, enabled: None
) -> None:
    user = make_user(db_session, "state-early@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())

    finished = service.finish(
        user,
        uuid.UUID(created.id),
        JourneyFinishRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=created.revision,
            finish_kind="early",
        ),
    )
    assert finished.status == "ended_early"
    assert {step.status for step in finished.steps} == {"skipped"}
    assert finished.recap is not None
    assert finished.recap.objective_outcome == "not_yet"
    assert finished.recap.practiced_targets == []
    assert finished.recap.capability_evidence == []
    assert finished.recap.collectible_ids == []


def test_control_language_falls_back_to_english_for_unsupported_learners(
    db_session: Session, enabled: None
) -> None:
    service = DailyJourneyService(db_session, build_adapters())
    german = make_user(db_session, "state-de@example.com", native_language="de")
    swedish = make_user(db_session, "state-sv@example.com", native_language="sv")

    assert service.get_today(german).control_language == "de"
    assert service.get_today(swedish).control_language == "en"


# ---------------------------------------------------------------------------
# Integration with the real WP-03 content and WP-05 learning adapters
# ---------------------------------------------------------------------------


def drive_to_finish(
    service: DailyJourneyService,
    user: User,
    snapshot: Any,
    *,
    finish_kind: str,
    answer: str = "Je voudrais un café en terrasse, s'il vous plaît.",
) -> Any:
    """Walk a journey to its ending through the real state machine."""

    from app.schemas.daily_journey import (
        JourneyAdvanceRequest,
        JourneyAttemptRequest,
    )

    journey_id = uuid.UUID(snapshot.id)
    state = snapshot
    while state.current_step_id is not None:
        step = next(s for s in state.steps if s.id == state.current_step_id)
        if step.kind == "recall":
            payload = correct_recall_input(service.db, step.id)
            state = service.submit_attempt(
                user,
                journey_id,
                uuid.UUID(step.id),
                JourneyAttemptRequest.model_validate(
                    {
                        "mutation_id": uuid.uuid4().hex,
                        "expected_revision": state.revision,
                        "input": payload,
                    }
                ),
            ).journey
        elif step.kind == "respond":
            # A weak answer earns a repair turn; spend it, or advance 409s.
            for _ in range(MAX_RESPOND_TURNS + 1):
                result = service.submit_attempt(
                    user,
                    journey_id,
                    uuid.UUID(step.id),
                    JourneyAttemptRequest.model_validate(
                        {
                            "mutation_id": uuid.uuid4().hex,
                            "expected_revision": state.revision,
                            "input": {"mode": "text", "text": answer},
                        }
                    ),
                )
                state = result.journey
                if result.next_turn is None:
                    break
        state = service.advance(
            user,
            journey_id,
            JourneyAdvanceRequest(
                mutation_id=uuid.uuid4().hex,
                expected_revision=state.revision,
                current_step_id=step.id,
            ),
        )
    return service.finish(
        user,
        journey_id,
        JourneyFinishRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=state.revision,
            finish_kind=finish_kind,
        ),
    )


def test_the_real_content_and_learning_adapters_drive_a_whole_journey(
    db_session: Session, enabled: None
) -> None:
    """No stubs for WP-03 content or WP-05 learning: the resolved modules win."""

    from app.db.models.session import LearningSession
    from app.services.daily_journey_adapters import build_default_adapters

    adapters = build_default_adapters()
    assert getattr(adapters.content, "is_stub", False) is False, "WP-03 must be real"
    assert getattr(adapters.learning, "is_stub", False) is False, "WP-05 must be real"

    user = make_user(db_session, "state-real-adapters@example.com")
    service = DailyJourneyService(db_session, adapters)
    created, code = service.create_journey(user, create_request())

    assert code == 201
    assert created.status == "active"
    assert created.scenario.content_version == "journey-content-v1"
    assert created.scenario.scenario_key == "order_at_cafe"

    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert row is not None
    assert row.level_band == created.scenario.level_band
    assert row.learning_session_id is not None

    session = db_session.get(LearningSession, row.learning_session_id)
    assert session is not None
    assert session.topic == f"daily_journey:{row.id}"
    assert session.status == "in_progress"

    final = drive_to_finish(service, user, created, finish_kind="complete")
    assert final.status == "completed"
    assert final.recap is not None
    # Canonical evidence, not the stub prefix.
    steps = (
        db_session.query(DailyJourney).filter(DailyJourney.id == row.id).one().steps
    )
    refs = [step.evidence_ref for step in steps if step.evidence_ref]
    assert refs, "the real learning adapter produced no evidence reference"
    assert not any(ref.startswith("stub:") for ref in refs)

    db_session.refresh(session)
    assert session.status == "completed"
    assert session.completed_at is not None


# ---------------------------------------------------------------------------
# One capability rubric: the recap and GET /capabilities/progress agree
# ---------------------------------------------------------------------------


def test_the_recap_and_the_progress_endpoint_agree_about_one_journey(
    db_session: Session, enabled: None
) -> None:
    """The finish recap and the progress view are the same rubric, or they lie.

    WP-02 used to compute the recap's capability state inline
    (``none`` assistance → ``independent_once``), which could report a state
    the CONTRACTS §8 rubric never granted. The recap now asks WP-09, so the
    same journey reads the same way in both places.
    """

    from app.services.daily_journey_adapters import build_default_adapters

    user = make_user(db_session, "state-capability-agreement@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, _ = service.create_journey(user, create_request())

    final = drive_to_finish(service, user, created, finish_kind="complete")
    assert final.recap is not None
    assert final.recap.objective_outcome == "met"

    evidence = final.recap.capability_evidence
    assert evidence, (
        "a learner who met the objective must leave capability evidence; "
        "an empty recap here means the turn-level record never got written"
    )
    claim = next(item for item in evidence if item.capability_key == "order_at_cafe")

    progress = service.get_capability_progress(user)
    summary = next(
        item for item in progress.capabilities if item.capability_key == "order_at_cafe"
    )

    assert summary.state == claim.state, (
        f"recap says {claim.state}, the progress endpoint says {summary.state}"
    )
    assert claim.model_dump() in [item.model_dump() for item in summary.evidence]
    assert claim.observed_on == summary.latest_qualifying_on
    assert claim.modality in summary.modalities


def test_a_journey_that_proves_nothing_makes_no_capability_claim(
    db_session: Session, enabled: None
) -> None:
    """A wrong answer earns no state, in the recap and on the endpoint alike."""

    from app.services.daily_journey_adapters import build_default_adapters

    user = make_user(db_session, "state-capability-nothing@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, _ = service.create_journey(user, create_request())

    final = drive_to_finish(
        service, user, created, finish_kind="complete", answer="aaa bbb ccc"
    )
    assert final.recap is not None
    assert final.recap.objective_outcome != "met"
    assert final.recap.capability_evidence == []

    progress = service.get_capability_progress(user)
    summary = next(
        item for item in progress.capabilities if item.capability_key == "order_at_cafe"
    )
    assert summary.state in {"not_tried", "with_support"}
    assert summary.state != "independent_once"


def test_ending_early_leaves_the_learning_session_open(
    db_session: Session, enabled: None
) -> None:
    """A partial stop must earn no completed-session achievement credit."""

    from app.db.models.session import LearningSession
    from app.services.daily_journey_adapters import build_default_adapters

    user = make_user(db_session, "state-early-session@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, _ = service.create_journey(user, create_request())
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert row is not None and row.learning_session_id is not None

    service.finish(
        user,
        uuid.UUID(created.id),
        JourneyFinishRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=created.revision,
            finish_kind="early",
        ),
    )

    session = db_session.get(LearningSession, row.learning_session_id)
    assert session is not None
    assert session.status == "in_progress"
    assert session.completed_at is None


def test_the_learner_timezone_reaches_the_learning_adapter(
    db_session: Session, enabled: None
) -> None:
    """WP-09's 24-hour rubric needs a learner-local observation date."""

    recorded: dict[str, Any] = {}

    class RecordingLearning(_MissingLearningAdapter):
        def apply_learning_evidence(self, db, **kwargs):
            recorded.update(kwargs)
            return super().apply_learning_evidence(db, **kwargs)

    user = make_user(db_session, "state-tz-evidence@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(learning=RecordingLearning())
    )
    created, _ = service.create_journey(user, create_request("Pacific/Auckland"))
    drive_to_finish(service, user, created, finish_kind="complete")

    assert recorded["timezone"] == "Pacific/Auckland"
    assert recorded["modality"] in {"text", "voice"}


def test_a_deterministic_content_problem_does_not_promise_a_retry(
    db_session: Session, enabled: None
) -> None:
    """WP-03 marks authored-data problems non-retryable; we must not lie."""

    from fastapi import HTTPException

    from app.schemas.daily_journey import JourneyRetryRequest

    class NotAuthored(HealthyPreviewFailingGeneration):
        def build_scenario_context(self, db, *, user, scenario_key=None, input_mode=None):
            return ContentUnavailable(
                reason="scenario_not_authored", retry_after_seconds=0, retry_allowed=False
            )

    user = make_user(db_session, "state-not-authored@example.com")
    service = DailyJourneyService(db_session, build_adapters(content=NotAuthored()))
    snapshot, code = service.create_journey(user, create_request())

    assert code == 200
    assert snapshot.status == "unavailable"
    assert snapshot.retry is not None
    assert snapshot.retry.allowed is False

    with pytest.raises(HTTPException) as excinfo:
        service.retry_journey(
            user,
            uuid.UUID(snapshot.id),
            JourneyRetryRequest(mutation_id=uuid.uuid4().hex),
        )
    assert excinfo.value.status_code == 503
    assert excinfo.value.detail["code"] == "generation_unavailable"


# ---------------------------------------------------------------------------
# Atomicity of {domain effect + receipt}
# ---------------------------------------------------------------------------


def advance_to_respond(service: DailyJourneyService, user: User, snapshot: Any) -> Any:
    """Walk to the respond step without answering it."""

    from app.schemas.daily_journey import JourneyAdvanceRequest, JourneyAttemptRequest

    journey_id = uuid.UUID(snapshot.id)
    state = snapshot
    while True:
        step = next(s for s in state.steps if s.id == state.current_step_id)
        if step.kind == "respond":
            return state, step
        if step.kind == "recall":
            state = service.submit_attempt(
                user,
                journey_id,
                uuid.UUID(step.id),
                JourneyAttemptRequest.model_validate(
                    {
                        "mutation_id": uuid.uuid4().hex,
                        "expected_revision": state.revision,
                        "input": correct_recall_input(service.db, step.id),
                    }
                ),
            ).journey
        state = service.advance(
            user,
            journey_id,
            JourneyAdvanceRequest(
                mutation_id=uuid.uuid4().hex,
                expected_revision=state.revision,
                current_step_id=step.id,
            ),
        )


def test_a_crash_while_applying_evidence_leaves_no_partial_state(
    db_session: Session, enabled: None
) -> None:
    """Domain effects and the receipt commit together, or not at all."""

    from app.db.models.daily_journey import DailyJourneyMutation, DailyJourneyStep
    from app.schemas.daily_journey import JourneyAttemptRequest

    class ExplodingLearning(_MissingLearningAdapter):
        def apply_learning_evidence(self, db, **kwargs):
            raise RuntimeError("canonical write crashed")

    user = make_user(db_session, "state-crash@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    broken = DailyJourneyService(
        db_session, build_adapters(learning=ExplodingLearning())
    )
    mutation_id = uuid.uuid4().hex
    body = JourneyAttemptRequest.model_validate(
        {
            "mutation_id": mutation_id,
            "expected_revision": state.revision,
            "input": {"mode": "text", "text": "Je voudrais un café, s'il vous plaît."},
        }
    )
    with pytest.raises(RuntimeError):
        broken.submit_attempt(user, uuid.UUID(created.id), uuid.UUID(respond.id), body)

    # Nothing was applied: no turn, no evidence, no revision bump.
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    step_row = db_session.get(DailyJourneyStep, uuid.UUID(respond.id))
    assert row is not None and step_row is not None
    assert row.revision == state.revision
    assert step_row.turns_used == 0
    assert step_row.evidence_ref is None
    assert step_row.status == "active"

    # …and the key is reusable, because the failure was infrastructure.
    receipt = (
        db_session.query(DailyJourneyMutation)
        .filter(DailyJourneyMutation.mutation_id == mutation_id)
        .one()
    )
    assert receipt.status == "failed"

    healed = service.submit_attempt(
        user, uuid.UUID(created.id), uuid.UUID(respond.id), body
    )
    assert healed.pending is False
    assert healed.task_outcome == "met"
    db_session.refresh(step_row)
    assert step_row.turns_used == 1


def test_a_grading_failure_is_retryable_and_never_a_learner_failure(
    db_session: Session, enabled: None
) -> None:
    from app.db.models.daily_journey import DailyJourneyMutation, DailyJourneyStep
    from app.schemas.daily_journey import JourneyAttemptRequest
    from app.services.journey_contracts import ResponseEvaluation, TaskOutcome

    class TimingOutConversation:
        """The real module with its grader timing out. Everything else is WP-06."""

        def __getattr__(self, name):
            return getattr(journey_conversation, name)

        def evaluate_response(self, db, **kwargs):
            return ResponseEvaluation(
                outcome=TaskOutcome.UNSCORED,
                assistance=kwargs["assistance"],
                observations=[],
                pending=True,
                failure_reason="provider_timeout",
            )

    user = make_user(db_session, "state-pending@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(conversation=TimingOutConversation())
    )
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    mutation_id = uuid.uuid4().hex
    result = service.submit_attempt(
        user,
        uuid.UUID(created.id),
        uuid.UUID(respond.id),
        JourneyAttemptRequest.model_validate(
            {
                "mutation_id": mutation_id,
                "expected_revision": state.revision,
                "input": {"mode": "voice", "text": "Je voudrais un café."},
            }
        ),
    )

    assert result.pending is True
    assert result.task_outcome == "unscored"
    assert result.task_outcome != "not_yet"
    assert result.evidence_ref == ""
    assert result.journey.revision == state.revision

    step_row = db_session.get(DailyJourneyStep, uuid.UUID(respond.id))
    assert step_row is not None
    assert step_row.turns_used == 0
    assert step_row.status == "active"
    receipt = (
        db_session.query(DailyJourneyMutation)
        .filter(DailyJourneyMutation.mutation_id == mutation_id)
        .one()
    )
    assert receipt.status == "failed", "a pending grade must keep the key reusable"


def test_deleting_a_learner_removes_their_journeys_steps_and_receipts(
    tmp_path, enabled: None
) -> None:
    """Ownership cascade, proved with foreign keys actually switched on.

    The shared test database runs SQLite with ``PRAGMA foreign_keys`` off, so a
    cascade assertion there would prove nothing. This builds a throwaway
    database with enforcement enabled.
    """

    from sqlalchemy import create_engine, delete, event
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base
    from app.db.models.daily_journey import DailyJourneyMutation, DailyJourneyStep
    from app.db.models.session import LearningSession
    from app.db.models.user import User as UserModel

    engine = create_engine(f"sqlite:///{tmp_path / 'cascade.db'}")

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):  # pragma: no cover - setup
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        UserModel.__table__,
        LearningSession.__table__,
        DailyJourney.__table__,
        DailyJourneyStep.__table__,
        DailyJourneyMutation.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    factory = sessionmaker(bind=engine)

    with factory() as db:
        user = make_user(db, "state-cascade@example.com")
        service = DailyJourneyService(db, build_adapters())
        created, _ = service.create_journey(user, create_request())
        assert db.query(DailyJourneyStep).count() == 4
        assert db.query(DailyJourneyMutation).count() == 1

        # Core DELETE, so what is exercised is the DDL cascade the production
        # database enforces, not SQLAlchemy's ORM relationship cascades.
        db.execute(
            delete(UserModel)
            .where(UserModel.id == user.id)
            .execution_options(synchronize_session=False)
        )
        db.commit()

        assert db.query(DailyJourney).count() == 0
        assert db.query(DailyJourneyStep).count() == 0
        assert db.query(DailyJourneyMutation).count() == 0
        assert created.id is not None

    engine.dispose()


def test_reading_today_never_pays_for_generation(
    db_session: Session, enabled: None
) -> None:
    """CONTRACTS §4: a GET must not trigger a costly content build."""

    from app.services.daily_journey_adapters import build_default_adapters

    calls: list[str] = []
    adapters = build_default_adapters()
    real_content = adapters.content

    class WatchedContent:
        def build_scenario_context(self, db, **kwargs):
            calls.append("build_scenario_context")
            return real_content.build_scenario_context(db, **kwargs)

        def list_available_scenarios(self, db, **kwargs):
            calls.append("list_available_scenarios")
            return real_content.list_available_scenarios(db, **kwargs)

        def resolve_scenario_brief(self, db, **kwargs):
            calls.append("resolve_scenario_brief")
            return real_content.resolve_scenario_brief(db, **kwargs)

    user = make_user(db_session, "state-cheap-get@example.com")
    service = DailyJourneyService(db_session, build_adapters(content=WatchedContent()))

    envelope = service.get_today(user, timezone_hint="Europe/Paris")

    assert envelope.available is not None
    assert envelope.available.scenario_key == "order_at_cafe"
    assert calls == ["list_available_scenarios"], calls


def test_an_absent_domain_module_is_stubbed_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Branch 1 of the coordinator's ratification (k): not written yet."""

    import app.services.daily_journey_adapters as adapters_module

    def absent_import(name: str):
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    monkeypatch.setattr(adapters_module, "import_module", absent_import)

    with caplog.at_level("WARNING"):
        adapters = adapters_module.build_default_adapters()

    assert getattr(adapters.capabilities, "is_stub", False) is True
    assert getattr(adapters.events, "is_stub", False) is True
    assert any("not written yet" in record.message for record in caplog.records)

    # …except the planner, which has no stub: absence is a hard failure there.
    assert getattr(adapters.planner, "is_broken", False) is True


def test_a_module_that_exists_but_cannot_import_is_never_stubbed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Branch 2 of (k): a broken module must not silently stop writing credit."""

    import app.services.daily_journey_adapters as adapters_module

    def broken_import(name: str):
        if name.endswith("journey_learning"):
            raise SyntaxError("source code string cannot contain null bytes")
        if name.endswith("journey_content"):
            # ImportError of ITS OWN dependency, not of the module itself.
            raise ModuleNotFoundError("No module named 'some_dep'", name="some_dep")
        return importlib.import_module(name)

    monkeypatch.setattr(adapters_module, "import_module", broken_import)

    with caplog.at_level("ERROR"):
        adapters = adapters_module.build_default_adapters()

    for member in (adapters.learning, adapters.content):
        assert getattr(member, "is_stub", False) is False
        assert getattr(member, "is_broken", False) is True
    assert sorted(adapters.broken_modules) == ["journey_content", "journey_learning"]

    # Every call refuses rather than returning a fake success.
    with pytest.raises(adapters_module.AdapterUnavailable):
        adapters.learning.apply_learning_evidence(None, user=None)
    assert any("refusing to stub" in record.message for record in caplog.records)


def test_a_broken_learning_module_fails_the_attempt_instead_of_faking_success(
    db_session: Session, enabled: None
) -> None:
    """The silent-failure footgun (k) names, closed end to end."""

    from fastapi import HTTPException

    from app.db.models.daily_journey import DailyJourneyStep
    from app.schemas.daily_journey import JourneyAttemptRequest
    from app.services.daily_journey_adapters import _BrokenAdapter

    user = make_user(db_session, "state-broken-learning@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    broken = DailyJourneyService(
        db_session,
        build_adapters(learning=_BrokenAdapter("journey_learning", "import_failed")),
    )
    with pytest.raises(HTTPException) as excinfo:
        broken.submit_attempt(
            user,
            uuid.UUID(created.id),
            uuid.UUID(respond.id),
            JourneyAttemptRequest.model_validate(
                {
                    "mutation_id": uuid.uuid4().hex,
                    "expected_revision": state.revision,
                    "input": {
                        "mode": "text",
                        "text": "Je voudrais un café, s'il vous plaît.",
                    },
                }
            ),
        )

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail["code"] == "generation_unavailable"

    # Nothing was written and nothing was claimed as done.
    step_row = db_session.get(DailyJourneyStep, uuid.UUID(respond.id))
    assert step_row is not None
    assert step_row.turns_used == 0
    assert step_row.evidence_ref is None
    assert step_row.status == "active"
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert row is not None and row.revision == state.revision


def test_a_broken_module_makes_creation_honestly_unavailable(
    db_session: Session, enabled: None
) -> None:
    from app.services.daily_journey_adapters import _BrokenAdapter

    user = make_user(db_session, "state-broken-create@example.com")
    service = DailyJourneyService(
        db_session,
        build_adapters(planner=_BrokenAdapter("journey_planner", "import_failed")),
    )
    snapshot, code = service.create_journey(user, create_request())

    assert code == 200
    assert snapshot.status == "unavailable"
    assert snapshot.steps == []
    assert snapshot.retry is not None and snapshot.retry.allowed is False

    row = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert row is not None
    assert row.unavailable_reason == "journey_planner_import_failed"


def test_resolved_adapters_accept_the_state_machines_exact_call_sites(
    db_session: Session,
) -> None:
    """Drift guard for WP-03/04/05/06/09/11 as each real module lands."""

    import inspect

    from app.services.daily_journey_adapters import build_default_adapters

    adapters = build_default_adapters()
    assert adapters.broken_modules == [], adapters.broken_modules
    call_sites = [
        (adapters.content, "build_scenario_context", ("db",), {"user", "scenario_key", "input_mode"}),
        (
            adapters.planner,
            "plan_journey",
            (),
            {"scenario", "candidates", "budget_seconds", "pace", "input_mode"},
        ),
        (
            adapters.learning,
            "select_learning_candidates",
            ("db",),
            {"user", "scenario", "limit"},
        ),
        (
            adapters.learning,
            "ensure_journey_learning_session",
            ("db",),
            {"user", "journey_id", "scenario_key"},
        ),
        (
            adapters.learning,
            "evaluate_recall",
            ("db",),
            {"user", "task", "answer", "assistance"},
        ),
        (
            adapters.learning,
            "apply_learning_evidence",
            ("db",),
            {"user", "journey_id", "step_id", "session", "evaluation", "modality", "timezone"},
        ),
        (
            adapters.conversation,
            "evaluate_response",
            ("db",),
            {
                "user",
                "scenario",
                "task",
                "answer",
                "turn_index",
                "assistance",
                "history",
            },
        ),
        (
            adapters.conversation,
            "apply_story_outcome",
            ("db",),
            {"user", "journey_id", "scenario", "proposal", "source_key"},
        ),
        (
            adapters.capabilities,
            "build_capability_summary",
            ("db",),
            {"user", "control_language"},
        ),
        (
            adapters.capabilities,
            "build_journey_capability_evidence",
            ("db",),
            {"user", "journey_id", "control_language"},
        ),
        (
            adapters.capabilities,
            "mint_journey_keepsake",
            ("db",),
            {"user", "journey_id", "scenario_key", "completion_kind"},
        ),
        (
            adapters.events,
            "record_journey_event",
            ("db",),
            {"event_name", "user_id", "source_key", "metadata"},
        ),
    ]

    for member, name, positional, keywords in call_sites:
        callable_ = getattr(member, name, None)
        assert callable(callable_), f"{name} is missing from {member!r}"
        signature = inspect.signature(callable_)
        signature.bind(*[None for _ in positional], **dict.fromkeys(keywords))


# ---------------------------------------------------------------------------
# WP-04 planner integration
# ---------------------------------------------------------------------------


def test_the_requested_modality_reaches_the_respond_prompt(
    db_session: Session, enabled: None
) -> None:
    """Without input_mode at the call site every journey would be text-only."""

    from app.schemas.daily_journey import JourneyCreateRequest

    def respond_modes(email: str, mode: str) -> list[str]:
        user = make_user(db_session, email)
        service = DailyJourneyService(db_session, build_adapters())
        created, code = service.create_journey(
            user,
            JourneyCreateRequest(
                mutation_id=uuid.uuid4().hex,
                timezone="Europe/Paris",
                budget_seconds=300,
                preferred_input_mode=InputMode(mode),
            ),
        )
        assert code == 201
        respond = next(step for step in created.steps if step.kind == "respond")
        return list(respond.prompt.input_modes)

    assert respond_modes("state-mode-voice@example.com", "voice") == ["text", "voice"]
    # Text is always offered; voice only when the journey was created for it.
    assert respond_modes("state-mode-text@example.com", "text") == ["text"]


def test_plan_unavailable_is_a_deterministic_dead_end_not_a_retry_loop(
    db_session: Session, enabled: None
) -> None:
    """WP-04's typed PlanUnavailable maps onto unavailable + retry_allowed False."""

    from dataclasses import replace as dc_replace

    from fastapi import HTTPException

    from app.schemas.daily_journey import JourneyRetryRequest

    class EndinglessContent(_MissingContentAdapter):
        """A scene with no authored ending: scenario_has_no_ending."""

        def describe_available_scenario(self, db, *, user, input_mode):
            return self.build_scenario_context(db, user=user, input_mode=input_mode)

        def build_scenario_context(self, db, *, user, scenario_key=None, input_mode=None):
            brief = _MissingContentAdapter.build_scenario_context(
                self, db, user=user, scenario_key=scenario_key, input_mode=input_mode
            )
            return dc_replace(brief, resolution_lines={}, resolution_summaries={})

    user = make_user(db_session, "state-plan-unavailable@example.com")
    service = DailyJourneyService(db_session, build_adapters(content=EndinglessContent()))
    snapshot, code = service.create_journey(user, create_request())

    assert code == 200
    assert snapshot.status == "unavailable"
    assert snapshot.retry is not None and snapshot.retry.allowed is False

    row = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert row is not None
    assert row.unavailable_reason == "scenario_has_no_ending"
    assert row.unavailable_retry_allowed is False

    with pytest.raises(HTTPException) as excinfo:
        service.retry_journey(
            user,
            uuid.UUID(snapshot.id),
            JourneyRetryRequest(mutation_id=uuid.uuid4().hex),
        )
    assert excinfo.value.status_code == 503
    assert excinfo.value.detail["code"] == "generation_unavailable"


def test_planner_target_identities_are_persisted_verbatim(
    db_session: Session, enabled: None
) -> None:
    """Composite "{kind}:{id}" ids: a vocab row and a grammar concept can collide."""

    user = make_user(db_session, "state-plan-selection@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())

    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert row is not None
    selection = row.plan_selection or {}
    assert selection["selected_target_ids"] == ["vocabulary:stub-target-un-cafe"]
    assert selection["omitted_candidate_ids"] == []
    # Verbatim: still composite, never split into a bare record id.
    for identity in selection["selected_target_ids"]:
        assert identity.count(":") >= 1
        assert identity.split(":", 1)[0] in {"vocabulary", "grammar", "error"}
    assert selection["rationale"]
    # None of it is public.
    assert "plan_selection" not in created.model_dump(mode="json")


def test_a_demonstrated_target_is_marked_skipped_not_turned_into_a_drill(
    db_session: Session, enabled: None
) -> None:
    """WP-04 may hand back a SKIPPED recall step; honour it, do not re-activate."""

    from app.services.journey_contracts import LearningCandidate, TargetKind, TargetRef

    demonstrated = TargetRef(
        kind=TargetKind.VOCABULARY,
        id="stub-target-un-cafe",
        label_fr="un café",
        label_native="a coffee",
    )

    class DemonstratedLearning(_MissingLearningAdapter):
        def select_learning_candidates(self, db, *, user, scenario, limit):
            return [
                LearningCandidate(
                    target=demonstrated,
                    priority_score=1.0,
                    due_since_days=0,
                    estimated_seconds=45,
                    relevance=1.0,
                    source_item_type="stub",
                    # WP-04's explicit flag: never inferred from a due date.
                    metadata={"demonstrated_independently": True},
                )
            ]

    user = make_user(db_session, "state-demonstrated@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(learning=DemonstratedLearning())
    )
    created, _ = service.create_journey(user, create_request())

    recall_steps = [step for step in created.steps if step.kind == "recall"]
    assert recall_steps, "the planner should still surface the target as a step"
    assert recall_steps[0].status == "skipped", (
        "an already-demonstrated target must not become a mandatory drill"
    )

    # The learner starts on a real step, never on the skipped one.
    current = next(step for step in created.steps if step.id == created.current_step_id)
    assert current.status == "active"
    assert current.id != recall_steps[0].id
    assert current.kind == "scene"

    # …and finishing complete does not require the skipped step to be answered.
    final = drive_to_finish(service, user, created, finish_kind="complete")
    assert final.status == "completed"
    assert [step.status for step in final.steps if step.kind == "recall"] == ["skipped"]


# ---------------------------------------------------------------------------
# WP-06 conversation integration
# ---------------------------------------------------------------------------


class PinnedScenarioContent:
    """The real WP-03 content, pinned to one scenario family."""

    def __init__(self, scenario_key: str) -> None:
        self.scenario_key = scenario_key

    def __getattr__(self, name: str) -> Any:
        from app.services import journey_content

        return getattr(journey_content, name)

    def describe_available_scenario(self, db, *, user, input_mode):
        return self.build_scenario_context(db, user=user, input_mode=input_mode)

    def build_scenario_context(self, db, *, user, scenario_key=None, input_mode=None):
        from app.services import journey_content
        from app.services.journey_contracts import InputMode as Mode

        return journey_content.resolve_scenario_brief(
            db,
            user=user,
            scenario_key=self.scenario_key,
            input_mode=input_mode or Mode.TEXT,
        )


def test_a_journey_with_no_agreement_never_renders_an_agreement(
    db_session: Session, enabled: None
) -> None:
    """The integration owner's rule: show the ending that was actually derived.

    WP-04 bakes an optimistic default into the plan. For ``arrange_meeting``
    that is ``meeting_saturday_market`` — a Saturday the learner never agreed
    to. Finishing without a successful response must never show it.
    """

    from app.schemas.daily_journey import JourneyAdvanceRequest, JourneyAttemptRequest

    user = make_user(db_session, "state-no-agreement@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(content=PinnedScenarioContent("arrange_meeting"))
    )
    created, _ = service.create_journey(user, create_request())
    assert created.scenario.scenario_key == "arrange_meeting"

    planned = next(step for step in created.steps if step.kind == "resolution")
    planned_key = planned.prompt.outcome_key

    state, respond = advance_to_respond(service, user, created)
    # Nothing gets across: the learner mumbles, twice.
    for _ in range(4):
        result = service.submit_attempt(
            user,
            uuid.UUID(created.id),
            uuid.UUID(respond.id),
            JourneyAttemptRequest.model_validate(
                {
                    "mutation_id": uuid.uuid4().hex,
                    "expected_revision": state.revision,
                    "input": {"mode": "text", "text": "euh"},
                }
            ),
        )
        state = result.journey
        assert result.task_outcome != "met"
        if result.next_turn is None:
            break

    state = service.advance(
        user,
        uuid.UUID(created.id),
        JourneyAdvanceRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=state.revision,
            current_step_id=respond.id,
        ),
    )
    resolution = next(step for step in state.steps if step.kind == "resolution")

    assert resolution.prompt.outcome_key != "meeting_saturday_market"
    assert resolution.prompt.outcome_key == "meeting_postponed"
    if planned_key == "meeting_saturday_market":
        assert resolution.prompt.outcome_key != planned_key
    assert resolution.prompt.character_line_fr
    assert "samedi" not in resolution.prompt.character_line_fr.lower()

    final = drive_to_finish(service, user, state, finish_kind="early")
    assert final.status == "ended_early"
    assert final.recap is not None
    assert final.recap.objective_outcome != "met"
    assert final.recap.story_outcome is None
    ending = next(step for step in final.steps if step.kind == "resolution")
    assert ending.prompt.outcome_key == "meeting_postponed"


def test_a_journey_abandoned_before_answering_shows_the_neutral_ending(
    db_session: Session, enabled: None
) -> None:
    """Finishing without ever answering must not leave the optimistic default."""

    user = make_user(db_session, "state-abandoned@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(content=PinnedScenarioContent("arrange_meeting"))
    )
    created, _ = service.create_journey(user, create_request())

    final = service.finish(
        user,
        uuid.UUID(created.id),
        JourneyFinishRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=created.revision,
            finish_kind="early",
        ),
    )
    resolution = next(step for step in final.steps if step.kind == "resolution")
    assert resolution.prompt.outcome_key == "meeting_postponed"
    assert resolution.prompt.outcome_key != "meeting_saturday_market"


def test_the_learner_gets_the_repair_turn_the_contract_promises(
    db_session: Session, enabled: None
) -> None:
    """CONTRACTS §3: two normal turns PLUS one optional repair, not two total."""

    from app.schemas.daily_journey import JourneyAttemptRequest

    user = make_user(db_session, "state-repair@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    private = _private_task(db_session, respond.id)["response_task"]
    budget = journey_conversation.turn_budget(_response_task(private))
    assert budget == private["max_turns"] + (1 if private["repair_allowed"] else 0)
    assert budget > private["max_turns"], "a repair turn must exist"

    accepted = 0
    for _ in range(budget + 2):
        result = service.submit_attempt(
            user,
            uuid.UUID(created.id),
            uuid.UUID(respond.id),
            JourneyAttemptRequest.model_validate(
                {
                    "mutation_id": uuid.uuid4().hex,
                    "expected_revision": state.revision,
                    "input": {"mode": "text", "text": "euh"},
                }
            ),
        )
        state = result.journey
        accepted += 1
        if result.next_turn is None:
            break
        assert result.next_turn.step_id == respond.id

    step_row = db_session.get(_step_model(), uuid.UUID(respond.id))
    assert step_row is not None
    assert accepted > private["max_turns"], (
        f"the learner got {accepted} turn(s); the repair turn was denied"
    )
    assert step_row.turns_used <= budget
    assert step_row.status == "completed"


def test_reply_provenance_is_surfaced_and_never_guessed(
    db_session: Session, enabled: None
) -> None:
    """An authored line must never be presented as a live model response."""

    from app.schemas.daily_journey import JourneyAttemptRequest

    user = make_user(db_session, "state-provenance@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    result = service.submit_attempt(
        user,
        uuid.UUID(created.id),
        uuid.UUID(respond.id),
        JourneyAttemptRequest.model_validate(
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": state.revision,
                "input": {
                    "mode": "text",
                    "text": "Je voudrais un café en terrasse, s'il vous plaît.",
                },
            }
        ),
    )

    assert result.reply_source in {"authored", "model", "none"}
    if result.character_reply_fr:
        # With the provider off in tests the line is authored, and says so.
        assert result.reply_source != "none"
    else:
        assert result.reply_source == "none"


def test_a_recall_attempt_reports_no_reply_provenance(
    db_session: Session, enabled: None
) -> None:
    from app.schemas.daily_journey import JourneyAdvanceRequest, JourneyAttemptRequest

    user = make_user(db_session, "state-recall-provenance@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    created, _ = service.create_journey(user, create_request())
    scene = next(step for step in created.steps if step.kind == "scene")
    state = service.advance(
        user,
        uuid.UUID(created.id),
        JourneyAdvanceRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=created.revision,
            current_step_id=scene.id,
        ),
    )
    recall = next(step for step in state.steps if step.id == state.current_step_id)
    if recall.kind != "recall":
        pytest.skip("this plan has no recall step")

    result = service.submit_attempt(
        user,
        uuid.UUID(created.id),
        uuid.UUID(recall.id),
        JourneyAttemptRequest.model_validate(
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": state.revision,
                "input": correct_recall_input(db_session, recall.id),
            }
        ),
    )
    assert result.character_reply_fr is None
    assert result.reply_source == "none"


def test_a_correction_with_an_apostrophe_survives_normalization(
    db_session: Session, enabled: None
) -> None:
    """iOS types U+2019; comparing the span raw would drop a real correction."""

    from app.schemas.daily_journey import JourneyAttemptRequest
    from app.services.journey_contracts import (
        Correction,
        EvidenceKind,
        ResponseEvaluation,
        StoryOutcomeProposal,
        TargetObservation,
        TaskOutcome,
    )

    class CorrectingConversation:
        def __getattr__(self, name):
            return getattr(journey_conversation, name)

        def evaluate_response(self, db, *, task, answer, assistance, **_kwargs):
            return ResponseEvaluation(
                outcome=TaskOutcome.PARTIALLY_MET,
                assistance=assistance,
                observations=[
                    TargetObservation(
                        target=target,
                        evidence_kind=EvidenceKind.PRODUCED_SUPPORTED,
                        assistance=assistance,
                        modality=answer.mode,
                        learner_text=answer.text,
                    )
                    for target in task.targets
                ],
                character_reply_fr="Très bien.",
                # The span carries a straight apostrophe, as WP-06 produces it
                # from the normalized answer; the learner typed a curly one.
                correction=Correction(
                    span_fr="s'il vous plait",
                    corrected_fr="s'il vous plaît",
                    note_native="Don't forget the circumflex.",
                ),
                consequence=StoryOutcomeProposal(outcome_key="served_at_counter"),
            )

    user = make_user(db_session, "state-correction@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(conversation=CorrectingConversation())
    )
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    result = service.submit_attempt(
        user,
        uuid.UUID(created.id),
        uuid.UUID(respond.id),
        JourneyAttemptRequest.model_validate(
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": state.revision,
                # U+2019 and a narrow no-break space, exactly as iOS sends them.
                "input": {
                    "mode": "text",
                    "text": "Un café, s’il vous plait !",
                },
            }
        ),
    )

    assert result.correction is not None, "a valid correction was silently dropped"
    assert result.correction.corrected_fr == "s'il vous plaît"


def test_a_fabricated_correction_span_is_still_refused(
    db_session: Session, enabled: None
) -> None:
    from app.schemas.daily_journey import JourneyAttemptRequest
    from app.services.journey_contracts import (
        Correction,
        ResponseEvaluation,
        TaskOutcome,
    )

    class FabricatingConversation:
        def __getattr__(self, name):
            return getattr(journey_conversation, name)

        def evaluate_response(self, db, *, assistance, **_kwargs):
            return ResponseEvaluation(
                outcome=TaskOutcome.PARTIALLY_MET,
                assistance=assistance,
                observations=[],
                character_reply_fr="Bien.",
                correction=Correction(
                    span_fr="je voudrais une bière",
                    corrected_fr="je voudrais un café",
                    note_native="Never written by the learner.",
                ),
            )

    user = make_user(db_session, "state-fabricated@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(conversation=FabricatingConversation())
    )
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    result = service.submit_attempt(
        user,
        uuid.UUID(created.id),
        uuid.UUID(respond.id),
        JourneyAttemptRequest.model_validate(
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": state.revision,
                "input": {"mode": "text", "text": "Un café, s'il vous plaît."},
            }
        ),
    )
    assert result.correction is None


def test_the_story_effect_uses_the_canonical_source_key(
    db_session: Session, enabled: None
) -> None:
    """WP-06's ledger dedupes on ``journey:{id}:`` and rejects anything else."""

    from app.schemas.daily_journey import JourneyAttemptRequest
    from app.services.journey_contracts import StoryOutcomeRef

    seen: dict[str, Any] = {}

    class RecordingConversation:
        def __getattr__(self, name):
            return getattr(journey_conversation, name)

        def apply_story_outcome(self, db, *, source_key, proposal, journey_id, **_kw):
            seen["source_key"] = source_key
            return StoryOutcomeRef(applied=True, outcome_key=proposal.outcome_key)

    user = make_user(db_session, "state-source-key@example.com")
    service = DailyJourneyService(
        db_session, build_adapters(conversation=RecordingConversation())
    )
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)

    service.submit_attempt(
        user,
        uuid.UUID(created.id),
        uuid.UUID(respond.id),
        JourneyAttemptRequest.model_validate(
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": state.revision,
                "input": {
                    "mode": "text",
                    "text": "Je voudrais un café en terrasse, s'il vous plaît.",
                },
            }
        ),
    )

    assert seen["source_key"] == journey_conversation.story_outcome_source_key(
        uuid.UUID(created.id)
    )
    assert seen["source_key"].startswith(f"journey:{created.id}:")
    assert seen["source_key"].endswith(":story_outcome")


# ---------------------------------------------------------------------------
# Scenario rotation (WP-12 defect D-1) and the ending that was earned (D-2)
# ---------------------------------------------------------------------------


def test_the_scenario_family_rotates_across_days_and_never_swaps_mid_flight(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP-12 D-1: every advertised family must be reachable from the real create path.

    ``GET /capabilities/progress`` advertises three capabilities; a create path
    that can only ever produce one of them makes the other two permanently
    ``not_tried``. Rotation is deterministic — untried first, then least
    recently served — and the chosen family is persisted before any provider
    call, so a retried create, a refetch and a generation retry all keep it.
    """

    from app.services import journey_content

    user = make_user(db_session, f"state-rotation-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_adapters(content=journey_content))
    advertised = {
        str(brief.scenario_key)
        for brief in journey_content.list_available_scenarios(db_session, user=user)
    }
    assert len(advertised) > 1, "nothing to rotate between"

    start = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
    served: list[str] = []
    for offset in range(len(advertised)):
        freeze(monkeypatch, start + timedelta(days=offset))
        offered = service.get_today(user).available
        created, code = service.create_journey(user, create_request())
        assert code == 201
        key = str(created.scenario.scenario_key)

        # What GET /today advertised is what POST /daily-journeys served, and a
        # retried create or a refetch cannot move the scene under the learner.
        assert offered is not None and str(offered.scenario_key) == key
        replayed, replay_code = service.create_journey(user, create_request())
        assert replay_code == 200
        assert str(replayed.scenario.scenario_key) == key
        refetched = service.get_journey(user, uuid.UUID(created.id))
        assert str(refetched.scenario.scenario_key) == key

        served.append(key)
        service.finish(
            user,
            uuid.UUID(created.id),
            JourneyFinishRequest(
                mutation_id=uuid.uuid4().hex,
                expected_revision=replayed.revision,
                finish_kind="early",
            ),
        )

    assert served[0] == "order_at_cafe", "a brand-new learner still starts at the café"
    assert set(served) == advertised, f"served {served} of {sorted(advertised)}"
    assert len(set(served)) == len(served), "an untried family must win over a tried one"

    # Once everything has been tried, the least recently served comes back.
    freeze(monkeypatch, start + timedelta(days=len(advertised)))
    again, _ = service.create_journey(user, create_request())
    assert str(again.scenario.scenario_key) == served[0]


def test_the_ending_names_the_drink_the_learner_actually_ordered(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP-12 D-2: the resolution may not serve a drink that was never ordered."""

    from app.schemas.daily_journey import JourneyAttemptRequest
    from app.services import journey_content

    cases = [
        ("Je voudrais un thé, s'il vous plaît. Au comptoir.", "un thé", "tea"),
        ("Un chocolat chaud au comptoir, s'il vous plaît.", "un chocolat chaud", "hot chocolate"),
        ("Un thé en terrasse, s'il vous plaît.", "un thé", "tea"),
        ("Je voudrais un café au comptoir, s'il vous plaît.", "un café", "coffee"),
    ]
    start = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
    for index, (answer, drink, gloss) in enumerate(cases):
        freeze(monkeypatch, start + timedelta(days=index))
        user = make_user(db_session, f"state-drink-{uuid.uuid4().hex[:8]}@example.com")
        service = DailyJourneyService(
            db_session, build_adapters(content=journey_content)
        )
        created, _ = service.create_journey(user, create_request())
        assert str(created.scenario.scenario_key) == "order_at_cafe"
        state, respond = advance_to_respond(service, user, created)
        result = service.submit_attempt(
            user,
            uuid.UUID(created.id),
            uuid.UUID(respond.id),
            JourneyAttemptRequest.model_validate(
                {
                    "mutation_id": uuid.uuid4().hex,
                    "expected_revision": state.revision,
                    "input": {"mode": "text", "text": answer},
                }
            ),
        )
        assert result.task_outcome.value == "met", answer
        resolution = next(
            step for step in result.journey.steps if step.kind == "resolution"
        )
        line = resolution.prompt.character_line_fr
        summary = resolution.prompt.summary_native

        assert drink in line.lower(), f"{answer!r} -> {line!r}"
        assert gloss in summary.lower(), f"{answer!r} -> {summary!r}"
        for other, other_gloss in (
            ("un café", "coffee"),
            ("un thé", "tea"),
            ("un chocolat chaud", "hot chocolate"),
        ):
            if other == drink:
                continue
            assert other not in line.lower(), f"{answer!r} was served {line!r}"
            assert other_gloss not in summary.lower(), f"{answer!r} -> {summary!r}"
        # The character's own reply and the ending must tell the same story.
        assert drink in (result.character_reply_fr or "").lower()


def test_an_unspoken_ending_names_no_drink_at_all(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A day that ends without an identifiable order may not invent one."""

    from app.services import journey_content

    freeze(monkeypatch, datetime(2026, 3, 10, 9, 0, tzinfo=UTC))
    user = make_user(db_session, f"state-nodrink-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_adapters(content=journey_content))
    created, _ = service.create_journey(user, create_request())
    resolution = next(step for step in created.steps if step.kind == "resolution")
    planned = resolution.prompt.character_line_fr
    assert "{" not in planned and "}" not in planned, planned
    for drink in ("café", "thé", "chocolat"):
        assert drink not in planned.lower(), planned
    assert "coffee" not in resolution.prompt.summary_native.lower()
