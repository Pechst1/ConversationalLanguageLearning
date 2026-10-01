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
