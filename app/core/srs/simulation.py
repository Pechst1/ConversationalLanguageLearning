"""A seeded learner simulation over the one memory model (WP-L3).

The numbers it produces are the input for WP-L6's intake throttle: how many
reviews a day each new item per day costs once the schedule has settled.

The learner is deliberately simple — a fixed accuracy, no forgetting curve — so
the result isolates the *scheduler's* load:

* one new item per day (``new_per_day``) is introduced the way §2.4 introduces a
  concept: a guided Essai item, then its use in the reply (Emploi);
* every due item is reviewed on its due day, with a Rappel format that scales
  with its stability (WP-L4: recognise under 3 days, guided under 7, transform
  under 15, free production above);
* each observation is correct with probability ``accuracy``; an error in
  production is a lapse, an error in an easier format a Hard.

The ``rated`` profile replays the same learner on self-graded cards (right →
Good, wrong → Again), the vocabulary-style baseline.
"""
from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass, field
from types import SimpleNamespace

from app.core.srs.memory import (
    MAX_INTERVAL_DAYS,
    Evidence,
    EvidenceFormat,
    MemoryState,
    Rating,
    review,
)

SIMULATION_START = dt.datetime(2026, 1, 5, 8, 0, tzinfo=dt.UTC)


def rappel_format(stability: float) -> EvidenceFormat:
    """The Rappel format a concept of this stability gets (WP-L4's ladder)."""

    if stability < 3:
        return EvidenceFormat.RECOGNISE
    if stability < 7:
        return EvidenceFormat.GUIDED
    if stability < 15:
        return EvidenceFormat.TRANSFORM
    return EvidenceFormat.PRODUCE


@dataclass
class SimulatedItem:
    introduced_day: int
    state: MemoryState = field(default_factory=MemoryState)
    due_day: int = 0
    review_days: list[int] = field(default_factory=list)
    intervals: list[int] = field(default_factory=list)
    #: One per observation, aligned with ``intervals``: was it correct, a lapse.
    outcomes: list[bool] = field(default_factory=list)
    lapses_at: list[bool] = field(default_factory=list)
    lapse_days: list[int] = field(default_factory=list)


@dataclass
class SimulationResult:
    accuracy: float
    profile: str
    days: int
    new_per_day: int
    reviews_per_day: list[int]
    items: list[SimulatedItem]
    steady_window: tuple[int, int]

    @property
    def steady_state_reviews_per_day(self) -> float:
        start, end = self.steady_window
        window = self.reviews_per_day[start:end]
        return sum(window) / max(1, len(window))

    @property
    def load_per_new_item(self) -> float:
        """Reviews a day per new item a day, in the steady window."""

        return self.steady_state_reviews_per_day / max(1, self.new_per_day)

    @property
    def max_gap_days(self) -> int:
        gaps = [
            later - earlier
            for item in self.items
            for earlier, later in zip(item.review_days, item.review_days[1:], strict=False)
        ]
        return max(gaps, default=0)

    @property
    def total_lapses(self) -> int:
        return sum(len(item.lapse_days) for item in self.items)


