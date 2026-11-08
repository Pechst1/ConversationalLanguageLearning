"""Step 4 of the 3D overhaul: «Die Geschichte bestellt, die Schmiede baut».

Le Quartier should grow with the story: small things that stay after a page (Gus's
petition on Le Mistral's window), and slowly the rooms, shops and streets the pages
name. Every page now says what it leaves in the quarter (``SceneDraft.leaves``, at
most two marks); the life keeps them (``live["world_marks"]``); the server gives the
forge what the season's lives have left, merged (``GET /story-engine/world-orders``),
and each learner the world their own story set (``GET /story-engine/world-state``).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.services import living_story as engine
from app.services import story_split
from app.services.season import frontier
from tests import test_journey_end_to_end as support
from tests.test_season_one import _play, _thread, season_on  # noqa: F401 - fixture
from tests.test_story_acts_morning import acts_writer  # noqa: F401 - fixture
from tests.test_story_split import _context as _split_context
from tests.test_story_split import _plan, split_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

PETITION = {
    "kind": "thing",
    "name_fr": "la pétition de Gus",
    "location_id": "le_mistral",
    "look": "A handwritten petition taped inside Le Mistral's front window.",
}
BAKERY = {
    "kind": "place",
    "name_fr": "la boulangerie de Mme Diallo",
    "location_id": None,
    "look": "A narrow bakery with a blue front, two doors down the quai.",
}


def _scene(**over) -> engine.SceneDraft:
    from tests.test_living_story import _wp62_scene

    return _wp62_scene(**over)


# ---------------------------------------------------------------------------
# A page's marks
# ---------------------------------------------------------------------------


def test_a_page_leaves_at_most_two_marks_and_a_malformed_one_never_costs_the_page():
    marks = engine.lenient_marks(
        [
            {"kind": "person", "name_fr": "Gus"},  # not a mark
            {"kind": "thing", "name_fr": ""},  # nameless
            "la pétition",  # not an object
            PETITION,
            BAKERY,
            {"kind": "thing", "name_fr": "un troisième", "location_id": "le_mistral"},
        ]
    )
    assert [mark.name_fr for mark in marks] == ["la pétition de Gus", "la boulangerie de Mme Diallo"]
    assert engine.lenient_marks("une pétition") == []
    assert _scene(leaves="une pétition").leaves == []
    assert [mark.kind for mark in _scene(leaves=[PETITION]).leaves] == ["thing"]
    # a page that leaves nothing is the usual page
    assert _scene().leaves == []


def test_the_life_keeps_what_its_pages_left_and_counts_what_the_story_comes_back_to():
    known = {"le_mistral", "stairwell"}
    first = engine.world_marks_after_scene(
        [],
        draft=_scene(
            leaves=[
                PETITION,
                {"kind": "thing", "name_fr": "une clé", "location_id": "berlin"},  # nowhere the world knows
            ]
        ),
        known_locations=known,
        event_id="e1",
        day=3,
        scene_id="s1",
        date="2026-11-01",
    )
    assert len(first) == 1
    row = first[0]
    assert row["id"] == "e1:mark:0" and row["kind"] == "thing" and row["location_id"] == "le_mistral"
    assert row["times"] == 1 and row["day"] == row["first_day"] == 3 and row["scene_id"] == "s1"

    # a place the world has no id for is still asked for, with no location
    second = engine.world_marks_after_scene(
        first,
        draft=_scene(n=1, leaves=[{**BAKERY, "location_id": "boulangerie_diallo"}]),
        known_locations=known,
        event_id="e2",
        day=4,
    )
    assert [mark["name_fr"] for mark in second] == ["la pétition de Gus", "la boulangerie de Mme Diallo"]
    assert second[1]["location_id"] is None

    # the same thing left again counts once more and moves to the end
    third = engine.world_marks_after_scene(
        second,
        draft=_scene(n=2, leaves=[{**PETITION, "name_fr": "La  pétition de Gus"}]),
        known_locations=known,
        event_id="e3",
        day=7,
    )
    assert [mark["name_fr"] for mark in third] == ["la boulangerie de Mme Diallo", "la pétition de Gus"]
    assert third[-1]["times"] == 2 and third[-1]["day"] == 7 and third[-1]["first_day"] == 3
    assert first[0]["times"] == 1, "the ledger it was given is not changed"

    # the life keeps its newest marks
    many = []
    for n in range(engine.WORLD_MARK_LEDGER_LIMIT + 5):
        many = engine.world_marks_after_scene(
            many,
            draft=_scene(leaves=[{"kind": "place", "name_fr": f"lieu {n}"}]),
            known_locations=known,
            event_id=f"e{n}",
            day=n,
        )
    assert len(many) == engine.WORLD_MARK_LEDGER_LIMIT and many[-1]["name_fr"] == f"lieu {engine.WORLD_MARK_LEDGER_LIMIT + 4}"


def test_the_planner_s_marks_reach_the_page_it_assembles():
    context = _split_context()
    text = story_split.PageText.model_validate(
        {
            "title_fr": "La boîte",
            "premise_fr": "Une boîte.",
            "panels": [
                {"visual_direction": "A box.", "dialogue": []},
                {"visual_direction": "Lila.", "dialogue": [{"character_id": "lila_bonnet", "text_fr": "Regarde."}]},
            ],
            "opening_line_fr": "C'est qui ?",
            "suggested_response_fr": "C'est Marin.",
        }
    )
    plan = _plan(leaves=[PETITION, {"kind": "nope"}, BAKERY])
    assert [mark.name_fr for mark in plan.leaves] == ["la pétition de Gus", "la boulangerie de Mme Diallo"]
    draft = engine.SceneDraft.model_validate(story_split.assemble(context, plan, text, None))
    assert [mark.model_dump() for mark in draft.leaves] == [PETITION, BAKERY]
    assert engine.SceneDraft.model_validate(story_split.assemble(context, _plan(), text, None)).leaves == []


def test_both_writers_are_told_what_a_mark_is():
    assert "leaves is what this page" in engine.DIRECTOR
    assert '"leaves"' in story_split.PLANNER


# ---------------------------------------------------------------------------
# Through a real day
# ---------------------------------------------------------------------------


def _learner(assembled_client, db_session, *, day: int = 13, full_name: str | None = None):
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    email = f"marks-{uuid.uuid4()}@example.com"
    headers = support.register(assembled_client, email, cefr="A2.1")
    user = db_session.scalar(select(User).where(User.email == email))
    if full_name:
        user.full_name = full_name
    jump_to_day(db_session, user, day=day)
    db_session.commit()
    return user, headers


def test_a_season_page_s_marks_are_kept_and_given_to_the_quarter_and_the_forge(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    provider = season_on
    original = provider._season_draft

    def leaving(context):
        return {**original(context), "leaves": [PETITION, BAKERY]}

    provider._season_draft = leaving
    monkeypatch.setattr(frontier, "_orders_cache", {})
    user, headers = _learner(assembled_client, db_session)
    d = support.Driver(assembled_client, headers, db=db_session)
    _play(d, provider, clock, "Je reste encore un peu.")

    live = (_thread(db_session, user.id).state or {})[engine.STATE_KEY]
    marks = live["world_marks"]
    assert [(mark["kind"], mark["name_fr"], mark["location_id"]) for mark in marks] == [
        ("thing", "la pétition de Gus", "le_mistral"),
        ("place", "la boulangerie de Mme Diallo", None),
    ]

    # the learner's own quarter: the flags their story set and what it left
    response = assembled_client.get("/api/v1/story-engine/world-state", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["season"] == "s1" and isinstance(body["flags"], dict)
    assert [mark["name_fr"] for mark in body["marks"]] == ["la pétition de Gus", "la boulangerie de Mme Diallo"]
    assert assembled_client.get("/api/v1/story-engine/world-state").status_code == 401

    # the forge's orders: what the lives left, with no learner in it
    orders = assembled_client.get("/api/v1/story-engine/world-orders").json()
    assert orders["season"] == "s1"
    petition = next(order for order in orders["orders"] if order["name_fr"] == "la pétition de Gus")
    assert petition == {**PETITION, "times": 1, "lives": 1}
    assert all(set(order) == {"kind", "name_fr", "location_id", "look", "times", "lives"} for order in orders["orders"])
    assert assembled_client.get("/api/v1/story-engine/world-orders?season=s9").status_code == 404
    assert assembled_client.get("/api/v1/story-engine/world-orders?season=../x").status_code == 422


def test_the_forge_reads_what_most_lives_left_first_and_never_a_learner_s_name(db_session, monkeypatch):
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.models.serial import SerialThread
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    def life(marks, *, full_name=None, memory=None):
        user = User(email=f"orders-{uuid.uuid4()}@example.com", hashed_password="t", timezone="UTC", full_name=full_name)
        db_session.add(user)
        db_session.flush()
        jump_to_day(db_session, user, day=13)
        thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == user.id))
        state = dict(thread.state or {})
        state[engine.STATE_KEY] = {**state[engine.STATE_KEY], "world_marks": marks, **({"memory": memory} if memory else {})}
        thread.state = state
        flag_modified(thread, "state")
        db_session.commit()

    life([{**PETITION, "times": 2}, BAKERY])
    life([PETITION])
    life([{"kind": "thing", "name_fr": "la lettre de Vincent", "location_id": "le_mistral", "look": ""}, "garbage"], full_name="Vincent Pechstein")
    # a short name is theirs too, matched word by word (never «li» inside «librairie»)
    life(
        [
            {"kind": "thing", "name_fr": "la lettre de Li", "location_id": "le_mistral", "look": ""},
            {"kind": "place", "name_fr": "la librairie du coin", "location_id": None, "look": ""},
        ],
        full_name="Li Wen",
    )
    # the name they gave the cast is theirs too
    life(
        [{"kind": "place", "name_fr": "l'atelier de Théo", "location_id": None, "look": ""}],
        memory={"facts": [{"key": "name", "value": "Théo", "fact_fr": "Il s'appelle Théo.", "known_by": ["lila_bonnet"]}]},
    )
    monkeypatch.setattr(frontier, "_orders_cache", {})
    orders = frontier.world_orders(db_session, "s1")["orders"]
    assert [(order["name_fr"], order["lives"], order["times"]) for order in orders] == [
        ("la pétition de Gus", 2, 3),
        ("la boulangerie de Mme Diallo", 1, 1),
        ("la librairie du coin", 1, 1),
    ]


def test_a_page_planned_ahead_of_time_carries_its_marks_to_the_day(assembled_client, db_session, journey_enabled, clock, split_on):  # noqa: F811
    """The night writes a gap day as plan, text and aids; the plan's marks go with the
    page it keeps for the learner's day, which settles them like a director's."""

    from app.services.journey_contracts import InputMode

    provider = split_on
    provider.critic_refusals_left = 0
    original = provider._plan
    box = {**PETITION, "name_fr": "la boîte de photos", "location_id": "user_apartment", "look": "A shoebox of Polaroids on Odile's bed."}

    def leaving(source):
        return {**original(source), "leaves": [box]}

    provider._plan = leaving
    user, _ = _learner(assembled_client, db_session, day=14)
    with engine.written_ahead_of_time():
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert not isinstance(brief, engine.ContentUnavailable), brief
    assert brief.story_context["draft"]["leaves"] == [box]
    assert [mark.name_fr for mark in engine.draft_model_for(brief.story_context).model_validate(brief.story_context["draft"]).leaves] == [
        "la boîte de photos"
    ]


@pytest.mark.parametrize("value", [None, {}, {"world_marks": "x"}])
def test_a_life_with_nothing_left_gives_an_empty_quarter(value):
    state = frontier.world_state(value or {})
    assert state["marks"] == [] and state["flags"] == {}


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_a_later_act_s_marks_are_kept_like_the_first_act_s(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch  # noqa: F811
):
    """«Le soir» is a page of the day like the first: what it leaves stays too."""

    from tests import test_story_acts_day as acts_day

    provider = acts_writer
    original = provider._plan

    def leaving(source):
        plan = original(source)
        if source.get("act"):
            plan["leaves"] = [{"kind": "thing", "name_fr": "la vieille radio", "location_id": plan["location_id"], "look": "An old radio on the zinc."}]
        return plan

    provider._plan = leaving
    user, d = acts_day._two_act_day(assembled_client, db_session, acts_writer, monkeypatch)
    d.play(answer=acts_day.ANSWER)
    assert d.finish("complete").status_code == 200
    live = (_thread(db_session, user.id).state or {})[engine.STATE_KEY]
    [mark] = [mark for mark in live.get("world_marks") or [] if mark["name_fr"] == "la vieille radio"]
    assert mark["event_id"].endswith(":story:act2") and mark["scene_id"]
