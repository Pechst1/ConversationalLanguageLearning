"""Celery application instance and configuration."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings


def _resolve_broker_url() -> str:
    if settings.CELERY_BROKER_URL is not None:
        return str(settings.CELERY_BROKER_URL)
    return str(settings.REDIS_URL)


def _resolve_result_backend() -> str:
    if settings.CELERY_RESULT_BACKEND is not None:
        return str(settings.CELERY_RESULT_BACKEND)
    return str(settings.REDIS_URL)


celery_app = Celery(
    "conversational_language_learning",
    broker=_resolve_broker_url(),
    backend=_resolve_result_backend(),
    include=[
        "app.tasks.analytics",
        "app.tasks.notifications",
        "app.tasks.achievements",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

celery_app.conf.beat_schedule = {
    "generate-daily-analytics": {
        "task": "app.tasks.analytics.generate_daily_snapshots",
        "schedule": crontab(hour=2, minute=0),
    },
    "cleanup-old-snapshots": {
        "task": "app.tasks.analytics.cleanup_old_snapshots",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
    "send-streak-reminders": {
        "task": "app.tasks.notifications.send_streak_reminders",
        "schedule": crontab(hour=18, minute=0),
    },
}

__all__ = ["celery_app"]
