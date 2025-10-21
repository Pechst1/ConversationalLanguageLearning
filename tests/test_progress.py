"""Tests for learner progress endpoints."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord


def register_and_login(client: TestClient, email: str, password: str) -> str:
    payload = {
        "email": email,
        "password": password,
        "target_language": "es",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=payload)
    login_response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return login_response.json()["access_token"]


@pytest.fixture()
def review_vocabulary(db_session):
    words = [
        VocabularyWord(
            language="es",
            word="hola",
            normalized_word="hola",
            part_of_speech="interjection",
            frequency_rank=1,
            english_translation="hello",
            difficulty_level=1,
            topic_tags=["greetings"],
        ),
        VocabularyWord(
            language="es",
            word="adiós",
            normalized_word="adios",
            part_of_speech="interjection",
            frequency_rank=2,
            english_translation="goodbye",
            difficulty_level=1,
            topic_tags=["greetings"],
        ),
    ]
    db_session.add_all(words)
    db_session.commit()
    try:
        yield words
    finally:
        db_session.query(VocabularyWord).delete()
        db_session.commit()


def test_progress_detail_defaults_to_new_state(client: TestClient, review_vocabulary) -> None:
    token = register_and_login(client, "progress-new@example.com", "verysecure")
    word_id = review_vocabulary[0].id

    response = client.get(
        f"/api/v1/progress/{word_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "new"
    assert payload["reps"] == 0
    assert payload["reviews_logged"] == 0


def test_submit_review_returns_next_schedule(client: TestClient, review_vocabulary) -> None:
    token = register_and_login(client, "progress-review@example.com", "verysecure")
    word_id = review_vocabulary[0].id

    response = client.post(
        "/api/v1/progress/review",
        json={"word_id": word_id, "rating": 3},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["word_id"] == word_id
    assert payload["scheduled_days"] >= 1
    assert payload["state"] in {"reviewing", "learning"}

    detail = client.get(
        f"/api/v1/progress/{word_id}", headers={"Authorization": f"Bearer {token}"}
    )
    detail_payload = detail.json()
    assert detail_payload["reps"] == 1
    assert detail_payload["state"] != "new"
    assert detail_payload["reviews_logged"] == 1


def test_queue_orders_due_before_new(client: TestClient, review_vocabulary, db_session) -> None:
    token = register_and_login(client, "progress-queue@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}
    word_id = review_vocabulary[0].id

    # Initial queue should contain new vocabulary entries.
    initial_queue = client.get("/api/v1/progress/queue", headers=headers, params={"limit": 2})
    assert initial_queue.status_code == 200
    initial_payload = initial_queue.json()
    assert len(initial_payload) == 2
    assert all(item["is_new"] for item in initial_payload)

    # Complete a review and force the due date to today to surface in the queue.
    client.post(
        "/api/v1/progress/review",
        json={"word_id": word_id, "rating": 2},
        headers=headers,
    )
    user = db_session.query(User).filter(User.email == "progress-queue@example.com").one()
    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.word_id == word_id,
            UserVocabularyProgress.user_id == user.id,
        )
        .one()
    )
    progress.due_date = date.today()
    db_session.commit()

    updated_queue = client.get("/api/v1/progress/queue", headers=headers, params={"limit": 2})
    assert updated_queue.status_code == 200
    queue_payload = updated_queue.json()
    assert len(queue_payload) == 2
    assert queue_payload[0]["word_id"] == word_id
    assert queue_payload[0]["is_new"] is False
    assert queue_payload[0]["state"] != "new"
