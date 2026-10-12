"""SP2 — what the learner's French is allowed to change, and how it stays changed.

The research brief (docs/research, 2026-10-12) asks for one contract between
"the learner wrote something" and "the world is different now". This module is
that contract, as pure functions over a small state object: no model calls, no
database, no clock. The runtime will hold :class:`WorldState` as a projection
next to the season flags; nothing here is wired into a live path yet.

The order is fixed, and every step can refuse::

    learner text + interpreted intent + state version
        → decide()   commit an event, ask once more, or say what is possible
        → apply()    validate and commit it, idempotently, at one state version
        → select()   pick the next storylet from the changed world, once

Rules this module enforces (they are the brief's hard failures):

* **Evidence is the learner's text.** Every committed event points at spans of
  the input it came from; a paraphrase written by a model is refused.
* **No invented consent.** Only ``accept`` and ``show`` grant access; ``decline``
  and ``withhold`` record a refusal; anything ambiguous asks again.
* **Conditions survive.** "Yes, but no photo" is stored as a grant *with* the
  condition, never as a plain yes. A condition the scene cannot honour is not
  dropped: the event is not committed and the character says what is possible.
* **Characters know only what they were told.** A fact moves to a character only
  through an event the learner made, and only if the learner knows it.
* **Committed is committed.** The same source turn applied twice changes nothing;
  a stale state version is refused; ``revise`` changes a permission from now on
  but never erases what a character already saw.
* **Sample once.** A storylet slot is decided once per state, from a recorded
  seed; reloads and retries read it back instead of rolling again.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.season.flags import holds

#: The pilot's whole vocabulary. Conditions and values are fields, not new verbs.
ACTIONS: tuple[str, ...] = ("ask", "tell", "show", "withhold", "accept", "decline", "propose", "promise", "revise")
Action = Literal["ask", "tell", "show", "withhold", "accept", "decline", "propose", "promise", "revise"]

#: Acts that can grant a character access to something.
GRANTING: frozenset[str] = frozenset({"accept", "show"})
#: Acts that record a refusal.
REFUSING: frozenset[str] = frozenset({"decline", "withhold"})
#: Acts that move a fact to the recipient (accepting "may I read it?" lets her read it).
DISCLOSING: frozenset[str] = frozenset({"tell", "show", "accept"})

LEARNER = "learner"


class TransitionError(ValueError):
    """A proposed change the contract refuses. ``code`` names the rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# What the interpreter hands over, and what the author allows
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """A span of the learner's own input: ``text == input[start:end]``."""

    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class Intent(BaseModel):
    """One interpreted act. Produced by the (future) interpretation call or a fixture."""

    action: Action
    subject: str | None = None
    recipient: str | None = None
    conditions: list[str] = Field(default_factory=list)
    reason: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    clarity: Literal["clear", "ambiguous", "unsupported"] = "clear"


class EffectSpec(BaseModel):
    """An authored effect a turn allows: which acts, about what, under which conditions."""

    id: str
    actions: list[Action]
    subject: str | None = None
    recipient: str | None = None
    allowed_conditions: list[str] = Field(default_factory=list)
    #: Fact ids this effect discloses to the recipient (for ``tell``/``show``).
    discloses: list[str] = Field(default_factory=list)
    #: Season flags the effect sets once committed (validated by the season later).
    sets: dict[str, Any] = Field(default_factory=dict)
    #: An authored line for what can be offered instead, shown when this effect
    #: matches the act but not its conditions.
    alternative: str | None = None


class TurnContract(BaseModel):
    """What one prompt in a scene lets the learner change."""

    turn_id: str
    speaker: str
    effects: list[EffectSpec]
    #: Fact ids no event from this turn may disclose, whatever the effect says.
    forbidden_facts: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Committed state
# ---------------------------------------------------------------------------


