"""Conversation turn generation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence, TYPE_CHECKING

from loguru import logger

from app.core.conversation.prompts import build_few_shot_examples, build_system_prompt
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.db.models.error import UserError
from app.services.llm_service import LLMResult
from app.services.progress import ProgressService, QueueItem
from app.services.auto_context_service import SessionContext  # [NEW]

if TYPE_CHECKING:
    from app.db.models.grammar import GrammarConcept, UserGrammarProgress

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
    # Fallback helpers
    # ------------------------------------------------------------------
    def _truncate_text(self, value: str, *, limit: int = 160) -> str:
        """Compact user text for insertion into template replies."""

        compact = " ".join(value.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[: limit - 3]}..."

    def _last_user_message(self, history: Sequence[ConversationHistoryMessage]) -> str:
        for message in reversed(history):
            if message.role == "user" and message.content:
                return message.content
        return ""

    def _build_template_reply(
        self,
        *,
        plan: ConversationPlan,
        history: Sequence[ConversationHistoryMessage],
        style: str,
        user: User,
        topic: str | None,
        error: Exception,
    ) -> LLMResult:
        tone_map = {
            "casual": "Salut ! Merci pour ton message.",
            "tutor": "Merci pour ton message, continuons ensemble.",
            "exam-prep": "C'est une bonne preparation, restons concentres.",
            "business": "Merci pour cette information, travaillons sur ton francais professionnel.",
            "storytelling": "Continuons notre histoire ensemble.",
            "dialogue": "Content de discuter avec toi !",
            "debate": "Merci pour ton point de vue, debattons-en.",
            "tutorial": "Voici une petite explication pour avancer.",
        }
        opener = tone_map.get(style.lower(), "Merci pour ton message !")

        last_user_text = self._last_user_message(history)
        lines: list[str] = [opener]
        if topic:
            lines.append(f"Le sujet de la fois: {topic}.")
        if last_user_text:
            lines.append(f"Tu as mentionne: \"{self._truncate_text(last_user_text)}\".")

        targets = plan.target_words
        if targets:
            formatted_targets: list[str] = []
            example_sentences: list[str] = []
            for target in targets:
                translation = f" ({target.translation})" if target.translation else ""
                descriptor = "nouveau" if target.is_new else "en revision"
                formatted_targets.append(f"{target.surface}{translation} [{descriptor}]")
            lines.append("Concentrons-nous sur les mots suivants: " + ", ".join(formatted_targets) + ".")

            for target in targets[:2]:
                translation = f" ({target.translation})" if target.translation else ""
                example_sentences.append(
                    f"Essaie une phrase avec \"{target.surface}\"{translation} liee a ta situation."
                )
            if example_sentences:
                lines.append("Par exemple: " + " ".join(example_sentences))
            lines.append("Peux-tu repondre en utilisant au moins l'un de ces mots ?")
        else:
            lines.append("Continuons a discuter pour pratiquer ton francais." )
            lines.append("Ajoute un ou deux details de plus dans ta prochaine reponse.")

        lines.append("A toi !")
        reply_text = " ".join(lines)

        logger.warning(
            "LLM generation unavailable, using template reply",
            provider_error=type(error).__name__,
        )

        return LLMResult(
            provider="template",
            model="rule-based",
            content=reply_text,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0.0,
            raw_response={
                "fallback": True,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )

    # ------------------------------------------------------------------
    # Vocabulary planning helpers
    # ------------------------------------------------------------------
    def _select_queue_items(
        self,
        *,
        user: User,
        dynamic_limit: int | None = None,
        dynamic_review_ratio: float | None = None,
        new_word_budget: int | None = None,
        exclude_ids: set[int] | None = None,
        direction: str | None = None,
    ) -> list[QueueItem]:
        """Return queue entries prioritizing reviews before new vocabulary."""

        effective_limit = dynamic_limit if dynamic_limit is not None else self.target_limit
        effective_ratio = (
            max(0.0, min(dynamic_review_ratio, 1.0))
            if dynamic_review_ratio is not None
            else self.review_ratio
        )

        if effective_limit == 0:
            return []

        queue = list(
            self.progress_service.get_learning_queue(
                user=user,
                limit=effective_limit,
                new_word_budget=new_word_budget,
                exclude_ids=exclude_ids,
                direction=direction,
            )
        )
        if not queue:
            exclude_set = exclude_ids or set()
            fallback_words = self.progress_service.sample_vocabulary(
                user=user,
                limit=effective_limit,
                exclude_ids=exclude_set,
                direction=direction,
            )
            # If exclusions resulted in no fallback items, retry once without exclusions
            if not fallback_words and exclude_set:
                logger.debug("Retrying sample_vocabulary without exclusions.")
                fallback_words = self.progress_service.sample_vocabulary(
                    user=user,
                    limit=effective_limit,
                    exclude_ids=set(),
                    direction=direction,
                )
            return [QueueItem(word=word, progress=None, is_new=True) for word in fallback_words]

        due_items = [item for item in queue if not item.is_new]
        new_items = [item for item in queue if item.is_new]

        desired_reviews = int(round(effective_limit * effective_ratio))
        desired_reviews = max(0, min(desired_reviews, len(due_items)))

        selected: list[QueueItem] = due_items[:desired_reviews]

        remaining = effective_limit - len(selected)
        if remaining > 0 and new_items:
            selected.extend(new_items[:remaining])

        remaining = effective_limit - len(selected)
        if remaining > 0:
            for item in due_items[desired_reviews:]:
                selected.append(item)
                if len(selected) >= effective_limit:
                    break

        if len(selected) < effective_limit:
            for item in new_items:
                selected.append(item)
                if len(selected) >= effective_limit:
                    break

        seen: set[int] = set()
        ordered: list[QueueItem] = []
        for item in selected:
            word_id = item.word.id
            if word_id in seen:
                continue
            ordered.append(item)
            seen.add(word_id)
            if len(ordered) >= effective_limit:
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
            translation = word.english_translation
            if word.direction == "fr_to_de":
                translation = word.german_translation or translation
            elif word.direction == "de_to_fr":
                translation = word.french_translation or translation
            metadata = TargetWord(
                id=word.id,
                surface=word.word,
                translation=translation,
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
    def _build_target_context(
        self,
        *,
        plan: ConversationPlan,
        learner_level: str,
        user: User,
        topic: str | None = None,
        scenario: str | None = None,
        due_errors: Sequence[UserError] | None = None,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None = None,
        scenario_context: str | None = None,
    ) -> str:
        """Return a context block describing vocabulary and learner profile."""

        lines: list[str] = [
            f"Learner proficiency level: {learner_level}",
            f"Learner native language: {user.native_language or 'unknown'}",
        ]

        if due_errors:
            # Limit to top 3 most problematic errors for focus
            prioritized_errors = list(due_errors)[:3]
            lines.append("")
            lines.append("PRIORITY ERROR CORRECTION (These are the learner's most persistent mistakes):")
            lines.append("Construct your response to naturally require correct usage of these patterns:")
            for err in prioritized_errors:
                lapses_info = f"[{err.lapses or 0} lapses, {err.reps or 0} reviews]" if err.lapses or err.reps else ""
                lines.append(
                    f"- {err.error_category}: {err.error_pattern} {lapses_info}"
                )
                lines.append(f"  Context: '{err.context_snippet}' → Correct: '{err.correction}'")

        # Add grammar concepts due for practice
        if due_grammar:
            lines.append("")
            lines.append("GRAMMAR FOCUS (Practice these concepts naturally in conversation):")
            for concept, progress in due_grammar[:2]:  # Limit to 2 concepts
                state_info = f" [{progress.state}]" if progress else " [new]"
                lines.append(f"- {concept.name} ({concept.level}){state_info}")
                if concept.description:
                    lines.append(f"  Description: {concept.description[:100]}..." if len(concept.description or "") > 100 else f"  Description: {concept.description}")
                if concept.examples:
                    # Show first example if available
                    lines.append(f"  Example usage: {concept.examples[:80]}..." if len(concept.examples or "") > 80 else f"  Example: {concept.examples}")

        if topic:
            lines.append(f"Conversation topic: {topic}")
        if scenario:
            lines.append(f"CURRENT SCENARIO: {scenario}")
        if scenario_context:
            lines.append(scenario_context)

        lines.append("Target vocabulary for this turn:")

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
        topic: str | None = None,
        scenario: str | None = None,
        due_errors: Sequence[UserError] | None = None,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None = None,
        scenario_context: str | None = None,
    ) -> list[dict[str, str]]:
        """Assemble the chat completion payload."""

        target_context = self._build_target_context(
            plan=plan,
            learner_level=learner_level,
            user=user,
            topic=topic,
            scenario=scenario,
            due_errors=due_errors,
            due_grammar=due_grammar,
            scenario_context=scenario_context,
        )
        context_message = {"role": "system", "content": target_context}

        vocabulary_terms = [target.surface for target in plan.target_words]
        few_shot = build_few_shot_examples(vocabulary_terms, learner_level, topic)
        history_messages = self._prepare_history(history)

        messages = [context_message, *few_shot, *history_messages]
        logger.debug("Built message payload", message_count=len(messages))
        return messages

    def generate_turn_with_context(
        self,
        *,
        user: User,
        learner_level: str,
        style: str,
        session_capacity: dict,
        history: Sequence[ConversationHistoryMessage] | None = None,
        temperature: float | None = None,
        review_focus: float | None = None,
        topic: str | None = None,
        exclude_ids: set[int] | None = None,
        anki_direction: str | None = None,
        scenario: str | None = None,
        due_errors: Sequence[UserError] | None = None,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None = None,
        scenario_context: str | None = None,
        session_context: SessionContext | None = None,  # [NEW]
    ) -> GeneratedTurn:
        """Generate a turn while respecting the adaptive session context."""

        history = history or ()
        total_capacity = max(0, int(session_capacity.get("total_capacity", self.target_limit)))
        words_per_turn = max(0, int(session_capacity.get("words_per_turn", self.target_limit)))
        words_per_turn = min(words_per_turn, self.target_limit)

        adaptive_ratio = self.progress_service.calculate_adaptive_review_ratio(
            user.id, direction=anki_direction
        )
        if review_focus is not None:
            adaptive_ratio = max(0.0, min(1.0, (adaptive_ratio + review_focus) / 2))
        new_budget = self.progress_service.calculate_new_word_budget(
            user.id, total_capacity, direction=anki_direction
        )
        queue_items = self._select_queue_items(
            user=user,
            dynamic_limit=words_per_turn,
            dynamic_review_ratio=adaptive_ratio,
            new_word_budget=new_budget,
            exclude_ids=exclude_ids,
            direction=anki_direction,
        )

        logger.info(
            "Adaptive queue calculated",
            user_id=str(user.id),
            performance=adaptive_ratio,
            review_ratio=adaptive_ratio,
            new_budget=new_budget,
            capacity=total_capacity,
        )

        plan = self._build_plan(queue_items)
        messages = self._build_messages(
            plan=plan,
            history=history,
            learner_level=learner_level,
            user=user,
            topic=topic,
            scenario=scenario,
            due_errors=due_errors,
            due_grammar=due_grammar,
        )

        system_prompt = build_system_prompt(style, learner_level)

        # [NEW] Inject auto-context signals (Time of day, rich style instructions, news)
        if session_context:
            system_prompt += "\n\n" + session_context.to_system_prompt_addition()

        if scenario:
            system_prompt += f"\n\nROLEPLAY SCENARIO: {scenario}\nAct exclusively as a character in this setting. Do not break character."
        applied_temperature = temperature if temperature is not None else self.default_temperature

        # Reduce token limit for speaking_first mode to keep responses short
        effective_max_tokens = self.max_tokens
        if style == "speaking_first":
            effective_max_tokens = 200  # Much shorter for voice responses

        try:
            result = self.llm_service.generate_chat_completion(
                messages,
                temperature=applied_temperature,
                max_tokens=effective_max_tokens,
                system_prompt=system_prompt,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback for offline dev
            result = self._build_template_reply(
                plan=plan,
                history=history,
                style=style,
                user=user,
                topic=topic,
                error=exc,
            )

        generated = GeneratedTurn(text=result.content, plan=plan, llm_result=result)
        logger.info(
            "Generated conversation turn",
            style=style,
            tokens=result.total_tokens,
            target_count=len(plan.target_words),
            adaptive_ratio=adaptive_ratio,
            new_budget=new_budget,
            requested_review_focus=review_focus,
        )
        return generated

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
        topic: str | None = None,
        exclude_ids: set[int] | None = None,
    ) -> GeneratedTurn:
        """Generate the next assistant response."""

        history = history or ()
        fallback_capacity = {
            "estimated_turns": 1,
            "words_per_turn": self.target_limit,
            "total_capacity": max(self.target_limit, 0),
        }
        return self.generate_turn_with_context(
            user=user,
            learner_level=learner_level,
            style=style,
            session_capacity=fallback_capacity,
            history=history,
            temperature=temperature,
            topic=topic,
            exclude_ids=exclude_ids,
        )

    # ------------------------------------------------------------------
    # NPC Story Response Generation
    # ------------------------------------------------------------------
    def generate_npc_response(
        self,
        *,
        user: User,
        npc_service,
        npc_id: str,
        player_input: str,
        scene_description: str,
        learner_level: str,
        conversation_history: Sequence[ConversationHistoryMessage] | None = None,
        scene_objectives: list[str] | None = None,
        story_flags: dict | None = None,
    ) -> dict:
        """
        Generate an NPC response for the Story RPG feature.
        
        Returns a dict with:
            - response: The NPC's dialogue text
            - emotion: Optional emotional state (happy, sad, curious, etc.)
            - relationship_delta: Change to relationship level (-2 to +2)
            - new_mood: Optional new mood for the NPC
            - triggers_unlocked: List of story triggers that were activated
            - llm_result: Raw LLM response metadata
        """
        # Get NPC context
        context = npc_service.get_prompt_context(user, npc_id)
        if not context:
            logger.warning("NPC not found", npc_id=npc_id)
            return {
                "response": "...",
                "emotion": None,
                "relationship_delta": 0,
                "new_mood": None,
                "triggers_unlocked": [],
                "llm_result": None,
            }
        
        npc = context.npc
        history = conversation_history or ()
        
        # Build the system prompt for NPC roleplay
        system_prompt = npc_service.build_npc_system_prompt(
            context=context,
            scene_description=scene_description,
            player_level=learner_level,
        )
        
        # Add scene objectives if present
        if scene_objectives:
            objectives_str = "\n".join(f"- {obj}" for obj in scene_objectives)
            system_prompt += f"\n\nAKTUELLE SZENEN-ZIELE:\n{objectives_str}"
        
        # Add story flags for context
        if story_flags:
            relevant_flags = [f"{k}={v}" for k, v in story_flags.items() if v]
            if relevant_flags:
                system_prompt += f"\n\nSTORY-FLAGS: {', '.join(relevant_flags[:5])}"
        
        # Prepare messages for LLM
        messages = self._prepare_history(history)
        
        # Add player's input as the latest user message
        messages.append({"role": "user", "content": player_input})
        
        # Generate response using LLM
        try:
            result = self.llm_service.generate_chat_completion(
                messages,
                temperature=0.8,  # Slightly higher for more creative roleplay
                max_tokens=350,
                system_prompt=system_prompt,
            )
            response_text = result.content.strip()
        except Exception as exc:
            logger.error("NPC response generation failed", error=str(exc), npc_id=npc_id)
            # Fallback response based on NPC personality
            speech = npc.speech_pattern or {}
            example_quotes = speech.get("example_quotes", [])
            if example_quotes:
                response_text = example_quotes[0]
            else:
                response_text = "..."
            result = None
        
        # Analyze player input for relationship effects
        player_analysis = self._analyze_player_input(player_input, npc)
        relationship_delta, new_mood = npc_service.evaluate_npc_reaction(
            npc_id, player_analysis
        )
        
        # Detect any story triggers from the response
        triggers_unlocked = self._detect_story_triggers(
            player_input=player_input,
            npc_response=response_text,
            npc_id=npc_id,
            story_flags=story_flags or {},
        )
        
        # Detect emotion from response
        emotion = self._detect_emotion(response_text, context.mood)
        
        # Evaluate objectives using LLM
        objectives_completed = []
        should_transition = False
        if scene_objectives:
            eval_result = self._evaluate_objectives_with_llm(
                player_input=player_input,
                npc_response=response_text,
                objectives=scene_objectives,
                conversation_history=history,
                story_flags=story_flags or {},
            )
            objectives_completed = eval_result.get("completed", [])
            should_transition = eval_result.get("should_transition", False)
        
        logger.info(
            "Generated NPC response",
            npc=npc.name,
            player_level=learner_level,
            relationship_delta=relationship_delta,
            triggers=len(triggers_unlocked),
            objectives_completed=objectives_completed,
            should_transition=should_transition,
        )
        
        return {
            "response": response_text,
            "emotion": emotion,
            "relationship_delta": relationship_delta,
            "new_mood": new_mood,
            "triggers_unlocked": triggers_unlocked,
            "objectives_completed": objectives_completed,
            "should_transition": should_transition,
            "llm_result": result,
        }

    def _analyze_player_input(self, player_input: str, npc) -> dict:
        """Analyze player input for relationship triggers."""
        text_lower = player_input.lower()
        triggers = []
        
        # Check for question patterns
        if any(word in text_lower for word in ["?", "qui", "quoi", "pourquoi", "comment", "où"]):
            triggers.append("player_asks_questions")
        
        # Check for emotional language
        emotion_words = ["triste", "content", "heureux", "aime", "peur", "seul", "ami"]
        if any(word in text_lower for word in emotion_words):
            triggers.append("player_shows_emotion")
        
        # Check for dismissive patterns
        dismissive = ["pas important", "seulement", "juste", "egal", "peu importe"]
        if any(word in text_lower for word in dismissive):
            triggers.append("player_is_dismissive")
        
        # Check for rushing
        rushing = ["vite", "rapide", "dépêche", "presse"]
        if any(word in text_lower for word in rushing):
            triggers.append("player_rushes")
        
        # Check for imagination/creativity
        imagination = ["imagine", "rêve", "si j'étais", "comme si"]
        if any(word in text_lower for word in imagination):
            triggers.append("player_uses_imagination")
        
        # Check for honesty signals
        honesty = ["je ne sais pas", "peut-être", "je pense", "honnêtement"]
        if any(phrase in text_lower for phrase in honesty):
            triggers.append("player_is_honest")
        
        # Check for humor
        humor_signals = ["haha", "drôle", "blague", ":)", "😄"]
        if any(signal in text_lower for signal in humor_signals):
            triggers.append("humor_attempt")
        
        return {
            "triggers": triggers,
            "word_count": len(player_input.split()),
            "has_question": "?" in player_input,
        }

    def _detect_story_triggers(
        self,
        player_input: str,
        npc_response: str,
        npc_id: str,
        story_flags: dict,
    ) -> list[str]:
        """Detect which story triggers should be unlocked."""
        triggers = []
        text = (player_input + " " + npc_response).lower()
        
        # Petit Prince specific triggers
        if npc_id == "petit_prince":
            # Box solution trigger
            if any(word in text for word in ["boîte", "caisse", "box", "dedans"]):
                if not story_flags.get("found_box_solution"):
                    triggers.append("found_box_solution")
            
            # Rose mentioned
            if "rose" in text and not story_flags.get("rose_mentioned"):
                triggers.append("rose_mentioned")
            
            # Philosophy about what's important
            if any(word in text for word in ["important", "essentiel", "cœur"]):
                triggers.append("philosophical_discussion")
            
            # Stars that laugh ending
            if any(word in text for word in ["étoiles", "rire", "rient"]):
                if story_flags.get("philosophical_discussion"):
                    triggers.append("stars_that_laugh_foreshadowed")
        
        return triggers

    def _detect_emotion(self, response_text: str, current_mood: str) -> str | None:
        """Detect emotion from NPC response text."""
        text_lower = response_text.lower()
        
        # Happiness indicators
        if any(word in text_lower for word in ["merci", "content", "heureux", "sourire"]):
            return "happy"
        
        # Sadness indicators
        if any(word in text_lower for word in ["triste", "seul", "manque", "parti"]):
            return "sad"
        
        # Curiosity indicators
        if any(word in text_lower for word in ["?", "pourquoi", "raconte", "dis-moi"]):
            return "curious"
        
        # Tender/vulnerable indicators
        if any(word in text_lower for word in ["rose", "aime", "apprivoisé"]):
            return "tender"
        
        return current_mood or "neutral"

    def _evaluate_objectives_with_llm(
        self,
        player_input: str,
        npc_response: str,
        objectives: list[str],
        conversation_history: Sequence[ConversationHistoryMessage],
        story_flags: dict,
    ) -> dict:
        """
        Use LLM to evaluate whether scene objectives have been achieved.
        
        Returns:
            dict with:
                - completed: list of objective descriptions that are now complete
                - should_transition: bool indicating if scene should advance
                - reasoning: explanation of evaluation
        """
        if not objectives:
            return {"completed": [], "should_transition": False, "reasoning": "No objectives"}
        
        # Build conversation summary
        history_summary = ""
        if conversation_history:
            recent = list(conversation_history)[-6:]  # Last 6 messages
            history_summary = "\n".join(
                f"{'Spieler' if m.role == 'user' else 'NPC'}: {m.content[:100]}"
                for m in recent
            )
        
        # Build evaluation prompt
        objectives_list = "\n".join(f"- {obj}" for obj in objectives)
        
        prompt = f"""Du evaluierst eine interaktive Geschichte für Sprachlerner.
        
