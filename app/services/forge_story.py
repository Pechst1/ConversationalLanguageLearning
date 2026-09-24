"""WP-S5 — what the learner's story has lately been about, for La Forge.

The item bank prefers the world bible's cast, places and recurring objects in
every sentence; this module narrows that to the learner's *own* story: the
people and places of the last chapters of the living story's chronicle
(WP-62). It only reads: the chronicle belongs to the story engine
(:mod:`app.services.living_story`), and nothing here writes to it.

The result is a set of item-bank lexicon ids (``marin``, ``mistral``,
``redaction``, …) passed to :meth:`app.services.item_bank.ItemBank.sample` as
``story``; an empty set when there is no story yet or it cannot be read.
"""
from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

#: World-bible character ids → item-bank cast ids.
CHARACTERS = {
    "marin_leveque": "marin",
    "lila_bonnet": "lila",
    "augustin_de_roncourt": "gus",
    "romy_tremblay": "romy",
    "margaux_barman": "margaux",
}
#: World-bible location ids → item-bank place ids.
LOCATIONS = {
    "le_mistral": "mistral",
    "newsroom": "redaction",
    "ngo_office": "ngo_office",
    "marche_canal": "marche_canal",
    "brocante": "brocante",
    "buttes_chaumont": "parc",
    "user_apartment": "appartement",
    "marin_lila_flat": "appartement",
    "gus_loft": "appartement",
}
#: How many of the latest chronicle rows count as «lately».
RECENT_ROWS = 6


def focus_from_chronicle(chronicle: list[dict[str, Any]] | None) -> frozenset[str]:
    """The lexicon ids the last chapters of a chronicle are about."""

    focus: set[str] = set()
    rows = [row for row in (chronicle or []) if isinstance(row, dict)]
    for row in rows[-RECENT_ROWS:]:
        for character in row.get("characters") or []:
            if str(character) in CHARACTERS:
                focus.add(CHARACTERS[str(character)])
        location = LOCATIONS.get(str(row.get("location_id") or ""))
        if location:
            focus.add(location)
    return frozenset(focus)


def story_focus(db: Session, user: Any) -> frozenset[str]:
    """What the learner's own story has lately been about (read-only)."""

    try:
        from app.db.models.serial import SerialThread
        from app.services.living_story import STATE_KEY

        thread = db.scalars(
            select(SerialThread)
            .where(SerialThread.user_id == user.id, SerialThread.status == "active")
            .order_by(SerialThread.created_at.desc())
        ).first()
        live = ((thread.state or {}) if thread else {}).get(STATE_KEY) or {}
        return focus_from_chronicle(live.get("chronicle") if isinstance(live, dict) else None)
    except Exception as exc:  # pragma: no cover - a story that cannot be read never blocks a séance
        logger.debug("La Forge: no story focus", error=str(exc))
        return frozenset()


__all__ = ["CHARACTERS", "LOCATIONS", "focus_from_chronicle", "story_focus"]
