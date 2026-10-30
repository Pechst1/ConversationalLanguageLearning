"""#313 / #315 (root cause #145) — one speaker per line, and nobody speaks for another.

The scene holds a line twice: as a transcript string (``«Lila : Pas encore.»``, the
form the model reads and the one an older client prints) and as spoken lines with a
``speaker_id`` (the form the learner's screen draws a bubble from). Nothing checked
that the two agree, so a model that copied the transcript pattern into its own line
(«Lila : Je demande : combien de temps tu restes ?» under Camille) shipped the label
as words, and a character answered for someone else.

This module is the one place that reads a speaker label out of a line. It is pure:
no model call, no database. A label counts only when it is the exact name of someone
in the cast (the registry, or the cast rows the caller passes), so «Attention : …» or
«Note : …» are never mistaken for a speaker.

* :func:`labels_in` — the ``(person, text)`` pairs of a text, one per line, with the
  person the label names or ``None`` for an unlabelled line;
* :func:`settle_labels` — strips the speaker's own label from each line and returns the
  people it found speaking for someone else, so the caller can refuse or repair.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from app.services import cast_registry

#: «Name : text» (French typography puts a space before the colon; any kind of space).
_LABEL = re.compile(r"^\s*(?P<label>[^\W\d_][^:：\n]{1,30}?)[\s  ]*[:：][\s  ]+(?P<rest>\S.*)$", re.DOTALL)
_NICKNAME = re.compile(r"«\s*([^»]+?)\s*»")


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip()


def _spellings(name: str) -> set[str]:
    """What a transcript may call this person: the full label, the nickname, the first name."""

    out: set[str] = set()
    text = str(name or "").strip()
    if not text:
        return out
    out.add(text)
    nickname = _NICKNAME.search(text)
    if nickname:
        out.add(nickname.group(1))
    plain = _NICKNAME.sub(" ", text).split()
    if plain and plain[0][:1].isupper() and len(plain[0]) >= 3:
        out.add(plain[0])
    return out


def name_table(cast: Iterable[Any] = ()) -> dict[str, str]:
    """``{folded spelling: person}`` for the whole registry plus the cast rows given
    (``{"id": …, "name": …}``). The person is the registry id where the registry holds
    them, the row's own id otherwise."""

    table: dict[str, str] = {}
    for member in cast_registry.all_members().values():
        for spelling in {member.short_name, member.spoken_name, *_spellings(member.name)}:
            table[_fold(spelling)] = member.id
    for row in cast:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        person = cast_registry.resolve_id(str(row["id"])) or str(row["id"])
        for spelling in _spellings(str(row.get("name") or "")):
            table.setdefault(_fold(spelling), person)
    return table


def person_of(character_id: str | None) -> str | None:
    """The canonical person for a scene's character id (registry id or the id itself)."""

    raw = str(character_id or "").strip()
    return (cast_registry.resolve_id(raw) or raw) or None


def labels_in(text: str, table: dict[str, str]) -> list[tuple[str | None, str]]:
    """One ``(person, text)`` per line of ``text``: the person a leading «Name :» names
    (``None`` for an unlabelled line) and the line without its label."""

    rows: list[tuple[str | None, str]] = []
    for line in str(text or "").split("\n"):
        found = _LABEL.match(line)
        person = table.get(_fold(found.group("label"))) if found else None
        rows.append((person, found.group("rest").strip()) if person and found else (None, line.strip()))
    return rows


def settle_labels(text: str, speaker_id: str | None, table: dict[str, str]) -> tuple[str, list[str]]:
    """``(text without the speaker's own labels, people who speak for someone else)``.

    A line labelled with the speaker's own name loses the label. A line labelled with
    another person keeps its words but is reported: the caller decides whether to refuse
    the line or draw it under that person."""

    speaker = person_of(speaker_id)
    kept: list[str] = []
    foreign: list[str] = []
    for person, line in labels_in(text, table):
        if person and person != speaker:
            foreign.append(person)
        kept.append(line)
    return "\n".join(part for part in kept if part), foreign
