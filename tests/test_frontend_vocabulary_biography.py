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
    assert "Tap card to reveal answer" in source
    assert "setRevealed((value) => !value)" in source
    assert "reviewOptions.map" in source


def test_atelier_daily_session_surfaces_target_vocabulary_in_context() -> None:
    source = read_page(ATELIER_PAGE)

    assert "function VocabularyFocus" in source
    assert "session.target_vocabulary" in source
    assert "target-word-strip" in source
    assert 'aria-label="Vocabulary targets for this paragraph"' in source
    assert "vocabularyTranslation(item)" in source