class Event(BaseModel):
    event_id: str
    source_turn: str
    action: Action
    effect_id: str
    subject: str | None = None
    recipient: str | None = None
    conditions: list[str] = Field(default_factory=list)
    reason: str | None = None
    evidence: list[Evidence]
    discloses: list[str] = Field(default_factory=list)
    revises: str | None = None
    #: The state version this event was committed at (the version it produced).
    version: int


class Permission(BaseModel):
    granted: bool
    conditions: list[str] = Field(default_factory=list)
    event_id: str


class Selection(BaseModel):
    storylet_id: str
    seed: str
    version: int


class WorldState(BaseModel):
    version: int = 0
    events: list[Event] = Field(default_factory=list)
    #: ``"subject>recipient"`` → the standing permission.
    permissions: dict[str, Permission] = Field(default_factory=dict)
    #: fact id → characters who know it. The learner is ``"learner"``.
    known_by: dict[str, list[str]] = Field(default_factory=dict)
    promises: list[str] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)
    #: slot → what was dealt there. Never rerolled.
    selections: dict[str, Selection] = Field(default_factory=dict)
    #: storylet ids already played, in order.
    played: list[str] = Field(default_factory=list)

    def event(self, event_id: str) -> Event | None:
        return next((row for row in self.events if row.event_id == event_id), None)


def permission_key(subject: str | None, recipient: str | None) -> str:
    return f"{subject or '-'}>{recipient or '-'}"


# ---------------------------------------------------------------------------
# decide(): commit, ask again, or offer what is possible
# ---------------------------------------------------------------------------


class Commit(BaseModel):
    kind: Literal["commit"] = "commit"
    event: Event


class Clarify(BaseModel):
    """Ask once more; nothing is committed. ``reason`` names what was unclear."""

    kind: Literal["clarify"] = "clarify"
    reason: str


class Acknowledge(BaseModel):
    """Understood, but not something this scene can do; say what it can. Nothing committed."""

    kind: Literal["acknowledge"] = "acknowledge"
    reason: str
    alternative: str | None = None


Decision = Commit | Clarify | Acknowledge


def event_id_for(turn_id: str, source_turn: str) -> str:
    """Deterministic: the same submission always names the same event."""

    return "ev_" + hashlib.sha256(f"{turn_id}|{source_turn}".encode()).hexdigest()[:16]


def _evidence_is_input(evidence: Iterable[Evidence], learner_text: str) -> bool:
    rows = list(evidence)
    return bool(rows) and all(
        row.end <= len(learner_text) and row.start < row.end and learner_text[row.start : row.end] == row.text
        for row in rows
    )


def _matching_effects(contract: TurnContract, intent: Intent) -> list[EffectSpec]:
    return [
        spec
        for spec in contract.effects
        if intent.action in spec.actions
        and (spec.subject is None or spec.subject == intent.subject)
        and (spec.recipient is None or spec.recipient == (intent.recipient or contract.speaker))
    ]


def decide(
    contract: TurnContract,
    intent: Intent,
    state: WorldState,
    *,
    learner_text: str,
    source_turn: str,
) -> Decision:
    """Turn one interpreted act into a committed-to-be event, or refuse honestly."""

    if intent.clarity == "ambiguous":
        return Clarify(reason="ambiguous")
    if intent.clarity == "unsupported":
        return Acknowledge(reason="unsupported")
    if not _evidence_is_input(intent.evidence, learner_text):
        # A choice is never reconstructed from generated prose.
        return Clarify(reason="no_evidence")

    candidates = _matching_effects(contract, intent)
    if not candidates:
        return Acknowledge(reason="no_effect", alternative=None)
    honourable = [spec for spec in candidates if set(intent.conditions) <= set(spec.allowed_conditions)]
    if not honourable:
        # The learner set a condition this scene cannot keep. Dropping it would
        # turn "yes, but" into "yes": offer what is possible instead.
        return Acknowledge(reason="condition_unsupported", alternative=candidates[0].alternative)
    spec = honourable[0]

    revises: str | None = None
    if intent.action == "revise":
        standing = state.permissions.get(permission_key(intent.subject, intent.recipient or contract.speaker))
        if standing is None:
            return Acknowledge(reason="nothing_to_revise")
        revises = standing.event_id

    discloses = [fact for fact in spec.discloses if intent.action in DISCLOSING]
    blocked = [fact for fact in discloses if fact in contract.forbidden_facts]
    if blocked:
        return Acknowledge(reason="forbidden_fact", alternative=spec.alternative)

    event = Event(
        event_id=event_id_for(contract.turn_id, source_turn),
        source_turn=source_turn,
        action=intent.action,
        effect_id=spec.id,
        subject=intent.subject,
        recipient=intent.recipient or contract.speaker,
        conditions=sorted(set(intent.conditions)),
        reason=intent.reason,
        evidence=list(intent.evidence),
        discloses=discloses,
        revises=revises,
        version=state.version + 1,
    )
    return Commit(event=event)


