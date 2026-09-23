"""WP-76 (latency half) — reply first, verdict second, and honest time.

What these tests pin, with a *slow fake provider* and never a paid call:

1. The measured respond request records when the character's reply became
   final (``reply_ready_ms``) next to when the verdict was served (``ms``). On
   the story engine the critic reviews reply and verdict together, so the reply
   is final only once the critic has accepted it — the test measures that
   instead of assuming it.
2. An idempotent replay of the same mutation returns the same final attempt and
   pays the provider nothing.
3. The step that held the graded answers declares that server time on its
   ``journey_step_completed`` event, so WP-11's ``active_seconds`` no longer
   bills a 12–17 s reply turn to the learner.
4. The digest reports reply-ready vs verdict percentiles.
"""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.pilot_event import PilotEvent
from app.services import journey_latency
from app.services.journey_events import (
    JOURNEY_ENTITY_TYPE,
    JourneyEventName,
    measure_journey_duration,
)
from app.services.journey_latency import (
    LATENCY_ENTITY_TYPE,
    LATENCY_EVENT,
    PHASE_RESPOND,
    format_latency_lines,
    latency_rollup,
    mark_reply_ready,
    measure_phase,
    record_latency,
    server_wait_ms_since_last_event,
)
from tests import test_journey_end_to_end as support
from tests.test_living_story import FakeProvider, driver

assembled_client = support.assembled_client
journey_enabled = support.journey_enabled

ACTOR_DELAY = 0.25
CRITIC_DELAY = 0.35


class SlowProvider(FakeProvider):
    """The scripted story provider, with a wall-clock cost per stage."""

    def __init__(self) -> None:
        super().__init__()
        self.stage_offsets: list[tuple[str, float]] = []
        self.started: float | None = None

    def generate_chat_completion(self, messages, **kwargs):
        import json

        schema = json.loads(messages[0]["content"])["output_schema"]["title"]
        if schema == "SemanticTurn":
            time.sleep(ACTOR_DELAY)
        elif schema == "Review":
            time.sleep(CRITIC_DELAY)
        result = super().generate_chat_completion(messages, **kwargs)
        if self.started is not None:
            self.stage_offsets.append((schema, time.monotonic() - self.started))
        return result


@pytest.fixture
def slow_provider(monkeypatch):
    from app.config import settings
    from app.services import living_story as engine

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    fake = SlowProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


def _respond_rows(db: Session, journey_id: str) -> list[PilotEvent]:
    rows = db.scalars(
        select(PilotEvent).where(
            PilotEvent.event_type == LATENCY_EVENT,
            PilotEvent.entity_id == journey_id,
        )
    ).all()
    return [row for row in rows if (row.payload or {}).get("phase") == PHASE_RESPOND]


def _to_respond(d) -> dict:
    d.create()
    d.advance()
    return next(s for s in d.journey["steps"] if s["kind"] == "respond")


# ---------------------------------------------------------------------------
# 1 + 2. Reply-ready vs verdict, and the idempotent replay
# ---------------------------------------------------------------------------


