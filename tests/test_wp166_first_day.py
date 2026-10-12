"""WP-166 (owner decision 2): day 1's way in is written per learner around T1's spine;
the authored opening is the fallback. No model: the writer is replaced by a fixed opening."""

from __future__ import annotations

import uuid

import pytest

from app.config import settings
from app.services.season import opening
from app.services.season.format import load_season
from app.services.season.page import project, resolve_day
from tests import test_journey_end_to_end as support
from tests.test_season_one import (  # noqa: F401 - fixtures
    _latest_scene,
    _pinned_brief,
    _user_id_of,
    assembled_client,
    clock,
    journey_enabled,
    season_on,
)

GOOD = {
    "hour": "21:40",
    "weather": "brouillard",
    "learner_doing": "stepping off a late train with a suitcase",
    "arrival": {
        "location_id": "gare_de_lest",
        "visual": "Fog under the glass roof of the gare de l'Est. Toi from behind, a suitcase, an envelope under the arm.",
        "caption_fr": "Le train arrive tard. Le brouillard te suit jusqu'au canal.",
        "caption_native": "The train is late. The fog follows you to the canal.",
        "lines": [],
    },
    "room": {
        "location_id": "le_mistral",
        "visual": "Inside Le Mistral: Marin fixes the jukebox with a spoon, Gus conducts, Lila draws them.",
        "caption_fr": "",
        "lines": [
            {"who": "marin_leveque", "text_fr": "Ma grand-mère réparait tout avec une cuillère.", "text_native": "My grandmother fixed everything with a spoon.", "mood": "happy"},
            {"who": "lila_bonnet", "text_fr": "Sept sur vingt, Marin.", "text_native": "Seven out of twenty, Marin.", "mood": "neutral"},
        ],
    },
}


def _page(band="A2", language="en", day="a"):
    return resolve_day(load_season("s1"), "t1", day, flags={}, band=band, language=language)


def _parsed(**changes):
    value = {**GOOD, **changes}
    return opening.FirstDayOpening.model_validate(value)


def test_a_good_opening_passes_the_guards_and_bad_ones_name_their_fault():
    assert opening.problems(_parsed(), band="A2") == []
    morning = opening.problems(_parsed(hour="08:15"), band="A2")
    assert any("evening" in problem for problem in morning)
    named = _parsed(room={**GOOD["room"], "lines": [{"who": "lila_bonnet", "text_fr": "Camille arrive ce soir ?"}]})
    assert any("camille" in problem for problem in opening.problems(named, band="A2"))
    stranger = _parsed(room={**GOOD["room"], "lines": [{"who": "romy_tremblay", "text_fr": "Voyons donc."}]})
    assert any("romy_tremblay may not speak" in problem for problem in opening.problems(stranger, band="A2"))
    agreed = _parsed(arrival={**GOOD["arrival"], "caption_fr": "Tu es trempée. Le canal brille."})
    assert any("agreement-free" in problem for problem in opening.problems(agreed, band="A2"))
    elsewhere = _parsed(arrival={**GOOD["arrival"], "location_id": "notaire"})
    assert any("arrival place" in problem for problem in opening.problems(elsewhere, band="A2"))
    spoiler = _parsed(room={**GOOD["room"], "lines": [{"who": "marin_leveque", "text_fr": "Le Mistral à nous, un jour."}]})
    assert any("forbidden reveal" in problem for problem in opening.problems(spoiler, band="A2"))


def test_a_shape_slip_is_read_tolerantly_and_a_greeting_is_refused():
    # The paid check of 2026-10-11 lost openings to «Gus» for an id, a 500-character
    # direction and a null caption; and served Gus greeting the newcomer.
    slipped = _parsed(
        arrival={**GOOD["arrival"], "visual": "Fog. " * 120},
        room={**GOOD["room"], "caption_fr": None, "lines": [{"who": "Gus", "text_fr": "Mesdames, messieurs !"}]},
    )
    assert slipped.room.lines[0].who == "augustin_de_roncourt"
    assert len(slipped.arrival.visual) <= 480 and slipped.room.caption_fr == ""
    assert opening.problems(slipped, band="A2") == []
    greeted = _parsed(room={**GOOD["room"], "lines": [{"who": "augustin_de_roncourt", "text_fr": "Vous arrivez au meilleur moment."}]})
    assert any("noticed the newcomer" in problem for problem in opening.problems(greeted, band="C1"))
    long_caption = _parsed(arrival={**GOOD["arrival"], "caption_fr": " ".join(["mot"] * 30)})
    assert any("the caption has 30 words" in problem for problem in opening.problems(long_caption, band="A1"))


