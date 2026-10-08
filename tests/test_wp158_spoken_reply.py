"""WP-158 slice 1 — speaking inside the story.

The learner answers a story character aloud. Four properties, all through the
real router with the fake transcriber (no provider is ever called):

1. upload → transcript → the **same** reply endpoint: a spoken reply and the
   same sentence typed get the same grading; only the modality differs;
2. the per-turn cost ceiling and the 30-second cap refuse an upload *before*
   the transcriber is called, and a refusal books nothing;
3. ``ATELIER_SPOKEN_REPLY_ENABLED`` off: the prompt offers nothing and the
   ``story_reply`` surface is refused;
4. the closing turn offers one useful line to repeat, and that line may be
   spoken by the step's line-audio door.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_llm_service
from app.api.v1.endpoints.daily_journey import get_journey_adapters
from app.config import settings
from app.db.models.daily_journey import DailyJourneyStep
from app.db.models.pilot_event import PilotEvent
from app.main import create_app
from app.services import daily_journey as daily_journey_service
from app.services import line_audio
from app.services.daily_journey_adapters import build_default_adapters
from app.services.spoken_reply import (
    FAKE_DEFAULT_TRANSCRIPT,
    FAKE_TRANSCRIPT_MARKER,
    STORY_REPLY_SURFACE,
    TURN_ENTITY_TYPE,
    FakeTranscriber,
)
from app.services.transcription_cost import (
    ASSUMED_BYTES_PER_SECOND,
    TRANSCRIPTION_EVENT_TYPE,
)
from tests.test_journey_end_to_end import Clock, Driver, register

SENTENCE = "Bonjour, je voudrais un café, s'il vous plaît."


@pytest.fixture()
def journey_on() -> Generator[None, None, None]:
    previous = (settings.ATELIER_DAILY_JOURNEY_ENABLED, settings.ATELIER_DAILY_JOURNEY_COHORT)
    settings.ATELIER_DAILY_JOURNEY_ENABLED = True
    settings.ATELIER_DAILY_JOURNEY_COHORT = ""
    try:
        yield
    finally:
        settings.ATELIER_DAILY_JOURNEY_ENABLED, settings.ATELIER_DAILY_JOURNEY_COHORT = previous


@pytest.fixture()
def api(db_session: Session, journey_on: None, monkeypatch: pytest.MonkeyPatch):
    """The real router and adapters (as WP-12's assembled client), on a fixed clock."""

    monkeypatch.setattr(daily_journey_service, "_utcnow", Clock(datetime(2026, 3, 10, 9, 0, tzinfo=UTC)))
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_journey_adapters] = build_default_adapters
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def spoken_on() -> Generator[None, None, None]:
    previous = (
        settings.ATELIER_SPOKEN_REPLY_ENABLED,
        settings.ATELIER_SPOKEN_REPLY_MAX_USD_PER_TURN,
        settings.ATELIER_SPOKEN_REPLY_MAX_SECONDS,
    )
    settings.ATELIER_SPOKEN_REPLY_ENABLED = True
    try:
        yield
    finally:
        (
            settings.ATELIER_SPOKEN_REPLY_ENABLED,
            settings.ATELIER_SPOKEN_REPLY_MAX_USD_PER_TURN,
            settings.ATELIER_SPOKEN_REPLY_MAX_SECONDS,
        ) = previous


@pytest.fixture()
def transcriber(api: TestClient) -> Generator[FakeTranscriber, None, None]:
    fake = FakeTranscriber()
    api.app.dependency_overrides[get_llm_service] = lambda: fake
    try:
        yield fake
    finally:
        api.app.dependency_overrides.pop(get_llm_service, None)


def _recording(text: str = SENTENCE, *, seconds: float = 6.0) -> bytes:
    """A fake upload the fake transcriber hears as ``text``, padded to ``seconds``."""

    head = FAKE_TRANSCRIPT_MARKER + text.encode("utf-8")
    return head + b"\x00" * max(0, int(seconds * ASSUMED_BYTES_PER_SECOND) - len(head))


