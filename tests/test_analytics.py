from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.session import LearningSession, WordInteraction
from app.db.models.user import User


async def _register_and_login(async_client, email: str, password: str) -> str:
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "target_language": "fr",
            "native_language": "en",
        },
    )
    response = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_analytics_endpoints(async_client, db_session, french_vocabulary):
    email = "analytics@example.com"
    token = await _register_and_login(async_client, email, "verysecure")
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.query(User).filter(User.email == email).one()
    now = datetime.now(timezone.utc)

    session_one = LearningSession(
        user_id=user.id,
        planned_duration_minutes=30,
        actual_duration_minutes=25,
        status="completed",
        words_practiced=6,
        new_words_introduced=3,
        words_reviewed=3,
        correct_responses=5,
        incorrect_responses=1,
        xp_earned=120,
        accuracy_rate=0.83,
        started_at=now - timedelta(days=1),
        completed_at=now - timedelta(days=1),
    )
    session_two = LearningSession(
        user_id=user.id,
        planned_duration_minutes=15,
        actual_duration_minutes=15,
        status="completed",
        words_practiced=4,
        new_words_introduced=1,
        words_reviewed=3,
        correct_responses=4,
        incorrect_responses=0,
        xp_earned=80,
        accuracy_rate=1.0,
        started_at=now - timedelta(days=2),
        completed_at=now - timedelta(days=2),
    )
    db_session.add_all([session_one, session_two])
    db_session.flush()

    baguette, fromage, bonjour = french_vocabulary
    progress_mastered = UserVocabularyProgress(
        user_id=user.id,
        word_id=baguette.id,
        state="mastered",
        due_date=now.date(),
    )
    progress_learning = UserVocabularyProgress(
        user_id=user.id,
        word_id=fromage.id,
        state="learning",
        due_date=(now + timedelta(days=2)).date(),
    )
    progress_new = UserVocabularyProgress(
        user_id=user.id,
        word_id=bonjour.id,
        state="learning",
        due_date=now.date(),
    )
    db_session.add_all([progress_mastered, progress_learning, progress_new])
    db_session.flush()

    review = ReviewLog(progress_id=progress_mastered.id, rating=3, review_date=now)
    db_session.add(review)

    interaction = WordInteraction(
        session_id=session_one.id,
        user_id=user.id,
        word_id=baguette.id,
        interaction_type="learner_use",
        error_type="gender",
        error_description="Le baguette devrait être la baguette.",
    )
    db_session.add(interaction)
    db_session.commit()

    summary_response = await async_client.get("/api/v1/analytics/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["sessions_completed"] == 2
    assert summary["words_mastered"] == 1
    assert summary["reviews_due_today"] >= 2  # two due items today
    assert summary["reviews_due_week"] >= summary["reviews_due_today"]

    stats_response = await async_client.get(
        "/api/v1/analytics/statistics", params={"days": 30}, headers=headers
    )
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert any(point["value"] > 0 for point in stats["xp_earned"])
    assert len(stats["reviews_completed"]) >= 1

    streak_response = await async_client.get(
        "/api/v1/analytics/streak", params={"window_days": 30}, headers=headers
    )
    assert streak_response.status_code == 200
    streak = streak_response.json()
    assert streak["longest_streak"] >= streak["current_streak"]
    assert len(streak["calendar"]) >= 2

    heatmap_response = await async_client.get("/api/v1/analytics/vocabulary", headers=headers)
    assert heatmap_response.status_code == 200
    heatmap = heatmap_response.json()
    assert heatmap["total"] == 3
    mastered_bucket = next(item for item in heatmap["states"] if item["state"] == "mastered")
    assert mastered_bucket["count"] == 1

    errors_response = await async_client.get(
        "/api/v1/analytics/errors", params={"limit": 5}, headers=headers
    )
    assert errors_response.status_code == 200
    errors = errors_response.json()
    assert errors["total"] == 1
    assert errors["items"][0]["error_type"] == "gender"
