"""WP-70 — a scripted abuse loop hits 429 on auth, on a paid route, and on the cap."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_llm_service
from app.config import settings
from app.core import rate_limit
from app.core.rate_limit import (
    PAID_ROUTES,
    MemoryRateLimitBackend,
    RateLimiter,
    RedisRateLimitBackend,
    client_ip,
    limiter,
)
from app.core.security import create_access_token
from app.db.models.daily_journey import DailyJourney
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.main import create_app
from app.services import spend_guard

ABUSER = ("203.0.113.7", 50000)


class _FakeSpeech:
    def __init__(self) -> None:
        self.calls = 0

    def text_to_speech(self, *, text: str, voice: str, provider: str | None) -> bytes:
        self.calls += 1
        return b"ID3-fake"


@pytest.fixture(autouse=True)
def _memory_limiter() -> Generator[None, None, None]:
    limiter.use_backend(MemoryRateLimitBackend())
    yield
    limiter.use_backend(None)


@pytest.fixture()
def speech() -> _FakeSpeech:
    return _FakeSpeech()


@pytest.fixture()
def abuser_client(db_session: Session, speech: _FakeSpeech) -> Generator[TestClient, None, None]:
    """A client whose socket peer is a real-looking address (not TestClient's exempt one)."""

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_llm_service] = lambda: speech
    with TestClient(app, client=ABUSER) as client:
        yield client


def _learner(db: Session) -> tuple[User, dict[str, str]]:
    user = User(
        email=f"wp70-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-used",
        target_language="fr",
        proficiency_level="A2",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), auth_version=int(user.auth_version or 0))
    return user, {"Authorization": f"Bearer {token}"}


def _assert_429(response, code: str) -> None:  # type: ignore[no-untyped-def]
    assert response.status_code == 429, response.text
    body = response.json()["detail"]
    assert body["code"] == code
    assert body["message"]
    retry_after = int(response.headers["Retry-After"])
    assert retry_after >= 1
    assert body["retry_after_seconds"] == retry_after


# ---------------------------------------------------------------------------
# auth — per IP
# ---------------------------------------------------------------------------


def test_a_login_loop_from_one_ip_hits_429(abuser_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX_REQUESTS", 5)
    statuses = [
        abuser_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": f"guess-{n}-Aa1!"},
        ).status_code
        for n in range(5)
    ]
    assert 429 not in statuses
    _assert_429(
        abuser_client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "guess-6-Aa1!"}
        ),
        "rate_limited",
    )
    # Another network is not punished for this one's script …
    other = abuser_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "x-Aa1!xyz"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    )
    assert other.status_code != 429


