"""STORY-ORIENTATION / STORY-FIRST (2026-10-12): the owner's first run on a phone.

«A new learner does not know where they are or what they are in», and «many tasks
make no sense». A learner who begins on the authored season skipped the café first
day and with it the only cast intro; the season's premise was never shown; and the
first screens were warm-up drills of words from a scene not yet read. Pinned here:

1. the learner's first season day carries the premise, how to play and the faces of
   the first night, in the learner's language — and only that day does;
2. on an authored season page nothing is drilled before the scene is read.
"""

from __future__ import annotations

import uuid

import pytest

from app.services import journey_planner as planner
from app.services.journey_contracts import DayShape, StepKind
from app.services.season.intro import is_first_season_day, season_intro
from tests import test_journey_end_to_end as support
from tests.test_journey_planner import _brief
from tests.test_season_one import _play, season_on  # noqa: F401 - fixture
from tests.test_wp78_practice_day import _dice
from tests.test_wp86_scene_floor import CAST, DRAFT, _lexicon_candidates

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


def test_the_season_intro_reads_in_the_learners_language():
    intro = season_intro("s1", "de")
    assert intro and "Odile" in intro["premise_native"] and "Mistral" in intro["premise_native"]
    assert "Wohnung" in intro["premise_native"]
    assert intro["how_native"]
    ids = [row["character_id"] for row in intro["cast_intro"]]
    assert ids == ["margaux_barman", "augustin_de_roncourt", "marin_leveque", "lila_bonnet"]
    assert all(row["role_native"] and row["line_fr"] and row["line_native"] for row in intro["cast_intro"])
    assert season_intro("nope", "de") is None
    assert "·" not in season_intro("s1", "fr")["premise_native"]


def test_only_the_first_season_page_is_a_first_day():
    def ctx(day, **extra):
        return {"season": {"kind": "tentpole", "position": {"season_day": day}, **extra}}

    assert is_first_season_day(ctx(1))
    assert not is_first_season_day(ctx(2))
    assert not is_first_season_day(ctx(1, reprise={"token": "x"}))
    assert not is_first_season_day({"season": {"kind": "gap", "position": {"season_day": 1}}})
    assert not is_first_season_day(None)


def _steps_before_first_scene(journey: dict) -> list[dict]:
    steps = journey.get("steps") or []
    first_scene = next(index for index, step in enumerate(steps) if step.get("kind") == "scene")
    return steps[:first_scene]


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_day_one_says_where_you_are_and_reads_the_scene_first(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    d = support.Driver(
        assembled_client, support.register(assembled_client, f"s1-orient-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session
    )
    d.create()
    day_one = d.journey
    assert day_one["story_premise_native"] and "Odile" in day_one["story_premise_native"]
    assert day_one["story_how_native"]
    assert [row["character_id"] for row in day_one["cast_intro"]][:1] == ["margaux_barman"]
    assert not [step for step in _steps_before_first_scene(day_one) if step.get("kind") == "recall"], (
        "nothing is drilled before the first page is read"
    )
    d.play(answer="Odile, c'est ma grand-mère.")
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    day_two = _play(d, provider, clock, "Odile, c'est ma grand-mère.")
    # Day two repeats where the learner is (over its «Précédemment»), not the cast.
    assert day_two["story_premise_native"] == day_one["story_premise_native"]
    assert day_two["cast_intro"] is None
    for _ in range(2):
        later = _play(d, provider, clock, "Odile, c'est ma grand-mère.")
    assert later["story_premise_native"] is None


def _plan(season: dict | None):
    context = {"draft": DRAFT, "source": {"world": {"cast": CAST}}}
    if season is not None:
        context["season"] = season
    plan = planner.plan_journey(
        scenario=_brief(story_context=context, control_language="de", level_band="A2"),
        candidates=_lexicon_candidates(),
        practice=True,
        dice=_dice(),
        day_shape=DayShape.STANDARD,
    )
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    return plan, kinds[: kinds.index(StepKind.SCENE)]


def test_an_authored_page_is_read_before_anything_is_drilled():
    _plan_, before = _plan(None)
    assert StepKind.RECALL in before, "a generated day still opens on its warm-ups"
    plan, before = _plan({"kind": "tentpole", "position": {"season_day": 1}})
    assert StepKind.RECALL not in before, plan.rationale
    assert any(step.kind is StepKind.RECALL for step in plan.steps), "the drills come after the scene"
