"""Enhanced SRS service with dual FSRS and Anki SM-2 support.

This service provides unified scheduling for both imported Anki cards
and native vocabulary, ensuring seamless integration and synchronization.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress, ReviewLog
from app.services.srs import FSRSScheduler, ReviewOutcome, SchedulerState


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AnkiState:
    """Anki SM-2 state parameters."""
    ease_factor: float
    interval_days: int
    reps: int
    lapses: int
    phase: str  # "new", "learn", "review", "relearn"
    step_index: int = 0


@dataclass(slots=True) 
class AnkiOutcome:
    """Result from Anki SM-2 review processing."""
    ease_factor: float
    interval_days: int
    phase: str
    step_index: int
    due_at: datetime
    elapsed_days: int


class AnkiSM2Scheduler:
    """Anki SM-2 algorithm implementation for imported cards."""
    
    # Default learning steps (in minutes)
    LEARNING_STEPS = [1, 10]  # 1 minute, 10 minutes
    RELEARNING_STEPS = [10]  # 10 minutes
    
    # Ease factor bounds
    MIN_EASE = 1.3
    MAX_EASE = 2.5
    INITIAL_EASE = 2.5
    
    # Interval bounds 
    MIN_INTERVAL = 1
    MAX_INTERVAL = 36500  # ~100 years
    
    def __init__(self, *, learning_steps: Optional[list[int]] = None, 
                 relearning_steps: Optional[list[int]] = None):
        self.learning_steps = learning_steps or self.LEARNING_STEPS
        self.relearning_steps = relearning_steps or self.RELEARNING_STEPS
    
    def review(
        self, 
        *, 
        state: AnkiState,
        rating: int,  # 0=Again, 1=Hard, 2=Good, 3=Easy
        last_review_at: Optional[datetime] = None,
        now: Optional[datetime] = None
    ) -> AnkiOutcome:
        """Process an Anki review and return updated scheduling."""
        
        if rating < 0 or rating > 3:
            raise ValueError("Anki rating must be between 0 and 3 inclusive")
        
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
            
        elapsed_days = 0
        if last_review_at:
            if last_review_at.tzinfo is None:
                last_review_at = last_review_at.replace(tzinfo=timezone.utc)
            elapsed_days = max(0, (now - last_review_at).days)
        
        if state.phase == "new":
            return self._handle_new_card(state, rating, now)
        elif state.phase == "learn":
            return self._handle_learning_card(state, rating, now, elapsed_days)
        elif state.phase == "review":
            return self._handle_review_card(state, rating, now, elapsed_days)
        elif state.phase == "relearn":
            return self._handle_relearning_card(state, rating, now, elapsed_days)
        else:
            # Default to new card handling
            return self._handle_new_card(state, rating, now)
    
    def _handle_new_card(self, state: AnkiState, rating: int, now: datetime) -> AnkiOutcome:
        """Handle review of a new card."""
        if rating == 0:  # Again
            return AnkiOutcome(
                ease_factor=self.INITIAL_EASE,
                interval_days=0,
                phase="learn",
                step_index=0,
                due_at=now + timedelta(minutes=self.learning_steps[0]),
                elapsed_days=0
            )
        else:
            # Good or Easy - move to learning or graduate
            if rating >= 2 and len(self.learning_steps) == 1:
                # Graduate immediately
                interval = 1 if rating == 2 else 4  # Good=1day, Easy=4days
                return AnkiOutcome(
                    ease_factor=self.INITIAL_EASE,
                    interval_days=interval,
                    phase="review",
                    step_index=0,
                    due_at=now + timedelta(days=interval),
                    elapsed_days=0
                )
            else:
                # Enter learning phase
                step_idx = 1 if rating == 1 else 0  # Hard starts at step 1
                step_idx = min(step_idx, len(self.learning_steps) - 1)
                
                return AnkiOutcome(
                    ease_factor=self.INITIAL_EASE,
                    interval_days=0,
                    phase="learn",
                    step_index=step_idx,
                    due_at=now + timedelta(minutes=self.learning_steps[step_idx]),
                    elapsed_days=0
                )
    
    def _handle_learning_card(self, state: AnkiState, rating: int, now: datetime, elapsed_days: int) -> AnkiOutcome:
        """Handle review of a learning card."""
        if rating == 0:  # Again - restart learning
            return AnkiOutcome(
                ease_factor=state.ease_factor,
                interval_days=0,
                phase="learn",
                step_index=0,
                due_at=now + timedelta(minutes=self.learning_steps[0]),
                elapsed_days=elapsed_days
            )
        
        if rating == 1:  # Hard - repeat current step
            return AnkiOutcome(
                ease_factor=state.ease_factor,
                interval_days=0,
                phase="learn",
                step_index=state.step_index,
                due_at=now + timedelta(minutes=self.learning_steps[state.step_index]),
                elapsed_days=elapsed_days
            )
        
        # Good or Easy - advance
        next_step = state.step_index + 1
        
        if next_step >= len(self.learning_steps):
            # Graduate to review
            interval = 1 if rating == 2 else 4  # Good=1day, Easy=4days  
            return AnkiOutcome(
                ease_factor=state.ease_factor,
                interval_days=interval,
                phase="review",
                step_index=0,
                due_at=now + timedelta(days=interval),
                elapsed_days=elapsed_days
            )
        else:
            # Continue learning
            return AnkiOutcome(
                ease_factor=state.ease_factor,
                interval_days=0,
                phase="learn",
                step_index=next_step,
                due_at=now + timedelta(minutes=self.learning_steps[next_step]),
                elapsed_days=elapsed_days
            )
    
    def _handle_review_card(self, state: AnkiState, rating: int, now: datetime, elapsed_days: int) -> AnkiOutcome:
        """Handle review of a mature card."""
        current_ease = state.ease_factor
        current_interval = state.interval_days
        
        if rating == 0:  # Again - enter relearning
            new_ease = max(self.MIN_EASE, current_ease - 0.2)
            return AnkiOutcome(
                ease_factor=new_ease,
                interval_days=0,
                phase="relearn",
                step_index=0,
                due_at=now + timedelta(minutes=self.relearning_steps[0]),
                elapsed_days=elapsed_days
            )
        
        # Calculate new ease factor
        if rating == 1:  # Hard
            new_ease = max(self.MIN_EASE, current_ease - 0.15)
            interval_multiplier = 1.2
        elif rating == 2:  # Good
            new_ease = current_ease  # No change
            interval_multiplier = current_ease
        else:  # Easy (rating == 3)
            new_ease = min(self.MAX_EASE, current_ease + 0.15)
            interval_multiplier = current_ease * 1.3
        
        # Calculate new interval
        if rating == 1:  # Hard - shorter interval
            new_interval = max(self.MIN_INTERVAL, int(current_interval * interval_multiplier))
        else:
            new_interval = max(self.MIN_INTERVAL, int(current_interval * interval_multiplier))
        
        new_interval = min(self.MAX_INTERVAL, new_interval)
        
        return AnkiOutcome(
            ease_factor=new_ease,
            interval_days=new_interval,
            phase="review",
            step_index=0,
            due_at=now + timedelta(days=new_interval),
            elapsed_days=elapsed_days
        )
    
    def _handle_relearning_card(self, state: AnkiState, rating: int, now: datetime, elapsed_days: int) -> AnkiOutcome:
        """Handle review of a relearning card."""
        if rating == 0:  # Again - restart relearning
            return AnkiOutcome(
                ease_factor=state.ease_factor,
                interval_days=0,
                phase="relearn",
                step_index=0,
                due_at=now + timedelta(minutes=self.relearning_steps[0]),
                elapsed_days=elapsed_days
            )
        
        # Graduate back to review with reduced interval
        base_interval = max(1, state.interval_days)
        new_interval = max(1, int(base_interval * 0.7))  # 70% of previous interval
        
        return AnkiOutcome(
            ease_factor=state.ease_factor,
            interval_days=new_interval,
            phase="review",
            step_index=0,
            due_at=now + timedelta(days=new_interval),
            elapsed_days=elapsed_days
        )


class EnhancedSRSService:
    """Enhanced SRS service supporting both FSRS and Anki SM-2 algorithms."""
    
    def __init__(self, db: Session):
        self.db = db
        self.fsrs_scheduler = FSRSScheduler()
        self.anki_scheduler = AnkiSM2Scheduler()
    
    def process_review(
        self,
        progress: UserVocabularyProgress,
        rating: int,
        response_time_ms: Optional[int] = None,
        now: Optional[datetime] = None
    ) -> None:
        """Process a vocabulary review using the appropriate scheduler."""
        
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        
        if progress.scheduler == "anki":
            self._process_anki_review(progress, rating, response_time_ms, now)
        else:
            self._process_fsrs_review(progress, rating, response_time_ms, now)
        
        # Update common fields
        progress.times_seen += 1
        if rating >= 2:  # Good or Easy
            progress.correct_count += 1
            progress.adjust_proficiency(10)
        else:
            progress.incorrect_count += 1
            progress.adjust_proficiency(-10)
    
    def _process_fsrs_review(
        self,
        progress: UserVocabularyProgress,
        rating: int,
        response_time_ms: Optional[int],
        now: datetime
    ) -> None:
        """Process review using FSRS algorithm."""
        
        # Convert to FSRS rating scale (0-3)
        fsrs_rating = min(3, max(0, rating))
        
        # Create FSRS state
        state = SchedulerState(
            stability=progress.stability or 0.0,
            difficulty=progress.difficulty or 5.0,
            reps=progress.reps or 0,
            lapses=progress.lapses or 0,
            scheduled_days=progress.scheduled_days or 1,
            state=progress.state or "new"
        )
        
        # Process review
        outcome = self.fsrs_scheduler.review(
            state=state,
            rating=fsrs_rating,
            last_review_at=progress.last_review_date,
            now=now
        )
        
        # Update progress
        progress.stability = outcome.stability
        progress.difficulty = outcome.difficulty
        progress.scheduled_days = outcome.scheduled_days
        progress.elapsed_days = outcome.elapsed_days
        progress.state = outcome.state
        progress.mark_review(now, outcome.next_review, fsrs_rating)
        
        # Create review log
        review_log = ReviewLog(
            progress_id=progress.id,
            review_date=now,
            rating=fsrs_rating,
            response_time_ms=response_time_ms,
            state_transition=f"{state.state} -> {outcome.state}",
            scheduler_type="fsrs"
        )
        review_log.set_schedule_transition(progress.scheduled_days, outcome.scheduled_days)
        
        self.db.add(review_log)
    
    def _process_anki_review(
        self,
        progress: UserVocabularyProgress,
        rating: int,
        response_time_ms: Optional[int],
        now: datetime
    ) -> None:
        """Process review using Anki SM-2 algorithm."""
        
        # Convert to Anki rating scale (0-3)
        anki_rating = min(3, max(0, rating))
        
        # Create Anki state
        state = AnkiState(
            ease_factor=progress.ease_factor or 2.5,
            interval_days=progress.interval_days or 0,
            reps=progress.reps or 0,
            lapses=progress.lapses or 0,
            phase=progress.phase or "new",
            step_index=progress.step_index or 0
        )
        
        # Process review
        outcome = self.anki_scheduler.review(
            state=state,
            rating=anki_rating,
            last_review_at=progress.last_review_date,
            now=now
        )
        
        # Update progress
        old_ease = progress.ease_factor
        old_interval = progress.interval_days
        
        progress.ease_factor = outcome.ease_factor
        progress.interval_days = outcome.interval_days
        progress.phase = outcome.phase
        progress.step_index = outcome.step_index
        progress.elapsed_days = outcome.elapsed_days
        progress.mark_anki_review(
            now, outcome.due_at, anki_rating, 
            outcome.interval_days, outcome.ease_factor, outcome.phase
        )
        
        # Create review log
        review_log = ReviewLog(
            progress_id=progress.id,
            review_date=now,
            rating=anki_rating,
            response_time_ms=response_time_ms,
            state_transition=f"{state.phase} -> {outcome.phase}",
            scheduler_type="anki"
        )
        review_log.set_anki_transition(old_ease, outcome.ease_factor, old_interval, outcome.interval_days)
        
        self.db.add(review_log)
    
    def get_due_cards(
        self, 
        user_id: str, 
        limit: int = 20,
        scheduler_type: Optional[str] = None
    ) -> list[UserVocabularyProgress]:
        """Get vocabulary cards due for review."""
        
        from sqlalchemy import select, and_, or_
        
        now = datetime.now(timezone.utc)
        
        # Base query for due cards
        query = select(UserVocabularyProgress).where(
            and_(
                UserVocabularyProgress.user_id == user_id,
                or_(
                    UserVocabularyProgress.due_at <= now,
                    UserVocabularyProgress.next_review_date <= now,
                    UserVocabularyProgress.due_date <= now.date()
                )
            )
        )
        
        # Filter by scheduler if specified
        if scheduler_type:
            query = query.where(UserVocabularyProgress.scheduler == scheduler_type)
        
        # Order by due date and limit
        query = query.order_by(
            UserVocabularyProgress.due_at.asc().nulls_last(),
            UserVocabularyProgress.next_review_date.asc().nulls_last()
        ).limit(limit)
        
        return list(self.db.scalars(query))
    
    def get_review_statistics(
        self, 
        user_id: str, 
        days: int = 30
    ) -> dict[str, Union[int, float]]:
        """Get review statistics for the user."""
        
        from sqlalchemy import select, func, and_
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Total reviews
        total_reviews = self.db.scalar(
            select(func.count()).select_from(ReviewLog)
            .join(UserVocabularyProgress)
            .where(
                and_(
                    UserVocabularyProgress.user_id == user_id,
                    ReviewLog.review_date >= cutoff_date
                )
            )
        ) or 0
        
        # Reviews by scheduler
        fsrs_reviews = self.db.scalar(
            select(func.count()).select_from(ReviewLog)
            .join(UserVocabularyProgress) 
            .where(
                and_(
                    UserVocabularyProgress.user_id == user_id,
                    ReviewLog.review_date >= cutoff_date,
                    ReviewLog.scheduler_type == "fsrs"
                )
            )
        ) or 0
        
        anki_reviews = self.db.scalar(
            select(func.count()).select_from(ReviewLog)
            .join(UserVocabularyProgress)
            .where(
                and_(
                    UserVocabularyProgress.user_id == user_id,
                    ReviewLog.review_date >= cutoff_date,
                    ReviewLog.scheduler_type == "anki"
                )
            )
        ) or 0
        
        # Average rating
        avg_rating = self.db.scalar(
            select(func.avg(ReviewLog.rating)).select_from(ReviewLog)
            .join(UserVocabularyProgress)
            .where(
                and_(
                    UserVocabularyProgress.user_id == user_id,
                    ReviewLog.review_date >= cutoff_date
                )
            )
        ) or 0.0
        
        return {
            'total_reviews': total_reviews,
            'fsrs_reviews': fsrs_reviews, 
            'anki_reviews': anki_reviews,
            'average_rating': round(avg_rating, 2),
            'period_days': days
        }