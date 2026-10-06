"""WP-123b — the 365-day drill workload simulation keeps its own rules.

``scripts/simulate_workload_365.py`` reports the year's due pile and review minutes;
these invariants are what make its numbers readable: it is deterministic, credits
exactly the walk's sub-bands, never brings a credited word back before its light
check window opens, honours the session cap and the struggling learner's cadence.
"""
from __future__ import annotations

import pytest

from app.services import band_check
from scripts import simulate_workload_365 as sim


def test_the_year_is_deterministic_and_has_twelve_months():
    first = sim.simulate_life("B1", "average")
    again = sim.simulate_life("B1", "average")
    assert [d.due for d in first.days] == [d.due for d in again.days]
    assert len(first.days) == sim.DAYS
    months = sim.month_summary(first)
    assert [m["month"] for m in months] == list(range(1, 13))
    assert all(m["due_median"] <= m["due_p90"] <= m["due_max"] for m in months)


def test_the_credit_is_the_walks_sub_bands_and_nothing_below_a2():
    assert sim.credit_plan("A1", "strong") == []
    plan = sim.credit_plan("B2", "strong")
    # B1.2 passed: B1.2 and everything below it, nearest first.
    assert [distance for _count, distance in plan] == [1, 2, 3, 4, 5, 6]
    assert sum(count for count, _ in plan) == sum(len(band_check._pool(s)) for s in band_check.SUB_BANDS[:6])
    assert sim.simulate_life("B2", "strong", days=1).credited_cards == sum(count for count, _ in plan)


def test_no_credited_word_comes_back_before_its_light_check_window():
    first_window_day = min(window[0] for window in band_check.VERIFY_WINDOWS.values())
    life = sim.simulate_life("C1", "average", days=first_window_day + 10)
    assert all(day.due_credited == 0 for day in life.days[:first_window_day])
    assert any(day.due_credited > 0 for day in life.days[first_window_day:])


def test_without_the_credit_no_credited_word_is_ever_due():
    life = sim.simulate_life("C1", "strong", credit=False, days=120)
    assert life.credited_cards == 0
    assert all(day.due_credited == 0 for day in life.days)


@pytest.mark.parametrize("quality", sim.QUALITIES)
def test_one_session_takes_at_most_its_cap_and_the_struggling_learner_drills_every_other_day(quality):
    life = sim.simulate_life("B2", quality, days=150)
    assert all(day.reviewed <= sim.DUE_PER_SESSION for day in life.days)
    assert all(day.new <= sim.NEW_PER_SESSION for day in life.days)
    if quality == "struggling":
        assert [day.drill_day for day in life.days[:4]] == [True, False, True, False]
        assert all(day.reviewed == 0 and day.new == 0 for day in life.days if not day.drill_day)
    else:
        assert all(day.drill_day for day in life.days)


def test_an_uncapped_learner_clears_the_whole_pile_every_drill_day():
    life = sim.simulate_life("B2", "average", cap=None, days=150)
    assert all(day.reviewed == day.due for day in life.days if day.drill_day)


def test_the_rendered_tables_name_every_life():
    lives = [sim.simulate_life(level, "strong", days=60) for level in sim.LEVELS]
    table = sim.render(lives, title="test")
    for level in sim.LEVELS:
        assert f"| {level} strong |" in table
