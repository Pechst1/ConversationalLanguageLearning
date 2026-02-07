"""Story service for managing interactive stories and user progress."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models.story import Story, Chapter, Scene, StoryProgress
from app.db.models.npc import NPC, NPCRelationship
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord

if TYPE_CHECKING:
    from app.services.progress import ProgressService


@dataclass
class StoryListItem:
    """Summary of a story for list display."""
    id: str
    title: str
    subtitle: str | None
    source_book: str | None
    source_author: str | None
    target_levels: list[str]
    themes: list[str]
    estimated_duration_minutes: int
    cover_image_url: str | None
    is_unlocked: bool
    progress: StoryProgressSummary | None = None


@dataclass
class StoryProgressSummary:
    """Summary of user progress in a story."""
    current_chapter_title: str | None
    completion_percentage: int
    status: str
    last_played_at: datetime | None


@dataclass
class SceneContext:
    """Full context for rendering and interacting with a scene."""
    scene: Scene
    chapter: Chapter
    story: Story
    narration: str  # Level-appropriate narration
    objectives: list[dict]
    npcs: list[NPCContext]
    player_choices: list[dict]
    story_flags: dict


@dataclass
class NPCContext:
    """NPC data with relationship context for a scene."""
    npc: NPC
    relationship_level: int
    trust: int
    mood: str
    memories: list[str] = field(default_factory=list)


@dataclass
class StoryStartResult:
    """Result of starting a new story."""
    progress: StoryProgress
    scene: SceneContext


@dataclass
class Consequence:
    """A consequence to apply after processing player input."""
    type: str  # "relationship_change", "set_flag", "add_memory", "unlock_info"
    target: str
    value: any


class StoryService:
    """Service for managing stories and user progress."""

    def __init__(self, db: Session):
        self.db = db

    def list_available_stories(self, user: User) -> list[StoryListItem]:
        """List stories available for the user's level."""
        
        # Get all active stories
        stmt = select(Story).where(Story.is_active == True).order_by(Story.title)
        stories = self.db.execute(stmt).scalars().all()
        
        # Get user's progress for all stories
        progress_stmt = select(StoryProgress).where(StoryProgress.user_id == user.id)
        progress_records = {p.story_id: p for p in self.db.execute(progress_stmt).scalars().all()}
        
        result = []
        for story in stories:
            # Check if user level allows access
            user_level = user.proficiency_level or "beginner"
            is_unlocked = self._check_level_unlock(story.target_levels, user_level)
            
            # Get progress summary if exists
            progress_summary = None
            if story.id in progress_records:
                progress = progress_records[story.id]
                chapter_title = None
                if progress.current_chapter_id:
                    chapter = self.db.get(Chapter, progress.current_chapter_id)
                    chapter_title = chapter.title if chapter else None
                
                progress_summary = StoryProgressSummary(
                    current_chapter_title=chapter_title,
                    completion_percentage=progress.completion_percentage or 0,
                    status=progress.status,
                    last_played_at=progress.last_played_at,
                )
            
            result.append(StoryListItem(
                id=story.id,
                title=story.title,
                subtitle=story.subtitle,
                source_book=story.source_book,
                source_author=story.source_author,
                target_levels=story.target_levels or [],
                themes=story.themes or [],
                estimated_duration_minutes=story.estimated_duration_minutes or 60,
                cover_image_url=story.cover_image_url,
                is_unlocked=is_unlocked,
                progress=progress_summary,
            ))
        
        return result

    def _check_level_unlock(self, target_levels: list[str] | None, user_level: str) -> bool:
        """Check if user's level allows access to the story.
        
        NOTE: Currently disabled - all stories are unlocked.
        Enable level-based locking in the future if needed.
        """
        return True  # All stories unlocked for now

    def get_story_progress(self, user: User, story_id: str) -> StoryProgress | None:
        """Get user's progress in a specific story."""
        stmt = select(StoryProgress).where(
            StoryProgress.user_id == user.id,
            StoryProgress.story_id == story_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def start_story(self, user: User, story_id: str) -> StoryStartResult:
        """Start a new story playthrough or resume existing."""
        
        # Check if story exists
        story = self.db.get(Story, story_id)
        if not story:
            raise ValueError(f"Story not found: {story_id}")
        
        # Check for existing progress
        existing = self.get_story_progress(user, story_id)
        if existing and existing.status == "in_progress":
            # Resume existing progress
            scene = self.get_current_scene(user, story_id)
            return StoryStartResult(progress=existing, scene=scene)
        
        # Get first chapter and scene
        first_chapter = self.db.execute(
            select(Chapter)
            .where(Chapter.story_id == story_id)
            .order_by(Chapter.order_index)
            .limit(1)
        ).scalar_one_or_none()
        
        if not first_chapter:
            raise ValueError(f"Story has no chapters: {story_id}")
        
        first_scene = self.db.execute(
            select(Scene)
            .where(Scene.chapter_id == first_chapter.id)
            .order_by(Scene.order_index)
            .limit(1)
        ).scalar_one_or_none()
        
        if not first_scene:
            raise ValueError(f"Chapter has no scenes: {first_chapter.id}")
        
        # Create new progress
        progress = StoryProgress(
            user_id=user.id,
            story_id=story_id,
            current_chapter_id=first_chapter.id,
            current_scene_id=first_scene.id,
            story_flags={},
            player_choices=[],
            philosophical_learnings=[],
            book_quotes_unlocked=[],
            chapters_completed=[],
            completion_percentage=0,
            status="in_progress",
        )
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        
        # Build scene context
        scene_context = self._build_scene_context(user, story, first_chapter, first_scene, progress)
        
        return StoryStartResult(progress=progress, scene=scene_context)

    def get_current_scene(self, user: User, story_id: str) -> SceneContext | None:
        """Get the current scene context for a user's story progress."""
        
        progress = self.get_story_progress(user, story_id)
        if not progress or not progress.current_scene_id:
            return None
        
        story = self.db.get(Story, story_id)
        chapter = self.db.get(Chapter, progress.current_chapter_id)
        scene = self.db.get(Scene, progress.current_scene_id)
        
        if not all([story, chapter, scene]):
            return None
        
        return self._build_scene_context(user, story, chapter, scene, progress)

    def _build_scene_context(
        self,
        user: User,
        story: Story,
        chapter: Chapter,
        scene: Scene,
        progress: StoryProgress,
    ) -> SceneContext:
        """Build full scene context including NPCs and level-appropriate narration."""
        
        # Get level-appropriate narration
        user_level = user.proficiency_level or "A1"
        narration = self._get_narration_for_level(scene.narration_variants, user_level)
        
        # Get NPC contexts
        npc_contexts = []
        npc_ids = scene.npcs_present or []
        for npc_id in npc_ids:
            npc = self.db.get(NPC, npc_id)
            if npc:
                relationship = self._get_or_create_relationship(user, npc_id)
                npc_contexts.append(NPCContext(
                    npc=npc,
                    relationship_level=relationship.level,
                    trust=relationship.trust,
                    mood=relationship.mood,
                ))
        
        return SceneContext(
            scene=scene,
            chapter=chapter,
            story=story,
            narration=narration,
            objectives=scene.objectives or [],
            npcs=npc_contexts,
            player_choices=progress.player_choices or [],
            story_flags=progress.story_flags or {},
        )

    def _get_narration_for_level(self, variants: dict | None, user_level: str) -> str:
        """Select the best narration variant for user's level."""
        if not variants:
            return ""
        
        # Try exact match first
        if user_level in variants:
            return variants[user_level]
        
        # Fall back to simplified levels
        level_fallbacks = {
            "beginner": ["A1"],
            "A1": ["A1"],
            "A2": ["A2", "A1"],
            "B1": ["B1", "A2", "A1"],
            "B2": ["B2", "B1", "A2"],
            "C1": ["C1", "B2", "B1"],
            "C2": ["C1", "B2"],
            "advanced": ["C1", "B2"],
        }
        
        for fallback in level_fallbacks.get(user_level, ["A1"]):
            if fallback in variants:
                return variants[fallback]
        
        # Return first available
        return next(iter(variants.values()), "")

    def _get_or_create_relationship(self, user: User, npc_id: str) -> NPCRelationship:
        """Get or create a relationship between user and NPC."""
        stmt = select(NPCRelationship).where(
            NPCRelationship.user_id == user.id,
            NPCRelationship.npc_id == npc_id,
        )
        relationship = self.db.execute(stmt).scalar_one_or_none()
        
        if not relationship:
            # Get NPC's default relationship config
            npc = self.db.get(NPC, npc_id)
            initial_level = 1
            if npc and npc.relationship_config:
                initial_level = npc.relationship_config.get("initial_level", 1)
            
            relationship = NPCRelationship(
                user_id=user.id,
                npc_id=npc_id,
                level=initial_level,
                trust=0,
                mood="neutral",
            )
            self.db.add(relationship)
            self.db.commit()
            self.db.refresh(relationship)
        
        return relationship

    def advance_scene(
        self,
        user: User,
        story_id: str,
        trigger: str,
    ) -> SceneContext | None:
        """Advance to the next scene based on trigger."""
        
        progress = self.get_story_progress(user, story_id)
        if not progress:
            return None
        
        current_scene = self.db.get(Scene, progress.current_scene_id)
        if not current_scene:
            return None
        
        # Find matching transition rule
        next_scene_id = None
        transition_narration = None
        
        for rule in (current_scene.transition_rules or []):
            if self._check_transition_condition(rule.get("condition", {}), trigger, progress):
                next_scene_id = rule.get("next_scene")
                transition_narration = rule.get("narration")
                break
        
        if not next_scene_id:
            # Try to go to next scene in order
            next_scene = self.db.execute(
                select(Scene)
                .where(
                    Scene.chapter_id == current_scene.chapter_id,
                    Scene.order_index > current_scene.order_index,
                )
                .order_by(Scene.order_index)
                .limit(1)
            ).scalar_one_or_none()
            
            if next_scene:
                next_scene_id = next_scene.id
            else:
                # Try next chapter
                return self._advance_to_next_chapter(user, progress)
        
        if not next_scene_id:
            return None
        
        # Update progress
        next_scene = self.db.get(Scene, next_scene_id)
        if not next_scene:
            return None
        
        progress.current_scene_id = next_scene_id
        progress.last_played_at = datetime.now(timezone.utc)
        self.db.commit()
        
        return self.get_current_scene(user, story_id)

    def _check_transition_condition(
        self,
        condition: dict,
        trigger: str,
        progress: StoryProgress,
    ) -> bool:
        """Check if a transition condition is met."""
        
        # Simple trigger match
        if condition.get("trigger") == trigger:
            return True
        
        # Flag-based condition
        if "flag" in condition:
            flag_name = condition["flag"]
            expected = condition.get("value", True)
            actual = (progress.story_flags or {}).get(flag_name)
            if actual == expected:
                return True
        
        return False

    def _advance_to_next_chapter(
        self,
        user: User,
        progress: StoryProgress,
    ) -> SceneContext | None:
        """Advance to the first scene of the next chapter."""
        
        current_chapter = self.db.get(Chapter, progress.current_chapter_id)
        if not current_chapter:
            return None
        
        # Mark current chapter as completed
        completed = progress.chapters_completed or []
        if current_chapter.id not in completed:
            completed.append(current_chapter.id)
            progress.chapters_completed = completed
        
        # Find next chapter
        next_chapter = self.db.execute(
            select(Chapter)
            .where(
                Chapter.story_id == progress.story_id,
                Chapter.order_index > current_chapter.order_index,
            )
            .order_by(Chapter.order_index)
            .limit(1)
        ).scalar_one_or_none()
        
        if not next_chapter:
            # Story complete
            progress.status = "completed"
            progress.completion_percentage = 100
            progress.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            return None
        
        # Get first scene of next chapter
        first_scene = self.db.execute(
            select(Scene)
            .where(Scene.chapter_id == next_chapter.id)
            .order_by(Scene.order_index)
            .limit(1)
        ).scalar_one_or_none()
        
        if not first_scene:
            return None
        
        # Update progress
        progress.current_chapter_id = next_chapter.id
        progress.current_scene_id = first_scene.id
        progress.last_played_at = datetime.now(timezone.utc)
        
        # Calculate completion percentage
        total_chapters = self.db.execute(
            select(Chapter).where(Chapter.story_id == progress.story_id)
        ).scalars().all()
        progress.completion_percentage = int(len(completed) / len(total_chapters) * 100)
        
        self.db.commit()
        
        return self.get_current_scene(user, progress.story_id)

    def set_story_flag(self, user: User, story_id: str, flag: str, value: any = True) -> None:
        """Set a story flag in the user's progress."""
        progress = self.get_story_progress(user, story_id)
        if not progress:
            return
        
        flags = progress.story_flags or {}
        flags[flag] = value
        progress.story_flags = flags
        self.db.commit()

    def record_player_choice(
        self,
        user: User,
        story_id: str,
        scene_id: str,
        choice_id: str,
    ) -> None:
        """Record a player choice for potential future reference."""
        progress = self.get_story_progress(user, story_id)
        if not progress:
            return
        
        choices = progress.player_choices or []
        choices.append({
            "scene_id": scene_id,
            "choice_id": choice_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        progress.player_choices = choices
        self.db.commit()

    def add_philosophical_learning(self, user: User, story_id: str, learning: str) -> None:
        """Add a philosophical learning to the user's progress."""
        progress = self.get_story_progress(user, story_id)
        if not progress:
            return
        
        learnings = progress.philosophical_learnings or []
        if learning not in learnings:
            learnings.append(learning)
            progress.philosophical_learnings = learnings
            self.db.commit()

    def unlock_book_quote(self, user: User, story_id: str, quote_id: str) -> None:
        """Unlock a book quote for the user."""
        progress = self.get_story_progress(user, story_id)
        if not progress:
            return
        
        quotes = progress.book_quotes_unlocked or []
        if quote_id not in quotes:
            quotes.append(quote_id)
            progress.book_quotes_unlocked = quotes
            self.db.commit()

    def queue_scene_vocabulary(
        self,
        user: User,
        chapter: Chapter,
        progress_service: "ProgressService",
    ) -> list[VocabularyWord]:
        """Queue vocabulary from a chapter's learning focus into user's practice queue.
        
        This creates the Story→Vocabulary synergy by ensuring that words
        encountered in stories appear in the user's spaced repetition queue.
        
        Returns the list of vocabulary words that were queued.
        """
        queued_words: list[VocabularyWord] = []
        
        # Get vocabulary from chapter's learning focus
        learning_focus = chapter.learning_focus or {}
        vocab_list = learning_focus.get("vocabulary", [])
        
        if not vocab_list:
            return queued_words
        
        # Find matching vocabulary words in the database
        for vocab_item in vocab_list:
            # vocab_item can be a string (word) or dict with word/translation
            if isinstance(vocab_item, str):
                word_text = vocab_item
            elif isinstance(vocab_item, dict):
                word_text = vocab_item.get("word", vocab_item.get("term", ""))
            else:
                continue
            
            if not word_text:
                continue
            
            # Find the vocabulary word
            vocab_word = self.db.execute(
                select(VocabularyWord).where(
                    VocabularyWord.normalized_word == word_text.lower()
                )
            ).scalar_one_or_none()
            
            if not vocab_word:
                # Try by exact word match
                vocab_word = self.db.execute(
                    select(VocabularyWord).where(
                        VocabularyWord.word == word_text
                    )
                ).scalar_one_or_none()
            
            if vocab_word:
                # Get or create progress entry (this adds it to the queue)
                progress_service.get_or_create_progress(
                    user_id=user.id,
                    word_id=vocab_word.id,
                )
                queued_words.append(vocab_word)
                logger.debug(
                    "Queued story vocabulary",
                    word=vocab_word.word,
                    chapter=chapter.title,
                    user_id=str(user.id),
                )
        
        if queued_words:
            logger.info(
                "Story→Vocabulary integration",
                chapter=chapter.title,
                words_queued=len(queued_words),
                user_id=str(user.id),
            )
        
        return queued_words

    def get_chapter_vocabulary(self, chapter: Chapter) -> list[dict]:
        """Get vocabulary words defined for a chapter with their details.
        
        Returns a list of dicts with word info for display in VocabularyHelper.
        """
        learning_focus = chapter.learning_focus or {}
        vocab_list = learning_focus.get("vocabulary", [])
        
        result = []
        for vocab_item in vocab_list:
            if isinstance(vocab_item, str):
                word_text = vocab_item
                translation = None
            elif isinstance(vocab_item, dict):
                word_text = vocab_item.get("word", vocab_item.get("term", ""))
                translation = vocab_item.get("translation", vocab_item.get("meaning"))
            else:
                continue
            
            if not word_text:
                continue
            
            # Look up full vocabulary word details
            vocab_word = self.db.execute(
                select(VocabularyWord).where(
                    VocabularyWord.normalized_word == word_text.lower()
                )
            ).scalar_one_or_none()
            
            if vocab_word:
                result.append({
                    "id": vocab_word.id,
                    "word": vocab_word.word,
                    "translation": translation or vocab_word.english_translation,
                    "definition": vocab_word.definition,
                    "example": vocab_word.example_sentence,
                    "from_story": True,
                })
            else:
                # Include even if not in our vocabulary database
                result.append({
                    "id": None,
                    "word": word_text,
                    "translation": translation,
                    "definition": None,
                    "example": None,
                    "from_story": True,
                })

        return result

    # ------------------------------------------------------------------
    # Chapter-based goal checking (merged from worktree)
    # ------------------------------------------------------------------

    def check_narrative_goals(
        self, session_id: uuid.UUID, chapter: Chapter
    ) -> "GoalCheckResult":
        """
        Evaluate narrative goal completion based on session messages.

        Uses French morphological matching to detect if required vocabulary
        words were used in their conjugated/declined forms.

        Args:
            session_id: The learning session ID
            chapter: The story chapter with narrative goals

        Returns:
            GoalCheckResult with completed and remaining goal IDs
        """
        from app.db.models.session import ConversationMessage
        import unicodedata
        import re

        def normalize_text(text: str) -> str:
            """Normalize text for comparison (lowercase, remove accents)."""
            normalized = unicodedata.normalize('NFD', text.lower())
            return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

        def get_french_stem(word: str) -> str:
            """Get approximate stem for French word matching."""
            normalized = normalize_text(word)
            # Common French verb infinitive endings
            if normalized.endswith('er'):
                return normalized[:-2]
            if normalized.endswith('ir'):
                return normalized[:-2]
            if normalized.endswith('re'):
                return normalized[:-2]
            if normalized.endswith('oir'):
                return normalized[:-3]
            # Handle past participles and other forms
            if normalized.endswith('e') and len(normalized) > 3:
                return normalized[:-1]
            if normalized.endswith('u') and len(normalized) > 3:
                return normalized[:-1]
            return normalized

        def word_matches(required_word: str, text_words: list[str], full_text: str) -> bool:
            """Check if required word (or its conjugated form) appears in user text."""
            normalized_required = normalize_text(required_word)
            required_stem = get_french_stem(required_word)

            # Direct match check
            if normalized_required in full_text:
                return True

            # Stem-based matching for verbs
            for user_word in text_words:
                normalized_user = normalize_text(user_word)
                user_stem = get_french_stem(user_word)

                # Check exact normalized match
                if normalized_user == normalized_required:
                    return True

                # Check stem match (for verb conjugations)
                # e.g., "cherch" matches "cherche", "chercher", "cherché"
                if len(required_stem) >= 4:  # Only stem-match for words with substantial stems
                    if normalized_user.startswith(required_stem):
                        return True
                    if user_stem == required_stem:
                        return True

                # Special handling for French irregular verbs
                # disparaître -> disparu, dispara-, dispar-
                if 'dispar' in normalized_required and 'dispar' in normalized_user:
                    return True
                if 'trouv' in normalized_required and 'trouv' in normalized_user:
                    return True

            return False

        # Get all user messages for this session
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.session_id == session_id,
                ConversationMessage.sender == "user"
            )
        )
        user_messages = self.db.execute(stmt).scalars().all()

        # Combine all user message content
        all_user_text = " ".join(msg.content for msg in user_messages)
        normalized_full_text = normalize_text(all_user_text)

        # Extract individual words from user text
        user_words = re.findall(r'\b\w+\b', all_user_text)

        # Check each narrative goal
        completed_goals = []
        narrative_goals = chapter.narrative_goals or []

        for goal in narrative_goals:
            goal_id = goal["goal_id"]
            required_words = goal.get("required_words", [])

            if not required_words:
                continue

            matched = [
                word
                for word in required_words
                if word_matches(word, user_words, normalized_full_text)
            ]
            # Default to requiring at least one match unless the goal specifies otherwise
            minimum_hits = max(1, int(goal.get("min_required", 1)))
            minimum_hits = min(minimum_hits, len(required_words))

            if len(matched) >= minimum_hits:
                completed_goals.append(goal_id)

        remaining_goals = [
            g["goal_id"] for g in narrative_goals if g["goal_id"] not in completed_goals
        ]

        completion_rate = (
            len(completed_goals) / len(narrative_goals) if narrative_goals else 0.0
        )

        return GoalCheckResult(
            goals_completed=completed_goals,
            goals_remaining=remaining_goals,
            completion_rate=completion_rate,
        )

    def complete_chapter_with_goals(
        self,
        user: User,
        chapter_id: str,
        session_id: uuid.UUID,
        goal_results: "GoalCheckResult",
    ) -> "ChapterCompletionReward":
        """Award XP, unlock next chapter, check achievements.

        Args:
            user: Current user
            chapter_id: Chapter being completed
            session_id: Learning session that was just completed
            goal_results: Results of narrative goal evaluation

        Returns:
            ChapterCompletionReward with XP, achievements, next chapter info

        Raises:
            ValueError: If chapter not found or user has no progress for this story
        """
        # Load chapter
        chapter = self.db.get(Chapter, chapter_id)
        if not chapter:
            raise ValueError(f"Chapter {chapter_id} not found")

        # Get user's story progress
        progress = self.get_story_progress(user, chapter.story_id)
        if not progress:
            raise ValueError(f"User has no progress for story {chapter.story_id}")

        # Check if chapter meets completion criteria
        criteria = chapter.completion_criteria or {}
        min_goals = criteria.get("min_goals_completed", 0)
        goals_met = len(goal_results.goals_completed) >= min_goals

        # Calculate XP
        is_perfect = goal_results.completion_rate == 1.0 and goals_met
        xp_earned = chapter.perfect_completion_xp if is_perfect else chapter.completion_xp

        # Update detailed completion tracking
        chapters_completed_details = progress.chapters_completed_details or []
        chapters_completed_details.append({
            "chapter_id": chapter.id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "xp_earned": xp_earned,
            "was_perfect": is_perfect,
            "goals_completed": goal_results.goals_completed,
        })
        progress.chapters_completed_details = chapters_completed_details

        # Update simple completion list too
        chapters_completed = progress.chapters_completed or []
        if chapter.id not in chapters_completed:
            chapters_completed.append(chapter.id)
            progress.chapters_completed = chapters_completed

        # Update XP tracking
        progress.total_xp_earned = (progress.total_xp_earned or 0) + xp_earned
        if is_perfect:
            progress.perfect_chapters_count = (progress.perfect_chapters_count or 0) + 1

        # Calculate completion percentage
        total_chapters = self.db.execute(
            select(Chapter).where(Chapter.story_id == chapter.story_id)
        ).scalars().all()
        progress.completion_percentage = int(
            len(chapters_completed) / len(total_chapters) * 100
        ) if total_chapters else 0

        # Determine next chapter
        next_chapter = None
        story_completed = False

        if chapter.default_next_chapter_id:
            next_chapter = self.db.get(Chapter, chapter.default_next_chapter_id)
            if next_chapter:
                progress.current_chapter_id = next_chapter.id
                # Get first scene of next chapter
                first_scene = self.db.execute(
                    select(Scene)
                    .where(Scene.chapter_id == next_chapter.id)
                    .order_by(Scene.order_index)
                    .limit(1)
                ).scalar_one_or_none()
                if first_scene:
                    progress.current_scene_id = first_scene.id
        else:
            # Check for next chapter by order_index
            next_by_order = self.db.execute(
                select(Chapter)
                .where(
                    Chapter.story_id == chapter.story_id,
                    Chapter.order_index > chapter.order_index,
                )
                .order_by(Chapter.order_index)
                .limit(1)
            ).scalar_one_or_none()

            if next_by_order:
                next_chapter = next_by_order
                progress.current_chapter_id = next_chapter.id
                # Get first scene
                first_scene = self.db.execute(
                    select(Scene)
                    .where(Scene.chapter_id == next_chapter.id)
                    .order_by(Scene.order_index)
                    .limit(1)
                ).scalar_one_or_none()
                if first_scene:
                    progress.current_scene_id = first_scene.id
            else:
                # No next chapter - story is complete
                story_completed = True
                progress.status = "completed"
                progress.completion_percentage = 100
                progress.completed_at = datetime.now(timezone.utc)

        progress.last_played_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(progress)

        return ChapterCompletionReward(
            xp_earned=xp_earned,
            achievements_unlocked=[],  # TODO: Implement achievements
            next_chapter=next_chapter,
            story_completed=story_completed,
            is_perfect=is_perfect,
        )

    def make_narrative_choice(
        self,
        user: User,
        story_id: str,
        choice_id: str,
    ) -> "NextChapterResult":
        """Record user's choice and advance to corresponding chapter.

        Args:
            user: Current user
            story_id: Story ID
            choice_id: Choice ID from branching_choices

        Returns:
            NextChapterResult with next chapter and recorded choice

        Raises:
            ValueError: If choice_id is invalid
        """
        progress = self.get_story_progress(user, story_id)
        if not progress:
            raise ValueError("No progress found for this story")

        current_chapter = self.db.get(Chapter, progress.current_chapter_id)
        if not current_chapter:
            raise ValueError("No current chapter")

        # Find the choice in branching_choices
        choices = current_chapter.branching_choices or []
        choice = next(
            (c for c in choices if c["choice_id"] == choice_id),
            None,
        )

        if not choice:
            raise ValueError(f"Invalid choice_id: {choice_id}")

        # Record choice in narrative_choices
        narrative_choices = progress.narrative_choices or {}
        narrative_choices[current_chapter.id] = choice_id
        progress.narrative_choices = narrative_choices

        # Get next chapter based on choice
        next_chapter_id = choice.get("next_chapter_id") or current_chapter.default_next_chapter_id
        if not next_chapter_id:
            raise ValueError("No next chapter specified for this choice")

        next_chapter = self.db.get(Chapter, next_chapter_id)
        if not next_chapter:
            raise ValueError(f"Next chapter {next_chapter_id} not found")

        # Update current chapter
        progress.current_chapter_id = next_chapter_id

        # Get first scene of next chapter
        first_scene = self.db.execute(
            select(Scene)
            .where(Scene.chapter_id == next_chapter_id)
            .order_by(Scene.order_index)
            .limit(1)
        ).scalar_one_or_none()
        if first_scene:
            progress.current_scene_id = first_scene.id

        progress.last_played_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(progress)

        return NextChapterResult(
            next_chapter=next_chapter,
            choice_recorded=choice_id,
        )


# Dataclasses for goal checking results (merged from worktree)
@dataclass
class GoalCheckResult:
    """Result of narrative goal evaluation."""
    goals_completed: list[str]  # goal_ids
    goals_remaining: list[str]  # goal_ids
    completion_rate: float


@dataclass
class ChapterCompletionReward:
    """Rewards for completing a chapter."""
    xp_earned: int
    achievements_unlocked: list[dict]
    next_chapter: Chapter | None
    story_completed: bool
    is_perfect: bool


@dataclass
class NextChapterResult:
    """Result of making a narrative choice."""
    next_chapter: Chapter
    choice_recorded: str
