"""Round 3 (walk 2, 17 Nov 2026): the day deck holds at most as many reviews as new words.

Both walks' day 6 dealt 27 and 30 cards: 15 new words and every word of day 1 at
once. A card rated «Good» on first sight gets the scheduler's first interval,
five days (``review_logs.interval_after`` = 5 for all of A1's day-1 «Good»
cards), so day 1's whole deck falls due together on day 6, day 2's on day 7, and
so on. The deck is now capped: the day's new-word dose plus at most as many
reviews, the longest waiting first; the rest are still due and come the next day.
At «Normal» (15 new words) that is at most 30 cards.

A separate function, called from ``day_words._due_review_ids`` (PR 877 owns the
rest of that module) and from ``daily_session.day_deck``'s fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session


def day_review_cap(user: Any) -> int:
    """The most reviews one day deck holds: the learner's planned new words a day."""

    from app.services.vocabulary_pace import planned_new_words

    return max(0, int(planned_new_words(user)))


def _due_of(row: Any) -> datetime:
    for value in (getattr(row, "due_at", None), getattr(row, "next_review_date", None)):
        if value is not None:
            return value if value.tzinfo else value.replace(tzinfo=UTC)
    if getattr(row, "due_date", None) is not None:
        return datetime.combine(row.due_date, datetime.min.time(), tzinfo=UTC)
    return datetime.min.replace(tzinfo=UTC)


def cap_day_reviews(db: Session, user: Any, word_ids: list[int]) -> list[int]:
    """``word_ids`` cut to :func:`day_review_cap`, the longest waiting first."""

    cap = day_review_cap(user)
    if len(word_ids) <= cap:
        return list(word_ids)
    from app.db.models.progress import UserVocabularyProgress

    rows = db.scalars(
        select(UserVocabularyProgress).where(
            UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id.in_(word_ids)
        )
    ).all()
    when = {int(row.word_id): _due_of(row) for row in rows}
    floor = datetime.min.replace(tzinfo=UTC)
    position = {word_id: index for index, word_id in enumerate(word_ids)}
    ordered = sorted(word_ids, key=lambda word_id: (when.get(int(word_id), floor), position[word_id]))
    return ordered[:cap]


__all__ = ["cap_day_reviews", "day_review_cap"]
