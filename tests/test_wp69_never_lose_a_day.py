"""WP-69 — never lose a day.

The 2026-09-22 walk lost a learner's first scene three ways at once, and each
has a test here:

* **L5** — a best-effort Courrier lookup hit a missing column. On PostgreSQL
  that aborts the transaction, the ``except`` swallowed the error, and the next
  statement of the learner's request failed: a 500 after 40 s. The tests below
  run the journey on SQLite with PostgreSQL's abort semantics switched on
  (:func:`postgres_abort_semantics`), so a swallowed SQL error poisons the
  session exactly as it did in production — and the day must still be served.
* **L6** — the journey then sat in ``preparing`` with no claim, forever. A dead
  claim now heals on the next read and the retry path regenerates it.
* A story engine that exhausts its attempts no longer costs the day: an authored
  scene for the learner's band is served instead, and only the plan says so.

Nothing here calls a provider.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, event, text, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

import app.services.daily_journey as journey_module
from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User
from app.db.savepoint import best_effort, run_best_effort, session_is_usable
from app.schemas.daily_journey import JourneyCreateRequest, JourneyRetryRequest
from app.services import journey_content, journey_conversation, journey_planner
from app.services import story_correspondence as courrier
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import (
    JourneyAdapters,
    _MissingCapabilitiesAdapter,
    _MissingContentAdapter,
    _MissingEventsAdapter,
    _MissingLearningAdapter,
)
from app.services.journey_contracts import ContentUnavailable, InputMode
from app.services.journey_day_shapes import set_letter_provider
from app.services.missions import MissionScheduler

# ---------------------------------------------------------------------------
# PostgreSQL's aborted-transaction semantics, on the SQLite test engine
# ---------------------------------------------------------------------------

_ABORTED = "current transaction is aborted, commands ignored until end of transaction block"


@contextmanager
def postgres_abort_semantics(engine: Any) -> Iterator[dict[str, int]]:
    """After any failed statement, refuse every statement until a rollback.

    That is what PostgreSQL does and SQLite does not: SQLite lets a transaction
    carry on after a failed SELECT, which is exactly why the L5 bug never showed
    up in the suite. ``ROLLBACK`` and ``ROLLBACK TO SAVEPOINT`` clear the state,
    as they do on PostgreSQL. The listeners are removed on exit so no other test
    inherits them.
    """

    state = {"aborted": 0, "errors": 0}

    def on_error(context: Any) -> None:
        state["errors"] += 1
        state["aborted"] = 1

    def before(conn: Any, cursor: Any, statement: str, params: Any, context: Any, executemany: bool) -> None:
        if not state["aborted"]:
            return
        if statement.strip().upper().startswith("ROLLBACK"):
            state["aborted"] = 0
            return
        raise sqlite3.OperationalError(_ABORTED)

    def on_rollback(conn: Any) -> None:
        state["aborted"] = 0

    event.listen(engine, "handle_error", on_error)
    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "rollback", on_rollback)
    try:
        yield state
    finally:
        event.remove(engine, "handle_error", on_error)
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "rollback", on_rollback)
        state["aborted"] = 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def build_adapters(**overrides: Any) -> JourneyAdapters:
    members: dict[str, Any] = {
        "content": _MissingContentAdapter(),
        "planner": journey_planner,
        "learning": _MissingLearningAdapter(),
        "conversation": journey_conversation,
        "capabilities": _MissingCapabilitiesAdapter(),
        "events": _MissingEventsAdapter(),
    }
    members.update(overrides)
    return JourneyAdapters(**members)


@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)


@pytest.fixture()
def letter_provider() -> Iterator[None]:
    """The real Courrier provider, installed for one test and taken down after."""

    courrier.install_letter_provider()
    try:
        yield
    finally:
        set_letter_provider(None)


def make_user(db: Session, *, cefr: str | None = None, native_language: str = "en") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp69-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language=native_language,
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate=cefr,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_request(mutation_id: str | None = None) -> JourneyCreateRequest:
    return JourneyCreateRequest(
        mutation_id=mutation_id or uuid.uuid4().hex,
        timezone="Europe/Paris",
        budget_seconds=300,
        preferred_input_mode=InputMode.TEXT,
    )


def retry_request(mutation_id: str | None = None) -> JourneyRetryRequest:
    return JourneyRetryRequest(mutation_id=mutation_id or uuid.uuid4().hex)


def freeze(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    monkeypatch.setattr(journey_module, "_utcnow", lambda: moment)


def assert_playable(snapshot: Any) -> None:
    assert snapshot.status == "active"
    assert snapshot.current_step_id is not None
    assert len(snapshot.steps) >= 3
    assert any(step.id == snapshot.current_step_id for step in snapshot.steps)


# ---------------------------------------------------------------------------
# 1. The savepoint helper
# ---------------------------------------------------------------------------


def _savepoint_engine() -> Any:
    """A private SQLite engine with SQLAlchemy's documented SAVEPOINT workaround.

    pysqlite does not emit ``BEGIN`` until the first write, so without these
    hooks a SAVEPOINT can open (and its RELEASE can commit) the transaction.
    With them, SQLite's transactions behave like PostgreSQL's and a rollback to
    the savepoint is provably a rollback.
    """

    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection: Any, connection_record: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")

    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE ledger (value INTEGER)")
    return engine


def _values(engine: Any) -> list[int]:
    with engine.connect() as conn:
        return sorted(row[0] for row in conn.exec_driver_sql("SELECT value FROM ledger"))


def test_a_failed_best_effort_block_rolls_back_only_itself() -> None:
    engine = _savepoint_engine()
    with Session(engine) as db:
        db.execute(text("INSERT INTO ledger VALUES (1)"))
        with best_effort(db, "wp69 probe") as attempt:
            db.execute(text("INSERT INTO ledger VALUES (2)"))
            db.execute(text("SELECT missing_column FROM ledger"))
        assert attempt.failed is True
        assert attempt.error is not None
        # The transaction is still the learner's: it keeps working and commits.
        db.execute(text("INSERT INTO ledger VALUES (3)"))
        db.commit()
    # 2 was written inside the failed block and is gone; 1 and 3 survive.
    assert _values(engine) == [1, 3]


def test_a_successful_best_effort_block_keeps_its_work() -> None:
    engine = _savepoint_engine()
    with Session(engine) as db:
        result = run_best_effort(
            db,
            "wp69 success",
            lambda: db.execute(text("INSERT INTO ledger VALUES (7)")) and 7,
            default=None,
        )
        assert result == 7
        db.rollback()
    # Released, not committed: the outer rollback still owns the write.
    assert _values(engine) == []


def test_reraise_types_still_roll_the_savepoint_back() -> None:
    engine = _savepoint_engine()

    class Refusal(RuntimeError):
        pass

    with Session(engine) as db:
        db.execute(text("INSERT INTO ledger VALUES (1)"))
        with pytest.raises(Refusal):
            with best_effort(db, "wp69 refusal", reraise=(Refusal,)):
                db.execute(text("INSERT INTO ledger VALUES (2)"))
                raise Refusal("the state machine must see this")
        db.commit()
    assert _values(engine) == [1]


def test_without_a_savepoint_the_emulated_abort_poisons_the_session(db_session: Session) -> None:
    """The emulation is honest: a swallowed error really does break the request."""

    engine = db_session.get_bind()
    with postgres_abort_semantics(engine):
        # Swallowed on purpose, as L5 did.
        with suppress(Exception):
            db_session.execute(text("SELECT missing_column FROM users"))
        assert session_is_usable(db_session) is False
        db_session.rollback()
        assert session_is_usable(db_session) is True


@pytest.mark.skipif(not os.environ.get("WP69_PG_URL"), reason="set WP69_PG_URL to a throwaway PostgreSQL database")
def test_best_effort_on_real_postgres() -> None:  # pragma: no cover - opt-in
    engine = create_engine(os.environ["WP69_PG_URL"])
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS wp69_ledger")
        conn.exec_driver_sql("CREATE TABLE wp69_ledger (value INTEGER)")
    try:
        with Session(engine) as db:
            db.execute(text("INSERT INTO wp69_ledger VALUES (1)"))
            with best_effort(db, "wp69 pg probe") as attempt:
                db.execute(text("SELECT missing_column FROM wp69_ledger"))
            assert attempt.failed
            assert session_is_usable(db)
            db.execute(text("INSERT INTO wp69_ledger VALUES (2)"))
            db.commit()
        with engine.connect() as conn:
            assert sorted(r[0] for r in conn.exec_driver_sql("SELECT value FROM wp69_ledger")) == [1, 2]
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS wp69_ledger")


# ---------------------------------------------------------------------------
# 2. L5 — a Courrier lookup that raises a real SQL error costs nothing
# ---------------------------------------------------------------------------


def _broken_open_letter(self: MissionScheduler, user: User) -> Any:
    # A real SQL error, as the missing column produced on the dev database.
    return self.db.execute(
        text("SELECT wp69_missing_column FROM real_world_missions WHERE user_id = :uid"),
        {"uid": str(user.id)},
    ).first()


def test_awaiting_letter_survives_a_real_sql_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session)
    monkeypatch.setattr(MissionScheduler, "_open_ad_hoc_letter", _broken_open_letter)
    with postgres_abort_semantics(db_session.get_bind()) as state:
        assert courrier.awaiting_letter(db_session, user=user) is None
        assert state["errors"] >= 1
        # The transaction the learner's request is inside is still usable.
        assert session_is_usable(db_session)
        assert db_session.get(User, user.id) is not None


def test_a_courrier_sql_error_still_yields_a_playable_journey(
    db_session: Session,
    enabled: None,
    letter_provider: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(db_session)
    monkeypatch.setattr(MissionScheduler, "_open_ad_hoc_letter", _broken_open_letter)
    service = DailyJourneyService(db_session, build_adapters())

    with postgres_abort_semantics(db_session.get_bind()) as state:
        snapshot, code = service.create_journey(user, create_request())
        assert state["errors"] >= 1, "the broken lookup must actually have run"

    assert code == 201
    assert_playable(snapshot)
    db_session.expire_all()
    row = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert row is not None and row.status == "active"
    # No letter was offered, so the day is not a letter day.
    assert snapshot.day_shape != "letter"


def test_mark_unavailable_recovers_an_aborted_transaction(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second half of L5: marking the journey unavailable must itself work."""

    user = make_user(db_session)
    service = DailyJourneyService(db_session, build_adapters())
    now = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    snapshot, _ = service.create_journey(user, create_request())
    row = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert row is not None
    row.status = "preparing"
    row.generation_claim_id = "the-claim"
    row.generation_claimed_at = now
    db_session.commit()

    with postgres_abort_semantics(db_session.get_bind()):
        # Poisoned on purpose.
        with suppress(Exception):
            db_session.execute(text("SELECT missing_column FROM daily_journeys"))
        marked, code = service._mark_unavailable(row, "planning_failed")
        db_session.commit()

    assert code == 200
    db_session.expire_all()
    stored = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert stored is not None
    assert stored.status == "unavailable"
    assert stored.unavailable_reason == "planning_failed"
    assert stored.generation_claim_id is None


