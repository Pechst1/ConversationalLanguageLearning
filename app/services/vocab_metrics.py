"""WP-115e — measuring retention honestly, from the review log.

In-session accuracy flatters: an answer given a minute after the word was shown says
little about memory. Every FSRS review, though, is a retrieval taken some time after the
last one, and since WP-115e the log records the scheduler's prediction (``predicted_r``)
and the lag (``elapsed_days_exact``). From that, read-only:

* **calibration** — predicted recall against actual recall, by bin: the scheduler is
  healthy when the two agree around the target (0.87);
* **the forgetting curve** — recall by lag (≈ 1, 7, 30 days, …), per format (typed,
  reply, recognition, …) and per place (the day, the drill, …): delayed retrieval,
  the headline the research asks for, never same-session accuracy;
* **the pilot** — for the hard words (≥ 2 lapses), recall at lags of a week or more in
  the story arm against the cahier arm (``story_words.pilot_arm``), only meaningful
  while ``VOCAB_STORY_PILOT_ENABLED`` is on;
* **load** — reviews per active learner-day, and today's backlog.

A review «passes» when its rating is above Again. Only reviews with a lag of at least
12 hours count as delayed (a same-day relearn is not a memory test).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models.progress import ReviewLog, UserVocabularyProgress

#: A lag shorter than this is a relearn inside the same day, not a memory test.
MIN_DELAYED_DAYS = 0.5
CALIBRATION_BINS: tuple[tuple[float, float], ...] = ((0.0, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.01))
LAG_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("1d", MIN_DELAYED_DAYS, 3.0),
    ("7d", 3.0, 14.0),
    ("30d", 14.0, 45.0),
    ("90d+", 45.0, 10_000.0),
)
HARD_LAPSES = 2


def _rows(db: Session, *, since: datetime, user_ids: list[Any] | None) -> list[tuple]:
    query = (
        select(
            ReviewLog.rating,
            ReviewLog.predicted_r,
            ReviewLog.elapsed_days_exact,
            ReviewLog.format,
            ReviewLog.source,
            UserVocabularyProgress.user_id,
            UserVocabularyProgress.word_id,
            UserVocabularyProgress.lapses,
        )
        .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
        .where(ReviewLog.review_date >= since, ReviewLog.elapsed_days_exact >= MIN_DELAYED_DAYS)
    )
    if user_ids:
        query = query.where(UserVocabularyProgress.user_id.in_(user_ids))
    return list(db.execute(query).all())


def _rate(passed: int, total: int) -> float | None:
    return round(passed / total, 4) if total else None


def calibration(rows: list[tuple]) -> list[dict[str, Any]]:
    out = []
    for low, high in CALIBRATION_BINS:
        hits = [row for row in rows if row.predicted_r is not None and low <= row.predicted_r < high]
        out.append(
            {
                "bin": f"{low:.2f}–{min(high, 1.0):.2f}",
                "reviews": len(hits),
                "predicted": round(sum(row.predicted_r for row in hits) / len(hits), 4) if hits else None,
                "actual": _rate(sum(1 for row in hits if row.rating > 0), len(hits)),
            }
        )
    return out


def forgetting_curve(rows: list[tuple], *, by: str | None = None) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        key = "all" if by is None else str(getattr(row, by) or "unknown")
        groups[key].append(row)
    curve: dict[str, list[dict[str, Any]]] = {}
    for key, members in sorted(groups.items()):
        points = []
        for label, low, high in LAG_BUCKETS:
            hits = [row for row in members if low <= (row.elapsed_days_exact or 0) < high]
            points.append({"lag": label, "reviews": len(hits), "recall": _rate(sum(1 for r in hits if r.rating > 0), len(hits))})
        curve[key] = points
    return curve


def pilot(rows: list[tuple]) -> dict[str, dict[str, Any]]:
    from app.services.story_words import pilot_arm

    arms: dict[str, list[tuple]] = {"story": [], "cahier": []}
    for row in rows:
        if (row.lapses or 0) >= HARD_LAPSES and (row.elapsed_days_exact or 0) >= 7:
            arms[pilot_arm(row.user_id, row.word_id)].append(row)
    return {
        arm: {
            "reviews": len(members),
            "words": len({(row.user_id, row.word_id) for row in members}),
            "recall_7d_plus": _rate(sum(1 for row in members if row.rating > 0), len(members)),
        }
        for arm, members in arms.items()
    }


def load(db: Session, *, since: datetime, user_ids: list[Any] | None, now: datetime) -> dict[str, Any]:
    day = func.date(ReviewLog.review_date)
    query = (
        select(UserVocabularyProgress.user_id, day, func.count(ReviewLog.id))
        .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
        .where(ReviewLog.review_date >= since)
        .group_by(UserVocabularyProgress.user_id, day)
    )
    backlog = select(func.count(UserVocabularyProgress.id)).where(
        UserVocabularyProgress.reps > 0,
        or_(
            UserVocabularyProgress.due_at <= now,
            and_(UserVocabularyProgress.due_at.is_(None), UserVocabularyProgress.next_review_date <= now),
        ),
    )
    if user_ids:
        query = query.where(UserVocabularyProgress.user_id.in_(user_ids))
        backlog = backlog.where(UserVocabularyProgress.user_id.in_(user_ids))
    days = list(db.execute(query).all())
    reviews = sum(int(row[2]) for row in days)
    return {
        "learner_days": len(days),
        "reviews_per_learner_day": round(reviews / len(days), 2) if days else None,
        "backlog_now": int(db.execute(backlog).scalar_one() or 0),
    }


def retention_report(
    db: Session, *, days: int = 28, user_ids: list[Any] | None = None, now: datetime | None = None
) -> dict[str, Any]:
    """The whole read, as one JSON-able dict."""

    from app.config import settings

    now = now or datetime.now(UTC)
    since = now - timedelta(days=days)
    rows = _rows(db, since=since, user_ids=user_ids)
    return {
        "window_days": days,
        "target_retention": getattr(settings, "VOCAB_TARGET_RETENTION", 0.87),
        "delayed_reviews": len(rows),
        "calibration": calibration(rows),
        "forgetting_curve": forgetting_curve(rows).get("all", []),
        "by_format": forgetting_curve(rows, by="format"),
        "by_source": forgetting_curve(rows, by="source"),
        "pilot": {
            "enabled": bool(getattr(settings, "VOCAB_STORY_PILOT_ENABLED", False)),
            **pilot(rows),
        },
        "load": load(db, since=since, user_ids=user_ids, now=now),
    }
