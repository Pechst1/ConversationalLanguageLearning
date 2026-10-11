"""The cast's knowledge on the Revue stage (WP-119 §7, phase 2).

Memory, bounded, not banned. For every cast member on stage (Romy, and the one
guest) the encounter passes the provider a **small knowledge context**:

* what this character knows about the learner — ``known_about_learner`` (the
  consequences they witnessed, WP-96), ``trust`` (``living_story.trust_of``), the
  ``register`` they use and ``tu_since`` (WP-97), all read through
  ``story_archive.cast_memory`` on the learner's active serial thread;
* the ``NPCMemory`` rows of this learner that are this character's own, or that
  mention the Revue's topic, each with its provenance (``npc_id``, ``scene_id``,
  ``memory_type``, date);
* nothing the season marks as a future reveal: every text row goes through the
  caller's Knowledge check (``refused``) and a refused row is dropped, not edited.

And the voice: name, personality and register with the learner from the season's
``world.json``, so the guest stays in character.

The authored defaults (:func:`authored_guest_line`) are one line per guest cast member
and topic in ``evergreen/guests/guest_lines.json`` (the evergreen loader globs
``evergreen/*.json`` for dossiers, hence the subdirectory). Write-back
(:func:`remember`) adds one ``NPCMemory`` row per cast member for what they
witnessed, get-or-creating the ``NPC`` row the foreign key needs (the season cast has
no NPC rows of its own). Season progression is never written from here.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

CAMILLE_ID = "camille_marchand"
GUEST_LINES_PATH = Path(__file__).with_name("evergreen") / "guests" / "guest_lines.json"
WORLD_PATH = Path(__file__).resolve().parents[2] / "data" / "season" / "s1" / "world.json"

#: How many NPCMemory rows of a character's own, and of the topic from others, travel.
OWN_MEMORIES = 5
TOPIC_MEMORIES = 3
KNOWN_ABOUT_ROWS = 5
TEXT_CHARS = 240

#: Romy's lines are hers; the generic fallback when a guest/topic pair is missing.
GENERIC_GUEST_LINE = "Je vous écoute. C'est intéressant, tout ça."

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("’", "'")


def _words(text: str | None) -> set[str]:
    words = set()
    for token in _WORD.findall(_fold(text)):
        if len(token) >= 5:
            words.add(token[:-1] if token[-1] in "sx" else token)
    return words


def _clip(text: Any, limit: int = TEXT_CHARS) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# Authored lines and voices
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_guest_lines() -> dict[str, dict[str, str]]:
    data = json.loads(GUEST_LINES_PATH.read_text(encoding="utf-8"))
    return {str(cast): {str(topic): str(line) for topic, line in rows.items()} for cast, rows in data["lines"].items()}


def authored_guest_line(cast_id: str, topic: str) -> str:
    """The authored default for ``cast_id`` on ``topic`` (§7 fallback)."""

    return load_guest_lines().get(cast_id, {}).get(topic) or GENERIC_GUEST_LINE


@lru_cache(maxsize=1)
def _world_cast() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - the world file ships with the app
        logger.warning("revue: world.json unreadable ({})", exc)
        return {}
    return {str(row["id"]): row for row in data.get("cast") or [] if isinstance(row, dict) and row.get("id")}


def cast_name(cast_id: str) -> str:
    row = _world_cast().get(cast_id) or {}
    return str(row.get("name") or cast_id)


def cast_voice(cast_id: str) -> dict[str, str]:
    """Name, role, personality and register with the learner (season-one ``world.json``)."""

    row = _world_cast().get(cast_id) or {}
    return {
        "name": str(row.get("name") or cast_id),
        "role": _clip(row.get("role"), 300),
        "personality": _clip(row.get("personality"), 400),
        "register_with_user": _clip(row.get("register_with_user"), 160),
    }


def default_register(cast_id: str) -> str:
    """``tu`` or ``vous`` — what ``register_with_user`` starts with in the world file."""

    text = _fold((_world_cast().get(cast_id) or {}).get("register_with_user"))
    return "vous" if text.startswith("vous") else "tu"


# ---------------------------------------------------------------------------
# The learner's world (the serial thread) — read once per turn
# ---------------------------------------------------------------------------


@dataclass
class LearnerWorld:
    """The learner's living-story ledger and per-character memory (empty off a season)."""

    live: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, dict[str, Any]] = field(default_factory=dict)

    def cast_variants(self) -> dict[str, str]:
        from app.services.story_headline import cast_variants

        try:
            return dict(cast_variants(self.live))
        except Exception:  # noqa: BLE001 - an unreadable flag means "not chosen"
            return {}

    def camille_chosen(self) -> bool:
        """WP-116 phase 2: Camille appears only once the learner chose her look."""

        return CAMILLE_ID in self.cast_variants()


def learner_world(db: Session, user: Any) -> LearnerWorld:
    """The active serial thread's ``living_story`` and ``story_archive.cast_memory``."""

    try:
        from app.services import living_story
        from app.services.story_archive import cast_memory

        thread = living_story._active_thread(db, user)
        if thread is None:
            return LearnerWorld()
        live = (thread.state or {}).get(living_story.STATE_KEY) or {}
        try:
            memory = cast_memory(db, thread)
        except Exception as exc:  # noqa: BLE001 - the ledger alone still says something
            logger.bind(user_id=str(getattr(user, "id", ""))).warning("revue: cast memory unavailable ({})", exc)
            memory = {}
        return LearnerWorld(live=dict(live) if isinstance(live, dict) else {}, memory=memory)
    except Exception as exc:  # noqa: BLE001 - a broken thread must not cost the Revue
        logger.bind(user_id=str(getattr(user, "id", ""))).warning("revue: learner world unavailable ({})", exc)
        return LearnerWorld()


