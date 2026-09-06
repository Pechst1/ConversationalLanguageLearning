"""Celery tasks for serial episode and Feuilleton generation."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.models.pilot_event import PilotEvent
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.session import SessionLocal
from app.services.graphic_novel import GraphicNovelScheduler
from app.services.serial import SerialThreadService

# A delayed episode is retried by the beat task, never by a learner-facing read path.
SERIAL_RETRY_EVENT = "serial_episode_retry"
SERIAL_GIVE_UP_EVENT = "episode_delayed"
SERIAL_RETRY_WINDOW = timedelta(days=1)
MAX_SERIAL_RETRIES_PER_WINDOW = 6


@celery_app.task(name="app.tasks.serial_generation.generate_scene_images")
def generate_scene_images(scene_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        scene = asyncio.run(GraphicNovelScheduler(db).render_scene_images(scene_id))
        return {"scene_id": str(scene.id), "status": scene.status}
    finally:
        db.close()


@celery_app.task(name="app.tasks.serial_generation.create_next_serial_beat")
def create_next_serial_beat(thread_id: str) -> dict[str, str | int]:
    db = SessionLocal()
    try:
        thread_uuid = UUID(str(thread_id))
        thread = db.get(SerialThread, thread_uuid)
        if not thread:
            raise ValueError(f"Serial thread {thread_id} not found")
        service = SerialThreadService(db)
        service.expire_stale_generations(thread)
        current = service.current_episode(thread)
        if current:
            return {"thread_id": str(thread.id), "episode_index": current.episode_index, "status": current.status}
        episode = asyncio.run(service.start_next_beat(thread))
        return {"thread_id": str(thread.id), "episode_index": episode.episode_index, "status": episode.status}
    except Exception as exc:
        logger.warning("Serial next beat task failed", thread_id=thread_id, error=str(exc))
        raise
    finally:
        db.close()


def _retry_attempts(db: Session, *, episode_id: UUID, since: datetime) -> int:
    return int(
        db.query(func.count(PilotEvent.id))
        .filter(
            PilotEvent.event_type == SERIAL_RETRY_EVENT,
            PilotEvent.entity_id == str(episode_id),
            PilotEvent.occurred_at >= since,
        )
        .scalar()
        or 0
    )


def _already_gave_up(db: Session, *, episode_id: UUID, since: datetime) -> bool:
    return bool(
        db.query(PilotEvent.id)
        .filter(
            PilotEvent.event_type == SERIAL_GIVE_UP_EVENT,
            PilotEvent.entity_id == str(episode_id),
            PilotEvent.occurred_at >= since,
        )
        .first()
    )


def retry_delayed_serial_episodes_sync(
    db: Session,
    *,
    limit: int = 100,
    now: datetime | None = None,
    thread_id: UUID | None = None,
) -> dict[str, int]:
    """Re-attempt generation for every current episode stuck in ``delayed``.

    Pass ``thread_id`` to sweep a single thread instead of the whole pilot.

    Guards:
    * only the thread's current episode of an active thread is retried;
    * the ``delayed`` -> ``generating`` claim is a conditional UPDATE, so a retry
      already in flight (or a second beat tick) cannot double-generate;
    * at most ``MAX_SERIAL_RETRIES_PER_WINDOW`` attempts per episode per rolling day,
      counted from the ``serial_episode_retry`` pilot events the task itself writes.
    """
    from app.services.pilot_events import PilotEventService

    moment = now or datetime.now(UTC)
    window_start = moment - SERIAL_RETRY_WINDOW
    service = SerialThreadService(db)
    scoped_thread = db.get(SerialThread, thread_id) if thread_id is not None else None
    if thread_id is not None and scoped_thread is None:
        return {"examined": 0, "retried": 0, "recovered": 0, "still_delayed": 0, "exhausted": 0, "skipped": 0}
    # Sweep stranded "generating" scenes first so this run also picks up what just went stale.
    service.expire_stale_generations(scoped_thread, now=moment)

    query = (
        db.query(SerialEpisode, SerialThread)
        .join(SerialThread, SerialThread.id == SerialEpisode.thread_id)
        .filter(
            SerialEpisode.status == "delayed",
            SerialEpisode.kind == "feuilleton",
            # A delayed episode has nothing readable attached; anything with a scene is
            # already recoverable by the stale-generation sweep and must not be claimed.
            SerialEpisode.scene_id.is_(None),
            SerialThread.status == "active",
            SerialEpisode.episode_index == SerialThread.current_episode_index,
        )
    )
    if scoped_thread is not None:
        query = query.filter(SerialEpisode.thread_id == scoped_thread.id)
    rows = query.order_by(SerialEpisode.created_at.asc()).limit(max(1, int(limit))).all()

    summary = {
        "examined": len(rows),
        "retried": 0,
        "recovered": 0,
        "still_delayed": 0,
        "exhausted": 0,
        "skipped": 0,
    }
    for episode, thread in rows:
        episode_id = episode.id
        attempts = _retry_attempts(db, episode_id=episode_id, since=window_start)
        if attempts >= MAX_SERIAL_RETRIES_PER_WINDOW:
            summary["exhausted"] += 1
            if not _already_gave_up(db, episode_id=episode_id, since=window_start):
                PilotEventService(db).record(
                    SERIAL_GIVE_UP_EVENT,
                    user_id=thread.user_id,
                    entity_type="serial_episode",
                    entity_id=str(episode_id),
                    payload={
                        "thread_id": str(thread.id),
                        "episode_index": episode.episode_index,
                        "attempts": attempts,
                        "reason": "retry_budget_exhausted",
                    },
                )
                db.commit()
                logger.warning(
                    "Serial delayed retry budget exhausted",
                    thread_id=str(thread.id),
                    episode_index=episode.episode_index,
                    attempts=attempts,
                )
            continue

        claimed = (
            db.query(SerialEpisode)
            .filter(SerialEpisode.id == episode_id, SerialEpisode.status == "delayed")
            .update({"status": "generating"}, synchronize_session=False)
        )
        db.commit()
        if not claimed:
            summary["skipped"] += 1
            continue

        PilotEventService(db).record(
            SERIAL_RETRY_EVENT,
            user_id=thread.user_id,
            entity_type="serial_episode",
            entity_id=str(episode_id),
            payload={
                "thread_id": str(thread.id),
                "episode_index": episode.episode_index,
                "attempt": attempts + 1,
            },
        )
        db.commit()
        summary["retried"] += 1

        try:
            refreshed = asyncio.run(service.start_feuilleton_beat(thread, retry_delayed=True))
        except Exception as exc:  # keep the episode retryable instead of stuck in "generating"
            db.rollback()
            db.query(SerialEpisode).filter(
                SerialEpisode.id == episode_id, SerialEpisode.status == "generating"
            ).update({"status": "delayed"}, synchronize_session=False)
            db.commit()
            summary["still_delayed"] += 1
            logger.warning(
                "Serial delayed retry failed",
                thread_id=str(thread.id),
                episode_index=episode.episode_index,
                error=str(exc),
            )
            continue

        if refreshed.status == "delayed":
            summary["still_delayed"] += 1
        else:
            summary["recovered"] += 1
    return summary


@celery_app.task(name="app.tasks.serial_generation.retry_delayed_serial_episodes")
def retry_delayed_serial_episodes(limit: int = 100) -> dict[str, int]:
    """Beat entry point: give every delayed episode a bounded second chance."""
    db = SessionLocal()
    try:
        summary = retry_delayed_serial_episodes_sync(db, limit=limit)
        logger.info("Serial delayed retry sweep complete", **summary)
        return summary
    finally:
        db.close()


__all__ = [
    "create_next_serial_beat",
    "generate_scene_images",
    "retry_delayed_serial_episodes",
    "retry_delayed_serial_episodes_sync",
]
