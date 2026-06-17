"""Static regression tests for the mobile Notebook mode switch."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read_web(path: str) -> str:
    return (WEB / path).read_text(encoding="utf-8")


def test_notebook_entry_remembers_last_mode() -> None:
    entry = read_web("pages/notebook.tsx")

    assert "NOTEBOOK_MODE_STORAGE_KEY" in entry
    assert "window.localStorage.getItem" in entry
    assert "router.push(" in entry
    assert "queryForMode(router.query, nextMode)" in entry
    assert "<NotebookModeSwitch" in entry


def test_notebook_switch_links_grammar_vocabulary_and_library() -> None:
    switch = read_web("components/mobile/NotebookModeSwitch.tsx")

    assert "atelier:notebook-mode" in switch
    assert 'href="/grammar"' in switch
    assert 'href="/vocabulary"' in switch
    assert 'href="/notebook?mode=library"' in switch
    assert "rememberNotebookMode('grammar')" in switch
    assert "rememberNotebookMode('vocabulary')" in switch
    assert "rememberNotebookMode('library')" in switch


def test_notebook_library_mode_fetches_books_and_episode() -> None:
    notebook = read_web("pages/notebook.tsx")
    api = read_web("services/api.ts")

    assert "mode === 'library'" in notebook
    assert "function LibraryNotebookSurface" in notebook
    assert "api.getLibraryBooks()" in notebook
    assert "api.getLibraryBook(targetId)" in notebook
    assert "api.getLibraryEpisode(book.id" in notebook
    assert "api.completeLibraryEpisode(selectedBook.id" in notebook
    assert "function LibraryEpisodeExerciseRunner" in notebook
    assert "<ExerciseShell" in notebook
    assert "<FeedbackSheet" in notebook
    assert 'href="/serial">Serial archive</Link>' in notebook
    assert 'href="/missions">Past missions</Link>' in notebook
    assert "async getLibraryBooks()" in api
    assert "async getLibraryEpisode" in api


def test_grammar_and_vocabulary_pages_share_notebook_switch() -> None:
    grammar = read_web("pages/grammar.tsx")
    vocabulary = read_web("pages/vocabulary.tsx")

    assert "NotebookModeSwitch" in grammar
    assert 'active="grammar"' in grammar
    assert 'href="/notebook?mode=vocabulary">Words</Link>' in grammar

    assert "NotebookModeSwitch" in vocabulary
    assert 'active="vocabulary"' in vocabulary
    assert 'href="/grammar">Rules</Link>' in vocabulary


def test_primary_notebook_nav_uses_smart_entrypoint() -> None:
    masthead = read_web("components/layout/EditorialMasthead.tsx")
    layout = read_web("components/layout/Layout.tsx")

    assert 'href="/notebook">Notebook</Link>' in masthead
    assert "PHONE_PRODUCT_TABS.map" in masthead
    assert "href={item.href}" in masthead
    assert "routeUsesOwnProductShell(router.pathname)" in layout
