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

**Phase 3 «Le kiosque».** The weekly intake (``intake.py``, ``app/tasks/revue.py``) writes
its dossiers to the ``revue_dossiers`` table. Given a database session, :func:`load_week`
reads the table first and the hand-authored folder second (a week the intake built
replaces the files; a week it never built is the files, as before).

**Periods (§12.2).** Under ``REVUE_CADENCE=weekly`` a Papier's period is the ISO week;
under ``daily`` it is the ISO date and the kiosk rolls: :func:`kiosk_for_day` shows the
dossiers built for the last seven days, newest first. :func:`period_for`,
:func:`week_of_period` and :func:`is_daily_period` are the only places that know the two
forms; ``revue_sessions.week`` stores whichever the cadence gives.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from app.services.revue.dossier import EditorialDossier, parse_week
from app.services.revue.evergreen import evergreen_source_texts, evergreens_for_week

WEEKLY_DIR = Path(__file__).with_name("weekly")
#: A recommendation and two alternatives (§5.1).
MIN_CHOICES = 3
#: Daily cadence: the chooser shows the dossiers of the last seven days (§12.2).
DAILY_KIOSK_DAYS = 7
PARIS = ZoneInfo("Europe/Paris")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Periods (§12.2)
# ---------------------------------------------------------------------------


def cadence() -> str:
    from app.config import settings

    value = str(getattr(settings, "REVUE_CADENCE", "weekly") or "weekly")
    return value if value in {"weekly", "daily"} else "weekly"


def is_daily_period(period: str) -> bool:
    """``"2026-10-03"`` (a day) rather than ``"2026-W40"`` (a week)."""

    if not _DAY.match(str(period or "")):
        return False
    date.fromisoformat(period)  # raises for "2026-02-31"
    return True


def week_of_period(period: str) -> str:
    """The ISO week a period belongs to (a week is its own week)."""

    if is_daily_period(period):
        year, number, _ = date.fromisoformat(period).isocalendar()
        return f"{year}-W{number:02d}"
    parse_week(period)
    return period


def period_for(now: datetime | date | None = None, *, cadence_name: str | None = None) -> str:
    """Today's period in Paris: the ISO week (weekly) or the ISO date (daily)."""

    if isinstance(now, datetime):
        local = (now if now.tzinfo else now.replace(tzinfo=UTC)).astimezone(PARIS).date()
    elif isinstance(now, date):
        local = now
    else:
        local = datetime.now(UTC).astimezone(PARIS).date()
    if (cadence_name or cadence()) == "daily":
        return local.isoformat()
    year, number, _ = local.isocalendar()
    return f"{year}-W{number:02d}"


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


def _rows(db: Any, *, periods: list[str]) -> list[EditorialDossier]:
    """The intake's dossiers for ``periods`` (``revue_dossiers``), newest period first."""

    from sqlalchemy import select

    from app.db.models.revue_session import RevueDossier

    rows = list(
        db.scalars(
            select(RevueDossier)
            .where(RevueDossier.period.in_(periods))
            .order_by(RevueDossier.period.desc(), RevueDossier.built_at.asc(), RevueDossier.id.asc())
        )
    )
    dossiers: list[EditorialDossier] = []
    for row in rows:
        try:
            dossiers.append(EditorialDossier.model_validate(row.payload))
        except Exception as exc:  # noqa: BLE001 - one bad row never empties the kiosk
            logger.bind(row=row.id).warning("revue: stored dossier unreadable ({})", exc)
    return dossiers


def load_week(week: str, db: Any | None = None) -> list[EditorialDossier]:
    """The week's dossiers, validated (copies); ``[]`` when there are none.

    With ``db``: the intake's rows for the week first (built ones, then the evergreen
    top-up, in build order); without rows — or without ``db`` — the week's folder, sorted
    by id.
    """

    folder = _week_dir(week)
    if db is not None:
        try:
            stored = _rows(db, periods=[week])
        except Exception as exc:  # noqa: BLE001 - the files still answer
            logger.bind(week=week).warning("revue: revue_dossiers unreadable ({}); files only", exc)
            stored = []
        if stored:
            return stored
    return [dossier.model_copy(deep=True) for dossier in _load(folder, week, _stamp(folder))]


def kiosk_for_day(day: str, db: Any | None = None) -> list[EditorialDossier]:
    """Daily cadence: the dossiers built for the last :data:`DAILY_KIOSK_DAYS` days to ``day``,
    newest first, one per id; the week's (weekly-built or authored) kiosk when none exists."""

    end = date.fromisoformat(day)
    periods = [(end - timedelta(days=offset)).isoformat() for offset in range(DAILY_KIOSK_DAYS)]
    dossiers: list[EditorialDossier] = []
    if db is not None:
        try:
            dossiers = _rows(db, periods=periods)
        except Exception as exc:  # noqa: BLE001
            logger.bind(day=day).warning("revue: revue_dossiers unreadable ({})", exc)
    seen: set[str] = set()
    unique = [d for d in dossiers if not (d.id in seen or seen.add(d.id))]
    if unique:
        return unique
    return available_for_week(week_of_period(day), db=db)


def forget_cache() -> None:
    """Drop the file caches (the intake just wrote a week)."""

    _load.cache_clear()
    _week_source_texts.cache_clear()


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


def available_for_week(week: str, db: Any | None = None) -> list[EditorialDossier]:
    """What the chooser offers for ``week``: live dossiers first, evergreens to fill.

    No live dossier → the week's evergreens (:func:`evergreens_for_week`). Fewer than
    :data:`MIN_CHOICES` live ones → topped up with that week's evergreens, most
    specific first, so there is always a recommendation and two alternatives when the
    evergreens allow it.
    """

    live = load_week(week, db) if db is not None else load_week(week)
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