# ---------------------------------------------------------------------------
# The knowledge context
# ---------------------------------------------------------------------------


def _known_about(world: LearnerWorld, cast_id: str) -> list[dict[str, Any]]:
    rows = (world.memory.get(cast_id) or {}).get("known_about_you")
    if rows is None:
        try:
            from app.services.living_story import known_about_learner

            rows = known_about_learner(world.live, cast_id)
        except Exception:  # noqa: BLE001
            rows = []
    out = []
    for row in rows or []:
        if isinstance(row, dict) and row.get("text_fr"):
            out.append({"text_fr": _clip(row["text_fr"]), "date": row.get("date"), "scene_id": row.get("scene_id")})
    return out[:KNOWN_ABOUT_ROWS]


def _trust(world: LearnerWorld, cast_id: str) -> int | None:
    entry = world.memory.get(cast_id) or {}
    if "trust" in entry:
        return entry.get("trust")
    try:
        from app.services.living_story import trust_of

        return trust_of(world.live, cast_id)
    except Exception:  # noqa: BLE001
        return None


def _memories(db: Session, user_id: Any, cast_id: str, topic_words: set[str]) -> list[dict[str, Any]]:
    from app.db.models.npc import NPCMemory

    try:
        rows = list(
            db.scalars(
                select(NPCMemory)
                .where(NPCMemory.user_id == user_id)
                .order_by(NPCMemory.created_at.desc())
                .limit(60)
            )
        )
    except Exception as exc:  # noqa: BLE001 - no memory table, no memories
        logger.warning("revue: NPCMemory unavailable ({})", exc)
        return []
    own = [row for row in rows if row.npc_id == cast_id][:OWN_MEMORIES]
    others = [
        row for row in rows if row.npc_id != cast_id and topic_words and _words(row.content) & topic_words
    ][:TOPIC_MEMORIES]
    return [
        {
            "content": _clip(row.content),
            "npc_id": row.npc_id,
            "scene_id": row.scene_id,
            "memory_type": row.memory_type,
            "at": row.created_at.isoformat() if row.created_at else None,
            "own": row.npc_id == cast_id,
        }
        for row in [*own, *others]
    ]


def knowledge_for(
    db: Session,
    user: Any,
    cast_ids: Iterable[str],
    *,
    topic_text: str,
    refused: Callable[[str], bool],
    world: LearnerWorld | None = None,
) -> dict[str, dict[str, Any]]:
    """Per cast member on stage: voice, what they know about the learner, memories.

    ``refused(text)`` is the Knowledge check for the learner's season position: a row it
    refuses (a future reveal) is dropped. ``topic_text`` (the dossier's title, summary and
    angle) selects other characters' ``NPCMemory`` rows that mention the topic.
    """

    world = world if world is not None else learner_world(db, user)
    topic_words = _words(topic_text)
    out: dict[str, dict[str, Any]] = {}
    for cast_id in dict.fromkeys(cast_ids):
        memory = world.memory.get(cast_id) or {}
        known = [row for row in _known_about(world, cast_id) if not refused(row["text_fr"])]
        memories = [row for row in _memories(db, getattr(user, "id", None), cast_id, topic_words) if not refused(row["content"])]
        out[cast_id] = {
            "cast_id": cast_id,
            **cast_voice(cast_id),
            "register": str(memory.get("register") or default_register(cast_id)),
            "trust": _trust(world, cast_id),
            "tu_since": memory.get("tu_since"),
            "known_about_learner": known,
            "memories": memories,
        }
    return out


# ---------------------------------------------------------------------------
# Write-back
# ---------------------------------------------------------------------------


def ensure_npc(db: Session, cast_id: str) -> None:
    """Get-or-create the ``NPC`` row ``npc_memories.npc_id`` needs."""

    from app.db.models.npc import NPC

    if db.get(NPC, cast_id) is None:
        voice = cast_voice(cast_id)
        db.add(NPC(id=cast_id, name=voice["name"][:100], role=(voice["role"] or "Le Papier de Romy")[:255],
                   backstory="Le Papier de Romy (WP-119)"))
        db.flush()


def remember(
    db: Session,
    *,
    user_id: Any,
    cast_id: str,
    content: str,
    scene_id: str,
    quote: str | None = None,
    sentiment: str = "neutral",
) -> None:
    """One ``NPCMemory`` row (``interaction``) for what ``cast_id`` witnessed. Never commits."""

    from app.db.models.npc import NPCMemory

    ensure_npc(db, cast_id)
    db.add(NPCMemory(
        user_id=user_id,
        npc_id=cast_id,
        memory_type="interaction",
        content=content,
        scene_id=scene_id[:50],
        sentiment=sentiment,
        importance=5,
        player_quote=str(quote)[:1000] if quote else None,
    ))


__all__ = [
    "GUEST_LINES_PATH",
    "LearnerWorld",
    "authored_guest_line",
    "cast_name",
    "cast_voice",
    "default_register",
    "ensure_npc",
    "knowledge_for",
    "learner_world",
    "load_guest_lines",
    "remember",
]