SZENEN-ZIELE (diese müssen EXAKT so in completed_objectives kopiert werden):
{objectives_list}

BISHERIGE KONVERSATION (Anzahl Nachrichten: {len(list(conversation_history)) if conversation_history else 0}):
{history_summary}

AKTUELLE SPIELER-EINGABE:
{player_input}

NPC-ANTWORT:
{npc_response}

AUFGABE:
Evaluiere welche Szenen-Ziele durch die bisherige Konversation erfüllt wurden.

REGELN FÜR DIE BEWERTUNG:

1. "Sprich mit X" gilt als ERFÜLLT wenn:
   - Mindestens 2-3 sinnvolle Nachrichten ausgetauscht wurden
   - Es gab echten Dialog (Fragen, Antworten, Gedankenaustausch)

2. "Verstehe..." oder "Erfahre..." Ziele erfordern:
   - Der NPC hat relevante Informationen geteilt
   - Das Thema wurde besprochen

3. Sei tolerant - es ist eine Sprachlern-App, nicht ein strenges Spiel.

4. WICHTIG: Kopiere die Ziel-Beschreibungen EXAKT wie oben angegeben!

should_advance_scene:
- true wenn ALLE nicht-optionalen Ziele erfüllt sind
- false wenn noch Ziele offen sind

