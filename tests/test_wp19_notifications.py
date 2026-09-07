"""WP-19 native release readiness.

Two things the TestFlight checklist promises but nothing covered before:

* the morning push for the Atelier V2 daily journey ("Votre scène du jour est
  prête", deep link ``/atelier``), which must fire only for learners the
  server-side cohort gate accepts, and
* the first-party crash path ``window.onerror`` → ``POST /analytics/client-error``
  → a ``client_crash`` row in the pilot daily ledger, which is the reason this
  build ships without Sentry.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User
from app.services.pilot_events import PilotEventService
from app.services.serial_notifications import (
    DAILY_JOURNEY_MORNING_TITLE,
    daily_journey_morning_copy,
)
from app.tasks.notifications import _morning_copy
from tests.test_users import register_and_login

TODAY = date(2026, 9, 7)


def _learner(client: TestClient, db_session, email: str) -> User:
    register_and_login(client, email, "verysecure")
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _journey(db_session, user: User, *, status: str, budget_seconds: int = 300) -> DailyJourney:
    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=TODAY,
        timezone="Europe/Paris",
        status=status,
        budget_seconds=budget_seconds,
        created_at=datetime.now(UTC),
    )
    db_session.add(journey)
    db_session.commit()
    return journey


def _enable_journey(monkeypatch, *, cohort: str = "") -> None:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", cohort)


# ---------------------------------------------------------------------------
# Daily-journey morning push
# ---------------------------------------------------------------------------


def test_journey_morning_copy_is_none_when_the_flag_is_off(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", False)
    user = _learner(client, db_session, "journey-push-off@example.com")

    assert daily_journey_morning_copy(db_session, user, today=TODAY) is None


def test_journey_morning_copy_is_none_outside_the_cohort(client, db_session, monkeypatch) -> None:
    user = _learner(client, db_session, "journey-push-outside@example.com")
    _enable_journey(monkeypatch, cohort="someone-else@example.com")

    assert daily_journey_morning_copy(db_session, user, today=TODAY) is None


def test_journey_morning_copy_announces_the_scene_for_a_cohort_learner(
    client, db_session, monkeypatch
) -> None:
    user = _learner(client, db_session, "journey-push-in@example.com")
    _enable_journey(monkeypatch, cohort="journey-push-in@example.com")

    copy = daily_journey_morning_copy(db_session, user, today=TODAY)

    assert copy is not None
    title, message = copy
    assert title == "Votre scène du jour est prête"
    assert title == DAILY_JOURNEY_MORNING_TITLE
    assert message


def test_journey_morning_copy_offers_to_resume_an_unfinished_scene(
    client, db_session, monkeypatch
) -> None:
    user = _learner(client, db_session, "journey-push-resume@example.com")
    _enable_journey(monkeypatch)
    _journey(db_session, user, status="paused", budget_seconds=300)

    title, message = daily_journey_morning_copy(db_session, user, today=TODAY)

    assert title == DAILY_JOURNEY_MORNING_TITLE
    assert "5 minutes" in message


def test_journey_morning_copy_stays_silent_after_the_scene_is_finished(
    client, db_session, monkeypatch
) -> None:
    user = _learner(client, db_session, "journey-push-done@example.com")
    _enable_journey(monkeypatch)
    _journey(db_session, user, status="completed")

    assert daily_journey_morning_copy(db_session, user, today=TODAY) is None


def test_journey_morning_copy_ignores_yesterdays_finished_scene(
    client, db_session, monkeypatch
) -> None:
    user = _learner(client, db_session, "journey-push-yesterday@example.com")
    _enable_journey(monkeypatch)
    journey = _journey(db_session, user, status="completed")
    journey.local_date = date(2026, 9, 6)
    db_session.commit()

    copy = daily_journey_morning_copy(db_session, user, today=TODAY)

    assert copy is not None
    assert copy[0] == DAILY_JOURNEY_MORNING_TITLE


def test_scheduler_copy_uses_the_journey_title_for_cohort_learners(
    client, db_session, monkeypatch
) -> None:
    """The existing serial scheduler is what actually sends the push."""
    user = _learner(client, db_session, "journey-push-sched@example.com")
    _enable_journey(monkeypatch, cohort="journey-push-sched@example.com")

    title, _message = _morning_copy(db_session, user, TODAY)

    assert title == DAILY_JOURNEY_MORNING_TITLE


def test_scheduler_copy_keeps_the_legacy_edition_for_everyone_else(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", False)
    user = _learner(client, db_session, "journey-push-legacy@example.com")

    title, _message = _morning_copy(db_session, user, TODAY)

    assert title != DAILY_JOURNEY_MORNING_TITLE
    assert "édition" in title


# ---------------------------------------------------------------------------
# First-party crash reporting (checklist §2)
# ---------------------------------------------------------------------------


def test_client_error_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/analytics/client-error",
        json={"message": "boom", "route": "/atelier", "source": "capacitor"},
    )

    assert response.status_code == 401


def test_client_error_becomes_a_client_crash_in_the_pilot_ledger(
    client: TestClient, db_session
) -> None:
    token = register_and_login(client, "crash@example.com", "verysecure")

    response = client.post(
        "/api/v1/analytics/client-error",
        json={
            "message": "TypeError: undefined is not an object",
            "stack": "at JourneyScene (atelier.js:1:1)",
            "route": "/atelier",
            "source": "capacitor",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    user = db_session.scalar(select(User).where(User.email == "crash@example.com"))
    report = PilotEventService(db_session).daily_rollup(date.today(), user_id=str(user.id))
    rows = [row for row in report["users"] if row["user_id"] == str(user.id)]
    assert rows, report
    assert rows[0]["events"]["client_crash"] == 1
    assert report["totals"]["failures"] >= 1
