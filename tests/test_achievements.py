"""Achievement endpoints over the WP-79 catalogue.

Reachability of every catalogue entry lives in ``tests/test_wp79_achievements.py``.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.models.achievement import Achievement
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.achievement import CATALOGUE, CATALOGUE_KEYS, AchievementDefinition, AchievementService
from app.services.streak import record_practice_day

TEST_PASSWORD = "securepass123"


def register_and_login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> str:
    payload = {
        "email": email,
        "password": password,
        "target_language": "fr",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=payload)
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login_response.json()["access_token"]


def _headers(client: TestClient, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {register_and_login(client, email)}"}


def test_the_catalogue_seeds_itself_on_the_first_read(client: TestClient, db_session):
    response = client.get("/api/v1/achievements", headers=_headers(client, "ach-list@example.com"))

    assert response.status_code == 200
    keys = [a["achievement_key"] for a in response.json()]
    assert keys == [item.key for item in CATALOGUE]
    # Idempotent: a second read neither duplicates nor reorders.
    again = client.get("/api/v1/achievements", headers=_headers(client, "ach-list2@example.com"))
    assert [a["achievement_key"] for a in again.json()] == keys
    rows = db_session.query(Achievement).filter(Achievement.achievement_key.in_(CATALOGUE_KEYS)).count()
    assert rows == len(CATALOGUE)


def test_retired_keys_are_never_listed(client: TestClient, db_session):
    AchievementService(db_session).seed_achievements(
        [
            AchievementDefinition(
                key="xp_bronze", name="XP Bronze", description="Earn 500 XP", category="xp", tier="bronze"
            )
        ]
    )
    response = client.get(
        "/api/v1/achievements/my",
        params={"include_locked": True},
        headers=_headers(client, "ach-retired@example.com"),
    )
    assert response.status_code == 200
    assert {a["achievement_key"] for a in response.json()} == set(CATALOGUE_KEYS)


def test_a_new_learner_has_nothing_unlocked(client: TestClient):
    headers = _headers(client, "ach-empty@example.com")
    assert client.get("/api/v1/achievements/my", headers=headers).json() == []

    locked = client.get("/api/v1/achievements/my", params={"include_locked": True}, headers=headers).json()
    assert len(locked) == len(CATALOGUE)
    assert all(item["completed"] is False for item in locked)
    assert all(item["xp_reward"] == 0 for item in locked), "no XP economy nobody can see"


def test_locked_progress_is_the_real_count(client: TestClient, db_session):
    email = "ach-progress@example.com"
    headers = _headers(client, email)
    user = db_session.query(User).filter(User.email == email).one()
    for i in range(20):
        word = VocabularyWord(
            language="fr", word=f"prog{i}", normalized_word=f"prog{i}", english_translation=f"p{i}", frequency_rank=i + 1
        )
        db_session.add(word)
        db_session.flush()
        db_session.add(UserVocabularyProgress(user_id=user.id, word_id=word.id, state="new"))
    db_session.commit()

    items = client.get("/api/v1/achievements/my", params={"include_locked": True}, headers=headers).json()
    words = next(a for a in items if a["achievement_key"] == "words_kept_50")
    assert (words["current_progress"], words["target_progress"], words["completed"]) == (20, 50, False)


def test_check_unlocks_once(client: TestClient, db_session):
    email = "ach-once@example.com"
    headers = _headers(client, email)
    user = db_session.query(User).filter(User.email == email).one()
    start = date(2026, 9, 1)
    for offset in range(3):
        record_practice_day(db_session, user, on_date=start + timedelta(days=offset))
    db_session.commit()

    first = client.post("/api/v1/achievements/check", headers=headers).json()
    assert [a["achievement_key"] for a in first["newly_unlocked"]] == ["session_streak_3"]
    second = client.post("/api/v1/achievements/check", headers=headers).json()
    assert second["total_unlocked"] == 0

    mine = client.get("/api/v1/achievements/my", headers=headers).json()
    assert [a["achievement_key"] for a in mine] == ["session_streak_3"]
    db_session.refresh(user)
    assert (user.total_xp or 0) == 0
