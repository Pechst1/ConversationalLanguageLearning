"""Analytics service for tracking learner progress."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.progress import UserVocabularyProgress
from app.db.models.error import UserError
from app.db.models.session import LearningSession

class AnalyticsService:
    """Service for calculating and retrieving user analytics."""

    def __init__(self, db: Session):
        self.db = db

    def calculate_cefr_level(self, user_id: str) -> str:
        """Estimate CEFR level based on vocabulary size and error rates."""
        # Count active vocabulary (words with at least 1 review)
        active_vocab_count = self.db.query(func.count(UserVocabularyProgress.id)).filter(
            UserVocabularyProgress.user_id == user_id,
            UserVocabularyProgress.reps > 0
        ).scalar() or 0

        # Simple heuristic mapping
        if active_vocab_count < 500:
            return "A1"
        elif active_vocab_count < 1000:
            return "A2"
        elif active_vocab_count < 2000:
            return "B1"
        elif active_vocab_count < 4000:
            return "B2"
        elif active_vocab_count < 8000:
            return "C1"
        else:
            return "C2"

    def get_error_distribution(self, user_id: str) -> dict[str, int]:
        """Return count of errors by category."""
        rows = self.db.query(
            UserError.error_category, func.count(UserError.id)
        ).filter(
            UserError.user_id == user_id
        ).group_by(UserError.error_category).all()
        
        return {category: count for category, count in rows}

    def get_progress_summary(self, user_id: str) -> dict:
        """Return a comprehensive progress summary."""
        cefr = self.calculate_cefr_level(user_id)
        error_dist = self.get_error_distribution(user_id)
        
        total_sessions = self.db.query(func.count(LearningSession.id)).filter(
            LearningSession.user_id == user_id,
            LearningSession.status == "completed"
        ).scalar() or 0

        return {
            "cefr_level": cefr,
            "error_distribution": error_dist,
            "total_sessions": total_sessions
        }