def test_an_unexpected_generation_crash_never_leaves_preparing(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session)

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("the planner fell over")

    monkeypatch.setattr(DailyJourneyService, "_day_shape_inputs", explode)
    monkeypatch.setattr(journey_module.DailyJourneyService, "_errata_targets", lambda self, user: [])
    service = DailyJourneyService(db_session, build_adapters())
    snapshot, code = service.create_journey(user, create_request())
    assert code == 200
    assert snapshot.status == "unavailable"
    assert snapshot.retry is not None and snapshot.retry.allowed is True


# ---------------------------------------------------------------------------
# 3. L6 — a dead `preparing` journey heals and is regenerated
# ---------------------------------------------------------------------------


def _stuck_preparing(db: Session, journey_id: str, *, claim: str | None, claimed_at: datetime | None) -> None:
    """The journey the 2026-09-22 walk left behind: preparing, no plan, no worker."""

    from app.db.models.daily_journey import DailyJourneyStep

    row = db.get(DailyJourney, uuid.UUID(journey_id))
    assert row is not None
    db.query(DailyJourneyStep).filter(DailyJourneyStep.journey_id == row.id).delete()
    row.status = "preparing"
    row.current_step_id = None
    row.generation_claim_id = claim
    row.generation_claimed_at = claimed_at
    row.generation_attempts = 1
    db.commit()
    db.expire_all()


