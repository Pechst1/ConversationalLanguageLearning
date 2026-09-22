"""WP-70 — rate limits, as FastAPI dependencies.

Two kinds, both answering ``429`` with a ``Retry-After`` header and a stable
``detail.code`` (the shape of ``daily_journey.journey_error``):

* **Per IP on the doors that take a password** — ``/auth/login``,
  ``/auth/register`` and every ``/auth/password-reset…`` route — so a script
  cannot guess passwords, mass-register or mail-bomb reset codes. Applied at
  the router include in ``app/api/v1/api.py`` (``auth_rate_limit``), which
  keeps ``endpoints/auth.py`` untouched. ``/auth/refresh`` is deliberately not
  limited: a phone waking up fires several refreshes at once.
* **Per learner on every paid route** — anything that calls a model, speech,
  transcription or image provider (:data:`PAID_ROUTES`). The same dependency
  also enforces the per-learner daily spend cap
  (:mod:`app.services.spend_guard`) before the provider is called.

Counters are fixed windows in Redis (``REDIS_URL``) so every uvicorn worker
shares them; when Redis is unreachable the limiter falls back to a per-process
in-memory window (and retries Redis after a short pause), so a Redis outage
degrades the limit rather than the app. Every dependency here is a plain
``def``: FastAPI runs it in the thread pool, so a slow Redis never touches the
event loop.

Client IP: behind Render's proxy the TCP peer is the proxy, so the address is
read from ``X-Forwarded-For`` counting ``RATE_LIMIT_TRUSTED_PROXY_HOPS`` entries
from the right (the entries our own proxies appended; anything to their left is
client-supplied and forgeable).
"""
from __future__ import annotations

import importlib
import importlib.util
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings

RATE_LIMITED_CODE = "rate_limited"


def _setting(name: str, default: Any) -> Any:
    value = getattr(settings, name, None)
    return default if value is None else value


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int


class RateLimitBackend(Protocol):
    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateDecision: ...