def _speak(client: TestClient, driver: Driver, payload: bytes):
    step = driver.current()
    assert step is not None
    return client.post(
        "/api/v1/audio/transcribe",
        headers=driver.headers,
        files={"file": ("reply.webm", payload, "audio/webm")},
        data={"surface": STORY_REPLY_SURFACE, "journey_id": driver.id, "step_id": step["id"]},
    )


def _at_reply(client: TestClient, db: Session, label: str) -> Driver:
    email = f"wp158-{label}-{uuid.uuid4().hex[:8]}@example.com"
    driver = Driver(client, register(client, email), db=db)
    driver.create(expect=(201,))
    driver.advance()
    step = driver.current()
    assert step is not None and step["kind"] == "respond"
    return driver


def _turn_rows(db: Session, step_id: str) -> list[PilotEvent]:
    return (
        db.query(PilotEvent)
        .filter(
            PilotEvent.event_type == TRANSCRIPTION_EVENT_TYPE,
            PilotEvent.entity_type == TURN_ENTITY_TYPE,
            PilotEvent.entity_id.like(f"{step_id}:%"),
        )
        .all()
    )


def _graded(body: dict[str, Any]) -> dict[str, Any]:
    """What grading decided, without ids, receipts or the snapshot."""

    return {
        "task_outcome": body["task_outcome"],
        "assistance_level": body["assistance_level"],
        "correction": body.get("correction"),
        "reply_source": body.get("reply_source"),
        "closing": body.get("next_turn") is None,
    }


# --------------------------------------------------------------------------
# 1. Spoken and typed meet the same grading
# --------------------------------------------------------------------------


def test_the_prompt_offers_parler_only_while_the_flag_is_on(
    api: TestClient,
    db_session: Session
) -> None:
    driver = _at_reply(api, db_session, "flag")
    assert driver.current()["prompt"]["spoken_reply"] is False
    settings.ATELIER_SPOKEN_REPLY_ENABLED = True
    try:
        snapshot = api.get(
            f"/api/v1/daily-journeys/{driver.id}", headers=driver.headers
        ).json()
    finally:
        settings.ATELIER_SPOKEN_REPLY_ENABLED = False
    respond = next(s for s in snapshot["steps"] if s["kind"] == "respond")
    assert respond["prompt"]["spoken_reply"] is True
    # Read at projection time, never stored: the persisted prompt is untouched.
    row = db_session.get(DailyJourneyStep, uuid.UUID(respond["id"]))
    assert "spoken_reply" not in (row.public_prompt or {})


def test_a_spoken_reply_is_graded_exactly_like_the_same_sentence_typed(
    api: TestClient,
    db_session: Session,
    spoken_on: None,
    transcriber: FakeTranscriber,
) -> None:
    spoken = _at_reply(api, db_session, "spoken")
    heard = _speak(api, spoken, _recording(SENTENCE))
    assert heard.status_code == 200, heard.text
    transcript = heard.json()["text"]
    assert transcript == SENTENCE
    assert transcriber.calls == 1
    # The transcript is returned, never submitted: the turn is still open.
    assert spoken.current()["kind"] == "respond"

    voice = spoken.attempt({"mode": "voice", "text": transcript})
    assert voice.status_code == 200, voice.text

    typed_driver = _at_reply(api, db_session, "typed")
    typed = typed_driver.attempt({"mode": "text", "text": SENTENCE})
    assert typed.status_code == 200, typed.text

    assert _graded(voice.json()) == _graded(typed.json())

    # One priced row, booked against the turn, carrying its references.
    respond_id = next(s["id"] for s in spoken.journey["steps"] if s["kind"] == "respond")
    rows = _turn_rows(db_session, respond_id)
    assert len(rows) == 1
    assert rows[0].payload["surface"] == STORY_REPLY_SURFACE
    assert rows[0].payload["journey_id"] == spoken.id
    assert rows[0].payload["estimated"] is True
    assert rows[0].cost_usd > 0.0


def test_the_fake_transcriber_hears_its_default_without_a_marker() -> None:
    assert FakeTranscriber().transcribe_audio(b"\x1a\x45\xdf\xa3 webm") == FAKE_DEFAULT_TRANSCRIPT
    assert FakeTranscriber().transcribe_audio(FAKE_TRANSCRIPT_MARKER + b"Oui !") == "Oui !"


