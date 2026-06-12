"""Graphic novel / Feuilleton practice services."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.atelier import AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.graphic_novel import (
    GraphicNovelAttempt,
    GraphicNovelPanel,
    GraphicNovelScene,
    PersonalInputItem,
)
from app.db.models.mission import RealWorldMission
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier_assets import AtelierAssetService
from app.services.error_memory import ErrorMemoryService, serialize_error_memory
from app.services.grammar_feedback import infer_grammar_profile
from app.services.llm_service import LLMProviderError, LLMService
from app.services.news_service import NewsService
from app.services.progress import ProgressService
from app.services.serial_costs import serial_generation_cost_event
from app.services.vocabulary_credit import VocabularyCreditService


GRAPHIC_NOVEL_PROMPT_VERSION = "feuilleton-visual-gag-v3"
COMEDY_REFERENCE_PACK_VERSION = "french-visual-gag-pack-v2"
GRAPHIC_NOVEL_PROMPT_ASSET_DIR = Path(__file__).resolve().parent.parent / "prompts" / "feuilleton"
GRAPHIC_NOVEL_TASKS = ("cloze", "choice", "short_sentence")
GRAPHIC_NOVEL_PANEL_COUNTS = (4, 6, 8)
GRAPHIC_NOVEL_TASK_COUNTS = {4: 3, 6: 5, 8: 7}
GRAPHIC_NOVEL_STORY_QUALITIES = ("standard", "premium")
GRAPHIC_NOVEL_HUMOR_STYLES = ("dry", "satirical", "absurd")
GRAPHIC_NOVEL_EXPERIENCE_MODES = ("study", "reward")
GRAPHIC_NOVEL_RENDER_MODES = ("page", "panels")
GRAPHIC_NOVEL_IMAGE_QUALITIES = ("low", "medium", "high")
GRAPHIC_NOVEL_PUBLIC_FIGURE_MODES = ("off", "named_context", "editorial_caricature")
GENERIC_PANEL_BEAT_PHRASES = (
    "the practical problem gets slightly more theatrical",
    "the target grammar stays necessary",
    "target grammar",
    "target construction",
    "pedagogy",
    "exercise",
    "worksheet",
    "learner",
)
IMAGE_STYLE_MOODBOARD = (
    "Visual moodboard: Penguin Crime and Penguin Modern Classics cover design, Len Deighton-era spy paperback covers, "
    "photomechanical halftone printing, sparse editorial collage, high-contrast ink, restrained cream/black/red with occasional muted blue or green, "
    "strong negative space, one decisive prop, diagonal typographic energy without readable typography, and slightly dry noir atmosphere. "
    "Avoid decorative modernist shape clutter, repeated props, busy café clutter, cute app illustration, and crowded adventure-comic scenes."
)
_PROMPT_ASSET_CACHE: dict[str, tuple[int, str]] = {}


def _cached_prompt_asset_text(filename: str) -> str:
    path = GRAPHIC_NOVEL_PROMPT_ASSET_DIR / filename
    try:
        mtime_ns = path.stat().st_mtime_ns
        cached = _PROMPT_ASSET_CACHE.get(filename)
        if cached and cached[0] == mtime_ns:
            return cached[1]
        text = path.read_text(encoding="utf-8")
        _PROMPT_ASSET_CACHE[filename] = (mtime_ns, text)
        return text
    except OSError as exc:
        logger.warning("Feuilleton prompt asset missing", path=str(path), error=str(exc))
        return ""


def _panel_count(value: int | None) -> int:
    resolved = value or settings.GRAPHIC_NOVEL_DEFAULT_PANEL_COUNT
    return resolved if resolved in GRAPHIC_NOVEL_PANEL_COUNTS else 6


def _story_quality(value: str | None) -> str:
    return value if value in GRAPHIC_NOVEL_STORY_QUALITIES else "standard"


def _humor_style(value: str | None) -> str:
    return value if value in GRAPHIC_NOVEL_HUMOR_STYLES else "satirical"


def _experience_mode(value: str | None) -> str:
    return value if value in GRAPHIC_NOVEL_EXPERIENCE_MODES else "study"


def _render_mode(value: str | None) -> str:
    return value if value in GRAPHIC_NOVEL_RENDER_MODES else "panels"


def _image_quality(value: str | None) -> str:
    configured = value or "medium"
    return configured if configured in GRAPHIC_NOVEL_IMAGE_QUALITIES else "medium"


def _public_figure_mode(value: str | None) -> str:
    return value if value in GRAPHIC_NOVEL_PUBLIC_FIGURE_MODES else "named_context"


def _task_count(panel_count: int, experience_mode: str) -> int:
    if experience_mode == "reward":
        return 0
    return GRAPHIC_NOVEL_TASK_COUNTS[panel_count]


def _safe_llm() -> LLMService | None:
    if not settings.ATELIER_LLM_ENABLED:
        return None
    try:
        return LLMService()
    except ValueError:
        return None


def _clean_feedback(text: Any) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"\b[Tt]he learner\b", "you", cleaned)
    cleaned = re.sub(r"\b[Tt]he user\b", "you", cleaned)
    cleaned = re.sub(r"\b[Cc]orrect\.\s*You matched the target form(?: in this panel)?\.?", "Yes. This answer makes the next beat work.", cleaned)
    cleaned = re.sub(r"\btarget form\b", "needed French form", cleaned)
    return cleaned


def _iter_strings(value: Any) -> Any:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_strings(child)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _iter_strings(child)


def _contains_any_phrase(value: Any, phrases: tuple[str, ...]) -> bool:
    lowered_phrases = tuple(phrase.lower() for phrase in phrases)
    return any(
        any(phrase in text.lower() for phrase in lowered_phrases)
        for text in _iter_strings(value)
    )


def _normalize_text(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[’']", "'", value)
    value = re.sub(r"[^a-z0-9àâçéèêëîïôûùüÿñæœ'\s-]", " ", value)
    return " ".join(value.split())


def _lexical_tokens(text: Any) -> set[str]:
    return {token for token in _normalize_text(text).split() if len(token) >= 4}


def _looks_like_english_sentence(text: Any) -> bool:
    normalized = f" {_normalize_text(text)} "
    if not normalized.strip():
        return False
    english_markers = (
        " the ",
        " they ",
        " their ",
        " this ",
        " that ",
        " with ",
        " from ",
        " into ",
        " would ",
        " could ",
        " should ",
        " oldest ",
        " poster ",
        " meeting ",
        " chair ",
        " coffee ",
    )
    french_markers = (
        " le ",
        " la ",
        " les ",
        " un ",
        " une ",
        " des ",
        " je ",
        " tu ",
        " il ",
        " elle ",
        " nous ",
        " vous ",
        " ils ",
        " elles ",
        " si ",
        " quand ",
        " que ",
        " qui ",
        " dans ",
        " pour ",
        " avec ",
        " est ",
        " sont ",
    )
    return any(marker in normalized for marker in english_markers) and not any(
        marker in normalized for marker in french_markers
    )


def _has_invalid_french_article_phrase(text: Any) -> bool:
    normalized = f" {_normalize_text(text)} "
    invalid_patterns = (
        r"\ble\s+[aeiouhàâéèêëîïôûùüÿ]",
        r"\bla\s+[aeiouhàâéèêëîïôûùüÿ]",
        r"\bl'\s+",
        r"\ble\s+\w+s\b",
        r"\bla\s+\w+s\b",
    )
    return any(re.search(pattern, normalized) for pattern in invalid_patterns)


def _mentions_parentheses(text: Any) -> bool:
    return any(word in _normalize_text(text) for word in ("parentheses", "parenthese"))


def _has_parenthetical_cue(text: Any) -> bool:
    return bool(re.search(r"\([^)]+\)", str(text or "")))


def _feature_summary(task: dict[str, Any]) -> str:
    features = [str(item).strip() for item in task.get("expected_features") or [] if str(item).strip()]
    if features:
        return "; ".join(features[:3])
    label = str(task.get("label") or "").strip()
    if label:
        return label
    return str(task.get("instruction") or "the requested French construction").strip()


def _task_context_text(task: dict[str, Any]) -> str:
    return _normalize_text(
        " ".join(
            str(value or "")
            for value in (
                task.get("label"),
                task.get("instruction"),
                task.get("prompt"),
                task.get("feedback_context"),
                " ".join(str(item) for item in task.get("expected_features") or []),
            )
        )
    )


def _task_requires_si_frame(task: dict[str, Any]) -> bool:
    text = _task_context_text(task)
    return " si " in f" {text} " or "s'il" in text or "type 1" in text or "condition" in text


def _feedback_sentence(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def _answer_fragment(answer: str) -> str:
    value = str(answer or "").strip()
    return f"`{value}`" if value else "your answer"


def _normalize_task_instruction(task: dict[str, Any], *, fallback: str = "") -> str:
    return str(task.get("instruction") or fallback).strip()


def _concept_title(concept: GrammarConcept, asset_service: AtelierAssetService | None = None) -> str:
    if asset_service:
        try:
            title = (asset_service.approved_blueprint_payload(concept) or {}).get("display_title")
            if title:
                return str(title)
        except Exception:
            pass
    return concept.name


def _ids(rows: list[Any]) -> list[str]:
    return [str(row.id) for row in rows if getattr(row, "id", None)]


def _dedupe_ints(values: list[Any]) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value is None:
            continue
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _compact_text(value: Any, *, max_length: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max(0, max_length - 1)].rstrip()}…"


class GraphicNovelGenerationError(RuntimeError):
    """Raised when Feuilleton script generation should fail honestly."""

    def __init__(self, message: str, *, errors: list[str] | None = None, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []
        self.metadata = metadata or {}


class GraphicNovelTargetVocabularyError(ValueError):
    """Raised when explicit Feuilleton vocabulary IDs cannot be resolved."""

    def __init__(self, missing_ids: list[int]) -> None:
        super().__init__("Unknown target vocabulary ids")
        self.missing_ids = missing_ids


class GraphicNovelScheduler:
    """Create and retrieve errata-led Feuilleton scenes."""

    def __init__(self, db: Session, generator: "GraphicNovelStoryGenerator | None" = None) -> None:
        self.db = db
        self.generator = generator or GraphicNovelStoryGenerator(db)

    async def today(self, user: User) -> dict[str, Any]:
        active = (
            self.db.query(GraphicNovelScene)
            .filter(GraphicNovelScene.user_id == user.id, GraphicNovelScene.status.in_(["in_progress", "generating"]))
            .order_by(GraphicNovelScene.updated_at.desc())
            .first()
        )
        available = (
            self.db.query(GraphicNovelScene)
            .filter(GraphicNovelScene.user_id == user.id, GraphicNovelScene.status == "available")
            .order_by(GraphicNovelScene.created_at.desc())
            .first()
        )
        recent = (
            self.db.query(GraphicNovelScene)
            .filter(GraphicNovelScene.user_id == user.id, GraphicNovelScene.status == "completed")
            .order_by(GraphicNovelScene.completed_at.desc().nullslast(), GraphicNovelScene.created_at.desc())
            .limit(5)
            .all()
        )
        due_errata = ErrorMemoryService(self.db).due_error_records(user, limit=5)
        return {
            "active_scene": serialize_scene(active) if active else None,
            "available_scene": serialize_scene(available) if available else None,
            "recent_completed": [serialize_scene(scene, include_children=False) for scene in recent],
            "recommendation": {
                "label": "Errata-led Feuilleton",
                "due_errata_count": len(due_errata),
                "reason": "Use due mistakes in a visual reading scene." if due_errata else "Use weak grammar in a short visual scene.",
                "target_errata": [
                    {
                        "id": str(error.id),
                        "display_label": error.display_label or error.error_pattern or "Remembered mistake",
                        "concept_id": error.concept_id,
                    }
                    for error in due_errata
                ],
            },
        }

    async def create(
        self,
        *,
        user: User,
        cadence: str = "ad_hoc",
        atelier_session_id: UUID | None = None,
        mission_id: UUID | None = None,
        serial_thread_id: UUID | None = None,
        episode_index: int | None = None,
        personal_input_item_id: UUID | None = None,
        preferred_concept_ids: list[int] | None = None,
        preferred_errata_ids: list[UUID] | None = None,
        target_vocabulary_ids: list[int] | None = None,
        use_news: bool = False,
        panel_count: int | None = None,
        story_quality: str = "standard",
        humor_style: str = "satirical",
        experience_mode: str = "study",
        render_mode: str = "panels",
        image_quality: str | None = None,
        public_figure_mode: str = "named_context",
        force_new: bool = False,
        refresh_news: bool = False,
        sync: bool | None = None,
    ) -> GraphicNovelScene:
        resolved_panel_count = _panel_count(panel_count)
        resolved_story_quality = _story_quality(story_quality)
        resolved_humor_style = _humor_style(humor_style)
        resolved_experience_mode = _experience_mode(experience_mode)
        resolved_render_mode = _render_mode(render_mode)
        resolved_image_quality = _image_quality(image_quality)
        resolved_public_figure_mode = _public_figure_mode(public_figure_mode)
        sync_images = bool(sync) if sync is not None else not settings.GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED
        atelier_session = self._atelier_session(user=user, atelier_session_id=atelier_session_id)
        mission = self._mission(user=user, mission_id=mission_id)
        serial_thread = self._serial_thread(user=user, serial_thread_id=serial_thread_id)
        if serial_thread and episode_index is None:
            episode_index = serial_thread.current_episode_index
        personal_item = self._personal_item(user=user, personal_input_item_id=personal_input_item_id)
        errata = self._select_errata(user=user, preferred_errata_ids=preferred_errata_ids, limit=3)
        concepts = self._select_concepts(
            user=user,
            errata=errata,
            atelier_session=atelier_session,
            mission=mission,
            preferred_concept_ids=preferred_concept_ids,
            limit=3,
        )
        source_snapshot = await self._source_snapshot(
            user=user,
            personal_item=personal_item,
            use_news=use_news,
            refresh_news=refresh_news,
        )
        if target_vocabulary_ids is not None:
            preferred_vocabulary_ids = _dedupe_ints(target_vocabulary_ids)
            preferred_vocabulary_source = "explicit"
        elif mission:
            preferred_vocabulary_ids = _dedupe_ints(mission.target_vocabulary_ids or [])
            preferred_vocabulary_source = "mission"
        else:
            preferred_vocabulary_ids = []
            preferred_vocabulary_source = "target"
        target_vocabulary = self._select_vocabulary(
            user=user,
            errata=errata,
            preferred_vocabulary_ids=preferred_vocabulary_ids,
            preferred_vocabulary_source=preferred_vocabulary_source,
            limit=4,
        )
        target_vocabulary_ids = _dedupe_ints(
            [item.get("word_id") for item in target_vocabulary]
            + [error.linked_word_id for error in errata if error.linked_word_id]
        )
        base_cache_key = self._cache_key(
            user=user,
            concepts=concepts,
            errata=errata,
            target_vocabulary_ids=target_vocabulary_ids,
            source_snapshot=source_snapshot,
            cadence=cadence,
            panel_count=resolved_panel_count,
            story_quality=resolved_story_quality,
            humor_style=resolved_humor_style,
            experience_mode=resolved_experience_mode,
            render_mode=resolved_render_mode,
            image_quality=resolved_image_quality,
            public_figure_mode=resolved_public_figure_mode,
            serial_context=self._serial_context(serial_thread=serial_thread, episode_index=episode_index),
        )
        cache_key = base_cache_key
        force_new_nonce: str | None = None
        if force_new:
            force_new_nonce = uuid4().hex[:24]
            cache_key = f"{base_cache_key}:fresh:{force_new_nonce}"
        existing = (
            self.db.query(GraphicNovelScene)
            .filter(GraphicNovelScene.user_id == user.id, GraphicNovelScene.cache_key == cache_key)
            .first()
        )
        if existing and not force_new:
            return existing

        script = self.generator.build_script(
            user=user,
            concepts=concepts,
            errata=errata,
            source_snapshot=source_snapshot,
            panel_count=resolved_panel_count,
            story_quality=resolved_story_quality,
            humor_style=resolved_humor_style,
            experience_mode=resolved_experience_mode,
            render_mode=resolved_render_mode,
            image_quality=resolved_image_quality,
            public_figure_mode=resolved_public_figure_mode,
            target_vocabulary=target_vocabulary,
            serial_context=self._serial_context(serial_thread=serial_thread, episode_index=episode_index),
        )
        generation_debug = script.setdefault("generation_debug", {})
        generation_debug["base_cache_key"] = base_cache_key
        generation_debug["cache_key"] = cache_key
        generation_debug["force_new"] = force_new
        if force_new_nonce:
            generation_debug["force_new_nonce"] = force_new_nonce
        scene = GraphicNovelScene(
            user_id=user.id,
            atelier_session_id=atelier_session.id if atelier_session else None,
            mission_id=mission.id if mission else None,
            serial_thread_id=serial_thread.id if serial_thread else None,
            episode_index=episode_index,
            personal_input_item_id=personal_item.id if personal_item else None,
            status="available" if sync_images else "generating",
            cadence=cadence,
            title=script["title"],
            brief=script["brief"],
            selected_concept_ids=[concept.id for concept in concepts],
            target_errata_ids=_ids(errata),
            target_vocabulary_ids=target_vocabulary_ids,
            source_snapshot=source_snapshot,
            script_payload=script,
            recap_payload={},
            cache_key=cache_key,
            prompt_version=GRAPHIC_NOVEL_PROMPT_VERSION,
            image_model=settings.OPENAI_IMAGE_MODEL,
            image_quality=resolved_image_quality,
            started_at=datetime.now(timezone.utc) if not sync_images else None,
        )
        self.db.add(scene)
        self.db.flush([scene])
        rendered_panels = (
            await self._render_panel_payloads(
                script=script,
                panel_payloads=script["panels"],
                image_quality=resolved_image_quality,
                render_mode=resolved_render_mode,
            )
            if sync_images
            else [
                (
                    panel_payload,
                    {
                        "url": None,
                        "prompt": panel_payload.get("image_prompt", ""),
                        "model": settings.OPENAI_IMAGE_MODEL,
                        "quality": resolved_image_quality,
                        "fallback_used": False,
                        "render_mode": resolved_render_mode,
                        "status": "queued",
                    },
                )
                for panel_payload in script["panels"]
            ]
        )
        for panel_payload, image in rendered_panels:
            self.db.add(
                GraphicNovelPanel(
                    scene_id=scene.id,
                    panel_index=panel_payload["panel_index"],
                    title=panel_payload["title"],
                    beat=panel_payload["beat"],
                    image_prompt=panel_payload["image_prompt"],
                    image_url=image["url"],
                    image_payload=image,
                    overlay_payload=panel_payload["overlay_payload"],
                    generation_metadata={
                        "prompt_version": GRAPHIC_NOVEL_PROMPT_VERSION,
                        "story_model": script.get("story_model"),
                        "story_quality": script.get("story_quality"),
                        "humor_style": script.get("humor_style"),
                        "experience_mode": resolved_experience_mode,
                        "render_mode": resolved_render_mode,
                        "image_quality": resolved_image_quality,
                        "public_figure_mode": resolved_public_figure_mode,
                        "story_prompt": {
                            "headline_mechanic": script.get("headline_mechanic"),
                            "selected_visual_premise": script.get("selected_visual_premise"),
                            "character_refs": script.get("character_bible"),
                            "visual_beat": panel_payload.get("beat"),
                            "visual_gag": panel_payload.get("visual_gag"),
                        },
                        "image_prompt": panel_payload.get("image_prompt"),
                        "hook": panel_payload.get("hook"),
                        "model": image.get("model"),
                        "fallback_used": image.get("fallback_used", False),
                        "image_status": "available" if image.get("url") else "queued",
                    },
                )
            )
        self.db.commit()
        self.db.refresh(scene)
        if serial_thread:
            logger.bind(
                event_name="serial_generation_cost_estimate",
                **serial_generation_cost_event(scene),
            ).info("Serial generation cost estimate recorded")
        if not sync_images:
            self._enqueue_scene_image_generation(scene.id)
        return scene

    async def _render_panel_payloads(
        self,
        *,
        script: dict[str, Any],
        panel_payloads: list[dict[str, Any]],
        image_quality: str,
        render_mode: str,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        image_service = GraphicNovelImageService()
        if render_mode == "page":
            script["page_image"] = await image_service.generate_page_image(
                script=script,
                image_quality=image_quality,
            )
            return [
                (
                    panel_payload,
                    {
                        "url": None,
                        "prompt": panel_payload.get("image_prompt", ""),
                        "model": "shared-page-image",
                        "quality": image_quality,
                        "fallback_used": False,
                        "render_mode": "page",
                    },
                )
                for panel_payload in panel_payloads
            ]
        image_concurrency = max(1, int(settings.GRAPHIC_NOVEL_IMAGE_CONCURRENCY or 1))
        image_semaphore = asyncio.Semaphore(image_concurrency)

        async def render_panel(panel_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            async with image_semaphore:
                image = await image_service.generate_panel_image(
                    panel_payload["image_prompt"],
                    panel_payload["panel_index"],
                    image_quality=image_quality,
                )
                return panel_payload, image

        return await asyncio.gather(*(render_panel(panel_payload) for panel_payload in panel_payloads))

    def _enqueue_scene_image_generation(self, scene_id: UUID) -> None:
        try:
            from app.tasks.serial_generation import generate_scene_images

            generate_scene_images.delay(str(scene_id))
        except Exception as exc:  # pragma: no cover - broker-less dev/test fallback
            logger.info("Feuilleton image generation queued for worker/lazy retry", scene_id=str(scene_id), error=str(exc))

    async def render_scene_images(self, scene_id: UUID | str) -> GraphicNovelScene:
        scene_uuid = UUID(str(scene_id)) if not isinstance(scene_id, UUID) else scene_id
        scene = self.db.get(GraphicNovelScene, scene_uuid)
        if not scene:
            raise ValueError(f"Graphic novel scene {scene_id} not found")
        script = dict(scene.script_payload or {})
        panels = sorted(scene.panels or [], key=lambda item: item.panel_index)
        if not panels:
            raise ValueError(f"Graphic novel scene {scene_id} has no panels")
        scene.status = "generating"
        scene.started_at = scene.started_at or datetime.now(timezone.utc)
        self.db.add(scene)
        self.db.commit()
        try:
            panel_payloads = script.get("panels") if isinstance(script.get("panels"), list) else []
            payload_by_index = {int(item.get("panel_index") or 0): item for item in panel_payloads if isinstance(item, dict)}
            rendered = await self._render_panel_payloads(
                script=script,
                panel_payloads=[payload_by_index.get(panel.panel_index, {
                    "panel_index": panel.panel_index,
                    "image_prompt": panel.image_prompt,
                }) for panel in panels],
                image_quality=_image_quality(scene.image_quality),
                render_mode=_render_mode(script.get("render_mode")),
            )
            image_by_index = {int(panel_payload.get("panel_index") or 0): image for panel_payload, image in rendered}
            for panel in panels:
                image = image_by_index.get(panel.panel_index) or {}
                panel.image_url = image.get("url")
                panel.image_payload = image
                metadata = dict(panel.generation_metadata or {})
                metadata["image_status"] = "available"
                metadata["model"] = image.get("model")
                metadata["fallback_used"] = image.get("fallback_used", False)
                panel.generation_metadata = metadata
                self.db.add(panel)
            scene.script_payload = script
            scene.status = "available"
            scene.completed_at = datetime.now(timezone.utc)
            if getattr(scene, "serial_thread_id", None):
                episode = (
                    self.db.query(SerialEpisode)
                    .filter(
                        SerialEpisode.thread_id == scene.serial_thread_id,
                        SerialEpisode.scene_id == scene.id,
                    )
                    .first()
                )
                if episode and episode.status != "completed":
                    episode.status = "available"
                    episode.hook = (scene.script_payload or {}).get("hook") or episode.hook or {}
                    episode.location_id = (scene.script_payload or {}).get("location_id") or episode.location_id
                    self.db.add(episode)
            self.db.add(scene)
            self.db.commit()
            self.db.refresh(scene)
            return scene
        except Exception:
            self.db.rollback()
            scene = self.db.get(GraphicNovelScene, scene_uuid)
            if scene:
                scene.status = "generation_failed"
                self.db.add(scene)
                self.db.commit()
            raise

    def _apply_target_vocabulary_credit(self, *, user: User, scene: GraphicNovelScene) -> dict[str, int]:
        target_ids = _dedupe_ints(scene.target_vocabulary_ids or [])
        if not target_ids:
            return {
                "seen_context": 0,
                "recognized": 0,
                "produced_correct": 0,
                "produced_incorrect": 0,
                "missed_target": 0,
                "errata_created": 0,
            }
        words = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(target_ids)).all()
        by_id = {word.id: word for word in words}
        summary = {
            "seen_context": 0,
            "recognized": 0,
            "produced_correct": 0,
            "produced_incorrect": 0,
            "missed_target": 0,
            "errata_created": 0,
        }
        explicit_event_ids: set[int] = set()
        for attempt in scene.attempts or []:
            for event in (attempt.correction_payload or {}).get("vocabulary_events") or []:
                if not isinstance(event, dict):
                    continue
                event_ids = _dedupe_ints([event.get("word_id")])
                if not event_ids or event_ids[0] not in by_id:
                    continue
                credit_kind = self._vocabulary_credit_kind(str(event.get("event_type") or "seen_context"))
                explicit_event_ids.add(event_ids[0])
                summary[credit_kind] = summary.get(credit_kind, 0) + 1

        credit_service = VocabularyCreditService(self.db)
        seen_results = []
        for word in words:
            if word.id in explicit_event_ids:
                continue
            seen_results.append(
                credit_service.apply(
                    user=user,
                    word=word,
                    event_type="seen_context",
                    source_type="graphic_novel",
                    context=scene.title,
                    source_payload={
                        "scene_id": str(scene.id),
                        "reason": "feuilleton_target_context",
                    },
                )
            )
        for key, value in credit_service.summarize(seen_results).items():
            summary[key] = summary.get(key, 0) + value
        return summary

    @staticmethod
    def _vocabulary_credit_kind(event_type: str) -> str:
        normalized = str(event_type or "seen_context").lower()
        if normalized in {"produced_correct", "used_correctly", "free_production_correct"}:
            return "produced_correct"
        if normalized in {"produced_incorrect", "used_incorrectly", "incorrect", "incorrect_production"}:
            return "produced_incorrect"
        if normalized in {"missed_target", "missing_target", "avoided_target"}:
            return "missed_target"
        if normalized in {"recognized", "translated", "recognition", "context_translation"}:
            return "recognized"
        return "seen_context"

    def complete(self, *, user: User, scene: GraphicNovelScene) -> GraphicNovelScene:
        attempts = scene.attempts or []
        errata_count = sum(len((attempt.correction_payload or {}).get("errata") or []) for attempt in attempts)
        vocabulary_credit = self._apply_target_vocabulary_credit(user=user, scene=scene)
        scene.status = "completed"
        scene.completed_at = datetime.now(timezone.utc)
        scene.recap_payload = {
            "attempts": len(attempts),
            "panels": len(scene.panels or []),
            "errata_logged": errata_count,
            "vocabulary_credit": vocabulary_credit,
            "completed_at": scene.completed_at.isoformat(),
            "targets": scene.script_payload.get("targets", []),
            "hook": (scene.script_payload or {}).get("hook") or {},
        }
        if getattr(scene, "serial_thread_id", None):
            episode = (
                self.db.query(SerialEpisode)
                .filter(
                    SerialEpisode.thread_id == scene.serial_thread_id,
                    SerialEpisode.scene_id == scene.id,
                )
                .first()
            )
            if episode:
                episode.hook = (scene.script_payload or {}).get("hook") or {}
                episode.location_id = (scene.script_payload or {}).get("location_id") or episode.location_id
                self.db.add(episode)
        self.db.add(scene)
        self.db.commit()
        self.db.refresh(scene)
        return scene

    def get(self, *, user: User, scene_id: UUID) -> GraphicNovelScene | None:
        return (
            self.db.query(GraphicNovelScene)
            .filter(GraphicNovelScene.id == scene_id, GraphicNovelScene.user_id == user.id)
            .first()
        )

    @staticmethod
    def required_task_ids(scene: GraphicNovelScene) -> list[str]:
        script = scene.script_payload or {}
        if script.get("visual_only_demo"):
            return []
        if script.get("experience_mode") == "reward":
            return []
        ordered: list[str] = []
        seen: set[str] = set()

        def add(task_id: Any) -> None:
            task_id_text = str(task_id or "").strip()
            if task_id_text and task_id_text not in seen:
                ordered.append(task_id_text)
                seen.add(task_id_text)

        for panel in scene.panels or []:
            for task in (panel.overlay_payload or {}).get("tasks") or []:
                if isinstance(task, dict):
                    add(task.get("id"))
        final_prompt = script.get("final_prompt") if isinstance(script.get("final_prompt"), dict) else {}
        add(final_prompt.get("id"))
        return ordered

    @classmethod
    def missing_required_task_ids(cls, scene: GraphicNovelScene) -> list[str]:
        attempted = {
            str(attempt.task_id)
            for attempt in scene.attempts or []
            if getattr(attempt, "task_id", None)
        }
        return [task_id for task_id in cls.required_task_ids(scene) if task_id not in attempted]

    def _atelier_session(self, *, user: User, atelier_session_id: UUID | None) -> AtelierSession | None:
        if not atelier_session_id:
            return None
        session = self.db.get(AtelierSession, atelier_session_id)
        return session if session and session.user_id == user.id else None

    def _mission(self, *, user: User, mission_id: UUID | None) -> RealWorldMission | None:
        if not mission_id:
            return None
        mission = self.db.get(RealWorldMission, mission_id)
        return mission if mission and mission.user_id == user.id else None

    def _serial_thread(self, *, user: User, serial_thread_id: UUID | None) -> SerialThread | None:
        if not serial_thread_id:
            return None
        thread = self.db.get(SerialThread, serial_thread_id)
        return thread if thread and thread.user_id == user.id else None

    def _serial_context(self, *, serial_thread: SerialThread | None, episode_index: int | None) -> dict[str, Any] | None:
        if not serial_thread:
            return None
        ordered_episodes = sorted(serial_thread.episodes or [], key=lambda item: item.episode_index)
        previous_locations = [episode.location_id for episode in ordered_episodes if episode.location_id]
        hook_from_previous: dict[str, Any] = {}
        for episode in reversed(ordered_episodes):
            if isinstance(episode.hook, dict) and episode.hook.get("text"):
                hook_from_previous = episode.hook
                break
        resolved_episode_index = episode_index if episode_index is not None else serial_thread.current_episode_index
        current_episode = next(
            (episode for episode in ordered_episodes if episode.episode_index == resolved_episode_index),
            None,
        )
        return {
            "thread_id": str(serial_thread.id),
            "episode_index": resolved_episode_index,
            "world_bible": serial_thread.world_bible or {},
            "state": serial_thread.state or {},
            "news_seed": serial_thread.news_seed or {},
            "previous_locations": previous_locations,
            "hook_from_previous": hook_from_previous,
            "episode_brief": current_episode.brief_payload if current_episode and isinstance(current_episode.brief_payload, dict) else {},
        }

    def _personal_item(self, *, user: User, personal_input_item_id: UUID | None) -> PersonalInputItem | None:
        if personal_input_item_id:
            item = self.db.get(PersonalInputItem, personal_input_item_id)
            return item if item and item.user_id == user.id else None
        return None

    def _select_errata(
        self,
        *,
        user: User,
        preferred_errata_ids: list[UUID] | None,
        limit: int,
    ) -> list[UserError]:
        ordered: list[UserError] = []
        seen: set[UUID] = set()
        if preferred_errata_ids:
            rows = (
                self.db.query(UserError)
                .filter(UserError.user_id == user.id, UserError.id.in_(preferred_errata_ids))
                .all()
            )
            by_id = {row.id: row for row in rows}
            for error_id in preferred_errata_ids:
                row = by_id.get(error_id)
                if row and row.id not in seen:
                    ordered.append(row)
                    seen.add(row.id)
        for row in ErrorMemoryService(self.db).due_error_records(user, limit=limit * 2):
            if row.id not in seen:
                ordered.append(row)
                seen.add(row.id)
            if len(ordered) >= limit:
                break
        return ordered[:limit]

    def _select_vocabulary(
        self,
        *,
        user: User,
        errata: list[UserError],
        preferred_vocabulary_ids: list[int] | None = None,
        preferred_vocabulary_source: str = "target",
        limit: int,
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        seen_word_ids: set[int] = set()

        native_language = (user.native_language or "").strip().lower()
        translation_order = [
            native_language[:2] if native_language else "",
            "de",
            "en",
            "fr",
        ]

        def add_item(item: dict[str, Any]) -> None:
            if len(selected) >= limit:
                return
            try:
                word_id = int(item.get("word_id"))
            except (TypeError, ValueError):
                return
            word = _compact_text(item.get("word"), max_length=80)
            if not word or word_id in seen_word_ids:
                return
            translations = item.get("translations") if isinstance(item.get("translations"), dict) else {}
            translation = ""
            for language in translation_order:
                if language:
                    translation = _compact_text(translations.get(language), max_length=90)
                    if translation:
                        break
            example_translation = item.get("example_translation")
            if example_translation is None:
                vocab_row = self.db.get(VocabularyWord, word_id)
                example_translation = vocab_row.example_translation if vocab_row else None
            selected.append(
                {
                    "word_id": word_id,
                    "word": word,
                    "translation": translation,
                    "bucket": item.get("bucket") or "due",
                    "scheduler": item.get("scheduler") or "fsrs",
                    "priority_score": item.get("priority_score") or 0,
                    "example_sentence": _compact_text(item.get("example_sentence"), max_length=180),
                    "example_translation": _compact_text(example_translation, max_length=180),
                }
            )
            seen_word_ids.add(word_id)

        preferred_word_ids = _dedupe_ints(preferred_vocabulary_ids or [])
        if preferred_word_ids:
            rows = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(preferred_word_ids)).all()
            by_id = {row.id: row for row in rows}
            missing_ids = [word_id for word_id in preferred_word_ids if word_id not in by_id]
            if missing_ids and preferred_vocabulary_source == "explicit":
                raise GraphicNovelTargetVocabularyError(missing_ids)
            for word_id in preferred_word_ids:
                word = by_id.get(word_id)
                if not word:
                    continue
                add_item(
                    {
                        "word_id": word.id,
                        "word": word.word,
                        "translations": {
                            "de": word.german_translation,
                            "en": word.english_translation,
                            "fr": word.french_translation,
                        },
                        "bucket": "target",
                        "scheduler": preferred_vocabulary_source,
                        "priority_score": 1.0,
                        "example_sentence": word.example_sentence,
                        "example_translation": word.example_translation,
                    }
                )

        linked_word_ids = _dedupe_ints([error.linked_word_id for error in errata if error.linked_word_id])
        if linked_word_ids:
            rows = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(linked_word_ids)).all()
            by_id = {row.id: row for row in rows}
            for word_id in linked_word_ids:
                word = by_id.get(word_id)
                if not word:
                    continue
                add_item(
                    {
                        "word_id": word.id,
                        "word": word.word,
                        "translations": {
                            "de": word.german_translation,
                            "en": word.english_translation,
                            "fr": word.french_translation,
                        },
                        "bucket": "erratum",
                        "scheduler": "linked_errata",
                        "priority_score": 1.0,
                        "example_sentence": word.example_sentence,
                        "example_translation": word.example_translation,
                    }
                )

        if len(selected) >= limit:
            return selected[:limit]

        recommendations = ProgressService(self.db).get_vocabulary_recommendations(
            user=user,
            limit=limit * 2,
            due_limit=max(1, min(limit, 2)),
            fragile_limit=max(0, min(limit, 1)),
            new_limit=max(0, limit - 3),
            direction="fr_to_de",
        )
        for item in recommendations.get("items") or []:
            add_item(item)
            if len(selected) >= limit:
                break
        return selected[:limit]

    def _select_concepts(
        self,
        *,
        user: User,
        errata: list[UserError],
        atelier_session: AtelierSession | None,
        mission: RealWorldMission | None,
        preferred_concept_ids: list[int] | None,
        limit: int,
    ) -> list[GrammarConcept]:
        concept_ids: list[int] = []
        if preferred_concept_ids:
            concept_ids.extend(int(item) for item in preferred_concept_ids if item)
        concept_ids.extend(int(error.concept_id) for error in errata if error.concept_id)
        if atelier_session:
            concept_ids.extend(int(item) for item in (atelier_session.selected_concept_ids or []) if item)
        if mission:
            concept_ids.extend(int(item) for item in (mission.selected_concept_ids or []) if item)

        ordered: list[GrammarConcept] = []
        seen: set[int] = set()
        if concept_ids:
            rows = (
                self.db.query(GrammarConcept)
                .filter(GrammarConcept.id.in_(concept_ids), GrammarConcept.active.is_(True))
                .all()
            )
            by_id = {row.id: row for row in rows}
            for concept_id in concept_ids:
                concept = by_id.get(concept_id)
                if concept and concept.id not in seen:
                    ordered.append(concept)
                    seen.add(concept.id)
                if len(ordered) >= limit:
                    return ordered
        fallback = (
            self.db.query(GrammarConcept)
            .filter(
                GrammarConcept.active.is_(True),
                GrammarConcept.external_id.isnot(None),
                GrammarConcept.external_id != "",
                ~GrammarConcept.id.in_(seen) if seen else True,
            )
            .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
            .limit(max(0, limit - len(ordered)))
            .all()
        )
        return [*ordered, *fallback][:limit]

    async def _source_snapshot(
        self,
        *,
        user: User,
        personal_item: PersonalInputItem | None,
        use_news: bool,
        refresh_news: bool = False,
    ) -> dict[str, Any]:
        if personal_item:
            return {
                "mode": "personal_input",
                "title": personal_item.title,
                "summary": personal_item.text[:420],
                "source": personal_item.source_name or "Personal input",
                "url": personal_item.source_url or "",
                "items": [
                    {
                        "title": personal_item.title,
                        "summary": personal_item.text[:420],
                        "source": personal_item.source_name or "Personal input",
                        "url": personal_item.source_url or "",
                    }
                ],
                "source_policy": "Personal input; used only as contextual inspiration.",
            }
        if use_news:
            interests = [item.strip() for item in (user.interests or "").split(",") if item.strip()]
            return await NewsService().fetch_feuilleton_daily_seed(interests=interests, refresh=refresh_news)
        return {
            "mode": "atelier_curated",
            "title": "A small Paris errand",
            "summary": "A fictional, France-flavoured scene built around the learner's due grammar and errata.",
            "source": "Atelier curated prompt",
            "url": "",
            "items": [],
            "source_policy": "Curated prompt; no live news source used.",
        }

    def _cache_key(
        self,
        *,
        user: User,
        concepts: list[GrammarConcept],
        errata: list[UserError],
        target_vocabulary_ids: list[int],
        source_snapshot: dict[str, Any],
        cadence: str,
        panel_count: int,
        story_quality: str,
        humor_style: str,
        experience_mode: str,
        render_mode: str,
        image_quality: str,
        public_figure_mode: str,
        serial_context: dict[str, Any] | None = None,
    ) -> str:
        source_item = ((source_snapshot.get("items") or [{}])[0] or {})
        payload = {
            "user_id": str(user.id),
            "date": date.today().isoformat(),
            "cadence": cadence,
            "panel_count": panel_count,
            "story_quality": story_quality,
            "humor_style": humor_style,
            "experience_mode": experience_mode,
            "render_mode": render_mode,
            "image_quality": image_quality,
            "public_figure_mode": public_figure_mode,
            "concept_ids": [concept.id for concept in concepts],
            "errata_ids": _ids(errata),
            "vocabulary_ids": target_vocabulary_ids,
            "source": {
                "mode": source_snapshot.get("mode"),
                "date": source_snapshot.get("date"),
                "seed_version": source_snapshot.get("seed_version"),
                "title": source_snapshot.get("title") or source_item.get("title"),
                "source": source_snapshot.get("source") or source_item.get("source"),
                "url": source_snapshot.get("url") or source_item.get("url"),
            },
            "prompt_version": GRAPHIC_NOVEL_PROMPT_VERSION,
            "reference_pack_version": COMEDY_REFERENCE_PACK_VERSION,
            "story_model": (
                settings.OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL
                if story_quality == "premium"
                else settings.OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL
            ),
            "image_model": settings.OPENAI_IMAGE_MODEL,
            "image_generation_mode": (
                "openai"
                if settings.GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED and settings.OPENAI_API_KEY
                else "local_fallback"
            ),
            "serial": {
                "thread_id": serial_context.get("thread_id"),
                "episode_index": serial_context.get("episode_index"),
                "state": serial_context.get("state"),
                "previous_locations": serial_context.get("previous_locations"),
            }
            if serial_context
            else None,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:64]


class GraphicNovelStoryGenerator:
    """Generate a plot-led Feuilleton script with validated overlay exercises."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.asset_service = AtelierAssetService(db)
        self.llm = _safe_llm()

    @staticmethod
    def _learner_level(user: User) -> str:
        raw_level = getattr(user, "current_level", None) or getattr(user, "proficiency_level", None) or "B1"
        if isinstance(raw_level, str):
            normalized = raw_level.strip()
            cefr = normalized.upper()
            if cefr in {"A1", "A2", "B1", "B2", "C1", "C2"}:
                return cefr
            return {
                "beginner": "A1",
                "elementary": "A2",
                "intermediate": "B1",
                "upper_intermediate": "B2",
                "upper-intermediate": "B2",
                "advanced": "C1",
            }.get(normalized.lower(), "B1")
        if isinstance(raw_level, int):
            return {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1"}.get(raw_level, "B1")
        return "B1"

    def build_script(
        self,
        *,
        user: User,
        concepts: list[GrammarConcept],
        errata: list[UserError],
        source_snapshot: dict[str, Any],
        panel_count: int | None = None,
        story_quality: str = "standard",
        humor_style: str = "satirical",
        experience_mode: str = "study",
        render_mode: str = "panels",
        image_quality: str | None = None,
        public_figure_mode: str = "named_context",
        target_vocabulary: list[dict[str, Any]] | None = None,
        serial_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_panel_count = _panel_count(panel_count)
        resolved_story_quality = _story_quality(story_quality)
        resolved_humor_style = _humor_style(humor_style)
        resolved_experience_mode = _experience_mode(experience_mode)
        resolved_render_mode = _render_mode(render_mode)
        resolved_image_quality = _image_quality(image_quality)
        resolved_public_figure_mode = _public_figure_mode(public_figure_mode)
        resolved_task_count = _task_count(resolved_panel_count, resolved_experience_mode)
        titles = [_concept_title(concept, self.asset_service) for concept in concepts]
        errata_labels = [error.display_label or error.error_pattern or "remembered mistake" for error in errata]
        target_summary = self._targets(concepts=concepts, errata=errata)
        source_title = (
            source_snapshot.get("title")
            or ((source_snapshot.get("items") or [{}])[0] or {}).get("title")
            or "A small Paris errand"
        )
        story_model = self._story_model(resolved_story_quality)
        if serial_context:
            raw_serial_script = self._serial_story_script(
                user=user,
                concepts=concepts,
                source_snapshot=source_snapshot,
                targets=target_summary,
                panel_count=resolved_panel_count,
                story_quality=resolved_story_quality,
                humor_style=resolved_humor_style,
                story_model=story_model,
                experience_mode=resolved_experience_mode,
                render_mode=resolved_render_mode,
                image_quality=resolved_image_quality,
                public_figure_mode=resolved_public_figure_mode,
                target_vocabulary=target_vocabulary or [],
                serial_context=serial_context,
            )
            serial_plan_source = raw_serial_script.get("plan_source", "template")
            script = self._normalize_script(
                script=raw_serial_script,
                source_snapshot=source_snapshot,
                concepts=concepts,
                targets=target_summary,
                target_vocabulary=target_vocabulary or [],
                panel_count=resolved_panel_count,
                story_quality=resolved_story_quality,
                humor_style=resolved_humor_style,
                story_model=story_model,
                experience_mode=resolved_experience_mode,
                render_mode=resolved_render_mode,
                image_quality=resolved_image_quality,
                public_figure_mode=resolved_public_figure_mode,
                story_cost=0.0,
            )
            validation_errors = self._validate_script(
                script=script,
                panel_count=resolved_panel_count,
                experience_mode=resolved_experience_mode,
                public_figure_mode=resolved_public_figure_mode,
                target_language=user.target_language,
                serial_context=serial_context,
            )
            generation = {
                "status": "serial_llm_script" if serial_plan_source == "llm" else "serial_deterministic_script",
                "model": story_model,
                "attempts": 0,
                "errors": validation_errors,
                "validation_errors": validation_errors,
                "fallback_used": serial_plan_source != "llm",
                "serial_context_used": True,
                "serial_plan_source": serial_plan_source,
                "prompt_variant": "serial_v2" if (serial_context or {}).get("episode_brief") else "serial",
                "prompt_version": GRAPHIC_NOVEL_PROMPT_VERSION,
                "reference_pack_version": COMEDY_REFERENCE_PACK_VERSION,
            }
            return {
                "version": GRAPHIC_NOVEL_PROMPT_VERSION,
                "title": script["title"],
                "brief": script["brief"],
                "source_title": source_title,
                "targets": target_summary,
                "target_vocabulary": target_vocabulary or [],
                "errata_labels": errata_labels,
                "panel_count": resolved_panel_count,
                "task_count": _task_count(resolved_panel_count, resolved_experience_mode),
                "story_quality": resolved_story_quality,
                "humor_style": resolved_humor_style,
                "experience_mode": resolved_experience_mode,
                "render_mode": resolved_render_mode,
                "image_quality": resolved_image_quality,
                "public_figure_mode": resolved_public_figure_mode,
                "visual_only_demo": bool(script.get("visual_only_demo")),
                "comedy_reference_pack_version": COMEDY_REFERENCE_PACK_VERSION,
                "visual_premise_candidates": script.get("visual_premise_candidates", []),
                "selected_visual_premise": script.get("selected_visual_premise", {}),
                "headline_mechanic": script.get("headline_mechanic", ""),
                "captions": script.get("captions", []),
                "generation_debug": generation,
                "satire_premise_candidates": script.get("satire_premise_candidates", []),
                "selected_comedy_premise": script.get("selected_comedy_premise", {}),
                "dialogue_register": script.get("dialogue_register", "native-like B2/C1"),
                "support_register": script.get("support_register", f"{self._learner_level(user)} learner scaffolding"),
                "glosses": script.get("glosses", []),
                "story_quality_score": script.get("story_quality_score", 0),
                "comedy_validation": script.get("comedy_validation", {}),
                "story_model": script.get("story_model") or story_model,
                "story_bible": script["story_bible"],
                "character_bible": script["character_bible"],
                "prop_bible": script.get("prop_bible", []),
                "comic_tone": script["comic_tone"],
                "source_usage": script["source_usage"],
                "quality_notes": script["quality_notes"],
                "story_validation": generation,
                "estimated_cost": script["estimated_cost"],
                "panels": script["panels"],
                "final_prompt": script["final_prompt"],
                "hook": script.get("hook") or {},
                "serial_context": script.get("serial_context") or serial_context,
                "location_id": script.get("location_id"),
                "model_policy": {
                    "image_model": settings.OPENAI_IMAGE_MODEL,
                    "image_quality": resolved_image_quality,
                    "render_mode": resolved_render_mode,
                    "text_is_html_overlay": True,
                },
            }
        script, generation = self._generate_story(
            user=user,
            concepts=concepts,
            errata=errata,
            source_snapshot=source_snapshot,
            targets=target_summary,
            panel_count=resolved_panel_count,
            story_quality=resolved_story_quality,
            humor_style=resolved_humor_style,
            story_model=story_model,
            experience_mode=resolved_experience_mode,
            render_mode=resolved_render_mode,
            image_quality=resolved_image_quality,
            public_figure_mode=resolved_public_figure_mode,
            target_vocabulary=target_vocabulary or [],
        )
        if script is None:
            raise GraphicNovelGenerationError(
                "Feuilleton generation failed",
                errors=generation.get("errors", []),
                metadata={
                    **generation,
                    "prompt_version": GRAPHIC_NOVEL_PROMPT_VERSION,
                    "reference_pack_version": COMEDY_REFERENCE_PACK_VERSION,
                },
            )
        generation["fallback_used"] = False

        return {
            "version": GRAPHIC_NOVEL_PROMPT_VERSION,
            "title": script["title"],
            "brief": script["brief"],
            "source_title": source_title,
            "targets": target_summary,
            "target_vocabulary": target_vocabulary or [],
            "errata_labels": errata_labels,
            "panel_count": resolved_panel_count,
            "task_count": resolved_task_count,
            "story_quality": resolved_story_quality,
            "humor_style": resolved_humor_style,
            "experience_mode": resolved_experience_mode,
            "render_mode": resolved_render_mode,
            "image_quality": resolved_image_quality,
            "public_figure_mode": resolved_public_figure_mode,
            "visual_only_demo": bool(script.get("visual_only_demo")),
            "comedy_reference_pack_version": COMEDY_REFERENCE_PACK_VERSION,
            "visual_premise_candidates": script.get("visual_premise_candidates", []),
            "selected_visual_premise": script.get("selected_visual_premise", {}),
            "headline_mechanic": script.get("headline_mechanic", ""),
            "captions": script.get("captions", []),
            "generation_debug": {
                **generation,
                "prompt_version": GRAPHIC_NOVEL_PROMPT_VERSION,
                "reference_pack_version": COMEDY_REFERENCE_PACK_VERSION,
            },
            "satire_premise_candidates": script.get("satire_premise_candidates", []),
            "selected_comedy_premise": script.get("selected_comedy_premise", {}),
            "dialogue_register": script.get("dialogue_register", "native-like B2/C1"),
            "support_register": script.get("support_register", f"{self._learner_level(user)} learner scaffolding"),
            "glosses": script.get("glosses", []),
            "story_quality_score": script.get("story_quality_score", 0),
            "comedy_validation": script.get("comedy_validation", {}),
            "story_model": script.get("story_model") or story_model,
            "story_bible": script["story_bible"],
            "character_bible": script["character_bible"],
            "prop_bible": script.get("prop_bible", []),
            "comic_tone": script["comic_tone"],
            "source_usage": script["source_usage"],
            "quality_notes": script["quality_notes"],
            "story_validation": generation,
            "estimated_cost": script["estimated_cost"],
            "panels": script["panels"],
            "final_prompt": script["final_prompt"],
            "model_policy": {
                "image_model": settings.OPENAI_IMAGE_MODEL,
                "image_quality": resolved_image_quality,
                "render_mode": resolved_render_mode,
                "text_is_html_overlay": True,
            },
        }

    def _targets(self, *, concepts: list[GrammarConcept], errata: list[UserError]) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []
        for concept in concepts[:3]:
            targets.append(
                {
                    "kind": "grammar",
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                    "label": _concept_title(concept, self.asset_service),
                    "target_count": 1,
                }
            )
        for error in errata[:2]:
            targets.append(
                {
                    "kind": error.review_mode or "erratum",
                    "error_id": str(error.id),
                    "concept_id": error.concept_id,
                    "label": f"Repair: {error.display_label or error.error_pattern or 'remembered mistake'}",
                    "target_count": 1,
                }
            )
        return targets

    def _story_model(self, story_quality: str) -> str:
        if story_quality == "premium":
            return settings.OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL
        return settings.OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL

    def _prompt_asset_text(self, filename: str) -> str:
        return _cached_prompt_asset_text(filename)

    def _vocabulary_context_anchors(self, target_vocabulary: list[dict[str, Any]]) -> list[dict[str, str]]:
        anchors: list[dict[str, str]] = []
        for item in target_vocabulary[:4]:
            word = _compact_text(item.get("word"), max_length=80)
            if not word:
                continue
            example_sentence = _compact_text(item.get("example_sentence"), max_length=180)
            translation = _compact_text(item.get("translation"), max_length=90)
            example_translation = _compact_text(item.get("example_translation") or translation, max_length=180)
            anchor = example_sentence or f"Quelqu'un doit utiliser naturellement {word} dans la suite de la scène."
            anchors.append(
                {
                    "word": word,
                    "meaning": translation,
                    "natural_context_anchor": anchor,
                    "anchor_translation": example_translation,
                    "task_use": "Ask for a fresh French sentence that uses this word in the comic situation.",
                }
            )
        return anchors

    def _comedy_reference_pack(self) -> dict[str, Any]:
        return {
            "version": COMEDY_REFERENCE_PACK_VERSION,
            "yaml": self._prompt_asset_text("style_pack_v2.yaml"),
            "purpose": "Style grounding only. Do not copy copyrighted text or named gags.",
            "style_cards": [
                {
                    "name": "deadpan bureaucracy",
                    "inspiration": "French satirical weekly register",
                    "mechanic": "An institution treats a tiny human inconvenience as a solemn administrative category.",
                    "synthetic_example": "The committee does not reject the plan; it appoints a subcommittee to define what counts as a plan.",
                },
                {
                    "name": "puppet-role satire",
                    "inspiration": "televised political puppet sketch rhythm",
                    "mechanic": "A public role is reduced to one stubborn verbal tic, repeated until the scene exposes the role.",
                    "synthetic_example": "The spokesperson answers every question with an official stamp, including whether the coffee is cold.",
                },
                {
                    "name": "visual absurdity without cruelty",
                    "inspiration": "French editorial cartoon logic",
                    "mechanic": "One ordinary object becomes visually over-important while people remain oddly polite about it.",
                    "synthetic_example": "A stamp pad occupies the ministerial chair because it has approved more things than anyone else.",
                },
                {
                    "name": "wordplay escalation",
                    "inspiration": "classic bande dessinée village logic",
                    "mechanic": "A phrase is taken literally, then physically staged, then resolved by a callback.",
                    "synthetic_example": "When someone says the situation is blocked, everyone starts looking for the key to the situation.",
                },
                {
                    "name": "social irritation",
                    "inspiration": "observational French comic irritation",
                    "mechanic": "The annoyance is mundane and recognizable; the joke is the honesty, not cruelty.",
                    "synthetic_example": "The only person who read the instructions is treated as the dangerous radical.",
                },
                {
                    "name": "polished topical framing",
                    "inspiration": "daily French topical sketch",
                    "mechanic": "A news premise is reframed as a precise everyday scene, then a callback lands the editorial point.",
                    "synthetic_example": "The national debate becomes a café loyalty card with too many conditions.",
                },
            ],
            "avoid": [
                "American-style punchline escalation without a dry premise",
                "translated-from-English idioms",
                "random quirky settings with no payoff",
                "making every panel a grammar demonstration",
                "flattening all French dialogue to learner language",
            ],
        }

    def _generate_story(
        self,
        *,
        user: User,
        concepts: list[GrammarConcept],
        errata: list[UserError],
        source_snapshot: dict[str, Any],
        targets: list[dict[str, Any]],
        panel_count: int,
        story_quality: str,
        humor_style: str,
        story_model: str,
        experience_mode: str,
        render_mode: str,
        image_quality: str,
        public_figure_mode: str,
        target_vocabulary: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        metadata: dict[str, Any] = {
            "status": "not_attempted",
            "model": story_model,
            "attempts": 0,
            "errors": [],
        }
        if not self.llm:
            if settings.GRAPHIC_NOVEL_DEMO_SCRIPT_ENABLED:
                demo_script = self._normalize_script(
                    script=self._demo_story_script(
                        user=user,
                        concepts=concepts,
                        source_snapshot=source_snapshot,
                        targets=targets,
                        panel_count=panel_count,
                        story_quality=story_quality,
                        humor_style=humor_style,
                        story_model=story_model,
                        experience_mode=experience_mode,
                        render_mode=render_mode,
                        image_quality=image_quality,
                        public_figure_mode=public_figure_mode,
                        target_vocabulary=target_vocabulary,
                    ),
                    source_snapshot=source_snapshot,
                    concepts=concepts,
                    targets=targets,
                    target_vocabulary=target_vocabulary,
                    panel_count=panel_count,
                    story_quality=story_quality,
                    humor_style=humor_style,
                    story_model=story_model,
                    experience_mode=experience_mode,
                    render_mode=render_mode,
                    image_quality=image_quality,
                    public_figure_mode=public_figure_mode,
                    story_cost=0.0,
                )
                validation_errors = self._validate_script(
                    script=demo_script,
                    panel_count=panel_count,
                    experience_mode=experience_mode,
                    public_figure_mode=public_figure_mode,
                    target_language=user.target_language,
                )
                metadata["status"] = "local_demo_script"
                metadata["errors"] = []
                metadata["demo_script_used"] = True
                metadata["validation_errors"] = validation_errors
                return demo_script, metadata
            metadata["status"] = "llm_disabled"
            metadata["errors"] = ["story_llm_unavailable"]
            return None, metadata

        standard_story_model = settings.OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL
        models_to_try = [story_model]
        if story_model != standard_story_model:
            models_to_try.append(standard_story_model)

        retry_errors: list[str] = []
        for attempt, model_to_try in enumerate(models_to_try, start=1):
            skeleton_result = self._llm_skeleton(
                user=user,
                concepts=concepts,
                errata=errata,
                source_snapshot=source_snapshot,
                targets=targets,
                panel_count=panel_count,
                story_quality=story_quality,
                humor_style=humor_style,
                story_model=model_to_try,
                experience_mode=experience_mode,
                render_mode=render_mode,
                image_quality=image_quality,
                public_figure_mode=public_figure_mode,
                target_vocabulary=target_vocabulary,
                retry_errors=retry_errors,
            )
            metadata["attempts"] = attempt
            if not skeleton_result:
                retry_errors = ["skeleton_model_returned_no_valid_json_or_provider_timeout"]
                metadata["errors"] = retry_errors
                metadata["fallback_model_used"] = bool(model_to_try != story_model)
                continue
            skeleton, skeleton_meta = skeleton_result
            skeleton_errors = self._validate_story_skeleton(skeleton=skeleton, panel_count=panel_count)
            if skeleton_errors:
                # These are craft/contract warnings, not a publication gate. Feed them
                # into the surface pass so the model can compensate, then persist the
                # warnings in generation_debug for inspection.
                retry_errors = skeleton_errors
                metadata.update(skeleton_meta)
                metadata["skeleton_validation_errors"] = skeleton_errors
                metadata["fallback_model_used"] = bool(model_to_try != story_model)

            surface_result = self._llm_surface(
                user=user,
                concepts=concepts,
                errata=errata,
                source_snapshot=source_snapshot,
                targets=targets,
                skeleton=skeleton,
                panel_count=panel_count,
                story_quality=story_quality,
                humor_style=humor_style,
                story_model=model_to_try,
                experience_mode=experience_mode,
                render_mode=render_mode,
                image_quality=image_quality,
                public_figure_mode=public_figure_mode,
                target_vocabulary=target_vocabulary,
                retry_errors=retry_errors,
            )
            if not surface_result:
                retry_errors = ["surface_model_returned_no_valid_json_or_provider_timeout"]
                metadata.update(skeleton_meta)
                metadata["errors"] = retry_errors
                metadata["fallback_model_used"] = bool(model_to_try != story_model)
                continue

            surface, surface_meta = surface_result
            script = {**surface, **{key: value for key, value in skeleton.items() if key not in surface}}
            script["story_skeleton"] = skeleton
            llm_meta = {
                **skeleton_meta,
                **surface_meta,
                "story_generation_usd": float(skeleton_meta.get("skeleton_generation_usd") or 0.0)
                + float(surface_meta.get("surface_generation_usd") or 0.0),
                "prompt_tokens": int(skeleton_meta.get("skeleton_prompt_tokens") or 0)
                + int(surface_meta.get("surface_prompt_tokens") or 0),
                "completion_tokens": int(skeleton_meta.get("skeleton_completion_tokens") or 0)
                + int(surface_meta.get("surface_completion_tokens") or 0),
            }
            metadata.update(llm_meta)
            metadata["requested_model"] = story_model
            metadata["fallback_model_used"] = bool(model_to_try != story_model)
            script = self._normalize_script(
                script=script,
                source_snapshot=source_snapshot,
                concepts=concepts,
                targets=targets,
                target_vocabulary=target_vocabulary,
                panel_count=panel_count,
                story_quality=story_quality,
                humor_style=humor_style,
                story_model=model_to_try,
                experience_mode=experience_mode,
                render_mode=render_mode,
                image_quality=image_quality,
                public_figure_mode=public_figure_mode,
                story_cost=float(llm_meta.get("story_generation_usd") or 0.0),
            )
            validation_errors = self._validate_script(
                script=script,
                panel_count=panel_count,
                experience_mode=experience_mode,
                public_figure_mode=public_figure_mode,
                target_language=user.target_language,
            )
            metadata["status"] = "accepted_with_notes" if validation_errors else "passed"
            metadata["errors"] = []
            metadata["validation_errors"] = validation_errors
            return script, metadata
        return None, metadata

    def _demo_story_script(
        self,
        *,
        user: User,
        concepts: list[GrammarConcept],
        source_snapshot: dict[str, Any],
        targets: list[dict[str, Any]],
        panel_count: int,
        story_quality: str,
        humor_style: str,
        story_model: str,
        experience_mode: str,
        render_mode: str,
        image_quality: str,
        public_figure_mode: str,
        target_vocabulary: list[dict[str, Any]],
    ) -> dict[str, Any]:
        source_title = str(
            source_snapshot.get("title")
            or ((source_snapshot.get("items") or [{}])[0] or {}).get("title")
            or "A small Paris errand"
        )
        panel_actions = [
            "A clerk places a red stamp on an empty counter while everyone waits.",
            "A messenger arrives with a folder that is smaller than the stamp.",
            "The queue reorganizes itself around the stamp as if it were a minister.",
            "A cafe table becomes an emergency desk for a single form.",
            "Two fictional officials measure the stamp with unnecessary seriousness.",
            "The stamp is carried outside and the queue quietly follows.",
            "The form is approved before anyone remembers the question.",
            "A passerby uses the stamp as a paperweight and the office applauds.",
        ]
        beat_sequence = [
            {
                "panel_index": index,
                "beat": f"A tiny city office treats one stamp as if it controls the whole agenda, step {index}.",
                "panel_action": panel_actions[(index - 1) % len(panel_actions)],
                "turn_type": "callback" if index == panel_count else "escalation",
                "action_change": "The prop gains a little more social power.",
            }
            for index in range(1, panel_count + 1)
        ]
        selected_visual_premise = {
            "angle": "One tiny object becomes institutionally over-important.",
            "mechanic": "A routine French errand is slowed down because everyone obeys a stamp instead of the actual problem.",
            "headline_mechanic": f"Fictionalized from: {source_title}",
            "anchor_object": "red approval stamp",
            "domain": "a fictional French municipal counter and nearby cafe",
            "why_it_matches_source": "The source becomes a small visual bureaucracy joke without depicting real people.",
            "beat_sequence": beat_sequence,
            "score_0_10": 7.6,
        }
        visual_candidates = [
            selected_visual_premise,
            {
                **selected_visual_premise,
                "angle": "A queue behaves like a weather system.",
                "anchor_object": "number ticket machine",
                "score_0_10": 6.9,
            },
            {
                **selected_visual_premise,
                "angle": "A cafe receipt becomes official evidence.",
                "anchor_object": "receipt on a saucer",
                "score_0_10": 6.7,
            },
        ]
        panels: list[dict[str, Any]] = []
        for index in range(1, panel_count + 1):
            panels.append(
                {
                    "panel_index": index,
                    "title": f"Counter beat {index}",
                    "beat": beat_sequence[index - 1]["panel_action"],
                    "panel_action": beat_sequence[index - 1]["panel_action"],
                    "image_prompt_note": beat_sequence[index - 1]["action_change"],
                    "overlay_payload": {
                        "caption": {
                            "panel_index": index,
                            "fr": f"Le tampon prend son role tres au serieux, episode {index}.",
                            "en": f"The stamp takes its role very seriously, episode {index}.",
                        },
                        "bubbles": [
                            {
                                "speaker": "Voix",
                                "fr": "On attend le tampon.",
                                "en": "We are waiting for the stamp.",
                                "x": 12 + (index % 2) * 38,
                                "y": 14 + (index % 3) * 8,
                                "tone": "deadpan",
                            }
                        ],
                        "tasks": [],
                    },
                }
            )
        return {
            "title": "Feuilleton: Le tampon mobile",
            "brief": "A local visual QA edition for reading the mobile Feuilleton flow without a story model.",
            "headline_mechanic": selected_visual_premise["headline_mechanic"],
            "visual_premise_candidates": visual_candidates,
            "selected_visual_premise": selected_visual_premise,
            "human_characters": [
                {
                    "name": "Camille",
                    "role": "fictional clerk",
                    "visual_description": "calm municipal clerk in a dark jacket",
                    "comic_function": "treats the stamp as a serious colleague",
                }
            ],
            "prop_bible": [
                {
                    "name": "red approval stamp",
                    "visual_description": "oversized red stamp on cream paper",
                    "comic_function": "recurring object that receives too much respect",
                }
            ],
            "twist": "The office follows the stamp outside instead of finishing the form.",
            "payoff": "The stamp approves the wrong thing, and everyone is relieved anyway.",
            "source_usage": {
                "mode": str(source_snapshot.get("mode") or "curated"),
                "how_used": "Local deterministic demo, not a live publication.",
                "attribution": str(source_snapshot.get("source") or "Atelier QA"),
            },
            "captions": [
                {
                    "panel_index": panel["panel_index"],
                    "fr": panel["overlay_payload"]["caption"]["fr"],
                    "en": panel["overlay_payload"]["caption"]["en"],
                }
                for panel in panels
            ],
            "comic_tone": humor_style,
            "dialogue_register": "clear B1/B2 French",
            "support_register": f"{self._learner_level(user)} learner support",
            "glosses": [
                {"term": "le tampon", "meaning": "the stamp", "reason": "Recurring visual anchor."},
                {"term": "le comptoir", "meaning": "the counter", "reason": "Where the scene starts."},
            ],
            "visual_gag_quality": {
                "headline_link_visible": True,
                "one_absurd_image": True,
                "visual_escalation_clear": True,
                "captions_not_pedagogy": True,
                "exercises_extend_premise": False,
                "notes": ["Visual-only QA script."],
            },
            "panels": panels,
            "final_prompt": {
                "id": "",
                "task_type": "visual_only",
                "instruction": "",
                "prompt_body": "",
                "prompt_translation": "",
                "expected_features": [],
                "placeholder": "",
                "min_words": 0,
                "max_words": 0,
            },
            "quality_notes": ["Local visual demo script used for UI QA.", "Images still use the deterministic SVG fallback."],
            "visual_only_demo": True,
            "story_model": story_model,
            "story_quality": story_quality,
            "image_quality": image_quality,
            "render_mode": render_mode,
            "public_figure_mode": public_figure_mode,
        }

    def _serial_plan_response_format(self, *, panel_count: int) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "serial_episode_plan",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "episode_title": {"type": "string"},
                        "episode_brief": {"type": "string"},
                        "twist": {"type": "string"},
                        "panels": {
                            "type": "array",
                            "minItems": panel_count,
                            "maxItems": panel_count,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "title": {"type": "string"},
                                    "beat": {"type": "string"},
                                    "panel_action": {"type": "string"},
                                    "caption_fr": {"type": "string"},
                                    "caption_en": {"type": "string"},
                                },
                                "required": ["title", "beat", "panel_action", "caption_fr", "caption_en"],
                            },
                        },
                        "opening_cloze": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "prompt": {"type": "string"},
                                "prompt_translation": {"type": "string"},
                                "answer": {"type": "string"},
                            },
                            "required": ["prompt", "prompt_translation", "answer"],
                        },
                        "choice": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "option_a_next_beat": {"type": "string"},
                                "option_b_next_beat": {"type": "string"},
                            },
                            "required": ["option_a_next_beat", "option_b_next_beat"],
                        },
                        "hook": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "text": {"type": "string"},
                                "unresolved_question": {"type": "string"},
                                "teaser": {"type": "string"},
                            },
                            "required": ["text", "unresolved_question", "teaser"],
                        },
                    },
                    "required": [
                        "episode_title",
                        "episode_brief",
                        "twist",
                        "panels",
                        "opening_cloze",
                        "choice",
                        "hook",
                    ],
                },
            },
        }

    def _serial_episode_plan(
        self,
        *,
        user: User,
        world: dict[str, Any],
        state: dict[str, Any],
        hook_from_previous: dict[str, Any],
        location: dict[str, Any],
        cast: list[dict[str, Any]],
        news_title: str,
        targets: list[dict[str, Any]],
        target_vocabulary: list[dict[str, Any]],
        episode_brief: dict[str, Any] | None,
        panel_count: int,
        story_quality: str,
        humor_style: str,
        story_model: str,
        episode_index: int | None,
    ) -> dict[str, Any] | None:
        """Generate the narrative layer of a serial episode with the LLM.

        Returns None when the LLM is unavailable or the call fails, so the caller
        falls back to the deterministic template.
        """
        if not self.llm:
            return None
        setting = world.get("setting") if isinstance(world.get("setting"), dict) else {}
        guardrails = world.get("generation_guardrails") if isinstance(world.get("generation_guardrails"), dict) else {}
        system = (
            "You are the staff writer of a serial French-learning comic in the spirit of How I Met Your Mother, "
            "set in Paris with a fixed recurring cast. Write ONE new illustrated episode.\n"
            "HARD RULES:\n"
            "- The cast names, jobs, origins, and personalities are FIXED. Never rename or recast them.\n"
            "- CONTINUE the story from hook_from_previous when present; do not restart the premise each episode.\n"
            "- Reflect the serial `state` flags in what has changed since last time.\n"
            "- Route any daily news through Romy (the journalist); it is this week's texture, never the whole plot.\n"
            "- The episode is set at the provided location. Make the setting visible and specific.\n"
            "- Follow the provided episode_brief: structure, required_cast, A-plot, B-plot, news/choice flags, and hook guidance.\n"
            "- The FINAL panel must end on a genuine cliffhanger (an unresolved question), not a recap.\n"
            "- Captions are story, not pedagogy: never mention grammar, exercises, targets, or worksheets.\n"
            "- Comedy first, but land one beat of real feeling. French captions in natural French.\n"
            f"- Produce exactly {panel_count} panels."
        )
        payload = {
            "logline": world.get("logline"),
            "setting": {"city": setting.get("city"), "neighborhood": setting.get("neighborhood")},
            "location": {"id": location.get("id"), "name": location.get("name"), "description": location.get("description")},
            "cast": [
                {
                    "id": member.get("id"),
                    "name": member.get("name"),
                    "role": member.get("role"),
                    "personality": member.get("personality"),
                    "speech_pattern": member.get("speech_pattern"),
                }
                for member in cast
            ],
            "serial_state": state,
            "hook_from_previous": hook_from_previous or None,
            "episode_index": episode_index,
            "this_week_news": news_title,
            "learner_level": user.proficiency_level,
            "target_vocabulary": [
                {"word": item.get("word"), "meaning": item.get("translation")}
                for item in (target_vocabulary or [])[:4]
            ],
            "grammar_targets": [target.get("label") for target in (targets or [])[:4]],
            "episode_brief": episode_brief or {},
            "relationships": (episode_brief or {}).get("relationship_context") or {},
            "tentpole_reference": self._serial_tentpole_reference_text(episode_brief),
            "humor_style": humor_style,
            "guardrails": {
                "no_stereotypes": guardrails.get("no_stereotypes"),
                "warmth_rule": guardrails.get("warmth_rule"),
                "news_integration": guardrails.get("news_integration"),
            },
            "panel_plan": {
                "structure": (episode_brief or {}).get("structure") or "ensemble",
                "panel_1": "Open on the consequence of the previous mission / current state.",
                "middle": "Advance the A-plot stage; use the B-plot as texture only.",
                "choice_fork": "Include a choice fork only if episode_brief.include_choice_fork is true.",
                "news_panel": "Include a Romy news panel only if episode_brief.include_news_panel is true.",
                "final": (episode_brief or {}).get("hook_guidance") or "End on a cliffhanger that demands the next beat.",
            },
        }
        try:
            result = self.llm.generate_chat_completion(
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=system,
                response_format=self._serial_plan_response_format(panel_count=panel_count),
                temperature=0.85 if story_quality == "premium" else 0.7,
                max_tokens=2200,
                model=story_model,
            )
            parsed = json.loads(result.content)
            if isinstance(parsed, dict) and isinstance(parsed.get("panels"), list) and parsed.get("hook"):
                return parsed
        except (LLMProviderError, AttributeError, json.JSONDecodeError, ValueError) as exc:
            logger.info("Serial episode plan unavailable; using deterministic template", error=str(exc))
        return None

    def _serial_story_script(
        self,
        *,
        user: User,
        concepts: list[GrammarConcept],
        source_snapshot: dict[str, Any],
        targets: list[dict[str, Any]],
        panel_count: int,
        story_quality: str,
        humor_style: str,
        story_model: str,
        experience_mode: str,
        render_mode: str,
        image_quality: str,
        public_figure_mode: str,
        target_vocabulary: list[dict[str, Any]],
        serial_context: dict[str, Any],
    ) -> dict[str, Any]:
        world = serial_context.get("world_bible") if isinstance(serial_context.get("world_bible"), dict) else {}
        state = serial_context.get("state") if isinstance(serial_context.get("state"), dict) else {}
        episode_brief = serial_context.get("episode_brief") if isinstance(serial_context.get("episode_brief"), dict) else {}
        location = self._serial_location(
            world=world,
            previous_locations=serial_context.get("previous_locations") or [],
            episode_index=serial_context.get("episode_index"),
        )
        if episode_brief.get("location_id"):
            planned_location = self._serial_location_by_id(world=world, location_id=str(episode_brief.get("location_id")))
            if planned_location:
                location = planned_location
        visual_design = world.get("visual_design") if isinstance(world.get("visual_design"), dict) else {}
        location_designs = visual_design.get("locations") if isinstance(visual_design.get("locations"), dict) else {}
        location_design = location_designs.get(str(location.get("id") or "")) if isinstance(location_designs, dict) else {}
        if isinstance(location_design, dict) and location_design:
            location_visual_description = self._serial_visual_description(location_design)
            location = {
                **location,
                "description": location_visual_description or location_design.get("canonical_descriptor") or location.get("description"),
                "visual_design": location_design,
            }
        location_id = str(location.get("id") or "le_mistral")
        location_name = str(location.get("name") or "Le Mistral")
        location_description = str(location.get("description") or "A warm corner cafe in Paris.")
        heating_fixed = state.get("heating_fixed") is True or state.get("heating_fixed") == "pending_tomorrow"
        trust = str(state.get("marchand_trust") or "neutral")
        news_title = (
            source_snapshot.get("title")
            or ((source_snapshot.get("items") or [{}])[0] or {}).get("title")
            or (serial_context.get("news_seed") or {}).get("title")
            or "la nouvelle du jour"
        )
        cast = self._serial_cast(world)
        required_cast = {str(item) for item in episode_brief.get("required_cast") or [] if str(item or "").strip()}
        if required_cast:
            chosen_cast = [item for item in cast if item.get("id") in required_cast]
        else:
            chosen_cast = [
                item
                for item in cast
                if item.get("id") in {"marin_leveque", "lila_bonnet", "romy_tremblay", "margaux_barman", "augustin_de_roncourt"}
            ]
        chosen_cast = chosen_cast or cast[:4]
        hook = self._serial_hook(state=state, location_name=location_name, heating_fixed=heating_fixed)
        warmth_line = (
            "Le message du propriétaire promet enfin une réparation; la pièce reste froide, mais la panique baisse."
            if heating_fixed
            else "Le propriétaire n'a pas compris; la pièce reste froide et le téléphone pèse plus lourd."
        )
        final_beat = (
            "Romy waits at the door, half-smiling, and asks why your first night already sounds like a story."
            if heating_fixed
            else "Romy notices the unanswered phone and asks the question no one else dared ask."
        )
        branch_target = {
            "A": {
                "state_delta": {
                    "set": {"user.first_impression": "shy", "user.default_register": "vous"},
                    "reason": "The learner entered formally and cautiously.",
                    "source": {"type": "feuilleton_choice", "task_id": "panel_2_choice"},
                },
                "next_panel_beat": "The group gently teases the formal vous, but Marin waves you into the booth anyway.",
            },
            "B": {
                "state_delta": {
                    "set": {"user.first_impression": "game", "user.knows_tu_switch": "learning"},
                    "reason": "The learner entered warmly with tu.",
                    "source": {"type": "feuilleton_choice", "task_id": "panel_2_choice"},
                },
                "next_panel_beat": "Lila grins at the warm tu and decides you may be useful entertainment.",
            },
        }
        target_word = (target_vocabulary or [{}])[0] if target_vocabulary else {}
        target_word_text = str(target_word.get("word") or "réparer")
        target_word_translation = str(target_word.get("translation") or "to repair")
        task_count = _task_count(panel_count, experience_mode)
        episode_plan = self._serial_episode_plan(
            user=user,
            world=world,
            state=state,
            hook_from_previous=serial_context.get("hook_from_previous") or {},
            location=location,
            cast=chosen_cast,
            news_title=news_title,
            targets=targets,
            target_vocabulary=target_vocabulary,
            episode_brief=episode_brief,
            panel_count=panel_count,
            story_quality=story_quality,
            humor_style=humor_style,
            story_model=story_model,
            episode_index=serial_context.get("episode_index"),
        )
        try:
            current_episode_index = int(serial_context.get("episode_index"))
        except (TypeError, ValueError):
            current_episode_index = 0
        if not episode_plan and current_episode_index >= 1:
            raise GraphicNovelGenerationError(
                "Serial story LLM unavailable",
                errors=["serial_story_llm_unavailable"],
                metadata={
                    "episode_index": current_episode_index,
                    "thread_id": serial_context.get("thread_id"),
                    "episode_brief": episode_brief,
                },
            )
        plan_source = "llm" if episode_plan else "template"
        title_default = "Feuilleton: Le Mistral, minuit" if location_id == "le_mistral" else f"Feuilleton: {location_name}"
        brief_default = "A serial episode that dramatizes the previous mission consequence and ends on a cliffhanger."
        twist_default = "The practical radiator problem turns into an accidental doorway into a friend group."
        episode_title = _compact_text((episode_plan or {}).get("episode_title"), max_length=120) or title_default
        episode_brief_text = _compact_text((episode_plan or {}).get("episode_brief"), max_length=400) or brief_default
        episode_twist = _compact_text((episode_plan or {}).get("twist"), max_length=400) or twist_default
        if episode_plan:
            plan_hook = episode_plan.get("hook") if isinstance(episode_plan.get("hook"), dict) else {}
            hook = {
                "text": _compact_text(plan_hook.get("text"), max_length=400) or hook.get("text", ""),
                "unresolved_question": _compact_text(plan_hook.get("unresolved_question"), max_length=300)
                or hook.get("unresolved_question", ""),
                "teaser": _compact_text(plan_hook.get("teaser"), max_length=200) or hook.get("teaser", ""),
                "next_beat_kind": episode_brief.get("next_beat_kind") or "mission",
            }
            plan_choice = episode_plan.get("choice") if isinstance(episode_plan.get("choice"), dict) else {}
            if _compact_text(plan_choice.get("option_a_next_beat")):
                branch_target["A"]["next_panel_beat"] = _compact_text(plan_choice.get("option_a_next_beat"), max_length=500)
            if _compact_text(plan_choice.get("option_b_next_beat")):
                branch_target["B"]["next_panel_beat"] = _compact_text(plan_choice.get("option_b_next_beat"), max_length=500)
        is_home_base = location_id == "le_mistral"
        arrival_title = "The door of Le Mistral" if is_home_base else f"Arrival at {location_name}"
        arrival_beat = (
            f"Rain pushes the newcomer toward {location_name}, where warm light cuts across the pavement."
            if is_home_base
            else f"The thread pulls the newcomer toward {location_name}, where Paris looks like a different problem."
        )
        group_title = "The booth" if is_home_base else "The familiar faces"
        group_beat = (
            "Marin waves you into the booth while Lila sizes up the newcomer like a project she already owns."
            if is_home_base
            else f"Marin and Lila turn {location_name} into a temporary headquarters, and the newcomer gets folded into the plan."
        )
        group_action = (
            "A booth full of recurring friends opens one seat without making a speech about it."
            if is_home_base
            else f"The recurring friends cluster around one decisive corner of {location_name}, making room without ceremony."
        )
        warmth_beat = (
            f"Margaux sets down a hot drink; even with Marchand trust at {trust}, the booth has already made room."
            if is_home_base
            else f"A small kindness at {location_name} lands at exactly the right moment; even with Marchand trust at {trust}, the group has already made room."
        )
        warmth_action = (
            "A bartender slides one extra cup into the group rhythm as if it had always belonged there."
            if is_home_base
            else "One practical gesture makes the location feel briefly like a home base."
        )
        panel_templates = [
            {
                "title": "The cold flat",
                "beat": warmth_line,
                "panel_action": "The newcomer stands in a coat beside a silent radiator while the phone glows with the landlord thread.",
                "caption_fr": "Première nuit à Paris. Le radiateur décide de garder le silence.",
                "caption_en": "First night in Paris. The radiator chooses silence.",
                "tasks": [
                    {
                        "id": "panel_1_cloze",
                        "task_type": "cloze",
                        "label": "Radiator phrase",
                        "instruction": "Complete the practical phrase.",
                        "prompt": "Le radiateur est _____.",
                        "prompt_translation": "The radiator is broken.",
                        "expected_answer": "en panne",
                        "accepted_answers": ["en panne"],
                        "options": [],
                        "expected_features": [],
                        "placeholder": "en panne",
                        "scene_function": "Names the practical problem before the protagonist leaves the flat.",
                        "feedback_context": "The phrase en panne is the useful way to say an object is out of order.",
                    }
                ],
            },
            {
                "title": arrival_title,
                "beat": arrival_beat,
                "panel_action": f"The door opens onto {location_description}",
                "caption_fr": "En bas, il y a du bruit. Donc peut-être une solution.",
                "caption_en": "Downstairs there is noise. So maybe there is a solution.",
                "tasks": [
                    {
                        "id": "panel_2_choice",
                        "task_type": "choice",
                        "label": "How do you enter?",
                        "instruction": "Choose the line that sets your first impression.",
                        "prompt": "Tu entres et tu dis :",
                        "prompt_translation": "You go in and say:",
                        "expected_answer": "B",
                        "accepted_answers": ["B", "Salut, c'est encore ouvert ?"],
                        "options": ["A", "B"],
                        "expected_features": [],
                        "placeholder": "",
                        "scene_function": "Turns the entrance into a bounded branch about tu/vous and confidence.",
                        "feedback_context": "Both options are plausible; the choice changes how the next panel treats you.",
                        "branch_target": branch_target,
                    }
                ],
            },
            {
                "title": group_title,
                "beat": group_beat,
                "panel_action": group_action,
                "caption_fr": "Tu ne connais personne. Eux, visiblement, ont déjà une opinion.",
                "caption_en": "You know no one. They apparently already have an opinion.",
                "tasks": [
                    {
                        "id": "panel_3_intro",
                        "task_type": "short_sentence",
                        "label": "Introduce yourself",
                        "instruction": "Write one French sentence introducing who you are and that you just arrived.",
                        "prompt": "Présente-toi au groupe.",
                        "prompt_translation": "Introduce yourself to the group.",
                        "expected_answer": "",
                        "accepted_answers": [],
                        "options": [],
                        "expected_features": ["present tense", "arriver / emménager", "self-introduction"],
                        "placeholder": "Je viens d'arriver...",
                        "scene_function": "Lets the protagonist earn the seat through a small real line.",
                        "feedback_context": "The sentence should sound like a first meeting, not a grammar drill.",
                    }
                ],
            },
            {
                "title": "Romy's screen",
                "beat": f"Romy points at a newsroom clip about {news_title}; the daily news becomes the group's weather, not the whole plot.",
                "panel_action": "Romy, half journalist and half reluctant friend, turns a news alert into cafe argument fuel.",
                "caption_fr": "Romy appelle ça une petite info. Personne ne la croit.",
                "caption_en": "Romy calls it a small story. No one believes her.",
                "tasks": [
                    {
                        "id": "panel_4_news",
                        "task_type": "short_sentence",
                        "label": "News reaction",
                        "instruction": f"Use {target_word_text} naturally in a short French reaction.",
                        "prompt": "Réagis à l'info de Romy en une phrase.",
                        "prompt_translation": "React to Romy's news item in one sentence.",
                        "expected_answer": "",
                        "accepted_answers": [],
                        "options": [],
                        "expected_features": [f"use {target_word_text}", "one clear consequence"],
                        "placeholder": f"Cette info peut {target_word_text}...",
                        "scene_function": "Keeps the news engine diegetic through Romy while practicing target vocabulary.",
                        "feedback_context": f"The target word means {target_word_translation}; use it as part of the cafe argument.",
                        "vocabulary_task": True,
                        "target_word_id": target_word.get("word_id"),
                        "target_word": target_word_text,
                        "target_translation": target_word_translation,
                    }
                ],
            },
            {
                "title": "The warmth beat",
                "beat": warmth_beat,
                "panel_action": warmth_action,
                "caption_fr": "Tu n'as pas encore leurs numéros. Mais tu as déjà une tasse.",
                "caption_en": "You do not have their numbers yet. But you already have a cup.",
                "tasks": [],
            },
            {
                "title": "Romy's question",
                "beat": final_beat,
                "panel_action": "At closing time Romy turns back under the awning, asking the question that makes tomorrow necessary.",
                "caption_fr": "La porte se ferme. L'histoire, elle, refuse poliment.",
                "caption_en": "The door closes. The story politely refuses.",
                "tasks": [
                    {
                        "id": "panel_6_hook_line",
                        "task_type": "short_sentence",
                        "label": "Keep the thread alive",
                        "instruction": "Write one French line that gives you a reason to see them again.",
                        "prompt": "Trouve un prétexte pour revoir le groupe.",
                        "prompt_translation": "Find a reason to see the group again.",
                        "expected_answer": "",
                        "accepted_answers": [],
                        "options": [],
                        "expected_features": ["clear invitation", "tu register", "concrete next step"],
                        "placeholder": "On pourrait...",
                        "scene_function": "Seeds the next mission from the cliffhanger instead of ending in recap.",
                        "feedback_context": "The line should be warm and concrete enough to become tomorrow's message.",
                    }
                ],
                "hook": hook,
            },
        ]
        if episode_brief:
            if not episode_brief.get("include_choice_fork") and len(panel_templates) > 1:
                panel_templates[1]["tasks"] = []
                panel_templates[1]["beat"] = _compact_text(
                    (episode_brief.get("a_plot") or {}).get("stage_summary"),
                    max_length=400,
                ) or panel_templates[1]["beat"]
                panel_templates[1]["panel_action"] = "A planner-selected story beat advances without a visible choice fork."
            if not episode_brief.get("include_news_panel") and len(panel_templates) > 3:
                b_plot = episode_brief.get("b_plot") if isinstance(episode_brief.get("b_plot"), dict) else {}
                panel_templates[3]["title"] = "The B-plot"
                panel_templates[3]["beat"] = _compact_text(b_plot.get("seed"), max_length=400) or panel_templates[3]["beat"]
                panel_templates[3]["panel_action"] = "A small everyday complication adds texture without becoming the plot."
                panel_templates[3]["caption_fr"] = "Le détour avait l'air petit. C'était rarement bon signe."
                panel_templates[3]["caption_en"] = "The detour looked small. That was rarely a good sign."
                panel_templates[3]["tasks"] = []
        if episode_plan:
            plan_panels = episode_plan.get("panels") if isinstance(episode_plan.get("panels"), list) else []
            for idx, template in enumerate(panel_templates):
                plan_panel = plan_panels[idx] if idx < len(plan_panels) and isinstance(plan_panels[idx], dict) else {}
                if not plan_panel:
                    continue
                template["title"] = _compact_text(plan_panel.get("title"), max_length=120) or template["title"]
                template["beat"] = _compact_text(plan_panel.get("beat"), max_length=400) or template["beat"]
                template["panel_action"] = _compact_text(plan_panel.get("panel_action"), max_length=400) or template["panel_action"]
                template["caption_fr"] = _compact_text(plan_panel.get("caption_fr"), max_length=240) or template["caption_fr"]
                template["caption_en"] = _compact_text(plan_panel.get("caption_en"), max_length=240) or template["caption_en"]
            opening_cloze = episode_plan.get("opening_cloze") if isinstance(episode_plan.get("opening_cloze"), dict) else {}
            if opening_cloze and panel_templates and panel_templates[0]["tasks"]:
                cloze_task = panel_templates[0]["tasks"][0]
                cloze_prompt = _compact_text(opening_cloze.get("prompt"), max_length=240)
                cloze_answer = _compact_text(opening_cloze.get("answer"), max_length=120)
                cloze_translation = _compact_text(opening_cloze.get("prompt_translation"), max_length=240)
                if cloze_prompt and cloze_answer:
                    cloze_task["prompt"] = cloze_prompt
                    cloze_task["prompt_translation"] = cloze_translation or cloze_task["prompt_translation"]
                    cloze_task["expected_answer"] = cloze_answer
                    cloze_task["accepted_answers"] = [cloze_answer]
                    cloze_task["placeholder"] = cloze_answer
        panels: list[dict[str, Any]] = []
        task_budget = task_count
        for index in range(1, panel_count + 1):
            template = panel_templates[(index - 1) % len(panel_templates)]
            tasks = template["tasks"] if task_budget > 0 else []
            if tasks:
                tasks = tasks[: max(0, task_budget)]
                task_budget -= len(tasks)
            panel = {
                "panel_index": index,
                "title": template["title"],
                "beat": template["beat"],
                "panel_action": template["panel_action"],
                "image_prompt_note": "Serial state-conditioned consequence beat.",
                "prop_focus": "radiator" if index == 1 else ("phone" if index == panel_count else "coffee cup"),
                "overlay_payload": {
                    "caption": {
                        "panel_index": index,
                        "fr": template["caption_fr"],
                        "en": template["caption_en"],
                    },
                    "bubbles": self._serial_bubbles(index=index, cast=chosen_cast),
                    "tasks": tasks,
                },
            }
            if template.get("hook"):
                panel["hook"] = template["hook"]
            panels.append(panel)
        visual_design_status = str((world.get("visual_design") or {}).get("status") or "text seeds")
        beat_sequence = [
            {
                "panel_index": panel["panel_index"],
                "beat": panel["beat"],
                "panel_action": panel["panel_action"],
                "turn_type": "cliffhanger" if panel["panel_index"] == panel_count else "state_consequence",
                "action_change": panel["image_prompt_note"],
            }
            for panel in panels
        ]
        selected_visual_premise = {
            "angle": "Persistent friend-group serial consequence.",
            "mechanic": "The learner's real-world French changes the next social beat in Paris.",
            "headline_mechanic": f"Romy routes this week's town texture through: {news_title}",
            "anchor_object": "glowing phone and hot drink",
            "domain": location_description,
            "why_it_matches_source": "News remains a diegetic texture through Romy while the plot follows learner state.",
            "beat_sequence": beat_sequence,
            "score_0_10": 8.4,
        }
        visual_candidates = [
            selected_visual_premise,
            {**selected_visual_premise, "angle": "The radiator problem becomes a found-family entrance.", "score_0_10": 8.0},
            {**selected_visual_premise, "angle": "Romy's news item reframes the newcomer as tomorrow's question.", "score_0_10": 7.8},
        ]
        return {
            "title": episode_title,
            "brief": episode_brief_text,
            "headline_mechanic": selected_visual_premise["headline_mechanic"],
            "visual_premise_candidates": visual_candidates,
            "selected_visual_premise": selected_visual_premise,
            "human_characters": chosen_cast,
            "prop_bible": [
                {
                    "name": "phone with landlord thread",
                    "visual_description": "a small glowing phone, never with readable text",
                    "comic_function": "shows what the learner's Mission changed",
                },
                {
                    "name": "hot drink",
                    "visual_description": "a plain white cup with amber warmth",
                    "comic_function": "marks the found-family warmth beat",
                },
            ],
            "twist": episode_twist,
            "payoff": hook["text"],
            "source_usage": {
                "mode": str(source_snapshot.get("mode") or "serial_news_seed"),
                "how_used": "Romy brings the daily news seed into town texture; it is not the whole premise.",
                "attribution": str(source_snapshot.get("source") or ((source_snapshot.get("items") or [{}])[0] or {}).get("source") or "Atelier serial seed"),
            },
            "captions": [
                {
                    "panel_index": panel["panel_index"],
                    "fr": panel["overlay_payload"]["caption"]["fr"],
                    "en": panel["overlay_payload"]["caption"]["en"],
                }
                for panel in panels
            ],
            "comic_tone": humor_style,
            "dialogue_register": "persistent cast, natural French, tu/vous tension as story content",
            "support_register": f"{self._learner_level(user)} learner support",
            "glosses": [
                {"term": "en panne", "meaning": "broken / out of order", "reason": "The radiator problem."},
                {"term": "un prétexte", "meaning": "an excuse / reason", "reason": "The next mission seed."},
            ],
            "visual_gag_quality": {
                "headline_link_visible": True,
                "one_absurd_image": True,
                "visual_escalation_clear": True,
                "captions_not_pedagogy": True,
                "exercises_extend_premise": True,
                "notes": [f"Serial prompt variant; visual design source: {visual_design_status}"],
            },
            "panels": panels,
            "final_prompt": {
                "id": "serial_final_line",
                "task_type": "short_sentence",
                "instruction": "Write a warm tu-register line for the next message.",
                "prompt_body": "Propose un prétexte concret pour revoir le groupe demain.",
                "prompt_translation": "Suggest a concrete reason to see the group again tomorrow.",
                "expected_features": ["tu register", "invitation", "concrete time or place"],
                "placeholder": "On se retrouve...",
                "min_words": 8,
                "max_words": 28,
            },
            "quality_notes": ["Serial state and world bible were applied.", "Final panel ends on a hook; recap is secondary."],
            "visual_only_demo": False,
            "story_model": story_model,
            "story_quality": story_quality,
            "image_quality": image_quality,
            "render_mode": render_mode,
            "public_figure_mode": public_figure_mode,
            "hook": hook,
            "location_id": location_id,
            "serial_context": serial_context,
            "plan_source": plan_source,
        }

    def _serial_location(
        self,
        *,
        world: dict[str, Any],
        previous_locations: list[Any],
        episode_index: Any = None,
    ) -> dict[str, Any]:
        setting = world.get("setting") if isinstance(world.get("setting"), dict) else {}
        locations = setting.get("recurring_locations") if isinstance(setting.get("recurring_locations"), list) else []
        locations = [item for item in locations if isinstance(item, dict) and item.get("id")]
        if not locations:
            return {"id": "le_mistral", "name": "Le Mistral", "description": "A warm corner cafe in Paris."}
        location_ids = [str(item.get("id")) for item in locations]
        by_id = {str(item.get("id")): item for item in locations}
        previous_ids = [str(item).strip() for item in previous_locations if str(item or "").strip()]
        last_location = previous_ids[-1] if previous_ids else ""
        usage = {location_id: previous_ids.count(location_id) for location_id in location_ids}
        try:
            episode_number = int(episode_index)
        except (TypeError, ValueError):
            episode_number = 0

        opener_anchor = by_id.get("le_mistral")
        if (
            opener_anchor
            and "le_mistral" not in previous_ids
            and last_location != "le_mistral"
            and (episode_number <= 1 or last_location == "user_apartment")
        ):
            return opener_anchor

        candidates = [item for item in locations if str(item.get("id")) != last_location]
        if not candidates:
            return locations[0]

        def rotation_key(location: dict[str, Any]) -> tuple[int, int, int]:
            location_id = str(location.get("id"))
            home_base_penalty = 1 if location_id == "le_mistral" and usage.get(location_id, 0) else 0
            return (
                usage.get(location_id, 0) + home_base_penalty,
                home_base_penalty,
                location_ids.index(location_id),
            )

        return min(candidates, key=rotation_key)

    @staticmethod
    def _serial_tentpole_reference_text(episode_brief: dict[str, Any] | None) -> str:
        reference = (episode_brief or {}).get("tentpole_reference")
        if not reference:
            return ""
        path = Path(__file__).resolve().parents[2] / str(reference)
        try:
            return path.read_text(encoding="utf-8")[:4000]
        except OSError:
            logger.warning("Serial tentpole reference missing", path=str(path))
            return ""

    @staticmethod
    def _serial_location_by_id(*, world: dict[str, Any], location_id: str) -> dict[str, Any] | None:
        setting = world.get("setting") if isinstance(world.get("setting"), dict) else {}
        for location in setting.get("recurring_locations") or []:
            if isinstance(location, dict) and str(location.get("id")) == location_id:
                return location
        return None

    def _serial_cast(self, world: dict[str, Any]) -> list[dict[str, Any]]:
        cast = world.get("cast") if isinstance(world.get("cast"), list) else []
        visual_design = ((world.get("visual_design") or {}).get("characters") or {}) if isinstance(world.get("visual_design"), dict) else {}
        characters: list[dict[str, Any]] = []
        for member in cast:
            if not isinstance(member, dict):
                continue
            member_id = str(member.get("id") or "")
            design = visual_design.get(member_id) if isinstance(visual_design, dict) else {}
            design_text = self._serial_visual_description(design)
            characters.append(
                {
                    "id": member_id,
                    "name": str(member.get("name") or member_id or "Ami"),
                    "role": str(member.get("role") or "recurring cast"),
                    "visual_description": design_text or str(member.get("personality") or member.get("speech_pattern") or "consistent recurring cast member"),
                    "comic_function": str(member.get("dynamic_with_user") or member.get("teaches") or member.get("role") or "serial cast member"),
                    "visual_design": design or {},
                }
            )
        return characters or [
            {
                "id": "margaux",
                "name": "Margaux",
                "role": "bartender",
                "visual_description": "unhurried bartender, apron, warm amber accent",
                "comic_function": "quiet oracle of the cafe",
            }
        ]

    @staticmethod
    def _serial_visual_description(design: Any) -> str:
        if not isinstance(design, dict):
            return ""
        canonical = _compact_text(design.get("canonical_descriptor"), max_length=500)
        parts = [canonical] if canonical else []
        accent = design.get("accent_colour") or design.get("accent_color")
        token = design.get("ui_token")
        if accent:
            parts.append(f"accent colour {accent}")
        if token:
            parts.append(f"UI token {token}")
        expressions = design.get("expressions") if isinstance(design.get("expressions"), dict) else {}
        if expressions:
            parts.append("expressions: " + ", ".join(str(key) for key in list(expressions.keys())[:6]))
        references = design.get("reference_images") if isinstance(design.get("reference_images"), list) else []
        if references:
            parts.append("reference images: " + ", ".join(str(item) for item in references[:3]))
        style_ref = _compact_text(design.get("style_ref"), max_length=240)
        if style_ref:
            parts.append(f"style reference: {style_ref}")
        return "; ".join(part for part in parts if part)

    @staticmethod
    def _serial_hook(*, state: dict[str, Any], location_name: str, heating_fixed: bool) -> dict[str, Any]:
        if heating_fixed:
            text = (
                "La porte se referme. Demain, quelqu'un viendra réparer le radiateur; ce soir, "
                f"{location_name} vient de te donner un problème plus doux: comment revoir ces gens ?"
            )
        else:
            text = (
                "La porte se referme. Le radiateur est toujours froid, mais une autre question chauffe déjà: "
                "qui, dans ce groupe, va t'aider à survivre à demain ?"
            )
        return {
            "text": text,
            "unresolved_question": "How do you turn one accidental night into actual friends, and what was that look from Romy?",
            "next_beat_kind": "mission",
            "teaser": "Il te faut un prétexte. Et leurs numéros.",
            "state_snapshot": {"heating_fixed": state.get("heating_fixed"), "marchand_trust": state.get("marchand_trust")},
        }

    @staticmethod
    def _serial_bubbles(*, index: int, cast: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if index == 3 and cast:
            return [
                {
                    "speaker": str(cast[0].get("name") or "Marin")[:32],
                    "fr": "Viens, tu vas geler.",
                    "en": "Come on, you'll freeze.",
                    "x": 12,
                    "y": 14,
                    "tone": "warm",
                }
            ]
        if index == 4:
            return [
                {
                    "speaker": "Romy",
                    "fr": "C'est quoi la vraie histoire ?",
                    "en": "What's the real story?",
                    "x": 44,
                    "y": 12,
                    "tone": "dry",
                }
            ]
        return []

    def _llm_skeleton(
        self,
        *,
        user: User,
        concepts: list[GrammarConcept],
        errata: list[UserError],
        source_snapshot: dict[str, Any],
        targets: list[dict[str, Any]],
        panel_count: int,
        story_quality: str,
        humor_style: str,
        story_model: str,
        experience_mode: str,
        render_mode: str,
        image_quality: str,
        public_figure_mode: str,
        target_vocabulary: list[dict[str, Any]],
        retry_errors: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        system = (
            "You create only the structural skeleton for Atelier Feuilleton, a French-learning visual-gag strip. "
            "Do not write exercises yet. Do not write image prompts yet. "
            "Your job is to turn today's source mechanic into a visual premise: one behavior being satirized, one recurring anchor object, a flexible domain, and a six-step visual progression. "
            "A premise is not a tableau. Avoid complete room descriptions. The selected premise must be reusable across visually distinct panels. "
            "The final beat must be a turn: outside view, role inversion, time jump, object perspective, callback with a changed meaning, or a new observer who reframes the gag. "
            "Use public people only as source mechanics when allowed; do not ask images to depict real identifiable public figures."
        )
        payload = {
            "panel_count": panel_count,
            "experience_mode": experience_mode,
            "render_mode": render_mode,
            "image_quality": image_quality,
            "public_figure_mode": public_figure_mode,
            "story_quality": story_quality,
            "humor_style": humor_style,
            "writer_prompt_asset": self._prompt_asset_text("visual_gag_writer_v2.yaml"),
            "comedy_reference_pack": self._comedy_reference_pack(),
            "learner": {
                "target_language": user.target_language,
                "native_language": user.native_language,
                "level": self._learner_level(user),
                "interests": user.interests,
            },
            "source_snapshot": self._source_prompt(source_snapshot),
            "targets": targets,
            "target_vocabulary": target_vocabulary,
            "target_vocabulary_context": self._vocabulary_context_anchors(target_vocabulary),
            "concepts": [self._concept_prompt(concept) for concept in concepts],
            "errata": [self._erratum_prompt(error) for error in errata],
            "retry_errors": retry_errors,
            "rules": [
                "Return exactly three visual premise candidates.",
                "Each candidate must include a mechanic, anchor_object, domain, headline_mechanic, why_it_matches_source, and a panel beat sequence.",
                "The selected premise must visibly enact the headline mechanic. If it could fit any headline, it is wrong.",
                "The anchor_object is one recurring prop or symbol, not a whole room and not a person.",
                "Human characters belong in human_characters. Recurring objects belong in prop_bible. Do not put posters, chairs, calendars, phones, umbrellas, cups, or machines in human_characters.",
                "Panel beats must be visual actions, not lesson notes. Never mention grammar, targets, exercises, pedagogy, or worksheets.",
                "If target_vocabulary is provided, treat the example sentences as natural context anchors for the scene; do not turn the words into a vocabulary list.",
                "Panel 6 must be a turn, not quantitative accumulation.",
                "Provide non-empty twist and payoff summaries so downstream code can detect whether the strip has a change of angle.",
            ],
        }
        try:
            result = self.llm.generate_chat_completion(
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=system,
                response_format=self._skeleton_response_format(panel_count=panel_count),
                temperature=0.9 if story_quality == "premium" else 0.75,
                max_tokens=2600,
                model=story_model,
            )
            return json.loads(result.content), {
                "provider": result.provider,
                "model": result.model,
                "skeleton_prompt_tokens": result.prompt_tokens,
                "skeleton_completion_tokens": result.completion_tokens,
                "skeleton_generation_usd": result.cost,
                "skeleton_system_prompt": system,
                "skeleton_user_payload": payload,
            }
        except (LLMProviderError, AttributeError, json.JSONDecodeError, ValueError) as exc:
            logger.info("Feuilleton skeleton generation unavailable", error=str(exc))
            return None

    def _llm_surface(
        self,
        *,
        user: User,
        concepts: list[GrammarConcept],
        errata: list[UserError],
        source_snapshot: dict[str, Any],
        targets: list[dict[str, Any]],
        skeleton: dict[str, Any],
        panel_count: int,
        story_quality: str,
        humor_style: str,
        story_model: str,
        experience_mode: str,
        render_mode: str,
        image_quality: str,
        public_figure_mode: str,
        target_vocabulary: list[dict[str, Any]],
        retry_errors: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        task_count = _task_count(panel_count, experience_mode)
        system = (
            "You write the surface layer for Atelier Feuilleton from an already validated visual-gag skeleton. "
            "Write the French captions first, then write the overlay exercises from follow-up beats that extend those captions. "
            "Do not invent unrelated exercise sentences. Every task must add a new comic beat that could happen after its panel. "
            "All expected answers, accepted answers, and multiple-choice options must be in French when the target language is French. "
            "Multiple-choice distractors must be plausible valid French forms; do not include obviously impossible strings just to make the answer easy. "
            "French captions may be native-like and deadpan. English text is translation/support only. "
            "Closed cloze/choice task instructions must not reveal the target answer or target form. "
            "Open short-sentence task instructions must name the exact grammar relation if the correction will require one. "
            "Every task prompt needs a concise English translation field. "
            "Create 0-2 short French speech bubbles per panel when they sharpen the visual gag. "
            "Speech bubbles are HTML overlays, not image text; keep them compact and place them with percentage x/y coordinates."
        )
        payload = {
            "panel_count": panel_count,
            "overlay_task_count": task_count,
            "experience_mode": experience_mode,
            "render_mode": render_mode,
            "image_quality": image_quality,
            "public_figure_mode": public_figure_mode,
            "story_quality": story_quality,
            "humor_style": humor_style,
            "learner": {
                "target_language": user.target_language,
                "native_language": user.native_language,
                "level": self._learner_level(user),
            },
            "source_snapshot": self._source_prompt(source_snapshot),
            "skeleton": skeleton,
            "targets": targets,
            "target_vocabulary": target_vocabulary,
            "target_vocabulary_context": self._vocabulary_context_anchors(target_vocabulary),
            "concepts": [self._concept_prompt(concept) for concept in concepts],
            "errata": [self._erratum_prompt(error) for error in errata],
            "retry_errors": retry_errors,
            "rules": [
                f"Generate exactly {task_count} overlay tasks across the panels.",
                "At least one panel should remain pure visual/caption context with no exercise.",
                "Every task prompt must advance the strip with a fresh line or action; it must not copy a caption sentence.",
                "For cloze and choice tasks, provide a full French follow-up sentence or phrase and blank only the target form.",
                "If an instruction mentions a verb in parentheses, the prompt must actually include that verb in parentheses; otherwise do not mention parentheses.",
                "Each task must include prompt_translation: an English translation of the French exercise prompt.",
                "Every short_sentence task instruction must explicitly name the required grammar feature, such as si + present with future/imperative consequence.",
                "For choice tasks, every option must be grammatical French in some context.",
                "Do not use English as expected_answer or as a choice option for French tasks.",
                "No task may ask for an English sentence.",
                "When target_vocabulary is provided, create at least one short_sentence production task that asks for one selected word in a fresh French sentence.",
                "Use target_vocabulary_context example sentences as natural scene anchors and hints; do not present the target words as a memorization list.",
                "When target_vocabulary is provided, weave 1-3 of those French words into captions, bubbles, task prompts, or glosses where they sound natural.",
                "Do not force target vocabulary into every panel; context and rhythm still matter.",
                "Each panel may include 0-2 speech bubbles. Bubble fr text is French; bubble en text is a concise English support translation.",
                "Bubbles must not repeat the caption verbatim and should read like in-world speech, not lesson narration.",
                "Bubble coordinates are percentages within the image: x 8-76, y 8-58. Keep text short enough to fit.",
                "Final prompt instruction and prompt_body must be different: instruction states the grammar job; prompt_body gives the scene cue.",
                "Final prompt must include expected_features and a prompt_translation for its French scene cue.",
                "No field may say 'the learner' or 'the user'.",
            ],
        }
        try:
            result = self.llm.generate_chat_completion(
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=system,
                response_format=self._surface_response_format(panel_count=panel_count),
                temperature=0.82 if story_quality == "premium" else 0.68,
                max_tokens=3600,
                model=story_model,
            )
            return json.loads(result.content), {
                "provider": result.provider,
                "model": result.model,
                "surface_prompt_tokens": result.prompt_tokens,
                "surface_completion_tokens": result.completion_tokens,
                "surface_generation_usd": result.cost,
                "surface_system_prompt": system,
                "surface_user_payload": payload,
            }
        except (LLMProviderError, AttributeError, json.JSONDecodeError, ValueError) as exc:
            logger.info("Feuilleton surface generation unavailable", error=str(exc))
            return None

    def _skeleton_response_format(self, *, panel_count: int) -> dict[str, Any]:
        beat_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "panel_index": {"type": "integer"},
                "beat": {"type": "string"},
                "panel_action": {"type": "string"},
                "turn_type": {"type": "string"},
                "action_change": {"type": "string"},
            },
            "required": ["panel_index", "beat", "panel_action", "turn_type", "action_change"],
        }
        visual_premise_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "angle": {"type": "string"},
                "mechanic": {"type": "string"},
                "headline_mechanic": {"type": "string"},
                "anchor_object": {"type": "string"},
                "domain": {"type": "string"},
                "why_it_matches_source": {"type": "string"},
                "beat_sequence": {
                    "type": "array",
                    "minItems": panel_count,
                    "maxItems": panel_count,
                    "items": beat_schema,
                },
                "score_0_10": {"type": "number"},
            },
            "required": [
                "angle",
                "mechanic",
                "headline_mechanic",
                "anchor_object",
                "domain",
                "why_it_matches_source",
                "beat_sequence",
                "score_0_10",
            ],
        }
        human_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "visual_description": {"type": "string"},
                "comic_function": {"type": "string"},
            },
            "required": ["name", "role", "visual_description", "comic_function"],
        }
        prop_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "visual_description": {"type": "string"},
                "comic_function": {"type": "string"},
            },
            "required": ["name", "visual_description", "comic_function"],
        }
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "feuilleton_visual_skeleton",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "brief": {"type": "string"},
                        "headline_mechanic": {"type": "string"},
                        "visual_premise_candidates": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": visual_premise_schema,
                        },
                        "selected_visual_premise": visual_premise_schema,
                        "human_characters": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 4,
                            "items": human_schema,
                        },
                        "prop_bible": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 5,
                            "items": prop_schema,
                        },
                        "twist": {"type": "string"},
                        "payoff": {"type": "string"},
                        "source_usage": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "mode": {"type": "string"},
                                "how_used": {"type": "string"},
                                "attribution": {"type": "string"},
                            },
                            "required": ["mode", "how_used", "attribution"],
                        },
                    },
                    "required": [
                        "title",
                        "brief",
                        "headline_mechanic",
                        "visual_premise_candidates",
                        "selected_visual_premise",
                        "human_characters",
                        "prop_bible",
                        "twist",
                        "payoff",
                        "source_usage",
                    ],
                },
            },
        }

    def _surface_response_format(self, *, panel_count: int) -> dict[str, Any]:
        task_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
                "task_type": {"type": "string", "enum": list(GRAPHIC_NOVEL_TASKS)},
                "concept_id": {"type": ["integer", "null"]},
                "label": {"type": "string"},
                "instruction": {"type": "string"},
                "prompt": {"type": "string"},
                "prompt_translation": {"type": "string"},
                "expected_answer": {"type": "string"},
                "accepted_answers": {"type": "array", "items": {"type": "string"}},
                "options": {"type": "array", "items": {"type": "string"}},
                "expected_features": {"type": "array", "items": {"type": "string"}},
                "placeholder": {"type": "string"},
                "scene_function": {"type": "string"},
                "feedback_context": {"type": "string"},
                "branch_target": {
                    "type": "object",
                    "additionalProperties": True,
                },
            },
            "required": [
                "id",
                "task_type",
                "concept_id",
                "label",
                "instruction",
                "prompt",
                "prompt_translation",
                "expected_answer",
                "accepted_answers",
                "options",
                "expected_features",
                "placeholder",
                "scene_function",
                "feedback_context",
            ],
        }
        caption_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "panel_index": {"type": "integer"},
                "fr": {"type": "string"},
                "en": {"type": "string"},
            },
            "required": ["panel_index", "fr", "en"],
        }
        bubble_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "speaker": {"type": "string"},
                "fr": {"type": "string"},
                "en": {"type": "string"},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "tone": {"type": "string"},
            },
            "required": ["speaker", "fr", "en", "x", "y", "tone"],
        }
        panel_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "panel_index": {"type": "integer"},
                "title": {"type": "string"},
                "beat": {"type": "string"},
                "panel_action": {"type": "string"},
                "image_prompt_note": {"type": "string"},
                "overlay_payload": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "caption": caption_schema,
                        "bubbles": {
                            "type": "array",
                            "minItems": 0,
                            "maxItems": 2,
                            "items": bubble_schema,
                        },
                        "tasks": {"type": "array", "items": task_schema},
                    },
                    "required": ["caption", "bubbles", "tasks"],
                },
            },
            "required": ["panel_index", "title", "beat", "panel_action", "image_prompt_note", "overlay_payload"],
        }
        gloss_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "term": {"type": "string"},
                "meaning": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["term", "meaning", "reason"],
        }
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "feuilleton_surface_script",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "brief": {"type": "string"},
                        "captions": {
                            "type": "array",
                            "minItems": panel_count,
                            "maxItems": panel_count,
                            "items": caption_schema,
                        },
                        "comic_tone": {"type": "string"},
                        "dialogue_register": {"type": "string"},
                        "support_register": {"type": "string"},
                        "glosses": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 8,
                            "items": gloss_schema,
                        },
                        "visual_gag_quality": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "headline_link_visible": {"type": "boolean"},
                                "one_absurd_image": {"type": "boolean"},
                                "visual_escalation_clear": {"type": "boolean"},
                                "captions_not_pedagogy": {"type": "boolean"},
                                "exercises_extend_premise": {"type": "boolean"},
                                "notes": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "headline_link_visible",
                                "one_absurd_image",
                                "visual_escalation_clear",
                                "captions_not_pedagogy",
                                "exercises_extend_premise",
                                "notes",
                            ],
                        },
                        "panels": {
                            "type": "array",
                            "minItems": panel_count,
                            "maxItems": panel_count,
                            "items": panel_schema,
                        },
                        "final_prompt": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {"type": "string"},
                                "task_type": {"type": "string", "enum": ["short_sentence"]},
                                "instruction": {"type": "string"},
                                "prompt_body": {"type": "string"},
                                "prompt_translation": {"type": "string"},
                                "expected_features": {"type": "array", "items": {"type": "string"}},
                                "placeholder": {"type": "string"},
                                "min_words": {"type": "integer"},
                                "max_words": {"type": "integer"},
                            },
                            "required": [
                                "id",
                                "task_type",
                                "instruction",
                                "prompt_body",
                                "prompt_translation",
                                "expected_features",
                                "placeholder",
                                "min_words",
                                "max_words",
                            ],
                        },
                        "quality_notes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 6,
                        },
                    },
                    "required": [
                        "title",
                        "brief",
                        "captions",
                        "comic_tone",
                        "dialogue_register",
                        "support_register",
                        "glosses",
                        "visual_gag_quality",
                        "panels",
                        "final_prompt",
                        "quality_notes",
                    ],
                },
            },
        }

    def _validate_story_skeleton(self, *, skeleton: dict[str, Any], panel_count: int) -> list[str]:
        errors: list[str] = []
        if len(skeleton.get("visual_premise_candidates") or []) != 3:
            errors.append("skeleton_missing_three_visual_premises")
        selected = skeleton.get("selected_visual_premise") if isinstance(skeleton.get("selected_visual_premise"), dict) else {}
        for key in ("mechanic", "headline_mechanic", "anchor_object", "domain", "why_it_matches_source"):
            if len(str(selected.get(key) or "").strip()) < 12:
                errors.append(f"skeleton_weak_selected_{key}")
        if len(str(skeleton.get("twist") or "").strip()) < 12:
            errors.append("skeleton_missing_twist")
        if len(str(skeleton.get("payoff") or "").strip()) < 12:
            errors.append("skeleton_missing_payoff")
        beats = selected.get("beat_sequence") if isinstance(selected.get("beat_sequence"), list) else []
        if len(beats) != panel_count:
            errors.append("skeleton_panel_beat_count_mismatch")
        if beats:
            beat_texts = [str((beat or {}).get("beat") or (beat or {}).get("panel_action") or "").strip() for beat in beats]
            if len({item.lower() for item in beat_texts if item}) < panel_count:
                errors.append("skeleton_duplicate_panel_beats")
            for text in beat_texts:
                lowered = text.lower()
                if len(text) < 18:
                    errors.append("skeleton_weak_panel_beat")
                    break
                if any(phrase in lowered for phrase in GENERIC_PANEL_BEAT_PHRASES):
                    errors.append("skeleton_panel_beat_is_template_or_pedagogy")
                    break
            if len(beats) >= 2:
                previous_tokens = _lexical_tokens((beats[-2] or {}).get("beat") or (beats[-2] or {}).get("panel_action"))
                final_tokens = _lexical_tokens((beats[-1] or {}).get("beat") or (beats[-1] or {}).get("panel_action"))
                overlap = len(previous_tokens & final_tokens) / max(len(final_tokens), 1)
                turn_type = str((beats[-1] or {}).get("turn_type") or "").lower()
                if overlap > 0.7 and not any(
                    word in turn_type for word in ("turn", "inversion", "outside", "callback", "time", "object", "reframe")
                ):
                    errors.append("skeleton_final_panel_is_more_of_same")
        prop_words = {"poster", "affiche", "chair", "chaise", "calendar", "calendrier", "cup", "tasse", "machine", "umbrella", "parapluie"}
        for character in skeleton.get("human_characters") or []:
            if not isinstance(character, dict):
                continue
            combined = _normalize_text(f"{character.get('name')} {character.get('role')} {character.get('visual_description')}")
            if any(word in combined for word in prop_words):
                errors.append("skeleton_prop_in_human_characters")
                break
        return sorted(set(errors))

    def _normalize_script(
        self,
        *,
        script: dict[str, Any],
        source_snapshot: dict[str, Any],
        concepts: list[GrammarConcept],
        targets: list[dict[str, Any]],
        target_vocabulary: list[dict[str, Any]],
        panel_count: int,
        story_quality: str,
        humor_style: str,
        story_model: str,
        experience_mode: str,
        render_mode: str,
        image_quality: str,
        public_figure_mode: str,
        story_cost: float,
    ) -> dict[str, Any]:
        source_title = (
            source_snapshot.get("title")
            or ((source_snapshot.get("items") or [{}])[0] or {}).get("title")
            or "Atelier scene"
        )
        visual_only_demo = bool(script.get("visual_only_demo"))
        visual_candidates = self._normalize_visual_premise_candidates(script)
        selected_visual = self._normalize_selected_visual_premise(script, visual_candidates)
        headline_mechanic = str(
            script.get("headline_mechanic")
            or selected_visual.get("headline_mechanic")
            or selected_visual.get("mechanic")
            or ""
        ).strip()
        captions = self._normalize_captions(script.get("captions"), panel_count=panel_count)
        skeleton = script.get("story_skeleton") if isinstance(script.get("story_skeleton"), dict) else {}
        story_bible_raw = script.get("story_bible") if isinstance(script.get("story_bible"), dict) else {}
        story_bible = {
            "premise": str(story_bible_raw.get("premise") or selected_visual.get("mechanic") or selected_visual.get("absurd_image") or ""),
            "setting": str(story_bible_raw.get("setting") or selected_visual.get("domain") or "A fictional French public space."),
            "conflict": str(story_bible_raw.get("conflict") or headline_mechanic),
            "news_mechanic": headline_mechanic,
            "twist": str(story_bible_raw.get("twist") or skeleton.get("twist") or script.get("twist") or ""),
            "payoff": str(story_bible_raw.get("payoff") or skeleton.get("payoff") or script.get("payoff") or ""),
            "grammar_integration": str(story_bible_raw.get("grammar_integration") or "Exercises extend captions with fresh beats."),
        }
        characters = script.get("human_characters") or script.get("character_refs") or script.get("character_bible")
        if not isinstance(characters, list) or not characters:
            characters = []
        characters = [character for character in characters if isinstance(character, dict) and not self._looks_like_prop_character(character)]
        prop_bible = script.get("prop_bible") if isinstance(script.get("prop_bible"), list) else []
        if selected_visual.get("anchor_object"):
            prop_bible = [
                {
                    "name": str(selected_visual.get("anchor_object")),
                    "visual_description": str(selected_visual.get("anchor_object")),
                    "comic_function": "recurring visual anchor",
                },
                *[prop for prop in prop_bible if isinstance(prop, dict)],
            ]
        beat_sequence = selected_visual.get("beat_sequence") if isinstance(selected_visual.get("beat_sequence"), list) else []
        panels = script.get("panels") if isinstance(script.get("panels"), list) else []
        normalized_panels: list[dict[str, Any]] = []
        for index, panel in enumerate(panels[:panel_count], start=1):
            if not isinstance(panel, dict):
                panel = {}
            skeleton_beat = beat_sequence[index - 1] if index - 1 < len(beat_sequence) and isinstance(beat_sequence[index - 1], dict) else {}
            caption = captions[index - 1] if index - 1 < len(captions) else {
                "panel_index": index,
                "fr": str((panel.get("overlay_payload") or {}).get("caption", {}).get("fr") or ""),
                "en": str((panel.get("overlay_payload") or {}).get("caption", {}).get("en") or ""),
            }
            panel["panel_index"] = index
            panel["title"] = str(panel.get("title") or "").strip()
            panel["beat"] = str(panel.get("beat") or skeleton_beat.get("beat") or "").strip()
            panel["panel_action"] = str(panel.get("panel_action") or skeleton_beat.get("panel_action") or panel.get("visual_gag") or "").strip()
            panel["image_prompt_note"] = str(panel.get("image_prompt_note") or skeleton_beat.get("action_change") or panel.get("image_prompt") or "").strip()
            panel["visual_gag"] = panel["panel_action"]
            panel["prop_focus"] = str(panel.get("prop_focus") or selected_visual.get("anchor_object") or "").strip()
            panel["overlay_payload"] = self._normalize_overlay(
                panel.get("overlay_payload"),
                panel_index=index,
                targets=targets,
                caption=caption,
                strip_tasks=experience_mode == "reward" or visual_only_demo,
            )
            panel["image_prompt"] = self._compose_image_prompt(
                headline_mechanic=headline_mechanic,
                selected_visual_premise=selected_visual,
                characters=characters,
                prop_bible=prop_bible,
                panel=panel,
                humor_style=humor_style,
                render_mode=render_mode,
                public_figure_mode=public_figure_mode,
            )
            normalized_panels.append(panel)

        final_prompt = script.get("final_prompt") if isinstance(script.get("final_prompt"), dict) else {}
        if visual_only_demo:
            final_prompt = {
                "id": "",
                "task_type": "visual_only",
                "instruction": "",
                "prompt_body": "",
                "prompt_translation": "",
                "expected_features": [],
                "placeholder": "",
                "min_words": 0,
                "max_words": 0,
                "prompt": "",
            }
        else:
            final_features = (
                final_prompt.get("expected_features")
                if isinstance(final_prompt.get("expected_features"), list)
                else []
            )
            final_features = [feature for feature in final_features if feature][:3]
            final_prompt = {
                "id": str(final_prompt.get("id") or "").strip(),
                "task_type": str(final_prompt.get("task_type") or "").strip(),
                "instruction": str(final_prompt.get("instruction") or "").strip(),
                "prompt_body": str(
                    final_prompt.get("prompt_body")
                    or final_prompt.get("prompt")
                    or ""
                ).strip(),
                "prompt_translation": str(final_prompt.get("prompt_translation") or final_prompt.get("translation") or ""),
                "expected_features": final_features,
                "placeholder": str(final_prompt.get("placeholder") or "").strip(),
                "min_words": _nonnegative_int(final_prompt.get("min_words")),
                "max_words": _nonnegative_int(final_prompt.get("max_words")),
            }
            final_prompt["instruction"] = _normalize_task_instruction(final_prompt)
            final_prompt["prompt"] = final_prompt["prompt_body"]
            if not (
                final_prompt["id"]
                and final_prompt["instruction"]
                and final_prompt["prompt_body"]
                and final_prompt["prompt_translation"]
                and final_prompt["expected_features"]
            ):
                final_prompt["id"] = ""
        return {
            "title": str(script.get("title") or "Feuilleton: Le sujet du jour"),
            "brief": str(
                script.get("brief")
                or (
                    f"Read the {panel_count} panels and inspect the visual sequence."
                    if visual_only_demo
                    else f"Read the {panel_count} panels, answer the overlay tasks, then finish the scene in French."
                )
            ),
            "story_bible": story_bible,
            "character_bible": characters,
            "prop_bible": prop_bible,
            "comic_tone": str(script.get("comic_tone") or humor_style),
            "source_usage": script.get("source_usage")
            if isinstance(script.get("source_usage"), dict)
            else {
                "mode": str(source_snapshot.get("mode") or "curated"),
                "how_used": "Fictional context only.",
                "attribution": str(source_snapshot.get("source") or "Atelier"),
            },
            "panels": normalized_panels,
            "page_image_prompt": self._compose_page_image_prompt(
                script={
                    "panel_count": panel_count,
                    "panels": normalized_panels,
                    "story_bible": story_bible,
                    "selected_comedy_premise": self._legacy_selected_premise(selected_visual),
                    "character_bible": characters,
                }
            ),
            "final_prompt": final_prompt,
            "quality_notes": script.get("quality_notes") if isinstance(script.get("quality_notes"), list) else [],
            "estimated_cost": self._estimated_cost(
                panel_count=panel_count,
                story_cost=story_cost,
                render_mode=render_mode,
                image_quality=image_quality,
            ),
            "story_quality": story_quality,
            "story_model": story_model,
            "experience_mode": experience_mode,
            "render_mode": render_mode,
            "image_quality": image_quality,
            "public_figure_mode": public_figure_mode,
            "visual_only_demo": visual_only_demo,
            "headline_mechanic": headline_mechanic,
            "visual_premise_candidates": visual_candidates,
            "selected_visual_premise": selected_visual,
            "serial_context": script.get("serial_context") if isinstance(script.get("serial_context"), dict) else {},
            "location_id": str(script.get("location_id") or ""),
            "hook": script.get("hook") if isinstance(script.get("hook"), dict) else {},
            "captions": captions,
            "satire_premise_candidates": self._legacy_premise_candidates(visual_candidates),
            "selected_comedy_premise": self._legacy_selected_premise(selected_visual),
            "dialogue_register": str(script.get("dialogue_register") or "native-like B2/C1 French dialogue"),
            "support_register": str(script.get("support_register") or "learner-level English support and glosses"),
            "glosses": self._normalize_glosses(script.get("glosses")),
            "story_quality_score": self._story_quality_score(
                selected_visual=selected_visual,
                visual_gag_quality=script.get("visual_gag_quality"),
                story_bible=story_bible,
            ),
            "comedy_validation": self._normalize_comedy_validation(script.get("visual_gag_quality") or script.get("comedy_validation")),
        }

    def _normalize_overlay(
        self,
        overlay: Any,
        *,
        panel_index: int,
        targets: list[dict[str, Any]],
        caption: dict[str, Any] | None = None,
        strip_tasks: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(overlay, dict):
            overlay = {}
        tasks = [] if strip_tasks else (overlay.get("tasks") if isinstance(overlay.get("tasks"), list) else [])
        normalized_tasks: list[dict[str, Any]] = []
        concept_id = next((target.get("concept_id") for target in targets if target.get("concept_id")), None)
        for task_index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict) or task.get("task_type") not in GRAPHIC_NOVEL_TASKS:
                continue
            task_type = task.get("task_type")
            normalized = {
                "id": str(task.get("id") or f"panel_{panel_index}_task_{task_index}"),
                "task_type": task_type,
                "concept_id": task.get("concept_id") if task.get("concept_id") is not None else concept_id,
                "label": str(task.get("label") or ""),
                "instruction": "",
                "prompt": str(task.get("prompt") or ""),
                "prompt_translation": str(task.get("prompt_translation") or task.get("translation") or task.get("prompt_en") or ""),
                "expected_answer": str(task.get("expected_answer") or ""),
                "accepted_answers": task.get("accepted_answers") if isinstance(task.get("accepted_answers"), list) else [],
                "options": task.get("options") if isinstance(task.get("options"), list) else [],
                "expected_features": task.get("expected_features") if isinstance(task.get("expected_features"), list) else [],
                "placeholder": str(task.get("placeholder") or ""),
                "scene_function": str(task.get("scene_function") or ""),
                "feedback_context": str(task.get("feedback_context") or ""),
            }
            if task_type == "choice" and isinstance(task.get("branch_target"), dict):
                normalized["branch_target"] = task["branch_target"]
            normalized["instruction"] = _normalize_task_instruction(task)
            if not normalized["instruction"] or not normalized["prompt"] or not normalized["prompt_translation"]:
                continue
            if task_type == "short_sentence" and not normalized["expected_features"]:
                continue
            if task_type in {"cloze", "choice"} and not normalized["expected_answer"]:
                continue
            if task_type == "choice" and len(normalized["options"]) < 2:
                continue
            if task_type in {"cloze", "choice"} and not normalized["accepted_answers"] and normalized["expected_answer"]:
                normalized["accepted_answers"] = [normalized["expected_answer"]]
            for key in (
                "vocabulary_task",
                "production_goal",
                "target_word_id",
                "target_word",
                "target_translation",
                "target_word_translation",
                "example_sentence",
                "example_translation",
                "hints",
            ):
                if key in task:
                    normalized[key] = task[key]
            normalized_tasks.append(normalized)
        normalized_caption = {
            "panel_index": panel_index,
            "fr": str((caption or {}).get("fr") or (overlay.get("caption") or {}).get("fr") or "").strip(),
            "en": str((caption or {}).get("en") or (overlay.get("caption") or {}).get("en") or "").strip(),
        }
        normalized_bubbles: list[dict[str, Any]] = []
        raw_bubbles = overlay.get("bubbles") if isinstance(overlay.get("bubbles"), list) else []
        caption_norm = _normalize_text(f"{normalized_caption.get('fr', '')} {normalized_caption.get('en', '')}")
        for bubble_index, bubble in enumerate(raw_bubbles[:2], start=1):
            if not isinstance(bubble, dict):
                continue
            fr = str(bubble.get("fr") or "").strip()
            if len(fr) < 2:
                continue
            en = str(bubble.get("en") or "").strip()
            bubble_norm = _normalize_text(f"{fr} {en}")
            if bubble_norm and bubble_norm == caption_norm:
                continue
            try:
                x = float(bubble.get("x", 14 + (bubble_index - 1) * 42))
            except (TypeError, ValueError):
                x = float(14 + (bubble_index - 1) * 42)
            try:
                y = float(bubble.get("y", 12 + (bubble_index - 1) * 18))
            except (TypeError, ValueError):
                y = float(12 + (bubble_index - 1) * 18)
            normalized_bubbles.append(
                {
                    "speaker": str(bubble.get("speaker") or f"Voix {bubble_index}").strip()[:32],
                    "fr": fr[:180],
                    "en": en[:180],
                    "x": max(4.0, min(78.0, x)),
                    "y": max(4.0, min(64.0, y)),
                    "tone": str(bubble.get("tone") or "deadpan").strip()[:32],
                }
            )
        return {"caption": normalized_caption, "bubbles": normalized_bubbles, "tasks": normalized_tasks}

    def _normalize_visual_premise_candidates(self, script: dict[str, Any]) -> list[dict[str, Any]]:
        raw = script.get("visual_premise_candidates")
        if not isinstance(raw, list):
            raw = []
        candidates: list[dict[str, Any]] = []
        for index, item in enumerate(raw[:3], start=1):
            if not isinstance(item, dict):
                continue
            candidates.append(
                {
                    "angle": str(item.get("angle") or f"Premise {index}"),
                    "mechanic": str(item.get("mechanic") or item.get("headline_mechanic") or "").strip(),
                    "headline_mechanic": str(item.get("headline_mechanic") or "").strip(),
                    "anchor_object": str(item.get("anchor_object") or "").strip(),
                    "domain": str(item.get("domain") or "").strip(),
                    "absurd_image": str(item.get("absurd_image") or item.get("mechanic") or "").strip(),
                    "why_it_matches_source": str(item.get("why_it_matches_source") or "").strip(),
                    "beat_sequence": item.get("beat_sequence") if isinstance(item.get("beat_sequence"), list) else [],
                    "visual_escalation": item.get("visual_escalation") if isinstance(item.get("visual_escalation"), list) else [],
                    "score_0_10": float(item.get("score_0_10") or 0),
                }
            )
        return candidates

    def _normalize_selected_visual_premise(self, script: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        raw = script.get("selected_visual_premise")
        if isinstance(raw, dict) and (raw.get("mechanic") or raw.get("absurd_image")):
            return self._normalize_visual_premise_candidates({"visual_premise_candidates": [raw]})[0]
        return candidates[0] if candidates else {
            "angle": "",
            "mechanic": "",
            "headline_mechanic": "",
            "anchor_object": "",
            "domain": "",
            "absurd_image": "",
            "why_it_matches_source": "",
            "beat_sequence": [],
            "visual_escalation": [],
            "score_0_10": 0,
        }

    def _normalize_captions(self, raw: Any, *, panel_count: int) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            raw = []
        captions: list[dict[str, Any]] = []
        for index, item in enumerate(raw[:panel_count], start=1):
            if not isinstance(item, dict):
                continue
            captions.append(
                {
                    "panel_index": int(item.get("panel_index") or index),
                    "fr": str(item.get("fr") or "").strip(),
                    "en": str(item.get("en") or "").strip(),
                }
            )
        return captions

    def _legacy_premise_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self._legacy_selected_premise(item) for item in candidates]

    def _legacy_selected_premise(self, premise: dict[str, Any]) -> dict[str, Any]:
        return {
            "angle": premise.get("angle", ""),
            "absurd_premise": premise.get("mechanic") or premise.get("absurd_image", ""),
            "opening_situation": premise.get("domain", ""),
            "character_want": "",
            "obstacle": premise.get("headline_mechanic", ""),
            "opposing_positions": [],
            "news_mechanic": premise.get("headline_mechanic", ""),
            "scene_mechanic": premise.get("why_it_matches_source", ""),
            "escalation": " / ".join(str((item or {}).get("beat") or item) for item in (premise.get("beat_sequence") or premise.get("visual_escalation") or [])[:3]),
            "payoff": "final panel turns the premise",
            "score_0_10": premise.get("score_0_10", 0),
            "why_it_works": premise.get("why_it_matches_source", ""),
        }

    def _normalize_glosses(self, raw: Any) -> list[dict[str, str]]:
        if not isinstance(raw, list):
            raw = []
        glosses: list[dict[str, str]] = []
        for item in raw[:8]:
            if not isinstance(item, dict):
                continue
            term = str(item.get("term") or "").strip()
            meaning = str(item.get("meaning") or "").strip()
            if not term or not meaning:
                continue
            glosses.append(
                {
                    "term": term,
                    "meaning": meaning,
                    "reason": str(item.get("reason") or "Useful phrase in the scene."),
                }
            )
        return glosses

    def _normalize_comedy_validation(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raw = {}
        if any(key in raw for key in ("headline_link_visible", "one_absurd_image", "visual_escalation_clear")):
            headline_link = bool(raw.get("headline_link_visible", True))
            one_image = bool(raw.get("one_absurd_image", True))
            escalation = bool(raw.get("visual_escalation_clear", True))
            captions = bool(raw.get("captions_not_pedagogy", True))
            exercises = bool(raw.get("exercises_extend_premise", True))
            return {
                "has_setup": headline_link and one_image,
                "has_escalation": escalation,
                "has_reversal": escalation,
                "has_payoff": headline_link and escalation,
                "dialogue_not_flattened": captions,
                "grammar_not_driving_every_panel": exercises,
                "notes": raw.get("notes") if isinstance(raw.get("notes"), list) else [],
            }
        return {
            "has_setup": bool(raw.get("has_setup", True)),
            "has_escalation": bool(raw.get("has_escalation", True)),
            "has_reversal": bool(raw.get("has_reversal", True)),
            "has_payoff": bool(raw.get("has_payoff", True)),
            "dialogue_not_flattened": bool(raw.get("dialogue_not_flattened", True)),
            "grammar_not_driving_every_panel": bool(raw.get("grammar_not_driving_every_panel", True)),
            "notes": raw.get("notes") if isinstance(raw.get("notes"), list) else [],
        }

    def _story_quality_score(
        self,
        *,
        selected_visual: dict[str, Any],
        visual_gag_quality: Any,
        story_bible: dict[str, Any],
    ) -> float:
        score = float(selected_visual.get("score_0_10") or 0)
        if isinstance(visual_gag_quality, dict):
            booleans = [
                bool(visual_gag_quality.get("headline_link_visible")),
                bool(visual_gag_quality.get("one_absurd_image")),
                bool(visual_gag_quality.get("visual_escalation_clear")),
                bool(visual_gag_quality.get("captions_not_pedagogy")),
                bool(visual_gag_quality.get("exercises_extend_premise")),
            ]
            score = max(score, sum(booleans) * 2.0)
        if story_bible.get("twist") and story_bible.get("payoff"):
            score = max(score, 7.0)
        return round(min(score, 10.0), 1)

    def _looks_like_prop_character(self, character: dict[str, Any]) -> bool:
        combined = _normalize_text(
            f"{character.get('name', '')} {character.get('role', '')} {character.get('visual_description', '')}"
        )
        prop_words = {
            "poster",
            "affiche",
            "chair",
            "chaise",
            "calendar",
            "calendrier",
            "cup",
            "tasse",
            "machine",
            "umbrella",
            "parapluie",
            "ticket",
            "phone",
            "telephone",
        }
        return any(word in combined for word in prop_words)

    def _validate_script(
        self,
        *,
        script: dict[str, Any],
        panel_count: int,
        experience_mode: str,
        public_figure_mode: str,
        target_language: str = "fr",
        serial_context: dict[str, Any] | None = None,
    ) -> list[str]:
        errors: list[str] = []
        if len(script.get("panels") or []) != panel_count:
            errors.append("panel_count_mismatch")
        if len(script.get("character_bible") or []) < 1:
            errors.append("missing_character_bible")
        if len(str(script.get("headline_mechanic") or "").strip()) < 24:
            errors.append("missing_headline_mechanic")
        if len(script.get("visual_premise_candidates") or []) != 3:
            errors.append("missing_visual_premise_candidates")
        selected_visual = script.get("selected_visual_premise") or {}
        for key in ("headline_mechanic", "mechanic", "anchor_object", "domain", "why_it_matches_source"):
            min_length = 8 if key == "anchor_object" else 24
            if len(str(selected_visual.get(key) or "").strip()) < min_length:
                errors.append(f"weak_selected_visual_premise_{key}")
        beat_sequence = selected_visual.get("beat_sequence") if isinstance(selected_visual.get("beat_sequence"), list) else []
        if len(beat_sequence) != panel_count:
            errors.append("selected_visual_premise_missing_beat_sequence")
        story_bible = script.get("story_bible") or {}
        if len(str(story_bible.get("twist") or "").strip()) < 12:
            errors.append("missing_story_twist")
        if len(str(story_bible.get("payoff") or "").strip()) < 12:
            errors.append("missing_story_payoff")
        if len(script.get("captions") or []) != panel_count:
            errors.append("caption_count_mismatch")
        for caption in script.get("captions") or []:
            if len(str(caption.get("fr") or "").strip()) < 6 or len(str(caption.get("en") or "").strip()) < 6:
                errors.append("weak_caption")
                break
        for panel in script.get("panels") or []:
            overlay = panel.get("overlay_payload") or {}
            caption = overlay.get("caption") or {}
            caption_norm = _normalize_text(f"{caption.get('fr', '')} {caption.get('en', '')}")
            bubbles = overlay.get("bubbles") if isinstance(overlay.get("bubbles"), list) else []
            if len(bubbles) > 2:
                errors.append("too_many_panel_bubbles")
                break
            for bubble in bubbles:
                if not isinstance(bubble, dict):
                    errors.append("invalid_panel_bubble")
                    break
                bubble_fr = str(bubble.get("fr") or "").strip()
                if len(bubble_fr) < 2:
                    errors.append("weak_panel_bubble")
                    break
                if _normalize_text(f"{bubble_fr} {bubble.get('en', '')}") == caption_norm:
                    errors.append("bubble_copies_caption")
                    break
                try:
                    x = float(bubble.get("x"))
                    y = float(bubble.get("y"))
                except (TypeError, ValueError):
                    errors.append("bubble_missing_position")
                    break
                if not (0 <= x <= 100 and 0 <= y <= 100):
                    errors.append("bubble_position_out_of_range")
                    break
        all_tasks = [
            task
            for panel in script.get("panels") or []
            for task in (panel.get("overlay_payload") or {}).get("tasks", [])
        ]
        visual_only_demo = bool(script.get("visual_only_demo"))
        if visual_only_demo and all_tasks:
            errors.append("visual_only_demo_has_tasks")
        if not visual_only_demo and experience_mode == "study" and not any(
            not (panel.get("overlay_payload") or {}).get("tasks") for panel in script.get("panels") or []
        ):
            errors.append("missing_story_only_panel")
        expected_task_count = _task_count(panel_count, experience_mode)
        if not visual_only_demo and len(all_tasks) != expected_task_count:
            errors.append(f"overlay_task_count_mismatch_expected_{expected_task_count}")
        if "grammar" in str(selected_visual.get("absurd_image") or "").lower():
            errors.append("premise_is_grammar_first")
        comedy_validation = script.get("comedy_validation") or {}
        for key in ("has_setup", "has_escalation", "has_reversal", "has_payoff", "dialogue_not_flattened", "grammar_not_driving_every_panel"):
            if comedy_validation.get(key) is False:
                errors.append(f"comedy_validation_{key}_failed")
        if experience_mode == "reward" and all_tasks:
            errors.append("reward_mode_has_required_tasks")
        if len({panel.get("title") for panel in script.get("panels") or []}) < panel_count:
            errors.append("duplicate_panel_titles")
        if any(self._looks_like_prop_character(character) for character in script.get("character_bible") or [] if isinstance(character, dict)):
            errors.append("prop_in_character_bible")
        beats = [str(panel.get("beat") or "").strip() for panel in script.get("panels") or []]
        if len({beat.lower() for beat in beats if beat}) < panel_count:
            errors.append("duplicate_panel_beats")
        for beat in beats:
            lowered = beat.lower()
            if len(beat) < 18:
                errors.append("weak_panel_beat")
                break
            if any(phrase in lowered for phrase in GENERIC_PANEL_BEAT_PHRASES):
                errors.append("panel_beat_is_pedagogy_or_template")
                break
        if len(beats) >= 2:
            previous_tokens = _lexical_tokens(beats[-2])
            final_tokens = _lexical_tokens(beats[-1])
            overlap = len(previous_tokens & final_tokens) / max(len(final_tokens), 1)
            final_turn = ""
            if beat_sequence:
                final_turn = str((beat_sequence[-1] or {}).get("turn_type") or "").lower()
            if overlap > 0.7 and not any(
                word in final_turn for word in ("turn", "inversion", "outside", "callback", "time", "object", "reframe")
            ):
                errors.append("final_panel_is_more_of_same")
        if _contains_any_phrase(script, ("the learner", "the user")):
            errors.append("third_person_feedback")
        final_prompt = script.get("final_prompt") or {}
        if not visual_only_demo and not (
            final_prompt.get("id")
            and final_prompt.get("instruction")
            and final_prompt.get("prompt_body")
            and final_prompt.get("prompt_translation")
        ):
            errors.append("final_prompt_missing_required_content")
        if not visual_only_demo and _normalize_text(final_prompt.get("instruction")) == _normalize_text(final_prompt.get("prompt_body")):
            errors.append("final_prompt_duplicates_instruction")
        if not visual_only_demo and not final_prompt.get("expected_features"):
            errors.append("final_prompt_missing_expected_features")
        if _contains_any_phrase(script, ("murder", "abuse", "sexual violence", "rape", "suicide")):
            errors.append("sensitive_plot_content")
        for panel in script.get("panels") or []:
            overlay = panel.get("overlay_payload") or {}
            caption = overlay.get("caption") or {}
            caption_text = _normalize_text(f"{caption.get('fr', '')} {caption.get('en', '')}")
            for task in (overlay.get("tasks") or []):
                if _mentions_parentheses(task.get("instruction")) and not _has_parenthetical_cue(task.get("prompt")):
                    errors.append("task_instruction_references_missing_parentheses")
                    break
                if len(str(task.get("prompt_translation") or "").strip()) < 4:
                    errors.append("task_missing_prompt_translation")
                    break
                if task.get("task_type") == "short_sentence" and not task.get("expected_features"):
                    errors.append("short_sentence_missing_expected_feature")
                    break
                if task.get("task_type") in {"cloze", "choice"}:
                    expected = _normalize_text(task.get("expected_answer") or "")
                    accepted = [_normalize_text(item) for item in task.get("accepted_answers") or [] if item]
                    prompt_text = _normalize_text(task.get("prompt") or "")
                    if expected and (expected in caption_text or any(item and item in caption_text for item in accepted)):
                        errors.append("closed_task_copied_from_caption")
                        break
                    if expected and expected in prompt_text:
                        errors.append("closed_task_answer_leaked_in_prompt")
                        break
                    if len(str(task.get("scene_function") or "").strip()) < 20:
                        errors.append("task_missing_scene_function")
                        break
                    if len(str(task.get("feedback_context") or "").strip()) < 20:
                        errors.append("task_missing_feedback_context")
                        break
                    if target_language == "fr":
                        answer_values = [task.get("expected_answer") or "", *(task.get("accepted_answers") or []), *(task.get("options") or [])]
                        if any(_looks_like_english_sentence(value) for value in answer_values if value):
                            errors.append("task_answer_not_target_language")
                            break
                        if any(_has_invalid_french_article_phrase(value) for value in (task.get("options") or [])):
                            errors.append("choice_task_has_implausible_distractor")
                            break
            prompt = str(panel.get("image_prompt") or "").lower()
            if "do not draw readable text" not in prompt and "do not include readable text" not in prompt:
                errors.append("image_prompt_missing_text_forbid")
                break
            for forbidden in (
                "story premise:",
                "news/context inspiration",
                "twist:",
                "payoff",
                "target grammar",
                "grammar framing",
                "bauhaus geometry",
                "many calendars",
                "many bags",
                "generic franco-belgian crowd",
            ):
                if forbidden in prompt:
                    errors.append("image_prompt_keeps_old_visual_clutter")
                    break
            if "penguin" not in prompt or "halftone" not in prompt:
                errors.append("image_prompt_missing_moodboard")
                break
            if "human continuity:" not in prompt or "panel action:" not in prompt or "scene visual preamble:" not in prompt:
                errors.append("image_prompt_missing_visual_context")
                break
            if public_figure_mode != "editorial_caricature" and "real identifiable" not in prompt and "real public figures" not in prompt:
                errors.append("image_prompt_missing_public_figure_policy")
                break
        for task in all_tasks:
            if task.get("task_type") in {"cloze", "choice"} and not task.get("expected_answer"):
                errors.append("closed_task_missing_answer")
                break
            if task.get("task_type") == "choice" and len(task.get("options") or []) < 2:
                errors.append("choice_task_missing_options")
                break
        serial_brief = (serial_context or {}).get("episode_brief") if isinstance(serial_context, dict) else {}
        if isinstance(serial_brief, dict) and serial_brief:
            required_ids = [str(item) for item in serial_brief.get("required_cast") or [] if str(item or "").strip()]
            world = (serial_context or {}).get("world_bible") if isinstance((serial_context or {}).get("world_bible"), dict) else {}
            cast_by_id = {
                str(member.get("id")): str(member.get("name") or member.get("id"))
                for member in world.get("cast") or []
                if isinstance(member, dict) and member.get("id")
            }
            haystack = _normalize_text(json.dumps(script.get("panels") or [], ensure_ascii=False))
            for character_id in required_ids:
                name = cast_by_id.get(character_id, character_id)
                tokens = [character_id.replace("_", " "), name]
                if character_id == "augustin_de_roncourt":
                    tokens.append("Gus")
                if not any(_normalize_text(token) in haystack for token in tokens):
                    errors.append(f"serial_required_cast_missing_{character_id}")
            hook = script.get("hook") if isinstance(script.get("hook"), dict) else {}
            if len(str(hook.get("unresolved_question") or "").strip()) < 8:
                errors.append("serial_final_hook_missing_unresolved_question")
        return sorted(set(errors))

    def _compose_image_prompt(
        self,
        *,
        headline_mechanic: str,
        selected_visual_premise: dict[str, Any],
        characters: list[dict[str, Any]],
        prop_bible: list[dict[str, Any]],
        panel: dict[str, Any],
        humor_style: str,
        render_mode: str,
        public_figure_mode: str,
    ) -> str:
        character_line = "; ".join(
            f"{item.get('name')}: {item.get('visual_description')}" for item in characters[:4] if isinstance(item, dict)
        )
        prop_line = "; ".join(
            f"{item.get('name')}: {item.get('visual_description')}" for item in prop_bible[:5] if isinstance(item, dict)
        )
        panel_action = str(panel.get("panel_action") or panel.get("visual_gag") or panel.get("beat") or "").strip()
        panel_note = str(panel.get("image_prompt_note") or "").strip()
        anchor = str(selected_visual_premise.get("anchor_object") or "one decisive recurring prop").strip()
        domain = str(selected_visual_premise.get("domain") or "a fictional French public space").strip()
        if public_figure_mode == "editorial_caricature":
            public_figure_policy = (
                "Public figures may be portrayed only as clearly editorial, non-defamatory caricature if relevant; "
                "do not portray victims, private people, or sensitive personal allegations."
            )
        elif public_figure_mode == "named_context":
            public_figure_policy = (
                "Use real public figures only as named topic context outside the image; in the image, use fictionalized people only and do not depict real identifiable politicians, celebrities, victims, or public figures."
            )
        else:
            public_figure_policy = "Exclude real public figures entirely; use fictional people only."
        return (
            "Draw one square editorial visual-gag comic panel in the spirit of Penguin Crime, Penguin Modern Classics, Len Deighton spy paperback covers, Sempé, and New Yorker single-panel restraint. "
            "Use photomechanical halftone texture, high-contrast black ink, cream paper, sharp red accents, and at most one muted blue or green accent. "
            f"{IMAGE_STYLE_MOODBOARD} "
            "The aesthetic should feel spare, printed, noir-adjacent, and book-cover intelligent, not a generic app illustration or a busy adventure panel. "
            f"Scene visual preamble: satirize this mechanic without naming the real source in the image: {headline_mechanic}. "
            f"Visual domain: {domain}. Anchor object: {anchor}. "
            f"Human continuity: {character_line or 'fictional French people with simple readable silhouettes'}. "
            f"Recurring props: {prop_line or anchor}. "
            f"Panel action: {panel_action}. "
            f"Action change from previous panel: {panel_note}. "
            f"Decisive foreground instruction: use {panel.get('prop_focus') or anchor} as the one visually dominant prop; avoid repeated calendars, bags, paperwork piles, and decorative geometry unless that exact prop is the joke. "
            f"Humour mode: {humor_style}; render mode: {render_mode}; funny through situation and composition, never cruelty. "
            f"{public_figure_policy} "
            "The image is context only; no readable text should appear. Do not draw readable text, letters, captions, speech bubbles, UI, blanks, subtitles, signs, labels, or answer choices. "
            "Leave calm negative space where HTML speech bubbles and annotations can sit later. "
            "Keep the composition legible at small size, with one strong foreground action, generous negative space, no prop repetition, no date-grid wallpaper, no shopping-bag piles, no abstract grammar diagrams, and no decorative geometric motif clutter."
        )

    def _compose_page_image_prompt(self, *, script: dict[str, Any]) -> str:
        panels = script.get("panels") or []
        panel_lines = " ".join(
            f"Panel {panel.get('panel_index')}: {panel.get('beat')} Visual gag: {panel.get('visual_gag')}."
            for panel in panels
        )
        characters = "; ".join(
            f"{item.get('name')}: {item.get('visual_description')}"
            for item in (script.get("character_bible") or [])[:5]
            if isinstance(item, dict)
        )
        return (
            "Draw one complete comic page containing exactly "
            f"{script.get('panel_count') or len(panels)} panels in a clean grid. Penguin Crime and Penguin Modern Classics paperback-cover mood, "
            "Len Deighton spy-cover restraint, photomechanical halftone texture, cream paper, high-contrast black ink, sharp red accents, and at most one muted blue or green accent. "
            f"{IMAGE_STYLE_MOODBOARD} "
            f"Story premise: {(script.get('story_bible') or {}).get('premise')}. "
            f"News-to-fiction mechanic: {(script.get('story_bible') or {}).get('news_mechanic')}. "
            f"Selected comic premise: {(script.get('selected_comedy_premise') or {}).get('absurd_premise')}. "
            f"Characters to keep consistent: {characters or 'fictional French characters with readable silhouettes'}. "
            f"Panel plan: {panel_lines}. "
            "Use fictionalized people unless editorial caricature is explicitly requested in metadata; never portray victims or private people. "
            "Do not draw readable text, letters, captions, speech bubbles, UI, blanks, subtitles, signs, labels, or answer choices. "
            "Leave natural calm areas where HTML speech bubbles, captions, and grammar annotations can be overlaid later. Avoid repeated props and crowded object piles."
        )

    def _estimated_cost(self, *, panel_count: int, story_cost: float, render_mode: str, image_quality: str) -> dict[str, Any]:
        units = 1 if render_mode == "page" else panel_count
        quality_factor = {"low": 0.55, "medium": 1.0, "high": 1.6}.get(image_quality, 1.0)
        image_cost = round(units * settings.GRAPHIC_NOVEL_IMAGE_COST_USD_PER_PANEL * quality_factor, 3)
        return {
            "currency": "USD",
            "panel_count": panel_count,
            "render_mode": render_mode,
            "image_quality": image_quality,
            "image_units": units,
            "image_generation_usd": image_cost,
            "story_generation_usd": round(story_cost, 4),
            "total_estimated_usd": round(image_cost + story_cost, 3),
            "basis": "Configured gpt-image-2 estimate scaled by render mode and quality; story cost uses provider token usage when available.",
        }

    def _source_prompt(self, source_snapshot: dict[str, Any]) -> dict[str, Any]:
        item = ((source_snapshot.get("items") or [{}])[0] or {})
        return {
            "mode": source_snapshot.get("mode") or "curated",
            "title": source_snapshot.get("title") or item.get("title") or "",
            "summary": source_snapshot.get("summary") or item.get("summary") or "",
            "source": source_snapshot.get("source") or item.get("source") or "",
            "source_policy": source_snapshot.get("source_policy") or "",
        }

    def _concept_prompt(self, concept: GrammarConcept) -> dict[str, Any]:
        blueprint = {}
        try:
            blueprint = self.asset_service.approved_blueprint_payload(concept) or {}
        except Exception:
            blueprint = {}
        pedagogy = blueprint.get("pedagogy") if isinstance(blueprint.get("pedagogy"), dict) else {}
        return {
            "id": concept.id,
            "external_id": concept.external_id,
            "title": _concept_title(concept, self.asset_service),
            "level": getattr(concept, "cefr_level", None) or concept.level,
            "category": concept.category,
            "core_rule": pedagogy.get("core_rule") or concept.core_rule,
            "traps": pedagogy.get("main_traps") or concept.main_traps,
            "examples": pedagogy.get("anchor_examples") or concept.anchor_examples,
        }

    def _erratum_prompt(self, error: UserError) -> dict[str, Any]:
        return {
            "id": str(error.id),
            "concept_id": error.concept_id,
            "label": error.display_label or error.error_pattern or "remembered mistake",
            "learner_text": error.original_text,
            "correction": error.correction,
            "why_wrong": error.why_wrong,
            "repair_hint": error.repair_hint,
            "occurrences": error.occurrences,
        }


GraphicNovelScriptGenerator = GraphicNovelStoryGenerator


class GraphicNovelImageService:
    """Generate or fall back to deterministic panel visuals."""

    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if settings.OPENAI_ORG_ID:
            headers["OpenAI-Organization"] = settings.OPENAI_ORG_ID
        return headers

    async def generate_page_image(self, *, script: dict[str, Any], image_quality: str) -> dict[str, Any]:
        prompt = str(script.get("page_image_prompt") or "").strip()
        if not prompt:
            prompt = (
                f"Draw one complete comic page with {script.get('panel_count', 6)} panels. "
                "Penguin Crime paperback-cover mood, photomechanical halftone texture, editorial paper, no readable text."
            )
        if settings.GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED and self.api_key:
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    image = await self._call_openai_image(
                        prompt,
                        image_quality=image_quality,
                        image_size="1024x1536",
                    )
                    image["render_mode"] = "page"
                    return image
                except Exception as exc:
                    last_error = exc
                    logger.warning(f"Graphic novel page image attempt {attempt} failed: {exc}")
                    if attempt < 3:
                        await asyncio.sleep(1.5 * attempt)
            logger.warning(f"Graphic novel page image fallback after retries: {last_error}")
        fallback = self._fallback_svg(prompt=prompt, panel_index=1)
        fallback["render_mode"] = "page"
        return fallback

    async def generate_panel_image(self, prompt: str, panel_index: int, image_quality: str | None = None) -> dict[str, Any]:
        if settings.GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED and self.api_key:
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    return await self._call_openai_image(
                        prompt,
                        image_quality=_image_quality(image_quality),
                        image_size=settings.OPENAI_IMAGE_SIZE,
                    )
                except Exception as exc:
                    last_error = exc
                    logger.warning(f"Graphic novel image attempt {attempt} failed: {exc}")
                    if attempt < 3:
                        await asyncio.sleep(1.5 * attempt)
            logger.warning(f"Graphic novel image fallback after retries: {last_error}")
        return self._fallback_svg(prompt=prompt, panel_index=panel_index)

    async def _call_openai_image(self, prompt: str, *, image_quality: str, image_size: str) -> dict[str, Any]:
        base_url = str(settings.OPENAI_API_BASE or "https://api.openai.com/v1").rstrip("/")
        async with httpx.AsyncClient(timeout=settings.OPENAI_IMAGE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}/images/generations",
                headers=self._build_headers(),
                json={
                    "model": settings.OPENAI_IMAGE_MODEL,
                    "prompt": prompt,
                    "n": 1,
                    "size": image_size,
                    "quality": image_quality,
                },
            )
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_body = error_data.get("error", {}).get("message", response.text)
                except Exception:
                    error_body = response.text
                raise RuntimeError(f"OpenAI image error {response.status_code}: {error_body[:500]}")
            data = response.json()
        image = (data.get("data") or [{}])[0]
        url = image.get("url")
        if not url and image.get("b64_json"):
            url = f"data:image/png;base64,{image['b64_json']}"
        if not url:
            raise ValueError("OpenAI image response did not include url or b64_json")
        return {
            "url": url,
            "prompt": prompt,
            "model": settings.OPENAI_IMAGE_MODEL,
            "quality": image_quality,
            "size": image_size,
            "fallback_used": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _fallback_svg(self, *, prompt: str, panel_index: int) -> dict[str, Any]:
        colors = [
            ("#f1ece1", "#d8321a", "#1d3a8a"),
            ("#e8e0cf", "#1d3a8a", "#f3c318"),
            ("#f1ece1", "#14110d", "#d8321a"),
            ("#e8e0cf", "#f3c318", "#1d3a8a"),
        ]
        bg, accent, accent_2 = colors[(panel_index - 1) % len(colors)]
        figure_shift = 52 * ((panel_index - 1) % 3)
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 620">
          <defs>
            <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="4" cy="4" r="2.2" fill="#14110d" opacity="0.16"/>
            </pattern>
          </defs>
          <rect width="900" height="620" fill="{bg}"/>
          <rect width="900" height="620" fill="url(#dots)"/>
          <rect x="42" y="42" width="816" height="536" fill="none" stroke="#14110d" stroke-width="7"/>
          <rect x="78" y="96" width="142" height="126" fill="#f1ece1" stroke="#14110d" stroke-width="6"/>
          <line x1="149" y1="96" x2="149" y2="222" stroke="#14110d" stroke-width="5"/>
          <line x1="78" y1="159" x2="220" y2="159" stroke="#14110d" stroke-width="5"/>
          <rect x="260" y="96" width="142" height="126" fill="#f1ece1" stroke="#14110d" stroke-width="6"/>
          <line x1="331" y1="96" x2="331" y2="222" stroke="#14110d" stroke-width="5"/>
          <line x1="260" y1="159" x2="402" y2="159" stroke="#14110d" stroke-width="5"/>
          <circle cx="760" cy="118" r="46" fill="{accent_2}" stroke="#14110d" stroke-width="6"/>
          <rect x="68" y="254" width="764" height="62" fill="{accent}" stroke="#14110d" stroke-width="6"/>
          <path d="M68 316 C160 384, 250 384, 342 316 C436 384, 526 384, 618 316 C710 384, 782 384, 832 316" fill="none" stroke="#14110d" stroke-width="7"/>
          <rect x="42" y="476" width="816" height="102" fill="#ded3bd" stroke="#14110d" stroke-width="5"/>
          <g transform="translate({120 + figure_shift} 276)">
            <circle cx="56" cy="54" r="34" fill="#f1ece1" stroke="#14110d" stroke-width="7"/>
            <rect x="30" y="94" width="56" height="112" rx="24" fill="{accent_2}" stroke="#14110d" stroke-width="7"/>
            <line x1="32" y1="124" x2="-14" y2="96" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
            <line x1="82" y1="124" x2="134" y2="94" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
            <line x1="46" y1="204" x2="28" y2="274" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
            <line x1="72" y1="204" x2="94" y2="274" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
          </g>
          <g transform="translate({470 - figure_shift // 2} 308) scale(.88)">
            <circle cx="56" cy="54" r="34" fill="#f1ece1" stroke="#14110d" stroke-width="7"/>
            <rect x="30" y="94" width="56" height="112" rx="24" fill="{accent}" stroke="#14110d" stroke-width="7"/>
            <line x1="32" y1="124" x2="-10" y2="112" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
            <line x1="82" y1="124" x2="128" y2="126" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
            <line x1="46" y1="204" x2="28" y2="274" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
            <line x1="72" y1="204" x2="94" y2="274" stroke="#14110d" stroke-width="8" stroke-linecap="round"/>
          </g>
          <rect x="686" y="390" width="116" height="22" fill="{accent_2}" stroke="#14110d" stroke-width="6"/>
          <line x1="704" y1="412" x2="704" y2="494" stroke="#14110d" stroke-width="7"/>
          <line x1="784" y1="412" x2="784" y2="494" stroke="#14110d" stroke-width="7"/>
          <rect x="726" y="326" width="36" height="62" rx="5" fill="#f1ece1" stroke="#14110d" stroke-width="6" transform="rotate(-8 744 357)"/>
        </svg>
        """
        return {
            "url": f"data:image/svg+xml;charset=utf-8,{quote(svg)}",
            "prompt": prompt,
            "model": "atelier-svg-fallback",
            "quality": "local",
            "fallback_used": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


class GraphicNovelCorrectionService:
    """Correct overlay tasks and persist durable errata."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm_service or _safe_llm()

    def submit_attempt(
        self,
        *,
        user: User,
        scene: GraphicNovelScene,
        task_id: str,
        answer_payload: dict[str, Any],
    ) -> tuple[GraphicNovelAttempt, list[dict[str, Any]]]:
        task, panel = self._find_task(scene, task_id)
        if not task:
            raise ValueError("Unknown Feuilleton task")
        if scene.status == "available":
            scene.status = "in_progress"
        if not scene.started_at:
            scene.started_at = datetime.now(timezone.utc)

        existing_attempt = (
            self.db.query(GraphicNovelAttempt)
            .filter(
                GraphicNovelAttempt.scene_id == scene.id,
                GraphicNovelAttempt.user_id == user.id,
                GraphicNovelAttempt.task_id == task_id,
            )
            .order_by(GraphicNovelAttempt.created_at.desc())
            .first()
        )
        if existing_attempt and (existing_attempt.answer_payload or {}) == (answer_payload or {}):
            self.db.add(scene)
            self.db.commit()
            self.db.refresh(existing_attempt)
            self.db.refresh(scene)
            return existing_attempt, []

        correction = self._correct(task=task, panel=panel, answer_payload=answer_payload)
        branch_outcome = self._apply_choice_branch(user=user, scene=scene, task=task, panel=panel, answer_payload=answer_payload)
        if branch_outcome:
            correction["branch_outcome"] = branch_outcome
        attempt = GraphicNovelAttempt(
            scene_id=scene.id,
            panel_id=panel.id if panel else None,
            user_id=user.id,
            task_id=task_id,
            task_type=task.get("task_type", "unknown"),
            answer_payload=answer_payload,
            correction_payload=correction,
            verdict=correction.get("verdict", "needs_revision"),
            score_0_4=float(correction.get("score_0_4") or 0),
        )
        self.db.add(attempt)
        self.db.add(scene)
        self.db.commit()
        self.db.refresh(attempt)
        self.db.refresh(scene)

        persisted: list[dict[str, Any]] = []
        memory = ErrorMemoryService(self.db)
        for index, erratum in enumerate(correction.get("errata") or []):
            if self._is_vocabulary_erratum(erratum):
                continue
            update = memory.record_erratum(
                user=user,
                erratum=erratum,
                source_type="graphic_novel",
                concept_id=erratum.get("concept_id") or task.get("concept_id"),
                source_payload={
                    "scene_id": str(scene.id),
                    "panel_id": str(panel.id) if panel else None,
                    "task_id": task_id,
                    "erratum_index": index,
                },
            )
            if update:
                persisted.append(update)
        persisted.extend(
            self._apply_vocabulary_events(
                user=user,
                scene=scene,
                task=task,
                panel=panel,
                attempt=attempt,
                correction=correction,
            )
        )
        self.db.commit()
        return attempt, persisted

    def _apply_choice_branch(
        self,
        *,
        user: User,
        scene: GraphicNovelScene,
        task: dict[str, Any],
        panel: GraphicNovelPanel | None,
        answer_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        branch_target = task.get("branch_target") if isinstance(task.get("branch_target"), dict) else {}
        if task.get("task_type") != "choice" or not branch_target:
            return None
        selected = str(
            answer_payload.get("answer")
            or answer_payload.get("selected")
            or answer_payload.get("text")
            or task.get("expected_answer")
            or ""
        ).strip()
        branch = branch_target.get(selected)
        if not isinstance(branch, dict):
            normalized_selected = _normalize_text(selected)
            for key, value in branch_target.items():
                if _normalize_text(key) == normalized_selected and isinstance(value, dict):
                    branch = value
                    selected = str(key)
                    break
        if not isinstance(branch, dict):
            return None
        state_delta = branch.get("state_delta") if isinstance(branch.get("state_delta"), dict) else {}
        if state_delta and getattr(scene, "serial_thread_id", None):
            thread = self.db.get(SerialThread, scene.serial_thread_id)
            if thread and thread.user_id == user.id:
                current_state = dict(thread.state or {})
                current_state.update(state_delta.get("set") or {})
                thread.state = current_state
                self.db.add(thread)
        next_panel_beat = _compact_text(branch.get("next_panel_beat"), max_length=500)
        if next_panel_beat and panel:
            next_panel = (
                self.db.query(GraphicNovelPanel)
                .filter(
                    GraphicNovelPanel.scene_id == scene.id,
                    GraphicNovelPanel.panel_index == panel.panel_index + 1,
                )
                .first()
            )
            if next_panel:
                next_panel.beat = next_panel_beat
                next_panel.generation_metadata = {
                    **(next_panel.generation_metadata or {}),
                    "branch_applied": {
                        "task_id": task.get("id"),
                        "selected": selected,
                        "next_panel_beat": next_panel_beat,
                    },
                }
                self.db.add(next_panel)
                script = dict(scene.script_payload or {})
                panels = script.get("panels") if isinstance(script.get("panels"), list) else []
                for panel_payload in panels:
                    if isinstance(panel_payload, dict) and panel_payload.get("panel_index") == next_panel.panel_index:
                        panel_payload["beat"] = next_panel_beat
                script["panels"] = panels
                branch_outcomes = script.get("branch_outcomes") if isinstance(script.get("branch_outcomes"), list) else []
                branch_outcomes.append({"task_id": task.get("id"), "selected": selected, "next_panel_beat": next_panel_beat})
                script["branch_outcomes"] = branch_outcomes
                scene.script_payload = script
                self.db.add(scene)
        return {
            "selected": selected,
            "state_delta": state_delta,
            "next_panel_beat": next_panel_beat,
        }

    def _find_task(self, scene: GraphicNovelScene, task_id: str) -> tuple[dict[str, Any] | None, GraphicNovelPanel | None]:
        for panel in scene.panels or []:
            for task in (panel.overlay_payload or {}).get("tasks") or []:
                if task.get("id") == task_id:
                    return task, panel
        final_prompt = (scene.script_payload or {}).get("final_prompt") or {}
        if final_prompt.get("id") == task_id:
            return final_prompt, None
        return None, None

    @staticmethod
    def _is_vocabulary_erratum(erratum: dict[str, Any]) -> bool:
        marker = f"{erratum.get('error_category') or ''} {erratum.get('task_error_type') or ''} {erratum.get('display_label') or ''}".lower()
        return bool(erratum.get("linked_word_id")) or "vocab" in marker

    def _apply_vocabulary_events(
        self,
        *,
        user: User,
        scene: GraphicNovelScene,
        task: dict[str, Any],
        panel: GraphicNovelPanel | None,
        attempt: GraphicNovelAttempt,
        correction: dict[str, Any],
    ) -> list[dict[str, Any]]:
        events = [event for event in correction.get("vocabulary_events") or [] if isinstance(event, dict)]
        if not events:
            return []
        word_ids = _dedupe_ints([event.get("word_id") for event in events])
        words = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(word_ids)).all()
        by_id = {word.id: word for word in words}
        credit_service = VocabularyCreditService(self.db)
        persisted: list[dict[str, Any]] = []
        for event in events:
            event_ids = _dedupe_ints([event.get("word_id")])
            if not event_ids:
                continue
            word = by_id.get(event_ids[0])
            if not word:
                continue
            result = credit_service.apply(
                user=user,
                word=word,
                event_type=str(event.get("event_type") or "seen_context"),
                source_type="graphic_novel",
                learner_text=str(event.get("learner_text") or ""),
                corrected_text=word.word,
                context=str(task.get("prompt") or panel.beat if panel else task.get("prompt") or scene.title),
                explanation=str(event.get("explanation") or ""),
                repair_hint=str(event.get("repair_hint") or task.get("example_sentence") or ""),
                source_payload={
                    "scene_id": str(scene.id),
                    "panel_id": str(panel.id) if panel else None,
                    "task_id": task.get("id"),
                    "attempt_id": str(attempt.id),
                    "reason": event.get("reason"),
                },
            )
            if result.erratum_id:
                try:
                    error = self.db.get(UserError, UUID(result.erratum_id))
                except (TypeError, ValueError):
                    error = None
                if error:
                    persisted.append(serialize_error_memory(error))
        return persisted

    def _correct(
        self,
        *,
        task: dict[str, Any],
        panel: GraphicNovelPanel | None,
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        task_type = task.get("task_type")
        if task_type in {"cloze", "choice"}:
            return self._correct_closed(task=task, panel=panel, answer_payload=answer_payload)
        return self._correct_short_sentence(task=task, answer_payload=answer_payload)

    def _correct_closed(
        self,
        *,
        task: dict[str, Any],
        panel: GraphicNovelPanel | None,
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        answer = str(answer_payload.get("answer") or answer_payload.get("text") or answer_payload.get("selected") or "")
        expected = str(task.get("expected_answer") or "")
        accepted = [expected, *[str(item) for item in task.get("accepted_answers") or []]]
        is_correct = _normalize_text(answer) in {_normalize_text(item) for item in accepted if item}
        feedback = self._llm_closed_feedback(
            task=task,
            panel=panel,
            answer=answer,
            expected=expected,
            is_correct=is_correct,
        ) or self._fallback_closed_feedback(task=task, answer=answer, expected=expected, is_correct=is_correct)
        if is_correct:
            return {
                "verdict": "correct",
                "score_0_4": 4,
                "corrected_answer": expected,
                "why": feedback["why"],
                "repair": feedback.get("repair", ""),
                "errata": [],
            }
        label = feedback.get("display_label") or task.get("label") or "Feuilleton repair"
        erratum = {
            "display_label": str(label),
            "learner_text": answer,
            "corrected_target": expected,
            "why_wrong": feedback["why"],
            "repair_hint": feedback["repair"],
            "severity": 2,
            "recurring": True,
            "task_error_type": str(feedback.get("error_type") or task.get("task_type") or "graphic_novel_task"),
            "concept_id": task.get("concept_id"),
            "external_id": "",
        }
        return {
            "verdict": "needs_revision",
            "score_0_4": 1,
            "corrected_answer": expected,
            "why": erratum["why_wrong"],
            "repair": erratum["repair_hint"],
            "errata": [erratum],
        }

    def _llm_closed_feedback(
        self,
        *,
        task: dict[str, Any],
        panel: GraphicNovelPanel | None,
        answer: str,
        expected: str,
        is_correct: bool,
    ) -> dict[str, str] | None:
        if not self.llm or not hasattr(self.llm, "generate_error_detection"):
            return None
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "graphic_novel_closed_task_feedback",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "display_label": {"type": "string"},
                        "why": {"type": "string"},
                        "repair": {"type": "string"},
                    },
                    "required": ["display_label", "why", "repair"],
                },
            },
        }
        panel_payload = panel.overlay_payload if panel else {}
        payload = {
            "already_graded_verdict": "correct" if is_correct else "needs_revision",
            "task": task,
            "panel": {
                "title": panel.title if panel else "",
                "beat": panel.beat if panel else "",
                "caption": (panel_payload or {}).get("caption") or {},
                "bubbles": (panel_payload or {}).get("bubbles") or [],
            },
            "learner_answer": answer,
            "expected_answer": expected,
        }
        system = (
            "You write feedback for one closed Feuilleton exercise after deterministic grading has already happened. "
            "Do not regrade. Do not invent a different answer. Address the learner directly as 'you'. "
            "Never say 'the learner', 'the user', 'target form', 'matched the target', or 'in this panel'. "
            "Explain why the answer does or does not make the next story beat work, then connect that to the exact grammar relation. "
            "For a correct answer, give one specific why sentence and leave repair empty. "
            "For a wrong answer, give one or two why sentences and one actionable repair sentence."
        )
        try:
            result = self.llm.generate_error_detection(
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=system,
                response_format=response_format,
                temperature=0.1,
                max_tokens=450,
            )
            parsed = json.loads(result.content)
            return {
                "display_label": str(parsed.get("display_label") or task.get("label") or "Feuilleton repair").strip(),
                "why": _clean_feedback(parsed.get("why")),
                "repair": _clean_feedback(parsed.get("repair")),
            }
        except (LLMProviderError, AttributeError, json.JSONDecodeError, ValueError) as exc:
            logger.debug("Graphic novel closed-task feedback fallback", error=str(exc))
            return None

    def _fallback_closed_feedback(
        self,
        *,
        task: dict[str, Any],
        answer: str,
        expected: str,
        is_correct: bool,
    ) -> dict[str, str]:
        profile = self._closed_task_profile(task)
        label = profile["label"]
        feature = profile["feature"]
        principle = profile["principle"]
        answer_display = _answer_fragment(answer)
        expected_display = _answer_fragment(expected)
        if is_correct:
            why = f"You chose {expected_display}; {principle}"
            return {
                "display_label": label,
                "why": _feedback_sentence(why),
                "repair": "",
                "error_type": profile["error_type"],
            }
        why = f"{answer_display} does not satisfy the requested relation: {principle}"
        repair = profile["repair"]
        if expected:
            repair = f"{repair} Use {expected_display} here."
        else:
            repair = f"{repair} Revise the answer so it clearly shows {feature}."
        return {
            "display_label": label,
            "why": _feedback_sentence(why),
            "repair": _feedback_sentence(repair),
            "error_type": profile["error_type"],
        }

    def _closed_task_profile(self, task: dict[str, Any]) -> dict[str, str]:
        label = str(task.get("label") or "Feuilleton repair").strip()
        task_text = _task_context_text(task)
        concept = self._task_concept(task)
        feature = _feature_summary(task)
        profile = infer_grammar_profile(concept, task_text=task_text, feature=feature, label=label)
        return {
            "label": label or profile.label,
            "feature": feature,
            "principle": profile.principle,
            "repair": profile.repair,
            "error_type": profile.key,
        }

    def _task_concept(self, task: dict[str, Any]) -> GrammarConcept | None:
        concept_id = task.get("concept_id")
        if not concept_id:
            return None
        try:
            return self.db.get(GrammarConcept, int(concept_id))
        except (TypeError, ValueError):
            return None

    def _correct_short_sentence(self, *, task: dict[str, Any], answer_payload: dict[str, Any]) -> dict[str, Any]:
        text = str(answer_payload.get("answer") or answer_payload.get("text") or "").strip()
        feature = _feature_summary(task)
        vocabulary_item = self._vocabulary_task_item(task)

        def finish(
            result: dict[str, Any],
            *,
            event_type: str | None = None,
            reason: str | None = None,
        ) -> dict[str, Any]:
            if not vocabulary_item:
                return result
            if event_type:
                return self._with_vocabulary_event(
                    result,
                    item=vocabulary_item,
                    event_type=event_type,
                    reason=reason or event_type,
                    learner_text=text,
                )
            if text and self._answer_contains_vocabulary(text, vocabulary_item) and not self._has_vocabulary_erratum(result):
                return self._with_vocabulary_event(
                    result,
                    item=vocabulary_item,
                    event_type="produced_correct",
                    reason="target_vocabulary_used",
                    learner_text=text,
                )
            return result

        if not text:
            requirement = f" that uses {feature}" if feature and feature != "the requested feature" else ""
            return finish({
                "verdict": "needs_revision",
                "score_0_4": 0,
                "corrected_answer": "",
                "why": "You did not write a sentence, so there is nothing to review.",
                "repair": f"Write one short French sentence{requirement} and continues the panel.",
                "errata": [
                    {
                        "display_label": "Missing Feuilleton answer",
                        "learner_text": "",
                        "corrected_target": f"Write one short French sentence{requirement}.",
                        "why_wrong": "You did not write a sentence, so there is nothing to review.",
                        "repair_hint": f"Write one short French sentence{requirement} and continues the panel.",
                        "severity": 1,
                        "recurring": False,
                        "task_error_type": "task_compliance",
                        "concept_id": task.get("concept_id"),
                        "external_id": "",
                    }
                ],
            }, event_type="missed_target" if vocabulary_item else None, reason="empty_vocabulary_task")

        if vocabulary_item and not self._answer_contains_vocabulary(text, vocabulary_item):
            erratum = self._vocabulary_task_erratum(item=vocabulary_item, learner_text=text, reason="missing_target")
            return finish({
                "verdict": "partial",
                "score_0_4": 2,
                "corrected_answer": erratum["corrected_target"],
                "why": erratum["why_wrong"],
                "repair": erratum["repair_hint"],
                "errata": [erratum],
            }, event_type="missed_target", reason="missing_target")

        llm_result = self._llm_short_sentence(task=task, text=text)
        if llm_result:
            return finish(llm_result)
        normalized = _normalize_text(text)
        if _task_requires_si_frame(task):
            has_si = bool(re.search(r"\bsi\b|s'il|s elle|s il", normalized))
            has_result = any(token in normalized for token in ("rai", "ras", "ra", "rons", "rez", "ront", "prends", "mange", "viens"))
            if has_si and has_result:
                return finish({
                    "verdict": "accepted",
                    "score_0_4": 3,
                    "corrected_answer": text,
                    "why": "You used a si-clause and gave the condition a future or imperative consequence.",
                    "repair": "",
                    "errata": [],
                })
            erratum = {
                "display_label": "Si frame in context",
                "learner_text": text,
                "corrected_target": "Si je pars maintenant, j'arriverai à l'heure.",
                "why_wrong": "Your sentence does not clearly use the si + present frame that this task asks for.",
                "repair_hint": "Start with si plus a present-tense condition, then add what will happen or what someone should do.",
                "severity": 2,
                "recurring": True,
                "task_error_type": "si_clause_frame",
                "concept_id": task.get("concept_id"),
                "external_id": "",
            }
            return finish({
                "verdict": "partial",
                "score_0_4": 2,
                "corrected_answer": erratum["corrected_target"],
                "why": erratum["why_wrong"],
                "repair": erratum["repair_hint"],
                "errata": [erratum],
            })
        words = re.findall(r"[a-zàâçéèêëîïôûùüÿñæœ'-]+", normalized, flags=re.IGNORECASE)
        french_markers = {
            "je",
            "tu",
            "il",
            "elle",
            "nous",
            "vous",
            "ils",
            "elles",
            "le",
            "la",
            "les",
            "un",
            "une",
            "des",
            "du",
            "de",
            "que",
            "qui",
            "dans",
            "avec",
            "pour",
            "mais",
            "puis",
            "est",
            "sont",
            "a",
            "ont",
        }
        if len(words) >= 4 and any(word in french_markers for word in words):
            return finish({
                "verdict": "accepted",
                "score_0_4": 3,
                "corrected_answer": text,
                "why": f"You wrote a usable French continuation and touched the requested area: {feature}.",
                "repair": "",
                "errata": [],
            })
        corrected = str(task.get("expected_answer") or task.get("example_answer") or "Le dossier continue, mais la scène reste lisible.").strip()
        erratum = {
            "display_label": "Short sentence in context",
            "learner_text": text,
            "corrected_target": corrected,
            "why_wrong": f"Your answer is not yet a clear French sentence for the requested beat: {feature}.",
            "repair_hint": "Write a complete French sentence that continues the scene before worrying about style.",
            "severity": 2,
            "recurring": False,
            "task_error_type": "short_sentence_context",
            "concept_id": task.get("concept_id"),
            "external_id": "",
        }
        return finish({
            "verdict": "partial",
            "score_0_4": 2,
            "corrected_answer": erratum["corrected_target"],
            "why": erratum["why_wrong"],
            "repair": erratum["repair_hint"],
            "errata": [erratum],
        })

    def _vocabulary_task_item(self, task: dict[str, Any]) -> dict[str, Any] | None:
        if not task.get("vocabulary_task") and not task.get("target_word_id"):
            return None
        word_ids = _dedupe_ints([task.get("target_word_id")])
        if not word_ids:
            return None
        return {
            "word_id": word_ids[0],
            "word": str(task.get("target_word") or task.get("expected_answer") or "").strip(),
            "translation": str(
                task.get("target_translation")
                or task.get("target_word_translation")
                or task.get("translation")
                or ""
            ).strip(),
            "example_sentence": str(task.get("example_sentence") or "").strip(),
            "example_translation": str(task.get("example_translation") or "").strip(),
        }

    def _answer_contains_vocabulary(self, text: str, item: dict[str, Any]) -> bool:
        normalized_text = _normalize_text(text)
        for form in (item.get("word"), item.get("normalized_word")):
            normalized_form = _normalize_text(form)
            if not normalized_form:
                continue
            if " " in normalized_form and f" {normalized_form} " in f" {normalized_text} ":
                return True
            if normalized_form in set(normalized_text.split()):
                return True
        return False

    def _has_vocabulary_erratum(self, result: dict[str, Any]) -> bool:
        return any(self._is_vocabulary_erratum(item) for item in result.get("errata") or [])

    def _vocabulary_task_erratum(
        self,
        *,
        item: dict[str, Any],
        learner_text: str,
        reason: str,
    ) -> dict[str, Any]:
        word = str(item.get("word") or "target word").strip()
        translation = str(item.get("translation") or "").strip()
        example = str(item.get("example_sentence") or "").strip()
        why = f"This Feuilleton task asked you to use {word}, but your sentence avoided the target word."
        repair = f"Write a fresh in-world sentence that includes {word}."
        if translation:
            repair = f"{repair} Meaning: {translation}."
        if example:
            repair = f"{repair} Pattern to borrow: {example}"
        return {
            "display_label": f"Use target word: {word}",
            "learner_text": learner_text,
            "corrected_target": word,
            "why_wrong": why,
            "repair_hint": repair,
            "severity": 2,
            "recurring": True,
            "task_error_type": "vocabulary_missing_target" if reason == "missing_target" else "vocabulary_incorrect_use",
            "concept_id": None,
            "external_id": f"VOCAB_{item.get('word_id')}",
            "error_category": "vocabulary",
            "linked_word_id": item.get("word_id"),
        }

    def _with_vocabulary_event(
        self,
        result: dict[str, Any],
        *,
        item: dict[str, Any],
        event_type: str,
        reason: str,
        learner_text: str,
    ) -> dict[str, Any]:
        events = list(result.get("vocabulary_events") or [])
        word_id = item.get("word_id")
        if word_id and not any(event.get("word_id") == word_id and event.get("event_type") == event_type for event in events):
            events.append(
                {
                    "word_id": word_id,
                    "event_type": event_type,
                    "reason": reason,
                    "learner_text": learner_text,
                    "explanation": result.get("why") or "",
                    "repair_hint": result.get("repair") or item.get("example_sentence") or "",
                }
            )
        return {**result, "vocabulary_events": events}

    def _llm_short_sentence(self, *, task: dict[str, Any], text: str) -> dict[str, Any] | None:
        if not self.llm or not hasattr(self.llm, "generate_error_detection"):
            return None
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "graphic_novel_short_sentence_correction",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "verdict": {"type": "string", "enum": ["accepted", "partial", "needs_revision"]},
                        "score_0_4": {"type": "number"},
                        "corrected_answer": {"type": "string"},
                        "why": {"type": "string"},
                        "repair": {"type": "string"},
                        "errata": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "display_label": {"type": "string"},
                                    "learner_text": {"type": "string"},
                                    "corrected_target": {"type": "string"},
                                    "why_wrong": {"type": "string"},
                                    "repair_hint": {"type": "string"},
                                    "severity": {"type": "integer"},
                                    "recurring": {"type": "boolean"},
                                    "task_error_type": {"type": "string"},
                                    "external_id": {"type": "string"},
                                },
                                "required": [
                                    "display_label",
                                    "learner_text",
                                    "corrected_target",
                                    "why_wrong",
                                    "repair_hint",
                                    "severity",
                                    "recurring",
                                    "task_error_type",
                                    "external_id",
                                ],
                            },
                        },
                    },
                    "required": ["verdict", "score_0_4", "corrected_answer", "why", "repair", "errata"],
                },
            },
        }
        system = (
            "You correct one short French sentence in a graphic-novel grammar exercise. "
            "Address the learner directly as 'you'. Never say 'the learner' or 'the user'. "
            "Only enforce grammar requirements that are explicitly present in task.instruction, task.expected_features, "
            "or task.label. If the task does not explicitly ask for a si-clause, do not criticize the answer for missing one. "
            "Feedback must explain the exact grammar relation, not generic target-form advice."
        )
        payload = {"task": task, "learner_text": text}
        try:
            result = self.llm.generate_error_detection(
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=system,
                response_format=response_format,
                temperature=0.1,
                max_tokens=900,
            )
            parsed = json.loads(result.content)
            parsed["why"] = _clean_feedback(parsed.get("why"))
            parsed["repair"] = _clean_feedback(parsed.get("repair"))
            parsed["errata"] = [
                {
                    **item,
                    "why_wrong": _clean_feedback(item.get("why_wrong")),
                    "repair_hint": _clean_feedback(item.get("repair_hint")),
                    "concept_id": task.get("concept_id"),
                }
                for item in parsed.get("errata") or []
            ]
            return parsed
        except (LLMProviderError, AttributeError, json.JSONDecodeError, ValueError) as exc:
            logger.debug("Graphic novel correction fallback", error=str(exc))
            return None

