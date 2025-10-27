from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.db.models import User, VocabularyWord
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.services.progress import ProgressService
from app.services.session_service import SessionService


@pytest.fixture()
def seeded_user(db_session):
    user = User(
        email=f"adaptive+{uuid4().hex}@example.com",
        hashed_password="not-used",
        native_language="en",
        target_language="fr",
        proficiency_level="B1",
    )
    db_session.add(user)
    db_session.flush()

    word = VocabularyWord(
        language="fr",
        word="réviser",
        normalized_word="reviser",
        english_translation="to review",
        frequency_rank=100,
        difficulty_level=2,
    )
    db_session.add(word)
    db_session.flush()

    progress = UserVocabularyProgress(user_id=user.id, word_id=word.id, state="learning")
    db_session.add(progress)
    db_session.commit()
    return user, word, progress


def test_review_performance_calculation(db_session, seeded_user):
    user, _, progress = seeded_user
    now = datetime.now(timezone.utc)
    ratings = [3, 2, 1]
    logs = [
        ReviewLog(progress=progress, rating=rating, review_date=now - timedelta(days=index))
        for index, rating in enumerate(ratings, start=1)
    ]
    db_session.add_all(logs)
    db_session.commit()

    service = ProgressService(db_session)
    performance = service.calculate_review_performance(user.id, lookback_days=7, now=now)
    expected = (1.0 + 0.66 + 0.33) / 3
    assert performance == pytest.approx(expected, rel=1e-2)


def test_adaptive_review_ratio_poor_performance(db_session, seeded_user):
    user, _, progress = seeded_user
    now = datetime.now(timezone.utc)
    logs = [
        ReviewLog(progress=progress, rating=0, review_date=now - timedelta(days=day))
        for day in range(1, 4)
    ]
    db_session.add_all(logs)
    db_session.commit()

    service = ProgressService(db_session)
    ratio = service.calculate_adaptive_review_ratio(user.id)
    assert ratio == pytest.approx(0.75)


def test_new_word_budget_respects_due_reviews(db_session):
    user = User(
        email="due@example.com",
        hashed_password="pass",
        native_language="en",
        target_language="fr",
    )
    db_session.add(user)
    db_session.flush()

    today = datetime.now(timezone.utc).date()
    for index in range(20):
        word = VocabularyWord(
            language="fr",
            word=f"mot{index}",
            normalized_word=f"mot{index}",
            english_translation=f"word{index}",
            frequency_rank=index + 1,
        )
        db_session.add(word)
        db_session.flush()
        progress = UserVocabularyProgress(
            user_id=user.id,
            word_id=word.id,
            due_date=today,
            state="review",
        )
        db_session.add(progress)
    db_session.commit()

    service = ProgressService(db_session)
    new_budget = service.calculate_new_word_budget(user.id, session_capacity=15)
    assert new_budget == 0


def test_session_capacity_calculation():
    service = SessionService.__new__(SessionService)
    short = service._calculate_session_capacity(10)
    medium = service._calculate_session_capacity(20)
    long = service._calculate_session_capacity(35)

    assert short["estimated_turns"] >= 3
    assert short["words_per_turn"] == 4
    assert medium["words_per_turn"] == 6
    assert long["words_per_turn"] == 8
