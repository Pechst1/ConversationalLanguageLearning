"""Notification helpers for serial editions and the V2 daily journey."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.serial import SerialEpisode
from app.db.models.user import User

#: Title for the WP-19 morning push of the Atelier V2 daily journey.
DAILY_JOURNEY_MORNING_TITLE = "Votre scène du jour est prête"


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
        title = f"Épisode {int(episode.episode_index) + 1} disponible"
        message = teaser or "Votre nouvelle édition du Feuilleton est prête."
    else:
        title = f"Épisode {int(episode.episode_index) + 1} · à vous"
        message = teaser or "Romy attend votre réponse dans le prochain acte."

    hook["notification_queued_key"] = notification_key
    hook["notification_queued_at"] = datetime.now(UTC).isoformat()
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


def daily_journey_morning_copy(
    db: Session,
    user: User,
    *,
    today: date,
) -> tuple[str, str] | None:
    """Morning copy for the V2 daily journey, or ``None`` when it does not apply.

    Returns ``None`` for every learner outside the journey cohort, so the caller
    falls back to the legacy edition copy, and also for a learner who has
    already finished today's scene: a "your scene is ready" push after the fact
    would be a lie.
    """
    from app.services.daily_journey import journey_enabled_for
    from app.services.journey_contracts import TERMINAL_JOURNEY_STATUSES

    if not journey_enabled_for(user):
        return None

    terminal = {str(value) for value in TERMINAL_JOURNEY_STATUSES}
    finished = db.scalar(
        select(DailyJourney.id).where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date == today,
            DailyJourney.status.in_(terminal),
        )
    )
    if finished is not None:
        return None

    resumable = db.scalar(
        select(DailyJourney)
        .where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date == today,
            DailyJourney.status.in_(("preparing", "active", "paused")),
        )
        .order_by(DailyJourney.created_at.desc())
    )
    if resumable is not None:
        minutes = max(1, round(int(resumable.budget_seconds or 300) / 60))
        message = f"Reprenez où vous en étiez : environ {minutes} minutes."
    else:
        message = "Une scène courte vous attend dans l’Atelier."
    return DAILY_JOURNEY_MORNING_TITLE, message


__all__ = [
    "DAILY_JOURNEY_MORNING_TITLE",
    "daily_journey_morning_copy",
    "enqueue_serial_edition_notification",
]
