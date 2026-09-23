"""WP-L4 — a grammar concept's life: intake, introduction, and «Tenue».

WORK-PACKAGES-2026-09-23-learning §2.4. One unit's stages, as this module
stores and reads them on the learner's progress row:

* **Rencontre / Règle** — the day the journey introduces the unit
  (``introduced_at``). The intake plan (:func:`introduction_for_today`) picks
  it from the learner's rhythm quota (§2.2: Léger 1, Régulier 2, Soutenu 3,
  Intensif 4 new concepts a week), through the Atelier's one new-concept
  picker (:meth:`AtelierScheduler.next_new_concepts`: band, teaching order,
  prerequisites).
* **Essai / Emploi / Rappel / Réemploi** — evidence through the one memory
  model (``apply_grammar_evidence``), which calls :func:`note_concept_evidence`
  for every observation, so the life is kept whichever surface saw it.
* **Tenue** — *held* is correct free use on two separate days at least seven
  days apart, plus one correct spaced item (a Rappel format, not a reply) at
  least fourteen days after the introduction. ``held_at`` is written the first
  time that is true and never cleared: demotion stays invisible (WP-L7), a
  fragile held concept simply comes back through the scheduler.

WP-L7 reads :func:`concept_stage`, :func:`held_concept_ids` and
:func:`introduced_concept_ids`.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.srs.memory import Evidence, EvidenceFormat, grade_evidence
from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization, UserGrammarProgress

#: §2.2 — new grammar units a week, per rhythm.
NEW_CONCEPTS_PER_WEEK: dict[str, int] = {
    "leger": 1,
    "regulier": 2,
    "soutenu": 3,
    "intensif": 4,
}
#: Held needs two correct free uses at least this many days apart…
HELD_FREE_USE_GAP_DAYS = 7
#: …and one correct spaced item at least this many days after the introduction.
HELD_SPACED_AFTER_DAYS = 14
#: The intake window: a rolling week.
INTAKE_WINDOW_DAYS = 7

#: The formats a *spaced item* is posed in (the Rappel's), as opposed to a reply.
SPACED_ITEM_FORMATS = frozenset(
    {EvidenceFormat.RECOGNISE, EvidenceFormat.GUIDED, EvidenceFormat.TRANSFORM, EvidenceFormat.RATED}
)

STAGE_NEW = "new"
STAGE_INTRODUCED = "introduced"
STAGE_PRACTISING = "practising"
STAGE_HELD = "held"


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# The life, written with every observation
# ---------------------------------------------------------------------------


def is_free_use(evidence: Evidence) -> bool:
    """A correct, unassisted use of the form in the learner's own reply."""

    return (
        evidence.format is EvidenceFormat.PRODUCE
        and bool(evidence.correct)
        and not evidence.assisted
    )


def held_conditions(progress: Any) -> tuple[bool, bool]:
    """``(free use on two days ≥ 7 apart, a correct spaced item ≥ 14 days in)``."""

    first = _aware(getattr(progress, "free_use_first_at", None))
    last = _aware(getattr(progress, "free_use_last_at", None))
    free_use = bool(
        first and last and (last.date() - first.date()).days >= HELD_FREE_USE_GAP_DAYS
    )
    spaced = getattr(progress, "spaced_success_at", None) is not None
    return free_use, spaced


def is_held(progress: Any) -> bool:
    return getattr(progress, "held_at", None) is not None or all(held_conditions(progress))


def note_concept_evidence(progress: Any, evidence: Evidence, *, now: datetime) -> None:
    """Keep the concept's life up to date with one observation. Never commits.

    Called by ``apply_grammar_evidence`` for every observation it schedules,
    and by the journey for a same-day success it folds (the schedule moves
    once a day; the life still sees every use).
    """

    now = _aware(now) or datetime.now(UTC)
    grade = grade_evidence(evidence)
    if getattr(progress, "introduced_at", None) is None:
        # First evidence on any surface introduces the unit. A row that
        # already has history started when it was created.
        created = _aware(getattr(progress, "created_at", None))
        history = int(getattr(progress, "reps", 0) or 0) > 1
        progress.introduced_at = created if history and created and created < now else now
    if grade is None or not grade.is_success:
        return
    if is_free_use(evidence):
        if getattr(progress, "free_use_first_at", None) is None:
            progress.free_use_first_at = now
        progress.free_use_last_at = now
    elif evidence.format in SPACED_ITEM_FORMATS:
        introduced = _aware(progress.introduced_at)
        if introduced is not None and now - introduced >= timedelta(days=HELD_SPACED_AFTER_DAYS):
            progress.spaced_success_at = now
    if getattr(progress, "held_at", None) is None and all(held_conditions(progress)):
        progress.held_at = now


def concept_stage(progress: Any | None) -> str:
    """``new`` · ``introduced`` (met, not yet practised) · ``practising`` · ``held``."""

    if progress is None:
        return STAGE_NEW
    if is_held(progress):
        return STAGE_HELD
    if int(getattr(progress, "reps", 0) or 0) > 0:
        return STAGE_PRACTISING
    if getattr(progress, "introduced_at", None) is not None:
        return STAGE_INTRODUCED
    return STAGE_NEW


