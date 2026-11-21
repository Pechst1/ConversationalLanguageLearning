"""Round 3 (walk 2, 17 Nov 2026) — the day deck holds at most as many reviews as new words.

Day 6 dealt 27 (A1) and 30 (B1) cards: 15 new and all of day 1's words at once (a
card rated «Good» on first sight is next due five days later, so a whole day's
deck falls due together). The deck is capped at the day's new-word dose plus as
many reviews, the longest waiting first; the rest come the next day.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord

NOW = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


def _learner(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"r3-deck-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
        timezone="UTC",
        daily_pace="normal",
    )
    db.add(user)
    db.flush()
    return user


def _due_words(db: Session, user: User, n: int) -> list[int]:
    """``n`` words due, the first one due longest ago… in a shuffled order."""

    ids: list[int] = []
    for index in range(n):
        word = VocabularyWord(
            word=f"r3cap{uuid.uuid4().hex[:8]}",
            normalized_word=f"r3cap{uuid.uuid4().hex[:8]}",
            language="fr",
            english_translation="x",
            frequency_rank=100 + index,
        )
        db.add(word)
        db.flush()
        due = NOW - timedelta(days=n - index)
        db.add(
            UserVocabularyProgress(
                user_id=user.id, word_id=word.id, reps=1, state="review", due_at=due, next_review_date=due
            )
        )
        ids.append(int(word.id))
    db.flush()
    return ids


def test_the_deck_holds_at_most_the_dose_in_reviews_oldest_first(db_session: Session) -> None:
    from app.services.day_review_cap import cap_day_reviews, day_review_cap
    from app.services.vocabulary_pace import planned_new_words

    user = _learner(db_session)
    ids = _due_words(db_session, user, 27)
    dose = planned_new_words(user)
    assert day_review_cap(user) == dose
    capped = cap_day_reviews(db_session, user, list(reversed(ids)))
    assert len(capped) == dose
    assert set(capped) == set(ids[:dose]), "the longest waiting first"


def test_the_plan_s_reviews_are_capped(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import day_words
    from app.services.progress import ProgressService
    from app.services.vocabulary_pace import planned_new_words

    user = _learner(db_session)
    ids = _due_words(db_session, user, 40)

    def due_context(self, **kwargs):
        return {"due_words": [{"word_id": word_id} for word_id in ids[: kwargs.get("limit", 100)]]}

    monkeypatch.setattr(ProgressService, "get_vocabulary_due_context", due_context)
    reviews = day_words._due_review_ids(db_session, user, room=85, now=NOW)
    assert len(reviews) == planned_new_words(user)
    assert planned_new_words(user) + len(reviews) <= 2 * planned_new_words(user)
