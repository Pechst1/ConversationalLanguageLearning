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
        "app.tasks.anki_sync",
        "app.tasks.serial_generation",
        "app.tasks.atelier",
        "app.tasks.book_library",
        "app.tasks.journey_prefetch",
        "app.tasks.health",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Berlin",  # Changed to Berlin timezone for 4 AM local time
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
    "send-morning-editions": {
        "task": "app.tasks.notifications.send_morning_editions",
        "schedule": crontab(minute="*/15"),
    },
    # WP-80: every 15 minutes, because "19:00" and "18:00" are each learner's
    # own local time; the task picks the learners whose evening it is.
    "send-streak-reminders": {
        "task": "app.tasks.notifications.send_streak_reminders",
        "schedule": crontab(minute="*/15"),
    },
    "send-review-reminders": {
        "task": "app.tasks.notifications.send_daily_srs_reminders",
        "schedule": crontab(minute="*/15"),
    },
    "sync-anki-cards-daily": {
        "task": "app.tasks.anki_sync.sync_anki_cards_for_all_users",
        "schedule": crontab(hour=4, minute=0),  # 4 AM daily
    },
    "audit-atelier-word-banks-weekly": {
        "task": "app.tasks.atelier.audit_atelier_word_banks",
        "schedule": crontab(hour=4, minute=30, day_of_week=1),
    },
    "retry-delayed-serial-episodes": {
        "task": "app.tasks.serial_generation.retry_delayed_serial_episodes",
        "schedule": crontab(minute="*/15"),
    },
    # WP-26: the draft the learner waits on is generated before they arrive.
    # Overnight in Europe/Berlin, plus a mid-afternoon top-up for a learner whose
    # story moved during the day and whose cached scene is therefore stale.
    "prefetch-next-journey-scenes": {
        "task": "app.tasks.journey_prefetch.prefetch_next_journey_scenes",
        "schedule": crontab(hour="3,15", minute=20),
    },
    "retire-unhealthy-atelier-exercises": {
        "task": "app.tasks.atelier.retire_unhealthy_exercise_sets",
        "schedule": crontab(hour=4, minute=45),
    },
    # WP-73: liveness — a fresh Redis heartbeat proves beat, broker and a worker.
    "worker-heartbeat": {
        "task": "app.tasks.health.worker_heartbeat",
        "schedule": 60.0,
    },
}


# --- WP-73 observability (begin) -------------------------------------------
# Celery's own logging setup is skipped (connecting ``setup_logging`` does that)
# so the worker writes the same JSON lines as the API, and Sentry starts in each
# worker process only when SENTRY_DSN is set. The request id of the API call
# that enqueued a task travels in the message headers and is bound while it runs.
from celery import signals  # noqa: E402

from app.core import observability  # noqa: E402


@signals.setup_logging.connect
def _wp73_setup_logging(**_: object) -> None:
    observability.configure_logging()


@signals.worker_process_init.connect
@signals.beat_init.connect
@signals.celeryd_init.connect
def _wp73_init_sentry(**_: object) -> None:
    if not observability.sentry_enabled():
        observability.init_sentry("worker")


@signals.worker_ready.connect
def _wp73_first_heartbeat(**_: object) -> None:
    try:
        observability.write_heartbeat()
    except Exception as exc:  # noqa: BLE001 — never block worker start on Redis
        observability.logger.warning("Worker heartbeat write failed", error=type(exc).__name__)


@signals.before_task_publish.connect
def _wp73_propagate_request_id(headers: dict | None = None, **_: object) -> None:
    request_id = observability.current_request_id()
    if request_id and headers is not None:
        headers.setdefault("request_id", request_id)


_wp73_tokens: dict[str, object] = {}


@signals.task_prerun.connect
def _wp73_bind_request_id(task_id: str | None = None, task: object = None, **_: object) -> None:
    request = getattr(task, "request", None)
    incoming = getattr(request, "request_id", None) or (getattr(request, "headers", None) or {}).get("request_id")
    request_id = observability.accept_request_id(incoming or task_id)
    if task_id:
        _wp73_tokens[task_id] = observability.request_id_var.set(request_id)
    observability._sentry_tag("request_id", request_id)
    if task is not None:
        observability._sentry_tag("celery_task", getattr(task, "name", "") or "")


@signals.task_postrun.connect
def _wp73_unbind_request_id(task_id: str | None = None, **_: object) -> None:
    token = _wp73_tokens.pop(task_id or "", None)
    if token is not None:
        try:
            observability.request_id_var.reset(token)  # type: ignore[arg-type]
        except ValueError:
            observability.request_id_var.set(None)
# --- WP-73 observability (end) ---------------------------------------------

__all__ = ["celery_app"]
