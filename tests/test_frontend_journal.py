"""WP-30 — the Cahier's journal tab, pinned by source scan.

The web front end has no component-level runner in this repo (the node suites
cover pure `.js` models); the established way to hold a screen's rules down is
a source scan, as `test_frontend_notebook_modes.py` does for the tab shell.

Four rules, and the first is the package:

1. the writing screen renders the cue and never the reveal;
2. the tab is real routing — a `?mode=journal` deep link, a remembered choice,
   a French title — not a button that does nothing;
3. the chrome is av2: French copy, `--av2-*` tokens, pill sentence-case
   actions, no hard-coded colour that would survive into dark mode;
4. a failed correction and a failed load are their own French states, never a
   verdict and never an empty screen.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TAB = Path("web-frontend/components/cahiers/JournalTab.tsx")
CAHIER = Path("web-frontend/components/cahiers/CahierV2.tsx")
NOTEBOOK = Path("web-frontend/pages/notebook.tsx")
API = Path("web-frontend/services/api.ts")


@pytest.fixture(scope="module")
def tab() -> str:
    return TAB.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. the scene is not on the writing screen
# ---------------------------------------------------------------------------


def test_the_writing_branch_renders_the_cue_and_nothing_from_the_reveal(tab: str):
    writing = tab.split("{/* ---- after:")[0]
    assert "cueLine(entry)" in writing
    for leak in ("reveal.setup_fr", "reveal.character_line_fr", "reveal.title_fr"):
        assert leak not in writing, f"the writing screen reads {leak}"


def test_the_reveal_is_rendered_only_under_the_written_branch(tab: str):
    after = tab.split("{entry && written && (")[1]
    assert "entry.reveal.setup_fr" in after
    assert "entry.reveal.character_line_fr" in after
    # And the cue line has no access to the scene at all.
    cue_fn = tab.split("export function cueLine")[1].split("}\n")[0]
    assert "setup" not in cue_fn and "title" not in cue_fn


def test_the_component_never_fetches_the_scene_from_a_second_endpoint(tab: str):
    """One source of scene text, and it is the one the server gates."""
    calls = re.findall(r"api\.(\w+)\(", tab)
    assert set(calls) <= {
        "getJournalState",
        "writeJournalEntry",
        "skipJournalEntry",
        "answerJournalFollowup",
    }, calls


# ---------------------------------------------------------------------------
# 2. the tab is real routing
# ---------------------------------------------------------------------------


def test_the_journal_is_a_cahier_tab_with_a_french_label():
    cahier = CAHIER.read_text(encoding="utf-8")
    assert "journal: 'Journal'" in cahier
    assert "'grammar', 'vocabulary', 'journal', 'releve'" in cahier
    assert "'grammar' | 'vocabulary' | 'journal' | 'releve' | 'library'" in cahier


def test_the_tab_is_deep_linkable_remembered_and_titled_in_french():
    notebook = NOTEBOOK.read_text(encoding="utf-8")
    assert "explicitMode === 'journal'" in notebook
    assert "stored === 'journal'" in notebook
    assert "journal: 'Le Cahier · Le journal de bord'" in notebook
    assert "<JournalTab />" in notebook


def test_the_api_client_carries_the_journal_calls():
    api = API.read_text(encoding="utf-8")
    for method in (
        "getJournalState",
        "writeJournalEntry",
        "skipJournalEntry",
        "answerJournalFollowup",
    ):
        assert f"async {method}(" in api
    assert "'/journal/state'" in api


# ---------------------------------------------------------------------------
# 3. av2 chrome
# ---------------------------------------------------------------------------


def test_the_journal_uses_only_av2_tokens_for_colour(tab: str):
    styles = tab.split("export function JournalStyles")[1]
    assert "--av2-" in styles
    for literal in re.findall(r"#[0-9a-fA-F]{3,8}\b", styles):
        pytest.fail(f"hard-coded colour {literal} would not follow the dark tokens")
    assert "rgb(" not in styles and "rgba(" not in styles


def test_every_action_is_a_pill_in_sentence_case(tab: str):
    """The owner's standing preference: pill buttons, sentence case, never a slab."""
    labels = re.findall(r">\s*([A-ZÀ-Ý][^<>{}\n]{3,60}?)\s*</Action>", tab)
    assert labels, "no action labels found"
    for label in labels:
        # Sentence case: one capital, at the front. Not a shouting ink slab and
        # not Title Case Applied To Every Word.
        assert label == label[0].upper() + label[1:].lower(), label
    assert "av2-btn" not in tab, "actions come from <Action>, not a hand-rolled class"


def test_the_learner_facing_copy_is_french(tab: str):
    for sentence in (
        "De mémoire",
        "La scène reste fermée jusqu’à votre envoi",
        "Envoyer et relire la scène",
        "Passer cette scène",
        "Tout voir",
        "Ce dont vous vous souvenez",
        "La scène, telle qu’elle était",
        "Une semaine plus tard",
    ):
        assert sentence in tab, sentence
    # No English leaked into a learner-visible string.
    assert "Submit" not in tab and "Skip" not in tab


# ---------------------------------------------------------------------------
# 4. failure states
# ---------------------------------------------------------------------------


def test_an_ungraded_entry_says_so_and_is_never_a_verdict(tab: str):
    assert "assessment_status !== 'checked'" in tab
    assert "La correction n’a pas pu être faite. Votre texte est gardé tel quel." in tab
    # The ungraded branch renders a Notice, not the correction block.
    unavailable = tab.split("entry.correction?.assessment_status === 'unavailable' ? (")[1]
    assert unavailable.split(") : (")[0].strip().startswith("<Notice")


def test_a_failed_load_is_a_retryable_french_state_not_an_empty_screen(tab: str):
    assert "Le journal n’a pas pu être ouvert" in tab
    assert "Réessayer" in tab
    assert 'tone="error"' in tab


def test_an_empty_journal_says_when_it_will_have_something(tab: str):
    assert "Rien à raconter aujourd’hui" in tab
    assert "Le journal s’ouvre le lendemain d’une scène" in tab


def test_the_two_verdicts_are_two_blocks_with_two_headings(tab: str):
    assert 'className="av2-label">Le français<' in tab
    assert 'className="av2-label">Ce dont vous vous souvenez<' in tab
    # And the recall sentence never speaks of correctness.
    recall_fn = tab.split("export function recallLine")[1].split("\n}\n")[0]
    assert "faute" not in recall_fn and "correct" not in recall_fn
