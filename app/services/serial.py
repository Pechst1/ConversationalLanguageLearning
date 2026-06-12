"""Serial World orchestration service."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.schemas.serial import EpisodeBrief
from app.services.graphic_novel import GraphicNovelGenerationError, GraphicNovelScheduler
from app.services.llm_service import LLMService
from app.services.missions import MissionScheduler
from app.services.news_service import NewsService
from app.services.serial_arc_planner import SerialArcPlanner


WORLD_BIBLE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "serial" / "world_bible_paris_v2.json"
WORLD_BIBLE_V1_PATH = Path(__file__).resolve().parent.parent / "prompts" / "serial" / "world_bible_paris_v1.json"


def _compact(value: Any, max_length: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text if len(text) <= max_length else text[: max_length - 1].rstrip() + "…"


CALLBACK_SALUTATION_PREFIXES = (
    "bonjour",
    "bonsoir",
    "salut",
    "coucou",
    "hello",
    "merci",
    "monsieur",
    "madame",
)


class SerialThreadService:
    """Create and advance the lightweight story spine shared by Missions and Feuilleton."""

    STALE_GENERATION_TIMEOUT = timedelta(minutes=15)

    def __init__(self, db: Session) -> None:
        self.db = db

    async def get_or_create_thread(
        self,
        user: User,
        *,
        world_bible: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
        news_seed: dict[str, Any] | None = None,
    ) -> SerialThread:
        existing = (
            self.db.query(SerialThread)
            .filter(SerialThread.user_id == user.id, SerialThread.status == "active")
            .order_by(SerialThread.created_at.desc())
            .first()
        )
        if existing:
            self._sync_world_bible_assets(existing)
            return existing
        seeded_world = world_bible or self._load_world_bible()
        seeded_state = state or dict(seeded_world.get("initial_state") or {})
        seeded_news = news_seed or await self._news_seed(user)
        thread = SerialThread(
            user_id=user.id,
            status="active",
            world_bible=seeded_world,
            state=seeded_state,
            news_seed=seeded_news,
            current_episode_index=0,
        )
        self.db.add(thread)
        self.db.commit()
        self.db.refresh(thread)
        self._sync_world_bible_assets(thread)
        return thread

    def _sync_world_bible_assets(self, thread: SerialThread) -> None:
        """Upgrade active threads with locked assets and v2 arc contracts without resetting story state."""
        current = thread.world_bible if isinstance(thread.world_bible, dict) else {}
        seeded_world = self._load_world_bible()
        next_world = dict(current or {})
        changed = False
        for key in ("setting", "protagonist", "cast", "register_map", "ensemble_dynamics", "season_one_situation", "cold_open", "generation_guardrails"):
            if key not in next_world and key in seeded_world:
                next_world[key] = seeded_world[key]
                changed = True
        seeded_visual = seeded_world.get("visual_design") if isinstance(seeded_world.get("visual_design"), dict) else None
        if seeded_visual and next_world.get("visual_design") != seeded_visual:
            next_world["visual_design"] = seeded_visual
            changed = True
        seeded_arcs = seeded_world.get("season_arcs") if isinstance(seeded_world.get("season_arcs"), list) else []
        if seeded_arcs and next_world.get("season_arcs") != seeded_arcs:
            next_world["season_arcs"] = seeded_arcs
            changed = True
        if seeded_world.get("world_bible_version") and next_world.get("world_bible_version") != seeded_world.get("world_bible_version"):
            next_world["world_bible_version"] = seeded_world.get("world_bible_version")
            changed = True
        if changed:
            thread.world_bible = next_world
        state_changed = self._initialize_thread_story_state(thread)
        if changed or state_changed:
            self.db.add(thread)
            self.db.commit()
            self.db.refresh(thread)

    async def today(self, user: User) -> dict[str, Any]:
        thread = await self.get_or_create_thread(user)
        self.expire_stale_generations(thread)
        episode = self._current_episode(thread)
        if not episode:
            episode = await self.start_next_beat(thread)
        elif episode.kind == "feuilleton" and episode.status == "delayed":
            episode = await self.start_feuilleton_beat(thread, retry_delayed=True)
        else:
            self._ensure_episode_contract(episode)
        return {
            **self.serialize_episode(episode),
            "thread": self.serialize_thread(thread),
        }

    def expire_stale_generations(
        self,
        thread: SerialThread | None = None,
        *,
        now: datetime | None = None,
        timeout: timedelta | None = None,
    ) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - (timeout or self.STALE_GENERATION_TIMEOUT)
        query = self.db.query(GraphicNovelScene).filter(
            GraphicNovelScene.status == "generating",
            GraphicNovelScene.updated_at < cutoff,
            GraphicNovelScene.serial_thread_id.isnot(None),
        )
        if thread:
            query = query.filter(GraphicNovelScene.serial_thread_id == thread.id)
        scenes = query.all()
        if not scenes:
            return 0

        for scene in scenes:
            scene.status = "generation_failed"
            scene.completed_at = now or datetime.now(timezone.utc)
            episode = (
                self.db.query(SerialEpisode)
                .filter(SerialEpisode.thread_id == scene.serial_thread_id, SerialEpisode.scene_id == scene.id)
                .first()
            )
            if episode and episode.status == "generating":
                episode.status = "delayed"
                episode.scene_id = None
                episode.hook = {
                    "text": "L'édition de demain est retardée.",
                    "unresolved_question": "Quand l'imprimerie relancera-t-elle l'épisode ?",
                    "teaser": "Demain : l'édition reprend dès que la salle de rédaction revient.",
                    "next_beat_kind": "feuilleton",
                }
                self.db.add(episode)
            self.db.add(scene)
        self.db.commit()
        if thread:
            self.db.refresh(thread)
        return len(scenes)

    async def start_mission_beat(self, thread: SerialThread) -> SerialEpisode:
        hook_from_previous = self._previous_hook(thread)
        episode_index = thread.current_episode_index
        brief = self._episode_brief(thread, "act")
        brief_payload = brief.model_dump(mode="json")
        self._upsert_planned_episode(
            thread=thread,
            episode_index=episode_index,
            kind="mission",
            hook_from_previous=hook_from_previous,
            brief_payload=brief_payload,
            status="available",
        )
        custom_scenario, desired_outcome, relationship, target_register = self._mission_seed(
            thread,
            hook_from_previous,
            brief_payload,
        )
        mission = await MissionScheduler(self.db).create(
            user=thread.user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            custom_scenario=custom_scenario,
            desired_outcome=desired_outcome,
            relationship=relationship,
            register=target_register,
            serial_thread_id=thread.id,
            episode_index=episode_index,
            stakes_level=brief.stakes_level,
        )
        if episode_index == 0:
            self._apply_episode_one_mission_contract(mission)
        else:
            self._apply_brief_mission_contract(mission=mission, thread=thread, brief_payload=brief_payload)
        episode = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == episode_index)
            .first()
        )
        if episode:
            episode.kind = "mission"
            episode.mission_id = mission.id
            episode.scene_id = None
            episode.hook_from_previous = episode.hook_from_previous or hook_from_previous or {}
            episode.brief_payload = brief_payload
        else:
            episode = SerialEpisode(
                thread_id=thread.id,
                episode_index=episode_index,
                kind="mission",
                mission_id=mission.id,
                scene_id=None,
                hook={},
                hook_from_previous=hook_from_previous or {},
                state_delta={},
                brief_payload=brief_payload,
                status="available",
            )
        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)
        return episode

    def _upsert_planned_episode(
        self,
        *,
        thread: SerialThread,
        episode_index: int,
        kind: str,
        hook_from_previous: dict[str, Any] | None,
        brief_payload: dict[str, Any],
        status: str,
    ) -> SerialEpisode:
        episode = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == episode_index)
            .first()
        )
        if episode:
            episode.kind = kind
            episode.hook_from_previous = episode.hook_from_previous or hook_from_previous or {}
            episode.brief_payload = brief_payload
            episode.location_id = brief_payload.get("location_id") or episode.location_id
            episode.status = status if episode.status not in {"completed"} else episode.status
        else:
            episode = SerialEpisode(
                thread_id=thread.id,
                episode_index=episode_index,
                kind=kind,
                hook={},
                hook_from_previous=hook_from_previous or {},
                state_delta={},
                brief_payload=brief_payload,
                location_id=brief_payload.get("location_id"),
                status=status,
            )
        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)
        return episode

    def _apply_brief_mission_contract(
        self,
        *,
        mission: RealWorldMission,
        thread: SerialThread,
        brief_payload: dict[str, Any],
    ) -> None:
        prompt = dict(mission.prompt_payload or {})
        messenger = dict(prompt.get("messenger") or {})
        addressed = self._addressed_character_from_brief(brief_payload)
        episode_label = f"Episode {int(mission.episode_index or 0) + 1}"
        cefr_profile = brief_payload.get("cefr_profile") if isinstance(brief_payload.get("cefr_profile"), dict) else {}
        min_words = int(cefr_profile.get("min_words") or prompt.get("min_words") or 35)
        prompt.update(
            {
                "serial_episode_brief": brief_payload,
                "serial_character_id": addressed,
                "serial_relationships": self._relationship_payload(thread=thread, character_ids=brief_payload.get("required_cast") or []),
                "target_register": self._register_for_character(thread, addressed),
                "min_words": min_words,
                "conversation_instruction": (
                    f"Stay in character as {self._character_name(thread, addressed)}. "
                    "Respect the current register and use shared callbacks only if they fit naturally."
                ),
            }
        )
        prompt["messenger"] = {
            **messenger,
            "channel_label": f"{episode_label} · Act",
            "contact_name": self._character_name(thread, addressed),
            "contact_role": self._character_role(thread, addressed),
            "contact_initials": self._character_initials(thread, addressed),
            "thread_title": messenger.get("thread_title") or self._character_name(thread, addressed),
            "dispatch_note": brief_payload.get("hook_guidance") or messenger.get("dispatch_note"),
            "inbox_context": mission.brief,
            "success_signal": messenger.get("success_signal") or "The addressee has a concrete next step and the story can move.",
        }
        mission.prompt_payload = prompt
        mission.stakes_level = int(brief_payload.get("stakes_level") or mission.stakes_level or 1)
        self.db.add(mission)
        self.db.commit()
        self.db.refresh(mission)

    def _ensure_episode_contract(self, episode: SerialEpisode) -> None:
        if episode.kind != "mission" or episode.episode_index != 0 or not episode.mission_id:
            return
        mission = self.db.get(RealWorldMission, episode.mission_id)
        if not mission:
            return
        if (mission.prompt_payload or {}).get("serial_reference") == "episode-01-beat-a":
            return
        self._apply_episode_one_mission_contract(mission)

    def _apply_episode_one_mission_contract(self, mission: RealWorldMission) -> None:
        prompt = dict(mission.prompt_payload or {})
        messenger = dict(prompt.get("messenger") or {})
        episode_vocabulary = [
            "le radiateur",
            "le chauffage",
            "en panne",
            "emménager",
            "l'appartement",
            "réparer",
            "le propriétaire",
        ]
        mission.title = "Reach the landlord"
        mission.brief = (
            "Your first night in Paris. The radiator in your new studio is dead and the flat is freezing. "
            "Write a short message to your landlord, M. Marchand, to report the problem and get it fixed."
        )
        mission.stakes_level = 1
        mission.source_snapshot = {
            "mode": "serial_episode_01",
            "title": "Episode 1 — Le radiateur",
            "source_policy": "Fixed season opener from docs/serial-episode-01-reference.md.",
            "items": [],
            "digest": "The learner must contact M. Marchand about the broken radiator.",
            "cold_open": self._load_world_bible().get("cold_open") or {},
        }
        mission.objectives = [
            {
                "id": "intro_self",
                "label": "Say who you are and that you just moved in",
                "kind": "communication",
                "target_count": 1,
                "required": True,
                "maps_to": ["present tense", "emménager", "l'appartement"],
            },
            {
                "id": "describe_problem",
                "label": "Describe the problem concretely: the heating does not work",
                "kind": "communication",
                "target_count": 1,
                "required": True,
                "maps_to": ["ne...pas", "le radiateur", "le chauffage", "en panne"],
            },
            {
                "id": "make_request",
                "label": "Ask clearly when or if he can fix it",
                "kind": "pragmatics",
                "target_count": 1,
                "required": True,
                "maps_to": ["pouvoir + infinitive", "réparer"],
            },
            {
                "id": "formal_register",
                "label": "Use the correct formal register with M. Marchand",
                "kind": "register",
                "target_count": 1,
                "required": True,
                "maps_to": ["vous", "pourriez-vous", "je vous remercie"],
            },
        ]
        prompt.update(
            {
                "serial_reference": "episode-01-beat-a",
                "display_title": "Le radiateur",
                "episode_title": "Episode 1 — Le radiateur",
                "serial_beat": "act",
                "serial_character_id": "landlord_marchand",
                "stakes_level": 1,
                "custom_context": {
                    "scenario": mission.brief,
                    "desired_outcome": "M. Marchand understands the heating problem and confirms a repair appointment.",
                    "relationship": "landlord_marchand",
                    "register": "vous / polite formal",
                    "source": "serial_episode_01",
                },
                "writing_title": "Reach the landlord",
                "writing_instruction": (
                    "Write the first message to M. Marchand: introduce yourself, describe the broken radiator, "
                    "ask for a repair time, and keep the register formal."
                ),
                "writing_placeholder": "Bonjour Monsieur Marchand, je viens d'emménager...",
                "min_words": 35,
                "max_words": 140,
                "target_register": "vous / polite formal",
                "target_vocabulary_terms": episode_vocabulary,
            }
        )
        prompt["messenger"] = {
            **messenger,
            "channel_label": "Episode 1 · Act",
            "contact_name": "M. Marchand",
            "contact_role": "propriétaire",
            "contact_initials": "M·",
            "presence": "répond brièvement, surtout le soir",
            "time_label": "21:48",
            "thread_title": "M. Marchand · chauffage",
            "scene_anchor": "Première nuit dans le studio, manteau encore sur les épaules",
            "dispatch_note": "The reply only works if M. Marchand knows who you are, what is broken, and what you need.",
            "inbox_context": mission.brief,
            "opening_message": "M. Marchand est votre propriétaire. Il répond vite, mais seulement si le message est précis et formel.",
            "ambient_cues": ["studio glacé", "radiateur froid", "premier soir à Paris"],
            "quick_replies": [
                "Bonjour Monsieur Marchand...",
                "Je viens d'emménager...",
                "Le radiateur ne fonctionne pas...",
                "Pourriez-vous le faire réparer ?",
            ],
            "success_signal": "M. Marchand confirms a repair window instead of asking for basic details.",
            "realism_rules": [
                "Use vous with M. Marchand.",
                "Name the apartment/heating problem concretely.",
                "Ask for a repair time, not just sympathy.",
            ],
            "vocabulary_focus_terms": episode_vocabulary,
        }
        mission.prompt_payload = prompt
        self.db.add(mission)
        self.db.commit()
        self.db.refresh(mission)

    async def start_feuilleton_beat(self, thread: SerialThread, *, retry_delayed: bool = False) -> SerialEpisode:
        hook_from_previous = self._previous_hook(thread)
        episode_index = thread.current_episode_index
        existing_episode = self._current_episode(thread)
        if (
            existing_episode
            and existing_episode.kind == "feuilleton"
            and existing_episode.scene_id
            and not (retry_delayed and existing_episode.status == "delayed")
        ):
            return existing_episode
        if (
            existing_episode
            and existing_episode.kind == "feuilleton"
            and existing_episode.status == "delayed"
            and not retry_delayed
        ):
            return existing_episode
        if (
            retry_delayed
            and existing_episode
            and existing_episode.kind == "feuilleton"
            and isinstance(existing_episode.brief_payload, dict)
            and existing_episode.brief_payload
        ):
            brief_payload = existing_episode.brief_payload
        else:
            brief = self._episode_brief(thread, "see")
            brief_payload = brief.model_dump(mode="json")
        episode = self._upsert_planned_episode(
            thread=thread,
            episode_index=episode_index,
            kind="feuilleton",
            hook_from_previous=hook_from_previous,
            brief_payload=brief_payload,
            status="generating",
        )
        latest_mission = self._latest_completed_mission(thread)
        thread.news_seed = await self._news_seed(thread.user)
        self.db.add(thread)
        self.db.commit()
        try:
            scene = await GraphicNovelScheduler(self.db).create(
                user=thread.user,
                cadence="ad_hoc",
                mission_id=latest_mission.id if latest_mission else None,
                serial_thread_id=thread.id,
                episode_index=episode_index,
                use_news=True,
                panel_count=6,
                story_quality="standard",
                experience_mode="study",
                force_new=True,
            )
        except GraphicNovelGenerationError as exc:
            if "serial_story_llm_unavailable" not in exc.errors:
                raise
            episode.status = "delayed"
            episode.hook = {
                "text": "L'édition de demain est retardée.",
                "unresolved_question": "Quand l'imprimerie relancera-t-elle l'épisode ?",
                "teaser": "Demain : l'édition reprend dès que la salle de rédaction revient.",
                "next_beat_kind": "feuilleton",
            }
            episode.scene_id = None
            episode.brief_payload = brief_payload
            self.db.add(episode)
            self.db.commit()
            self.db.refresh(episode)
            return episode
        location_id = (scene.script_payload or {}).get("location_id") or None
        episode = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == episode_index)
            .first()
        )
        if episode:
            episode.kind = "feuilleton"
            episode.mission_id = latest_mission.id if latest_mission else None
            episode.scene_id = scene.id
            episode.location_id = location_id
            episode.hook = (scene.script_payload or {}).get("hook") or {}
            episode.hook_from_previous = episode.hook_from_previous or hook_from_previous or {}
            episode.brief_payload = brief_payload
            episode.status = scene.status
        else:
            episode = SerialEpisode(
                thread_id=thread.id,
                episode_index=episode_index,
                kind="feuilleton",
                mission_id=latest_mission.id if latest_mission else None,
                scene_id=scene.id,
                location_id=location_id,
                hook=(scene.script_payload or {}).get("hook") or {},
                hook_from_previous=hook_from_previous or {},
                state_delta={},
                brief_payload=brief_payload,
                status=scene.status,
            )
        self.db.add(episode)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            episode = (
                self.db.query(SerialEpisode)
                .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == episode_index)
                .first()
            )
            if not episode:
                raise
        self.db.refresh(episode)
        return episode

    async def apply_completion(
        self,
        thread: SerialThread,
        *,
        mission: RealWorldMission | None = None,
        scene: GraphicNovelScene | None = None,
        state_delta: dict[str, Any] | None = None,
        hook: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        episode = self._episode_for_completion(thread=thread, mission=mission, scene=scene)
        if not episode:
            raise ValueError("No serial episode found for completion")
        emitted_delta = state_delta or self._completion_state_delta(mission=mission, scene=scene)
        emitted_hook = hook or self._completion_hook(mission=mission, scene=scene)
        self._merge_state(thread, emitted_delta)
        self._record_story_beat(thread, episode=episode, mission=mission, scene=scene, hook=emitted_hook)
        self._apply_episode_brief_completion(thread=thread, episode=episode, mission=mission, scene=scene, hook=emitted_hook)
        episode.state_delta = emitted_delta or {}
        episode.hook = emitted_hook or {}
        episode.status = "completed"
        episode.completed_at = datetime.now(timezone.utc)
        if scene and (scene.script_payload or {}).get("location_id"):
            episode.location_id = (scene.script_payload or {}).get("location_id")
        thread.current_episode_index = max(thread.current_episode_index, episode.episode_index + 1)
        self.db.add_all([thread, episode])
        self.db.commit()
        self.db.refresh(thread)
        self._enqueue_next_beat(thread.id)
        existing_next = self._current_episode(thread)
        if existing_next:
            return self.serialize_episode(existing_next)
        next_kind = str((emitted_hook or {}).get("next_beat_kind") or ("mission" if thread.current_episode_index % 2 == 0 else "feuilleton"))
        return {
            "thread_id": str(thread.id),
            "episode_index": thread.current_episode_index,
            "episode_label": f"Episode {thread.current_episode_index + 1}",
            "kind": "feuilleton" if next_kind == "feuilleton" else "mission",
            "beat": "see" if next_kind == "feuilleton" else "act",
            "status": "generation_queued",
        }

    def serialize_episode(self, episode: SerialEpisode) -> dict[str, Any]:
        previously = (episode.hook_from_previous or {}).get("text") if isinstance(episode.hook_from_previous, dict) else None
        return {
            "id": str(episode.id),
            "thread_id": str(episode.thread_id),
            "episode_index": episode.episode_index,
            "episode_label": f"Episode {episode.episode_index + 1}",
            "beat": "act" if episode.kind == "mission" else "see",
            "kind": episode.kind,
            "mission_id": str(episode.mission_id) if episode.mission_id else None,
            "scene_id": str(episode.scene_id) if episode.scene_id else None,
            "hook_from_previous": episode.hook_from_previous or None,
            "previously": previously,
            "hook": episode.hook or {},
            "state_delta": episode.state_delta or {},
            "brief_payload": episode.brief_payload or {},
            "status": episode.status,
            "location_id": episode.location_id,
            "created_at": episode.created_at.isoformat() if episode.created_at else None,
            "completed_at": episode.completed_at.isoformat() if episode.completed_at else None,
        }

    def serialize_thread(self, thread: SerialThread) -> dict[str, Any]:
        episodes = sorted(thread.episodes or [], key=lambda item: item.episode_index)
        return {
            "id": str(thread.id),
            "status": thread.status,
            "world_bible": thread.world_bible or {},
            "state": thread.state or {},
            "news_seed": thread.news_seed or {},
            "current_episode_index": thread.current_episode_index,
            "episodes": [self.serialize_episode(episode) for episode in episodes],
            "created_at": thread.created_at.isoformat() if thread.created_at else None,
            "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
        }

    def episode_archive(self, thread: SerialThread) -> list[dict[str, Any]]:
        episodes = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.status == "completed")
            .order_by(SerialEpisode.episode_index.asc())
            .all()
        )
        return [self._archive_episode_payload(episode) for episode in episodes]

    def _archive_episode_payload(self, episode: SerialEpisode) -> dict[str, Any]:
        title = "Episode"
        thumbnail = None
        if episode.mission_id:
            mission = self.db.get(RealWorldMission, episode.mission_id)
            if mission:
                title = mission.title
        if episode.scene_id:
            scene = self.db.get(GraphicNovelScene, episode.scene_id)
            if scene:
                title = scene.title
                first_panel = sorted(scene.panels or [], key=lambda item: item.panel_index)[0] if scene.panels else None
                thumbnail = first_panel.image_url or (first_panel.image_payload or {}).get("url") if first_panel else None
        return {
            "id": str(episode.id),
            "episode_index": episode.episode_index,
            "episode_label": f"Season 1 · Episode {episode.episode_index + 1}",
            "kind": episode.kind,
            "title": title,
            "mission_id": str(episode.mission_id) if episode.mission_id else None,
            "scene_id": str(episode.scene_id) if episode.scene_id else None,
            "thumbnail_url": thumbnail,
            "hook_text": (episode.hook or {}).get("text") or (episode.hook or {}).get("teaser") or "",
            "completed_at": episode.completed_at.isoformat() if episode.completed_at else None,
            "status": episode.status,
        }

    def cast_payload(self, thread: SerialThread) -> list[dict[str, Any]]:
        world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
        relationships = (thread.state or {}).get("relationships") if isinstance((thread.state or {}).get("relationships"), dict) else {}
        visual_characters = ((world.get("visual_design") or {}).get("characters") or {}) if isinstance(world.get("visual_design"), dict) else {}
        rows: list[dict[str, Any]] = []
        for member in world.get("cast") or []:
            if not isinstance(member, dict) or not member.get("id"):
                continue
            character_id = str(member.get("id"))
            relationship = relationships.get(character_id, {})
            visual = visual_characters.get(character_id, {}) if isinstance(visual_characters, dict) else {}
            rows.append(
                {
                    "id": character_id,
                    "name": member.get("name"),
                    "role": member.get("role"),
                    "dynamic_with_user": member.get("dynamic_with_user"),
                    "model_sheet_url": f"/assets/serial/characters/{character_id}/model-sheet.png",
                    "accent_colour": visual.get("accent_colour"),
                    "relationship": {
                        "closeness": int((relationship or {}).get("closeness") or 0),
                        "register": (relationship or {}).get("register") or "vous",
                        "register_switch_episode": (relationship or {}).get("register_switch_episode"),
                        "last_summary": (relationship or {}).get("last_summary") or "",
                        "callbacks": (relationship or {}).get("callbacks") or [],
                    },
                }
            )
        return rows

    @staticmethod
    def _load_world_bible() -> dict[str, Any]:
        for path in (WORLD_BIBLE_PATH, WORLD_BIBLE_V1_PATH):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
        return {
            "logline": "A newcomer settles into Paris.",
            "setting": {"city": "Paris", "tone": "warm, wry", "recurring_locations": []},
            "initial_state": {"heating_fixed": False, "marchand_trust": "neutral"},
            "cast": [],
            "register_map": {},
            "season_arcs": [],
        }

    def _initialize_thread_story_state(self, thread: SerialThread) -> bool:
        world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
        state = dict(thread.state or {})
        changed = False

        arcs_state = dict(state.get("arcs") or {})
        for arc in world.get("season_arcs") or []:
            if not isinstance(arc, dict) or not arc.get("id"):
                continue
            arc_id = str(arc.get("id"))
            if arc_id not in arcs_state:
                arcs_state[arc_id] = {"stage": None, "stage_index": -1, "advanced_at_episode": -1}
                changed = True
        if arcs_state != state.get("arcs"):
            state["arcs"] = arcs_state
            changed = True

        cast_ids = self._main_cast_ids(world) + ["landlord_marchand"]
        cast_last_seen = dict(state.get("cast_last_seen") or {})
        for character_id in cast_ids:
            if character_id not in cast_last_seen:
                cast_last_seen[character_id] = -1
                changed = True
        if cast_last_seen != state.get("cast_last_seen"):
            state["cast_last_seen"] = cast_last_seen
            changed = True

        relationships = dict(state.get("relationships") or {})
        for character_id in cast_ids:
            if character_id not in relationships:
                relationships[character_id] = {
                    "closeness": 0,
                    "register": "vous",
                    "register_switch_episode": None,
                    "last_summary": "",
                    "callbacks": [],
                }
                changed = True
        if relationships != state.get("relationships"):
            state["relationships"] = relationships
            changed = True

        if changed:
            thread.state = state
        return changed

    @staticmethod
    def _main_cast_ids(world: dict[str, Any]) -> list[str]:
        cast = world.get("cast") if isinstance(world.get("cast"), list) else []
        return [
            str(member.get("id"))
            for member in cast
            if isinstance(member, dict) and member.get("id") not in {"user", "landlord_marchand"}
        ]

    def _episode_brief(self, thread: SerialThread, beat: str) -> EpisodeBrief:
        if int(thread.current_episode_index or 0) == 0:
            return self._episode_one_brief(thread, beat)
        return SerialArcPlanner(thread).plan_next_episode(beat)

    def _episode_one_brief(self, thread: SerialThread, beat: str) -> EpisodeBrief:
        normalized_beat = "see" if beat in {"see", "feuilleton"} else "act"
        return EpisodeBrief(
            episode_index=0,
            beat=normalized_beat,
            a_plot={
                "arc_id": "user_settling_in",
                "stage_id": "arrival",
                "stage_index": 0,
                "stage_summary": "The radiator problem makes Paris practical before it becomes romantic.",
                "characters": ["user", "landlord_marchand"],
                "advance_on_completion": True,
                "sets": {"user.settling_thread": "arrival"},
            },
            b_plot={"kind": "everyday", "seed": "A cold apartment makes the first French message matter."},
            required_cast=["landlord_marchand"],
            location_id="user_apartment",
            structure="bottle",
            include_news_panel=False,
            include_choice_fork=False,
            stakes_level=1,
            hook_guidance="End with the radiator problem opening the door to Le Mistral.",
            next_beat_kind="feuilleton" if normalized_beat == "act" else "mission",
            relationship_context={"landlord_marchand": (thread.state or {}).get("relationships", {}).get("landlord_marchand", {})},
        )

    async def _news_seed(self, user: User) -> dict[str, Any]:
        interests = [item.strip() for item in (user.interests or "").split(",") if item.strip()]
        try:
            return await NewsService().fetch_feuilleton_daily_seed(interests=interests, refresh=True)
        except Exception:
            return {
                "mode": "serial_curated",
                "title": "Paris parle de petites urgences quotidiennes",
                "summary": "A curated town-texture seed for the serial episode.",
                "source": "Atelier serial fallback",
                "items": [],
            }

    def _current_episode(self, thread: SerialThread) -> SerialEpisode | None:
        return (
            self.db.query(SerialEpisode)
            .filter(
                SerialEpisode.thread_id == thread.id,
                SerialEpisode.episode_index == thread.current_episode_index,
            )
            .first()
        )

    def current_episode(self, thread: SerialThread) -> SerialEpisode | None:
        return self._current_episode(thread)

    async def start_next_beat(self, thread: SerialThread) -> SerialEpisode:
        hook = self._previous_hook(thread)
        next_kind = str((hook or {}).get("next_beat_kind") or ("mission" if thread.current_episode_index % 2 == 0 else "feuilleton"))
        if next_kind == "feuilleton":
            return await self.start_feuilleton_beat(thread)
        return await self.start_mission_beat(thread)

    def _previous_hook(self, thread: SerialThread) -> dict[str, Any]:
        previous = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index < thread.current_episode_index)
            .order_by(SerialEpisode.episode_index.desc())
            .first()
        )
        return previous.hook or {} if previous else {}

    def _latest_completed_mission(self, thread: SerialThread) -> RealWorldMission | None:
        episode = (
            self.db.query(SerialEpisode)
            .filter(
                SerialEpisode.thread_id == thread.id,
                SerialEpisode.kind == "mission",
                SerialEpisode.mission_id.isnot(None),
            )
            .order_by(SerialEpisode.episode_index.desc())
            .first()
        )
        return self.db.get(RealWorldMission, episode.mission_id) if episode and episode.mission_id else None

    def _episode_for_completion(
        self,
        *,
        thread: SerialThread,
        mission: RealWorldMission | None,
        scene: GraphicNovelScene | None,
    ) -> SerialEpisode | None:
        query = self.db.query(SerialEpisode).filter(SerialEpisode.thread_id == thread.id)
        if mission:
            return query.filter(SerialEpisode.mission_id == mission.id).first()
        if scene:
            return query.filter(SerialEpisode.scene_id == scene.id).first()
        return None

    @staticmethod
    def _completion_state_delta(
        *,
        mission: RealWorldMission | None,
        scene: GraphicNovelScene | None,
    ) -> dict[str, Any]:
        if mission:
            return ((mission.recap_payload or {}).get("outcome") or {}).get("state_delta") or {}
        if scene:
            branch_deltas: list[dict[str, Any]] = []
            for attempt in scene.attempts or []:
                branch = (attempt.correction_payload or {}).get("branch_outcome") or {}
                delta = branch.get("state_delta") if isinstance(branch, dict) else {}
                if isinstance(delta, dict) and delta.get("set"):
                    branch_deltas.append(delta)
            merged: dict[str, Any] = {"set": {}, "reason": "Feuilleton choices completed.", "source": {"type": "feuilleton", "id": str(scene.id)}}
            for delta in branch_deltas:
                merged["set"].update(delta.get("set") or {})
            return merged if merged["set"] else {}
        return {}

    @staticmethod
    def _completion_hook(
        *,
        mission: RealWorldMission | None,
        scene: GraphicNovelScene | None,
    ) -> dict[str, Any]:
        if mission:
            return ((mission.recap_payload or {}).get("outcome") or {}).get("hook") or {}
        if scene:
            return (scene.script_payload or {}).get("hook") or (scene.recap_payload or {}).get("hook") or {}
        return {}

    @staticmethod
    def _merge_state(thread: SerialThread, state_delta: dict[str, Any] | None) -> None:
        if not state_delta:
            return
        updates = state_delta.get("set") if isinstance(state_delta, dict) else {}
        if not isinstance(updates, dict):
            return
        merged = dict(thread.state or {})
        merged.update(updates)
        thread.state = merged

    def _apply_episode_brief_completion(
        self,
        *,
        thread: SerialThread,
        episode: SerialEpisode,
        mission: RealWorldMission | None,
        scene: GraphicNovelScene | None,
        hook: dict[str, Any] | None,
    ) -> None:
        brief = self._episode_brief_payload_for_completion(thread=thread, episode=episode)
        state = dict(thread.state or {})
        a_plot = brief.get("a_plot") if isinstance(brief.get("a_plot"), dict) else {}
        arc_id = str(a_plot.get("arc_id") or "")
        stage_id = a_plot.get("stage_id")
        try:
            stage_index = int(a_plot.get("stage_index"))
        except (TypeError, ValueError):
            stage_index = -1
        if arc_id and a_plot.get("advance_on_completion") and stage_id and stage_index >= 0:
            arcs_state = dict(state.get("arcs") or {})
            arcs_state[arc_id] = {
                "stage": str(stage_id),
                "stage_index": stage_index,
                "advanced_at_episode": episode.episode_index,
            }
            state["arcs"] = arcs_state
            for key, value in (a_plot.get("sets") or {}).items():
                state[str(key)] = value

        required_cast = [str(item) for item in brief.get("required_cast") or [] if str(item or "").strip()]
        if required_cast:
            cast_last_seen = dict(state.get("cast_last_seen") or {})
            for character_id in required_cast:
                cast_last_seen[character_id] = episode.episode_index
            state["cast_last_seen"] = cast_last_seen

        addressed = self._addressed_character_for_completion(brief=brief, mission=mission)
        if addressed:
            self._update_relationship_state(
                state=state,
                thread=thread,
                episode=episode,
                character_id=addressed,
                mission=mission,
                scene=scene,
                hook=hook,
            )

        pending = state.get("pending_register_switch")
        if isinstance(pending, dict) and pending.get("character_id") in required_cast and "offers the tu" in str(brief.get("hook_guidance") or ""):
            state.pop("pending_register_switch", None)
        thread.state = state

    def _episode_brief_payload_for_completion(self, *, thread: SerialThread, episode: SerialEpisode) -> dict[str, Any]:
        brief = episode.brief_payload if isinstance(episode.brief_payload, dict) else {}
        if isinstance(brief.get("a_plot"), dict) and brief.get("required_cast"):
            return brief

        beat = "see" if episode.kind == "feuilleton" else "act"
        original_index = thread.current_episode_index
        try:
            thread.current_episode_index = episode.episode_index
            generated = self._episode_brief(thread, beat).model_dump(mode="json")
        finally:
            thread.current_episode_index = original_index

        payload = {**generated, **brief}
        payload["episode_index"] = episode.episode_index
        if not isinstance(payload.get("a_plot"), dict):
            payload["a_plot"] = generated.get("a_plot") or {}
        if not payload.get("required_cast"):
            payload["required_cast"] = generated.get("required_cast") or []
        episode.brief_payload = payload
        self.db.add(episode)
        return payload

    def _update_relationship_state(
        self,
        *,
        state: dict[str, Any],
        thread: SerialThread,
        episode: SerialEpisode,
        character_id: str,
        mission: RealWorldMission | None,
        scene: GraphicNovelScene | None,
        hook: dict[str, Any] | None,
    ) -> None:
        relationships = dict(state.get("relationships") or {})
        entry = dict(relationships.get(character_id) or {})
        entry["closeness"] = max(0, min(5, int(entry.get("closeness") or 0)))
        entry["register"] = str(entry.get("register") or "vous")
        success = self._completion_success(mission=mission, scene=scene)
        if success:
            entry["closeness"] = min(5, entry["closeness"] + 1)
        summary = self._relationship_summary(mission=mission, scene=scene, hook=hook)
        if summary:
            entry["last_summary"] = summary
        callback = self._harvest_callback(mission=mission)
        if callback:
            callbacks = [str(item) for item in entry.get("callbacks") or [] if str(item or "").strip()]
            if callback not in callbacks:
                callbacks.append(callback)
            entry["callbacks"] = callbacks[-5:]
        if (
            entry["closeness"] >= 3
            and entry.get("register") != "tu"
            and self._tu_eligible(thread=thread, character_id=character_id)
        ):
            entry["register"] = "tu"
            entry["register_switch_episode"] = episode.episode_index + 1
            state["pending_register_switch"] = {
                "character_id": character_id,
                "name": self._character_name(thread, character_id),
                "episode_index": episode.episode_index + 1,
            }
        relationships[character_id] = entry
        state["relationships"] = relationships

    @staticmethod
    def _completion_success(*, mission: RealWorldMission | None, scene: GraphicNovelScene | None) -> bool:
        if scene:
            return True
        if not mission:
            return False
        outcome_source = (((mission.recap_payload or {}).get("outcome") or {}).get("state_delta") or {}).get("source") or {}
        try:
            score = float(outcome_source.get("score_0_4"))
        except (TypeError, ValueError):
            score = 0.0
        for attempt in mission.attempts or []:
            score = max(score, float(attempt.score_0_4 or 0.0))
        return score >= 3

    @staticmethod
    def _relationship_summary(
        *,
        mission: RealWorldMission | None,
        scene: GraphicNovelScene | None,
        hook: dict[str, Any] | None,
    ) -> str:
        if mission:
            reply = ((mission.recap_payload or {}).get("outcome") or {}).get("reply_text")
            if reply:
                return _compact(reply, 220)
        if scene and scene.title:
            return _compact(f"You shared the episode '{scene.title}'.", 220)
        return _compact((hook or {}).get("text"), 220)

    def _harvest_callback(self, *, mission: RealWorldMission | None) -> str:
        if not mission:
            return ""
        candidates: list[str] = []
        for attempt in sorted(mission.attempts or [], key=lambda item: item.created_at):
            text = (attempt.answer_payload or {}).get("text") or (attempt.answer_payload or {}).get("answer")
            if text:
                candidates.append(str(text))
        for turn in sorted(mission.turns or [], key=lambda item: item.turn_index):
            if turn.role == "user" and turn.text:
                candidates.append(turn.text)
        if not candidates:
            return ""
        return self._extract_callback_phrase(candidates[-1])

    def _extract_callback_phrase(self, text: str) -> str:
        candidate = _compact(text, 700)
        if not candidate or not settings.ATELIER_LLM_ENABLED or not (settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY):
            return ""
        try:
            result = LLMService().generate_chat_completion(
                [
                    {
                        "role": "user",
                        "content": (
                            "Learner message:\n"
                            f"{candidate}\n\n"
                            "Return exactly one memorable, funny, or reusable phrase from the learner's message "
                            "that friends could later quote back as an in-joke. Use at most 6 words. "
                            "Do not return greetings, names, polite openers, or generic task wording. "
                            "Return NONE if there is no distinctive phrase."
                        ),
                    }
                ],
                system_prompt="You extract tiny callback phrases for an episodic language-learning story.",
                temperature=0,
                max_tokens=24,
                model=settings.OPENAI_MISSION_FAST_MODEL if settings.OPENAI_API_KEY else None,
                request_timeout=8,
                disable_retries=True,
            )
        except Exception as exc:  # noqa: BLE001 - callback capture is optional story color
            logger.debug("Serial callback extraction skipped", error=str(exc))
            return ""
        return self._clean_callback_phrase(result.content)

    @staticmethod
    def _clean_callback_phrase(value: str) -> str:
        phrase = str(value or "").strip().strip("\"'“”‘’«»")
        phrase = _compact(phrase, 80)
        if not phrase or phrase.upper() == "NONE":
            return ""
        words = [word.strip(" ,.;:!?\"'()[]“”‘’«»") for word in phrase.split() if word.strip(" ,.;:!?\"'()[]“”‘’«»")]
        if not words or len(words) > 6:
            return ""
        normalized = " ".join(words).lower()
        if any(normalized.startswith(prefix) for prefix in CALLBACK_SALUTATION_PREFIXES):
            return ""
        return " ".join(words)

    # --- WP-G3: rolling "story so far" memory (lifetime continuity) ---
    STORY_SO_FAR_MAX = 12

    def _record_story_beat(
        self,
        thread: SerialThread,
        *,
        episode: SerialEpisode,
        mission: RealWorldMission | None,
        scene: GraphicNovelScene | None,
        hook: dict[str, Any] | None,
    ) -> None:
        """Append a short beat summary so long-running threads stay coherent without
        replaying full history into the generator. Capped to the last N beats."""
        beat_kind = "You acted" if mission else "You saw"
        if mission:
            title = mission.title or "a message"
            summary = ((mission.recap_payload or {}).get("outcome") or {}).get("reply_text") or ""
        else:
            title = (scene.title if scene else "") or "an episode"
            summary = ""
        hook_text = (hook or {}).get("text") or ""
        line = f"Ep {episode.episode_index + 1} · {beat_kind}: {title}."
        if hook_text:
            line += f" Left on: {hook_text}"
        state = dict(thread.state or {})
        history = list(state.get("story_so_far") or [])
        history.append(_compact(line, 240))
        state["story_so_far"] = history[-self.STORY_SO_FAR_MAX :]
        state["episodes_completed"] = int(state.get("episodes_completed") or 0) + 1
        thread.state = state

    @staticmethod
    def _story_so_far_text(thread: SerialThread) -> str:
        history = (thread.state or {}).get("story_so_far") or []
        return " ".join(str(item) for item in history[-6:])

    @staticmethod
    def _stakes_level(thread: SerialThread) -> int:
        completed = [episode for episode in thread.episodes or [] if episode.kind == "mission"]
        return max(1, min(3, 1 + len(completed) // 2))

    def _mission_seed(
        self,
        thread: SerialThread,
        hook: dict[str, Any],
        brief_payload: dict[str, Any] | None = None,
    ) -> tuple[str, str, str, str]:
        if thread.current_episode_index == 0:
            return (
                "Your first night in Paris. The radiator in your new studio is dead. Write a short formal message to the landlord to report the heating problem and ask for a repair time.",
                "The landlord understands the problem and confirms a repair appointment.",
                "landlord_marchand",
                "vous / polite formal",
            )
        brief = brief_payload or {}
        addressed = self._addressed_character_from_brief(brief)
        a_plot = brief.get("a_plot") if isinstance(brief.get("a_plot"), dict) else {}
        b_plot = brief.get("b_plot") if isinstance(brief.get("b_plot"), dict) else {}
        teaser = hook.get("teaser") or hook.get("text") or "Continue the thread with a concrete message."
        recap = self._story_so_far_text(thread)
        prefix = f"Story so far: {recap} " if recap else ""
        stage = a_plot.get("stage_summary") or "Move the relationship one concrete step forward."
        b_seed = b_plot.get("seed") or "Keep one everyday Paris complication alive."
        target_name = self._character_name(thread, addressed)
        return (
            (
                f"{prefix}The last episode ended here: {teaser} Write the next French message to {target_name}. "
                f"Advance this A-plot beat: {stage} Keep the B-plot as texture: {b_seed}"
            ),
            f"{target_name} understands what you propose and knows the next concrete step.",
            addressed,
            self._register_for_character(thread, addressed),
        )

    @staticmethod
    def _addressed_character_from_brief(brief_payload: dict[str, Any] | None) -> str:
        brief = brief_payload or {}
        required_cast = [str(item) for item in brief.get("required_cast") or [] if str(item or "").strip()]
        for preferred in ("landlord_marchand", "romy_tremblay", "lila_bonnet", "marin_leveque", "augustin_de_roncourt", "margaux_barman"):
            if preferred in required_cast:
                return preferred
        return required_cast[0] if required_cast else "margaux_barman"

    def _addressed_character_for_completion(
        self,
        *,
        brief: dict[str, Any],
        mission: RealWorldMission | None,
    ) -> str:
        if mission:
            prompt = mission.prompt_payload or {}
            if prompt.get("serial_character_id"):
                return str(prompt.get("serial_character_id"))
        return self._addressed_character_from_brief(brief)

    def _relationship_payload(self, *, thread: SerialThread, character_ids: list[Any]) -> dict[str, Any]:
        relationships = (thread.state or {}).get("relationships") if isinstance((thread.state or {}).get("relationships"), dict) else {}
        return {
            str(character_id): relationships.get(str(character_id), {"closeness": 0, "register": "vous", "callbacks": []})
            for character_id in character_ids
        }

    def _register_for_character(self, thread: SerialThread, character_id: str) -> str:
        if character_id == "landlord_marchand" or character_id.startswith("office_"):
            return "vous / polite formal"
        relationships = (thread.state or {}).get("relationships") if isinstance((thread.state or {}).get("relationships"), dict) else {}
        entry = relationships.get(character_id) if isinstance(relationships, dict) else {}
        if isinstance(entry, dict) and str(entry.get("register") or "").lower() == "tu":
            return "tu / warm informal"
        return "vous / cautious newcomer"

    def _tu_eligible(self, *, thread: SerialThread, character_id: str) -> bool:
        if character_id in {"landlord_marchand", "user"}:
            return False
        member = self._cast_member(thread, character_id)
        raw = str((member or {}).get("register_with_user") or "").lower()
        return "tu" in raw or character_id in self._main_cast_ids(thread.world_bible or {})

    def _character_name(self, thread: SerialThread, character_id: str) -> str:
        member = self._cast_member(thread, character_id)
        if member and member.get("name"):
            return str(member.get("name"))
        return {
            "landlord_marchand": "M. Marchand",
            "margaux_barman": "Margaux",
            "augustin_de_roncourt": "Gus",
            "romy_tremblay": "Romy",
            "marin_leveque": "Marin",
            "lila_bonnet": "Lila",
        }.get(character_id, character_id.replace("_", " ").title())

    def _character_role(self, thread: SerialThread, character_id: str) -> str:
        member = self._cast_member(thread, character_id)
        if member and member.get("role"):
            return _compact(member.get("role"), 80)
        return "propriétaire" if character_id == "landlord_marchand" else "Paris thread"

    def _character_initials(self, thread: SerialThread, character_id: str) -> str:
        name = self._character_name(thread, character_id)
        parts = [part for part in name.replace("«", " ").replace("»", " ").split() if part[:1].isalpha()]
        return "·".join(part[:1].upper() for part in parts[:2]) or "S"

    @staticmethod
    def _cast_member(thread: SerialThread, character_id: str) -> dict[str, Any] | None:
        world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
        for member in world.get("cast") or []:
            if isinstance(member, dict) and member.get("id") == character_id:
                return member
        return None

    def _enqueue_next_beat(self, thread_id: UUID) -> None:
        try:
            from app.tasks.serial_generation import create_next_serial_beat

            create_next_serial_beat.delay(str(thread_id))
        except Exception as exc:  # pragma: no cover - broker-less dev/test fallback
            logger.info("Serial next beat queued for lazy generation", thread_id=str(thread_id), error=str(exc))


__all__ = ["SerialThreadService"]
