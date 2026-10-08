"""WP-123b (proposed patch) — the vocabulary check's credit is not learning pace.

A placed B2 learner's ~2,800 credited cards were counted as words learnt in the
last 14 days (≈200 a day) and, a week later, as a perfectly retained sample.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.level_forecast import measured_intake


def test_credited_cards_are_neither_intake_nor_retention(db_session):
    user = User(id=uuid.uuid4(), email=f"wp123b-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
                native_language="en", target_language="fr", proficiency_level="B2", cefr_estimate="B2.1",
                cefr_estimate_payload={})
    db_session.add(user)
    db_session.flush()
    now = datetime.now(UTC)
    for index in range(30):
        text = f"credit{uuid.uuid4().hex[:8]}"
        word = VocabularyWord(word=text, normalized_word=text, language="fr")
        db_session.add(word)
        db_session.flush()
        db_session.add(UserVocabularyProgress(
            user_id=user.id, word_id=word.id, provenance="band_check_inferred" if index < 28 else None,
            stability=60.0, reps=2, state="review", created_at=now - timedelta(days=1),
        ))
    db_session.commit()
    measured = measured_intake(db_session, user, now=now)
    assert measured.words_per_day == 2 / 14  # the two words the learner met, not the 28 credited
    later = measured_intake(db_session, user, now=now + timedelta(days=10))
    assert later.word_sample == 2
