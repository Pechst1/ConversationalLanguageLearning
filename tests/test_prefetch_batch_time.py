"""The nightly prefetch fits Celery's soft limit (Codex review on #186, 2026-10-16).

A page written ahead of time may take up to 330 s, and the batch runs learners one by
one: a page that could not finish before the soft limit is not started.
"""

from __future__ import annotations

from app.celery_app import celery_app
from app.config import settings
from app.services import living_story
from app.tasks import journey_prefetch


def test_the_batch_leaves_room_for_the_longest_page_before_the_soft_limit():
    assert journey_prefetch._PAGE_AT_MOST_SECONDS == living_story.AHEAD_OPERATION_BUDGET_SECONDS
    assert journey_prefetch._BATCH_SECONDS < celery_app.conf.task_soft_time_limit


def test_a_page_that_cannot_finish_in_time_is_not_started(monkeypatch):
    clock = iter([0, 0, 600, 1200])  # started, then before learners 1, 2 and 3
    monkeypatch.setattr(journey_prefetch, "monotonic", lambda: next(clock))
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_MAX_LEARNERS", 25)

    class Db:
        def get(self, model, user_id):
            return user_id

        def rollback(self):
            pass

        def close(self):
            pass

    started: list[str] = []
    monkeypatch.setattr(journey_prefetch, "SessionLocal", Db)
    monkeypatch.setattr(journey_prefetch, "sweep_expired_prefetches", lambda db: 0)
    monkeypatch.setattr(journey_prefetch, "_active_learner_ids", lambda db, **kw: ["a", "b", "c"])
    monkeypatch.setattr(journey_prefetch, "prefetch_enabled_for", lambda user: True)
    monkeypatch.setattr(
        journey_prefetch, "prefetch_scene_for", lambda db, user, **kw: started.append(user) or "prefetched"
    )

    result = journey_prefetch.prefetch_next_journey_scenes()
    # 1,200 s in, a 330 s page would end past the 1,440 s batch: learner c waits.
    assert started == ["a", "b"]
    assert result["stopped_at_time"] == 1


def test_a_truncated_page_written_ahead_of_time_retries_with_more_room():
    class Truncated(Exception):
        details = {"truncated": True}

    assert living_story._next_budget(Truncated(), None) == living_story.TRUNCATED_RETRY_TOKENS
    with living_story.written_ahead_of_time():
        assert living_story._next_budget(Truncated(), None) > living_story.AHEAD_DRAFT_MAX_TOKENS
