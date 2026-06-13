"""Deterministic CEFR estimate and forecast service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierAttempt
from app.db.models.cefr import UserCEFRProgressHistory
from app.db.models.error import UserError
from app.db.models.graphic_novel import GraphicNovelAttempt
from app.db.models.grammar import UserGrammarProgress
from app.db.models.mission import RealWorldMissionAttempt
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User


CEFR_PROGRESS_VERSION = "cefr-progress-v1"
CEFR_LEVELS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2")

CEFR_THRESHOLDS: dict[str, dict[str, float]] = {
    "A1.1": {"vocabulary": 0, "grammar": 0, "avg_score": 0.0, "max_error_rate": 1.0},
    "A1.2": {"vocabulary": 300, "grammar": 20, "avg_score": 2.6, "max_error_rate": 0.42},
    "A2.1": {"vocabulary": 700, "grammar": 45, "avg_score": 2.8, "max_error_rate": 0.38},
    "A2.2": {"vocabulary": 1200, "grammar": 75, "avg_score": 3.0, "max_error_rate": 0.34},
    "B1.1": {"vocabulary": 2000, "grammar": 110, "avg_score": 3.1, "max_error_rate": 0.3},
    "B1.2": {"vocabulary": 2800, "grammar": 150, "avg_score": 3.2, "max_error_rate": 0.26},
    "B2.1": {"vocabulary": 3800, "grammar": 210, "avg_score": 3.3, "max_error_rate": 0.22},
    "B2.2": {"vocabulary": 5000, "grammar": 280, "avg_score": 3.4, "max_error_rate": 0.18},
}


@dataclass(frozen=True)
class CEFRSignals:
    mastered_vocabulary: int
    mastered_grammar: int
    recent_error_count: int
    recent_attempt_count: int
    recent_error_rate: float
    recent_average_score: float
    active_days_14: int
    words_mastered_14: int
    concepts_mastered_14: int
    today_words_active: int
    today_concepts_active: int
    today_attempts: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "mastered_vocabulary": self.mastered_vocabulary,
            "mastered_grammar": self.mastered_grammar,
            "recent_error_count": self.recent_error_count,
            "recent_attempt_count": self.recent_attempt_count,
            "recent_error_rate": self.recent_error_rate,
            "recent_average_score": self.recent_average_score,
            "active_days_14": self.active_days_14,
            "words_mastered_14": self.words_mastered_14,
            "concepts_mastered_14": self.concepts_mastered_14,
            "today_words_active": self.today_words_active,
            "today_concepts_active": self.today_concepts_active,
            "today_attempts": self.today_attempts,
        }


def level_index(level: str | None) -> int:
    try:
        return CEFR_LEVELS.index(str(level or "A1.1"))
    except ValueError:
        return 0


def next_cefr_level(level: str | None) -> str | None:
    index = level_index(level)
    return CEFR_LEVELS[index + 1] if index + 1 < len(CEFR_LEVELS) else None


class CEFRProgressService:
    """Compute, smooth, persist, and serialize CEFR estimates."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def recompute(self, user: User, *, source: str = "recompute", persist: bool = True) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        signals = self._signals(user=user, now=now)
        computed_level = self._computed_level(signals)
        estimate_level = self._smooth_level(user=user, computed_level=computed_level)
        target_level = self._target_level(user=user, estimate_level=estimate_level)
        payload = self._payload(
            user=user,
            signals=signals,
            computed_level=computed_level,
            estimate_level=estimate_level,
            target_level=target_level,
            now=now,
        )
        if persist:
            user.cefr_estimate = estimate_level
            user.cefr_estimate_payload = payload
            self.db.add(user)
            self.db.add(
                UserCEFRProgressHistory(
                    user_id=user.id,
                    estimate_level=estimate_level,
                    source=source,
                    signal_snapshot=signals.as_dict(),
                    payload={**payload, "computed_level": computed_level},
                )
            )
            self.db.commit()
            self.db.refresh(user)
        return payload

    def current(self, user: User, *, recompute_if_missing: bool = True) -> dict[str, Any]:
        payload = user.cefr_estimate_payload if isinstance(getattr(user, "cefr_estimate_payload", None), dict) else {}
        if payload and payload.get("version") == CEFR_PROGRESS_VERSION:
            return payload
        if recompute_if_missing:
            return self.recompute(user, source="lazy")
        estimate = str(getattr(user, "cefr_estimate", None) or "A1.1")
        target = self._target_level(user=user, estimate_level=estimate)
        return {
            "version": CEFR_PROGRESS_VERSION,
            "estimate": estimate,
            "computed_estimate": estimate,
            "target": target,
            "next_level": next_cefr_level(estimate),
            "signals": {},
            "thresholds": CEFR_THRESHOLDS,
            "forecast": None,
            "today_delta": {"words_active": 0, "concepts_active": 0, "attempts": 0},
        }

    def _signals(self, *, user: User, now: datetime) -> CEFRSignals:
        start_14 = now - timedelta(days=14)
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        mastered_vocabulary = int(
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(UserVocabularyProgress.user_id == user.id)
            .filter(
                or_(
                    UserVocabularyProgress.mastered_date.isnot(None),
                    UserVocabularyProgress.proficiency_score >= 90,
                    UserVocabularyProgress.state == "mastered",
                )
            )
            .scalar()
            or 0
        )
        mastered_grammar = int(
            self.db.query(func.count(UserGrammarProgress.id))
            .filter(UserGrammarProgress.user_id == user.id)
            .filter(or_(UserGrammarProgress.state == "gemeistert", UserGrammarProgress.score >= 8))
            .scalar()
            or 0
        )
        recent_error_count = int(
            self.db.query(func.count(UserError.id))
            .filter(UserError.user_id == user.id, UserError.created_at >= start_14)
            .scalar()
            or 0
        )
        recent_scores = self._recent_scores(user=user, start=start_14)
        recent_attempt_count = len(recent_scores)
        recent_average_score = round(sum(recent_scores) / recent_attempt_count, 3) if recent_scores else 0.0
        denominator = max(recent_attempt_count + recent_error_count, 1)
        recent_error_rate = round(recent_error_count / denominator, 3)
        active_days = set(self._active_days(user=user, start=start_14))
        words_mastered_14 = int(
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.mastered_date >= start_14)
            .scalar()
            or 0
        )
        concepts_mastered_14 = int(
            self.db.query(func.count(UserGrammarProgress.id))
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.updated_at >= start_14)
            .filter(or_(UserGrammarProgress.state == "gemeistert", UserGrammarProgress.score >= 8))
            .scalar()
            or 0
        )
        today_words_active = int(
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.updated_at >= start_today)
            .scalar()
            or 0
        )
        today_concepts_active = int(
            self.db.query(func.count(UserGrammarProgress.id))
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.updated_at >= start_today)
            .scalar()
            or 0
        )
        today_attempts = 0
        for model in (AtelierAttempt, RealWorldMissionAttempt, GraphicNovelAttempt):
            today_attempts += int(
                self.db.query(func.count(model.id))
                .filter(model.user_id == user.id, model.created_at >= start_today)
                .scalar()
                or 0
            )
        return CEFRSignals(
            mastered_vocabulary=mastered_vocabulary,
            mastered_grammar=mastered_grammar,
            recent_error_count=recent_error_count,
            recent_attempt_count=recent_attempt_count,
            recent_error_rate=recent_error_rate,
            recent_average_score=recent_average_score,
            active_days_14=len(active_days),
            words_mastered_14=words_mastered_14,
            concepts_mastered_14=concepts_mastered_14,
            today_words_active=today_words_active,
            today_concepts_active=today_concepts_active,
            today_attempts=today_attempts,
        )

    def _recent_scores(self, *, user: User, start: datetime) -> list[float]:
        scores: list[float] = []
        for model in (AtelierAttempt, RealWorldMissionAttempt, GraphicNovelAttempt):
            rows = (
                self.db.query(model.score_0_4)
                .filter(model.user_id == user.id, model.created_at >= start)
                .all()
            )
            scores.extend(float(row[0] or 0.0) for row in rows)
        return scores

    def _active_days(self, *, user: User, start: datetime) -> list[str]:
        days: set[str] = set()
        for model in (AtelierAttempt, RealWorldMissionAttempt, GraphicNovelAttempt):
            rows = self.db.query(model.created_at).filter(model.user_id == user.id, model.created_at >= start).all()
            for row in rows:
                created = row[0]
                if created:
                    days.add(created.date().isoformat())
        return sorted(days)

    def _computed_level(self, signals: CEFRSignals) -> str:
        estimate = "A1.1"
        for level in CEFR_LEVELS:
            threshold = CEFR_THRESHOLDS[level]
            if (
                signals.mastered_vocabulary >= threshold["vocabulary"]
                and signals.mastered_grammar >= threshold["grammar"]
                and signals.recent_average_score >= threshold["avg_score"]
                and signals.recent_error_rate <= threshold["max_error_rate"]
            ):
                estimate = level
        return estimate

    def _smooth_level(self, *, user: User, computed_level: str) -> str:
        previous = str(getattr(user, "cefr_estimate", None) or "A1.1")
        if level_index(computed_level) >= level_index(previous):
            return computed_level
        recent = (
            self.db.query(UserCEFRProgressHistory)
            .filter(UserCEFRProgressHistory.user_id == user.id)
            .order_by(UserCEFRProgressHistory.created_at.desc())
            .limit(3)
            .all()
        )
        recent_computed = [
            str((row.payload or {}).get("computed_level") or row.estimate_level)
            for row in recent
            if isinstance(row.payload, dict) or row.estimate_level
        ]
        if len(recent_computed) >= 3 and all(level_index(level) < level_index(previous) for level in recent_computed):
            return computed_level
        return previous

    @staticmethod
    def _target_level(*, user: User, estimate_level: str) -> str:
        raw = str(getattr(user, "cefr_target_level", None) or "").strip().upper()
        if raw in CEFR_LEVELS and level_index(raw) > level_index(estimate_level):
            return raw
        return next_cefr_level(estimate_level) or estimate_level

    def _payload(
        self,
        *,
        user: User,
        signals: CEFRSignals,
        computed_level: str,
        estimate_level: str,
        target_level: str,
        now: datetime,
    ) -> dict[str, Any]:
        forecast = self._forecast(signals=signals, estimate_level=estimate_level, target_level=target_level, now=now)
        return {
            "version": CEFR_PROGRESS_VERSION,
            "estimate": estimate_level,
            "computed_estimate": computed_level,
            "target": target_level,
            "next_level": next_cefr_level(estimate_level),
            "daily_minutes": int(getattr(user, "daily_goal_minutes", None) or 20),
            "signals": signals.as_dict(),
            "thresholds": CEFR_THRESHOLDS,
            "breakdown": self._breakdown(signals=signals, target_level=target_level),
            "forecast": forecast,
            "today_delta": {
                "words_active": signals.today_words_active,
                "concepts_active": signals.today_concepts_active,
                "attempts": signals.today_attempts,
            },
            "generated_at": now.isoformat(),
        }

    @staticmethod
    def _breakdown(*, signals: CEFRSignals, target_level: str) -> dict[str, Any]:
        threshold = CEFR_THRESHOLDS.get(target_level, CEFR_THRESHOLDS["A1.2"])
        return {
            "vocabulary": {
                "current": signals.mastered_vocabulary,
                "target": int(threshold["vocabulary"]),
            },
            "grammar": {
                "current": signals.mastered_grammar,
                "target": int(threshold["grammar"]),
            },
            "score": {
                "current": signals.recent_average_score,
                "target": threshold["avg_score"],
            },
            "error_rate": {
                "current": signals.recent_error_rate,
                "target": threshold["max_error_rate"],
            },
        }

    @staticmethod
    def _forecast(*, signals: CEFRSignals, estimate_level: str, target_level: str, now: datetime) -> dict[str, Any] | None:
        if not target_level or target_level == estimate_level:
            return None
        if signals.active_days_14 < 7:
            return {
                "status": "insufficient_data",
                "message": "Come back after 7 active days for a forecast.",
                "active_days_14": signals.active_days_14,
            }
        threshold = CEFR_THRESHOLDS[target_level]
        words_gap = max(0.0, threshold["vocabulary"] - signals.mastered_vocabulary)
        grammar_gap = max(0.0, threshold["grammar"] - signals.mastered_grammar)
        words_per_day = signals.words_mastered_14 / 14.0
        concepts_per_day = signals.concepts_mastered_14 / 14.0
        if (words_gap and words_per_day <= 0) or (grammar_gap and concepts_per_day <= 0):
            return {
                "status": "too_slow",
                "message": "A forecast needs a steadier recent pace.",
                "active_days_14": signals.active_days_14,
            }
        days = 0.0
        if words_gap:
            days = max(days, words_gap / max(words_per_day, 0.01))
        if grammar_gap:
            days = max(days, grammar_gap / max(concepts_per_day, 0.01))
        days = min(365.0, max(1.0, days))
        low_days = int(max(1, round(days * 0.85)))
        high_days = int(max(low_days, round(days * 1.25)))
        projected = now + timedelta(days=round(days))
        return {
            "status": "available",
            "target": target_level,
            "projected_date": projected.date().isoformat(),
            "range_days": [low_days, high_days],
            "pace": {
                "words_per_day": round(words_per_day, 2),
                "concepts_per_day": round(concepts_per_day, 2),
            },
        }


__all__ = [
    "CEFR_LEVELS",
    "CEFR_PROGRESS_VERSION",
    "CEFR_THRESHOLDS",
    "CEFRProgressService",
    "next_cefr_level",
]
