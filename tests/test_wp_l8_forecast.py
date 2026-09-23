"""WP-L8 — an honest forecast.

Pins:
1. before 7 active days the forecast is the rhythm's prior, labelled an estimate;
2. after, it is measured intake ÷ what is left, scaled by retention, as a
   0.8×–1.3× range, capped at two years;
3. the rhythm cards' priors (Réglages) are ordered and plausible;
4. the simulation: a Régulier learner at 85 % covers A1.1 (and so reaches A1.2)
   within ±20 % of what the measured forecast said on day 14.
"""
from __future__ import annotations

import statistics
import uuid
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

from app.core.srs.simulation import simulate_band_coverage
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import level_forecast as forecast
from app.services.cefr_progress import CEFRProgressService
from app.services.level_coverage import band_words

NOW = datetime.now(UTC)


def _user(db_session, *, minutes: int = 10) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wpl8-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
        cefr_estimate="A1.1",
        cefr_estimate_payload={},
        daily_goal_minutes=minutes,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _active_days(db_session, user: User, days: int) -> None:
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="completed")
    db_session.add(session)
    db_session.flush()
    for day in range(days):
        db_session.add(
            AtelierAttempt(
                atelier_session_id=session.id,
                user_id=user.id,
                concept_id=None,
                round="recognize",
                mode="fill",
                exercise_id=f"wpl8-{uuid.uuid4().hex[:6]}",
                verdict="correct",
                score_0_4=3.0,
                created_at=NOW - timedelta(days=day, hours=1),
            )
        )
    db_session.commit()


# ---------------------------------------------------------------------------
# 1–2. Prior and measured paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("minutes,rhythm", [(5, "leger"), (10, "regulier"), (20, "soutenu"), (30, "intensif")])
def test_before_seven_active_days_the_forecast_is_the_rhythms_prior(db_session, minutes, rhythm):
    user = _user(db_session, minutes=minutes)
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    fc = payload["forecast"]
    assert fc["status"] == "prior"
    assert fc["kind"] == "estimate"
    assert fc["rhythm"] == rhythm
    assert fc["target"] == "A1.2"
    words_per_day, units_per_week = forecast.PRIOR_INTAKE[rhythm]
    assert fc["basis"]["words_per_day"] == words_per_day
    assert fc["basis"]["units_per_week"] == units_per_week
    low, high = fc["range_days"]
    assert low < high and high == pytest.approx(low * 1.3 / 0.8, rel=0.05)


def test_prior_ranges_shrink_as_the_rhythm_grows(db_session):
    ranges = {
        rhythm: forecast.rhythm_prior(rhythm)["range_days"] for rhythm in ("leger", "regulier", "soutenu", "intensif")
    }
    assert ranges["leger"][0] > ranges["regulier"][0] > ranges["soutenu"][0] >= ranges["intensif"][0]
    # §2.3: Régulier ≈ 5–6 months for A1, Léger ≈ 10 — the ranges straddle them.
    regulier = forecast.rhythm_prior("regulier")
    assert 3.0 <= regulier["range_months"][0] <= 6.0 <= regulier["range_months"][1] + 1.0
    leger = forecast.rhythm_prior("leger")
    assert leger["range_months"][0] <= 10.0 <= leger["range_months"][1]
    assert regulier["target"] == "A1" and regulier["kind"] == "estimate"


def test_after_seven_active_days_the_forecast_is_measured(db_session, monkeypatch):
    # Words only: other suites leave grammar concepts behind, and a band with
    # units and no unit intake would (rightly) be the two-year cap.
    monkeypatch.setattr("app.services.level_coverage.band_unit_ids", lambda db, band: [])
    user = _user(db_session)
    _active_days(db_session, user, 8)
    for index in range(28):  # two new words a day over the last 14 days
        made_up = f"zorblax{chr(97 + index % 26)}{chr(97 + index // 26)}"  # never a lexicon lemma
        word = VocabularyWord(language="fr", word=made_up, normalized_word=made_up, difficulty_level=1)
        db_session.add(word)
        db_session.flush()
        db_session.add(
            UserVocabularyProgress(
                user_id=user.id,
                word_id=word.id,
                stability=3.0,
                reps=2,
                state="reviewing",
                last_review_date=NOW - timedelta(days=1),
                created_at=NOW - timedelta(days=index % 14, hours=2),
            )
        )
    db_session.commit()
    fc = CEFRProgressService(db_session).recompute(user, source="test")["forecast"]
    assert fc["status"] == "available"
    assert fc["basis"]["source"] == "measured"
    assert fc["basis"]["words_per_day"] == pytest.approx(2.0)
    # The 14 cards introduced 7–60 days ago all stuck.
    assert fc["basis"]["word_sample"] == 14
    assert fc["basis"]["word_retention"] == pytest.approx(1.0)
    # None of these cards is a band word: 253 of A1.1's words are still
    # needed, at two a day.
    words_needed = fc["basis"]["words_needed"]
    assert words_needed == 253
    assert fc["base_days"] == round(words_needed / 2.0 + forecast.CHECKPOINT_DAYS)
    assert fc["capped"] is False