def simulate_learner(
    accuracy: float,
    *,
    days: int = 120,
    new_per_day: int = 1,
    seed: int = 20260923,
    profile: str = "grammar",
    steady_window: tuple[int, int] | None = None,
) -> SimulationResult:
    rng = random.Random(f"{seed}:{accuracy}:{profile}")  # noqa: S311 - a seeded simulation
    items: list[SimulatedItem] = []
    reviews_per_day = [0] * days

    def observe(item: SimulatedItem, day: int, fmt: EvidenceFormat) -> None:
        correct = rng.random() < accuracy
        if profile == "rated":
            evidence = Evidence.rated(Rating.GOOD if correct else Rating.AGAIN)
        else:
            evidence = Evidence(fmt, correct=correct)
        decision = review(item.state, evidence, now=SIMULATION_START + dt.timedelta(days=day))
        if decision is None:  # pragma: no cover - only a mention returns None
            raise RuntimeError("a graded observation must schedule")
        item.state = MemoryState(
            stability=decision.stability,
            difficulty=decision.difficulty,
            reps=decision.reps,
            lapses=decision.lapses,
        )
        item.due_day = day + decision.interval_days
        item.intervals.append(decision.interval_days)
        item.outcomes.append(correct)
        item.lapses_at.append(decision.is_lapse)
        if decision.is_lapse:
            item.lapse_days.append(day)

    for day in range(days):
        for item in items:
            if item.due_day <= day:
                reviews_per_day[day] += 1
                item.review_days.append(day)
                observe(item, day, rappel_format(item.state.stability))
        for _ in range(new_per_day):
            item = SimulatedItem(introduced_day=day)
            item.review_days.append(day)
            observe(item, day, EvidenceFormat.GUIDED)  # Essai
            observe(item, day, EvidenceFormat.PRODUCE)  # Emploi, same day
            items.append(item)

    window = steady_window or (max(0, days - 30), days)
    return SimulationResult(
        accuracy=accuracy,
        profile=profile,
        days=days,
        new_per_day=new_per_day,
        reviews_per_day=reviews_per_day,
        items=items,
        steady_window=window,
    )


# ---------------------------------------------------------------------------
# WP-L7/L8 — a learner walking one sub-band
# ---------------------------------------------------------------------------

#: WP-L7's word rule: retrievability ≥ 0.85 on a card seen at least twice.
_WORD_KNOWN_R = 0.85
_R_FACTOR = 0.9 ** (1 / -0.5) - 1


def _retrievability(stability: float, elapsed_days: float) -> float:
    if stability <= 0:
        return 0.0
    return (1 + _R_FACTOR * max(0.0, elapsed_days) / stability) ** -0.5


@dataclass
class BandDay:
    """The learner's state at the end of one simulated day."""

    day: int
    units_introduced: int
    units_held: int
    words_introduced: int
    words_known: int
    #: Items introduced 7–60 days ago, and how many of them stuck.
    retention_sample: int
    retention_kept: int
    units_sample: int = 0
    units_kept: int = 0
    #: Cumulative graded observations and how many were right (reviews and introductions).
    observations: int = 0
    correct: int = 0
    #: Days since introduction of every unit introduced but not yet held.
    pending_elapsed: tuple[int, ...] = ()


@dataclass
class BandSimulation:
    accuracy: float
    units_per_week: float
    words_per_day: float
    units_total: int
    words_total: int
    units_required: int
    words_required: int
    days: list[BandDay]
    #: First day both coverage criteria are met (``None`` if never, in the horizon).
    coverage_day: int | None


def new_unit_life() -> SimpleNamespace:
    """A grammar unit's WP-L4 life, as ``UserGrammarProgress`` stores it."""

    return SimpleNamespace(
        created_at=None,
        reps=0,
        introduced_at=None,
        free_use_first_at=None,
        free_use_last_at=None,
        spaced_success_at=None,
        held_at=None,
    )


def note_unit_life(life: SimpleNamespace, evidence: Evidence, *, day: int) -> None:
    """One observation through the app's own «Tenue» bookkeeping."""

    from app.services.concept_life import note_concept_evidence

    note_concept_evidence(life, evidence, now=SIMULATION_START + dt.timedelta(days=day))


