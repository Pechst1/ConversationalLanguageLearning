"""WP-115a — FSRS-4.5 for vocabulary: the properties that matter to a learner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.srs import SchedulerState
from app.services.vocab_fsrs import FACTOR, VocabularyFSRS, retrievability

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _state(stability: float, difficulty: float = 5.0, reps: int = 3) -> SchedulerState:
    return SchedulerState(stability=stability, difficulty=difficulty, reps=reps, lapses=0, scheduled_days=0, state="reviewing")


def test_the_forgetting_curve_is_the_one_the_coverage_code_reads():
    assert FACTOR == pytest.approx(19 / 81)
    assert retrievability(10.0, 10.0) == pytest.approx(0.9)
    assert retrievability(10.0, 0.0) == pytest.approx(1.0)


def test_a_review_minutes_after_another_barely_moves_the_word():
    """The old scheduler grew stability ×1.3 on every pass; reviewing a word twice in a
    day advanced it twice. FSRS grows it by what was forgotten."""

    fsrs = VocabularyFSRS(retention=0.87)
    early = fsrs.review(state=_state(10.0), rating=2, last_review_at=NOW - timedelta(minutes=5), now=NOW)
    on_time = fsrs.review(state=_state(10.0), rating=2, last_review_at=NOW - timedelta(days=12), now=NOW)
    assert early.stability < 10.5
    assert on_time.stability > 25


def test_a_lapse_relearns_in_ten_minutes_with_lower_stability():
    outcome = VocabularyFSRS().review(state=_state(20.0), rating=0, last_review_at=NOW - timedelta(days=25), now=NOW)
    assert outcome.state == "relearning"
    assert outcome.next_review - NOW == timedelta(minutes=10)
    assert outcome.stability < 20.0
    assert outcome.difficulty > 5.0


def test_recognition_counts_less_than_recall():
    fsrs = VocabularyFSRS()
    hard = fsrs.review(state=_state(8.0), rating=1, last_review_at=NOW - timedelta(days=9), now=NOW)
    good = fsrs.review(state=_state(8.0), rating=2, last_review_at=NOW - timedelta(days=9), now=NOW)
    assert hard.stability < good.stability
    assert hard.next_review < good.next_review


def test_a_new_word_starts_from_the_published_initial_stability():
    fsrs = VocabularyFSRS(retention=0.87)
    new = SchedulerState(stability=0.0, difficulty=5.0, reps=0, lapses=0, scheduled_days=0, state="new")
    good = fsrs.review(state=new, rating=2, last_review_at=None, now=NOW)
    again = fsrs.review(state=new, rating=0, last_review_at=None, now=NOW)
    assert good.stability == pytest.approx(3.7145)
    assert good.scheduled_days == 5
    assert again.state == "learning" and again.next_review - NOW == timedelta(minutes=10)


def test_a_higher_target_retention_means_shorter_intervals():
    assert VocabularyFSRS(retention=0.95).interval_days(30.0) < VocabularyFSRS(retention=0.87).interval_days(30.0)
    assert VocabularyFSRS(retention=0.9).interval_days(30.0) == 30
