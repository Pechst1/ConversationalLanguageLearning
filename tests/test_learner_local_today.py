"""«Today» is the learner's local day everywhere, also between 23:00 and 24:00 UTC.

On 9 Nov 2026 three PRs (#656, #657, #658) failed the same checks in the CI jobs that
ran between 23:00 and 24:00 UTC, when Berlin's date is already the next one. Two were
the tests' own seeding (``tests/test_gold_view.py``, ``tests/test_vocab_scene_first.py``,
now run at each ``learner_clock`` moment). One was the product: ``GET
/daily-journeys/today`` without a ``timezone`` (the Feuilleton's «today» card asks so)
read the UTC date, found yesterday's finished journey and showed no episode. This
file pins that read at each moment.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User
from app.services.streak import local_today
from tests.test_wp80_streak import _auth


def test_today_without_a_zone_is_the_learners_day_not_utcs(
    client, db_session, monkeypatch, learner_clock: datetime
):
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "*")
    email = f"local-today-{uuid.uuid4().hex[:8]}@example.com"
    headers = _auth(client, email)
    user = db_session.scalar(select(User).where(User.email == email))
    user.timezone = "Europe/Berlin"
    today = local_today(user, learner_clock)
    yesterday = today - timedelta(days=1)
    db_session.add(
        DailyJourney(
            id=uuid.uuid4(),
            user_id=user.id,
            local_date=yesterday,
            timezone="Europe/Berlin",
            status="completed",
            budget_seconds=600,
            created_at=learner_clock - timedelta(hours=20),
        )
    )
    db_session.commit()

    for params in ({}, {"timezone": "Europe/Berlin"}):
        response = client.get("/api/v1/daily-journeys/today", headers=headers, params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["local_date"] == today.isoformat(), (params, body["local_date"])
        assert body["journey"] is None, (
            f"yesterday's finished journey stood in for today ({params})"
        )