def simulate_band_coverage(
    *,
    accuracy: float,
    units_per_week: float,
    words_per_day: float,
    units_total: int,
    words_total: int,
    units_share: float = 0.85,
    words_share: float = 0.80,
    horizon_days: int = 400,
    seed: int = 20260924,
) -> BandSimulation:
    """One learner, one sub-band: intake at a rhythm, every due item reviewed.

    * **units** are introduced as §2.4 introduces them (guided Essai + Emploi in
      the reply) and reviewed on their due day in a format that grows with
      stability; held is WP-L4's «Tenue», kept by the same code the app runs
      (:func:`new_unit_life` / :func:`app.services.concept_life.note_concept_evidence`),
      and once held a unit stays counted (a lapse brings it back, it does not
      uncover the band);
    * **words** are self-rated cards (right → Good, wrong → Again), introduced
      then reviewed on their due day; known = seen twice, last answer right and
      retrievability ≥ 0.85 that evening;
    * intake stops once every unit / word of the band has been introduced.
    """

    import math

    rng = random.Random(f"band:{seed}:{accuracy}:{units_per_week}:{words_per_day}")  # noqa: S311
    units_required = math.ceil(units_total * units_share)
    words_required = math.ceil(words_total * words_share)

    @dataclass
    class _Item:
        introduced: int
        state: MemoryState = field(default_factory=MemoryState)
        due: int = 0
        last: int = 0
        last_correct: bool = False
        lapsed: bool = False
        life: object | None = None

        @property
        def ever_held(self) -> bool:
            return getattr(self.life, "held_at", None) is not None

    tally = {"observations": 0, "correct": 0}

    def observe(item: _Item, day: int, evidence: Evidence, correct: bool) -> None:
        tally["observations"] += 1
        tally["correct"] += 1 if correct else 0
        decision = review(item.state, evidence, now=SIMULATION_START + dt.timedelta(days=day))
        if decision is None:  # pragma: no cover - a graded observation always schedules
            raise RuntimeError("a graded observation must schedule")
        item.state = MemoryState(
            stability=decision.stability,
            difficulty=decision.difficulty,
            reps=decision.reps,
            lapses=decision.lapses,
        )
        item.due = day + decision.interval_days
        item.last = day
        item.last_correct = correct
        item.lapsed = decision.is_lapse
        if item.life is not None:
            note_unit_life(item.life, evidence, day=day)

    units: list[_Item] = []
    words: list[_Item] = []
    history: list[BandDay] = []
    coverage_day: int | None = None
    for day in range(horizon_days):
        for item in units:
            if item.due <= day:
                correct = rng.random() < accuracy
                observe(item, day, Evidence(rappel_format(item.state.stability), correct=correct), correct)
        for item in words:
            if item.due <= day:
                correct = rng.random() < accuracy
                observe(item, day, Evidence.rated(Rating.GOOD if correct else Rating.AGAIN), correct)
        # Intake by exact quota (``floor((day + 1) · rate)``), not a float
        # accumulator: 7 × (1/7) must make one unit, not 0.999….
        unit_quota = math.floor((day + 1) * units_per_week / 7.0 + 1e-9)
        while len(units) < min(unit_quota, units_total):
            item = _Item(introduced=day, life=new_unit_life())
            for fmt in (EvidenceFormat.GUIDED, EvidenceFormat.PRODUCE):
                correct = rng.random() < accuracy
                observe(item, day, Evidence(fmt, correct=correct), correct)
            units.append(item)
        word_quota = math.floor((day + 1) * words_per_day + 1e-9)
        while len(words) < min(word_quota, words_total):
            item = _Item(introduced=day)
            correct = rng.random() < accuracy
            observe(item, day, Evidence.rated(Rating.GOOD if correct else Rating.AGAIN), correct)
            words.append(item)

        # «Tenue» is written once and never cleared: a later lapse makes a unit
        # fragile and it comes back in the reviews, the band stays covered.
        held = sum(1 for item in units if item.ever_held)
        known = sum(
            1
            for item in words
            if item.state.reps >= 2
            and item.last_correct
            and _retrievability(item.state.stability, day - item.last) >= _WORD_KNOWN_R
        )
        sample = kept = 0
        units_sample = units_kept = 0
        for item in units:
            if 7 <= day - item.introduced <= 60:
                units_sample += 1
                units_kept += 0 if item.lapsed else 1
        for item in words:
            if 7 <= day - item.introduced <= 60:
                sample += 1
                kept += 1 if (
                    item.state.reps >= 2
                    and item.last_correct
                    and _retrievability(item.state.stability, day - item.last) >= _WORD_KNOWN_R
                ) else 0
        history.append(
            BandDay(
                day=day,
                units_introduced=len(units),
                units_held=held,
                words_introduced=len(words),
                words_known=known,
                retention_sample=sample,
                retention_kept=kept,
                units_sample=units_sample,
                units_kept=units_kept,
                observations=tally["observations"],
                correct=tally["correct"],
                pending_elapsed=tuple(day - item.introduced for item in units if not item.ever_held),
            )
        )
        if coverage_day is None and held >= units_required and known >= words_required:
            coverage_day = day
            break
    return BandSimulation(
        accuracy=accuracy,
        units_per_week=units_per_week,
        words_per_day=words_per_day,
        units_total=units_total,
        words_total=words_total,
        units_required=units_required,
        words_required=words_required,
        days=history,
        coverage_day=coverage_day,
    )