def test_no_intake_at_all_is_the_two_year_cap():
    stalled = forecast.ForecastInputs(100, 0.0, 0.9, 10, 0, 12, 2, 0.0, 0.9)
    assert forecast.forecast_days(stalled) == (float(forecast.CAP_DAYS), True)
    assert forecast.forecast_range(forecast.CAP_DAYS, capped=True) == (forecast.CAP_DAYS, forecast.CAP_DAYS)


def test_the_measured_formula():
    inputs = forecast.ForecastInputs(
        words_needed=200,
        words_per_day=4.0,
        word_retention=0.8,
        units_required=0,
        units_held=0,
        units_total=0,
        units_introduced=0,
        units_per_week=0.0,
        unit_retention=0.8,
    )
    base, capped = forecast.forecast_days(inputs)
    assert not capped
    assert base == pytest.approx(200 / (4 * 0.8) + forecast.CHECKPOINT_DAYS)
    assert forecast.forecast_range(base, capped=False) == (round(base * 0.8), round(base * 1.3))
    # The épreuve bounds it below: a failed one waits its week.
    floor = forecast.forecast_days(
        forecast.ForecastInputs(0, 4.0, 0.8, 0, 0, 0, 0, 0.0, 0.8, checkpoint_floor_days=6.0)
    )[0]
    assert floor == pytest.approx(7.0)
    # Two years at most.
    slow = forecast.ForecastInputs(5000, 1.0, 0.5, 0, 0, 0, 0, 0.0, 0.5)
    assert forecast.forecast_days(slow) == (float(forecast.CAP_DAYS), True)


def test_units_need_their_hold_lag_even_when_all_are_introduced():
    inputs = forecast.ForecastInputs(
        words_needed=0,
        words_per_day=4.0,
        word_retention=0.9,
        units_required=16,
        units_held=0,
        units_total=18,
        units_introduced=18,
        units_per_week=2.0,
        unit_retention=1.0,
        pending_elapsed_days=tuple(range(0, 36, 2)),
    )
    base, _ = forecast.forecast_days(inputs)
    assert forecast.hold_lag_days() == 41
    # The 16th-fastest of 18 units introduced 0–34 days ago, each needing 41 days.
    assert 30 <= base <= 42


# ---------------------------------------------------------------------------
# 4. The simulation
# ---------------------------------------------------------------------------


def _forecast_on(sim, day: int) -> float:
    """What the measured forecast says on ``day``, from the simulated learner's own numbers."""

    state = sim.days[day]
    start = sim.days[day - 14] if day >= 14 else None
    observations = state.observations - (start.observations if start else 0)
    correct = state.correct - (start.correct if start else 0)
    accuracy = correct / observations
    inputs = forecast.ForecastInputs(
        words_needed=max(0, sim.words_required - state.words_known),
        words_per_day=(state.words_introduced - (start.words_introduced if start else 0)) / 14,
        word_retention=accuracy,
        units_required=sim.units_required,
        units_held=state.units_held,
        units_total=sim.units_total,
        units_introduced=state.units_introduced,
        units_per_week=(state.units_introduced - (start.units_introduced if start else 0)) / 2,
        unit_retention=accuracy,
        pending_elapsed_days=state.pending_elapsed,
    )
    base, capped = forecast.forecast_days(inputs)
    assert not capped
    return day + base


def test_a_regulier_learner_at_85_percent_reaches_a12_as_the_forecast_said():
    words_per_day, units_per_week = forecast.PRIOR_INTAKE["regulier"]
    words = len(band_words("A1.1"))
    with mock.patch(
        "app.services.grammar_catalog.active_catalog_version", return_value="fr-core-v2"
    ):
        units = forecast.static_band_unit_count("A1.1")
    assert units == 18
    actual: list[int] = []
    predicted: list[float] = []
    for seed in range(7):
        sim = simulate_band_coverage(
            accuracy=0.85,
            units_per_week=units_per_week,
            words_per_day=words_per_day,
            units_total=units,
            words_total=words,
            seed=seed,
            horizon_days=400,
        )
        assert sim.coverage_day is not None
        actual.append(sim.coverage_day + forecast.CHECKPOINT_DAYS)
        predicted.append(_forecast_on(sim, 13))
    actual_median = statistics.median(actual)
    predicted_median = statistics.median(predicted)
    assert abs(predicted_median - actual_median) <= 0.2 * actual_median, (actual, predicted)
    # Plausible: about three to five months for the first sub-band at ten minutes a day.
    assert 90 <= actual_median <= 150
    # And the measured range brackets what happened for most learners.
    inside = sum(1 for got, said in zip(actual, predicted, strict=True) if 0.8 * said <= got <= 1.3 * said)
    assert inside >= 5
