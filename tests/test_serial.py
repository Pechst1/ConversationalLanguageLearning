"""Regression tests for the Serial World spine."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from uuid import UUID
from typing import Any

from fastapi.testclient import TestClient

from app.config import settings
from app.db.models.atelier import AtelierCollectible
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.schemas.serial import EpisodeRead, SerialThreadRead
from app.services.graphic_novel import GraphicNovelGenerationError, GraphicNovelScheduler
from app.services.missions import MissionScheduler, serialize_mission
from app.services.news_service import NewsService
from app.services.serial_arc_planner import SEASON_FINALE_ARC_ID, SerialArcPlanner, cefr_generation_profile
from app.services.serial import SerialThreadService, WORLD_BIBLE_PATH
from app.services.serial_notifications import enqueue_serial_edition_notification


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


def _callback_llm(content: str):
    return lambda: SimpleNamespace(generate_chat_completion=lambda *args, **kwargs: SimpleNamespace(content=content))


def test_feuilleton_news_summary_strips_feed_artifacts():
    service = NewsService.__new__(NewsService)
    selected = {
        "title": "Un conseil municipal sous tension",
        "summary": "La maire exprime sacolère après le vote. I Personnes citées: Anne Exemple, Marc Exemple.",
        "source": "RFI",
        "named_people": ["Anne Exemple", "Marc Exemple"],
    }
    support = [{"title": "Personnes citées: autre liste. Les voisins réagissent.", "source": "Franceinfo"}]

    summary = service._feuilleton_summary_fr(selected, support)
    digest = service._format_feuilleton_seed_digest(selected, support, [])

    assert "sa colère" in summary
    assert "sacolère" not in summary
    assert "Personnes citées" not in summary
    assert " I " not in summary
    assert "Personnes citées" not in digest
    assert "sacolère" not in digest


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
                    },
                    "user": {
                        "canonical_descriptor": "custom learner avatar descriptor",
                        "reference_images": ["assets/serial/characters/user/model-sheet.png"],
                        "style_ref": "assets/serial/characters/user/model-sheet.png",
                        "avatar_builder": {"hair": "short", "jacket": "blue"},
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
    assert existing.world_bible["visual_design"]["characters"]["user"]["reference_images"] == [
        "assets/serial/characters/user/model-sheet.png"
    ]
    assert existing.world_bible["visual_design"]["characters"]["user"]["avatar_builder"]["jacket"] == "blue"
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


def _complete_season_arcs(thread, *, episode_index: int = 99):
    state = dict(thread.state or {})
    arcs_state = {}
    for arc in thread.world_bible.get("season_arcs", []):
        stages = arc.get("stages") or []
        final_index = len(stages) - 1
        arcs_state[arc["id"]] = {
            "stage": stages[final_index]["id"],
            "stage_index": final_index,
            "advanced_at_episode": episode_index,
        }
    state["arcs"] = arcs_state
    thread.state = state


def test_serial_arc_planner_returns_finale_when_season_complete(db_session):
    user = _user(db_session, email="serial-finale-plan@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    thread.current_episode_index = 48
    _complete_season_arcs(thread, episode_index=47)

    brief = SerialArcPlanner(thread).plan_next_episode("see").model_dump(mode="json")

    assert brief["season_finale"] is True
    assert brief["a_plot"]["arc_id"] == SEASON_FINALE_ARC_ID
    assert brief["a_plot"]["advance_on_completion"] is False
    assert brief["structure"] == "ensemble"
    assert {"marin_leveque", "lila_bonnet", "augustin_de_roncourt", "romy_tremblay"}.issubset(brief["required_cast"])


def test_season_finale_completion_rolls_into_season_two(db_session, monkeypatch):
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    user = _user(db_session, email="serial-finale-rollover@example.com")
    service = SerialThreadService(db_session)
    thread = _run(service.get_or_create_thread(user))
    thread.current_episode_index = 48
    _complete_season_arcs(thread, episode_index=47)
    state = dict(thread.state or {})
    relationships = dict(state["relationships"])
    relationships["romy_tremblay"] = {**relationships["romy_tremblay"], "closeness": 2, "last_summary": "Still here."}
    state["relationships"] = relationships
    thread.state = state
    finale_payload = SerialArcPlanner(thread).plan_next_episode("see").model_dump(mode="json")
    db_session.add(thread)
    db_session.flush()
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=48,
        status="completed",
        cadence="serial",
        title="Season finale",
        brief="The season closes at Le Mistral.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "title": "Season finale",
            "location_id": "le_mistral",
            "panels": [],
            "hook": {
                "text": "Le matin suivant, la meme table attend une decision.",
                "unresolved_question": "What does season two ask first?",
                "next_beat_kind": "mission",
                "teaser": "Demain : choisir quoi dire.",
            },
        },
        recap_payload={},
        cache_key=f"serial-finale-rollover-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=48,
            kind="feuilleton",
            scene_id=scene.id,
            hook={},
            hook_from_previous={},
            state_delta={},
            status="available",
            brief_payload=finale_payload,
        )
    )
    db_session.commit()

    _run(service.apply_completion(thread, scene=scene))
    db_session.refresh(thread)
    season_two_arc_ids = {arc["id"] for arc in thread.world_bible["season_arcs"]}

    assert thread.world_bible["world_bible_version"] == "paris-s2"
    assert thread.world_bible["season_number"] == 2
    assert thread.state["season_number"] == 2
    assert thread.state["season_finale_completed"] == 1
    assert thread.state["relationships"]["romy_tremblay"]["closeness"] == 3
    assert set(thread.state["arcs"]) == season_two_arc_ids
    assert all(entry["stage_index"] == -1 for entry in thread.state["arcs"].values())
    next_brief = SerialArcPlanner(thread).plan_next_episode("act").model_dump(mode="json")
    assert not next_brief.get("season_finale")
    assert next_brief["a_plot"]["arc_id"] in season_two_arc_ids


def test_cefr_generation_profile_is_monotonic():
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    min_words = [cefr_generation_profile(level)["min_words"] for level in levels]
    objective_counts = [cefr_generation_profile(level)["mission_objective_count"] for level in levels]

    assert min_words == sorted(min_words)
    assert objective_counts == sorted(objective_counts)


def test_serial_arc_planner_rotates_mission_formats(db_session, monkeypatch):
    monkeypatch.setattr(settings, "FEUILLETON_AUDIO_ENABLED", True)
    monkeypatch.setattr(settings, "SERIAL_PHONE_CALL_MISSIONS_ENABLED", False)
    user = _user(db_session, email="serial-mission-formats@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    formats: list[str] = []

    for episode_index in range(1, 7):
        thread.current_episode_index = episode_index
        brief = SerialArcPlanner(thread).plan_next_episode("act").model_dump(mode="json")
        formats.append(brief["mission_format"])
        db_session.add(
            SerialEpisode(
                thread_id=thread.id,
                episode_index=episode_index,
                kind="mission",
                hook={},
                hook_from_previous={},
                state_delta={},
                status="completed",
                brief_payload=brief,
                location_id=brief.get("location_id"),
            )
        )
        db_session.add(thread)
        db_session.commit()
        db_session.refresh(thread)

    assert "phone_call" not in formats
    assert "voicemail_reply" in formats
    assert {"email_formal", "admin_form"}.issubset(set(formats))
    assert all(current != previous for previous, current in zip(formats, formats[1:]))


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
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.serial.LLMService", _callback_llm("aider avec les cartons"))
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


def test_serial_callback_extraction_skips_salutation_only_phrase(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.serial.LLMService", _callback_llm("Bonjour Monsieur Marchand"))
    user = _user(db_session, email="serial-callback-salutation@example.com")
    mission = RealWorldMission(
        user_id=user.id,
        title="Callback salutation",
        brief="Send a practical message.",
        objectives=[],
        prompt_payload={},
        source_snapshot={},
    )
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id,
            user_id=user.id,
            mode="writing",
            answer_payload={"text": "Bonjour Monsieur Marchand, je viens d'emménager et le radiateur ne marche pas."},
            correction_payload={},
            verdict="accepted",
            score_0_4=4,
        )
    )
    db_session.commit()
    db_session.refresh(mission)

    assert SerialThreadService(db_session)._harvest_callback(mission=mission) == ""


def test_serial_callback_extraction_keeps_distinctive_phrase(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.serial.LLMService", _callback_llm("la clé sous la pluie"))
    user = _user(db_session, email="serial-callback-distinctive@example.com")
    mission = RealWorldMission(
        user_id=user.id,
        title="Callback distinctive",
        brief="Send a practical message.",
        objectives=[],
        prompt_payload={},
        source_snapshot={},
    )
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id,
            user_id=user.id,
            mode="writing",
            answer_payload={"text": "Si tu vois Marin, dis-lui que la clé sous la pluie n'est pas un signe normal."},
            correction_payload={},
            verdict="accepted",
            score_0_4=4,
        )
    )
    db_session.commit()
    db_session.refresh(mission)

    assert SerialThreadService(db_session)._harvest_callback(mission=mission) == "la clé sous la pluie"


def test_legacy_feuilleton_completion_backfills_brief_payload(db_session, monkeypatch):
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    user = _user(db_session, email="serial-legacy-feuilleton@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    thread.current_episode_index = 1
    db_session.add(thread)
    db_session.flush()
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="completed",
        cadence="serial",
        title="Legacy Feuilleton",
        brief="A generated scene from before serial brief payloads existed.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "title": "Legacy Feuilleton",
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
        cache_key=f"serial-legacy-feuilleton-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    episode = SerialEpisode(
        thread_id=thread.id,
        episode_index=1,
        kind="feuilleton",
        scene_id=scene.id,
        hook={},
        hook_from_previous={},
        state_delta={},
        status="available",
        brief_payload={},
    )
    db_session.add(episode)
    db_session.commit()

    _run(SerialThreadService(db_session).apply_completion(thread, scene=scene))
    db_session.refresh(thread)
    db_session.refresh(episode)
    payload = episode.brief_payload
    required_cast = payload["required_cast"]

    assert payload["episode_index"] == 1
    assert payload["a_plot"]["advance_on_completion"] is True
    assert required_cast
    assert any(value.get("advanced_at_episode") == 1 for value in thread.state["arcs"].values())
    assert any(thread.state["cast_last_seen"][character_id] == 1 for character_id in required_cast)
    assert any(
        thread.state["relationships"][character_id]["closeness"] == 1
        for character_id in required_cast
        if character_id in thread.state["relationships"]
    )


def test_feuilleton_completion_mints_story_seal_with_crop(db_session, monkeypatch):
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    user = _user(db_session, email="serial-story-seal@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    thread.current_episode_index = 1
    db_session.add(thread)
    db_session.flush()
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="available",
        cadence="serial",
        title="Le papier cachete",
        brief="A test scene with a seal-worthy panel.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "title": "Le papier cachete",
            "location_id": "le_mistral",
            "panels": [],
            "hook": {
                "text": "Romy voit une signature impossible.",
                "unresolved_question": "Who signed it?",
                "next_beat_kind": "mission",
                "teaser": "Demain : répondre.",
            },
        },
        recap_payload={},
        cache_key=f"serial-story-seal-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    db_session.add(
        GraphicNovelPanel(
            scene_id=scene.id,
            panel_index=1,
            title="The reveal",
            beat="Romy lifts the paper.",
            image_prompt="A square panel.",
            image_url="https://example.test/panel.png",
            image_payload={"url": "https://example.test/panel.png"},
            overlay_payload={},
            generation_metadata={
                "seal_crop": {
                    "kind": "panel_crop",
                    "panel_index": 1,
                    "focal_point": {"x": 0.42, "y": 0.35},
                    "region": {"x": 0.2, "y": 0.1, "width": 0.6, "height": 0.6},
                    "image_url": "https://example.test/panel.png",
                }
            },
        )
    )
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=1,
            kind="feuilleton",
            scene_id=scene.id,
            hook={},
            hook_from_previous={},
            state_delta={},
            status="available",
            brief_payload={},
        )
    )
    db_session.commit()
    db_session.refresh(thread)

    result = _run(SerialThreadService(db_session).apply_completion(thread, scene=scene))

    minted = result["minted_collectibles"]
    assert minted[0]["kind"] == "story_seal"
    assert minted[0]["metadata"]["seal_crop"]["focal_point"] == {"x": 0.42, "y": 0.35}
    assert minted[0]["metadata"]["seal_crop"]["image_url"] == "https://example.test/panel.png"
    assert db_session.query(AtelierCollectible).filter(
        AtelierCollectible.user_id == user.id,
        AtelierCollectible.kind == "story_seal",
    ).count() == 1


def test_feuilleton_complete_endpoint_returns_next_serial_beat(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", True)
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    email = f"serial-feuilleton-next-{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "serial-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "serial-secure"}).json()["access_token"]
    user = db_session.query(User).filter(User.email == email).one()
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    thread.current_episode_index = 1
    db_session.add(thread)
    db_session.flush()
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="available",
        cadence="serial",
        title="La signature impossible",
        brief="A test serial scene ready to file.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "title": "La signature impossible",
            "location_id": "le_mistral",
            "hook": {
                "text": "Romy voit une signature impossible.",
                "unresolved_question": "Who signed it?",
                "next_beat_kind": "mission",
                "teaser": "Demain : répondre à Romy.",
            },
        },
        recap_payload={},
        cache_key=f"serial-feuilleton-next-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=1,
            kind="feuilleton",
            scene_id=scene.id,
            hook={},
            hook_from_previous={},
            state_delta={},
            status="available",
            brief_payload={},
        )
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/graphic-novel/scenes/{scene.id}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scene"]["status"] == "completed"
    assert payload["next_serial"]["kind"] == "mission"
    assert payload["next_serial"]["episode_index"] == 2
    assert payload["next_serial"]["status"] == "generation_queued"


def test_delayed_feuilleton_retries_without_duplicate_episode(db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_feuilleton_daily_seed", _fake_seed)
    user = _user(db_session, email="serial-delayed-retry@example.com")
    service = SerialThreadService(db_session)
    thread = _run(service.get_or_create_thread(user))
    thread.current_episode_index = 1
    brief_payload = service._episode_brief(thread, "see").model_dump(mode="json")
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=1,
            kind="feuilleton",
            hook={
                "text": "L'édition de demain est retardée.",
                "unresolved_question": "Quand l'imprimerie relancera-t-elle l'épisode ?",
                "teaser": "Demain : l'édition reprend dès que la salle de rédaction revient.",
                "next_beat_kind": "feuilleton",
            },
            hook_from_previous={},
            state_delta={},
            status="delayed",
            brief_payload=brief_payload,
        )
    )
    db_session.add(thread)
    db_session.commit()
    calls = 0

    async def fake_create(self, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GraphicNovelGenerationError(
                "serial story unavailable",
                errors=["serial_story_llm_unavailable"],
            )
        scene = GraphicNovelScene(
            user_id=kwargs["user"].id,
            mission_id=kwargs.get("mission_id"),
            serial_thread_id=kwargs["serial_thread_id"],
            episode_index=kwargs["episode_index"],
            status="available",
            cadence="serial",
            title="Retry success",
            brief="A regenerated scene after a delayed Feuilleton.",
            selected_concept_ids=[],
            target_errata_ids=[],
            target_vocabulary_ids=[],
            source_snapshot={},
            script_payload={
                "title": "Retry success",
                "location_id": "le_mistral",
                "panels": [],
                "hook": {
                    "text": "Romy aperçoit une enveloppe sous la table.",
                    "unresolved_question": "Qui l'a laissée là ?",
                    "next_beat_kind": "mission",
                    "teaser": "Demain : répondre à Romy.",
                },
            },
            recap_payload={},
            cache_key=f"serial-delayed-retry-{uuid4().hex}",
            prompt_version="test",
            image_model="test",
            image_quality="medium",
        )
        self.db.add(scene)
        self.db.commit()
        self.db.refresh(scene)
        return scene

    monkeypatch.setattr(GraphicNovelScheduler, "create", fake_create)

    still_delayed = _run(service.today(user))
    db_session.expire_all()
    delayed_episode = (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 1)
        .one()
    )
    assert calls == 1
    assert still_delayed["status"] == "delayed"
    assert delayed_episode.status == "delayed"
    assert delayed_episode.scene_id is None
    assert (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 1)
        .count()
        == 1
    )

    retried = _run(service.today(user))
    db_session.expire_all()
    retry_episode = (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 1)
        .one()
    )

    assert calls == 2
    assert retried["status"] == "available"
    assert retried["scene_id"]
    assert retry_episode.status == "available"
    assert retry_episode.scene_id
    assert (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 1)
        .count()
        == 1
    )


def test_stale_generating_scene_expires_to_retryable_delayed_episode(db_session):
    user = _user(db_session, email="serial-stale-generating@example.com")
    service = SerialThreadService(db_session)
    thread = _run(service.get_or_create_thread(user))
    thread.current_episode_index = 3
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=3,
        status="generating",
        cadence="serial",
        title="Stale scene",
        brief="A scene stranded by a stopped worker.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={"hook": {"text": "A stranded hook.", "next_beat_kind": "mission"}},
        recap_payload={},
        cache_key=f"serial-stale-generating-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
        started_at=stale_at,
        updated_at=stale_at,
    )
    db_session.add(scene)
    db_session.flush()
    episode = SerialEpisode(
        thread_id=thread.id,
        episode_index=3,
        kind="feuilleton",
        scene_id=scene.id,
        hook={},
        hook_from_previous={},
        state_delta={},
        status="generating",
        brief_payload=service._episode_brief(thread, "see").model_dump(mode="json"),
    )
    db_session.add_all([thread, episode])
    db_session.commit()

    expired = service.expire_stale_generations(thread)
    db_session.refresh(scene)
    db_session.refresh(episode)

    assert expired == 1
    assert scene.status == "generation_failed"
    assert episode.status == "delayed"
    assert episode.scene_id is None
    assert "retardée" in episode.hook["text"]


def test_full_loop(db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_feuilleton_daily_seed", _fake_seed)
    monkeypatch.setattr(SerialThreadService, "_enqueue_next_beat", lambda self, thread_id: None)
    monkeypatch.setattr("app.services.graphic_novel.enqueue_serial_edition_notification", lambda *args, **kwargs: False)
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
    assert feuilleton_episode["status"] == "available"
    assert feuilleton_episode["scene_id"]
    assert feuilleton_episode["brief_payload"]["episode_index"] == 1

    scene = db_session.get(GraphicNovelScene, UUID(feuilleton_episode["scene_id"]))

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
    monkeypatch.setattr("app.services.graphic_novel.enqueue_serial_edition_notification", lambda *args, **kwargs: False)
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
    assert today_payload["status"] == "available"
    assert today_payload["scene_id"]


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
    thread.current_episode_index = 1
    thread.state = {
        **(thread.state or {}),
        "relationships": {
            "marin_leveque": {
                "closeness": 3,
                "register": "tu",
                "register_switch_episode": 0,
                "last_summary": "Marin remembers the radiator night.",
                "callbacks": ["la clé sous la pluie"],
            }
        },
    }
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
    episode.brief_payload = {"required_cast": ["marin_leveque"]}
    db_session.add(episode)
    db_session.add(thread)
    db_session.commit()

    archive = client.get("/api/v1/serial/threads/current/episodes", headers={"Authorization": f"Bearer {token}"})
    cast = client.get("/api/v1/serial/threads/current/cast", headers={"Authorization": f"Bearer {token}"})

    assert archive.status_code == 200
    assert archive.json()["current_episode_index"] == 1
    assert archive.json()["episodes"][0]["episode_label"] == "Season 1 · Episode 1"
    assert archive.json()["episodes"][0]["title"] == "Reach the landlord"
    assert archive.json()["episodes"][0]["required_cast"] == ["marin_leveque"]
    assert cast.status_code == 200
    cast_rows = {row["id"]: row for row in cast.json()["cast"]}
    assert "marin_leveque" in cast_rows
    assert cast_rows["marin_leveque"]["model_sheet_url"].endswith("/assets/serial/characters/marin_leveque/model-sheet.png")
    assert cast_rows["marin_leveque"]["relationship"]["register"] == "tu"
    assert cast_rows["marin_leveque"]["relationship"]["callbacks"] == ["la clé sous la pluie"]
    assert cast_rows["marin_leveque"]["episodes"][0]["href"] == "/serial/episode/0"


def test_serial_edition_notification_is_idempotent(db_session, monkeypatch):
    user = _user(db_session, email="serial-notify@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    thread.current_episode_index = 1
    episode = SerialEpisode(
        thread_id=thread.id,
        episode_index=1,
        kind="feuilleton",
        hook={"teaser": "Demain : Romy trouve une enveloppe."},
        hook_from_previous={},
        state_delta={},
        brief_payload={},
        status="available",
    )
    db_session.add_all([thread, episode])
    db_session.commit()
    calls: list[tuple[Any, ...]] = []

    monkeypatch.setattr(
        "app.tasks.notifications.send_serial_edition_notification.delay",
        lambda *args: calls.append(args),
    )

    assert enqueue_serial_edition_notification(db_session, episode, user=user) is True
    db_session.refresh(episode)
    assert episode.hook["notification_queued_key"].startswith("serial-edition:")
    assert calls and calls[0][2] == "Episode 2 is ready"
    assert "Romy trouve" in calls[0][3]

    assert enqueue_serial_edition_notification(db_session, episode, user=user) is False
    assert len(calls) == 1


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


def test_direct_serial_mission_creation_rejects_unfinished_previous_episode(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", True)
    email = f"serial-direct-blocked-{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "serial-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "serial-secure"}).json()["access_token"]
    user = db_session.query(User).filter(User.email == email).one()
    thread = SerialThread(
        user_id=user.id,
        world_bible={"logline": "Paris serial test"},
        state={},
        news_seed={},
        current_episode_index=1,
    )
    db_session.add(thread)
    db_session.flush()
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="available",
        cadence="serial",
        title="Le papier cachete",
        brief="The scene has not been filed yet.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={"hook": {"next_beat_kind": "mission", "teaser": "Romy asks for a reply."}},
        recap_payload={},
        cache_key=f"serial-direct-blocked-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=1,
            kind="feuilleton",
            scene_id=scene.id,
            hook={},
            hook_from_previous={},
            state_delta={},
            status="available",
            brief_payload={},
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "serial_thread_id": str(thread.id),
            "episode_index": 2,
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "serial_episode_not_ready"
    assert detail["blocking_episode_index"] == 1
    assert detail["blocking_status"] == "available"
    assert (
        db_session.query(SerialEpisode)
        .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == 2)
        .first()
        is None
    )


def test_serial_endpoints_return_disabled_when_flag_off(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", False)
    token = _token(client)
    response = client.get("/api/v1/serial/today", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "serial_world_disabled"
