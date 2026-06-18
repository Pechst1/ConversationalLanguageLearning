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
    assert "'Season ' + seasonNumber" in archive
    assert 'className="s-map"' in archive
    assert "aria-label={`Season ${seasonNumber} thread`}" in archive
    assert 'className="s-ep-link"' in archive
    assert "href=\"/serial/cast\"" in archive
    assert "apiService.getSerialCast()" in cast
    assert "apiService.setSerialAvatar" in cast
    assert "Use POV" in cast
    assert "model_sheet_url" in cast
    assert "relationship.closeness" in cast
    assert "apiService.getGraphicNovelScene" in replay
    assert "apiService.getMission" in replay
    assert "mission-replay" in replay
    assert "getSerialEpisodes()" in api
    assert "getSerialCast()" in api
    assert "setSerialAvatar" in api


def test_graphic_novel_serial_page_keeps_bubbles_and_panel_tasks_inline() -> None:
    source = read_web("pages/graphic-novel.tsx")

    assert "function PanelInlineTaskDisclosure" in source
    assert "À toi —" in source
    assert "data-panel-task-drawer" in source
    assert "className=\"panel-task-drawer\"" in source
    assert "className=\"source-card compact-source\"" in source
    assert "<details className=\"feuilleton-vocabulary-strip\"" in source
    assert "display: block;" in source[source.index(".feuilleton-page .bubble-layer") : source.index(".feuilleton-page .mobile-panel-dialogue")]
    assert "choiceOptionView" in source


def test_graphic_novel_scene_leads_with_panels_before_brief() -> None:
    source = read_web("pages/graphic-novel.tsx")

    assert source.index("<SerialSceneReader") < source.index("<SceneBrief scene={scene}")
    assert "className=\"serial-reader s-feuil\"" in source
    assert "function SerialFinalAct" in source
    assert source.index(") : scene.script_payload?.render_mode === 'page' ?") < source.index("<SceneBrief scene={scene}")
    assert source.index('className="panel-grid" id="reading-panels"') < source.index("<SceneBrief scene={scene}")


def test_almanac_story_seals_render_panel_crop_art() -> None:
    source = read_web("pages/almanac.tsx")

    assert "function StorySealCard" in source
    assert "metadata?.seal_crop" in source
    assert "storySealImageUrl(seal)" in source
    assert "objectPosition" in source
    assert "className=\"story-seal-grid\"" in source
    assert "className=\"story-seal-ring\"" in source


def test_product_direction_surfaces_are_wired() -> None:
    atelier = read_web("pages/atelier.tsx")
    missions = read_web("pages/missions.tsx")
    api = read_web("services/api.ts")
    redirects = read_web("next.config.js")
    bibliotheque = read_web("pages/bibliotheque.tsx")

    assert "CEFRPromiseStrip" in atelier
    assert "estimatedRemainingMinutes" in atelier
    assert "MissionFormatBrief" in missions
    assert "voicemail_reply" in missions
    assert "admin_form" in missions
    assert "mission_format" in api
    assert "getCefrProgress()" in api
    assert "destination: '/bibliotheque'" in redirects
    assert "source: '/stories/:path*'" in redirects
    assert "from './stories'" in bibliotheque
