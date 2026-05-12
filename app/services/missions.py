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
from app.db.models.vocabulary import VocabularyWord
from app.db.models.user import User
from app.services.atelier_assets import AtelierAssetService
from app.services.error_memory import ErrorMemoryService, serialize_error_memory
from app.services.llm_service import LLMProviderError, LLMService
from app.services.news_service import NewsService
from app.services.progress import ProgressService


MISSION_CORRECTION_PROMPT_VERSION = "mission-correction-v1"
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
        use_news: bool = True,
        custom_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mission_type = mission_type if mission_type in MISSION_TEMPLATES else "message"
        custom_context = self._custom_context(custom_context)
        concepts = self._select_concepts(
            user=user,
            atelier_session=atelier_session,
            preferred_concept_ids=preferred_concept_ids,
            limit=3,
        )
        errata = self._select_errata(user=user, preferred_errata_ids=preferred_errata_ids, limit=3)
        source_snapshot = await self._source_snapshot(
            user=user,
            mission_type=mission_type,
            use_news=use_news,
        )
        objectives = self._objectives(mission_type=mission_type, concepts=concepts, errata=errata, source_snapshot=source_snapshot)
        title, brief = self._brief(mission_type=mission_type, cadence=cadence, source_snapshot=source_snapshot, concepts=concepts)
        messenger = self._messenger_payload(mission_type=mission_type, source_snapshot=source_snapshot, concepts=concepts)
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
            "experience": "reality_messenger",
            "custom_context": custom_context,
            "messenger": messenger,
            "conversation_opening": conversation_opening,
            "conversation_title": self._conversation_title(mission_type),
            "conversation_instruction": self._conversation_instruction(mission_type),
            "writing_title": self._writing_title(mission_type),
            "writing_instruction": self._writing_instruction(mission_type),
            "writing_placeholder": self._placeholder(mission_type),
            "min_words": 50 if mission_type != "message" else 35,
            "max_words": 150,
            "target_register": "natural French; formal only when the scenario requires it",
            "show_source_context": mission_type == "news_summary",
            "source_context_card": self._source_context_card(source_snapshot) if mission_type == "news_summary" else None,
            "branching": {
                "enabled": True,
                "signals": ["understood", "needs_detail", "too_vague", "tone_mismatch"],
            },
        }
        return {
            "title": title,
            "brief": brief,
            "selected_concept_ids": [concept.id for concept in concepts],
            "target_errata_ids": _source_ids(errata),
            "target_vocabulary_ids": [error.linked_word_id for error in errata if error.linked_word_id],
            "source_snapshot": source_snapshot,
            "objectives": objectives,
            "prompt_payload": prompt_payload,
        }

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
        source_snapshot: dict[str, Any],
    ) -> list[dict[str, Any]]:
        asset_service = AtelierAssetService(self.db)
        objectives = [
            {
                "id": "real_world_task",
                "label": self._task_label(mission_type),
                "target_count": 1,
                "kind": "communication",
                "required": True,
            }
        ]
        for index, concept in enumerate(concepts[:3], start=1):
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
        for error in errata[:2]:
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

    def correct_submission(self, *, user: User, mission: RealWorldMission, text: str, mode: str) -> dict[str, Any]:
        correction = self._llm_correction(user=user, mission=mission, text=text, mode=mode) or self._fallback_correction(
            mission=mission,
            text=text,
        )
        correction["errata"] = [self._normalize_erratum(item, mission) for item in correction.get("errata") or []]
        correction["correction_debug"] = {
            "prompt_version": MISSION_CORRECTION_PROMPT_VERSION,
            "fallback_used": correction.get("_fallback_used", False),
            "model": correction.get("_model"),
        }
        correction.pop("_fallback_used", None)
        correction.pop("_model", None)
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

    def _fallback_correction(self, *, mission: RealWorldMission, text: str) -> dict[str, Any]:
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
        errata: list[dict[str, Any]] = []
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
        return {
            "verdict": "accepted" if stripped else "needs_revision",
            "score_0_4": 3 if len(words) >= 8 else (2 if stripped else 1),
            "corrected_answer": stripped,
            "objective_progress": objective_progress,
            "concept_hits": [],
            "missing_targets": missing_targets[:4],
            "errata": errata,
            "vocabulary_links": [],
            "_fallback_used": True,
            "_model": None,
        }

    def _normalize_erratum(self, erratum: dict[str, Any], mission: RealWorldMission) -> dict[str, Any]:
        external_id = erratum.get("external_id")
        concept_id = None
        if external_id:
            concept = self.db.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).first()
            concept_id = concept.id if concept else None
        if not concept_id and (mission.selected_concept_ids or []):
            concept_id = int((mission.selected_concept_ids or [0])[0] or 0) or None
        return {
            **erratum,
            "why_wrong": _clean_feedback(erratum.get("why_wrong")),
            "repair_hint": _clean_feedback(erratum.get("repair_hint")),
            "concept_id": concept_id,
            "error_category": erratum.get("error_category") or "grammar",
        }


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
        use_news: bool = True,
        custom_scenario: str | None = None,
        desired_outcome: str | None = None,
        relationship: str | None = None,
        register: str | None = None,
    ) -> RealWorldMission:
        custom_context = {
            "scenario": custom_scenario,
            "desired_outcome": desired_outcome,
            "relationship": relationship,
            "register": register,
        }
        has_custom_context = bool(_compact_text(custom_scenario))
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
            use_news=use_news,
            custom_context=custom_context if has_custom_context else None,
        )
        iso = date.today().isocalendar() if cadence == "weekly" and not has_custom_context else None
        mission = RealWorldMission(
            user_id=user.id,
            atelier_session_id=atelier_session.id if atelier_session else None,
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

    def get(self, *, user: User, mission_id: UUID) -> RealWorldMission | None:
        return (
            self.db.query(RealWorldMission)
            .filter(RealWorldMission.id == mission_id, RealWorldMission.user_id == user.id)
            .first()
        )

    def complete(self, *, user: User, mission: RealWorldMission) -> RealWorldMission:
        attempts = mission.attempts or []
        turns = [turn for turn in (mission.turns or []) if turn.role == "user"]
        errata_count = sum(len((attempt.correction_payload or {}).get("errata") or []) for attempt in attempts)
        errata_count += sum(len((turn.correction_payload or {}).get("errata") or []) for turn in turns)
        srs_result = MissionSRSService(self.db).seed_phrase_bank(user=user, mission=mission)
        debrief = MissionDebriefService().build(
            mission=mission,
            attempts=attempts,
            turns=turns,
            errata_count=errata_count,
            srs_result=srs_result,
        )
        mission.status = "completed"
        mission.completed_at = datetime.now(timezone.utc)
        mission.recap_payload = {
            "attempts": len(attempts),
            "turns": len(turns),
            "errata_logged": errata_count,
            "objectives": mission.objectives or [],
            "completed_at": mission.completed_at.isoformat(),
            **debrief,
        }
        self.db.add(mission)
        self.db.commit()
        self.db.refresh(mission)
        return mission


class MissionConversationService:
    """Generate mission chat responses without duplicating the old audio route."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm_service or _safe_llm()

    def respond(self, *, user: User, mission: RealWorldMission, user_text: str) -> str:
        if not self.llm:
            return self._fallback_response(mission)
        context = json.dumps(
            {
                "title": mission.title,
                "brief": mission.brief,
                "objectives": mission.objectives,
                "source_snapshot": mission.source_snapshot,
                "learner_level": user.proficiency_level,
                "conversation_instruction": (mission.prompt_payload or {}).get("conversation_instruction"),
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
            "then ask the next natural question. Do not explain grammar unless the learner asks."
        )
        try:
            result = self.llm.generate_chat_completion(
                messages=messages,
                system_prompt=system,
                temperature=0.7,
                max_tokens=220,
            )
            return result.content
        except LLMProviderError as exc:
            logger.debug("Mission conversation fallback", error=str(exc))
            return self._fallback_response(mission)

    def _fallback_response(self, mission: RealWorldMission) -> str:
        user_turns = [turn for turn in (mission.turns or []) if turn.role == "user"]
        if user_turns:
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

    def branch_state(self, *, mission: RealWorldMission, user_text: str, assistant_text: str) -> dict[str, Any]:
        text = _compact_text(user_text, max_length=500)
        words = re.findall(r"\S+", text)
        has_question = "?" in text or any(token in text.lower() for token in ("est-ce", "pouvez", "peux", "pourriez"))
        has_detail = len(words) >= 10 or any(char.isdigit() for char in text)
        messenger = (mission.prompt_payload or {}).get("messenger") or {}
        expected_register = " ".join(messenger.get("realism_rules") or []).lower()
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
        "atelier_session_id": str(mission.atelier_session_id) if mission.atelier_session_id else None,
        "iso_year": mission.iso_year,
        "iso_week": mission.iso_week,
        "title": mission.title,
        "brief": mission.brief,
        "selected_concept_ids": mission.selected_concept_ids or [],
        "target_errata_ids": mission.target_errata_ids or [],
        "target_vocabulary_ids": mission.target_vocabulary_ids or [],
        "source_snapshot": mission.source_snapshot or {},
        "objectives": mission.objectives or [],
        "prompt_payload": mission.prompt_payload or {},
        "recap": mission.recap_payload or {},
        "created_at": mission.created_at.isoformat() if mission.created_at else None,
        "started_at": mission.started_at.isoformat() if mission.started_at else None,
        "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
    }
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
