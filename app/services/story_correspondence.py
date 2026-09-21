"""WP-64 — Le Courrier vit dans l'histoire.

Everything a Courrier letter does to the living story lives here, and nothing
else in the mission stack touches ``thread.state["living_story"]`` directly.
``app/services/living_story.py`` owns that ledger for the Feuilleton; this module
is the second writer, and it writes the *same* rows — an ``events[]`` entry whose
witness is the correspondent, a mood/trust shift on the existing ``moods{}``
structure, and ``commitments[]`` opened or closed from the promises the learner
actually made — so that a rude letter to Romy is a fact tomorrow's scene can read.

Three rules shape the whole file.

**Non-deterministic, not random.** Every choice that could have gone another way
is a seeded die: ``sha256(thread/user id : week : …)``. Two learners get different
affairs on the same day; the same learner replayed in a test gets the same one.

**State over prose.** Chains, soft deadlines, cooled correspondents and the
story-born letter ledger are rows under ``thread.state["courrier"]`` — a namespace
of our own, deliberately outside ``living_story`` so WP-62's ``chronicle``,
``consequences``, ``planted`` and ``secrets`` keys cannot collide with ours.

**Consequences never punish.** A missed letter cools the correspondent by one
step and is mentioned the next time they write. Trust — the slow number — is
never taken away for a letter that was merely clumsy, and an ignored letter
produces a remark, never a failure screen.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.mission import RealWorldMission
from app.db.models.serial import SerialThread
from app.db.models.user import User

# The living story's own ledger keys. Imported rather than re-spelled so a rename
# in living_story.py breaks loudly here instead of silently writing a second,
# orphaned event list.
from app.services.living_story import MAX_HISTORY, MOOD_RANGE, STATE_KEY, TRUST_RANGE

#: Our namespace on ``thread.state``. Never nested inside ``living_story``: WP-62
#: is adding keys there and two agents writing one dict is how ledgers get lost.
CORRESPONDENCE_KEY = "courrier"

#: Stamped on every event this module writes, so the Feuilleton's director can
#: tell «ce qui s'est dit dans une lettre» from «ce qui s'est passé dans la scène».
EVENT_SOURCE = "courrier"

#: What a finished letter did for the person who wrote it.
OUTCOMES = ("kept", "partial", "missed", "ignored")

#: An affair is 2 to 4 letters. Below two it is not a chain; above four the
#: learner is answering the same administrative saga for a week.
CHAIN_LENGTHS = (2, 3, 4)

#: How often a fresh standalone letter opens an affair rather than standing alone.
CHAIN_OPEN_PROBABILITY = 0.45

#: A letter's soft deadline, in days. Soft: nothing is lost when it passes.
EXPIRY_DAYS = (3, 4, 5)

#: At most two letters a week may be born from a journey scene.
STORY_LETTERS_PER_WEEK = 2

#: How likely a fresh journey event is to make a character pick up a pen.
STORY_LETTER_PROBABILITY = 0.5

#: Mood and trust deltas per outcome. Trust never falls for a clumsy letter —
#: only silence and an actively cold exchange move the slow number.
_MOOD_SHIFT: dict[str, tuple[int, int]] = {
    "kept": (1, 1),
    "partial": (0, 0),
    "missed": (-1, 0),
    "ignored": (-1, -1),
}

_SHIFT_LABEL = {"kept": "warmer", "partial": "steady", "missed": "colder", "ignored": "colder"}


# ---------------------------------------------------------------------------
# Seeded dice
# ---------------------------------------------------------------------------


def dice(*parts: Any) -> float:
    """A reproducible float in [0, 1) for this exact tuple of facts.

    The only randomness in the Courrier. Seeded on identity + calendar + purpose,
    so a test that pins the ids gets the same affair every run and two learners on
    the same Tuesday do not.
    """

    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def dice_pick(items: Sequence[Any], *seed: Any) -> Any:
    """One element of ``items``, chosen by the seed. ``None`` for an empty sequence."""

    items = list(items)
    if not items:
        return None
    return items[min(len(items) - 1, int(dice(*seed) * len(items)))]


def weighted_pick(weighted: Sequence[tuple[Any, float]], *seed: Any) -> Any:
    """Seeded weighted sampling. Zero-weight candidates can never be drawn.

    This is the replacement for ``ordered[0]``: recency lowers a weight instead of
    sorting a catalogue, so the same learner never sees the same bakery twice in a
    row and two learners never walk the same catalogue order.
    """

    pool = [(item, float(weight)) for item, weight in weighted if float(weight) > 0]
    if not pool:
        pool = [(item, 1.0) for item, _ in weighted]
    if not pool:
        return None
    total = sum(weight for _, weight in pool)
    roll = dice(*seed) * total
    for item, weight in pool:
        roll -= weight
        if roll <= 0:
            return item
    return pool[-1][0]


def seeded_order(items: Sequence[Any], *seed: Any) -> list[Any]:
    """A seeded permutation of ``items`` (Fisher–Yates, driven by :func:`dice`).

    Used where a *rotation* must stay complete — every fuel source has to come
    round — but the order it comes round in should still be this learner's own
    rather than a catalogue index. Reproducible for a given seed.
    """

    result = list(items)
    for index in range(len(result) - 1, 0, -1):
        swap = min(index, int(dice(*seed, index) * (index + 1)))
        result[index], result[swap] = result[swap], result[index]
    return result


def iso_week_key(moment: datetime | None = None) -> str:
    """``2026-W38`` — the bucket the weekly caps and the weekly seeds count in."""

    moment = moment or datetime.now(UTC)
    iso = moment.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ---------------------------------------------------------------------------
# Thread and state access
# ---------------------------------------------------------------------------


def active_thread(db: Session, user: User) -> SerialThread | None:
    """The learner's live story thread, whatever ``SERIAL_WORLD_ENABLED`` says.

    The flag gates the *legacy* serial surface. A living-story thread exists and
    accumulates state regardless, and a letter written into it must land in the
    same ledger — that is the whole point of the package.
    """

    return (
        db.query(SerialThread)
        .filter(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
        .first()
    )


def living_story_thread(db: Session, user: User) -> SerialThread | None:
    """The thread only when it already carries a living story to write into."""

    thread = active_thread(db, user)
    if thread and isinstance((thread.state or {}).get(STATE_KEY), dict):
        return thread
    return None


def _state(thread: SerialThread) -> dict[str, Any]:
    return dict(thread.state or {})


def correspondence_state(thread: SerialThread | None) -> dict[str, Any]:
    """Our own namespace: chains, cooled correspondents, story-born ledger."""

    if thread is None:
        return {}
    value = (thread.state or {}).get(CORRESPONDENCE_KEY)
    return dict(value) if isinstance(value, dict) else {}


def _save(thread: SerialThread, state: dict[str, Any]) -> None:
    # SQLAlchemy only notices a JSON column that is *replaced*, never one mutated
    # in place — the 2026-09 serial-state bug that lost a whole episode's delta.
    thread.state = dict(state)


# ---------------------------------------------------------------------------
# Who wrote the letter
# ---------------------------------------------------------------------------


def slug(value: Any) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_")


def correspondent_of(mission: RealWorldMission | None) -> dict[str, Any]:
    """The person on the other side of this letter, as one stable identity.

    A living-story letter is addressed to a cast member (``serial_character_id``);
    a standalone one to a named contact from the scenario bank or the model. Both
    resolve to one id so the thread with one person survives across both kinds.
    """

    if mission is None:
        return {}
    prompt = mission.prompt_payload or {}
    messenger = prompt.get("messenger") if isinstance(prompt.get("messenger"), dict) else {}
    variety = prompt.get("variety") if isinstance(prompt.get("variety"), dict) else {}
    name = str(messenger.get("contact_name") or variety.get("contact") or "").strip()
    character_id = str(prompt.get("serial_character_id") or "").strip()
    identifier = character_id or getattr(mission, "correspondent_id", None) or slug(name)
    if not identifier:
        return {}
    return {
        "id": str(identifier),
        "name": name or str(identifier).replace("_", " ").title(),
        "role": str(messenger.get("contact_role") or variety.get("domain_label") or "").strip(),
        "initials": str(messenger.get("contact_initials") or "").strip(),
        "channel": str(variety.get("channel") or "").strip(),
        "domain": str(variety.get("domain") or "").strip(),
    }


def moods_of(thread: SerialThread | None) -> dict[str, Any]:
    if thread is None:
        return {}
    live = (thread.state or {}).get(STATE_KEY)
    moods = live.get("moods") if isinstance(live, dict) else None
    return dict(moods) if isinstance(moods, dict) else {}


#: One French line a learner may read above the letter. Printed text, so French.
_MOOD_LINES = {
    -2: "Toujours fâché(e) depuis votre dernier échange.",
    -1: "Un peu distant(e) en ce moment.",
    0: "Neutre : rien à rattraper, rien d'acquis.",
    1: "De bonne humeur avec vous.",
    2: "Ravi(e) d'avoir de vos nouvelles.",
}


def mood_line(thread: SerialThread | None, correspondent_id: str | None) -> str | None:
    """The correspondent's current feeling, in one French sentence, or ``None``."""

    entry = moods_of(thread).get(str(correspondent_id or ""))
    if not isinstance(entry, dict) or "mood" not in entry:
        return None
    mood = max(MOOD_RANGE[0], min(MOOD_RANGE[1], int(entry.get("mood") or 0)))
    trust = max(TRUST_RANGE[0], min(TRUST_RANGE[1], int(entry.get("trust") or 0)))
    line = _MOOD_LINES.get(mood, _MOOD_LINES[0])
    if trust >= 4:
        return f"{line} Vous confie des choses."
    if trust <= 1:
        return f"{line} Encore sur la réserve."
    return line


