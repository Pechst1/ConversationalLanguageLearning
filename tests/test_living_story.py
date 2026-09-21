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


# WP-59: from B1 an objective is a move, not a sentence. Four different moves, so the
# suffix never makes two days' objectives read as the same situation.
UPPER_BAND_MOVES = [
    " Give your reason, and propose an alternative if you cannot.",
    " Explain what worries you about it, then name a condition.",
    " Say why it matters to you and offer one concrete plan.",
    " Take a position, concede one point, and hold your line.",
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


def _fresh_question(context, n=0):
    """The n-th chapter question, skipping any this life has already answered (WP-58:
    four-scene chapters open more chapters in fourteen days than the list has entries)."""
    retired = {str(q).casefold() for q in context.get("resolved_chapter_questions") or []}
    current = (context.get("chapter") or {}).get("dramatic_question")
    if current:
        retired.add(str(current).casefold())
    ordered = [QUESTIONS[(n + i) % len(QUESTIONS)] for i in range(len(QUESTIONS))]
    return next((q for q in ordered if q.casefold() not in retired), ordered[0])



def _shaped(context, n):
    """Where this scene happens and who speaks, for a director that obeys its shape.

    WP-63 deals each chapter a shape: a bottle chapter never leaves its room, and
    three scenes with one character in one place still have to rotate somebody. A
    fixture that ignored either would be testing an incompetent director.
    """

    chapter = context.get("chapter") or {}
    shape = str((context.get("chapter_shape") or {}).get("shape") or chapter.get("shape") or "")
    location = LOCATIONS[n % len(LOCATIONS)]
    if shape == "bottle" and chapter.get("location_id"):
        location = str(chapter["location_id"])
    speaker = "romy_tremblay"
    must_change = (context.get("variety") or {}).get("must_change") or {}
    if must_change.get("character_id") == speaker and must_change.get("location_id") == location:
        cast = [
            member
            for member in (context.get("world") or {}).get("cast") or []
            if member.get("id") and member["id"] != speaker
        ]
        speaker = cast[n % len(cast)]["id"] if cast else speaker
    return speaker, location


def draft(context, n=0):
    chapter = context.get("chapter") or {}
    speaker, location = _shaped(context, n)
    return {
        "title_fr": f"Les affiches {n}",
        # Seven distinct premises and objectives: the engine rejects either one
        # overlapping any of the last five situations.
        "premise_fr": PREMISES[n % len(PREMISES)],
        "setup_native": "Romy is arranging a neighborhood exhibition.",
        # WP-59: from B1 an objective is a move, not a sentence; the fixture grows one.
        "objective_native": OBJECTIVES[n % len(OBJECTIVES)]
        + (
            UPPER_BAND_MOVES[n % len(UPPER_BAND_MOVES)]
            if str(context.get("level") or "") in ("B1", "B2", "C1")
            else ""
        ),
        "objective_semantics": "Clearly express an offer or a refusal of help with the exhibition.",
        "character_id": speaker,
        "location_id": location,
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
            "dramatic_question": _fresh_question(context, n),
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
                "dialogue": [{"character_id": speaker, "text_fr": "Vous avez une idée ?"}],
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
    # WP-59: the scripted provider answers one draft per day; the two-draft loop
    # has its own test and stays off here.
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
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
    # WP-63: a chapter is as long as its shape (three beats for a two-hander, five
    # for an ensemble), so fourteen days no longer divide into exactly four.
    assert 3 <= len(chapter_ids) <= 6
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    events = thread.state["living_story"]["events"]
    played = [e for e in events if not str(e["id"]).startswith(engine.MEANWHILE_PREFIX)]
    assert len(played) == 14, "one recorded exchange per day"
    # The rest are the cast's own week: off-screen, witnessed by characters only.
    assert all(
        e["kind"] == "meanwhile" and e["witnesses"] and e["summary_fr"]
        for e in events
        if e not in played
    )
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
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    provider.reject = True
    # Exercises the scene-stage critic explicitly; the default is turns only.
    monkeypatch.setattr(engine, "CRITIC_STAGES", frozenset({"SceneDraft", "SemanticTurn"}))
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
    # WP-58: both attempts refused is no longer a failed send. The learner gets an
    # honest authored ending (the character is called away), labelled as such, with
    # nothing graded as met and no invented commitment.
    assert result.json()["pending"] is False
    assert result.json()["reply_source"] == "authored"
    assert result.json()["task_outcome"] == "partially_met"
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    # The fallback is a real, settled exchange: one event, honest about what happened,
    # with the learner's own words as its only evidence and no commitment.
    events = thread.state["living_story"].get("events", [])
    assert len(events) == 1
    assert events[0]["outcome"] == "partially_met"
    assert events[0]["source_quotes"] == ["Non, merci."]
    assert thread.state["living_story"].get("commitments", []) == []
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
    # WP-58: the critic's rejection stands — the disputed reply is never shown — and
    # the learner still gets a settled, honest ending instead of a failed send.
    assert response.json()["pending"] is False
    assert response.json()["reply_source"] == "authored"
    assert response.json()["task_outcome"] == "partially_met"
    assert "appelle" in response.json()["character_reply_fr"]
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    events = thread.state["living_story"].get("events", [])
    assert len(events) == 1 and events[0]["outcome"] == "partially_met"


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
        # WP-58: a middle-dot form keeps its first half rather than costing the day.
        ("neutral", "Tu es trempé·e, viens.", "scrub:Tu es trempé, viens."),
        ("feminine", "Bienvenue au·à la nouvel·le arrivé·e.", "scrub:Bienvenue au la nouvel arrivé."),
        # WP-58: a forbidden endearment is cut from the line, never fatal.
        ("neutral", "Allez, commande, mon grand.", "scrub:Allez, commande."),
        ("neutral", "Fais-nous rêver, ma puce.", "scrub:Fais-nous rêver."),
        ("feminine", "Tu gères, mon grand.", "scrub:Tu gères."),
        ("masculine", "Tu gères, ma puce.", "scrub:Tu gères."),
        ("feminine", "Tu gères, ma puce.", None),
        ("masculine", "Tu gères, mon grand.", None),
        ("neutral", "Tu gères, bravo.", None),
    ],
)
def test_learner_address_is_enforced_deterministically(address, text, reason):
    """WP-14F L-6: prompt-only address rules were violated live; now a rule."""
    context = _scene_context(learner={"address": address})
    proposal = engine.SceneDraft.model_validate({**draft(context, 0), "opening_line_fr": text})
    if reason and reason.startswith("scrub:"):
        engine._validate_scene(proposal, context)
        assert proposal.opening_line_fr == reason.removeprefix("scrub:")
    elif reason:
        with pytest.raises(engine.StoryUnavailable, match=reason):
            engine._validate_scene(proposal, context)
    else:
        engine._validate_scene(proposal, context)
        assert proposal.opening_line_fr == text


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
    # WP-58: an endearment the address forbids is cut, not fatal — the sentence
    # stands and the day goes on; only agreement still rejects.
    turn = engine.SemanticTurn.model_validate({**turn_fixture(learner), "reply_fr": "Parfait, mon grand !"})
    engine._validate_turn(turn, payload)
    assert turn.reply_fr == "Parfait !"
    with pytest.raises(engine.StoryUnavailable, match="gendered_agreement"):
        engine._validate_turn(
            engine.SemanticTurn.model_validate({**turn_fixture(learner), "reply_fr": "Tu es content, alors."}),
            payload,
        )
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


def test_the_open_chapters_own_scenes_are_not_a_repeat():
    """Live B1 review 2026-09-21: a complication was refused as a repeat of its setup."""

    proposal = engine.SceneDraft.model_validate(draft(_scene_context(), 0))
    open_chapter = {**proposal.chapter.model_dump(), "resolved": False}
    row = {
        "character_id": proposal.character_id,
        "location_id": proposal.location_id,
        "premise_fr": "Une histoire tout à fait différente ce matin.",
        "objective_native": "Offer help for the exhibition next week.",
        "novelty_key": "other",
    }
    # The same row from ANOTHER chapter is still the repeat it always was …
    elsewhere = _scene_context(
        chapter=open_chapter, recent_situations=[{**row, "chapter_title_fr": "Autre chapitre"}]
    )
    with pytest.raises(engine.StoryUnavailable, match="repeated_premise_triple"):
        engine._validate_scene(proposal, elsewhere)
    # … but the open chapter's own earlier scene is the story continuing.
    own = _scene_context(
        chapter=open_chapter,
        recent_situations=[{**row, "chapter_title_fr": open_chapter["title_fr"]}],
    )
    try:
        engine._validate_scene(proposal, own)
    except engine.StoryUnavailable as error:
        assert str(error) != "repeated_premise_triple"


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
    # At B1 the register passes; the draft is rebuilt for that band because a B1
    # objective must be a move (WP-59).
    upper = {**draft(_scene_context(level="B1"), 0), "opening_line_fr": "Putain, tu peux nous aider ?"}
    upper["panels"][1]["dialogue"] = [
        {"character_id": "romy_tremblay", "text_fr": "Putain, tu as une idée ?"}
    ]
    engine._validate_scene(engine.SceneDraft.model_validate(upper), _scene_context(level="B1"))

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
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    """5. The pilot ledger and the weekly guardrail both see engine spend, once."""
    # Exercises the scene-stage critic explicitly; the default is turns only.
    monkeypatch.setattr(engine, "CRITIC_STAGES", frozenset({"SceneDraft", "SemanticTurn"}))

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
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    """5. A rejected generation is real spend; the ledger keeps it."""
    # Exercises the scene-stage critic explicitly; the default is turns only.
    monkeypatch.setattr(engine, "CRITIC_STAGES", frozenset({"SceneDraft", "SemanticTurn"}))

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
    proposal = engine.SceneDraft.model_validate(gendered)
    engine._validate_scene(proposal, _scene_context(learner={"address": "neutral"}))
    assert "·" not in proposal.chapter.dramatic_question
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


