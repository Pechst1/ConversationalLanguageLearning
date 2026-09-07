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


# One communicative act each, at most one clause: the engine rejects a chained A1/A2
# objective (WP-17 paid run) and any objective overlapping a recent situation.
OBJECTIVES = [
    "Offer your help for the exhibition.",
    "Propose another time for the market morning.",
    "Ask the price of the bike.",
    "Explain where the parcel went.",
    "Say whether you come on Friday.",
    "Ask a neighbour about the flooded cellar.",
    "Accept or decline the cat-sitting.",
]


# The engine rotates location and character (WP-17): the same pair may not carry three
# consecutive situations, and the same pair may not repeat an objective.
LOCATIONS = [
    "le_mistral",
    "marche_canal",
    "buttes_chaumont",
    "user_apartment",
    "newsroom",
    "metro_platform",
    "brocante",
]

# A resolved chapter's question may never come back, and a reworded twin is a repeat.
QUESTIONS = [
    "Comment organiser cette exposition ?",
    "Qui gardera le chat pendant le week-end ?",
    "Faut-il vendre le vieux vélo du voisin ?",
    "Le colis perdu arrivera-t-il chez son destinataire ?",
    "Qui viendra à la soirée jeux de vendredi ?",
    "Comment vider la cave inondée avant lundi ?",
    "Les poubelles seront-elles descendues à temps ?",
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
        "location_id": LOCATIONS[n % len(LOCATIONS)],
        "causal_reason": "Continue the actual proposal from the previous exchange."
        if context.get("events")
        else "Romy invites the newcomer to help.",
        "source_event_ids": [e["id"] for e in context.get("events", [])[-1:]],
        "novelty_key": f"exhibition-task-{n}",
        "chapter": {
            k: chapter[k] for k in ("title_fr", "dramatic_question", "possible_developments")
        }
        # A compliant director opens a new chapter once the current one is answered or
        # exhausted (by resolved commitments or by CHAPTER_MAX_SCENES).
        if chapter and not (chapter.get("resolved") or chapter.get("exhausted"))
        else {
            "title_fr": f"Une exposition {n}",
            "dramatic_question": QUESTIONS[n % len(QUESTIONS)],
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
        # Per-call estimated cost, as the provider reports it in usage metadata.
        self.cost_usd = 0.0
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
            cost=self.cost_usd,
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
    world = {
        "cast": [{"id": "romy_tremblay"}, {"id": "lila_bonnet"}],
        "locations": [{"id": location} for location in LOCATIONS],
    }
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
    recent = [{"novelty_key": "x", "premise_fr": "Tout autre chose ce matin.", "objective_native": "Offer your help with the exhibition."}]
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


# ---------------------------------------------------------------------------
# WP-17 — variety, chapter turnover, register and the cost ledger
# ---------------------------------------------------------------------------


def test_director_sees_the_whole_world_bible_not_one_cafe(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """1. Location/character rotation is data-driven from the bible, not hard-coded."""

    d = driver(assembled_client, db_session)
    d.create()
    context = next(payload for schema, payload in provider.calls if schema == "SceneDraft")
    variety = context["variety"]
    assert len(variety["all_locations"]) >= 5 and "le_mistral" in variety["all_locations"]
    assert len(variety["all_characters"]) >= 4 and "lila_bonnet" in variety["all_characters"]
    # Day one has used nothing yet, so everything is offered as a rotation target.
    assert set(variety["unused_locations"]) == set(variety["all_locations"])
    assert set(variety["unused_characters"]) == set(variety["all_characters"])
    assert variety["must_change"] is None
    assert {loc["id"] for loc in context["world"]["locations"]} >= set(variety["all_locations"])


def test_three_scenes_with_one_pair_force_a_rotation():
    """1. After PAIR_REPEAT_LIMIT identical pairs the director must move."""

    recent = [
        {"character_id": "romy_tremblay", "location_id": "le_mistral", "objective_native": f"O{i}"}
        for i in range(engine.PAIR_REPEAT_LIMIT)
    ]
    cast = [{"id": "romy_tremblay"}, {"id": "lila_bonnet"}]
    locations = [{"id": "le_mistral"}, {"id": "marche_canal"}]
    variety = engine._variety(recent, cast, locations)
    assert variety["must_change"] == {
        "character_id": "romy_tremblay",
        "location_id": "le_mistral",
    }
    assert variety["unused_characters"] == ["lila_bonnet"]
    assert variety["unused_locations"] == ["marche_canal"]

    context = _scene_context(recent_situations=recent, variety=variety)
    stuck = engine.SceneDraft.model_validate(
        {**draft(context, 5), "character_id": "romy_tremblay", "location_id": "le_mistral"}
    )
    with pytest.raises(engine.StoryUnavailable, match="setting_not_rotated"):
        engine._validate_scene(stuck, context)
    # Changing either half of the pair is enough.
    engine._validate_scene(
        engine.SceneDraft.model_validate(
            {**draft(context, 5), "character_id": "lila_bonnet", "location_id": "le_mistral"}
        ),
        context,
    )
    engine._validate_scene(
        engine.SceneDraft.model_validate(
            {**draft(context, 5), "character_id": "romy_tremblay", "location_id": "marche_canal"}
        ),
        context,
    )
    # Two scenes at the counter are still allowed; the third must move.
    assert engine._variety(recent[:2], cast, locations)["must_change"] is None


def test_same_character_same_place_same_objective_is_a_repeat():
    """3. Premise overlap on (location, character, objective), not only content words."""

    recent = [
        {
            "character_id": "romy_tremblay",
            "location_id": "le_mistral",
            "premise_fr": "Une histoire tout à fait différente ce matin.",
            # Overlaps the new objective enough to be the same ask (>= 0.4) but not
            # enough for the plain content-word rule (0.6) to catch it.
            "objective_native": "Offer help for the exhibition next week.",
            "novelty_key": "other",
        }
    ]
    proposal = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    context = _scene_context(recent_situations=recent)
    with pytest.raises(engine.StoryUnavailable, match="repeated_premise_triple"):
        engine._validate_scene(proposal, context)
    # The same objective elsewhere, or with someone else, is a different situation.
    moved = proposal.model_copy(update={"location_id": "marche_canal"})
    engine._validate_scene(moved, context)
    other = proposal.model_copy(update={"character_id": "lila_bonnet"})
    engine._validate_scene(other, context)


def test_a_chapter_exhausted_by_resolved_commitments_must_be_replaced():
    """2. Turnover after N resolved commitments, not only after an answered question."""

    live = {
        "chapter": {
            "id": "c1",
            "title_fr": "Une exposition",
            "dramatic_question": "Comment organiser cette exposition ?",
            "possible_developments": ["Trouver une salle.", "Inviter les voisins."],
            "resolved": False,
            "resolved_commitments": engine.CHAPTER_RESOLVED_COMMITMENT_LIMIT,
        }
    }
    chapter = engine.chapter_state(live)
    assert chapter["exhausted"] is True
    context = _scene_context(chapter=chapter)
    replay = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    replay = replay.model_copy(
        update={
            "chapter": engine.Chapter(
                title_fr="Une exposition",
                dramatic_question="Comment organiser cette exposition ?",
                possible_developments=["Trouver une salle.", "Inviter les voisins."],
            )
        }
    )
    with pytest.raises(engine.StoryUnavailable, match="chapter_not_advanced"):
        engine._validate_scene(replay, context)
    # One below the limit the chapter is still open, and abandoning it is the error.
    live["chapter"]["resolved_commitments"] = engine.CHAPTER_RESOLVED_COMMITMENT_LIMIT - 1
    open_context = _scene_context(chapter=engine.chapter_state(live))
    engine._validate_scene(replay, open_context)
    with pytest.raises(engine.StoryUnavailable, match="abandoned_chapter"):
        engine._validate_scene(
            engine.SceneDraft.model_validate(draft(_scene_context(), 1)), open_context
        )
    # A new question closes it out.
    engine._validate_scene(engine.SceneDraft.model_validate(draft(_scene_context(), 1)), context)


def test_a_retired_chapter_question_never_comes_back():
    """2. Every resolved chapter is retired, not only the most recent one."""

    retired = ["Comment organiser cette exposition ?"]
    context = _scene_context(resolved_chapter_questions=retired, chapter=None)
    replay = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    with pytest.raises(engine.StoryUnavailable, match="chapter_not_advanced"):
        engine._validate_scene(replay, context)
    # A reworded twin of a retired question is the same question.
    reworded = replay.model_copy(
        update={
            "chapter": replay.chapter.model_copy(
                update={"dramatic_question": "Comment organiser vraiment cette exposition ?"}
            )
        }
    )
    with pytest.raises(engine.StoryUnavailable, match="chapter_not_advanced"):
        engine._validate_scene(reworded, context)
    engine._validate_scene(engine.SceneDraft.model_validate(draft(_scene_context(), 1)), context)


def test_lilas_putain_is_stripped_below_b1_and_rejected_in_generated_text():
    """4. Register: the bible keeps Lila's voice; an A1/A2 learner never sees it."""

    from app.services.serial import SerialThreadService

    world = SerialThreadService._load_world_bible()
    lila = next(c for c in world["cast"] if c["id"] == "lila_bonnet")
    assert "putain" in json.dumps(lila, ensure_ascii=False).casefold(), (
        "fixture guard: the bible is expected to carry the coarse register"
    )
    cast = [
        {key: member.get(key) for key in ("id", "name", "speech_pattern", "personality")}
        for member in world["cast"]
    ]
    for level in ("A1", "A2"):
        cleaned = engine._cast_for_level(deepcopy(cast), level)
        assert "putain" not in json.dumps(cleaned, ensure_ascii=False).casefold()
        assert all(member["register_note"] for member in cleaned)
        assert next(c for c in cleaned if c["id"] == "lila_bonnet")["name"] == lila["name"]
    assert "putain" in json.dumps(
        engine._cast_for_level(deepcopy(cast), "B1"), ensure_ascii=False
    ).casefold()

    coarse = {**draft(_scene_context(), 0), "opening_line_fr": "Putain, tu peux nous aider ?"}
    coarse["panels"][1]["dialogue"] = [
        {"character_id": "romy_tremblay", "text_fr": "Putain, tu as une idée ?"}
    ]
    proposal = engine.SceneDraft.model_validate(coarse)
    with pytest.raises(engine.StoryUnavailable, match="vulgar_register"):
        engine._validate_scene(proposal, _scene_context(level="A1"))
    engine._validate_scene(proposal, _scene_context(level="B1"))

    payload = {
        "learner_text": "Je peux venir samedi.",
        "history": [],
        "targets": [],
        "story": {"commitments": [], "level": "A1"},
        "scene": {},
    }
    reply = engine.SemanticTurn.model_validate(
        {**turn_fixture("Je peux venir samedi."), "reply_fr": "Putain, merci beaucoup !"}
    )
    with pytest.raises(engine.StoryUnavailable, match="vulgar_register"):
        engine._validate_turn(reply, payload)
    payload["story"]["level"] = "B1"
    engine._validate_turn(reply, payload)


def test_narration_and_dialogue_must_address_the_learner_the_same_way():
    """4. Narration vous with dialogue tu was the live review's cosmetic defect."""

    mixed = deepcopy(draft(_scene_context(), 0))
    mixed["panels"][0]["narration_fr"] = "Vous poussez la porte du café."
    mixed["premise_fr"] = "Vous arrivez au marché avec votre parapluie."
    mixed["opening_line_fr"] = "Tu peux nous aider ?"
    mixed["panels"][1]["dialogue"] = [
        {"character_id": "romy_tremblay", "text_fr": "Tu as une idée ?"}
    ]
    with pytest.raises(engine.StoryUnavailable, match="mixed_address_register"):
        engine._validate_scene(engine.SceneDraft.model_validate(mixed), _scene_context())
    aligned = deepcopy(mixed)
    aligned["panels"][0]["narration_fr"] = "Tu pousses la porte du café."
    aligned["premise_fr"] = "Tu arrives au marché avec ton parapluie."
    engine._validate_scene(engine.SceneDraft.model_validate(aligned), _scene_context())
    # A plural "vous" in a group scene is not a register signal, so nothing is rejected.
    ambiguous = deepcopy(mixed)
    ambiguous["panels"][1]["dialogue"] = [
        {"character_id": "romy_tremblay", "text_fr": "Tu as une idée ? Vous venez tous ?"}
    ]
    engine._validate_scene(engine.SceneDraft.model_validate(ambiguous), _scene_context())


def test_every_accepted_scene_and_turn_writes_one_cost_row(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """5. The pilot ledger and the weekly guardrail both see engine spend, once."""

    from app.db.models.pilot_event import PilotEvent
    from app.services.serial_costs import SerialGenerationCostService

    provider.cost_usd = 0.004
    d = driver(assembled_client, db_session)
    d.create()
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")
    db_session.expire_all()

    rows = list(
        db_session.scalars(select(PilotEvent).where(PilotEvent.user_id == d.user_id))
    )
    by_type = {}
    for row in rows:
        by_type.setdefault(row.event_type, []).append(row)
    assert len(by_type["journey_story_scene_cost"]) == 1
    assert len(by_type["journey_story_turn_cost"]) == 1
    # Draft + critic, then turn + critic: four calls, all four billed exactly once.
    assert by_type["journey_story_scene_cost"][0].cost_usd == pytest.approx(0.008)
    assert by_type["journey_story_turn_cost"][0].cost_usd == pytest.approx(0.008)
    assert all(row.cost_usd == 0.0 for row in by_type["journey_story_model_call"]), (
        "per-call rows stay diagnostics so nothing is counted twice"
    )
    assert by_type["journey_story_model_call"][0].payload["call_cost_usd"] == pytest.approx(0.004)

    scene = db_session.scalar(
        select(GraphicNovelScene).where(GraphicNovelScene.user_id == d.user_id)
    )
    assert by_type["journey_story_scene_cost"][0].entity_id == str(scene.id)
    assert scene.script_payload["estimated_cost"]["total_estimated_usd"] == pytest.approx(0.016)
    weekly = SerialGenerationCostService(db_session).weekly_rollup(user_id=d.user_id)
    assert len(weekly) == 1
    assert weekly[0]["total_usd"] == pytest.approx(0.016), (
        "PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD reads this rollup"
    )


def test_a_rolled_back_scene_leaves_no_phantom_cost_row(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    """5. Cost rows live in the same transaction as the artifact they pay for."""

    from app.db.models.pilot_event import PilotEvent

    provider.cost_usd = 0.004
    d = driver(assembled_client, db_session)
    d.create()
    d.advance()
    step = next(s for s in d.journey["steps"] if s["kind"] == "respond")
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
    types = [
        row.event_type
        for row in db_session.scalars(select(PilotEvent).where(PilotEvent.user_id == d.user_id))
    ]
    assert "journey_story_turn_cost" not in types, "a rolled-back turn must not be billed"
    # The published scene is still there, and so is its single cost row.
    assert types.count("journey_story_scene_cost") == 1


def test_spend_on_a_scene_nobody_can_use_is_still_recorded(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """5. A rejected generation is real spend; the ledger keeps it."""

    from app.db.models.pilot_event import PilotEvent

    provider.cost_usd = 0.004
    provider.reject = True
    d = driver(assembled_client, db_session)
    d.create(expect=(200,))
    assert d.journey["status"] == "unavailable"
    db_session.expire_all()
    rows = [
        row
        for row in db_session.scalars(select(PilotEvent).where(PilotEvent.user_id == d.user_id))
        if row.event_type == "journey_story_generation_failed"
    ]
    assert len(rows) == 1
    assert rows[0].cost_usd == pytest.approx(0.004 * rows[0].payload["calls"])
    assert rows[0].payload["reason"]


def test_the_critic_call_can_be_switched_off_for_the_owners_ab_run(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    """6. --no-critic drops the review call and nothing else."""

    monkeypatch.setattr(engine, "CRITIC_ENABLED", False)
    d = driver(assembled_client, db_session)
    d.create()
    assert d.journey["status"] == "active"
    schemas = [schema for schema, _ in provider.calls]
    assert schemas == ["SceneDraft"], schemas
    # The deterministic guards still run: an invented location is still refused.
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")
    assert "Review" not in [schema for schema, _ in provider.calls]


# ---------------------------------------------------------------------------
# WP-17 paid runs (2026-09-07) — each defect the live A1/A2 runs exposed
# ---------------------------------------------------------------------------


def test_a_repetition_rejection_tells_the_director_what_to_change():
    """A2 paid run: five days lost to a retry that only saw "repeated_premise_triple".

    The retry feedback must name the offending triple, the objectives already used and
    the ids that are still free, or the model answers a repetition refusal by rewording
    the same scene (days 9-12 and 14 were literally the same "call the seller" scene).
    """

    recent = [
        {
            "character_id": "romy_tremblay",
            "location_id": "le_mistral",
            "objective_native": "Offer help for the exhibition next week.",
            "premise_fr": "Une histoire tout à fait différente ce matin.",
            "novelty_key": "other",
        }
    ]
    context = _scene_context(recent_situations=recent)
    context["variety"] = engine._variety(
        recent, context["world"]["cast"], context["world"]["locations"]
    )
    proposal = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    with pytest.raises(engine.StoryUnavailable) as caught:
        engine._validate_scene(proposal, context)
    error = caught.value
    assert str(error) == "repeated_premise_triple", "the machine reason stays a token"
    assert "romy_tremblay" in error.hint and "le_mistral" in error.hint
    assert "Offer help for the exhibition next week." in error.hint
    assert "lila_bonnet" in error.hint, "the free ids must be named"
    assert error.feedback.startswith("repeated_premise_triple: ")
    # The context the director sees carries the same facts, before any rejection.
    assert context["variety"]["used_objectives"] == [
        "Offer help for the exhibition next week."
    ]


def test_the_retry_carries_the_hint_not_the_bare_token(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    """The hint has to reach the model's ``previous_rejections``, not just the log."""

    rejections = []

    def refuse_once(proposal, context):
        if not rejections:
            rejections.append(True)
            raise engine.StoryUnavailable("repeated_situation", hint="pick another café")

    monkeypatch.setattr(engine, "_validate_scene", refuse_once)
    d = driver(assembled_client, db_session)
    d.create()
    contexts = [payload for schema, payload in provider.calls if schema == "SceneDraft"]
    assert contexts[1]["previous_rejections"] == ["repeated_situation: pick another café"]


@pytest.mark.parametrize(
    ("level", "objective", "rejected"),
    [
        # The exact A1 objective the paid run served on day 1.
        (
            "A1",
            "Accept or decline the invitation, give a simple reason about budget or "
            "schedule, and ask for the meeting time and place.",
            True,
        ),
        ("A1", "Ask Lila what time you meet at the market.", False),
        # The A2 objective that produced five identical retries.
        (
            "A2",
            "Decide if Marin should call now, give a short reason about your budget, and "
            "ask what Marin will say to the seller.",
            True,
        ),
        ("A2", "Ask the price and propose another time to come back.", False),
        # B1 and B2 may negotiate several things at once.
        (
            "B1",
            "Accept or decline the invitation, give a reason, and ask for the time and "
            "the place, then propose an alternative.",
            False,
        ),
    ],
)
def test_a1_and_a2_objectives_must_be_one_communicative_act(level, objective, rejected):
    """A1 paid run: ten of twelve days ended in a clarification loop on chained asks."""

    if rejected:
        with pytest.raises(engine.StoryUnavailable, match="objective_too_complex"):
            engine._check_objective_scope(objective, level)
    else:
        engine._check_objective_scope(objective, level)


def test_a_chapter_ends_after_five_scenes_even_if_nothing_is_ever_resolved():
    """A1 paid run: one chapter for twelve days — no commitment, no resolution, no end."""

    live = {
        "chapter": {
            "id": "c1",
            "title_fr": "Une exposition",
            "dramatic_question": "Comment organiser cette exposition ?",
            "resolved": False,
            "resolved_commitments": 0,
            "scene_count": engine.CHAPTER_MAX_SCENES - 1,
        }
    }
    assert engine.chapter_state(live)["exhausted"] is False
    live["chapter"]["scene_count"] = engine.CHAPTER_MAX_SCENES
    chapter = engine.chapter_state(live)
    assert chapter["exhausted"] is True
    replay = engine.SceneDraft.model_validate(draft(_scene_context(), 0)).model_copy(
        update={
            "chapter": engine.Chapter(
                title_fr="Une exposition",
                dramatic_question="Comment organiser cette exposition ?",
                possible_developments=["Trouver une salle.", "Inviter les voisins."],
            )
        }
    )
    with pytest.raises(engine.StoryUnavailable, match="chapter_not_advanced"):
        engine._validate_scene(replay, _scene_context(chapter=chapter))
    engine._validate_scene(
        engine.SceneDraft.model_validate(draft(_scene_context(), 1)),
        _scene_context(chapter=chapter),
    )


def test_the_chapter_question_is_held_to_the_learners_address_and_register():
    """A1 paid run stored "tu restes réservé·e" in the chapter for fourteen days."""

    gendered = deepcopy(draft(_scene_context(), 0))
    gendered["chapter"]["dramatic_question"] = (
        "Est-ce que tu acceptes l'aide des nouveaux amis ou tu restes réservé·e ?"
    )
    with pytest.raises(engine.StoryUnavailable, match="inclusive_dot_form"):
        engine._validate_scene(
            engine.SceneDraft.model_validate(gendered),
            _scene_context(learner={"address": "neutral"}),
        )
    coarse = deepcopy(draft(_scene_context(), 0))
    coarse["chapter"]["title_fr"] = "Putain de vernissage"
    with pytest.raises(engine.StoryUnavailable, match="vulgar_register"):
        engine._validate_scene(
            engine.SceneDraft.model_validate(coarse), _scene_context(level="A1")
        )


@pytest.mark.parametrize(
    ("existing", "proposed", "same"),
    [
        # The exact pair the A2 run left open at the end of fourteen days.
        (
            "Venir dimanche au marché et se retrouver à 11h au pont.",
            "Tu viens dimanche au marché.",
            True,
        ),
        ("Apporter les affiches samedi.", "APPORTER les affiches, samedi !", True),
        ("Aider Marin à ranger le bureau.", "Venir dimanche au marché.", False),
        ("Apporter les affiches samedi.", "Réserver la salle pour vendredi.", False),
    ],
)
def test_a_restated_promise_is_not_a_second_commitment(existing, proposed, same):
    assert engine._same_promise(existing, proposed) is same


def test_the_critic_can_be_limited_to_turns(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    """WP-17 paid runs: 19 scene reviews, one rejection, and it duplicated a guard.

    Reviewing turns only keeps every unique catch, halves the review cost and — because a
    review rejection consumes one of ``ATELIER_STORY_MAX_ATTEMPTS`` — gives both attempts
    back to the deterministic scene guards.
    """

    monkeypatch.setattr(engine, "CRITIC_STAGES", frozenset({"SemanticTurn"}))
    d = driver(assembled_client, db_session)
    d.create()
    assert [schema for schema, _ in provider.calls] == ["SceneDraft"]
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")
    schemas = [schema for schema, _ in provider.calls]
    assert schemas.count("Review") == 1, schemas
    assert schemas == ["SceneDraft", "SemanticTurn", "Review"]


def test_the_interpreters_own_reading_of_the_learner_is_address_checked():
    """A2 paid run: only the critic saw "Le·a apprenant·e" in understood_intent."""

    payload = {
        "learner_text": "Je viens dimanche.",
        "history": [],
        "targets": [],
        "story": {"commitments": [], "level": "A1", "learner": {"address": "neutral"}},
        "scene": {},
    }
    turn = engine.SemanticTurn.model_validate(
        {
            **turn_fixture("Je viens dimanche."),
            "understood_intent": "Le·a apprenant·e accepte de venir dimanche.",
        }
    )
    with pytest.raises(engine.StoryUnavailable, match="inclusive_dot_form"):
        engine._validate_turn(turn, payload)
