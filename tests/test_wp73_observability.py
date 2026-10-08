"""WP-73 — see production: logs with extras, request ids, Sentry capture without PII,
pre-sign-in crash intake, worker heartbeat."""
from __future__ import annotations

import io
import json
import logging
from collections.abc import Generator

import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from loguru import logger
from sentry_sdk.transport import Transport

from app.api.deps import get_db
from app.core import observability
from app.core.rate_limit import MemoryRateLimitBackend, limiter
from app.main import create_app

FAKE_DSN = "https://public@o0.ingest.sentry.io/1"
LEARNER_TEXT = "Je voudrais un croissant, s'il vous plaît"


class CaptureTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            event = item.get_event()
            if event is not None:
                self.events.append(event)

    def flush(self, *args, **kwargs):
        return None


@pytest.fixture()
def sentry_capture() -> Generator[CaptureTransport, None, None]:
    transport = CaptureTransport()
    observability.init_sentry("api", transport=transport, dsn=FAKE_DSN)
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.init(dsn=None)
    observability._sentry_ready = False


@pytest.fixture()
def memory_limiter() -> Generator[None, None, None]:
    limiter.use_backend(MemoryRateLimitBackend())
    yield
    limiter.use_backend(None)


# --------------------------------------------------------------------------- logs


def test_json_log_line_includes_extras_and_request_id() -> None:
    stream = io.StringIO()
    observability.configure_logging(fmt="json", stream=stream)
    try:
        token = observability.request_id_var.set("req-12345678")
        try:
            logger.error("OpenAI TTS error", status=502, provider="openai")
        finally:
            observability.request_id_var.reset(token)
        line = json.loads(stream.getvalue().strip().splitlines()[-1])
    finally:
        observability.configure_logging(fmt="text")
    assert line["message"] == "OpenAI TTS error"
    assert line["level"] == "ERROR"
    assert line["request_id"] == "req-12345678"
    assert line["extra"] == {"status": 502, "provider": "openai"}


def test_text_log_line_renders_extras_and_stdlib_is_intercepted() -> None:
    stream = io.StringIO()
    observability.configure_logging(fmt="text", stream=stream)
    try:
        logger.warning("Rate limiter degraded", backend="memory")
        logging.getLogger("uvicorn.error").warning("stdlib says hello")
    finally:
        observability.configure_logging(fmt="text")
    out = stream.getvalue()
    assert "Rate limiter degraded" in out and "backend='memory'" in out
    assert "stdlib says hello" in out


def test_json_is_the_production_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    assert observability.log_format() == "json"
    monkeypatch.setenv("APP_ENV", "development")
    assert observability.log_format() == "text"


# ----------------------------------------------------------------- request ids


def test_request_id_is_created_echoed_and_rejected_when_unsafe(client: TestClient) -> None:
    fresh = client.get("/health")
    assert len(fresh.headers["x-request-id"]) == 32
    echoed = client.get("/health", headers={"X-Request-ID": "ios-abcdef12"})
    assert echoed.headers["x-request-id"] == "ios-abcdef12"
    hostile = client.get("/health", headers={"X-Request-ID": "x\"; drop"})
    assert hostile.headers["x-request-id"] != "x\"; drop"


# ---------------------------------------------------------------------- sentry


def test_sentry_is_a_no_op_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert observability.init_sentry("api") is False
    assert observability.sentry_enabled() is False


def test_api_crash_reaches_sentry_with_request_id_and_no_pii(db_session, sentry_capture) -> None:
    app = create_app()

    @app.post("/__wp73_boom")
    async def boom(payload: dict) -> None:
        raise RuntimeError("wp73 api boom")

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/__wp73_boom?token=secret-reset-code",
            json={"text": LEARNER_TEXT},
            headers={
                "X-Request-ID": "wp73-api-0001",
                "Authorization": "Bearer secret.jwt.token",
                "Cookie": "session=abc",
            },
        )
    assert response.status_code == 500
    sentry_sdk.flush()
    events = [e for e in sentry_capture.events if "wp73 api boom" in json.dumps(e)]
    assert events, sentry_capture.events
    event = events[0]
    assert event["tags"]["request_id"] == "wp73-api-0001"
    for exc in event["exception"]["values"]:
        for frame in exc["stacktrace"]["frames"]:  # source lines of this test file, not data
            for key in ("pre_context", "context_line", "post_context"):
                frame.pop(key, None)
    blob = json.dumps(event)
    for secret in (LEARNER_TEXT, "secret.jwt.token", "secret-reset-code", "session=abc"):
        assert secret not in blob
    assert "vars" not in blob or all(
        "vars" not in frame for exc in event["exception"]["values"] for frame in exc["stacktrace"]["frames"]
    )


