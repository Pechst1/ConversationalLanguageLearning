"""N1 — what the learner decides on a generated day stays decided.

Connects :mod:`app.services.season.consequences` to the season's generated
days, behind ``SEASON_AGENCY_PILOT`` (off by default). A generated day's turn
carries a contract: what the learner may decide, under which limits. It comes
from ``agency.json`` when the day stages an authored premise (gap 1's «Romy
enquête», with its callbacks); on any other day it is the open contract
(:func:`open_contract`): the learner goes along with what the character asks,
or refuses it, under any limit they set in their own words.

Only the day whose required premise has an authored contract shows the writer
the contract rules (``learner_agency_rules``). Phase 1: given every day, they
had the writer invent a contract with «conditions» daily, and that vocabulary
leaked into the dialogue and the task. A ``season_checklist.learner_agency``
the writer proposes all the same is checked deterministically
(:func:`generated_contract`) and dropped (the day runs as before) when it does
not hold.

* **the turn** (:func:`agency_for_turn`) — the voice lane is told what the
  learner may decide, and returns the acts it heard with verbatim quotes;
* **the release** (:func:`acts_for_details`) — before the reply is shown, the
  acts are checked against the contract (:func:`consequences.decide`) and stored
  on the turn's details with the learner's text, in the respond transaction;
* **the settle** (:func:`settle_day`) — the day's settle commits them to
  ``state["agency"]`` (idempotent per day) and marks a staged callback played;
* **the next days** (:func:`brief_extras`) — the director reads the standing
  agreements and, when one is due, a callback that cites the learner's words:
  an authored storylet of the gap when one is due, else the oldest decision no
  later day has acted on yet (and, on an authored premise's day, the rules).

Nothing here calls a model, and every failure leaves the day as it was before
the pilot: an act that cannot be committed is logged and dropped.
"""
from __future__ import annotations

import json
import logging
import re
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
#: What a turn stores for the settle (:func:`acts_for_details`).
DETAIL_KEYS = ("season_acts", "agency_text", "agency_decisions", "agency_contract")
#: The voice's actions that refuse; only these reach the ending lane.
REFUSING = ("decline", "withhold")
#: Only a grant carries limits: «oui, mais sans mon nom».
LIMITABLE = ("accept", "show", "promise")
#: ``world.flags[NOTES_KEY][event_id]``: the line, the character and the gap of a commit.
NOTES_KEY = "notes"


class Contract(BaseModel):
    season: str = ""
    gap: str
    premise: str
    speaker: str
    subjects: dict[str, str]
    conditions: dict[str, str] = Field(default_factory=dict)
    effects: list[EffectSpec]
    #: Authored: the standing agreement per outcome («granted:no_name», «refused»).
    agreements: dict[str, str] = Field(default_factory=dict)
    #: Generated: what becomes true per effect id.
    outcomes: dict[str, str] = Field(default_factory=dict)
    #: The open contract (:func:`open_contract`): any limit the learner sets in their
    #: own words is honoured and recorded, not only the declared ones.
    open_conditions: bool = False

    def note_for(self, event: Any) -> str:
        """One English sentence for the director: what this committed event made true."""

        if self.open_conditions and event.effect_id in self.outcomes:
            # Agency walk 4, 12 Oct 2026: the open contract's subject is the writer's
            # private turn_want («The learner must want to say…»), which read as meta
            # text in the brief. What the learner said is what the next day needs.
            quote = event.evidence[0].text if event.evidence else ""
            return f"{self.outcomes[event.effect_id]} In their words: «{quote}»" if quote else self.outcomes[event.effect_id]
        if event.effect_id in self.outcomes:
            line = self.outcomes[event.effect_id]
        else:
            if event.action in ("accept", "show"):
                name = "granted" + (":" + "+".join(sorted(event.conditions)) if event.conditions else "")
            elif event.action in ("decline", "withhold"):
                name = "refused"
            else:
                name = event.action
            line = self.agreements.get(name) or self.agreements.get(name.split(":")[0]) or ""
            if line:
                return line
            line = f"The learner chose to {event.action} ({self.subjects.get(event.subject or '', event.subject)})."
        limits = [self.conditions.get(c, c) for c in event.conditions]
        return f"{line} Limits the learner set: {' '.join(limits)}" if limits else line

    def turn(self) -> TurnContract:
        return TurnContract(turn_id=f"{self.gap}.{self.premise}", speaker=self.speaker, effects=self.effects)

    def widened(self, intent: Intent) -> Contract:
        """An open contract that also honours the limits this intent set, each described
        by the learner's own words. Any other contract is returned unchanged."""

        new = [c for c in intent.conditions if c not in self.conditions and _SLUG.match(c)]
        if not self.open_conditions or not new:
            return self
        quote = intent.evidence[0].text if intent.evidence else ""
        conditions = dict(self.conditions)
        for slug in new[: max(0, MAX_CONDITIONS - len(conditions))]:
            words = slug.replace("_", " ")
            conditions[slug] = f"{words} (the learner's words: «{quote}»)" if quote else words
        effects = [
            spec.model_copy(update={"allowed_conditions": sorted({*spec.allowed_conditions, *conditions})})
            for spec in self.effects
        ]
        return self.model_copy(update={"conditions": conditions, "effects": effects})


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


