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


def test_repair_slip_replaces_duplicate_mission_and_feuilleton_markup() -> None:
    missions = read(MISSIONS_PAGE)
    feuilleton = read(FEUILLETON_PAGE)

    assert "import { ContinuationCard, RedInkRepairSlip, VocabularyCreditBadge }" in missions
    assert "function TurnRepairMarkup" in missions
    assert "className=\"turn-repair-slip\"" in missions
    assert "function CorrectionStack" in missions
    assert "slipNumber={`NO. ${String(index + 1).padStart(2, '0')}`}" in missions
    assert "import { ContinuationCard, MobileBottomSheet, RedInkRepairSlip, VocabularyCreditBadge }" in feuilleton
    assert "source=\"Feuilleton" in feuilleton


def test_atelier_uses_repair_slip_for_due_errata_and_closure() -> None:
    atelier = read(ATELIER_PAGE)
    api_types = read(API_TYPES)

    assert "function DueErrataList" in atelier
    assert "function ErrataReviewOverlay" in atelier
    assert "function ErrataStack" in atelier
    assert "ERRATA DUE" in atelier
    assert "REMEMBERED SLIP" in atelier
    assert "SUBMIT REPAIR" in atelier
    assert "result.is_correct ? 'REPAIRED' : 'NOT YET'" in atelier
    assert "Repair in mission" in atelier
    assert "export interface AtelierErrataAttemptResult" in api_types


def test_grammar_notebook_uses_same_repair_slip() -> None:
    grammar = read(GRAMMAR_PAGE)

    assert "NotebookModeSwitch, RedInkRepairSlip" in grammar
    assert "function ErratumCard" in grammar
    assert "className=\"notebook-erratum-card\"" in grammar
    assert "Repair in mission" in grammar
