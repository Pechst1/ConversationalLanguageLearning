"""Conversation turn generation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from loguru import logger

from app.core.conversation.prompts import build_few_shot_examples, build_system_prompt
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.llm_service import LLMResult
from app.services.progress import ProgressService, QueueItem

ConversationRole = Literal["user", "assistant"]


@dataclass(slots=True)
class ConversationHistoryMessage:
    """Minimal representation of a conversation message."""

    role: ConversationRole
    content: str


@dataclass(slots=True)
class TargetWord:
    """Metadata about a vocabulary word targeted during generation."""

    id: int
    surface: str
    translation: str | None
    is_new: bool


@dataclass(slots=True)
class ConversationPlan:
    """Breakdown of review and new vocabulary to weave into the response."""

    queue_items: Sequence[QueueItem]
    review_targets: list[TargetWord]
    new_targets: list[TargetWord]

    @property
    def target_words(self) -> list[TargetWord]:
        """Return ordered collection of all target words."""

        return [*self.review_targets, *self.new_targets]


@dataclass(slots=True)
class GeneratedTurn:
    """Structured payload returned after generating an assistant response."""

    text: str
    plan: ConversationPlan
    llm_result: LLMResult


class ConversationGenerator:
    """High-level orchestration for generating LLM-backed conversation turns."""

    def __init__(
        self,
        *,
        progress_service: ProgressService,
        llm_service,
        target_limit: int = 8,
        review_ratio: float = 0.6,
        max_history_messages: int = 6,
        default_temperature: float = 0.65,
        max_tokens: int = 450,
    ) -> None:
        self.progress_service = progress_service
        self.llm_service = llm_service
        self.target_limit = max(0, target_limit)
        self.review_ratio = max(0.0, min(review_ratio, 1.0))
        self.max_history_messages = max_history_messages
        self.default_temperature = default_temperature
        self.max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Vocabulary planning helpers
    # ------------------------------------------------------------------
    def _select_queue_items(self, *, user: User) -> list[QueueItem]:
        """Return queue entries prioritizing reviews before new vocabulary."""

        if self.target_limit == 0:
            return []

        queue = list(self.progress_service.get_learning_queue(user=user, limit=self.target_limit))
        if not queue:
            return []

        due_items = [item for item in queue if not item.is_new]
        new_items = [item for item in queue if item.is_new]

        desired_reviews = int(round(self.target_limit * self.review_ratio))
        desired_reviews = max(0, min(desired_reviews, len(due_items)))

        selected: list[QueueItem] = due_items[:desired_reviews]

        remaining = self.target_limit - len(selected)
        if remaining > 0 and new_items:
            selected.extend(new_items[:remaining])

        remaining = self.target_limit - len(selected)
        if remaining > 0:
            for item in due_items[desired_reviews:]:
                selected.append(item)
                if len(selected) >= self.target_limit:
                    break

        if len(selected) < self.target_limit:
            for item in new_items:
                selected.append(item)
                if len(selected) >= self.target_limit:
                    break

        seen: set[int] = set()
        ordered: list[QueueItem] = []
        for item in selected:
            word_id = item.word.id
            if word_id in seen:
                continue
            ordered.append(item)
            seen.add(word_id)
            if len(ordered) >= self.target_limit:
                break

        logger.debug(
            "Selected queue items",
            total=len(ordered),
            review_count=sum(1 for item in ordered if not item.is_new),
            new_count=sum(1 for item in ordered if item.is_new),
        )
        return ordered

    def _build_plan(self, queue_items: Sequence[QueueItem]) -> ConversationPlan:
        """Transform queue items into a conversation plan."""

        review_targets: list[TargetWord] = []
        new_targets: list[TargetWord] = []
        for item in queue_items:
            word = item.word
            metadata = TargetWord(
                id=word.id,
                surface=word.word,
                translation=word.english_translation,
                is_new=item.is_new,
            )
            if item.is_new:
                new_targets.append(metadata)
            else:
                review_targets.append(metadata)

        plan = ConversationPlan(
            queue_items=tuple(queue_items),
            review_targets=review_targets,
            new_targets=new_targets,
        )
        logger.debug(
            "Built conversation plan",
            total=len(plan.target_words),
            review=len(plan.review_targets),
            new=len(plan.new_targets),
        )
        return plan

    # ------------------------------------------------------------------
    # Prompt preparation helpers
    # ------------------------------------------------------------------
    def _build_target_context(self, *, plan: ConversationPlan, learner_level: str, user: User) -> str:
        """Return a context block describing vocabulary and learner profile."""

        lines: list[str] = [
            f"Learner proficiency level: {learner_level}",
            f"Learner native language: {user.native_language or 'unknown'}",
            "Target vocabulary for this turn:",
        ]

        if plan.target_words:
            if plan.review_targets:
                lines.append("Review targets:")
                lines.extend(
                    f"- {target.surface} — {target.translation or 'no translation available'}"
                    for target in plan.review_targets
                )
            if plan.new_targets:
                lines.append("New targets:")
                lines.extend(
                    f"- {target.surface} — {target.translation or 'no translation available'}"
                    for target in plan.new_targets
                )
        else:
            lines.append("- No explicit targets; continue natural conversation.")

        context = "\n".join(lines)
        logger.debug("Built target context", target_count=len(plan.target_words))
        return context

    def _prepare_history(self, history: Sequence[ConversationHistoryMessage]) -> list[dict[str, str]]:
        """Trim and format chat history for the LLM payload."""

        if not history:
            return []

        trimmed = history[-self.max_history_messages :]
        formatted = [{"role": message.role, "content": message.content} for message in trimmed]
        logger.debug("Prepared history", provided=len(history), used=len(formatted))
        return formatted

    def _build_messages(
        self,
        *,
        plan: ConversationPlan,
        history: Sequence[ConversationHistoryMessage] = (),
        learner_level: str,
        user: User,
    ) -> list[dict[str, str]]:
        """Assemble the chat completion payload."""

        target_context = self._build_target_context(plan=plan, learner_level=learner_level, user=user)
        context_message = {"role": "system", "content": target_context}

        vocabulary_terms = [target.surface for target in plan.target_words]
        few_shot = build_few_shot_examples(vocabulary_terms, learner_level)
        history_messages = self._prepare_history(history)

        messages = [context_message, *few_shot, *history_messages]
        logger.debug("Built message payload", message_count=len(messages))
        return messages

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_turn(
        self,
        *,
        user: User,
        learner_level: str,
        style: str,
        history: Sequence[ConversationHistoryMessage] | None = None,
        temperature: float | None = None,
    ) -> GeneratedTurn:
        """Generate the next assistant response."""

        history = history or ()
        queue_items = self._select_queue_items(user=user)
        plan = self._build_plan(queue_items)
        messages = self._build_messages(
            plan=plan,
            history=history,
            learner_level=learner_level,
            user=user,
        )

        system_prompt = build_system_prompt(style, learner_level)
        applied_temperature = temperature if temperature is not None else self.default_temperature

        result = self.llm_service.generate_chat_completion(
            messages,
            temperature=applied_temperature,
            max_tokens=self.max_tokens,
            system_prompt=system_prompt,
        )

        generated = GeneratedTurn(text=result.content, plan=plan, llm_result=result)
        logger.info(
            "Generated conversation turn",
            style=style,
            tokens=result.total_tokens,
            target_count=len(plan.target_words),
        )
        return generated


def iter_target_vocabulary(plan: ConversationPlan) -> Iterable[VocabularyWord]:
    """Yield :class:`VocabularyWord` instances referenced in the plan."""

    for item in plan.queue_items:
        yield item.word


__all__ = [
    "ConversationGenerator",
    "ConversationHistoryMessage",
    "ConversationPlan",
    "GeneratedTurn",
    "TargetWord",
    "iter_target_vocabulary",
]
