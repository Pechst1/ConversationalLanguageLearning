"""WP-46 — Réglages reads in the learner's native language.

Owner decision, 2026-09-17: the app's chrome is French on every *product*
screen (WP-43, `CHROME_KEYS`) — the learner came to read a French publication
and its furniture is part of that. Réglages is the exception, because it is not
a product screen: it is the administrative surface, where a learner changes the
address they sign in with and reads what «suppression définitive» removes. None
of that teaches French, and all of it has to be understood *before* the learner
acts.

The page is auth-gated and the preview cannot render an authenticated route, so
these tests read the source. They pin two things a copy-table unit test cannot:
that the page actually renders through the table, and that no French sentence
was left behind in it — a leftover is exactly the bug this work package exists
to remove, and it is invisible to a German learner's reviewer who reads French.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web-frontend"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


PAGE = "pages/settings.tsx"
COPY = "lib/settings-copy.ts"


# ---------------------------------------------------------------------------
# 1. The table exists and is complete in three languages
# ---------------------------------------------------------------------------

def test_the_copy_table_exists_and_covers_three_languages() -> None:
    copy = _source(COPY)
    assert "export function settingsCopy(" in copy
    assert "export function resolveSettingsLanguage(" in copy
    for table in ("const EN: SettingsCopy = {", "const DE: SettingsCopy = {", "const FR: SettingsCopy = {"):
        assert table in copy, table
    # The behavioural contract — identical keys, no blanks, English fallback —
    # is pinned by lib/settings-copy.test.js, which is wired into CI.
    assert '"test:settings-copy": "node --test lib/settings-copy.test.js"' in _source("package.json")
    assert "npm run test:settings-copy" in (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_the_three_tables_hold_the_same_keys() -> None:
    """A key missing from one table is a blank row for that learner."""

    copy = _source(COPY)
    tables = {}
    for name in ("EN", "DE", "FR"):
        body = copy.split(f"const {name}: SettingsCopy = {{", 1)[1].split("\n};", 1)[0]
        tables[name] = set(re.findall(r"^  ([a-z0-9_]+):", body, flags=re.M))
    assert len(tables["EN"]) > 100, f"expected the whole screen, got {len(tables['EN'])}"
    assert tables["EN"] == tables["DE"] == tables["FR"]


# ---------------------------------------------------------------------------
# 2. The page renders through it, and chooses the learner's language
# ---------------------------------------------------------------------------

def test_the_page_renders_through_the_table() -> None:
    page = _source(PAGE)
    assert "from '@/lib/settings-copy'" in page
    assert "const copy = settingsCopy(copyLanguage);" in page
    # Every section title, and the page's own furniture.
    for key in (
        "copy.page_title", "copy.headline", "copy.page_label",
        "copy.section_profile", "copy.section_learning", "copy.section_practice",
        "copy.section_notifications", "copy.section_appearance",
        "copy.section_audio", "copy.section_privacy",
        "copy.action_save", "copy.pending_save",
    ):
        assert key in page, key


def test_the_language_is_the_learners_and_never_flickers() -> None:
    """French is rendered only when the learner's own language is French.

    The account's answer is what selects the table, and until it arrives the
    page says so: `nativeLanguageKnown` is false and `resolveSettingsLanguage`
    answers English for an unknown language. A pre-hydration French default that
    then swapped would be the exact failure this pins against.
    """

    page = _source(PAGE)
    assert "const [nativeLanguageKnown, setNativeLanguageKnown] = useState(false);" in page
    assert "setNativeLanguageKnown(true);" in page
    assert "nativeLanguageKnown ? settings.nativeLanguage : null," in page
    # The design-system root follows the same choice, so the chrome around the
    # copy cannot disagree with it.
    assert page.count("language={copyLanguage}") == 3
    assert "language={settings.nativeLanguage}" not in page

    copy = _source(COPY)
    # …and the resolver's own fallback order is native → control → English.
    resolver = copy.split("export function resolveSettingsLanguage(", 1)[1]
    assert "return normalizeSettingsLanguage(nativeLanguage);" in resolver
    assert "return 'en';" in resolver


# ---------------------------------------------------------------------------
# 3. Nothing French was left behind in the page
# ---------------------------------------------------------------------------

# Words that are data or proper nouns, not copy:
#  - the interest topics are the *values* stored in `interests` and sent to the
#    server, not labels (changing them would change what the newsroom selects);
#  - "L’Atelier" and "Réglages" name the product and its route.
ALLOWED_FRENCH = {
    "technologie", "travail", "voyage", "sport", "politique", "sciences",
    "culture", "économie", "santé", "cuisine",
    "Atelier", "Réglages", "L’Atelier",
}

FRENCH_LETTERS = "àâçéèêëîïôûùüÿœÀÂÇÉÈÊËÎÏÔÛÙÜŒ«»"


def _strip_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return re.sub(r"^\s*//.*$", "", code, flags=re.M)


def test_no_french_sentence_is_left_in_the_page() -> None:
    """Every accented line in the page is a comment, a token, or an allowed value.

    A French string that never reached the table would render in French for a
    German learner and no other test would notice, because the page still
    *looks* right to a French reader.
    """

    code = _strip_comments(_source(PAGE))
    offenders = []
    for line in code.splitlines():
        if not any(letter in line for letter in FRENCH_LETTERS):
            continue
        stripped = line.strip().strip(",").strip("'\"")
        if stripped in ALLOWED_FRENCH:
            continue
        offenders.append(line.strip())
    assert offenders == [], offenders


def test_the_page_holds_no_bare_french_labels_or_hints() -> None:
    """Labels, hints, placeholders and aria-labels are expressions, not literals."""

    code = _strip_comments(_source(PAGE))
    offenders = re.findall(
        r'(?:label|hint|desc|placeholder|aria-label|aria-labelledby|pendingLabel|title)='
        r'"([^"]*[' + FRENCH_LETTERS + r'][^"]*)"',
        code,
    )
    assert offenders == [], offenders


def test_the_toasts_and_confirmations_come_from_the_table() -> None:
    """A message a learner only meets when something went wrong is the one that
    most has to be in a language they read."""

    code = _strip_comments(_source(PAGE))
    offenders = re.findall(
        r"(?:toast\.(?:error|success|loading)|confirm|setSaveMessage)\(\s*'([^']*['’a-zà-ÿ][^']*)'",
        code,
    )
    literal_sentences = [o for o in offenders if any(letter in o for letter in FRENCH_LETTERS) or " " in o]
    assert literal_sentences == [], literal_sentences