def _authored(agency: Agency, gap: str, premise: str | None) -> Contract | None:
    """The contract ``agency.json`` writes for this gap's premise, if any."""

    if not premise:
        return None
    return next((row for row in agency.contracts if row.gap == gap and row.premise == premise), None)


#: What the writer may propose for one day (``season_checklist.learner_agency``).
MAX_SUBJECTS = 2
MAX_CONDITIONS = 4
MAX_EFFECTS = 4
_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def _cast_ids(season_id: str) -> set[str]:
    from app.services.season.format import load_season

    return {member.id for member in load_season(season_id).cast}


def _cast_name(season_id: str, member_id: str) -> str:
    from app.services.season.format import load_season

    member = next((row for row in load_season(season_id).cast if row.id == member_id), None)
    return member.name.split(" ")[0] if member else member_id


def generated_contract(season_id: str, gap: str, premise: str | None, raw: Any) -> Contract | None:
    """The writer's ``learner_agency`` as a contract, or ``None`` when it does not hold.

    Deterministic checks only: the speaker is in the cast; subjects, limits and
    effect ids are short slugs; every effect uses the action vocabulary, one of
    the day's subjects and only the day's limits, and says what becomes true
    (``outcome_en``). Generated effects never disclose a fact: what a character
    learns from an authored scene stays authored.
    """

    if not isinstance(raw, dict):
        return None
    try:
        speaker = str(raw.get("speaker") or "").strip()
        subjects = {
            str(k).strip(): " ".join(str(v).split())[:200]
            for k, v in dict(raw.get("subjects") or {}).items()
            if _SLUG.match(str(k).strip()) and str(v).strip()
        }
        conditions = {
            str(k).strip(): " ".join(str(v).split())[:200]
            for k, v in dict(raw.get("conditions") or {}).items()
            if _SLUG.match(str(k).strip()) and str(v).strip()
        }
        if speaker not in _cast_ids(season_id) or not subjects or len(subjects) > MAX_SUBJECTS:
            return None
        if len(conditions) > MAX_CONDITIONS:
            return None
        effects: list[EffectSpec] = []
        outcomes: dict[str, str] = {}
        for row in list(raw.get("effects") or [])[:MAX_EFFECTS]:
            effect_id = str(row.get("id") or "").strip()
            actions = [a for a in row.get("actions") or [] if a in ACTIONS]
            subject = str(row.get("subject") or "").strip()
            allowed = [c for c in row.get("allowed_conditions") or [] if c in conditions]
            outcome = " ".join(str(row.get("outcome_en") or "").split())[:200]
            if not _SLUG.match(effect_id) or effect_id in outcomes or not actions or subject not in subjects or not outcome:
                continue
            alternative = " ".join(str(row.get("alternative_en") or "").split())[:200] or None
            effects.append(
                EffectSpec(
                    id=effect_id, actions=actions, subject=subject, allowed_conditions=allowed, alternative=alternative
                )
            )
            outcomes[effect_id] = outcome
    except Exception:  # noqa: BLE001 - a malformed proposal is no contract, never a lost day
        logger.warning("agency: the writer's learner_agency does not parse")
        return None
    if not effects:
        return None
    return Contract(
        season=season_id,
        gap=gap,
        premise=premise or "own",
        speaker=speaker,
        subjects=subjects,
        conditions=conditions,
        effects=effects,
        outcomes=outcomes,
    )