# ---------------------------------------------------------------------------
# The thread with one person
# ---------------------------------------------------------------------------


def _compact(value: Any, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].strip()


def summarise_letter(mission: RealWorldMission) -> str:
    """One French line describing what this letter was about."""

    prompt = mission.prompt_payload or {}
    messenger = prompt.get("messenger") if isinstance(prompt.get("messenger"), dict) else {}
    return (
        _compact(messenger.get("thread_title"), limit=120)
        or _compact(mission.title, limit=120)
        or "Une lettre du Courrier."
    )


def thread_history(
    db: Session,
    *,
    user: User,
    correspondent_id: str | None,
    limit: int = 3,
    exclude_mission_id: Any = None,
) -> list[dict[str, Any]]:
    """The last ``limit`` finished letters with this person, oldest first.

    This is the continuity the Courrier never had: the actor prompt and the card
    both read it, so the baker remembers she already set aside a loaf.
    """

    if not correspondent_id:
        return []
    rows = (
        db.query(RealWorldMission)
        .filter(
            RealWorldMission.user_id == user.id,
            RealWorldMission.correspondent_id == str(correspondent_id),
            RealWorldMission.status.in_(["completed", "lapsed"]),
        )
        .order_by(RealWorldMission.completed_at.desc().nullslast(), RealWorldMission.created_at.desc())
        .limit(limit + 1)
        .all()
    )
    history: list[dict[str, Any]] = []
    for row in rows:
        if exclude_mission_id is not None and str(row.id) == str(exclude_mission_id):
            continue
        recap = row.recap_payload or {}
        history.append(
            {
                "mission_id": str(row.id),
                "title": row.title,
                "summary_fr": _compact(recap.get("courrier_summary_fr") or summarise_letter(row), limit=180),
                "outcome": str(recap.get("courrier_outcome") or ("ignored" if row.status == "lapsed" else "")) or None,
                "stakes_level": int(getattr(row, "stakes_level", None) or 1),
                "chain_index": getattr(row, "chain_index", None),
                "at": row.completed_at.isoformat() if row.completed_at else (row.created_at.isoformat() if row.created_at else None),
            }
        )
        if len(history) >= limit:
            break
    history.reverse()
    return history