def test_reply_ready_is_measured_and_replay_returns_the_same_final_attempt(
    assembled_client, db_session, journey_enabled, slow_provider
):
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    body = {
        "mutation_id": str(uuid.uuid4()),
        "expected_revision": d.journey["revision"],
        "input": {"mode": "text", "text": "Oui, j'apporte les affiches samedi."},
    }
    route = f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts"

    slow_provider.started = time.monotonic()
    first = assembled_client.post(route, json=body, headers=d.headers)
    served = time.monotonic() - slow_provider.started
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["pending"] is False
    assert result["reply_source"] == "model"
    assert result["character_reply_fr"]

    rows = _respond_rows(db_session, d.journey["id"])
    assert len(rows) == 1
    payload = rows[0].payload
    assert "reply_ready_ms" in payload, payload
    reply_ready = payload["reply_ready_ms"] / 1000
    verdict = payload["ms"] / 1000
    # The reply is final before (or when) the verdict is served…
    assert reply_ready <= verdict <= served + 0.05
    # …but never before the critic accepted it: the reviewed reply is the only
    # reply a learner may see, so on this engine reply-ready includes both calls.
    stages = dict(slow_provider.stage_offsets)
    assert stages["SemanticTurn"] >= ACTOR_DELAY
    assert stages["Review"] >= ACTOR_DELAY + CRITIC_DELAY
    assert reply_ready >= ACTOR_DELAY + CRITIC_DELAY - 0.01
    print(
        f"\n[wp76] actor done +{stages['SemanticTurn']:.3f}s · critic done "
        f"+{stages['Review']:.3f}s · reply final +{reply_ready:.3f}s · verdict "
        f"+{verdict:.3f}s · response +{served:.3f}s"
    )

    calls = len(slow_provider.calls)
    again = assembled_client.post(route, json=body, headers=d.headers)
    assert again.status_code == 200
    assert again.json() == result
    assert len(slow_provider.calls) == calls, "a replay must never pay the provider"


# ---------------------------------------------------------------------------
# 3. Server waits are not learner time
# ---------------------------------------------------------------------------


@pytest.fixture
def per_request_client(db_engine):
    """The real router with a fresh session per request, as production runs it.

    The shared-session harness hides one class of bug: a row added after the
    request's last commit survives there (the next request commits it) and is
    silently dropped in production when ``get_db`` closes the session.
    """

    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.api.deps import get_db
    from app.api.v1.endpoints.daily_journey import get_journey_adapters
    from app.main import create_app
    from app.services.daily_journey_adapters import build_default_adapters

    local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    app = create_app()

    def override():
        session = local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_journey_adapters] = build_default_adapters
    with TestClient(app) as client:
        yield client, local


def test_the_graded_step_declares_its_server_wait_and_active_time_excludes_it(
    per_request_client, journey_enabled, slow_provider
):
    client, local = per_request_client
    headers = support.register(client, f"wp76-{uuid.uuid4()}@example.com")
    d = support.Driver(client, headers)
    step = _to_respond(d)
    route = f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts"
    response = client.post(
        route,
        json={
            "mutation_id": str(uuid.uuid4()),
            "expected_revision": d.journey["revision"],
            "input": {"mode": "text", "text": "Oui, j'apporte les affiches samedi."},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    d.journey = response.json()["journey"]
    db = local()
    waited_ms = sum(row.payload["ms"] for row in _respond_rows(db, d.journey["id"]))
    assert waited_ms >= (ACTOR_DELAY + CRITIC_DELAY) * 1000

    advanced = client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/advance",
        json={
            "mutation_id": str(uuid.uuid4()),
            "expected_revision": d.journey["revision"],
            "current_step_id": step["id"],
        },
        headers=headers,
    )
    assert advanced.status_code == 200, advanced.text

    db.expire_all()
    completed = list(
        db.scalars(
            select(PilotEvent).where(
                PilotEvent.entity_type == JOURNEY_ENTITY_TYPE,
                PilotEvent.entity_id == d.journey["id"],
                PilotEvent.event_type == str(JourneyEventName.STEP_COMPLETED),
            )
        ).all()
    )
    # Both advances (scene, then the graded respond step) left their event.
    assert len(completed) == 2, [row.payload for row in completed]
    closing = max(completed, key=lambda row: row.payload.get("ordinal", 0))
    assert closing.payload.get("step_kind") == "respond"
    declared = closing.payload.get("provider_wait_ms")
    assert declared is not None and declared >= waited_ms - 1
    scene_close = min(completed, key=lambda row: row.payload.get("ordinal", 0))
    assert scene_close.payload.get("provider_wait_ms") == 0.0

    duration = measure_journey_duration(db, journey_id=d.journey["id"])
    assert duration.provider_wait_seconds >= (ACTOR_DELAY + CRITIC_DELAY) - 0.01
    db.close()


def test_server_wait_counts_only_requests_after_the_last_event(db_session: Session) -> None:
    journey_id = str(uuid.uuid4())
    base = datetime.now(UTC) - timedelta(minutes=5)

    def latency(at: datetime, ms: int, phase: str = PHASE_RESPOND) -> None:
        row = PilotEvent(
            event_type=LATENCY_EVENT,
            entity_type=LATENCY_ENTITY_TYPE,
            entity_id=journey_id,
            payload={"phase": phase, "ms": ms, "seconds": ms / 1000, "outcome": "ok"},
        )
        row.occurred_at = at
        db_session.add(row)

    latency(base + timedelta(seconds=10), 9_000)  # before the last event: its own segment
    started = PilotEvent(
        event_type=str(JourneyEventName.STARTED),
        entity_type=JOURNEY_ENTITY_TYPE,
        entity_id=journey_id,
        payload={},
    )
    started.occurred_at = base + timedelta(seconds=30)
    db_session.add(started)
    latency(base + timedelta(seconds=60), 12_600)
    latency(base + timedelta(seconds=90), 800)
    latency(base + timedelta(seconds=95), 20_000, phase="draft")  # not an answer
    db_session.commit()

    assert server_wait_ms_since_last_event(db_session, journey_id=journey_id) == 13_400
    assert server_wait_ms_since_last_event(db_session, journey_id=str(uuid.uuid4())) == 0.0


# ---------------------------------------------------------------------------
# The mark itself
# ---------------------------------------------------------------------------


def test_mark_is_a_noop_outside_a_measured_request_and_first_mark_wins(
    db_session: Session,
) -> None:
    assert mark_reply_ready() is None
    with measure_phase(db_session, user=None, phase=PHASE_RESPOND, journey_id="j-1") as timing:
        time.sleep(0.02)
        first = mark_reply_ready()
        time.sleep(0.02)
        assert mark_reply_ready() == first
        assert timing.reply_ready_seconds == first
    assert mark_reply_ready() is None, "the mark must not leak past its request"
    row = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == LATENCY_EVENT)
    ).all()[-1]
    assert row.payload["reply_ready_ms"] >= 20
    assert row.payload["reply_ready_ms"] <= row.payload["ms"]


