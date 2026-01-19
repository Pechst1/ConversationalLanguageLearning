"""Story management endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.session import LearningSession
from app.db.models.story import Story, StoryChapter, UserStoryProgress
from app.db.models.user import User
from app.schemas.story import (
    ChapterBase,
    ChapterCompletionRequest,
    ChapterCompletionResponse,
    ChapterSessionRequest,
    ChapterWithStatus,
    GoalCheckRequest,
    GoalCheckResponse,
    NarrativeChoiceRequest,
    NextChapterResponse,
    StoryBase,
    StoryDetailResponse,
    StoryListItem,
    StoryProgressSummary,
    UserStoryProgressBase,
    UserStoryProgressResponse,
)
from app.services.story_service import (
    ChapterCompletionReward,
    GoalCheckResult,
    StoryService,
    StoryWithProgress,
)

router = APIRouter(prefix="/stories", tags=["stories"])


def _story_to_base(story: Story) -> StoryBase:
    """Convert Story model to StoryBase schema."""
    return StoryBase(
        id=story.id,
        story_key=story.story_key,
        title=story.title,
        description=story.description,
        difficulty_level=story.difficulty_level,
        estimated_duration_minutes=story.estimated_duration_minutes,
        theme_tags=story.theme_tags or [],
        vocabulary_theme=story.vocabulary_theme,
        cover_image_url=story.cover_image_url,
        author=story.author,
        total_chapters=story.total_chapters,
        is_published=story.is_published,
    )


def _chapter_to_base(chapter: StoryChapter) -> ChapterBase:
    """Convert StoryChapter model to ChapterBase schema."""
    return ChapterBase(
        id=chapter.id,
        chapter_key=chapter.chapter_key,
        sequence_order=chapter.sequence_order,
        title=chapter.title,
        synopsis=chapter.synopsis,
        opening_narrative=chapter.opening_narrative,
        min_turns=chapter.min_turns,
        max_turns=chapter.max_turns,
        narrative_goals=chapter.narrative_goals or [],
        completion_criteria=chapter.completion_criteria,
        branching_choices=chapter.branching_choices,
        completion_xp=chapter.completion_xp,
        perfect_completion_xp=chapter.perfect_completion_xp,
    )


def _progress_to_base(progress: UserStoryProgress) -> UserStoryProgressBase:
    """Convert UserStoryProgress model to schema."""
    return UserStoryProgressBase(
        id=progress.id,
        user_id=progress.user_id,
        story_id=progress.story_id,
        current_chapter_id=progress.current_chapter_id,
        status=progress.status,
        chapters_completed=progress.chapters_completed or [],
        total_chapters_completed=progress.total_chapters_completed,
        completion_percentage=progress.completion_percentage,
        total_xp_earned=progress.total_xp_earned,
        total_time_spent_minutes=progress.total_time_spent_minutes,
        vocabulary_mastered_count=progress.vocabulary_mastered_count,
        perfect_chapters_count=progress.perfect_chapters_count,
        narrative_choices=progress.narrative_choices or {},
        started_at=progress.started_at,
        last_accessed_at=progress.last_accessed_at,
        completed_at=progress.completed_at,
    )


@router.get("", response_model=list[StoryListItem])
def list_stories(
    difficulty: str | None = Query(None, description="Filter by CEFR level (A1, A2, B1, B2, C1, C2)"),
    theme: str | None = Query(None, description="Filter by theme tag"),
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StoryListItem]:
    """List all available stories with user progress."""
    service = StoryService(db)
    stories_with_progress = service.list_available_stories(
        user=current_user,
        difficulty_filter=difficulty,
        theme_filter=theme,
    )

    result = []
    for item in stories_with_progress:
        # Build progress summary
        progress_summary = None
        if item.progress:
            current_chapter_title = None
            if item.progress.current_chapter:
                current_chapter_title = item.progress.current_chapter.title

            progress_summary = StoryProgressSummary(
                is_started=item.is_started,
                is_completed=item.is_completed,
                completion_percentage=item.completion_percentage,
                current_chapter_number=item.current_chapter_number,
                current_chapter_title=current_chapter_title,
                chapters_completed=item.progress.total_chapters_completed,
                total_xp_earned=item.progress.total_xp_earned,
            )

        result.append(
            StoryListItem(
                story=_story_to_base(item.story),
                user_progress=progress_summary,
            )
        )

    return result


@router.get("/{story_id}", response_model=StoryDetailResponse)
def get_story(
    story_id: int,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoryDetailResponse:
    """Get full story details including chapters and progress."""
    service = StoryService(db)

    try:
        detail = service.get_story_details(story_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # Convert to schemas
    chapters_with_status = [
        ChapterWithStatus(
            chapter=_chapter_to_base(ch.chapter),
            is_locked=ch.is_locked,
            is_completed=ch.is_completed,
            was_perfect=ch.was_perfect,
        )
        for ch in detail.chapters
    ]

    progress_schema = None
    if detail.user_progress:
        progress_schema = _progress_to_base(detail.user_progress)

    return StoryDetailResponse(
        story=_story_to_base(detail.story),
        chapters=chapters_with_status,
        user_progress=progress_schema,
    )


@router.post("/{story_id}/start", response_model=UserStoryProgressResponse)
def start_story(
    story_id: int,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserStoryProgressResponse:
    """Begin or resume a story."""
    service = StoryService(db)

    try:
        progress = service.start_story(current_user, story_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Load current chapter if exists
    current_chapter = None
    if progress.current_chapter_id:
        current_chapter = db.get(StoryChapter, progress.current_chapter_id)

    return UserStoryProgressResponse(
        progress=_progress_to_base(progress),
        current_chapter=_chapter_to_base(current_chapter) if current_chapter else None,
    )


@router.post(
    "/{story_id}/chapters/{chapter_id}/check-goals",
    response_model=GoalCheckResponse,
)
def check_chapter_goals(
    story_id: int,
    chapter_id: int,
    payload: GoalCheckRequest,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalCheckResponse:
    """Check which narrative goals have been completed in the current session."""
    service = StoryService(db)

    # Get the session
    session = db.get(LearningSession, payload.session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Verify session belongs to this chapter
    if session.story_chapter_id != chapter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session does not belong to this chapter",
        )

    # Get the chapter
    chapter = db.get(StoryChapter, chapter_id)
    if not chapter or chapter.story_id != story_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    # Check narrative goals
    result = service.check_narrative_goals(
        session_id=payload.session_id,
        chapter=chapter,
    )

    return GoalCheckResponse(
        goals_completed=result.goals_completed,
        goals_remaining=result.goals_remaining,
        completion_rate=result.completion_rate,
    )


@router.post(
    "/{story_id}/chapters/{chapter_id}/complete",
    response_model=ChapterCompletionResponse,
)
def complete_chapter(
    story_id: int,
    chapter_id: int,
    payload: ChapterCompletionRequest,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChapterCompletionResponse:
    """Mark chapter complete and unlock next."""
    service = StoryService(db)

    # Get the session
    session = db.get(LearningSession, payload.session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Verify session belongs to this chapter
    if session.story_chapter_id != chapter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session does not belong to this chapter",
        )

    # Build goal results from completed goals
    goal_results = GoalCheckResult(
        goals_completed=payload.goals_completed,
        goals_remaining=[],  # Not needed for completion
        completion_rate=1.0 if payload.goals_completed else 0.0,
    )

    try:
        reward = service.complete_chapter(
            user=current_user,
            chapter_id=chapter_id,
            session=session,
            goal_results=goal_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Convert to response
    next_chapter_schema = None
    if reward.next_chapter:
        next_chapter_schema = _chapter_to_base(reward.next_chapter)

    return ChapterCompletionResponse(
        xp_earned=reward.xp_earned,
        achievements_unlocked=reward.achievements_unlocked,
        next_chapter_id=reward.next_chapter.id if reward.next_chapter else None,
        next_chapter=next_chapter_schema,
        story_completed=reward.story_completed,
        is_perfect=reward.is_perfect,
    )


@router.post("/{story_id}/make-choice", response_model=NextChapterResponse)
def make_narrative_choice(
    story_id: int,
    payload: NarrativeChoiceRequest,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NextChapterResponse:
    """Record narrative choice and advance to next chapter."""
    service = StoryService(db)

    # Get user's story progress
    progress = service._get_user_story_progress(current_user.id, story_id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No progress found for story {story_id}",
        )

    try:
        result = service.make_narrative_choice(
            user=current_user,
            story_progress=progress,
            choice_id=payload.choice_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return NextChapterResponse(
        next_chapter=_chapter_to_base(result.next_chapter),
        choice_recorded=result.choice_recorded,
    )
