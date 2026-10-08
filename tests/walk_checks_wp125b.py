"""WP-125B walk checks — credible fallback letters, over a life record.

Runs over a life record from ``tests/experience_walk.py`` (the ``courrier`` entry
of each day). Provider-off, the Courrier used to reprint its canned letters
(«Plus de pain blanc» six times in a month to a B1 learner, four days running
for an affair whose letter 2 was letter 1 again) and to send the A1 bread
question to C1 learners. Two invariants:

* :func:`check_letter_repeats` — a request the learner completed is not asked
  again within seven days, unless the new letter is a follow-up that names the
  earlier exchange (and is not a word-for-word reprint of it);
* :func:`check_letter_levels` — no letter beyond its reach for the learner: a
  closed letter is credible up to one band above its own, an open one two
  (:func:`app.services.missions.letter_reach`), so nothing arrives two or more
  bands below the learner.

A letter's level, reach and request are read from its ``letter_fit`` when the
walk records it, else inferred from its title (the canned and authored letters
have unique titles; «Un mot de …» is the story frame).
"""
from __future__ import annotations

from typing import Any

from app.services.missions import (
    FIRST_LETTERS,
    REAL_WORLD_MISSION_DOMAINS,
    STORY_FRAMES,
    letter_band_index,
    letter_reach,
)

#: A completed request may come back after this many days (the app's own rule).
REPEAT_WINDOW_DAYS = 7

_CANNED_BY_TITLE = {str(item["title"]): item for item in REAL_WORLD_MISSION_DOMAINS}
_AUTHORED_BY_TITLE = {str(item["title"]): item for item in FIRST_LETTERS.values()}


def letter_identity(letter: dict[str, Any]) -> dict[str, Any]:
    """``{source, level, reach, request_key, follow_up_of}`` for a recorded letter (``None`` where unknown)."""

    fit = letter.get("letter_fit") if isinstance(letter.get("letter_fit"), dict) else None
    title = str(letter.get("title") or "")
    if fit and fit.get("reach"):
        return {
            "source": fit.get("source"),
            "level": fit.get("level"),
            "reach": fit.get("reach"),
            "request_key": fit.get("request_key") or f"{title}|{letter.get('brief')}",
            "follow_up_of": fit.get("follow_up_of") or letter.get("follow_up_of"),
        }
    canned = _CANNED_BY_TITLE.get(title)
    authored = _AUTHORED_BY_TITLE.get(title)
    follow = letter.get("follow_up_of") or letter.get("chain_note")
    if canned:
        return {
            "source": "canned",
            "level": canned.get("level"),
            "reach": letter_reach(canned.get("level"), open_ended=bool(canned.get("open_ended"))),
            "request_key": str(canned["domain"]),
            "follow_up_of": follow,
        }
    if authored:
        return {
            "source": "authored",
            "level": authored.get("level"),
            "reach": letter_reach(authored.get("level"), open_ended=bool(authored.get("open_ended"))),
            "request_key": str(authored.get("domain")),
            "follow_up_of": follow,
        }
    if title.startswith("Un mot de "):
        # The story frame. Without a recorded fit only the lowest frame is known
        # for certain to be the one printed.
        level = min(STORY_FRAMES, key=letter_band_index)
        return {
            "source": "story_frame",
            "level": level,
            "reach": letter_reach(level, open_ended=bool(STORY_FRAMES[level].get("open_ended", True))),
            "request_key": f"{title}|{letter.get('brief')}",
            "follow_up_of": follow,
        }
    return {"source": None, "level": None, "reach": None, "request_key": f"{title}|{letter.get('brief')}", "follow_up_of": follow}


def _new_letters(record: dict[str, Any]):
    """Each letter once, on the day it first arrived (a skipped letter is shown again)."""

    seen: set[str] = set()
    for day in record.get("days") or []:
        for letter in (day.get("courrier") or {}).get("letters") or []:
            ident = str(letter.get("id") or "")
            if ident and ident in seen:
                continue
            seen.add(ident)
            yield int(day.get("day") or 0), letter


def _answered(record: dict[str, Any]) -> dict[str, int]:
    """Letter id → the day it was answered."""

    done: dict[str, int] = {}
    for day in record.get("days") or []:
        for letter in (day.get("courrier") or {}).get("letters") or []:
            if letter.get("reply") and letter.get("id") and str(letter["id"]) not in done:
                done[str(letter["id"])] = int(day.get("day") or 0)
    return done


def check_letter_repeats(record: dict[str, Any]) -> list[str]:
    """No completed request is asked again within seven days without naming the earlier exchange."""

    problems: list[str] = []
    who = f"{record.get('persona')} {record.get('quality')}"
    answered = _answered(record)
    completed: dict[str, list[tuple[int, str, str]]] = {}
    arrivals = list(_new_letters(record))
    for day, letter in arrivals:
        identity = letter_identity(letter)
        key = str(identity["request_key"])
        opening = str(letter.get("opening_message") or "")
        for done_day, done_id, done_opening in completed.get(key, []):
            if done_id == str(letter.get("id")) or day - done_day >= REPEAT_WINDOW_DAYS:
                continue
            if identity.get("follow_up_of") and opening != done_opening:
                continue
            problems.append(
                f"{who} day {day}: {letter.get('title')!r} asks again what was answered on day {done_day}"
                + (" (a word-for-word reprint)" if opening == done_opening else " (no reference to that exchange)")
            )
        ident = str(letter.get("id") or "")
        if ident in answered:
            # Recorded for the day it was answered, which is when the request was completed.
            completed.setdefault(key, []).append((answered[ident], ident, opening))
    return problems


def check_letter_levels(record: dict[str, Any]) -> list[str]:
    """No letter arrives beyond its reach: two or more bands below the learner."""

    problems: list[str] = []
    who = f"{record.get('persona')} {record.get('quality')}"
    learner = str(record.get("true_level") or "")[:2]
    if not learner:
        return problems
    for day, letter in _new_letters(record):
        identity = letter_identity(letter)
        if not identity.get("reach"):
            continue
        if letter_band_index(learner) > letter_band_index(identity["reach"]):
            problems.append(
                f"{who} day {day}: {letter.get('title')!r} ({identity['source']}, written at "
                f"{identity['level']}, credible up to {identity['reach']}) sent to a {learner} learner"
            )
    return problems


def letter_volume(record: dict[str, Any]) -> dict[str, Any]:
    """For the report: new letters, answered letters and repeats in one life."""

    arrivals = list(_new_letters(record))
    return {
        "letters": len(arrivals),
        "answered": len(_answered(record)),
        "by_source": _count(letter_identity(letter)["source"] or "unknown" for _day, letter in arrivals),
        "repeats_within_7_days": len(check_letter_repeats(record)),
        "beyond_reach": len(check_letter_levels(record)),
    }


def _count(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


__all__ = ["check_letter_levels", "check_letter_repeats", "letter_identity", "letter_volume"]
