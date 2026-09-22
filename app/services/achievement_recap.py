"""WP-79 — the end of the day, as a reward: the recap's extra facts.

``DailyJourneyService._build_recap`` calls :func:`recap_extras` once, while the
finish transaction is open. Every fact below is *read* from something the app
already recorded; nothing is estimated and nothing is a formula over a word
count:

* ``steps_done`` — steps the learner completed, the honest fallback when the
  active minutes were not measurable;
* ``words`` — the vocabulary targets the day's graded steps observed, minus
  the ones that were "not yet";
* ``mood`` — the day's character in the living story's WP-61 mood ledger. The
  shift is only claimed when the ledger's last move was this journey's own
  exchange (``last_event_id == journey:<id>:story``);
* ``keepsake`` — the vignette WP-09 already minted for a completed day;
* ``teaser`` — «La suite demain», in the same source order as WP-80's morning
  push: the living story's ``next_teaser``, then the resolution's last
  forward-looking line, then an authored line per band that promises nothing;
* ``level`` / ``level_up`` — the CEFR estimate, and a move up since the
  previous recap. The move is detected by comparing with the previous recap's
  stored ``level``, so it is shown exactly once, and a learner whose recaps
  predate WP-79 is never told they "moved" on no evidence.

Everything here is defensive: a failure logs and yields nothing, because a
reward line is never worth the day (the L5 lesson).
"""
from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User

#: The living-story state key (``app/services/living_story.py``, read-only here).
LIVING_STORY_KEY = "living_story"

#: A resolution line that looks forward. Explicit markers only: a guess that
#: turns an ending into a promise would be a lie about the plot.
FORWARD_MARKERS = re.compile(
    r"\b(demain|bient[oô]t|la prochaine|prochaine fois|à suivre|la suite|ce soir|"
    r"plus tard|on verra|rendez-vous|à tout à l['’]heure|je vous (?:attends|raconte|dirai|"
    r"raconterai|montrerai)|on se revoit|on se voit)\b",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")


def _event_id(journey: DailyJourney) -> str:
    return f"journey:{journey.id}:story"


def _clean(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].rstrip() if len(text) > limit else text


# ---------------------------------------------------------------------------
# Steps and words
# ---------------------------------------------------------------------------


def steps_done(journey: DailyJourney) -> int:
    return sum(1 for step in journey.steps if str(step.status) == "completed")


def recap_words(practiced: list[Any]) -> list[dict[str, Any]]:
    """Distinct vocabulary targets observed today, in order, minus "not yet"."""

    words: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in practiced:
        target = getattr(item, "target", None)
        if target is None or str(target.kind) != "vocabulary":
            continue
        evidence = str(item.evidence_kind)
        if evidence == "not_yet":
            continue
        key = str(target.id)
        if key in seen:
            continue
        seen.add(key)
        words.append(
            {
                "id": key,
                "label_fr": target.label_fr,
                "label_native": target.label_native,
                "evidence_kind": evidence,
            }
        )
    return words


def kept_today(db: Session, user: User, journey: DailyJourney, seen: set[str]) -> list[dict[str, Any]]:
    """Words the learner kept («Garder», WP-78) since this journey started.

    ``unscored``: keeping a word is a choice, not a graded observation.
    """

    try:
        from app.services.kept_words import kept_words_for
    except ImportError:
        return []
    since = getattr(journey, "started_at", None) or getattr(journey, "created_at", None)
    if since is None:
        return []
    out: list[dict[str, Any]] = []
    for row in kept_words_for(db, user_id=user.id, since=since, limit=10):
        key = str(row.word_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": key,
                "label_fr": row.surface or row.word,
                "label_native": row.gloss or None,
                "evidence_kind": "unscored",
            }
        )
    return out


# ---------------------------------------------------------------------------
# The living story, read-only
# ---------------------------------------------------------------------------


