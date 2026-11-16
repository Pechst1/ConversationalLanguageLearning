"""Red-thread design, slice 2: the planned hook and the gap's destination, by code.

On 9 walked gap days production showed the planned hook 0 times: «À suivre…» was a
loose end drawn at random (10 November: a card in Marin's pocket, in Marin's own
mouth). With ``STORY_DAY_CONTRACT`` a contract day ends on the plan's hook, and Home
says where the gap is going and how many days are left.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import living_story, story_headline
from app.services.season import clock as season_clock
from app.services.season import day_contract
from app.services.season.format import load_season


@pytest.fixture
def contract_on(monkeypatch):
    monkeypatch.setattr(settings, "STORY_DAY_CONTRACT", True, raising=False)


def _ctx(premise: str, *, day: int, segment: str = "g3", owed: str | None = None, **extra) -> dict:
    return {
        "kind": "gap",
        "position": {"season_id": "s1", "segment": segment, "day_in_segment": day, "key": f"{segment}.{day}"},
        "checklist": {"premise_id": premise},
        "required_premise": owed or premise,
        **extra,
    }


def _g3_position(day: int):
    season = load_season("s1")
    index = [segment.id for segment in season.segments].index("g3")
    played = [
        {"segment": segment.id, "day_in_segment": n, "event_id": f"{segment.id}.{n}"}
        for segment in season.segments[:index]
        for n in range(1, segment.days + 1)
    ]
    played += [{"segment": "g3", "day_in_segment": n, "event_id": f"g3.{n}"} for n in range(1, day)]
    pos = season_clock.position(season, {"id": "s1", "played": played}, today=date(2026, 11, 27) + timedelta(days=day))
    assert pos.key == f"g3.{day}"
    return season, pos


def test_off_by_default_the_old_teaser_stands():
    assert settings.STORY_DAY_CONTRACT is False
    season = load_season("s1")
    assert day_contract.hook_teaser(season, _ctx("les_canapes", day=5), band="A1", date="2026-11-10") is None
    assert day_contract.arc(*_g3_position(5)) is None


def test_the_canape_day_ends_on_lilas_photo_not_on_a_loose_end(contract_on):
    season = load_season("s1")
    teaser = day_contract.hook_teaser(season, _ctx("les_canapes", day=5), band="A1", date="2026-11-10")
    assert teaser == {
        "text_fr": "Demain, j'ai besoin de toi. Il manque la photo du milieu.",
        "character_id": "lila_bonnet",
        "date": "2026-11-10",
        "ref": "contract:g3.les_canapes",
        "kind": "season",
    }


def test_a_hook_reads_at_the_learners_level(contract_on):
    season = load_season("s1")
    a1 = day_contract.hook_teaser(season, _ctx("deux_repetitions", day=4), band="A1", date=None)
    b1 = day_contract.hook_teaser(season, _ctx("deux_repetitions", day=4), band="B1", date=None)
    assert a1["text_fr"] == "Demain, chez moi. Tu goûtes. Viens avec faim."
    assert b1["text_fr"] == "Demain, chez moi. J'ai besoin de quelqu'un pour goûter. Viens avec faim."


def test_a_narrated_hook_has_no_speaker(contract_on):
    season = load_season("s1")
    teaser = day_contract.hook_teaser(season, _ctx("au_milieu_du_mur", day=6), band="A2", date=None)
    assert teaser["character_id"] is None
    assert "lettre" in teaser["text_fr"]


def test_the_day_before_a_tentpole_keeps_the_seasons_own_line(contract_on):
    season = load_season("s1")
    assert day_contract.hook_teaser(season, _ctx("tout_va_bien", day=7), band="A2", date=None) is None


def test_a_page_about_something_else_does_not_borrow_the_hook(contract_on):
    """A fallback page that did not stage the planned beat promises nothing of it."""

    season = load_season("s1")
    other = _ctx("sur_le_toit", day=5, owed="les_canapes")
    assert day_contract.hook_teaser(season, other, band="A1", date=None) is None
    assert day_contract.hook_teaser(season, _ctx("les_canapes", day=5, bridge=True), band="A1", date=None) is None
    assert day_contract.hook_teaser(season, {**_ctx("x", day=1), "kind": "tentpole"}, band="A1", date=None) is None


def test_a_gap_without_contracts_keeps_its_old_teaser(contract_on):
    season = load_season("s1")
    premise = season.gaps["g1"].days[0].premise
    assert day_contract.hook_teaser(season, _ctx(premise, day=1, segment="g1"), band="A1", date=None) is None


def test_the_settle_asks_the_contract_before_the_loose_ends(contract_on, monkeypatch):
    monkeypatch.setattr(living_story, "learner_level_band", lambda user: "A1")
    teaser = living_story._contract_hook({"season": _ctx("les_canapes", day=5)}, user=object(), date="2026-11-10")
    assert teaser["ref"] == "contract:g3.les_canapes"
    assert living_story._contract_hook({}, user=object(), date=None) is None


def test_the_arc_counts_the_days_to_saturday(contract_on):
    season, pos = _g3_position(5)
    assert day_contract.arc(season, pos) == {
        "gap_title_fr": "Avant la fête",
        "title_fr": "Les 25 ans du Mistral",
        "when_fr": "samedi",
        "days_left": 3,
    }
    assert day_contract.arc(*_g3_position(7))["days_left"] == 1
    assert day_contract.arc(*_g3_position(1))["days_left"] == 7


def test_a_gap_that_names_no_destination_has_no_arc(contract_on):
    season = load_season("s1")
    gap4 = next(segment for segment in season.segments if segment.id == "g4")
    pos = SimpleNamespace(is_gap=True, segment=gap4, day_in_segment=2)
    assert day_contract.arc(season, pos) is None
    tentpole = next(segment for segment in season.segments if segment.id == "t4")
    assert day_contract.arc(season, SimpleNamespace(is_gap=False, segment=tentpole, day_in_segment=1)) is None


def test_the_headline_carries_the_arc_only_with_the_flag(monkeypatch):
    season, pos = _g3_position(5)
    today = SimpleNamespace(season=season, pos=pos)
    monkeypatch.setattr("app.services.season.runtime.today_for", lambda live, **kwargs: today)
    user = SimpleNamespace(id="u1")
    assert story_headline._arc({}, user) is None
    monkeypatch.setattr(settings, "STORY_DAY_CONTRACT", True, raising=False)
    assert story_headline._arc({}, user)["days_left"] == 3
