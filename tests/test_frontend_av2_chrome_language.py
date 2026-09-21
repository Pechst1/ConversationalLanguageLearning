"""WP-67 — the publication's chrome does not slip back into English.

The design contract splits the app's words in two
(`docs/design-overhaul-2026-08-31.md`): the fiction and the publication chrome
are **French** — «La séance du jour», «Votre dossier», «Reprendre» — while
anything that *explains* something follows the learner's `native_language` and
therefore lives in a copy table, never in a component.

Both halves mean the same thing for an av2 component: **a rendered sentence in
a component is French, or it is not there**. An English sentence in one of these
files is either chrome that was never translated (the defect WP-67 was written
for: `resolveProductTitle` returned `'Settings'` under a French masthead) or an
explanation that belongs in `settings-copy.ts` / `learner_copy.py` instead.

This test is a *guard*, not a repair: when it was written the av2 tree scanned
clean, and its job is to keep it that way. It reads only text a learner can
actually receive —

* text between JSX tags, with `{expressions}` stripped, and
* string literals given to a prop that renders or is announced (`label`,
  `hint`, `title`, `placeholder`, `aria-label`, …), including the object form
  used by Home's `entries` rows —

so identifiers, class names, hrefs, imports and comments are out of scope by
construction. A sentence fails when it contains a word from
:data:`ENGLISH_ONLY_WORDS`: English function words with no French homograph, so
that «question», «sentence», «note», «on», «a», «or», «car», «plus» and the rest
of the shared vocabulary cannot raise a false alarm.

Two deliberate exemptions, both from the contract itself:

* **Réglages** (`pages/settings.tsx`, `lib/settings-copy.ts`) is the
  administrative surface and is written in the learner's own language by design
  (WP-46) — English there is correct, and `tests/test_settings_language.py`
  already guards its own rule, which is that every string is a table key.
* **The gallery and the QA harness** (`pages/atelier-v2-gallery.tsx`,
  `pages/mobile-visual-qa.tsx`) are tooling for us, not a publication for a
  learner.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"

#: Learner-facing av2 surfaces. Components first, then the pages that mount them.
SCANNED_DIRECTORIES = (WEB / "components" / "atelier-v2",)
SCANNED_PAGES = (
    WEB / "pages" / "atelier.tsx",
    WEB / "pages" / "dossier.tsx",
    WEB / "pages" / "repetition.tsx",
    WEB / "pages" / "missions.tsx",
    WEB / "pages" / "notebook.tsx",
    WEB / "pages" / "graphic-novel.tsx",
    WEB / "pages" / "placement.tsx",
)

#: English words that are not also French words. A hit on any of them in a
#: rendered sentence means the sentence is in English.
ENGLISH_ONLY_WORDS = frozenset(
    {
        "the", "your", "you", "with", "and", "this", "that", "from", "have",
        "not", "are", "was", "were", "will", "what", "when", "where", "which",
        "who", "why", "how", "here", "there", "then", "again", "next", "close",
        "open", "save", "cancel", "done", "loading", "settings", "please",
        "try", "answer", "word", "words", "rule", "rules", "level", "day",
        "days", "week", "weeks", "back", "needs", "needed", "choose", "chose",
        "wrong", "right", "about", "before", "after", "still", "only", "every",
        "something", "nothing",
    }
)

#: Props whose string value a learner reads or hears.
TEXT_PROPS = (
    "label",
    "title",
    "hint",
    "body",
    "placeholder",
    "pendingLabel",
    "ariaLabel",
    "aria-label",
    "aria-description",
    "message",
    "caption",
    "summary",
    "heading",
    "kicker",
    "headline",
)

_JSX_TEXT = re.compile(r">([^<>{}]+)<")
_PROP_LITERAL = re.compile(
    r"\b(?:" + "|".join(re.escape(prop) for prop in TEXT_PROPS) + r")\s*[=:]\s*(['\"])(.*?)\1"
)
_WORDS = re.compile(r"[A-Za-zÀ-ÿ']+")


def rendered_strings(source: str) -> list[tuple[int, str]]:
    """Every line-numbered sentence in `source` a learner can receive."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        for match in _JSX_TEXT.finditer(line):
            found.append((number, match.group(1)))
        for match in _PROP_LITERAL.finditer(line):
            found.append((number, match.group(2)))
    return found


def english_words_in(text: str) -> set[str]:
    return {word.lower() for word in _WORDS.findall(text)} & ENGLISH_ONLY_WORDS


def offences(path: Path) -> list[str]:
    reports: list[str] = []
    for number, raw in rendered_strings(path.read_text(encoding="utf-8")):
        text = raw.strip()
        if len(text) < 4:
            continue
        hits = english_words_in(text)
        if hits:
            reports.append(f"{path.relative_to(ROOT)}:{number}: {text[:80]!r} ({', '.join(sorted(hits))})")
    return reports


def scanned_files() -> list[Path]:
    files = [path for directory in SCANNED_DIRECTORIES for path in sorted(directory.rglob("*.tsx"))]
    files.extend(page for page in SCANNED_PAGES if page.exists())
    return files


def test_the_scan_covers_the_av2_surfaces() -> None:
    """A scan that silently stopped finding files would pass for ever."""
    files = scanned_files()
    names = {path.name for path in files}

    assert len(files) > 20
    assert "HomeScreen.tsx" in names
    assert "DossierScreen.tsx" in names
    assert "atelier.tsx" in names


def test_the_scan_would_catch_an_english_chrome_string() -> None:
    """The guard has to fail on the thing it exists to prevent."""
    planted = '<p className="av2-label">Settings</p>\n  <Action label="Close the day" />'

    reports = [text for _, text in rendered_strings(planted) if english_words_in(text)]

    assert len(reports) == 2


def test_the_scan_accepts_the_french_chrome_it_guards() -> None:
    french = (
        '<h1 className="av2-headline">Ce que nous croyons savoir de vous</h1>\n'
        "  <Action pendingLabel=\"Vérification…\">Reprendre la séance</Action>\n"
        "  { id: 'dossier', label: 'Votre dossier', hint: 'D’où vient chaque chiffre.' }"
    )

    assert [text for _, text in rendered_strings(french) if english_words_in(text)] == []


def test_no_english_chrome_in_learner_facing_av2_components() -> None:
    reports: list[str] = []
    for path in scanned_files():
        reports.extend(offences(path))

    assert reports == [], (
        "English sentences on a French publication surface. Chrome is French; an "
        "explanation belongs in a copy table (app/services/learner_copy.py or "
        "web-frontend/lib/settings-copy.ts), not in a component:\n  "
        + "\n  ".join(reports)
    )


def test_reglages_and_the_gallery_are_not_scanned() -> None:
    """The two exemptions are deliberate, so name them in a test."""
    scanned = {path.name for path in scanned_files()}

    assert "settings.tsx" not in scanned
    assert "atelier-v2-gallery.tsx" not in scanned
    assert "mobile-visual-qa.tsx" not in scanned