# ---------------------------------------------------------------------------
# WP-S3 — items to «Tenue» per rule: today's ladder versus La Forge
# ---------------------------------------------------------------------------

#: The legacy ladder, per concept, in serving order: (round, mode, items).
_LEGACY_LADDER: tuple[tuple[str, str, int], ...] = (
    ("recognize", "fill", 3),
    ("recognize", "classify", 3),
    ("recognize", "word_bank", 3),
    ("transform", "rewrite", 3),
    ("sentence", "sentence", 1),
    ("speak", "speak", 1),
    ("conversation", "conversation", 1),
)


@dataclass
class ItemsToHeld:
    """One simulated learner, one engine: how many items each rule cost."""

    engine: str
    accuracy: float
    days: int
    rappel: bool
    #: Items a rule had cost when it became held (held rules only).
    items_to_held: list[int]
    #: Items spent on rules introduced early enough to be judged, never held.
    censored: list[int]
    rules_judged: int
    #: Brand-new rules in the séance that had the most of them.
    max_new_rules_per_seance: int
    #: Every séance item answered, and the evidence entries they wrote.
    items_answered: int
    evidence_written: int
    days_to_held: list[int] = field(default_factory=list)
    #: WP-S8: the simulation day each rule was held on (every held rule,
    #: judged or not), for «rules held within N days».
    held_on_days: list[int] = field(default_factory=list)

    def held_within(self, day: int) -> int:
        """Rules held before simulation day ``day`` (the learner's day count)."""

        return sum(1 for held in self.held_on_days if held < day)

    @property
    def held_share(self) -> float:
        return len(self.items_to_held) / max(1, self.rules_judged)

    @property
    def median_items_to_held(self) -> float:
        """Median over judged rules; a never-held rule counts as infinite."""

        values = [float(v) for v in self.items_to_held] + [math.inf] * len(self.censored)
        if not values:
            return math.nan
        values.sort()
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2.0

    @property
    def median_days_to_held(self) -> float:
        values = sorted(self.days_to_held)
        if not values:
            return math.nan
        return float(values[len(values) // 2])


@dataclass
class _SimRule:
    index: int
    introduced: int | None = None
    state: MemoryState = field(default_factory=MemoryState)
    due: int | None = None
    rung: int = 0
    items: int = 0
    held_day: int | None = None
    held_items: int | None = None
    life: object = field(default_factory=new_unit_life)


def simulate_items_to_held(
    accuracy: float,
    *,
    engine: str = "forge",
    days: int = 150,
    units_per_week: float = 2.0,
    seance_seconds: int = 360,
    seconds_per_item: float = 25.0,
    rappel: bool = False,
    judge_margin_days: int = 45,
    seed: int = 20260924,
    ladder_concepts: int = 2,
    ladder_padding: bool = True,
) -> ItemsToHeld:
    """One learner, one séance a day, the journey introducing rules at a rhythm.

    * **journey** — rule *k* is introduced (the Règle: ``introduced_at``, no
      evidence) on day ``⌊k · 7 / units_per_week⌋``; with ``rappel`` every due
      rule also gets one journey Rappel item a day, in the WP-L4 format for
      its stability (counted in its items).
    * **forge** — :class:`app.core.forge.ForgeState`: today's rule (introduced
      today, else the weakest rule not yet forged to the top), up to three due
      rules and the previous rule as contrast partner; length from the budget
      over the pace; item-level evidence with the forge's caps.
    * **ladder** — today's séance: up to ``ladder_concepts`` concepts (due
      first, padded with the next never-studied rules, as ``select_today``
      does); per concept fill/classify/word bank ×3 with the adaptive lock
      (three clean recognise items retire the unused modes, two clean
      rewrites the third), sentence, speak, conversation; one evidence per
      concept at the end (``atelier_session_evidence``). With
      ``ladder_padding=False`` the ladder only takes rules the journey
      introduced (the same intake as the forge) — no padding with new rules.

    Held is WP-L4's «Tenue», kept by the app's own ``note_concept_evidence``.
    A rule is judged when it was introduced at least ``judge_margin_days``
    before the horizon.
    """

    import math

    from app.core import forge as forge_core
    from app.core.srs.memory import EvidenceGrade, grade_evidence

    rng = random.Random(f"s3:{seed}:{accuracy}:{engine}:{rappel}")  # noqa: S311
    rules: list[_SimRule] = []
    stats = {"answered": 0, "evidence": 0, "max_new": 0}

    def rule(index: int) -> _SimRule:
        while len(rules) <= index:
            rules.append(_SimRule(index=len(rules)))
        return rules[index]

    def introduce(item: _SimRule, day: int) -> None:
        if item.introduced is None:
            item.introduced = day
            item.life.introduced_at = SIMULATION_START + dt.timedelta(days=day)

    def apply(item: _SimRule, day: int, evidence: Evidence, *, schedule: bool, weight_scale: float = 1.0) -> None:
        if schedule:
            graded: Evidence | EvidenceGrade = evidence
            if weight_scale != 1.0:
                grade = grade_evidence(evidence)
                if grade is not None:
                    graded = EvidenceGrade(grade.rating, grade.weight * weight_scale, grade.step)
            decision = review(item.state, graded, now=SIMULATION_START + dt.timedelta(days=day))
            if decision is not None:
                item.state = MemoryState(decision.stability, decision.difficulty, decision.reps, decision.lapses)
                item.due = day + decision.interval_days
                item.life.reps = decision.reps
        note_unit_life(item.life, evidence, day=day)
        if item.held_day is None and getattr(item.life, "held_at", None) is not None:
            item.held_day = day
            item.held_items = item.items

    def is_due(item: _SimRule, day: int) -> bool:
        return item.introduced is not None and (item.due is None or item.due <= day)

    next_intro = 0
    for day in range(days):
        introduced_today: _SimRule | None = None
        quota = math.floor((day + 1) * units_per_week / 7.0 + 1e-9)
        while next_intro < quota:
            introduced_today = rule(next_intro)
            introduce(introduced_today, day)
            next_intro += 1

        if rappel:
            for item in list(rules):
                if item is introduced_today or not is_due(item, day) or item.state.reps == 0:
                    continue
                correct = rng.random() < accuracy
                item.items += 1
                apply(item, day, Evidence(rappel_format(item.state.stability), correct=correct), schedule=True)

        if engine == "forge":
            units: list[forge_core.ForgeUnit] = []
            live = [item for item in rules if item.introduced is not None and item.held_day is None]
            today = introduced_today
            if today is None:
                unforged = [item for item in live if item.rung < forge_core.TOP_RUNG]
                today = min(unforged, key=lambda item: (item.rung, item.index), default=None)
            if today is not None:
                units.append(
                    forge_core.ForgeUnit(
                        today.index, forge_core.Role.TODAY.value, today.rung, is_new=today.state.reps == 0
                    )
                )
            due = sorted(
                (item for item in rules if item is not today and is_due(item, day) and item.state.reps > 0),
                key=lambda item: (item.due or 0, item.index),
            )[:3]
            for item in due:
                needs_spaced = (
                    item.held_day is None
                    and item.introduced is not None
                    and day - item.introduced >= 14
                    and getattr(item.life, "spaced_success_at", None) is None
                )
                units.append(
                    forge_core.ForgeUnit(
                        item.index, forge_core.Role.DUE.value, max(0, item.rung - 1), needs_spaced=needs_spaced
                    )
                )
            if today is not None and today.index > 0:
                partner = rules[today.index - 1]
                if partner.introduced is not None and all(unit.concept_id != partner.index for unit in units):
                    units.append(
                        forge_core.ForgeUnit(
                            partner.index,
                            forge_core.Role.CONTRAST.value,
                            min(partner.rung, int(forge_core.Rung.DISCRIMINATE)),
                        )
                    )
            if not units:
                continue
            state = forge_core.ForgeState.seance(
                units, length=forge_core.seance_length(seance_seconds, seconds_per_item)
            )
            stats["max_new"] = max(
                stats["max_new"],
                sum(1 for unit in units if unit.is_new and state.track(unit.concept_id) is not None),
            )
            while (slot := state.next_slot()) is not None:
                item = rules[slot.concept_id]
                verdict = forge_core.Verdict.right() if rng.random() < accuracy else forge_core.Verdict.wrong()
                decision = state.record(concept_id=slot.concept_id, rung=slot.rung, verdict=verdict)
                item.items += 1
                stats["answered"] += 1
                if decision.evidence is not None:
                    stats["evidence"] += 1
                    apply(item, day, decision.evidence, schedule=decision.schedule, weight_scale=decision.weight_scale)
            for track in state.tracks:
                rules[track.concept_id].rung = track.rung
            continue

        # engine == "ladder": today's séance.
        from app.services.atelier import atelier_session_evidence

        picked = sorted(
            (item for item in rules if is_due(item, day)),
            key=lambda item: (item.due if item.due is not None else -1, item.index),
        )[:ladder_concepts]
        new_count = sum(1 for item in picked if item.state.reps == 0)
        while ladder_padding and len(picked) < ladder_concepts:
            fresh = rule(next_intro)
            next_intro += 1
            introduce(fresh, day)
            picked.append(fresh)
            new_count += 1
        stats["max_new"] = max(stats["max_new"], new_count)
        for item in picked:
            observations: list[tuple[str, str, float]] = []
            recognise_clean = 0
            recognise_dirty = False
            transform_clean = 0
            transform_dirty = False
            for round_name, mode, count in _LEGACY_LADDER:
                if round_name == "recognize" and recognise_clean >= 3 and not recognise_dirty:
                    continue  # the adaptive lock retired the unused modes
                for index in range(count):
                    if round_name == "transform" and index == 2 and transform_clean >= 2 and not transform_dirty:
                        break  # two clean rewrites retire the third
                    correct = rng.random() < accuracy
                    item.items += 1
                    stats["answered"] += 1
                    observations.append((round_name, mode, 4.0 if correct else 0.0))
                    if round_name == "recognize":
                        recognise_clean += 1 if correct else 0
                        recognise_dirty = recognise_dirty or not correct
                    if round_name == "transform":
                        transform_clean += 1 if correct else 0
                        transform_dirty = transform_dirty or not correct
            quality = sum(score for _r, _m, score in observations) / max(1, len(observations)) / 4 * 10
            evidence = atelier_session_evidence(observations, passed=quality >= 5.0)
            stats["evidence"] += 1
            apply(item, day, evidence, schedule=True)

    judged = [item for item in rules if item.introduced is not None and item.introduced <= days - judge_margin_days]
    held = [item for item in judged if item.held_day is not None]
    return ItemsToHeld(
        engine=engine,
        accuracy=accuracy,
        days=days,
        rappel=rappel,
        items_to_held=[int(item.held_items or 0) for item in held],
        censored=[item.items for item in judged if item.held_day is None],
        rules_judged=len(judged),
        max_new_rules_per_seance=stats["max_new"],
        items_answered=stats["answered"],
        evidence_written=stats["evidence"],
        days_to_held=[int(item.held_day - (item.introduced or 0)) for item in held],
        held_on_days=sorted(int(item.held_day) for item in rules if item.held_day is not None),
    )


__all__ = [
    "ItemsToHeld",
    "simulate_items_to_held",
    "BandDay",
    "BandSimulation",
    "new_unit_life",
    "note_unit_life",
    "simulate_band_coverage",
    "MAX_INTERVAL_DAYS",
    "SimulatedItem",
    "SimulationResult",
    "rappel_format",
    "simulate_learner",
]
