"""WP-166 — wider, generated variety between tentpoles.

The WP-164 baseline (``docs/implementation/atelier-v2/VARIETY-BASELINE-2026-10.md``)
found one room: Le Mistral took 50–67 % of the real model's generated days, five
days running in four reads of five, and a gap's premise came back two or three days
in a row. The owner's rule (11 October): generated beats authored-and-seeded.

So the director now **invents** the day's premise and complication. The authored
decks (``living_story.COMPLICATION_CARDS``, each gap's premises, small moments and
complications in ``app/data/season/s1/gaps.json``) are an optional spark: one card
of each, dealt per learner and per day, which the director may take, twist or
ignore. What it must not do is repeat this learner's own recent past, so it is
told that past — the **novelty memory**: the last premises, openings,
complications and places this life has seen. And Le Mistral is the anchor, not the
default: **at most 2 days in 5** unless the day's premise is set there.

Nothing here refuses a page. The place spread is a soft hint (``place_spread_hint``):
one retry with the reason, then the page is served wherever it is.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections import Counter
from typing import Any

MISTRAL = "le_mistral"
#: The place spread: Le Mistral at most ``MISTRAL_CAP`` days in any ``PLACE_WINDOW``.
PLACE_WINDOW = 5
MISTRAL_CAP = 2
#: How many of this life's recent premises, openings and complications the director reads.
NOVELTY_WINDOW = 8
#: How many places the brief proposes for today, least visited first.
PREFER_PLACES = 6
_NOTE_CHARS = 140
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")

NOVELTY_RULE = (
    "This life has already seen what novelty lists. Today's premise, complication and "
    "opening line must be new to it: not a rewording of recent_premises, not a "
    "complication in recent_complications, and a first narration sentence that opens on "
    "something other than recent_openings (another hour, another weather, another place, "
    "another person's gesture). Invent; the decks are only sparks."
)


def _cut(text: Any, limit: int = _NOTE_CHARS) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1].rsplit(" ", 1)[0] + "…"


def first_sentence(text: Any) -> str:
    """The first sentence of a narration (whitespace folded, cut to a note)."""

    value = " ".join(str(text or "").split())
    return _cut(_SENTENCE_END.split(value, 1)[0]) if value else ""


def opening_of(panels: list[Any]) -> str:
    """A page's opening: the first sentence of its first non-empty narration."""

    for panel in panels or []:
        narration = panel.get("narration_fr") if isinstance(panel, dict) else getattr(panel, "narration_fr", "")
        if str(narration or "").strip():
            return first_sentence(narration)
    return ""


def _mistral_days(recent: list[dict]) -> int:
    """Le Mistral's days among the last ``PLACE_WINDOW - 1`` (today is the fifth)."""

    return sum(1 for item in recent[-(PLACE_WINDOW - 1) :] if item.get("location_id") == MISTRAL)


def mistral_open(recent: list[dict]) -> bool:
    """May today be at Le Mistral without a premise that is set there?"""

    return _mistral_days(recent) < MISTRAL_CAP


def preferred_places(recent: list[dict], places: list[str], *, seed: str = "") -> list[str]:
    """The places to steer today toward: never the Mistral, least visited by this life
    first, and not one of the last few days' rooms (ties broken per learner)."""

    counts = Counter(item.get("location_id") for item in recent)
    lately = {item.get("location_id") for item in recent[-(PLACE_WINDOW - 1) :]}
    pool = [place for place in dict.fromkeys(places) if place and place != MISTRAL]
    fresh = [place for place in pool if place not in lately] or pool

    def key(place: str) -> tuple[int, str]:
        return counts[place], hashlib.sha256(f"{seed}:{place}".encode()).hexdigest()

    return sorted(fresh, key=key)[:PREFER_PLACES]


def place_rule(recent: list[dict], places: list[str], *, seed: str = "") -> dict[str, Any]:
    """Today's place spread, as the director reads it (``novelty.places``)."""

    used = _mistral_days(recent)
    open_ = used < MISTRAL_CAP
    return {
        "rule": (
            f"Le Mistral is the anchor, not the default: at most {MISTRAL_CAP} days in "
            f"{PLACE_WINDOW} are set there, unless today's premise is set there "
            "(a premise's place). "
            + (
                "Today may be at the Mistral, but prefer somewhere this life has not been lately."
                if open_
                else f"It already had {used} of the last {PLACE_WINDOW - 1} days: set today "
                "somewhere else — one of prefer, or any other place of the world."
            )
        ),
        "mistral_days_in_last_4": used,
        "mistral_open_today": open_,
        "recent_places": [item.get("location_id") for item in recent[-(PLACE_WINDOW - 1) :]],
        "prefer": preferred_places(recent, places, seed=seed),
    }


