"""WP-06 — grounded story consequences.

A daily journey is a **side scene**: it may add a bounded, grounded callback to
the existing serial memory, but it may never complete an episode, advance the
thread, move an arc stage, roll a season over, or write an outcome key the brief
did not declare. These tests pin exactly that, plus the once-only guarantee.
"""
from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.services import journey_content as jc_content
from app.services import journey_conversation as jc
from app.services.graphic_novel import GRAPHIC_NOVEL_PROMPT_VERSION
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    InputMode,
    ScenarioBrief,
    StoryOutcomeProposal,
    effect_source_key,
)
from app.services.serial import SerialThreadService
from app.services.serial_arc_planner import SEASON_FINALE_ARC_ID


@pytest.fixture(autouse=True)
def _clear_content_cache():
    jc_content.reset_content_cache()
    yield
    jc_content.reset_content_cache()


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@journey.test",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _thread(
    db_session,
    user: User,
    *,
    episode_index: int = 3,
    episode_status: str | None = "available",
    kind: str = "feuilleton",
    brief_payload: dict | None = None,
    scene_prompt_version: str | None = None,
    state: dict | None = None,
) -> tuple[SerialThread, SerialEpisode | None]:
    world = SerialThreadService._load_world_bible()
    thread = SerialThread(
        id=uuid4(),
        user_id=user.id,
        status="active",
        world_bible=world,
        state=state or {},
        news_seed={},
        current_episode_index=episode_index,
    )
    db_session.add(thread)
    db_session.flush()

    episode = None
    if episode_status is not None:
        scene_id = None
        if scene_prompt_version is not None:
            scene = GraphicNovelScene(
                id=uuid4(),
                user_id=user.id,
                serial_thread_id=thread.id,
                episode_index=episode_index,
                status="available",
                cadence="serial",
                title="Le Mistral",
                brief="brief",
                selected_concept_ids=[],
                target_errata_ids=[],
                target_vocabulary_ids=[],
                source_snapshot={},
                script_payload={},
                recap_payload={},
                cache_key=str(uuid4())[:32],
                prompt_version=scene_prompt_version,
                image_model="none",
                image_quality="low",
            )
            db_session.add(scene)
            db_session.flush()
            scene_id = scene.id
        episode = SerialEpisode(
            id=uuid4(),
            thread_id=thread.id,
            episode_index=episode_index,
            kind=kind,
            scene_id=scene_id,
            location_id="le_mistral",
            hook={},
            hook_from_previous={},
            state_delta={},
            brief_payload=brief_payload or {"location_id": "le_mistral"},
            status=episode_status,
        )
        db_session.add(episode)
    db_session.commit()
    db_session.refresh(thread)
    return thread, episode


def _brief(db_session, user, key: CapabilityKey = CapabilityKey.ORDER_AT_CAFE) -> ScenarioBrief:
    brief = jc_content.resolve_scenario_brief(db_session, user=user, scenario_key=key)
    assert isinstance(brief, ScenarioBrief)
    return brief


def _apply(db_session, user, brief, *, journey_id=None, outcome_key="served_at_terrace",
           callback="un thé en terrasse", character_id=None):
    journey_id = journey_id or uuid4()
    return jc.apply_story_outcome(
        db_session,
        user=user,
        journey_id=journey_id,
        scenario=brief,
        proposal=StoryOutcomeProposal(
            outcome_key=outcome_key,
            callback_fr=callback,
            character_id=character_id or brief.character_id,
        ),
        source_key=jc.story_outcome_source_key(journey_id),
    )


def _relationship(db_session, thread, character_id="margaux_barman") -> dict:
    db_session.refresh(thread)
    return dict((thread.state or {}).get("relationships", {}).get(character_id) or {})


# --------------------------------------------------------------------------
# Binding and the happy path
# --------------------------------------------------------------------------


