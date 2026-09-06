"""Concurrency: real simultaneous HTTP requests, not two sequential service calls.

CONTRACTS §5 requires the transaction tests to exercise concurrent requests.
The shared in-memory ``StaticPool`` database used elsewhere in the suite has a
single connection, so this module builds its own file-backed SQLite database in
WAL mode where each request thread gets a real connection of its own.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.api.v1.endpoints.daily_journey import get_journey_adapters
from app.config import settings
from app.db.base import Base
from app.db.models.atelier import AtelierSession
from app.db.models.daily_journey import (
    DailyJourney,
    DailyJourneyMutation,
    DailyJourneyStep,
)
from app.db.models.session import LearningSession
from app.db.models.user import RefreshToken, User
from app.main import create_app
from tests.test_daily_journey_api import TEST_PASSWORD, TZ, key, stub_adapters

CONCURRENCY = 6


@dataclass
class Harness:
    app: Any
    session_factory: sessionmaker
    headers: dict[str, str]

    def client(self) -> TestClient:
        """A fresh client per thread; the app and database are shared."""

        return TestClient(self.app)


@pytest.fixture()
def harness(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Generator[Harness, None, None]:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")

    engine = create_engine(
        f"sqlite:///{tmp_path / 'journey-concurrency.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _record):  # pragma: no cover - setup
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    tables = [
        User.__table__,
        RefreshToken.__table__,
        AtelierSession.__table__,
        LearningSession.__table__,
        DailyJourney.__table__,
        DailyJourneyStep.__table__,
        DailyJourneyMutation.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = create_app()

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_journey_adapters] = stub_adapters

    email = f"concurrent-{uuid.uuid4().hex[:8]}@example.com"
    with TestClient(app) as setup_client:
        setup_client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": TEST_PASSWORD,
                "target_language": "fr",
                "native_language": "en",
            },
        )
        login = setup_client.post(
            "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    try:
        yield Harness(app=app, session_factory=session_factory, headers=headers)
    finally:
        Base.metadata.drop_all(bind=engine, tables=list(reversed(tables)))
        engine.dispose()


def _run_together(work, count: int = CONCURRENCY) -> list[Any]:
    """Release ``count`` threads from the same barrier and collect the results."""

    barrier = threading.Barrier(count)

    def runner(index: int) -> Any:
        barrier.wait(timeout=30)
        return work(index)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(runner, range(count)))


def test_simultaneous_creates_produce_exactly_one_journey(harness: Harness) -> None:
    def create(_index: int) -> Any:
        client = harness.client()
        return client.post(
            "/api/v1/daily-journeys",
            headers=harness.headers,
            json={
                "mutation_id": key(),
                "timezone": TZ,
                "budget_seconds": 300,
                "preferred_input_mode": "text",
            },
        )

    responses = _run_together(create)

    assert all(response.status_code in (200, 201, 202) for response in responses), [
        (r.status_code, r.text) for r in responses
    ]
    ids = {response.json()["id"] for response in responses}
    assert len(ids) == 1, f"concurrent creates produced {len(ids)} journeys"

    with harness.session_factory() as db:
        assert db.query(DailyJourney).count() == 1
        journey = db.query(DailyJourney).one()
        assert journey.status in {"active", "preparing"}
        assert db.query(DailyJourneyStep).filter(
            DailyJourneyStep.journey_id == journey.id
        ).count() in (0, 4)


def test_simultaneous_creates_with_one_shared_key_still_produce_one_journey(
    harness: Harness,
) -> None:
    mutation_id = key()

    def create(_index: int) -> Any:
        client = harness.client()
        return client.post(
            "/api/v1/daily-journeys",
            headers=harness.headers,
            json={
                "mutation_id": mutation_id,
                "timezone": TZ,
                "budget_seconds": 300,
                "preferred_input_mode": "text",
            },
        )

    responses = _run_together(create)

    assert all(response.status_code in (200, 201, 202) for response in responses)
    with harness.session_factory() as db:
        assert db.query(DailyJourney).count() == 1
        # One receipt for one key, never a duplicate row.
        assert (
            db.query(DailyJourneyMutation)
            .filter(DailyJourneyMutation.mutation_id == mutation_id)
            .count()
            == 1
        )


def _reach_respond_step(harness: Harness) -> tuple[dict[str, Any], dict[str, Any]]:
    client = harness.client()
    created = client.post(
        "/api/v1/daily-journeys",
        headers=harness.headers,
        json={
            "mutation_id": key(),
            "timezone": TZ,
            "budget_seconds": 300,
            "preferred_input_mode": "text",
        },
    )
    assert created.status_code == 201, created.text
    state = created.json()
    journey_id = state["id"]

    def step(kind: str) -> dict[str, Any]:
        return next(item for item in state["steps"] if item["kind"] == kind)

    scene = step("scene")
    state = client.post(
        f"/api/v1/daily-journeys/{journey_id}/advance",
        headers=harness.headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "current_step_id": scene["id"],
        },
    ).json()
    recall = step("recall")
    state = client.post(
        f"/api/v1/daily-journeys/{journey_id}/steps/{recall['id']}/attempts",
        headers=harness.headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "input": {"mode": "choice", "option_id": "opt_a"},
        },
    ).json()["journey"]
    state = client.post(
        f"/api/v1/daily-journeys/{journey_id}/advance",
        headers=harness.headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "current_step_id": recall["id"],
        },
    ).json()
    return state, step("respond")


def test_a_duplicated_attempt_key_never_consumes_two_turns(harness: Harness) -> None:
    state, respond = _reach_respond_step(harness)
    url = (
        f"/api/v1/daily-journeys/{state['id']}/steps/{respond['id']}/attempts"
    )
    body = {
        "mutation_id": key(),
        "expected_revision": state["revision"],
        "input": {"mode": "text", "text": "Je voudrais un café, s'il vous plaît."},
    }

    def submit(_index: int) -> Any:
        return harness.client().post(url, headers=harness.headers, json=body)

    responses = _run_together(submit)

    codes = sorted(response.status_code for response in responses)
    assert set(codes) <= {200, 202}, [(r.status_code, r.text) for r in responses]
    assert 200 in codes

    with harness.session_factory() as db:
        step = db.get(DailyJourneyStep, uuid.UUID(respond["id"]))
        assert step is not None
        # One accepted answer: one consumed turn, one evidence reference.
        assert step.turns_used == 1
        assert step.status == "completed"
        journey = db.get(DailyJourney, uuid.UUID(state["id"]))
        assert journey is not None
        assert journey.revision == state["revision"] + 1
        assert (
            db.query(DailyJourneyMutation)
            .filter(DailyJourneyMutation.mutation_id == body["mutation_id"])
            .count()
            == 1
        )

    successes = [r for r in responses if r.status_code == 200]
    payloads = {r.text for r in successes}
    assert len(payloads) == 1, "committed replays must be byte-identical"


def test_concurrent_distinct_advances_do_not_skip_a_step(harness: Harness) -> None:
    """Only one of two racing advances may win; the other sees a conflict."""

    client = harness.client()
    created = client.post(
        "/api/v1/daily-journeys",
        headers=harness.headers,
        json={
            "mutation_id": key(),
            "timezone": TZ,
            "budget_seconds": 300,
            "preferred_input_mode": "text",
        },
    ).json()
    scene = next(item for item in created["steps"] if item["kind"] == "scene")

    def advance(_index: int) -> Any:
        return harness.client().post(
            f"/api/v1/daily-journeys/{created['id']}/advance",
            headers=harness.headers,
            json={
                "mutation_id": key(),
                "expected_revision": created["revision"],
                "current_step_id": scene["id"],
            },
        )

    responses = _run_together(advance, count=4)
    accepted = [r for r in responses if r.status_code == 200]
    conflicted = [r for r in responses if r.status_code == 409]

    assert len(accepted) == 1, [(r.status_code, r.text) for r in responses]
    assert len(conflicted) == len(responses) - 1
    assert all(
        r.json()["detail"]["code"]
        in {"journey_version_conflict", "step_not_active"}
        for r in conflicted
    )

    with harness.session_factory() as db:
        journey = db.get(DailyJourney, uuid.UUID(created["id"]))
        assert journey is not None
        assert journey.revision == created["revision"] + 1
        completed = (
            db.query(DailyJourneyStep)
            .filter(
                DailyJourneyStep.journey_id == journey.id,
                DailyJourneyStep.status == "completed",
            )
            .count()
        )
        assert completed == 1
