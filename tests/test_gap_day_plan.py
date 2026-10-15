"""Story plan (2026-10-15): a gap can plan one change per day (``Gap.days``).

The measurement read every writer low on «new»: a gap day had no planned change, so
the page circled. A planned beat names the premise of the day, where the page starts
(``before``), where the learner's exchange ends (``after``) and the hook for tomorrow.
"""

from __future__ import annotations

from datetime import date

from app.services.season import clock as season_clock
from app.services.season.director import gap_brief, planned_beat
from app.services.season.flags import effective_flags
from app.services.season.format import DayBeat, load_season, validate_season


def _g1_day(day: int, premises: list[str] | None = None):
    season = load_season("s1")
    played = [{"segment": "t1", "day_in_segment": n, "event_id": str(n)} for n in (1, 2)]
    played += [{"segment": "g1", "day_in_segment": n, "event_id": f"g{n}"} for n in range(1, day)]
    state = {
        "id": "s1",
        "played": played,
        "premises": [{"gap": "g1", "premise": premise} for premise in premises or []],
    }
    pos = season_clock.position(season, state, today=date(2026, 11, 12 + day))
    assert pos.key == f"g1.{day}"
    return season, pos, state


def test_gap_one_plans_a_change_for_each_of_its_five_days():
    gap = load_season("s1").gaps["g1"]
    assert [beat.day for beat in gap.days] == [1, 2, 3, 4, 5]
    assert gap.days[0].premise == "plusieurs_semaines"
    assert gap.days[-1].premise == "la_meme_chose"
    assert all(beat.before != beat.after for beat in gap.days)


def test_the_brief_hands_the_director_the_planned_beat_of_the_day():
    season, pos, state = _g1_day(1)
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    assert brief["today"]["required_premise"]["id"] == "plusieurs_semaines"
    beat = brief["today"]["beat"]
    assert set(beat) == {"before", "after", "also", "hook"}
    assert beat["before"] and beat["after"]


def test_a_beat_that_did_not_happen_comes_back_before_the_next_one():
    season, pos, state = _g1_day(3, premises=["plusieurs_semaines"])
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    assert brief["today"]["required_premise"]["id"] == "soupe_de_marin", "day 2's beat is owed first"


def test_a_beat_staged_early_moves_the_plan_on():
    gap = load_season("s1").gaps["g1"]
    beat = planned_beat(gap, 2, {"plusieurs_semaines", "soupe_de_marin"}, {})
    assert beat is not None and beat.premise == "le_billet"


def test_a_finished_plan_leaves_the_day_free():
    gap = load_season("s1").gaps["g1"]
    done = {beat.premise for beat in gap.days}
    assert planned_beat(gap, 5, done, {}) is None


def test_the_check_refuses_a_plan_that_breaks_the_required_window():
    season = load_season("s1")
    gap = season.gaps["g1"]
    late = [beat.model_copy(update={"day": 9}) if beat.premise == "la_meme_chose" else beat for beat in gap.days]
    late += [DayBeat(day=1, premise="nope", before="a", after="b")]
    broken = season.model_copy(update={"gaps": {**season.gaps, "g1": gap.model_copy(update={"days": late})}})
    problems = " | ".join(validate_season(broken))
    assert "two beats on one day" in problems
    assert "'nope', which is not a premise" in problems
    assert "day 9 is past the gap's 5 days" in problems
    assert "required 'la_meme_chose' is not planned inside days" in problems