def test_the_interpreters_own_reading_of_the_learner_is_scrubbed_not_rejected():
    """A2 paid run: "Le·a apprenant·e" landed in understood_intent, a field no
    learner reads. The live review of 2026-09-19 lost a day to rejecting it
    twice; the private field is scrubbed and the clean reply goes through."""

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
    engine._validate_turn(turn, payload)
    assert "·" not in turn.understood_intent
    assert "accepte de venir dimanche" in turn.understood_intent

    # What the learner reads is repaired the same way, never shown with a dot.
    spoken = engine.SemanticTurn.model_validate(
        {**turn_fixture("Je viens dimanche."), "reply_fr": "Tu es trempé·e, viens."}
    )
    engine._validate_turn(spoken, payload)
    assert spoken.reply_fr == "Tu es trempé, viens."


# ---------------------------------------------------------------------------
# WP-58 — story shape: beats, a fresh problem per chapter, arcs, and no dead day
# ---------------------------------------------------------------------------


def test_a_chapter_has_four_required_beats_and_the_last_must_resolve():
    assert engine.required_beats(None) == ("setup",)
    assert engine.required_beats({"scene_count": 0}) == ("setup",)
    assert engine.required_beats({"scene_count": 1}) == ("complication",)
    assert engine.required_beats({"scene_count": 2}) == ("turn", "resolution")
    assert engine.required_beats({"scene_count": 3}) == ("resolution",)
    assert engine.required_beats({"scene_count": 1, "resolved": True}) == ("setup",)


def test_a_scene_with_the_wrong_beat_is_told_which_beat_to_write():
    """The 14-day A2 run of 2026-09-07 kept one leaking radiator alive for two weeks:
    nothing ever forced a chapter to reach its resolution."""

    context = _scene_context()
    first = engine.SceneDraft.model_validate(draft(context, 0))
    chapter = {
        **first.chapter.model_dump(),
        "id": "c1",
        "scene_count": 3,
        "resolved": False,
        "resolved_commitments": 0,
    }
    open_context = _scene_context(chapter=engine.chapter_state({"chapter": chapter}))
    assert open_context["chapter"]["required_beat"] == "resolution"
    stuck = engine.SceneDraft.model_validate({**draft(open_context, 1), "beat": "complication"})
    stuck = stuck.model_copy(update={"chapter": first.chapter})
    with pytest.raises(engine.StoryUnavailable, match="wrong_beat") as info:
        engine._validate_scene(stuck, open_context)
    assert "resolution" in info.value.feedback
    # A model that left the field out is given the required beat rather than refused.
    silent = engine.SceneDraft.model_validate(draft(open_context, 1)).model_copy(
        update={"chapter": first.chapter}
    )
    engine._validate_scene(silent, open_context)
    assert silent.beat == "resolution"


def test_a_new_chapter_cannot_reuse_the_problem_the_last_one_played():
    context = _scene_context(
        variety={**engine._variety([], [], []), "used_problems": ["radiateur_fuite"]}
    )
    same = engine.SceneDraft.model_validate(
        {**draft(context, 0), "beat": "setup", "problem_key": "fuite_du_radiateur"}
    )
    with pytest.raises(engine.StoryUnavailable, match="stale_problem"):
        engine._validate_scene(same, context)
    fresh = engine.SceneDraft.model_validate(
        {**draft(context, 0), "beat": "setup", "problem_key": "bague_de_marin"}
    )
    engine._validate_scene(fresh, context)


def test_the_resolution_beat_closes_the_chapter_whatever_the_learner_answered():
    scene = engine.SceneDraft.model_validate(
        {
            **draft(_scene_context(), 0),
            "beat": "resolution",
            "problem_key": "p",
            "arc_id": "marin_proposal",
            # WP-63: the arc moves on this claim, and on nothing else.
            "arc_stage_id": "a",
            "advances_arc": True,
        }
    )
    refused = engine.SemanticTurn.model_validate(turn_fixture("Non.", close=False))
    refused = refused.model_copy(update={"outcome": "not_yet"})
    chapter = engine.chapter_after_scene(engine.open_chapter(scene), scene, refused, "e1")
    assert chapter["resolved"] is True and chapter["beats"] == ["resolution"]
    assert chapter["problem_key"] == "p" and chapter["arc_id"] == "marin_proposal"
    # …and the arc it was anchored in moves one stage, once.
    arcs = [{"id": "marin_proposal", "stages": [{"id": "a"}, {"id": "b"}]}]
    progress = engine.arc_progress_after_scene({}, chapter, arcs, "e1")
    assert progress["marin_proposal"]["stage"] == 1
    assert engine.arc_progress_after_scene(progress, chapter, arcs, "e1") == progress
    projection = engine._season_projection({"season_arcs": [{**arcs[0], "title": "T", "stages": [{"id": "a", "summary": "A"}, {"id": "b", "summary": "B"}]}]}, progress)
    assert projection["arcs"][0]["current_stage"]["id"] == "a"
    assert projection["arcs"][0]["next_stage"]["id"] == "b"


def test_the_director_reads_the_seasons_arcs_secrets_and_threads():
    from app.services.serial import SerialThreadService

    world = SerialThreadService._load_world_bible()
    season = engine._season_projection(world, {})
    assert {arc["id"] for arc in season["arcs"]} >= {"marin_proposal", "lila_berlin_secret"}
    assert all(arc["next_stage"] for arc in season["arcs"])
    assert season["open_threads"] and season["warmth_rule"]
    cast = engine._cast_projection(world)
    marin = next(c for c in cast if c["id"] == "marin_leveque")
    assert marin["secret"] and marin["contradiction"] and marin["flaw"]
    for word in ("required_beat", "problem_key", "arc_id", "world.arcs", "open_threads", "secret"):
        assert word in engine.DIRECTOR, word


def test_a_forbidden_endearment_is_cut_and_the_sentence_kept():
    cut = engine._scrub_endearments
    assert cut("Merci, mon grand. Vraiment ?", "neutral") == "Merci. Vraiment ?"
    assert cut("D'accord, ma puce, je comprends.", "neutral") == "D'accord, je comprends."
    assert cut("Tu gères, ma puce.", "feminine") == "Tu gères, ma puce."
    assert cut("Tu gères, ma puce.", "masculine") == "Tu gères."
    # An adjective is not a vocative.
    assert cut("Mon grand frère arrive.", "neutral") == "Mon grand frère arrive."
    assert cut("Mon grand, tu viens ?", "neutral") == "Tu viens ?"


# ---------------------------------------------------------------------------
# WP-59 — loop engineering, per-learner dice, and level-true B1/B2/C1
# ---------------------------------------------------------------------------


def test_upper_bands_are_asked_for_a_move_not_a_sentence():
    with pytest.raises(engine.StoryUnavailable, match="objective_too_thin"):
        engine._check_objective_scope("Tell Romy in one sentence whether you want to try.", "B1")
    with pytest.raises(engine.StoryUnavailable, match="objective_too_thin"):
        engine._check_objective_scope("Accept the invitation.", "B2")
    engine._check_objective_scope(
        "Take a position on Romy's offer, give your reason, and propose a condition under which you would say yes.",
        "B2",
    )
    # A1/A2 keep the one-act rule.
    with pytest.raises(engine.StoryUnavailable, match="objective_too_complex"):
        engine._check_objective_scope("Order a coffee, ask the price, and then thank the waiter.", "A1")


def test_c1_is_a_band_of_its_own_and_c2_reads_as_c1():
    def user(estimate):
        return type("U", (), {"cefr_estimate": estimate})()

    assert engine.learner_level_band(user("C1.2")) == "C1"
    assert engine.learner_level_band(user("C2.1")) == "C1"
    assert engine.learner_level_band(user("B2.2")) == "B2"
    assert engine._REPLY_WORD_LIMITS["C1"] > engine._REPLY_WORD_LIMITS["B2"] > engine._REPLY_WORD_LIMITS["A2"]
    assert engine._SCENE_WORD_LIMITS["C1"] > engine._SCENE_WORD_LIMITS["A1"]
    assert "C1" in engine.DIRECTOR and "prêt(e)" in engine.ACTOR


