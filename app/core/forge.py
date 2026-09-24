"""La Forge — the séance as the grammar engine (WP-S3). The pure core.

WORK-PACKAGES-2026-09-24-seance §2 / WP-S3. No database here: the service
(:mod:`app.services.forge`) stores this state on the Atelier session and turns
its evidence decisions into ``apply_grammar_evidence`` calls; the simulation
(:mod:`app.core.srs.simulation`) runs the very same objects.

**Per-rule staircase.** Six rungs, weakest first::

    recognise → discriminate → build → transform → produce → free_use

A checked correct answer moves the rule up one rung, a checked error down one
and books a **reprise**: the same rule comes back 3–5 items later, with a
different item (the item provider is asked to exclude what was served). A
partial answer keeps the rung. An unchecked answer (the grader could not look)
moves nothing and counts for nothing. A correct ``free_use`` *tops the rule
out* for this séance: it has nothing left to prove today, so it stops taking
slots. That is the old adaptive lock folded in — every clean answer retires its
rung, and a rule that is clean at the top retires altogether.

**Composition.** A séance is ≈ 40 % today's rule, ≈ 40 % due rules, ≈ 20 %
contrast partners (shares renormalised over the roles that are present, and
over the rules still able to take a slot). Never two items of one rule back to
back (the one exception: a séance with a single rule). At most
:data:`MAX_NEW_RULES` brand-new rule per séance.

**Evidence, with caps.** Every checked answer yields exactly one evidence
entry. Within one séance only the first success per rule per rung — and the
first failure per rule — moves the schedule; the rest *fold*: they still feed
the concept's life (WP-L4 «Tenue») and the staircase, never the interval.
Successive schedule-moving successes of one rule inside one séance are massed
practice, not spacing, so their weight halves each time
(:data:`MASSED_WEIGHT_DECAY`): practice counts without inflating the memory.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

from app.core.srs.memory import Evidence, EvidenceFormat


class Rung(IntEnum):
    RECOGNISE = 0
    DISCRIMINATE = 1
    BUILD = 2
    TRANSFORM = 3
    PRODUCE = 4
    FREE_USE = 5


RUNG_NAMES: dict[Rung, str] = {
    Rung.RECOGNISE: "recognise",
    Rung.DISCRIMINATE: "discriminate",
    Rung.BUILD: "build",
    Rung.TRANSFORM: "transform",
    Rung.PRODUCE: "produce",
    Rung.FREE_USE: "free_use",
}
TOP_RUNG = Rung.FREE_USE

#: The WP-L3 evidence format each rung proves, and whether it is assisted.
#: ``produce`` is short, guided production (a model and a frame are given), so
#: it is production *with help*; ``free_use`` is the learner's own line in a
#: mini-situation — the only rung that counts as free use for «Tenue».
RUNG_EVIDENCE: dict[Rung, tuple[EvidenceFormat, bool]] = {
    Rung.RECOGNISE: (EvidenceFormat.RECOGNISE, False),
    Rung.DISCRIMINATE: (EvidenceFormat.RECOGNISE, False),
    Rung.BUILD: (EvidenceFormat.GUIDED, False),
    Rung.TRANSFORM: (EvidenceFormat.TRANSFORM, False),
    Rung.PRODUCE: (EvidenceFormat.PRODUCE, True),
    Rung.FREE_USE: (EvidenceFormat.PRODUCE, False),
}

#: Rungs whose success is a *spaced item* for WP-L4 (not a reply-like use).
SPACED_RUNGS = frozenset({Rung.RECOGNISE, Rung.DISCRIMINATE, Rung.BUILD, Rung.TRANSFORM})


class Role(StrEnum):
    TODAY = "today"
    DUE = "due"
    CONTRAST = "contrast"


ROLE_SHARES: dict[Role, float] = {Role.TODAY: 0.4, Role.DUE: 0.4, Role.CONTRAST: 0.2}

#: A reprise comes back this many items after the error (inclusive range).
REPRISE_MIN_GAP = 3
REPRISE_MAX_GAP = 5

#: Never more than this many brand-new rules in one séance.
MAX_NEW_RULES = 1

#: Weight factor of the k-th schedule-moving success of one rule in one séance.
MASSED_WEIGHT_DECAY = 0.5

#: Séance length bounds (items) and the rhythm's séance budget (seconds).
MIN_SEANCE_ITEMS = 6
MAX_SEANCE_ITEMS = 24
DEFAULT_SECONDS_PER_ITEM = 25.0
SEANCE_SECONDS_BY_RHYTHM: dict[str, int] = {
    "leger": 240,
    "regulier": 360,
    "soutenu": 480,
    "intensif": 600,
}

#: «Épreuve de la règle»: five mixed items including production.
TEST_OUT_RUNGS: tuple[Rung, ...] = (
    Rung.RECOGNISE,
    Rung.DISCRIMINATE,
    Rung.BUILD,
    Rung.TRANSFORM,
    Rung.FREE_USE,
)
TEST_OUT_PASS_CORRECT = 4

MODE_SEANCE = "seance"
MODE_TEST_OUT = "test_out"
#: WP-S7 Éclair: the discriminate rung only, with the forge's evidence caps and
#: no staircase (an Éclair never moves a rule's rung).
MODE_ECLAIR = "eclair"


def rung_name(rung: int) -> str:
    return RUNG_NAMES[Rung(clamp_rung(rung))]


def clamp_rung(rung: int | None) -> int:
    return int(max(Rung.RECOGNISE, min(TOP_RUNG, int(rung or 0))))


def seance_length(budget_seconds: float | None, seconds_per_item: float | None) -> int:
    """Items in a séance: the rhythm's budget over the learner's measured pace."""

    budget = float(budget_seconds or SEANCE_SECONDS_BY_RHYTHM["regulier"])
    pace = float(seconds_per_item or DEFAULT_SECONDS_PER_ITEM)
    pace = max(8.0, pace)
    return int(max(MIN_SEANCE_ITEMS, min(MAX_SEANCE_ITEMS, round(budget / pace))))


# ---------------------------------------------------------------------------
# Verdicts and the staircase
# ---------------------------------------------------------------------------

OUTCOME_CORRECT = "correct"
OUTCOME_PARTIAL = "partial"
OUTCOME_INCORRECT = "incorrect"


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the grader said about one answer (WP-S1 makes it arrive fast).

    ``checked`` is False when nobody could actually look at the answer (the
    checker was unavailable, or only a placeholder verdict exists): such an
    answer never counts — not for the staircase, the schedule or the combo.
    """

    outcome: str
    checked: bool = True
    confidence: str | None = None
    #: An unchecked answer's instant local reading (WP-S1: free production's
    #: detector check while the relecture runs). It only keeps the staircase
    #: moving — a sentence that uses the rule steps up at once — and is never
    #: evidence: the relecture's verdict is (``ForgeService.amend_attempt``).
    local: str | None = None

    @property
    def correct(self) -> bool:
        return self.outcome == OUTCOME_CORRECT

    @property
    def partial(self) -> bool:
        return self.outcome == OUTCOME_PARTIAL

    @classmethod
    def right(cls, *, confidence: str | None = None) -> Verdict:
        return cls(OUTCOME_CORRECT, confidence=confidence)

    @classmethod
    def wrong(cls, *, confidence: str | None = None) -> Verdict:
        return cls(OUTCOME_INCORRECT, confidence=confidence)


