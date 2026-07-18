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

    # Home screen is the "La Une" front page (components/laune/LaUne.tsx).
    assert "function TodayView" in source
    assert "from '@/components/laune/LaUne'" in source
    assert "<LaUneStyles" in source
    assert "<LuMasthead" in source
    assert "<LuLead" in source
    assert "<LuSeance" in source
    assert 'aria-label="Atelier · La Une"' in source
    assert "STORY_FEATURE_VISIBLE" in source


def test_today_thread_hands_context_to_mission_feuilleton_and_hides_story_library() -> None:
    source = read_atelier()

    # The lead story routes to today's serial mission/feuilleton beat; the
    # library article stays gated behind STORY_FEATURE_VISIBLE.
    assert "serialActionFromToday(today, activeSession)" in source
    assert "const serialKind = serialAction?.episodeKind" in source
    assert "const openStory = storyHref ? () => { void router.push(storyHref); } : null" in source
    assert "mission={isMissionBeat}" in source
    assert "libraryEpisode = STORY_FEATURE_VISIBLE ? (today as any)?.library_episode || null : null" in source
    assert "STORY_FEATURE_VISIBLE && libraryEpisode && (" in source


def test_atelier_fallback_shell_uses_shared_theme_tokens() -> None:
    source = read_atelier()

    assert "--paper: var(--app-paper)" in source
    assert "--sheet: var(--app-sheet)" in source
    assert "--ink: var(--app-ink)" in source
    assert "--paper: #f1ece1" not in source


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
    # Feedback is the inline épreuve verdict (EpVerdict + galley marks in the
    # page flow), not a floating sheet; one-word fixes skip the typed repair.
    assert "InlineFeedbackModel" in source
    assert "feedback.issues?.length" in source
    assert "<EpVerdict tone=" in source
    assert "isRepairableLine(target)" in source
    assert "const errata: AtelierErratum[]" in source


def test_inline_feedback_scopes_errata_to_each_exercise() -> None:
    source = read_atelier()

    assert "const hasItemScopedErrata = errata.some" in source
    assert "if (erratumItemId) return erratumItemId === item.id" in source
    assert "if (hasItemScopedErrata) return false" in source
    assert "errLearner === learnerNorm && errTarget === targetNorm" in source


def test_feedback_confirms_lexical_gap_words_added_to_notebook() -> None:
    source = read_atelier()

    # A German/English fallback word the learner used is added to the vocabulary
    # notebook by the backend; the feedback confirms it inline.
    assert "correction?.vocabulary_gaps?.added" in source
    assert 'className="ep-notebook-add"' in source
    assert "Ajouté au carnet" in source


def test_atelier_feedback_uses_reduced_motion_safe_haptics() -> None:
    source = read_atelier()
    haptics = HAPTICS_LIB.read_text(encoding="utf-8")

    assert "function pulseAtelierHaptic" in source
    assert "pulseAppHaptic(kind)" in source
    assert "prefers-reduced-motion: reduce" in haptics
    assert "vibrate(pattern)" in haptics
    assert "pulseAtelierHaptic(result.verdict === 'correct' ? 'correct' : 'repair')" in source
    assert "pulseAtelierHaptic('complete')" in source