def test_a_bound_journey_records_the_callback_on_the_current_beat(db_session):
    user = _user(db_session)
    thread, episode = _thread(db_session, user)
    brief = _brief(db_session, user)
    assert brief.serial_thread_id == str(thread.id)
    assert brief.is_authored_fallback is False

    ref = _apply(db_session, user, brief)
    db_session.commit()

    assert ref.applied is True
    assert ref.already_applied is False
    assert ref.outcome_key == "served_at_terrace"
    assert ref.serial_thread_id == str(thread.id)
    assert ref.serial_episode_id == str(episode.id)
    assert ref.callback_fr == "un thé en terrasse"

    relationship = _relationship(db_session, thread)
    assert relationship["closeness"] == 1
    assert relationship["callbacks"] == ["un thé en terrasse"]
    assert "terrace" in relationship["last_summary"] or "terrasse" in relationship["last_summary"]


def test_the_callback_is_eligible_for_a_later_serial_beat(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    _apply(db_session, user, brief)
    db_session.commit()
    db_session.refresh(thread)

    service = SerialThreadService(db_session)
    payload = service._relationship_payload(thread=thread, character_ids=["margaux_barman"])
    assert payload["margaux_barman"]["callbacks"] == ["un thé en terrasse"]
    assert "un thé en terrasse" in str(service.cast_payload(thread))
    story_so_far = service._story_so_far_text(thread)
    assert "Daily journey" in story_so_far
    assert "Mistral" in story_so_far or "café" in story_so_far


def test_apply_story_outcome_does_not_commit(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    ref = _apply(db_session, user, brief)
    assert ref.applied is True

    db_session.rollback()
    db_session.refresh(thread)
    assert (thread.state or {}).get("journey_outcomes") in (None, {})
    assert not (thread.state or {}).get("relationships", {}).get("margaux_barman", {}).get(
        "callbacks"
    )


# --------------------------------------------------------------------------
# Once only
# --------------------------------------------------------------------------


def test_a_duplicate_finish_changes_nothing_a_second_time(db_session):
    user = _user(db_session)
    thread, episode = _thread(db_session, user)
    brief = _brief(db_session, user)
    journey_id = uuid4()

    first = _apply(db_session, user, brief, journey_id=journey_id)
    db_session.commit()
    before = _relationship(db_session, thread)
    story_before = list((thread.state or {}).get("story_so_far") or [])

    second = _apply(db_session, user, brief, journey_id=journey_id)
    db_session.commit()
    after = _relationship(db_session, thread)

    assert first.already_applied is False
    assert second.already_applied is True
    assert second.applied is True
    assert second.serial_episode_id == str(episode.id)
    assert after == before
    assert after["closeness"] == 1
    assert list((thread.state or {}).get("story_so_far") or []) == story_before


def test_two_different_journeys_each_get_their_own_ledger_entry(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    first_id, second_id = uuid4(), uuid4()
    _apply(db_session, user, brief, journey_id=first_id, callback="un thé en terrasse")
    _apply(
        db_session,
        user,
        brief,
        journey_id=second_id,
        outcome_key="takeaway",
        callback="un café à emporter",
    )
    db_session.commit()

    ledger = (thread.state or {})["journey_outcomes"]
    assert set(ledger) == {
        effect_source_key(journey_id=first_id, effect="story_outcome"),
        effect_source_key(journey_id=second_id, effect="story_outcome"),
    }
    assert _relationship(db_session, thread)["callbacks"] == [
        "un thé en terrasse",
        "un café à emporter",
    ]
    assert _relationship(db_session, thread)["closeness"] == 2


def test_the_source_key_must_belong_to_the_journey(db_session):
    user = _user(db_session)
    _thread(db_session, user)
    brief = _brief(db_session, user)

    with pytest.raises(ValueError, match="does not belong to journey"):
        jc.apply_story_outcome(
            db_session,
            user=user,
            journey_id=uuid4(),
            scenario=brief,
            proposal=StoryOutcomeProposal(outcome_key="takeaway"),
            source_key=jc.story_outcome_source_key(uuid4()),
        )


# --------------------------------------------------------------------------
# A side scene is not an episode completion
# --------------------------------------------------------------------------


def test_a_side_scene_never_advances_the_episode_or_the_thread(db_session):
    user = _user(db_session)
    thread, episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    _apply(db_session, user, brief)
    db_session.commit()
    db_session.refresh(thread)
    db_session.refresh(episode)

    assert thread.current_episode_index == 3
    assert episode.status == "available"
    assert episode.completed_at is None
    assert episode.state_delta == {}
    assert (thread.state or {}).get("episodes_completed") in (None, 0)
    assert (thread.state or {}).get("arcs") in (None, {})
    assert SerialThreadService(db_session).current_episode(thread).id == episode.id


def test_an_episode_the_thread_has_moved_past_is_not_bound(db_session):
    user = _user(db_session)
    thread, episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    # An unrelated unread episode: the thread advanced between planning and finish.
    thread.current_episode_index = 4
    db_session.add(thread)
    db_session.commit()

    ref = _apply(db_session, user, brief)
    db_session.commit()
    db_session.refresh(episode)

    assert ref.applied is True
    assert ref.serial_episode_id is None
    assert episode.status == "available"
    assert _relationship(db_session, thread)["callbacks"] == ["un thé en terrasse"]


def test_a_superseded_feuilleton_scene_is_not_bound(db_session):
    user = _user(db_session)
    thread, episode = _thread(db_session, user, scene_prompt_version="feuilleton-2025-01")
    brief = _brief(db_session, user)
    brief = replace(brief, serial_thread_id=str(thread.id), serial_episode_id=str(episode.id))

    ref = _apply(db_session, user, brief)
    db_session.commit()
    db_session.refresh(episode)

    assert ref.applied is True
    assert ref.serial_episode_id is None
    assert episode.scene_id is not None
    assert episode.status == "available"
    assert _relationship(db_session, thread)["callbacks"] == ["un thé en terrasse"]


def test_a_current_contract_scene_is_still_bound(db_session):
    user = _user(db_session)
    thread, episode = _thread(
        db_session, user, scene_prompt_version=GRAPHIC_NOVEL_PROMPT_VERSION
    )
    brief = _brief(db_session, user)

    ref = _apply(db_session, user, brief)
    db_session.commit()

    assert ref.serial_episode_id == str(episode.id)


def test_a_season_finale_is_never_consumed_or_rolled_over_by_a_journey(db_session):
    user = _user(db_session)
    thread, episode = _thread(
        db_session,
        user,
        brief_payload={
            "location_id": "le_mistral",
            "season_finale": True,
            "a_plot": {"arc_id": SEASON_FINALE_ARC_ID, "advance_on_completion": True},
        },
    )
    world_before = dict(thread.world_bible or {})
    brief = _brief(db_session, user)
    brief = replace(brief, serial_thread_id=str(thread.id), serial_episode_id=str(episode.id))

    ref = _apply(db_session, user, brief)
    db_session.commit()
    db_session.refresh(thread)
    db_session.refresh(episode)

    assert ref.applied is True
    assert ref.serial_episode_id is None
    assert episode.status == "available"
    assert thread.current_episode_index == 3
    state = thread.state or {}
    assert state.get("season_finale_completed") is None
    assert state.get("previous_seasons") is None
    assert state.get("season_complete") is None
    assert thread.world_bible == world_before
    assert _relationship(db_session, thread)["callbacks"] == ["un thé en terrasse"]


@pytest.mark.parametrize("status", ["generating", "delayed", "completed", "planned"])
def test_an_episode_that_is_not_readable_is_not_bound(db_session, status):
    user = _user(db_session)
    thread, episode = _thread(db_session, user, episode_status=status)

    # WP-03 already refuses to bind these, so the brief arrives as an authored
    # fallback. Force the bound shape to prove the serial-side guard as well.
    unbound = _brief(db_session, user)
    assert unbound.is_authored_fallback is True
    assert unbound.serial_episode_id is None
    brief = replace(
        unbound,
        serial_thread_id=str(thread.id),
        serial_episode_id=str(episode.id),
        is_authored_fallback=False,
    )

    ref = _apply(db_session, user, brief)
    db_session.commit()
    db_session.refresh(episode)

    assert ref.applied is True
    assert ref.serial_episode_id is None
    assert episode.status == status
    assert episode.completed_at is None
    assert _relationship(db_session, thread)["callbacks"] == ["un thé en terrasse"]


# --------------------------------------------------------------------------
# Authored side scenes and ownership
# --------------------------------------------------------------------------


def test_an_authored_fallback_writes_nothing_to_the_serial_ledger(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user, episode_status=None)
    brief = _brief(db_session, user)
    assert brief.is_authored_fallback is True
    assert brief.serial_thread_id is None

    ref = _apply(db_session, user, brief)
    db_session.commit()
    db_session.refresh(thread)

    assert ref.applied is False
    assert ref.serial_thread_id is None
    assert ref.callback_fr == "un thé en terrasse"
    assert (thread.state or {}) == {}


def test_a_thread_owned_by_someone_else_is_never_touched(db_session):
    owner = _user(db_session)
    intruder = _user(db_session)
    thread, _episode = _thread(db_session, owner)
    brief = _brief(db_session, owner)

    ref = _apply(db_session, intruder, brief)
    db_session.commit()
    db_session.refresh(thread)

    assert ref.applied is False
    assert (thread.state or {}).get("journey_outcomes") in (None, {})


# --------------------------------------------------------------------------
# Typed keys and canonical characters
# --------------------------------------------------------------------------


def test_an_arbitrary_outcome_key_never_reaches_the_ledger(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    ref = _apply(db_session, user, brief, outcome_key="margaux_gives_you_the_bar")
    db_session.commit()
    db_session.refresh(thread)

    assert ref.outcome_key == "not_ordered"
    ledger = list((thread.state or {})["journey_outcomes"].values())
    assert [row["outcome_key"] for row in ledger] == ["not_ordered"]
    assert "margaux_gives_you_the_bar" not in str(thread.state)


def test_an_unknown_character_falls_back_to_the_canonical_one(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    ref = _apply(db_session, user, brief, character_id="margaux_the_ghost")
    db_session.commit()
    db_session.refresh(thread)

    assert ref.applied is True
    relationships = (thread.state or {})["relationships"]
    assert "margaux_the_ghost" not in relationships
    assert relationships["margaux_barman"]["callbacks"] == ["un thé en terrasse"]


def test_a_scene_with_no_canonical_character_writes_nothing(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = replace(_brief(db_session, user), character_id="nobody_at_all")

    ref = _apply(db_session, user, brief, character_id="also_nobody")
    db_session.commit()
    db_session.refresh(thread)

    assert ref.applied is False
    assert (thread.state or {}).get("relationships") in (None, {})


def test_a_neutral_outcome_records_the_fact_without_raising_closeness(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user, CapabilityKey.ARRANGE_MEETING)
    brief = replace(brief, serial_thread_id=str(thread.id), is_authored_fallback=False)

    ref = _apply(
        db_session,
        user,
        brief,
        outcome_key="meeting_postponed",
        callback="rendez-vous reporté",
    )
    db_session.commit()

    assert ref.applied is True
    relationship = _relationship(db_session, thread, "lila_bonnet")
    assert relationship["closeness"] == 0
    assert relationship["callbacks"] == ["rendez-vous reporté"]


def test_existing_relationship_bounds_still_apply(db_session):
    """Closeness is clamped at 5 and the tu switch uses the existing rule."""

    user = _user(db_session)
    thread, _episode = _thread(
        db_session,
        user,
        state={"relationships": {"margaux_barman": {"closeness": 4, "register": "vous"}}},
    )
    brief = _brief(db_session, user)

    _apply(db_session, user, brief, journey_id=uuid4())
    db_session.commit()
    relationship = _relationship(db_session, thread)
    assert relationship["closeness"] == 5
    assert relationship["register"] == "tu"

    _apply(db_session, user, brief, journey_id=uuid4(), callback="un café au comptoir")
    db_session.commit()
    assert _relationship(db_session, thread)["closeness"] == 5


def test_the_ledger_is_bounded(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    for _ in range(SerialThreadService.JOURNEY_OUTCOME_MAX + 5):
        _apply(db_session, user, brief, journey_id=uuid4())
    db_session.commit()
    db_session.refresh(thread)

    ledger = (thread.state or {})["journey_outcomes"]
    assert len(ledger) == SerialThreadService.JOURNEY_OUTCOME_MAX
    assert len((thread.state or {})["relationships"]["margaux_barman"]["callbacks"]) <= 5


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "outcome_key", "callback"),
    [
        ("Un thé en terrasse, s'il vous plaît.", "served_at_terrace", "un thé en terrasse"),
        ("Un café au comptoir, s'il vous plaît.", "served_at_counter", "un café au comptoir"),
        ("Un thé à emporter, merci.", "takeaway", "un thé à emporter"),
    ],
)
def test_a_full_respond_then_finish_lands_the_learners_own_choice(
    db_session, text, outcome_key, callback
):
    user = _user(db_session)
    thread, episode = _thread(db_session, user)
    brief = _brief(db_session, user)
    journey_id = uuid4()

    evaluation = jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=brief.response_task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )
    assert evaluation.consequence is not None
    assert evaluation.consequence.outcome_key == outcome_key
    assert evaluation.consequence.callback_fr == callback

    ref = jc.apply_story_outcome(
        db_session,
        user=user,
        journey_id=journey_id,
        scenario=brief,
        proposal=evaluation.consequence,
        source_key=jc.story_outcome_source_key(journey_id),
    )
    db_session.commit()

    assert ref.applied is True
    assert ref.outcome_key == outcome_key
    assert ref.serial_episode_id == str(episode.id)
    assert ref.callback_fr == callback
    assert jc.resolution_line(brief, outcome_key)
    assert _relationship(db_session, thread)["callbacks"] == [callback]

    db_session.refresh(episode)
    assert episode.status == "available"
    assert thread.current_episode_index == 3


def test_a_voice_failure_at_the_end_leaves_the_story_untouched(db_session):
    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)

    evaluation = jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=brief.response_task,
        answer=AttemptAnswer(mode=InputMode.VOICE, text=""),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )
    db_session.commit()
    db_session.refresh(thread)

    assert evaluation.consequence is None
    assert evaluation.turn_consumed is False
    assert (thread.state or {}) == {}


def test_a_second_effect_label_for_the_same_journey_is_still_once_only(db_session):
    """One journey warms the story once, whatever effect label the caller uses.

    The frozen grammar is ``journey:{journey_id}:{effect}``; the caller is free
    to name the effect, so dedup is scoped to the journey, not the label.
    """

    user = _user(db_session)
    thread, _episode = _thread(db_session, user)
    brief = _brief(db_session, user)
    journey_id = uuid4()

    def _call(outcome_key, callback):
        return jc.apply_story_outcome(
            db_session,
            user=user,
            journey_id=journey_id,
            scenario=brief,
            proposal=StoryOutcomeProposal(
                outcome_key=outcome_key,
                callback_fr=callback,
                character_id=brief.character_id,
            ),
            source_key=effect_source_key(
                journey_id=journey_id, effect=f"story:{outcome_key}"
            ),
        )

    first = _call("served_at_terrace", "un thé en terrasse")
    second = _call("takeaway", "un café à emporter")
    db_session.commit()

    assert first.already_applied is False
    assert second.already_applied is True
    assert second.outcome_key == "served_at_terrace"
    relationship = _relationship(db_session, thread)
    assert relationship["closeness"] == 1
    assert relationship["callbacks"] == ["un thé en terrasse"]
    assert len((thread.state or {})["journey_outcomes"]) == 1


def test_the_canonical_effect_key_is_exposed_for_callers(db_session):
    journey_id = uuid4()
    assert jc.story_outcome_source_key(journey_id) == effect_source_key(
        journey_id=journey_id, effect="story_outcome"
    )
