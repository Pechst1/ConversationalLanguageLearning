"""Achievements — a small, honest set tied to the story (WP-79).

Before WP-79, 19 of the 20 achievements could not be earned: they read
``total_xp`` (never written by the V2 app), a vocabulary state ``mastered``
(never written), ``LearningSession.accuracy_rate`` (never written),
``review_champion`` had no check at all, the grammar ones hung off an endpoint
no screen calls, and the seed script was never run on deploy.

The catalogue below replaces them. Every entry is measured from a row the app
really writes, and each one is reachable by a test learner
(``tests/test_wp79_achievements.py``):

=====================  =====================================================
measure                source
=====================  =====================================================
``scenes``             ``DailyJourney`` rows finished as ``completed``
``streak``             the practice streak's record (WP-80 writes it)
``letters``            Courrier letters answered (``RealWorldMission`` done)
``words``              the learner's own Lexique rows (``UserVocabularyProgress``)
``chapters``           chapters the living story closed (its chronicle)
=====================  =====================================================

No XP is awarded: nothing on screen spends or shows it, and a number that only
grows is not a reward. Retired keys stay in the table (their rows are history)
but are never listed or unlocked again.

The catalogue seeds itself: :meth:`AchievementService.ensure_catalogue` is an
idempotent upsert run before any read or check, so a fresh deploy has the set
without anyone remembering ``scripts/seed_achievements.py``.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.achievement import Achievement, UserAchievement
from app.db.models.user import User

AchievementCategory = Literal["story", "streak", "courrier", "vocabulary"]
Measure = Literal["scenes", "streak", "letters", "words", "chapters"]


@dataclass(frozen=True)
class AchievementDefinition:
    """One achievement: what it is called and what earns it."""

    key: str
    name: str
    description: str
    category: str
    tier: str
    xp_reward: int = 0
    icon_url: str | None = None
    unlock_criteria: dict[str, Any] | None = None
    #: What is counted, and how many earn it. ``None`` for a definition seeded
    #: by hand (tests); it is never unlocked automatically.
    measure: Measure | None = None
    target: int = 1


#: The one catalogue. French: the Relevé is French, and so is the story.
CATALOGUE: tuple[AchievementDefinition, ...] = (
    AchievementDefinition(
        key="first_scene",
        name="Première scène",
        description="La première journée bouclée.",
        category="story",
        tier="bronze",
        measure="scenes",
        target=1,
    ),
    AchievementDefinition(
        key="scenes_10",
        name="Dix scènes",
        description="Dix journées bouclées.",
        category="story",
        tier="silver",
        measure="scenes",
        target=10,
    ),
    AchievementDefinition(
        key="session_streak_3",
        name="Trois jours de suite",
        description="Trois jours d’affilée à l’Atelier.",
        category="streak",
        tier="bronze",
        measure="streak",
        target=3,
    ),
    AchievementDefinition(
        key="session_streak_7",
        name="Une semaine de suite",
        description="Sept jours d’affilée à l’Atelier.",
        category="streak",
        tier="silver",
        measure="streak",
        target=7,
    ),
    AchievementDefinition(
        key="session_streak_30",
        name="Trente jours de suite",
        description="Trente jours d’affilée à l’Atelier.",
        category="streak",
        tier="gold",
        measure="streak",
        target=30,
    ),
    AchievementDefinition(
        key="first_letter",
        name="Première lettre",
        description="Une première réponse au Courrier.",
        category="courrier",
        tier="bronze",
        measure="letters",
        target=1,
    ),
    AchievementDefinition(
        key="words_kept_50",
        name="Cinquante mots gardés",
        description="Cinquante mots dans votre Lexique.",
        category="vocabulary",
        tier="silver",
        measure="words",
        target=50,
    ),
    AchievementDefinition(
        key="first_chapter",
        name="Premier chapitre bouclé",
        description="Le premier chapitre du feuilleton s’est refermé.",
        category="story",
        tier="silver",
        measure="chapters",
        target=1,
    ),
)
CATALOGUE_KEYS: frozenset[str] = frozenset(item.key for item in CATALOGUE)
_BY_KEY: dict[str, AchievementDefinition] = {item.key: item for item in CATALOGUE}


@dataclass
class AchievementProgress:
    """Current progress toward an achievement."""

    achievement_id: int
    achievement_key: str
    name: str
    description: str | None
    tier: str
    xp_reward: int
    icon_url: str | None
    current_progress: int
    target_progress: int
    completed: bool
    unlocked_at: datetime | None


class AchievementNotFoundError(ValueError):
    """Raised when an achievement cannot be located."""


# ---------------------------------------------------------------------------
# Measures — each one a count of rows the app really writes
# ---------------------------------------------------------------------------


def _scenes(db: Session, user: User) -> int:
    from app.db.models.daily_journey import DailyJourney

    return int(
        db.scalar(
            select(func.count(DailyJourney.id)).where(
                DailyJourney.user_id == user.id, DailyJourney.status == "completed"
            )
        )
        or 0
    )


def _streak(db: Session, user: User) -> int:
    from app.services.streak import read_streak

    try:
        current = read_streak(user).days
    except Exception:  # pragma: no cover - a bad timezone never costs a badge
        current = 0
    return max(
        int(current or 0),
        int(getattr(user, "grammar_longest_streak", 0) or 0),
        int(getattr(user, "longest_streak", 0) or 0),
    )


def _letters(db: Session, user: User) -> int:
    from app.db.models.mission import RealWorldMission

    return int(
        db.scalar(
            select(func.count(RealWorldMission.id)).where(
                RealWorldMission.user_id == user.id, RealWorldMission.status == "completed"
            )
        )
        or 0
    )


def _words(db: Session, user: User) -> int:
    from app.db.models.progress import UserVocabularyProgress

    return int(
        db.scalar(
            select(func.count(UserVocabularyProgress.id)).where(
                UserVocabularyProgress.user_id == user.id
            )
        )
        or 0
    )


def _chapters(db: Session, user: User) -> int:
    from app.db.models.serial import SerialThread

    total = 0
    for state in db.scalars(select(SerialThread.state).where(SerialThread.user_id == user.id)):
        live = (state or {}).get("living_story") if isinstance(state, dict) else None
        chronicle = (live or {}).get("chronicle") if isinstance(live, dict) else None
        if isinstance(chronicle, list):
            total += len(chronicle)
    return total


MEASURES = {
    "scenes": _scenes,
    "streak": _streak,
    "letters": _letters,
    "words": _words,
    "chapters": _chapters,
}


class AchievementService:
    """Seed, measure and unlock the catalogue."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Catalogue
    # ------------------------------------------------------------------
    def seed_achievements(self, definitions: Iterable[AchievementDefinition]) -> None:
        """Upsert ``definitions`` and commit. Idempotent."""

        if self._upsert(definitions):
            self.db.commit()

    def ensure_catalogue(self) -> None:
        """The WP-79 catalogue is in the table — an upsert, safe on every call."""

        if self._upsert(CATALOGUE):
            self.db.commit()

    def _upsert(self, definitions: Iterable[AchievementDefinition]) -> bool:
        definitions = list(definitions)
        keys = [item.key for item in definitions]
        existing = {
            row.achievement_key: row
            for row in self.db.scalars(select(Achievement).where(Achievement.achievement_key.in_(keys)))
        }
        changed = False
        for defn in definitions:
            fields = {
                "name": defn.name,
                "description": defn.description,
                "tier": defn.tier,
                "xp_reward": defn.xp_reward,
                "icon_url": defn.icon_url,
                "category": defn.category,
                "trigger_type": defn.measure,
                "trigger_value": defn.target if defn.measure else None,
            }
            row = existing.get(defn.key)
            if row is None:
                try:
                    with self.db.begin_nested():
                        self.db.add(Achievement(achievement_key=defn.key, **fields))
                        self.db.flush()
                except IntegrityError:  # a concurrent seeder won the insert
                    pass
                changed = True
                continue
            for name, value in fields.items():
                if getattr(row, name) != value:
                    setattr(row, name, value)
                    changed = True
        return changed

    def _catalogue_rows(self) -> list[Achievement]:
        self.ensure_catalogue()
        order = {item.key: index for index, item in enumerate(CATALOGUE)}
        rows = list(
            self.db.scalars(select(Achievement).where(Achievement.achievement_key.in_(CATALOGUE_KEYS)))
        )
        return sorted(rows, key=lambda row: order.get(row.achievement_key, len(order)))

    def list_all_achievements(self) -> list[Achievement]:
        """The catalogue, in its own order. Retired keys are never listed."""

        return self._catalogue_rows()

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------
    def measures(self, user: User) -> dict[str, int]:
        return {name: fn(self.db, user) for name, fn in MEASURES.items()}

    def get_user_achievements(
        self, user_id: uuid.UUID, *, include_locked: bool = False
    ) -> list[AchievementProgress]:
        rows = self._catalogue_rows()
        unlocked = {
            ua.achievement_id: ua
            for ua in self.db.scalars(select(UserAchievement).where(UserAchievement.user_id == user_id))
        }
        user = self.db.get(User, user_id) if include_locked else None
        measured = self.measures(user) if user is not None else {}
        items: list[AchievementProgress] = []
        for row in rows:
            defn = _BY_KEY[row.achievement_key]
            held = unlocked.get(row.id)
            completed = bool(held and held.completed)
            if not completed and not include_locked:
                continue
            current = (
                int(held.progress or defn.target)
                if completed
                else min(measured.get(defn.measure or "", 0), defn.target)
            )
            items.append(
                AchievementProgress(
                    achievement_id=row.id,
                    achievement_key=row.achievement_key,
                    name=row.name,
                    description=row.description,
                    tier=row.tier,
                    xp_reward=row.xp_reward or 0,
                    icon_url=row.icon_url,
                    current_progress=current,
                    target_progress=defn.target,
                    completed=completed,
                    unlocked_at=held.unlocked_at if completed else None,
                )
            )
        return items

    # ------------------------------------------------------------------
    # Unlock
    # ------------------------------------------------------------------
    def check_and_unlock(self, *, user: User, commit: bool = True) -> list[Achievement]:
        """Unlock every catalogue entry the learner has earned. Idempotent."""

        rows = self._catalogue_rows()
        held = {
            ua.achievement_id: ua
            for ua in self.db.scalars(select(UserAchievement).where(UserAchievement.user_id == user.id))
        }
        measured = self.measures(user)
        newly: list[Achievement] = []
        now = datetime.now(UTC)
        for row in rows:
            defn = _BY_KEY[row.achievement_key]
            value = measured.get(defn.measure or "", 0)
            existing = held.get(row.id)
            if existing is not None and existing.completed:
                continue
            if defn.measure is None or value < defn.target:
                continue
            if existing is None:
                self.db.add(
                    UserAchievement(
                        user_id=user.id,
                        achievement_id=row.id,
                        progress=value,
                        completed=True,
                        unlocked_at=now,
                    )
                )
            else:
                existing.progress = value
                existing.completed = True
                existing.unlocked_at = now
            newly.append(row)
        if newly:
            if commit:
                self.db.commit()
            else:
                self.db.flush()
        return newly


def definition_for(key: str) -> AchievementDefinition:
    try:
        return _BY_KEY[key]
    except KeyError as exc:
        raise AchievementNotFoundError(key) from exc


__all__ = [
    "CATALOGUE",
    "CATALOGUE_KEYS",
    "MEASURES",
    "AchievementDefinition",
    "AchievementNotFoundError",
    "AchievementProgress",
    "AchievementService",
    "definition_for",
]
