"""Static regression tests for the shared red-ink repair UI."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_INDEX = ROOT / "web-frontend" / "components" / "mobile" / "index.ts"
REPAIR_SLIP = ROOT / "web-frontend" / "components" / "mobile" / "RedInkRepairSlip.tsx"
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"
MISSIONS_PAGE = ROOT / "web-frontend" / "pages" / "missions.tsx"
FEUILLETON_PAGE = ROOT / "web-frontend" / "pages" / "graphic-novel.tsx"
GRAMMAR_PAGE = ROOT / "web-frontend" / "pages" / "grammar.tsx"
API_TYPES = ROOT / "web-frontend" / "services" / "api.ts"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_red_ink_repair_slip_is_shared_mobile_primitive() -> None:
    source = read(REPAIR_SLIP)
    exports = read(MOBILE_INDEX)

    assert "export interface RedInkRepairSlipProps" in source
    assert "const RedInkRepairSlip" in source
    assert 'aria-label="Red ink repair"' in source
    assert "You wrote" in source
    assert "Corrected" in source
    assert "Corrected. Filed." in source
    assert "export { RedInkRepairSlip" in exports


def test_mission_screen_removed_duplicate_repair_chrome_while_feuilleton_uses_slip() -> None:
    missions = read(MISSIONS_PAGE)
    feuilleton = read(FEUILLETON_PAGE)

    assert "RedInkRepairSlip" not in missions
    assert "function TurnRepairMarkup" not in missions
    assert "className=\"turn-repair-slip\"" not in missions
    assert "function CorrectionStack" not in missions
    # Missions keeps its own quiet graphite repair (CrRepair), not the shared slip.
    assert "<CrRepair" in missions
    assert "correctedAnswer={correctedAnswer}" in missions
    assert "savedCount={savedCount}" in missions
    # Reader rebuild: the Feuilleton reply shows ONE short French response inline
    # (audit §6), so the bottom-sheet duplicate and the shared repair slip are gone.
    assert "MobileBottomSheet" not in feuilleton
    assert "RedInkRepairSlip" not in feuilleton
    assert "function correctionLine" in feuilleton


def test_atelier_uses_repair_slip_for_due_errata_and_closure() -> None:
    atelier = read(ATELIER_PAGE)
    api_types = read(API_TYPES)

    # DueErrataList/ErrataStack were unreferenced legacy components; the live
    # repair path is the overlay reached from La Une and the review deck.
    assert "function ErrataReviewOverlay" in atelier
    assert "ERREUR MÉMORISÉE" in atelier
    assert "ENVOYER LA REPRISE" in atelier
    assert "result.is_correct ? 'REPRIS' : 'PAS ENCORE'" in atelier
    assert "export interface AtelierErrataAttemptResult" in api_types


def test_grammar_notebook_uses_same_repair_slip() -> None:
    grammar = read(GRAMMAR_PAGE)

    # In the Cahiers fiche, a concept's errata are filed as proofreader-style
    # ledger rows: the learner's slip struck through, the correction in the
    # margin — split into "à revoir" (due) and "récents" (repaired) sections.
    # Claude-design fiche: the same ledger rows on the av2 surface.
    assert "function ErratumLine" in grammar
    assert "<s>{learner}</s>" in grammar
    assert 't="Errata à revoir"' in grammar
    assert 't="Errata récents"' in grammar
    assert "<ErratumLine" in grammar
