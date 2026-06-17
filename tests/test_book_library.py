"""Regression tests for the user-owned guided reading library."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.models.library import BookEpisode, UserBook
from app.db.models.user import User
from app.services.book_library import BookLibraryService


def _user(db_session, email: str) -> User:
    user = User(
        email=email,
        hashed_password="test",
        full_name="Library Tester",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _register_and_login(client: TestClient, email: str, password: str = "library-secure") -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Library Tester",
            "native_language": "en",
            "target_language": "fr",
            "proficiency_level": "A2",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _book_bytes() -> bytes:
    first = (
        "CHAPTER 1\n"
        + (
            "Marie ouvre la porte et regarde la rue calme. "
            "Elle ne comprend pas pourquoi la lumiere reste allumee. "
        )
        * 45
    )
    second = (
        "\n\nCHAPTER 2\n"
        + (
            "Le lendemain, Paul a trouve une lettre sous la table. "
            "Si Marie ecoute bien, elle entendra la verite. "
        )
        * 45
    )
    return (first + second).encode("utf-8")


def test_user_book_processing_segments_whole_book_into_grounded_episodes(db_session) -> None:
    user = _user(db_session, "library-service@example.com")
    service = BookLibraryService(db_session)
    book, deduped = service.create_upload_record(
        user=user,
        file_content=_book_bytes(),
        filename="petit-test.txt",
        title="Petit Test",
        author="Atelier",
        target_level="A1",
        task_id="library-task-1",
    )

    assert deduped is False

    processed = service.process_upload(
        book_id=book.id,
        file_content=_book_bytes(),
        filename="petit-test.txt",
        title="Petit Test",
        author="Atelier",
        target_level="A1",
        user=user,
    )

    episodes = db_session.query(BookEpisode).filter(BookEpisode.user_book_id == processed.id).all()
    assert processed.status == "ready"
    assert processed.total_episodes == len(episodes)
    assert processed.total_episodes >= 4
    assert processed.estimated_total_words > 0
    assert all(episode.word_count <= 170 for episode in episodes)
    assert any("CHAPTER 2" not in episode.passage_text and "Paul" in episode.passage_text for episode in episodes)

    first_payload = episodes[0].exercise_payload
    assert first_payload["engine_version"]
    assert first_payload["source"] == "deterministic_passage_scaffold"
    assert first_payload["comprehension"][0]["evidence"] in episodes[0].passage_text
    assert first_payload["vocabulary"]
    assert first_payload["production"]["success_criteria"]


def test_library_status_and_reads_are_scoped_to_owner(client: TestClient, db_session) -> None:
    owner_token = _register_and_login(client, "library-owner@example.com")
    other_token = _register_and_login(client, "library-other@example.com")
    owner = db_session.query(User).filter(User.email == "library-owner@example.com").one()
    other = db_session.query(User).filter(User.email == "library-other@example.com").one()

    service = BookLibraryService(db_session)
    book, _ = service.create_upload_record(
        user=owner,
        file_content=b"CHAPTER 1\nUne phrase assez longue pour creer un episode de test.",
        filename="private.txt",
        title="Private Book",
        target_level="A2",
        task_id="private-task",
    )
    book.status = "ready"
    book.status_message = "Ready."
    book.progress_percent = 100
    db_session.add(book)
    db_session.commit()

    owner_status = client.get(
        "/api/v1/stories/upload-status/private-task",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_status.status_code == 200
    assert owner_status.json()["book_id"] == str(book.id)
    assert owner_status.json()["status"] == "completed"

    other_status = client.get(
        "/api/v1/stories/upload-status/private-task",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_status.status_code == 404
    assert service.list_books(user=other) == []
    with pytest.raises(ValueError):
        service.get_book(user=other, book_id=book.id)


def test_library_episode_api_returns_passage_and_exercises_for_owner(client: TestClient, db_session) -> None:
    token = _register_and_login(client, "library-episode@example.com")
    user = db_session.query(User).filter(User.email == "library-episode@example.com").one()
    service = BookLibraryService(db_session)
    book, _ = service.create_upload_record(
        user=user,
        file_content=_book_bytes(),
        filename="episode.txt",
        title="Episode Book",
        target_level="A2",
        task_id="episode-task",
    )
    service.process_upload(
        book_id=book.id,
        file_content=_book_bytes(),
        filename="episode.txt",
        title="Episode Book",
        target_level="A2",
        user=user,
    )

    response = client.get(
        f"/api/v1/stories/library/{book.id}/episodes/0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["passage_text"]
    assert payload["exercise_payload"]["comprehension"]
    assert payload["exercise_payload"]["source"] == "deterministic_passage_scaffold"

    completed = client.post(
        f"/api/v1/stories/library/{book.id}/episodes/0/complete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert completed.status_code == 200
    assert completed.json()["completed_episode_indices"] == [0]


def test_atelier_today_surfaces_next_library_episode(client: TestClient, db_session) -> None:
    token = _register_and_login(client, "library-today@example.com")
    user = db_session.query(User).filter(User.email == "library-today@example.com").one()
    book = UserBook(
        user_id=user.id,
        title="Daily Reader",
        author="Atelier",
        source_filename="daily-reader.txt",
        source_type="txt",
        source_hash="daily-reader-hash",
        target_level="A2",
        status="ready",
        status_message="Ready.",
        progress_percent=100,
        total_episodes=2,
        current_episode_index=1,
        completed_episode_indices=[0],
        estimated_total_words=400,
        task_id="daily-reader-task",
        extra_metadata={},
    )
    db_session.add(book)
    db_session.flush()
    db_session.add(
        BookEpisode(
            user_book_id=book.id,
            order_index=1,
            title="The Second Passage",
            passage_text="Marie lit la deuxieme page et note un detail important.",
            est_reading_minutes=3,
            cefr_level="A2",
            word_count=10,
            vocab_seed=[],
            grammar_seed=[],
            exercise_payload={"source": "test"},
            status="ready",
        )
    )
    db_session.commit()

    response = client.get("/api/v1/atelier/today", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["library_episode"]["book_id"] == str(book.id)
    assert payload["library_episode"]["episode_index"] == 1
    assert payload["progress"]["librarySuggested"] is True
    assert payload["progress"]["libraryDone"] is False
    assert any(node["id"] == "library" and node["suggested"] for node in payload["progress"]["nodes"])
