"""Inline learning-moment planning for conversational sessions."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence, TYPE_CHECKING
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.core.error_detection import ErrorDetectionResult
from app.db.models.error import UserError
from app.db.models.session import ConversationMessage, LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.brief_exercise_service import BriefExerciseService
from app.services.grammar import GrammarService
from app.services.grammar_feedback import is_concept_demonstrated
from app.services.llm_service import LLMService
from app.services.progress import ProgressService
from app.services.unified_srs import ItemType, UnifiedSRSService

if TYPE_CHECKING:
    from app.core.conversation import ConversationPlan
    from app.services.session_service import WordFeedback
    from app.db.models.grammar import GrammarConcept, UserGrammarProgress


PRIMARY_VOCAB_DECK_NAME = "Französisch 5000::1. FR → DE"
BLOCKING_MOMENT_KINDS = {"vocab_check", "grammar_challenge", "grammar_repair", "error_repair"}
EXPLICIT_MOMENT_KINDS = {
    "vocab_boost",
    "vocab_check",
    "grammar_challenge",
    "grammar_repair",
    "error_repair",
}


def _run_async(coro):
    """Run a coroutine from a synchronous service context."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _normalize_answer(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _split_expected_answers(value: str | None) -> list[str]:
    if not value:
        return []
    parts: list[str] = []
    for chunk in value.replace("/", ";").split(";"):
        normalized = _normalize_answer(chunk)
        if normalized:
            parts.append(normalized)
    return parts


def _solution_hint(solution: str | None, explanation: str | None = None) -> str | None:
    parts: list[str] = []
    if solution:
        parts.append(f"Short solution: {solution}")
    if explanation:
        parts.append(explanation)
    return "\n".join(parts) if parts else None


@dataclass(slots=True)
class PlannedMoment:
    """Normalized inline learning moment before persistence."""

    kind: str
    source_type: str
    source_id: str | None
    source_deck_name: str | None
    title: str
    body: str
    input_mode: str
    choices: list[dict[str, str]] = field(default_factory=list)
    prefill_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MomentEvaluation:
    """Result of resolving a learning moment."""

    moment: SessionLearningMoment
    is_correct: bool | None
    score_0_10: float | None
    feedback_summary: str
    next_step_hint: str | None = None


@dataclass(slots=True)
class GrammarContextEvaluation:
    """Best-effort evaluation of a grammar concept inside a normal reply."""

    used_target_concept: bool
    score_0_10: float
    feedback_summary: str
    retry_needed: bool