def test_a_parenthesised_gender_form_is_cut():
    assert engine._scrub_paren_gender("Je suis prêt(e) et content(e)s, chère(ère) amie.") == "Je suis prêt et contents, chère amie."
    assert engine._scrub_paren_gender("(e) seul") == "(e) seul"


def test_the_resolution_may_not_ask_the_turns_question_again():
    context = _scene_context()
    first = engine.SceneDraft.model_validate(draft(context, 0))
    chapter = engine.chapter_state(
        {"chapter": {**first.chapter.model_dump(), "id": "c1", "scene_count": 3, "resolved": False, "resolved_commitments": 0}}
    )
    recent = [
        {
            "novelty_key": "turn-1",
            "premise_fr": "Tout autre chose hier soir au parc.",
            "objective_native": "Tell Romy whether you want to try something real with her or stay friends.",
            "chapter_title_fr": chapter["title_fr"],
            "beat": "turn",
        }
    ]
    same = engine.SceneDraft.model_validate(
        {
            **draft(context, 1),
            "beat": "resolution",
            "objective_native": "Tell Romy whether you want to try something real with her and stay together.",
        }
    ).model_copy(update={"chapter": first.chapter})
    with pytest.raises(engine.StoryUnavailable, match="resolution_repeats_turn"):
        engine._validate_scene(same, _scene_context(chapter=chapter, recent_situations=recent))


def test_the_dice_are_rolled_per_learner_and_per_chapter():
    from app.services.serial import SerialThreadService

    world = SerialThreadService._load_world_bible()
    one = engine._season_projection(world, {}, seed="thread-1", chapter_index=0)
    two = engine._season_projection(world, {}, seed="thread-2", chapter_index=0)
    again = engine._season_projection(world, {}, seed="thread-1", chapter_index=0)
    assert [a["id"] for a in one["arcs"]] == [a["id"] for a in again["arcs"]], "reproducible per learner"
    assert [a["id"] for a in one["arcs"]] != [a["id"] for a in two["arcs"]], "different lives, different order"
    assert one["suggested_arc"] == one["arcs"][0]["id"]
    assert one["complication_card"] in engine.COMPLICATION_CARDS
    assert one["complication_card"] != engine._season_projection(world, {}, seed="thread-1", chapter_index=1)["complication_card"] or len(engine.COMPLICATION_CARDS) == 1
    # A completed arc is never suggested again.
    done = {a["id"]: {"stage": len(a["stages"])} for a in one["arcs"][:1]}
    assert engine._season_projection(world, done, seed="thread-1")["suggested_arc"] == one["arcs"][1]["id"]
    assert engine.chapters_opened({"resolved_chapter_questions": ["a", "b"], "chapter": {"id": "c"}}) == 3
    for word in ("suggested_arc", "complication_card"):
        assert word in engine.DIRECTOR, word


def test_two_drafts_are_written_on_the_surprise_beats_and_the_novel_one_is_kept(monkeypatch):
    """WP-59 loop engineering: setup and turn draw two candidates; the score keeps the
    one this life has not seen, and the loser's usage is still recorded."""

    context = _scene_context(
        recent_situations=[
            {"novelty_key": "seen", "premise_fr": "Romy cherche encore une idée pour une exposition dans le quartier.", "objective_native": "Offer your help with the exhibition."}
        ]
    )
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", True)
    assert engine.dual_draft_candidates(_scene_context()) == 2
    assert engine.dual_draft_candidates(_scene_context(chapter={"scene_count": 1})) == 1
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    assert engine.dual_draft_candidates(_scene_context()) == 1
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", True)

    stale = engine.SceneDraft.model_validate({**draft(context, 0), "novelty_key": "stale", "premise_fr": "Romy cherche une idée pour une exposition dans le quartier ce matin."})
    fresh = engine.SceneDraft.model_validate({**draft(context, 1), "novelty_key": "fresh", "premise_fr": "Marin fait tomber la bague de sa poche devant tout le Mistral.", "objective_native": "Say what you saw fall, and whether you keep the secret."})
    served = iter([stale, fresh])
    recorded: list[dict] = []

    def fake_json_call(system, payload, schema, on_usage=None, *, deadline):
        proposal = next(served)
        if on_usage:
            on_usage({"stage": "SceneDraft", "model": "fake", "provider": "fake", "tokens": 1, "cost_usd": 0.0})
        return proposal, {}

    monkeypatch.setattr(engine, "_json_call", fake_json_call)
    monkeypatch.setattr(engine, "CRITIC_ENABLED", False)

    class Sink:
        def add(self, event):
            recorded.append(event)

    kept, usage = engine._approved(
        engine.DIRECTOR,
        context,
        engine.SceneDraft,
        lambda p: None,
        db=Sink(),
        user=type("U", (), {"id": "u"})(),
        candidates=2,
        choose=lambda p: engine._scene_score(p, context),
    )
    assert kept.novelty_key == "fresh"
    assert len(usage) == 2, "both drafts' spend is kept"
    assert engine._scene_score(fresh, context) > engine._scene_score(stale, context)


# ---------------------------------------------------------------------------
# WP-60 — C1 prose fits the schema, and an overflow tells the retry which field
# ---------------------------------------------------------------------------


def test_a_c1_scene_fits_the_field_caps():
    """The first C1 live run lost its second day to a 118-word scene whose premise ran
    past 350 characters; the word limits, not the character caps, bound reading."""

    long_premise = (
        "Au parc des Buttes-Chaumont, Romy serre son téléphone comme si la nouvelle "
        "pouvait encore changer d'avis ; elle a reçu l'appel qu'elle attendait depuis "
        "Montréal et, pourtant, c'est vers toi qu'elle se tourne d'abord, avec ce "
        "sourire qui ne décide rien et cette question qu'elle pose comme on tend une "
        "main sous la pluie : est-ce qu'une année à Paris te fait sourire ou te donne "
        "envie de fuir, et qu'est-ce qui, chez toi, tient vraiment ?"
    )
    assert len(long_premise) > 350
    scene = engine.SceneDraft.model_validate({**draft(_scene_context(level="C1"), 0), "premise_fr": long_premise})
    assert scene.premise_fr == long_premise.strip()
    assert engine._SCENE_WORD_LIMITS["C1"] >= len(long_premise.split()) + 100


def test_an_overflowing_draft_tells_the_retry_which_field(monkeypatch, provider):
    provider.transform = lambda schema, value: (
        {**value, "objective_native": "x" * 400} if schema == "SceneDraft" else value
    )
    import time as _time

    with pytest.raises(engine.StoryUnavailable, match="invalid_story_output") as caught:
        engine._json_call(engine.DIRECTOR, {"data": 1}, engine.SceneDraft, deadline=_time.monotonic() + 60)
    assert caught.value.hint and "objective_native" in caught.value.hint
    assert "shorten" in caught.value.hint


# ---------------------------------------------------------------------------
# WP-61 — moods and trust per character, and branching on what came true
# ---------------------------------------------------------------------------


def _wp61_turn(**over):
    base = {"outcome": "met", "understood_intent": "x", "evidence_quotes": ["Oui."], "reply_fr": "Bien.", "needs_clarification": False}
    return engine.SemanticTurn.model_validate({**base, **over})


def test_a_characters_mood_and_trust_follow_the_exchange_and_others_recover():
    moods = {"lila_bonnet": {"mood": 2, "trust": 3}}
    after = engine.moods_after_turn(moods, "romy_tremblay", _wp61_turn(feeling_shift="colder"), "e1")
    assert after["romy_tremblay"]["mood"] == -1 and after["romy_tremblay"]["trust"] == 1
    assert after["lila_bonnet"]["mood"] == 1, "a week passes; feelings drift toward neutral"
    assert engine.moods_after_turn(after, "romy_tremblay", _wp61_turn(feeling_shift="colder"), "e1") == after, "idempotent per event"
    warmer = engine.moods_after_turn(after, "romy_tremblay", _wp61_turn(feeling_shift="warmer", commitments=[{"text_fr": "Je viens demain.", "source_quote": "Oui."}]), "e2")
    assert warmer["romy_tremblay"]["mood"] == 0 and warmer["romy_tremblay"]["trust"] == 3, "a promise buys trust"
    refused = engine.moods_after_turn({}, "marin_leveque", _wp61_turn(outcome="not_yet"), "e3")
    assert refused["marin_leveque"]["mood"] == -1, "a refused objective cools a character even when the actor says steady"
    assert engine.MOOD_RANGE[0] <= refused["marin_leveque"]["mood"] <= engine.MOOD_RANGE[1]