def test_celery_task_crash_reaches_sentry_with_request_id() -> None:
    from app.celery_app import celery_app

    transport = CaptureTransport()
    observability.init_sentry("worker", transport=transport, dsn=FAKE_DSN)
    try:
        @celery_app.task(name="tests.wp73.boom")
        def boom(text: str) -> None:
            raise ValueError("wp73 task boom")

        token = observability.request_id_var.set("wp73-task-0001")
        try:
            result = boom.apply(args=(LEARNER_TEXT,), headers={"request_id": "wp73-task-0001"})
        finally:
            observability.request_id_var.reset(token)
        assert result.failed()
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init(dsn=None)
        observability._sentry_ready = False
    events = [e for e in transport.events if "wp73 task boom" in json.dumps(e)]
    assert events
    assert events[0]["tags"]["request_id"] == "wp73-task-0001"
    assert LEARNER_TEXT not in json.dumps(events[0])


def test_scrub_event_keeps_user_id_only() -> None:
    event = observability.scrub_event(
        {
            "user": {"id": "u-1", "email": "a@b.c", "ip_address": "1.2.3.4"},
            "request": {"data": LEARNER_TEXT, "headers": {"Authorization": "Bearer x", "User-Agent": "ua"}},
        }
    )
    assert event["user"] == {"id": "u-1"}
    assert "data" not in event["request"]
    assert event["request"]["headers"] == {"User-Agent": "ua"}


# --------------------------------------------------------- pre-sign-in crashes


def test_anonymous_crash_report_is_accepted_without_auth(client: TestClient, db_session, memory_limiter) -> None:
    from app.db.models.pilot_event import PilotEvent

    response = client.post(
        "/api/v1/analytics/client-error/anonymous",
        json={"message": "TypeError: x is undefined", "route": "/onboarding?code=123456", "source": "capacitor"},
        headers={"X-Request-ID": "wp73-crash-0001"},
    )
    assert response.status_code == 204
    events = db_session.query(PilotEvent).filter(PilotEvent.event_type == "client_crash").all()
    event = next(e for e in events if (e.payload or {}).get("request_id") == "wp73-crash-0001")
    assert event.user_id is None
    assert event.payload["route"] == "/onboarding"
    assert event.payload["request_id"] == "wp73-crash-0001"


def test_anonymous_crash_report_refuses_unknown_fields_and_sources(client: TestClient, memory_limiter) -> None:
    url = "/api/v1/analytics/client-error/anonymous"
    assert client.post(url, json={"message": "x", "email": "a@b.c"}).status_code == 422
    assert client.post(url, json={"message": "x", "source": "evil"}).status_code == 422
    big = client.post(url, content=b'{"message":"' + b"a" * 20_000 + b'"}', headers={"Content-Type": "application/json"})
    assert big.status_code == 413


def test_anonymous_crash_report_is_rate_limited(
    client: TestClient, memory_limiter, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_EXEMPT_PEERS", "")
    url = "/api/v1/analytics/client-error/anonymous"
    codes = [client.post(url, json={"message": f"boom {i}"}).status_code for i in range(12)]
    assert codes[:10] == [204] * 10
    assert codes[10] == 429


# --------------------------------------------------------------- worker health


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key, value, ex=None):
        self.store[key] = value

    def get(self, key):
        value = self.store.get(key)
        return value.encode() if value is not None else None


def test_heartbeat_staleness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_HEARTBEAT_STALE_SECONDS", "300")
    redis = FakeRedis()
    assert observability.worker_health(redis, now=1000.0)["status"] == "missing"
    observability.write_heartbeat(redis, now=1000.0)
    assert observability.worker_health(redis, now=1100.0)["status"] == "ok"
    stale = observability.worker_health(redis, now=1400.0)
    assert stale["status"] == "stale" and stale["age_seconds"] == 400.0


def test_worker_health_endpoint_is_separate_from_ready(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(observability, "_redis_client", lambda: redis)
    assert client.get("/health/worker").status_code == 503
    observability.write_heartbeat(redis)
    body = client.get("/health/worker").json()
    assert body["status"] == "ok"

    def unreachable():
        raise ConnectionError("down")

    monkeypatch.setattr(observability, "_redis_client", unreachable)
    assert client.get("/health/worker").json()["status"] == "unreachable"


def test_heartbeat_is_on_the_beat_schedule() -> None:
    import app.tasks.health  # noqa: F401 — the worker imports it through ``include``
    from app.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["worker-heartbeat"]
    assert entry["task"] == "app.tasks.health.worker_heartbeat"
    assert "app.tasks.health.worker_heartbeat" in celery_app.tasks

