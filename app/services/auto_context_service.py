"""Service for generating automated context for 'Zero Decision' sessions."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.error import UserError
from app.db.models.vocabulary import VocabularyWord
from app.services.news_service import NewsService  # [NEW]
from app.services.progress import ProgressService

ConversationStyle = Literal["casual", "interviewer", "debate", "storytelling"]

@dataclass
class SessionContext:
    """Rich context payload for driving the session generation."""
    
    time_of_day: str  # e.g. "morning", "afternoon", "evening", "late_night"
    style: ConversationStyle
    greeting_focused: bool = True
    suggested_topic: str | None = None
    news_digest: str | None = None
    due_errors: list[str] = field(default_factory=list)
    due_words: list[str] = field(default_factory=list)
    
    def to_system_prompt_addition(self) -> str:
        """Convert context into a system prompt segment."""
        lines = []
        
        # Style instruction
        style_prompts = {
            "casual": "Adopt a casual, friendly persona like a close friend. Use informal language (tu) unless specified otherwise. Be chatty and warm.",
            "interviewer": "Adopt a curious, interviewer persona. Ask thoughtful questions about the user's life, opinions, and experiences. Keep the spotlight on them.",
            "debate": "Adopt a playful, slightly contrarian persona. Gently challenge the user's opinions to provoke reasoning and explanation. Keep it lighthearted/friendly.",
            "storytelling": "Adopt a storytelling persona. Start by setting a small narrative scene or asking user to contribute to a story. Be imaginative."
        }
        lines.append(f"STYLE: {style_prompts.get(self.style, style_prompts['casual'])}")
        
        # Time context
        lines.append(f"CURRENT CONTEXT: It is {self.time_of_day}. Adjust your greeting and initial small talk to fit this time.")
        
        if self.news_digest:
            lines.append(f"CURRENT EVENTS: Here is a digest of recent news relevant to the user:\n{self.news_digest}\nYou may reference these naturally if relevant.")
            
        if self.due_words or self.due_errors:
            lines.append("\nLEARNING FOCUS:")
            if self.due_words:
                words_str = ", ".join(self.due_words)
                lines.append(f"- Target Vocabulary: Incorporate these words naturally: {words_str}")
            if self.due_errors:
                errors_str = "; ".join(self.due_errors)
                lines.append(f"- Correction Focus: Help the user avoid these previous errors: {errors_str}")

        return "\n".join(lines)


class AutoContextService:
    """Orchestrates the gathering of signals for automated session context."""

    def __init__(self, db: Session):
        self.db = db
        self.news_service = NewsService()
        self.progress_service = ProgressService(db)

    async def build_auto_context(self, user: User) -> SessionContext:
        """Gather signals and build the session context."""
        
        time_context = self._get_time_of_day_context()
        style = self._get_style_rotation(user)
        
        # Fetch news if API is configured
        interests = [tag.strip() for tag in user.interests.split(",")] if user.interests else None
        news_digest = await self.news_service.fetch_news_digest(interests)
        
        # Fetch SRS Items
        # 1. Words
        queue_items = self.progress_service.get_learning_queue(user=user, limit=5)
        due_words = [item.word.word for item in queue_items]
                
        # 2. Errors (Prioritize persistent errors)
        now = datetime.now(timezone.utc)
        due_error_objs = (
            self.db.query(UserError)
            .filter(
                UserError.user_id == user.id,
                UserError.next_review_date <= now,
                UserError.state != "mastered"
            )
            .order_by(
                UserError.lapses.desc(),
                UserError.reps.desc(),
                UserError.next_review_date.asc()
            )
            .limit(3)
            .all()
        )
        due_errors = [f"{e.category} ({e.pattern})" if e.pattern else e.category for e in due_error_objs]
        
        logger.info(f"Built auto-context for user {user.id}: {time_context}, {style}, news={bool(news_digest)}, words={len(due_words)}, errors={len(due_errors)}")
        
        return SessionContext(
            time_of_day=time_context,
            style=style,
            greeting_focused=True,
            news_digest=news_digest,
            due_words=due_words,
            due_errors=due_errors,
        )

    def _get_time_of_day_context(self) -> str:
        """Return a string descriptor of the current time of day."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 22:
            return "evening"
        else:
            return "late_night"

    def _get_style_rotation(self, user: User) -> ConversationStyle:
        """
        Determine the conversation style based on history/rotation.
        For now, random selection to ensure variety.
        In future: check last session style and rotate.
        """
        styles: list[ConversationStyle] = ["casual", "interviewer", "debate", "storytelling"]
        # Basic weighted choice: Casual is most common
        weights = [0.4, 0.3, 0.15, 0.15]
        
        return random.choices(styles, weights=weights, k=1)[0]