def test_the_development_the_learner_made_true_is_recorded_for_the_next_beat():
    scene = engine.SceneDraft.model_validate({**draft(_scene_context(), 0), "beat": "setup"})
    options = scene.chapter.possible_developments
    chapter = engine.chapter_after_scene(engine.open_chapter(scene), scene, _wp61_turn(development_index=2), "e1")
    assert chapter["last_development"] == options[1]
    assert chapter["developments"][0]["index"] == 2 and chapter["developments"][0]["outcome"] == "met"
    none = engine.chapter_after_scene(engine.open_chapter(scene), scene, _wp61_turn(development_index=0), "e2")
    assert "last_development" not in none
    assert "chapter.last_development" in engine.DIRECTOR and "feeling_shift" in engine.ACTOR and "moods" in engine.DIRECTOR


def test_the_score_prefers_a_hurt_character_and_a_draft_that_follows_the_branch():
    base = _scene_context()
    plain = engine.SceneDraft.model_validate(draft(base, 0))
    cold = _scene_context(moods={"romy_tremblay": {"mood": -2, "trust": 1, "last_shift": "colder"}})
    assert engine._scene_score(plain, cold) > engine._scene_score(plain, base)
    branched = _scene_context(chapter={**engine.chapter_state({"chapter": {**plain.chapter.model_dump(), "id": "c", "scene_count": 1, "resolved": False, "resolved_commitments": 0}}), "last_development": "Trouver une salle pour l'exposition dans le quartier."})
    follows = engine.SceneDraft.model_validate({**draft(base, 1), "premise_fr": "Romy a trouvé une salle pour l'exposition dans le quartier, mais elle est trop petite."}).model_copy(update={"chapter": plain.chapter})
    ignores = engine.SceneDraft.model_validate({**draft(base, 1), "premise_fr": "Marin fait tomber une bague au comptoir du Mistral."}).model_copy(update={"chapter": plain.chapter})
    assert engine._scene_score(follows, branched) > engine._scene_score(ignores, branched)


# ---------------------------------------------------------------------------
# WP-62 — la mémoire longue: chronicle, consequences, plants, callbacks, secrets
# ---------------------------------------------------------------------------


def _wp62_scene(context=None, n=0, **over):
    context = context if context is not None else _scene_context()
    return engine.SceneDraft.model_validate({**draft(context, n), **over})


def test_a_resolved_chapter_folds_into_one_chronicle_digest():
    """Day 100 cannot reference day 5 through a rolling tail of forty events. It can
    through a digest per chapter, written once, when the chapter closes."""

    scene = _wp62_scene(beat="resolution")
    turn = _wp61_turn(
        development_index=1,
        callback_fr="La salle du quartier est réservée pour samedi.",
        evidence_quotes=["Je réserve la salle."],
    )
    opened = engine.open_chapter(scene)

    # An open chapter writes nothing: a digest is what closing costs.
    still_open = engine.chapter_after_scene(
        opened, scene.model_copy(update={"beat": "setup"}), turn, "e0"
    )
    assert engine.chronicle_after_chapter(
        [], chapter=still_open, draft=scene, turn=turn, event_id="e0", day=1
    ) == []

    chapter = engine.chapter_after_scene(opened, scene, turn, "e1")
    chronicle = engine.chronicle_after_chapter(
        [], chapter=chapter, draft=scene, turn=turn, event_id="e1", day=4
    )
    row = chronicle[0]
    assert row["day"] == 4 and row["title_fr"] == chapter["title_fr"]
    assert row["question"] == chapter["dramatic_question"]
    assert row["resolved_fr"] == "La salle du quartier est réservée pour samedi."
    assert row["development"] == scene.chapter.possible_developments[0]
    assert row["quote"] == "Je réserve la salle."
    assert row["location_id"] == scene.location_id and "romy_tremblay" in row["characters"]
    assert engine.chronicle_after_chapter(
        chronicle, chapter=chapter, draft=scene, turn=turn, event_id="e1", day=4
    ) == chronicle, "idempotent per event: a replayed settle writes no second digest"

    # A chapter replaced because its commitments ran out never wrote a resolution
    # beat, and used to vanish without trace. It is remembered too.
    exhausted = {**opened, "resolved_commitments": engine.CHAPTER_RESOLVED_COMMITMENT_LIMIT}
    assert engine.chapter_closing(exhausted) is True
    assert engine.chronicle_after_chapter(
        [], chapter=exhausted, draft=scene, turn=turn, event_id="e2", day=6
    )


def test_the_chronicle_folds_into_a_season_and_still_knows_the_first_week():
    scene = _wp62_scene(beat="resolution")
    chronicle: list[dict] = []
    for index in range(30):
        chapter = {
            **engine.open_chapter(scene),
            "id": f"c{index}",
            "resolved": True,
            "title_fr": f"Chapitre {index}",
            "dramatic_question": f"Question {index} ?",
            "last_development": f"Développement {index}.",
        }
        chronicle = engine.chronicle_after_chapter(
            chronicle,
            chapter=chapter,
            draft=scene,
            turn=_wp61_turn(callback_fr=f"Fin du chapitre {index}.", evidence_quotes=[f"Jour {index}."]),
            event_id=f"e{index}",
            day=index * 4 + 1,
        )

    detailed = [row for row in chronicle if row.get("kind") != "season"]
    assert len(detailed) == engine.CHRONICLE_DETAIL_CHAPTERS
    season = chronicle[0]
    assert season["kind"] == "season"
    assert season["chapters"] == 30 - engine.CHRONICLE_DETAIL_CHAPTERS
    assert season["from_day"] == 1 and season["to_day"] == (30 - engine.CHRONICLE_DETAIL_CHAPTERS - 1) * 4 + 1
    assert len(season["facts"]) == engine.CHRONICLE_SEASON_FACTS
    assert "Chapitre 0" in season["facts"][0], (
        "the beginning of a life is the part a long memory keeps"
    )

    lines = engine.chronicle_for_prompt(chronicle)
    assert sum(len(line) + 1 for line in lines) <= engine.CHRONICLE_PROMPT_CHARS
    assert any("Chapitre 0" in line for line in lines)
    assert any("Chapitre 29" in line for line in lines)

    # And when the lines themselves are long, the trim takes the middle out: both
    # ends of the life survive, which is what a reader of a serial remembers.
    fat = [
        {**row, "title_fr": "T" * 60, "question": "Q" * 60}
        for row in detailed
    ]
    trimmed = engine.chronicle_for_prompt([season, *fat])
    assert sum(len(line) + 1 for line in trimmed) <= engine.CHRONICLE_PROMPT_CHARS
    assert trimmed[0] == season["facts"][0] and "T" * 60 in trimmed[-1]


def test_consequences_outlive_their_chapter_and_trust_never_decays():
    chapter = {"id": "c1", "resolved": True, "last_development": "Romy part à Montréal sans vous."}
    turn = _wp61_turn(
        development_index=2,
        feeling_shift="colder",
        callback_fr="Romy est partie fâchée.",
        evidence_quotes=["Je ne viens pas."],
    )
    before = {"romy_tremblay": {"mood": -1, "trust": 2}}
    after = engine.moods_after_turn(before, "romy_tremblay", turn, "e1")
    rows = engine.consequences_after_turn(
        [],
        character_id="romy_tremblay",
        chapter=chapter,
        turn=turn,
        event_id="e1",
        day=7,
        moods_before=before,
        moods_after=after,
        commitments=[],
    )
    assert {row["kind"] for row in rows} == {"branch", "mood_break"}
    branch = next(row for row in rows if row["kind"] == "branch")
    assert branch["text_fr"] == "Romy part à Montréal sans vous."
    assert branch["quote"] == "Je ne viens pas." and branch["weight"] == 3
    assert branch["day"] == 7 and branch["last_referenced"] is None
    assert next(row for row in rows if row["kind"] == "mood_break")["weight"] == 3
    assert engine.consequences_after_turn(
        rows,
        character_id="romy_tremblay",
        chapter=chapter,
        turn=turn,
        event_id="e1",
        day=7,
        moods_before=before,
        moods_after=after,
        commitments=[],
    ) == rows, "idempotent per event"

    # Chapters come and go; the ledger does not. Forty days later it is still read.
    assert [row["id"] for row in engine.top_consequences(rows, day=47)] == [
        row["id"] for row in rows
    ]
    # ...and a row a scene really used sinks for a while instead of being replayed.
    used = engine.mark_consequence_referenced(rows, branch["id"], 46)
    assert engine.top_consequences(used, day=47)[0]["kind"] == "mood_break"

    # Only surface mood decays. Trust is what the learner earned; a week off does
    # not take it away.
    drifted = engine.moods_after_turn(
        {"lila_bonnet": {"mood": 2, "trust": 4}}, "romy_tremblay", _wp61_turn(), "e9"
    )
    assert drifted["lila_bonnet"]["mood"] == 1
    assert drifted["lila_bonnet"]["trust"] == 4