#: Whatever today's turn asks, the learner may go along with it or refuse it.
OPEN_AGREE = ("accept", "show", "tell", "promise")
OPEN_REFUSE = ("decline", "withhold")


def open_contract(season_id: str, gap: str, premise: str | None, speaker: str, asked: str) -> Contract | None:
    """The contract of a generated day that has neither an authored nor a valid written
    one: the learner may go along with what the character asks today, or refuse it,
    under any limit they set in their own words. Built in code, so a decision is never
    lost because the writer left ``learner_agency`` out (agency walk, 12 Oct 2026)."""

    if speaker not in _cast_ids(season_id):
        return None
    asked = " ".join(str(asked or "").split())[:200] or "what the character asks of the learner today"
    return Contract(
        season=season_id,
        gap=gap,
        premise=premise or "open",
        speaker=speaker,
        subjects={"request": asked},
        effects=[
            EffectSpec(id="went_along", actions=list(OPEN_AGREE), subject="request"),
            EffectSpec(id="refused", actions=list(OPEN_REFUSE), subject="request"),
        ],
        outcomes={
            "went_along": f"The learner went along with what {_cast_name(season_id, speaker)} asked of them.",
            "refused": f"The learner refused what {_cast_name(season_id, speaker)} asked of them.",
        },
        open_conditions=True,
    )


def contract_for(season_day: dict | None, *, speaker: str | None = None) -> Contract | None:
    """The day's contract when the pilot is on: authored for its premise, else the
    writer's, else (given the scene's ``speaker``) the open contract."""

    if not enabled() or not isinstance(season_day, dict) or season_day.get("kind") != "gap":
        return None
    gap = str((season_day.get("position") or {}).get("segment") or "")
    checklist = season_day.get("checklist") or {}
    premise = str(checklist.get("premise_id") or "")
    season_id = str(season_day.get("id") or "")
    if not gap or not season_id:
        return None
    try:
        agency = load_agency(season_id)
    except Exception:  # noqa: BLE001 - a broken pilot file never costs the day
        logger.exception("agency: %s/agency.json could not be read", season_id)
        agency = Agency()
    authored = _authored(agency, gap, premise)
    if authored is not None:
        return authored.model_copy(update={"season": season_id})
    try:
        written = generated_contract(season_id, gap, premise or None, checklist.get("learner_agency"))
        if written is not None or not speaker:
            return written
        return open_contract(season_id, gap, premise or None, speaker, str(checklist.get("turn_want") or ""))
    except Exception:  # noqa: BLE001
        logger.exception("agency: no contract for %s", gap)
        return None


def contract_from_turn(turn_agency: dict | None) -> Contract | None:
    """The contract an ``agency_for_turn`` block carries."""

    if not isinstance(turn_agency, dict) or not isinstance(turn_agency.get("contract"), dict):
        return None
    try:
        return Contract.model_validate(turn_agency["contract"])
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------


def agency_for_turn(contract: Contract) -> dict[str, Any]:
    """What the voice lane reads (``story.season_turn.agency``)."""

    return {
        "contract": contract.model_dump(mode="json"),
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
        **({"conditions_open": True} if contract.open_conditions else {}),
        "if_condition_impossible": next((e.alternative for e in contract.effects if e.alternative), None),
    }


