"""«Demain» (steering read 2026-10-24): the learner picks which thread tomorrow follows.

The day plans of gaps 2, 3 and 5 are not a chain: once the box is open, «Je peux ?»,
the dinner, Gus's birthday and the petition can come in any order. A beat with a
``pick_fr`` may be pulled forward by the learner; the plan's last beat stays last, and
no pick pushes a required moment past its day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.services.season import clock as season_clock
from app.services.season import runtime as season_runtime
from app.services.season.director import (
    TOMORROW_KEY,
    gap_brief,
    planned_beat,
    tomorrow_options,
)
from app.services.season.flags import effective_flags
from app.services.season.format import load_season, validate_season


def _ids(beats) -> list[str]:
    return [beat.premise for beat in beats]


def _g2_day(day: int, premises: list[str], *, pick: dict | None = None):
    season = load_season("s1")
    played = [{"segment": seg, "day_in_segment": n, "event_id": f"{seg}{n}"} for seg in ("t1", "t2") for n in (1, 2)]
    played[2:2] = [{"segment": "g1", "day_in_segment": n, "event_id": f"g1.{n}"} for n in range(1, 6)]
    played += [{"segment": "g2", "day_in_segment": n, "event_id": f"g2.{n}"} for n in range(1, day)]
    state = {
        "id": "s1",
        "played": played,
        "premises": [{"gap": "g2", "premise": premise} for premise in premises],
        **({TOMORROW_KEY: pick} if pick else {}),
    }
    pos = season_clock.position(season, state, today=date(2026, 11, 24 + day))
    assert pos.key == f"g2.{day}"
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    return brief


def test_the_plan_offers_its_own_beat_first_and_two_that_stand_alone():
    gap = load_season("s1").gaps["g2"]
    options = tomorrow_options(gap, 2, {"la_boite"}, {}, length=6)
    assert _ids(options) == ["je_peux", "le_diner_rate", "pour_son_anniversaire"]
    assert [beat.pick_fr for beat in options] == [
        "Parler du plan d'Odile avec Marin",
        "Cuisiner avec Lila",
        "Fêter l'anniversaire de Gus",
    ]


def test_the_last_beat_stays_last_and_the_last_days_have_no_choice():
    gap = load_season("s1").gaps["g2"]
    staged = {"la_boite", "je_peux", "le_diner_rate", "pour_son_anniversaire"}
    assert tomorrow_options(gap, 5, staged, {}, length=6) == [], "only Bastien's call is left beside the petition"
    assert tomorrow_options(gap, 6, staged | {"la_petition"}, {}, length=6) == []
    assert "bastien_appelle" not in _ids(tomorrow_options(gap, 4, staged - {"pour_son_anniversaire"}, {}, length=6))


def test_the_day_after_a_tentpole_has_no_choice():
    gap = load_season("s1").gaps["g2"]
    assert tomorrow_options(gap, 1, set(), {}, length=6) == [], "the box opens the gap"


def test_a_beat_waits_for_what_it_stands_on():
    gap = load_season("s1").gaps["g3"]
    staged = {"le_billet_encore", "sur_le_toit", "deux_repetitions"}
    # The wall needs the cards: a first day the critic left behind does not count.
    assert "au_milieu_du_mur" not in _ids(
        tomorrow_options(gap, 5, staged, {}, length=7, dropped={"les_petites_cartes"})
    )
    assert "au_milieu_du_mur" in _ids(tomorrow_options(gap, 5, staged | {"les_petites_cartes"}, {}, length=7))


def test_no_pick_pushes_a_required_moment_past_its_day():
    gap = load_season("s1").gaps["g2"]
    staged = {"la_boite", "je_peux"}
    # The dinner is required by day 5: picked away on day 4 it still comes on day 5.
    assert _ids(tomorrow_options(gap, 4, staged, {}, length=6)) == [
        "le_diner_rate",
        "pour_son_anniversaire",
        "la_petition",
    ]
    # On day 5 it is due: nothing else may take the day.
    assert tomorrow_options(gap, 5, staged, {}, length=6) == []


def test_a_preferred_beat_comes_before_the_plan_but_never_before_the_last_day():
    gap = load_season("s1").gaps["g2"]
    staged = {"la_boite"}
    assert planned_beat(gap, 2, staged, {}, length=6, prefer="pour_son_anniversaire").premise == "pour_son_anniversaire"
    assert planned_beat(gap, 2, staged, {}, length=6, prefer="nope").premise == "je_peux"
    assert planned_beat(gap, 6, staged, {}, length=6, prefer="le_diner_rate").premise == "bastien_appelle"


def test_the_brief_stages_the_learners_pick_and_says_what_waits():
    pick = {"gap": "g2", "day": 2, "premise": "pour_son_anniversaire"}
    brief = _g2_day(2, ["la_boite"], pick=pick)
    today = brief["today"]
    assert today["required_premise"]["id"] == "pour_son_anniversaire"
    assert today["picked"] == {
        "by_learner": "Fêter l'anniversaire de Gus",
        "waits": {"title_fr": "Je peux ?", "before": "Odile's plan «Le Mistral à nous» is one page in a notebook."},
    }
    assert set(today["beat"]) == {"before", "after", "also", "hook"}


def test_the_plan_comes_back_the_day_after_a_pick():
    brief = _g2_day(3, ["la_boite", "pour_son_anniversaire"], pick={"gap": "g2", "day": 2, "premise": "pour_son_anniversaire"})
    assert brief["today"]["required_premise"]["id"] == "je_peux"
    assert "picked" not in brief["today"]


def test_a_pick_the_day_no_longer_offers_is_ignored():
    for pick in (
        {"gap": "g2", "day": 2, "premise": "bastien_appelle"},
        {"gap": "g2", "day": 3, "premise": "pour_son_anniversaire"},
        {"gap": "g3", "day": 2, "premise": "pour_son_anniversaire"},
    ):
        brief = _g2_day(2, ["la_boite"], pick=pick)
        assert brief["today"]["required_premise"]["id"] == "je_peux", pick
        assert "picked" not in brief["today"]


def _hook(premise: str) -> str:
    return next(beat.hook for beat in load_season("s1").gaps["g2"].days if beat.premise == premise)


def test_a_picked_day_ends_on_the_hook_of_what_comes_next():
    """Paid check 2026-10-28: the learner picked the dinner before «Je peux ?». The
    dinner's own hook promised Gus's birthday for tomorrow while «Je peux ?» waited,
    and the next day «Je peux ?»'s own hook («Ce soir, on cuisine chez toi.») came
    after the dinner. The hook now leads into what the plan stages next."""

    dinner = _g2_day(2, ["la_boite"], pick={"gap": "g2", "day": 2, "premise": "le_diner_rate"})["today"]
    assert dinner["required_premise"]["id"] == "le_diner_rate"
    assert dinner["beat"]["hook"] == _hook("la_boite"), "Marin wants to ask the learner something"
    after = _g2_day(3, ["la_boite", "le_diner_rate"])["today"]
    assert after["required_premise"]["id"] == "je_peux"
    assert after["beat"]["hook"] == _hook("le_diner_rate"), "Gus's birthday, not tonight's dinner"


def test_a_day_in_the_plans_order_keeps_its_own_hook():
    for day, staged, premise in (
        (2, ["la_boite"], "je_peux"),
        (3, ["la_boite", "je_peux"], "le_diner_rate"),
        (6, ["la_boite", "je_peux", "le_diner_rate", "pour_son_anniversaire", "la_petition"], "bastien_appelle"),
    ):
        today = _g2_day(day, staged)["today"]
        assert today["required_premise"]["id"] == premise
        assert today["beat"]["hook"] == _hook(premise), premise


def test_the_learner_picking_the_plans_own_beat_changes_nothing():
    brief = _g2_day(2, ["la_boite"], pick={"gap": "g2", "day": 2, "premise": "je_peux"})
    assert brief["today"]["required_premise"]["id"] == "je_peux"
    assert "picked" not in brief["today"]


def test_the_check_refuses_a_beat_that_needs_a_later_one():
    season = load_season("s1")
    gap = season.gaps["g2"]
    days = [
        beat.model_copy(update={"needs": ["la_petition"]}) if beat.premise == "je_peux" else beat for beat in gap.days
    ]
    broken = season.model_copy(update={"gaps": {**season.gaps, "g2": gap.model_copy(update={"days": days})}})
    assert "g2: 'je_peux' needs 'la_petition', which the plan does not stage before it" in validate_season(broken)


def _live_after_g2_1(event_id: str = "journey:j:story") -> dict:
    played = [{"segment": "t1", "day_in_segment": n, "event_id": f"t1{n}"} for n in (1, 2)]
    played += [{"segment": "g1", "day_in_segment": n, "event_id": f"g1.{n}"} for n in range(1, 6)]
    played += [{"segment": "t2", "day_in_segment": n, "event_id": f"t2{n}"} for n in (1, 2)]
    played += [{"segment": "g2", "day_in_segment": 1, "event_id": event_id}]
    return {season_clock.SEASON_KEY: {"id": "s1", "played": played, "premises": [{"gap": "g2", "premise": "la_boite"}]}}


_LEARNER = SimpleNamespace(timezone="UTC", cefr_estimate="A2", native_language="en", proficiency_level="A2")
_THURSDAY_EVENING = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)


def test_the_finished_day_offers_tomorrows_threads():
    choice = season_runtime.tomorrow_choice(
        _live_after_g2_1(), user=_LEARNER, seed="x", event_id="journey:j:story", now=_THURSDAY_EVENING
    )
    assert choice == {
        "gap": "g2",
        "day": 2,
        "options": [
            {"premise_id": "je_peux", "label_fr": "Parler du plan d'Odile avec Marin", "planned": True},
            {"premise_id": "le_diner_rate", "label_fr": "Cuisiner avec Lila", "planned": False},
            {"premise_id": "pour_son_anniversaire", "label_fr": "Fêter l'anniversaire de Gus", "planned": False},
        ],
        "picked": None,
    }


def test_no_choice_before_today_is_played_or_for_another_day():
    live = _live_after_g2_1()
    kwargs = {"user": _LEARNER, "seed": "x", "now": _THURSDAY_EVENING}
    assert season_runtime.tomorrow_choice(live, event_id="journey:other:story", **kwargs) is None
    assert season_runtime.tomorrow_choice({}, event_id="journey:j:story", **kwargs) is None


def test_a_pick_is_kept_for_tomorrow_and_only_from_the_options():
    live = _live_after_g2_1()
    kwargs = {"user": _LEARNER, "seed": "x", "event_id": "journey:j:story", "now": _THURSDAY_EVENING}
    assert season_runtime.pick_tomorrow(live, "bastien_appelle", **kwargs) is None
    picked = season_runtime.pick_tomorrow(live, "pour_son_anniversaire", **kwargs)
    assert picked[season_clock.SEASON_KEY][TOMORROW_KEY] == {"gap": "g2", "day": 2, "premise": "pour_son_anniversaire"}
    assert TOMORROW_KEY not in live[season_clock.SEASON_KEY], "the life it was given is left as it was"
    assert season_runtime.tomorrow_choice(picked, **kwargs)["picked"] == "pour_son_anniversaire"
    again = season_runtime.pick_tomorrow(picked, "je_peux", **kwargs)
    assert again[season_clock.SEASON_KEY][TOMORROW_KEY]["premise"] == "je_peux"
