"""WP-21: no learner-facing deterministic sentence is authored in one language.

Two halves:

* the copy tables themselves must be complete — a key with a missing German
  column would silently serve English, which is exactly the defect this package
  exists to remove;
* the surfaces that used to hold those sentences must no longer contain them.
  The sentinel list is small on purpose: it names strings that were verifiably
  the leftovers (English in the corrector, hardcoded German in the brief
  exercise, French-only microphone toasts), so the test fails on a regression
  rather than on any English word appearing anywhere in the tree.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.learner_copy import (
    LEARNER_COPY,
    SUPPORTED_COPY_LANGUAGES,
    copy_language,
    learner_text,
)

ROOT = Path(__file__).resolve().parents[1]

# The file that is *allowed* to contain every sentence: the table itself.
COPY_MODULE = ROOT / "app" / "services" / "learner_copy.py"
FRONTEND_COPY_MODULE = ROOT / "web-frontend" / "lib" / "atelier-v2-copy.ts"
VISUAL_CUES_MODULE = ROOT / "web-frontend" / "lib" / "visual-cues.ts"

# Surfaces that author deterministic learner-facing prose.
SCANNED_FILES = [
    ROOT / "app" / "core" / "error_detection" / "rules.py",
    ROOT / "app" / "core" / "error_detection" / "detector.py",
    ROOT / "app" / "services" / "error_memory.py",
    ROOT / "app" / "services" / "brief_exercise_service.py",
    ROOT / "app" / "services" / "missions.py",
    ROOT / "web-frontend" / "pages" / "vocabulary" / "review.tsx",
    ROOT / "web-frontend" / "pages" / "missions.tsx",
    ROOT / "web-frontend" / "pages" / "audio-session.tsx",
]

# Sentences that were shipped in exactly one language before WP-21.
ENGLISH_ONLY_SENTINELS = [
    "This form needs review",
    "Pronoun choice",
    "Vocabulary choice",
    "Language repair",
    "then practise the same contrast",
    "Review the requested form, then answer",
    "Missing mission response",
    "Too little context",
    "No answer yet",
    "Write a short French response before submitting",
    "there is no French to review",
    "too short to prove the mission targets",
    "Add one reason, one concrete detail",
    "With vous, avoir is avez",
    "The French word is problème with an accent grave",
    "Possible feminine article used with masculine noun",
    "Verb appears to be in infinitive form after pronoun",
    "Automated heuristic review only",
    "Great job",
]

GERMAN_ONLY_SENTINELS = [
    "Das passt zur Grammatikaufgabe.",
    "Leider falsch. Richtig",
    "Fast! Die richtige Antwort",
    "Richtig! ",
]

FRENCH_ONLY_SENTINELS = [
    "La transcription a échoué.",
    "Le micro n’a pas pu être ouvert.",
    "Rien n’a été transcrit — réessayez.",
    "Micro refusé — autorisez",
    "Aucun micro disponible sur cet appareil",
    "Je n’ai rien entendu. Touchez le micro",
    "Le micro n’est pas disponible ici",
]

ALL_SENTINELS = ENGLISH_ONLY_SENTINELS + GERMAN_ONLY_SENTINELS + FRENCH_ONLY_SENTINELS


def _placeholders(template: str) -> set[str]:
    return set(re.findall(r"\{([a-z_]+)\}", template))


@pytest.mark.parametrize("key", sorted(LEARNER_COPY))
def test_every_copy_row_ships_all_three_languages(key: str) -> None:
    row = LEARNER_COPY[key]
    assert set(row) == set(SUPPORTED_COPY_LANGUAGES), key
    for language, value in row.items():
        assert value.strip(), f"{key}/{language} is empty"


@pytest.mark.parametrize("key", sorted(LEARNER_COPY))
def test_placeholders_match_across_languages(key: str) -> None:
    row = LEARNER_COPY[key]
    expected = _placeholders(row["en"])
    for language in SUPPORTED_COPY_LANGUAGES:
        assert _placeholders(row[language]) == expected, f"{key}/{language}"


def test_learner_text_resolves_and_falls_back() -> None:
    assert learner_text("erratum.label_spelling", "de") == "Rechtschreibung"
    assert learner_text("erratum.label_spelling", "de-AT") == "Rechtschreibung"
    # A language we do not ship must not blank the card.
    assert learner_text("erratum.label_spelling", "pt") == LEARNER_COPY["erratum.label_spelling"]["en"]
    assert learner_text("erratum.label_spelling", None) == LEARNER_COPY["erratum.label_spelling"]["en"]
    # A placeholder is filled; a missing one returns the sentence, never raises.
    assert "avez" in learner_text("erratum.repair_use_suggestion", "fr", suggestion="avez")
    assert learner_text("erratum.repair_use_suggestion", "fr") == LEARNER_COPY["erratum.repair_use_suggestion"]["fr"]
    # An unknown key is visible, not fatal, inside a grading path.
    assert learner_text("no.such.key", "en") == "no.such.key"


def test_copy_language_normalizes() -> None:
    assert copy_language("FR") == "fr"
    assert copy_language("de_AT") == "de"
    assert copy_language("") == "en"
    assert copy_language("sv") == "en"


def _without_comments(path: Path) -> str:
    """Only what the learner could see. A comment may still name a removed
    string — the mission code explains *why* two labels are filtered out — and
    that is documentation, not shipped copy."""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("#", "//", "*", "/*")):
            continue
        lines.append(line)
    return "\n".join(lines)


@pytest.mark.parametrize("path", SCANNED_FILES, ids=lambda path: path.name)
def test_no_single_language_leftovers_in_learner_facing_code(path: Path) -> None:
    source = _without_comments(path)
    found = [sentinel for sentinel in ALL_SENTINELS if sentinel in source]
    assert not found, f"{path.name} still authors single-language learner copy: {found}"


def test_the_copy_tables_are_where_the_sentences_live() -> None:
    """The sentinels did not simply vanish — they moved into the tables."""
    backend = COPY_MODULE.read_text(encoding="utf-8")
    assert "Das passt zur Grammatikaufgabe." in backend
    assert "Review the requested form, then answer" in backend

    frontend = FRONTEND_COPY_MODULE.read_text(encoding="utf-8")
    for key in (
        "mic_unavailable",
        "mic_denied",
        "mic_open_failed",
        "transcribing",
        "transcription_failed",
        "transcription_empty",
        "nothing_heard",
    ):
        # One union member plus one row per shipped language.
        assert frontend.count(f"'{key}'") == 1, key
        assert frontend.count(f"{key}:") == 3, key

    cues = VISUAL_CUES_MODULE.read_text(encoding="utf-8")
    # 14 scene cues plus the "Mot / Word / Wort" default.
    definitions = len(re.findall(r"^\s{2,4}id: '", cues, re.M))
    assert definitions == 15, "the cue table lost rows"
    for language in SUPPORTED_COPY_LANGUAGES:
        assert cues.count(f"{language}: {{ label:") == definitions, language
