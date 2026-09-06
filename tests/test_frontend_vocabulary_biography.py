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
    # Was "Word biography": the Cahier is a French publication surface, and the
    # whole word-detail sheet was still in English (PROMPT/ANSWER, "Progress /
    # SRS", "Recent context will appear after use."). Pin the French label.
    assert "La biographie du mot" in source
    assert "open={Boolean(biographyWordId)}" in source


def test_vocabulary_notebook_loads_biography_endpoint() -> None:
    source = read_vocabulary_page()

    assert "apiService.getVocabularyBiography(biographyWordId)" in source
    assert "setBiography(nextBiography)" in source
    # French replaces the English failure copy (see above).
    assert "La biographie de ce mot n\u2019a pas pu \u00eatre ouverte." in source
    assert "setBiographyWordId(null)" in source


def test_vocabulary_review_keeps_anki_flow_and_exposes_history() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "WordBiographySheet" in source
    assert "const [biographyOpen, setBiographyOpen]" in source
    assert "apiService.getVocabularyBiography(current.word_id)" in source
    assert "L’histoire du mot" in source
    assert "queueExample(current)" in source
    assert "exampleTranslation" in source
    # The design's side labels: "Touche pour retourner" / "Sens · touche pour revenir".
    assert "Touche pour retourner" in source
    assert "Sens · touche pour revenir" in source
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

    # The word is the one Garamond-italic headline; every card colour comes
    # from the --av2 tokens (card face front, yellow back).
    assert "review-prompt-term" in source
    assert ".av2 .lx-card__word" in source
    assert "--lx-card-face: var(--av2-yellow);" in source
    assert "review-answer-word" in source
    assert "review-context-anchor" in source


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
    # Design: the word at 46px, in rem so the text-size setting moves it.
    assert "font-size: 2.875rem; /* design 46px */" in source
    assert "const sessionRemaining = remainingItems.length" in source
    assert "${sessionRemaining} ${sessionRemaining > 1 ? 'cartes' : 'carte'}" in source
    assert "remainingSummary.due" in source
    assert "refreshQueueSummary" not in source
    assert "const handleRatingClick" in source
    assert "disabled={reviewing}" in source
    assert "disabled={reviewing || !revealed}" not in source
    assert "Révéler la réponse avant de noter" in source
    assert ">Deck</Link>" not in source


def test_vocabulary_review_uses_local_visual_cues_before_generated_images() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "function wordVisualCue" in source
    # Icon sets are gone: the cue carries one of the four Bauhaus shapes.
    assert "lucide-react" not in source
    assert "shape: ShapeKind" in source
    assert "abaisser" in source
    assert "review-visual-cue" in source
    # The badge is French publication copy now: the labels were the last
    # English on the card ("WORD / MEMORY CUE", "TIME / when"), and the caption
    # no longer echoes `part_of_speech` — that column is heuristic import data
    # and printed "exemplaire" (a noun) as a verb.
    assert "aria-label={`Indice visuel : ${visualCue.label}`}" in source
    assert "label: 'Temps', caption: 'quand'" in source
    # The hint line prints the column only through the French whitelist.
    assert "partOfSpeechLabel(item.part_of_speech)" in source
    assert "PART_OF_SPEECH_LABELS" in source


def test_vocabulary_review_back_face_keeps_answer_content_visible() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "FSRS · {current.bucket}" not in source
    assert 'className="lx-card__middle review-answer-container"' in source
    # The back face is the yellow reward surface; the example sits on it.
    assert ".av2 .lx-card[data-face='back'] {" in source
    assert "{revealed && visibleExample && (" in source
    assert "overflow-wrap: anywhere;" in source


def test_vocabulary_notebook_uses_compact_coverage_snapshot() -> None:
    source = read_vocabulary_page()

    # The coverage atlas is a progressive-disclosure fold in the Cahiers design:
    # collapsed by default, revealing CEFR / topic / verb coverage tracks and
    # the Français 5000 mastery map when opened.
    assert "Atlas des acquis" in source
    assert "setAtlasOpen((open) => !open)" in source
    assert "Couverture CECR" in source
    assert "<LxTrack" in source
    assert "<LxMasteryMap" in source
    assert "Carte de maîtrise — Français 5000" in source
    assert "Registre des mots — Français 5000" in source
    # The old English dashboard labels are gone.
    assert "Choose a set to master" not in source
    assert "Verbs & conjugation" not in source
    assert "Grammar patterns" not in source


def test_atelier_daily_session_surfaces_target_vocabulary_in_context() -> None:
    source = read_page(ATELIER_PAGE)

    assert "session.target_vocabulary" in source
    assert "target-word-strip" in source
    assert 'aria-label="Lexique visé pour ce paragraphe"' in source
    assert "vocabularyTranslation(item)" in source


def test_atelier_today_surfaces_vocabulary_training_step() -> None:
    source = read_page(ATELIER_PAGE)

    # On the La Une front page the vocabulary review path is the "Le Lexique"
    # article, which routes to /vocabulary/review when words are due.
    assert "vocabularyReviewDue" in source
    # The lexique is one of the three Home tiles since the Claude design.
    assert "<HomeScreen" in source
    assert "id: 'lexique'" in source
    assert "href: '/vocabulary/review'" in source


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
    assert "L’Atelier n’a pas pu confirmer la séance en cours" in source