def test_register_and_password_reset_are_limited_per_ip(abuser_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX_REQUESTS", 2)
    for _ in range(2):
        assert abuser_client.post("/api/v1/auth/register", json={}).status_code != 429
    _assert_429(abuser_client.post("/api/v1/auth/register", json={}), "rate_limited")

    for _ in range(2):
        response = abuser_client.post(
            "/api/v1/auth/password-reset/request", json={"email": "someone@example.com"}
        )
        assert response.status_code != 429
    _assert_429(
        abuser_client.post("/api/v1/auth/password-reset/request", json={"email": "someone@example.com"}),
        "rate_limited",
    )


def test_refresh_is_never_rate_limited(abuser_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX_REQUESTS", 1)
    for _ in range(4):
        response = abuser_client.post("/api/v1/auth/refresh", json={"refresh_token": "nope"})
        assert response.status_code != 429


def test_the_forwarded_client_is_read_from_the_right(monkeypatch) -> None:
    from starlette.requests import Request

    def request(xff: str | None) -> Request:
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request({"type": "http", "headers": headers, "client": ("10.0.0.1", 1)})

    monkeypatch.setattr(settings, "RATE_LIMIT_TRUSTED_PROXY_HOPS", 1)
    # A client may prepend anything; only the entry our proxy appended counts.
    assert client_ip(request("1.1.1.1, 203.0.113.9")) == "203.0.113.9"
    assert client_ip(request(None)) == "10.0.0.1"
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUSTED_PROXY_HOPS", 0)
    assert client_ip(request("1.1.1.1")) == "10.0.0.1"


# ---------------------------------------------------------------------------
# paid routes — per learner
# ---------------------------------------------------------------------------


def test_a_paid_endpoint_loop_hits_429(abuser_client: TestClient, db_session: Session, speech, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_PAID_MAX_REQUESTS", 3)
    _user, headers = _learner(db_session)
    for _ in range(3):
        assert abuser_client.post("/api/v1/audio/speak", json={"text": "Bonjour"}, headers=headers).status_code == 200
    _assert_429(
        abuser_client.post("/api/v1/audio/speak", json={"text": "Bonjour"}, headers=headers),
        "rate_limited",
    )
    assert speech.calls == 3, "the limited request must never reach the provider"

    # The limit is the learner's, not the network's.
    _other, other_headers = _learner(db_session)
    assert abuser_client.post("/api/v1/audio/speak", json={"text": "Salut"}, headers=other_headers).status_code == 200


def test_free_routes_on_a_paid_router_are_not_counted(abuser_client: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_PAID_MAX_REQUESTS", 1)
    _user, headers = _learner(db_session)
    for _ in range(3):
        assert abuser_client.get("/api/v1/audio-session/scenarios", headers=headers).status_code == 200


def test_speech_is_now_on_the_ledger(abuser_client: TestClient, db_session: Session) -> None:
    user, headers = _learner(db_session)
    assert abuser_client.post("/api/v1/audio/speak", json={"text": "Bonjour à tous"}, headers=headers).status_code == 200
    rows = db_session.scalars(
        select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == "audio_speech")
    ).all()
    assert len(rows) == 1
    assert rows[0].cost_usd > 0
    assert rows[0].payload["estimated"] is True


def test_the_test_client_peer_is_exempt(client: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX_REQUESTS", 1)
    for _ in range(3):
        assert client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x-Aa1!xyz"}).status_code != 429


def test_every_paid_route_exists() -> None:
    """A renamed route must not silently fall out of the guard."""

    app = create_app()
    prefix = settings.API_V1_STR
    served = {
        (method, route.path[len(prefix):])
        for route in app.routes
        if getattr(route, "methods", None) and route.path.startswith(prefix)
        for method in route.methods
    }
    assert set(PAID_ROUTES) - served == set()


# ---------------------------------------------------------------------------
# the daily spend cap
# ---------------------------------------------------------------------------


def _spend(db: Session, user: User, amount: float, *, event_type: str = "atelier_correction", when=None) -> None:  # type: ignore[no-untyped-def]
    db.add(
        PilotEvent(
            user_id=user.id,
            event_type=event_type,
            payload={},
            cost_usd=amount,
            occurred_at=when or datetime.now(UTC),
        )
    )
    db.commit()


def test_the_daily_cap_answers_daily_budget_reached_before_the_provider(
    abuser_client: TestClient, db_session: Session, speech, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)
    user, headers = _learner(db_session)
    _spend(db_session, user, 0.30)
    assert abuser_client.post("/api/v1/audio/speak", json={"text": "Encore"}, headers=headers).status_code == 200
    _spend(db_session, user, 0.25)
    response = abuser_client.post("/api/v1/audio/speak", json={"text": "Encore"}, headers=headers)
    _assert_429(response, "daily_budget_reached")
    assert speech.calls == 1
    assert int(response.headers["Retry-After"]) <= 24 * 3600


def test_the_cap_covers_the_daily_journey_router(abuser_client: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)
    user, headers = _learner(db_session)
    _spend(db_session, user, 0.75, event_type="journey_story_turn_cost")
    before = db_session.scalar(select(func.count(DailyJourney.id)).where(DailyJourney.user_id == user.id))
    _assert_429(abuser_client.post("/api/v1/daily-journeys", json={}, headers=headers), "daily_budget_reached")
    after = db_session.scalar(select(func.count(DailyJourney.id)).where(DailyJourney.user_id == user.id))
    assert before == after == 0


def test_a_normal_day_never_touches_the_cap(abuser_client: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)
    user, headers = _learner(db_session)
    # WP-68's measured Séance: about five cents, in a dozen priced calls.
    for _ in range(12):
        _spend(db_session, user, 0.0045)
    assert abuser_client.post("/api/v1/audio/speak", json={"text": "Bonjour"}, headers=headers).status_code == 200


def test_yesterday_does_not_count_and_zero_switches_the_cap_off(db_session: Session, monkeypatch) -> None:
    user, _headers = _learner(db_session)
    _spend(db_session, user, 5.0, when=datetime.now(UTC) - timedelta(days=1, hours=1))
    assert spend_guard.spend_today_usd(db_session, user.id) == 0.0
    _spend(db_session, user, 5.0)
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.0)
    spend_guard.enforce_daily_budget(db_session, user)  # no raise


def test_scene_ledgers_are_not_counted_twice(db_session: Session) -> None:
    user, _headers = _learner(db_session)
    _spend(db_session, user, 0.10)  # an unrelated correction
    _spend(db_session, user, 0.20, event_type="journey_story_scene_cost")
    db_session.add(
        GraphicNovelScene(
            user_id=user.id,
            cache_key=f"wp70-{uuid.uuid4().hex}",
            status="ready",
            title="Scène",
            brief="Une scène.",
            prompt_version="wp70-test",
            image_model="none",
            image_quality="none",
            script_payload={"estimated_cost": {"total_estimated_usd": 0.25}},
        )
    )
    db_session.commit()
    # 0.10 + max(0.20 on the event ledger, 0.25 on the scene ledger)
    assert spend_guard.spend_today_usd(db_session, user.id) == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# backends
# ---------------------------------------------------------------------------


class _FakePipeline:
    def __init__(self, store: dict[str, int]) -> None:
        self.store = store
        self.ops: list[tuple[str, str]] = []

    def incr(self, key: str) -> None:
        self.ops.append(("incr", key))

    def expire(self, key: str, seconds: int) -> None:
        self.ops.append(("expire", key))

    def execute(self) -> list[int]:
        results = []
        for op, key in self.ops:
            if op == "incr":
                self.store[key] = self.store.get(key, 0) + 1
                results.append(self.store[key])
            else:
                results.append(True)
        return results


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self, transaction: bool = False) -> _FakePipeline:
        return _FakePipeline(self.store)


def test_the_redis_backend_counts_a_shared_window() -> None:
    backend = RedisRateLimitBackend(_FakeRedis(), clock=lambda: 1_000.0)
    decisions = [backend.hit("paid:x", limit=2, window_seconds=60) for _ in range(3)]
    assert [d.allowed for d in decisions] == [True, True, False]
    assert decisions[-1].retry_after_seconds == 20  # the window 960-1020 ends in 20 s


def test_a_redis_outage_falls_back_to_memory(monkeypatch) -> None:
    class _Broken:
        def hit(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise ConnectionError("redis down")

    fallback = RateLimiter()
    monkeypatch.setattr(fallback, "_redis_backend", lambda: _Broken())
    decisions = [fallback.hit("auth:login:1.2.3.4", limit=1, window_seconds=60) for _ in range(2)]
    assert [d.allowed for d in decisions] == [True, False]


def test_the_memory_window_resets() -> None:
    now = {"t": 0.0}
    backend = MemoryRateLimitBackend(clock=lambda: now["t"])
    assert backend.hit("k", limit=1, window_seconds=10).allowed
    assert not backend.hit("k", limit=1, window_seconds=10).allowed
    now["t"] = 10.5
    assert backend.hit("k", limit=1, window_seconds=10).allowed


def test_the_limiter_can_be_switched_off(abuser_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX_REQUESTS", 1)
    for _ in range(3):
        assert abuser_client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x-Aa1!xyz"}).status_code != 429
    assert rate_limit.RATE_LIMITED_CODE == "rate_limited"
