"""Static regression tests for Atelier's visible cross-mode thread handoff."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"
HAPTICS_LIB = ROOT / "web-frontend" / "lib" / "haptics.ts"


def read_atelier() -> str:
    return ATELIER_PAGE.read_text(encoding="utf-8")


def test_atelier_renders_today_practice_thread() -> None:
    source = read_atelier()

    assert "function TodayView" in source
    assert "edition-cover" in source
    assert "today-plan" in source
    assert ">Today</span>" in source
    assert 'aria-label="Atelier roadmap"' in source
    assert "SerialThreadCard" in source
    assert "LibraryThreadCard" in source


def test_today_thread_hands_context_to_mission_feuilleton_and_notebook() -> None:
    source = read_atelier()

    assert "function NotebookBridge" in source
    assert "function MissionBridge" in source
    assert "const query = conceptQueryString(concepts)" in source
    assert "const nodes: RoadmapNode[] = [" in source
    assert "serialActionFromToday(today, activeSession)" in source
    assert "libraryEpisode = (today as any)?.library_episode" in source
    assert "recommendation.kind === 'library'" in source
    assert "const conceptIds = concepts.map((concept) => `concept_id=${concept.id}`).join('&')" in source
    assert "href={`/grammar?concept=${concept.id}`}" in source
    assert "href={`/missions${conceptIds ? `?${conceptIds}` : ''}`}" in source
    assert "href={`/graphic-novel${conceptIds ? `?${conceptIds}` : ''}`}" in source


def test_do_mode_uses_rule_first_ramp_and_feedback_sheet() -> None:
    source = read_atelier()

    assert "{ id: 'fill', label: 'Fill', short: 'A' }" in source
    assert "{ id: 'classify', label: 'Classify', short: 'B' }" in source
    assert "{ id: 'word_bank', label: 'Word-bank', short: 'C' }" in source
    assert "firstConceptDrill" in source
    assert "rule-bridge" in source
    assert "Now try it on the easiest item." in source
    assert "payload.rule_panel" in source
    assert "reportAtelierExercise" in source
    assert "InlineFeedback" in source
    assert "feedback.issues || []" in source
    assert "const errata: AtelierErratum[]" in source


def test_inline_feedback_scopes_errata_to_each_exercise() -> None:
    source = read_atelier()

    assert "const hasItemScopedErrata = errata.some" in source
    assert "if (erratumItemId) return erratumItemId === item.id" in source
    assert "if (hasItemScopedErrata) return false" in source
    assert "errLearner === learnerNorm && errTarget === targetNorm" in source


def test_atelier_feedback_uses_reduced_motion_safe_haptics() -> None:
    source = read_atelier()
    haptics = HAPTICS_LIB.read_text(encoding="utf-8")

    assert "function pulseAtelierHaptic" in source
    assert "pulseAppHaptic(kind)" in source
    assert "prefers-reduced-motion: reduce" in haptics
    assert "vibrate(pattern)" in haptics
    assert "pulseAtelierHaptic(result.verdict === 'correct' ? 'correct' : 'repair')" in source
    assert "pulseAtelierHaptic('complete')" in source