def _window(window_seconds: int, now: float) -> tuple[int, int]:
    """``(window index, seconds until it ends)`` for a fixed window."""

    index = int(now // window_seconds)
    retry_after = max(1, math.ceil((index + 1) * window_seconds - now))
    return index, retry_after


class MemoryRateLimitBackend:
    """Per-process fixed windows. Used for tests, dev, and when Redis is down."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, int]] = {}

    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateDecision:
        index, retry_after = _window(window_seconds, self._clock())
        with self._lock:
            window_index, count = self._counts.get(key, (index, 0))
            if window_index != index:
                count = 0
            count += 1
            self._counts[key] = (index, count)
            if len(self._counts) > 50_000:  # bound memory under a key-spraying script
                self._counts = {k: v for k, v in self._counts.items() if v[0] == index}
        return RateDecision(count <= limit, count, limit, retry_after)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


class RedisRateLimitBackend:
    """Fixed windows shared by every worker: ``INCR`` + ``EXPIRE`` in one round trip."""

    def __init__(self, client: Any, clock: Callable[[], float] = time.time) -> None:
        self._client = client
        self._clock = clock

    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateDecision:
        index, retry_after = _window(window_seconds, self._clock())
        redis_key = f"wp70:rl:{key}:{index}"
        pipeline = self._client.pipeline(transaction=False)
        pipeline.incr(redis_key)
        pipeline.expire(redis_key, window_seconds + 1)
        count = int(pipeline.execute()[0])
        return RateDecision(count <= limit, count, limit, retry_after)


class RateLimiter:
    """Redis when it answers, memory when it does not."""

    #: After a Redis error, stay on memory this long before trying Redis again.
    REDIS_RETRY_SECONDS = 30.0

    def __init__(self, backend: RateLimitBackend | None = None) -> None:
        self._lock = threading.Lock()
        self._forced = backend
        self._memory = MemoryRateLimitBackend()
        self._redis: RedisRateLimitBackend | None = None
        self._redis_checked = False
        self._redis_down_until = 0.0

    def use_backend(self, backend: RateLimitBackend | None) -> None:
        """Pin a backend (tests); ``None`` restores Redis-with-memory-fallback."""

        with self._lock:
            self._forced = backend
            self._memory = MemoryRateLimitBackend()

    def _redis_backend(self) -> RedisRateLimitBackend | None:
        with self._lock:
            if self._redis_checked:
                return self._redis
            self._redis_checked = True
            url = str(_setting("REDIS_URL", "") or "")
            if not url or importlib.util.find_spec("redis") is None:
                return None
            try:
                redis_module = importlib.import_module("redis")
                client = redis_module.Redis.from_url(
                    url,
                    socket_connect_timeout=0.25,
                    socket_timeout=0.25,
                    decode_responses=True,
                )
                self._redis = RedisRateLimitBackend(client)
            except Exception:  # pragma: no cover - a malformed URL
                logger.warning("Rate limiter: Redis unavailable, using in-memory windows")
                self._redis = None
            return self._redis

    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateDecision:
        if self._forced is not None:
            return self._forced.hit(key, limit=limit, window_seconds=window_seconds)
        redis_backend = self._redis_backend()
        if redis_backend is not None and time.monotonic() >= self._redis_down_until:
            try:
                return redis_backend.hit(key, limit=limit, window_seconds=window_seconds)
            except Exception as exc:
                self._redis_down_until = time.monotonic() + self.REDIS_RETRY_SECONDS
                logger.warning("Rate limiter: Redis error, using in-memory windows: {}", exc)
        return self._memory.hit(key, limit=limit, window_seconds=window_seconds)


limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Who is asking
# ---------------------------------------------------------------------------


def _exempt_peers() -> set[str]:
    raw = _setting("RATE_LIMIT_EXEMPT_PEERS", "testclient")
    values = raw.split(",") if isinstance(raw, str) else list(raw or [])
    return {str(value).strip() for value in values if str(value).strip()}


def is_exempt(request: Request) -> bool:
    """Starlette's TestClient reports its peer as the literal ``testclient``.

    Only the raw ASGI peer is consulted, never a header, so no real client can
    claim the exemption: a socket's peer is always an address.
    """

    if not bool(_setting("RATE_LIMIT_ENABLED", True)):
        return True
    peer = request.client.host if request.client else ""
    return peer in _exempt_peers()


def client_ip(request: Request) -> str:
    hops = int(_setting("RATE_LIMIT_TRUSTED_PROXY_HOPS", 1) or 0)
    forwarded = request.headers.get("x-forwarded-for", "")
    if hops > 0 and forwarded:
        entries = [entry.strip() for entry in forwarded.split(",") if entry.strip()]
        if entries:
            return entries[-hops] if len(entries) >= hops else entries[0]
    return request.client.host if request.client else "unknown"


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None) or request.url.path
    prefix = str(_setting("API_V1_STR", "/api/v1"))
    return path[len(prefix):] if path.startswith(prefix) else path


def too_many_requests(code: str, message: str, retry_after_seconds: int) -> HTTPException:
    retry_after = max(1, int(retry_after_seconds))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": code, "message": message, "retry_after_seconds": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


def enforce(key: str, *, limit: int, window_seconds: int, message: str) -> None:
    if limit <= 0:
        return
    decision = limiter.hit(key, limit=int(limit), window_seconds=max(1, int(window_seconds)))
    if not decision.allowed:
        logger.warning("Rate limit hit: {} ({} > {})", key.split(":", 1)[0], decision.count, limit)
        raise too_many_requests(RATE_LIMITED_CODE, message, decision.retry_after_seconds)


# ---------------------------------------------------------------------------
# Auth: per IP
# ---------------------------------------------------------------------------


def _auth_bucket(path: str) -> str | None:
    if path.endswith("/auth/login"):
        return "login"
    if path.endswith("/auth/register"):
        return "register"
    if "/auth/password-reset" in path:
        return "password-reset" + path.split("/auth/password-reset", 1)[1].replace("/", ":")
    return None


def auth_rate_limit(request: Request) -> None:
    """Router dependency for ``auth.router``: limit the password doors per IP."""

    bucket = _auth_bucket(_route_path(request))
    if bucket is None or is_exempt(request):
        return
    enforce(
        f"auth:{bucket}:{client_ip(request)}",
        limit=int(_setting("RATE_LIMIT_AUTH_MAX_REQUESTS", 10)),
        window_seconds=int(_setting("RATE_LIMIT_AUTH_WINDOW_SECONDS", 60)),
        message="Too many attempts from this network. Please wait a moment and try again.",
    )


# ---------------------------------------------------------------------------
# Paid routes: per learner, plus the daily spend cap
# ---------------------------------------------------------------------------

#: ``(method, path under API_V1_STR)`` of every route that pays a provider.
PAID_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # speech in and out
        ("POST", "/audio/transcribe"),
        ("POST", "/audio/speak"),
        ("POST", "/audio-session/start"),
        ("POST", "/audio-session/respond"),
        ("POST", "/missions/audio/transcribe"),
        ("POST", "/story-engine/episodes/{scene_id}/audio"),
        # the daily journey (WP-69's router, guarded from api.py)
        ("POST", "/daily-journeys"),
        ("POST", "/daily-journeys/{journey_id}/steps/{step_id}/attempts"),
        ("POST", "/daily-journeys/{journey_id}/steps/{step_id}/help"),
        ("POST", "/daily-journeys/{journey_id}/retry"),
        ("POST", "/placement/{session_id}/respond"),
        # Atelier practice and correction
        ("POST", "/atelier/sessions"),
        ("POST", "/atelier/sessions/{session_id}/attempts"),
        ("POST", "/atelier/attempts/{attempt_id}/repair"),
        ("POST", "/atelier/attempts/{attempt_id}/ai-review"),
        ("POST", "/atelier/errata/{error_id}/attempt"),
        ("POST", "/atelier/workshop/compose"),
        ("POST", "/atelier/translate"),
        # Courrier, Feuilleton, serial
        ("POST", "/missions"),
        ("POST", "/missions/"),
        ("POST", "/missions/{mission_id}/submit"),
        ("POST", "/missions/{mission_id}/turns"),
        ("POST", "/graphic-novel/scenes"),
        ("POST", "/graphic-novel/scenes/"),
        ("POST", "/graphic-novel/scenes/{scene_id}/attempts"),
        ("POST", "/serial/threads"),
        ("POST", "/serial/threads/"),
        ("POST", "/serial/threads/{thread_id}/advance"),
        # companions
        ("POST", "/intake/text"),
        ("POST", "/intake/photo"),
        ("POST", "/journal/{entry_id}/write"),
        ("POST", "/journal/{entry_id}/followup"),
        ("POST", "/rehearsals"),
        ("POST", "/rehearsals/{rehearsal_id}/prepare"),
        ("POST", "/rehearsals/{rehearsal_id}/turns"),
        ("POST", "/rehearsals/{rehearsal_id}/debrief"),
        # legacy conversation and stories
        ("POST", "/sessions"),
        ("POST", "/sessions/quick-start"),
        ("POST", "/sessions/{session_id}/messages"),
        ("POST", "/sessions/{session_id}/moments/{moment_id}/submit"),
        ("POST", "/stories/{story_id}/input"),
        ("POST", "/stories/{story_id}/discuss"),
        ("GET", "/stories/{story_id}/scene/{scene_id}/visualization"),
        ("GET", "/stories/{story_id}/chapter/{chapter_id}/cover"),
    }
)


def is_paid_route(request: Request) -> bool:
    return (request.method.upper(), _route_path(request)) in PAID_ROUTES


def paid_route_guard(user_dependency: Callable[..., Any]) -> Callable[..., None]:
    """Build the router dependency for routers whose routes resolve ``user_dependency``.

    FastAPI caches a dependency per request, so the learner resolved here is the
    very object the route receives — no second token decode, no second query.
    Routes not in :data:`PAID_ROUTES` pass straight through.
    """

    def guard(
        request: Request,
        current_user: Any = Depends(user_dependency),
        db: Session = Depends(get_db),
    ) -> None:
        if not is_paid_route(request) or is_exempt(request):
            return
        user_id = getattr(current_user, "id", None)
        if user_id is None:
            return
        enforce(
            f"paid:{user_id}",
            limit=int(_setting("RATE_LIMIT_PAID_MAX_REQUESTS", 60)),
            window_seconds=int(_setting("RATE_LIMIT_PAID_WINDOW_SECONDS", 60)),
            message="You are going a little fast. Please wait a moment and try again.",
        )
        from app.services.spend_guard import enforce_daily_budget

        enforce_daily_budget(db, current_user)

    guard.__name__ = f"paid_route_guard_{getattr(user_dependency, '__name__', 'user')}"
    return guard


__all__ = [
    "PAID_ROUTES",
    "RATE_LIMITED_CODE",
    "MemoryRateLimitBackend",
    "RateLimiter",
    "RedisRateLimitBackend",
    "auth_rate_limit",
    "client_ip",
    "is_paid_route",
    "limiter",
    "paid_route_guard",
    "too_many_requests",
]
