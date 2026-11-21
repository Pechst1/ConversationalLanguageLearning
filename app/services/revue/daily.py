"""«Papier · les rendez-vous» (owner 2026-11-21): ``REVUE_CADENCE=daily`` as a complete mode.

Under the daily cadence a Papier's period is the ISO date (``weekly.period_for``), the intake
builds ``REVUE_STORIES_PER_DAY`` stories each morning, every desk writes what that morning's
kiosk is missing (``app/tasks/revue.py``: each desk reads ``leads.kiosk_periods``, the last
seven days, and asks once per story), and the kiosk shows the last seven days.

What this module adds is the deal: **one story per learner per day, from that morning's
stories, never one they have played.** :func:`deal_daily` reorders the kiosk the encounter
ranked (topic least recent, interests, the counter's stories first) so that

1. a story the learner has already played (any session of theirs on it that is not the open
   one) is out of the deal — never recommended, never an alternative, never started again from
   «Autre chose ?»;
2. that morning's stories (``revue_dossiers.period == day``) come first, in the encounter's
   order; the previous days' stories follow, still reachable behind the chip (the
   alternatives, «Autre chose ?»).

Nothing changes under ``weekly`` (the encounter only calls this for a daily period). No model
call. The cost of a daily morning is stated in the PR («Papier · les rendez-vous»).
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import select

from app.db.models.revue_session import RevueDossier, RevueSession


def played_ids(db: Any, user_id: Any) -> set[str]:
    """The stories the learner has played: every session of theirs but the open one."""

    rows = db.execute(
        select(RevueSession.dossier_id).where(RevueSession.user_id == user_id, RevueSession.status != "active")
    ).all()
    return {str(dossier_id) for (dossier_id,) in rows}


def morning_ids(db: Any, day: str) -> set[str]:
    """The ids of the stories the intake built for ``day`` (that morning's)."""

    try:
        rows = db.scalars(select(RevueDossier).where(RevueDossier.period == day)).all()
    except Exception as exc:  # noqa: BLE001 - the deal still excludes what was played
        logger.bind(day=day).warning("revue: the morning's dossiers unreadable ({})", exc)
        return set()
    return {str((row.payload or {}).get("id") or "") for row in rows} - {""}


def deal_daily(db: Any, user: Any, day: str, ordered: list[Any]) -> list[Any]:
    """``ordered`` without the stories the learner played, that morning's first (stable)."""

    played = played_ids(db, user.id)
    morning = morning_ids(db, day)
    fresh = [dossier for dossier in ordered if dossier.id not in played]
    return sorted(fresh, key=lambda dossier: dossier.id not in morning)


__all__ = ["deal_daily", "morning_ids", "played_ids"]
