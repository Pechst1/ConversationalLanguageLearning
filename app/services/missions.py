"""Real-world scenario mission services."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.atelier import AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.vocabulary import VocabularyWord
from app.db.models.user import User
from app.services.atelier_assets import AtelierAssetService
from app.services.error_memory import ErrorMemoryService, serialize_error_memory
from app.services.llm_service import LLMProviderError, LLMService
from app.services.news_service import NewsService
from app.services.progress import ProgressService
from app.services.serial_arc_planner import cefr_generation_profile
from app.services.vocabulary_credit import VocabularyCreditService


MISSION_CORRECTION_PROMPT_VERSION = "mission-correction-v1"
MISSION_FAST_CORRECTION_PROMPT_VERSION = "mission-correction-fast-v1"
MISSION_TEMPLATES = ("message", "explain_plan", "news_summary", "travel_work", "conversation")


MISSION_CORRECTION_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "real_world_mission_correction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "verdict": {"type": "string", "enum": ["accepted", "partial", "needs_revision"]},
                "score_0_4": {"type": "number"},
                "corrected_answer": {"type": "string"},
                "objective_progress": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "met": {"type": "boolean"},
                            "note": {"type": "string"},
                        },
                        "required": ["id", "label", "met", "note"],
                    },
                },
                "concept_hits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "external_id": {"type": "string"},
                            "label": {"type": "string"},
                            "detected_count": {"type": "integer"},
                            "target_count": {"type": "integer"},
                        },
                        "required": ["external_id", "label", "detected_count", "target_count"],
                    },
                },
                "missing_targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "external_id": {"type": "string"},
                            "label": {"type": "string"},
                            "detected_count": {"type": "integer"},
                            "target_count": {"type": "integer"},
                            "missing_count": {"type": "integer"},
                        },
                        "required": ["external_id", "label", "detected_count", "target_count", "missing_count"],
                    },
                },
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
                "vocabulary_links": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "learner_text": {"type": "string"},
                            "target": {"type": "string"},
                            "translation": {"type": "string"},
                        },
                        "required": ["learner_text", "target", "translation"],
                    },
                },
            },
            "required": [
                "verdict",
                "score_0_4",
                "corrected_answer",
                "objective_progress",
                "concept_hits",
                "missing_targets",
                "errata",
                "vocabulary_links",
            ],
        },
    },
}


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
    return cleaned


def _concept_title(concept: GrammarConcept, asset_service: AtelierAssetService | None = None) -> str:
    if asset_service:
        try:
            blueprint = asset_service.approved_blueprint_payload(concept)
            title = blueprint.get("display_title")
            if title:
                return str(title)
        except Exception:
            pass
    return concept.name


def _source_ids(rows: list[Any]) -> list[str]:
    return [str(row.id) for row in rows if getattr(row, "id", None)]


def _dedupe_ints(values: list[Any]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value is None:
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number in seen:
            continue
        seen.add(number)
        result.append(number)
    return result


def _compact_text(value: Any, *, max_length: int = 800) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_length]


def _normalize_phrase(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


class MissionGenerator:
    """Create realistic mission briefs from concepts, errata, vocabulary, and news."""

    def __init__(self, db: Session, news_service: NewsService | None = None) -> None:
        self.db = db
        self.news_service = news_service or NewsService()

    async def build_payload(
        self,
        *,
        user: User,
        mission_type: str,
        cadence: str,
        atelier_session: AtelierSession | None = None,
        preferred_concept_ids: list[int] | None = None,
        preferred_errata_ids: list[UUID] | None = None,
        preferred_vocabulary_ids: list[int] | None = None,
        use_news: bool = True,
        custom_context: dict[str, Any] | None = None,
        stakes_level: int | None = None,
    ) -> dict[str, Any]:
        mission_type = mission_type if mission_type in MISSION_TEMPLATES else "message"
        custom_context = self._custom_context(custom_context)
        stakes_level = self._stakes_level(stakes_level, cadence=cadence)
        concepts = self._select_concepts(
            user=user,
            atelier_session=atelier_session,
            preferred_concept_ids=preferred_concept_ids,
            limit=3,
        )
        errata = self._select_errata(user=user, preferred_errata_ids=preferred_errata_ids, limit=3)
        vocabulary = self._select_vocabulary(user=user, preferred_vocabulary_ids=preferred_vocabulary_ids, limit=4)
        source_snapshot = await self._source_snapshot(
            user=user,
            mission_type=mission_type,
            use_news=use_news,
        )
        objectives = self._objectives(
            mission_type=mission_type,
            concepts=concepts,
            errata=errata,
            vocabulary=vocabulary,
            source_snapshot=source_snapshot,
            stakes_level=stakes_level,
        )
        title, brief = self._brief(mission_type=mission_type, cadence=cadence, source_snapshot=source_snapshot, concepts=concepts)
        messenger = self._messenger_payload(mission_type=mission_type, source_snapshot=source_snapshot, concepts=concepts)
        if vocabulary:
            messenger = self._with_vocabulary_focus(messenger, vocabulary)
        if custom_context:
            title, brief, messenger, custom_objectives = self._customize_mission(
                mission_type=mission_type,
                title=title,
                brief=brief,
                messenger=messenger,
                custom_context=custom_context,
                concepts=concepts,
            )
            objectives = [*custom_objectives, *objectives]
        conversation_opening = messenger.get("opening_message") or self._conversation_opening(
            mission_type=mission_type,
            source_snapshot=source_snapshot,
        )
        prompt_payload = {
            "version": "real-world-mission-v2",
            "mission_type": mission_type,
            "cadence": cadence,
            "stakes_level": stakes_level,
            "experience": "reality_messenger",
            "custom_context": custom_context,
            "messenger": messenger,
            "conversation_opening": conversation_opening,
            "conversation_title": self._conversation_title(mission_type),
            "conversation_instruction": self._conversation_instruction(mission_type),
            "writing_title": self._writing_title(mission_type),
            "writing_instruction": self._writing_instruction(mission_type),
            "writing_placeholder": self._placeholder(mission_type),
            "min_words": max(
                self._min_words(mission_type=mission_type, stakes_level=stakes_level),
                int(cefr_generation_profile(user.proficiency_level).get("min_words") or 0),
            ),
            "max_words": self._max_words(stakes_level=stakes_level),
            "target_register": "natural French; formal only when the scenario requires it",
            "show_source_context": mission_type == "news_summary",
            "source_context_card": self._source_context_card(source_snapshot) if mission_type == "news_summary" else None,
            "branching": {
                "enabled": True,
                "signals": ["understood", "needs_detail", "too_vague", "tone_mismatch"],
                "stakes_level": stakes_level,
                "tone_failures_matter": stakes_level >= 3,
            },
            "target_vocabulary": vocabulary,
        }
        target_vocabulary_ids = [item["word_id"] for item in vocabulary]
        target_vocabulary_ids.extend(error.linked_word_id for error in errata if error.linked_word_id)
        return {
            "title": title,
            "brief": brief,
            "selected_concept_ids": [concept.id for concept in concepts],
            "target_errata_ids": _source_ids(errata),
            "target_vocabulary_ids": _dedupe_ints(target_vocabulary_ids),
            "source_snapshot": source_snapshot,
            "objectives": objectives,
            "prompt_payload": prompt_payload,
            "stakes_level": stakes_level,
        }

    @staticmethod
    def _stakes_level(value: int | None, *, cadence: str) -> int:
        if value is not None:
            try:
                return max(1, min(3, int(value)))
            except (TypeError, ValueError):
                return 1
        if cadence == "post_session":
            return 2
        return 1

    @staticmethod
    def _min_words(*, mission_type: str, stakes_level: int) -> int:
        base = 35 if mission_type == "message" else 50
        return base + {1: 0, 2: 20, 3: 40}.get(stakes_level, 0)

    @staticmethod
    def _max_words(*, stakes_level: int) -> int:
        return {1: 150, 2: 190, 3: 230}.get(stakes_level, 150)

    def _select_concepts(
        self,
        *,
        user: User,
        atelier_session: AtelierSession | None,
        preferred_concept_ids: list[int] | None,
        limit: int,
    ) -> list[GrammarConcept]:
        concept_ids: list[int] = []
        ordered: list[GrammarConcept] = []
        seen: set[int] = set()
        if preferred_concept_ids:
            preferred_ids = [int(item) for item in preferred_concept_ids if item]
            preferred_rows = self.db.query(GrammarConcept).filter(GrammarConcept.id.in_(preferred_ids)).all()
            by_id = {row.id: row for row in preferred_rows}
            for concept_id in preferred_ids:
                concept = by_id.get(concept_id)
                if concept and concept.id not in seen:
                    ordered.append(concept)
                    seen.add(concept.id)
                if len(ordered) >= limit:
                    return ordered
            concept_ids.extend(preferred_ids)
        if atelier_session:
            concept_ids.extend(int(item) for item in (atelier_session.selected_concept_ids or []) if item)
        for error in ErrorMemoryService(self.db).due_error_records(user, limit=limit):
            if error.concept_id:
                concept_ids.append(error.concept_id)
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
            preferred = (
                self.db.query(UserError)
                .filter(UserError.user_id == user.id, UserError.id.in_(preferred_errata_ids))
                .all()
            )
            by_id = {row.id: row for row in preferred}
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
        preferred_vocabulary_ids: list[int] | None = None,
        limit: int,
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        seen_word_ids: set[int] = set()

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
            translation = (
                _compact_text(item.get("translation"), max_length=90)
                or _compact_text(translations.get("de"), max_length=90)
                or _compact_text(translations.get("en"), max_length=90)
                or _compact_text(translations.get("fr"), max_length=90)
            )
            selected.append(
                {
                    "word_id": word_id,
                    "word": word,
                    "translation": translation,
                    "bucket": item.get("bucket") or "due",
                    "scheduler": item.get("scheduler") or "fsrs",
                    "priority_score": item.get("priority_score") or 0,
                }
            )
            seen_word_ids.add(word_id)

        preferred_ids = _dedupe_ints(preferred_vocabulary_ids or [])
        if preferred_ids:
            rows = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(preferred_ids)).all()
            by_id = {row.id: row for row in rows}
            for word_id in preferred_ids:
                word = by_id.get(word_id)
                if not word:
                    continue
                add_item(
                    {
                        "word_id": word.id,
                        "word": word.word,
                        "translation": word.german_translation or word.english_translation or word.french_translation,
                        "translations": {
                            "de": word.german_translation,
                            "en": word.english_translation,
                            "fr": word.french_translation,
                        },
                        "bucket": "preferred",
                        "scheduler": "explicit",
                        "priority_score": 1.0,
                    }
                )

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

    @staticmethod
    def _with_vocabulary_focus(messenger: dict[str, Any], vocabulary: list[dict[str, Any]]) -> dict[str, Any]:
        words = [str(item.get("word") or "").strip() for item in vocabulary[:3] if item.get("word")]
        if not words:
            return messenger
        focus_label = ", ".join(words)
        quick_replies = list(messenger.get("quick_replies") or [])
        quick_replies.append(f"Je peux utiliser: {focus_label}...")
        realism_rules = list(messenger.get("realism_rules") or [])
        realism_rules.append(f"Reuse one of today's vocabulary words naturally: {focus_label}.")
        return {
            **messenger,
            "quick_replies": quick_replies[:4],
            "realism_rules": realism_rules,
            "vocabulary_focus": vocabulary,
        }

    def _custom_context(self, value: dict[str, Any] | None) -> dict[str, Any]:
        scenario = _compact_text((value or {}).get("scenario"), max_length=1200)
        if not scenario:
            return {}
        desired_outcome = _compact_text((value or {}).get("desired_outcome"), max_length=400)
        relationship = _compact_text((value or {}).get("relationship"), max_length=120)
        register = _compact_text((value or {}).get("register"), max_length=80)
        return {
            "scenario": scenario,
            "desired_outcome": desired_outcome,
            "relationship": relationship,
            "register": register or self._infer_register(scenario=scenario, relationship=relationship),
            "source": "learner_custom",
        }

    def _customize_mission(
        self,
        *,
        mission_type: str,
        title: str,
        brief: str,
        messenger: dict[str, Any],
        custom_context: dict[str, Any],
        concepts: list[GrammarConcept],
    ) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
        scenario = custom_context["scenario"]
        relationship = custom_context.get("relationship") or self._infer_relationship(scenario)
        register = custom_context.get("register") or self._infer_register(scenario=scenario, relationship=relationship)
        outcome = custom_context.get("desired_outcome") or self._infer_outcome(scenario)
        contact = self._custom_contact(relationship=relationship, scenario=scenario)
        scene_anchor = self._custom_scene_anchor(scenario)
        grammar_hint = self._grammar_goal(concepts)
        custom_messenger = {
            **messenger,
            **contact,
            "channel_label": "Custom reality mission",
            "thread_title": f"{contact['contact_name']} · {self._thread_topic(scenario)}",
            "scene_anchor": scene_anchor,
            "dispatch_note": f"Make this usable for your real situation: {outcome}",
            "inbox_context": scenario,
            "opening_message": self._custom_opening(
                relationship=relationship,
                register=register,
                outcome=outcome,
                scenario=scenario,
            ),
            "ambient_cues": self._custom_cues(scenario=scenario, register=register),
            "quick_replies": self._custom_quick_replies(register=register, mission_type=mission_type),
            "success_signal": outcome,
            "realism_rules": [
                f"Use a {register} register.",
                "Name the practical constraint before asking for help.",
                grammar_hint,
            ],
        }
        custom_title = f"Real Mission: {self._thread_topic(scenario)}"
        custom_brief = (
            f"You asked to practise this real situation: {scenario} "
            f"Your target outcome: {outcome} Keep the French natural, specific, and register-aware."
        )
        objectives = [
            {
                "id": "custom_real_life_outcome",
                "label": f"Achieve: {outcome}",
                "target_count": 1,
                "kind": "pragmatics",
                "required": True,
            },
            {
                "id": "custom_register",
                "label": f"Use a {register} register with {relationship}",
                "target_count": 1,
                "kind": "register",
                "required": True,
            },
        ]
        return custom_title or title, custom_brief or brief, custom_messenger, objectives

    def _infer_relationship(self, scenario: str) -> str:
        marker = scenario.lower()
        if any(token in marker for token in ("landlord", "owner", "apartment", "heating", "rent")):
            return "landlord"
        if any(token in marker for token in ("boss", "manager", "colleague", "work", "client")):
            return "work contact"
        if any(token in marker for token in ("doctor", "pharmacy", "appointment", "medical")):
            return "health professional"
        if any(token in marker for token in ("teacher", "professor", "school", "university")):
            return "teacher"
        if any(token in marker for token in ("friend", "parents", "family", "dinner", "date")):
            return "friend or host"
        return "local contact"

    def _infer_register(self, *, scenario: str, relationship: str) -> str:
        marker = f"{scenario} {relationship}".lower()
        if any(token in marker for token in ("friend", "family", "date", "text my partner")):
            return "warm informal"
        if any(token in marker for token in ("landlord", "doctor", "admin", "office", "client", "teacher", "manager", "boss")):
            return "polite formal"
        return "polite neutral"

    def _infer_outcome(self, scenario: str) -> str:
        marker = scenario.lower()
        if "heating" in marker or "broken" in marker or "repair" in marker:
            return "The other person understands the problem and agrees on a next step."
        if "delay" in marker or "late" in marker:
            return "They understand the delay and know when to expect you."
        if "appointment" in marker or "booking" in marker or "reservation" in marker:
            return "The appointment or booking is confirmed without ambiguity."
        if "parents" in marker or "dinner" in marker:
            return "You sound considerate, prepared, and easy to respond to."
        return "The other person knows what happened, what you need, and what to do next."

    def _custom_contact(self, *, relationship: str, scenario: str) -> dict[str, Any]:
        marker = f"{relationship} {scenario}".lower()
        if "landlord" in marker:
            return {"contact_name": "Mme Laurent", "contact_role": "landlord", "contact_initials": "ML", "presence": "usually replies in the evening"}
        if any(token in marker for token in ("boss", "manager", "colleague", "client", "work")):
            return {"contact_name": "Nadia", "contact_role": relationship, "contact_initials": "NA", "presence": "at work now"}
        if any(token in marker for token in ("doctor", "pharmacy", "medical")):
            return {"contact_name": "Cabinet Martin", "contact_role": relationship, "contact_initials": "CM", "presence": "desk open until 18:30"}
        if any(token in marker for token in ("parents", "family", "dinner", "host")):
            return {"contact_name": "Claire", "contact_role": relationship, "contact_initials": "CL", "presence": "planning tonight"}
        return {"contact_name": "Camille", "contact_role": relationship, "contact_initials": "CA", "presence": "available now"}

    def _thread_topic(self, scenario: str) -> str:
        words = [word for word in re.findall(r"[A-Za-zÀ-ÿ']+", scenario) if len(word) > 3]
        stop = {"need", "want", "about", "with", "that", "this", "text", "message", "french", "please"}
        topic = " ".join(word for word in words if word.lower() not in stop)[:34].strip()
        return topic or "real situation"

    def _custom_scene_anchor(self, scenario: str) -> str:
        marker = scenario.lower()
        if any(token in marker for token in ("heating", "apartment", "landlord")):
            return "At home, before sending a message that needs a concrete response"
        if any(token in marker for token in ("work", "colleague", "client", "boss")):
            return "Work chat, with someone waiting for a clear update"
        if any(token in marker for token in ("station", "train", "airport", "hotel")):
            return "On the move, with one practical constraint"
        if any(token in marker for token in ("dinner", "parents", "family")):
            return "Before a social moment where tone matters"
        return "A real-life moment where clarity and tone both matter"

    def _custom_opening(self, *, relationship: str, register: str, outcome: str, scenario: str) -> str:
        if "formal" in register:
            return f"Bonjour, expliquez-moi la situation clairement. Quel résultat souhaitez-vous obtenir ?"
        if "informal" in register:
            return f"D'accord, raconte-moi vite la situation. Qu'est-ce que tu veux obtenir exactement ?"
        return f"D'accord, explique-moi le contexte. Le but, c'est bien: {outcome}"

    def _custom_cues(self, *, scenario: str, register: str) -> list[str]:
        cues = [f"{register} register", "real person on the other side", "one concrete next step"]
        marker = scenario.lower()
        if "urgent" in marker or "today" in marker:
            cues[2] = "time pressure today"
        if "angry" in marker or "complain" in marker:
            cues[0] = "firm but calm tone"
        return cues

    def _custom_quick_replies(self, *, register: str, mission_type: str) -> list[str]:
        if "formal" in register:
            return [
                "Bonjour, je vous contacte parce que...",
                "Serait-il possible de...",
                "Je vous remercie par avance...",
            ]
        if "informal" in register:
            return [
                "Coucou, je voulais te dire que...",
                "Est-ce que ça te va si...",
                "Merci, ça m'aiderait beaucoup...",
            ]
        if mission_type == "conversation":
            return [
                "Je voudrais expliquer la situation...",
                "Le point important, c'est que...",
                "Qu'est-ce que vous me conseillez ?",
            ]
        return [
            "Bonjour, je voulais vous prévenir que...",
            "Le plus important, c'est que...",
            "Est-ce que vous pourriez me confirmer...",
        ]

    async def _source_snapshot(self, *, user: User, mission_type: str, use_news: bool) -> dict[str, Any]:
        if mission_type != "news_summary":
            return {
                "mode": "none",
                "digest": "",
                "items": [],
                "source_policy": "No live source context is needed for this mission type.",
            }
        if not use_news:
            return {
                "mode": "curated_prompt",
                "digest": "Paris is preparing for a busy week of transport, work, and cultural events. Use this as a neutral current-affairs prompt rather than a live article.",
                "items": [
                    {
                        "title": "Curated France scenario",
                        "summary": "A fixed France-focused context used when live news is disabled.",
                        "source": "Atelier curated fallback",
                        "url": "",
                    }
                ],
                "source_policy": "Curated prompt; live news disabled for this news mission.",
            }
        interests = [item.strip() for item in (user.interests or "").split(",") if item.strip()]
        return await self.news_service.fetch_france_context(interests=interests, limit=3)

    def _objectives(
        self,
        *,
        mission_type: str,
        concepts: list[GrammarConcept],
        errata: list[UserError],
        vocabulary: list[dict[str, Any]],
        source_snapshot: dict[str, Any],
        stakes_level: int = 1,
    ) -> list[dict[str, Any]]:
        asset_service = AtelierAssetService(self.db)
        concept_limit = 3
        errata_limit = 2
        vocabulary_limit = 3
        objectives = [
            {
                "id": "real_world_task",
                "label": self._task_label(mission_type),
                "target_count": 1,
                "kind": "communication",
                "required": True,
                "stakes_level": stakes_level,
            }
        ]
        if stakes_level >= 2:
            objectives.append(
                {
                    "id": "follow_up_move",
                    "label": "Make the next step explicit enough that the other person can act",
                    "target_count": 1,
                    "kind": "pragmatics",
                    "required": stakes_level >= 3,
                    "stakes_level": stakes_level,
                }
            )
        if stakes_level >= 3:
            objectives.append(
                {
                    "id": "register_pressure",
                    "label": "Keep the register precise under pressure",
                    "target_count": 1,
                    "kind": "register",
                    "required": True,
                    "stakes_level": stakes_level,
                }
            )
        for index, concept in enumerate(concepts[:concept_limit], start=1):
            objectives.append(
                {
                    "id": f"concept_{concept.id}",
                    "label": f"Use {index} clear instance of {_concept_title(concept, asset_service)}",
                    "target_count": 1,
                    "kind": "grammar",
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                    "required": False,
                }
            )
        for error in errata[:errata_limit]:
            objectives.append(
                {
                    "id": f"erratum_{error.id}",
                    "label": f"Repair: {error.display_label or error.error_pattern or 'remembered mistake'}",
                    "target_count": 1,
                    "kind": error.review_mode or "grammar",
                    "error_id": str(error.id),
                    "concept_id": error.concept_id,
                    "required": False,
                }
            )
        for item in vocabulary[:vocabulary_limit]:
            objectives.append(
                {
                    "id": f"vocabulary_{item['word_id']}",
                    "label": f"Use {item['word']} naturally",
                    "target_count": 1,
                    "kind": "vocabulary",
                    "word_id": item["word_id"],
                    "translation": item.get("translation"),
                    "bucket": item.get("bucket"),
                    "required": False,
                }
            )
        if mission_type == "news_summary" and source_snapshot.get("items"):
            objectives.append(
                {
                    "id": "source_context",
                    "label": "Use one attributed detail from the news card",
                    "target_count": 1,
                    "kind": "source",
                    "required": False,
                }
            )
        return objectives

    def _brief(
        self,
        *,
        mission_type: str,
        cadence: str,
        source_snapshot: dict[str, Any],
        concepts: list[GrammarConcept],
    ) -> tuple[str, str]:
        first_source = ((source_snapshot.get("items") or [{}])[0] or {}).get("title", "")
        grammar_goal = self._grammar_goal(concepts)
        if mission_type == "news_summary":
            return (
                "Turn One French Headline Into a Brief",
                f"Write a compact French briefing from the source card. State what happened, why it matters, and one practical consequence. Use your current grammar targets naturally; do not copy the article wording. Focus: {first_source or 'the source card'}.",
            )
        if mission_type == "explain_plan":
            return (
                "Explain Tomorrow's Plan",
                f"A colleague asks how you will handle a small schedule change tomorrow. Explain the first step, the backup plan, and one condition that would change your decision. {grammar_goal}",
            )
        if mission_type == "travel_work":
            return (
                "Solve a Desk Problem",
                f"You are at a station, hotel, or office desk in France. Say what the problem is, ask for a concrete solution, and confirm the next step politely. {grammar_goal}",
            )
        if mission_type == "conversation":
            return (
                "Back-and-Forth Scenario",
                f"Hold a short French conversation with the assistant. Reply to each question as if the scene were real, add one useful detail, and let the assistant continue the exchange. {grammar_goal}",
            )
        label = "post-session" if cadence == "post_session" else "weekly"
        return (
            "Message Before Arrival",
            f"Write a short French message you could actually send before meeting someone in France. Say when you arrive, mention one practical need, and ask one polite question. This is a {label} mission. {grammar_goal}",
        )

    def _conversation_opening(self, *, mission_type: str, source_snapshot: dict[str, Any]) -> str:
        if mission_type == "travel_work":
            return "Bonjour, je suis à l'accueil. Expliquez-moi le problème, et je vais vous proposer une solution."
        if mission_type == "news_summary":
            first_source = ((source_snapshot.get("items") or [{}])[0] or {}).get("title")
            if first_source:
                return f"J'ai vu ce titre: « {first_source} ». Tu peux me résumer l'idée principale en français ?"
            return "J'ai vu une information française ce matin. Tu peux me résumer ce qui se passe et pourquoi c'est important ?"
        if mission_type == "explain_plan":
            return "D'accord, explique-moi ton plan. Qu'est-ce que tu vas faire d'abord, et pourquoi ?"
        if mission_type == "conversation":
            return "Bonjour, on joue une scène réaliste. Vous arrivez avec une petite contrainte de temps: qu'est-ce que vous me dites ?"
        return "Lis-moi ton message comme si tu allais l'envoyer. Qu'est-ce que tu veux dire exactement ?"

    def _source_context_card(self, source_snapshot: dict[str, Any]) -> dict[str, Any] | None:
        items = source_snapshot.get("items") or []
        if not items:
            return None
        first = items[0] or {}
        return {
            "headline": first.get("title") or "France context",
            "summary": first.get("summary") or source_snapshot.get("digest") or "",
            "source": first.get("source") or "Source",
            "url": first.get("url") or "",
            "supporting_sources": [
                {
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "url": item.get("url"),
                }
                for item in items[1:3]
            ],
        }

    def _messenger_payload(
        self,
        *,
        mission_type: str,
        source_snapshot: dict[str, Any],
        concepts: list[GrammarConcept],
    ) -> dict[str, Any]:
        grammar_hint = self._grammar_goal(concepts)
        first_source = ((source_snapshot.get("items") or [{}])[0] or {}).get("title", "")
        defaults: dict[str, Any] = {
            "channel_label": "Reality messages",
            "contact_name": "Camille",
            "contact_role": "Local contact",
            "contact_initials": "CA",
            "presence": "available now",
            "time_label": "17:42",
            "thread_title": "Camille · arrival logistics",
            "scene_anchor": "Outside Gare de Lyon, 12 minutes before boarding",
            "dispatch_note": "Send a believable French reply that would make sense on a real phone.",
            "inbox_context": "The other person needs useful information, not a classroom answer.",
            "opening_message": "Coucou, tu arrives à quelle heure ? Tu as besoin de quelque chose avant qu'on parte ?",
            "ambient_cues": ["battery at 18%", "platform announcement nearby", "one practical constraint"],
            "quick_replies": [
                "J'arrive vers 18 h 20...",
                "Est-ce que je peux...",
                "Si le train est en retard...",
            ],
            "success_signal": "They know when you arrive, what you need, and what to answer next.",
            "realism_rules": [
                "Keep the reply short enough for a real message.",
                "Add one concrete detail before asking for help.",
                grammar_hint,
            ],
        }
        variants: dict[str, dict[str, Any]] = {
            "message": defaults,
            "explain_plan": {
                **defaults,
                "contact_name": "Nadia",
                "contact_role": "teammate",
                "contact_initials": "NA",
                "time_label": "08:15",
                "thread_title": "Nadia · tomorrow plan",
                "scene_anchor": "A work chat before a schedule change",
                "dispatch_note": "Explain the plan as a calm, practical update.",
                "inbox_context": "Nadia needs sequence, backup, and a condition that could change the plan.",
                "opening_message": "Tu peux me dire comment tu vas organiser demain ? J'ai besoin d'un plan clair.",
                "ambient_cues": ["calendar moved", "one colleague is unavailable", "decision needed before noon"],
                "quick_replies": [
                    "D'abord, je vais...",
                    "Si cela change...",
                    "Comme solution de secours...",
                ],
                "success_signal": "Nadia can repeat your plan without asking three follow-up questions.",
            },
            "news_summary": {
                **defaults,
                "contact_name": "Mina",
                "contact_role": "news-curious friend",
                "contact_initials": "MI",
                "time_label": "12:03",
                "thread_title": "Mina · French headline",
                "scene_anchor": "Lunch break, one headline in your feed",
                "dispatch_note": "Turn the source into a useful short briefing.",
                "inbox_context": first_source or "Mina saw a France-related headline and wants the practical point.",
                "opening_message": (
                    f"J'ai vu ce titre : « {first_source} ». Tu peux me résumer l'idée principale ?"
                    if first_source
                    else "J'ai vu une info française ce matin. Tu peux me résumer ce qui se passe ?"
                ),
                "ambient_cues": ["one source card", "no copying", "one practical consequence"],
                "quick_replies": [
                    "En bref, il s'agit de...",
                    "Ce qui compte, c'est que...",
                    "Concrètement, cela peut...",
                ],
                "success_signal": "Mina understands what happened, why it matters, and what changes next.",
            },
            "travel_work": {
                **defaults,
                "contact_name": "Agent Moreau",
                "contact_role": "front-desk agent",
                "contact_initials": "AM",
                "time_label": "19:28",
                "thread_title": "Agent Moreau · desk problem",
                "scene_anchor": "A service desk with a line forming behind you",
                "dispatch_note": "Explain the problem politely and secure the next step.",
                "inbox_context": "The agent can help only if your request is specific.",
                "opening_message": "Bonjour, expliquez-moi le problème et je vais regarder ce que je peux faire.",
                "ambient_cues": ["queue behind you", "ticket or reservation ready", "polite register matters"],
                "quick_replies": [
                    "Bonjour, j'ai un problème avec...",
                    "Est-ce qu'il serait possible de...",
                    "Je voudrais confirmer que...",
                ],
                "success_signal": "The agent knows the problem, the request, and the exact next step.",
            },
            "conversation": {
                **defaults,
                "contact_name": "Noémie",
                "contact_role": "scenario partner",
                "contact_initials": "NO",
                "time_label": "21:06",
                "thread_title": "Noémie · live roleplay",
                "scene_anchor": "A spontaneous chat with one time constraint",
                "dispatch_note": "Keep the exchange alive with details, questions, and reactions.",
                "inbox_context": "Noémie will respond naturally if you give her something real to work with.",
                "opening_message": "On joue une scène réaliste : tu arrives avec une petite contrainte de temps. Qu'est-ce que tu me dis ?",
                "ambient_cues": ["time pressure", "one human reaction", "a natural follow-up question"],
                "quick_replies": [
                    "J'ai seulement quelques minutes...",
                    "Je préfère...",
                    "Qu'est-ce que vous me conseillez ?",
                ],
                "success_signal": "The conversation can continue without sounding scripted.",
            },
        }
        return variants.get(mission_type, defaults)

    def _grammar_goal(self, concepts: list[GrammarConcept]) -> str:
        if not concepts:
            return "Use at least one repaired grammar form from your recent practice."
        asset_service = AtelierAssetService(self.db)
        names = [_concept_title(concept, asset_service) for concept in concepts[:3]]
        if len(names) == 1:
            return f"Try to include one natural use of {names[0]}."
        return f"Try to include: {', '.join(names[:-1])}, and {names[-1]}."

    def _writing_title(self, mission_type: str) -> str:
        return {
            "message": "Draft the message",
            "explain_plan": "Write the plan",
            "news_summary": "Write the brief",
            "travel_work": "Write what you would say",
            "conversation": "Prepare a first reply",
        }.get(mission_type, "One useful response")

    def _writing_instruction(self, mission_type: str) -> str:
        return {
            "message": "Keep it short enough for a real message: greeting, useful detail, one question, polite close.",
            "explain_plan": "Use sequence and consequence: first step, backup option, and what will happen next.",
            "news_summary": "Do not paste the source. Summarize the point and add your own practical consequence.",
            "travel_work": "Be specific and polite: problem, request, confirmation.",
            "conversation": "Write the first answer you would say aloud. You can continue in the conversation box below.",
        }.get(mission_type, "Write a realistic response.")

    def _conversation_title(self, mission_type: str) -> str:
        return "Back-and-forth scene" if mission_type == "conversation" else "Practice a follow-up turn"

    def _conversation_instruction(self, mission_type: str) -> str:
        if mission_type == "conversation":
            return "Answer the assistant, then continue for several turns. Each reply should move the situation forward."
        return "Use this if you want to rehearse the same mission as a short spoken or typed exchange."

    def _task_label(self, mission_type: str) -> str:
        return {
            "message": "Write a message someone could actually send",
            "explain_plan": "Explain a concrete plan",
            "news_summary": "Summarize French news with one consequence",
            "travel_work": "Handle a travel or work situation",
            "conversation": "Keep the conversation moving",
        }.get(mission_type, "Complete the realistic task")

    def _placeholder(self, mission_type: str) -> str:
        if mission_type == "news_summary":
            return "Résume l'information, puis explique ce que cela change..."
        if mission_type == "travel_work":
            return "Bonjour, je vous écris parce que..."
        if mission_type == "explain_plan":
            return "D'abord, je vais..."
        return "Write your mission response here."


class MissionCorrectionService:
    """Correct mission writing and turns, then persist durable error memory."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm_service or _safe_llm()

    def correct_submission(
        self,
        *,
        user: User,
        mission: RealWorldMission,
        text: str,
        mode: str,
        near_realtime: bool = False,
    ) -> dict[str, Any]:
        deterministic_errata, deterministic_answer = self._deterministic_errata(text)
        if near_realtime:
            correction = self._fallback_correction(
                mission=mission,
                text=text,
                corrected_answer=deterministic_answer,
                deterministic_errata=deterministic_errata,
            )
            correction["_prompt_version"] = MISSION_FAST_CORRECTION_PROMPT_VERSION
        else:
            correction = self._llm_correction(user=user, mission=mission, text=text, mode=mode) or self._fallback_correction(
                mission=mission,
                text=text,
                corrected_answer=deterministic_answer,
                deterministic_errata=deterministic_errata,
            )
            if deterministic_errata:
                correction = self._merge_deterministic_errata(
                    correction=correction,
                    deterministic_errata=deterministic_errata,
                    corrected_answer=deterministic_answer,
                )
        correction["errata"] = [self._normalize_erratum(item, mission) for item in correction.get("errata") or []]
        correction["correction_debug"] = {
            "prompt_version": correction.get("_prompt_version") or MISSION_CORRECTION_PROMPT_VERSION,
            "fallback_used": correction.get("_fallback_used", False),
            "model": correction.get("_model"),
            "deterministic_rule_count": len(deterministic_errata),
            "near_realtime": near_realtime,
        }
        correction = self._apply_vocabulary_feedback(mission=mission, text=text, correction=correction)
        correction.pop("_fallback_used", None)
        correction.pop("_model", None)
        correction.pop("_prompt_version", None)
        return correction

    def persist_errata(
        self,
        *,
        user: User,
        mission: RealWorldMission,
        correction: dict[str, Any],
        mode: str,
        source_id: str,
    ) -> list[dict[str, Any]]:
        memory = ErrorMemoryService(self.db)
        persisted: list[dict[str, Any]] = []
        for index, erratum in enumerate(correction.get("errata") or []):
            if self._is_vocabulary_erratum(erratum):
                continue
            update = memory.record_erratum(
                user=user,
                erratum=erratum,
                source_type="mission",
                concept_id=erratum.get("concept_id"),
                source_payload={
                    "mission_id": str(mission.id),
                    "mission_type": mission.mission_type,
                    "mode": mode,
                    "source_id": source_id,
                    "erratum_index": index,
                },
            )
            if update:
                persisted.append(update)
        persisted.extend(
            self._apply_vocabulary_events(
                user=user,
                mission=mission,
                correction=correction,
                mode=mode,
                source_id=source_id,
            )
        )
        return persisted

    def _llm_correction(self, *, user: User, mission: RealWorldMission, text: str, mode: str) -> dict[str, Any] | None:
        if not self.llm:
            return None
        payload = {
            "mission": serialize_mission(mission, include_children=False),
            "mode": mode,
            "learner_text": text,
            "learner_level": user.proficiency_level or "A2",
        }
        system = (
            "You are a strict but concise French correction engine for a real-world mission. "
            "Address feedback directly as 'you'. Never say 'the learner' or 'the user'. "
            "Do not create generic repairs; explain exactly what changed."
        )
        try:
            result = self.llm.generate_error_detection(
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=system,
                response_format=MISSION_CORRECTION_RESPONSE_FORMAT,
                temperature=0.1,
                max_tokens=1400,
            )
            parsed = json.loads(result.content)
            parsed["_model"] = result.model
            parsed["_fallback_used"] = False
            return parsed
        except (LLMProviderError, json.JSONDecodeError, ValueError) as exc:
            logger.debug("Mission correction LLM fallback", error=str(exc))
            return None

    def _fallback_correction(
        self,
        *,
        mission: RealWorldMission,
        text: str,
        corrected_answer: str | None = None,
        deterministic_errata: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        stripped = text.strip()
        objectives = mission.objectives or []
        words = re.findall(r"\S+", stripped)
        objective_progress = [
            {
                "id": obj.get("id"),
                "label": obj.get("label"),
                "met": bool(stripped) if obj.get("kind") == "communication" else False,
                "note": "Submitted" if stripped else "No answer yet",
            }
            for obj in objectives
        ]
        missing_targets = [
            {
                "external_id": str(obj.get("external_id") or obj.get("id") or "target"),
                "label": str(obj.get("label") or "Target"),
                "detected_count": 0,
                "target_count": int(obj.get("target_count") or 1),
                "missing_count": int(obj.get("target_count") or 1),
            }
            for obj in objectives
            if obj.get("kind") in {"grammar", "source"} and stripped
        ]
        errata: list[dict[str, Any]] = list(deterministic_errata or [])
        if not stripped:
            errata.append(
                {
                    "display_label": "Missing mission response",
                    "learner_text": "",
                    "corrected_target": "Write a short French response before submitting.",
                    "why_wrong": "You submitted an empty response, so there is no French to review.",
                    "repair_hint": "Write two or three sentences that answer the mission brief.",
                    "severity": 2,
                    "recurring": False,
                    "task_error_type": "task_compliance",
                    "external_id": "MISSION_TASK",
                }
            )
        elif len(words) < 8:
            errata.append(
                {
                    "display_label": "Too little context",
                    "learner_text": stripped,
                    "corrected_target": stripped,
                    "why_wrong": "Your response is understandable, but it is too short to prove the mission targets.",
                    "repair_hint": "Add one reason, one concrete detail, and one target grammar form.",
                    "severity": 2,
                    "recurring": False,
                    "task_error_type": "task_compliance",
                    "external_id": "MISSION_TASK",
                }
            )
        score = 3 if len(words) >= 8 else (2 if stripped else 1)
        verdict = "accepted" if stripped else "needs_revision"
        if deterministic_errata:
            max_severity = max(int(item.get("severity") or 1) for item in deterministic_errata)
            verdict = "needs_revision" if max_severity >= 2 else "partial"
            score = min(score, 2 if max_severity >= 2 else 3)
        return {
            "verdict": verdict,
            "score_0_4": score,
            "corrected_answer": corrected_answer if corrected_answer is not None else stripped,
            "objective_progress": objective_progress,
            "concept_hits": [],
            "missing_targets": missing_targets[:4],
            "errata": errata,
            "vocabulary_links": [],
            "_fallback_used": True,
            "_model": None,
        }

    def _deterministic_errata(self, text: str) -> tuple[list[dict[str, Any]], str]:
        corrected = text
        errata: list[dict[str, Any]] = []

        def preserve_case(original: str, replacement: str) -> str:
            if original.isupper():
                return replacement.upper()
            if original[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        avet_pattern = re.compile(r"\b(?:(vous)\s+)?(avet)\b", re.IGNORECASE)
        avet_match = avet_pattern.search(text)
        if avet_match:
            learner_text = avet_match.group(0)
            corrected_target = re.sub(
                r"\bavet\b",
                lambda match: preserve_case(match.group(0), "avez"),
                learner_text,
                flags=re.IGNORECASE,
            )
            errata.append(
                {
                    "display_label": "Conjugation: vous avez",
                    "learner_text": learner_text,
                    "corrected_target": corrected_target,
                    "why_wrong": "With vous, avoir is avez, not avet.",
                    "repair_hint": "Use vous avez before a noun or past participle.",
                    "severity": 2,
                    "recurring": False,
                    "task_error_type": "verb_conjugation",
                    "external_id": "FR_ORTHO_AVOIR_VOUS",
                }
            )
            corrected = re.sub(
                r"\bavet\b",
                lambda match: preserve_case(match.group(0), "avez"),
                corrected,
                flags=re.IGNORECASE,
            )

        probleme_pattern = re.compile(r"\b(probleme)(s?)\b", re.IGNORECASE)
        probleme_match = probleme_pattern.search(text)
        if probleme_match:
            learner_text = probleme_match.group(0)
            base = preserve_case(probleme_match.group(1), "problème")
            corrected_target = f"{base}{probleme_match.group(2)}"
            errata.append(
                {
                    "display_label": "Spelling: problème",
                    "learner_text": learner_text,
                    "corrected_target": corrected_target,
                    "why_wrong": "The French word is problème with an accent grave.",
                    "repair_hint": "Write problème, or problèmes in the plural.",
                    "severity": 1,
                    "recurring": False,
                    "task_error_type": "orthography",
                    "external_id": "FR_ORTHO_PROBLEME_ACCENT",
                }
            )
            corrected = re.sub(
                r"\b(probleme)(s?)\b",
                lambda match: f"{preserve_case(match.group(1), 'problème')}{match.group(2)}",
                corrected,
                flags=re.IGNORECASE,
            )

        return errata, corrected.strip()

    def _merge_deterministic_errata(
        self,
        *,
        correction: dict[str, Any],
        deterministic_errata: list[dict[str, Any]],
        corrected_answer: str,
    ) -> dict[str, Any]:
        if not deterministic_errata:
            return correction
        merged = {**correction}
        existing = list(merged.get("errata") or [])
        existing_keys = {
            (
                str(item.get("learner_text") or "").casefold(),
                str(item.get("corrected_target") or "").casefold(),
                str(item.get("task_error_type") or ""),
            )
            for item in existing
        }
        for item in deterministic_errata:
            key = (
                str(item.get("learner_text") or "").casefold(),
                str(item.get("corrected_target") or "").casefold(),
                str(item.get("task_error_type") or ""),
            )
            if key not in existing_keys:
                existing.append(item)
                existing_keys.add(key)
        merged["errata"] = existing
        merged["corrected_answer"] = corrected_answer or merged.get("corrected_answer") or ""
        max_severity = max(int(item.get("severity") or 1) for item in deterministic_errata)
        if max_severity >= 2 and merged.get("verdict") == "accepted":
            merged["verdict"] = "needs_revision"
        elif merged.get("verdict") == "accepted":
            merged["verdict"] = "partial"
        current_score = float(merged.get("score_0_4") or 0)
        score_cap = 2.0 if max_severity >= 2 else 3.0
        merged["score_0_4"] = min(current_score or score_cap, score_cap)
        return merged

    def _normalize_erratum(self, erratum: dict[str, Any], mission: RealWorldMission) -> dict[str, Any]:
        external_id = erratum.get("external_id")
        concept_id = None
        if external_id:
            concept = self.db.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).first()
            concept_id = concept.id if concept else None
        if not concept_id and external_id and str(external_id).startswith("FR_ORTHO_"):
            concept_id = None
        elif not concept_id and (mission.selected_concept_ids or []):
            concept_id = int((mission.selected_concept_ids or [0])[0] or 0) or None
        return {
            **erratum,
            "why_wrong": _clean_feedback(erratum.get("why_wrong")),
            "repair_hint": _clean_feedback(erratum.get("repair_hint")),
            "concept_id": concept_id,
            "error_category": erratum.get("error_category") or "grammar",
            "linked_word_id": erratum.get("linked_word_id"),
        }

    def _apply_vocabulary_feedback(
        self,
        *,
        mission: RealWorldMission,
        text: str,
        correction: dict[str, Any],
    ) -> dict[str, Any]:
        vocabulary = self._mission_vocabulary_items(mission)
        if not vocabulary:
            correction.setdefault("vocabulary_events", [])
            return correction

        merged = {**correction}
        objective_progress = list(merged.get("objective_progress") or [])
        objectives_by_id = {
            str(item.get("id")): item
            for item in objective_progress
            if isinstance(item, dict) and item.get("id")
        }
        missing_targets = list(merged.get("missing_targets") or [])
        errata = list(merged.get("errata") or [])
        vocabulary_links = list(merged.get("vocabulary_links") or [])
        vocabulary_events = list(merged.get("vocabulary_events") or [])
        existing_vocab_error_ids = {
            int(item.get("linked_word_id"))
            for item in errata
            if item.get("linked_word_id") and str(item.get("error_category") or "").lower() == "vocabulary"
        }
        normalized_text = _normalize_phrase(text)
        added_vocab_erratum = False

        for item in vocabulary[:3]:
            word_id = item.get("word_id")
            if not word_id:
                continue
            objective_id = f"vocabulary_{word_id}"
            word = str(item.get("word") or "target word").strip()
            translation = str(item.get("translation") or "").strip()
            used_target = self._contains_vocabulary_form(normalized_text, item)
            translation_hit = self._translation_hit(normalized_text, item)
            if used_target:
                objectives_by_id[objective_id] = {
                    "id": objective_id,
                    "label": f"Use {word} naturally",
                    "met": True,
                    "note": f"You used {word} in your response.",
                }
                vocabulary_links.append(
                    {
                        "learner_text": word,
                        "target": word,
                        "translation": translation,
                        "word_id": word_id,
                        "event_type": "produced_correct",
                    }
                )
                vocabulary_events.append(
                    {
                        "word_id": word_id,
                        "event_type": "produced_correct",
                        "reason": "target_vocabulary_used",
                        "learner_text": word,
                    }
                )
                continue

            objectives_by_id[objective_id] = {
                "id": objective_id,
                "label": f"Use {word} naturally",
                "met": False,
                "note": f"Try to work {word} into the mission naturally.",
            }
            missing_targets.append(
                {
                    "external_id": f"VOCAB_{word_id}",
                    "label": f"Use {word} naturally",
                    "detected_count": 0,
                    "target_count": 1,
                    "missing_count": 1,
                }
            )
            if added_vocab_erratum or int(word_id) in existing_vocab_error_ids or not normalized_text:
                continue
            errata.append(
                self._target_vocabulary_erratum(
                    item=item,
                    learner_text=translation_hit or "",
                    reason="translation_instead_of_target" if translation_hit else "missing_target",
                )
            )
            vocabulary_events.append(
                {
                    "word_id": word_id,
                    "event_type": "produced_incorrect" if translation_hit else "missed_target",
                    "reason": "translation_instead_of_target" if translation_hit else "missing_target",
                    "learner_text": translation_hit or _compact_text(text, max_length=160),
                    "explanation": "The mission target vocabulary was not produced in French.",
                    "repair_hint": f"Add {word} naturally in one short French sentence.",
                }
            )
            added_vocab_erratum = True

        if objectives_by_id:
            seen_ids: set[str] = set()
            merged_progress: list[dict[str, Any]] = []
            for item in objective_progress:
                item_id = str(item.get("id") or "")
                if item_id in objectives_by_id:
                    merged_progress.append(objectives_by_id[item_id])
                    seen_ids.add(item_id)
                else:
                    merged_progress.append(item)
            for item_id, item in objectives_by_id.items():
                if item_id not in seen_ids:
                    merged_progress.append(item)
            merged["objective_progress"] = merged_progress
        if added_vocab_erratum and merged.get("verdict") == "accepted":
            merged["verdict"] = "partial"
            merged["score_0_4"] = min(float(merged.get("score_0_4") or 3), 3)
        merged["missing_targets"] = missing_targets[:8]
        merged["errata"] = errata
        merged["vocabulary_links"] = vocabulary_links
        merged["vocabulary_events"] = vocabulary_events
        return merged

    def _mission_vocabulary_items(self, mission: RealWorldMission) -> list[dict[str, Any]]:
        payload_items = [
            item
            for item in ((mission.prompt_payload or {}).get("target_vocabulary") or [])
            if isinstance(item, dict) and item.get("word_id")
        ]
        by_id: dict[int, dict[str, Any]] = {}
        for item in payload_items:
            try:
                word_id = int(item.get("word_id"))
            except (TypeError, ValueError):
                continue
            by_id[word_id] = {
                **item,
                "word_id": word_id,
                "word": item.get("word") or item.get("target") or "",
                "translation": item.get("translation") or item.get("english_translation") or "",
            }

        missing_ids = [word_id for word_id in _dedupe_ints(mission.target_vocabulary_ids or []) if word_id not in by_id]
        if missing_ids:
            words = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(missing_ids)).all()
            for word in words:
                by_id[word.id] = {
                    "word_id": word.id,
                    "word": word.word,
                    "normalized_word": word.normalized_word,
                    "translation": word.german_translation or word.english_translation or word.definition or "",
                    "example_sentence": word.example_sentence,
                    "example_translation": word.example_translation,
                }

        ordered_ids = _dedupe_ints(
            [
                *[item.get("word_id") for item in payload_items],
                *(mission.target_vocabulary_ids or []),
            ]
        )
        return [by_id[word_id] for word_id in ordered_ids if word_id in by_id]

    def _contains_vocabulary_form(self, normalized_text: str, item: dict[str, Any]) -> bool:
        forms = [
            item.get("word"),
            item.get("normalized_word"),
            item.get("french_translation"),
        ]
        return any(self._contains_normalized_phrase(normalized_text, form) for form in forms)

    def _translation_hit(self, normalized_text: str, item: dict[str, Any]) -> str:
        translation = str(item.get("translation") or "")
        candidates = [
            part.strip()
            for part in re.split(r"[,;/|()]+", translation)
            if len(_normalize_phrase(part.strip())) >= 4
        ]
        for candidate in candidates[:4]:
            if self._contains_normalized_phrase(normalized_text, candidate):
                return candidate
        return ""

    @staticmethod
    def _contains_normalized_phrase(normalized_text: str, phrase: Any) -> bool:
        normalized_phrase = _normalize_phrase(phrase)
        if not normalized_text or not normalized_phrase:
            return False
        if " " in normalized_phrase:
            return f" {normalized_phrase} " in f" {normalized_text} "
        return normalized_phrase in set(normalized_text.split())

    def _target_vocabulary_erratum(
        self,
        *,
        item: dict[str, Any],
        learner_text: str,
        reason: str,
    ) -> dict[str, Any]:
        word = str(item.get("word") or "target word").strip()
        translation = str(item.get("translation") or "").strip()
        example = str(item.get("example_sentence") or "").strip()
        if reason == "translation_instead_of_target":
            why = f"You reached for the meaning of {word}, but the mission target is the French word itself."
            repair = f"Use {word} in a natural French sentence instead of writing the translation."
        else:
            why = f"This mission asked you to try the target word {word}, but it did not appear in your response."
            repair = f"Add one short sentence that uses {word} naturally."
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
            "external_id": f"VOCAB_{item.get('word_id')}",
            "error_category": "vocabulary",
            "linked_word_id": item.get("word_id"),
            "translation": translation,
        }

    @staticmethod
    def _is_vocabulary_erratum(erratum: dict[str, Any]) -> bool:
        marker = f"{erratum.get('error_category') or ''} {erratum.get('task_error_type') or ''} {erratum.get('display_label') or ''}".lower()
        return bool(erratum.get("linked_word_id")) or "vocab" in marker

    def _apply_vocabulary_events(
        self,
        *,
        user: User,
        mission: RealWorldMission,
        correction: dict[str, Any],
        mode: str,
        source_id: str,
    ) -> list[dict[str, Any]]:
        events = [event for event in correction.get("vocabulary_events") or [] if isinstance(event, dict)]
        if not events:
            return []
        word_ids = _dedupe_ints([event.get("word_id") for event in events])
        words = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(word_ids)).all()
        by_id = {word.id: word for word in words}
        target_items = {item.get("word_id"): item for item in self._mission_vocabulary_items(mission)}
        credit_service = VocabularyCreditService(self.db)
        persisted: list[dict[str, Any]] = []
        for event in events:
            word_id = _dedupe_ints([event.get("word_id")])
            if not word_id:
                continue
            word = by_id.get(word_id[0])
            if not word:
                continue
            item = target_items.get(word.id) or {}
            result = credit_service.apply(
                user=user,
                word=word,
                event_type=str(event.get("event_type") or "seen_context"),
                source_type="mission",
                learner_text=str(event.get("learner_text") or ""),
                corrected_text=word.word,
                context=str(item.get("example_sentence") or mission.title or ""),
                explanation=str(event.get("explanation") or ""),
                repair_hint=str(event.get("repair_hint") or ""),
                source_payload={
                    "mission_id": str(mission.id),
                    "mission_type": mission.mission_type,
                    "mode": mode,
                    "source_id": source_id,
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


class MissionSRSService:
    """Turn useful mission language into reviewable vocabulary/phrase items."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_phrase_bank(self, *, user: User, mission: RealWorldMission) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        phrases = self._phrase_bank(mission)
        saved: list[dict[str, Any]] = []
        for phrase in phrases[:5]:
            normalized = _normalize_phrase(phrase["phrase"])
            if not normalized or len(normalized) < 4:
                continue
            word = self._get_or_create_phrase(user=user, phrase=phrase, normalized=normalized)
            progress = ProgressService(self.db).get_or_create_progress(user_id=user.id, word_id=word.id)
            progress.times_seen = (progress.times_seen or 0) + 1
            progress.times_used_correctly = (progress.times_used_correctly or 0) + 1
            progress.correct_count = (progress.correct_count or 0) + 1
            progress.state = "learning"
            progress.phase = "learn"
            progress.scheduler = progress.scheduler or "fsrs"
            progress.due_at = now + timedelta(hours=12)
            progress.next_review_date = progress.due_at
            progress.due_date = progress.due_at.date()
            progress.updated_at = now
            existing_types = list(progress.error_types or [])
            marker = f"mission_phrase:{mission.mission_type}"
            if marker not in existing_types:
                existing_types.append(marker)
            progress.error_types = existing_types
            self.db.add(progress)
            saved.append(
                {
                    "word_id": word.id,
                    "progress_id": str(progress.id),
                    "phrase": word.word,
                    "translation": word.english_translation,
                    "due_at": progress.due_at.isoformat() if progress.due_at else None,
                    "source": "mission_phrase_bank",
                }
            )
        return {
            "saved_count": len(saved),
            "phrase_bank": saved,
            "review_route": "/daily-practice?focus=mission",
            "queue_note": "Saved mission phrases are due in the unified SRS queue.",
        }

    def _get_or_create_phrase(self, *, user: User, phrase: dict[str, Any], normalized: str) -> VocabularyWord:
        language = (user.target_language or "fr").strip() or "fr"
        existing = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.language == language, VocabularyWord.normalized_word == normalized)
            .first()
        )
        if existing:
            return existing
        word = VocabularyWord(
            language=language,
            word=phrase["phrase"],
            normalized_word=normalized,
            english_translation=phrase.get("translation") or "Mission-ready phrase",
            definition=phrase.get("role") or "Reusable phrase from a real-world mission",
            example_sentence=phrase.get("example") or phrase["phrase"],
            usage_notes=phrase.get("note") or "Saved from Missions for spaced review.",
            difficulty_level=2,
            topic_tags=["mission_phrase", "real_world", str(phrase.get("mission_type") or "mission")],
        )
        self.db.add(word)
        self.db.flush([word])
        return word

    def _phrase_bank(self, mission: RealWorldMission) -> list[dict[str, Any]]:
        messenger = (mission.prompt_payload or {}).get("messenger") or {}
        phrases: list[dict[str, Any]] = []
        for item in messenger.get("quick_replies") or []:
            text = _compact_text(item, max_length=140)
            if text:
                phrases.append(
                    {
                        "phrase": text,
                        "translation": "Reusable opening or reply fragment",
                        "role": "quick reply scaffold",
                        "note": "Use this as a flexible start, then add the real detail.",
                        "mission_type": mission.mission_type,
                    }
                )
        for attempt in sorted(mission.attempts or [], key=lambda item: item.created_at):
            correction = attempt.correction_payload or {}
            text = _compact_text(correction.get("corrected_answer") or (attempt.answer_payload or {}).get("text"), max_length=180)
            if text:
                phrases.append(
                    {
                        "phrase": text,
                        "translation": "Polished mission dispatch",
                        "role": "ready-to-send phrase",
                        "note": "Review this as a real message pattern.",
                        "mission_type": mission.mission_type,
                    }
                )
        for turn in sorted(mission.turns or [], key=lambda item: item.turn_index):
            if turn.role != "user":
                continue
            text = _compact_text((turn.correction_payload or {}).get("corrected_answer") or turn.text, max_length=160)
            if text:
                phrases.append(
                    {
                        "phrase": text,
                        "translation": "Conversation reply from a mission",
                        "role": "spoken or chat reply",
                        "note": "Practise this as a natural response under pressure.",
                        "mission_type": mission.mission_type,
                    }
                )
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for phrase in phrases:
            key = _normalize_phrase(phrase["phrase"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(phrase)
        return unique


class MissionDebriefService:
    """Build a human-readable completion debrief from mission traces."""

    def build(
        self,
        *,
        mission: RealWorldMission,
        attempts: list[RealWorldMissionAttempt],
        turns: list[RealWorldMissionTurn],
        errata_count: int,
        srs_result: dict[str, Any],
    ) -> dict[str, Any]:
        latest_correction = self._latest_correction(attempts=attempts, turns=turns)
        objective_progress = latest_correction.get("objective_progress") or []
        objectives = mission.objectives or []
        met_required = sum(1 for item in objective_progress if item.get("met"))
        required_total = max(1, len([item for item in objectives if item.get("required")]) or len(objectives) or 1)
        score = float(latest_correction.get("score_0_4") or 0)
        clarity = min(100, round((score / 4) * 70 + min(len(turns), 3) * 10))
        task_fit = min(100, round((met_required / required_total) * 100))
        repair_stability = max(20, 100 - errata_count * 18)
        naturalness = min(100, round(55 + min(self._word_total(attempts, turns), 80) * 0.45))
        readiness = round((clarity * 0.3) + (task_fit * 0.3) + (repair_stability * 0.2) + (naturalness * 0.2))
        outcome = self._outcome_label(readiness=readiness, errata_count=errata_count, turns=len(turns))
        return {
            "debrief_version": "mission-debrief-v1",
            "readiness": {
                "overall": readiness,
                "clarity": clarity,
                "task_fit": task_fit,
                "register": self._register_score(mission),
                "repair_stability": repair_stability,
                "naturalness": naturalness,
                "outcome": outcome,
            },
            "branch_outcome": {
                "state": "resolved" if readiness >= 75 else "needs_follow_up",
                "label": outcome,
                "next_best_move": self._next_best_move(mission=mission, errata_count=errata_count, readiness=readiness),
            },
            "saved_to_srs": srs_result,
            "next_mission_seed": self._next_mission_seed(mission=mission, readiness=readiness, errata_count=errata_count),
        }

    def _latest_correction(
        self,
        *,
        attempts: list[RealWorldMissionAttempt],
        turns: list[RealWorldMissionTurn],
    ) -> dict[str, Any]:
        turn_correction = [turn.correction_payload or {} for turn in turns if turn.correction_payload]
        attempt_correction = [attempt.correction_payload or {} for attempt in attempts if attempt.correction_payload]
        return (turn_correction or attempt_correction or [{}])[-1]

    def _word_total(self, attempts: list[RealWorldMissionAttempt], turns: list[RealWorldMissionTurn]) -> int:
        texts = [(attempt.answer_payload or {}).get("text", "") for attempt in attempts]
        texts.extend(turn.text for turn in turns)
        return sum(len(re.findall(r"\S+", text or "")) for text in texts)

    def _register_score(self, mission: RealWorldMission) -> int:
        messenger = (mission.prompt_payload or {}).get("messenger") or {}
        rules = " ".join(messenger.get("realism_rules") or []).lower()
        return 86 if "formal" in rules or "informal" in rules else 78

    def _outcome_label(self, *, readiness: int, errata_count: int, turns: int) -> str:
        if readiness >= 85 and errata_count == 0:
            return "Ready to use in a real conversation."
        if readiness >= 70:
            return "Usable, with one careful reread."
        if turns == 0:
            return "Rehearse one live turn before using this."
        return "Needs a follow-up repair before real use."

    def _next_best_move(self, *, mission: RealWorldMission, errata_count: int, readiness: int) -> str:
        if errata_count:
            return "Review the repair slips in daily practice, then send a cleaner version."
        if readiness < 75:
            return "Add one specific detail and ask a clearer next-step question."
        return "Try the same situation aloud once, then use the saved phrase in daily practice."

    def _next_mission_seed(self, *, mission: RealWorldMission, readiness: int, errata_count: int) -> dict[str, Any]:
        messenger = (mission.prompt_payload or {}).get("messenger") or {}
        if errata_count:
            prompt = f"Repair the same situation with fewer mistakes: {messenger.get('success_signal') or mission.title}"
        elif readiness < 75:
            prompt = f"Make the next reply more specific in: {messenger.get('thread_title') or mission.title}"
        else:
            prompt = f"Do a voice-note version of: {messenger.get('thread_title') or mission.title}"
        return {
            "mission_type": "conversation" if readiness >= 75 else mission.mission_type,
            "custom_scenario": prompt,
            "reason": "Generated from your mission debrief and SRS trace.",
        }


class MissionScheduler:
    """Create, retrieve, and complete missions."""

    def __init__(self, db: Session, generator: MissionGenerator | None = None) -> None:
        self.db = db
        self.generator = generator or MissionGenerator(db)

    async def today(self, user: User) -> dict[str, Any]:
        weekly = await self.ensure_weekly(user)
        active = (
            self.db.query(RealWorldMission)
            .filter(RealWorldMission.user_id == user.id, RealWorldMission.status == "in_progress")
            .order_by(RealWorldMission.updated_at.desc())
            .first()
        )
        if not active:
            active = (
                self.db.query(RealWorldMission)
                .filter(
                    RealWorldMission.user_id == user.id,
                    RealWorldMission.cadence == "ad_hoc",
                    RealWorldMission.status == "available",
                )
                .order_by(RealWorldMission.created_at.desc())
                .first()
            )
        post_session = (
            self.db.query(RealWorldMission)
            .filter(
                RealWorldMission.user_id == user.id,
                RealWorldMission.cadence == "post_session",
                RealWorldMission.status.in_(["available", "in_progress"]),
            )
            .order_by(RealWorldMission.created_at.desc())
            .first()
        )
        recent = (
            self.db.query(RealWorldMission)
            .filter(RealWorldMission.user_id == user.id, RealWorldMission.status == "completed")
            .order_by(RealWorldMission.completed_at.desc().nullslast(), RealWorldMission.created_at.desc())
            .limit(5)
            .all()
        )
        return {
            "weekly_mission": serialize_mission(weekly),
            "post_session_recommendation": serialize_mission(post_session) if post_session else None,
            "active_mission": serialize_mission(active) if active else None,
            "recent_completed": [serialize_mission(row, include_children=False) for row in recent],
        }

    async def ensure_weekly(self, user: User) -> RealWorldMission:
        iso = date.today().isocalendar()
        existing = (
            self.db.query(RealWorldMission)
            .filter(
                RealWorldMission.user_id == user.id,
                RealWorldMission.cadence == "weekly",
                RealWorldMission.iso_year == iso.year,
                RealWorldMission.iso_week == iso.week,
            )
            .first()
        )
        if existing:
            return existing
        mission_type = MISSION_TEMPLATES[iso.week % len(MISSION_TEMPLATES)]
        return await self.create(
            user=user,
            mission_type=mission_type,
            cadence="weekly",
            use_news=mission_type == "news_summary",
        )

    async def create(
        self,
        *,
        user: User,
        mission_type: str,
        cadence: str,
        atelier_session_id: UUID | None = None,
        preferred_concept_ids: list[int] | None = None,
        preferred_errata_ids: list[UUID] | None = None,
        preferred_vocabulary_ids: list[int] | None = None,
        use_news: bool = True,
        custom_scenario: str | None = None,
        desired_outcome: str | None = None,
        relationship: str | None = None,
        register: str | None = None,
        serial_thread_id: UUID | None = None,
        episode_index: int | None = None,
        stakes_level: int | None = None,
    ) -> RealWorldMission:
        custom_context = {
            "scenario": custom_scenario,
            "desired_outcome": desired_outcome,
            "relationship": relationship,
            "register": register,
        }
        has_custom_context = bool(_compact_text(custom_scenario))
        serial_thread = self.db.get(SerialThread, serial_thread_id) if serial_thread_id else None
        if serial_thread and serial_thread.user_id != user.id:
            serial_thread = None
            serial_thread_id = None
        if serial_thread and episode_index is None:
            episode_index = serial_thread.current_episode_index
        if serial_thread:
            existing_mission = self._existing_serial_mission(thread=serial_thread, episode_index=episode_index)
            if existing_mission:
                return existing_mission
            if not has_custom_context:
                custom_context = self._serial_custom_context(thread=serial_thread, episode_index=episode_index)
                has_custom_context = True
        if cadence == "weekly" and not has_custom_context:
            iso = date.today().isocalendar()
            existing = (
                self.db.query(RealWorldMission)
                .filter(
                    RealWorldMission.user_id == user.id,
                    RealWorldMission.cadence == "weekly",
                    RealWorldMission.iso_year == iso.year,
                    RealWorldMission.iso_week == iso.week,
                )
                .first()
            )
            if existing:
                return existing
        atelier_session = self.db.get(AtelierSession, atelier_session_id) if atelier_session_id else None
        if atelier_session and atelier_session.user_id != user.id:
            atelier_session = None
        payload = await self.generator.build_payload(
            user=user,
            mission_type=mission_type,
            cadence=cadence,
            atelier_session=atelier_session,
            preferred_concept_ids=preferred_concept_ids,
            preferred_errata_ids=preferred_errata_ids,
            preferred_vocabulary_ids=preferred_vocabulary_ids,
            use_news=use_news,
            custom_context=custom_context if has_custom_context else None,
            stakes_level=stakes_level,
        )
        iso = date.today().isocalendar() if cadence == "weekly" and not has_custom_context else None
        mission = RealWorldMission(
            user_id=user.id,
            atelier_session_id=atelier_session.id if atelier_session else None,
            serial_thread_id=serial_thread_id,
            episode_index=episode_index,
            status="available",
            cadence=cadence,
            mission_type=mission_type if mission_type in MISSION_TEMPLATES else "message",
            iso_year=iso.year if iso else None,
            iso_week=iso.week if iso else None,
            **payload,
        )
        self.db.add(mission)
        self.db.commit()
        self.db.refresh(mission)
        if serial_thread:
            self._apply_serial_mission_contract(
                mission=mission,
                thread=serial_thread,
                episode_index=episode_index if episode_index is not None else serial_thread.current_episode_index,
            )
            self._link_serial_episode(
                mission=mission,
                thread=serial_thread,
                episode_index=episode_index if episode_index is not None else serial_thread.current_episode_index,
            )
        if mission.mission_type == "conversation":
            opening = (mission.prompt_payload or {}).get("conversation_opening")
            if opening:
                self.db.add(
                    RealWorldMissionTurn(
                        mission_id=mission.id,
                        user_id=user.id,
                        turn_index=1,
                        role="assistant",
                        mode="chat",
                        text=str(opening),
                        audio_payload={},
                        correction_payload={},
                    )
                )
                self.db.commit()
                self.db.refresh(mission)
        return mission

    def _existing_serial_mission(
        self,
        *,
        thread: SerialThread,
        episode_index: int | None,
    ) -> RealWorldMission | None:
        if episode_index is None:
            return None
        episode = (
            self.db.query(SerialEpisode)
            .filter(
                SerialEpisode.thread_id == thread.id,
                SerialEpisode.episode_index == episode_index,
                SerialEpisode.kind == "mission",
                SerialEpisode.mission_id.isnot(None),
            )
            .first()
        )
        if not episode or not episode.mission_id:
            return None
        mission = self.db.get(RealWorldMission, episode.mission_id)
        if not mission or mission.user_id != thread.user_id:
            return None
        return mission

    def _serial_custom_context(
        self,
        *,
        thread: SerialThread,
        episode_index: int | None,
    ) -> dict[str, Any]:
        index = episode_index if episode_index is not None else thread.current_episode_index
        if index == 0:
            return {
                "scenario": (
                    "Your first night in Paris. The radiator in your new studio is dead. "
                    "Write a short formal message to the landlord to report the heating problem "
                    "and ask for a repair time."
                ),
                "desired_outcome": "The landlord understands the problem and confirms a repair appointment.",
                "relationship": "landlord_marchand",
                "register": "vous / polite formal",
                "source": "serial_thread",
            }

        brief = self._serial_episode_brief(thread=thread, episode_index=index)
        if brief:
            hook = self._serial_previous_hook(thread=thread, episode_index=index)
            teaser = (
                _compact_text(hook.get("teaser"), max_length=240)
                or _compact_text(hook.get("text"), max_length=240)
                or _compact_text(hook.get("unresolved_question"), max_length=240)
                or "The previous episode left a practical question unanswered."
            )
            a_plot = brief.get("a_plot") if isinstance(brief.get("a_plot"), dict) else {}
            b_plot = brief.get("b_plot") if isinstance(brief.get("b_plot"), dict) else {}
            addressed = self._serial_brief_character(brief)
            register = self._serial_register_for_character(thread=thread, character_id=addressed)
            recap = self._serial_story_so_far(thread)
            scenario = (
                f"Story so far: {recap} " if recap else ""
            ) + (
                f"The last episode ended here: {teaser} Write the next French message to "
                f"{self._serial_character_name(thread, addressed)}. Advance this beat: "
                f"{a_plot.get('stage_summary') or 'move the story forward'}. "
                f"Keep this as texture: {b_plot.get('seed') or 'one everyday Paris complication'}."
            )
            return {
                "scenario": scenario,
                "desired_outcome": f"{self._serial_character_name(thread, addressed)} understands the next concrete step.",
                "relationship": addressed,
                "register": register,
                "source": "serial_thread",
                "episode_brief": brief,
            }

        hook = self._serial_previous_hook(thread=thread, episode_index=index)
        teaser = (
            _compact_text(hook.get("teaser"), max_length=240)
            or _compact_text(hook.get("text"), max_length=240)
            or _compact_text(hook.get("unresolved_question"), max_length=240)
            or "The previous episode left a practical question unanswered."
        )
        recap = self._serial_story_so_far(thread)
        scenario = (
            f"Story so far: {recap} " if recap else ""
        ) + f"The last episode ended here: {teaser} Write the next French message that moves the Paris story forward."
        return {
            "scenario": scenario,
            "desired_outcome": "The other person understands what you propose and knows the next concrete step.",
            "relationship": self._serial_relationship(hook),
            "register": self._serial_register(hook),
            "source": "serial_thread",
        }

    def _apply_serial_mission_contract(
        self,
        *,
        mission: RealWorldMission,
        thread: SerialThread,
        episode_index: int,
    ) -> None:
        if (mission.prompt_payload or {}).get("serial_reference") == "episode-01-beat-a":
            return
        hook = self._serial_previous_hook(thread=thread, episode_index=episode_index)
        brief = self._serial_episode_brief(thread=thread, episode_index=episode_index)
        title = self._serial_mission_title(hook=hook, episode_index=episode_index)
        episode_label = f"Episode {episode_index + 1}"
        prompt = dict(mission.prompt_payload or {})
        messenger = dict(prompt.get("messenger") or {})
        addressed = self._serial_brief_character(brief) if brief else self._serial_relationship(hook)
        profile = cefr_generation_profile(thread.user.proficiency_level)
        prompt.update(
            {
                "serial_reference": f"episode-{episode_index + 1:02d}-mission",
                "display_title": title,
                "episode_title": f"{episode_label} — {title}",
                "serial_beat": "act",
                "serial_character_id": addressed,
                "serial_episode_brief": brief or {},
                "serial_relationships": self._serial_relationship_payload(thread=thread, brief=brief or {}),
                "target_register": self._serial_register_for_character(thread=thread, character_id=addressed),
                "min_words": max(int(prompt.get("min_words") or 0), int(profile.get("min_words") or 0)),
                "serial_context": {
                    "thread_id": str(thread.id),
                    "episode_index": episode_index,
                    "hook_from_previous": hook,
                    "story_so_far": self._serial_story_so_far(thread),
                    "episode_brief": brief or {},
                },
            }
        )
        prompt["messenger"] = {
            **messenger,
            "channel_label": f"{episode_label} · Act",
            "thread_title": messenger.get("thread_title") or title,
            "dispatch_note": (
                hook.get("unresolved_question")
                or hook.get("text")
                or "Answer the story beat with one concrete next step."
            ),
            "inbox_context": mission.brief,
            "opening_message": messenger.get("opening_message")
            or hook.get("text")
            or "Le fil continue. Répondez avec un message clair et utile.",
            "success_signal": messenger.get("success_signal")
            or "The next person in the story knows exactly what to do.",
        }
        mission.title = title
        mission.prompt_payload = prompt
        self.db.add(mission)
        self.db.commit()
        self.db.refresh(mission)

    def _serial_episode_brief(self, *, thread: SerialThread, episode_index: int) -> dict[str, Any]:
        episode = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == episode_index)
            .first()
        )
        if episode and isinstance(episode.brief_payload, dict):
            return episode.brief_payload
        return {}

    @staticmethod
    def _serial_brief_character(brief: dict[str, Any]) -> str:
        required_cast = [str(item) for item in brief.get("required_cast") or [] if str(item or "").strip()]
        for preferred in ("landlord_marchand", "romy_tremblay", "lila_bonnet", "marin_leveque", "augustin_de_roncourt", "margaux_barman"):
            if preferred in required_cast:
                return preferred
        return required_cast[0] if required_cast else "margaux_barman"

    @staticmethod
    def _serial_character_name(thread: SerialThread, character_id: str) -> str:
        world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
        for member in world.get("cast") or []:
            if isinstance(member, dict) and member.get("id") == character_id:
                return str(member.get("name") or character_id)
        return {
            "landlord_marchand": "M. Marchand",
            "margaux_barman": "Margaux",
            "augustin_de_roncourt": "Gus",
            "romy_tremblay": "Romy",
            "marin_leveque": "Marin",
            "lila_bonnet": "Lila",
        }.get(character_id, character_id.replace("_", " ").title())

    @staticmethod
    def _serial_register_for_character(*, thread: SerialThread, character_id: str) -> str:
        if character_id == "landlord_marchand":
            return "vous / polite formal"
        relationships = (thread.state or {}).get("relationships") if isinstance((thread.state or {}).get("relationships"), dict) else {}
        entry = relationships.get(character_id) if isinstance(relationships, dict) else {}
        if isinstance(entry, dict) and str(entry.get("register") or "").lower() == "tu":
            return "tu / warm informal"
        return "vous / cautious newcomer"

    @staticmethod
    def _serial_relationship_payload(*, thread: SerialThread, brief: dict[str, Any]) -> dict[str, Any]:
        relationships = (thread.state or {}).get("relationships") if isinstance((thread.state or {}).get("relationships"), dict) else {}
        return {
            str(character_id): relationships.get(str(character_id), {"closeness": 0, "register": "vous", "callbacks": []})
            for character_id in brief.get("required_cast") or []
        }

    def _link_serial_episode(
        self,
        *,
        mission: RealWorldMission,
        thread: SerialThread,
        episode_index: int,
    ) -> None:
        existing = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index == episode_index)
            .first()
        )
        if existing and existing.kind != "mission":
            return
        hook = self._serial_previous_hook(thread=thread, episode_index=episode_index)
        if existing:
            existing.mission_id = mission.id
            existing.scene_id = None
            existing.hook_from_previous = existing.hook_from_previous or hook or {}
            self.db.add(existing)
        else:
            self.db.add(
                SerialEpisode(
                    thread_id=thread.id,
                    episode_index=episode_index,
                    kind="mission",
                    mission_id=mission.id,
                    scene_id=None,
                    hook={},
                    hook_from_previous=hook or {},
                    state_delta={},
                    status="available",
                )
            )
        self.db.commit()

    def _serial_previous_hook(self, *, thread: SerialThread, episode_index: int) -> dict[str, Any]:
        previous = (
            self.db.query(SerialEpisode)
            .filter(SerialEpisode.thread_id == thread.id, SerialEpisode.episode_index < episode_index)
            .order_by(SerialEpisode.episode_index.desc())
            .first()
        )
        return previous.hook or {} if previous else {}

    @staticmethod
    def _serial_story_so_far(thread: SerialThread) -> str:
        history = (thread.state or {}).get("story_so_far") or []
        if not isinstance(history, list):
            return ""
        return _compact_text(" ".join(str(item) for item in history[-6:]), max_length=700)

    @staticmethod
    def _serial_relationship(hook: dict[str, Any]) -> str:
        text = " ".join(str(hook.get(key) or "") for key in ("speaker", "text", "teaser", "unresolved_question")).lower()
        if "marchand" in text or "propriétaire" in text or "radiateur" in text:
            return "landlord_marchand"
        if "romy" in text:
            return "Romy"
        if "lila" in text:
            return "Lila"
        if "marin" in text:
            return "Marin"
        if "gus" in text or "augustin" in text:
            return "Gus"
        return "friend group"

    @staticmethod
    def _serial_register(hook: dict[str, Any]) -> str:
        relationship = MissionScheduler._serial_relationship(hook).lower()
        if "landlord" in relationship or "marchand" in relationship:
            return "vous / polite formal"
        return "warm informal"

    @staticmethod
    def _serial_mission_title(*, hook: dict[str, Any], episode_index: int) -> str:
        if episode_index == 0:
            return "Reach the landlord"
        raw = (
            _compact_text(hook.get("teaser"), max_length=80)
            or _compact_text(hook.get("unresolved_question"), max_length=80)
            or _compact_text(hook.get("text"), max_length=80)
        )
        if not raw:
            return "Answer the Thread"
        cleaned = re.sub(r"^(demain|next)\s*[:·-]\s*", "", raw, flags=re.IGNORECASE).strip()
        return cleaned[:1].upper() + cleaned[1:] if cleaned else "Answer the Thread"

    def get(self, *, user: User, mission_id: UUID) -> RealWorldMission | None:
        return (
            self.db.query(RealWorldMission)
            .filter(RealWorldMission.id == mission_id, RealWorldMission.user_id == user.id)
            .first()
        )

    def _apply_target_vocabulary_credit(
        self,
        *,
        user: User,
        mission: RealWorldMission,
        attempts: list[RealWorldMissionAttempt],
        turns: list[RealWorldMissionTurn],
    ) -> dict[str, int]:
        target_ids = _dedupe_ints(mission.target_vocabulary_ids or [])
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
        correction_payloads = [
            *[(attempt.correction_payload or {}) for attempt in attempts],
            *[(turn.correction_payload or {}) for turn in turns],
        ]
        summary = {
            "seen_context": 0,
            "recognized": 0,
            "produced_correct": 0,
            "produced_incorrect": 0,
            "missed_target": 0,
            "errata_created": 0,
        }
        explicit_event_ids: set[int] = set()
        for correction in correction_payloads:
            for event in correction.get("vocabulary_events") or []:
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
        for word_id in target_ids:
            word = by_id.get(word_id)
            if not word or word_id in explicit_event_ids:
                continue
            seen_results.append(
                credit_service.apply(
                    user=user,
                    word=word,
                    event_type="seen_context",
                    source_type="mission",
                    context=mission.title,
                    source_payload={
                        "mission_id": str(mission.id),
                        "mission_type": mission.mission_type,
                        "reason": "mission_target_context",
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

    def complete(self, *, user: User, mission: RealWorldMission) -> RealWorldMission:
        attempts = mission.attempts or []
        turns = [turn for turn in (mission.turns or []) if turn.role == "user"]
        errata_count = sum(len((attempt.correction_payload or {}).get("errata") or []) for attempt in attempts)
        errata_count += sum(len((turn.correction_payload or {}).get("errata") or []) for turn in turns)
        srs_result = MissionSRSService(self.db).seed_phrase_bank(user=user, mission=mission)
        vocabulary_credit = self._apply_target_vocabulary_credit(
            user=user,
            mission=mission,
            attempts=attempts,
            turns=turns,
        )
        debrief = MissionDebriefService().build(
            mission=mission,
            attempts=attempts,
            turns=turns,
            errata_count=errata_count,
            srs_result=srs_result,
        )
        outcome: dict[str, Any] | None = None
        if getattr(mission, "serial_thread_id", None):
            conversation_service = MissionConversationService(self.db)
            state_delta = conversation_service.resolve_outcome(mission=mission, attempts=attempts, turns=mission.turns or [])
            hook = conversation_service.resolve_hook(mission=mission, state_delta=state_delta)
            reply_text = self._serial_reply_text(mission=mission, state_delta=state_delta, turns=mission.turns or [])
            if state_delta or hook or reply_text:
                outcome = {
                    "reply_text": reply_text,
                    "state_delta": state_delta,
                    "hook": hook,
                }
        mission.status = "completed"
        mission.completed_at = datetime.now(timezone.utc)
        mission.recap_payload = {
            "attempts": len(attempts),
            "turns": len(turns),
            "errata_logged": errata_count,
            "vocabulary_credit": vocabulary_credit,
            "objectives": mission.objectives or [],
            "completed_at": mission.completed_at.isoformat(),
            **debrief,
        }
        if outcome:
            mission.recap_payload["outcome"] = outcome
        self.db.add(mission)
        self.db.commit()
        self.db.refresh(mission)
        return mission

    @staticmethod
    def _serial_reply_text(
        *,
        mission: RealWorldMission,
        state_delta: dict[str, Any],
        turns: list[RealWorldMissionTurn],
    ) -> str:
        latest_assistant = [
            turn.text for turn in sorted(turns or [], key=lambda item: item.turn_index) if turn.role == "assistant" and turn.text
        ]
        if latest_assistant:
            return latest_assistant[-1]
        updates = state_delta.get("set") if isinstance(state_delta, dict) else {}
        if isinstance(updates, dict) and updates.get("heating_fixed") in {True, "pending_tomorrow"}:
            return "Bien reçu. J'envoie un plombier demain matin entre 8 h et 10 h. Bonne installation."
        if isinstance(updates, dict) and updates.get("marchand_trust") == "cold":
            return "On ne se connaît pas. Reformulez correctement, s'il vous plaît."
        return "Je peux vous aider, mais il me manque un détail concret. Reformulez et dites-moi exactement ce qu'il faut faire."


class MissionConversationService:
    """Generate mission chat responses without duplicating the old audio route."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm_service or _safe_llm()

    def respond(self, *, user: User, mission: RealWorldMission, user_text: str) -> str:
        latest_progress = self._latest_objective_progress(mission)
        preliminary_branch = self.branch_state(mission=mission, user_text=user_text, assistant_text="")
        if not self.llm:
            return self._fallback_response(mission, branch=preliminary_branch, objective_progress=latest_progress)
        context = json.dumps(
            {
                "title": mission.title,
                "brief": mission.brief,
                "objectives": mission.objectives,
                "stakes_level": int(getattr(mission, "stakes_level", None) or 1),
                "source_snapshot": mission.source_snapshot,
                "target_vocabulary": (mission.prompt_payload or {}).get("target_vocabulary") or [],
                "learner_level": user.proficiency_level,
                "conversation_instruction": (mission.prompt_payload or {}).get("conversation_instruction"),
                "objective_progress": latest_progress,
                "branch_state": preliminary_branch,
            },
            ensure_ascii=False,
        )
        history = [
            {"role": turn.role if turn.role in {"user", "assistant"} else "assistant", "content": turn.text}
            for turn in sorted(mission.turns or [], key=lambda item: item.turn_index)
        ][-10:]
        messages = [
            {"role": "user", "content": f"Mission context: {context}"},
            *history,
        ]
        if not history or history[-1].get("content") != user_text:
            messages.append({"role": "user", "content": user_text})
        system = (
            "You are a French conversation partner inside a realistic mission. "
            "Stay in scenario, answer in French, keep replies to 1-3 short sentences, and end with a natural prompt. "
            "Treat this as a real back-and-forth. React to the learner's last answer, add one new concrete detail, "
            "then ask the next natural question. If branch_state is needs_detail, missing_next_step, or tone_mismatch, "
            "be confused, blocked, or socially cool in-fiction and ask for the missing detail or register repair. "
            "If objective_progress is all met and branch_state is understood, resolve the request in-fiction instead of surfacing a score. "
            "Do not explain grammar unless the learner asks."
        )
        try:
            result = self.llm.generate_chat_completion(
                messages=messages,
                system_prompt=system,
                temperature=0.7,
                max_tokens=220,
                model=settings.OPENAI_MISSION_FAST_MODEL,
                request_timeout=settings.MISSION_CHAT_TIMEOUT_SECONDS,
            )
            return result.content
        except LLMProviderError as exc:
            logger.debug("Mission conversation fallback", error=str(exc))
            return self._fallback_response(mission, branch=preliminary_branch, objective_progress=latest_progress)

    def _fallback_response(
        self,
        mission: RealWorldMission,
        *,
        branch: dict[str, Any] | None = None,
        objective_progress: list[dict[str, Any]] | None = None,
    ) -> str:
        user_turns = [turn for turn in (mission.turns or []) if turn.role == "user"]
        branch_state = (branch or {}).get("state")
        all_met = bool(objective_progress) and all(bool(item.get("met")) for item in objective_progress)
        if user_turns:
            if branch_state == "tone_mismatch":
                return "On ne se connaît pas encore. Reformulez plus poliment, s'il vous plaît, et je pourrai vous aider."
            if objective_progress and not all_met:
                missing = next((item for item in objective_progress if not item.get("met")), {})
                label = _compact_text(missing.get("label"), max_length=120) or "un détail important"
                return f"Je comprends l'idée, mais il me manque encore ceci : {label}. Ajoutez ce point et je pourrai avancer."
            if branch_state in {"needs_detail", "missing_next_step"}:
                return "Je peux vous aider, mais il me manque un détail concret. Quel est le problème exact et que souhaitez-vous que je fasse ?"
            if all_met or branch_state == "understood":
                if "heating" in f"{mission.title} {mission.brief} {(mission.prompt_payload or {}).get('messenger', {})}".lower():
                    return "Bien reçu. J'envoie quelqu'un demain matin entre 8 h et 10 h. Bonne installation."
                return "C'est clair, merci. Je m'en occupe et je vous confirme la suite dès que possible."
            if mission.mission_type == "travel_work":
                return "Très bien. Pour vous aider, j'ai besoin d'un détail: à quelle heure devez-vous repartir ?"
            if mission.mission_type == "news_summary":
                return "D'accord. Et selon toi, quelle conséquence concrète cette information peut avoir cette semaine ?"
            if mission.mission_type == "explain_plan":
                return "Je comprends. Quelle partie de ton plan pourrait changer si la situation devient plus compliquée ?"
            if mission.mission_type == "conversation":
                return "D'accord, je note la contrainte. Quelle solution préférez-vous maintenant ?"
            return "D'accord. Ajoute un détail pratique, puis dis-moi ce que tu veux demander à l'autre personne."
        opening = (mission.prompt_payload or {}).get("conversation_opening")
        if opening:
            return str(opening)
        return "D'accord. Donne-moi un détail de plus, et on continue la situation."

    def _latest_objective_progress(self, mission: RealWorldMission) -> list[dict[str, Any]]:
        candidates: list[tuple[datetime | None, dict[str, Any]]] = []
        for attempt in mission.attempts or []:
            payload = attempt.correction_payload or {}
            if payload.get("objective_progress"):
                candidates.append((attempt.created_at, payload))
        for turn in mission.turns or []:
            if turn.role != "user":
                continue
            payload = turn.correction_payload or {}
            if payload.get("objective_progress"):
                candidates.append((turn.created_at, payload))
        if not candidates:
            return []
        payload = sorted(candidates, key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc))[-1][1]
        return [item for item in payload.get("objective_progress") or [] if isinstance(item, dict)]

    def _latest_score(self, *, attempts: list[RealWorldMissionAttempt], turns: list[RealWorldMissionTurn]) -> float:
        candidates: list[tuple[datetime | None, float]] = []
        for attempt in attempts:
            candidates.append((attempt.created_at, float(attempt.score_0_4 or 0)))
        for turn in turns:
            if turn.role == "user":
                payload = turn.correction_payload or {}
                candidates.append((turn.created_at, float(payload.get("score_0_4") or 0)))
        if not candidates:
            return 0.0
        return sorted(candidates, key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc))[-1][1]

    def resolve_outcome(
        self,
        *,
        mission: RealWorldMission,
        attempts: list[RealWorldMissionAttempt],
        turns: list[RealWorldMissionTurn],
    ) -> dict[str, Any]:
        if not getattr(mission, "serial_thread_id", None):
            return {}
        thread = self.db.get(SerialThread, mission.serial_thread_id)
        if not thread:
            return {}
        progress = self._latest_objective_progress(mission)
        required_ids = {
            str(item.get("id"))
            for item in (mission.objectives or [])
            if item.get("required") is True and item.get("id")
        }
        if progress:
            met_ids = {str(item.get("id")) for item in progress if item.get("met")}
            required_met = required_ids.issubset(met_ids) if required_ids else all(bool(item.get("met")) for item in progress)
            all_met = all(bool(item.get("met")) for item in progress)
        else:
            required_met = False
            all_met = False
        score = self._latest_score(attempts=attempts, turns=turns)
        latest_user_text = self._latest_user_text(attempts=attempts, turns=turns)
        latest_assistant_text = self._latest_assistant_text(turns=turns)
        branch = self.branch_state(mission=mission, user_text=latest_user_text, assistant_text=latest_assistant_text)
        success = score >= 3 and required_met and (all_met or branch.get("state") == "understood")
        tone_failed = branch.get("state") == "tone_mismatch"
        known_state = thread.state or {}
        topic_text = f"{mission.title} {mission.brief} {mission.prompt_payload}".lower()
        is_episode_one = (mission.prompt_payload or {}).get("serial_reference") == "episode-01-beat-a"
        updates: dict[str, Any] = {}
        if is_episode_one:
            updates["heating_fixed"] = "pending_tomorrow" if success else False
            if success:
                updates["marchand_trust"] = "ok"
            elif tone_failed:
                updates["marchand_trust"] = "cold"
        elif "heating_fixed" in known_state or any(token in topic_text for token in ("heating", "radiateur", "chauffage")):
            updates["heating_fixed"] = "pending_tomorrow" if success else False
            if "marchand_trust" in known_state or "landlord" in topic_text or "propriétaire" in topic_text:
                updates["marchand_trust"] = "ok" if success else ("cold" if tone_failed else "neutral")
        else:
            updates["mission.last_outcome"] = "success" if success else ("tone_mismatch" if tone_failed else "needs_detail")
            updates["user.last_mission_success"] = success
        reason = (
            "Learner's message was clear and hit the required objectives."
            if success
            else "The world still needs a clearer detail, next step, or better register."
        )
        return {
            "set": updates,
            "reason": reason,
            "source": {"type": "mission", "id": str(mission.id), "score_0_4": score},
        }

    def resolve_hook(self, *, mission: RealWorldMission, state_delta: dict[str, Any]) -> dict[str, Any]:
        if not getattr(mission, "serial_thread_id", None) or not state_delta:
            return {}
        if self.llm:
            payload = {
                "mission": serialize_mission(mission, include_children=False),
                "state_delta": state_delta,
                "instructions": "Write a 1-2 sentence unresolved hook for the next Feuilleton beat.",
            }
            try:
                result = self.llm.generate_chat_completion(
                    messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                    system_prompt=(
                        "Return JSON with text, unresolved_question, next_beat_kind='feuilleton', and teaser. "
                        "The hook must be in-fiction, concrete, and unresolved."
                    ),
                    temperature=0.65,
                    max_tokens=260,
                    model=settings.OPENAI_MISSION_FAST_MODEL,
                    request_timeout=settings.MISSION_CHAT_TIMEOUT_SECONDS,
                )
                parsed = json.loads(result.content)
                if isinstance(parsed, dict) and parsed.get("text") and parsed.get("unresolved_question"):
                    return {
                        "text": str(parsed.get("text") or ""),
                        "unresolved_question": str(parsed.get("unresolved_question") or ""),
                        "next_beat_kind": "feuilleton",
                        "teaser": str(parsed.get("teaser") or ""),
                    }
            except (LLMProviderError, json.JSONDecodeError, ValueError, AttributeError) as exc:
                logger.debug("Mission hook fallback", error=str(exc))
        updates = state_delta.get("set") if isinstance(state_delta, dict) else {}
        if isinstance(updates, dict) and updates.get("heating_fixed") in {True, "pending_tomorrow"}:
            return {
                "text": "Tu raccroches. L'appartement est glacé, le silence total. Six étages plus bas, il y a de la lumière, du bruit, des rires — un café, encore ouvert.",
                "unresolved_question": "Who's down there, and what happens if you go in?",
                "next_beat_kind": "feuilleton",
                "teaser": "Tu n'as pas envie de rester seul ce soir.",
            }
        return {
            "text": "Tu relis le message. Rien n'est réglé encore, et dehors Paris continue comme si ta première nuit n'avait pas besoin d'aide.",
            "unresolved_question": "Who will help now, and what does this mistake change?",
            "next_beat_kind": "feuilleton",
            "teaser": "Il faut sortir de l'appartement.",
        }

    def turn_outcome(
        self,
        *,
        mission: RealWorldMission,
        user_text: str,
        assistant_text: str,
    ) -> dict[str, Any]:
        """Per-turn, in-fiction outcome the act screen can show before completion.

        Always returns the character reply + branch state. For serial missions it
        also reports whether the learner can advance, and (only when ready) the
        forward hook — so the costly hook generation is not paid on every turn.
        """
        reply_text = _compact_text(assistant_text, max_length=600)
        branch = self.branch_state(mission=mission, user_text=user_text, assistant_text=assistant_text)
        outcome: dict[str, Any] = {"reply_text": reply_text, "branch": branch}
        if not getattr(mission, "serial_thread_id", None):
            return outcome
        progress = self._latest_objective_progress(mission)
        required_ids = {
            str(item.get("id"))
            for item in (mission.objectives or [])
            if item.get("required") is True and item.get("id")
        }
        if progress:
            met_ids = {str(item.get("id")) for item in progress if item.get("met")}
            required_met = required_ids.issubset(met_ids) if required_ids else all(bool(item.get("met")) for item in progress)
        else:
            required_met = False
        ready = bool(progress) and required_met and branch.get("state") == "understood"
        outcome["ready_to_advance"] = ready
        if ready:
            state_delta = self.resolve_outcome(
                mission=mission,
                attempts=mission.attempts or [],
                turns=mission.turns or [],
            )
            hook = self.resolve_hook(mission=mission, state_delta=state_delta)
            if state_delta:
                outcome["state_delta"] = state_delta
            if hook:
                outcome["hook"] = hook
        return outcome

    @staticmethod
    def _latest_user_text(
        *,
        attempts: list[RealWorldMissionAttempt],
        turns: list[RealWorldMissionTurn],
    ) -> str:
        candidates: list[tuple[datetime | None, str]] = []
        for attempt in attempts:
            candidates.append((attempt.created_at, str((attempt.answer_payload or {}).get("text") or "")))
        for turn in turns:
            if turn.role == "user":
                candidates.append((turn.created_at, turn.text))
        if not candidates:
            return ""
        return sorted(candidates, key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc))[-1][1]

    @staticmethod
    def _latest_assistant_text(*, turns: list[RealWorldMissionTurn]) -> str:
        assistant_turns = [turn for turn in turns if turn.role == "assistant"]
        if not assistant_turns:
            return ""
        return sorted(assistant_turns, key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc))[-1].text

    def branch_state(self, *, mission: RealWorldMission, user_text: str, assistant_text: str) -> dict[str, Any]:
        text = _compact_text(user_text, max_length=500)
        words = re.findall(r"\S+", text)
        has_question = "?" in text or any(token in text.lower() for token in ("est-ce", "pouvez", "peux", "pourriez"))
        has_detail = len(words) >= 10 or any(char.isdigit() for char in text)
        messenger = (mission.prompt_payload or {}).get("messenger") or {}
        expected_register = " ".join(messenger.get("realism_rules") or []).lower()
        stakes_level = int(getattr(mission, "stakes_level", None) or (mission.prompt_payload or {}).get("stakes_level") or 1)
        formal_markers = any(token in text.lower() for token in ("vous", "pourriez", "serait-il", "merci par avance"))
        informal_markers = any(token in text.lower() for token in ("tu", "coucou", "bisous"))
        tone_ok = True
        if "formal" in expected_register and informal_markers and not formal_markers:
            tone_ok = False
        if "informal" in expected_register and formal_markers and not informal_markers:
            tone_ok = False
        if not has_detail:
            state = "needs_detail"
            label = "The other person needs one concrete detail."
            pressure = "Add time, place, number, reason, or constraint."
        elif not has_question:
            state = "missing_next_step"
            label = "The message explains, but does not invite the next move."
            pressure = "Ask for confirmation, permission, or a specific action."
        elif not tone_ok:
            state = "tone_mismatch"
            label = "The register does not quite fit the relationship."
            pressure = "Adjust tu/vous and warmth before using it."
        else:
            state = "understood"
            label = "They can respond without guessing."
            pressure = "Now keep the thread moving naturally."
        return {
            "state": state,
            "label": label,
            "pressure": pressure,
            "has_detail": has_detail,
            "has_question": has_question,
            "tone_ok": tone_ok,
            "stakes_level": stakes_level,
            "tone_critical": stakes_level >= 3,
            "assistant_continuation": _compact_text(assistant_text, max_length=240),
        }


