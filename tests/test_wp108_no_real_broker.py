"""WP-108: the suite never reaches the real Celery broker (1,499 stale jobs, 2026-09-29)."""

from __future__ import annotations

import pytest

from app.celery_app import broker_is_memory, celery_app


def test_the_suite_runs_on_the_in_memory_broker():
    assert broker_is_memory(), celery_app.conf.broker_url
    assert not str(celery_app.conf.result_backend).startswith("redis"), celery_app.conf.result_backend


def test_a_task_sent_to_a_real_broker_fails_the_test(monkeypatch):
    from app.tasks.health import worker_heartbeat

    # Celery reads CELERY_BROKER_URL from the environment on every access.
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    with pytest.raises(AssertionError, match="real broker"):
        worker_heartbeat.apply_async()


def test_a_task_sent_to_the_memory_broker_is_allowed():
    from app.tasks.health import worker_heartbeat

    result = worker_heartbeat.apply_async()
    assert result.id