def serialize_panel(panel: GraphicNovelPanel) -> dict[str, Any]:
    return {
        "id": str(panel.id),
        "panel_index": panel.panel_index,
        "title": panel.title,
        "beat": panel.beat,
        "image_prompt": panel.image_prompt,
        "image_url": panel.image_url,
        "image_payload": panel.image_payload or {},
        "overlay_payload": panel.overlay_payload or {},
        "generation_metadata": panel.generation_metadata or {},
        "created_at": panel.created_at.isoformat() if panel.created_at else None,
    }


def serialize_attempt(attempt: GraphicNovelAttempt) -> dict[str, Any]:
    return {
        "id": str(attempt.id),
        "scene_id": str(attempt.scene_id),
        "panel_id": str(attempt.panel_id) if attempt.panel_id else None,
        "task_id": attempt.task_id,
        "task_type": attempt.task_type,
        "answer_payload": attempt.answer_payload or {},
        "correction": attempt.correction_payload or {},
        "verdict": attempt.verdict,
        "score_0_4": attempt.score_0_4,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }


def serialize_scene(scene: GraphicNovelScene | None, *, include_children: bool = True) -> dict[str, Any] | None:
    if not scene:
        return None
    payload = {
        "id": str(scene.id),
        "status": scene.status,
        "cadence": scene.cadence,
        "atelier_session_id": str(scene.atelier_session_id) if scene.atelier_session_id else None,
        "mission_id": str(scene.mission_id) if scene.mission_id else None,
        "serial_thread_id": str(scene.serial_thread_id) if getattr(scene, "serial_thread_id", None) else None,
        "episode_index": scene.episode_index,
        "personal_input_item_id": str(scene.personal_input_item_id) if scene.personal_input_item_id else None,
        "title": scene.title,
        "brief": scene.brief,
        "selected_concept_ids": scene.selected_concept_ids or [],
        "target_errata_ids": scene.target_errata_ids or [],
        "target_vocabulary_ids": scene.target_vocabulary_ids or [],
        "target_vocabulary": (scene.script_payload or {}).get("target_vocabulary") or [],
        "source_snapshot": scene.source_snapshot or {},
        "script_payload": scene.script_payload or {},
        "hook": (scene.script_payload or {}).get("hook") or (scene.recap_payload or {}).get("hook") or {},
        "recap": scene.recap_payload or {},
        "cache_key": scene.cache_key,
        "prompt_version": scene.prompt_version,
        "image_model": scene.image_model,
        "image_quality": scene.image_quality,
        "created_at": scene.created_at.isoformat() if scene.created_at else None,
        "started_at": scene.started_at.isoformat() if scene.started_at else None,
        "completed_at": scene.completed_at.isoformat() if scene.completed_at else None,
    }
    if include_children:
        payload["panels"] = [serialize_panel(panel) for panel in sorted(scene.panels or [], key=lambda item: item.panel_index)]
        payload["attempts"] = [
            serialize_attempt(attempt) for attempt in sorted(scene.attempts or [], key=lambda item: item.created_at)
        ]
    return payload


__all__ = [
    "GRAPHIC_NOVEL_PROMPT_VERSION",
    "GraphicNovelCorrectionService",
    "GraphicNovelImageService",
    "GraphicNovelScheduler",
    "GraphicNovelScriptGenerator",
    "GraphicNovelStoryGenerator",
    "serialize_attempt",
    "serialize_panel",
    "serialize_scene",
]
