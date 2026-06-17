"""Tests for learner progress endpoints."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.models.error import UserError
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.progress import ReviewLog, UserVocabularyProgress
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


def test_vocabulary_mastery_map_returns_human_srs_states(client: TestClient, db_session) -> None:
    email = "progress-map@example.com"
    token = register_and_login(client, email, "verysecure")
    user = db_session.query(User).filter(User.email == email).one()
    now = datetime.now(timezone.utc)
    words = [
        VocabularyWord(
            language="es",
            word="nuevo",
            normalized_word="nuevo",
            frequency_rank=1,
            english_translation="new",
            direction="fr_to_de",
            deck_name="French 5000",
            is_anki_card=True,
        ),
        VocabularyWord(
            language="es",
            word="debido",
            normalized_word="debido",
            frequency_rank=2,
            english_translation="due",
            direction="fr_to_de",
            deck_name="French 5000",
            is_anki_card=True,
        ),
        VocabularyWord(
            language="es",
            word="fragil",
            normalized_word="fragil",
            frequency_rank=3,
            english_translation="fragile",
            direction="fr_to_de",
            deck_name="French 5000",
            is_anki_card=True,
        ),
        VocabularyWord(
            language="es",
            word="solido",
            normalized_word="solido",
            frequency_rank=4,
            english_translation="solid",
            direction="fr_to_de",
            deck_name="French 5000",
            is_anki_card=True,
        ),
    ]
    db_session.add_all(words)
    db_session.flush()
    db_session.add_all(
        [
            UserVocabularyProgress(
                user_id=user.id,
                word_id=words[1].id,
                scheduler="anki",
                state="reviewing",
                phase="review",
                due_at=now - timedelta(days=1),
                reps=2,
                proficiency_score=65,
            ),
            UserVocabularyProgress(
                user_id=user.id,
                word_id=words[2].id,
                scheduler="anki",
                state="relearning",
                phase="relearn",
                lapses=2,
                reps=3,
                proficiency_score=25,
            ),
            UserVocabularyProgress(
                user_id=user.id,
                word_id=words[3].id,
                scheduler="anki",
                state="reviewing",
                phase="review",
                reps=8,
                proficiency_score=95,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/progress/vocabulary/map",
        params={"limit": 10, "direction": "fr_to_de"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    states = {cell["word"]: cell["mastery_state"] for cell in payload["cells"]}
    assert states["nuevo"] == "new"
    assert states["debido"] == "due"
    assert states["fragil"] == "fragile"
    assert states["solido"] == "mastered"
    assert payload["summary"]["total"] >= 4
    assert payload["summary"]["new"] >= 1
    assert payload["summary"]["due"] >= 1
    assert payload["summary"]["fragile"] >= 1
    assert payload["summary"]["mastered"] >= 1


def test_weekly_dossier_summarizes_repairs_reviews_and_threads(client: TestClient, db_session) -> None:
    email = "weekly-dossier@example.com"
    token = register_and_login(client, email, "verysecure")
    user = db_session.query(User).filter(User.email == email).one()
    now = datetime.now(timezone.utc)
    strong_word = VocabularyWord(
        language="es",
        word="avanzar",
        normalized_word="avanzar",
        frequency_rank=10,
        english_translation="advance",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    fragile_word = VocabularyWord(
        language="es",
        word="olvidar",
        normalized_word="olvidar",
        frequency_rank=11,
        english_translation="forget",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add_all([strong_word, fragile_word])
    db_session.flush()
    strong_progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=strong_word.id,
        scheduler="anki",
        state="reviewing",
        phase="review",
        reps=5,
        proficiency_score=82,
        times_seen=4,
        times_used_correctly=2,
    )
    fragile_progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=fragile_word.id,
        scheduler="anki",
        state="relearning",
        phase="relearn",
        reps=2,
        lapses=2,
        proficiency_score=20,
        times_seen=1,
        times_used_incorrectly=1,
    )
    db_session.add_all([strong_progress, fragile_progress])
    db_session.flush()
    db_session.add_all(
        [
            ReviewLog(progress_id=strong_progress.id, review_date=now, rating=2),
            UserError(
                user_id=user.id,
                error_category="vocabulary",
                display_label="Use target word",
                original_text="missing target",
                correction="avanzar",
                created_at=now,
            ),
            RealWorldMission(
                user_id=user.id,
                status="completed",
                cadence="ad_hoc",
                mission_type="message",
                title="Weekly test mission",
                brief="Use the word in context.",
                selected_concept_ids=[],
                target_errata_ids=[],
                target_vocabulary_ids=[strong_word.id],
                source_snapshot={},
                objectives=[],
                prompt_payload={},
                recap_payload={},
                completed_at=now,
            ),
            GraphicNovelScene(
                user_id=user.id,
                status="completed",
                cadence="ad_hoc",
                title="Weekly test scene",
                brief="A compact scene.",
                selected_concept_ids=[],
                target_errata_ids=[],
                target_vocabulary_ids=[fragile_word.id],
                source_snapshot={},
                script_payload={},
                recap_payload={},
                cache_key="weekly-dossier-scene",
                prompt_version="test",
                image_model="none",
                image_quality="low",
                completed_at=now,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/progress/weekly-dossier",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["headline"].startswith("Semaine")
    assert payload["stats"]["repairs_filed"] == 1
    assert payload["stats"]["vocabulary_reviews"] == 1
    assert payload["stats"]["words_seen"] == 5
    assert payload["stats"]["words_produced"] == 3
    assert payload["stats"]["missions_completed"] == 1
    assert payload["stats"]["feuilleton_scenes_completed"] == 1
    assert any(item["title"] == "avanzar" for item in payload["strengths"])
    assert any(item["title"] == "olvidar" for item in payload["fragile_threads"])
    assert [item["title"] for item in payload["next_actions"]][:2] == [
        "Repair the red notes",
        "Review today's words",
    ]


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


def test_vocabulary_recommendations_rank_due_fragile_and_new_cards(
    client: TestClient, db_session
) -> None:
    token = register_and_login(client, "progress-vocab-recs@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == "progress-vocab-recs@example.com").one()
    user.target_language = "fr"

    due_word = VocabularyWord(
        language="fr",
        word="arriver",
        normalized_word="arriver",
        frequency_rank=70,
        german_translation="ankommen",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    fragile_word = VocabularyWord(
        language="fr",
        word="prévoir",
        normalized_word="prevoir",
        frequency_rank=120,
        german_translation="vorsehen",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    new_word = VocabularyWord(
        language="fr",
        word="maison",
        normalized_word="maison",
        frequency_rank=30,
        german_translation="Haus",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    stopword = VocabularyWord(
        language="fr",
        word="le",
        normalized_word="le",
        frequency_rank=1,
        german_translation="der",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add_all([due_word, fragile_word, new_word, stopword])
    db_session.flush()
    created_word_ids = [due_word.id, fragile_word.id, new_word.id, stopword.id]

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            UserVocabularyProgress(
                user_id=user.id,
                word_id=due_word.id,
                scheduler="anki",
                state="reviewing",
                phase="review",
                due_at=now - timedelta(days=2),
                due_date=(now - timedelta(days=2)).date(),
                last_review_date=now - timedelta(days=8),
                stability=4.0,
                difficulty=6.0,
                interval_days=4,
                scheduled_days=4,
                reps=12,
                proficiency_score=72,
            ),
            UserVocabularyProgress(
                user_id=user.id,
                word_id=fragile_word.id,
                scheduler="anki",
                state="reviewing",
                phase="review",
                due_at=now + timedelta(days=5),
                due_date=(now + timedelta(days=5)).date(),
                last_review_date=now - timedelta(days=1),
                stability=1.2,
                difficulty=8.5,
                interval_days=6,
                scheduled_days=6,
                reps=6,
                lapses=1,
                proficiency_score=35,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/progress/vocabulary/recommendations",
        headers=headers,
        params={
            "limit": 3,
            "due_limit": 1,
            "fragile_limit": 1,
            "new_limit": 1,
            "direction": "fr_to_de",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["algorithm"] == "fsrs_retrievability_v1"
    assert payload["summary"]["due"] == 1
    assert payload["summary"]["fragile"] == 1
    assert payload["summary"]["new"] == 1
    assert [item["bucket"] for item in payload["items"]] == ["due", "fragile", "new"]
    assert [item["word"] for item in payload["items"]] == ["arriver", "prévoir", "maison"]
    assert payload["items"][0]["scheduler"] == "anki"
    assert payload["items"][0]["translations"]["de"] == "ankommen"
    assert "le" not in {item["word"] for item in payload["items"]}

    db_session.query(UserVocabularyProgress).filter(
        UserVocabularyProgress.user_id == user.id
    ).delete()
    db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(created_word_ids)).delete(
        synchronize_session=False
    )
    db_session.commit()


def test_vocabulary_recommendations_use_local_demo_user_without_auth(
    client: TestClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", True)
    word = VocabularyWord(
        language="fr",
        word="rappel",
        normalized_word="rappel",
        frequency_rank=40,
        german_translation="Erinnerung",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(word)
    db_session.commit()

    try:
        response = client.get(
            "/api/v1/progress/vocabulary/recommendations",
            params={
                "limit": 1,
                "due_limit": 0,
                "fragile_limit": 0,
                "new_limit": 1,
                "direction": "fr_to_de",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["word"] == "rappel"
        demo_user = db_session.query(User).filter(User.email == "atelier-demo@local.test").one()
        assert demo_user.target_language == "fr"
    finally:
        db_session.query(VocabularyWord).filter(VocabularyWord.id == word.id).delete()
        db_session.query(User).filter(User.email == "atelier-demo@local.test").delete()
        db_session.commit()


def test_vocabulary_recommendations_exclude_shared_mission_phrases_by_default(
    client: TestClient, db_session
) -> None:
    token = register_and_login(client, "progress-vocab-phrases@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == "progress-vocab-phrases@example.com").one()
    user.target_language = "fr"

    mission_phrase = VocabularyWord(
        language="fr",
        word="Bonjour, je voulais vous prevenir que...",
        normalized_word="bonjour je voulais vous prevenir que",
        frequency_rank=None,
        english_translation="Reusable opening or reply fragment",
        direction=None,
        is_anki_card=False,
    )
    deck_word = VocabularyWord(
        language="fr",
        word="abaisser",
        normalized_word="abaisser",
        frequency_rank=120,
        german_translation="herabsetzen, senken",
        direction="fr_to_de",
        deck_name="Französisch 5000::1. FR → DE",
        is_anki_card=True,
    )
    db_session.add_all([mission_phrase, deck_word])
    db_session.flush()

    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=mission_phrase.id,
            scheduler="fsrs",
            state="learning",
            phase="learn",
            due_at=datetime.now(timezone.utc) - timedelta(days=5),
            due_date=date.today() - timedelta(days=5),
            scheduled_days=1,
            proficiency_score=0,
        )
    )
    db_session.commit()

    try:
        response = client.get(
            "/api/v1/progress/vocabulary/recommendations",
            headers=headers,
            params={
                "limit": 4,
                "due_limit": 3,
                "fragile_limit": 0,
                "new_limit": 1,
                "direction": "fr_to_de",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        words = {item["word"] for item in payload["items"]}
        assert "abaisser" in words
        assert "Bonjour, je voulais vous prevenir que..." not in words
        assert all(item["deck_name"] for item in payload["items"])
    finally:
        db_session.query(UserVocabularyProgress).filter(
            UserVocabularyProgress.user_id == user.id
        ).delete()
        db_session.query(VocabularyWord).filter(
            VocabularyWord.id.in_([mission_phrase.id, deck_word.id])
        ).delete(synchronize_session=False)
        db_session.commit()


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
