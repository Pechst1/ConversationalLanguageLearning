"""The night run's first draft should be able to pass (follow-up to P11).

Real-model play of 18 Nov (Sonnet 5.5 writer, B1, season 1 days 3–6): every night used
all three attempts. ``bottle_left_the_room`` («This chapter is a bottle: every scene
happens in rue_de_lancry…») refused a draft on four of five nights while the season's
beat for the day was elsewhere; ``grammar_not_woven``, ``mixed_address_register``,
``chapter_missing`` and ``gendered_learner_noun`` refused rules the writer was told late,
conditionally or not at all. These guards play the night with the split writer's fake.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm.attributes import flag_modified

from app.services import living_story as engine
from app.services import story_split
from app.services.journey_latency import prefetch_scene_for
from tests import test_journey_end_to_end as support
from tests.test_p11_night_run_lands import _outcome, _Writer, night  # noqa: F401 - fixture
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_story_split import (  # noqa: F401 - fixture
    _context,
    _learner_on_gap_day,
    _plan,
    split_on,
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

#: The chapter the day-3 page opened on 18 Nov: a bottle, in the street.
LANCRY_BOTTLE = {
    "id": "chapter-lancry",
    "title_fr": "Le billet",
    "dramatic_question": "Est-ce que le billet va changer ?",
    "possible_developments": ["Il change.", "Il ne change pas."],
    "scene_count": 1,
    "resolved_commitments": 0,
    "resolved": False,
    "beats": ["setup"],
    "problem_key": "billet",
    "arc_id": None,
    "shape": "bottle",
    "location_id": "rue_de_lancry",
    "character_id": "lila_bonnet",
    "side_story": True,
}


def _open_bottle_in_the_street(db_session, user) -> None:
    thread = engine._active_thread(db_session, user)
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    live["chapter"] = dict(LANCRY_BOTTLE)
    state[engine.STATE_KEY] = live
    thread.state = state
    flag_modified(thread, "state")
    db_session.commit()


def test_a_season_day_in_the_flat_passes_in_a_bottle_opened_in_the_street(
    assembled_client, db_session, journey_enabled, clock, night, caplog  # noqa: F811
):
    """The fake writer sets every page in user_apartment, where the learner's ticket
    call happens: the chapter's first room (rue_de_lancry) does not bind the next day."""

    writer = night(_Writer())
    user = _learner_on_gap_day(assembled_client, db_session)
    _open_bottle_in_the_street(db_session, user)
    with caplog.at_level(logging.INFO, logger="app.services.journey_latency"):
        assert prefetch_scene_for(db_session, user) == "prefetched"
    outcome = _outcome(caplog)
    assert outcome["attempts"] == 1, outcome
    assert outcome["refusals"] == [] and outcome["kept"] is None
    plan = next(payload for schema, payload in writer.calls if schema == "PagePlan")
    assert plan["brief"]["shape"] == "bottle", "the chapter is still a bottle"


def test_the_brief_says_what_a_bottle_asks_on_a_season_day(assembled_client, db_session, journey_enabled, clock, split_on):  # noqa: F811
    user = _learner_on_gap_day(assembled_client, db_session)
    _open_bottle_in_the_street(db_session, user)
    context = engine.story_context(db_session, user)
    assert context["chapter_shape"]["note"] == engine.SEASON_BOTTLE_NOTE
    assert context["chapter"]["shape_note"] == engine.SEASON_BOTTLE_NOTE
    assert "rue_de_lancry" not in json.dumps(context["chapter_shape"])
    assert engine.bottle_room(context) is None


