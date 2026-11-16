"""Package V stage 1: rows stored before the verdict stack keep what they counted for.

The verdict stack reads each surface's stored payload and asks whether it ``counts`` (#333).
Main never asked: every stored attempt fed the level average, every finished letter paid its
gold and its token. Reading old rows the new way would re-judge history on deploy, and a
learner's level could move without them doing anything.

So the three reads that decide a level, l'or or a token ask :func:`keeps_what_it_counted`
first. A row stored before the cut-over (the one row of ``verdict_cutover``, written by the
migration that ships the stack) answers as main's code did, while ``VERDICT_LEGACY_ROWS``
is ``as_counted`` (the default). ``rejudge`` reads every row the new way;
``scripts/verdict_level_report.py`` prints, per learner, what that would change.

With no cut-over row (a fresh database built by ``create_all``, every test that does not
add one), no row is legacy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings

AS_COUNTED = "as_counted"
REJUDGE = "rejudge"

__all__ = ["AS_COUNTED", "REJUDGE", "Cutover", "cutover", "keeps_what_it_counted"]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Cutover:
    """The cut-over read once per request or job, then asked per row."""

    def __init__(self, at: datetime | None, mode: str) -> None:
        self.at = _utc(at)
        self.mode = mode

    def keeps(self, row: Any) -> bool:
        """``row`` was stored before the cut-over and keeps what main's code counted it for."""

        if self.at is None or self.mode != AS_COUNTED:
            return False
        created = _utc(getattr(row, "created_at", None))
        return created is not None and created < self.at


def cutover(db: Session | None) -> Cutover:
    mode = str(getattr(settings, "VERDICT_LEGACY_ROWS", AS_COUNTED) or AS_COUNTED).strip().lower()
    if db is None or mode != AS_COUNTED:
        return Cutover(None, mode)
    from app.db.models.verdict_cutover import VerdictCutover

    try:
        with db.begin_nested():  # a database not yet migrated has no table, and no legacy rows
            at = db.query(VerdictCutover.at).order_by(VerdictCutover.id).limit(1).scalar()
    except Exception:  # noqa: BLE001
        at = None
    return Cutover(at, mode)


def keeps_what_it_counted(db: Session | None, row: Any) -> bool:
    return cutover(db).keeps(row)
