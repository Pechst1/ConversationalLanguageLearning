"""Regression tests for the Serial World spine."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from uuid import UUID
from typing import Any

from fastapi.testclient import TestClient

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.schemas.serial import EpisodeRead, SerialThreadRead
from app.services.graphic_novel import GraphicNovelScheduler
from app.services.missions import MissionScheduler, serialize_mission
from app.services.news_service import NewsService
from app.services.serial_arc_planner import SerialArcPlanner, cefr_generation_profile
from app.services.serial import SerialThreadService, WORLD_BIBLE_PATH


def _run(coro):
    return asyncio.run(coro)


def _token(client: TestClient) -> str:
    email = f"{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "serial-secure",
            "target_language": "fr",
            "native_language": "en",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "serial-secure"})
    return response.json()["access_token"]


def _user(db_session, *, email: str = "serial@example.com") -> User:
    user = User(
        id=uuid4(),
        email=email,
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_world_bible_world_reference_assets_exist():
    world = json.loads(WORLD_BIBLE_PATH.read_text(encoding="utf-8"))
    visual_design = world["visual_design"]
    characters = visual_design["characters"]
    locations = visual_design["locations"]
    props = visual_design["props"]
    public_root = Path(__file__).resolve().parents[1] / "web-frontend" / "public"
    expected_characters = {
        "user",
        "marin_leveque",
        "lila_bonnet",
        "augustin_de_roncourt",
        "romy_tremblay",
        "margaux_barman",
        "landlord_marchand",
    }
    expected_locations = {
        "le_mistral": [
            "assets/serial/locations/le_mistral-booth.png",
            "assets/serial/locations/le_mistral-counter.png",
        ],
        "user_apartment": ["assets/serial/locations/user_apartment.png"],
        "marin_lila_flat": ["assets/serial/locations/marin_lila_flat.png"],
        "newsroom": ["assets/serial/locations/newsroom.png"],
        "ngo_office": ["assets/serial/locations/ngo_office.png"],
        "marche_canal": ["assets/serial/locations/marche_canal.png"],
        "buttes_chaumont": ["assets/serial/locations/buttes_chaumont.png"],
        "metro_platform": ["assets/serial/locations/metro_platform.png"],
        "gus_loft": ["assets/serial/locations/gus_loft.png"],
        "brocante": ["assets/serial/locations/brocante.png"],
        "office_admin": ["assets/serial/locations/office_admin.png"],
    }

    assert visual_design["status"] == "assets-locked-v2"
    assert expected_characters.issubset(characters)
    for character_id in expected_characters:
        design = characters[character_id]
        assert design["reference_images"] == [f"assets/serial/characters/{character_id}/model-sheet.png"]
        assert design["style_ref"] == f"assets/serial/characters/{character_id}/model-sheet.png"
        assert (public_root / design["style_ref"]).is_file()
    for location_id, references in expected_locations.items():
        assert locations[location_id]["reference_images"] == references
        for reference in references:
            assert (public_root / reference).is_file()
    assert props["le_mistral_booth"]["reference_images"] == ["assets/serial/props/le_mistral_booth.png"]
    assert (public_root / props["le_mistral_booth"]["reference_images"][0]).is_file()


async def _fake_seed(self, interests=None, refresh=False):  # type: ignore[no-untyped-def]
    return {
        "mode": "serial_test_seed",
        "title": "Le quartier parle d'une panne de chauffage",
        "summary": "A local test seed routed through Romy.",
        "source": "Serial test",
        "items": [
            {
                "title": "Panne de chauffage dans le quartier",
                "summary": "Les voisins s'organisent.",
                "source": "Serial test",
                "url": "",
            }
        ],
    }


def test_thread_episode_roundtrip(db_session):
    user = _user(db_session, email="serial-roundtrip@example.com")
    thread = SerialThread(
        user_id=user.id,
        world_bible={
            "logline": "A newcomer settles into the fictional town of Saint-Renan.",
            "setting": {"town": "Saint-Renan", "era": "present day", "tone": "warm, wry"},
            "protagonist": {"name": "Toi", "situation": "just arrived, renting an apartment"},
            "cast": [{"id": "landlord_marchand", "name": "M. Marchand", "role": "landlord"}],
            "register_map": {"landlord_marchand": "vous"},
        },
        state={"heating_fixed": False, "marchand_trust": "neutral", "has_met_neighbor": False},
        news_seed={},
    )
    db_session.add(thread)
    db_session.flush()
    db_session.add_all(
        [
            SerialEpisode(
                thread_id=thread.id,
                episode_index=0,
                kind="mission",
                hook={},
                hook_from_previous={},
                state_delta={},
                status="available",
            ),
            SerialEpisode(
                thread_id=thread.id,
                episode_index=1,
                kind="feuilleton",
                hook={
                    "text": "On rentre, et il y a une enveloppe glissée sous la porte.",
                    "unresolved_question": "Who left the envelope, and what does it want?",
                    "next_beat_kind": "mission",
                    "teaser": "Demain : il faut répondre.",
                },
                hook_from_previous={},
                state_delta={"set": {"heating_fixed": True}, "reason": "ok", "source": {"type": "mission"}},
                status="completed",
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(thread)

    thread_payload = SerialThreadRead.model_validate(thread).model_dump(mode="json")
    episode_payload = EpisodeRead.model_validate(thread.episodes[0]).model_dump(mode="json")

    assert thread_payload["world_bible"]["logline"].startswith("A newcomer")
    assert thread_payload["state"]["heating_fixed"] is False
    assert episode_payload == {
        "thread_id": str(thread.id),
        "episode_index": 0,
        "kind": "mission",
        "mission_id": None,
        "scene_id": None,
        "hook_from_previous": {},
        "status": "available",
        "location_id": None,
        "brief_payload": {},
    }


def test_existing_thread_syncs_locked_character_assets(db_session):
    user = _user(db_session, email="serial-asset-sync@example.com")
    thread = SerialThread(
        user_id=user.id,
        world_bible={
            "logline": "Old active serial copy",
            "initial_state": {},
            "visual_design": {
                "status": "design-contract-v1-text-seeds",
                "characters": {
                    "romy_tremblay": {
                        "reference_images": [],
                        "style_ref": "",
                    }
                },
            },
        },
        state={},
        news_seed={},
    )
    db_session.add(thread)
    db_session.commit()

    existing = _run(SerialThreadService(db_session).get_or_create_thread(user))

    assert existing.id == thread.id
    assert existing.world_bible["logline"] == "Old active serial copy"
    assert existing.world_bible["world_bible_version"] == "paris-v2"
    assert {arc["id"] for arc in existing.world_bible["season_arcs"]} >= {
        "marin_proposal",
        "lila_berlin_secret",
        "gus_aristocracy",
        "romy_romance",
        "user_settling_in",
    }
    assert existing.world_bible["visual_design"]["status"] == "assets-locked-v2"
    assert existing.world_bible["visual_design"]["characters"]["romy_tremblay"]["reference_images"] == [
        "assets/serial/characters/romy_tremblay/model-sheet.png"
    ]
    assert existing.world_bible["visual_design"]["locations"]["le_mistral"]["reference_images"] == [
        "assets/serial/locations/le_mistral-booth.png",
        "assets/serial/locations/le_mistral-counter.png",
    ]
    assert set(existing.state["arcs"]) >= {"marin_proposal", "lila_berlin_secret", "gus_aristocracy"}
    assert existing.state["cast_last_seen"]["romy_tremblay"] == -1
    assert existing.state["relationships"]["lila_bonnet"]["register"] == "vous"


def test_serial_arc_planner_rotates_arcs_cast_and_spacing(db_session):
    user = _user(db_session, email="serial-planner@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    arc_gaps = {
        arc["id"]: int(arc.get("min_episodes_between_stages") or 0)
        for arc in thread.world_bible.get("season_arcs", [])
    }
    main_cast = [
        member["id"]
        for member in thread.world_bible.get("cast", [])
        if member.get("id") not in {"user", "landlord_marchand"}
    ]
    last_advanced: dict[str, int] = {}
    advanced_arcs: set[str] = set()
    plans: list[dict[str, Any]] = []

    for episode_index in range(1, 13):
        thread.current_episode_index = episode_index
        brief = SerialArcPlanner(thread).plan_next_episode("see" if episode_index % 2 else "act")
        payload = brief.model_dump(mode="json")
        plans.append(payload)
        a_plot = payload["a_plot"]
        arc_id = a_plot.get("arc_id")
        if a_plot.get("advance_on_completion") and arc_id:
            if arc_id in last_advanced:
                assert episode_index - last_advanced[arc_id] >= arc_gaps[arc_id]
            last_advanced[arc_id] = episode_index
            advanced_arcs.add(arc_id)
            state = dict(thread.state or {})
            arcs = dict(state.get("arcs") or {})
            arcs[arc_id] = {
                "stage": a_plot["stage_id"],
                "stage_index": a_plot["stage_index"],
                "advanced_at_episode": episode_index,
            }
            state["arcs"] = arcs
            cast_last_seen = dict(state.get("cast_last_seen") or {})
            for character_id in payload["required_cast"]:
                cast_last_seen[character_id] = episode_index
            state["cast_last_seen"] = cast_last_seen
            thread.state = state
        db_session.add(
            SerialEpisode(
                thread_id=thread.id,
                episode_index=episode_index,
                kind="feuilleton" if payload["beat"] == "see" else "mission",
                hook={},
                hook_from_previous={},
                state_delta={},
                status="completed",
                brief_payload=payload,
                location_id=payload.get("location_id"),
            )
        )
        db_session.add(thread)
        db_session.commit()
        db_session.refresh(thread)

    assert len(advanced_arcs) >= 3
    for previous, current in zip(plans, plans[1:]):
        assert current["structure"] != previous["structure"]
    for index, plan in enumerate(plans, start=1):
        if plan["include_news_panel"]:
            assert plan["structure"] == "news_edition" or (index - 1) % 7 == 0
    for start in range(0, len(plans) - 3):
        window_cast = {character_id for plan in plans[start : start + 4] for character_id in plan["required_cast"]}
        assert set(main_cast).issubset(window_cast)


def test_cefr_generation_profile_is_monotonic():
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    min_words = [cefr_generation_profile(level)["min_words"] for level in levels]
    objective_counts = [cefr_generation_profile(level)["mission_objective_count"] for level in levels]

    assert min_words == sorted(min_words)
    assert objective_counts == sorted(objective_counts)


def test_serial_mission_contract_honors_relationship_register(db_session):
    user = _user(db_session, email="serial-register@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    state = dict(thread.state or {})
    relationships = dict(state["relationships"])
    relationships["lila_bonnet"] = {**relationships["lila_bonnet"], "register": "tu", "closeness": 4}
    state["relationships"] = relationships
    thread.state = state
    db_session.add(thread)
    db_session.flush()
    mission = RealWorldMission(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=4,
        title="Register test",
        brief="Ask Lila for help without sounding distant.",
        objectives=[],
        prompt_payload={"messenger": {}},
        source_snapshot={},
    )
    db_session.add(mission)
    db_session.flush()

    SerialThreadService(db_session)._apply_brief_mission_contract(
        mission=mission,
        thread=thread,
        brief_payload={
            "episode_index": 4,
            "required_cast": ["lila_bonnet"],
            "hook_guidance": "Lila wants a warmer reply.",
            "stakes_level": 2,
            "cefr_profile": {"min_words": 35},
        },
    )

    assert mission.prompt_payload["serial_character_id"] == "lila_bonnet"
    assert mission.prompt_payload["target_register"] == "tu / warm informal"
    assert mission.prompt_payload["messenger"]["contact_name"] == "Lila Bonnet"


def test_serial_relationship_completion_can_unlock_tu(db_session, monkeypatch):
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    user = _user(db_session, email="serial-tu-switch@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    state = dict(thread.state or {})
    relationships = dict(state["relationships"])
    relationships["lila_bonnet"] = {
        **relationships["lila_bonnet"],
        "closeness": 2,
        "register": "vous",
    }
    state["relationships"] = relationships
    thread.state = state
    thread.current_episode_index = 3
    db_session.add(thread)
    db_session.flush()
    mission = RealWorldMission(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=3,
        title="Help Lila",
        brief="Send Lila the practical next step.",
        objectives=[],
        prompt_payload={"serial_character_id": "lila_bonnet"},
        recap_payload={
            "outcome": {
                "reply_text": "Parfait, on se tutoie maintenant.",
                "state_delta": {
                    "set": {"user.last_mission_success": True},
                    "source": {"type": "mission", "score_0_4": 4},
                },
                "hook": {"text": "Lila sourit au changement.", "next_beat_kind": "feuilleton"},
            }
        },
    )
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id,
            user_id=user.id,
            mode="writing",
            answer_payload={"text": "Je peux passer demain et t'aider avec les cartons."},
            correction_payload={"objective_progress": []},
            verdict="accepted",
            score_0_4=4,
        )
    )
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=3,
            kind="mission",
            mission_id=mission.id,
            hook={},
            hook_from_previous={},
            state_delta={},
            status="available",
            brief_payload={
                "episode_index": 3,
                "beat": "act",
                "required_cast": ["lila_bonnet"],
                "a_plot": {"arc_id": "lila_berlin_secret", "stage_id": "avoidance", "stage_index": 0},
            },
        )
    )
    db_session.commit()

    _run(SerialThreadService(db_session).apply_completion(thread, mission=mission))
    db_session.refresh(thread)
    relationship = thread.state["relationships"]["lila_bonnet"]

    assert relationship["register"] == "tu"
    assert relationship["register_switch_episode"] == 4
    assert thread.state["pending_register_switch"]["character_id"] == "lila_bonnet"
    assert relationship["callbacks"]


def test_full_loop(db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_feuilleton_daily_seed", _fake_seed)
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    user = _user(db_session, email="serial-loop@example.com")
    service = SerialThreadService(db_session)

    thread = _run(service.get_or_create_thread(user))
    first = _run(service.today(user))
    assert first["kind"] == "mission"
    assert first["thread"]["id"] == str(thread.id)
    assert first["thread"]["episodes"][0]["id"] == first["id"]
    assert first["thread"]["episodes"][0]["hook"] == {}
    # WP-G2: episodes carry a human label and act/see beat tag.
    assert first["episode_label"] == "Episode 1"
    assert first["beat"] == "act"

    mission = db_session.get(RealWorldMission, UUID(first["mission_id"]))
    assert mission is not None
    assert mission.title == "Reach the landlord"
    # WP-G1: the season opener carries cold-open prologue content for the on-ramp.
    assert mission.source_snapshot["cold_open"]["paragraphs"]
    assert mission.prompt_payload["display_title"] == "Le radiateur"
    assert mission.prompt_payload["messenger"]["contact_name"] == "M. Marchand"
    assert [objective["id"] for objective in mission.objectives[:4]] == [
        "intro_self",
        "describe_problem",
        "make_request",
        "formal_register",
    ]
    progress = [
        {"id": objective["id"], "label": objective["label"], "met": True, "note": "Met in the heating message."}
        for objective in mission.objectives
    ]
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id,
            user_id=user.id,
            mode="writing",
            answer_payload={
                "text": "Bonjour, je viens d'emménager dans l'appartement et le chauffage est en panne. Pourriez-vous envoyer quelqu'un demain matin ?"
            },
            correction_payload={
                "verdict": "accepted",
                "score_0_4": 4,
                "corrected_answer": "Bonjour, je viens d'emménager dans l'appartement et le chauffage est en panne. Pourriez-vous envoyer quelqu'un demain matin ?",
                "objective_progress": progress,
                "concept_hits": [],
                "missing_targets": [],
                "errata": [],
                "vocabulary_links": [],
            },
            verdict="accepted",
            score_0_4=4,
        )
    )
    db_session.commit()
    db_session.refresh(mission)

    completed_mission = MissionScheduler(db_session).complete(user=user, mission=mission)
    serialized = serialize_mission(completed_mission)
    assert serialized and serialized["outcome"]["state_delta"]["set"]["heating_fixed"] == "pending_tomorrow"
    assert serialized["outcome"]["state_delta"]["set"]["marchand_trust"] == "ok"

    queued_episode = _run(service.apply_completion(thread, mission=completed_mission))
    db_session.refresh(thread)
    assert thread.state["heating_fixed"] == "pending_tomorrow"
    assert queued_episode["kind"] == "feuilleton"
    assert queued_episode["status"] == "generation_queued"
    # WP-G3: rolling "story so far" memory accrues for long-term continuity.
    assert thread.state.get("story_so_far") and len(thread.state["story_so_far"]) >= 1
    assert thread.state.get("episodes_completed") == 1

    feuilleton_episode = _run(service.today(user))
    assert feuilleton_episode["kind"] == "feuilleton"
    assert feuilleton_episode["status"] == "delayed"
    assert feuilleton_episode["scene_id"] is None
    assert "retardée" in feuilleton_episode["hook"]["text"]
    assert "radiateur" not in json.dumps(feuilleton_episode["hook"], ensure_ascii=False).lower()
    assert feuilleton_episode["brief_payload"]["episode_index"] == 1

    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="available",
        cadence="serial",
        title="Episode 2: Le Mistral",
        brief="A test scene standing in for the delayed worker output.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "title": "Episode 2: Le Mistral",
            "location_id": "le_mistral",
            "panels": [],
            "hook": {
                "text": "Romy demande une réponse concrète.",
                "unresolved_question": "What do you send Romy?",
                "next_beat_kind": "mission",
                "teaser": "Demain : écrire à Romy.",
            },
        },
        recap_payload={},
        cache_key=f"serial-loop-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    planned_see = (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 1)
        .one()
    )
    planned_see.scene_id = scene.id
    planned_see.status = "available"
    db_session.add(planned_see)
    db_session.commit()

    assert scene is not None
    assert scene.serial_thread_id == thread.id

    completed_scene = GraphicNovelScheduler(db_session).complete(user=user, scene=scene)
    next_mission_episode = _run(service.apply_completion(thread, scene=completed_scene))
    assert next_mission_episode["kind"] == "mission"
    assert next_mission_episode["status"] == "generation_queued"


def test_mission_complete_endpoint_advances_serial_thread(client: TestClient, db_session, monkeypatch):
    """Completing a serial mission via the API must advance the thread to the next beat.

    Regression: previously /missions/{id}/complete never called apply_completion, so the
    story froze at episode 0 and the Atelier on-ramp showed 'all caught up'.
    """
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", False)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(NewsService, "fetch_feuilleton_daily_seed", _fake_seed)
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    email = f"{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "serial-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "serial-secure"}).json()["access_token"]
    user = db_session.query(User).filter(User.email == email).one()

    service = SerialThreadService(db_session)
    thread = _run(service.get_or_create_thread(user))
    first = _run(service.today(user))
    assert first["kind"] == "mission"
    mission = db_session.get(RealWorldMission, UUID(first["mission_id"]))
    progress = [
        {"id": objective["id"], "label": objective["label"], "met": True, "note": "Met in the heating message."}
        for objective in mission.objectives
    ]
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id,
            user_id=user.id,
            mode="writing",
            answer_payload={"text": "Bonjour, je viens d'emménager et le chauffage est en panne. Pourriez-vous le réparer ?"},
            correction_payload={
                "verdict": "accepted",
                "score_0_4": 4,
                "corrected_answer": "Bonjour, je viens d'emménager et le chauffage est en panne. Pourriez-vous le réparer ?",
                "objective_progress": progress,
                "concept_hits": [],
                "missing_targets": [],
                "errata": [],
                "vocabulary_links": [],
            },
            verdict="accepted",
            score_0_4=4,
        )
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/missions/{mission.id}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(SerialThread, thread.id)
    assert refreshed.current_episode_index >= 1
    today_response = client.get("/api/v1/serial/today", headers={"Authorization": f"Bearer {token}"})
    assert today_response.status_code == 200
    today_payload = today_response.json()
    assert today_payload["kind"] == "feuilleton"
    assert today_payload["status"] == "delayed"
    assert today_payload["scene_id"] is None
    assert "radiateur" not in json.dumps(today_payload["hook"], ensure_ascii=False).lower()


def test_serial_archive_and_cast_endpoints(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", True)
    email = f"serial-archive-{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "serial-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "serial-secure"}).json()["access_token"]
    user = db_session.query(User).filter(User.email == email).one()
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    mission = RealWorldMission(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=0,
        title="Reach the landlord",
        brief="Episode 1 archive fixture.",
        objectives=[],
        prompt_payload={},
        source_snapshot={},
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(mission)
    db_session.flush()
    episode = (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 0)
        .first()
    )
    if not episode:
        episode = SerialEpisode(
            thread_id=thread.id,
            episode_index=0,
            kind="mission",
            hook_from_previous={},
            state_delta={},
        )
    episode.kind = "mission"
    episode.mission_id = mission.id
    episode.hook = {"text": "Le café reste allumé."}
    episode.state_delta = {}
    episode.status = "completed"
    episode.completed_at = datetime.now(timezone.utc)
    episode.brief_payload = {"required_cast": ["landlord_marchand"]}
    db_session.add(episode)
    db_session.commit()

    archive = client.get("/api/v1/serial/threads/current/episodes", headers={"Authorization": f"Bearer {token}"})
    cast = client.get("/api/v1/serial/threads/current/cast", headers={"Authorization": f"Bearer {token}"})

    assert archive.status_code == 200
    assert archive.json()["episodes"][0]["episode_label"] == "Season 1 · Episode 1"
    assert archive.json()["episodes"][0]["title"] == "Reach the landlord"
    assert cast.status_code == 200
    cast_rows = {row["id"]: row for row in cast.json()["cast"]}
    assert "marin_leveque" in cast_rows
    assert cast_rows["marin_leveque"]["model_sheet_url"].endswith("/assets/serial/characters/marin_leveque/model-sheet.png")
    assert "register" in cast_rows["marin_leveque"]["relationship"]


def test_direct_serial_mission_creation_uses_story_seed(db_session):
    """A /missions serial query must not fall back to the generic ad-hoc brief."""
    user = _user(db_session, email="serial-direct-mission@example.com")
    thread = SerialThread(
        user_id=user.id,
        world_bible={"logline": "Paris serial test"},
        state={"story_so_far": ["Ep 1 · You acted: Reach the landlord. Left on: Romy asks what happens next."]},
        news_seed={},
        current_episode_index=2,
    )
    db_session.add(thread)
    db_session.flush()
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=1,
            kind="feuilleton",
            hook={
                "text": "Romy sees the radiator problem is still unresolved.",
                "teaser": "Romy asks for one concrete next reply.",
                "unresolved_question": "What do you send now?",
                "next_beat_kind": "mission",
            },
            hook_from_previous={},
            state_delta={},
            status="completed",
        )
    )
    db_session.commit()

    mission = _run(
        MissionScheduler(db_session).create(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            serial_thread_id=thread.id,
            episode_index=2,
            use_news=False,
        )
    )

    assert mission.serial_thread_id == thread.id
    assert mission.episode_index == 2
    assert mission.title != "Message Before Arrival"
    assert mission.prompt_payload["serial_reference"] == "episode-03-mission"
    assert mission.prompt_payload["serial_context"]["hook_from_previous"]["teaser"] == "Romy asks for one concrete next reply."
    linked = (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 2)
        .one()
    )
    assert linked.kind == "mission"
    assert linked.mission_id == mission.id


def test_serial_endpoints_return_disabled_when_flag_off(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", False)
    token = _token(client)
    response = client.get("/api/v1/serial/today", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "serial_world_disabled"