# --------------------------------------------------------------------------
# 2. Money and length are checked before the transcriber
# --------------------------------------------------------------------------


def test_the_turn_cost_ceiling_refuses_before_any_transcription(
    api: TestClient,
    db_session: Session,
    spoken_on: None,
    transcriber: FakeTranscriber,
) -> None:
    # Room for one 20 s recording (US$0.002), not two.
    settings.ATELIER_SPOKEN_REPLY_MAX_USD_PER_TURN = 0.003
    driver = _at_reply(api, db_session, "ceiling")
    first = _speak(api, driver, _recording(seconds=20))
    assert first.status_code == 200, first.text
    second = _speak(api, driver, _recording(seconds=20))
    assert second.status_code == 429, second.text
    assert second.json()["detail"]["code"] == "spoken_reply_turn_ceiling"
    assert transcriber.calls == 1, "a refused upload reached the transcriber"
    respond_id = driver.current()["id"]
    assert len(_turn_rows(db_session, respond_id)) == 1, "a refusal was booked"
    # The typed path is untouched by the refusal.
    typed = driver.attempt({"mode": "text", "text": SENTENCE})
    assert typed.status_code == 200, typed.text


def test_a_recording_over_thirty_seconds_is_refused(
    api: TestClient,
    db_session: Session,
    spoken_on: None,
    transcriber: FakeTranscriber,
) -> None:
    driver = _at_reply(api, db_session, "long")
    response = _speak(api, driver, _recording(seconds=60))
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "spoken_reply_too_long"
    assert transcriber.calls == 0


def test_another_learners_turn_cannot_be_spoken_into(
    api: TestClient,
    db_session: Session,
    spoken_on: None,
    transcriber: FakeTranscriber,
) -> None:
    owner = _at_reply(api, db_session, "owner")
    stranger = Driver(
        api,
        register(api, f"wp158-stranger-{uuid.uuid4().hex[:8]}@example.com"),
    )
    response = api.post(
        "/api/v1/audio/transcribe",
        headers=stranger.headers,
        files={"file": ("reply.webm", _recording(), "audio/webm")},
        data={
            "surface": STORY_REPLY_SURFACE,
            "journey_id": owner.id,
            "step_id": owner.current()["id"],
        },
    )
    assert response.status_code == 404
    assert transcriber.calls == 0


# --------------------------------------------------------------------------
# 3. Flag off
# --------------------------------------------------------------------------


def test_with_the_flag_off_the_story_surface_is_refused(
    api: TestClient,
    db_session: Session,
    transcriber: FakeTranscriber,
) -> None:
    assert settings.ATELIER_SPOKEN_REPLY_ENABLED is False, "the flag defaults off"
    driver = _at_reply(api, db_session, "off")
    response = _speak(api, driver, _recording())
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "spoken_reply_disabled"
    assert transcriber.calls == 0


# --------------------------------------------------------------------------
# 4. One line to repeat
# --------------------------------------------------------------------------


def _close_the_reply(driver: Driver) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for _ in range(8):
        step = driver.current()
        if step is None or step["kind"] != "respond":
            break
        response = driver.attempt({"mode": "voice", "text": SENTENCE})
        assert response.status_code == 200, response.text
        body = response.json()
        if body.get("next_turn") is None:
            break
    return body


def test_the_closing_turn_offers_one_line_to_repeat_and_it_may_be_spoken(
    api: TestClient,
    db_session: Session,
    spoken_on: None,
) -> None:
    driver = _at_reply(api, db_session, "repeat")
    respond_id = driver.current()["id"]
    closing = _close_the_reply(driver)
    assert closing.get("next_turn") is None
    line = closing.get("repeat_line_fr")
    assert line, "the closed reply offers no line to repeat"

    step = db_session.get(DailyJourneyStep, uuid.UUID(respond_id))
    db_session.refresh(step)
    journey = step.journey
    lines = line_audio.step_lines(db_session, journey, step)
    assert line_audio.match_line(lines, line) is not None


def test_no_line_to_repeat_while_the_flag_is_off(
    api: TestClient,
    db_session: Session
) -> None:
    driver = _at_reply(api, db_session, "norepeat")
    closing = _close_the_reply(driver)
    assert closing.get("repeat_line_fr") is None