def cooling_note(thread: SerialThread | None, correspondent_id: str | None) -> str | None:
    """What an ignored letter left behind, for the correspondent to mention once."""

    entry = correspondence_state(thread).get("cooled", {}).get(str(correspondent_id or ""))
    if not isinstance(entry, dict):
        return None
    return _compact(entry.get("mention_fr"), limit=200) or None


def clear_cooling(db: Session, *, user: User, correspondent_id: str | None) -> None:
    """The remark is made once; after that the silence is water under the bridge."""

    thread = active_thread(db, user)
    if thread is None or not correspondent_id:
        return
    state = _state(thread)
    courrier = dict(state.get(CORRESPONDENCE_KEY) or {})
    cooled = dict(courrier.get("cooled") or {})
    if str(correspondent_id) not in cooled:
        return
    cooled.pop(str(correspondent_id), None)
    courrier["cooled"] = cooled
    state[CORRESPONDENCE_KEY] = courrier
    _save(thread, state)
    db.add(thread)


# ---------------------------------------------------------------------------
# Outcome from the corrector's own flags
# ---------------------------------------------------------------------------


def outcome_from_objectives(
    *,
    objectives: Sequence[dict[str, Any]] | None,
    progress_by_id: dict[str, dict[str, Any]] | None,
    had_submission: bool = True,
) -> str:
    """``kept`` | ``partial`` | ``missed`` from the per-objective flags.

    The old success test read keywords out of ``branch_state`` ("does the message
    contain a question mark?"). The corrector already returns, per objective,
    whether the learner handled it; that is the measured signal and this is the
    only place it is turned into a word.
    """

    objectives = [item for item in (objectives or []) if isinstance(item, dict)]
    progress_by_id = progress_by_id or {}
    if not had_submission:
        return "missed"
    scored = [item for item in objectives if item.get("required")] or objectives
    if not scored:
        return "partial"
    met = sum(1 for item in scored if progress_by_id.get(str(item.get("id")), {}).get("met"))
    if met >= len(scored):
        return "kept"
    optional_met = any(
        progress_by_id.get(str(item.get("id")), {}).get("met")
        for item in objectives
        if not item.get("required")
    )
    if met or optional_met:
        return "partial"
    return "missed"