def _thread(db: Session, user: User, journey: DailyJourney):
    from app.db.models.serial import SerialThread

    raw = journey.serial_thread_id or (journey.scenario_snapshot or {}).get("serial_thread_id")
    if raw:
        try:
            thread = db.get(SerialThread, uuid.UUID(str(raw)))
        except (ValueError, TypeError):
            thread = None
        if thread is not None and thread.user_id == user.id:
            return thread
    return db.scalar(
        select(SerialThread)
        .where(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
        .limit(1)
    )


def _live(thread: Any) -> dict[str, Any]:
    state = getattr(thread, "state", None) if thread is not None else None
    live = (state or {}).get(LIVING_STORY_KEY) if isinstance(state, dict) else None
    return dict(live) if isinstance(live, dict) else {}


def _portrait_id(character_id: Any) -> str | None:
    from app.services.serial_notifications import portrait_character

    return portrait_character(character_id)


def recap_mood(journey: DailyJourney, live: dict[str, Any]) -> dict[str, Any] | None:
    """The day's character in the mood ledger, or ``None`` without one."""

    scenario = dict(journey.scenario_snapshot or {})
    raw_id = str(scenario.get("character_id") or "").strip()
    name = str(scenario.get("character_name") or "").strip()
    if not raw_id or not name:
        return None
    moods = live.get("moods") if isinstance(live.get("moods"), dict) else {}
    candidates = [raw_id, _portrait_id(raw_id)]
    entry = next(
        (moods[key] for key in candidates if key and isinstance(moods.get(key), dict)),
        None,
    )
    if entry is None:
        return None
    try:
        mood = max(-2, min(2, int(entry.get("mood") or 0)))
    except (TypeError, ValueError):
        mood = 0
    shift = entry.get("last_shift")
    today = entry.get("last_event_id") == _event_id(journey)
    return {
        "character_id": raw_id,
        "character_name": name,
        "mood": mood,
        "shift": shift if today and shift in {"warmer", "colder", "steady"} else None,
    }


# ---------------------------------------------------------------------------
# Keepsake
# ---------------------------------------------------------------------------


def _step_image(journey: DailyJourney, kind: str) -> str | None:
    for step in journey.steps:
        if str(step.kind) == kind:
            url = (step.public_prompt or {}).get("image_url")
            if isinstance(url, str) and url.strip():
                return url
    return None


def recap_keepsake(db: Session, journey: DailyJourney, collectible_ids: list[str]) -> dict[str, Any] | None:
    if not collectible_ids:
        return None
    from app.db.models.atelier import AtelierCollectible

    try:
        item = db.get(AtelierCollectible, uuid.UUID(str(collectible_ids[0])))
    except (ValueError, TypeError):
        item = None
    if item is None or item.user_id != journey.user_id:
        return None
    meta = dict(item.metadata_payload or {})
    scenario = dict(journey.scenario_snapshot or {})
    title = _clean(meta.get("scenario_title_fr") or scenario.get("title_fr"), 120)
    if not title:
        return None
    image = (
        _step_image(journey, "resolution")
        or _step_image(journey, "scene")
        or (scenario.get("image_url") if isinstance(scenario.get("image_url"), str) else None)
    )
    try:
        local = date.fromisoformat(str(meta.get("date") or journey.local_date))
    except ValueError:
        local = journey.local_date
    return {
        "collectible_id": str(item.id),
        "title_fr": title,
        "location_name": _clean(meta.get("location_name") or scenario.get("location_name"), 80) or None,
        "image_url": image,
        "local_date": local,
    }


# ---------------------------------------------------------------------------
# Teaser — the same source order as WP-80's morning push
# ---------------------------------------------------------------------------


def forward_line(text: Any) -> str | None:
    """The last sentence of ``text`` that looks forward, else ``None``."""

    sentences = [part.strip() for part in _SENTENCE.findall(str(text or "")) if part.strip()]
    for sentence in reversed(sentences):
        if FORWARD_MARKERS.search(sentence):
            return _clean(sentence, 160)
    return None


def _resolution_line(journey: DailyJourney) -> str | None:
    for step in journey.steps:
        if str(step.kind) == "resolution":
            return forward_line((step.public_prompt or {}).get("character_line_fr"))
    return None


def recap_teaser(user: User, journey: DailyJourney, live: dict[str, Any]) -> dict[str, Any]:
    from app.services.serial_notifications import (
        CHARACTER_NAMES,
        DEFAULT_CHARACTER_ID,
        DEFAULT_MORNING_LINE,
        MORNING_LINES,
        band_group,
    )

    scenario = dict(journey.scenario_snapshot or {})
    raw_id = str(scenario.get("character_id") or "").strip()
    name = str(scenario.get("character_name") or "").strip()

    teaser = live.get("next_teaser")
    if isinstance(teaser, dict) and _clean(teaser.get("text_fr")):
        # A teaser the engine wrote for an earlier day is not tomorrow's.
        source_event = teaser.get("source_event_id")
        if not source_event or source_event == _event_id(journey):
            teaser_id = str(teaser.get("character_id") or "").strip() or raw_id
            return {
                "text_fr": _clean(teaser.get("text_fr"), 160),
                "character_id": teaser_id or None,
                "character_name": _clean(teaser.get("character_name"), 60)
                or (name if teaser_id == raw_id else CHARACTER_NAMES.get(_portrait_id(teaser_id) or "", ""))
                or None,
                "source": "engine",
            }

    line = _resolution_line(journey)
    if line:
        return {
            "text_fr": line,
            "character_id": raw_id or None,
            "character_name": name or None,
            "source": "resolution",
        }

    key = _portrait_id(raw_id)
    speaker = key or DEFAULT_CHARACTER_ID
    return {
        "text_fr": MORNING_LINES.get(speaker, DEFAULT_MORNING_LINE)[band_group(user)],
        "character_id": raw_id if key else speaker,
        "character_name": (name if key else None) or CHARACTER_NAMES.get(speaker),
        "source": "authored",
    }


# ---------------------------------------------------------------------------
# Level
# ---------------------------------------------------------------------------


def _previous_recap_level(db: Session, user: User, journey: DailyJourney) -> str | None:
    rows = db.scalars(
        select(DailyJourney)
        .where(
            DailyJourney.user_id == user.id,
            DailyJourney.id != journey.id,
            DailyJourney.recap_snapshot.isnot(None),
        )
        .order_by(DailyJourney.completed_at.desc().nullslast(), DailyJourney.created_at.desc())
        .limit(5)
    ).all()
    for row in rows:
        level = (row.recap_snapshot or {}).get("level")
        if isinstance(level, str) and level:
            return level
    return None


def _measure_up(db: Session, user: User) -> None:
    """Let the CEFR engine move the estimate *up* on the day's evidence.

    The engine's own rule (``CEFRProgressService.recompute``), without its
    commit: the finish transaction owns that. Only an upward, measured move is
    written here — a downward move keeps its own smoothing at the engine's
    other recompute points, and a day that moved nothing writes nothing.
    """

    from app.db.models.cefr import UserCEFRProgressHistory
    from app.services.cefr_progress import CEFRProgressService, level_index

    previous = str(getattr(user, "cefr_estimate", None) or "A1.1")
    with db.begin_nested():
        payload = CEFRProgressService(db).recompute(user, source="daily_journey", persist=False)
        estimate = str(payload.get("estimate") or previous)
        if payload.get("estimate_source") != "measured" or level_index(estimate) <= level_index(previous):
            return
        user.cefr_estimate = estimate
        user.cefr_estimate_payload = payload
        db.add(
            UserCEFRProgressHistory(
                user_id=user.id,
                estimate_level=estimate,
                source="daily_journey",
                signal_snapshot=dict(payload.get("signals") or {}),
                payload={**payload, "computed_level": payload.get("computed_estimate")},
            )
        )
        db.flush()


def recap_level(db: Session, user: User, journey: DailyJourney) -> tuple[str | None, dict[str, Any] | None]:
    from app.services.cefr_progress import level_index

    try:
        _measure_up(db, user)
    except Exception:  # pragma: no cover - a level line is never worth the day
        logger.exception("wp79: cefr measure failed")
    level = str(getattr(user, "cefr_estimate", None) or "").strip() or None
    if level is None:
        return None, None
    previous = _previous_recap_level(db, user, journey)
    payload = user.cefr_estimate_payload if isinstance(user.cefr_estimate_payload, dict) else {}
    if (
        previous
        and level_index(level) > level_index(previous)
        and payload.get("estimate_source") == "measured"
    ):
        signals = payload.get("signals") if isinstance(payload.get("signals"), dict) else {}
        return level, {
            "from_level": previous,
            "to_level": level,
            "mastered_vocabulary": int(signals.get("mastered_vocabulary") or 0),
            "mastered_grammar": int(signals.get("mastered_grammar") or 0),
        }
    return level, None


# ---------------------------------------------------------------------------
# The one entry point
# ---------------------------------------------------------------------------


def recap_extras(
    db: Session,
    *,
    user: User,
    journey: DailyJourney,
    practiced: list[Any],
    collectible_ids: list[str],
) -> dict[str, Any]:
    """The WP-79 recap fields, each one independently optional."""

    words = recap_words(practiced)
    try:
        words += kept_today(db, user, journey, {w["id"] for w in words})
    except Exception:  # pragma: no cover - WP-78's module is optional here
        logger.exception("wp79: kept words read failed")
    extras: dict[str, Any] = {"steps_done": steps_done(journey), "words": words}
    live: dict[str, Any] = {}
    try:
        live = _live(_thread(db, user, journey))
    except Exception:  # pragma: no cover - defensive
        logger.exception("wp79: living story read failed")
    for key, build in (
        ("mood", lambda: recap_mood(journey, live)),
        ("keepsake", lambda: recap_keepsake(db, journey, collectible_ids)),
        ("teaser", lambda: recap_teaser(user, journey, live)),
    ):
        try:
            extras[key] = build()
        except Exception:  # pragma: no cover - defensive
            logger.exception("wp79: recap %s failed", key)
            extras[key] = None
    teaser = extras.get("teaser") or {}
    extras["teaser_fr"] = teaser.get("text_fr") if teaser.get("source") in {"engine", "resolution"} else None
    level, level_up = recap_level(db, user, journey)
    extras["level"] = level
    extras["level_up"] = level_up
    return extras


__all__ = [
    "FORWARD_MARKERS",
    "forward_line",
    "kept_today",
    "recap_extras",
    "recap_keepsake",
    "recap_level",
    "recap_mood",
    "recap_teaser",
    "recap_words",
    "steps_done",
]
