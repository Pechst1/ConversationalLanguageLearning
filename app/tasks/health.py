"""WP-73 — worker liveness.

Beat enqueues :func:`worker_heartbeat` every minute and a worker runs it, so a
fresh ``wp73:worker:heartbeat`` in Redis proves beat, broker *and* a worker are
all alive. ``GET /health/worker`` reports its age; ``/ready`` deliberately does not.
"""
from __future__ import annotations

from app.celery_app import celery_app
from app.core.observability import write_heartbeat


@celery_app.task(name="app.tasks.health.worker_heartbeat", ignore_result=True, expires=120)
def worker_heartbeat() -> float:
    return write_heartbeat()
