"""Notification helpers for serial edition availability."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.serial import SerialEpisode
from app.db.models.user import User


def _compact(value: Any, max_length: int = 140) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max(0, max_length - 1)].rstrip()}…"


def enqueue_serial_edition_notification(db: Session, episode: SerialEpisode, *, user: User | None = None) -> bool:
    """Queue exactly one push notification when a serial beat becomes available."""
    if episode.status != "available" or int(episode.episode_index or 0) <= 0:
        return False
    learner = user or (episode.thread.user if episode.thread else None)
    if not learner or not getattr(learner, "notifications_enabled", True):
        return False
    if not getattr(learner, "serial_edition_notifications", True):
        return False

    notification_key = (
        f"serial-edition:{episode.thread_id}:{episode.episode_index}:{episode.kind}:"
        f"{episode.scene_id or episode.mission_id or 'planned'}"
    )
    hook = dict(episode.hook or {})
    if hook.get("notification_queued_key") == notification_key:
        return False

    teaser = _compact(hook.get("teaser") or hook.get("text") or hook.get("unresolved_question"))
    if episode.kind == "feuilleton":
        title = f"Episode {int(episode.episode_index) + 1} is ready"
        message = teaser or "The next Feuilleton edition is ready to read."
    else:
        title = f"Episode {int(episode.episode_index) + 1} needs your reply"
        message = teaser or "The next serial act is ready."

    hook["notification_queued_key"] = notification_key
    hook["notification_queued_at"] = datetime.now(timezone.utc).isoformat()
    episode.hook = hook
    db.add(episode)
    db.commit()

    try:
        from app.tasks.notifications import send_serial_edition_notification

        send_serial_edition_notification.delay(
            str(learner.id),
            int(episode.episode_index),
            title,
            message,
            notification_key,
        )
    except Exception as exc:  # pragma: no cover - local broker-less fallback
        logger.info(
            "Serial edition notification queued for worker/lazy retry",
            user_id=str(learner.id),
            episode_id=str(episode.id),
            error=str(exc),
        )
    return True


__all__ = ["enqueue_serial_edition_notification"]
