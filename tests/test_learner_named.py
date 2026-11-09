"""«Deine eigenen Worte bestellen beim Bau» (Vincent, 8 Nov): what the learner names in their
own words reaches the forge first.

A page already says what it leaves in Le Quartier (``SceneDraft.leaves``). The learner had
no say in it but through the writer: «on pourrait aller à la boulangerie» was a line in the
memory and nothing more. The ending that closes a scene now reports what the learner
themselves brought in (``SemanticTurn.named``: a place they named, a thing they brought),
kept only with their own words verbatim; the life keeps it as a mark counted in ``said``;
the forge's orders put those first.
"""

from __future__ import annotations

from app.services import living_story as engine
from app.services import story_lanes, story_memory
from app.services.season import frontier
from tests.test_living_story_longitudinal import (  # noqa: F401 - fixtures
    TurnScript,
    assembled_client,
    clock,
    driver,
    journey_enabled,
    live_state,
    play_day,
    provider,
)
from tests.test_story_memory_days import one_exchange  # noqa: F401 - fixture

SEASON_PLACES = {
    "le_mistral": "Le Mistral",
    "boulangerie": "La boulangerie de Mme Diallo",
    "odile_flat": "L'appartement d'Odile",
    "user_apartment": "Ton studio",
}


def _scene(**over) -> engine.SceneDraft:
    from tests.test_living_story import _wp62_scene

    return _wp62_scene(**over)


def test_the_ending_s_named_list_is_lenient_and_kept_only_in_the_learner_s_words():
    named = story_memory.lenient_named(
        [
            {"kind": "person", "name_fr": "Gus", "quote": "Gus"},  # not a place or a thing
            {"kind": "Place", "name_fr": "la boulangerie", "quote": "on va à la boulangerie ?"},
            "la boulangerie",  # not an object
            {"kind": "thing", "name_fr": "", "quote": "des fleurs"},  # nameless
            {"kind": "thing", "name_fr": "des fleurs pour Odile", "quote": "j'ai des fleurs"},
            {"kind": "thing", "name_fr": "un troisième", "quote": "un troisième"},
        ]
    )
    assert [(item.kind, item.name_fr) for item in named] == [("place", "la boulangerie"), ("thing", "des fleurs pour Odile")]
    texts = ["Bonjour ! On va à la boulangerie ?"]
    assert [item.name_fr for item in story_memory.grounded_named(named, texts)] == ["la boulangerie"]
    assert story_memory.grounded_named(named, []) == []
    # a turn that reports nothing (or rubbish) is the usual turn
    assert engine.SemanticTurn.model_validate(_turn(named="la boulangerie")).named == []
    assert engine.SemanticTurn.model_validate(_turn()).named == []


def _turn(**over) -> dict:
    return {
        "outcome": "met",
        "understood_intent": "They answered.",
        "evidence_quotes": ["oui"],
        "reply_fr": "D'accord.",
        "needs_clarification": False,
        **over,
    }


def test_what_the_learner_named_becomes_a_mark_where_the_world_can_build_it():
    named = story_memory.lenient_named(
        [
            {"kind": "place", "name_fr": "la boulangerie", "quote": "la boulangerie"},
            {"kind": "thing", "name_fr": "des fleurs pour Odile", "quote": "des fleurs"},
        ]
    )
    marks = engine.learner_marks(named, location_id="odile_flat", places=SEASON_PLACES)
    # «la boulangerie» is the season's bakery: the forge finds it by its id
    assert [mark.model_dump() for mark in marks] == [
        {"kind": "place", "name_fr": "la boulangerie", "location_id": "boulangerie", "look": ""},
        {"kind": "thing", "name_fr": "des fleurs pour Odile", "location_id": "odile_flat", "look": ""},
    ]
    # a place the world has no id for stays a name; the scene's own place is no order
    other = story_memory.lenient_named(
        [
            {"kind": "place", "name_fr": "un petit marché", "quote": "un petit marché"},
            {"kind": "place", "name_fr": "le Mistral", "quote": "au Mistral"},
        ]
    )
    assert [(mark.name_fr, mark.location_id) for mark in engine.learner_marks(other, location_id="le_mistral", places=SEASON_PLACES)] == [
        ("un petit marché", None)
    ]
    # a word two places share names neither
    two = {"a": "La rue de Lancry", "b": "La rue Bichat"}
    rue = story_memory.lenient_named([{"kind": "place", "name_fr": "la rue", "quote": "la rue"}])
    assert engine.learner_marks(rue, location_id=None, places=two)[0].location_id is None
    # a thing needs the scene's place to stand in
    assert engine.learner_marks(named[1:], location_id=None, places=SEASON_PLACES) == []


