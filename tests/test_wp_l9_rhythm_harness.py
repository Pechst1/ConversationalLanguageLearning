"""WP-L9 — the 126-day harness, per rhythm (a sibling of the WP-68 harness).

``tests/test_long_horizon_evidence.py`` plays two learners through the whole
assembled system; this file asks the *curriculum* question it cannot afford to
ask twelve times: per rhythm (Léger / Régulier / Soutenu / Intensif) and per
simulated accuracy (70 / 85 / 95 %), what a day costs and what it buys.

* the séance's minutes and graded interactions come from the **real planner**
  at the rhythm's budget and the prior pace;
* intake, reviews, the auto-throttle, «Tenue» and the band walk come from
  :mod:`app.core.srs.rhythm_horizon` (the app's own memory model, throttle rule
  and concept-life bookkeeping).

Run ``pytest tests/test_wp_l9_rhythm_harness.py -s`` to print the table the
learning WP doc carries (WP-L9 Status).
"""
from __future__ import annotations

from functools import lru_cache

import pytest

from app.core.srs.rhythm_horizon import (
    ACCURACIES,
    CHECKPOINTS,
    RHYTHM_BUDGET,
    RhythmHorizon,
    render_table,
    simulate_rhythm_horizon,
)
from app.services import journey_planner as planner
from app.services.grammar_catalog import (
    FRENCH_CORE_CATALOG_V2_VERSION,
    FRENCH_CORE_CATALOG_VERSION,
    catalog_rows,
)
from app.services.journey_contracts import rhythm_caps
from app.services.level_coverage import SUB_BANDS, band_words
from tests.test_wpl6_rhythm import _plan

RHYTHMS = ("leger", "regulier", "soutenu", "intensif")
CATALOGUES = ("v1", "v2")


def _units(band: str, catalogue: str) -> int:
    """Units in a band, as WP-L7 counts them (v1: the level halved; v2: the tag)."""

    if catalogue == "v2":
        return sum(
            1
            for row in catalog_rows(FRENCH_CORE_CATALOG_V2_VERSION)
            if ((row.get("source_refs") or {}).get("syllabus") or {}).get("sub_band") == band
        )
    in_level = sum(
        1
        for row in catalog_rows(FRENCH_CORE_CATALOG_VERSION)
        if str(row.get("level") or "").upper()[:2] == band[:2]
    )
    half = -(-in_level // 2)
    return half if band.endswith(".1") else in_level - half


@lru_cache(maxsize=2)
def _bands(catalogue: str = "v1") -> tuple[tuple[str, int, int], ...]:
    return tuple((band, _units(band, catalogue), len(band_words(band))) for band in SUB_BANDS)


@lru_cache(maxsize=4)
def _seance(rhythm: str) -> tuple[int, int]:
    budget = RHYTHM_BUDGET[rhythm]
    plan = _plan(budget, pool=rhythm_caps(budget).candidate_limit)
    plan.validate()
    return plan.estimated_active_seconds, planner.graded_interactions(plan)


@lru_cache(maxsize=32)
def _run(rhythm: str, accuracy: float, catalogue: str = "v1") -> RhythmHorizon:
    seconds, graded = _seance(rhythm)
    return simulate_rhythm_horizon(
        rhythm,
        accuracy,
        bands=list(_bands(catalogue)),
        seance_seconds=seconds,
        seance_graded=graded,
    )


def _all(catalogue: str = "v1") -> list[RhythmHorizon]:
    return [_run(rhythm, accuracy, catalogue) for rhythm in RHYTHMS for accuracy in ACCURACIES]


def _progress(run: RhythmHorizon, day: int = 126) -> float:
    """Bands closed plus the current band's percent: one comparable number."""

    entry = run.days[day - 1]
    return SUB_BANDS.index(entry.band) + entry.percent / 100


@pytest.mark.parametrize("catalogue", CATALOGUES)
def test_the_report_covers_every_rhythm_and_accuracy(catalogue: str) -> None:
    results = _all(catalogue)
    table = render_table(results)
    print(f"\ncatalogue {catalogue}: bands {_bands(catalogue)}\n" + table)  # noqa: T201 - the report
    assert {r.rhythm for r in results} == set(RHYTHMS)
    assert {r.accuracy for r in results} == set(ACCURACIES)
    for result in results:
        assert len(result.days) == 126
        for day in CHECKPOINTS:
            assert result.level_at(day)


@pytest.mark.parametrize("rhythm", RHYTHMS)
def test_the_seance_fits_its_rhythm(rhythm: str) -> None:
    seconds, graded = _seance(rhythm)
    assert seconds <= RHYTHM_BUDGET[rhythm]
    assert graded >= 3


def test_more_minutes_buy_more_intake_and_more_level() -> None:
    for accuracy in ACCURACIES:
        runs = [_run(rhythm, accuracy) for rhythm in RHYTHMS]
        intake = [run.new_items_per_day for run in runs]
        assert intake == sorted(intake), (accuracy, intake)
        minutes = [run.minutes_per_day for run in runs]
        assert minutes == sorted(minutes), (accuracy, minutes)
    # The level, on the syllabus draft (v2: 16–23 units a band, so one stuck
    # unit does not decide the band): more minutes, further by day 126.
    for accuracy in (0.85, 0.95):
        progress = [_progress(_run(rhythm, accuracy, "v2")) for rhythm in RHYTHMS]
        assert progress == sorted(progress), (accuracy, progress)
    # On v1 (six units a half-level, all six must be held) the order is noisy
    # at 85 %; Intensif still ends ahead of Léger.
    assert _progress(_run("intensif", 0.85)) > _progress(_run("leger", 0.85))


def test_the_throttle_answers_accuracy() -> None:
    for rhythm in RHYTHMS:
        low, mid, high = (_run(rhythm, accuracy) for accuracy in ACCURACIES)
        # 70 % is under the 80 % line: intake halves for most of the run.
        assert low.throttled_share > 0.5, (rhythm, low.throttled_share)
        assert high.throttled_share <= mid.throttled_share <= low.throttled_share
        assert low.new_words_per_day < high.new_words_per_day


def test_review_load_grows_with_intake_and_errors() -> None:
    for accuracy in ACCURACIES:
        loads = [_run(rhythm, accuracy).reviews_per_day(90, 126) for rhythm in RHYTHMS]
        assert loads == sorted(loads), (accuracy, loads)
