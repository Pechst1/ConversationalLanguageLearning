"""Per-panel illustrations for story-engine scenes (app/services/panel_art.py).

Fake image API only, never a paid call. What these tests pin:

* a published scene opens on its location plate, every panel marked ``rendering``,
  and the drawing is queued only for after the commit;
* each drawn panel replaces its plate (``panel_art``); a failed one keeps it;
* the prompt carries the style, the place, who is in frame and the panel's own
  direction, and only approved cast portraits are sent as references;
* with the flag off nothing is queued and the panels are plain plates.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import settings
from app.services import panel_art
from tests import test_wp87_lanes as harness
from tests.test_living_story import driver

assembled_client = harness.assembled_client
journey_enabled = harness.journey_enabled
clock = harness.clock
provider = harness.provider


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (48, 32), "#1d3a8a").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def art(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_ENABLED", True)
    # WP-116 phase 6: drawn is the default and draws the cast in the client; per-panel
    # drawing is the painted set's pipeline, so these tests pin painted.
    monkeypatch.setattr(settings, "ATELIER_ART_SET", "painted")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", "local")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", str(tmp_path))
    # The test harness shares one connection; production draws on separate ones.
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_CONCURRENCY", 1)
    # WP-88's allowance is pinned in tests/test_wp88_switch_on.py; here every panel draws.
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD", 10.0)
    queued: list = []
    monkeypatch.setattr(panel_art, "dispatcher", queued.append)
    drawn: list = []

    def fake_draw(job):
        drawn.append(job)
        if job.panel_index == 1:
            raise RuntimeError("scripted failure")
        return _png()

    monkeypatch.setattr(panel_art, "draw", fake_draw)
    return SimpleNamespace(queued=queued, drawn=drawn)


def _episode(client, d) -> dict:
    listed = client.get("/api/v1/story-engine/episodes", headers=d.headers).json()["episodes"]
    assert len(listed) == 1
    return listed[0]


def test_panels_open_on_the_plate_and_their_drawings_replace_it(
    assembled_client, db_session, journey_enabled, clock, provider, art
):
    d = driver(assembled_client, db_session)
    d.create()
    before = _episode(assembled_client, d)
    assert len(before["panels"]) >= 4
    assert {p["image_status"] for p in before["panels"]} == {"rendering"}
    assert all(p["image_url"] for p in before["panels"]), "the reader never waits for art"
    assert len(art.queued) == 1, "queued once, after the commit"

    assert panel_art.render_scene_art(art.queued[0]) == "partial"
    assert len(art.drawn) == len(before["panels"])

    after = _episode(assembled_client, d)
    statuses = [p["image_status"] for p in after["panels"]]
    assert statuses[1] == "setting_reference", "a failed drawing keeps its plate"
    assert statuses.count("panel_art") == len(statuses) - 1
    drawn = [p for p in after["panels"] if p["image_status"] == "panel_art"]
    assert all(p["image_url"].startswith("/media/graphic-novel/scenes/") for p in drawn)
    assert after["panels"][1]["image_url"] == before["panels"][1]["image_url"]


def test_flag_off_queues_nothing(assembled_client, db_session, journey_enabled, clock, provider, art, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_ENABLED", False)
    d = driver(assembled_client, db_session)
    d.create()
    episode = _episode(assembled_client, d)
    assert {p["image_status"] for p in episode["panels"]} == {"setting_reference"}
    assert art.queued == []


def test_the_drawn_set_queues_nothing_and_keeps_the_plates(
    assembled_client, db_session, journey_enabled, clock, provider, art, monkeypatch
):
    """WP-116 phase 6: under the drawn default the cast is drawn in the client, over the plate."""
    monkeypatch.setattr(settings, "ATELIER_ART_SET", "drawn")
    d = driver(assembled_client, db_session)
    d.create()
    episode = _episode(assembled_client, d)
    assert {p["image_status"] for p in episode["panels"]} == {"setting_reference"}
    assert all(p["image_url"] for p in episode["panels"]), "every panel shows its plate"
    assert art.queued == [] and art.drawn == []


def test_a_rolled_back_scene_is_never_drawn(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_ART_SET", "painted")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    queued: list = []
    monkeypatch.setattr(panel_art, "dispatcher", queued.append)
    nested = db_session.begin_nested()
    # WP-88: a scene with nothing to draw queues nothing, so give it one panel.
    scene = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000000",
        panels=[SimpleNamespace(panel_index=0, generation_metadata={})],
    )
    assert panel_art.request_scene_art(db_session, scene)
    nested.rollback()
    db_session.rollback()
    db_session.commit()
    assert queued == []


WORLD = {
    "cast": [
        {"id": "romy_tremblay", "name": "Romane « Romy » Tremblay"},
        {"id": "marin_leveque", "name": "Marin Lévêque"},
        {"id": "lila_bonnet", "name": "Lila Bonnet"},
    ],
    "visual_design": {
        "art_direction": {"style": "Flat screen print.", "palette": "Brand inks only."},
        "characters": {
            "romy_tremblay": {"canonical_descriptor": "long brown hair, leather jacket"},
            "marin_leveque": {"canonical_descriptor": "big, bearded, green sweater"},
        },
        "locations": {"le_mistral": {"canonical_descriptor": "narrow café-bar, zinc counter"}},
    },
}


def _panel(direction, speakers=()):
    return SimpleNamespace(
        panel_index=2,
        image_prompt=direction,
        overlay_payload={"dialogue": [{"character_id": s, "text_fr": "Salut."} for s in speakers]},
    )


def test_the_prompt_names_who_is_in_frame_and_sends_their_portraits():
    scene = SimpleNamespace(id="s", script_payload={"location_id": "le_mistral"})
    job = panel_art.panel_job(
        scene, _panel("Medium shot: Marin laughs while Lila steals his croissant.", ["romy_tremblay"]), WORLD
    )
    assert job.references == ("romy_tremblay", "marin_leveque"), "speakers first, at most two"
    for fragment in (
        "Flat screen print.",
        "narrow café-bar, zinc counter",
        "Romane « Romy » Tremblay (reference image 1",
        "big, bearded, green sweater",
        "Lila Bonnet",
        "Marin laughs while Lila steals his croissant.",
        "No speech bubbles",
    ):
        assert fragment in job.prompt, fragment


def test_an_empty_room_is_drawn_without_references():
    scene = SimpleNamespace(id="s", script_payload={"location_id": "le_mistral"})
    job = panel_art.panel_job(scene, _panel("Wide shot of the rain on the window."), WORLD)
    assert job.references == ()
    assert "In frame" not in job.prompt
