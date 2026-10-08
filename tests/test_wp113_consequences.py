"""WP-113 «Conséquences»: generated days honour the learner's choices, a
complication card is tomorrow's obstacle, and the in-between story moves on the
learner's engagement (owner OK 2026-10-02)."""

from __future__ import annotations

from datetime import date

from app.services.season import clock as season_clock
from app.services.season import runtime as season_runtime
from app.services.season.director import (
    StoryReview,
    critic_payload,
    forbidden_hits,
    gap_brief,
    open_obstacle,
    review_verdict,
)
from app.services.season.flags import effective_flags
from app.services.season.format import load_season

PLAYED_T1 = [
    {"segment": "t1", "day_in_segment": 1, "event_id": "1"},
    {"segment": "t1", "day_in_segment": 2, "event_id": "2"},
]


def _gap_ctx(day: int = 1, *, checklist: dict | None = None, gap: str = "g1") -> dict:
    return {
        "id": "s1",
        "kind": "gap",
        "position": {"segment": gap, "day_in_segment": day},
        "checklist": checklist or {},
    }


def _scheduled_premise(season) -> str:
    return season.gaps["g1"].premises[0].id


# ---------------------------------------------------------------------------
# 1. The learner's choices are honoured
# ---------------------------------------------------------------------------


def test_nobody_says_the_price_until_it_is_public():
    season = load_season("s1")
    secret = effective_flags(season, {"flags": {"s1.price_public": False}}, seed="x")
    public = effective_flags(season, {"flags": {"s1.price_public": True}}, seed="x")
    for line in ("Margaux murmure : « Trois cent dix mille euros. »", "310 000 €, c'est fou.", "310000, Gus."):
        assert "price_secret" in [key for key, _ in forbidden_hits(season, "g1", [line], flags=secret)], line
        assert "price_secret" not in [key for key, _ in forbidden_hits(season, "g1", [line], flags=public)], line
    assert not forbidden_hits(season, "g1", ["Margaux sait quelque chose. Elle ne dit rien."], flags=secret)


def test_the_critic_refuses_a_day_that_contradicts_a_choice_or_ignores_the_obstacle():
    good = StoryReview(meaningful_change=True, in_character=True)
    assert review_verdict(good)
    assert not review_verdict(good.model_copy(update={"honours_choices": False}))
    assert not review_verdict(good.model_copy(update={"obstacle_faced": False}))


def test_the_critic_reads_the_flags_and_the_open_obstacle():
    brief = {
        "today": {"required_premise": None, "gate": None, "open_obstacle": "Plus de chauffage.", "premises": [1]},
        "flags": {"s1.letter_reader": "margaux"},
    }
    payload = critic_payload(brief, {"title_fr": "Le froid"})
    assert payload["flags"] == {"s1.letter_reader": "margaux"}
    assert payload["today"] == {"required_premise": None, "gate": None, "open_obstacle": "Plus de chauffage."}


# ---------------------------------------------------------------------------
# 2. A complication is tomorrow's obstacle
# ---------------------------------------------------------------------------


def test_a_complication_is_the_next_days_obstacle_in_the_same_gap_only():
    season = load_season("s1")
    state = {"id": "s1", "played": list(PLAYED_T1)}
    state = season_runtime._settle_gap(
        season,
        state,
        _gap_ctx(1, checklist={"complication": "Le radiateur est mort : pas de chauffage avant la pièce de Gus."}),
        {"outcome": "met"},
        event_id="g1-1",
        day=3,
    )
    assert open_obstacle(state, "g1") == "Le radiateur est mort : pas de chauffage avant la pièce de Gus."
    assert open_obstacle(state, "g2") is None, "a tentpole in between does not carry it into another gap"

    state["played"].append({"segment": "g1", "day_in_segment": 1, "event_id": "g1-1"})
    pos = season_clock.position(season, state, today=date(2026, 11, 14))
    assert pos.key == "g1.2"
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    assert brief["today"]["open_obstacle"].startswith("Le radiateur est mort")

    # Faced today, with no new card drawn: the way is clear tomorrow.
    state = season_runtime._settle_gap(season, state, _gap_ctx(2), {"outcome": "met"}, event_id="g1-2", day=4)
    assert open_obstacle(state, "g1") is None


# ---------------------------------------------------------------------------
# 3. The in-between story moves on engagement
# ---------------------------------------------------------------------------


def test_a_scheduled_moment_counts_only_when_the_learner_engaged():
    season = load_season("s1")
    premise = _scheduled_premise(season)
    checklist = {"premise_id": premise}

    skipped = season_runtime._settle_gap(
        season, {"id": "s1"}, _gap_ctx(checklist=checklist), {"outcome": "not_yet"}, event_id="a", day=3
    )
    assert not skipped.get("premises"), "a day the learner did not take up leaves its moment owed"

    for outcome in ("met", "partially_met", None):
        details = {} if outcome is None else {"outcome": outcome}
        state = season_runtime._settle_gap(
            season, {"id": "s1"}, _gap_ctx(checklist=checklist), details, event_id="b", day=3
        )
        assert [row["premise"] for row in state["premises"]] == [premise], outcome
