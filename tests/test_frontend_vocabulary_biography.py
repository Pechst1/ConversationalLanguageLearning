"""Static regression tests for vocabulary biography surfaces."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VOCABULARY_PAGE = ROOT / "web-frontend" / "pages" / "vocabulary.tsx"
VOCABULARY_REVIEW_PAGE = ROOT / "web-frontend" / "pages" / "vocabulary" / "review.tsx"
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"


def read_vocabulary_page() -> str:
    return VOCABULARY_PAGE.read_text(encoding="utf-8")


def read_page(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_vocabulary_notebook_opens_word_biography_sheet() -> None:
    source = read_vocabulary_page()

    assert "WordBiographySheet" in source
    assert "const [biographyWordId, setBiographyWordId]" in source
    assert "const [biography, setBiography]" in source
    assert "const [biographyLoading, setBiographyLoading]" in source
    assert "const [biographyError, setBiographyError]" in source
    assert "setBiographyWordId(detailWordId(detail))" in source
    assert "Word biography" in source
    assert "open={Boolean(biographyWordId)}" in source


def test_vocabulary_notebook_loads_biography_endpoint() -> None:
    source = read_vocabulary_page()

    assert "apiService.getVocabularyBiography(biographyWordId)" in source
    assert "setBiography(nextBiography)" in source
    assert "Could not load this word biography." in source
    assert "setBiographyWordId(null)" in source


def test_vocabulary_review_keeps_anki_flow_and_exposes_history() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "WordBiographySheet" in source
    assert "const [biographyOpen, setBiographyOpen]" in source
    assert "apiService.getVocabularyBiography(current.word_id)" in source
    assert "History" in source
    assert "queueExample(current)" in source
    assert "exampleTranslation" in source
    assert "Taper pour révéler" in source
    assert "setRevealed((value) => !value)" in source
    assert "reviewOptions.map" in source


def test_vocabulary_review_cloze_and_audio_guards_are_unicode_safe() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "const boundary = 'A-Za-z0-9À-ÖØ-öø-ÿ'" in source
    assert "new RegExp(`(^|[^${boundary}])" in source
    assert "recordingWordIdRef" in source
    assert "activeWordIdRef.current !== wordId" in source
    assert "cancelActiveRecording()" in source
    assert "speechSynthesis.cancel()" in source


def test_vocabulary_review_uses_visible_card_text_classes() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert 'className="review-prompt-term"' in source
    assert "color: var(--ink);" in source
    assert ".review-answer-word" in source
    assert ".review-context-anchor" in source


def test_vocabulary_review_retries_stale_auth_as_local_flow() -> None:
    source = read_page(ROOT / "web-frontend" / "services" / "api.ts")

    assert "return this.atelierGet('/progress/vocabulary/recommendations', { params });" in source
    assert "async getVocabularyDueContext" in source
    assert "return this.atelierGet('/vocabulary/due-context', { params });" in source
    assert "return this.atelierGet('/vocabulary/coverage');" in source
    assert "return this.atelierGet('/vocabulary/conjugation/review', { params });" in source
    assert "return this.atelierPost('/vocabulary/conjugation/review', data);" in source
    assert "return this.atelierGet('/progress/vocabulary/map', { params });" in source
    assert "return this.atelierGet('/progress/weekly-dossier', { params });" in source
    assert "return this.atelierGet<CEFRProgress>('/progress/cefr');" in source
    assert "async submitAnkiReview" in source
    assert "return this.atelierPost('/anki/review', data);" in source


def test_vocabulary_review_keeps_header_and_rating_controls_compact() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "review-topline" not in source
    assert "review-deck-link" not in source
    assert "mobileAction=" not in source
    assert "font-size: clamp(34px, 10vw, 42px);" in source
    assert "const sessionRemaining = remainingItems.length" in source
    assert "<strong>{sessionRemaining}</strong>" in source
    assert "remainingSummary.due" in source
    assert "refreshQueueSummary" not in source
    assert "const handleRatingClick" in source
    assert "disabled={reviewing}" in source
    assert "disabled={reviewing || !revealed}" not in source
    assert "Reveal answer before rating" in source
    assert ">Deck</Link>" not in source


def test_vocabulary_review_uses_local_visual_cues_before_generated_images() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "function wordVisualCue" in source
    assert "type LucideIcon" in source
    assert "abaisser" in source
    assert "review-visual-cue" in source
    assert "aria-label={`${visualCue.label} visual cue`}" in source


def test_vocabulary_review_back_face_keeps_answer_content_visible() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "FSRS · {current.bucket}" not in source
    assert 'className="review-answer-container w-full flex-1 flex flex-col"' in source
    assert ".vocab-flashcard-back {\n          background: #fbfaf6;\n          transform: rotateY(180deg);\n          overflow: hidden;" in source
    assert ".review-answer-container {\n          min-height: 0;" in source
    assert "overflow-y: auto;" in source


def test_vocabulary_notebook_uses_compact_coverage_snapshot() -> None:
    source = read_vocabulary_page()

    assert "reliableTopicCategories" in source
    assert "coverageSummaryCards" in source
    assert "Level {currentBand?.band || 'A1'}" in source
    assert "Choose a set to master" in source
    assert "See full atlas" in source
    assert "French 5000 mastery map" in source
    assert "Uncategorized" not in source
    assert "Words & categories" not in source
    assert "Verbs & conjugation" not in source
    assert "Grammar patterns" not in source


def test_atelier_daily_session_surfaces_target_vocabulary_in_context() -> None:
    source = read_page(ATELIER_PAGE)

    assert "function VocabularyFocus" in source
    assert "session.target_vocabulary" in source
    assert "target-word-strip" in source
    assert 'aria-label="Vocabulary targets for this paragraph"' in source
    assert "vocabularyTranslation(item)" in source


def test_atelier_today_surfaces_vocabulary_training_step() -> None:
    source = read_page(ATELIER_PAGE)

    assert "vocabularyReviewDue" in source
    assert 'name="Vocabulary training"' in source
    assert 'href="/vocabulary/review"' in source
    assert 'roman="VOC"' in source
    assert "function AtelierVocabularyOpen" in source


def test_atelier_daily_plan_waits_for_active_session_hydration() -> None:
    source = read_page(ATELIER_PAGE)
    load_start = source.index("Promise.all([")
    load_end = source.index("])", load_start)
    initial_load_block = source[load_start:load_end]

    assert "const loadActiveSession = useCallback" in source
    assert "loadActiveSession(() => alive)" in initial_load_block
    assert "apiService.getAtelierToday()" in initial_load_block
    assert "apiService.getVocabularyDueContext" in initial_load_block
    assert "apiService.getActiveAtelierSession()" in source
    assert "Atelier could not confirm your active session" in source
