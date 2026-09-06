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
    assert "Queue claire" in source
    assert "onReturn" in source
    assert "onRefresh" in source
    assert "href={`/vocabulary?word=${wordId}`}" in source
    assert "Actualiser" in source


def test_mission_completion_routes_to_new_moment_and_home() -> None:
    source = read(MISSIONS_PAGE)

    # The resolved dossier ("Le Courrier") offers: next act (serial) / a fresh
    # correspondence / back to La Une — per the design brief §6.
    assert "resolutionCredit(mission" in source
    assert "Nouveau courrier" in source
    assert "Retour à la Une" in source
    assert "routeForMissionSerialBeat(completedNextSerial)" in source
    assert "createSeededMission({" in source
    assert "minted_collectibles" in source


def test_feuilleton_post_scene_uses_journal_continuation_primitives() -> None:
    source = read(FEUILLETON_PAGE)

    # Reader rebuild: the post-scene furniture (completion card with counters,
    # lexical summary, two-beat continuation, duplicate complete row) collapsed
    # into one FeuilletonEnd — the filed stamp plus a single next action.
    assert "function FeuilletonEnd" in source
    assert "<FeuilletonEnd" in source
    assert "<FeFiled label=" in source
    assert "function FeuilletonContinuationCard" not in source
    assert "Agir dans Le Courrier" in source
    assert "Lire le prochain épisode" in source
    assert "nextBeatIsMission" in source
    assert "routeWithQuery('/missions', missionPairs)" in source
    assert "routeWithQuery('/graphic-novel', readerPairs)" in source


def test_atelier_recap_continues_session_into_context() -> None:
    source = read(ATELIER_PAGE)

    # The recap is now the L'Épreuve proof sheet (EpBatStage/EpRecapHead/EpTally/
    # EpProof/EpSeal/EpHandoff) instead of the old plain "Edition printed" card;
    # its close button replaces the old "Done" label.
    assert "function RecapModal" in source
    assert "<EpBatStage" in source
    assert "<EpRecapHead" in source
    assert "<EpTally" in source
    assert "<EpProof" in source
    assert "<EpSeal" in source
    assert "<EpHandoff" in source
    assert "session_id: result.session_id" in source
    assert "aria-label=\"Fermer l’épreuve\"" in source


def test_serial_world_design_surfaces_are_integrated() -> None:
    atelier = read(ATELIER_PAGE)
    missions = read(MISSIONS_PAGE)
    feuilleton = read(FEUILLETON_PAGE)
    globals_css = read(GLOBALS)

    # SerialThreadCard was an unreferenced legacy card; the serial surfaces on
    # La Une are LuLead/LuDemain, wired from the serial payload.
    assert "const isSerialAct = Boolean(mission?.serial_thread_id || seed.serialThreadId)" in missions
    # A serial act flips the desk furniture to the blue "Le Feuilleton · Acte N"
    # kicker and stamps "Acte bouclé" on resolution.
    assert "Le Feuilleton · Acte" in missions
    assert "Acte bouclé" in missions
    assert "function FeuilletonCliffhangerHero" in feuilleton
    # "Le Feuilleton" reskin: the cliffhanger is drawn with the shared FeCliff
    # primitive inside an .fe-embed scope (see components/feuilleton/Feuilleton).
    assert "className=\"fe-embed feuilleton-cliffhanger\"" in feuilleton
    assert "<FeCliff" in feuilleton
    assert "--char-romy: #1d3a8a" in globals_css
    assert "[data-char=\"marchand\"]" in globals_css
