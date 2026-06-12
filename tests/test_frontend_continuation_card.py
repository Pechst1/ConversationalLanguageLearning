"""Static regression tests for cross-mode continuation surfaces."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOBILE_INDEX = ROOT / "web-frontend" / "components" / "mobile" / "index.ts"
CONTINUATION_CARD = ROOT / "web-frontend" / "components" / "mobile" / "ContinuationCard.tsx"
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"
MISSIONS_PAGE = ROOT / "web-frontend" / "pages" / "missions.tsx"
FEUILLETON_PAGE = ROOT / "web-frontend" / "pages" / "graphic-novel.tsx"
VOCABULARY_REVIEW_PAGE = ROOT / "web-frontend" / "pages" / "vocabulary" / "review.tsx"
GLOBALS = ROOT / "web-frontend" / "styles" / "globals.css"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_continuation_card_is_shared_mobile_primitive() -> None:
    source = read(CONTINUATION_CARD)
    exports = read(MOBILE_INDEX)

    assert "export type ContinuationTone" in source
    assert "export type ContinuationAction" in source
    assert "const ContinuationCard" in source
    assert 'aria-label="Continuation"' in source
    assert "export { ContinuationCard" in exports


def test_vocabulary_review_done_state_offers_context_handoffs() -> None:
    source = read(VOCABULARY_REVIEW_PAGE)

    assert "function VocabularyReviewContinuation" in source
    assert "<ContinuationCard" in source
    assert "Carry the freshest word into context" in source
    assert "hrefWithQuery('/missions', [['vocabulary_id', wordId]])" in source
    assert "hrefWithQuery('/graphic-novel', [['vocabulary_id', wordId]])" in source
    assert "Refresh queue" in source


def test_mission_bridge_uses_shared_continuation_card() -> None:
    source = read(MISSIONS_PAGE)

    assert "import { ContinuationCard, RedInkRepairSlip, VocabularyCreditBadge }" in source
    assert "function MissionBridgePanel" in source
    assert "<ContinuationCard" in source
    assert "Next repair bridge" in source
    assert "Quick repair session" in source
    assert "Read in Feuilleton" in source
    assert "routeWithQuery('/graphic-novel', feuilletonPairs)" in source


def test_feuilleton_post_scene_uses_shared_continuation_card() -> None:
    source = read(FEUILLETON_PAGE)

    assert "function FeuilletonContinuationCard" in source
    assert "<FeuilletonContinuationCard scene={scene} vocabulary={targetVocabulary} />" in source
    assert "<ContinuationCard" in source
    assert "Turn this scene into practice" in source
    assert "routeWithQuery('/missions', missionPairs)" in source
    assert "routeWithQuery('/atelier', atelierPairs)" in source


def test_atelier_recap_continues_session_into_context() -> None:
    source = read(ATELIER_PAGE)

    assert "function RecapModal" in source
    assert "Session recap" in source
    assert "recap.session_id" in source
    assert "href={`/missions?atelier_session_id=${recap.session_id}`}" in source
    assert "USE IN MISSION" in source
    assert "RETURN TO TODAY" in source


def test_serial_world_design_surfaces_are_integrated() -> None:
    atelier = read(ATELIER_PAGE)
    missions = read(MISSIONS_PAGE)
    feuilleton = read(FEUILLETON_PAGE)
    globals_css = read(GLOBALS)

    assert "function SerialThreadCard" in atelier
    assert "className={`s-thread" in atelier
    assert "function MissionWorldReplyCard" in missions
    assert "className=\"s-reply mission-world-reply\"" in missions
    assert "function FeuilletonCliffhangerHero" in feuilleton
    assert "className=\"s-cliff feuilleton-cliffhanger\"" in feuilleton
    assert "--char-romy: #1d3a8a" in globals_css
    assert "[data-char=\"marchand\"]" in globals_css
