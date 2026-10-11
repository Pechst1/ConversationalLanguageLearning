"""WP-108 «Le Feuilleton répare»: a page is never «sous presse» forever.

Fake image API only, never a paid call, never a real broker. Pinned here:

* a drawing is sent to Celery only when a worker is alive (the ``/health/worker``
  heartbeat); with none it is drawn in this process;
* a panel still ``rendering`` after three minutes is served as its plate, marked
  ``failed`` with reason ``timeout``, when the episode is read; rows written before the
  timestamp existed heal too.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from uuid import UUID

import pytest

from app import celery_app as celery_module
from app.db.models.graphic_novel import GraphicNovelPanel
from app.services import panel_art
from tests import test_wp87_lanes as harness
from tests.test_living_story import driver
from tests.test_panel_art import _episode, art  # noqa: F401  (fixture)

assembled_client = harness.assembled_client
journey_enabled = harness.journey_enabled
clock = harness.clock
provider = harness.provider


@pytest.fixture(autouse=True)
def _fresh_worker_cache(monkeypatch):
    monkeypatch.setattr(panel_art, "_WORKER_CHECK", None)


def _job() -> panel_art.PrefetchArtJob:
    return panel_art.PrefetchArtJob("prefetch-1", bind=None)


# ---------------------------------------------------------------------------
# Worker presence
# ---------------------------------------------------------------------------


def test_no_worker_in_the_test_broker_or_eager_mode(monkeypatch):
    assert panel_art.worker_available() is False  # the suite runs on memory://
    monkeypatch.setattr(celery_module, "broker_is_memory", lambda: False)
    monkeypatch.setattr(celery_module, "is_eager", lambda: True)
    assert panel_art.worker_available() is False


def test_worker_available_follows_the_heartbeat_and_is_cached(monkeypatch):
    monkeypatch.setattr(celery_module, "broker_is_memory", lambda: False)
    monkeypatch.setattr(celery_module, "is_eager", lambda: False)
    calls: list[str] = []
    status = {"value": "ok"}

    def health():
        calls.append(status["value"])
        return {"status": status["value"]}

    monkeypatch.setattr("app.core.observability.worker_health", health)
    assert panel_art.worker_available(now=100.0) is True
    status["value"] = "missing"
    assert panel_art.worker_available(now=110.0) is True, "cached for 30 s"
    assert panel_art.worker_available(now=131.0) is False
    assert calls == ["ok", "missing"]
    status["value"] = "stale"
    assert panel_art.worker_available(now=170.0) is False


def test_an_unreachable_redis_means_no_worker(monkeypatch):
    monkeypatch.setattr(celery_module, "broker_is_memory", lambda: False)
    monkeypatch.setattr(celery_module, "is_eager", lambda: False)

    def boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.observability.worker_health", boom)
    assert panel_art.worker_available() is False


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_prefetch_art_without_a_worker_is_drawn_in_process(monkeypatch):
    sent: list = []
    submitted: list = []
    monkeypatch.setattr("app.tasks.journey_prefetch.draw_prefetched_panel_art.apply_async", lambda **kw: sent.append(kw))
    monkeypatch.setattr(panel_art, "worker_available", lambda: False)
    monkeypatch.setattr(panel_art, "_executor", lambda: SimpleNamespace(submit=lambda fn, job: submitted.append((fn, job))))
    job = _job()
    panel_art._dispatch_prefetch(job)
    assert sent == [], "nothing is queued for a worker that is not there"
    assert submitted == [(panel_art.render_prefetch_art, job)]


def test_prefetch_art_with_a_live_worker_goes_to_celery(monkeypatch):
    sent: list = []
    submitted: list = []
    monkeypatch.setattr("app.tasks.journey_prefetch.draw_prefetched_panel_art.apply_async", lambda **kw: sent.append(kw))
    monkeypatch.setattr(panel_art, "worker_available", lambda: True)
    monkeypatch.setattr(panel_art, "_executor", lambda: SimpleNamespace(submit=lambda fn, job: submitted.append(job)))
    panel_art._dispatch_prefetch(_job())
    assert sent == [{"args": ["prefetch-1"]}]
    assert submitted == []


def test_a_broker_failure_still_draws_in_process(monkeypatch):
    submitted: list = []

    def refuse(**kw):
        raise ConnectionError("broker gone")

    monkeypatch.setattr("app.tasks.journey_prefetch.draw_prefetched_panel_art.apply_async", refuse)
    monkeypatch.setattr(panel_art, "worker_available", lambda: True)
    monkeypatch.setattr(panel_art, "_executor", lambda: SimpleNamespace(submit=lambda fn, job: submitted.append(job)))
    panel_art._dispatch_prefetch(_job())
    assert len(submitted) == 1


# ---------------------------------------------------------------------------
# The timeout, healed on read
# ---------------------------------------------------------------------------


def _panel(meta, created_at=None):
    return SimpleNamespace(generation_metadata=meta, created_at=created_at)


class _Db:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_heal_only_releases_panels_past_the_timeout():
    now = 10_000.0
    old = _panel({"image_status": "rendering", "rendering_since": now - 241})
    fresh = _panel({"image_status": "rendering", "rendering_since": now - 60})
    waiting = _panel({"image_status": "rendering", "rendering_since": now - 500, "awaiting_prefetch": "p"})
    ready = _panel({"image_status": "ready", "rendering_since": now - 900})
    db = _Db()
    healed = panel_art.heal_stale_rendering(db, [SimpleNamespace(panels=[old, fresh, waiting, ready])], now=now)
    assert healed == 2 and db.commits == 1
    assert old.generation_metadata["image_status"] == "failed"
    assert old.generation_metadata["image_error"] == "timeout"
    assert "rendering_since" not in old.generation_metadata
    assert waiting.generation_metadata["image_status"] == "failed"
    assert "awaiting_prefetch" not in waiting.generation_metadata
    assert fresh.generation_metadata["image_status"] == "rendering"
    assert ready.generation_metadata["image_status"] == "ready"
    assert panel_art.heal_stale_rendering(db, [SimpleNamespace(panels=[fresh])], now=now) == 0
    assert db.commits == 1, "nothing to heal, nothing written"


def test_a_row_from_before_the_timestamp_counts_from_its_creation():
    from datetime import UTC, datetime

    now = time.time()
    # SQLite hands created_at back as naive UTC.
    stuck = _panel({"image_status": "rendering"}, created_at=datetime.fromtimestamp(now - 3 * 3600, tz=UTC).replace(tzinfo=None))
    recent = _panel({"image_status": "rendering"}, created_at=datetime.fromtimestamp(now - 30, tz=UTC).replace(tzinfo=None))
    assert panel_art.heal_stale_rendering(_Db(), [SimpleNamespace(panels=[stuck, recent])], now=now) == 1
    assert stuck.generation_metadata["image_status"] == "failed"
    assert recent.generation_metadata["image_status"] == "rendering"


def test_requesting_art_stamps_when_the_panel_went_rendering(db_session, monkeypatch, art):  # noqa: F811
    before = time.time()
    scene = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000000",
        panels=[SimpleNamespace(panel_index=0, generation_metadata={})],
    )
    assert panel_art.request_scene_art(db_session, scene)
    meta = scene.panels[0].generation_metadata
    assert meta["image_status"] == "rendering" and meta["rendering_since"] >= before
    db_session.rollback()


def test_the_episode_read_serves_a_stale_rendering_panel_as_its_plate(
    assembled_client, db_session, journey_enabled, clock, provider, art  # noqa: F811
):
    d = driver(assembled_client, db_session)
    d.create()
    first = _episode(assembled_client, d)
    assert {p["image_status"] for p in first["panels"]} == {"rendering"}

    rows = (
        db_session.query(GraphicNovelPanel)
        .filter(GraphicNovelPanel.scene_id == UUID(first["id"]))
        .order_by(GraphicNovelPanel.panel_index)
        .all()
    )
    assert len(rows) == len(first["panels"])
    stale = time.time() - 5 * 60
    for row in rows[:-1]:
        row.generation_metadata = {**row.generation_metadata, "rendering_since": stale}
    db_session.commit()

    for read in (
        lambda: _episode(assembled_client, d),
        lambda: assembled_client.get(f"/api/v1/story-engine/episodes/{first['id']}", headers=d.headers).json(),
    ):
        episode = read()
        statuses = [p["image_status"] for p in episode["panels"]]
        assert statuses[:-1] == ["setting_reference"] * (len(statuses) - 1), "the plate, not «sous presse»"
        assert statuses[-1] == "rendering", "a panel inside its timeout keeps drawing"
        assert all(p["image_url"] for p in episode["panels"])

    db_session.expire_all()
    healed = rows[0]
    assert healed.generation_metadata["image_status"] == "failed"
    assert healed.generation_metadata["image_error"] == "timeout"


def test_eager_dev_does_not_queue_the_next_day_warmup(monkeypatch):
    """An eager task ignores its ETA and would run a paid generation inside the request."""

    from app.celery_app import celery_app
    from app.tasks import journey_prefetch

    monkeypatch.setattr(journey_prefetch, "prefetch_enabled_for", lambda user: True)
    monkeypatch.setitem(celery_app.conf, "task_always_eager", True)
    ran: list = []
    monkeypatch.setattr(journey_prefetch.warm_learner_next_day, "apply_async", lambda **kw: ran.append(kw))
    user = SimpleNamespace(id="u1")
    assert journey_prefetch.schedule_next_day_warmup(user, timezone_name="Europe/Paris") is None
    assert ran == []