def step_rung(rung: int, verdict: Verdict) -> int:
    """The staircase: up on correct, down on error, stay on partial/unchecked."""

    rung = clamp_rung(rung)
    if not verdict.checked:
        # A provisional «uses the rule» moves on; a provisional miss is only a
        # hint and never takes a rung away.
        return clamp_rung(rung + 1) if verdict.local == OUTCOME_CORRECT else rung
    if verdict.partial:
        return rung
    if verdict.correct:
        return clamp_rung(rung + 1)
    return clamp_rung(rung - 1)


def evidence_for(rung: int, verdict: Verdict) -> Evidence | None:
    """The WP-L3 observation one answered item is. ``None``: unchecked."""

    if not verdict.checked:
        return None
    fmt, assisted = RUNG_EVIDENCE[Rung(clamp_rung(rung))]
    if verdict.partial:
        return Evidence(fmt, correct=True, assisted=True)
    return Evidence(fmt, correct=verdict.correct, assisted=assisted)


def reprise_gap(concept_id: int, position: int) -> int:
    """3–5 items: deterministic, so a resumed séance agrees with itself."""

    span = REPRISE_MAX_GAP - REPRISE_MIN_GAP + 1
    return REPRISE_MIN_GAP + (int(concept_id) * 7 + int(position) * 3) % span