def serialize_mission(mission: RealWorldMission | None, *, include_children: bool = True) -> dict[str, Any] | None:
    if not mission:
        return None
    payload = {
        "id": str(mission.id),
        "status": mission.status,
        "cadence": mission.cadence,
        "mission_type": mission.mission_type,
        "mission_format": (mission.prompt_payload or {}).get("mission_format")
        or (mission.prompt_payload or {}).get("serial_mission_format")
        or "chat_message",
        "stakes_level": int(getattr(mission, "stakes_level", None) or 1),
        "atelier_session_id": str(mission.atelier_session_id) if mission.atelier_session_id else None,
        "serial_thread_id": str(mission.serial_thread_id) if getattr(mission, "serial_thread_id", None) else None,
        "episode_index": mission.episode_index,
        "iso_year": mission.iso_year,
        "iso_week": mission.iso_week,
        "title": mission.title,
        "brief": mission.brief,
        "selected_concept_ids": mission.selected_concept_ids or [],
        "target_errata_ids": mission.target_errata_ids or [],
        "target_vocabulary_ids": mission.target_vocabulary_ids or [],
        "target_vocabulary": (mission.prompt_payload or {}).get("target_vocabulary") or [],
        "source_snapshot": mission.source_snapshot or {},
        "objectives": mission.objectives or [],
        "prompt_payload": mission.prompt_payload or {},
        "recap": mission.recap_payload or {},
        "created_at": mission.created_at.isoformat() if mission.created_at else None,
        "started_at": mission.started_at.isoformat() if mission.started_at else None,
        "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
    }
    outcome = (mission.recap_payload or {}).get("outcome") if mission.recap_payload else None
    if getattr(mission, "serial_thread_id", None) and isinstance(outcome, dict):
        payload["outcome"] = outcome
    if include_children:
        payload["attempts"] = [
            {
                "id": str(attempt.id),
                "mode": attempt.mode,
                "answer_payload": attempt.answer_payload or {},
                "correction": attempt.correction_payload or {},
                "verdict": attempt.verdict,
                "score_0_4": attempt.score_0_4,
                "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
            }
            for attempt in sorted(mission.attempts or [], key=lambda item: item.created_at)
        ]
        payload["turns"] = [
            {
                "id": str(turn.id),
                "turn_index": turn.turn_index,
                "role": turn.role,
                "mode": turn.mode,
                "text": turn.text,
                "audio_payload": turn.audio_payload or {},
                "correction": turn.correction_payload or {},
                "created_at": turn.created_at.isoformat() if turn.created_at else None,
            }
            for turn in sorted(mission.turns or [], key=lambda item: item.turn_index)
        ]
    return payload


__all__ = [
    "MissionConversationService",
    "MissionCorrectionService",
    "MissionDebriefService",
    "MissionGenerator",
    "MissionSRSService",
    "MissionScheduler",
    "serialize_mission",
]
