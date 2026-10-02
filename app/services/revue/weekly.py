"""Weekly editorial dossiers: the real news of one ISO week (WP-119 §4.1).

Until the intake (``intake.py``) builds dossiers from the feeds, a week's stories are
authored by hand in the §3.1 schema with real, dated sources — the same format as the
evergreens (``evergreen/README.md``). Files live next to this module in
``weekly/<ISO week>/``: one ``<id>.json`` per dossier (``"evergreen": false``,
``"week"`` = the folder's week) and, in ``sources/``, one ``<source_id>.txt`` excerpt per
source (first line ``# <url> — fetched <date>``) so the Anchor check runs offline.

:func:`available_for_week` is what the chooser offers (§5.1): the week's live dossiers,
topped up with that week's evergreens when there are fewer than
:data:`MIN_CHOICES`, or only the evergreens when the week has no folder.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.services.revue.dossier import EditorialDossier, parse_week
from app.services.revue.evergreen import evergreen_source_texts, evergreens_for_week

WEEKLY_DIR = Path(__file__).with_name("weekly")
#: A recommendation and two alternatives (§5.1).
MIN_CHOICES = 3


def _week_dir(week: str) -> Path:
    parse_week(week)  # raises ValueError for anything but "2026-W40"
    return WEEKLY_DIR / week


def _stamp(folder: Path) -> int:
    """The folder's mtime: a week written after the first lookup is not cached as empty."""

    try:
        return folder.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


@lru_cache(maxsize=32)
def _load(folder: Path, week: str, stamp: int) -> tuple[EditorialDossier, ...]:
    if not folder.is_dir():
        return ()
    dossiers: list[EditorialDossier] = []
    for path in sorted(folder.glob("*.json")):
        dossier = EditorialDossier.model_validate_json(path.read_text(encoding="utf-8"))
        if dossier.week != week:
            raise ValueError(f"{path.name}: week {dossier.week!r} is not the folder's {week!r}")
        if dossier.evergreen:
            raise ValueError(f"{path.name}: a weekly dossier is not an evergreen")
        dossiers.append(dossier)
    return tuple(sorted(dossiers, key=lambda dossier: dossier.id))


def load_week(week: str) -> list[EditorialDossier]:
    """The week's dossiers, validated, sorted by id (copies); ``[]`` when the folder is missing."""

    folder = _week_dir(week)
    return [dossier.model_copy(deep=True) for dossier in _load(folder, week, _stamp(folder))]


def _excerpt(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


@lru_cache(maxsize=32)
def _week_source_texts(folder: Path, stamp: int) -> dict[str, str]:
    sources = folder / "sources"
    return {path.stem: _excerpt(path) for path in sorted(sources.glob("*.txt"))}


def source_texts_for_week(week: str) -> dict[str, str]:
    """``source_id`` → excerpt for the week's sources merged with the evergreens' ones.

    A chooser that mixes live and evergreen dossiers can then anchor every claim.
    """

    folder = _week_dir(week)
    merged = evergreen_source_texts()
    merged.update(_week_source_texts(folder, _stamp(folder / "sources")))
    return merged


def available_for_week(week: str) -> list[EditorialDossier]:
    """What the chooser offers for ``week``: live dossiers first, evergreens to fill.

    No live dossier → the week's evergreens (:func:`evergreens_for_week`). Fewer than
    :data:`MIN_CHOICES` live ones → topped up with that week's evergreens, most
    specific first, so there is always a recommendation and two alternatives when the
    evergreens allow it.
    """

    live = load_week(week)
    if not live:
        return evergreens_for_week(week)
    if len(live) >= MIN_CHOICES:
        return live
    seen = {dossier.id for dossier in live}
    for dossier in evergreens_for_week(week):
        if len(live) >= MIN_CHOICES:
            break
        if dossier.id not in seen:
            live.append(dossier)
            seen.add(dossier.id)
    return live
