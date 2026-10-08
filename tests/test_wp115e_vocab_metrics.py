"""WP-115e — measuring retention honestly: prediction and lag on every review, the report,
and the optional story-vs-cahier pilot."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.services.progress import ProgressService
from app.services.story_words import pilot_arm, story_due_words
from app.services.vocab_metrics import retention_report
from tests.test_daily_words import _make_due_word, _make_user

NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


def test_a_review_logs_what_the_scheduler_predicted_and_the_lag(db_session):
    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "la serrure", rank=900)
    db_session.flush()
    service = ProgressService(db_session)
    service.record_review(user=user, word=word, rating=2, now=NOW - timedelta(days=10))
    _progress, log, _outcome = service.record_review(user=user, word=word, rating=2, now=NOW)
    assert log.elapsed_days_exact == pytest.approx(10.0)
    assert 0.0 < log.predicted_r < 1.0


def _logged(db_session, user, word, *, rating, predicted, elapsed, review_format="typed", source="drill"):
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()
    db_session.add(
        ReviewLog(
            progress_id=progress.id, rating=rating, review_date=NOW - timedelta(days=1),
            predicted_r=predicted, elapsed_days_exact=elapsed, format=review_format, source=source,
        )
    )


def test_the_report_reads_calibration_and_the_forgetting_curve(db_session):
    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "le palier", rank=901)
    db_session.flush()
    for rating in (2, 2, 2, 0):  # 3 of 4 recalled at a predicted 0.85, a week later
        _logged(db_session, user, word, rating=rating, predicted=0.85, elapsed=7.0)
    _logged(db_session, user, word, rating=2, predicted=0.99, elapsed=0.01, source="atelier")  # same day
    db_session.flush()
    report = retention_report(db_session, days=28, user_ids=[user.id], now=NOW)
    assert report["delayed_reviews"] == 4, "a same-day relearn is not a memory test"
    row = next(b for b in report["calibration"] if b["bin"] == "0.80–0.90")
    assert (row["reviews"], row["predicted"], row["actual"]) == (4, 0.85, 0.75)
    week = next(p for p in report["forgetting_curve"] if p["lag"] == "7d")
    assert (week["reviews"], week["recall"]) == (4, 0.75)
    assert "typed" in report["by_format"] and "drill" in report["by_source"]
    assert report["load"]["learner_days"] >= 1


def test_the_pilot_splits_each_learners_words_in_two_stable_halves():
    arms = [pilot_arm("learner", word_id) for word_id in range(400)]
    assert arms == [pilot_arm("learner", word_id) for word_id in range(400)], "stable"
    assert 160 < arms.count("story") < 240, "about half and half"


def test_with_the_pilot_on_only_the_story_half_rides_the_story(db_session, monkeypatch):
    user = _make_user(db_session)
    words = [_make_due_word(db_session, user, f"le mot{n}", rank=950 + n) for n in range(8)]
    db_session.flush()
    for word in words:
        db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one().lapses = 3
    db_session.flush()
    monkeypatch.setattr(settings, "VOCAB_STORY_PILOT_ENABLED", True)
    carried = story_due_words(db_session, user=user, limit=8)
    assert carried and all(pilot_arm(user.id, row["word_id"]) == "story" for row in carried)


def test_the_report_refuses_the_live_database():
    done = subprocess.run(  # noqa: S603 - this interpreter and a repo script, no shell
        [sys.executable, "scripts/vocab_retention_report.py", "--database-url", "postgresql://localhost/language_learning"],
        capture_output=True, text=True,
    )
    assert done.returncode != 0 and "Refusing" in done.stderr