def test_a_promise_nobody_ever_kept_becomes_one_consequence():
    commitments = [
        {
            "id": "c0",
            "text_fr": "Apporter les affiches samedi.",
            "source_quote": "Je les apporte samedi.",
            "status": "open",
            "witnesses": ["romy_tremblay"],
            "day": 1,
        }
    ]

    def ledger(rows, *, day, event_id):
        return engine.consequences_after_turn(
            rows,
            character_id="marin_leveque",
            chapter={"id": "ch"},
            turn=_wp61_turn(),
            event_id=event_id,
            day=day,
            moods_before={},
            moods_after={},
            commitments=commitments,
        )

    early = ledger([], day=engine.COMMITMENT_LAPSE_DAYS, event_id="e1")
    assert early == [] and "lapsed_at" not in commitments[0]
    late = ledger([], day=engine.COMMITMENT_LAPSE_DAYS + 1, event_id="e2")
    assert [row["kind"] for row in late] == ["commitment_broken"]
    assert late[0]["character_id"] == "romy_tremblay", "the person who was promised"
    assert late[0]["weight"] == 3 and late[0]["quote"] == "Je les apporte samedi."
    assert commitments[0]["lapsed_at"] == engine.COMMITMENT_LAPSE_DAYS + 1
    assert commitments[0]["status"] == "open", (
        "a promise nobody kept is still owed; the engine does not cancel it"
    )
    assert ledger(late, day=40, event_id="e3") == late, "recorded once, not every day"

    # Keeping one is a consequence too.
    commitments[0].update(status="resolved", resolved_by="e4")
    kept = ledger([], day=12, event_id="e4")
    assert [row["kind"] for row in kept] == ["commitment_kept"]


def test_an_unpaid_plant_comes_back_to_the_director_until_a_scene_pays_it():
    planter = _wp62_scene(plant_fr="Une clé en cuivre reste sur le comptoir du Mistral.")
    planted = engine.plants_after_scene(
        [], draft=planter, chapter={"id": "c1"}, event_id="e1", day=2, chapter_index=1
    )
    assert planted[0]["status"] == "open"
    assert planted[0]["text_fr"] == "Une clé en cuivre reste sur le comptoir du Mistral."
    assert engine.plants_due(planted, chapter_index=1) == [], "a fresh plant is not yet owed"
    due = engine.plants_due(planted, chapter_index=1 + engine.PLANT_OVERDUE_CHAPTERS)
    assert [row["id"] for row in due] == [planted[0]["id"]]

    payer = _wp62_scene(n=1, pays_plant_id=planted[0]["id"])
    paid = engine.plants_after_scene(
        planted, draft=payer, chapter={"id": "c2"}, event_id="e2", day=9, chapter_index=3
    )
    assert paid[0]["status"] == "paid" and paid[0]["paid_by"] == "e2" and paid[0]["paid_day"] == 9
    assert engine.plants_due(paid, chapter_index=99) == []
    # An id nobody holds is a no-op, never a lost day.
    stray = _wp62_scene(n=2, pays_plant_id="nobody")
    assert engine.plants_after_scene(
        paid, draft=stray, chapter={"id": "c3"}, event_id="e3", day=11, chapter_index=4
    ) == paid


def test_a_callback_to_a_past_that_never_happened_is_refused():
    """The one memory defect a prompt can never be trusted with: a character who
    remembers a promise the learner never made."""

    context = _scene_context(
        chronicle=[
            "j5 · La cave inondée — Comment vider la cave ? → Vous avez descendu les seaux."
        ],
        consequences=[
            {
                "id": "x:branch:0",
                "kind": "branch",
                "text_fr": "Vous avez promis d'aider Marin à déménager.",
                "quote": "Je t'aide.",
                "weight": 3,
                "day": 5,
            }
        ],
    )
    invented = _wp62_scene(
        context, callback_fr="Gus n'a jamais rendu la trompette qu'il avait empruntée."
    )
    with pytest.raises(engine.StoryUnavailable, match="fabricated_callback") as caught:
        engine._validate_scene(invented, context)
    assert caught.value.hint and "leave callback_fr empty" in caught.value.hint

    grounded = _wp62_scene(
        context,
        callback_fr="Vous aviez promis d'aider Marin à déménager samedi.",
        callback_ref="x:branch:0",
    )
    engine._validate_scene(grounded, context)
    assert grounded.callback_ref == "x:branch:0"

    # Grounded in the text but citing an id nobody holds: the scene stands, the
    # provenance is dropped — as unknown source_event_ids already are.
    stray = _wp62_scene(
        context, callback_fr="La cave inondée a été vidée avec des seaux.", callback_ref="nope"
    )
    engine._validate_scene(stray, context)
    assert stray.callback_ref is None

    # On day one nothing has happened, so every callback is invented.
    with pytest.raises(engine.StoryUnavailable, match="fabricated_callback"):
        engine._validate_scene(
            _wp62_scene(callback_fr="Vous aviez promis d'aider Marin."), _scene_context()
        )


def test_the_score_rewards_a_scene_that_uses_the_callback_it_was_offered():
    candidate = {
        "id": "x:branch:0",
        "kind": "branch",
        "text_fr": "Vous avez promis d'aider Marin à déménager.",
        "day": 5,
        "character_id": "marin_leveque",
    }
    context = _scene_context(
        callback=candidate,
        plants_due=[{"id": "p1", "text_fr": "Une clé en cuivre est restée sur le comptoir."}],
        chronicle=["j2 · La cave inondée — Comment vider la cave ? → Les seaux sont descendus."],
    )
    plain = _wp62_scene(context)
    offered = _wp62_scene(
        context,
        callback_fr="Vous avez promis d'aider Marin à déménager.",
        callback_ref="x:branch:0",
    )
    elsewhere = _wp62_scene(context, callback_fr="La cave inondée a été vidée avec des seaux.")
    pays = _wp62_scene(context, pays_plant_id="p1")
    assert engine._scene_score(offered, context) > engine._scene_score(elsewhere, context)
    assert engine._scene_score(elsewhere, context) > engine._scene_score(plain, context)
    assert engine._scene_score(pays, context) > engine._scene_score(plain, context)


def test_two_lives_are_dealt_different_callbacks_and_each_life_the_same_ones():
    live = {
        "consequences": [
            {"id": f"e{i}:branch:0", "kind": "branch", "text_fr": f"Choix {i}.", "weight": 1 + i % 3, "day": i}
            for i in range(6)
        ],
        "chronicle": [
            {"kind": "season", "season": 1, "facts": [f"j{i} · Chapitre {i} — fini." for i in range(5)]},
            {"id": "c9", "day": 40, "title_fr": "Le dernier", "resolved_fr": "Réglé.", "characters": ["romy_tremblay"]},
        ],
    }

    def dealt(seed):
        return [
            (engine.callback_candidate({**live, "resolved_chapter_questions": ["q"] * n}, seed=seed) or {}).get("id")
            for n in range(8)
        ]

    assert dealt("thread-a") == dealt("thread-a"), "reproducible for one learner"
    assert dealt("thread-a") != dealt("thread-b"), "different lives, different memories"
    # A folded season fact is still in the deck: this is how day 5 reaches day 100.
    assert any(str(value).startswith("season:") for value in dealt("thread-a") + dealt("thread-b"))
    # Only a setup beat gets one; mid-chapter the story already has its thread.
    assert engine.callback_candidate(live, seed="thread-a", beat="turn") is None
    assert engine.callback_candidate({}, seed="thread-a") is None


def test_secrets_are_state_and_the_reveal_order_is_seeded():
    cast = ["romy_tremblay", "marin_leveque", "lila_bonnet", "margaux_barman", "gus_pellerin"]
    one = engine.secrets_projection(cast, {}, seed="thread-1")
    two = engine.secrets_projection(cast, {}, seed="thread-2")
    assert sorted(one["order"]) == sorted(cast) and one["order"] != two["order"]
    assert engine.secrets_projection(cast, {}, seed="thread-1")["order"] == one["order"]
    assert set(one["states"].values()) == {"hidden"} and one["next"] == one["order"][0]

    hinted = engine.secrets_after_turn({}, "lila_bonnet", "hinted", None, allowed_reveal=one["next"])
    assert hinted["lila_bonnet"] == "hinted"
    # A reveal out of turn is downgraded to a hint, never refused: a deterministic
    # repair must not cost the learner their day (the WP-58 rule).
    out_of_turn = next(member for member in cast if member != one["next"])
    assert (
        engine.secrets_after_turn({}, out_of_turn, None, "revealed", allowed_reveal=one["next"])[out_of_turn]
        == "hinted"
    )
    assert (
        engine.secrets_after_turn({}, one["next"], None, "revealed", allowed_reveal=one["next"])[one["next"]]
        == "revealed"
    )
    assert (
        engine.secrets_after_turn({"lila_bonnet": "revealed"}, "lila_bonnet", "hinted")["lila_bonnet"]
        == "revealed"
    ), "a secret never goes back in"
    assert engine.secrets_after_turn({}, "romy_tremblay", None, None) == {}
    moved = engine.secrets_projection(cast, {one["order"][0]: "revealed"}, seed="thread-1")
    assert moved["next"] == one["order"][1]


