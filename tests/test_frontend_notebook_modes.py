"""Static regression tests for the mobile Notebook mode switch."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read_web(path: str) -> str:
    return (WEB / path).read_text(encoding="utf-8")


def read_web_code(path: str) -> str:
    """Source with comments stripped.

    These tests assert that a piece of English copy is *gone* from a surface,
    and the commit that removes a string usually names it in the comment
    explaining why — which would match and fail the assertion.
    """
    source = read_web(path)
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


def test_notebook_entry_remembers_last_mode() -> None:
    entry = read_web("pages/notebook.tsx")

    assert "NOTEBOOK_MODE_STORAGE_KEY" in entry
    assert "window.localStorage.getItem" in entry
    assert "router.push(" in entry
    assert "queryForMode(router.query, resolvedMode)" in entry
    # The mode switch is the Atelier V2 segmented pill (Règles · Mots · Relevé).
    assert "<NotebookModeTabs" in entry
    assert "onSelect={switchMode}" in entry
    assert "rememberNotebookMode(nextMode)" in entry


def test_notebook_switch_links_grammar_and_vocabulary_while_story_library_is_hidden() -> None:
    flags = read_web("launch-flags.json")
    switch = read_web("components/mobile/NotebookModeSwitch.tsx")

    assert '"storyFeatureVisible": false' in flags
    assert "atelier:notebook-mode" in switch
    assert 'href="/grammar"' in switch
    assert 'href="/vocabulary"' in switch
    assert "{STORY_FEATURE_VISIBLE && (" in switch
    assert 'href="/notebook?mode=library"' in switch
    # Drawn as the design's segmented pill on the V2 tokens, no hex.
    assert ".av2.notebook-mode-switch" in switch
    assert "background: var(--av2-line);" in switch
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", switch)
    assert "rememberNotebookMode('grammar')" in switch
    assert "rememberNotebookMode('vocabulary')" in switch
    assert "rememberNotebookMode('library')" in switch


def test_notebook_library_mode_is_parked_behind_story_launch_flag() -> None:
    notebook = read_web("pages/notebook.tsx")
    api = read_web("services/api.ts")

    assert "STORY_FEATURE_VISIBLE && stored === 'library'" in notebook
    assert "STORY_FEATURE_VISIBLE && explicitMode === 'library'" in notebook
    assert "STORY_FEATURE_VISIBLE && firstQueryValue(query.book)" in notebook
    assert "!STORY_FEATURE_VISIBLE && requestedMode === 'library'" in notebook
    assert "const visibleMode = !STORY_FEATURE_VISIBLE && mode === 'library' ? 'grammar' : mode" in notebook
    # The Bibliothèque mode tab appears only when the story launch flag is on.
    assert "library={STORY_FEATURE_VISIBLE}" in notebook
    assert "mode === 'library'" in notebook
    assert "function LibraryNotebookSurface" in notebook
    assert "api.getLibraryBooks()" in notebook
    assert "api.getLibraryBook(targetId)" in notebook
    assert "api.getLibraryEpisode(book.id" in notebook
    assert "api.completeLibraryEpisode(selectedBook.id" in notebook
    assert "function LibraryEpisodeExerciseRunner" in notebook
    assert "<ExerciseShell" in notebook
    assert "<FeedbackSheet" in notebook
    assert "async getLibraryBooks()" in api
    assert "async getLibraryEpisode" in api


def test_grammar_and_vocabulary_pages_share_notebook_switch() -> None:
    grammar = read_web("pages/grammar.tsx")
    vocabulary = read_web("pages/vocabulary.tsx")

    # The direct /grammar route carries the same Cahier head as /notebook, with
    # the pill tabs as links to the sibling registers; the embedded view
    # inherits the shell's tabs.
    assert '<NotebookModeTabs active="grammar" hrefFor={standaloneHref} />' in grammar
    assert "if (mode === 'vocabulary') return '/vocabulary';" in grammar
    assert "embedded" in grammar

    assert 'route="Vocabulaire"' in vocabulary
    assert 'xlink="Grammaire"' in vocabulary
    assert 'xlinkHref="/grammar"' in vocabulary
    assert "embedded" in vocabulary


def test_primary_notebook_nav_uses_smart_entrypoint() -> None:
    masthead = read_web("components/layout/EditorialMasthead.tsx")
    phone_nav = read_web("components/layout/PhoneProductNav.tsx")
    layout = read_web("components/layout/Layout.tsx")

    assert 'href="/notebook">Cahier</Link>' in masthead
    assert "<PhoneProductNav active={mobileSection} />" in masthead
    assert "PHONE_PRODUCT_TABS.map" in phone_nav
    assert "href={item.href}" in phone_nav
    assert "routeUsesOwnProductShell(router.pathname)" in layout


def test_cahier_word_detail_sheet_speaks_french() -> None:
    """The registre row opened a fully English sheet inside the French Cahier.

    Every string below was English on a publication surface: the flashcard
    faces, the section heads, the placeholders and the three handoff buttons.
    """
    page = read_web_code("pages/vocabulary.tsx")

    for gone in (
        "Progress / SRS",
        "Recent context will appear after use.",
        "Examples by source",
        "Recent traces",
        "Word biography",
        "Use in mission",
        "Read in Feuilleton",
        "Tap card to flip",
        "translation pending",
        "traduction à venir",
    ):
        assert gone not in page, gone

    for present in ("Touche pour retourner", "Sens · touche pour revenir", "Le suivi", "Traces récentes", "La biographie du mot"):
        assert present in page, present


def test_cahier_word_rows_use_the_resolved_gloss_not_a_language_guess() -> None:
    """`german_translation ||  english_translation || …` served German to everyone.

    The server resolves the gloss for the signed-in learner and sends it as
    `translation`; the page must read it through the shared helper instead of
    re-picking a language of its own (see web-frontend/lib/glosses.ts).
    """
    page = read_web_code("pages/vocabulary.tsx")

    assert "item.german_translation || item.english_translation" not in page
    assert "learnerGloss(item)" in page


def test_cahier_hides_scheduler_internals_and_guessed_parts_of_speech() -> None:
    """Stability/difficulty/retrievability are corrector internals, not learner copy.

    `part_of_speech` on the imported deck is a heuristic guess (élire is filed
    as an adjective), stored as an English key, sometimes literally "x" — so it
    is printed as a French label only when it is a value we recognise, and the
    old `|| 'French'` fallback that printed "French" as a part of speech is gone.
    """
    page = read_web_code("pages/vocabulary.tsx")

    for internal in ("'Stability'", "'Retrievability'", "'Scheduler'", "'Priority'"):
        assert internal not in page, internal
    assert "word?.part_of_speech || 'French'" not in page
    assert "partOfSpeechLabel" in page
    assert "PART_OF_SPEECH_LABELS" in page


def test_grammar_fiche_handoff_seats_the_rule_in_the_atelier() -> None:
    """"Composer à l'Atelier" was a bare /atelier link.

    /atelier reads `concept_id` from the query and posts it as
    `preferred_concept_id`, which seats the rule as the fragile concept; without
    it the fiche's CTA opened the generic scheduled séance instead.
    """
    page = read_web_code("pages/grammar.tsx")

    assert "/atelier?concept_id=${concept.id}" in page
    assert 'NcCta href="/atelier"' not in page
    # Generator keys ("si", "future", "imperative") are internal inventory.
    assert "nc-exercisetags" not in page


def test_conjugation_drill_is_french_and_reachable() -> None:
    """The drill ran, scheduled itself, and had no inbound link anywhere."""
    drill = read_web_code("pages/vocabulary/conjugation.tsx")
    registre = read_web_code("pages/vocabulary.tsx")

    for gone in ("Irregular forms", "Coverage map", "Reveal table", "Type the form", "Retry"):
        assert gone not in drill, gone
    assert "Les formes irrégulières" in drill
    assert 'href="/vocabulary/conjugation"' in registre
