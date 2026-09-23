"""Static regression tests for vocabulary biography surfaces."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY_PAGE = ROOT / "web-frontend" / "pages" / "vocabulary.tsx"
VOCABULARY_REVIEW_PAGE = ROOT / "web-frontend" / "pages" / "vocabulary" / "review.tsx"
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"
VISUAL_CUES_LIB = ROOT / "web-frontend" / "lib" / "visual-cues.ts"
ATELIER_COPY_LIB = ROOT / "web-frontend" / "lib" / "atelier-v2-copy.ts"
# WP-82: the Lexique pages read their chrome from one copy table, in the chrome
# language (the learner's own up to A2, French from B1).
LEXIQUE_COPY = ROOT / "web-frontend" / "components" / "lexique" / "lexique-copy.ts"


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
    # SRS", "Recent context will appear after use."). Pin the French label,
    # now in the Lexique copy table's French column (WP-82).
    assert "{t.action_biography}" in source
    assert "action_biography: 'La biographie du mot'" in read_page(LEXIQUE_COPY)
    assert "open={Boolean(biographyWordId)}" in source


def test_vocabulary_notebook_loads_biography_endpoint() -> None:
    source = read_vocabulary_page()

    assert "apiService.getVocabularyBiography(biographyWordId)" in source
    assert "setBiography(nextBiography)" in source
    # French replaces the English failure copy (see above); WP-82 reads it
    # from the Lexique copy table in the chrome language.
    assert "error={biographyError ? t.biography_failed : null}" in source
    assert "biography_failed: 'La biographie de ce mot n\u2019a pas pu \u00eatre ouverte.'" in read_page(LEXIQUE_COPY)
    assert "setBiographyWordId(null)" in source


def test_vocabulary_review_keeps_anki_flow_and_exposes_history() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)

    assert "WordBiographySheet" in source
    assert "const [biographyOpen, setBiographyOpen]" in source
    assert "apiService.getVocabularyBiography(current.word_id)" in source
    copy = read_page(LEXIQUE_COPY)
    assert "title={t.story_title}" in source
    assert "story_title: 'L’histoire du mot'" in copy
    assert "queueExample(current)" in source
    assert "exampleTranslation" in source
    # The design's side labels: "Touche pour retourner" / "Sens · touche pour
    # revenir" — in the copy table's French column since WP-82.
    assert "revealed ? t.flip_back : t.flip_front" in source
    assert "flip_front: 'Touche pour retourner'" in copy
    assert "flip_back: 'Sens · touche pour revenir'" in copy
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
    assert "plural(t, 'cards', sessionRemaining)" in source
    assert "cards_many: '{n} cartes'" in read_page(LEXIQUE_COPY)
    assert "remainingSummary.due" in source
    assert "refreshQueueSummary" not in source
    assert "const handleRatingClick" in source
    assert "disabled={reviewing}" in source
    assert "disabled={reviewing || !revealed}" not in source
    assert "t.reveal_before" in source
    assert "reveal_before: 'Révéler la réponse avant de noter'" in read_page(LEXIQUE_COPY)
    assert ">Deck</Link>" not in source


def test_vocabulary_review_uses_local_visual_cues_before_generated_images() -> None:
    source = read_page(VOCABULARY_REVIEW_PAGE)
    cues = read_page(VISUAL_CUES_LIB)

    assert "function wordVisualCue" in source
    # Icon sets are gone: the cue carries one of the four Bauhaus shapes.
    assert "lucide-react" not in source
    assert "shape: VisualCueShape" in cues
    assert "'abaisser'" in cues
    assert "review-visual-cue" in source
    # WP-21: the badge was English ("WORD / MEMORY CUE", "TIME / when"), then
    # French-only, which left a beginner reading French on the one card that
    # teaches French. The scene name explains the word, so it follows the
    # learner's language through `lib/visual-cues.ts`. WP-82: it and the
    # chrome around it (the aria prefix) follow the one chrome language — the
    # learner's up to A2, French from B1 — so the card never mixes two. The
    # caption still does not echo `part_of_speech` — that column is heuristic
    # import data and printed "exemplaire" (a noun) as a verb.
    assert "aria-label={fill(t.cue_aria, { label: visualCue.label })}" in source
    assert "cue_aria: 'Indice visuel : {label}'" in read_page(LEXIQUE_COPY)
    assert "visualCueFor(signal, hasSignal, language)" in source
    assert "wordVisualCue(current, language)" in source
    assert "const language = useChromeLanguage();" in source
    assert "fr: { label: 'Temps', caption: 'quand' }" in cues
    assert "en: { label: 'Time', caption: 'when' }" in cues
    assert "de: { label: 'Zeit', caption: 'wann' }" in cues
    # The hint line prints the column only through the whitelist (labelled in
    # the chrome language, WP-82).
    assert "partOfSpeechLabel(t, item.part_of_speech)" in source
    assert "export const PART_OF_SPEECH_LABELS" in read_page(LEXIQUE_COPY)


def test_vocabulary_review_mic_failures_follow_the_learner_language() -> None:
    """The deck's microphone toasts were French for every learner (WP-21).

    WP-82: they follow the deck's one chrome language (the learner's own up to
    A2, French from B1), like every other word of chrome on the card.
    """
    source = read_page(VOCABULARY_REVIEW_PAGE)
    copy = read_page(ATELIER_COPY_LIB)

    assert "const chrome = atelierChrome(language);" in source
    for key in ("mic_unavailable", "mic_open_failed", "transcription_failed", "transcription_empty"):
        assert f"chrome.{key}" in source, key
        # One entry per shipped language, plus the union member.
        assert copy.count(f"{key}:") == 3, key
    assert "La transcription a échoué." not in source
    assert "Le micro n’a pas pu être ouvert.'" not in source


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
    copy = read_page(LEXIQUE_COPY)
    assert "{t.atlas_title}" in source
    assert "atlas_title: 'Atlas des acquis'" in copy
    assert "setAtlasOpen((open) => !open)" in source
    assert "cefr_title: 'Couverture CECR'" in copy
    assert "<LxTrack" in source
    assert "<LxMasteryMap" in source
    assert "map_title: 'Carte de maîtrise — Français 5000'" in copy
    assert "registre_title: 'Registre des mots — Français 5000'" in copy
    # The old English dashboard labels are gone.
    for gone in ("Choose a set to master", "Verbs & conjugation", "Grammar patterns"):
        assert gone not in source, gone
        assert gone not in copy, gone


def test_atelier_daily_session_surfaces_target_vocabulary_in_context() -> None:
    source = read_page(ATELIER_PAGE)

    assert "session.target_vocabulary" in source
    assert "target-word-strip" in source
    assert "aria-label={t.produce_words_label}" in source
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
    assert "ATELIER_CONFIRM_NEEDED_NOTICE: AtelierErrorNotice = { kind: 'confirm_needed' }" in source
    errors = (Path(__file__).resolve().parents[1] / "web-frontend" / "lib" / "atelier-errors.ts").read_text(encoding="utf-8")
    assert "La séance en cours n’a pas pu être confirmée." in errors
