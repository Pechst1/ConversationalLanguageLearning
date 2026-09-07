"""Real API/DB integration with an injected provider; never calls live models."""

from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialEpisode, SerialThread
from app.services import living_story as engine
from tests import test_journey_end_to_end as support

Driver = support.Driver
register = support.register
assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


PREMISES = [
    "Romy cherche une idée pour une exposition dans le quartier.",
    "Le four du café est en panne le jour du marché.",
    "Un voisin veut vendre son vieux vélo et demande un prix.",
    "Le facteur a livré un colis pour quelqu'un d'autre.",
    "Une affiche annonce une soirée jeux vendredi.",
    "La pluie a inondé la cave de l'immeuble.",
    "Margaux cherche quelqu'un pour garder son chat ce week-end.",
]


OBJECTIVES = [
    "Suggest how you can help, or explain that you cannot.",
    "Propose an alternative for the market morning, or decline.",
    "Negotiate a price or say the bike does not interest you.",
    "Explain what happened to the parcel.",
    "Say whether you come on Friday and what you bring.",
    "Ask a neighbour for help, or offer yours.",
    "Accept or decline cat-sitting, and say when you are free.",
]


def draft(context, n=0):
    chapter = context.get("chapter") or {}
    return {
        "title_fr": f"Les affiches {n}",
        # Seven distinct premises and objectives: the engine rejects either one
        # overlapping any of the last five situations.
        "premise_fr": PREMISES[n % len(PREMISES)],
        "setup_native": "Romy is arranging a neighborhood exhibition.",
        "objective_native": OBJECTIVES[n % len(OBJECTIVES)],
        "objective_semantics": "Clearly express an offer or a refusal of help with the exhibition.",
        "character_id": "romy_tremblay",
        "location_id": "le_mistral",
        "causal_reason": "Continue the actual proposal from the previous exchange."
        if context.get("events")
        else "Romy invites the newcomer to help.",
        "source_event_ids": [e["id"] for e in context.get("events", [])[-1:]],
        "novelty_key": f"exhibition-task-{n}",
        "chapter": {
            k: chapter[k] for k in ("title_fr", "dramatic_question", "possible_developments")
        }
        if chapter and not chapter.get("resolved")
        else {
            "title_fr": f"Une exposition {n}",
            "dramatic_question": f"Comment organiser cette exposition {n} ?",
            "possible_developments": [
                "Trouver une salle.",
                "Inviter les voisins.",
                "Ouvrir les portes.",
            ],
        },
        "panels": [
            {
                "narration_fr": "La pluie glisse sur la vitre.",
                "dialogue": [],
                "visual_direction": "Wide shot of the café window, rain and evening light.",
            },
            {
                "narration_fr": "",
                "dialogue": [{"character_id": "romy_tremblay", "text_fr": "Vous avez une idée ?"}],
                "visual_direction": "Romy unfolds a blank poster at the counter.",
            },
        ],
        "opening_line_fr": "Vous pouvez nous aider ?",
        "suggested_response_fr": "Je peux apporter les affiches samedi.",
        "hint_native": "Say what you could bring.",
        "translation_native": "Can you help us?",
        "capability_key": None,
    }


def turn_fixture(text, *, close=False):
    return _turn(text, close=close)


def turn(payload, *, close=False):
    return _turn(payload["learner_text"], close=close)


def _turn(text, *, close=False):
    return {
        "outcome": "met",
        "understood_intent": "Learner offers to bring posters on Saturday.",
        "evidence_quotes": [text],
        "reply_fr": "Merci ! On prépare la salle ensemble.",
        "needs_clarification": False,
        "resolution_fr": "Romy note votre proposition pour samedi.",
        "summary_native": "You offered to bring posters on Saturday.",
        "callback_fr": "Vous apportez les affiches samedi.",
        "commitments": [{"text_fr": "Apporter les affiches samedi.", "source_quote": text}],
        "resolved_commitment_ids": [],
        "chapter_resolved": close,
        "demonstrated_target_ids": [],
    }


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.scenes = 0
        self.turns = 0
        self.reject = False
        self.transform = lambda schema, output: output

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        source = data["data"]
        self.calls.append((schema, deepcopy(source)))
        if schema == "SceneDraft":
            value = draft(source, self.scenes)
            self.scenes += 1
        elif schema == "SemanticTurn":
            self.turns += 1
            value = turn(source, close=self.turns % 4 == 0)
        else:
            value = {
                "accepted": not self.reject,
                "issues": ["contradiction"] if self.reject else [],
            }
        return SimpleNamespace(
            content=json.dumps(self.transform(schema, value)),
            model="fake-review",
            provider="test",
            total_tokens=30,
            cost=0.0,
        )


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    fake = FakeProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


