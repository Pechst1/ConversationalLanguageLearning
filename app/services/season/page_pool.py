"""Red-thread design, slice 5 (option B2): a contract day's page, shared.

A page written for one learner costs the same for every learner. The day's contract
makes that avoidable: it fixes what becomes true, and what is the learner's own
travels through slots (their marks) and the live exchange. So on a contract day, with
``STORY_SHARED_PAGES`` on:

* the writer is given the day **without the life** (:func:`shareable`): no past pages,
  no memory, no callbacks, no grammar plan, no review words, none of the dice a life
  rolls for itself;
* the accepted page is kept (:func:`store`), slots unfilled, the claims a page makes
  on a life cleared (:func:`sanitized`);
* a learner whose day gives the writer exactly the same input (:func:`frame`, hashed)
  is served that page (:func:`candidates`) after their own words fill its slots and
  **every guard has run on it in their own life**. A page a guard refuses for them is
  not served to them: their page is written, as before.

Nothing here decides alone that a page is good: the guards and the critic do, as
for any page. A context key this module does not know makes the day unshareable
(:func:`applies`), so a new personal input can never reach a shared page by default.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

#: At most this many pages are kept per frame: a second or third is written only when
#: the ones kept were refused by a reader's own guards.
MAX_PER_FRAME = 3

#: What the writer of a shared page still reads (top-level context keys).
SHARED_KEYS = frozenset(
    {
        "control_language",
        "learner",
        "level",
        "level_register",
        "line_translation",
        "chapter",
        "chapter_shape",
        "relationships",
        "season",
        "season_script",
        "world",
    }
)
#: Read by the writer, never part of the frame (the reader's own are used when served).
UNFRAMED_KEYS = frozenset({"can_dos"})
#: The life: what a shared page is written without, and the value that stands for it.
LIFE_KEYS: dict[str, Any] = {
    "agendas": [],
    "callback": None,
    "chronicle": [],
    "commitments": [],
    "consequences": [],
    "day_index": None,
    "drilled_words": [],
    "errata": [],
    "escalated_problems": [],
    "events": [],
    "gap_days": None,
    "kept_words": [],
    "legacy_beat": None,
    "lexicon_history": [],
    "moods": {},
    "plants_due": [],
    "recent_situations": [],
    "resolved_chapter_questions": [],
    "revision": None,
    "secrets": {},
    "story_so_far": [],
    "thread_id": None,
    "variety": {},
}
#: Dropped from the writer's context altogether (learning material and the long memory:
#: the owner's decision of 10 November, «Seite geteilt, Lernstoff im Training»).
DROPPED_KEYS = frozenset({"memory", "grammar_plan", "story_words", "mots_a_placer"})
#: The engine's own handles: never prompted, kept for the guards the writing runs.
RUNTIME_KEYS = frozenset({"_season", "lexicon", "lexical_coverage", "grammar", "words", "_contract_missing_slots"})
#: A day with one of these is written for its learner.
PERSONAL_DAY_KEYS = frozenset({"absence", "epreuve", "tutoiement", "act"})

_CHAPTER_KEYS = (
    "title_fr",
    "dramatic_question",
    "possible_developments",
    "shape",
    "beats",
    "location_id",
    "scene_count",
    "resolved",
    "exhausted",
)
_PAGE_RULE_KEYS = ("checked", "chapter", "voices", "address", "objective", "limits")
_CHAPTER_RULE_KEYS = ("open_new", "beat", "rule")
#: What a page claims about the life it was written in; a shared page claims nothing.
_LIFE_CLAIMS: dict[str, Any] = {
    "source_event_ids": [],
    "callback_fr": "",
    "callback_ref": None,
    "plant_fr": "",
    "pays_plant_id": None,
    "returns_to": None,
    "carries_over": False,
    "secret_shift": None,
    "arc_id": None,
    "arc_stage_id": None,
    "advances_arc": False,
    "season_thread": None,
    "thread_shift": None,
    "escalates_ref": None,
}


def enabled() -> bool:
    return bool(getattr(settings, "STORY_DAY_CONTRACT", False)) and bool(
        getattr(settings, "STORY_SHARED_PAGES", False)
    )


def _contract(context: dict) -> dict | None:
    today = ((context.get("season_script") or {}).get("brief") or {}).get("today") or {}
    return today.get("contract") if isinstance(today.get("contract"), dict) else None


def applies(context: dict) -> bool:
    """Whether today's page may be shared: a contract day's first act, an ordinary day
    of a running season, and a context this module knows key by key."""

    if not enabled() or _contract(context) is None:
        return False
    if any(context.get(key) for key in PERSONAL_DAY_KEYS):
        return False
    if str((context.get("season") or {}).get("phase") or "running") != "running":
        return False
    known = SHARED_KEYS | UNFRAMED_KEYS | DROPPED_KEYS | RUNTIME_KEYS | PERSONAL_DAY_KEYS | set(LIFE_KEYS)
    unknown = sorted(set(context) - known)
    if unknown:
        logger.warning("page_pool: the day is written for its learner (unknown context keys %s)", unknown)
        return False
    return True


def depersonalise(context: dict) -> None:
    """The learner's own context on a shared day: the learning material is not the
    page's (the training carries it), so nothing is measured or graded against it."""

    for key in ("grammar_plan", "story_words", "mots_a_placer"):
        context.pop(key, None)


