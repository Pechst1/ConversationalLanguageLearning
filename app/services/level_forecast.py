"""WP-L8 — an honest forecast: when will the current sub-band be covered?

Two paths, one formula (:func:`forecast_days`):

* **prior** — before :data:`MIN_ACTIVE_DAYS` (7) active days, the intake the
  learner's rhythm plans (§2.2: words a day, units a week) and a planning
  retention of :data:`PRIOR_RETENTION`. It is labelled an estimate and never
  shown as a promise.
* **measured** — after that: the learner's own intake over the last 14 days
  (words introduced a day, units introduced a week) scaled by their measured
  retention (the share of items introduced 7–60 days ago that stuck).

The formula::

    words_days = words_needed / (words_per_day · word_retention)
    units_days = to_introduce / units_per_day + hold_lag / unit_retention
                 (to_introduce = units required − units already introduced;
                  hold_lag = days a new unit takes to be held on a clean run;
                  a unit once held stays counted, so lapses stretch the lag)
    base       = max(words_days, units_days, checkpoint_floor) + 1 day (the épreuve)
    range      = [0.8 · base, 1.3 · base], capped at 730 days (two years)

``checkpoint_floor`` is the lower bound set by the épreuve: a failed épreuve
cannot be retaken before its week of consolidation is over.

Pure arithmetic, except :func:`measured_intake` and :func:`build_forecast`, which read.
"""
from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.grammar import UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.services.journey_rhythm import RHYTHMS, Rhythm, rhythm_of
from app.services.level_coverage import (
    SUB_BANDS,
    UNITS_HELD_SHARE,
    WORDS_KNOWN_SHARE,
    band_words,
    is_word_known,
)

#: §2.2 — what each rhythm plans to introduce: (new words a day, new units a week).
PRIOR_INTAKE: dict[Rhythm, tuple[float, float]] = {
    "leger": (2.0, 1.0),
    "regulier": (4.0, 2.0),
    "soutenu": (8.0, 3.0),
    "intensif": (12.0, 4.0),
}
#: The planning retention before anything is measured (§2.2 keeps review
#: accuracy ≥ 80 % with the throttle; 0.9 is the scheduler's own target).
PRIOR_RETENTION = 0.9
MIN_ACTIVE_DAYS = 7
INTAKE_WINDOW_DAYS = 14
RETENTION_MIN_AGE_DAYS = 7
RETENTION_MAX_AGE_DAYS = 60
RETENTION_MIN_SAMPLE = 10
RETENTION_FLOOR = 0.3
RANGE_LOW = 0.8
RANGE_HIGH = 1.3
CAP_DAYS = 730
#: The épreuve is an episode of its own: one more day once coverage is met.
CHECKPOINT_DAYS = 1


#: Monte-Carlo sizes: lag samples per accuracy, trials per forecast. Seeded.
HOLD_LAG_SAMPLES = 400
FORECAST_TRIALS = 200


def _held_after(accuracy: float, rng: random.Random) -> int:
    """Days from one unit's introduction until the held rule first counts it."""

    from app.core.srs.memory import Evidence, EvidenceFormat, MemoryState, review
    from app.core.srs.simulation import SIMULATION_START, rappel_format
    from app.services.level_coverage import HELD_FALLBACK_STABILITY_DAYS

    state = MemoryState()
    day = 0
    interval = 0
    lapsed = False
    for fmt in (EvidenceFormat.GUIDED, EvidenceFormat.PRODUCE):
        correct = rng.random() < accuracy
        decision = review(state, Evidence(fmt, correct=correct), now=SIMULATION_START)
        if decision is None:  # pragma: no cover - a graded observation always schedules
            raise RuntimeError("a graded observation must schedule")
        state = MemoryState(decision.stability, decision.difficulty, decision.reps, decision.lapses)
        interval, lapsed = decision.interval_days, decision.is_lapse
    while not (state.stability >= HELD_FALLBACK_STABILITY_DAYS and not lapsed) and day < 365:
        day += interval
        correct = rng.random() < accuracy
        decision = review(
            state,
            Evidence(rappel_format(state.stability), correct=correct),
            now=SIMULATION_START + dt.timedelta(days=day),
        )
        if decision is None:  # pragma: no cover - a graded observation always schedules
            raise RuntimeError("a graded observation must schedule")
        state = MemoryState(decision.stability, decision.difficulty, decision.reps, decision.lapses)
        interval, lapsed = decision.interval_days, decision.is_lapse
    return day


