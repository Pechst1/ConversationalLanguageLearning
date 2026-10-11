"""WP-L8 — the weekly forecast line at the Seal, and WP-L6's consolidation flag.

«At this rhythm: A1.2 around <month>» — once a week on the recap, only from a
*measured* forecast (never the prior, never as a promise before measurement).
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.schemas.daily_journey import JourneyRecap
from app.services.achievement_recap import forecast_line
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    drive_to_finish,
    enabled,
    freeze,
    make_user,
)

MEASURED = {
    "status": "available",
    "kind": "estimate",
    "band": "A1.1",
    "target": "A1.2",
    "rhythm": "regulier",
    "base_days": 60,
    "range_days": [48, 78],
    "capped": False,
}


def test_the_line_needs_a_measured_forecast() -> None:
    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    line = forecast_line(MEASURED, now=now)
    assert line == {
        "target": "A1.2",
        "band": "A1.1",
        "month": "2026-11",
        "range_days": [48, 78],
        "rhythm": "regulier",
        "measured": True,
    }
    assert forecast_line({**MEASURED, "status": "prior"}, now=now) is None
    assert forecast_line({**MEASURED, "capped": True}, now=now) is None
    assert forecast_line(None, now=now) is None
    assert forecast_line({**MEASURED, "base_days": None}, now=now) is None


def _day(service, user, monkeypatch, when: datetime):
    freeze(monkeypatch, when)
    created, _ = service.create_journey(user, create_request())
    return drive_to_finish(service, user, created, finish_kind="complete").recap


def test_the_seal_shows_the_line_once_a_week(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811 - pytest fixture
) -> None:
    user = make_user(db_session, "wp-l8-seal@example.com")
    # A measured payload the day's own recompute does not replace (no version).
    user.cefr_estimate_payload = {"estimate": "A1.1", "forecast": dict(MEASURED)}
    db_session.commit()
    service = DailyJourneyService(db_session, build_default_adapters())

    day1 = _day(service, user, monkeypatch, datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
    assert day1.forecast_line is not None
    assert (day1.forecast_line.target, day1.forecast_line.month) == ("A1.2", "2026-10")
    assert day1.consolidating is False
    JourneyRecap.model_validate(day1.model_dump(mode="json"))

    day2 = _day(service, user, monkeypatch, datetime(2026, 9, 2, 9, 0, tzinfo=UTC))
    assert day2.forecast_line is None, "once a week, not every day"

    day8 = _day(service, user, monkeypatch, datetime(2026, 9, 8, 9, 0, tzinfo=UTC))
    assert day8.forecast_line is not None


def test_no_line_before_measurement(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811 - pytest fixture
) -> None:
    user = make_user(db_session, "wp-l8-prior@example.com")
    user.cefr_estimate_payload = {"estimate": "A1.1", "forecast": {**MEASURED, "status": "prior"}}
    db_session.commit()
    service = DailyJourneyService(db_session, build_default_adapters())
    recap = _day(service, user, monkeypatch, datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
    assert recap.forecast_line is None