def shareable(context: dict) -> dict:
    """The context a shared page is written from: the day without the life."""

    shared: dict[str, Any] = {key: value for key, value in context.items() if key in RUNTIME_KEYS | UNFRAMED_KEYS}
    for key in SHARED_KEYS:
        if key in context:
            shared[key] = copy.deepcopy(context[key])
    for key, neutral in LIFE_KEYS.items():
        shared[key] = copy.deepcopy(neutral)
    chapter = shared.get("chapter")
    if isinstance(chapter, dict):
        shared["chapter"] = {key: chapter[key] for key in _CHAPTER_KEYS if key in chapter}
    shared["relationships"] = {
        str(who): {"register": (row or {}).get("register")}
        for who, row in (shared.get("relationships") or {}).items()
    }
    season = shared.get("season")
    if isinstance(season, dict):
        shared["season"] = {key: season.get(key) for key in ("number", "phase")}
    world = shared.get("world")
    if isinstance(world, dict):
        world.update({"arcs": [], "suggested_arc": None, "complication_card": None})
    brief = (shared.get("season_script") or {}).get("brief")
    if isinstance(brief, dict):
        today = brief.get("today")
        if isinstance(today, dict):
            today.pop("callback", None)
        rules = brief.get("page_rules")
        if isinstance(rules, dict):
            rules = {key: rules[key] for key in _PAGE_RULE_KEYS if key in rules}
            if isinstance(rules.get("chapter"), dict):
                rules["chapter"] = {key: rules["chapter"][key] for key in _CHAPTER_RULE_KEYS if key in rules["chapter"]}
            brief["page_rules"] = rules
    return shared


def frame(shared: dict) -> dict:
    """What the writer of a shared page is given, as data: two days with the same
    frame get the same page."""

    return {key: shared.get(key) for key in sorted(SHARED_KEYS)}


@dataclass(frozen=True)
class PoolKey:
    season_id: str
    day_key: str
    band: str
    language: str
    frame_hash: str


def key_for(context: dict, shared: dict) -> PoolKey | None:
    block = context.get("season_script") or {}
    today = (block.get("brief") or {}).get("today") or {}
    premise = (today.get("required_premise") or {}).get("id")
    gap = (block.get("position") or {}).get("segment")
    if not (block.get("id") and gap and premise):
        return None
    body = json.dumps(frame(shared), sort_keys=True, ensure_ascii=False, default=str)
    return PoolKey(
        season_id=str(block["id"]),
        day_key=f"{gap}:{premise}"[:160],
        band=str(context.get("level") or "")[:8],
        language=str(context.get("control_language") or "")[:8],
        frame_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def sanitized(draft: dict) -> dict:
    """The draft as the pool keeps it: nothing it claims about one life."""

    return {**copy.deepcopy(draft), **copy.deepcopy(_LIFE_CLAIMS)}


def _rows(db: Session, key: PoolKey):
    from app.db.models.story_pool import StoryPoolPage

    return list(
        db.scalars(
            select(StoryPoolPage)
            .where(
                StoryPoolPage.season_id == key.season_id,
                StoryPoolPage.day_key == key.day_key,
                StoryPoolPage.frame_hash == key.frame_hash,
                StoryPoolPage.retired_at.is_(None),
            )
            .order_by(StoryPoolPage.created_at, StoryPoolPage.id)
        )
    )


def candidates(db: Session, key: PoolKey) -> list[Any]:
    """The pages kept for this frame, oldest first. Never raises: no pool, no page."""

    try:
        return _rows(db, key)
    except Exception:  # noqa: BLE001 - the pool never costs a learner their day
        logger.exception("page_pool: the pool could not be read")
        return []


def store(db: Session, key: PoolKey, draft: dict, *, engine_version: str, cost_usd: float = 0.0) -> Any | None:
    """Keep an accepted page for the learners who share its frame. Never raises."""

    from app.db.models.story_pool import StoryPoolPage

    try:
        with db.begin_nested():
            if len(_rows(db, key)) >= MAX_PER_FRAME:
                return None
            row = StoryPoolPage(
                season_id=key.season_id,
                day_key=key.day_key,
                band=key.band,
                language=key.language,
                frame_hash=key.frame_hash,
                draft=sanitized(draft),
                engine_version=str(engine_version)[:40],
                cost_usd=float(cost_usd or 0.0),
            )
            db.add(row)
            db.flush()
        return row
    except Exception:  # noqa: BLE001 - the pool never costs a learner their day
        logger.exception("page_pool: the page could not be kept")
        return None


def served(db: Session, row: Any) -> None:
    try:
        with db.begin_nested():
            row.served = int(row.served or 0) + 1
            db.flush()
    except Exception:  # noqa: BLE001 - a count never costs a learner their day
        logger.exception("page_pool: the served count could not be written")


def retire(db: Session, page_id: Any, *, reason: str = "") -> bool:
    """Take a page out of the pool for everyone who has not read it yet. The row stays."""

    from app.db.models.story_pool import StoryPoolPage

    row = db.get(StoryPoolPage, page_id)
    if row is None or row.retired_at is not None:
        return False
    row.retired_at = datetime.now(UTC)
    row.retired_reason = str(reason or "")[:200] or None
    db.flush()
    return True