@lru_cache(maxsize=32)
def hold_lag_samples(accuracy_percent: int) -> tuple[int, ...]:
    """How long units take to be held at this accuracy (sorted, seeded sample).

    Replays the memory model: guided Essai + Emploi on the day of introduction,
    every Rappel on its due day in the format its stability calls for, each
    observation right with probability ``accuracy``; «held» is
    :func:`app.services.level_coverage.held_unit_ids`'s rule. When WP-L4's
    Tenue rule replaces that fallback, this sampler should follow it.
    """

    accuracy = max(RETENTION_FLOOR, min(1.0, accuracy_percent / 100.0))
    rng = random.Random(f"hold-lag:{accuracy_percent}")  # noqa: S311 - a seeded model
    return tuple(sorted(_held_after(accuracy, rng) for _ in range(HOLD_LAG_SAMPLES)))


def hold_lag_days(accuracy: float = 1.0) -> int:
    """Median days from a unit's introduction to «held» (41 on a clean run)."""

    samples = hold_lag_samples(_percent(accuracy))
    return samples[len(samples) // 2]


def _percent(value: float) -> int:
    """Accuracy bucketed to 5 points, so the lag samples stay cached."""

    return int(round(max(RETENTION_FLOOR, min(1.0, value)) * 20)) * 5


@dataclass(frozen=True)
class ForecastInputs:
    words_needed: int
    words_per_day: float
    #: Share of introduced words that stay known.
    word_retention: float
    units_required: int
    units_held: int
    units_total: int
    #: Band units already introduced (held or on their way).
    units_introduced: int
    units_per_week: float
    #: The learner's accuracy on unit reviews: picks the hold-lag distribution.
    unit_retention: float
    #: Days before the épreuve can be (re)taken (a failed one waits a week).
    checkpoint_floor_days: float = 0.0
    #: Days since introduction of each band unit introduced but not yet held.
    pending_elapsed_days: tuple[float, ...] = ()


def forecast_days(inputs: ForecastInputs) -> tuple[float, bool]:
    """``(base_days, capped)`` until the band is covered and its épreuve taken.

    Capped at two years, and capped when there is no intake at all.
    """

    word_retention = max(RETENTION_FLOOR, min(1.0, inputs.word_retention))
    days = max(0.0, float(inputs.checkpoint_floor_days))
    if inputs.words_needed > 0:
        if inputs.words_per_day <= 0:
            return float(CAP_DAYS), True
        days = max(days, inputs.words_needed / (inputs.words_per_day * word_retention))
    units_days = _units_days(inputs)
    if units_days is None:
        return float(CAP_DAYS), True
    days = max(days, units_days)
    days += CHECKPOINT_DAYS
    if days >= CAP_DAYS:
        return float(CAP_DAYS), True
    return days, False


def _units_days(inputs: ForecastInputs) -> float | None:
    """Days until the band's required units are held; ``None`` if never at this intake.

    Once held, a unit stays counted (WP-L7), so the band is covered when the
    ``needed``-th of the units in flight is first held. Units already introduced
    have already spent part of their lag (``pending_elapsed_days``); the rest
    arrive at the measured intake. Each unit's lag is drawn from :func:`hold_lag_samples` at the
    learner's unit retention, and the answer is the median over seeded trials —
    the time the *slowest needed* unit takes matters, not the average one.
    """

    needed = inputs.units_required - inputs.units_held
    if needed <= 0:
        return 0.0
    pending = max(0, inputs.units_introduced - inputs.units_held)
    remaining = (
        max(0, inputs.units_total - inputs.units_introduced) if inputs.units_total else needed
    )
    per_day = inputs.units_per_week / 7.0
    if per_day <= 0:
        remaining = 0
    if pending + remaining < needed:
        return None
    samples = hold_lag_samples(_percent(inputs.unit_retention))
    rng = random.Random(  # noqa: S311 - a seeded model, not security
        f"forecast:{needed}:{pending}:{remaining}:{per_day:.3f}:{len(samples)}"
    )
    results: list[float] = []
    elapsed = list(inputs.pending_elapsed_days)[:pending]
    elapsed += [0.0] * (pending - len(elapsed))
    tails = [[lag - spent for lag in samples if lag > spent] or [1.0] for spent in elapsed]
    for _ in range(FORECAST_TRIALS):
        done = [rng.choice(tail) for tail in tails]
        done += [(k + 1) / per_day + rng.choice(samples) for k in range(remaining)]
        done.sort()
        results.append(done[needed - 1])
    results.sort()
    return results[len(results) // 2]


def forecast_range(base_days: float, *, capped: bool) -> tuple[int, int]:
    if capped:
        return CAP_DAYS, CAP_DAYS
    low = max(1, int(round(base_days * RANGE_LOW)))
    high = min(CAP_DAYS, max(low, int(round(base_days * RANGE_HIGH))))
    return low, high


def _months(days: int) -> float:
    return round(days / 30.4, 1)


def forecast_payload(
    inputs: ForecastInputs,
    *,
    status: str,
    band: str,
    target: str | None,
    now: datetime,
    rhythm: str,
    basis: dict[str, Any],
) -> dict[str, Any]:
    base, capped = forecast_days(inputs)
    low, high = forecast_range(base, capped=capped)
    return {
        # "prior": planned intake, not measured; "available": measured.
        "status": status,
        "kind": "estimate",
        "band": band,
        "target": target,
        "rhythm": rhythm,
        "base_days": int(round(base)),
        "range_days": [low, high],
        "range_months": [_months(low), _months(high)],
        "projected_dates": [
            (now + timedelta(days=low)).date().isoformat(),
            (now + timedelta(days=high)).date().isoformat(),
        ],
        "capped": capped,
        "basis": {
            **basis,
            "words_needed": inputs.words_needed,
            "units_needed": max(0, inputs.units_required - inputs.units_held),
            "units_introduced": inputs.units_introduced,
            "words_per_day": round(inputs.words_per_day, 2),
            "units_per_week": round(inputs.units_per_week, 2),
            "word_retention": round(inputs.word_retention, 3),
            "unit_retention": round(inputs.unit_retention, 3),
            "hold_lag_days": hold_lag_days(inputs.unit_retention),
            "checkpoint_floor_days": round(inputs.checkpoint_floor_days, 1),
        },
    }


# ---------------------------------------------------------------------------
# The prior per rhythm (Réglages' cards)
# ---------------------------------------------------------------------------


def static_band_unit_count(band: str) -> int:
    """Units in a band, from the active catalogue file (no DB): the card's prior."""

    import math as _math

    from app.services.grammar_catalog import (
        FRENCH_CORE_CATALOG_V2_VERSION,
        active_catalog_version,
        catalog_rows,
    )

    version = active_catalog_version()
    rows = catalog_rows(version)
    if version == FRENCH_CORE_CATALOG_V2_VERSION:
        return sum(1 for row in rows if ((row.get("source_refs") or {}).get("syllabus") or {}).get("sub_band") == band)
    level = band[:2]
    in_level = sum(1 for row in rows if str(row.get("level") or "").upper()[:2] == level)
    half = _math.ceil(in_level / 2)
    return half if band.endswith(".1") else in_level - half


def rhythm_prior(rhythm: Rhythm, *, bands: tuple[str, ...] = ("A1.1", "A1.2"), now: datetime | None = None) -> dict[str, Any]:
    """From zero to the end of ``bands`` (default: A1) at a rhythm's planned intake."""

    words_per_day, units_per_week = PRIOR_INTAKE[rhythm]
    units_total = sum(static_band_unit_count(band) for band in bands)
    units_required = sum(math.ceil(static_band_unit_count(band) * UNITS_HELD_SHARE) for band in bands)
    words = sum(math.ceil(len(band_words(band)) * WORDS_KNOWN_SHARE) for band in bands)
    inputs = ForecastInputs(
        words_needed=words,
        words_per_day=words_per_day,
        word_retention=PRIOR_RETENTION,
        units_required=units_required,
        units_held=0,
        units_total=units_total,
        units_introduced=0,
        units_per_week=units_per_week,
        unit_retention=PRIOR_RETENTION,
    )
    base, capped = forecast_days(inputs)
    # One épreuve per band; the last one is already in forecast_days.
    base += CHECKPOINT_DAYS * (len(bands) - 1)
    low, high = forecast_range(base, capped=capped)
    same_level = len({band[:2] for band in bands}) == 1 and len(bands) > 1
    return {
        "rhythm": rhythm,
        "target": bands[-1][:2] if same_level else bands[-1],
        "status": "prior",
        "kind": "estimate",
        "range_days": [low, high],
        "range_months": [_months(low), _months(high)],
        "words_per_day": words_per_day,
        "units_per_week": units_per_week,
    }


def rhythm_priors(*, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    return {rhythm: rhythm_prior(rhythm, now=now) for rhythm in RHYTHMS}


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class MeasuredIntake:
    words_per_day: float
    units_per_week: float
    word_retention: float
    unit_retention: float
    word_sample: int
    unit_sample: int


#: A handful of units is a thin sample (two a week at Régulier): their
#: retention is shrunk toward the words' by this many pseudo-observations.
UNIT_RETENTION_PRIOR_WEIGHT = 5


def shrunk_retention(kept: int, sample: int, *, prior: float) -> float:
    weight = UNIT_RETENTION_PRIOR_WEIGHT
    return (kept + prior * weight) / (sample + weight)


def measured_intake(db: Session, user: Any, *, now: datetime) -> MeasuredIntake:
    """Intake over the last 14 days and retention of what was introduced 7–60 days ago.

    * words: the share of cards introduced 7–60 days ago that are known today;
    * units: the share of units introduced 7–60 days ago whose last review was
      not a lapse, shrunk toward the words' retention while the sample is small.
    """

    start = now - timedelta(days=INTAKE_WINDOW_DAYS)
    words = db.query(UserVocabularyProgress).filter(UserVocabularyProgress.user_id == user.id).all()
    units = db.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id).all()
    words_recent = sum(1 for row in words if row.created_at is not None and _aware(row.created_at) >= start)
    units_recent = sum(1 for row in units if row.created_at is not None and _aware(row.created_at) >= start)

    old_lo = now - timedelta(days=RETENTION_MAX_AGE_DAYS)
    old_hi = now - timedelta(days=RETENTION_MIN_AGE_DAYS)
    word_kept = word_sample = 0
    for row in words:
        created = _aware(row.created_at)
        if created is None or not (old_lo <= created <= old_hi):
            continue
        word_sample += 1
        word_kept += 1 if is_word_known(row, now=now) else 0
    unit_kept = unit_sample = 0
    for row in units:
        created = _aware(row.created_at)
        if created is None or not (old_lo <= created <= old_hi):
            continue
        unit_sample += 1
        last, nxt = _aware(row.last_review), _aware(row.next_review)
        lapsed = last is not None and nxt is not None and (nxt - last).total_seconds() <= 1.5 * 86_400
        unit_kept += 0 if lapsed else 1
    word_retention = word_kept / word_sample if word_sample >= RETENTION_MIN_SAMPLE else PRIOR_RETENTION
    unit_retention = shrunk_retention(unit_kept, unit_sample, prior=word_retention)
    return MeasuredIntake(
        words_per_day=words_recent / INTAKE_WINDOW_DAYS,
        units_per_week=units_recent / (INTAKE_WINDOW_DAYS / 7.0),
        word_retention=max(RETENTION_FLOOR, min(1.0, word_retention)),
        unit_retention=max(RETENTION_FLOOR, min(1.0, unit_retention)),
        word_sample=word_sample,
        unit_sample=unit_sample,
    )


def build_forecast(
    db: Session,
    user: Any,
    *,
    coverage: Any,
    checkpoint: dict[str, Any],
    active_days: int,
    target: str | None,
    now: datetime,
) -> dict[str, Any] | None:
    """The forecast for the learner's current band (``coverage`` is a BandCoverage)."""

    if coverage is None or coverage.band not in SUB_BANDS:
        return None
    rhythm = rhythm_of(user)
    state = str(checkpoint.get("state") or "")
    if state in {"passed", "credited"}:
        return None
    floor = 0.0
    if state == "failed" and checkpoint.get("retry_after"):
        try:
            retry = datetime.fromisoformat(str(checkpoint["retry_after"]))
            floor = max(0.0, (_aware(retry) - now).total_seconds() / 86_400)
        except ValueError:  # pragma: no cover - defensive
            floor = 7.0
    band_units = set(coverage.unit_ids)
    introduced = {
        int(row[0])
        for row in db.query(UserGrammarProgress.concept_id).filter(UserGrammarProgress.user_id == user.id).all()
    }
    common: dict[str, Any] = {
        "words_needed": max(0, coverage.words_required - coverage.words_known),
        "units_required": coverage.units_required,
        "units_held": coverage.units_held,
        "units_total": coverage.units_total,
        "units_introduced": len(introduced & band_units),
        "checkpoint_floor_days": floor,
    }
    if active_days < MIN_ACTIVE_DAYS:
        words_per_day, units_per_week = PRIOR_INTAKE[rhythm]
        inputs = ForecastInputs(
            **common,
            words_per_day=words_per_day,
            word_retention=PRIOR_RETENTION,
            units_per_week=units_per_week,
            unit_retention=PRIOR_RETENTION,
        )
        return forecast_payload(
            inputs,
            status="prior",
            band=coverage.band,
            target=target,
            now=now,
            rhythm=rhythm,
            basis={"source": "rhythm_prior", "active_days": active_days, "active_days_required": MIN_ACTIVE_DAYS},
        )
    measured = measured_intake(db, user, now=now)
    inputs = ForecastInputs(
        **common,
        words_per_day=measured.words_per_day,
        word_retention=measured.word_retention,
        units_per_week=measured.units_per_week,
        unit_retention=measured.unit_retention,
    )
    return forecast_payload(
        inputs,
        status="available",
        band=coverage.band,
        target=target,
        now=now,
        rhythm=rhythm,
        basis={
            "source": "measured",
            "active_days": active_days,
            "window_days": INTAKE_WINDOW_DAYS,
            "word_sample": measured.word_sample,
            "unit_sample": measured.unit_sample,
        },
    )


__all__ = [
    "CAP_DAYS",
    "MIN_ACTIVE_DAYS",
    "PRIOR_INTAKE",
    "PRIOR_RETENTION",
    "ForecastInputs",
    "MeasuredIntake",
    "build_forecast",
    "forecast_days",
    "forecast_range",
    "hold_lag_days",
    "hold_lag_samples",
    "measured_intake",
    "shrunk_retention",
    "rhythm_prior",
    "rhythm_priors",
    "static_band_unit_count",
]