class GrammarContextEvaluator:
    """Evaluate whether a learner demonstrated the target grammar concept."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service
        self._cache: dict[tuple[int, str, str], GrammarContextEvaluation] = {}

    def evaluate(
        self,
        *,
        concept: "GrammarConcept",
        assistant_prompt: str,
        learner_reply: str,
        error_result: ErrorDetectionResult,
    ) -> GrammarContextEvaluation:
        key = (concept.id, assistant_prompt.strip(), learner_reply.strip())
        if key in self._cache:
            return self._cache[key]

        fallback = self._heuristic_evaluation(
            concept=concept,
            learner_reply=learner_reply,
            error_result=error_result,
        )
        if not self.llm_service:
            self._cache[key] = fallback
            return fallback

        try:
            result = self.llm_service.generate_chat_completion(
                [
                    {
                        "role": "user",
                        "content": (
                            "Evaluate whether the learner used the target French grammar concept.\n"
                            f"Concept: {concept.name}\n"
                            f"Description: {concept.description or ''}\n"
                            f"Examples: {concept.examples or ''}\n"
                            f"Assistant prompt: {assistant_prompt}\n"
                            f"Learner reply: {learner_reply}\n"
                            "Return JSON with keys used_target_concept (bool), "
                            "score_0_10 (number), feedback_summary (string), retry_needed (bool)."
                        ),
                    }
                ],
                temperature=0.0,
                max_tokens=220,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(result.content)
            evaluation = GrammarContextEvaluation(
                used_target_concept=bool(parsed.get("used_target_concept")),
                score_0_10=float(parsed.get("score_0_10", fallback.score_0_10)),
                feedback_summary=str(parsed.get("feedback_summary") or fallback.feedback_summary),
                retry_needed=bool(parsed.get("retry_needed")),
            )
        except Exception:
            evaluation = fallback

        self._cache[key] = evaluation
        return evaluation

    def _heuristic_evaluation(
        self,
        *,
        concept: "GrammarConcept",
        learner_reply: str,
        error_result: ErrorDetectionResult,
    ) -> GrammarContextEvaluation:
        grammar_errors = [item for item in error_result.errors if item.category == "grammar"]
        token_count = len([part for part in learner_reply.split() if part.strip()])

        if grammar_errors:
            return GrammarContextEvaluation(
                used_target_concept=False,
                score_0_10=3.0,
                feedback_summary=grammar_errors[0].message,
                retry_needed=True,
            )

        if token_count < 4:
            return GrammarContextEvaluation(
                used_target_concept=False,
                score_0_10=4.0,
                feedback_summary=f"Try one more sentence using {concept.name}.",
                retry_needed=True,
            )

        if not self._matches_concept_pattern(concept=concept, learner_reply=learner_reply):
            return GrammarContextEvaluation(
                used_target_concept=False,
                score_0_10=5.0,
                feedback_summary=f"Try one more sentence that clearly uses {concept.name}.",
                retry_needed=False,
            )

        return GrammarContextEvaluation(
            used_target_concept=True,
            score_0_10=9.0,
            feedback_summary=f"Reviewed {concept.name} in context.",
            retry_needed=False,
        )

    def _matches_concept_pattern(self, *, concept: "GrammarConcept", learner_reply: str) -> bool:
        return is_concept_demonstrated(concept, learner_reply)


class SessionMomentPlanner:
    """Plan and resolve inline learning moments within a live session."""

    primary_vocab_deck_name = PRIMARY_VOCAB_DECK_NAME

    def __init__(
        self,
        db: Session,
        *,
        progress_service: ProgressService,
        grammar_service: GrammarService,
        llm_service: LLMService | None = None,
    ) -> None:
        self.db = db
        self.progress_service = progress_service
        self.grammar_service = grammar_service
        self.llm_service = llm_service
        self.grammar_evaluator = GrammarContextEvaluator(llm_service)
        self.brief_exercise_service = BriefExerciseService(db, llm_service) if llm_service else None

    # ------------------------------------------------------------------
    # Fetch helpers
    # ------------------------------------------------------------------
    def get_pending_moment(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
    ) -> SessionLearningMoment | None:
        return (
            self.db.query(SessionLearningMoment)
            .filter(
                SessionLearningMoment.session_id == session_id,
                SessionLearningMoment.user_id == user_id,
                SessionLearningMoment.status == "pending",
            )
            .order_by(SessionLearningMoment.created_at.desc())
            .first()
        )

    def get_pending_moment_by_id(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        moment_id: UUID,
    ) -> SessionLearningMoment | None:
        return (
            self.db.query(SessionLearningMoment)
            .filter(
                SessionLearningMoment.id == moment_id,
                SessionLearningMoment.session_id == session_id,
                SessionLearningMoment.user_id == user_id,
            )
            .first()
        )

    def build_message_moment_map(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        message_ids: Sequence[UUID],
    ) -> dict[UUID, SessionLearningMoment]:
        if not message_ids:
            return {}
        rows = (
            self.db.query(SessionLearningMoment)
            .filter(
                SessionLearningMoment.session_id == session_id,
                SessionLearningMoment.user_id == user_id,
                SessionLearningMoment.anchor_message_id.in_(message_ids),
                SessionLearningMoment.status == "pending",
            )
            .all()
        )
        return {
            row.anchor_message_id: row
            for row in rows
            if row.anchor_message_id is not None
        }

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def serialize_moment(self, moment: SessionLearningMoment | None) -> dict[str, Any] | None:
        if not moment:
            return None
        payload = dict(moment.prompt_payload or {})
        payload.update(
            {
                "id": str(moment.id),
                "kind": moment.kind,
                "source_type": moment.source_type,
                "status": moment.status,
            }
        )
        return payload

    def serialize_result(self, evaluation: MomentEvaluation) -> dict[str, Any]:
        return {
            "moment_id": str(evaluation.moment.id),
            "is_correct": evaluation.is_correct,
            "score_0_10": evaluation.score_0_10,
            "feedback_summary": evaluation.feedback_summary,
            "next_step_hint": evaluation.next_step_hint,
        }

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------
    def plan_next_moment(
        self,
        *,
        session: LearningSession,
        user: User,
        anchor_message: ConversationMessage,
        conversation_plan: "ConversationPlan",
        due_errors: Sequence[UserError] | None = None,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None = None,
        last_error_result: ErrorDetectionResult | None = None,
        word_feedback: Sequence["WordFeedback"] | None = None,
    ) -> SessionLearningMoment | None:
        if not settings.SESSION_INLINE_MOMENTS_ENABLED:
            return None
        if self.get_pending_moment(session_id=session.id, user_id=user.id):
            return None
        if anchor_message.sequence_number <= 1:
            return None

        planned = (
            self._plan_immediate_repair(due_grammar=due_grammar, last_error_result=last_error_result)
            or self._plan_due_error_repair(due_errors=due_errors, last_error_result=last_error_result)
            or self._plan_due_grammar_challenge(session=session, due_grammar=due_grammar)
            or self._plan_vocab_check(
                session=session,
                conversation_plan=conversation_plan,
                word_feedback=word_feedback,
            )
            or self._plan_vocab_boost(
                session=session,
                conversation_plan=conversation_plan,
            )
        )

        if not planned:
            return None
        return self._create_moment(
            session=session,
            user=user,
            anchor_message=anchor_message,
            planned=planned,
        )

    def _create_moment(
        self,
        *,
        session: LearningSession,
        user: User,
        anchor_message: ConversationMessage,
        planned: PlannedMoment,
    ) -> SessionLearningMoment:
        moment = SessionLearningMoment(
            session_id=session.id,
            user_id=user.id,
            anchor_message_id=anchor_message.id,
            kind=planned.kind,
            source_type=planned.source_type,
            source_id=planned.source_id,
            source_deck_name=planned.source_deck_name,
            status="pending",
            prompt_payload={
                "title": planned.title,
                "body": planned.body,
                "input_mode": planned.input_mode,
                "choices": planned.choices,
                "prefill_text": planned.prefill_text,
                "metadata": planned.metadata,
            },
        )
        self.db.add(moment)
        self.db.flush([moment])
        self.sync_anchor_message_snapshot(moment)
        logger.info(
            "session_moment_presented",
            session_id=str(session.id),
            moment_id=str(moment.id),
            kind=moment.kind,
            source_type=moment.source_type,
        )
        return moment

    def _plan_immediate_repair(
        self,
        *,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None,
        last_error_result: ErrorDetectionResult | None,
    ) -> PlannedMoment | None:
        if not due_grammar or not last_error_result or not last_error_result.errors:
            return None
        grammar_errors = [item for item in last_error_result.errors if item.category == "grammar"]
        if not grammar_errors:
            return None
        primary = grammar_errors[0]
        correct_answer = primary.suggestion or primary.span
        return PlannedMoment(
            kind="grammar_repair",
            source_type="grammar",
            source_id=None,
            source_deck_name=None,
            title="Try that sentence again",
            body=primary.message,
            input_mode="free_text",
            metadata={
                "exercise_type": "correction",
                "prompt": primary.message,
                "correct_answer": correct_answer,
                "retry_span": primary.span,
                "example_format": correct_answer,
                "solution_brief": correct_answer,
            },
        )

    def _plan_due_error_repair(
        self,
        *,
        due_errors: Sequence[UserError] | None,
        last_error_result: ErrorDetectionResult | None,
    ) -> PlannedMoment | None:
        if not due_errors:
            return None
        top_error = next((item for item in due_errors if (item.lapses or 0) >= 2), None)
        if not top_error:
            return None
        if last_error_result and not any(
            item.category == top_error.error_category for item in last_error_result.errors
        ):
            return None

        payload = self._generate_error_repair_payload(top_error)
        return PlannedMoment(
            kind="error_repair",
            source_type="error",
            source_id=str(top_error.id),
            source_deck_name=None,
            title=payload["title"],
            body=payload["body"],
            input_mode="free_text",
            metadata=payload["metadata"],
        )

    def _plan_due_grammar_challenge(
        self,
        *,
        session: LearningSession,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None,
    ) -> PlannedMoment | None:
        if not due_grammar:
            return None
        concept, _ = due_grammar[0]
        if self._has_recent_grammar_evidence(session=session, concept_id=concept.id):
            return None
        if not self._can_schedule_explicit(session=session):
            return None

        payload = self._generate_grammar_challenge_payload(concept)
        return PlannedMoment(
            kind="grammar_challenge",
            source_type="grammar",
            source_id=str(concept.id),
            source_deck_name=None,
            title=payload["title"],
            body=payload["body"],
            input_mode="free_text",
            metadata=payload["metadata"],
        )

    def _plan_vocab_check(
        self,
        *,
        session: LearningSession,
        conversation_plan: "ConversationPlan",
        word_feedback: Sequence["WordFeedback"] | None,
    ) -> PlannedMoment | None:
        if not self._can_schedule_explicit(session=session):
            return None
        if not self._should_trigger_vocab_check(session=session, word_feedback=word_feedback):
            return None
        word = self._select_primary_deck_word(conversation_plan=conversation_plan)
        if not word:
            return None
        prompt, accepted = self._build_vocab_check_prompt(word)
        if not accepted:
            return None
        return PlannedMoment(
            kind="vocab_check",
            source_type="vocabulary",
            source_id=str(word.id),
            source_deck_name=word.deck_name,
            title=f"Quick check: {word.word}",
            body=prompt,
            input_mode="free_text",
            metadata={
                "word_id": word.id,
                "word": word.word,
                "translation": word.german_translation or word.english_translation,
                "correct_answer": accepted[0],
                "accepted_answers": accepted,
                "deck_name": word.deck_name,
                "solution_brief": accepted[0],
            },
        )

    def _plan_vocab_boost(
        self,
        *,
        session: LearningSession,
        conversation_plan: "ConversationPlan",
    ) -> PlannedMoment | None:
        if not self._can_schedule_explicit(session=session):
            return None
        word = self._select_primary_deck_word(conversation_plan=conversation_plan)
        if not word:
            return None
        translation = word.german_translation or word.english_translation or "this word"
        return PlannedMoment(
            kind="vocab_boost",
            source_type="vocabulary",
            source_id=str(word.id),
            source_deck_name=word.deck_name,
            title=f"Use {word.word}",
            body=f"Answer in French and naturally include `{word.word}` ({translation}).",
            input_mode="chips",
            metadata={
                "word_id": word.id,
                "word": word.word,
                "translation": translation,
                "deck_name": word.deck_name,
            },
        )

    def _select_primary_deck_word(
        self,
        *,
        conversation_plan: "ConversationPlan",
    ) -> VocabularyWord | None:
        for item in conversation_plan.queue_items:
            if item.word.deck_name == self.primary_vocab_deck_name:
                return item.word
        for item in conversation_plan.queue_items:
            if item.word.language == "fr":
                return item.word
        return None

    def _build_vocab_check_prompt(self, word: VocabularyWord) -> tuple[str, list[str]]:
        translation = word.german_translation or word.english_translation
        accepted = _split_expected_answers(translation)
        if accepted:
            return (f"What does `{word.word}` mean?", accepted)
        if word.example_sentence:
            return (
                f"Use `{word.word}` in a short French sentence.",
                [word.word.lower()],
            )
        return ("", [])

    def _generate_grammar_challenge_payload(self, concept: "GrammarConcept") -> dict[str, Any]:
        if self.brief_exercise_service is not None:
            try:
                response = _run_async(
                    self.brief_exercise_service.generate_grammar_exercises(concept.id)
                )
                exercises = response.get("exercises", []) if isinstance(response, dict) else []
                if exercises:
                    exercise = exercises[0]
                    return {
                        "title": f"Practice {concept.name}",
                        "body": exercise.get("prompt") or exercise.get("instruction") or concept.name,
                        "metadata": {
                            "concept_id": concept.id,
                            "concept_name": concept.name,
                            "exercise_type": exercise.get("type", "short_answer"),
                            "prompt": exercise.get("prompt", ""),
                            "instruction": exercise.get("instruction"),
                            "correct_answer": exercise.get("correct_answer"),
                            "hint": exercise.get("hint"),
                            "example_format": exercise.get("correct_answer"),
                            "solution_brief": exercise.get("correct_answer"),
                        },
                    }
            except Exception as exc:
                logger.warning("Unable to generate grammar challenge", concept_id=concept.id, error=str(exc))

        return {
            "title": f"Practice {concept.name}",
            "body": concept.description or f"Write one sentence using {concept.name}.",
            "metadata": {
                "concept_id": concept.id,
                "concept_name": concept.name,
                "exercise_type": "short_answer",
                "prompt": concept.description or f"Write one sentence using {concept.name}.",
                "correct_answer": concept.examples or concept.name,
                "example_format": concept.examples or concept.name,
                "solution_brief": concept.examples or concept.name,
            },
        }

    def _generate_error_repair_payload(self, error: UserError) -> dict[str, Any]:
        if self.brief_exercise_service is not None:
            try:
                response = _run_async(self.brief_exercise_service.generate_error_exercise(error.id))
                if isinstance(response, dict) and response.get("correct_answer"):
                    return {
                        "title": "Repair this recurring mistake",
                        "body": response.get("prompt") or error.original_text or "Try again.",
                        "metadata": {
                            "error_id": str(error.id),
                            "exercise_type": response.get("exercise_type", "correction"),
                            "prompt": response.get("prompt") or error.original_text or "",
                            "correct_answer": response.get("correct_answer") or error.correction or "",
                            "explanation": response.get("explanation") or error.context_snippet,
                            "memory_tip": response.get("memory_tip"),
                            "example_format": response.get("correct_answer") or error.correction or "",
                            "solution_brief": response.get("correct_answer") or error.correction or "",
                        },
                    }
            except Exception as exc:
                logger.warning("Unable to generate error repair prompt", error_id=str(error.id), error=str(exc))

        return {
            "title": "Repair this recurring mistake",
            "body": error.original_text or "Correct this mistake.",
            "metadata": {
                "error_id": str(error.id),
                "exercise_type": "correction",
                "prompt": error.original_text or "",
                "correct_answer": error.correction or "",
                "explanation": error.context_snippet,
                "example_format": error.correction or "",
                "solution_brief": error.correction or "",
            },
        }

    def _can_schedule_explicit(self, *, session: LearningSession) -> bool:
        explicit_count = (
            self.db.query(SessionLearningMoment)
            .filter(
                SessionLearningMoment.session_id == session.id,
                SessionLearningMoment.kind.in_(tuple(EXPLICIT_MOMENT_KINDS)),
            )
            .count()
        )
        if explicit_count >= self._explicit_limit(session.planned_duration_minutes or 5):
            return False

        last_explicit = (
            self.db.query(SessionLearningMoment)
            .filter(
                SessionLearningMoment.session_id == session.id,
                SessionLearningMoment.kind.in_(tuple(EXPLICIT_MOMENT_KINDS)),
            )
            .order_by(SessionLearningMoment.created_at.desc())
            .first()
        )
        if not last_explicit or not last_explicit.anchor_message_id:
            return True

        anchor_message = self.db.get(ConversationMessage, last_explicit.anchor_message_id)
        if not anchor_message:
            return True

        learner_turns_since = (
            self.db.query(ConversationMessage)
            .filter(
                ConversationMessage.session_id == session.id,
                ConversationMessage.sender == "user",
                ConversationMessage.sequence_number > anchor_message.sequence_number,
            )
            .count()
        )
        return learner_turns_since >= 2

    def _explicit_limit(self, planned_duration_minutes: int) -> int:
        if planned_duration_minutes < 7:
            return 2
        if planned_duration_minutes <= 15:
            return 3
        return 5

    def _has_recent_grammar_evidence(self, *, session: LearningSession, concept_id: int) -> bool:
        recent = (
            self.db.query(SessionLearningMoment)
            .filter(
                SessionLearningMoment.session_id == session.id,
                SessionLearningMoment.source_type == "grammar",
                SessionLearningMoment.source_id == str(concept_id),
                SessionLearningMoment.status == "completed",
            )
            .order_by(SessionLearningMoment.created_at.desc())
            .first()
        )
        if not recent:
            return False
        anchor = self.db.get(ConversationMessage, recent.anchor_message_id) if recent.anchor_message_id else None
        if not anchor:
            return False
        learner_turns_since = (
            self.db.query(ConversationMessage)
            .filter(
                ConversationMessage.session_id == session.id,
                ConversationMessage.sender == "user",
                ConversationMessage.sequence_number > anchor.sequence_number,
            )
            .count()
        )
        return learner_turns_since < 2

    def _should_trigger_vocab_check(
        self,
        *,
        session: LearningSession,
        word_feedback: Sequence["WordFeedback"] | None,
    ) -> bool:
        if not word_feedback:
            return False
        ignored_current = all(not item.was_used for item in word_feedback)
        if not ignored_current:
            return False

        previous_user = (
            self.db.query(ConversationMessage)
            .filter(
                ConversationMessage.session_id == session.id,
                ConversationMessage.sender == "user",
            )
            .order_by(ConversationMessage.sequence_number.desc())
            .offset(1)
            .first()
        )
        if not previous_user:
            return False
        return bool(previous_user.target_words and not previous_user.suggested_words_used)

    # ------------------------------------------------------------------
    # Automatic post-turn updates
    # ------------------------------------------------------------------
    def apply_post_turn_updates(
        self,
        *,
        session: LearningSession,
        user: User,
        assistant_message: ConversationMessage | None,
        learner_reply: str,
        pending_moment: SessionLearningMoment | None,
        word_feedback: Sequence["WordFeedback"],
        error_result: ErrorDetectionResult,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}

        if pending_moment and pending_moment.kind == "vocab_boost":
            resolved = self._resolve_vocab_boost_from_feedback(
                moment=pending_moment,
                word_feedback=word_feedback,
            )
            if resolved:
                payload["moment_result"] = self.serialize_result(resolved)

        if assistant_message and due_grammar:
            concept, _ = due_grammar[0]
            evaluation = self.grammar_evaluator.evaluate(
                concept=concept,
                assistant_prompt=assistant_message.content,
                learner_reply=learner_reply,
                error_result=error_result,
            )
            if evaluation.used_target_concept:
                self.grammar_service.record_context_review(
                    user=user,
                    concept_id=concept.id,
                    score=evaluation.score_0_10,
                    notes=evaluation.feedback_summary,
                )
                moment = SessionLearningMoment(
                    session_id=session.id,
                    user_id=user.id,
                    anchor_message_id=assistant_message.id,
                    kind="conversation_turn",
                    source_type="grammar",
                    source_id=str(concept.id),
                    status="completed",
                    prompt_payload={
                        "title": concept.name,
                        "body": assistant_message.content,
                        "input_mode": "free_text",
                        "choices": [],
                        "prefill_text": None,
                        "metadata": {
                            "concept_id": concept.id,
                            "concept_name": concept.name,
                        },
                    },
                    result_payload={
                        "is_correct": True,
                        "score_0_10": evaluation.score_0_10,
                        "feedback_summary": evaluation.feedback_summary,
                        "next_step_hint": None,
                    },
                    score_0_10=evaluation.score_0_10,
                    srs_credit_applied=True,
                    completed_at=datetime.now(timezone.utc),
                )
                self.db.add(moment)
                self.db.flush([moment])
                payload["grammar_feedback"] = evaluation.feedback_summary
                logger.info(
                    "session_context_review_applied",
                    session_id=str(session.id),
                    concept_id=concept.id,
                )

        deck_words = [item for item in word_feedback if item.word.deck_name == self.primary_vocab_deck_name]
        if deck_words:
            payload["deck_words_used"] = len([item for item in deck_words if item.was_used])
            if payload["deck_words_used"]:
                logger.info(
                    "session_vocab_review_applied",
                    session_id=str(session.id),
                    used=payload["deck_words_used"],
                )

        return payload

    def _resolve_vocab_boost_from_feedback(
        self,
        *,
        moment: SessionLearningMoment,
        word_feedback: Sequence["WordFeedback"],
    ) -> MomentEvaluation | None:
        word_id = (moment.prompt_payload or {}).get("metadata", {}).get("word_id")
        if not isinstance(word_id, int):
            return None
        feedback = next((item for item in word_feedback if item.word.id == word_id), None)
        if not feedback:
            return None

        if feedback.was_used:
            return self._complete_moment(
                moment=moment,
                is_correct=True,
                score_0_10=9.0,
                feedback_summary=f"Nice use of {feedback.word.word}.",
                next_step_hint=None,
                srs_credit_applied=True,
            )

        return self._skip_existing_moment(
            moment=moment,
            feedback_summary=f"Skipped {moment.prompt_payload.get('title', 'this prompt')}.",
        )

    # ------------------------------------------------------------------
    # Explicit moment resolution
    # ------------------------------------------------------------------
    def submit_moment(
        self,
        *,
        session: LearningSession,
        user: User,
        moment: SessionLearningMoment,
        answer_text: str | None = None,
        selected_choice: str | None = None,
        skipped: bool = False,
    ) -> MomentEvaluation:
        if moment.status != "pending":
            raise ValueError("Learning moment has already been resolved")

        if skipped:
            return self._skip_existing_moment(
                moment=moment,
                feedback_summary=f"Skipped {moment.prompt_payload.get('title', 'this prompt')}.",
            )

        answer = answer_text or selected_choice or ""
        metadata = (moment.prompt_payload or {}).get("metadata", {})
        kind = moment.kind

        if kind == "vocab_check":
            return self._submit_vocab_check(moment=moment, user=user, answer=answer, metadata=metadata)
        if kind in {"grammar_challenge", "grammar_repair"}:
            return self._submit_grammar_moment(moment=moment, user=user, answer=answer, metadata=metadata)
        if kind == "error_repair":
            return self._submit_error_repair(moment=moment, user=user, answer=answer, metadata=metadata)
        if kind == "vocab_boost":
            raise ValueError("Vocab boost moments are resolved by the next normal reply")

        raise ValueError(f"Unsupported learning moment kind: {kind}")

    def _submit_vocab_check(
        self,
        *,
        moment: SessionLearningMoment,
        user: User,
        answer: str,
        metadata: dict[str, Any],
    ) -> MomentEvaluation:
        accepted_answers = [
            item
            for item in metadata.get("accepted_answers", [])
            if isinstance(item, str) and item
        ]
        normalized = _normalize_answer(answer)
        is_correct = normalized in {_normalize_answer(item) for item in accepted_answers}
        score = 9.5 if is_correct else 3.0

        word_id = metadata.get("word_id")
        if isinstance(word_id, int):
            vocab_word = self.db.get(VocabularyWord, word_id)
            if vocab_word:
                rating = 3 if is_correct else 1
                self.progress_service.record_review(user=user, word=vocab_word, rating=rating)

        return self._complete_moment(
            moment=moment,
            is_correct=is_correct,
            score_0_10=score,
            feedback_summary=(
                f"Correct: {metadata.get('word', 'word')}."
                if is_correct
                else f"Try to remember: {metadata.get('correct_answer') or metadata.get('translation') or 'the target meaning'}."
            ),
            next_step_hint=_solution_hint(
                str(
                    metadata.get("solution_brief")
                    or metadata.get("correct_answer")
                    or metadata.get("translation")
                    or ""
                )
            ),
            srs_credit_applied=True,
        )

    def _submit_grammar_moment(
        self,
        *,
        moment: SessionLearningMoment,
        user: User,
        answer: str,
        metadata: dict[str, Any],
    ) -> MomentEvaluation:
        check_result = self._check_free_text_answer(
            exercise_type=str(metadata.get("exercise_type") or "short_answer"),
            prompt=str(metadata.get("prompt") or ""),
            correct_answer=str(metadata.get("correct_answer") or ""),
            answer=answer,
            concept_id=metadata.get("concept_id") if isinstance(metadata.get("concept_id"), int) else None,
            user_id=user.id,
        )

        is_correct = bool(check_result.get("is_correct"))
        raw_score = float(check_result.get("score", 0) or 0)
        score = 9.5 if is_correct else (6.0 if raw_score >= 6.0 else 3.0)

        concept_id = metadata.get("concept_id")
        if isinstance(concept_id, int):
            self.grammar_service.record_context_review(
                user=user,
                concept_id=concept_id,
                score=score,
                notes=str(check_result.get("feedback") or check_result.get("explanation") or ""),
                source="moment",
            )

        return self._complete_moment(
            moment=moment,
            is_correct=is_correct,
            score_0_10=score,
            feedback_summary=str(
                check_result.get("feedback")
                or check_result.get("explanation")
                or "Moment reviewed."
            ),
            next_step_hint=_solution_hint(
                str(
                    check_result.get("sample_solution")
                    or metadata.get("solution_brief")
                    or metadata.get("correct_answer")
                    or ""
                ),
                str(check_result.get("explanation") or "") or None,
            ),
            srs_credit_applied=True,
        )

    def _submit_error_repair(
        self,
        *,
        moment: SessionLearningMoment,
        user: User,
        answer: str,
        metadata: dict[str, Any],
    ) -> MomentEvaluation:
        check_result = self._check_free_text_answer(
            exercise_type=str(metadata.get("exercise_type") or "correction"),
            prompt=str(metadata.get("prompt") or ""),
            correct_answer=str(metadata.get("correct_answer") or ""),
            answer=answer,
            concept_id=None,
            user_id=user.id,
        )
        is_correct = bool(check_result.get("is_correct"))
        srs_service = UnifiedSRSService(self.db)
        error_id = metadata.get("error_id")
        if isinstance(error_id, str):
            rating = 4 if is_correct else 1
            srs_service.complete_item(
                user_id=user.id,
                item_type=ItemType.ERROR,
                item_id=error_id,
                rating=rating,
            )

        return self._complete_moment(
            moment=moment,
            is_correct=is_correct,
            score_0_10=9.5 if is_correct else 3.0,
            feedback_summary=str(
                check_result.get("feedback")
                or check_result.get("explanation")
                or "Moment reviewed."
            ),
            next_step_hint=_solution_hint(
                str(
                    check_result.get("sample_solution")
                    or metadata.get("solution_brief")
                    or metadata.get("correct_answer")
                    or ""
                ),
                str(check_result.get("explanation") or "") or None,
            ),
            srs_credit_applied=True,
        )

    def _check_free_text_answer(
        self,
        *,
        exercise_type: str,
        prompt: str,
        correct_answer: str,
        answer: str,
        concept_id: int | None,
        user_id: UUID,
    ) -> dict[str, Any]:
        if self.brief_exercise_service is not None:
            try:
                result = _run_async(
                    self.brief_exercise_service.check_answer(
                        exercise_type=exercise_type,
                        prompt=prompt,
                        correct_answer=correct_answer,
                        user_answer=answer,
                        user_id=user_id,
                        concept_id=concept_id,
                    )
                )
                if isinstance(result, dict):
                    return result
            except Exception as exc:
                logger.warning("Moment answer check failed", error=str(exc))

        normalized_answer = _normalize_answer(answer)
        accepted = set(_split_expected_answers(correct_answer))
        is_correct = normalized_answer in accepted if accepted else bool(normalized_answer)
        return {
            "is_correct": is_correct,
            "feedback": "Correct." if is_correct else f"Expected: {correct_answer}",
            "explanation": "",
            "score": 10 if is_correct else 3,
        }

    def _complete_moment(
        self,
        *,
        moment: SessionLearningMoment,
        is_correct: bool | None,
        score_0_10: float | None,
        feedback_summary: str,
        next_step_hint: str | None,
        srs_credit_applied: bool,
    ) -> MomentEvaluation:
        moment.status = "completed"
        moment.score_0_10 = score_0_10
        moment.srs_credit_applied = srs_credit_applied
        moment.result_payload = {
            "is_correct": is_correct,
            "score_0_10": score_0_10,
            "feedback_summary": feedback_summary,
            "next_step_hint": next_step_hint,
        }
        moment.completed_at = datetime.now(timezone.utc)
        self.sync_anchor_message_snapshot(moment)
        logger.info(
            "session_moment_completed",
            session_id=str(moment.session_id),
            moment_id=str(moment.id),
            kind=moment.kind,
        )
        return MomentEvaluation(
            moment=moment,
            is_correct=is_correct,
            score_0_10=score_0_10,
            feedback_summary=feedback_summary,
            next_step_hint=next_step_hint,
        )

    def _skip_existing_moment(
        self,
        *,
        moment: SessionLearningMoment,
        feedback_summary: str,
    ) -> MomentEvaluation:
        moment.status = "skipped"
        moment.result_payload = {
            "is_correct": None,
            "score_0_10": None,
            "feedback_summary": feedback_summary,
            "next_step_hint": None,
        }
        moment.completed_at = datetime.now(timezone.utc)
        self.sync_anchor_message_snapshot(moment)
        logger.info(
            "session_moment_skipped",
            session_id=str(moment.session_id),
            moment_id=str(moment.id),
            kind=moment.kind,
        )
        return MomentEvaluation(
            moment=moment,
            is_correct=None,
            score_0_10=None,
            feedback_summary=feedback_summary,
            next_step_hint=None,
        )

    # ------------------------------------------------------------------
    # Message snapshot sync
    # ------------------------------------------------------------------
    def sync_anchor_message_snapshot(self, moment: SessionLearningMoment) -> None:
        if not moment.anchor_message_id:
            return
        message = self.db.get(ConversationMessage, moment.anchor_message_id)
        if not message:
            return
        payload = dict(message.errors_detected or {})
        if moment.status == "pending":
            payload["pending_moment"] = self.serialize_moment(moment)
        else:
            payload.pop("pending_moment", None)
        message.errors_detected = payload


__all__ = [
    "GrammarContextEvaluation",
    "GrammarContextEvaluator",
    "MomentEvaluation",
    "PlannedMoment",
    "PRIMARY_VOCAB_DECK_NAME",
    "SessionMomentPlanner",
]
