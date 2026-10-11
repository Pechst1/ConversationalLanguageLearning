"""WP-111: is the runnable season still the owner-approved bible?

The bible (``docs/story/season-1/0N-*.md``) is the source of truth; the season
files are its transcription. This module extracts every French line the bible
puts on the page — character lines and captions («…» after ``NAME ·``), the likely
replies (*«…»*), the cards (**[ … ]**) and the Déchiffrer documents (> *…*) — and
reports the ones a season file does not carry verbatim. A transcription that drops,
rewords or invents a line fails ``tests/test_season_format.py``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BIBLE_ROOT = REPO / "docs" / "story"

_GUILLEMETS = re.compile(r"«\s*(.+?)\s*»", re.DOTALL)
#: A dialogue or caption line: "- GUS · A2 «…» · B1 «…»", "- CAPTION · …", "MARGAUX *(now)* · …".
_SPEAKER_LINE = re.compile(r"^\s*(?:[-*>]\s*)?(?:\*\*)?[A-ZÉÈÀÂÇ][A-ZÉÈÀÂÇ0-9 ./'’()-]{1,40}(?:\*\*)?\s*(?:\*\([^)]*\)\*\s*)?·")
_REPLY = re.compile(r"\*«(.+?)»\*")
_CARD = re.compile(r"\*\*\[\s*(.+?)\s*\]\*\*")
_OPTION = re.compile(r"\[\s*([^\]]+?)\s*\]")
_DOCUMENT = re.compile(r"^>\s*\*(.+?)\*\s*$")
_NOTE_BLOCK = re.compile(r"^\s*\*\*Who remembers what")
_STAGE = re.compile(r"\*\([^)]*\)\*")
_BAND_LABEL = re.compile(r"^\*?\s*(A1|A2|B1|B2)\s*\*?$")
_GLOSS = re.compile(r"\(\s*«[^»]*»\s*\)")


def _prose_word(quote: str) -> bool:
    """One or two words with no sentence punctuation, quoted inside prose."""

    words = quote.split()
    return len(words) <= 2 and not re.search(r"[.!?…:]", quote)


def fold(text: str) -> str:
    """Compare lines up to typography: quotes, dashes, spacing and case."""

    text = unicodedata.normalize("NFC", str(text))
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("—", "-"), ("–", "-"), (" ", " "), (" ", " ")):
        text = text.replace(a, b)
    text = text.replace("…", "...")
    text = re.sub(r"\s+", " ", text)
    return text.strip().strip("\"'").strip().casefold()


def _is_note(line: str) -> bool:
    stripped = line.lstrip("> ").lstrip()
    return stripped.startswith(("**Note", "Note", "*Note", "**Agreement", "**Agreement notes")) or "**Note" in line[:12]


#: Owner-decided departures from the bible's text, by tentpole: the bible line and
#: the decision that replaced it. Anything else missing is a transcription fault.
DEVIATIONS: dict[str, dict[str, str]] = {
    "t1": {
        "Camille, pour toi, c'est… [ un homme ] [ une femme ]": (
            "S-9 (2026-09-30): Camille's gender arises in-story — the learner asks "
            "«Vous êtes son fils ? / sa fille ?» — no card outside the fiction."
        ),
    },
}


def bible_lines(markdown: str) -> list[str]:
    """Every French line the page shows, in the order the bible writes them.

    Every «…» outside headings and owner notes counts, plus the Déchiffrer
    documents (``> *…*``) and the cards (``**[ … ]**``).
    """

    found: list[str] = []
    in_note = False
    in_block = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            in_note = in_block = False
            continue
        if line.lstrip().startswith("#"):
            continue
        if _NOTE_BLOCK.match(line):
            # «Who remembers what»: an owner-only list that runs to the next blank line.
            in_block = True
            continue
        if in_block:
            continue
        # Italic stage directions — *(Gus's «vulnerable» expression)* — describe the art.
        line = _STAGE.sub(" ", line)
        if _is_note(line) or line.lstrip().startswith("> **Note"):
            in_note = True
            continue
        if in_note and line.lstrip().startswith(">"):
            continue
        in_note = False
        document = _DOCUMENT.match(line)
        if document and "«" not in document.group(1):
            if not _BAND_LABEL.match(document.group(1)):
                found.append(document.group(1))
            continue
        # An English gloss in parentheses after a French prompt — «(«Where was the
        # fire? Show me.»)» — is the bible explaining itself, not a line on the page.
        line = _GLOSS.sub(" ", line)
        speaker = bool(_SPEAKER_LINE.match(line)) or "→" in line
        for quote in _GUILLEMETS.findall(line):
            if not speaker and _prose_word(quote):
                # «vulnerable», «softened», «fatiguée» inside a sentence of English
                # prose name an expression or a beat; they are not lines.
                continue
            found.append(quote)
        for match in _CARD.findall(line):
            if len(match) < 80 and "«" not in match and not match.startswith("`"):
                found.append(match)
    cleaned = []
    for text in found:
        text = text.strip()
        if len(fold(text)) < 2:
            continue
        cleaned.append(text)
    return cleaned


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for key, item in value.items():
            if key in {"native", "note", "visual", "intent", "means", "listens_for"}:
                continue
            out.extend(_strings(item))
        return out
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def season_text(path: Path) -> str:
    """Every French string a season file carries, folded, as one searchable blob."""

    data = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(fold(text) for text in _strings(data))


def missing_lines(markdown_path: Path, season_path: Path, *, tentpole: str | None = None) -> list[str]:
    """Bible lines the season file does not carry verbatim (up to typography),
    minus the owner-decided :data:`DEVIATIONS`."""

    blob = season_text(season_path)
    allowed = {fold(text) for text in DEVIATIONS.get(tentpole or season_path.stem, {})}
    missing = []
    for line in bible_lines(markdown_path.read_text(encoding="utf-8")):
        if fold(line) in allowed:
            continue
        # A bible line may be split into several captions at a «(beat)» or carry
        # stage directions in italics; each fragment must be there.
        fragments = [part for part in re.split(r"\s*\*\([^)]*\)\*\s*", line) if fold(part)]
        for fragment in fragments or [line]:
            if fold(fragment) not in blob:
                missing.append(fragment)
    return missing
