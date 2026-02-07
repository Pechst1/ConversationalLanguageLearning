"""Insights service for AI-powered learning recommendations."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.services.analytics import AnalyticsService
from app.services.grammar import GrammarService
from app.services.llm_service import LLMService, LLMResult
from app.utils.cache import cache_backend

if TYPE_CHECKING:
    pass


@dataclass
class LearningInsight:
    """AI-generated learning insight for a user."""
    
    generated_at: datetime
    period_days: int
    
    # Summary of progress
    headline: str
    progress_summary: str
    
    # Strengths and areas for improvement
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    
    # Specific recommendations
    recommendations: list[dict] = field(default_factory=list)
    # Structure: {type: "grammar"|"vocabulary"|"practice", title: str, description: str}
    
    # Encouragement/motivation
    encouragement: str = ""
    
    # Raw LLM response for debugging
    llm_result: LLMResult | None = None


INSIGHT_SYSTEM_PROMPT = """You are a supportive French language learning coach. Your role is to analyze the learner's progress data and provide encouraging, specific, and actionable insights.

Guidelines:
- Be warm, encouraging, and specific
- Acknowledge both achievements and areas to improve
- Give 2-3 concrete recommendations they can act on this week
- Reference specific numbers from their data where helpful
- Keep recommendations focused and practical
- Use a conversational, supportive tone

