"""Static regression tests for Serial Season 1 archive surfaces."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read_web(path: str) -> str:
    return (WEB / path).read_text(encoding="utf-8")


def test_serial_archive_cast_and_replay_pages_are_wired() -> None:
    archive = read_web("pages/serial/index.tsx")
    cast = read_web("pages/serial/cast.tsx")
    replay = read_web("pages/serial/episode/[index].tsx")
    api = read_web("services/api.ts")

    assert "apiService.getSerialEpisodes()" in archive
    assert "Season 1" in archive
    assert "href=\"/serial/cast\"" in archive
    assert "apiService.getSerialCast()" in cast
    assert "model_sheet_url" in cast
    assert "relationship.closeness" in cast
    assert "apiService.getGraphicNovelScene" in replay
    assert "apiService.getMission" in replay
    assert "mission-replay" in replay
    assert "getSerialEpisodes()" in api
    assert "getSerialCast()" in api

def test_graphic_novel_serial_page_keeps_bubbles_and_panel_tasks_inline() -> None:
    source = read_web("pages/graphic-novel.tsx")

    assert "function PanelInlineTaskDisclosure" in source
    assert "À toi —" in source
    assert "data-panel-task-drawer" in source
    assert 'className="panel-task-drawer"' in source
    assert 'className="source-card compact-source"' in source
    assert '<details className="feuilleton-vocabulary-strip"' in source
    assert "display: block;" in source[source.index(".feuilleton-page .bubble-layer") : source.index(".feuilleton-page .mobile-panel-dialogue")]
    assert "choiceOptionView" in source