def test_both_prompts_carry_the_long_memory():
    for word in (
        "chronicle",
        "consequences",
        "callback_fr",
        "callback_ref",
        "plants_due",
        "plant_fr",
        "pays_plant_id",
        "secret_shift",
        "secrets.next",
    ):
        assert word in engine.DIRECTOR, word
    for word in ("story.consequences", "story.secrets", "secret_shift"):
        assert word in engine.ACTOR, word


def test_the_long_memory_reaches_the_director_but_not_the_character(
    assembled_client, db_session, journey_enabled, clock, provider
):
    """The ledgers are written from a real settled day, and the knowledge boundary
    holds: the chronicle and today's callback are the director's planning surface."""

    d = driver(assembled_client, db_session)
    d.create()
    d.play(answer="Je peux apporter les affiches samedi.")
    d.finish("complete")

    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    db_session.refresh(thread)
    live = (thread.state or {})[engine.STATE_KEY]
    assert live["day_index"] == 1
    assert live["commitments"][0]["day"] == 1
    assert live["consequences"] == [] or all(row["day"] == 1 for row in live["consequences"])
    assert "chronicle" in live and "planted" in live and "secrets" in live

    clock.advance(days=1)
    d.create()
    director = [payload for schema, payload in provider.calls if schema == "SceneDraft"][-1]
    for key in ("chronicle", "consequences", "plants_due", "callback", "secrets", "day_index"):
        assert key in director, key
    assert director["day_index"] == 1
    assert director["secrets"]["states"] and director["secrets"]["next"]

    d.play(answer="Les affiches sont prêtes pour samedi.")
    actor = [payload for schema, payload in provider.calls if schema == "SemanticTurn"][-1]
    assert "chronicle" not in actor["story"] and "callback" not in actor["story"]
    assert "plants_due" not in actor["story"]
    assert set(actor["story"]["secrets"]) == {"romy_tremblay"}


# ---------------------------------------------------------------------------
# WP-63 — l'horizon de saison: shapes, agendas, threads, arc gates, season end
# ---------------------------------------------------------------------------


def _world():
    from app.services.serial import SerialThreadService

    return SerialThreadService._load_world_bible()


def test_a_chapter_is_dealt_a_shape_and_its_beats_follow_it():
    """Every chapter used to be the same four beats. It is now a hand, dealt by
    this life's own dice — and the beat guards simply follow it."""

    first = [engine.chapter_shape("thread-1", n) for n in range(12)]
    assert first == [engine.chapter_shape("thread-1", n) for n in range(12)], "reproducible"
    assert first != [engine.chapter_shape("thread-2", n) for n in range(12)], "per learner"
    assert len(set(first)) >= 3, first
    # No two identical shapes in a row, when the previous one is handed back.
    previous = None
    dealt = []
    for n in range(20):
        previous = engine.chapter_shape("thread-1", n, previous)
        dealt.append(previous)
    assert all(a != b for a, b in zip(dealt, dealt[1:], strict=False)), dealt
    assert set(dealt) <= set(engine.CHAPTER_SHAPES)

    # The beats — and therefore the required beat and the chapter's length.
    assert engine.required_beats({"scene_count": 1, "shape": "two_hander"}) == ("turn", "resolution")
    assert engine.required_beats({"scene_count": 1, "shape": "ensemble"}) == ("complication",)
    assert engine.required_beats({"scene_count": 3, "shape": "ensemble"}) == ("turn", "resolution")
    assert engine.required_beats({"scene_count": 4, "shape": "ensemble"}) == ("resolution",)
    assert engine.chapter_closing({"scene_count": 3, "shape": "two_hander"}) is True
    assert engine.chapter_closing({"scene_count": 4, "shape": "ensemble"}) is False
    # A chapter stored before shapes existed is a standard four-beat chapter.
    assert engine.required_beats({"scene_count": 2}) == ("turn", "resolution")
    assert engine.chapter_state({"chapter": {"scene_count": 1}})["shape"] == engine.DEFAULT_SHAPE


def test_a_two_hander_keeps_two_voices_and_a_bottle_keeps_one_room():
    context = _scene_context(chapter_shape={"shape": "two_hander"})
    crowded = engine.SceneDraft.model_validate(draft(context, 0))
    crowded.panels[1].dialogue.append(
        engine.Dialogue(character_id="lila_bonnet", text_fr="Moi j'ai le temps.")
    )
    with pytest.raises(engine.StoryUnavailable, match="two_hander_crowded") as info:
        engine._validate_scene(crowded, context)
    assert "lila_bonnet" in info.value.feedback and "two-hander" in info.value.feedback
    engine._validate_scene(engine.SceneDraft.model_validate(draft(context, 0)), context)

    room = {
        "title_fr": "Le huis clos",
        "dramatic_question": "Qui restera au comptoir ?",
        "possible_developments": ["Rester.", "Partir."],
        "id": "c1",
        "shape": "bottle",
        "scene_count": 1,
        "location_id": "le_mistral",
        "resolved": False,
        "resolved_commitments": 0,
    }
    bottle = _scene_context(chapter=engine.chapter_state({"chapter": room}))
    left = engine.SceneDraft.model_validate(
        {**draft(bottle, 1), "location_id": "brocante", "beat": "complication"}
    )
    left = left.model_copy(
        update={
            "chapter": engine.Chapter.model_validate(
                {key: room[key] for key in ("title_fr", "dramatic_question", "possible_developments")}
            )
        }
    )
    with pytest.raises(engine.StoryUnavailable, match="bottle_left_the_room") as info:
        engine._validate_scene(left, bottle)
    assert "le_mistral" in info.value.feedback
    stayed = left.model_copy(update={"location_id": "le_mistral"})
    engine._validate_scene(stayed, bottle)


def test_an_arc_advances_only_when_its_stage_really_happened():
    """«an arc stage advances whether or not its content happened» (WP-63 §1).

    The claim is the draft's, the gates are the bible's, and a chapter that claims
    nothing is a side story — a real evening in this life that did not move the season.
    """

    arcs = [
        {
            "id": "romy_romance",
            "min_episodes_between_stages": 3,
            "stages": [
                {"id": "spark", "sets": {"romy.user_tension": "spark"}},
                {"id": "first_real", "entry_requires": {"user.has_met_group": True}},
                {"id": "almost"},
            ],
        }
    ]
    base = engine.SceneDraft.model_validate(
        {**draft(_scene_context(), 0), "beat": "resolution", "arc_id": "romy_romance"}
    )
    settled = engine.SemanticTurn.model_validate(turn_fixture("D'accord."))

    side = engine.chapter_after_scene(engine.open_chapter(base), base, settled, "e0")
    assert side["resolved"] is True and side["side_story"] is True
    assert engine.arc_progress_after_scene({}, side, arcs, "e0", day=4) == {}, (
        "a chapter that claims no stage leaves the season where it was"
    )
    digest = engine.chapter_digest(side, base, settled, event_id="e0", day=4)
    assert digest["side_story"] is True and digest["shape"] == engine.DEFAULT_SHAPE

    claimed = base.model_copy(update={"advances_arc": True, "arc_stage_id": "spark"})
    chapter = engine.chapter_after_scene(engine.open_chapter(claimed), claimed, settled, "e1")
    assert chapter["side_story"] is False and chapter["stage_reached"] is True
    progress = engine.arc_progress_after_scene({}, chapter, arcs, "e1", day=4)
    assert progress["romy_romance"] == {"stage": 1, "last_event_id": "e1", "last_day": 4}

    # `min_episodes_between_stages`: three episodes, not three scenes of the same week.
    too_soon = engine.arc_progress_after_scene(progress, chapter, arcs, "e2", day=6)
    assert too_soon["romy_romance"]["stage"] == 1, "the next stage is still too close"
    # …and `entry_requires`: the flag comes from another arc's stage, not from a wish.
    blocked = engine.arc_progress_after_scene(progress, chapter, arcs, "e3", day=9, flags={})
    assert blocked["romy_romance"]["stage"] == 1
    allowed = engine.arc_progress_after_scene(
        progress, chapter, arcs, "e4", day=9, flags={"user.has_met_group": True}
    )
    assert allowed["romy_romance"]["stage"] == 2

    # The flags are derived from the stages this life actually reached.
    assert engine.arc_flags(arcs, {"romy_romance": {"stage": 1}}) == {"romy.user_tension": "spark"}
    projection = engine._season_projection(
        {"season_arcs": arcs, "season_number": 1}, progress, day=6
    )
    assert projection["arcs"][0]["blocked_by"] == "entry_requires:user.has_met_group"
    assert projection["arcs"][0]["next_stage"]["id"] == "first_real"
    waiting = engine._season_projection(
        {"season_arcs": arcs, "season_number": 1},
        progress,
        day=6,
        flags={"user.has_met_group": True},
    )
    assert waiting["arcs"][0]["blocked_by"] == "min_episodes_between_stages:3"
    ready = engine._season_projection(
        {"season_arcs": arcs, "season_number": 1},
        progress,
        day=9,
        flags={"user.has_met_group": True},
    )
    assert ready["arcs"][0]["blocked_by"] is None
    # A blocked arc is not the arc to play — but a season with nothing else left is
    # still told about one, because silence is not a story.
    assert projection["suggested_arc"] == "romy_romance"


