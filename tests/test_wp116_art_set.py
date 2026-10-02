"""WP-116 phase 2: the backend side of the art-set switch."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services import panel_art, serial_notifications

REPO = Path(__file__).resolve().parents[1]


def test_pushes_use_the_painted_face_by_default_and_the_drawn_png_when_drawn(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_ART_SET", "painted")
    assert serial_notifications.portrait_path("marin", "happy") == "/assets/serial/characters/marin_leveque/portrait-happy.webp"
    monkeypatch.setattr(settings, "ATELIER_ART_SET", "drawn")
    path = serial_notifications.portrait_path("marin", "happy")
    assert path == "/assets/serial/drawn/marin_leveque/portrait-ravie.png"
    assert (REPO / "web-frontend/public" / path.lstrip("/")).exists(), "run node scripts/render-rigs.mjs"
    for face in serial_notifications.PORTRAIT_FACES:
        for key in set(serial_notifications.PORTRAIT_CHARACTERS.values()):
            drawn = serial_notifications.portrait_path(key, face)
            assert (REPO / "web-frontend/public" / drawn.lstrip("/")).exists(), drawn
    assert serial_notifications.portrait_path("bastien", "happy") is None


def test_drawn_set_switches_paid_panel_drawing_off(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_ART_SET", "drawn")
    assert "drawn" in (panel_art.unavailable_reason() or "")
    assert panel_art.enabled() is False


def test_a_panel_keeps_its_plate_when_a_drawing_replaces_it():
    from types import SimpleNamespace

    from app.api.v1.endpoints.story_engine import panel_plate_url

    plate = "/assets/serial/locations/le_mistral-counter.webp"
    undrawn = SimpleNamespace(image_url=plate, generation_metadata={"image_source": "setting_reference"})
    assert panel_plate_url(undrawn) == plate
    drawn_new = SimpleNamespace(image_url="/media/x.webp", generation_metadata={"image_source": "panel_art", "plate_url": plate})
    assert panel_plate_url(drawn_new) == plate
    drawn_old = SimpleNamespace(image_url="/media/x.webp", generation_metadata={"image_source": "panel_art"})
    assert panel_plate_url(drawn_old) is None, "an old drawing never passes itself off as a plate"

    panel = SimpleNamespace(image_url=plate, image_payload=None, generation_metadata={"image_source": "setting_reference"})
    panel_art._attach(panel, {"image_url": "/media/drawn.webp"}, "prefetch-1")
    assert panel.image_url == "/media/drawn.webp"
    assert panel.generation_metadata["plate_url"] == plate


def test_t1_opens_on_the_rainy_quai_seen_from_the_cafe_not_the_market():
    """2026-10-02: T1 P1 is night rain on the quai de Valmy; the market plate (a sunny
    day with stalls) told the wrong story, on Home's card and on the first panel."""

    from app.services.season.world import plate_for

    assert plate_for("quai_de_valmy") == "/assets/serial/locations/le_mistral-counter.webp"