# ---------------------------------------------------------------------------
# The séance's state
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ForgeUnit:
    """One rule entering a séance (from the picker, WP-S4)."""

    concept_id: int
    role: str = Role.TODAY.value
    #: The rung the rule stands on (``UserGrammarProgress.forge_rung``).
    rung: int = 0
    #: Never practised: no progress history at all.
    is_new: bool = False
    #: Introduced ≥ 14 days ago, not held, no spaced success yet: its first
    #: item today is posed in a spaced format (WP-L4 «Tenue» needs one).
    needs_spaced: bool = False


@dataclass(slots=True)
class RuleTrack:
    concept_id: int
    role: str
    rung: int
    served: int = 0
    last_position: int = -1
    reprise_at: int | None = None
    topped: bool = False
    needs_spaced: bool = False
    #: Rungs whose success already moved the schedule this séance.
    scheduled_success_rungs: list[int] = field(default_factory=list)
    scheduled_failure: bool = False
    exhausted_rungs: list[int] = field(default_factory=list)

    def entry_rung(self) -> int:
        if self.needs_spaced:
            return min(self.rung, int(Rung.TRANSFORM))
        return self.rung


@dataclass(slots=True)
class Slot:
    position: int
    concept_id: int
    rung: int
    role: str
    reprise: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "rung_name": rung_name(self.rung)}


@dataclass(slots=True)
class EvidenceDecision:
    """What one answered item does to the memory model."""

    concept_id: int
    rung: int
    evidence: Evidence | None
    #: Moves the schedule (``apply_grammar_evidence``); else it folds.
    schedule: bool = False
    #: Weight factor for the schedule move (massed practice decays).
    weight_scale: float = 1.0
    #: Counted at all (checked). Unchecked answers are never evidence.
    counted: bool = False
    new_rung: int = 0

    def ledger(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "rung": self.rung,
            "format": self.evidence.format.value if self.evidence else None,
            "correct": bool(self.evidence.correct) if self.evidence else None,
            "assisted": bool(self.evidence.assisted) if self.evidence else None,
            "schedule": self.schedule,
            "weight_scale": round(self.weight_scale, 4),
            "counted": self.counted,
        }


def _prepare_units(units: Iterable[ForgeUnit]) -> list[ForgeUnit]:
    """De-duplicate, and keep at most :data:`MAX_NEW_RULES` brand-new rules."""

    seen: set[int] = set()
    out: list[ForgeUnit] = []
    new_count = 0
    # Today's rule first, so the one new rule allowed is today's.
    order = {Role.TODAY.value: 0, Role.DUE.value: 1, Role.CONTRAST.value: 2}
    for unit in sorted(units, key=lambda item: order.get(str(item.role), 3)):
        cid = int(unit.concept_id)
        if cid in seen:
            continue
        if unit.is_new:
            if new_count >= MAX_NEW_RULES or unit.role != Role.TODAY.value:
                continue
            new_count += 1
        seen.add(cid)
        out.append(unit)
    return out