Antworte im JSON-Format:
{{
    "completed_objectives": ["Exakter Zieltext 1", "Exakter Zieltext 2"],
    "should_advance_scene": true/false,
    "reasoning": "Kurze Begründung"
}}

Antworte NUR mit dem JSON-Objekt."""

        try:
            result = self.llm_service.generate_chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.2,  # Low temperature for consistent evaluation
                max_tokens=200,
                system_prompt="Du bist ein Story-Evaluator. Antworte nur mit valiem JSON.",
                response_format={"type": "json_object"},
            )
            
            import json
            try:
                evaluation = json.loads(result.content)
                completed = evaluation.get("completed_objectives", [])
                should_transition = evaluation.get("should_advance_scene", False)
                reasoning = evaluation.get("reasoning", "")
                
                logger.debug(
                    "Objective evaluation",
                    completed=completed,
                    should_transition=should_transition,
                    reasoning=reasoning,
                )
                
                return {
                    "completed": completed,
                    "should_transition": should_transition,
                    "reasoning": reasoning,
                }
            except json.JSONDecodeError:
                logger.warning("Failed to parse objective evaluation JSON", content=result.content[:100])
                return {"completed": [], "should_transition": False, "reasoning": "Parse error"}
                
        except Exception as exc:
            logger.error("Objective evaluation failed", error=str(exc))
            return {"completed": [], "should_transition": False, "reasoning": str(exc)}


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