def test_a_journey_with_no_claim_heals_on_today_and_the_retry_regenerates_it(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session)
    service = DailyJourneyService(db_session, build_adapters())
    now = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    created, _ = service.create_journey(user, create_request())
    _stuck_preparing(db_session, created.id, claim=None, claimed_at=None)

    today = service.get_today(user, timezone_hint="Europe/Paris")
    assert today.journey is not None
    assert today.journey.id == created.id
    assert today.journey.status == "unavailable"
    assert today.journey.retry is not None
    assert today.journey.retry.allowed is True
    assert today.journey.retry.after_seconds == 0

    recovered, code = service.retry_journey(user, uuid.UUID(created.id), retry_request())
    assert code == 201
    assert recovered.id == created.id
    assert_playable(recovered)


def test_an_expired_claim_heals_on_a_journey_read(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session)
    service = DailyJourneyService(db_session, build_adapters())
    now = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    created, _ = service.create_journey(user, create_request())
    _stuck_preparing(db_session, created.id, claim="a-dead-worker", claimed_at=now)

    # While the claim is live, a read changes nothing: the worker may finish.
    assert service.get_journey(user, uuid.UUID(created.id)).status == "preparing"

    freeze(monkeypatch, now + timedelta(seconds=journey_module.GENERATION_CLAIM_TTL_SECONDS + 1))
    healed = service.get_journey(user, uuid.UUID(created.id))
    assert healed.status == "unavailable"
    assert healed.retry is not None and healed.retry.allowed is True

    recovered, code = service.retry_journey(user, uuid.UUID(created.id), retry_request())
    assert code == 201
    assert_playable(recovered)


