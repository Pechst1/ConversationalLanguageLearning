"""Grammar review service with SRS scheduling."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User


# SRS Interval Logic (from Excel tracker)
# Score 9-10: +30 days
# Score 7-8:  +14 days
# Score 5-6:  +7 days
# Score 3-4:  +3 days
# Score 0-2:  +1 day

def calculate_next_review(score: float) -> timedelta:
    """Calculate the next review interval based on score (0-10)."""
    if score >= 9:
        return timedelta(days=30)
    elif score >= 7:
        return timedelta(days=14)
    elif score >= 5:
        return timedelta(days=7)
    elif score >= 3:
        return timedelta(days=3)
    else:
        return timedelta(days=1)


def determine_state(score: float, reps: int) -> str:
    """Determine the state label based on score and repetitions."""
    if reps == 0:
        return "neu"
    elif score >= 9 and reps >= 3:
        return "gemeistert"
    elif score >= 7:
        return "gefestigt"
    elif score >= 5:
        return "in_arbeit"
    else:
        return "ausbaufähig"


class GrammarService:
    """Service for grammar concept management and SRS review."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ─────────────────────────────────────────────────────────────────
    # Concept Management
    # ─────────────────────────────────────────────────────────────────

    def list_concepts(
        self,
        *,
        level: str | None = None,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GrammarConcept]:
        """List grammar concepts, optionally filtered by level or category."""
        query = self.db.query(GrammarConcept)
        if level:
            query = query.filter(GrammarConcept.level == level)
        if category:
            query = query.filter(GrammarConcept.category == category)
        query = query.order_by(GrammarConcept.level, GrammarConcept.difficulty_order)
        return list(query.offset(offset).limit(limit).all())

    def get_concept(self, concept_id: int) -> GrammarConcept | None:
        """Get a single grammar concept by ID."""
        return self.db.get(GrammarConcept, concept_id)

    def create_concept(
        self,
        *,
        name: str,
        level: str,
        category: str | None = None,
        description: str | None = None,
        examples: str | None = None,
        difficulty_order: int = 0,
    ) -> GrammarConcept:
        """Create a new grammar concept."""
        concept = GrammarConcept(
            name=name,
            level=level,
            category=category,
            description=description,
            examples=examples,
            difficulty_order=difficulty_order,
        )
        self.db.add(concept)
        self.db.commit()
        self.db.refresh(concept)
        logger.info("Created grammar concept", concept_id=concept.id, name=name)
        return concept

    def bulk_create_concepts(self, concepts: list[dict]) -> int:
        """Bulk create grammar concepts from a list of dicts."""
        created = 0
        for data in concepts:
            existing = self.db.query(GrammarConcept).filter(
                GrammarConcept.name == data.get("name"),
                GrammarConcept.level == data.get("level"),
            ).first()
            if not existing:
                concept = GrammarConcept(
                    name=data.get("name", ""),
                    level=data.get("level", "A1"),
                    category=data.get("category"),
                    description=data.get("description"),
                    examples=data.get("examples"),
                    difficulty_order=data.get("difficulty_order", 0),
                )
                self.db.add(concept)
                created += 1
        self.db.commit()
        logger.info("Bulk created grammar concepts", count=created)
        return created

    # ─────────────────────────────────────────────────────────────────
    # User Progress
    # ─────────────────────────────────────────────────────────────────

    def get_or_create_progress(
        self, *, user_id: UUID, concept_id: int
    ) -> UserGrammarProgress:
        """Get or create a user's progress for a concept."""
        progress = (
            self.db.query(UserGrammarProgress)
            .filter(
                UserGrammarProgress.user_id == user_id,
                UserGrammarProgress.concept_id == concept_id,
            )
            .first()
        )
        if not progress:
            progress = UserGrammarProgress(
                user_id=user_id,
                concept_id=concept_id,
                score=0.0,
                reps=0,
                state="neu",
            )
            self.db.add(progress)
            self.db.flush([progress])
        return progress

    def get_user_progress(
        self,
        *,
        user: User,
        level: str | None = None,
    ) -> list[UserGrammarProgress]:
        """Get all user progress, optionally filtered by level."""
        query = (
            self.db.query(UserGrammarProgress)
            .join(GrammarConcept)
            .filter(UserGrammarProgress.user_id == user.id)
        )
        if level:
            query = query.filter(GrammarConcept.level == level)
        return list(query.order_by(GrammarConcept.level, GrammarConcept.difficulty_order).all())

    def get_due_concepts(
        self,
        *,
        user: User,
        limit: int = 5,
        level: str | None = None,
    ) -> list[tuple[GrammarConcept, UserGrammarProgress | None]]:
        """Get concepts due for review, prioritizing overdue and new."""
        now = datetime.now(timezone.utc)

        # First, get concepts with progress that are due
        due_query = (
            self.db.query(GrammarConcept, UserGrammarProgress)
            .outerjoin(
                UserGrammarProgress,
                (UserGrammarProgress.concept_id == GrammarConcept.id)
                & (UserGrammarProgress.user_id == user.id),
            )
            .filter(
                (UserGrammarProgress.id.is_(None))  # New concepts
                | (UserGrammarProgress.next_review <= now)  # Due
                | (UserGrammarProgress.next_review.is_(None))  # Never reviewed
            )
            .filter(
                (UserGrammarProgress.id.is_(None))
                | (UserGrammarProgress.state != "gemeistert")
            )
        )

        if level:
            due_query = due_query.filter(GrammarConcept.level == level)

        # Order: new first, then by due date, then by score (struggling first)
        due_query = due_query.order_by(
            UserGrammarProgress.reps.asc().nullsfirst(),  # New first
            UserGrammarProgress.score.asc().nullsfirst(),  # Struggling first
            UserGrammarProgress.next_review.asc().nullsfirst(),
        )

        results = due_query.limit(limit).all()
        return [(concept, progress) for concept, progress in results]

    def record_review(
        self,
        *,
        user: User,
        concept_id: int,
        score: float,
        notes: str | None = None,
    ) -> UserGrammarProgress:
        """Record a grammar review with a 0-10 score."""
        score = max(0.0, min(10.0, score))  # Clamp to 0-10
        progress = self.get_or_create_progress(user_id=user.id, concept_id=concept_id)

        now = datetime.now(timezone.utc)
        interval = calculate_next_review(score)

        progress.score = score
        progress.reps += 1
        progress.last_review = now
        progress.next_review = now + interval
        progress.state = determine_state(score, progress.reps)
        if notes:
            progress.notes = notes
        progress.updated_at = now

        self.db.commit()
        self.db.refresh(progress)

        logger.info(
            "Recorded grammar review",
            user_id=str(user.id),
            concept_id=concept_id,
            score=score,
            next_review=progress.next_review.isoformat(),
            state=progress.state,
        )
        return progress

    # ─────────────────────────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────────────────────────

    def get_summary(self, *, user: User) -> dict:
        """Get grammar progress summary for dashboard."""
        # Total concepts
        total_concepts = self.db.query(func.count(GrammarConcept.id)).scalar() or 0

        # Progress counts by state
        state_counts = dict(
            self.db.query(UserGrammarProgress.state, func.count(UserGrammarProgress.id))
            .filter(UserGrammarProgress.user_id == user.id)
            .group_by(UserGrammarProgress.state)
            .all()
        )

        # Level breakdown
        level_counts = dict(
            self.db.query(GrammarConcept.level, func.count(GrammarConcept.id))
            .group_by(GrammarConcept.level)
            .all()
        )

        # Due today
        now = datetime.now(timezone.utc)
        due_today = (
            self.db.query(func.count(UserGrammarProgress.id))
            .filter(
                UserGrammarProgress.user_id == user.id,
                UserGrammarProgress.next_review <= now,
                UserGrammarProgress.state != "gemeistert",
            )
            .scalar()
            or 0
        )

        # New concepts (not started)
        started_ids = (
            self.db.query(UserGrammarProgress.concept_id)
            .filter(UserGrammarProgress.user_id == user.id)
            .subquery()
        )
        new_available = (
            self.db.query(func.count(GrammarConcept.id))
            .filter(~GrammarConcept.id.in_(started_ids))
            .scalar()
            or 0
        )

        return {
            "total_concepts": total_concepts,
            "started": sum(state_counts.values()),
            "due_today": due_today,
            "new_available": new_available,
            "state_counts": {
                "neu": state_counts.get("neu", 0),
                "ausbaufähig": state_counts.get("ausbaufähig", 0),
                "in_arbeit": state_counts.get("in_arbeit", 0),
                "gefestigt": state_counts.get("gefestigt", 0),
                "gemeistert": state_counts.get("gemeistert", 0),
            },
            "level_counts": level_counts,
        }

    def get_concepts_by_level(self, *, user: User) -> dict[str, list[dict]]:
        """Get concepts grouped by level with user progress."""
        concepts = self.list_concepts(limit=1000)  # Fetch all concepts
        progress_map = {
            p.concept_id: p
            for p in self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id)
            .all()
        }

        result: dict[str, list[dict]] = {}
        for concept in concepts:
            level = concept.level
            if level not in result:
                result[level] = []

            progress = progress_map.get(concept.id)
            result[level].append({
                "id": concept.id,
                "name": concept.name,
                "category": concept.category,
                "description": concept.description,
                "score": progress.score if progress else None,
                "state": progress.state if progress else "neu",
                "reps": progress.reps if progress else 0,
                "next_review": progress.next_review.isoformat() if progress and progress.next_review else None,
            })

        return result

    def get_concepts_for_user_errors(
        self,
        *,
        user: User,
        limit: int = 5,
    ) -> list[tuple[GrammarConcept, list[str]]]:
        """Get grammar concepts related to the user's most frequent errors.
        
        This creates the Error→Grammar synergy by identifying which grammar
        concepts the user should review based on their error patterns.
        
        Returns:
            List of (GrammarConcept, [error_patterns]) tuples where the 
            grammar concept matches the user's problematic error patterns.
        """
        from app.core.error_concepts import (
            ERROR_CONCEPT_REGISTRY,
            get_concept_for_pattern,
            get_concept_for_category,
        )
        from app.db.models.error import UserError
        
        # Get user's most problematic errors
        errors = (
            self.db.query(UserError)
            .filter(
                UserError.user_id == user.id,
                UserError.state != "mastered",
            )
            .order_by(
                UserError.lapses.desc(),
                UserError.occurrences.desc(),
            )
            .limit(20)  # Get more to find matching concepts
            .all()
        )
        
        if not errors:
            return []
        
        # Map errors to error concepts
        concept_errors: dict[str, list[str]] = {}  # concept_id -> [error patterns]
        
        for error in errors:
            # Try to find matching error concept
            error_concept = get_concept_for_pattern(error.error_pattern)
            if not error_concept:
                error_concept = get_concept_for_category(error.error_category)
            
            if error_concept:
                if error_concept.id not in concept_errors:
                    concept_errors[error_concept.id] = []
                if error.error_pattern:
                    concept_errors[error_concept.id].append(error.error_pattern)
        
        # Find matching GrammarConcepts in the database
        results: list[tuple[GrammarConcept, list[str]]] = []
        seen_concepts: set[int] = set()
        
        for error_concept_id, patterns in concept_errors.items():
            # Map error concept name to grammar concepts
            error_concept = ERROR_CONCEPT_REGISTRY.get(error_concept_id)
            if not error_concept:
                continue
            
            # Search for grammar concepts with matching names
            matching = (
                self.db.query(GrammarConcept)
                .filter(
                    GrammarConcept.name.ilike(f"%{error_concept.name}%")
                    | GrammarConcept.category.ilike(f"%{error_concept.name}%")
                    | GrammarConcept.name.ilike(f"%{error_concept.name_de}%")
                )
                .all()
            )
            
            for grammar_concept in matching:
                if grammar_concept.id not in seen_concepts:
                    results.append((grammar_concept, patterns))
                    seen_concepts.add(grammar_concept.id)
                    
                    if len(results) >= limit:
                        break
            
            if len(results) >= limit:
                break
        
        if results:
            logger.info(
                "Error→Grammar linking",
                user_id=str(user.id),
                linked_concepts=len(results),
                error_patterns=sum(len(p) for _, p in results),
            )
        
        return results


    # ─────────────────────────────────────────────────────────────────
    # Concept Graph & Chapter Integration
    # ─────────────────────────────────────────────────────────────────

    def get_concept_graph(
        self,
        *,
        user: User,
        level: str | None = None,
    ) -> dict:
        """
        Get the concept dependency graph for visualization.

        Returns a graph structure with nodes (concepts) and edges (prerequisites).
        Each node includes the user's mastery status.
        """
        # Get all concepts with optional level filter
        query = self.db.query(GrammarConcept)
        if level:
            query = query.filter(GrammarConcept.level == level)
        query = query.order_by(GrammarConcept.level, GrammarConcept.difficulty_order)
        concepts = query.all()

        # Get user progress for all concepts
        progress_map = {
            p.concept_id: p
            for p in self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id)
            .all()
        }

        # Build nodes
        nodes = []
        for concept in concepts:
            progress = progress_map.get(concept.id)
            prerequisites = concept.prerequisites or []

            # Check if all prerequisites are mastered (unlocked)
            is_locked = False
            if prerequisites:
                for prereq_id in prerequisites:
                    prereq_progress = progress_map.get(prereq_id)
                    if not prereq_progress or prereq_progress.state not in ["gefestigt", "gemeistert"]:
                        is_locked = True
                        break

            nodes.append({
                "id": concept.id,
                "name": concept.name,
                "level": concept.level,
                "category": concept.category,
                "description": concept.description,
                "visualization_type": concept.visualization_type,
                "prerequisites": prerequisites,
                "is_locked": is_locked,
                "state": progress.state if progress else "neu",
                "score": progress.score if progress else 0,
                "reps": progress.reps if progress else 0,
            })

        # Build edges from prerequisites
        edges = []
        for node in nodes:
            for prereq_id in node["prerequisites"]:
                edges.append({
                    "source": prereq_id,
                    "target": node["id"],
                })

        # Group by level for layout
        levels = {}
        for node in nodes:
            lvl = node["level"]
            if lvl not in levels:
                levels[lvl] = []
            levels[lvl].append(node["id"])

        return {
            "nodes": nodes,
            "edges": edges,
            "levels": levels,
        }

    def get_concepts_for_chapter(
        self,
        *,
        chapter_id: str,
        user: User | None = None,
    ) -> list[dict]:
        """
        Get grammar concepts associated with a story chapter.

        Args:
            chapter_id: The chapter ID to get concepts for
            user: Optional user to include progress info

        Returns:
            List of concept dicts with optional user progress
        """
        from app.db.models.story import Chapter

        chapter = self.db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return []

        # Get concept IDs from grammar_focus
        concept_ids = chapter.grammar_focus or []
        if not concept_ids:
            return []

        # Fetch concepts
        concepts = (
            self.db.query(GrammarConcept)
            .filter(GrammarConcept.id.in_(concept_ids))
            .all()
        )

        # Get user progress if user provided
        progress_map = {}
        if user:
            progress_list = (
                self.db.query(UserGrammarProgress)
                .filter(
                    UserGrammarProgress.user_id == user.id,
                    UserGrammarProgress.concept_id.in_(concept_ids),
                )
                .all()
            )
            progress_map = {p.concept_id: p for p in progress_list}

        result = []
        for concept in concepts:
            progress = progress_map.get(concept.id) if user else None
            result.append({
                "id": concept.id,
                "name": concept.name,
                "level": concept.level,
                "category": concept.category,
                "description": concept.description,
                "visualization_type": concept.visualization_type,
                "state": progress.state if progress else "neu",
                "score": progress.score if progress else 0,
                "reps": progress.reps if progress else 0,
                "is_due": (
                    progress.next_review is not None
                    and progress.next_review <= datetime.now(timezone.utc)
                ) if progress else True,
            })

        return result

    def mark_concepts_practiced_in_context(
        self,
        *,
        user: User,
        concept_ids: list[int],
    ) -> None:
        """
        Mark grammar concepts as practiced in story context.

        This gives a small boost to the user's progress for practicing
        grammar in an immersive context rather than isolated exercises.
        """
        now = datetime.now(timezone.utc)

        for concept_id in concept_ids:
            progress = self.get_or_create_progress(user_id=user.id, concept_id=concept_id)

            # If this is a first-time practice, give it a starting score
            if progress.reps == 0:
                progress.score = 5.0  # Middle score for context practice
                progress.reps = 1
                progress.state = determine_state(5.0, 1)
                progress.last_review = now
                progress.next_review = now + calculate_next_review(5.0)
            else:
                # Small boost for practicing in context (max +0.5)
                new_score = min(10.0, progress.score + 0.5)
                progress.score = new_score
                progress.state = determine_state(new_score, progress.reps)
                progress.last_review = now

            progress.updated_at = now

        self.db.commit()
        logger.info(
            "Marked concepts practiced in context",
            user_id=str(user.id),
            concept_ids=concept_ids,
        )


__all__ = ["GrammarService", "calculate_next_review", "determine_state"]

