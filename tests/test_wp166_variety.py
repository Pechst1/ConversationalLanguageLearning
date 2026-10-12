"""WP-166: wider, generated variety between tentpoles (no database, no model)."""

from __future__ import annotations

from datetime import date

import pytest

from app.services import living_story as engine
from app.services import story_variety as variety
from app.services.season import clock as season_clock
from app.services.season.director import _all_rows, gap_brief, pattern_hits
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.world import SEASON_ONE_LOCATIONS
from tests.test_living_story import _scene_context, draft


def _recent(*places):
    return [{"location_id": place, "premise_fr": f"Jour {i}.", "opening_fr": f"Ouverture {i}."} for i, place in enumerate(places)]


# ---------------------------------------------------------------------------
# The decks are wider
# ---------------------------------------------------------------------------


def test_every_gap_offers_at_least_six_premises_ten_moments_and_six_complications():
    season = load_season("s1")
    for gap in season.gaps.values():
        # A learner sees the premises whose condition holds: count the unconditional ones
        # plus the one a plan-specific branch adds (gap 6).
        always = [premise for premise in gap.premises if not premise.when]
        assert len(always) + (1 if len(always) < len(gap.premises) else 0) >= 6, gap.id
        assert len(gap.small_moments) >= 10, gap.id
        assert len(gap.complications) >= 6, gap.id
        assert len({moment.id for moment in gap.small_moments}) == len(gap.small_moments), gap.id
        assert len({premise.id for premise in gap.premises}) == len(gap.premises), gap.id


def test_the_new_material_keeps_each_gap_s_canon():
    season = load_season("s1")
    for gap in season.gaps.values():
        rows = _all_rows(gap, season)
        for premise in gap.premises:
            assert premise.place is None or premise.place in SEASON_ONE_LOCATIONS, (gap.id, premise.id)
            assert not pattern_hits(rows, [premise.title_fr, premise.text, premise.change, premise.turn]), premise.id
        for moment in gap.small_moments:
            assert not pattern_hits(rows, [moment.text]), moment.id
        assert not pattern_hits(rows, list(gap.complications)), gap.id
        # The place spread needs somewhere to go: every gap sets premises outside the Mistral.
        assert len({premise.place for premise in gap.premises if premise.place not in (None, variety.MISTRAL)}) >= 2, gap.id


def test_the_serial_complication_deck_is_about_thirty_six_cards():
    assert len(engine.COMPLICATION_CARDS) >= 36
    assert len(set(engine.COMPLICATION_CARDS)) == len(engine.COMPLICATION_CARDS)
    assert "spark" in engine.DIRECTOR and "novelty" in engine.DIRECTOR


# ---------------------------------------------------------------------------
# The gap brief: a spark dealt per learner, never a menu in file order
# ---------------------------------------------------------------------------


def _brief(seed: str, played: int = 2):
    season = load_season("s1")
    state = {"id": "s1", "played": [{"segment": "t1", "day_in_segment": d, "event_id": str(d)} for d in range(1, played + 1)]}
    pos = season_clock.position(season, state, today=date(2026, 11, 13))
    return gap_brief(season, pos, flags=effective_flags(season, state, seed=seed), state=state, seed=seed)


def test_the_brief_deals_the_premises_and_a_spark_per_learner():
    one, again, other = _brief("life-a"), _brief("life-a"), _brief("life-b")
    assert [p["id"] for p in one["today"]["premises"]] == [p["id"] for p in again["today"]["premises"]], "reproducible"
    orders = {tuple(p["id"] for p in _brief(f"life-{n}")["today"]["premises"]) for n in range(8)}
    assert len(orders) > 1, "different learners, different order"
    assert sorted(p["id"] for p in one["today"]["premises"]) == sorted(p["id"] for p in other["today"]["premises"])
    spark = one["today"]["spark"]
    assert spark["complication"] in load_season("s1").gaps["g1"].complications
    assert spark["small_moment"]["id"] in {m.id for m in load_season("s1").gaps["g1"].small_moments}
    required = (one["today"]["required_premise"] or {}).get("id")
    assert spark["premise"] is None or spark["premise"]["id"] != required
    assert "Invent" in one["today"]["invent"]


# ---------------------------------------------------------------------------
# The novelty memory and the place spread
# ---------------------------------------------------------------------------


def test_the_novelty_memory_names_this_life_s_recent_past():
    recent = _recent("le_mistral", "boulangerie", "le_mistral", "toit")
    recent[-1]["complication"] = "Le radiateur est mort."
    recent[-1]["premise_id"] = "soupe_de_marin"
    memory = variety.novelty_memory(recent, list(SEASON_ONE_LOCATIONS), seed="x")
    assert memory["recent_openings"] == ["Ouverture 0.", "Ouverture 1.", "Ouverture 2.", "Ouverture 3."]
    assert memory["recent_complications"] == ["Le radiateur est mort."]
    assert memory["recent_premise_ids"] == ["soupe_de_marin"]
    places = memory["places"]
    assert places["mistral_days_in_last_4"] == 2 and places["mistral_open_today"] is False
    assert variety.MISTRAL not in places["prefer"]
    assert not {"boulangerie", "toit"} & set(places["prefer"]), "not the rooms of the last days"
    assert len(places["prefer"]) == variety.PREFER_PLACES


def test_a_page_at_the_mistral_past_its_share_is_sent_elsewhere_once():
    context = _scene_context(recent_situations=_recent("le_mistral", "marche_canal", "le_mistral", "newsroom"))
    context["novelty"] = variety.novelty_memory(context["recent_situations"], [loc["id"] for loc in context["world"]["locations"]])
    proposal = engine.SceneDraft.model_validate({**draft(context, 0), "location_id": "le_mistral"})
    with pytest.raises(engine.SoftRejection) as refused:
        engine._check_reading_aids(proposal, context)
    assert "Le Mistral already had 2 of the last 4 days" in refused.value.hint
    assert refused.value.proposal is not None, "servable as it stands: one retry, then served"
    # Elsewhere, or with room left at the Mistral, nothing is said.
    engine._check_reading_aids(proposal.model_copy(update={"location_id": "newsroom"}), context)
    roomy = _scene_context(recent_situations=_recent("le_mistral", "marche_canal", "brocante", "newsroom"))
    engine._check_reading_aids(proposal, roomy)


def test_a_premise_set_at_the_mistral_may_take_it_past_its_share():
    recent = _recent("le_mistral", "le_mistral", "toit", "ecole")
    today = {"required_premise": {"id": "la_meme_chose", "place": "le_mistral"}, "premises": []}
    context = {"recent_situations": recent, "season_script": {"brief": {"today": today}}}
    proposal = engine.SceneDraft.model_validate({**draft(_scene_context(), 0), "location_id": "le_mistral"})
    assert variety.place_spread_hint(proposal, context) is None
    context["season_script"]["brief"]["today"] = {"required_premise": None, "premises": [{"id": "romy_enquete", "place": "le_mistral"}]}
    assert variety.place_spread_hint(proposal, context) is not None, "an unclaimed premise does not exempt the page"


def test_a_published_page_leaves_its_opening_and_complication_for_the_memory():
    proposal = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    extras = variety.situation_extras(proposal)
    assert extras["opening_fr"] == variety.first_sentence(next(p.narration_fr for p in proposal.panels if p.narration_fr))
    assert extras["complication"] == ""
    assert variety.first_sentence("Il pleut. Tu as une valise.") == "Il pleut."
