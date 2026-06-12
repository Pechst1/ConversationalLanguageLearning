"""Celery tasks for serial episode and Feuilleton generation."""
from __future__ import annotations

import asyncio
from uuid import UUID

from loguru import logger

from app.celery_app import celery_app
from app.db.models.serial import SerialThread
from app.db.session import SessionLocal
from app.services.graphic_novel import GraphicNovelScheduler
from app.services.serial import SerialThreadService


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
        existing = (
            db.query(SerialThread)
            .filter(SerialThread.id == thread.id)
            .first()
        )
        if not existing:
            raise ValueError(f"Serial thread {thread_id} not found")
        service = SerialThreadService(db)
        current = service._current_episode(existing)
        if current:
            return {"thread_id": str(existing.id), "episode_index": current.episode_index, "status": current.status}
        episode = asyncio.run(service._start_next_beat(existing))
        return {"thread_id": str(existing.id), "episode_index": episode.episode_index, "status": episode.status}
    except Exception as exc:
        logger.warning("Serial next beat task failed", thread_id=thread_id, error=str(exc))
        raise
    finally:
        db.close()


__all__ = ["create_next_serial_beat", "generate_scene_images"]
