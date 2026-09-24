"""WP-30 — the Cahier's journal tab, pinned by source scan.

The web front end has no component-level runner in this repo (the node suites
cover pure `.js` models); the established way to hold a screen's rules down is
a source scan, as `test_frontend_notebook_modes.py` does for the tab shell.

Four rules, and the first is the package:

1. the writing screen renders the cue and never the reveal;
2. the tab is real routing — a `?mode=journal` deep link, a remembered choice,
   a French title — not a button that does nothing;
3. the chrome is av2: `--av2-*` tokens, pill sentence-case actions, no
   hard-coded colour that would survive into dark mode — and, since WP-82, its
   words live in `cahier-copy.ts` (the learner's language up to A2, French from
   B1), whose French column keeps the wording pinned here;
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
COPY = Path("web-frontend/components/cahiers/cahier-copy.ts")


@pytest.fixture(scope="module")
def tab() -> str:
    return TAB.read_text(encoding="utf-8")


def _table(language: str) -> str:
    """One language's column of the Cahier copy table, as source text."""
    copy = COPY.read_text(encoding="utf-8")
    starts = {"fr": "const FR = {", "en": "const EN: CahierCopy = {", "de": "const DE: CahierCopy = {"}
    ends = {"fr": "export type CahierCopy", "en": "const DE: CahierCopy", "de": "const TABLES"}
    return copy[copy.index(starts[language]):copy.index(ends[language])]


def _journal(language: str) -> str:
    table = _table(language)
    return table[table.index("  journal: {"):table.index("  legacy: {")]


@pytest.fixture(scope="module")
def french() -> str:
    """The journal's French chrome: the wording this file was written to protect."""
    return _journal("fr")


def _value(section: str, key: str) -> str:
    match = re.search(rf"^\s+{key}: '(.*)',$", section, re.M)
    assert match, key
    return match.group(1)


# ---------------------------------------------------------------------------
# 1. the scene is not on the writing screen
# ---------------------------------------------------------------------------


def test_the_writing_branch_renders_the_cue_and_nothing_from_the_reveal(tab: str):
    writing = tab.split("{/* ---- after:")[0]
    assert "cueLine(entry, t)" in writing
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
    assert "journal: 'mode_journal'" in cahier
    assert "mode_journal: 'Journal'" in _table("fr")
    assert "'grammar', 'vocabulary', 'journal', 'releve'" in cahier
    assert "'grammar' | 'vocabulary' | 'journal' | 'releve' | 'library'" in cahier


def test_the_tab_is_deep_linkable_remembered_and_titled_in_french():
    notebook = NOTEBOOK.read_text(encoding="utf-8")
    assert "explicitMode === 'journal'" in notebook
    assert "stored === 'journal'" in notebook
    assert "journal: 'title_journal'" in notebook
    assert "title_journal: 'Le Cahier · Le journal de bord'" in _table("fr")
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
    keys = re.findall(r">\s*\{(?:showAll \? )?t\.(\w+)(?: : t\.(\w+))?\}\s*</Action>", tab)
    keys = [key for pair in keys for key in pair if key]
    assert keys, "no action labels found"
    # German capitalises its nouns, so the sentence-case check reads the French
    # and English columns; the German one must at least never shout.
    for language in ("fr", "en"):
        section = _journal(language)
        for key in keys:
            label = _value(section, key)
            # Sentence case: one capital, at the front. Not a shouting ink slab
            # and not Title Case Applied To Every Word.
            assert label == label[0].upper() + label[1:].lower(), (language, label)
    for key in keys:
        label = _value(_journal("de"), key)
        assert label != label.upper(), label
    assert "av2-btn" not in tab, "actions come from <Action>, not a hand-rolled class"


def test_the_learner_facing_copy_is_french(tab: str, french: str):
    # Comments may name the copy they describe; only shipped code counts.
    code = re.sub(r"\{?/\*.*?\*/\}?", "", tab, flags=re.S)
    for sentence in (
        # WP-45 re-pins the writing state on `Journal.dc.html`: the headline is
        # the screen's name, the primary is one word, and the scene-stays-shut
        # promise moved to the foot caption under it.
        "Le journal de bord",
        "Hier, en français",
        "Relire la scène après l’envoi",
        "Envoyer",
        "Passer cette scène",
        "Tout voir",
        "Ce dont vous vous souvenez",
        "La scène, telle qu’elle était",
        "Une semaine plus tard",
    ):
        assert sentence in french, sentence
        assert sentence not in code, f"inline chrome: {sentence}"
    # No English leaked into a learner-visible string.
    assert "Submit" not in tab and "Skip" not in tab