# ---------------------------------------------------------------------------
# apply(): the only writer
# ---------------------------------------------------------------------------


def _grants(action: str) -> bool | None:
    if action in GRANTING:
        return True
    if action in REFUSING:
        return False
    return None


def apply(state: WorldState, event: Event, *, expected_version: int, learner_text: str) -> WorldState:
    """Commit ``event`` at ``expected_version``. Idempotent per ``event_id``.

    Raises :class:`TransitionError` instead of committing anything illegal.
    """

    existing = state.event(event.event_id)
    if existing is not None:
        if existing.model_dump() != event.model_dump():
            raise TransitionError("conflicting_replay", f"{event.event_id} was committed with other content")
        return state  # a retry or a double tap: already settled, nothing changes
    if state.version != expected_version:
        raise TransitionError("stale_version", f"state is at {state.version}, event was built at {expected_version}")
    if event.version != expected_version + 1:
        raise TransitionError("bad_version", "an event must produce the next state version")
    if event.action not in ACTIONS:
        raise TransitionError("unknown_action", event.action)
    if not _evidence_is_input(event.evidence, learner_text):
        raise TransitionError("no_evidence", "evidence must be spans of the learner's own text")

    nxt = state.model_copy(deep=True)
    key = permission_key(event.subject, event.recipient)

    if event.action == "revise":
        standing = nxt.permissions.get(key)
        if standing is None or event.revises != standing.event_id:
            raise TransitionError("bad_revision", "revise must name the standing permission it changes")
        nxt.permissions[key] = Permission(granted=standing.granted, conditions=event.conditions, event_id=event.event_id)
    else:
        granted = _grants(event.action)
        if granted is not None:
            # "No, unless…" stays a refusal: its terms are kept, but nothing is granted.
            nxt.permissions[key] = Permission(granted=granted, conditions=event.conditions, event_id=event.event_id)

    for fact in event.discloses:
        knowers = nxt.known_by.setdefault(fact, [])
        if LEARNER not in knowers:
            raise TransitionError("unknown_fact", f"the learner cannot pass on {fact}: they do not know it")
        if event.recipient and event.recipient not in knowers:
            knowers.append(event.recipient)

    if event.action == "promise" and event.subject:
        nxt.promises.append(event.subject)

    nxt.events.append(event)
    nxt.version = event.version
    return nxt


# ---------------------------------------------------------------------------
# Projection the season's condition syntax can read
# ---------------------------------------------------------------------------


def projected_flags(state: WorldState) -> dict[str, Any]:
    """``flags`` plus ``perm.<subject>.<recipient>`` (granted/refused), its ``.cond`` list and
    one ``.<condition>: True`` per condition, ``knows.<fact>`` and ``promised``."""

    flags = dict(state.flags)
    for key, permission in state.permissions.items():
        subject, recipient = key.split(">", 1)
        flags[f"perm.{subject}.{recipient}"] = "granted" if permission.granted else "refused"
        flags[f"perm.{subject}.{recipient}.cond"] = list(permission.conditions)
        for condition in permission.conditions:
            flags[f"perm.{subject}.{recipient}.{condition}"] = True
    for fact, knowers in state.known_by.items():
        flags[f"knows.{fact}"] = list(knowers)
    flags["promised"] = list(state.promises)
    return flags


