"""Story plan (2026-10-15): a gap can plan one change per day (``Gap.days``).

The measurement read every writer low on «new»: a gap day had no planned change, so
the page circled. A planned beat names the premise of the day, where the page starts
(``before``), where the learner's exchange ends (``after``) and the hook for tomorrow.
"""

from __future__ import annotations

from datetime import date

from app.services.season import clock as season_clock
from app.services.season import runtime as season_runtime
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


def _settle(premise: str, outcome: str, state: dict | None = None) -> dict:
    ctx = {"id": "s1", "kind": "gap", "position": {"segment": "g1", "day_in_segment": 2}, "checklist": {"premise_id": premise}}
    return season_runtime._settle_gap(load_season("s1"), state or {"id": "s1"}, ctx, {"outcome": outcome}, event_id="e", day=4)


def test_a_planned_beat_the_learner_did_not_take_up_still_moves_the_plan_on():
    """Gap-1 comparison (2026-10-15): the learner answered Marin beside the point, the
    soup stayed owed, and day 3 served Marin's soup again instead of the ticket."""

    state = _settle("soupe_de_marin", "not_yet", {"id": "s1", "premises": [{"gap": "g1", "premise": "plusieurs_semaines"}]})
    assert [row["premise"] for row in state["premises"]] == ["plusieurs_semaines", "soupe_de_marin"]
    beat = planned_beat(load_season("s1").gaps["g1"], 3, {row["premise"] for row in state["premises"]}, {})
    assert beat is not None and beat.premise == "le_billet"


def test_a_required_beat_the_learner_let_pass_moves_on_and_settles_its_fact():
    """Third gap-1 run: the ticket came back on day 4 instead of Romy. Owner OK
    2026-10-15: a required day moves on too, and the story settles its fact so T2
    («you have moved your ticket to 2 December») still holds."""

    state = _settle("le_billet", "not_yet")
    assert [row["premise"] for row in state["premises"]] == ["le_billet"]
    assert state["flags"]["user.return_ticket"] == "mercredi 2 décembre"
    order = _settle("la_meme_chose", "not_yet")
    assert order["flags"]["user.usual_order"] == "un café crème"


def test_the_learners_own_choice_is_never_overwritten():
    state = _settle("la_meme_chose", "not_yet", {"id": "s1", "flags": {"user.usual_order": "un thé"}})
    assert state["flags"]["user.usual_order"] == "un thé"


def _settle_g1(premise: str, details: dict, state: dict | None = None, *, day: int = 3) -> dict:
    ctx = {"id": "s1", "kind": "gap", "position": {"segment": "g1", "day_in_segment": day}, "checklist": {"premise_id": premise}}
    return season_runtime._settle_gap(load_season("s1"), state or {"id": "s1"}, ctx, details, event_id="e", day=day + 2)


def test_the_ticket_day_moves_the_ticket_for_a_learner_who_gave_no_date():
    """Steering read 2026-10-24: both learners took the ticket day up («met») without
    naming a date, nothing settled it, and on 26 November the ticket still said 18
    November. The day now moves the ticket to the world's date."""

    assert _settle_g1("le_billet", {"outcome": "met"})["flags"]["user.return_ticket"] == "mercredi 2 décembre"


def test_a_date_the_learner_said_stays_theirs_for_the_rest_of_the_gap():
    said = {"outcome": "met", "season_flags": [{"flag": "user.return_ticket", "value": "lundi 30 novembre"}]}
    assert _settle_g1("le_billet", said)["flags"]["user.return_ticket"] == "lundi 30 novembre"
    # Said on the day the notary spoke, before the ticket day: the ticket day, taken up
    # or let pass, does not move it again.
    early = _settle_g1("plusieurs_semaines", said, day=1)
    assert early["learner_set"] == {"user.return_ticket": "g1"}
    for outcome in ("met", "not_yet"):
        later = _settle_g1("le_billet", {"outcome": outcome}, early)
        assert later["flags"]["user.return_ticket"] == "lundi 30 novembre", outcome
    # A later gap's ticket day still moves it: the learner's date was for this gap.
    ctx = {"id": "s1", "kind": "gap", "position": {"segment": "g3", "day_in_segment": 2}, "checklist": {"premise_id": "le_billet_encore"}}
    moved = season_runtime._settle_gap(load_season("s1"), early, ctx, {"outcome": "not_yet"}, event_id="e", day=20)
    assert moved["flags"]["user.return_ticket"] == "samedi 19 décembre"


