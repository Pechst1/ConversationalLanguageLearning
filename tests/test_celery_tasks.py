"""Tests for Celery background tasks."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.session import LearningSession
from app.db.models.user import User
from app.tasks.analytics import (
    cleanup_old_snapshots,
    generate_daily_snapshots,
    generate_user_snapshot,
)
from app.tasks.serial_generation import generate_scene_images


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


def test_generate_scene_images_task_renders_queued_panels(db_session, task_session_factory, active_user, monkeypatch):
    monkeypatch.setattr(settings, "FEUILLETON_AUDIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)

    class FakeTTS:
        def text_to_speech(self, **kwargs):  # type: ignore[no-untyped-def]
            assert "Ça arrive" in kwargs["text"]
            return b"fake-mp3"

    monkeypatch.setattr("app.services.graphic_novel._safe_llm", lambda: FakeTTS())
    notification_calls: list[tuple] = []
    monkeypatch.setattr(
        "app.tasks.notifications.send_serial_edition_notification.delay",
        lambda *args: notification_calls.append(args),
    )
    thread = SerialThread(
        user_id=active_user.id,
        status="active",
        world_bible={},
        state={},
        news_seed={},
        current_episode_index=1,
    )
    db_session.add(thread)
    db_session.flush()
    scene = GraphicNovelScene(
        user_id=active_user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="generating",
        cadence="ad_hoc",
        title="Queued art",
        brief="A task test for async art.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "render_mode": "panels",
            "panels": [
                {
                    "panel_index": 1,
                    "title": "Queued",
                    "beat": "A queued panel waits for ink.",
                    "image_prompt": "Draw one square quiet cafe panel.",
                    "overlay_payload": {"caption": {"fr": "Ça arrive.", "en": "It is coming."}, "tasks": []},
                }
            ],
        },
        recap_payload={},
        cache_key=f"celery-scene-{uuid4().hex}",
        prompt_version="test",
        image_model="test-image-model",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=1,
            kind="feuilleton",
            scene_id=scene.id,
            hook={"teaser": "Demain : la suite arrive."},
            hook_from_previous={},
            state_delta={},
            brief_payload={},
            status="generating",
        )
    )
    db_session.add(
        GraphicNovelPanel(
            scene_id=scene.id,
            panel_index=1,
            title="Queued",
            beat="A queued panel waits for ink.",
            image_prompt="Draw one square quiet cafe panel.",
            image_url=None,
            image_payload={"status": "queued", "url": None},
            overlay_payload={"caption": {"fr": "Ça arrive.", "en": "It is coming."}, "tasks": []},
            generation_metadata={"image_status": "queued"},
        )
    )
    db_session.commit()

    image_mock = AsyncMock(
        return_value={
            "url": "/assets/generated/panel-1.png",
            "prompt": "Draw one square quiet cafe panel.",
            "model": "test-image-model",
            "quality": "medium",
            "fallback_used": False,
            "render_mode": "panels",
        }
    )
    with patch("app.tasks.serial_generation.SessionLocal", side_effect=task_session_factory), patch(
        "app.services.graphic_novel.GraphicNovelImageService.generate_panel_image",
        image_mock,
    ):
        result = generate_scene_images.run(str(scene.id))

    assert result == {"scene_id": str(scene.id), "status": "available"}
    db_session.expire_all()
    rendered = db_session.get(GraphicNovelScene, scene.id)
    panel = rendered.panels[0]
    assert rendered.status == "available"
    assert panel.image_url == "/assets/generated/panel-1.png"
    assert panel.audio_payload["status"] == "available"
    assert panel.audio_payload["url"].startswith("data:audio/mpeg;base64,")
    assert notification_calls and notification_calls[0][2] == "Episode 2 is ready"
    assert panel.generation_metadata["image_status"] == "available"
    assert image_mock.await_count == 1
