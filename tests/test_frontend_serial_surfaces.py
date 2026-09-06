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
    # "Le Feuilleton" supplement reskin: the archive is the bound season.
    assert "La saison reliée" in archive
    assert "FeArchivePlate" in archive
    assert "FeSectionNav" in archive
    assert "href=\"/serial/cast\"" in archive
    assert "apiService.getSerialCast()" in cast
    assert "apiService.setSerialAvatar" in cast
    assert "Rester en POV" in cast
    assert "FeCastCard" in cast
    assert "model_sheet_url" in cast
    assert "relationship.closeness" in cast
    assert "apiService.getGraphicNovelScene" in replay
    assert "apiService.getMission" in replay
    assert "mission-replay" in replay
    assert "getSerialEpisodes()" in api
    assert "getSerialCast()" in api
    assert "setSerialAvatar" in api


def test_graphic_novel_panel_prints_art_dialogue_and_one_inline_action() -> None:
    """Reader rebuild: the panel drawer, the source card and the vocabulary strip
    are gone; a panel is art + one numeral + dialogue lines + one quiet action."""
    source = read_web("pages/graphic-novel.tsx")

    assert "function PanelTask" in source
    assert "function panelDialogueLines" in source
    assert "function additivePanelCaption" in source
    assert "<FeDialogue" in source
    assert "choiceOptionView" in source
    for dead in (
        "function PanelInlineTaskDisclosure",
        "data-panel-task-drawer",
        "panel-task-drawer",
        "source-card",
        "feuilleton-vocabulary-strip",
        "bubble-layer",
        "mobile-panel-dialogue",
        "function BubbleOverlay",
        "function BubbleTranscript",
    ):
        assert dead not in source


def test_graphic_novel_scene_leads_with_panels_and_has_no_scene_brief() -> None:
    """Reader rebuild: SceneBrief (news-first synopsis + source card + edition
    meta) is removed outright, so the read simply leads."""
    source = read_web("pages/graphic-novel.tsx")

    assert "function SceneBrief" not in source
    assert "<SceneBrief" not in source
    assert "className=\"serial-reader\"" in source
    assert "function SerialFinalAct" in source
    assert source.index("<SerialSceneReader") < source.index("<SerialFinalAct")
    assert source.index('className="panel-grid" id="reading-panels"') < source.index("<SerialFinalAct")


def test_graphic_novel_completion_routes_to_returned_serial_beat() -> None:
    source = read_web("pages/graphic-novel.tsx")
    missions = read_web("pages/missions.tsx")
    api = read_web("services/api.ts")

    assert "next_serial?: SerialToday | null" in api
    assert "function routeForSerialBeat" in source
    assert "routeForSerialBeat(result.next_serial)" in source
    assert "function routeForMissionSerialBeat" in missions
    assert "serialQueryString(serial)" in missions
    assert "routeForMissionSerialBeat(completedNextSerial)" in missions
    # The non-serial continuation still follows the declared next beat.
    assert "const nextBeatIsMission = hook?.next_beat_kind === 'mission'" in source
    assert "routeWithQuery('/missions', missionPairs)" in source
    assert "routeWithQuery('/graphic-novel', readerPairs)" in source
    # Reader rebuild: the end of the episode is one action — Terminer l’épisode
    # while it is open, the declared next beat once it is filed.
    assert "Terminer l’épisode" in source
    assert "<Link className=\"btn solid lg\" href={nextBeatHref}>" in source


def test_feuilleton_legacy_reader_rules_are_pruned_after_fe_panel_adoption() -> None:
    source = read_web("pages/graphic-novel.tsx")

    for dead_selector in (".s-mast", ".s-prev", ".s-panel", ".s-art", ".s-cap"):
        assert dead_selector not in source

    # Reader rebuild: the "cette semaine" news aside and the uppercase fork
    # header are gone with the rest of the legacy .s-* era.
    assert ".s-news" not in source
    assert ".s-fork" not in source
    assert 'className="fe-embed serial-final-act"' in source


def test_graphic_novel_default_route_rejoins_canonical_story_beat() -> None:
    source = read_web("pages/graphic-novel.tsx")

    assert "const [canonicalBeat, setCanonicalBeat]" in source
    assert "const [serialResult, editionsResult] = await Promise.allSettled" in source
    assert "if (serial.kind === 'feuilleton' && serial.scene_id)" in source
    assert "canonicalBeat?.kind === 'mission'" in source
    assert "La suite se joue avant de se lire." in source
    # Soft-button pass: CTA labels are sentence case (text-transform removed).
    assert "Ouvrir la mission du jour" in source
    assert "onClick={openCanonicalBeat}" in source
    assert "Aucun récit parallèle ne sera créé." in source


def test_feuilleton_translations_stay_hidden_until_requested() -> None:
    """Reader rebuild: the global "Afficher EN" toggle is replaced by a per-panel
    and per-task Traduire affordance; nothing English renders unrequested."""
    source = read_web("pages/graphic-novel.tsx")
    supplement = read_web("components/feuilleton/Feuilleton.tsx")

    assert "showMobileTranslations" not in source
    assert "Afficher EN" not in source
    assert "translated={translated}" in source
    assert "onTranslate={() => setTranslated((current) => !current)}" in source
    assert "translateLabel = 'Traduire'" in supplement
    assert "{translated && line.en && <em>{line.en}</em>}" in supplement
    assert "@media (max-width: 900px)" in source
    assert ".feuilleton-page .serial-act > .fe-task" in source


def test_almanac_story_seals_render_panel_crop_art() -> None:
    source = read_web("pages/almanac.tsx")

    assert "function StorySealCard" in source
    assert "function PlateCard" in source
    assert "metadata?.seal_crop" in source
    assert "storySealImageUrl(seal)" in source
    assert "objectPosition" in source
    assert "className=\"story-seal-grid\"" in source
    assert "className=\"story-seal-ring\"" in source
    assert "loadError" in source
    assert "composeError" in source
    assert "The originals stay nested in your almanac" in source
    assert "className=\"plate-members\"" in source
    assert "setAlmanac(null)" not in source


def test_product_direction_surfaces_are_wired() -> None:
    atelier = read_web("pages/atelier.tsx")
    missions = read_web("pages/missions.tsx")
    api = read_web("services/api.ts")
    redirects = read_web("next.config.js")
    bibliotheque = read_web("pages/bibliotheque.tsx")

    # Le cours is an En bref row since the manchette redesign; the full block
    # lives in Le Relevé.
    assert "<LuEnBref" in atelier
    assert "href: '/notebook?mode=releve'" in atelier
    assert "estimatedRemainingMinutes" in atelier
    assert "CrTranslate" in missions or "translate={translateFrame}" in missions
    assert "className=\"cr motion\"" in missions
    assert "missionVariety" in missions
    assert "voicemail_reply" in api
    assert "admin_form" in api
    assert "mission_format" in api
    assert "getCefrProgress()" in api
    assert "destination: '/atelier'" in redirects
    assert "source: '/stories/:path*'" in redirects
    assert "source: '/bibliotheque/:path*'" in redirects
    assert "from './stories'" in bibliotheque