def novelty_memory(recent: list[dict], places: list[str], *, seed: str = "") -> dict[str, Any]:
    """``context["novelty"]``: this life's recent past, so the director avoids it."""

    window = recent[-NOVELTY_WINDOW:]
    return {
        "rule": NOVELTY_RULE,
        "recent_premises": [_cut(item.get("premise_fr")) for item in window if item.get("premise_fr")],
        "recent_openings": [item["opening_fr"] for item in window if item.get("opening_fr")],
        "recent_complications": [
            _cut(item.get("complication")) for item in window if item.get("complication")
        ],
        "recent_premise_ids": [item["premise_id"] for item in window if item.get("premise_id")],
        "places": place_rule(recent, places, seed=seed),
    }


def situation_extras(draft: Any) -> dict[str, Any]:
    """What ``recent_situations`` keeps of a published page for the novelty memory: its
    opening, the complication it drew and the season premise it staged."""

    checklist = getattr(draft, "season_checklist", None)
    complication = str(getattr(checklist, "complication", "") or "") if checklist else ""
    if not complication and getattr(draft, "beat", None) == "complication":
        complication = str(getattr(draft, "premise_fr", "") or "")
    return {
        "opening_fr": opening_of(list(getattr(draft, "panels", None) or [])),
        "complication": _cut(complication),
        "premise_id": (getattr(checklist, "premise_id", None) if checklist else None) or None,
    }


def place_spread_hint(draft: Any, context: dict) -> str | None:
    """The soft hint when a page sits at Le Mistral past its share (``None`` otherwise).

    A premise set at the Mistral is exempt: the season's required moment (or the
    premise the page claims) whose ``place`` is ``le_mistral`` may be staged there. So
    is an open bottle chapter whose one room is the Mistral."""

    if getattr(draft, "location_id", None) != MISTRAL:
        return None
    recent = list(context.get("recent_situations") or [])
    if mistral_open(recent):
        return None
    chapter = context.get("chapter") or {}
    if (
        chapter.get("shape") == "bottle"
        and chapter.get("location_id") == MISTRAL
        and not (chapter.get("resolved") or chapter.get("exhausted"))
    ):
        # An open bottle chapter keeps its one room: the shape sets it there.
        return None
    today = (((context.get("season_script") or {}).get("brief")) or {}).get("today") or {}
    premises = [today.get("required_premise") or {}, *(today.get("premises") or [])]
    checklist = getattr(draft, "season_checklist", None)
    claimed = {
        str((today.get("required_premise") or {}).get("id") or ""),
        str(getattr(checklist, "premise_id", "") or ""),
    }
    if any(row.get("place") == MISTRAL and row.get("id") in claimed for row in premises if row):
        return None
    prefer = ((context.get("novelty") or {}).get("places") or {}).get("prefer") or []
    elsewhere = f" — for example {', '.join(prefer[:3])}" if prefer else ""
    return (
        f"Le Mistral already had {_mistral_days(recent)} of the last {PLACE_WINDOW - 1} days "
        f"(at most {MISTRAL_CAP} in {PLACE_WINDOW}): set today's page somewhere else"
        f"{elsewhere}, and let the people come to the place"
    )


# ---------------------------------------------------------------------------
# The season's sparks (a gap day)
# ---------------------------------------------------------------------------

INVENT_RULE = (
    "Invent today's premise and complication yourself, inside gap.threads and the gap's "
    "rules, for THIS learner: their flags, their recent days (novelty), their place spread. "
    "today.spark is one premise, one complication and one small moment dealt to this "
    "learner today from the gap's decks: an optional spark — take one, twist one, combine "
    "them, or ignore them for something better. today.premises lists the gap's authored "
    "premises in this learner's order: examples of tone and scale, never a menu to copy. "
    "When today.required_premise is set, that moment is still staged today (it is the "
    "season's), but how, where and with what complication is yours. Set "
    "season_checklist.premise_id to an authored premise's id only when you stage that "
    "premise; for a premise of your own, null."
)


def _rng(seed: str, salt: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest(), 16))  # noqa: S311 - a story deal


def dealt_order(items: list[Any], seed: str, salt: str) -> list[Any]:
    """``items`` in an order dealt for this learner and day (no first-item bias)."""

    rows = list(items)
    _rng(seed, salt).shuffle(rows)
    return rows


def spark(
    premises: list[dict],
    complications: list[str],
    moments: list[dict],
    *,
    seed: str,
    salt: str,
) -> dict[str, Any]:
    """One premise, one complication and one small moment, dealt to this learner today."""

    rng = _rng(seed, f"spark:{salt}")
    return {
        "premise": rng.choice(premises) if premises else None,
        "complication": rng.choice(complications) if complications else None,
        "small_moment": rng.choice(moments) if moments else None,
    }
