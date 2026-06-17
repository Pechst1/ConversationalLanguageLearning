"""Endpoints for learner vocabulary progress."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_or_demo, get_db
from app.db.models.error import UserError
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.schemas import (
    AnkiProgressSummary,
    AnkiWordProgressRead,
    AnkiConnectSyncRequest,
    CEFRProgressResponse,
    ProgressDetail,
    QueueWord,
    ReviewRequest,
    ReviewResponse,
    UnifiedQueueItem,
    UnifiedQueueResponse,
    UnifiedQueueSummary,
    VocabularyMasteryMapCell,
    VocabularyMasteryMapResponse,
    VocabularyMasteryMapSummary,
    VocabularyRecommendationResponse,
    WeeklyDossierResponse,
    WeeklyDossierStats,
    WeeklyDossierThread,
)
from app.services.progress import ProgressService
from app.services.cefr_progress import CEFRProgressService
from app.services.unified_srs import InterleavingMode, UnifiedSRSService


router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/cefr", response_model=CEFRProgressResponse)
def get_cefr_progress(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> CEFRProgressResponse:
    """Return the visible CEFR estimate and next-level forecast."""

    return CEFRProgressResponse(**CEFRProgressService(db).current(current_user))


@router.post("/cefr/recompute", response_model=CEFRProgressResponse)
def recompute_cefr_progress(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> CEFRProgressResponse:
    """Recompute and persist a CEFR estimate snapshot."""

    return CEFRProgressResponse(**CEFRProgressService(db).recompute(current_user, source="api"))


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _progress_due(progress: UserVocabularyProgress | None, now: datetime) -> bool:
    if progress is None:
        return False
    due_at = _aware(progress.due_at) or _aware(progress.next_review_date)
    if due_at is not None:
        return due_at <= now
    return progress.due_date is not None and progress.due_date <= date.today()


def _mastery_state(progress: UserVocabularyProgress | None, now: datetime) -> str:
    if progress is None or (progress.reps or 0) == 0:
        return "new"
    if progress.state == "mastered" or (progress.proficiency_score or 0) >= 90:
        return "mastered"
    if (progress.lapses or 0) > 0 or (progress.proficiency_score or 0) < 45:
        return "fragile"
    if _progress_due(progress, now):
        return "due"
    if (progress.proficiency_score or 0) >= 70:
        return "solid"
    return "building"


def _thread(title: str, subtitle: str | None = None, *, tone: str = "neutral", count: int = 0) -> WeeklyDossierThread:
    return WeeklyDossierThread(title=title, subtitle=subtitle, tone=tone, count=count)


@router.get("/queue", response_model=list[QueueWord])
def get_review_queue(
    *,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of queue entries to return"),
    direction: str | None = Query(None, description="Optional card direction filter (fr_to_de or de_to_fr)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> list[QueueWord]:
    """Return a mix of due and new words for the authenticated learner."""

    service = ProgressService(db)
    if direction and direction not in {"fr_to_de", "de_to_fr"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid direction filter")
    queue_items = service.get_learning_queue(user=current_user, limit=limit, direction=direction)
    response: list[QueueWord] = []
    for item in queue_items:
        progress = item.progress

        response.append(
            QueueWord(
                word_id=item.word.id,
                word=item.word.word,
                language=item.word.language,
                english_translation=item.word.english_translation,
                german_translation=item.word.german_translation,
                french_translation=item.word.french_translation,
                part_of_speech=item.word.part_of_speech,
                difficulty_level=item.word.difficulty_level,
                state=progress.state if progress else "new",
                next_review=progress.next_review_date if progress else None,
                scheduled_days=progress.scheduled_days if progress else None,
                is_new=item.is_new or progress is None,
                scheduler=(progress.scheduler if progress else ("anki" if item.word.is_anki_card else "fsrs")),
            )
    )
    return response


@router.get("/unified-queue", response_model=UnifiedQueueResponse)
def get_unified_review_queue(
    *,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of unified queue entries"),
    time_budget_minutes: int | None = Query(
        None,
        ge=1,
        le=180,
        description="Optional budget used to truncate the queue by estimated time",
    ),
    interleaving_mode: str = Query(
        "random",
        description="Queue strategy: random, blocks, or priority. Random is deterministic round-robin.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> UnifiedQueueResponse:
    """Return one canonical SRS queue across vocabulary, grammar, and durable errata."""

    try:
        mode = InterleavingMode(interleaving_mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid interleaving mode",
        ) from exc

    service = UnifiedSRSService(db)
    session = service.get_daily_practice_queue(
        user_id=current_user.id,
        time_budget_minutes=time_budget_minutes,
        interleaving_mode=mode,
    )
    queue = session.queue[:limit]

    return UnifiedQueueResponse(
        summary=UnifiedQueueSummary(**session.summary.__dict__),
        queue=[UnifiedQueueItem(**service.serialize_item(item)) for item in queue],
        interleaving_mode=session.interleaving_mode.value,
        time_budget_minutes=session.time_budget_minutes,
    )


@router.get("/anki", response_model=list[AnkiWordProgressRead])
def list_anki_progress(
    *,
    direction: str | None = Query(None, description="Optional card direction filter (fr_to_de or de_to_fr)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> list[AnkiWordProgressRead]:
    """Return all imported Anki cards with their current progress for the learner."""

    service = ProgressService(db)
    if direction and direction not in {"fr_to_de", "de_to_fr"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid direction filter")
    records = service.list_anki_progress(user=current_user, direction=direction)
    return [AnkiWordProgressRead(**record) for record in records]


@router.get("/anki/summary", response_model=AnkiProgressSummary)
def get_anki_summary(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> AnkiProgressSummary:
    """Return aggregate progress metrics for imported Anki cards."""

    service = ProgressService(db)
    summary = service.anki_progress_summary(user=current_user)
    summary = service.anki_progress_summary(user=current_user)
    return AnkiProgressSummary(**summary)


@router.post("/anki/sync")
def sync_anki_progress_endpoint(
    *,
    payload: AnkiConnectSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Sync progress from AnkiConnect."""
    service = ProgressService(db)
    return service.sync_anki_progress(user=current_user, cards=payload.cards)


