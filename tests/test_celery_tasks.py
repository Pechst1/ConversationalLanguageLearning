"""Tests for Celery background tasks."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.session import LearningSession
from app.db.models.user import User
from app.tasks.analytics import (
    cleanup_old_snapshots,
    generate_daily_snapshots,
    generate_user_snapshot,
)


@pytest.fixture()
def task_session_factory(db_session):
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_session.bind)
    sessions: list = []

    def create_session():
        session = factory()
        sessions.append(session)
        return session

    try:
        yield create_session
    finally:
        for session in sessions:
            session.close()


@pytest.fixture()
def active_user(db_session):
    user = User(
        email="celery-test@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        is_active=True,
        last_activity_date=date.today() - timedelta(days=1),
        current_streak=4,
    )
    db_session.add(user)
    db_session.commit()

    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=15,
        actual_duration_minutes=15,
        topic="Travel",
        conversation_style="tutor",
        accuracy_rate=0.85,
        xp_earned=120,
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=1, hours=1),
        completed_at=datetime.now(timezone.utc) - timedelta(days=1),
        new_words_introduced=3,
        words_practiced=6,
    )
    db_session.add(session)
    db_session.commit()
    try:
        yield user
    finally:
        db_session.query(LearningSession).delete()
        db_session.query(User).delete()
        db_session.query(AnalyticsSnapshot).delete()
        db_session.commit()


def test_generate_user_snapshot(db_session, task_session_factory, active_user):
    target_date = (date.today() - timedelta(days=1)).isoformat()

    with patch("app.tasks.analytics.SessionLocal", side_effect=task_session_factory):
        result = generate_user_snapshot.run(str(active_user.id), target_date)

    assert result["user_id"] == str(active_user.id)
    assert result["date"] == target_date
    assert "snapshot_id" in result

    snapshots = db_session.query(AnalyticsSnapshot).filter_by(user_id=active_user.id).all()
    assert len(snapshots) == 1
    assert snapshots[0].snapshot_date.isoformat() == target_date


def test_generate_daily_snapshots(db_session, task_session_factory, active_user):
    target_date = (date.today() - timedelta(days=1)).isoformat()

    with patch("app.tasks.analytics.SessionLocal", side_effect=task_session_factory):
        result = generate_daily_snapshots.run(target_date)

    assert result["success"] >= 1
    assert result["total"] >= 1
    assert result["date"] == target_date


def test_cleanup_old_snapshots(db_session, task_session_factory, active_user):
    old_date = date.today() - timedelta(days=400)
    snapshot = AnalyticsSnapshot(
        user_id=active_user.id,
        snapshot_date=old_date,
        total_words_seen=10,
    )
    db_session.add(snapshot)
    db_session.commit()

    with patch("app.tasks.analytics.SessionLocal", side_effect=task_session_factory):
        result = cleanup_old_snapshots.run(retention_days=365)

    assert result["deleted"] >= 1
    remaining = db_session.query(AnalyticsSnapshot).filter_by(user_id=active_user.id).all()
    assert all(item.snapshot_date >= date.today() - timedelta(days=365) for item in remaining)
