"""N1 pilot — the consequence contract on one real generated day.

The research brief (2026-10-12) asks for one gap where the learner's French
changes something durable, before anything wider. This module connects
:mod:`app.services.season.consequences` to the season, behind
``SEASON_AGENCY_PILOT`` (off by default):

* **the turn** (:func:`agency_for_turn`) — on a generated day that stages a
  premise with a contract in ``agency.json``, the voice lane is told what the
  learner may decide there, and returns the acts it heard with verbatim quotes;
* **the release** (:func:`acts_for_details`) — before the reply is shown, the
  acts are checked against the contract (:func:`consequences.decide`) and stored
  on the turn's details with the learner's text, in the respond transaction;
* **the settle** (:func:`settle_day`) — the day's settle commits them to
  ``state["agency"]`` (idempotent per day) and marks a staged callback played;
* **the next day** (:func:`brief_extras`) — the director reads the standing
  agreements and, when one is due, the callback that cites the learner's words.

Nothing here calls a model, and every failure leaves the day as it was before
the pilot: an act that cannot be committed is logged and dropped.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.services.season.consequences import (
    ACTIONS,
    Commit,
    EffectSpec,
    Evidence,
    Intent,
    Storylet,
    TransitionError,
    TurnContract,
    WorldState,
    apply,
    callback_source,
    decide,
    select,
)

logger = logging.getLogger(__name__)

STATE_KEY = "agency"


class Contract(BaseModel):
    season: str = ""
    gap: str
    premise: str
    speaker: str
    subjects: dict[str, str]
    conditions: dict[str, str] = Field(default_factory=dict)
    effects: list[EffectSpec]
    agreements: dict[str, str] = Field(default_factory=dict)

    def turn(self) -> TurnContract:
        return TurnContract(turn_id=f"{self.gap}.{self.premise}", speaker=self.speaker, effects=self.effects)


class Agency(BaseModel):
    contracts: list[Contract] = Field(default_factory=list)
    storylets: list[Storylet] = Field(default_factory=list)


def enabled() -> bool:
    return bool(getattr(settings, "SEASON_AGENCY_PILOT", False))


@lru_cache(maxsize=4)
def load_agency(season_id: str) -> Agency:
    from app.services.season.format import SEASON_ROOT

    path = SEASON_ROOT / season_id / "agency.json"
    if not path.is_file():
        return Agency()
    return Agency.model_validate(json.loads(path.read_text(encoding="utf-8")))


def contract_for(season_day: dict | None) -> Contract | None:
    """The contract of the premise a generated day staged, when the pilot is on."""

    if not enabled() or not isinstance(season_day, dict) or season_day.get("kind") != "gap":
        return None
    gap = str((season_day.get("position") or {}).get("segment") or "")
    premise = str((season_day.get("checklist") or {}).get("premise_id") or "")
    if not gap or not premise or not season_day.get("id"):
        return None
    try:
        agency = load_agency(str(season_day["id"]))
    except Exception:  # noqa: BLE001 - a broken pilot file never costs the day
        logger.exception("agency: %s/agency.json could not be read", season_day.get("id"))
        return None
    contract = next((row for row in agency.contracts if row.gap == gap and row.premise == premise), None)
    return contract.model_copy(update={"season": str(season_day["id"])}) if contract is not None else None


def contract_from_turn(turn_agency: dict | None) -> Contract | None:
    """The contract an ``agency_for_turn`` block was built from."""

    if not isinstance(turn_agency, dict):
        return None
    ref = turn_agency.get("contract") or {}
    return contract_for(
        {
            "id": ref.get("season"),
            "kind": "gap",
            "position": {"segment": ref.get("gap")},
            "checklist": {"premise_id": ref.get("premise")},
        }
    )


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------


def agency_for_turn(contract: Contract) -> dict[str, Any]:
    """What the voice lane reads (``story.season_turn.agency``)."""

    return {
        "contract": {"season": contract.season, "gap": contract.gap, "premise": contract.premise},
        "character": contract.speaker,
        "may_decide": [
            {
                "subject": subject,
                "about": about,
                "actions": sorted({a for e in contract.effects if e.subject == subject for a in e.actions}),
            }
            for subject, about in contract.subjects.items()
        ],
        "conditions": dict(contract.conditions),
        "if_condition_impossible": next((e.alternative for e in contract.effects if e.alternative), None),
    }


VOICE_ADDENDUM = """
agency is present: what the learner may decide in this scene. acts lists what the
learner's words actually decided about agency.may_decide, at most 3: action is one of
that entry's actions, subject its subject, conditions the limits the learner set (a key
of agency.conditions when it matches; otherwise a short snake_case name of what they
asked for), evidence_quotes exact verbatim quotes from learner_text or history[].learner.
A learner who has not clearly agreed or refused has decided nothing: then clarity is
ambiguous. Nothing about agency.may_decide in their words: acts is an empty list.
reply_fr never accepts a limit that is not a key of agency.conditions; offer
agency.if_condition_impossible instead. reply_fr never claims anything was written,
sent or published."""


class VoiceAct(BaseModel):
    """An act the voice heard (``VoiceReply.acts``)."""

    action: str = Field(min_length=1, max_length=20)
    subject: str | None = Field(default=None, max_length=60)
    conditions: list[str] = Field(default_factory=list, max_length=4)
    evidence_quotes: list[str] = Field(default_factory=list, max_length=3)
    clarity: str = "clear"


def agency_text(learner_text: str, history: list[dict] | None) -> str:
    """Everything the learner wrote in the scene, which evidence must quote."""

    earlier = [str(row.get("learner") or "") for row in history or [] if isinstance(row, dict)]
    return "\n".join([*[text for text in earlier if text], learner_text])


def _intent(act: VoiceAct, text: str) -> Intent | None:
    if act.action not in ACTIONS:
        return None
    evidence = []
    for quote in act.evidence_quotes:
        quote = quote.strip()
        start = text.find(quote) if quote else -1
        if start >= 0:
            evidence.append(Evidence(text=quote, start=start, end=start + len(quote)))
    clarity = act.clarity if act.clarity in ("clear", "ambiguous", "unsupported") else "ambiguous"
    return Intent(
        action=act.action,  # type: ignore[arg-type]
        subject=act.subject,
        conditions=[c.strip()[:40] for c in act.conditions if c.strip()],
        evidence=evidence,
        clarity=clarity,  # type: ignore[arg-type]
    )


def acts_for_details(contract: Contract, acts: list[VoiceAct], *, text: str) -> dict[str, Any]:
    """``{"season_acts": [...], "agency_text": text, "agency_decisions": [...]}`` for the
    turn's details. Decided against an empty world (what this premise allows); the
    settle decides again against the learner's own state."""

    intents = [intent for act in acts if (intent := _intent(act, text)) is not None]
    decisions = [
        decide(contract.turn(), intent, WorldState(), learner_text=text, source_turn="preview").kind
        for intent in intents
    ]
    return {
        "season_acts": [intent.model_dump(mode="json") for intent in intents],
        "agency_text": text,
        "agency_decisions": decisions,
    }