@router.get("/vocabulary/recommendations", response_model=VocabularyRecommendationResponse)
def get_vocabulary_recommendations(
    *,
    limit: int = Query(12, ge=1, le=50, description="Maximum number of recommendations"),
    due_limit: int = Query(6, ge=0, le=50, description="Maximum due cards to include"),
    fragile_limit: int = Query(3, ge=0, le=50, description="Maximum fragile cards to include"),
    new_limit: int = Query(3, ge=0, le=50, description="Maximum new cards to include"),
    direction: str | None = Query(None, description="Optional card direction filter (fr_to_de or de_to_fr)"),
    deck_name: str | None = Query(None, description="Optional imported deck name filter"),
    include_upcoming_days: int = Query(0, ge=0, le=14, description="Treat near-future reviews as due"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> VocabularyRecommendationResponse:
    """Return SRS-ranked vocabulary cards for today's learning loop."""

    if direction and direction not in {"fr_to_de", "de_to_fr"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid direction filter")
    service = ProgressService(db)
    recommendations = service.get_vocabulary_recommendations(
        user=current_user,
        limit=limit,
        due_limit=due_limit,
        fragile_limit=fragile_limit,
        new_limit=new_limit,
        direction=direction,
        deck_name=deck_name,
        include_upcoming_days=include_upcoming_days,
    )
    return VocabularyRecommendationResponse(**recommendations)


@router.get("/vocabulary/map", response_model=VocabularyMasteryMapResponse)
def get_vocabulary_mastery_map(
    *,
    limit: int = Query(5000, ge=1, le=5000, description="Maximum French 5000 cards to map"),
    direction: str | None = Query("fr_to_de", description="Optional card direction filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> VocabularyMasteryMapResponse:
    """Return a compact mastery map for the imported French 5000 deck."""

    if direction and direction not in {"fr_to_de", "de_to_fr"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid direction filter")

    query = db.query(VocabularyWord).filter(
        VocabularyWord.language == current_user.target_language,
        VocabularyWord.is_anki_card.is_(True),
    )
    if direction:
        query = query.filter(or_(VocabularyWord.direction == direction, VocabularyWord.direction.is_(None)))
    words = (
        query.order_by(VocabularyWord.frequency_rank.asc().nullslast(), VocabularyWord.id.asc())
        .limit(limit)
        .all()
    )
    progress_rows = (
        db.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == current_user.id,
            UserVocabularyProgress.word_id.in_([word.id for word in words] or [0]),
        )
        .all()
    )
    progress_by_word = {progress.word_id: progress for progress in progress_rows}
    now = datetime.now(timezone.utc)
    counts = {key: 0 for key in ("new", "due", "fragile", "building", "solid", "mastered")}
    cells: list[VocabularyMasteryMapCell] = []
    for word in words:
        progress = progress_by_word.get(word.id)
        state = _mastery_state(progress, now)
        counts[state] = counts.get(state, 0) + 1
        cells.append(
            VocabularyMasteryMapCell(
                word_id=word.id,
                word=word.word,
                frequency_rank=word.frequency_rank,
                mastery_state=state,
                proficiency_score=progress.proficiency_score if progress else 0,
                is_due=_progress_due(progress, now),
                lapses=progress.lapses if progress else 0,
            )
        )

    return VocabularyMasteryMapResponse(
        summary=VocabularyMasteryMapSummary(total=len(cells), **counts),
        cells=cells,
    )


@router.get("/weekly-dossier", response_model=WeeklyDossierResponse)
def get_weekly_dossier(
    *,
    period_days: int = Query(7, ge=1, le=31),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> WeeklyDossierResponse:
    """Return a deterministic editorial digest of this learner's recent work."""

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=period_days)

    progress_ids = (
        select(UserVocabularyProgress.id)
        .filter(UserVocabularyProgress.user_id == current_user.id)
    )
    vocabulary_reviews = (
        db.query(func.count(ReviewLog.id))
        .filter(ReviewLog.progress_id.in_(progress_ids))
        .filter(ReviewLog.review_date >= period_start)
        .scalar()
        or 0
    )
    repairs_filed = (
        db.query(func.count(UserError.id))
        .filter(UserError.user_id == current_user.id, UserError.created_at >= period_start)
        .scalar()
        or 0
    )
    words_seen, words_produced = (
        db.query(
            func.coalesce(func.sum(UserVocabularyProgress.times_seen), 0),
            func.coalesce(
                func.sum(UserVocabularyProgress.times_used_correctly + UserVocabularyProgress.times_used_incorrectly),
                0,
            ),
        )
        .filter(UserVocabularyProgress.user_id == current_user.id)
        .one()
    )
    missions_completed = (
        db.query(func.count(RealWorldMission.id))
        .filter(
            RealWorldMission.user_id == current_user.id,
            RealWorldMission.completed_at.isnot(None),
            RealWorldMission.completed_at >= period_start,
        )
        .scalar()
        or 0
    )
    scenes_completed = (
        db.query(func.count(GraphicNovelScene.id))
        .filter(
            GraphicNovelScene.user_id == current_user.id,
            GraphicNovelScene.completed_at.isnot(None),
            GraphicNovelScene.completed_at >= period_start,
        )
        .scalar()
        or 0
    )

    strong_rows = (
        db.query(UserVocabularyProgress, VocabularyWord)
        .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
        .filter(UserVocabularyProgress.user_id == current_user.id)
        .order_by(
            UserVocabularyProgress.proficiency_score.desc(),
            UserVocabularyProgress.times_used_correctly.desc(),
            VocabularyWord.frequency_rank.asc().nullslast(),
        )
        .limit(3)
        .all()
    )
    fragile_rows = (
        db.query(UserVocabularyProgress, VocabularyWord)
        .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
        .filter(UserVocabularyProgress.user_id == current_user.id)
        .filter(
            or_(
                UserVocabularyProgress.lapses > 0,
                UserVocabularyProgress.proficiency_score < 50,
                UserVocabularyProgress.phase.in_(["learn", "relearn", "learning", "relearning"]),
            )
        )
        .order_by(
            UserVocabularyProgress.lapses.desc(),
            UserVocabularyProgress.proficiency_score.asc(),
            VocabularyWord.frequency_rank.asc().nullslast(),
        )
        .limit(3)
        .all()
    )

    strengths = [
        _thread(
            word.word,
            f"{progress.proficiency_score or 0}/100 · {progress.times_used_correctly or 0} productive uses",
            tone="solid",
            count=progress.proficiency_score or 0,
        )
        for progress, word in strong_rows
        if (progress.proficiency_score or 0) >= 60 or (progress.times_used_correctly or 0) > 0
    ]
    fragile_threads = [
        _thread(
            word.word,
            f"{progress.lapses or 0} lapses · {progress.proficiency_score or 0}/100",
            tone="fragile",
            count=progress.lapses or 0,
        )
        for progress, word in fragile_rows
    ]
    next_actions = [
        _thread("Repair the red notes", f"{repairs_filed} new repairs filed this week", tone="repair", count=repairs_filed),
        _thread("Review today's words", f"{vocabulary_reviews} vocabulary reviews logged", tone="vocabulary", count=vocabulary_reviews),
        _thread("Use one thread in context", "Send a mission or open a Feuilleton scene", tone="create", count=missions_completed + scenes_completed),
    ]
    headline = (
        f"Semaine — {repairs_filed} repairs, {vocabulary_reviews} vocabulary reviews, "
        f"{missions_completed + scenes_completed} creative completions."
    )

    return WeeklyDossierResponse(
        period_start=period_start,
        period_end=period_end,
        headline=headline,
        stats=WeeklyDossierStats(
            repairs_filed=repairs_filed,
            vocabulary_reviews=vocabulary_reviews,
            words_seen=int(words_seen or 0),
            words_produced=int(words_produced or 0),
            missions_completed=missions_completed,
            feuilleton_scenes_completed=scenes_completed,
        ),
        strengths=strengths,
        fragile_threads=fragile_threads,
        next_actions=next_actions,
    )


@router.get("/{word_id}", response_model=ProgressDetail)
def get_progress_detail(
    *,
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> ProgressDetail:
    """Return the learner's scheduling stats for a vocabulary item."""

    service = ProgressService(db)
    word = db.get(VocabularyWord, word_id)
    if not word:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary word not found")

    progress = service.get_progress(user_id=current_user.id, word_id=word_id)
    summary = service.progress_summary(user_id=current_user.id, word_id=word_id)

    return ProgressDetail(
        word_id=word_id,
        state=progress.state if progress else "new",
        stability=progress.stability if progress else None,
        difficulty=progress.difficulty if progress else None,
        scheduled_days=progress.scheduled_days if progress else None,
        next_review=progress.next_review_date if progress else None,
        last_review=progress.last_review_date if progress else None,
        reps=summary.get("reps", 0),
        lapses=summary.get("lapses", 0),
        correct_count=summary.get("correct_count", 0),
        incorrect_count=summary.get("incorrect_count", 0),
        hint_count=progress.hint_count if progress else 0,
        proficiency_score=progress.proficiency_score if progress else 0,
        reviews_logged=summary.get("reviews_logged", 0),
    )


@router.post("/review", response_model=ReviewResponse)
def submit_review(
    *,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> ReviewResponse:
    """Register a learner review and return the next scheduled review time."""

    word = db.get(VocabularyWord, payload.word_id)
    if not word:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary word not found")

    service = ProgressService(db)
    progress, review_log, outcome = service.record_review(
        user=current_user,
        word=word,
        rating=payload.rating,
    )
    if payload.response_time_ms is not None:
        review_log.response_time_ms = payload.response_time_ms

    db.commit()
    db.refresh(progress)

    return ReviewResponse(
        word_id=word.id,
        state=progress.state,
        stability=progress.stability or 0.0,
        difficulty=progress.difficulty or 0.0,
        scheduled_days=progress.scheduled_days or 0,
        next_review=outcome.next_review,
    )


@router.post("/bump/{word_id}")
def bump_word_difficulty(
    *,
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> dict:
    """
    Bump a word's difficulty to schedule it for earlier review.
    This is equivalent to marking a word as "Again" in spaced repetition.
    Used when a user clicks on a word during conversation to indicate they need more practice.
    """
    word = db.get(VocabularyWord, word_id)
    if not word:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary word not found")

    service = ProgressService(db)
    # Submit a review with rating 0 ("Again") to reschedule the word
    progress, review_log, outcome = service.record_review(
        user=current_user,
        word=word,
        rating=0,  # "Again" rating
    )
    db.commit()
    db.refresh(progress)

    return {
        "word_id": word_id,
        "message": "Word scheduled for earlier review",
        "next_review": outcome.next_review.isoformat() if outcome.next_review else None,
        "state": progress.state,
    }


@router.get("/insights/weekly")
def get_weekly_insights(
    *,
    force_refresh: bool = Query(False, description="Force regenerate insights (bypass cache)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get AI-powered weekly learning insights and recommendations.
    
    This endpoint generates personalized insights based on the user's
    learning analytics, including:
    - Progress summary for the week
    - Strengths and areas for improvement
    - Specific actionable recommendations
    - Motivational encouragement
    
    Results are cached for 24 hours unless force_refresh is True.
    """
    from app.services.insights_service import InsightsService
    
    insights_service = InsightsService(db)
    insight = insights_service.generate_weekly_insight(
        user=current_user,
        force_refresh=force_refresh,
    )
    
    return {
        "generated_at": insight.generated_at.isoformat(),
        "period_days": insight.period_days,
        "headline": insight.headline,
        "progress_summary": insight.progress_summary,
        "strengths": insight.strengths,
        "improvements": insight.improvements,
        "recommendations": insight.recommendations,
        "encouragement": insight.encouragement,
    }