# ---------------------------------------------------------------------------
# Promises
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")

#: First-person commitments a French learner actually writes: near future
#: («je vais passer»), simple future («je passerai», never the ``-rais``
#: conditional, which is politeness and not a promise), and explicit undertakings.
_PROMISE_PATTERNS = (
    re.compile(r"\bj(?:e|')\s*(?:vais|vais\s+vous|vais\s+te)\s+\w+", re.IGNORECASE),
    re.compile(r"\bj(?:e|')\s*(?:\w+)?(?<!ai)(?:[a-zà-ÿ]{2,})rai\b", re.IGNORECASE),
    re.compile(r"\bje\s+m['’]engage\b", re.IGNORECASE),
    re.compile(r"\bje\s+m['’]en\s+occupe\b", re.IGNORECASE),
    re.compile(r"\b(?:c['’]est\s+)?promis\b", re.IGNORECASE),
    re.compile(r"\bon\s+(?:se\s+)?(?:voit|retrouve)\b", re.IGNORECASE),
)


def promises_in(text: str, *, limit: int = 2) -> list[dict[str, str]]:
    """The promises this letter makes, as quotable sentences.

    Deterministic, and deliberately conservative: a commitment the story will hold
    the learner to must come from something they actually wrote, never from a
    model's impression of what they meant.
    """

    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in _SENTENCE_SPLIT.split(" ".join(str(text or "").split())):
        candidate = sentence.strip()
        if len(candidate) < 8:
            continue
        if not any(pattern.search(candidate) for pattern in _PROMISE_PATTERNS):
            continue
        key = _folded(candidate)
        if key in seen:
            continue
        seen.add(key)
        found.append({"text_fr": _compact(candidate, limit=180), "source_quote": _compact(candidate, limit=180)})
        if len(found) >= limit:
            break
    return found