def test_a_recall_answer_carries_no_reply_mark(db_session: Session) -> None:
    with measure_phase(db_session, user=None, phase=PHASE_RESPOND, journey_id="j-2"):
        pass
    row = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == LATENCY_EVENT)
    ).all()[-1]
    assert "reply_ready_ms" not in row.payload


# ---------------------------------------------------------------------------
# 4. The digest
# ---------------------------------------------------------------------------


def test_rollup_and_digest_report_reply_ready_against_the_verdict(
    db_session: Session,
) -> None:
    from tests.test_journey_latency import make_user

    user = make_user(db_session, f"wp76-digest-{uuid.uuid4()}@example.com")
    # The pilot ledger's day is a Europe/Berlin day (`pilot_events._day_bounds`);
    # the UTC date is yesterday's between 00:00 and 02:00 Berlin time.
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    for ready, total in ((11.0, 12.6), (13.0, 13.4), (15.5, 17.0)):
        record_latency(
            db_session,
            user=user,
            phase=PHASE_RESPOND,
            seconds=total,
            journey_id="j-3",
            reply_ready_seconds=ready,
        )
    record_latency(db_session, user=user, phase=PHASE_RESPOND, seconds=0.2, journey_id="j-3")
    db_session.commit()

    rollup = latency_rollup(db_session, today, user_id=user.id)
    reply = rollup["reply"]
    assert reply["samples"] == 3
    assert reply["ready_p50_seconds"] == 13.0
    assert reply["to_verdict_p50_seconds"] == pytest.approx(1.5, abs=0.01)
    assert rollup["phases"][PHASE_RESPOND]["samples"] == 4
    lines = format_latency_lines(rollup)
    assert any(line.strip().startswith("reply turns: n=3") for line in lines), lines
    assert journey_latency.GATE_SECONDS[PHASE_RESPOND] == 20.0
