"""A scene's drawing starts only once the scene is really committed (2026-09-30).

The journey binds a scene inside a SAVEPOINT (WP-69). SQLAlchemy fires ``after_commit``
for the savepoint release too, so the drawing used to be handed to its worker while the
outer transaction was still open: on PostgreSQL the worker could not see the scene, ended
as «missing» without a log line, and the panels sat ``rendering`` until the heal.

Fake image API only, never a paid call.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.config import settings
from uuid import UUID

from app.db.models.graphic_novel import GraphicNovelScene
from app.services import panel_art
from tests import test_wp87_lanes as harness
from tests.test_living_story import driver
from tests.test_panel_art import art  # noqa: F401  (fixture)

assembled_client = harness.assembled_client
journey_enabled = harness.journey_enabled
clock = harness.clock
provider = harness.provider


def test_the_drawing_is_dispatched_by_the_real_commit_not_a_savepoint_release(
    assembled_client, db_session, journey_enabled, clock, provider, art, monkeypatch  # noqa: F811
):
    seen: list[dict] = []

    def record(job):
        seen.append(
            {
                "nested": db_session.in_nested_transaction(),
                "scene_visible": db_session.get(GraphicNovelScene, UUID(job.scene_id)) is not None,
            }
        )

    monkeypatch.setattr(panel_art, "dispatcher", record)
    d = driver(assembled_client, db_session)
    d.create()
    assert len(seen) == 1, "one scene, one drawing job"
    assert seen[0]["nested"] is False, "dispatched from a savepoint release, before the commit"
    assert seen[0]["scene_visible"]


def test_a_rolled_back_savepoint_does_not_drop_the_queued_drawing(db_session, art):  # noqa: F811
    db_session.info.setdefault(panel_art.PENDING_KEY, []).append("job")
    with db_session.begin_nested() as nested:
        nested.rollback()
    assert db_session.info[panel_art.PENDING_KEY] == ["job"]
    db_session.rollback()
    assert panel_art.PENDING_KEY not in db_session.info, "a real rollback discards it"


def test_a_savepoint_release_keeps_the_job_until_the_real_commit(db_session, art):  # noqa: F811
    db_session.info.setdefault(panel_art.PENDING_KEY, []).append("job")
    with db_session.begin_nested():
        pass
    assert art.queued == []
    db_session.commit()
    assert art.queued == ["job"]


def test_the_timeout_is_a_setting(monkeypatch):
    assert settings.ATELIER_PANEL_ART_RENDER_TIMEOUT_SECONDS == 240.0
    now = 10_000.0
    panel = SimpleNamespace(generation_metadata={"image_status": "rendering", "rendering_since": now - 200})

    class Db:
        def commit(self):
            pass

    scene = SimpleNamespace(panels=[panel])
    assert panel_art.heal_stale_rendering(Db(), [scene], now=now) == 0
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_RENDER_TIMEOUT_SECONDS", 120.0)
    assert panel_art.heal_stale_rendering(Db(), [scene], now=now) == 1


def test_a_drawing_that_lands_after_the_heal_is_shown(db_session, art, monkeypatch):  # noqa: F811
    healed = {"image_status": "failed", "image_error": "timeout", "image_source": "setting_reference"}
    calls = {}

    class Panel:
        panel_index = 0
        image_url = "/plate.webp"
        image_payload = None
        generation_metadata = healed

    class Scene:
        panels = [Panel()]
        user_id = None
        id = "s"

    class Db:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, model, key):
            return Scene()

        def commit(self):
            calls["commit"] = True

    monkeypatch.setattr(panel_art, "_record_cost", lambda *a, **k: None)
    job = SimpleNamespace(scene_id="00000000-0000-0000-0000-000000000000", panel_index=0, prompt="p")
    panel_art._write_back(lambda: Db(), job, {"url": "/art.webp"}, None)
    meta = Scene.panels[0].generation_metadata
    assert meta["image_status"] == "ready" and "image_error" not in meta
    assert Scene.panels[0].image_url == "/art.webp"
