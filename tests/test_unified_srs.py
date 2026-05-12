"""Tests for the cross-mode unified SRS service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.unified_srs import InterleavingMode, ItemType, UnifiedSRSService


def _user(db_session, *, email: str | None = None) -> User:
    user = User(
        id=uuid4(),
        email=email or f"unified-srs-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="B1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _seed_due_memory(db_session, user: User) -> tuple[GrammarConcept, VocabularyWord, UserError]:
    now = datetime.now(timezone.utc)
    concept = GrammarConcept(
        external_id=f"FR_B1_TEST_{uuid4().hex[:8]}",
        language="fr",
        name="Object pronoun contrast",
        level="B1",
        category="Pronouns",
        active=True,
    )
    inactive = GrammarConcept(
        external_id=f"FR_B1_ARCHIVED_{uuid4().hex[:8]}",
        language="fr",
        name="Archived micro-topic",
        level="B1",
        category="Archived",
        active=False,
    )
    word = VocabularyWord(
        language="fr",
        word="soigner",
        normalized_word="soigner",
        english_translation="to take care of",
        difficulty_level=2,
    )
    db_session.add_all([concept, inactive, word])
    db_session.flush()
    db_session.add_all(
        [
            UserGrammarProgress(
                user_id=user.id,
                concept_id=concept.id,
                score=3.0,
                reps=2,
                state="in_arbeit",
                next_review=now - timedelta(hours=2),
            ),
            UserGrammarProgress(
                user_id=user.id,
                concept_id=inactive.id,
                score=1.0,
                reps=1,
                state="in_arbeit",
                next_review=now - timedelta(days=3),
            ),
            UserVocabularyProgress(
                user_id=user.id,
                word_id=word.id,
                state="learning",
                due_at=now - timedelta(minutes=30),
                due_date=(now + timedelta(days=2)).date(),
                lapses=1,
            ),
        ]
    )
    durable_error = UserError(
        user_id=user.id,
        concept_id=concept.id,
        linked_word_id=word.id,
        error_category="grammar",
        task_error_type="pronoun_choice",
        display_label="Pronoun choice: en/la",
        original_text="tu en peux me pose",
        correction="tu peux me la poser",
        why_wrong="You used en for a specific object that needs la.",
        repair_hint="Ask what the pronoun replaces before choosing en or la.",
        review_mode="grammar",
        source_type="graphic_novel",
        state="review",
        occurrences=2,
        lapses=1,
        next_review_date=now - timedelta(hours=1),
        error_metadata={"severity": 3},
    )
    task_compliance = UserError(
        user_id=user.id,
        error_category="grammar",
        task_error_type="task_compliance",
        display_label="Missing requested target",
        review_mode="grammar",
        source_type="atelier",
        state="review",
        occurrences=1,
        lapses=0,
        next_review_date=now - timedelta(hours=1),
    )
    mastered_error = UserError(
        user_id=user.id,
        error_category="grammar",
        task_error_type="agreement",
        display_label="Old mastered error",
        review_mode="grammar",
        state="mastered",
        next_review_date=now - timedelta(days=5),
    )
    db_session.add_all([durable_error, task_compliance, mastered_error])
    db_session.commit()
    return concept, word, durable_error


def test_unified_queue_surfaces_cross_mode_due_items_and_filters_noise(db_session) -> None:
    user = _user(db_session)
    concept, word, _ = _seed_due_memory(db_session, user)

    session = UnifiedSRSService(db_session).get_daily_practice_queue(
        user_id=user.id,
        interleaving_mode=InterleavingMode.RANDOM,
    )
    items = session.queue
    by_type = {item.item_type for item in items}
    titles = {item.display_title for item in items}

    assert {ItemType.ERROR, ItemType.GRAMMAR, ItemType.VOCAB} <= by_type
    assert "Pronoun choice: en/la" in titles
    assert "Object pronoun contrast" in titles
    assert "soigner" in titles
    assert "Missing requested target" not in titles
    assert "Old mastered error" not in titles
    assert "Archived micro-topic" not in titles

    error_item = next(item for item in items if item.item_type == ItemType.ERROR)
    assert error_item.metadata["source_label"] == "Feuilleton"
    assert error_item.metadata["concept_id"] == concept.id
    assert error_item.metadata["linked_word_id"] == word.id


def test_unified_queue_labels_mission_phrases(db_session) -> None:
    user = _user(db_session)
    now = datetime.now(timezone.utc)
    phrase = VocabularyWord(
        language="fr",
        word="Est-ce que vous pourriez me confirmer ?",
        normalized_word="est-ce que vous pourriez me confirmer ?",
        english_translation="Could you confirm for me?",
        difficulty_level=2,
        topic_tags=["mission_phrase", "real_world", "message"],
    )
    db_session.add(phrase)
    db_session.flush()
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=phrase.id,
            state="learning",
            due_at=now - timedelta(minutes=5),
            due_date=now.date(),
        )
    )
    db_session.commit()

    session = UnifiedSRSService(db_session).get_daily_practice_queue(user_id=user.id)
    item = next(item for item in session.queue if item.display_title == phrase.word)

    assert item.display_subtitle == "Mission phrase from Missions"
    assert item.level == "Mission phrase"
    assert item.metadata["review_mode"] == "mission_phrase"
    assert item.metadata["route"] == "/daily-practice?focus=mission"


def test_completing_error_item_credits_linked_grammar_and_vocabulary(db_session) -> None:
    user = _user(db_session)
    concept, word, error = _seed_due_memory(db_session, user)

    result = UnifiedSRSService(db_session).complete_item(
        user_id=user.id,
        item_type=ItemType.ERROR,
        item_id=str(error.id),
        rating=3,
    )

    db_session.refresh(error)
    grammar_progress = (
        db_session.query(UserGrammarProgress)
        .filter(
            UserGrammarProgress.user_id == user.id,
            UserGrammarProgress.concept_id == concept.id,
        )
        .one()
    )
    vocab_progress = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == word.id,
        )
        .one()
    )

    assert result["state"] == "review"
    assert error.next_review_date is not None
    assert grammar_progress.last_review is not None
    assert grammar_progress.notes and "unified_srs" in grammar_progress.notes
    assert vocab_progress.last_review_date is not None
    assert vocab_progress.reps >= 1


def test_unified_queue_endpoint_returns_serialized_items(client: TestClient, db_session) -> None:
    email = f"unified-api-{uuid4().hex}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "strongpass",
            "target_language": "fr",
            "native_language": "en",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strongpass"},
    )
    token = login.json()["access_token"]
    user = db_session.query(User).filter(User.email == email).one()
    _seed_due_memory(db_session, user)

    response = client.get(
        "/api/v1/progress/unified-queue",
        params={"limit": 10},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_due"] >= 3
    assert {item["item_type"] for item in payload["queue"]} >= {"error", "grammar", "vocab"}
    assert payload["queue"][0]["metadata"]
