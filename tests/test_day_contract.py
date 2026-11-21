"""Red-thread design (2026-11-10), slice 1: a planned day as a contract.

Production served 8 of 10 generated days over the story critic's refusal, and the
level guard refused the plan's own task line on three of the owner's last four days.
A contract names, per planned day, what becomes true whatever the learner answers
(``lands``), what their words add (``mark``), one ask per level, the place and the
one thing owed tomorrow (``hook``). This slice is data and its checks; nothing reads
the contract at run time yet.
"""

from __future__ import annotations

import copy

import pytest

from app.services import living_story
from app.services.season import director
from app.services.season.format import (
    LEVEL_FIELDS,
    DayContract,
    Gap,
    _check_day_contracts,
    load_season,
    validate_season,
)
from app.services.season.world import season_location_ids

CONTRACT_GAPS = ("g3", "g4")


def _contracts():
    season = load_season("s1")
    return [(gap, beat) for gap in season.gaps.values() for beat in gap.days if beat.contract]


def _french(contract: DayContract) -> list[str]:
    lines = [turn.ask_again_fr for turn in contract.turns]
    lines += [contract.mark.default_fr] if contract.mark else []
    for wording in (contract.hook.fr, contract.after_fr):
        lines += [getattr(wording, field) or "" for field in LEVEL_FIELDS]
    return [line for line in lines if line]


def test_every_planned_day_of_gaps_three_and_four_has_a_contract():
    season = load_season("s1")
    for gap_id in CONTRACT_GAPS:
        missing = [beat.premise for beat in season.gaps[gap_id].days if beat.contract is None]
        assert not missing, f"{gap_id}: no contract for {missing}"
    assert season.gaps["g3"].destination.tentpole == "t4"
    assert season.gaps["g3"].destination.when_fr == "samedi"


def test_the_contracts_hold_against_the_season_and_its_places():
    assert validate_season(load_season("s1"), locations=season_location_ids("s1")) == []


@pytest.mark.parametrize("level", ["a1", "a2", "b1"])
def test_no_ask_is_one_the_level_guard_refuses(level):
    """``objective_too_complex`` refused «Sag Marin freundlich, welches Häppchen bleiben
    soll und warum.» on 10 November: the plan's own turn. An authored ask is checked here,
    once, instead of every night."""

    for _gap, beat in _contracts():
        for turn in beat.contract.turns:
            ask = turn.ask.get(level)
            if ask:
                living_story._check_objective_scope(ask, level.upper())


def test_the_plans_old_turn_is_what_the_guard_refuses_at_a1():
    with pytest.raises(living_story.StoryUnavailable):
        living_story._check_objective_scope("Tell Marin which canapé to keep, and why, kindly.", "A1")


def test_no_authored_line_makes_a_reveal_its_gap_forbids():
    season = load_season("s1")
    for gap, beat in _contracts():
        hits = director.pattern_hits([*gap.must_not, *season.global_must_not], _french(beat.contract))
        assert not hits, f"{gap.id}.{beat.day}: {hits}"


def test_the_canape_day_is_the_one_the_design_describes():
    beat = next(beat for _gap, beat in _contracts() if beat.premise == "les_canapes")
    contract = beat.contract
    assert contract.place == "marin_lila_flat" and contract.place_alt == "le_mistral"
    assert [fact.id for fact in contract.lands] == ["g3.menu"]
    assert contract.mark.id == "g3.canape_name" and contract.mark.comes_back == ["g3.7", "t4"]
    assert [route.id for route in contract.routes if route.default] == ["elsewhere"]
    assert contract.hook.about == "au_milieu_du_mur" and contract.hook.speaker == "lila_bonnet"
    assert "{g3.canape_name}" in contract.after_fr.text("A1")


def test_the_brief_does_not_carry_the_contract_yet():
    """Slice 1 changes nothing the writer reads."""

    from datetime import date

    from app.services.season import clock as season_clock
    from app.services.season.flags import effective_flags

    season = load_season("s1")
    played = [
        {"segment": segment.id, "day_in_segment": day, "event_id": f"{segment.id}.{day}"}
        for segment in season.segments[: [s.id for s in season.segments].index("g3")]
        for day in range(1, segment.days + 1)
    ]
    state = {"id": "s1", "played": played, "premises": []}
    pos = season_clock.position(season, state, today=date(2026, 11, 28))
    assert pos.key == "g3.1"
    brief = director.gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    assert set(brief["today"]["beat"]) == {"before", "after", "also", "hook"}


# --- the checks themselves ----------------------------------------------------


def _g3(change) -> list[str]:
    season = load_season("s1")
    raw = copy.deepcopy(season.gaps["g3"].model_dump())
    change(raw)
    return _check_day_contracts(season, Gap.model_validate(raw), locations=season_location_ids("s1"))


def _day(raw: dict, premise: str) -> dict:
    return next(beat for beat in raw["days"] if beat["premise"] == premise)["contract"]


def test_a_hook_must_lead_into_the_next_planned_day():
    problems = _g3(lambda raw: _day(raw, "les_canapes")["hook"].update(about="tout_va_bien"))
    assert any("the hook is about 'tout_va_bien'" in problem for problem in problems)


def test_a_rephrased_hook_must_still_name_its_words():
    def change(raw):
        _day(raw, "les_canapes")["hook"]["fr"]["a2"] = "Demain, j'ai besoin de toi."

    assert any("does not name ['photo', 'milieu']" in problem for problem in _g3(change))


def test_a_mark_comes_back_later_and_somewhere():
    earlier = _g3(lambda raw: _day(raw, "les_canapes")["turns"][1]["mark"].update(comes_back=["g3.2"]))
    assert any("which is not later" in problem for problem in earlier)
    nowhere = _g3(lambda raw: _day(raw, "les_canapes")["turns"][1]["mark"].update(comes_back=[]))
    assert any("comes back nowhere" in problem for problem in nowhere)


def test_a_place_outside_the_season_is_refused():
    problems = _g3(lambda raw: _day(raw, "les_canapes").update(place="la_lune"))
    assert any("'la_lune' is not a place of the season" in problem for problem in problems)


def test_a_fact_is_named_once_in_a_gap():
    def change(raw):
        _day(raw, "au_milieu_du_mur")["lands"][0]["id"] = "g3.menu"

    assert any("'g3.menu' is named twice" in problem for problem in _g3(change))


def test_an_after_line_fills_only_the_days_own_mark():
    def change(raw):
        _day(raw, "au_milieu_du_mur")["after_fr"]["a2"] = "Le mur est prêt : « {g3.canape_name} »."

    assert any("slots ['g3.canape_name'] the day does not fill" in problem for problem in _g3(change))


def test_a_contract_has_exactly_one_default_route():
    season = load_season("s1")
    raw = next(beat for beat in season.gaps["g3"].days if beat.premise == "les_canapes").contract.model_dump()
    raw["routes"][0]["default"] = True
    with pytest.raises(ValueError, match="exactly one default route"):
        DayContract.model_validate(raw)


def test_closing_job_says_whether_the_last_turn_carries_the_mark():
    season = load_season("s1")
    raw = next(beat for beat in season.gaps["g3"].days if beat.premise == "les_canapes").contract.model_dump()
    raw["closing_job"] = "turn"
    with pytest.raises(ValueError, match="closing_job"):
        DayContract.model_validate(raw)
