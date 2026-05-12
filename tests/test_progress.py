"""Tests for learner progress endpoints."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.progress import ProgressService


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


def test_learning_queue_includes_non_anki_words_for_target_language(db_session) -> None:
    user = User(
        email="non-anki-queue@example.com",
        hashed_password="pass",
        native_language="en",
        target_language="fr",
    )
    db_session.add(user)
    db_session.flush()

    due_word = VocabularyWord(
        language="fr",
        word="baguette",
        normalized_word="baguette",
        english_translation="baguette",
    )
    new_word = VocabularyWord(
        language="fr",
        word="croissant",
        normalized_word="croissant",
        english_translation="croissant",
    )
    other_language_word = VocabularyWord(
        language="es",
        word="queso",
        normalized_word="queso",
        english_translation="cheese",
    )
    db_session.add_all([due_word, new_word, other_language_word])
    db_session.flush()

    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=due_word.id,
            due_date=date.today(),
            state="learning",
        )
    )
    db_session.commit()

    queue = ProgressService(db_session).get_learning_queue(user=user, limit=3)
    queued_words = {item.word.word for item in queue}

    assert "baguette" in queued_words
    assert "croissant" in queued_words
    assert "queso" not in queued_words


def test_direction_filter_keeps_non_directional_words_in_shared_queue(db_session) -> None:
    user = User(
        email="direction-shared-queue@example.com",
        hashed_password="pass",
        native_language="en",
        target_language="it",
    )
    db_session.add(user)
    db_session.flush()

    matching_direction = VocabularyWord(
        language="it",
        word="formaggio",
        normalized_word="formaggio",
        english_translation="cheese",
        direction="fr_to_de",
        is_anki_card=True,
    )
    non_directional = VocabularyWord(
        language="it",
        word="insalata",
        normalized_word="insalata",
        english_translation="salad",
    )
    opposite_direction = VocabularyWord(
        language="it",
        word="zuppa",
        normalized_word="zuppa",
        english_translation="soup",
        direction="de_to_fr",
        is_anki_card=True,
    )
    db_session.add_all([matching_direction, non_directional, opposite_direction])
    db_session.commit()

    queue = ProgressService(db_session).get_learning_queue(
        user=user,
        limit=3,
        direction="fr_to_de",
    )
    queued_words = {item.word.word for item in queue}

    assert "formaggio" in queued_words
    assert "insalata" in queued_words
    assert "zuppa" not in queued_words


def test_deck_filter_restricts_learning_queue_to_requested_deck(db_session) -> None:
    user = User(
        email="deck-filter@example.com",
        hashed_password="pass",
        native_language="en",
        target_language="fr",
    )
    db_session.add(user)
    db_session.flush()

    matching_word = VocabularyWord(
        language="fr",
        word="malgre",
        normalized_word="malgre",
        english_translation="despite",
        deck_name="Französisch 5000::1. FR → DE",
    )
    other_deck_word = VocabularyWord(
        language="fr",
        word="cependant",
        normalized_word="cependant",
        english_translation="however",
        deck_name="Another Deck",
    )
    generic_word = VocabularyWord(
        language="fr",
        word="pourtant",
        normalized_word="pourtant",
        english_translation="yet",
    )
    db_session.add_all([matching_word, other_deck_word, generic_word])
    db_session.commit()

    queue = ProgressService(db_session).get_learning_queue(
        user=user,
        limit=10,
        deck_name="Französisch 5000::1. FR → DE",
    )
    queued_words = {item.word.word for item in queue}

    assert "malgre" in queued_words
    assert "cependant" not in queued_words
    assert "pourtant" not in queued_words
