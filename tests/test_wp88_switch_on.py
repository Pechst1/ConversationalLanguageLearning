"""WP-88 — switch it on, safely.

What these tests pin:

* the spend cap counts the learner's own calendar day, not UTC's;
* a day already started is never cut off at the cap: its own routes are held to
  the open-day ceiling instead, which still stops a loop;
* panel art is budgeted apart from the text cap, on a per-day allowance, and a
  panel the allowance does not cover keeps its plate;
* art stays off in production without the cast references or durable storage;
* production refuses to start with a blank journey cohort;
* the manifest and the image carry what the above needs.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.rate_limit import OPEN_DAY_ROUTES, PAID_ROUTES
from app.db.models.pilot_event import PilotEvent
from app.services import panel_art, spend_guard
from tests.test_wp70_rate_limits import (  # noqa: F401 - fixtures
    _assert_429,
    _learner,
    _memory_limiter,
    _spend,
    abuser_client,
    speech,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# The learner's day
# ---------------------------------------------------------------------------


def test_the_cap_day_is_the_learners_own_day() -> None:
    auckland = ZoneInfo("Pacific/Auckland")
    # 11:00 UTC on the 1st is 00:00 on the 2nd in Auckland (NZDT, UTC+13).
    now = datetime(2026, 1, 1, 11, 30, tzinfo=UTC)
    start, end = spend_guard.day_bounds(now, auckland)
    assert start == datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    assert end == datetime(2026, 1, 2, 11, 0, tzinfo=UTC)
    assert spend_guard.seconds_until_reset(now, auckland) == int(timedelta(hours=23, minutes=30).total_seconds())


def test_an_unknown_or_missing_zone_falls_back_to_utc() -> None:
    assert spend_guard.learner_zone(SimpleNamespace(timezone="Mars/Olympus")) == ZoneInfo("UTC")
    assert spend_guard.learner_zone(None) == ZoneInfo("UTC")
    assert spend_guard.learner_zone(SimpleNamespace(timezone="Europe/Paris")) == ZoneInfo("Europe/Paris")


# ---------------------------------------------------------------------------
# A started day is finished
# ---------------------------------------------------------------------------


def test_open_day_routes_are_paid_routes() -> None:
    assert OPEN_DAY_ROUTES <= PAID_ROUTES
    assert ("POST", "/daily-journeys") not in OPEN_DAY_ROUTES, "starting a day still meets the cap"


def test_a_started_day_passes_the_cap_but_not_the_ceiling(
    abuser_client: TestClient, db_session: Session, monkeypatch  # noqa: F811
) -> None:
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_OPEN_DAY_MULTIPLIER", 2.0)
    user, headers = _learner(db_session)
    _spend(db_session, user, 0.75, event_type="journey_story_turn_cost")
    attempt = f"/api/v1/daily-journeys/{uuid.uuid4()}/steps/{uuid.uuid4()}/attempts"
    body = {"expected_revision": 1, "mutation_id": str(uuid.uuid4()), "answer": {"mode": "text", "text": "Bonjour"}}

    _assert_429(abuser_client.post("/api/v1/daily-journeys", json={}, headers=headers), "daily_budget_reached")
    # Past the cap, under the ceiling: the guard lets the day's own route through
    # (the journey does not exist, so the route itself answers).
    assert abuser_client.post(attempt, json=body, headers=headers).status_code != 429

    _spend(db_session, user, 0.30, event_type="journey_story_turn_cost")
    _assert_429(abuser_client.post(attempt, json=body, headers=headers), "daily_budget_reached")


def test_art_is_not_counted_against_the_text_cap(db_session: Session) -> None:
    user, _headers = _learner(db_session)
    _spend(db_session, user, 0.10)
    _spend(db_session, user, 0.24, event_type=spend_guard.PANEL_ART_EVENT_TYPE)
    assert spend_guard.spend_today_usd(db_session, user.id) == pytest.approx(0.10)
    assert spend_guard.art_spend_today_usd(db_session, user.id) == pytest.approx(0.24)


# ---------------------------------------------------------------------------
# Panel art: allowance, bands, production readiness
# ---------------------------------------------------------------------------


@pytest.fixture
def art_on(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_COST_USD_PER_PANEL", 0.06)
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD", 0.25)
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_TEXT_PRESSURE", 0.7)
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_BANDS", "")
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)


def test_the_allowance_decides_how_many_panels_are_drawn(db_session: Session, art_on) -> None:
    user, _headers = _learner(db_session)
    assert panel_art.affordable_panels(db_session, user, 6) == 4  # 0.25 // 0.06
    _spend(db_session, user, 0.18, event_type=spend_guard.PANEL_ART_EVENT_TYPE)
    assert panel_art.affordable_panels(db_session, user, 6) == 1
    _spend(db_session, user, 0.06, event_type=spend_guard.PANEL_ART_EVENT_TYPE)
    assert panel_art.affordable_panels(db_session, user, 6) == 0


def test_a_day_under_text_pressure_draws_nothing(db_session: Session, art_on) -> None:
    user, _headers = _learner(db_session)
    _spend(db_session, user, 0.36)  # 72 % of the 0.50 cap
    assert panel_art.affordable_panels(db_session, user, 6) == 0


def _scene(panels: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=None,
        panels=[SimpleNamespace(panel_index=i, generation_metadata={}) for i in range(panels)],
    )


def test_only_covered_panels_are_marked_rendering(db_session: Session, art_on, monkeypatch) -> None:
    user, _headers = _learner(db_session)
    monkeypatch.setattr(panel_art, "dispatcher", lambda job: None)
    scene = _scene(6)
    assert panel_art.request_scene_art(db_session, scene, level_band="A1", user=user) is True
    statuses = [p.generation_metadata.get("image_status") for p in scene.panels]
    assert statuses == ["rendering"] * 4 + [None, None], "panels past the allowance keep their plate"
    db_session.info.pop(panel_art.PENDING_KEY, None)


def test_bands_outside_the_list_keep_their_plates(db_session: Session, art_on, monkeypatch) -> None:
    user, _headers = _learner(db_session)
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_BANDS", "A1,A2")
    scene = _scene(4)
    assert panel_art.request_scene_art(db_session, scene, level_band="B1.1", user=user) is False
    assert all("image_status" not in p.generation_metadata for p in scene.panels)
    assert panel_art._band_allowed("A2.2") is True


def test_production_keeps_art_off_without_durable_storage(art_on, monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", "local")
    assert panel_art.enabled() is False
    assert "s3" in (panel_art.unavailable_reason() or "")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", "s3")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_S3_BUCKET", "atelier-panels")
    assert panel_art.enabled() is True


def test_art_stays_off_without_the_cast_references(art_on, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(panel_art, "CAST_REFERENCES", tmp_path / "missing")
    assert panel_art.enabled() is False
    assert "cast references" in (panel_art.unavailable_reason() or "")


def test_a_drawn_panel_writes_its_price_to_the_ledger(db_session: Session, art_on) -> None:
    user, _headers = _learner(db_session)
    scene = SimpleNamespace(id=uuid.uuid4(), user_id=user.id)
    job = panel_art.PanelJob(scene_id=str(scene.id), panel_index=2, prompt="…", references=())
    panel_art._record_cost(db_session, scene, job)
    db_session.commit()
    row = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == user.id, PilotEvent.event_type == spend_guard.PANEL_ART_EVENT_TYPE
        )
    ).one()
    assert row.cost_usd == pytest.approx(0.06)
    assert row.payload["panel_index"] == 2 and row.payload["estimated"] is True
    assert spend_guard.art_spend_today_usd(db_session, user.id) == pytest.approx(0.06)


# ---------------------------------------------------------------------------
# Production start-up and the deploy manifest
# ---------------------------------------------------------------------------


def _start(monkeypatch, cohort: str, *, legal_contact: str = "owner@example.org") -> None:
    from app.main import lifespan

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", False)
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "atelier@example.com")
    monkeypatch.setattr(settings, "SCHEMA_GUARD_ENABLED", False)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", cohort)
    monkeypatch.setattr(settings, "LEGAL_CONTACT_EMAIL", legal_contact)

    async def run() -> None:
        async with lifespan(FastAPI()):
            pass

    asyncio.run(run())


def test_production_refuses_a_blank_cohort(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="ATELIER_DAILY_JOURNEY_COHORT"):
        _start(monkeypatch, "  ")


def test_production_refuses_a_placeholder_legal_contact(monkeypatch) -> None:
    """WP-138: the privacy policy never goes live naming «[contact e-mail]»."""

    with pytest.raises(RuntimeError, match="LEGAL_CONTACT_EMAIL"):
        _start(monkeypatch, "*", legal_contact="")


@pytest.mark.parametrize("cohort", ["*", "none", "owner@example.com"])
def test_production_starts_with_an_explicit_cohort(monkeypatch, cohort: str) -> None:
    _start(monkeypatch, cohort)


def test_none_means_nobody(monkeypatch) -> None:
    from app.services.daily_journey import journey_enabled_for

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "none")
    assert journey_enabled_for(SimpleNamespace(id=uuid.uuid4(), email="learner@example.com")) is False


def test_manifest_switches_audio_and_art_on_and_leaves_storage_to_the_dashboard() -> None:
    yaml = pytest.importorskip("yaml")
    manifest = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    for service in manifest["services"]:
        if service.get("type") not in {"web", "worker"}:
            continue
        env = {item["key"]: item for item in service.get("envVars", [])}
        assert env["ATELIER_EPISODE_AUDIO_ENABLED"]["value"] == "true", service["name"]
        assert env["ATELIER_PANEL_ART_ENABLED"]["value"] == "true", service["name"]
        assert env["ATELIER_PANEL_ART_BANDS"]["value"] == "A1,A2", service["name"]
        for key in ("GRAPHIC_NOVEL_IMAGE_STORAGE", "GRAPHIC_NOVEL_IMAGE_S3_BUCKET"):
            assert env[key].get("sync") is False, (service["name"], key)


def test_the_image_ships_the_cast_references() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "docs/design-reference/cast" in dockerfile
    assert any((ROOT / "docs/design-reference/cast").glob("*/reference.webp"))