def held_concept_ids(db: Session, user_id: UUID) -> set[int]:
    """The units this learner holds (WP-L7's coverage numerator)."""

    return {
        concept_id
        for (concept_id,) in db.query(UserGrammarProgress.concept_id)
        .filter(UserGrammarProgress.user_id == user_id, UserGrammarProgress.held_at.isnot(None))
        .all()
    }


def introduced_concept_ids(db: Session, user_id: UUID) -> set[int]:
    return {
        concept_id
        for (concept_id,) in db.query(UserGrammarProgress.concept_id)
        .filter(UserGrammarProgress.user_id == user_id, UserGrammarProgress.introduced_at.isnot(None))
        .all()
    }


def mark_introduced(db: Session, *, user: Any, concept_id: int, now: datetime | None = None) -> UserGrammarProgress | None:
    """The Règle was read: the unit is introduced (no schedule change)."""

    concept = db.get(GrammarConcept, int(concept_id))
    if concept is None:
        return None
    from app.services.grammar import GrammarService

    progress = GrammarService(db).get_or_create_progress(user_id=user.id, concept_id=concept.id)
    if progress.introduced_at is None:
        progress.introduced_at = now or datetime.now(UTC)
        db.add(progress)
        db.flush([progress])
    return progress


# ---------------------------------------------------------------------------
# The intake plan
# ---------------------------------------------------------------------------


def weekly_concept_quota(db: Session, user: Any, *, now: datetime) -> int:
    """New units this learner takes in a week: the rhythm's, throttled (§2.2)."""

    from app.services.journey_rhythm import rhythm_of
    from app.services.vocabulary_pace import intake_throttle_factor

    base = NEW_CONCEPTS_PER_WEEK.get(rhythm_of(user), NEW_CONCEPTS_PER_WEEK["regulier"])
    try:
        factor = float(intake_throttle_factor(db, user, now=now))
    except Exception:  # pragma: no cover - the throttle is a hook
        factor = 1.0
    return max(0, int(base * max(0.0, min(1.0, factor))))


def introductions_in_window(db: Session, user: Any, *, now: datetime) -> list[datetime]:
    since = now - timedelta(days=INTAKE_WINDOW_DAYS)
    rows = (
        db.query(UserGrammarProgress.introduced_at)
        .filter(
            UserGrammarProgress.user_id == user.id,
            UserGrammarProgress.introduced_at.isnot(None),
        )
        .all()
    )
    return sorted(
        stamp
        for (value,) in rows
        if (stamp := _aware(value)) is not None and since < stamp <= now + timedelta(minutes=1)
    )


def introduction_due(db: Session, user: Any, *, now: datetime) -> bool:
    """May today introduce a new unit? The rhythm's weekly quota, spread out.

    Régulier's two a week are at least three days apart (7 // quota), so a
    week is not two new rules on Monday and Tuesday and none after.
    """

    now = _aware(now) or datetime.now(UTC)
    quota = weekly_concept_quota(db, user, now=now)
    if quota <= 0:
        return False
    recent = introductions_in_window(db, user, now=now)
    if len(recent) >= quota:
        return False
    if recent:
        spacing = max(1, INTAKE_WINDOW_DAYS // quota)
        if (now.date() - recent[-1].date()).days < spacing:
            return False
    return True


def _localizations(db: Session, concept_id: int) -> dict[str, str]:
    return {
        str(row.locale): str(row.title)
        for row in db.query(GrammarConceptLocalization)
        .filter(GrammarConceptLocalization.concept_id == concept_id)
        .all()
        if row.title
    }


def concept_brief(
    db: Session,
    concept: GrammarConcept,
    *,
    control_language: str,
    stability: float | None = None,
) -> dict[str, Any]:
    """The planner's JSON-safe view of one unit (:func:`grammar_units.unit_brief`)."""

    from app.services.grammar_units import unit_brief

    return unit_brief(
        concept,
        control_language=control_language,
        localizations=_localizations(db, concept.id),
        stability=stability,
    )


def introduction_for_today(
    db: Session,
    user: Any,
    *,
    now: datetime | None = None,
    control_language: str = "en",
) -> dict[str, Any] | None:
    """Today's new unit as a brief, or ``None`` (quota spent, nothing ready).

    Read-only: the unit is *introduced* only when the learner reads its rule
    (:func:`mark_introduced`), so a day that is planned and abandoned offers
    the same unit again tomorrow.
    """

    now = _aware(now) or datetime.now(UTC)
    if not introduction_due(db, user, now=now):
        return None
    from app.services.atelier import AtelierScheduler

    language = str(getattr(user, "target_language", None) or "fr")
    picked = AtelierScheduler(db).next_new_concepts(user, limit=1, language=language)
    if not picked:
        return None
    brief = concept_brief(db, picked[0], control_language=control_language)
    if not brief.get("rule_card") or not brief.get("examples"):
        return None
    return brief


__all__ = [
    "HELD_FREE_USE_GAP_DAYS",
    "HELD_SPACED_AFTER_DAYS",
    "NEW_CONCEPTS_PER_WEEK",
    "STAGE_HELD",
    "STAGE_INTRODUCED",
    "STAGE_NEW",
    "STAGE_PRACTISING",
    "concept_brief",
    "concept_stage",
    "held_concept_ids",
    "held_conditions",
    "introduced_concept_ids",
    "introduction_due",
    "introduction_for_today",
    "is_free_use",
    "is_held",
    "mark_introduced",
    "note_concept_evidence",
    "weekly_concept_quota",
]