def test_the_life_counts_what_the_learner_said_apart_from_what_the_pages_left():
    draft = _scene(leaves=[{"kind": "place", "name_fr": "la boulangerie", "location_id": "boulangerie", "look": "Blue front."}])
    known = set(SEASON_PLACES)
    first = engine.world_marks_after_scene([], draft=draft, known_locations=known, event_id="e1", day=1)
    assert [(row["name_fr"], row["said"]) for row in first] == [("la boulangerie", 0)]
    said = [engine.WorldMark(kind="place", name_fr="La  boulangerie", location_id="boulangerie")]
    second = engine.world_marks_after_scene(first, draft=_scene(), known_locations=known, event_id="e2", day=2, named=said)
    [row] = second
    assert (row["times"], row["said"], row["look"]) == (2, 1, "Blue front.")
    fresh = engine.world_marks_after_scene(
        [], draft=_scene(), known_locations=known, event_id="e3", day=3,
        named=[engine.WorldMark(kind="thing", name_fr="des fleurs", location_id="odile_flat")],
    )
    assert [(row["kind"], row["said"], row["times"]) for row in fresh] == [("thing", 1, 1)]


def test_the_forge_reads_what_a_learner_said_before_what_more_pages_left(db_session, monkeypatch):
    import uuid

    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.models.serial import SerialThread
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    def life(marks):
        user = User(email=f"said-{uuid.uuid4()}@example.com", hashed_password="t", timezone="UTC")
        db_session.add(user)
        db_session.flush()
        jump_to_day(db_session, user, day=13)
        thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == user.id))
        state = dict(thread.state or {})
        state[engine.STATE_KEY] = {**state[engine.STATE_KEY], "world_marks": marks}
        thread.state = state
        flag_modified(thread, "state")
        db_session.commit()

    petition = {"kind": "thing", "name_fr": "la pétition de Gus", "location_id": "le_mistral", "look": ""}
    flowers = {"kind": "thing", "name_fr": "des fleurs", "location_id": "odile_flat", "look": ""}
    life([petition, {**flowers, "said": 1}])
    life([petition])
    monkeypatch.setattr(frontier, "_orders_cache", {})
    orders = frontier.world_orders(db_session, "s1")["orders"]
    assert [(order["name_fr"], order["lives"], order["said"]) for order in orders] == [
        ("des fleurs", 1, 1),
        ("la pétition de Gus", 2, 0),
    ]
    state = frontier.world_state({"world_marks": [petition, {**flowers, "said": 2}]})
    assert [mark["said"] for mark in state["marks"]] == [0, 2]


def test_both_turn_writers_are_told_what_the_learner_named():
    assert story_memory.NAMED_REPORT in engine.ACTOR
    assert story_memory.NAMED_REPORT in story_lanes.STORY
    assert "named" in story_lanes.StoryTurn.model_fields
    ending = story_lanes.StoryTurn.model_validate({"named": [{"kind": "place", "name_fr": "la boulangerie", "quote": "la boulangerie"}]})
    assert [item.name_fr for item in ending.named] == ["la boulangerie"]
    # the story lane's ending reaches the one turn the settle reads (its words are then
    # held to the learner's like the one actor's: ``_validate_turn``, run by ``validate_story``)
    tutor = story_lanes.TutorVerdict(outcome="met", evidence_quotes=["oui"])
    voice = story_lanes.VoiceReply(reply_fr="D'accord.", understood_intent="They agreed.", needs_clarification=False)
    assert [item.name_fr for item in story_lanes.merged_turn(tutor, voice, ending).named] == ["la boulangerie"]
    assert story_lanes.merged_turn(tutor, voice).named == []


def test_a_day_keeps_what_the_learner_named_in_their_own_words(
    assembled_client, db_session, journey_enabled, clock, provider, one_exchange  # noqa: F811
):
    d = driver(assembled_client, db_session)
    play_day(
        d,
        provider,
        answer="Oui, et après on pourrait aller à la boulangerie, j'ai faim.",
        turn=TurnScript(
            extra={
                "named": [
                    {"kind": "place", "name_fr": "la boulangerie", "quote": "on pourrait aller à la boulangerie"},
                    # not in the learner's words: never kept
                    {"kind": "thing", "name_fr": "un parapluie rouge", "quote": "j'ai un parapluie rouge"},
                ]
            }
        ),
    )
    marks = live_state(db_session, d).get("world_marks") or []
    assert [(mark["kind"], mark["name_fr"], mark["said"]) for mark in marks] == [("place", "la boulangerie", 1)]