def _folded(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", folded.lower())


def _promise_overlap(left: str, right: str) -> float:
    left_words = {word for word in _folded(left).split() if len(word) > 3}
    right_words = {word for word in _folded(right).split() if len(word) > 3}
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / float(min(len(left_words), len(right_words)))


# ---------------------------------------------------------------------------
# The writeback
# ---------------------------------------------------------------------------


def record_letter(
    db: Session,
    *,
    user: User,
    mission: RealWorldMission,
    outcome: str,
    learner_text: str = "",
    summary_fr: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Write one finished letter into the living story. Idempotent per mission.

    Returns the stored event, or ``None`` when this learner has no living story to
    write into (a brand-new account, or a thread that only ever ran the legacy
    serial). Never raises into ``complete()``: a story that cannot be written is a
    logged warning, not a mission the learner cannot finish.
    """

    outcome = outcome if outcome in OUTCOMES else "partial"
    thread = living_story_thread(db, user)
    if thread is None:
        return None
    correspondent = correspondent_of(mission)
    if not correspondent.get("id"):
        return None
    now = now or datetime.now(UTC)
    event_id = f"courrier:{mission.id}"
    state = _state(thread)
    live = dict(state.get(STATE_KEY) or {})
    events = list(live.get("events") or [])
    if any(isinstance(item, dict) and item.get("id") == event_id for item in events):
        return next(item for item in events if isinstance(item, dict) and item.get("id") == event_id)

    character_id = str(correspondent["id"])
    quotes = [item["source_quote"] for item in promises_in(learner_text)]
    event = {
        "id": event_id,
        "scene_id": None,
        "witnesses": [character_id],
        "summary_fr": _compact(summary_fr or _default_summary(mission, correspondent, outcome), limit=280),
        "source_quotes": quotes,
        "outcome": outcome,
        "at": now.isoformat(),
        # WP-64's own stamp. The director reads `events[]` as one list; this key
        # lets it say «dans votre lettre» rather than «dans la scène».
        "source": EVENT_SOURCE,
        "mission_id": str(mission.id),
    }
    live["events"] = [*events, event][-MAX_HISTORY:]
    live["moods"] = _moods_after_letter(live.get("moods") or {}, character_id, outcome, event_id)
    live["commitments"] = _commitments_after_letter(
        list(live.get("commitments") or []),
        learner_text=learner_text,
        outcome=outcome,
        event_id=event_id,
        character_id=character_id,
    )
    state[STATE_KEY] = live
    state["story_so_far"] = [*list(state.get("story_so_far") or []), event["summary_fr"]][-40:]
    _save(thread, state)
    db.add(thread)
    logger.debug("courrier: wrote {} into the living story ({})", event_id, outcome)
    return event


def _default_summary(mission: RealWorldMission, correspondent: dict[str, Any], outcome: str) -> str:
    name = correspondent.get("name") or "votre correspondant"
    topic = summarise_letter(mission)
    if outcome == "kept":
        return f"Vous avez écrit à {name} : {topic}. Tout était réglé."
    if outcome == "partial":
        return f"Vous avez écrit à {name} : {topic}. Il reste un point en suspens."
    if outcome == "ignored":
        return f"{name} vous a écrit à propos de {topic}. Vous n'avez jamais répondu."
    return f"Vous avez écrit à {name} : {topic}. Le nécessaire n'a pas été dit."


def _moods_after_letter(
    moods: dict[str, Any],
    character_id: str,
    outcome: str,
    event_id: str,
) -> dict[str, Any]:
    """The correspondent's feeling after this letter. Idempotent per event.

    Unlike the journey's own ``moods_after_turn``, nobody else drifts: a letter is
    a private exchange and the rest of the cast did not hear it.
    """

    moods = {key: dict(value) for key, value in (moods or {}).items() if isinstance(value, dict)}
    entry = moods.get(character_id) or {"mood": 0, "trust": 2}
    if entry.get("last_event_id") == event_id:
        return moods
    delta_mood, delta_trust = _MOOD_SHIFT.get(outcome, (0, 0))
    entry["mood"] = max(MOOD_RANGE[0], min(MOOD_RANGE[1], int(entry.get("mood") or 0) + delta_mood))
    entry["trust"] = max(TRUST_RANGE[0], min(TRUST_RANGE[1], int(entry.get("trust") or 2) + delta_trust))
    entry["last_shift"] = _SHIFT_LABEL.get(outcome, "steady")
    entry["last_event_id"] = event_id
    entry["last_source"] = EVENT_SOURCE
    moods[character_id] = entry
    return moods


def _commitments_after_letter(
    commitments: list[dict[str, Any]],
    *,
    learner_text: str,
    outcome: str,
    event_id: str,
    character_id: str,
) -> list[dict[str, Any]]:
    """Open the promises the letter made; close the ones it delivered on."""

    rows = [dict(item) for item in commitments if isinstance(item, dict)]
    promises = promises_in(learner_text)
    # A letter that settles the matter delivers on whatever this correspondent was
    # already owed and that the letter visibly restates.
    if outcome == "kept":
        for row in rows:
            if row.get("status") != "open":
                continue
            if character_id not in (row.get("witnesses") or []):
                continue
            if _promise_overlap(str(row.get("text_fr") or ""), learner_text) >= 0.4:
                row.update(status="resolved", resolved_by=event_id)
    for index, promise in enumerate(promises):
        duplicate = next(
            (
                row
                for row in rows
                if row.get("status") == "open"
                and _promise_overlap(str(row.get("text_fr") or ""), promise["text_fr"]) >= 0.6
            ),
            None,
        )
        if duplicate is not None:
            duplicate["restatements"] = [
                *list(duplicate.get("restatements") or []),
                {"text_fr": promise["text_fr"], "source_quote": promise["source_quote"], "source_event_id": event_id},
            ][-5:]
            continue
        rows.append(
            {
                "id": f"{event_id}:commitment:{index}",
                "text_fr": promise["text_fr"],
                "source_quote": promise["source_quote"],
                "source_event_id": event_id,
                "witnesses": [character_id],
                "status": "open",
                "source": EVENT_SOURCE,
            }
        )
    # Same rule as the journey writer: an open promise is never dropped to fit a cap.
    return [row for row in rows if row.get("status") == "open"] + [
        row for row in rows if row.get("status") != "open"
    ][-20:]


# ---------------------------------------------------------------------------
# Chains
# ---------------------------------------------------------------------------


def plan_chain(*, user: User, correspondent_id: str, ordinal: int, week: str) -> dict[str, Any] | None:
    """Seeded decision: does this fresh letter open an affair, and how long?"""

    if not correspondent_id:
        return None
    if dice("chain", user.id, correspondent_id, week, ordinal) >= CHAIN_OPEN_PROBABILITY:
        return None
    total = dice_pick(CHAIN_LENGTHS, "chain-length", user.id, correspondent_id, week, ordinal)
    return {
        "chain_id": f"chain:{slug(correspondent_id)}:{week}:{ordinal}",
        "index": 1,
        "total": int(total or 2),
    }


def expiry_for(*, user: User, mission_id: Any, created_at: datetime, stakes_level: int = 1) -> datetime:
    """A soft deadline. Higher stakes come due sooner; nothing is ever lost."""

    days = dice_pick(EXPIRY_DAYS, "expiry", user.id, mission_id) or 3
    return created_at + timedelta(days=max(2, int(days) - max(0, int(stakes_level) - 1)))


def open_chain_step(
    db: Session,
    *,
    user: User,
    mission: RealWorldMission,
    outcome: str,
) -> dict[str, Any] | None:
    """Queue letter k+1 of an affair once letter k is answered.

    The outcome of k is carried forward verbatim, because that is what shapes k+1:
    a settled letter earns a warm follow-up, a missed one earns a chase.
    """

    chain_id = getattr(mission, "chain_id", None)
    if not chain_id:
        return None
    index = int(getattr(mission, "chain_index", None) or 1)
    total = int(getattr(mission, "chain_total", None) or 1)
    if index >= total:
        close_chain(db, user=user, chain_id=chain_id)
        return None
    thread = active_thread(db, user)
    if thread is None:
        return None
    correspondent = correspondent_of(mission)
    step = {
        "chain_id": str(chain_id),
        "index": index + 1,
        "total": total,
        "correspondent": correspondent,
        # The setup is pinned, not re-rolled: letter 2 is the same person about the
        # same thing. `_choose_variety` reads this as `forced_domain`.
        "domain": correspondent.get("domain") or None,
        "after_outcome": outcome,
        "after_summary_fr": summarise_letter(mission),
        "after_mission_id": str(mission.id),
        # The affair tightens: letter 2 of 3 matters more than letter 1.
        "stakes_level": max(1, min(3, int(getattr(mission, "stakes_level", None) or 1) + 1)),
        "queued_at": datetime.now(UTC).isoformat(),
    }
    state = _state(thread)
    courrier = dict(state.get(CORRESPONDENCE_KEY) or {})
    chains = dict(courrier.get("chains") or {})
    chains[str(chain_id)] = step
    courrier["chains"] = chains
    state[CORRESPONDENCE_KEY] = courrier
    _save(thread, state)
    db.add(thread)
    return step


def pending_chain_step(db: Session, *, user: User) -> dict[str, Any] | None:
    """The next queued letter of an open affair, if one is waiting."""

    chains = correspondence_state(active_thread(db, user)).get("chains") or {}
    steps = [value for value in chains.values() if isinstance(value, dict) and value.get("index")]
    if not steps:
        return None
    steps.sort(key=lambda item: str(item.get("queued_at") or ""))
    return steps[0]


def close_chain(db: Session, *, user: User, chain_id: str | None) -> None:
    thread = active_thread(db, user)
    if thread is None or not chain_id:
        return
    state = _state(thread)
    courrier = dict(state.get(CORRESPONDENCE_KEY) or {})
    chains = dict(courrier.get("chains") or {})
    if str(chain_id) not in chains:
        return
    chains.pop(str(chain_id), None)
    courrier["chains"] = chains
    state[CORRESPONDENCE_KEY] = courrier
    _save(thread, state)
    db.add(thread)


# ---------------------------------------------------------------------------
# The ignored letter
# ---------------------------------------------------------------------------


def lapse_overdue_letters(
    db: Session,
    *,
    user: User,
    now: datetime | None = None,
) -> list[RealWorldMission]:
    """A letter past its soft deadline stops waiting — and is felt, not punished.

    Only chain letters lapse. The weekly mission is the learner's standing
    invitation and lapsing it would strand the week behind a unique constraint;
    an affair, by contrast, is a person waiting for an answer, and a person
    eventually stops waiting.
    """

    now = now or datetime.now(UTC)
    rows = (
        db.query(RealWorldMission)
        .filter(
            RealWorldMission.user_id == user.id,
            RealWorldMission.status.in_(["available", "in_progress"]),
            RealWorldMission.chain_id.isnot(None),
            RealWorldMission.expires_at.isnot(None),
            RealWorldMission.cadence != "weekly",
        )
        .all()
    )
    lapsed: list[RealWorldMission] = []
    for mission in rows:
        deadline = mission.expires_at
        if deadline is None:
            continue
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if deadline > now:
            continue
        mission.status = "lapsed"
        mission.outcome = "ignored"
        mission.recap_payload = {
            **(mission.recap_payload or {}),
            "courrier_outcome": "ignored",
            "courrier_summary_fr": summarise_letter(mission),
            "lapsed_at": now.isoformat(),
        }
        db.add(mission)
        correspondent = correspondent_of(mission)
        record_letter(
            db,
            user=user,
            mission=mission,
            outcome="ignored",
            learner_text="",
            now=now,
        )
        _note_cooling(db, user=user, mission=mission, correspondent=correspondent, now=now)
        close_chain(db, user=user, chain_id=getattr(mission, "chain_id", None))
        lapsed.append(mission)
    if lapsed:
        db.commit()
    return lapsed


def _note_cooling(
    db: Session,
    *,
    user: User,
    mission: RealWorldMission,
    correspondent: dict[str, Any],
    now: datetime,
) -> None:
    """Leave the remark the correspondent will make next time they write."""

    thread = active_thread(db, user)
    if thread is None or not correspondent.get("id"):
        return
    state = _state(thread)
    courrier = dict(state.get(CORRESPONDENCE_KEY) or {})
    cooled = dict(courrier.get("cooled") or {})
    cooled[str(correspondent["id"])] = {
        "mission_id": str(mission.id),
        "at": now.isoformat(),
        # Read by the actor prompt, not printed as-is: the character mentions the
        # silence in their own words, once, and then lets it go.
        "mention_fr": (
            f"Vous n'avez jamais répondu à leur message sur « {summarise_letter(mission)} ». "
            "Mentionnez-le une fois, sans reproche, puis passez à autre chose."
        ),
    }
    courrier["cooled"] = cooled
    state[CORRESPONDENCE_KEY] = courrier
    _save(thread, state)
    db.add(thread)


# ---------------------------------------------------------------------------
# Story-born letters
# ---------------------------------------------------------------------------


def story_letter_candidate(
    db: Session,
    *,
    user: User,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """A character who wants to write to the learner about what just happened.

    Seeded, capped at two a week, and only ever about an event that is already in
    the ledger — a letter about a scene that did not happen is a fabricated memory,
    which is the one thing the story engine's guards exist to prevent.
    """

    thread = living_story_thread(db, user)
    if thread is None:
        return None
    now = now or datetime.now(UTC)
    week = iso_week_key(now)
    courrier = correspondence_state(thread)
    ledger = [item for item in (courrier.get("story_born") or []) if isinstance(item, dict)]
    if sum(1 for item in ledger if item.get("week") == week) >= STORY_LETTERS_PER_WEEK:
        return None
    used = {str(item.get("event_id")) for item in ledger}
    live = (thread.state or {}).get(STATE_KEY) or {}
    events = [
        item
        for item in reversed(list(live.get("events") or []))
        if isinstance(item, dict)
        and item.get("scene_id")
        and item.get("id")
        and str(item["id"]) not in used
    ]
    # Newest first, and each event rolls its own die: a scene that did not move
    # anybody to write is simply skipped, rather than blocking the two or three
    # behind it. The weekly cap above is what keeps this from becoming a firehose.
    event = next(
        (
            item
            for item in events[:8]
            if dice("story-letter", thread.id, item.get("id")) < STORY_LETTER_PROBABILITY
        ),
        None,
    )
    if event is None:
        return None
    witnesses = [str(item) for item in (event.get("witnesses") or []) if str(item or "").strip()]
    if not witnesses:
        return None
    character_id = dice_pick(sorted(witnesses), "story-letter-who", thread.id, event.get("id"))
    return {
        "event_id": str(event.get("id")),
        "character_id": str(character_id),
        "character_name": _cast_name(thread, str(character_id)),
        "summary_fr": _compact(event.get("summary_fr"), limit=240),
        "source_quotes": [str(item) for item in (event.get("source_quotes") or [])][:2],
        "week": week,
    }


def note_story_letter(db: Session, *, user: User, candidate: dict[str, Any], mission_id: Any) -> None:
    """Record that this event has produced its letter, so it never produces two."""

    thread = active_thread(db, user)
    if thread is None:
        return
    state = _state(thread)
    courrier = dict(state.get(CORRESPONDENCE_KEY) or {})
    ledger = [item for item in (courrier.get("story_born") or []) if isinstance(item, dict)]
    ledger.append(
        {
            "event_id": str(candidate.get("event_id")),
            "character_id": str(candidate.get("character_id")),
            "week": str(candidate.get("week") or iso_week_key()),
            "mission_id": str(mission_id),
        }
    )
    courrier["story_born"] = ledger[-24:]
    state[CORRESPONDENCE_KEY] = courrier
    _save(thread, state)
    db.add(thread)


def _cast_name(thread: SerialThread, character_id: str) -> str:
    world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
    for member in world.get("cast") or []:
        if isinstance(member, dict) and str(member.get("id")) == character_id:
            return str(member.get("name") or character_id)
    return character_id.replace("_", " ").title()


def story_letter_context(candidate: dict[str, Any]) -> dict[str, Any]:
    """The custom context a story-born letter is generated from.

    Phrased as an instruction to the scenario writer, and grounded entirely in the
    stored event: the character writes *about what happened*, they do not invent a
    past the learner never played.
    """

    name = candidate.get("character_name") or "Un personnage"
    summary = candidate.get("summary_fr") or "ce qui vient de se passer"
    return {
        "scenario": (
            f"{name} vous écrit après ce qui vient de se passer dans le feuilleton : {summary} "
            f"Répondez-lui en français. N'inventez aucun fait nouveau : parlez de cet épisode-là."
        ),
        "desired_outcome": f"{name} sait ce que vous en pensez et ce que vous comptez faire ensuite.",
        "relationship": str(candidate.get("character_id") or ""),
        "source": "story_born",
    }


__all__ = [
    "CHAIN_LENGTHS",
    "CHAIN_OPEN_PROBABILITY",
    "CORRESPONDENCE_KEY",
    "EVENT_SOURCE",
    "EXPIRY_DAYS",
    "OUTCOMES",
    "STORY_LETTERS_PER_WEEK",
    "active_thread",
    "clear_cooling",
    "close_chain",
    "cooling_note",
    "correspondence_state",
    "correspondent_of",
    "dice",
    "dice_pick",
    "expiry_for",
    "iso_week_key",
    "lapse_overdue_letters",
    "living_story_thread",
    "mood_line",
    "moods_of",
    "note_story_letter",
    "open_chain_step",
    "outcome_from_objectives",
    "pending_chain_step",
    "plan_chain",
    "promises_in",
    "record_letter",
    "seeded_order",
    "slug",
    "story_letter_candidate",
    "story_letter_context",
    "summarise_letter",
    "thread_history",
    "weighted_pick",
]