# ---------------------------------------------------------------------------
# Storylets
# ---------------------------------------------------------------------------


class Storylet(BaseModel):
    id: str
    version: int = 1
    gap: str
    #: Season ``Cond`` over :func:`projected_flags`.
    when: dict[str, Any] = Field(default_factory=dict)
    #: Every fact here must be known by the named character for the storylet to run.
    requires_known: dict[str, list[str]] = Field(default_factory=dict)
    cast: list[str] = Field(default_factory=list)
    salience: int = 0
    #: Made due by a committed event with this effect id (a callback).
    pays_off: str | None = None
    repeatable: bool = False
    #: The always-finishable continuation for this gap.
    fallback: bool = False


def _knows(state: WorldState, character: str, fact: str) -> bool:
    return character in state.known_by.get(fact, [])


def eligible(library: Iterable[Storylet], state: WorldState, *, gap: str, band: str | None = None) -> list[Storylet]:
    flags = projected_flags(state)
    rows = []
    for storylet in library:
        if storylet.gap != gap or storylet.fallback:
            continue
        if not storylet.repeatable and storylet.id in state.played:
            continue
        if not holds(storylet.when, flags, band=band):
            continue
        if not all(_knows(state, who, fact) for who, facts in storylet.requires_known.items() for fact in facts):
            continue
        rows.append(storylet)
    return rows


def _due(storylet: Storylet, state: WorldState) -> bool:
    return bool(storylet.pays_off) and any(row.effect_id == storylet.pays_off for row in state.events)


def select(
    library: list[Storylet],
    state: WorldState,
    *,
    gap: str,
    slot: str,
    seed: str,
    band: str | None = None,
    pool: int = 3,
) -> tuple[Storylet, WorldState]:
    """Deal ``slot`` once: a due callback first, else a seeded pick among the top ``pool``.

    A slot already dealt is read back, so a reload, a retry or another device
    sees the same scene. With nothing eligible the gap's fallback plays.
    """

    by_id = {row.id: row for row in library}
    dealt = state.selections.get(slot)
    if dealt is not None and dealt.storylet_id in by_id:
        return by_id[dealt.storylet_id], state

    candidates = eligible(library, state, gap=gap, band=band)
    due = [row for row in candidates if _due(row, state)]
    if due:
        chosen = sorted(due, key=lambda row: (-row.salience, row.id))[0]
    elif candidates:
        ranked = sorted(candidates, key=lambda row: (-row.salience, row.id))[: max(1, pool)]
        digest = hashlib.sha256(f"{seed}|{slot}|{state.version}".encode()).digest()
        chosen = ranked[int.from_bytes(digest[:8], "big") % len(ranked)]
    else:
        fallbacks = [row for row in library if row.gap == gap and row.fallback]
        if not fallbacks:
            raise TransitionError("dead_end", f"gap {gap} has no eligible storylet and no fallback")
        chosen = fallbacks[0]

    nxt = state.model_copy(deep=True)
    nxt.selections[slot] = Selection(storylet_id=chosen.id, seed=seed, version=state.version)
    if not chosen.fallback:
        nxt.played.append(chosen.id)
    return chosen, nxt


def callback_source(storylet: Storylet, state: WorldState) -> Event | None:
    """The committed event a callback storylet answers (so its line can cite it)."""

    if not storylet.pays_off:
        return None
    return next((row for row in reversed(state.events) if row.effect_id == storylet.pays_off), None)


__all__ = [
    "ACTIONS",
    "Acknowledge",
    "Clarify",
    "Commit",
    "Decision",
    "EffectSpec",
    "Event",
    "Evidence",
    "Intent",
    "Permission",
    "Selection",
    "Storylet",
    "TransitionError",
    "TurnContract",
    "WorldState",
    "apply",
    "callback_source",
    "decide",
    "eligible",
    "event_id_for",
    "permission_key",
    "projected_flags",
    "select",
]