# ---------------------------------------------------------------------------
# 4. failure states
# ---------------------------------------------------------------------------


def test_an_ungraded_entry_says_so_and_is_never_a_verdict(tab: str, french: str):
    assert "assessment_status !== 'checked'" in tab
    assert "return t.correction_unavailable;" in tab
    assert "La correction n’a pas pu être faite. Votre texte est gardé tel quel." in french
    # The ungraded branch renders a Notice, not the correction block.
    unavailable = tab.split("entry.correction?.assessment_status === 'unavailable' ? (")[1]
    assert unavailable.split(") : (")[0].strip().startswith("<Notice")


def test_a_failed_load_is_a_retryable_french_state_not_an_empty_screen(tab: str, french: str):
    assert "title={t.load_failed_title}" in tab
    assert "Le journal n’a pas pu être ouvert" in french
    assert "label: copy.cahier.retry" in tab
    assert "retry: 'Réessayer'" in _table("fr")
    assert 'tone="error"' in tab


def test_an_empty_journal_says_when_it_will_have_something(tab: str, french: str):
    assert "title={t.empty_title}" in tab
    assert "Rien à raconter aujourd’hui" in french
    assert "Le journal s’ouvre le lendemain d’une scène" in french


def test_the_two_verdicts_are_two_blocks_with_two_headings(tab: str, french: str):
    assert 'className="av2-label">{t.french_label}<' in tab
    assert 'className="av2-label">{t.recall_label}<' in tab
    assert "french_label: 'Le français'" in french
    assert "recall_label: 'Ce dont vous vous souvenez'" in french
    # And the recall sentence never speaks of correctness.
    recall_fn = tab.split("export function recallLine")[1].split("\n}\n")[0]
    assert "faute" not in recall_fn and "correct" not in recall_fn
    for key in ("recall_unscored", "recall_all", "recall_none", "recall_some"):
        assert "faute" not in _value(french, key) and "correct" not in _value(french, key)


# ---------------------------------------------------------------------------
# 5. WP-45 — the writing state on `Journal.dc.html` + canvas note «note-pied»
# ---------------------------------------------------------------------------


def test_the_writing_state_carries_its_action_in_a_foot_below_the_body(tab: str):
    """At 390x844 the Cahier sits under a fixed four-tab bar, so the entry's
    action has to be the last thing in the flow and the flow has to reserve the
    bar's height."""
    writing = tab.split("{/* ---- after:")[0]
    body = writing.index('className="jn-write"')
    foot = writing.index('className="jn-foot"')
    assert body < foot, "the foot comes after the body in the DOM"
    assert "@media (max-width: 760px)" in tab
    assert "padding-bottom: var(--phone-bottom-nav-space, 0px);" in tab


def test_the_story_label_reads_when_where_who(tab: str, french: str):
    """«Hier · Le Mistral · avec Augustin», and in the story blue."""
    assert 'className="av2-label av2-label--story">{cueLine(entry, t)' in tab
    cue_fn = tab.split("export function cueLine")[1].split("}\n")[0]
    assert "[when, where || null, who ? fill(t.with, { name: who }) : null]" in cue_fn
    assert "t.yesterday" in cue_fn
    assert "yesterday: 'Hier'" in french
    assert "with: 'avec {name}'" in french


def test_the_entry_field_is_the_shared_control_drawn_150px_tall(tab: str, french: str):
    assert "label: t.field_label" in tab
    assert "field_label: 'Hier, en français'" in french
    assert 'className="jn-entry-field"' in tab
    assert re.search(
        r"\.av2 \.jn-entry-field \.av2-field__control \{ min-height: 150px; \}", tab
    )


def test_the_dashed_note_states_both_promises(tab: str, french: str):
    """One correction in the foreground, and the +7-day line."""
    writing = tab.split("{/* ---- after:")[0]
    assert '<p className="jn-hint">{t.hint}</p>' in writing
    hint = _value(french, "hint")
    assert "Une seule correction en avant, la liste complète sur demande." in hint
    assert "Dans une semaine," in hint and "redemandera cette scène" in hint


def test_the_foot_caption_is_not_a_control(tab: str, french: str):
    """«Relire la scène après l'envoi» describes what Envoyer does; there is
    nothing to press, so it must not be drawn as a button."""
    assert '<p className="jn-foot__note">{t.foot_note}</p>' in tab
    assert "{t.foot_note}</Action>" not in tab
    assert "foot_note: 'Relire la scène après l’envoi'" in french