VOICE_ADDENDUM = """
agency is present: what the learner may decide in this scene. acts lists what the
learner's words actually decided about agency.may_decide, at most 3: action is one of
that entry's actions, subject its subject, evidence_quotes exact verbatim quotes from
learner_text or history[].learner. Letting the character use, do or keep something is
accept; refusing it is decline; giving information is tell. conditions are only the
limits the learner's own words set on an accept («mais sans mon nom»), each one in an
evidence quote: a key of agency.conditions when it matches, otherwise a short snake_case
name of what they asked for. Never copy agency.conditions the learner did not state: a
plain answer sets no limit.
A learner who has not clearly agreed or refused has decided nothing: then clarity is
ambiguous. Nothing about agency.may_decide in their words: acts is an empty list.
reply_fr never accepts a limit that is not a key of agency.conditions, unless
agency.conditions_open is true (then the character may honour a reasonable limit the
learner sets, and keeps it); otherwise offer agency.if_condition_impossible instead.
reply_fr never claims anything was written,
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


def _slugged(name: str) -> str:
    """«no name» or «No-Name» as the ``no_name`` the contract keys use."""

    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")[:40]


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
        # A limit belongs to a grant: «c'est moi, Paul» tells, and sets none
        # (second agency walk: the contract's limits copied onto a plain answer).
        conditions=[slug for c in act.conditions if (slug := _slugged(c))] if act.action in LIMITABLE else [],
        evidence=evidence,
        clarity=clarity,  # type: ignore[arg-type]
    )


def acts_for_details(contract: Contract, acts: list[VoiceAct], *, text: str) -> dict[str, Any]:
    """``{"season_acts": [...], "agency_text": text, "agency_decisions": [...]}`` for the
    turn's details. Decided against an empty world (what this premise allows); the
    settle decides again against the learner's own state."""

    intents = [intent for act in acts if (intent := _intent(act, text)) is not None]
    decisions = [
        decide(contract.widened(intent).turn(), intent, WorldState(), learner_text=text, source_turn="preview").kind
        for intent in intents
    ]
    return {
        "season_acts": [intent.model_dump(mode="json") for intent in intents],
        "agency_text": text,
        "agency_decisions": decisions,
        # The settle commits against this contract: an open one cannot be rebuilt
        # from the season day alone (it needs the scene's character).
        "agency_contract": contract.model_dump(mode="json"),
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
    if contract is None and isinstance(details.get("agency_contract"), dict):
        contract = contract_from_turn({"contract": details["agency_contract"]})
    text = str(details.get("agency_text") or details.get("learner_text") or "")
    if contract is not None and text:
        for index, raw in enumerate(details.get("season_acts") or []):
            try:
                intent = Intent.model_validate(raw)
            except Exception:  # noqa: BLE001 - a malformed act is dropped, not the day
                logger.warning("agency: unreadable act dropped: %r", raw)
                continue
            source = f"{event_id}:{index}"
            terms = contract.widened(intent)
            decision = decide(terms.turn(), intent, world, learner_text=text, source_turn=source)
            if not isinstance(decision, Commit):
                continue
            try:
                world = apply(world, decision.event, expected_version=world.version, learner_text=text)
            except TransitionError as exc:
                logger.warning("agency: act not committed (%s)", exc)
                continue
            notes = dict(world.flags.get(NOTES_KEY) or {})
            notes.setdefault(
                decision.event.event_id,
                {"line": terms.note_for(decision.event), "character": terms.speaker, "gap": terms.gap},
            )
            world.flags[NOTES_KEY] = notes
            changed = True
    callback = season_ctx.get("callback") or {}
    # Played when the accepted page claims it, whatever the learner answered (agency
    # walk 5: a scene whose answer went astray left its staged callback unplayed). A
    # page that left the callback out keeps it owed for a later day.
    if callback.get("id") and season_ctx.get("callback_staged") and callback["id"] not in world.played:
        world.played.append(str(callback["id"]))
        world.flags["callbacks"] = [
            *(world.flags.get("callbacks") or []),
            {"id": callback["id"], "source_event": callback.get("source_event"), "event_id": event_id},
        ]
        changed = True
    if changed:
        state = dict(state)
        state[STATE_KEY] = world.model_dump(mode="json")
    return state


# ---------------------------------------------------------------------------
# The next day
# ---------------------------------------------------------------------------


def _standing_lines(world: WorldState) -> list[str]:
    """The latest note per permission (or per other act), oldest first, at most six."""

    notes = world.flags.get(NOTES_KEY) or {}
    latest: dict[str, str] = {}
    for event in world.events:
        note = notes.get(event.event_id)
        if not note:
            continue
        key = f"{event.subject}>{event.recipient}" if event.action in ("accept", "show", "decline", "withhold", "revise") else event.event_id
        latest.pop(key, None)
        latest[key] = note["line"]
    return list(latest.values())[-6:]


def _authored_callback(agency: Agency, world: WorldState, gap_id: str, day: int, seed: str) -> dict | None:
    library = [row for row in agency.storylets if row.gap == gap_id]
    if not any(row.pays_off for row in library):
        return None
    library = [*library, Storylet(id="gap_as_planned", gap=gap_id, fallback=True)]
    try:
        chosen, _ = select(library, world, gap=gap_id, slot=f"{gap_id}.day{day}", seed=seed)
    except TransitionError:
        return None
    source = callback_source(chosen, world) if not chosen.fallback else None
    if source is None:
        return None
    return {
        "id": chosen.id,
        "character": (chosen.cast or [None])[0],
        "instruction": chosen.instruction,
        "learner_words": [row.text for row in source.evidence][:3],
        "source_event": source.event_id,
    }


def _owed_callback(world: WorldState) -> dict | None:
    """The oldest committed decision no later day has acted on yet."""

    notes = world.flags.get(NOTES_KEY) or {}
    acted_on = {
        row.get("source_event") for row in world.flags.get("callbacks") or [] if isinstance(row, dict)
    }
    for event in world.events:
        note = notes.get(event.event_id)
        if not note or event.event_id in acted_on or f"cb_{event.event_id}" in world.played:
            continue
        return {
            "id": f"cb_{event.event_id}",
            "character": note.get("character"),
            "instruction": (
                f"Show that this still holds and that it changed something today, through the character: {note['line']}"
            ),
            "learner_words": [row.text for row in event.evidence][:3],
            "source_event": event.event_id,
        }
    return None


#: What the writer reads to fill ``season_checklist.learner_agency``: pilot on, and only
#: on the day of a premise ``agency.json`` writes a contract for (:func:`brief_extras`).
AGENCY_RULES = {
    "actions": list(ACTIONS),
    "max_subjects": MAX_SUBJECTS,
    "max_conditions": MAX_CONDITIONS,
    "max_effects": MAX_EFFECTS,
    "shape": {
        "speaker": "cast id of the character the learner answers",
        "subjects": {"snake_case_id": "what the decision is about, one English sentence"},
        "conditions": {"snake_case_id": "a limit the learner may set that this character would honour"},
        "effects": [
            {
                "id": "snake_case_id",
                "actions": ["accept"],
                "subject": "one of subjects",
                "allowed_conditions": ["ids from conditions"],
                "outcome_en": "what is true afterwards, one English sentence",
                "alternative_en": "what the character offers instead of a limit they cannot honour, or null",
            }
        ],
    },
}


def brief_extras(
    season_id: str, gap_id: str, day: int, *, state: dict | None, seed: str, premise: str | None = None
) -> dict[str, Any]:
    """``{"learner_agency_rules", "agreements", "callback"}`` for the director's ``today``,
    or ``{}`` with the pilot off.

    ``learner_agency_rules`` only when today's required ``premise`` has an authored
    contract; any other day's turn runs on the open contract (:func:`contract_for`),
    so a decision is still recorded. The agreements and the callback come on any day
    once the learner has decided something."""

    if not enabled():
        return {}
    try:
        agency = load_agency(season_id)
    except Exception:  # noqa: BLE001
        agency = Agency()
    extras: dict[str, Any] = {}
    if _authored(agency, gap_id, premise) is not None:
        extras["learner_agency_rules"] = AGENCY_RULES
    world = world_of(state)
    if not world.events:
        return extras
    lines = _standing_lines(world)
    if lines:
        extras["agreements"] = lines
    callback = _authored_callback(agency, world, gap_id, day, seed) or _owed_callback(world)
    if callback is not None:
        extras["callback"] = callback
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
    "generated_contract",
    "enabled",
    "load_agency",
    "settle_day",
    "world_of",
]
