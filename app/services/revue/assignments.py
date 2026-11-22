"""«Le Papier · les rubriques»: the assignment desk (WP-119, owner 2026-11-20).

The learner is Romy's trainee, and each story is dealt one ASSIGNMENT («rubrique»): «Au
comptoir» (the vox pop, ``comptoir_loop.py``), «Le fil» (the wire back in order,
``fil_loop.py``), «Le titre» (the honest headline, ``titre_loop.py``), «L'intox express» (five
statements, true or false, ``intox_loop.py``), «La photo» (the photo desk, ``photo_loop.py``: only on a
story with at least two pictures) and «Le micro» (the interview, ``micro_loop.py``). Never the same shape twice
in three days: a session is dealt an assignment its story can carry that is not the one of the
learner's last two Papier sessions.

- :class:`Assignment` and :func:`register`: each assignment says, from the story's
  :class:`Material` (the dossier and what the desks wrote for it), whether it can carry it.
  A new assignment registers itself here (and adds what it reads to :class:`Material`); the
  dealer (:func:`deal`) never changes.
- :func:`deal` is deterministic: the assignments the story can carry, minus the last two the
  learner played, ordered by a hash of (learner, dossier, assignment); when every one was
  played lately it falls back to the one played least recently; ``None`` (the chat) when the
  story carries none.
- The dealt assignment is recorded on the session's first ``choice`` event (``mode``), like
  the comptoir's, and kept for the session's life (:func:`session_mode` replays it).

«Papier · le choix» (2026-11-22): only the assignments ``REVUE_ASSIGNMENTS_OFFERED`` names
(default «Au comptoir» and «Le titre») are dealt (:func:`offered_keys`); the others are parked
— registered, so a session dealt one before plays to its end, but never dealt again.

Nothing here runs while ``REVUE_ASSIGNMENTS_ENABLED`` is off: the session starts as before it
existed (the comptoir when that switch is on and the story has takes, else the chat).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.revue.dossier import (
    ComptoirTakes,
    EditorialDossier,
    FilWire,
    IntoxExpress,
    MicroDesk,
    PhotoDesk,
    TitreDesk,
)

#: The modes a session can be in; ``chat`` is the Papier before the assignments.
CHAT = "chat"
#: How many of the learner's last Papier sessions an assignment must not repeat.
RECENT = 2


@dataclass(frozen=True)
class Material:
    """What a story offers the assignments: the dossier, the comptoir's takes (``None``
    while that switch is off or the desk refused), the wire, the headlines, the statements
    (each ``None`` without one)."""

    dossier: EditorialDossier
    takes: ComptoirTakes | None = None
    wire: FilWire | None = None
    titre: TitreDesk | None = None
    intox: IntoxExpress | None = None
    #: «La photo» and «Le micro» (2026-11-21); ``pictures``: the story's gallery as the photo
    #: desk reads it (``photo.story_pictures``), each a dict with its ``ref`` and ``basis_fr``.
    photo: PhotoDesk | None = None
    micro: MicroDesk | None = None
    pictures: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Assignment:
    """One «rubrique»: its key (the session's ``mode``), its French name, and whether a
    story's material can carry it."""

    key: str
    name_fr: str
    carries: Callable[[Material], bool]


_REGISTRY: dict[str, Assignment] = {}


def register(assignment: Assignment) -> Assignment:
    """Add (or replace) an assignment; the order of registration is the dealer's tie-break."""

    _REGISTRY[assignment.key] = assignment
    return assignment


def registered() -> list[str]:
    return list(_REGISTRY)


def assignment(key: str) -> Assignment | None:
    return _REGISTRY.get(key)


register(Assignment("comptoir", "Au comptoir", lambda material: material.takes is not None))
register(Assignment("fil", "Le fil", lambda material: material.wire is not None))
register(Assignment("titre", "Le titre", lambda material: material.titre is not None))
register(Assignment("intox", "L'intox express", lambda material: material.intox is not None))


def _photo_carries(material: Material) -> bool:
    from app.services.revue.photo import bind  # noqa: PLC0415 - photo reads the gallery

    return material.photo is not None and bind(material.photo, list(material.pictures)) is not None


register(Assignment("photo", "La photo", _photo_carries))
register(Assignment("micro", "Le micro", lambda material: material.micro is not None))

#: What each assignment snapshots on the dossier (its field), for the dealt one only.
FIELDS: dict[str, str] = {"comptoir": "comptoir", "fil": "fil", "titre": "titre", "intox": "intox", "photo": "photo",
                          "micro": "micro"}


def dealt_material(material: Material, key: str) -> Any:
    """The material the dealt assignment ``key`` plays («La photo»: bound to the gallery as it
    stands, its pictures' links and credits filled)."""

    if key == "photo":
        from app.services.revue.photo import bind  # noqa: PLC0415

        return bind(material.photo, list(material.pictures)) if material.photo is not None else None
    return {"comptoir": material.takes, "fil": material.wire, "titre": material.titre,
            "intox": material.intox, "micro": material.micro}.get(key)


#: «Papier · le choix» (2026-11-22): what ``REVUE_ASSIGNMENTS_OFFERED`` says when it is unset.
DEFAULT_OFFERED = "comptoir,titre"


def offered_keys() -> list[str]:
    """The assignments the paper deals today (``REVUE_ASSIGNMENTS_OFFERED``), in registration
    order; an unknown key is ignored. The others are parked: never dealt, their desks never run."""

    from app.config import settings

    raw = getattr(settings, "REVUE_ASSIGNMENTS_OFFERED", DEFAULT_OFFERED)
    wanted = {part.strip().lower() for part in str(raw if raw is not None else DEFAULT_OFFERED).split(",")}
    return [key for key in _REGISTRY if key in wanted]


def is_offered(key: str) -> bool:
    return key in offered_keys()


def available(material: Material) -> list[str]:
    """The offered assignments ``material`` can carry, in registration order."""

    offered = set(offered_keys())
    return [key for key, row in _REGISTRY.items() if key in offered and row.carries(material)]


def _rank(seed: str, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def deal(offered: list[str], recent: list[str], *, seed: str, prefer: list[str] | None = None) -> str | None:
    """The assignment a new session plays: one of ``offered`` that is not among the last
    :data:`RECENT` of ``recent`` (newest first), picked by ``seed`` (learner + dossier);
    when each was played lately, the one played least recently; ``None`` when nothing is
    offered (the chat).

    ``prefer`` («Papier · le choix»: the assignments whose material exercises the day's rule,
    best first) goes ahead of the seed: the first preferred one not played lately, else the
    first preferred one that is not the very last shape played; else the seeded deal."""

    if not offered:
        return None
    lately = list(recent[:RECENT])
    fresh = [key for key in offered if key not in lately]
    for pool in (fresh, [key for key in offered if key not in lately[:1]]):
        best = next((key for key in prefer or [] if key in pool), None)
        if best is not None:
            return best
    if fresh:
        return min(fresh, key=lambda key: _rank(seed, key))
    # every offered shape was played lately: the one played longest ago
    return max(offered, key=lambda key: (lately.index(key), _rank(seed, key)))


def seed_for(user_id: Any, dossier_id: str) -> str:
    return f"{user_id}:{dossier_id}"


def session_mode(state: Any) -> str:
    """The mode recorded on a session's first dossier choice: an assignment's key, else ``chat``."""

    for event in state.events:
        if event.kind == "choice" and event.payload.get("kind") == "dossier":
            mode = event.payload.get("mode")
            return str(mode) if mode in _REGISTRY else CHAT
    return CHAT


def mode_of_row(row: Any) -> str:
    """:func:`session_mode` from a stored session row, without validating its whole state."""

    for event in (getattr(row, "state", None) or {}).get("events") or []:
        payload = event.get("payload") or {}
        if event.get("kind") == "choice" and payload.get("kind") == "dossier":
            mode = payload.get("mode")
            return str(mode) if mode in _REGISTRY else CHAT
    return CHAT


def recent_modes(rows: list[Any]) -> list[str]:
    """The modes of the learner's last Papier sessions, newest first (``rows`` newest first)."""

    return [mode_of_row(row) for row in rows[:RECENT]]


def assignments_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False))


__all__ = [
    "Assignment",
    "Material",
    "assignments_enabled",
    "available",
    "deal",
    "is_offered",
    "offered_keys",
    "recent_modes",
    "register",
    "registered",
    "seed_for",
    "session_mode",
]