def test_a_played_problem_may_come_back_once_as_an_escalation():
    """WP-58 forbade any problem from returning, so nothing could ever get worse."""

    context = _scene_context(
        variety={**engine._variety([], [], []), "used_problems": ["radiateur_fuite"]},
        consequences=[{"id": "e7:branch:0", "text_fr": "Vous n'avez pas rappelé le plombier."}],
        plants_due=[{"id": "e9:plant", "text_fr": "La clé du compteur reste sur la table."}],
        escalated_problems=[],
    )
    again = {**draft(context, 0), "beat": "setup", "problem_key": "radiateur_fuite"}
    with pytest.raises(engine.StoryUnavailable, match="stale_problem") as info:
        engine._validate_scene(engine.SceneDraft.model_validate(again), context)
    assert "escalates_ref" in info.value.feedback and "e7:branch:0" in info.value.feedback

    # A ref nobody holds is not a licence.
    invented = {**again, "escalates_ref": "e99:branch:0"}
    with pytest.raises(engine.StoryUnavailable, match="stale_problem"):
        engine._validate_scene(engine.SceneDraft.model_validate(invented), context)

    escalation = {**again, "escalates_ref": "e9:plant"}
    engine._validate_scene(engine.SceneDraft.model_validate(escalation), context)

    # Once. The second time the same problem returns, the ledger says no.
    spent = _scene_context(
        variety=context["variety"],
        consequences=context["consequences"],
        plants_due=context["plants_due"],
        escalated_problems=["radiateur_fuite"],
    )
    with pytest.raises(engine.StoryUnavailable, match="stale_problem") as info:
        engine._validate_scene(engine.SceneDraft.model_validate(escalation), spent)
    assert "Already escalated once" in info.value.feedback
    assert engine.escalation_refs(context) == {"e7:branch:0", "e9:plant"}


def test_the_cast_has_a_week_of_its_own_and_the_learner_only_hears_about_it():
    world = _world()
    plans = engine.character_agendas(world)
    assert set(plans) == {member["id"] for member in world["cast"]}
    assert all(4 <= len(steps) <= 6 for steps in plans.values()), {
        key: len(value) for key, value in plans.items()
    }
    assert all(
        step.get("meanwhile_fr") and step.get("id") and step.get("witnesses")
        for steps in plans.values()
        for step in steps
    )

    agendas: dict = {}
    ticks = []
    for chapter_index in range(12):
        agendas, event = engine.agenda_tick(
            world, agendas, seed="thread-1", chapter_index=chapter_index, day=chapter_index * 4
        )
        ticks.append(event["character_id"] if event else None)
        if event:
            # A witness rule, not a broadcast: the learner is nobody's witness, and
            # the character whose week it was is not their own hearsay.
            assert event["witnesses"] and event["character_id"] not in event["witnesses"]
            assert set(event["witnesses"]) <= set(plans)
            assert event["kind"] == "meanwhile" and event["summary_fr"]
    assert any(ticks) and any(tick is None for tick in ticks), (
        "some chapters move somebody's week along, and some are quiet"
    )
    assert sum(1 for tick in ticks if tick) <= len(ticks), "at most one agenda per chapter"
    assert len({tick for tick in ticks if tick}) > 1, "not always the same person"

    other = []
    theirs: dict = {}
    for chapter_index in range(12):
        theirs, event = engine.agenda_tick(
            world, theirs, seed="thread-2", chapter_index=chapter_index, day=chapter_index * 4
        )
        other.append(event["character_id"] if event else None)
    assert other != ticks, "two lives, two sets of dice"

    # The projection is compact, and a finished agenda drops out of it.
    projection = engine.agendas_projection(world, agendas)
    assert len(projection) <= engine.AGENDA_PROMPT_LIMIT
    assert all(set(row) == {"character_id", "now", "done"} for row in projection)
    done = {key: {"step": len(steps)} for key, steps in plans.items()}
    assert engine.agendas_projection(world, done) == []
    assert engine.agenda_tick(world, done, seed="thread-1", chapter_index=1, day=4)[1] is None


def test_the_seasons_long_questions_are_state_not_prose():
    world = _world()
    authored = engine.season_threads(world)
    assert len(authored) == 5 and all(row["key"].startswith("s1:") for row in authored)
    assert all(row["text_fr"] and row["text"] for row in authored), "French for the page"
    keys = [row["key"] for row in authored]

    scene = engine.SceneDraft.model_validate(
        {**draft(_scene_context(), 0), "season_thread": keys[1], "thread_shift": "developing"}
    )
    threads = engine.threads_after_scene(
        {}, draft=scene, known_keys=keys, closing=False, day=3, event_id="e1"
    )
    assert threads[keys[1]]["state"] == "developing"
    # Idempotent per event, and never backwards.
    assert engine.threads_after_scene(
        threads, draft=scene, known_keys=keys, closing=False, day=9, event_id="e1"
    ) == threads
    back = scene.model_copy(update={"thread_shift": "developing"})
    assert engine.threads_after_scene(
        {**threads, keys[1]: {"state": "closed"}},
        draft=back, known_keys=keys, closing=True, day=9, event_id="e2",
    )[keys[1]]["state"] == "closed"
    # `closed` mid-chapter is honest about what happened: the chapter is not over.
    early = scene.model_copy(update={"thread_shift": "closed"})
    assert engine.threads_after_scene(
        {}, draft=early, known_keys=keys, closing=False, day=3, event_id="e3"
    )[keys[1]]["state"] == "developing"
    assert engine.threads_after_scene(
        {}, draft=early, known_keys=keys, closing=True, day=3, event_id="e4"
    )[keys[1]]["state"] == "closed"
    # A key nobody authored is dropped by the validator, never a lost day.
    stray = engine.SceneDraft.model_validate(
        {**draft(_scene_context(), 0), "season_thread": "s9:9", "thread_shift": "closed"}
    )
    context = _scene_context()
    context["world"]["open_threads"] = authored
    engine._validate_scene(stray, context)
    assert stray.season_thread is None and stray.thread_shift is None

    live = {"threads": threads}
    projected = engine.threads_projection(world, live)
    assert [row["state"] for row in projected] == [
        "developing" if row["key"] == keys[1] else "open" for row in projected
    ]
    closed = engine.close_open_threads(threads, keys, day=40)
    assert {row["state"] for row in engine.threads_projection(world, {"threads": closed})} == {"closed"}


