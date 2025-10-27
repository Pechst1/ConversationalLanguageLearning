"""Tests for achievement service and endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.achievement import AchievementDefinition, AchievementService


TEST_PASSWORD = "securepass123"


def register_and_login(
    client: TestClient, email: str, password: str = TEST_PASSWORD
) -> str:
    payload = {
        "email": email,
        "password": password,
        "target_language": "fr",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=payload)
    login_response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return login_response.json()["access_token"]


@pytest.fixture()
def seeded_achievements(db_session):
    """Seed basic achievements for testing."""

    service = AchievementService(db_session)
    definitions = [
        AchievementDefinition(
            key="first_session",
            name="First Steps",
            description="Complete your first session",
            category="session",
            tier="bronze",
            xp_reward=50,
        ),
        AchievementDefinition(
            key="session_streak_3",
            name="Three Day Streak",
            description="Complete sessions 3 days in a row",
            category="streak",
            tier="bronze",
            xp_reward=100,
        ),
        AchievementDefinition(
            key="vocabulary_learner",
            name="Vocabulary Learner",
            description="Master 50 words",
            category="vocabulary",
            tier="bronze",
            xp_reward=200,
        ),
        AchievementDefinition(
            key="xp_bronze",
            name="XP Bronze",
            description="Earn 500 XP",
            category="xp",
            tier="bronze",
            xp_reward=100,
        ),
    ]
    service.seed_achievements(definitions)
    try:
        yield
    finally:
        pass


def test_list_achievements(client: TestClient, seeded_achievements):
    token = register_and_login(client, "achievements-list@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/achievements", headers=headers)

    assert response.status_code == 200
    achievements = response.json()
    assert len(achievements) >= 4
    assert any(a["achievement_key"] == "first_session" for a in achievements)


def test_get_my_achievements_empty(client: TestClient, seeded_achievements):
    token = register_and_login(client, "achievements-empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/achievements/my", headers=headers)

    assert response.status_code == 200
    progress = response.json()
    assert len(progress) == 0


def test_get_my_achievements_with_locked(client: TestClient, seeded_achievements):
    token = register_and_login(client, "achievements-locked@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/achievements/my",
        params={"include_locked": True},
        headers=headers,
    )

    assert response.status_code == 200
    progress = response.json()
    assert len(progress) >= 4
    assert all(item["completed"] is False for item in progress)


def test_check_achievements_first_session(
    client: TestClient, db_session, seeded_achievements
):
    email = "achievements-first@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.query(User).filter(User.email == email).one()
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=15,
        status="completed",
        xp_earned=120,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(session)
    db_session.commit()

    response = client.post("/api/v1/achievements/check", headers=headers)

    assert response.status_code == 200
    result = response.json()
    assert result["total_unlocked"] == 1
    assert result["newly_unlocked"][0]["achievement_key"] == "first_session"

    db_session.refresh(user)
    assert user.total_xp >= 50


def test_check_achievements_streak(client: TestClient, db_session, seeded_achievements):
    email = "achievements-streak@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.query(User).filter(User.email == email).one()
    user.current_streak = 3
    db_session.commit()

    response = client.post("/api/v1/achievements/check", headers=headers)

    assert response.status_code == 200
    result = response.json()
    assert any(
        a["achievement_key"] == "session_streak_3" for a in result["newly_unlocked"]
    )


def test_check_achievements_vocabulary(
    client: TestClient, db_session, seeded_achievements
):
    email = "achievements-vocab@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.query(User).filter(User.email == email).one()

    for i in range(50):
        word = VocabularyWord(
            language="fr",
            word=f"mot{i}",
            normalized_word=f"mot{i}",
            english_translation=f"word{i}",
            frequency_rank=i + 1,
        )
        db_session.add(word)
        db_session.flush()

        progress = UserVocabularyProgress(
            user_id=user.id,
            word_id=word.id,
            state="mastered",
        )
        db_session.add(progress)

    db_session.commit()

    response = client.post("/api/v1/achievements/check", headers=headers)

    assert response.status_code == 200
    result = response.json()
    assert any(
        a["achievement_key"] == "vocabulary_learner" for a in result["newly_unlocked"]
    )


def test_check_achievements_xp(client: TestClient, db_session, seeded_achievements):
    email = "achievements-xp@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.query(User).filter(User.email == email).one()
    user.total_xp = 500
    db_session.commit()

    response = client.post("/api/v1/achievements/check", headers=headers)

    assert response.status_code == 200
    result = response.json()
    assert any(a["achievement_key"] == "xp_bronze" for a in result["newly_unlocked"])


def test_achievement_not_unlocked_twice(
    client: TestClient, db_session, seeded_achievements
):
    email = "achievements-duplicate@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.query(User).filter(User.email == email).one()
    user.total_xp = 500
    db_session.commit()

    first_check = client.post("/api/v1/achievements/check", headers=headers)
    assert first_check.status_code == 200
    assert first_check.json()["total_unlocked"] >= 1

    second_check = client.post("/api/v1/achievements/check", headers=headers)
    assert second_check.status_code == 200
    assert second_check.json()["total_unlocked"] == 0


def test_achievement_progress_tracking(
    client: TestClient, db_session, seeded_achievements
):
    email = "achievements-progress@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.query(User).filter(User.email == email).one()

    for i in range(25):
        word = VocabularyWord(
            language="fr",
            word=f"test{i}",
            normalized_word=f"test{i}",
            english_translation=f"test{i}",
            frequency_rank=i + 1,
        )
        db_session.add(word)
        db_session.flush()

        progress = UserVocabularyProgress(
            user_id=user.id,
            word_id=word.id,
            state="mastered",
        )
        db_session.add(progress)

    db_session.commit()

    response = client.get(
        "/api/v1/achievements/my",
        params={"include_locked": True},
        headers=headers,
    )

    assert response.status_code == 200
    progress_list = response.json()
    vocab_achievement = next(
        (a for a in progress_list if a["achievement_key"] == "vocabulary_learner"),
        None,
    )
    assert vocab_achievement is not None
    assert vocab_achievement["current_progress"] == 0
    assert vocab_achievement["target_progress"] == 50
    assert vocab_achievement["completed"] is False
