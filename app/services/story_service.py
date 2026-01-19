"""Business logic for interactive story learning."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.session import LearningSession
from app.db.models.story import Story, StoryChapter, UserStoryProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.progress import ProgressService


@dataclass(slots=True)
class StoryWithProgress:
    """Story with user progress overlay."""

    story: Story
    progress: UserStoryProgress | None
    completion_percentage: float
    is_started: bool
    is_completed: bool
    current_chapter_number: int | None


@dataclass(slots=True)
class StoryDetailResponse:
    """Complete story information with chapters and progress."""

    story: Story
    chapters: list[ChapterWithStatus]
    user_progress: UserStoryProgress | None


@dataclass(slots=True)
class ChapterWithStatus:
    """Chapter with user completion status."""

    chapter: StoryChapter
    is_locked: bool
    is_completed: bool
    was_perfect: bool


@dataclass(slots=True)
class GoalCheckResult:
    """Result of narrative goal evaluation."""

    goals_completed: list[str]  # goal_ids
    goals_remaining: list[str]  # goal_ids
    completion_rate: float


@dataclass(slots=True)
class ChapterCompletionReward:
    """Rewards for completing a chapter."""

    xp_earned: int
    achievements_unlocked: list[dict[str, Any]]
    next_chapter: StoryChapter | None
    story_completed: bool
    is_perfect: bool


@dataclass(slots=True)
class NextChapterResult:
    """Result of making a narrative choice."""

    next_chapter: StoryChapter
    choice_recorded: str


class StoryService:
    """High level helper for story-based learning workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.progress_service = ProgressService(db)

    # ------------------------------------------------------------------
    # Story browsing and discovery
    # ------------------------------------------------------------------

    def list_available_stories(
        self,
        user: User,
        difficulty_filter: str | None = None,
        theme_filter: str | None = None,
    ) -> list[StoryWithProgress]:
        """List all published stories with user progress overlays.

        Args:
            user: Current user
            difficulty_filter: Optional CEFR level filter (A1, A2, B1, B2, C1, C2)
            theme_filter: Optional theme tag filter

        Returns:
            List of stories with progress information
        """
        # Build base query for published stories
        stmt = select(Story).where(Story.is_published == True)  # noqa: E712

        # Apply filters
        if difficulty_filter:
            stmt = stmt.where(Story.difficulty_level == difficulty_filter)

        if theme_filter:
            # Check if theme is in the JSONB array
            stmt = stmt.where(Story.theme_tags.contains([theme_filter]))

        # Execute query
        stories = self.db.execute(stmt).scalars().all()

        # Build response with progress overlays
        result = []
        for story in stories:
            # Get user progress for this story
            progress = self._get_user_story_progress(user.id, story.id)

            # Calculate completion percentage
            completion_pct = 0.0
            current_chapter_num = None
            if progress:
                completion_pct = progress.completion_percentage or 0.0
                if progress.current_chapter:
                    current_chapter_num = progress.current_chapter.sequence_order

            result.append(
                StoryWithProgress(
                    story=story,
                    progress=progress,
                    completion_percentage=completion_pct,
                    is_started=progress is not None and progress.status == "in_progress",
                    is_completed=progress is not None and progress.status == "completed",
                    current_chapter_number=current_chapter_num,
                )
            )

        return result

    def get_story_details(self, story_id: int, user: User) -> StoryDetailResponse:
        """Get full story with all chapters and user progress.

        Args:
            story_id: Story ID
            user: Current user

        Returns:
            Complete story information with chapter list and progress

        Raises:
            ValueError: If story not found
        """
        # Load story with chapters
        stmt = (
            select(Story)
            .where(Story.id == story_id)
            .options(joinedload(Story.chapters))
        )
        story = self.db.execute(stmt).unique().scalar_one_or_none()

        if not story:
            raise ValueError(f"Story {story_id} not found")

        # Get user progress
        progress = self._get_user_story_progress(user.id, story_id)

        # Build chapter list with status
        completed_chapter_ids = set()
        perfect_chapter_ids = set()
        if progress and progress.chapters_completed:
            for chapter_completion in progress.chapters_completed:
                completed_chapter_ids.add(chapter_completion["chapter_id"])
                if chapter_completion.get("was_perfect"):
                    perfect_chapter_ids.add(chapter_completion["chapter_id"])

        current_chapter_id = progress.current_chapter_id if progress else None

        chapters_with_status = []
        for chapter in sorted(story.chapters, key=lambda c: c.sequence_order):
            is_completed = chapter.id in completed_chapter_ids
            is_locked = False

            # Lock chapters that haven't been reached yet
            if not is_completed and current_chapter_id is not None:
                # If there's a current chapter, lock all chapters after it
                if chapter.sequence_order > (progress.current_chapter.sequence_order if progress and progress.current_chapter else 0):
                    is_locked = True

            chapters_with_status.append(
                ChapterWithStatus(
                    chapter=chapter,
                    is_locked=is_locked,
                    is_completed=is_completed,
                    was_perfect=chapter.id in perfect_chapter_ids,
                )
            )

        return StoryDetailResponse(
            story=story,
            chapters=chapters_with_status,
            user_progress=progress,
        )

    # ------------------------------------------------------------------
    # Story progress management
    # ------------------------------------------------------------------

    def start_story(self, user: User, story_id: int) -> UserStoryProgress:
        """Begin new story or resume existing progress.

        Args:
            user: Current user
            story_id: Story ID to start

        Returns:
            UserStoryProgress record (new or existing)

        Raises:
            ValueError: If story not found or not published
        """
        # Check if story exists and is published
        story = self.db.get(Story, story_id)
        if not story:
            raise ValueError(f"Story {story_id} not found")
        if not story.is_published:
            raise ValueError(f"Story {story_id} is not published")

        # Check for existing progress
        existing_progress = self._get_user_story_progress(user.id, story_id)
        if existing_progress and existing_progress.status == "in_progress":
            return existing_progress

        # Get first chapter
        first_chapter = (
            self.db.execute(
                select(StoryChapter)
                .where(StoryChapter.story_id == story_id)
                .order_by(StoryChapter.sequence_order)
                .limit(1)
            )
            .scalar_one_or_none()
        )

        if not first_chapter:
            raise ValueError(f"Story {story_id} has no chapters")

        # Create new progress record
        progress = UserStoryProgress(
            id=uuid.uuid4(),
            user_id=user.id,
            story_id=story_id,
            current_chapter_id=first_chapter.id,
            status="in_progress",
            chapters_completed=[],
            total_chapters_completed=0,
            completion_percentage=0.0,
            total_xp_earned=0,
            total_time_spent_minutes=0,
            vocabulary_mastered_count=0,
            perfect_chapters_count=0,
            narrative_choices={},
            started_at=datetime.now(timezone.utc),
            last_accessed_at=datetime.now(timezone.utc),
        )

        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)

        return progress

    def get_chapter_vocabulary(
        self, chapter: StoryChapter, user: User, count: int = 7
    ) -> list[VocabularyWord]:
        """Select vocabulary for chapter using hybrid strategy.

        Hybrid approach:
        1. Filter vocabulary by chapter's theme tags
        2. Of theme-matched words, prioritize what user needs (due for review or new)
        3. Use existing ProgressService.get_learning_queue() with theme filter
        4. Ensure mix of review (60%) and new (40%) words

        Args:
            chapter: Chapter to get vocabulary for
            user: Current user
            count: Number of words to return (default: 7)

        Returns:
            List of vocabulary words matching theme + user progress needs
        """
        # Parse theme tags from story's vocabulary_theme
        story = chapter.story
        if not story.vocabulary_theme:
            # No theme specified, use regular learning queue
            return [
                item.word
                for item in self.progress_service.get_learning_queue(
                    user_id=user.id, limit=count
                )
            ]

        # Split vocabulary_theme into individual topics
        theme_tags = [tag.strip() for tag in story.vocabulary_theme.split(",")]

        # Get user's learning queue items
        queue_items = self.progress_service.get_learning_queue(
            user_id=user.id, limit=count * 3  # Get more to filter
        )

        # Filter queue items to only include words matching theme tags
        theme_matched_items = []
        for item in queue_items:
            word = item.word
            if word.topic_tags:
                # Check if any of the word's topic tags match our theme tags
                word_topics = set(word.topic_tags)
                if any(theme in word_topics for theme in theme_tags):
                    theme_matched_items.append(item)

        # If we don't have enough theme-matched words, add more from vocabulary
        if len(theme_matched_items) < count:
            # Query for additional words matching themes
            stmt = (
                select(VocabularyWord)
                .where(
                    or_(*[VocabularyWord.topic_tags.contains([tag]) for tag in theme_tags])
                )
                .limit(count - len(theme_matched_items))
            )
            additional_words = self.db.execute(stmt).scalars().all()

            # Add these words (they'll be "new" for the user)
            for word in additional_words:
                if word not in [item.word for item in theme_matched_items]:
                    theme_matched_items.append(
                        type("QueueItem", (), {"word": word, "is_new": True})()
                    )

        # Return up to `count` words
        return [item.word for item in theme_matched_items[:count]]

    def check_narrative_goals(
        self, chapter: StoryChapter, session_messages: list[dict[str, Any]]
    ) -> GoalCheckResult:
        """Evaluate if narrative goals are met based on conversation.

        Args:
            chapter: Chapter with narrative_goals
            session_messages: List of conversation messages

        Returns:
            GoalCheckResult with completed/remaining goals
        """
        if not chapter.narrative_goals:
            return GoalCheckResult(
                goals_completed=[],
                goals_remaining=[],
                completion_rate=1.0,
            )

        # Extract user messages (where vocabulary is used)
        user_messages = [
            msg["content"]
            for msg in session_messages
            if msg.get("role") == "user"
        ]
        all_user_text = " ".join(user_messages).lower()

        goals_completed = []
        goals_remaining = []

        for goal in chapter.narrative_goals:
            goal_id = goal["goal_id"]
            required_words = goal.get("required_words", [])

            # Check if all required words were used
            all_words_used = True
            for word in required_words:
                if word.lower() not in all_user_text:
                    all_words_used = False
                    break

            if all_words_used:
                goals_completed.append(goal_id)
            else:
                goals_remaining.append(goal_id)

        completion_rate = (
            len(goals_completed) / len(chapter.narrative_goals)
            if chapter.narrative_goals
            else 1.0
        )

        return GoalCheckResult(
            goals_completed=goals_completed,
            goals_remaining=goals_remaining,
            completion_rate=completion_rate,
        )

    def complete_chapter(
        self,
        user: User,
        chapter_id: int,
        session: LearningSession,
        goal_results: GoalCheckResult,
    ) -> ChapterCompletionReward:
        """Award XP, unlock next chapter, check achievements.

        Args:
            user: Current user
            chapter_id: Chapter being completed
            session: Learning session that was just completed
            goal_results: Results of narrative goal evaluation

        Returns:
            ChapterCompletionReward with XP, achievements, next chapter info

        Raises:
            ValueError: If chapter not found or user has no progress for this story
        """
        # Load chapter
        chapter = self.db.get(StoryChapter, chapter_id)
        if not chapter:
            raise ValueError(f"Chapter {chapter_id} not found")

        # Get user's story progress
        progress = self._get_user_story_progress(user.id, chapter.story_id)
        if not progress:
            raise ValueError(f"User has no progress for story {chapter.story_id}")

        # Check if chapter meets completion criteria
        criteria = chapter.completion_criteria or {}
        min_goals = criteria.get("min_goals_completed", 0)
        goals_met = len(goal_results.goals_completed) >= min_goals

        # Calculate XP
        is_perfect = goal_results.completion_rate == 1.0 and goals_met
        xp_earned = chapter.perfect_completion_xp if is_perfect else chapter.completion_xp

        # Update progress
        chapters_completed = progress.chapters_completed or []
        chapters_completed.append(
            {
                "chapter_id": chapter.id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "xp_earned": xp_earned,
                "was_perfect": is_perfect,
                "goals_completed": goal_results.goals_completed,
            }
        )

        progress.chapters_completed = chapters_completed
        progress.total_chapters_completed += 1
        progress.total_xp_earned += xp_earned
        if is_perfect:
            progress.perfect_chapters_count += 1

        # Calculate completion percentage
        progress.completion_percentage = (
            progress.total_chapters_completed / chapter.story.total_chapters * 100
            if chapter.story.total_chapters > 0
            else 0.0
        )

        # Determine next chapter
        next_chapter = None
        story_completed = False

        if chapter.default_next_chapter_id:
            next_chapter = self.db.get(StoryChapter, chapter.default_next_chapter_id)
            progress.current_chapter_id = next_chapter.id
        else:
            # No next chapter - story is complete
            story_completed = True
            progress.status = "completed"
            progress.completed_at = datetime.now(timezone.utc)

        progress.last_accessed_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(progress)

        # TODO: Trigger achievement checks
        achievements_unlocked = []

        return ChapterCompletionReward(
            xp_earned=xp_earned,
            achievements_unlocked=achievements_unlocked,
            next_chapter=next_chapter,
            story_completed=story_completed,
            is_perfect=is_perfect,
        )

    def make_narrative_choice(
        self,
        user: User,
        story_progress: UserStoryProgress,
        choice_id: str,
    ) -> NextChapterResult:
        """Record user's choice and advance to corresponding chapter.

        Args:
            user: Current user
            story_progress: User's story progress
            choice_id: Choice ID from branching_choices

        Returns:
            NextChapterResult with next chapter and recorded choice

        Raises:
            ValueError: If choice_id is invalid
        """
        current_chapter = story_progress.current_chapter
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
        narrative_choices = story_progress.narrative_choices or {}
        narrative_choices[current_chapter.chapter_key] = choice_id
        story_progress.narrative_choices = narrative_choices

        # Get next chapter based on choice
        next_chapter_id = choice.get("next_chapter_id") or current_chapter.default_next_chapter_id
        if not next_chapter_id:
            raise ValueError("No next chapter specified for this choice")

        next_chapter = self.db.get(StoryChapter, next_chapter_id)
        if not next_chapter:
            raise ValueError(f"Next chapter {next_chapter_id} not found")

        # Update current chapter
        story_progress.current_chapter_id = next_chapter_id
        story_progress.last_accessed_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(story_progress)

        return NextChapterResult(
            next_chapter=next_chapter,
            choice_recorded=choice_id,
        )

    def check_narrative_goals(
        self, session_id: uuid.UUID, chapter: StoryChapter
    ) -> GoalCheckResult:
        """
        Evaluate narrative goal completion based on session messages.

        Args:
            session_id: The learning session ID
            chapter: The story chapter with narrative goals

        Returns:
            GoalCheckResult with completed and remaining goal IDs
        """
        from app.db.models.session import WordInteraction

        # Get all word interactions for this session
        stmt = select(WordInteraction).where(WordInteraction.session_id == session_id)
        word_interactions = self.db.execute(stmt).scalars().all()

        # Extract words used correctly (no errors or only minor ones)
        used_words = {
            wi.word.word
            for wi in word_interactions
            if wi.word and wi.interaction_type in ("used_correctly", "practice_recall")
        }

        # Check each narrative goal
        completed_goals = []
        narrative_goals = chapter.narrative_goals or []

        for goal in narrative_goals:
            goal_id = goal["goal_id"]
            required_words = goal.get("required_words", [])

            # Check if all required words were used
            if all(word in used_words for word in required_words):
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

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _get_user_story_progress(
        self, user_id: uuid.UUID, story_id: int
    ) -> UserStoryProgress | None:
        """Get user's progress for a specific story."""
        stmt = (
            select(UserStoryProgress)
            .where(
                and_(
                    UserStoryProgress.user_id == user_id,
                    UserStoryProgress.story_id == story_id,
                )
            )
            .options(joinedload(UserStoryProgress.current_chapter))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()