def driver(client, db):
    email = f"story-{uuid4()}@example.com"
    headers = register(client, email)
    result = Driver(client, headers, db=db)
    result.user_id = support.learner_id(db, email)
    return result


def test_real_journey_publishes_same_scene_for_reader(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    before = len(provider.calls)
    offered = assembled_client.get("/api/v1/daily-journeys/today", headers=d.headers)
    assert offered.status_code == 200
    assert len(provider.calls) == before, "GET must never generate"
    d.create()
    assert d.journey["status"] == "active", d.journey
    assert d.journey["scenario"]["scenario_key"].startswith("story_")
    assert d.journey["scenario"]["scenario_key"] not in [
        "order_at_cafe",
        "arrange_meeting",
        "explain_delay",
    ]
    listed = assembled_client.get("/api/v1/story-engine/episodes", headers=d.headers).json()[
        "episodes"
    ]
    assert len(listed) == 1
    scene = listed[0]
    assert scene["journey_id"] == d.journey["id"]
    filtered = assembled_client.get(
        f"/api/v1/story-engine/episodes?journey_id={d.journey['id']}", headers=d.headers
    ).json()
    assert [item["id"] for item in filtered["episodes"]] == [scene["id"]]
    assert (
        assembled_client.get(
            f"/api/v1/story-engine/episodes?journey_id={uuid4()}", headers=d.headers
        ).json()["episodes"]
        == []
    )
    assert len(scene["panels"]) == 2
    assert scene["resolution"] is None
    assert "rubric" not in json.dumps(scene) and "suggested_response" not in json.dumps(scene)
    thread = db_session.get(SerialThread, UUID(d.journey["scenario"]["serial_thread_id"]))
    state_before = deepcopy(thread.state)
    position = assembled_client.put(
        f"/api/v1/story-engine/episodes/{scene['id']}/position",
        json={"panel_index": 1},
        headers=d.headers,
    )
    assert position.status_code == 200
    db_session.refresh(thread)
    assert thread.state == state_before
    assert (
        assembled_client.get(
            f"/api/v1/story-engine/episodes/{scene['id']}", headers=d.headers
        ).json()["panel_index"]
        == 1
    )
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")
    ended = assembled_client.get(
        f"/api/v1/story-engine/episodes/{scene['id']}", headers=d.headers
    ).json()
    assert ended["resolution"]["text_fr"] == "Romy note votre proposition pour samedi."
    db_session.refresh(thread)
    assert len(thread.state["living_story"]["events"]) == 1
    assert thread.current_episode_index == 1
    assert d.journey["recap"]["capability_evidence"] == [], (
        "A new objective must not invent a capability"
    )


def test_fourteen_days_causal_context_and_new_chapters(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    chapter_ids = set()
    for day in range(14):
        d.create()
        assert d.journey["status"] == "active", d.journey
        scene = assembled_client.get("/api/v1/story-engine/episodes", headers=d.headers).json()[
            "episodes"
        ][0]
        chapter_ids.add(scene["chapter"]["id"])
        d.play(answer=f"Je peux apporter les affiches samedi. Projet {day}.")
        d.finish("complete")
        clock.advance(days=1)
    contexts = [p for schema, p in provider.calls if schema == "SceneDraft"]
    assert len(contexts) == 14
    assert all(c["events"] and c["commitments"] for c in contexts[1:])
    assert len(chapter_ids) == 4
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    assert len(thread.state["living_story"]["events"]) == 14
    assert (
        len(
            list(
                db_session.scalars(
                    select(SerialEpisode).where(
                        SerialEpisode.status == "completed", SerialEpisode.thread_id == thread.id
                    )
                )
            )
        )
        == 14
    )


def test_generation_failure_never_serves_authored_scene(
    assembled_client, db_session, journey_enabled, clock, provider
):
    provider.reject = True
    d = driver(assembled_client, db_session)
    d.create(expect=(200,))
    assert d.journey["status"] == "unavailable"
    assert not d.journey["steps"]
    assert (
        db_session.scalar(select(GraphicNovelScene).where(GraphicNovelScene.user_id == d.user_id))
        is None
    )


def test_reader_is_owned_and_position_validated(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    d.create()
    scene = assembled_client.get("/api/v1/story-engine/episodes", headers=d.headers).json()[
        "episodes"
    ][0]
    # Dialogue lines carry the cast member's display name from the world bible,
    # so the reader never labels a speaker with a raw id such as "romy_tremblay".
    spoken = [line for panel in scene["panels"] for line in panel["dialogue"]]
    assert spoken and all(line["character_name"] == "Romane « Romy » Tremblay" for line in spoken)
    other = driver(assembled_client, db_session)
    route = f"/api/v1/story-engine/episodes/{scene['id']}"
    assert assembled_client.get(route, headers=other.headers).status_code == 404
    assert (
        assembled_client.put(
            route + "/position", json={"panel_index": 0}, headers=other.headers
        ).status_code
        == 404
    )
    for index in (-1, 2, 500, True):
        assert (
            assembled_client.put(
                route + "/position", json={"panel_index": index}, headers=d.headers
            ).status_code
            == 422
        )
    assert (
        assembled_client.get("/api/v1/story-engine/episodes", headers=other.headers).json()[
            "episodes"
        ]
        == []
    )


def test_turn_rejects_fabricated_quotes_and_keeps_attempt_retryable(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    d.create()
    d.advance()
    provider.transform = lambda schema, value: (
        {**value, "evidence_quotes": ["I said something else"]}
        if schema == "SemanticTurn"
        else value
    )
    step = next(s for s in d.journey["steps"] if s["kind"] == "respond")
    body = {
        "mutation_id": str(uuid4()),
        "expected_revision": d.journey["revision"],
        "input": {"mode": "text", "text": "Non, merci."},
    }
    route = f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts"
    result = assembled_client.post(route, json=body, headers=d.headers)
    assert result.status_code in (200, 202), result.text
    assert result.json()["pending"] is True
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    assert thread.state["living_story"].get("events", []) == []
    provider.transform = lambda schema, value: value
    result = assembled_client.post(route, json=body, headers=d.headers)
    assert result.status_code == 200, result.text
    assert result.json()["pending"] is False
    again = assembled_client.post(route, json=body, headers=d.headers)
    assert again.json() == result.json()
    db_session.refresh(thread)
    assert len(thread.state["living_story"]["events"]) == 1


def test_legacy_routes_cannot_create_or_complete_parallel_plot(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", True)
    d = driver(assembled_client, db_session)
    initial = assembled_client.get("/api/v1/serial/today", headers=d.headers)
    assert initial.status_code == 200
    assert initial.json()["status"] == "journey_required"
    assert provider.calls == []
    d.create()
    scene = assembled_client.get("/api/v1/story-engine/episodes", headers=d.headers).json()[
        "episodes"
    ][0]
    calls = len(provider.calls)
    for suffix in ("/complete", "/attempts"):
        body = {} if suffix == "/complete" else {"task_id": "invented", "learner_response": "oui"}
        response = assembled_client.post(
            f"/api/v1/graphic-novel/scenes/{scene['id']}{suffix}", headers=d.headers, json=body
        )
        assert response.status_code in (409, 422)
    assert (
        assembled_client.post(
            "/api/v1/graphic-novel/scenes", json={}, headers=d.headers
        ).status_code
        == 409
    )
    current = assembled_client.get("/api/v1/serial/today", headers=d.headers).json()
    assert current["scene_id"] == scene["id"]
    assert "possible_developments" not in json.dumps(current)
    assert len(provider.calls) == calls
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")
    current = assembled_client.get("/api/v1/serial/today", headers=d.headers).json()
    assert current["status"] == "journey_required"
    assert len(provider.calls) == calls + 2


def test_late_story_conflict_rolls_back_learning_and_revision(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    from app.db.models.daily_journey import DailyJourney
    from app.db.models.session import SessionLearningMoment

    d = driver(assembled_client, db_session)
    d.create()
    d.advance()
    step = next(s for s in d.journey["steps"] if s["kind"] == "respond")
    before = list(db_session.scalars(select(SessionLearningMoment.id)))
    revision = d.journey["revision"]

    def conflict(*args, **kwargs):
        raise engine.StoryUnavailable("story_revision_conflict")

    monkeypatch.setattr(engine, "settle_resolution", conflict)
    response = assembled_client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts",
        headers=d.headers,
        json={
            "mutation_id": str(uuid4()),
            "expected_revision": revision,
            "input": {"mode": "text", "text": "Je peux apporter les affiches samedi."},
        },
    )
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(DailyJourney, UUID(d.journey["id"])).revision == revision
    assert list(db_session.scalars(select(SessionLearningMoment.id))) == before
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    assert thread.state["living_story"].get("events", []) == []


def test_existing_callbacks_feed_director_but_only_witnessed_facts_feed_actor(
    assembled_client, db_session, journey_enabled, clock, provider
):
    from app.db.models.user import User

    d = driver(assembled_client, db_session)
    d.create()
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    thread.state = {
        **thread.state,
        "journey_outcomes": {
            "legacy:1": {"callback": "Vous cherchez une salle.", "character_id": "romy_tremblay"},
            "legacy:2": {
                "callback": "Une surprise reste secrète.",
                "character_id": "unseen_character",
            },
        },
    }
    db_session.commit()
    context = engine.story_context(db_session, db_session.get(User, d.user_id))
    assert {e["id"] for e in context["events"]} == {"legacy:1", "legacy:2"}
    d.play(answer="Je peux apporter les affiches samedi.")
    payload = next(p for schema, p in provider.calls if schema == "SemanticTurn")
    assert [e["id"] for e in payload["story"]["events"]] == ["legacy:1"]
    assert payload["story"]["recent_situations"] == []
    assert "possible_developments" not in payload["story"]["chapter"]


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("character_id", "invented_character", "unknown_character_or_location"),
        ("location_id", "invented_place", "unknown_character_or_location"),
    ],
)
def test_scene_validation_rejects_invented_canon(field, value, reason):
    context = {
        "world": {"cast": [{"id": "romy_tremblay"}], "locations": [{"id": "le_mistral"}]},
        "events": [],
        "chapter": None,
        "recent_situations": [],
        "level": "A1",
    }
    proposal = engine.SceneDraft.model_validate({**draft(context), field: value})
    with pytest.raises(engine.StoryUnavailable, match=reason):
        engine._validate_scene(proposal, context)


def test_semantic_critic_can_reject_a_false_interpretation_with_real_quotes(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    d.create()
    d.advance()
    provider.reject = True
    step = next(s for s in d.journey["steps"] if s["kind"] == "respond")
    response = assembled_client.post(
        f"/api/v1/daily-journeys/{d.journey['id']}/steps/{step['id']}/attempts",
        headers=d.headers,
        json={
            "mutation_id": str(uuid4()),
            "expected_revision": d.journey["revision"],
            "input": {"mode": "text", "text": "Je ne peux pas apporter les affiches samedi."},
        },
    )
    assert response.json()["pending"] is True
    assert response.json()["character_reply_fr"] is None
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    assert thread.state["living_story"].get("events", []) == []


def test_expired_generation_budget_never_calls_provider(provider):
    with pytest.raises(engine.StoryUnavailable, match="story_generation_deadline"):
        engine._json_call(engine.DIRECTOR, {}, engine.SceneDraft, deadline=0)
    assert provider.calls == []


@pytest.mark.parametrize(
    ("reply", "learner", "echo"),
    [
        ("Oui, je viens. À quelle heure ? C'est où ?", "Oui, je viens. À quelle heure et c'est où ?", False),
        ("oui je viens, à quelle heure ? c'est où", "Oui, je viens. À quelle heure ? C'est où ?", True),
        ("Merci ! On prépare la salle ensemble.", "Je peux apporter les affiches samedi.", False),
    ],
)
def test_a_reply_that_only_echoes_the_learner_is_rejected(reply, learner, echo):
    turn = engine.SemanticTurn.model_validate(
        {**turn_fixture(learner), "reply_fr": reply}
    )
    payload = {"learner_text": learner, "history": [], "targets": [], "story": {"commitments": []}}
    if echo:
        with pytest.raises(engine.StoryUnavailable, match="reply_echoes_learner"):
            engine._validate_turn(turn, payload)
    else:
        engine._validate_turn(turn, payload)


def _scene_context(**overrides):
    world = {"cast": [{"id": "romy_tremblay"}], "locations": [{"id": "le_mistral"}]}
    context = {"world": world, "events": [], "chapter": None, "recent_situations": [], "level": "A1"}
    context.update(overrides)
    return context


def test_a_resolved_chapter_cannot_be_replayed():
    first = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    resolved = {**first.chapter.model_dump(), "resolved": True}
    replay = engine.SceneDraft.model_validate(draft(_scene_context(), 1))
    replay = replay.model_copy(update={"chapter": first.chapter})
    with pytest.raises(engine.StoryUnavailable, match="chapter_not_advanced"):
        engine._validate_scene(replay, _scene_context(chapter=resolved))
    engine._validate_scene(
        engine.SceneDraft.model_validate(draft(_scene_context(), 1)),
        _scene_context(chapter=resolved),
    )


def test_a_reworded_repeat_of_a_recent_premise_is_rejected():
    proposal = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    recent = [
        {
            "novelty_key": "something-else",
            "premise_fr": "Romy cherche encore une idée pour une exposition dans le quartier.",
        }
    ]
    with pytest.raises(engine.StoryUnavailable, match="repeated_situation"):
        engine._validate_scene(proposal, _scene_context(recent_situations=recent))
    fresh = [{"novelty_key": "other", "premise_fr": "Le facteur a livré un colis pour quelqu'un d'autre."}]
    engine._validate_scene(proposal, _scene_context(recent_situations=fresh))


def test_unknown_source_ids_are_dropped_not_fatal():
    """WP-14F L-1: the director cited situation ids as sources and lost thirteen days."""
    context = _scene_context(events=[{"id": "journey:1:story", "witnesses": []}])
    proposal = engine.SceneDraft.model_validate(
        {**draft(context, 0), "source_event_ids": ["journey:1:story", "story_abc", "day:1"]}
    )
    engine._validate_scene(proposal, context)
    assert proposal.source_event_ids == ["journey:1:story"]


def test_recent_situations_reach_the_director_without_ids(assembled_client, db_session, journey_enabled, clock, provider):
    d = driver(assembled_client, db_session)
    d.create()
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")
    clock.advance(days=1)
    d.create()
    contexts = [p for schema, p in provider.calls if schema == "SceneDraft"]
    recent = contexts[-1]["recent_situations"]
    assert recent and all("id" not in item and item["objective_native"] for item in recent)


def test_a_reworded_repeat_of_a_recent_objective_is_rejected():
    proposal = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    recent = [{"novelty_key": "x", "premise_fr": "Tout autre chose ce matin.", "objective_native": "Suggest how you could help, or explain you cannot."}]
    with pytest.raises(engine.StoryUnavailable, match="repeated_situation"):
        engine._validate_scene(proposal, _scene_context(recent_situations=recent))


@pytest.mark.parametrize(
    ("address", "text", "reason"),
    [
        ("neutral", "Tu es trempé·e, viens.", "inclusive_dot_form"),
        ("feminine", "Bienvenue au·à la nouvel·le arrivé·e.", "inclusive_dot_form"),
        ("neutral", "Allez, commande, mon grand.", "gendered_address"),
        ("neutral", "Fais-nous rêver, ma puce.", "gendered_address"),
        ("feminine", "Tu gères, mon grand.", "gendered_address"),
        ("masculine", "Tu gères, ma puce.", "gendered_address"),
        ("feminine", "Tu gères, ma puce.", None),
        ("masculine", "Tu gères, mon grand.", None),
        ("neutral", "Tu gères, bravo.", None),
    ],
)
def test_learner_address_is_enforced_deterministically(address, text, reason):
    """WP-14F L-6: prompt-only address rules were violated live; now a rule."""
    context = _scene_context(learner={"address": address})
    proposal = engine.SceneDraft.model_validate({**draft(context, 0), "opening_line_fr": text})
    if reason:
        with pytest.raises(engine.StoryUnavailable, match=reason):
            engine._validate_scene(proposal, context)
    else:
        engine._validate_scene(proposal, context)


def test_a_reply_that_recites_the_suggested_answer_is_rejected():
    """WP-14F L-3: the character handed over the answer key with no assistance recorded."""
    learner = "Je suis d'accord, je vais au marché demain."
    turn = engine.SemanticTurn.model_validate({**turn_fixture(learner), "reply_fr": "D'accord. Dis par exemple : « Je peux apporter les affiches samedi ! »"})
    payload = {"learner_text": learner, "history": [], "targets": [], "story": {"commitments": [], "level": "A1", "learner": {"address": "neutral"}}, "scene": {"suggested_response_fr": "Je peux apporter les affiches samedi."}}
    with pytest.raises(engine.StoryUnavailable, match="reply_leaks_suggestion"):
        engine._validate_turn(turn, payload)


def test_an_a1_reply_far_above_level_or_gendered_is_rejected():
    learner = "Oui, je viens."
    long_reply = " ".join(["mot"] * 41)
    payload = {"learner_text": learner, "history": [], "targets": [], "story": {"commitments": [], "level": "A1", "learner": {"address": "neutral"}}, "scene": {}}
    with pytest.raises(engine.StoryUnavailable, match="reply_above_level"):
        engine._validate_turn(engine.SemanticTurn.model_validate({**turn_fixture(learner), "reply_fr": long_reply}), payload)
    with pytest.raises(engine.StoryUnavailable, match="gendered_address"):
        engine._validate_turn(engine.SemanticTurn.model_validate({**turn_fixture(learner), "reply_fr": "Parfait, mon grand !"}), payload)
    engine._validate_turn(engine.SemanticTurn.model_validate({**turn_fixture(learner), "reply_fr": "Parfait, à samedi !"}), payload)