# ---------------------------------------------------------------------------
# The settle
# ---------------------------------------------------------------------------


def world_of(state: dict | None) -> WorldState:
    raw = (state or {}).get(STATE_KEY)
    try:
        return WorldState.model_validate(raw) if isinstance(raw, dict) else WorldState()
    except Exception:  # noqa: BLE001 - a damaged projection starts over, never crashes a settle
        logger.exception("agency: unreadable state, starting a new projection")
        return WorldState()


def settle_day(state: dict, season_ctx: dict, details: dict, *, event_id: str, engaged: bool) -> dict:
    """Commit the day's acts and mark a staged callback played. Idempotent per day."""

    if not enabled():
        return state
    world = world_of(state)
    changed = False
    contract = contract_for(season_ctx)
    text = str(details.get("agency_text") or details.get("learner_text") or "")
    if contract is not None and text:
        for index, raw in enumerate(details.get("season_acts") or []):
            try:
                intent = Intent.model_validate(raw)
            except Exception:  # noqa: BLE001 - a malformed act is dropped, not the day
                logger.warning("agency: unreadable act dropped: %r", raw)
                continue
            source = f"{event_id}:{index}"
            decision = decide(contract.turn(), intent, world, learner_text=text, source_turn=source)
            if not isinstance(decision, Commit):
                continue
            try:
                world = apply(world, decision.event, expected_version=world.version, learner_text=text)
                changed = True
            except TransitionError as exc:
                logger.warning("agency: act not committed (%s)", exc)
    callback = season_ctx.get("callback") or {}
    if engaged and callback.get("id") and callback["id"] not in world.played:
        world.played.append(str(callback["id"]))
        changed = True
    if changed:
        state = dict(state)
        state[STATE_KEY] = world.model_dump(mode="json")
    return state


# ---------------------------------------------------------------------------
# The next day
# ---------------------------------------------------------------------------


def _agreement_lines(season_id: str, world: WorldState) -> list[str]:
    agency = load_agency(season_id)
    lines = []
    for key, permission in world.permissions.items():
        subject, recipient = key.split(">", 1)
        contract = next(
            (row for row in agency.contracts if row.speaker == recipient and subject in row.subjects), None
        )
        if contract is None:
            continue
        name = "granted" if permission.granted else "refused"
        if permission.granted and permission.conditions:
            name += ":" + "+".join(sorted(permission.conditions))
        line = contract.agreements.get(name) or contract.agreements.get(name.split(":")[0])
        if line:
            lines.append(line)
    return lines


def brief_extras(season_id: str, gap_id: str, day: int, *, state: dict | None, seed: str) -> dict[str, Any]:
    """``{"agreements": [...], "callback": {...}}`` for the director's ``today``, or ``{}``."""

    if not enabled():
        return {}
    world = world_of(state)
    if not world.events:
        return {}
    try:
        agency = load_agency(season_id)
    except Exception:  # noqa: BLE001
        return {}
    extras: dict[str, Any] = {}
    lines = _agreement_lines(season_id, world)
    if lines:
        extras["agreements"] = lines
    library = [row for row in agency.storylets if row.gap == gap_id]
    due = [row for row in library if row.pays_off]
    if due:
        # Only callbacks are dealt here; with none due, the day is the gap's own.
        library = [*library, Storylet(id="gap_as_planned", gap=gap_id, fallback=True)]
        try:
            chosen, _ = select(library, world, gap=gap_id, slot=f"{gap_id}.day{day}", seed=seed)
        except TransitionError:
            chosen = None
        source = callback_source(chosen, world) if chosen is not None and not chosen.fallback else None
        if chosen is not None and source is not None:
            extras["callback"] = {
                "id": chosen.id,
                "character": (chosen.cast or [None])[0],
                "instruction": chosen.instruction,
                "learner_words": [row.text for row in source.evidence][:3],
                "source_event": source.event_id,
            }
    return extras


__all__ = [
    "STATE_KEY",
    "VOICE_ADDENDUM",
    "VoiceAct",
    "acts_for_details",
    "agency_for_turn",
    "agency_text",
    "brief_extras",
    "contract_for",
    "contract_from_turn",
    "enabled",
    "load_agency",
    "settle_day",
    "world_of",
]