@dataclass(slots=True)
class ForgeState:
    """One séance (or one test-out): its rules, its history, its evidence."""

    mode: str
    length: int
    tracks: list[RuleTrack]
    history: list[dict[str, Any]] = field(default_factory=list)
    pending: dict[str, Any] | None = None
    served_fingerprints: list[str] = field(default_factory=list)
    #: Test-out: the fixed rung order of the five items.
    plan: list[int] = field(default_factory=list)
    finished: bool = False
    result: dict[str, Any] | None = None

    # -- construction ------------------------------------------------------

    @classmethod
    def seance(cls, units: Iterable[ForgeUnit], *, length: int) -> ForgeState:
        prepared = _prepare_units(units)
        tracks = [
            RuleTrack(
                concept_id=int(unit.concept_id),
                role=str(unit.role),
                rung=clamp_rung(unit.rung),
                needs_spaced=bool(unit.needs_spaced),
            )
            for unit in prepared
        ]
        return cls(mode=MODE_SEANCE, length=max(1, int(length)), tracks=tracks)

    @classmethod
    def test_out(cls, concept_id: int) -> ForgeState:
        track = RuleTrack(concept_id=int(concept_id), role=Role.TODAY.value, rung=0)
        return cls(
            mode=MODE_TEST_OUT,
            length=len(TEST_OUT_RUNGS),
            tracks=[track],
            plan=[int(rung) for rung in TEST_OUT_RUNGS],
        )

    # -- (de)serialisation, for the session's JSON column --------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "mode": self.mode,
            "length": self.length,
            "tracks": [asdict(track) for track in self.tracks],
            "history": list(self.history),
            "pending": self.pending,
            "served_fingerprints": list(self.served_fingerprints),
            "plan": list(self.plan),
            "finished": self.finished,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ForgeState:
        tracks = [RuleTrack(**dict(track)) for track in raw.get("tracks") or []]
        return cls(
            mode=str(raw.get("mode") or MODE_SEANCE),
            length=int(raw.get("length") or 0),
            tracks=tracks,
            history=list(raw.get("history") or []),
            pending=raw.get("pending"),
            served_fingerprints=list(raw.get("served_fingerprints") or []),
            plan=[int(item) for item in raw.get("plan") or []],
            finished=bool(raw.get("finished")),
            result=raw.get("result"),
        )

    # -- reading -----------------------------------------------------------

    def track(self, concept_id: int) -> RuleTrack | None:
        return next((track for track in self.tracks if track.concept_id == int(concept_id)), None)

    @property
    def position(self) -> int:
        """Items answered so far (unchecked ones included: they were served)."""

        return len(self.history)

    @property
    def counted_items(self) -> int:
        return sum(1 for entry in self.history if entry.get("counted"))

    @property
    def evidence_written(self) -> int:
        return sum(1 for entry in self.history if entry.get("counted"))

    def served_by_role(self) -> dict[str, int]:
        counts = {role.value: 0 for role in Role}
        for entry in self.history:
            counts[str(entry.get("role"))] = counts.get(str(entry.get("role")), 0) + 1
        return counts

    def last_concept_id(self) -> int | None:
        return int(self.history[-1]["concept_id"]) if self.history else None

    # -- composing the next item ---------------------------------------------

    def next_slot(self) -> Slot | None:
        """The rule and rung of the next item, or ``None``: the séance is over."""

        if self.finished:
            return None
        position = self.position
        if position >= self.length:
            return None
        if self.mode == MODE_TEST_OUT:
            track = self.tracks[0]
            return Slot(position=position, concept_id=track.concept_id, rung=self.plan[position], role=track.role)

        live = [track for track in self.tracks if not track.topped]
        if not live:
            return None
        last = self.last_concept_id()
        single_rule = len(self.tracks) == 1
        eligible = [track for track in live if single_rule or track.concept_id != last]
        if not eligible:
            # Only the rule just served could go on: never back to back.
            return None

        due_reprises = [
            track for track in eligible if track.reprise_at is not None and track.reprise_at <= position
        ]
        if due_reprises:
            pick = min(due_reprises, key=lambda track: (track.reprise_at, track.served))
            return Slot(position, pick.concept_id, pick.rung, pick.role, reprise=True)

        # A rule waiting for its reprise sits out until then, when it can.
        waiting = [track for track in eligible if track.reprise_at is None or track.reprise_at <= position]
        pool = waiting or eligible

        roles_present = {track.role for track in pool}
        weights = {role: ROLE_SHARES.get(Role(role), 0.0) for role in roles_present}
        total = sum(weights.values()) or 1.0
        served = self.served_by_role()
        # Deficit against the renormalised share of the items served so far
        # plus this one: the role furthest behind its share goes next.
        deficits = {
            role: (weights[role] / total) * (position + 1) - served.get(role, 0)
            for role in roles_present
        }
        role_order = {Role.TODAY.value: 0, Role.DUE.value: 1, Role.CONTRAST.value: 2}
        role = max(roles_present, key=lambda item: (deficits[item], -role_order.get(item, 3)))
        candidates = [track for track in pool if track.role == role]
        pick = min(candidates, key=lambda track: (track.served, track.rung, track.concept_id))
        rung = pick.entry_rung() if pick.served == 0 else pick.rung
        return Slot(position, pick.concept_id, rung, pick.role)

    # -- recording one answer ------------------------------------------------

    def record(
        self,
        *,
        concept_id: int,
        rung: int,
        verdict: Verdict,
        fingerprint: str | None = None,
        role: str | None = None,
    ) -> EvidenceDecision:
        """One answered item: move the staircase, decide the evidence."""

        track = self.track(concept_id)
        if track is None:
            # An item of a rule the forge did not seat (a legacy client):
            # it is still evidence, graded at its own rung.
            track = RuleTrack(concept_id=int(concept_id), role=str(role or Role.DUE.value), rung=clamp_rung(rung))
            self.tracks.append(track)
        position = self.position
        rung = clamp_rung(rung)
        evidence = evidence_for(rung, verdict)
        decision = EvidenceDecision(
            concept_id=track.concept_id,
            rung=rung,
            evidence=evidence,
            counted=evidence is not None,
            new_rung=track.rung,
        )
        if evidence is not None:
            if evidence.correct:
                if rung not in track.scheduled_success_rungs:
                    decision.schedule = True
                    decision.weight_scale = MASSED_WEIGHT_DECAY ** len(track.scheduled_success_rungs)
                    track.scheduled_success_rungs.append(rung)
                if rung in SPACED_RUNGS:
                    track.needs_spaced = False
            elif not track.scheduled_failure:
                decision.schedule = True
                track.scheduled_failure = True

            if self.mode == MODE_SEANCE:
                track.rung = step_rung(rung, verdict)
                if verdict.correct and rung == TOP_RUNG:
                    track.topped = True
                if verdict.correct or verdict.partial:
                    if track.reprise_at is not None and track.reprise_at <= position:
                        track.reprise_at = None
                else:
                    gap = reprise_gap(track.concept_id, position)
                    track.reprise_at = min(position + gap, self.length - 1)
                    if track.reprise_at <= position:
                        track.reprise_at = None
        elif self.mode == MODE_SEANCE and verdict.local == OUTCOME_CORRECT:
            # Unchecked but the local check reads the rule: the staircase moves
            # on (no evidence, no reprise); the relecture decides the evidence.
            track.rung = step_rung(rung, verdict)
            if rung == TOP_RUNG:
                track.topped = True
        decision.new_rung = track.rung
        track.served += 1
        track.last_position = position
        if fingerprint:
            self.served_fingerprints.append(str(fingerprint))
        self.history.append(
            {
                "position": position,
                "concept_id": track.concept_id,
                "role": track.role,
                "rung": rung,
                "outcome": verdict.outcome,
                "checked": verdict.checked,
                "fingerprint": fingerprint,
                **decision.ledger(),
            }
        )
        self.pending = None
        if self.mode == MODE_TEST_OUT and self.position >= self.length:
            self.finished = True
            self.result = evaluate_test_out(
                [(int(entry["rung"]), entry.get("outcome") == OUTCOME_CORRECT and bool(entry.get("checked"))) for entry in self.history]
            ).to_dict()
        elif self.mode == MODE_SEANCE and self.next_slot() is None:
            self.finished = True
        return decision


