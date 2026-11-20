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

«Au comptoir» (WP-119, 2026-10-19): ``evergreen/comptoir/<id>.json`` holds the takes the desk
wrote for that evergreen (checked, read by eye, committed), loaded onto its dossier here, so
an evergreen week makes no desk call and the tests and the walk play real French offline.

«Le fil» (2026-11-20): ``evergreen/fil/<id>.json`` holds a wire written by hand for the
evergreens whose claims carry four events in a stated order (most do not: they describe a
custom, not a sequence). Read on demand (:func:`evergreen_wire`), never attached to the loaded
dossiers, so nothing an evergreen stores or snapshots changes while the assignments are off.
«Le titre» and «L'intox express» likewise read ``evergreen/titre/<id>.json`` and
``evergreen/intox/<id>.json`` (:func:`evergreen_titre`, :func:`evergreen_intox`).
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from app.services.revue.dossier import (
    ComptoirTakes,
    EditorialDossier,
    FilWire,
    IntoxExpress,
    TitreDesk,
    week_bounds,
)

EVERGREEN_DIR = Path(__file__).with_name("evergreen")
SOURCES_DIR = EVERGREEN_DIR / "sources"
COMPTOIR_DIR = EVERGREEN_DIR / "comptoir"
FIL_DIR = EVERGREEN_DIR / "fil"
TITRE_DIR = EVERGREEN_DIR / "titre"
INTOX_DIR = EVERGREEN_DIR / "intox"


@lru_cache(maxsize=1)
def _takes() -> dict[str, ComptoirTakes]:
    return {
        path.stem: ComptoirTakes.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(COMPTOIR_DIR.glob("*.json"))
    }


def evergreen_takes(dossier_id: str) -> ComptoirTakes | None:
    """The takes shipped with the evergreen ``dossier_id`` (a copy), or ``None``."""

    takes = _takes().get(dossier_id)
    return takes.model_copy(deep=True) if takes is not None else None


@lru_cache(maxsize=1)
def _wires() -> dict[str, FilWire]:
    return {path.stem: FilWire.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(FIL_DIR.glob("*.json"))}


def evergreen_wire(dossier_id: str) -> FilWire | None:
    """«Le fil» shipped with the evergreen ``dossier_id`` (a copy), or ``None``."""

    wire = _wires().get(dossier_id)
    return wire.model_copy(deep=True) if wire is not None else None


@lru_cache(maxsize=1)
def _titres() -> dict[str, TitreDesk]:
    return {path.stem: TitreDesk.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(TITRE_DIR.glob("*.json"))}


def evergreen_titre(dossier_id: str) -> TitreDesk | None:
    """«Le titre» shipped with the evergreen ``dossier_id`` (a copy), or ``None``."""

    titre = _titres().get(dossier_id)
    return titre.model_copy(deep=True) if titre is not None else None


@lru_cache(maxsize=1)
def _intoxes() -> dict[str, IntoxExpress]:
    return {path.stem: IntoxExpress.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(INTOX_DIR.glob("*.json"))}


def evergreen_intox(dossier_id: str) -> IntoxExpress | None:
    """«L'intox express» shipped with the evergreen ``dossier_id`` (a copy), or ``None``."""

    intox = _intoxes().get(dossier_id)
    return intox.model_copy(deep=True) if intox is not None else None


@lru_cache(maxsize=1)
def _load() -> tuple[EditorialDossier, ...]:
    dossiers = [
        EditorialDossier.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(EVERGREEN_DIR.glob("*.json"))
    ]
    takes = _takes()
    dossiers = [
        dossier.model_copy(update={"comptoir": takes[dossier.id]}) if dossier.id in takes else dossier
        for dossier in dossiers
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
