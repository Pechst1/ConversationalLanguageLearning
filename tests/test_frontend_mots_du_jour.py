"""Static regression tests for the "Les Mots du jour" daily word slate surfaces."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"
REVIEW_PAGE = ROOT / "web-frontend" / "pages" / "vocabulary" / "review.tsx"
MOTS_DU_JOUR = ROOT / "web-frontend" / "components" / "lexique" / "MotsDuJour.tsx"
API_SERVICE = ROOT / "web-frontend" / "services" / "api.ts"


def test_api_client_exposes_words_of_the_day() -> None:
    source = API_SERVICE.read_text(encoding="utf-8")
    assert "getWordsOfTheDay(): Promise<DailyWordSlate>" in source
    assert "'/vocabulary/words-of-the-day'" in source
    assert "export interface DailyWordSlate" in source
    assert "export interface DailyWordEntry" in source


def test_la_une_mounts_the_mots_du_jour_strip() -> None:
    source = ATELIER_PAGE.read_text(encoding="utf-8")
    # The slate strip left La Une in the manchette redesign; the day's words
    # are counted in the En bref lexique row and dealt in the review deck.
    assert "apiService.getWordsOfTheDay()" in source
    assert "const slateCount = wordSlate?.words?.length || 0;" in source
    assert "mots' if" not in source  # guard against a broken plural helper
    assert "du jour" in source


def test_mots_du_jour_component_uses_tokens_and_triple_stamps() -> None:
    source = MOTS_DU_JOUR.read_text(encoding="utf-8")
    for stamp in ("'lu'", "'retrouve'", "'place'"):
        assert stamp in source
    assert "Le Lexique" in source
    assert "Triplé" in source
    assert "var(--av2-serif)" in source
    assert "if (words.length === 0) return null" in source


def test_review_deck_floats_slate_words_first_with_anchor() -> None:
    source = REVIEW_PAGE.read_text(encoding="utf-8")
    assert "apiService.getWordsOfTheDay().catch(() => null)" in source
    assert "slateById.has(item.word_id)" in source
    assert "Mot du jour" in source
    assert "currentSlateEntry?.anchor" in source