def test_the_opening_replaces_the_way_in_and_keeps_the_spine():
    page = _page()
    served = opening.apply_opening(page, GOOD)
    before = {m.get("id"): m for m in page["movements"]}
    after = {m.get("id"): m for m in served["movements"]}
    assert list(before) == list(after), "same movements, same order"
    assert after["a.p1"]["location_id"] == "gare_de_lest"
    assert after["a.p1"]["lines"][0]["text_fr"] == GOOD["arrival"]["caption_fr"]
    assert after["a.p1"]["lines"][0]["text_native"] == GOOD["arrival"]["caption_native"], "A2, English: translated"
    assert [line["who"] for line in after["a.p2"]["lines"]] == ["marin_leveque", "lila_bonnet"]
    assert after["a.p2"]["lines"][0]["name"] == "Marin Lévêque"
    for key in before:
        if key not in opening.OPENING_PANELS and before[key].get("kind") == "turn":
            assert after[key]["replies"] == before[key]["replies"], "the turns are T1's"
    # The scene's first caption — the day's premise — is now this learner's.
    captions = [line for panel in project(served)["scene_panels"] for line in panel.get("lines") or [] if line.get("kind") == "caption"]
    assert captions[0]["text_fr"] == GOOD["arrival"]["caption_fr"]
    # A foggy evening dries the later directions (Camille's helmet is not rain-soaked).
    assert "rain-soaked" not in str(served["movements"]) and "rain-soaked" in str(page["movements"])
    assert served["opening"]["weather"] == "brouillard"


def test_from_b1_the_way_in_follows_the_one_language_rule():
    served = opening.apply_opening(_page(band="B1"), GOOD)
    first = next(m for m in served["movements"] if m.get("id") == "a.p1")
    assert first["lines"][0]["text_native"] is None


def test_day_one_serves_the_learner_s_opening_and_falls_back_to_the_authored_one(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    headers = support.register(assembled_client, f"wp166-{uuid.uuid4()}@example.com", cefr="A2.1")
    monkeypatch.setattr(settings, "ATELIER_VARIED_FIRST_DAY_ENABLED", True)
    monkeypatch.setattr(opening, "enabled", lambda: True)
    calls = []

    def written(page, *, band, language, budget):
        calls.append((band, language, budget))
        return dict(GOOD), [{"stage": "FirstDayOpening", "cost_usd": 0.001}]

    monkeypatch.setattr(opening, "write_opening", written)
    d = support.Driver(assembled_client, headers, db=db_session)
    d.create()
    assert d.journey["status"] == "active", d.journey
    draft = _pinned_brief(db_session, d.journey["id"])["story_context"]["draft"]
    assert draft["premise_fr"] == GOOD["arrival"]["caption_fr"]
    assert calls and calls[0][2] == opening.OPENING_INLINE_SECONDS, "no background row: written inside the cold-day budget"
    assert season_on.director_contexts() == [], "a tentpole day still makes no director call"
    status, stored, _ = opening.stored_opening(db_session, _user_id_of(db_session, d.journey))
    assert status == "ready" and stored["hour"] == "21:40"


def test_a_refused_or_absent_opening_serves_t1_as_written(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    headers = support.register(assembled_client, f"wp166-{uuid.uuid4()}@example.com", cefr="A2.1")
    monkeypatch.setattr(settings, "ATELIER_VARIED_FIRST_DAY_ENABLED", True)
    monkeypatch.setattr(opening, "enabled", lambda: True)
    monkeypatch.setattr(opening, "write_opening", lambda page, **_: (None, []))
    d = support.Driver(assembled_client, headers, db=db_session)
    d.create()
    draft = _pinned_brief(db_session, d.journey["id"])["story_context"]["draft"]
    authored = project(_page())["scene_panels"][0]["lines"][0]["text_fr"]
    assert draft["premise_fr"] == authored


@pytest.mark.parametrize("flag", [False])
def test_with_the_flag_off_nothing_is_written(flag, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_VARIED_FIRST_DAY_ENABLED", flag)
    assert opening.enabled() is False
    assert opening.opening_page(None, None, None) is None