def test_a_bottle_still_keeps_its_room_off_a_season_and_inside_a_day():
    chapter = dict(LANCRY_BOTTLE)
    assert engine.bottle_room({"chapter": chapter}) == "rue_de_lancry", "a life without a season"
    gap_day = {"chapter": chapter, "season_script": {"brief": {"gap": {"id": "g1"}, "today": {}}}}
    assert engine.bottle_room(gap_day) is None
    later_act = {**gap_day, "act": {"shape": "bottle", "room": "user_apartment"}}
    assert engine.bottle_room(later_act) == "user_apartment", "a later act stays in today's room"
    first = {"location_id": "user_apartment", "lead_id": "lila_bonnet"}
    context = story_split.act_context(
        {**_context(), "chapter": chapter}, {"location_id": "user_apartment", "character_id": "lila_bonnet"}, "soir"
    )
    assert context["act"]["room"] == first["location_id"], "the act's room is today's, not the chapter's first"


#: A day with a new rule (the B1 night of 18 Nov: «Le plus-que-parfait»).
NEW_RULE = {
    "introduce": {
        "unit_id": "b1_plus_que_parfait",
        "title_fr": "Le plus-que-parfait : le passé du passé",
        "examples": ["Quand Léa est arrivée, ses amis étaient déjà partis."],
        "detectors": [r"\b(?:avais|avait|étais|était)\s+\w+é\b"],
        "coach_id": "lila_bonnet",
    },
    "weave": [],
}


def _day(**extra) -> dict:
    context = _context()
    context["season_script"]["brief"]["registers"] = {"lila_bonnet": "tu", "marin_leveque": "vous"}
    context["learner"] = {"address": "neutral"}
    context.update(extra)
    return context


def test_the_brief_for_a_day_with_a_new_rule_says_a_cast_member_says_it():
    from app.services.living_story import GRAMMAR_PLAN_KEY

    checked = story_split.planner_payload(_day(**{GRAMMAR_PLAN_KEY: NEW_RULE}), [])["brief"]["today"]["checked"]
    assert checked == [
        "Someone on the page says today's form «Le plus-que-parfait : le passé du passé» once, in "
        "their own dialogue (as in «Quand Léa est arrivée, ses amis étaient déjà partis.»), before "
        "the question to the learner."
    ]
    today = story_split.author_payload(_day(**{GRAMMAR_PLAN_KEY: NEW_RULE}), _plan(), [])["today"]
    assert today[0].startswith("lila_bonnet says today's form «Le plus-que-parfait"), "the coach, when on the page"
    # A day without a new rule adds nothing to the planner's brief.
    assert "checked" not in story_split.planner_payload(_day(), [])["brief"]["today"]


def test_the_brief_for_a_tu_character_says_the_narration_s_register():
    today = story_split.author_payload(_day(), _plan(), [])["today"]
    assert "lila_bonnet says tu to the learner; premise_fr and the captions say tu too, or address nobody." in today
    vous = story_split.author_payload(_day(), _plan(lead_id="marin_leveque", cast=["marin_leveque"]), [])["today"]
    assert "marin_leveque says vous to the learner; premise_fr and the captions address nobody." in vous
    assert any("«C'est vous, l'héritage ?»" in line for line in vous), "the example in the lead's register"


def test_the_brief_says_a_new_chapter_needs_its_title_and_no_gendered_noun():
    opening = _plan(chapter={"question": "Le billet va-t-il changer ?", "developments": ["Oui.", "Non."]})
    today = story_split.author_payload(_day(), opening, [])["today"]
    assert (
        "This page opens a chapter: chapter_title_fr names it and chapter_question_fr asks "
        "plan.chapter.question in French."
    ) in today
    assert not any("opens a chapter" in line for line in story_split.author_payload(_day(), _plan(), [])["today"])
    assert any("never l'héritier or l'héritière" in line for line in today)
    feminine = story_split.author_payload(_day(learner={"address": "feminine"}), _plan(), [])["today"]
    assert "The learner is addressed as a woman: every noun, agreement and pet name for them says so." in feminine


def test_the_prompts_say_the_checks_come_first():
    assert "brief.today.checked, when present, is what today's page is checked for" in story_split.PLANNER
    author = story_split.AUTHOR
    assert author.index("today lists what this page is checked for") < author.index("THE PAGE")
    # The concept line no longer reads as optional («if a line … can carry it»).
    assert "if a line the situation needs can carry it" not in author
