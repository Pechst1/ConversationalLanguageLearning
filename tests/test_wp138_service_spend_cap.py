# ruff: noqa: F811 - the WP-70 fixtures are imported by name and requested as arguments
"""WP-138 — a ceiling on what the whole service can cost in a day.

The per-learner cap (WP-70) cannot bound the bill: every allowed learner may
spend up to it. ``SERVICE_DAILY_SPEND_CAP_USD`` sums every learner and every
ledger (panel art included) since UTC midnight; at the cap the paid routes
answer ``daily_budget_reached``, panels keep their plates and the prefetch beat
skips. The suite shares one database, so each test sets the cap relative to
what the service has already "spent" today.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.services import spend_guard
from tests.test_wp70_rate_limits import (  # noqa: F401 - fixtures
    _assert_429,
    _learner,
    _memory_limiter,
    _spend,
    abuser_client,
    speech,
)


def test_off_by_default_and_every_learner_counts(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", 0.0)
    assert spend_guard.service_budget_reached(db_session) is False

    before = spend_guard.service_spend_today_usd(db_session)
    first, _ = _learner(db_session)
    second, _ = _learner(db_session)
    _spend(db_session, first, 0.10)
    _spend(db_session, second, 0.20)
    _spend(db_session, second, 0.05, event_type=spend_guard.PANEL_ART_EVENT_TYPE)
    assert abs(spend_guard.service_spend_today_usd(db_session) - before - 0.35) < 1e-6


def test_the_service_cap_refuses_a_learner_well_under_their_own_cap(
    abuser_client: TestClient, db_session: Session, speech, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)
    baseline = spend_guard.service_spend_today_usd(db_session)
    monkeypatch.setattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", baseline + 1.00)
    others, _ = _learner(db_session)
    user, headers = _learner(db_session)

    assert abuser_client.post("/api/v1/audio/speak", json={"text": "Encore"}, headers=headers).status_code == 200
    _spend(db_session, others, 1.00)  # someone else spent the service's day
    response = abuser_client.post("/api/v1/audio/speak", json={"text": "Encore"}, headers=headers)
    _assert_429(response, "daily_budget_reached")
    assert speech.calls == 1
    assert spend_guard.spend_today_usd(db_session, user.id) < 0.50


def test_at_the_service_cap_panels_keep_their_plates(
    db_session: Session, monkeypatch
) -> None:
    from app.services import panel_art

    user, _ = _learner(db_session)
    _spend(db_session, user, 0.01)
    monkeypatch.setattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", spend_guard.service_spend_today_usd(db_session))
    assert spend_guard.service_budget_reached(db_session) is True
    assert panel_art.affordable_panels(db_session, user, 4) == 0