def test_a_heal_never_overwrites_a_claim_taken_after_the_read(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session)
    service = DailyJourneyService(db_session, build_adapters())
    now = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    created, _ = service.create_journey(user, create_request())
    _stuck_preparing(db_session, created.id, claim=None, claimed_at=None)
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert row is not None
    row_revision = row.revision

    # Another worker reclaims between this read and the heal.
    db_session.execute(
        update(DailyJourney)
        .where(DailyJourney.id == row.id)
        .values(generation_claim_id="fresh-worker", revision=DailyJourney.revision + 1)
        .execution_options(synchronize_session=False)
    )
    db_session.commit()
    # The stale read this request is still holding (not a pending write).
    set_committed_value(row, "revision", row_revision)
    set_committed_value(row, "generation_claim_id", None)
    assert service._heal_interrupted(row) is False
    db_session.expire_all()
    stored = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert stored is not None and stored.status == "preparing"
    assert stored.generation_claim_id == "fresh-worker"


def test_a_still_preparing_answer_is_not_replayed_to_the_same_key(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client reuses one key per intent; a 202 must not freeze that key."""

    user = make_user(db_session)
    service = DailyJourneyService(db_session, build_adapters())
    now = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    created, _ = service.create_journey(user, create_request())
    _stuck_preparing(db_session, created.id, claim="a-live-worker", claimed_at=now)

    key = uuid.uuid4().hex
    waiting, code = service.retry_journey(user, uuid.UUID(created.id), retry_request(key))
    assert code == 202 and waiting.status == "preparing"

    # The worker dies. The same request, asked again, is answered again.
    freeze(monkeypatch, now + timedelta(seconds=journey_module.GENERATION_CLAIM_TTL_SECONDS + 1))
    recovered, code = service.retry_journey(user, uuid.UUID(created.id), retry_request(key))
    assert code == 201
    assert_playable(recovered)


# ---------------------------------------------------------------------------
# 4. The authored day, when the story engine cannot write one
# ---------------------------------------------------------------------------


class _EngineCalls:
    def __init__(self) -> None:
        self.count = 0


@pytest.fixture()
def failing_story_engine(monkeypatch: pytest.MonkeyPatch) -> _EngineCalls:
    """The real content module with the story engine on and always failing."""

    from app.services import living_story

    calls = _EngineCalls()

    def generate_scene(db: Session, *, user: User, input_mode: InputMode) -> ContentUnavailable:
        calls.count += 1
        return ContentUnavailable(reason="scene_rejected_twice")

    monkeypatch.setattr(journey_module.settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False)
    monkeypatch.setattr(
        journey_module.settings, "ATELIER_JOURNEY_AUTHORED_FALLBACK_ENABLED", True, raising=False
    )
    monkeypatch.setattr(living_story, "generate_scene", generate_scene)
    return calls


def _authored_keys() -> set[str]:
    return {str(key) for key in journey_content.SCENARIO_PRIORITY}


@pytest.mark.parametrize(
    ("cefr", "expected_band"),
    [("A1.1", "A1"), ("A2.2", "A2"), ("B1.1", "A2")],
)
def test_a_story_engine_failure_serves_an_authored_day_for_the_band(
    db_session: Session,
    enabled: None,
    failing_story_engine: _EngineCalls,
    cefr: str,
    expected_band: str,
) -> None:
    user = make_user(db_session, cefr=cefr)
    service = DailyJourneyService(db_session, build_adapters(content=journey_content))

    snapshot, code = service.create_journey(user, create_request())

    assert failing_story_engine.count == 1
    assert code == 201
    assert_playable(snapshot)
    assert snapshot.scenario.scenario_key in _authored_keys()
    assert snapshot.scenario.level_band == expected_band
    # Internal telemetry says what happened …
    row = db_session.get(DailyJourney, uuid.UUID(snapshot.id))
    assert row is not None
    marker = (row.plan_selection or {}).get("generation_fallback")
    assert marker is not None
    assert marker["kind"] == "authored"
    assert marker["reason"] == "scene_rejected_twice"
    assert marker["level_band"] == expected_band
    # … and the learner is told nothing about it.
    public = snapshot.model_dump_json()
    assert "fallback" not in public
    assert "scene_rejected_twice" not in public


def test_the_authored_day_is_graded_and_finishable(
    db_session: Session, enabled: None, failing_story_engine: _EngineCalls
) -> None:
    from app.schemas.daily_journey import JourneyAdvanceRequest

    user = make_user(db_session, cefr="A1.2")
    service = DailyJourneyService(db_session, build_adapters(content=journey_content))
    snapshot, _ = service.create_journey(user, create_request())
    assert snapshot.steps[0].kind == "scene"
    advanced = service.advance(
        user,
        uuid.UUID(snapshot.id),
        JourneyAdvanceRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=snapshot.revision,
            current_step_id=snapshot.current_step_id,
        ),
    )
    assert advanced.status == "active"
    assert advanced.current_step_id != snapshot.current_step_id


def test_a_spent_provider_budget_still_gets_the_authored_day_without_a_provider_call(
    db_session: Session,
    enabled: None,
    failing_story_engine: _EngineCalls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(db_session, cefr="A2.1")
    service = DailyJourneyService(db_session, build_adapters(content=journey_content))
    now = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    created, _ = service.create_journey(user, create_request())
    _stuck_preparing(db_session, created.id, claim=None, claimed_at=None)
    row = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert row is not None
    row.generation_attempts = journey_module.MAX_GENERATION_ATTEMPTS
    db_session.commit()
    before = failing_story_engine.count

    healed = service.get_journey(user, uuid.UUID(created.id))
    assert healed.status == "unavailable"
    assert healed.retry is not None and healed.retry.allowed is True

    recovered, code = service.retry_journey(user, uuid.UUID(created.id), retry_request())
    assert code == 201
    assert_playable(recovered)
    assert failing_story_engine.count == before, "no provider call past the budget"
    db_session.expire_all()
    stored = db_session.get(DailyJourney, uuid.UUID(created.id))
    assert stored is not None
    assert stored.plan_selection["generation_fallback"]["reason"] == "generation_attempts_exhausted"


def test_with_the_story_engine_off_a_content_failure_stays_honest(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback is for the story engine only; authored content failing is its own."""

    monkeypatch.setattr(journey_module.settings, "ATELIER_STORY_ENGINE_ENABLED", False, raising=False)

    class FailingContent:
        is_stub = True
        SCENARIO_PRIORITY = journey_content.SCENARIO_PRIORITY
        resolve_scenario_brief = staticmethod(journey_content.resolve_scenario_brief)

        def describe_available_scenario(self, db: Any, *, user: Any, input_mode: Any) -> Any:
            return _MissingContentAdapter().build_scenario_context(db, user=user, input_mode=input_mode)

        def build_scenario_context(self, db: Any, **_kwargs: Any) -> ContentUnavailable:
            return ContentUnavailable(reason="provider_timeout")

    user = make_user(db_session)
    service = DailyJourneyService(db_session, build_adapters(content=FailingContent()))
    snapshot, code = service.create_journey(user, create_request())
    assert code == 200
    assert snapshot.status == "unavailable"


def test_with_the_fallback_switched_off_a_story_failure_is_the_old_honest_dead_end(
    db_session: Session,
    enabled: None,
    failing_story_engine: _EngineCalls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        journey_module.settings, "ATELIER_JOURNEY_AUTHORED_FALLBACK_ENABLED", False, raising=False
    )
    user = make_user(db_session, cefr="A1.1")
    service = DailyJourneyService(db_session, build_adapters(content=journey_content))
    snapshot, code = service.create_journey(user, create_request())
    assert code == 200
    assert snapshot.status == "unavailable"
    assert snapshot.steps == []
