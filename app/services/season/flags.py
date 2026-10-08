"""World flags a season sets and reads (bible §6), and Lila's path (§7).

Flags live in ``live["season_script"]["flags"]``; Lila's gate signals in
``live["season_script"]["signals"]``. Every writer here is a pure function of the
state it is given. A flag is set by what the learner *did* — a reply routed, a card
chosen, a solve played — or by a tentpole's fixed ``state_out``. Some flags are
*derived* from others and never stored on their own:

* ``s1.promised_to`` from the two halves of T3 (``s1.promise_gus`` on Day A,
  ``s1.promise_marin`` on Day B): you cannot fully promise both;
* ``s1.plan`` from ``s1.evidence_shared`` (T6 B), when no card set it;
* ``s1.berlin_told_how`` from ``s1.fire_photo`` once Berlin is revealed;
* ``s1.ending`` and ``s1.painting`` from ``s1.flat_decision`` (T7 B);
* ``s1.lila_path`` from the gate signals — **never from accuracy**.

Affection is never a visible score: nothing here is ever sent to the page.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.services.season.format import B1_BANDS, Cond, Season, SetsIf

logger = logging.getLogger(__name__)

SIGNALS = ("romance", "friendship", "none")
#: Bible §7: "Two romance-leaning expressions make the path romance."
ROMANCE_SIGNALS_NEEDED = 2
_PROMISE_SCORE = {"yes": 2, "half": 1, "no": 0}


def stored_flags(state: dict | None) -> dict[str, Any]:
    return dict((state or {}).get("flags") or {})


def signals_of(state: dict | None) -> list[dict]:
    return [row for row in (state or {}).get("signals") or [] if isinstance(row, dict)]


def lila_path(signals: list[dict]) -> str:
    """Romance, friendship or open — from what the learner *expressed* at the gates.

    Two romance-leaning expressions make it romance; one leaves it open (Lila
    notices). Naming friendship steers back at any time: the latest expression that
    leans either way decides between romance and friendship. Letting an opening pass
    ("none") changes nothing — nothing is ever lost.
    """

    values = [str(row.get("signal")) for row in signals if row.get("signal") in SIGNALS]
    romance = sum(1 for value in values if value == "romance")
    leaning = [value for value in values if value in ("romance", "friendship")]
    last = leaning[-1] if leaning else None
    if last == "friendship":
        return "friendship"
    if romance >= ROMANCE_SIGNALS_NEEDED and last == "romance":
        return "romance"
    return "open"


def _seeded(seed: str, key: str, values: list[str]) -> str:
    digest = hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
    return values[int(digest, 16) % len(values)]


def promised_to(flags: dict[str, Any]) -> str | None:
    gus = _PROMISE_SCORE.get(str(flags.get("s1.promise_gus") or ""), None)
    marin = _PROMISE_SCORE.get(str(flags.get("s1.promise_marin") or ""), None)
    if gus is None and marin is None:
        return None
    gus, marin = gus or 0, marin or 0
    if gus and marin:
        return "both_half"
    if gus:
        return "gus"
    if marin:
        return "marin"
    return "neither"


def ending_for(flags: dict[str, Any]) -> str | None:
    """The ending T7 B's flat decision leads to (bible §6, «What T7 B offers»).

    Keeping the flat is «Garder» only when Marchand alone saw the notebook; after
    «kept» (Marchand signed with Solvel) keeping the flat is the «keep» fold of
    «Laisser partir». Selling is always «Laisser partir», including after a signed
    lease (S-10; the fold T7's note describes).
    """

    decision = flags.get("s1.flat_decision")
    if decision == "coop":
        return "partager"
    if decision == "keep":
        return "garder" if flags.get("s1.evidence_shared") == "marchand_only" else "laisser_partir"
    if decision == "sell":
        return "laisser_partir"
    return None


PAINTING_BY_ENDING = {"garder": "with_you", "partager": "with_gus", "laisser_partir": "lost"}
PLAN_BY_EVIDENCE = {"marchand_only": "lease", "public": "coop", "kept": "last_service"}


def effective_flags(season: Season, state: dict | None, *, seed: str = "") -> dict[str, Any]:
    """Every flag as the story reads it now: defaults, stored values, derived ones."""

    flags: dict[str, Any] = {}
    for spec in season.flags:
        if spec.default is not None:
            flags[spec.id] = list(spec.default) if isinstance(spec.default, list) else spec.default
    flags.update(stored_flags(state))
    if "s1.promised_to" not in stored_flags(state):
        derived = promised_to(flags)
        if derived:
            flags["s1.promised_to"] = derived
    if not flags.get("s1.plan") and flags.get("s1.evidence_shared") and "s1.evidence_shared" in stored_flags(state):
        flags["s1.plan"] = PLAN_BY_EVIDENCE.get(str(flags["s1.evidence_shared"]))
    if not flags.get("s1.berlin_told_how") and flags.get("lila.berlin_revealed"):
        flags["s1.berlin_told_how"] = "told" if flags.get("s1.fire_photo") == "wall" else "discovered"
    if not flags.get("s1.ending"):
        ending = ending_for(flags)
        if ending:
            flags["s1.ending"] = ending
    if flags.get("s1.ending") and not flags.get("s1.painting"):
        flags["s1.painting"] = PAINTING_BY_ENDING.get(str(flags["s1.ending"]))
    if not flags.get("s1.camille_gender") and seed:
        # S-9: the learner decides in T1 B. Until they have (or when that moment
        # was not played), the story needs one; it is seeded, never random per page.
        flags["s1.camille_gender"] = _seeded(seed, "camille_gender", ["f", "m"])
    flags["s1.lila_path"] = lila_path(signals_of(state))
    return flags


def _band_key(band: str | None) -> str:
    return "b1" if str(band or "")[:2].upper() in B1_BANDS else "a1a2"


def holds(cond: Cond | None, flags: dict[str, Any], *, band: str | None = None) -> bool:
    """Does a season condition hold? (Syntax: :data:`app.services.season.format.Cond`.)"""

    for key, want in (cond or {}).items():
        if key == "any":
            if not any(holds(inner, flags, band=band) for inner in want or []):
                return False
            continue
        if key == "all":
            if not all(holds(inner, flags, band=band) for inner in want or []):
                return False
            continue
        if key == "band":
            allowed = want if isinstance(want, list) else [want]
            if _band_key(band) not in allowed:
                return False
            continue
        if key == "path":
            have = flags.get("s1.lila_path") or "open"
        else:
            have = flags.get(key)
        if isinstance(want, dict):
            if "not" in want:
                excluded = want["not"] if isinstance(want["not"], list) else [want["not"]]
                if have in excluded:
                    return False
            if "set" in want and bool(have not in (None, "", [])) != bool(want["set"]):
                return False
            continue
        if isinstance(want, list):
            if have not in want:
                return False
            continue
        if have != want:
            return False
    return True


def apply_sets(
    season: Season,
    state: dict | None,
    sets: dict[str, Any] | None,
    *,
    source: str,
) -> dict:
    """The season state with ``sets`` applied. ``"+slug"`` appends to a list flag.

    A value the flag table does not allow is dropped with a warning, never stored:
    a transcription slip must not become canon.
    """

    state = dict(state or {})
    flags = stored_flags(state)
    for flag_id, value in (sets or {}).items():
        spec = season.flag(flag_id)
        if spec is None:
            logger.warning("season: %s sets unknown flag %s", source, flag_id)
            continue
        if spec.values == "list":
            current = list(flags.get(flag_id) or [])
            item = str(value)[1:] if str(value).startswith("+") else str(value)
            if item and item not in current:
                current.append(item)
            flags[flag_id] = current
            continue
        if isinstance(spec.values, list) and value not in spec.values:
            logger.warning("season: %s sets %s to %r, not one of %s", source, flag_id, value, spec.values)
            continue
        if spec.values == "bool" and not isinstance(value, bool):
            value = str(value).strip().casefold() in {"true", "1", "yes", "oui"}
        flags[flag_id] = value
    state["flags"] = flags
    return state


def conditional_sets(rows: list[SetsIf], flags: dict[str, Any], *, band: str | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for row in rows or []:
        if holds(row.when, flags, band=band):
            merged.update(row.sets)
    return merged


def add_signal(state: dict | None, *, gate: int | None, signal: str | None, source: str, day: int) -> dict:
    """Record what the learner expressed toward Lila at a gate. Idempotent per source."""

    state = dict(state or {})
    if signal not in SIGNALS:
        return state
    rows = signals_of(state)
    if any(row.get("source") == source for row in rows):
        return state
    rows.append({"gate": gate, "signal": signal, "source": source, "day": int(day)})
    state["signals"] = rows
    return state
