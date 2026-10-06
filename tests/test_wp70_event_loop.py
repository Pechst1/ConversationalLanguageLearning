"""WP-70 — one slow provider call must not stop the server.

The regression: ``POST /audio/speak`` (and a dozen other handlers) were
``async def`` and then called the synchronous OpenAI wrapper, so a stalled
provider froze uvicorn's event loop — ``/ready`` and every other learner's
request waited behind it. These tests stall a fake provider for up to 60 s and
prove the loop keeps answering, then audit every coroutine route so the next
``async def`` with a blocking call is caught in review, not in production.
"""
from __future__ import annotations

import asyncio
import inspect
import threading
import time
import uuid

import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_llm_service
from app.core.offload import OFFLOADED_ATTRIBUTE, off_event_loop, run_coroutine_off_loop
from app.core.rate_limit import MemoryRateLimitBackend, limiter
from app.db.models.user import User
from app.main import create_app

STALL_SECONDS = 60.0

#: Coroutine routes that are genuinely asynchronous end to end, reviewed by hand:
#: FastAPI's own docs pages, the liveness probe, the websocket, and a handler
#: whose only I/O is an ``httpx.AsyncClient`` news fetch.
REVIEWED_ASYNC_ROUTES = {
    "/openapi.json",
    "/api/v1/docs",
    "/docs/oauth2-redirect",
    "/api/v1/redoc",
    "/health",
    "/api/v1/sessions/{session_id}/ws",
    "/api/v1/sessions/live-stories",
}


class _StallingSpeech:
    """A provider whose ``slow`` line blocks its thread until released."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.entered = threading.Event()

    def text_to_speech(self, *, text: str, voice: str, provider: str | None) -> bytes:
        if text == "slow":
            self.entered.set()
            self.release.wait(STALL_SECONDS)
        return b"ID3-fake-mp3"


def _user(db: Session, email: str) -> User:
    user = User(
        email=email,
        hashed_password="not-used",
        target_language="fr",
        proficiency_level="A2",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(autouse=True)
def _memory_limiter():
    limiter.use_backend(MemoryRateLimitBackend())
    yield
    limiter.use_backend(None)


def test_a_stalled_provider_call_does_not_delay_ready_or_another_learner(db_session: Session) -> None:
    alice = _user(db_session, f"wp70-alice-{uuid.uuid4().hex[:6]}@example.com")
    bob = _user(db_session, f"wp70-bob-{uuid.uuid4().hex[:6]}@example.com")
    speech = _StallingSpeech()
    users = {"alice": alice, "bob": bob}

    app = create_app()

    def override_db():
        yield db_session

    from fastapi import Header

    def current_user_from_header(x_test_user: str = Header("alice")) -> User:
        return users[x_test_user]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = current_user_from_header
    app.dependency_overrides[get_llm_service] = lambda: speech

    async def scenario() -> tuple[float, float, int, int, int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            stalled = asyncio.create_task(
                client.post(
                    "/api/v1/audio/speak",
                    json={"text": "slow"},
                    headers={"X-Test-User": "alice"},
                )
            )
            # Wait until the provider call is really in flight (on its thread).
            for _ in range(200):
                if speech.entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert speech.entered.is_set(), "the stalled call never reached the provider"

            started = time.monotonic()
            ready = await asyncio.wait_for(client.get("/ready"), timeout=5)
            ready_seconds = time.monotonic() - started

            started = time.monotonic()
            other = await asyncio.wait_for(
                client.post(
                    "/api/v1/audio/speak",
                    json={"text": "vite"},
                    headers={"X-Test-User": "bob"},
                ),
                timeout=5,
            )
            other_seconds = time.monotonic() - started

            assert not stalled.done(), "the stalled call should still be waiting"
            speech.release.set()
            first = await asyncio.wait_for(stalled, timeout=10)
            return ready_seconds, other_seconds, ready.status_code, other.status_code, first.status_code

    ready_seconds, other_seconds, ready_status, other_status, first_status = asyncio.run(scenario())

    assert ready_status == 200
    assert other_status == 200
    assert first_status == 200
    assert ready_seconds < 2.0, f"/ready waited {ready_seconds:.2f}s behind a stalled provider call"
    assert other_seconds < 2.0, f"another learner waited {other_seconds:.2f}s"


def test_every_coroutine_route_is_offloaded_or_reviewed() -> None:
    app = create_app()
    offenders = []
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None or not inspect.iscoroutinefunction(endpoint):
            continue
        if getattr(endpoint, OFFLOADED_ATTRIBUTE, False):
            continue
        if route.path in REVIEWED_ASYNC_ROUTES:
            continue
        offenders.append(f"{route.path} ({endpoint.__module__}.{endpoint.__name__})")
    assert not offenders, (
        "async def routes run on the event loop; make these plain def handlers or "
        "decorate them with @off_event_loop: " + ", ".join(offenders)
    )


def test_the_known_blocking_handlers_are_off_the_loop() -> None:
    from app.api.v1.endpoints import audio, graphic_novel, intake, missions

    for handler in (
        audio.text_to_speech,
        audio.transcribe_audio,
        missions.create_mission,
        missions.transcribe_mission_audio,
        intake.submit_photo,
        graphic_novel.create_graphic_novel_scene,
    ):
        assert getattr(handler, OFFLOADED_ATTRIBUTE, False) or not inspect.iscoroutinefunction(handler)


def test_offloaded_coroutines_run_on_a_worker_thread_with_their_own_loop() -> None:
    main_thread = threading.get_ident()

    @off_event_loop
    async def handler(value: int) -> tuple[int, int]:
        await asyncio.sleep(0)
        return value * 2, threading.get_ident()

    async def run() -> tuple[int, int]:
        return await handler(21)

    doubled, thread_id = asyncio.run(run())
    assert doubled == 42
    assert thread_id != main_thread

    async def boom() -> None:
        raise ValueError("kept")

    with pytest.raises(ValueError, match="kept"):
        asyncio.run(run_coroutine_off_loop(boom))


def test_off_event_loop_refuses_a_plain_function() -> None:
    with pytest.raises(TypeError):
        off_event_loop(lambda: None)  # type: ignore[arg-type]