# ---------------------------------------------------------------------------
# Test-out
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TestOutResult:
    passed: bool
    correct: int
    total: int
    production_correct: bool
    #: Where the rule enters the forge (the top on a pass).
    placement_rung: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "correct": self.correct,
            "total": self.total,
            "production_correct": self.production_correct,
            "placement_rung": self.placement_rung,
            "placement_rung_name": rung_name(self.placement_rung),
        }


def evaluate_test_out(results: Sequence[tuple[int, bool]]) -> TestOutResult:
    """Pass: ≥ 4 of 5 with the production item correct.

    Fail: the rule enters the forge at the lowest rung it failed — the first
    step the learner could not take. A production failure alone places it on
    guided ``produce`` (one below free use). Unchecked items count as not
    proven.
    """

    total = len(results)
    correct = sum(1 for _rung, ok in results if ok)
    production = [ok for rung, ok in results if rung >= Rung.PRODUCE]
    production_correct = bool(production) and all(production)
    passed = correct >= min(TEST_OUT_PASS_CORRECT, total) and production_correct
    if passed:
        return TestOutResult(True, correct, total, True, int(TOP_RUNG))
    failed = [rung for rung, ok in results if not ok]
    placement = min(failed) if failed else int(Rung.PRODUCE)
    placement = min(placement, int(Rung.PRODUCE))
    return TestOutResult(False, correct, total, production_correct, clamp_rung(placement))


