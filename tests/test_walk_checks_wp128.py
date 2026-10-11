"""WP-128 — the life-walk time checks fire on a bad record and stay quiet on a good one."""
from __future__ import annotations

from tests import walk_checks_wp128 as checks


def _day(number: int, *, seconds: float, longer: bool = False, home: int = 540, recap: int | None = 540,
         offered: int = 520, forecast: int = 520) -> dict:
    return {
        "day": number,
        "journey": {"budget_seconds": 600, "estimated_active_seconds": 540},
        "time": {"journey": {"total": seconds}},
        "time_budget": {"core_seconds": 540, "longer_day": longer, "home": {"core_seconds": home},
                        "recap_core_seconds": recap},
        "la_une": {"available": {"estimated_seconds": offered}, "time_estimate": {"core_seconds": forecast}},
    }


def _life(*days: dict) -> dict:
    return {"persona": "a1-de-fresh", "quality": "average", "days": list(days)}


def test_a_good_life_is_quiet() -> None:
    life = _life(_day(1, seconds=560), _day(2, seconds=715), _day(3, seconds=900, longer=True))
    assert checks.check_life_wp128(life) == []


def test_too_many_overrun_days_are_reported_with_each_outlier() -> None:
    days = [_day(n, seconds=560) for n in range(1, 9)]
    # One outlier in ten ordinary days is the tail …
    assert checks.check_core_day_fits(_life(*days, _day(9, seconds=800), _day(10, seconds=560))) == []
    # … two are a pattern, and each is named.
    problems = checks.check_core_day_fits(_life(*days, _day(9, seconds=800), _day(10, seconds=780)))
    assert len(problems) == 1 and "day 9" in problems[0] and "day 10" in problems[0] and "+33%" in problems[0]


def test_a_day_past_twice_the_rhythm_is_always_reported() -> None:
    problems = checks.check_core_day_fits(_life(*[_day(n, seconds=560) for n in range(1, 20)], _day(20, seconds=1300)))
    assert len(problems) == 1 and "day 20" in problems[0]


def test_home_or_the_ending_saying_another_number_is_reported() -> None:
    problems = checks.check_one_core_number(
        _life(_day(1, seconds=500, home=600), _day(2, seconds=500, recap=480), _day(3, seconds=500, forecast=600))
    )
    assert [p.split(":")[0] for p in problems] == [
        "a1-de-fresh average day 1", "a1-de-fresh average day 2", "a1-de-fresh average day 3",
    ]


def test_a_struggling_life_is_held_to_what_its_measured_pace_would_allow() -> None:
    struggling = {**_life(_day(1, seconds=900)), "quality": "struggling"}
    assert checks.check_core_day_fits(struggling) == []
    assert checks.check_core_day_fits({**_life(_day(1, seconds=1000)), "quality": "struggling"})
    assert checks.check_core_day_fits({**_life(_day(1, seconds=900)), "quality": "average"})
