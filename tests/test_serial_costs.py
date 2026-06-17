"""Cost rollup tests for Serial Feuilleton generation."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services.serial_costs import SerialGenerationCostService, format_rollup_table, serial_generation_cost_event


def _user(db_session, *, email: str) -> User:
    user = User(
        id=uuid4(),
        email=email,
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _thread(db_session, user: User) -> SerialThread:
    thread = SerialThread(
        user_id=user.id,
        status="active",
        world_bible={"world_bible_version": "test"},
        state={},
        news_seed={},
        current_episode_index=0,
    )
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)
    return thread


def _scene(
    db_session,
    *,
    user: User,
    thread: SerialThread,
    episode_index: int,
    created_at: datetime,
    cost: dict,
) -> GraphicNovelScene:
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=episode_index,
        status="available",
        cadence="serial",
        title=f"Episode {episode_index}",
        brief="Generated serial episode.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "panel_count": cost.get("panel_count", 6),
            "estimated_cost": cost,
        },
        recap_payload={},
        cache_key=f"serial-cost-{episode_index}-{uuid4().hex}",
        prompt_version="test",
        image_model="test-image",
        image_quality=cost.get("image_quality", "medium"),
        created_at=created_at,
    )
    db_session.add(scene)
    db_session.commit()
    db_session.refresh(scene)
    return scene


def test_serial_generation_cost_event_reads_persisted_estimate(db_session):
    user = _user(db_session, email="serial-cost-event@example.com")
    thread = _thread(db_session, user)
    scene = _scene(
        db_session,
        user=user,
        thread=thread,
        episode_index=3,
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        cost={
            "currency": "USD",
            "panel_count": 6,
            "image_units": 6,
            "image_quality": "high",
            "render_mode": "panels",
            "story_generation_usd": 0.012345,
            "image_generation_usd": 0.5088,
            "total_estimated_usd": 0.521145,
        },
    )

    event = serial_generation_cost_event(scene)

    assert event["user_id"] == str(user.id)
    assert event["serial_thread_id"] == str(thread.id)
    assert event["episode_index"] == 3
    assert event["story_usd"] == 0.012345
    assert event["image_usd"] == 0.5088
    assert event["total_usd"] == 0.521145
    assert event["image_count"] == 6
    assert event["image_quality"] == "high"


def test_weekly_rollup_groups_serial_generation_costs_by_learner(db_session):
    first_user = _user(db_session, email="serial-cost-first@example.com")
    second_user = _user(db_session, email="serial-cost-second@example.com")
    first_thread = _thread(db_session, first_user)
    second_thread = _thread(db_session, second_user)
    week_start = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
    _scene(
        db_session,
        user=first_user,
        thread=first_thread,
        episode_index=2,
        created_at=week_start,
        cost={
            "panel_count": 6,
            "image_units": 6,
            "image_quality": "medium",
            "story_generation_usd": 0.01,
            "image_generation_usd": 0.318,
            "total_estimated_usd": 0.328,
        },
    )
    _scene(
        db_session,
        user=first_user,
        thread=first_thread,
        episode_index=4,
        created_at=datetime(2026, 1, 7, 9, 0, tzinfo=timezone.utc),
        cost={
            "panel_count": 6,
            "image_units": 1,
            "image_quality": "low",
            "story_generation_usd": 0.02,
            "image_generation_usd": 0.029,
            "total_estimated_usd": 0.049,
        },
    )
    _scene(
        db_session,
        user=second_user,
        thread=second_thread,
        episode_index=1,
        created_at=datetime(2026, 1, 8, 9, 0, tzinfo=timezone.utc),
        cost={
            "panel_count": 4,
            "image_units": 4,
            "image_quality": "medium",
            "story_generation_usd": 0.005,
            "image_generation_usd": 0.212,
            "total_estimated_usd": 0.217,
        },
    )

    rows = SerialGenerationCostService(db_session).weekly_rollup(
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 12),
    )

    assert len(rows) == 2
    first = next(row for row in rows if row["user_email"] == first_user.email)
    assert first["week_start"] == "2026-01-05"
    assert first["scene_count"] == 2
    assert first["episode_count"] == 2
    assert first["episodes"] == [2, 4]
    assert first["story_usd"] == 0.03
    assert first["image_usd"] == 0.347
    assert first["total_usd"] == 0.377
    assert first["image_count"] == 7
    assert first["image_quality_breakdown"] == {"low": 1, "medium": 1}
    table = format_rollup_table(rows)
    assert "serial-cost-first@example.com" in table
    assert "total_usd" in table