def test_the_season_ends_in_a_finale_an_interlude_and_a_second_season(tmp_path):
    world = _world()
    arcs = list(world["season_arcs"])
    assert engine.season_completion(arcs, {}) == 0.0
    # Everything played except the last arc's last two stages: over the ratio, and
    # not the trivial "every stage done" case.
    almost = {arc["id"]: {"stage": len(arc["stages"])} for arc in arcs}
    almost[arcs[-1]["id"]] = {"stage": len(arcs[-1]["stages"]) - 2}
    assert engine.SEASON_COMPLETE_RATIO <= engine.season_completion(arcs, almost) < 1.0

    live = {"season_chapters": 12, "chapter": {"resolved": True}, "arc_progress": almost}
    assert engine.season_stage_after_chapter(
        live, chapter={"resolved": True}, world_arcs=arcs, arc_progress=almost
    ) == "finale"
    # A season that never advances an arc still ends: the chapter ceiling is the
    # promise that `suggested_arc` can never quietly run out with no finale.
    assert engine.season_stage_after_chapter(
        {"season_chapters": engine.SEASON_MAX_CHAPTERS},
        chapter={"resolved": True},
        world_arcs=arcs,
        arc_progress={},
    ) == "finale"
    assert engine.season_stage_after_chapter(
        {}, chapter={"finale": True}, world_arcs=arcs, arc_progress=almost
    ) == "interlude"

    # The finale is built from what this learner did, not from a new plot.
    finale_live = {
        "consequences": [
            {"id": "e1:branch:0", "kind": "branch", "text_fr": "Vous avez couvert Gus.", "weight": 3, "day": 20},
        ],
        "planted": [
            {"id": "e2:plant", "text_fr": "La clé du compteur.", "status": "open", "chapter_index": 0, "day": 9},
        ],
        "threads": {},
        "resolved_chapter_questions": ["q"] * 20,
    }
    finale = engine.finale_context(finale_live, world=world, day=80)
    assert finale["heaviest"][0]["id"] == "e1:branch:0"
    assert finale["unpaid_plants"][0]["id"] == "e2:plant"
    assert len(finale["open_threads"]) == 5 and finale["instruction"]

    beat = engine.interlude_beat("thread-1", 30)
    assert beat["id"] and beat["summary"] and "never present this as a finale" in beat["instruction"]

    # The rollover: a new bible, the same life.
    thread = SimpleNamespace(id="thread-1", world_bible=world)
    rolled = {
        **finale_live,
        "season_index": 1,
        "arc_progress": almost,
        "agendas": {"marin_leveque": {"step": 2}},
        "escalated_problems": {"radiateur": {"day": 4}},
        "season_chapters": 30,
        "secrets": {"lila_bonnet": "revealed"},
        "chronicle": [{"id": "c1", "season": 1, "day": 4}],
    }
    assert engine.roll_over_season(None, thread, rolled, day=90) is True
    assert rolled["season_index"] == 2
    assert thread.world_bible["season_number"] == 2
    assert thread.world_bible["cast"] == world["cast"], "the cast survives the season"
    # What the learner lived is carried; only the season's own counters reset.
    assert rolled["chronicle"] and rolled["secrets"] == {"lila_bonnet": "revealed"}
    assert rolled["consequences"] and rolled["planted"]
    assert rolled["arc_progress"] == {} and rolled["agendas"] == {}
    assert rolled["escalated_problems"] == {} and rolled["season_chapters"] == 0
    assert rolled["season_stage"] == "running"
    assert rolled["world_flags"], "what season one established is still true"
    assert rolled["threads_archive"] and rolled["seasons"] == [{"season": 1, "ended_day": 90}]

    # And season two is a season: its own situation, its own arcs, its own agendas.
    second = thread.world_bible
    assert engine.season_situation(second)["your_arc"] == second["season_two_situation"]["your_arc"]
    threads = engine.season_threads(second)
    assert [row["key"] for row in threads] == [f"s2:{n}" for n in range(5)]
    assert all(row["text_fr"] for row in threads)
    assert {arc["id"] for arc in second["season_arcs"]} == {
        "romy_montreal_deadline",
        "lila_berlin_opening",
        "gus_creteil_truth",
        "marin_father_call",
        "user_chosen_paris",
    }
    assert set(engine.character_agendas(second)) == {member["id"] for member in second["cast"]}
    assert engine.season_completion(list(second["season_arcs"]), {}) == 0.0


def test_the_letter_chapter_is_a_flag_and_a_seam_and_nothing_else():
    """WP-64/65 own the letter. The story engine only says where one belongs."""

    assert engine.letter_chapter_seam({"chapter": {"shape": "bottle"}}) is None
    seam = engine.letter_chapter_seam(
        {"chapter": {"id": "c1", "shape": "letter", "scene_count": 2, "character_id": "romy_tremblay"}}
    )
    assert seam == {
        "chapter_id": "c1",
        "shape": "letter",
        "beat": engine.LETTER_BEAT,
        "character_id": "romy_tremblay",
        "is_next_beat": True,
    }
    assert engine.letter_chapter_seam({"chapter": {"id": "c1", "shape": "letter", "scene_count": 0}})[
        "is_next_beat"
    ] is False
    # The engine writes no letter and needs no new beat for one.
    assert engine.CHAPTER_SHAPES["letter"] == engine.CHAPTER_BEATS


def test_the_director_reads_the_horizon_and_the_character_does_not(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    d.create()
    director = [payload for schema, payload in provider.calls if schema == "SceneDraft"][-1]
    for key in ("agendas", "chapter_shape", "season", "escalated_problems"):
        assert key in director, key
    assert director["season"]["phase"] == "running" and director["season"]["number"] == 1
    assert director["chapter_shape"]["beats"], director["chapter_shape"]
    assert director["agendas"] and all(row["now"] for row in director["agendas"])
    threads = director["world"]["open_threads"]
    assert all(row["state"] == "open" and row["key"] for row in threads)
    assert all(arc["blocked_by"] is None or arc["blocked_by"] for arc in director["world"]["arcs"])

    d.play(answer="Je peux apporter les affiches samedi.")
    actor = [payload for schema, payload in provider.calls if schema == "SemanticTurn"][-1]
    story = actor["story"]
    for key in ("season", "escalated_problems", "chapter_shape"):
        assert key not in story, key
    assert "open_threads" not in story["world"]
    assert all(row["character_id"] == "romy_tremblay" for row in story["agendas"])


def test_both_prompts_carry_the_season_horizon():
    for word in (
        "chapter.shape",
        "agendas",
        "season_thread",
        "thread_shift",
        "advances_arc",
        "arc_stage_id",
        "escalates_ref",
        "blocked_by",
        "season.phase",
        "two_hander",
        "bottle",
        "ensemble",
    ):
        assert word in engine.DIRECTOR, word


def test_a_thread_stored_before_the_season_horizon_still_loads():
    """No migration: a life mid-chapter on the day this ships keeps playing.

    Every WP-63 read is defaulted, so a chapter with no shape is the four-beat
    chapter it has always been, a life with no agendas has a cast that has done
    nothing yet, and a season with no counters is simply running.
    """

    old = {
        "chapter": {
            "id": "c1",
            "title_fr": "Avant",
            "dramatic_question": "Qui paiera le plombier ?",
            "possible_developments": ["Payer.", "Attendre."],
            "scene_count": 2,
            "resolved_commitments": 0,
            "resolved": False,
        },
        "events": [{"id": "e1", "witnesses": ["romy_tremblay"], "summary_fr": "…"}],
        "commitments": [],
    }
    assert engine.season_phase(old) == "running"
    assert engine.chapters_total(old) == 1
    assert engine.planned_shape(old, seed="thread-1") == engine.DEFAULT_SHAPE
    state = engine.chapter_state(old)
    assert state["shape"] == engine.DEFAULT_SHAPE and state["required_beat"] == "turn"
    assert engine.chapter_beats(state) == engine.CHAPTER_BEATS
    assert engine.threads_projection(_world(), old)[0]["state"] == "open"
    assert engine.agendas_projection(_world(), old.get("agendas") or {})
    assert engine.agenda_tick(_world(), {}, seed="t", chapter_index=0, day=1)[0] is not None
    assert engine.letter_chapter_seam(old) is None
    assert engine.season_completion(list(_world()["season_arcs"]), {}) == 0.0
    assert engine.finale_context(old, world=_world(), day=3)["open_threads"]


def test_the_director_is_told_what_the_open_chapter_already_asked():
    """Live A2 review 2026-09-21: the resolution re-asked the turn's task and lost the day."""

    live = {
        "chapter": {"id": "c1", "title_fr": "Le radiateur", "dramatic_question": "?", "beats": []},
        "recent_situations": [
            {"chapter_title_fr": "Autre", "objective_native": "Order a coffee."},
            {"chapter_title_fr": "Le radiateur", "objective_native": "Offer two times."},
            {"chapter_title_fr": "Le radiateur", "objective_native": "Choose a time."},
        ],
    }
    projected = engine.chapter_state(live)
    assert projected["already_asked"] == ["Offer two times.", "Choose a time."]
    assert "already_asked" not in live["chapter"], "a projection, never stored"
    assert "chapter.already_asked" in engine.DIRECTOR


def test_a_parenthetical_constraint_is_not_a_second_ask():
    """Paid A2 re-run 2026-09-21: "(one sentence, max two short clauses)" cost a day."""

    engine._check_objective_scope(
        "Write one short sentence in French that Lila can write to Marin to propose a calm, "
        "private meeting tomorrow (one sentence, max two short clauses).",
        "A2",
    )
    with pytest.raises(engine.StoryUnavailable, match="objective_too_complex"):
        engine._check_objective_scope(
            "Greet Marin, then ask about the ring, and also propose a time, and explain why.", "A2"
        )


def test_the_learners_act_rotates_not_only_the_setting():
    """Paid B1 review 2026-09-21: nine of ten objectives were «tell X whether they should…»."""

    assert engine.speech_act("Tell Gus whether he should tell the truth now or delay.") == "advice"
    assert engine.speech_act("Dis à Marin s'il doit demander Lila en mariage maintenant.") == "advice"
    assert engine.speech_act("Refuse Margaux's invitation politely and propose another day.") == "other"
    advice = {"objective_native": "Tell Romy whether she should stay in Paris.", "character_id": "romy_tremblay", "location_id": "le_mistral"}
    other = {"objective_native": "Thank Lila for the portrait.", "character_id": "lila_bonnet", "location_id": "le_mistral"}
    cast = [{"id": "romy_tremblay"}, {"id": "lila_bonnet"}]
    places = [{"id": "le_mistral"}]
    pressed = engine._variety([other, advice, advice], cast, places)
    assert pressed["recent_acts"] == ["other", "advice", "advice"]
    assert "DIFFERENT act" in pressed["act_rule"]
    assert "DIFFERENT act" not in engine._variety([advice, other], cast, places)["act_rule"]
    assert "variety.act_rule" in engine.DIRECTOR