# ---------------------------------------------------------------------------
# WP-S7 — the combo
# ---------------------------------------------------------------------------


def _combo_step(entry: dict[str, Any]) -> str:
    """``extends`` · ``breaks`` · ``skips`` for one answered item (S1 semantics).

    Only a checked verdict settles an answer: a checked right one extends the
    run, a checked wrong or partial one resets it, an unchecked or provisional
    one (its relecture still running) does neither.
    """

    if not entry.get("checked"):
        return "skips"
    return "extends" if entry.get("outcome") == OUTCOME_CORRECT else "breaks"


def combo_runs(history: Sequence[dict[str, Any]]) -> tuple[int, int]:
    """``(current, best)``: the run of checked right answers, newest last."""

    current = best = 0
    for entry in sorted(history, key=lambda item: int(item.get("position", 0))):
        step = _combo_step(entry)
        if step == "extends":
            current += 1
            best = max(best, current)
        elif step == "breaks":
            current = 0
    return current, best


def distinct_rule_runs(concept_ids: Sequence[int]) -> int:
    """How many times one rule is served twice in a row (0 is the rule)."""

    return sum(1 for left, right in zip(concept_ids, concept_ids[1:], strict=False) if left == right)


def role_shares(history: Sequence[dict[str, Any]]) -> dict[str, float]:
    total = len(history)
    if not total:
        return {}
    counts: dict[str, int] = {}
    for entry in history:
        counts[str(entry.get("role"))] = counts.get(str(entry.get("role")), 0) + 1
    return {role: count / total for role, count in counts.items()}


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


__all__ = [
    "DEFAULT_SECONDS_PER_ITEM",
    "MASSED_WEIGHT_DECAY",
    "MAX_NEW_RULES",
    "MODE_ECLAIR",
    "MODE_SEANCE",
    "MODE_TEST_OUT",
    "OUTCOME_CORRECT",
    "OUTCOME_INCORRECT",
    "OUTCOME_PARTIAL",
    "REPRISE_MAX_GAP",
    "REPRISE_MIN_GAP",
    "ROLE_SHARES",
    "RUNG_EVIDENCE",
    "RUNG_NAMES",
    "SEANCE_SECONDS_BY_RHYTHM",
    "SPACED_RUNGS",
    "TEST_OUT_RUNGS",
    "TOP_RUNG",
    "EvidenceDecision",
    "ForgeState",
    "ForgeUnit",
    "Role",
    "RuleTrack",
    "Rung",
    "Slot",
    "TestOutResult",
    "Verdict",
    "clamp_rung",
    "combo_runs",
    "distinct_rule_runs",
    "evaluate_test_out",
    "evidence_for",
    "median",
    "reprise_gap",
    "role_shares",
    "rung_name",
    "seance_length",
    "step_rung",
]