def test_the_retry_for_a_dropped_planned_day_names_its_change():
    """Second gap-1 run: day 2 left premise_id empty and wrote Lila on the quay; the
    retry was told only the premise's title."""

    from types import SimpleNamespace

    from app.services.living_story import _season_required_moment

    season, pos, state = _g1_day(2, premises=["plusieurs_semaines"])
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    draft = SimpleNamespace(season_checklist=None)
    hint = _season_required_moment(draft, {"season_script": {"brief": brief}})
    assert "'soupe_de_marin'" in hint
    assert brief["today"]["beat"]["before"] in hint and brief["today"]["beat"]["after"] in hint


def test_every_gap_plans_a_change_for_every_day():
    """Gaps 2-7 (2026-10-16): every generated day of the season has a planned change."""

    season = load_season("s1")
    for segment in season.segments:
        if segment.kind != "gap":
            continue
        days = {beat.day for beat in season.gaps[segment.id].days}
        assert days == set(range(1, segment.days + 1)), segment.id


def test_the_ticket_moves_in_gaps_one_three_five_and_seven():
    """Steering read 2026-10-24: each ticket day gives the world's reason the old date no
    longer works, so the learner who wants to leave and the one who wants to stay both
    move it, each for their own reason («or keeps it» was a choice the season cannot
    honour: the next tentpole needs them in Paris)."""

    season = load_season("s1")
    for gap_id in ("g1", "g3", "g5", "g7"):
        gap = season.gaps[gap_id]
        planned = {beat.premise for beat in gap.days}
        movers = [p for p in gap.premises if p.id in planned and "user.return_ticket" in p.sets]
        assert movers, gap_id
        for premise in movers:
            assert premise.settles.get("user.return_ticket"), premise.id
            assert "whatever the learner wants" in premise.text.lower(), premise.id
            assert "own reason" in premise.change or "own reason" in premise.text, premise.id
            assert "or keeps it" not in premise.text, premise.id


def test_gap_six_plans_the_step_of_the_plan_the_learner_chose():
    gap = load_season("s1").gaps["g6"]
    done = {"le_cadeau", "deux_croissants", "la_caisse_est_partie"}
    expected = {"coop": "cent_cinquante", "lease": "margaux_ne_repond_pas", "last_service": "les_verres"}
    for plan, premise in expected.items():
        beat = planned_beat(gap, 4, done, {"s1.plan": plan})
        assert beat is not None and beat.premise == premise
        later = planned_beat(gap, 5, done | {premise}, {"s1.plan": plan})
        assert later is not None and later.premise == "regle_numero_un"


def test_two_beats_share_a_day_only_when_they_can_never_both_hold():
    season = load_season("s1")
    gap = season.gaps["g6"]
    clash = [
        beat.model_copy(update={"day": 4}) if beat.premise == "regle_numero_un" else beat
        for beat in gap.days
    ]
    broken = season.model_copy(
        update={"gaps": {**season.gaps, "g6": gap.model_copy(update={"days": clash})}}
    )
    assert "g6: the day plan has two beats on one day" in validate_season(broken)
    assert validate_season(season) == []


def test_a_ticket_day_the_learner_let_pass_still_moves_the_ticket():
    """Owner hand-off 2026-10-16: the ticket days of gaps 3, 5 and 7 stay unrequired;
    a day that passes without a date from the learner moves the ticket to the story's."""

    def settle(gap_id: str, premise: str, details: dict) -> dict:
        ctx = {
            "id": "s1",
            "kind": "gap",
            "position": {"segment": gap_id, "day_in_segment": 2},
            "checklist": {"premise_id": premise},
        }
        state = {"id": "s1", "flags": {"user.return_ticket": "mercredi 2 décembre"}}
        return season_runtime._settle_gap(load_season("s1"), state, ctx, details, event_id="e", day=20)

    passed = settle("g3", "le_billet_encore", {"outcome": "not_yet"})
    assert passed["flags"]["user.return_ticket"] == "samedi 19 décembre"
    chosen = {"outcome": "met", "season_flags": [{"flag": "user.return_ticket", "value": "dimanche 3 janvier"}]}
    assert settle("g3", "le_billet_encore", chosen)["flags"]["user.return_ticket"] == "dimanche 3 janvier"
    assert settle("g7", "le_dernier_billet", {"outcome": "met"})["flags"]["user.return_ticket"] == "samedi 9 janvier"


def test_a_gap_the_weekend_shortened_still_ends_on_its_last_beat():
    """Measured run 2026-10-16: the weekend cut gap 1 to four days and «La même chose ?»,
    the beat that leads into the next tentpole, never came."""
    gap = load_season("s1").gaps["g1"]
    done = {"plusieurs_semaines", "soupe_de_marin", "le_billet"}
    assert planned_beat(gap, 4, done, {}, length=5).premise != "la_meme_chose"
    assert planned_beat(gap, 4, done, {}, length=4).premise == "la_meme_chose"
    assert planned_beat(gap, 3, {"plusieurs_semaines"}, {}, length=4).premise == "soupe_de_marin"
