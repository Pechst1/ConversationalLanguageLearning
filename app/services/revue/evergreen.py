"""Evergreen editorial dossiers (WP-119 §4.3).

Twelve authored dossiers in the §3.1 schema — la rentrée, le Beaujolais nouveau, la
galette des rois, les soldes, la Fête de la musique, le Tour, la Toussaint, le marché du
dimanche, une grève, le bac, le 14 juillet, Noël au marché — with real, dated public
sources. They fill a thin week and are the only content of the test and walk harnesses.

Files live next to this module in ``evergreen/``: one ``<id>.json`` per dossier and, in
``evergreen/sources/``, one ``<source_id>.txt`` excerpt per source (first line
``# <url> — fetched <date>``, then the paragraphs that hold the quotes) so the Anchor
check runs offline in CI. See ``evergreen/README.md``.

Which evergreen fits a week is decided by ``time_scope`` alone: a dossier's stored
``week`` (the ISO week its ``happening`` window starts in) only satisfies the schema.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from app.services.revue.dossier import EditorialDossier, week_bounds

EVERGREEN_DIR = Path(__file__).with_name("evergreen")
SOURCES_DIR = EVERGREEN_DIR / "sources"


@lru_cache(maxsize=1)
def _load() -> tuple[EditorialDossier, ...]:
    dossiers = [
        EditorialDossier.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(EVERGREEN_DIR.glob("*.json"))
    ]
    return tuple(sorted(dossiers, key=lambda dossier: dossier.id))


def load_evergreens() -> list[EditorialDossier]:
    """Every evergreen dossier, validated, sorted by id (copies: callers may mutate)."""

    return [dossier.model_copy(deep=True) for dossier in _load()]


def _excerpt(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


@lru_cache(maxsize=1)
def _source_texts() -> dict[str, str]:
    return {path.stem: _excerpt(path) for path in sorted(SOURCES_DIR.glob("*.txt"))}


def evergreen_source_texts() -> dict[str, str]:
    """``source_id`` → excerpt text (header line stripped), for the Anchor check."""

    return dict(_source_texts())


def _overlaps(dossier: EditorialDossier, monday: date, sunday: date) -> bool:
    scope = dossier.time_scope
    return scope.start <= sunday and scope.end >= monday


def evergreens_for_week(week: str) -> list[EditorialDossier]:
    """The evergreens whose ``time_scope.happening`` overlaps the ISO ``week``.

    The stored ``week`` is ignored. Seasonal dossiers come before the year-round ones
    (shorter windows first, then by id), so the first match is the most specific one.
    """

    monday, sunday = week_bounds(week)
    matches = [dossier for dossier in load_evergreens() if _overlaps(dossier, monday, sunday)]
    return sorted(
        matches, key=lambda dossier: (dossier.time_scope.end - dossier.time_scope.start, dossier.id)
    )


def evergreen_for(week: str, topic: str | None = None) -> EditorialDossier | None:
    """The first evergreen for ``week`` (most specific first), of ``topic`` when given."""

    for dossier in evergreens_for_week(week):
        if topic is None or dossier.topic == topic:
            return dossier
    return None