Respond in this exact JSON format:
{
    "headline": "A short, encouraging headline about their progress (max 10 words)",
    "progress_summary": "2-3 sentences summarizing their learning journey this period",
    "strengths": ["strength 1", "strength 2"],
    "improvements": ["area to improve 1", "area to improve 2"],
    "recommendations": [
        {"type": "grammar", "title": "Short title", "description": "Specific actionable step"},
        {"type": "vocabulary", "title": "Short title", "description": "Specific actionable step"},
        {"type": "practice", "title": "Short title", "description": "Specific actionable step"}
    ],
    "encouragement": "A motivating closing message (1-2 sentences)"
}"""


class InsightsService:
    """Generate AI-powered learning insights and recommendations."""
    
    CACHE_TTL_SECONDS = 86400  # 24 hours
    
    def __init__(
        self,
        db: Session,
        *,
        analytics_service: AnalyticsService | None = None,
        grammar_service: GrammarService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.db = db
        self.analytics_service = analytics_service or AnalyticsService(db)
        self.grammar_service = grammar_service or GrammarService(db)
        self.llm_service = llm_service or LLMService()
    
    def generate_weekly_insight(
        self,
        *,
        user: User,
        force_refresh: bool = False,
    ) -> LearningInsight:
        """Generate or retrieve cached weekly learning insight.
        
        This is the main API for the Progress Insights AI feature.
        It collects analytics data and uses the LLM to generate
        personalized recommendations.
        """
        cache_key = f"{user.id}:weekly"
        
        # Check cache unless force refresh
        if not force_refresh:
            cached = cache_backend.get("insights:weekly", cache_key)
            if cached:
                logger.debug("Returning cached insight", user_id=str(user.id))
                return self._deserialize_insight(cached)
        
        # Gather analytics data
        analytics_data = self._gather_analytics_data(user, days=7)
        
        # Generate insight using LLM
        insight = self._generate_insight_with_llm(user, analytics_data, period_days=7)
        
        # Cache the result
        cache_backend.set(
            "insights:weekly",
            cache_key,
            self._serialize_insight(insight),
            ttl_seconds=self.CACHE_TTL_SECONDS,
        )
        
        logger.info(
            "Generated weekly insight",
            user_id=str(user.id),
            headline=insight.headline[:50],
        )
        
        return insight
    
    def _gather_analytics_data(self, user: User, days: int = 7) -> dict:
        """Collect all relevant analytics for insight generation."""
        
        # Get summary metrics
        summary = self.analytics_service.get_user_summary(user=user, days=days)
        
        # Get statistics
        stats = self.analytics_service.get_statistics(user=user, days=days)
        
        # Get streak info
        streak = self.analytics_service.get_streak_info(user=user, window_days=90)
        
        # Get error patterns
        error_patterns = self.analytics_service.get_error_patterns(user=user, limit=5)
        
        # Get grammar summary
        grammar_summary = self.grammar_service.get_summary(user=user)
        
        # Get error→grammar links for targeted recommendations
        error_grammar_links = self.grammar_service.get_concepts_for_user_errors(user=user, limit=3)
        
        return {
            "period_days": days,
            "summary": summary,
            "statistics": stats,
            "streak": streak,
            "error_patterns": error_patterns,
            "grammar": grammar_summary,
            "error_grammar_links": [
                {"concept": c.name, "level": c.level, "patterns": p}
                for c, p in error_grammar_links
            ],
            "user_level": user.proficiency_level or "B1",
            "user_name": user.display_name or "Learner",
        }
    
    def _generate_insight_with_llm(
        self,
        user: User,
        analytics_data: dict,
        period_days: int,
    ) -> LearningInsight:
        """Use LLM to generate personalized insight from analytics."""
        
        # Build the data summary for LLM
        data_prompt = self._format_analytics_for_llm(analytics_data)
        
        messages = [
            {"role": "user", "content": data_prompt},
        ]
        
        try:
            result = self.llm_service.generate_chat_completion(
                messages,
                temperature=0.7,
                max_tokens=800,
                system_prompt=INSIGHT_SYSTEM_PROMPT,
            )
            
            # Parse JSON response
            insight_data = self._parse_llm_response(result.content)
            
            return LearningInsight(
                generated_at=datetime.now(timezone.utc),
                period_days=period_days,
                headline=insight_data.get("headline", "Keep up the great work!"),
                progress_summary=insight_data.get("progress_summary", ""),
                strengths=insight_data.get("strengths", []),
                improvements=insight_data.get("improvements", []),
                recommendations=insight_data.get("recommendations", []),
                encouragement=insight_data.get("encouragement", ""),
                llm_result=result,
            )
            
        except Exception as exc:
            logger.error("Failed to generate insight", error=str(exc), user_id=str(user.id))
            
            # Return a fallback insight
            return self._generate_fallback_insight(analytics_data, period_days)
    
    def _format_analytics_for_llm(self, data: dict) -> str:
        """Format analytics data into a prompt for the LLM."""
        
        summary = data.get("summary", {})
        stats = data.get("statistics", {})
        streak = data.get("streak", {})
        errors = data.get("error_patterns", [])
        grammar = data.get("grammar", {})
        links = data.get("error_grammar_links", [])
        
        lines = [
            f"## Learning Analytics for {data.get('user_name', 'Learner')} (Level: {data.get('user_level', 'B1')})",
            f"Period: Last {data.get('period_days', 7)} days",
            "",
            "### Activity",
            f"- Sessions completed: {summary.get('total_sessions', 0)}",
            f"- Total practice time: {summary.get('total_minutes', 0)} minutes",
            f"- Current streak: {streak.get('current', 0)} days",
            f"- Longest streak: {streak.get('longest', 0)} days",
            "",
            "### Vocabulary",
            f"- Words mastered: {summary.get('words_mastered', 0)}",
            f"- Words learning: {summary.get('words_learning', 0)}",
            f"- Review accuracy: {stats.get('review_accuracy', 0):.0%}" if stats.get('review_accuracy') else "- Review accuracy: N/A",
            "",
            "### Grammar",
            f"- Concepts started: {grammar.get('started', 0)}/{grammar.get('total_concepts', 0)}",
            f"- Concepts mastered: {grammar.get('state_counts', {}).get('gemeistert', 0)}",
            f"- Due for review: {grammar.get('due_today', 0)}",
            "",
            "### Common Mistakes",
        ]
        
        if errors:
            for err in errors[:5]:
                lines.append(f"- {err.get('category', 'Unknown')}: {err.get('count', 0)} occurrences")
        else:
            lines.append("- No significant error patterns detected")
        
        if links:
            lines.append("")
            lines.append("### Grammar Areas Related to Mistakes")
            for link in links:
                lines.append(f"- {link.get('concept', '')} ({link.get('level', '')})")
        
        lines.append("")
        lines.append("Based on this data, provide personalized learning insights and recommendations.")
        
        return "\n".join(lines)
    
    def _parse_llm_response(self, content: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        
        # Strip markdown code blocks if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (code block markers)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM JSON response", error=str(e))
            return {}
    
    def _generate_fallback_insight(self, data: dict, period_days: int) -> LearningInsight:
        """Generate a basic insight when LLM fails."""
        
        summary = data.get("summary", {})
        streak = data.get("streak", {})
        
        return LearningInsight(
            generated_at=datetime.now(timezone.utc),
            period_days=period_days,
            headline="Keep Learning Every Day!",
            progress_summary=f"Over the past {period_days} days, you've completed {summary.get('total_sessions', 0)} sessions and practiced for {summary.get('total_minutes', 0)} minutes. Great effort!",
            strengths=["Consistent practice sessions"],
            improvements=["Review vocabulary more frequently"],
            recommendations=[
                {
                    "type": "practice",
                    "title": "Daily 10-minute sessions",
                    "description": "Try to practice for at least 10 minutes every day to maintain your streak.",
                }
            ],
            encouragement=f"You're on a {streak.get('current', 0)}-day streak! Keep it up!",
            llm_result=None,
        )
    
    def _serialize_insight(self, insight: LearningInsight) -> dict:
        """Serialize insight for caching."""
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
    
    def _deserialize_insight(self, data: dict) -> LearningInsight:
        """Deserialize insight from cache."""
        return LearningInsight(
            generated_at=datetime.fromisoformat(data["generated_at"]),
            period_days=data["period_days"],
            headline=data["headline"],
            progress_summary=data["progress_summary"],
            strengths=data.get("strengths", []),
            improvements=data.get("improvements", []),
            recommendations=data.get("recommendations", []),
            encouragement=data.get("encouragement", ""),
            llm_result=None,
        )


__all__ = ["InsightsService", "LearningInsight"]
