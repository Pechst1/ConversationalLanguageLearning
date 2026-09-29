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

WP-93 «Plus d'histoire, moins d'exercices»: the séance is planned on a real
page (a five-panel story-engine scene, :mod:`tests.wp93_briefs`), priced by what
is on it, with the «Lecture» offered from Soutenu up, and the report adds the
new mix per rhythm — input share, recall count, reuse rate — with audio off
and on.
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
from app.services.lexical_coverage import tokenize
from tests.test_wpl6_rhythm import _plan
from tests.wp93_briefs import engine_brief, engine_draft

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


#: Yesterday's page, offered as the «relecture» from Soutenu up (WP-93).
YESTERDAY = engine_draft()


def _reading(audio: bool) -> dict:
    texts = planner.page_texts(YESTERDAY["panels"])
    return {
        "variant": "relecture",
        "title_fr": YESTERDAY["title_fr"],
        "scene_id": "00000000-0000-4000-8000-00000000c1e0",
        "status": "ready",
        "audio_available": audio,
        "texts_fr": texts,
        "panel_count": len(YESTERDAY["panels"]),
    }


@lru_cache(maxsize=16)
def _day(rhythm: str, audio: bool = False):
    budget = RHYTHM_BUDGET[rhythm]
    plan = _plan(
        budget,
        pool=rhythm_caps(budget).candidate_limit,
        scenario=engine_brief(),
        audio_available=audio,
        reading=_reading(audio),
    )
    plan.validate()
    return plan


@lru_cache(maxsize=4)
def _seance(rhythm: str) -> tuple[int, int]:
    plan = _day(rhythm)
    return plan.estimated_active_seconds, planner.graded_interactions(plan)


def _lemma_keys(text: str) -> list[str]:
    return [token.key for token in tokenize(text)]


def _mix(rhythm: str, audio: bool) -> dict:
    plan = _day(rhythm, audio)
    asked, found = planner.scene_reuse(plan.scenario, lemma_keys=_lemma_keys)
    return {
        "minutes": round(plan.estimated_active_seconds / 60, 1),
        "input_of_budget": planner.input_share(plan),
        "input_of_day": round(
            planner.input_seconds(plan) / max(1, plan.estimated_active_seconds), 4
        ),
        "recall": planner.recall_count(plan),
        "reuse": round(found / asked, 2) if asked else None,
        "lecture": any(step.kind.value == "read" for step in plan.steps),
    }


def render_mix() -> str:
    rows = ["rhythm    audio  min   input/budget  input/day  recall  reuse  lecture"]
    for rhythm in RHYTHMS:
        for audio in (False, True):
            mix = _mix(rhythm, audio)
            rows.append(
                f"{rhythm:<9} {'on ' if audio else 'off'}   {mix['minutes']:>4}  "
                f"{mix['input_of_budget']:>12.0%}  {mix['input_of_day']:>9.0%}  "
                f"{mix['recall']:>6}  {mix['reuse']!s:>5}  {'yes' if mix['lecture'] else 'no'}"
            )
    return "\n".join(rows)


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


# ---------------------------------------------------------------------------
# WP-93 — the new mix, per rhythm
# ---------------------------------------------------------------------------

#: WP-93's recall ceilings (about 6 · 12 · 20 · 28).
RECALL_CAPS = {"leger": 6, "regulier": 12, "soutenu": 20, "intensif": 28}


def test_the_report_prints_the_new_mix_per_rhythm() -> None:
    print("\nWP-93 mix (engine page, prior pace)\n" + render_mix())  # noqa: T201 - the report
    for rhythm in RHYTHMS:
        for audio in (False, True):
            mix = _mix(rhythm, audio)
            assert mix["recall"] <= RECALL_CAPS[rhythm], (rhythm, audio, mix)
            assert mix["reuse"] is not None and mix["reuse"] >= 0.5, (rhythm, mix)
            # The «Lecture» is bought from Soutenu up, never on shorter days.
            assert mix["lecture"] is (RHYTHM_BUDGET[rhythm] >= 1200), (rhythm, mix)
    # Régulier's p50 still fits 8–10 minutes, and with the deployment
    # speaking its input clears the 35 % floor (D-5).
    for audio in (False, True):
        assert 8 <= _mix("regulier", audio)["minutes"] <= 10, audio
    assert _mix("regulier", True)["input_of_budget"] >= 0.35
    # Every rhythm's input is at least a third of the day it plans.
    for rhythm in RHYTHMS:
        assert _mix(rhythm, True)["input_of_day"] >= 0.33, rhythm


def test_drills_never_take_the_input_floor() -> None:
    """Non-input time never exceeds 65 % of the budget on a paged day."""

    for rhythm in RHYTHMS:
        for audio in (False, True):
            plan = _day(rhythm, audio)
            other = plan.estimated_active_seconds - planner.input_seconds(plan)
            assert other <= round(0.65 * plan.budget_seconds), (rhythm, audio, other)
