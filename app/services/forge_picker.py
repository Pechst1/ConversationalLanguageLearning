"""WP-S4 — La Forge's one picker: which grammar rules a forge block works on.

WORK-PACKAGES-2026-09-24-seance §2 / WP-S4. The day introduces a rule
(WP-L4's Règle), the forge takes it from introduced to proficient and keeps
due rules held, and the level shows it (WP-L7). This module decides the
*rules*; WP-S3's ``Composer`` (``app/services/forge.py``) decides the *items*.

The picker is built only from the primitives the journey already uses, so the
journey and the séance can never disagree about what today is:

* **today** — one anchor rule, in this order:

  1. the rule the learner explicitly asked for (``preferred_concept_id``: the
     Cahier fiche, a practice link) — always seated, always first;
  2. the rule introduced today (``introduced_at`` today, WP-L4's Règle read or
     its first evidence), not yet held;
  3. a rule a due erratum points at (repair first: the learner's own
     mistake is the most urgent thing to forge);
  4. today's new rule from the rhythm quota (:func:`concept_life.introduction_due`
     through the one new-concept picker, ``AtelierScheduler.next_new_concepts``
     — the same pick :func:`concept_life.introduction_for_today` makes for the
     journey), when nothing was introduced today;
  5. the weakest rule in progress (introduced, not held; lowest stability,
     then score);
  6. the most urgent due rule (a scheduled rule the learner never formally
     met, e.g. from an older surface);
  7. a held rule kept warm (earliest next review), so the forge is never empty
     for a learner who holds everything and has no quota left.

* **due** — grammar rules the one review queue (WP-L3
  ``UnifiedSRSService.plan_review_items``) says are due, including rules a due
  erratum points at, in the queue's own priority order;
* **contrast** — introduced contrast partners (WP-L2 ``contrast_partners``) of
  the anchor and the due rules; the queue's own contrast items come first.

**New rules come only from the quota.** A due rule has a schedule, a contrast
partner must already be introduced, and the anchor is new only through step 4
(or the learner's own explicit choice). There is no padding from teaching
order: a plan may hold a single rule. That is what retired
the generation service's old «select daily concepts» and the séance endpoint's
pad-to-three.

Read-only. Nothing here writes or moves a due date.

**Interface for WP-S3** (``Composer``)::

    plan = forge_plan(db, user, now, preferred_concept_id=None, budget_seconds=None)
    plan.units            # (ForgeUnit(concept_id, role, reason), …) today first
    plan.pairs()          # [(concept_id, "today" | "due" | "contrast"), …]
    plan.budget_seconds   # the block's length, from the rhythm (or the fold)
    plan.reason           # why the anchor is the anchor (see ANCHOR_REASONS)
    plan.new_concept_id   # the anchor when forging it introduces it, else None

A started séance stores ``plan.as_payload()`` in ``quote_payload["forge"]``
(with ``origin`` and, when folded into the day, ``journey_step_id``), so the
composer reads the same plan the start endpoint seated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept, UserGrammarProgress

ForgeRole = Literal["today", "due", "contrast"]
ROLE_TODAY: ForgeRole = "today"
ROLE_DUE: ForgeRole = "due"
ROLE_CONTRAST: ForgeRole = "contrast"

#: Why the anchor was chosen (``ForgePlan.reason``).
REASON_PREFERRED = "preferred"
REASON_INTRODUCED_TODAY = "introduced_today"
REASON_DUE_ERRATUM = "due_erratum"
REASON_NEW_FROM_QUOTA = "new_from_quota"
REASON_WEAKEST_IN_PROGRESS = "weakest_in_progress"
REASON_MOST_DUE = "most_due"
REASON_KEEP_WARM = "keep_warm"
REASON_EMPTY = "empty"
ANCHOR_REASONS = (
    REASON_PREFERRED,
    REASON_INTRODUCED_TODAY,
    REASON_DUE_ERRATUM,
    REASON_NEW_FROM_QUOTA,
    REASON_WEAKEST_IN_PROGRESS,
    REASON_MOST_DUE,
    REASON_KEEP_WARM,
    REASON_EMPTY,
)

#: A forge block on its own (the after-day chip, «Forge · 5 min»), per rhythm.
#: Soutenu and Intensif fold the forge into the day instead; there the planner
#: sizes it from what the day leaves (``journey_planner``), capped by this.
FORGE_SECONDS: dict[str, int] = {
    "leger": 300,
    "regulier": 300,
    "soutenu": 420,
    "intensif": 600,
}
#: A forge block shorter than this is not a block (the fold is then skipped).
FORGE_MIN_SECONDS = 120
#: The room a folded day keeps free of quick items for the forge; the forge
#: then takes whatever the day leaves, up to the rhythm's FORGE_SECONDS.
FORGE_RESERVE_SECONDS = 240
#: The rhythms whose day folds the forge into the Scène movement (owner
#: decision 3, 2026-09-24). Léger and Régulier get the after-day chip.
FOLDED_RHYTHMS = frozenset({"soutenu", "intensif"})


@dataclass(frozen=True, slots=True)
class ForgeUnit:
    concept_id: int
    role: ForgeRole
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ForgePlan:
    units: tuple[ForgeUnit, ...]
    budget_seconds: int
    reason: str
    rhythm: str = "regulier"
    #: The anchor, when forging it is what introduces it (quota or explicit).
    new_concept_id: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def anchor(self) -> ForgeUnit | None:
        return self.units[0] if self.units and self.units[0].role == ROLE_TODAY else None

    @property
    def concept_ids(self) -> list[int]:
        return [unit.concept_id for unit in self.units]

    @property
    def folded(self) -> bool:
        return self.rhythm in FOLDED_RHYTHMS

    def pairs(self) -> list[tuple[int, ForgeRole]]:
        """``[(concept_id, role), …]`` — the list WP-S3's Composer takes."""

        return [(unit.concept_id, unit.role) for unit in self.units]

    def as_payload(self) -> dict[str, Any]:
        return {
            "units": [
                {"concept_id": unit.concept_id, "role": unit.role, "reason": unit.reason}
                for unit in self.units
            ],
            "budget_seconds": self.budget_seconds,
            "reason": self.reason,
            "rhythm": self.rhythm,
            "new_concept_id": self.new_concept_id,
        }


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def forge_budget_seconds(user: Any) -> int:
    """A standalone forge block's length for this learner's rhythm."""

    from app.services.journey_rhythm import rhythm_of

    return FORGE_SECONDS.get(rhythm_of(user), FORGE_SECONDS["regulier"])


def forge_is_folded(user: Any) -> bool:
    """Does this learner's day carry the forge inside it (Soutenu, Intensif)?"""

    from app.services.journey_rhythm import rhythm_of

    return rhythm_of(user) in FOLDED_RHYTHMS


def unit_caps(budget_seconds: int) -> tuple[int, int]:
    """``(due, contrast)`` rules a block of this length has room for.

    The composition is ≈ 40 % today / 40 % due / 20 % contrast (§2); a rule
    needs a handful of items to be worth seating, so a short block seats fewer.
    """

    if budget_seconds <= 180:
        return 1, 1
    if budget_seconds <= 360:
        return 2, 1
    return 3, 2


def _language(user: Any) -> str:
    return str(getattr(user, "target_language", None) or "fr").strip() or "fr"


def _usable(concept: GrammarConcept | None, language: str) -> bool:
    return bool(
        concept is not None
        and concept.active
        and concept.external_id
        and (concept.language or "fr") == language
    )


def _progress_rows(db: Session, user: Any, language: str) -> list[tuple[UserGrammarProgress, GrammarConcept]]:
    return (
        db.query(UserGrammarProgress, GrammarConcept)
        .join(GrammarConcept, GrammarConcept.id == UserGrammarProgress.concept_id)
        .filter(
            UserGrammarProgress.user_id == user.id,
            GrammarConcept.active.is_(True),
            GrammarConcept.language == language,
            GrammarConcept.external_id.isnot(None),
            GrammarConcept.external_id != "",
        )
        .all()
    )


def _introduced(progress: UserGrammarProgress) -> bool:
    return progress.introduced_at is not None or int(progress.reps or 0) > 0


def _anchor(
    db: Session,
    user: Any,
    *,
    now: datetime,
    language: str,
    rows: list[tuple[UserGrammarProgress, GrammarConcept]],
    preferred_concept_id: int | None,
    errata_ids: list[int],
    due_ids: list[int],
) -> tuple[int | None, str, bool]:
    """``(concept_id, reason, is_new)`` of today's rule."""

    from app.services import concept_life

    by_id = {concept.id: progress for progress, concept in rows}
    if preferred_concept_id:
        concept = db.get(GrammarConcept, int(preferred_concept_id))
        if concept is not None and concept.active:
            progress = by_id.get(concept.id)
            return concept.id, REASON_PREFERRED, progress is None or not _introduced(progress)

    today = now.date()
    introduced_today = sorted(
        (
            (stamp, concept.id)
            for progress, concept in rows
            if (stamp := _aware(progress.introduced_at)) is not None
            and stamp.date() == today
            and stamp <= now
            and progress.held_at is None
        ),
        reverse=True,
    )
    if introduced_today:
        return introduced_today[0][1], REASON_INTRODUCED_TODAY, False

    for concept_id in errata_ids:
        concept = db.get(GrammarConcept, concept_id)
        if _usable(concept, language):
            progress = by_id.get(concept_id)
            return concept_id, REASON_DUE_ERRATUM, progress is None or not _introduced(progress)

    if concept_life.introduction_due(db, user, now=now):
        from app.services.atelier import AtelierScheduler

        picked = AtelierScheduler(db).next_new_concepts(user, limit=1, language=language)
        if picked:
            return picked[0].id, REASON_NEW_FROM_QUOTA, True

    in_progress = [
        (float(progress.stability or 0.0), float(progress.score or 0.0), concept.difficulty_order or 0, concept.id)
        for progress, concept in rows
        if _introduced(progress) and progress.held_at is None
    ]
    if in_progress:
        return min(in_progress)[3], REASON_WEAKEST_IN_PROGRESS, False

    for concept_id in due_ids:
        if _usable(db.get(GrammarConcept, concept_id), language):
            return concept_id, REASON_MOST_DUE, False

    held = sorted(
        (
            _aware(progress.next_review) or now,
            concept.id,
        )
        for progress, concept in rows
        if progress.held_at is not None
    )
    if held:
        return held[0][1], REASON_KEEP_WARM, False
    return None, REASON_EMPTY, False


def _review_queue(db: Session, user: Any, *, now: datetime) -> tuple[list[int], list[int], list[int]]:
    """``(errata, due, contrast)`` concept ids from WP-L3's one queue, in its order.

    ``errata``: rules a due erratum points at; ``due``: every due rule, errata
    ones included; ``contrast``: the queue's own contrast partners.
    """

    from app.services.unified_srs import ItemType, UnifiedSRSService

    try:
        # The whole queue: the block's own budget is the composer's business;
        # here only the ranking matters.
        items = UnifiedSRSService(db).plan_review_items(user.id, budget_seconds=3600, now=now)
    except Exception:  # pragma: no cover - a broken queue costs the due rules, never the forge
        return [], [], []
    errata: list[int] = []
    due: list[int] = []
    contrast: list[int] = []
    for item in items:
        if item.item_type not in (ItemType.GRAMMAR, ItemType.ERROR):
            continue
        raw = (item.metadata or {}).get("concept_id")
        try:
            concept_id = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            concept_id = None
        if concept_id is None:
            continue
        if item.item_type is ItemType.GRAMMAR and (item.metadata or {}).get("contrast_for"):
            if concept_id not in contrast:
                contrast.append(concept_id)
        else:
            if item.item_type is ItemType.ERROR and concept_id not in errata:
                errata.append(concept_id)
            if concept_id not in due:
                due.append(concept_id)
    return errata, due, contrast


def _partners(
    db: Session,
    concept_ids: list[int],
    *,
    introduced: dict[int, UserGrammarProgress],
    language: str,
) -> list[int]:
    """Introduced contrast partners of these rules, in the rules' order."""

    from app.services.unified_srs import contrast_partner_refs

    if not concept_ids:
        return []
    concepts = {
        concept.id: concept
        for concept in db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids)).all()
    }
    refs: list[int | str] = []
    for concept_id in concept_ids:
        concept = concepts.get(concept_id)
        if concept is not None:
            refs.extend(contrast_partner_refs(concept))
    if not refs:
        return []
    ids = {ref for ref in refs if isinstance(ref, int)}
    external = {ref for ref in refs if isinstance(ref, str)}
    query = db.query(GrammarConcept).filter(GrammarConcept.active.is_(True), GrammarConcept.language == language)
    found = query.filter(
        (GrammarConcept.id.in_(sorted(ids) or [-1])) | (GrammarConcept.external_id.in_(sorted(external) or [""]))
    ).all()
    by_ref: dict[int | str, int] = {}
    for concept in found:
        by_ref[concept.id] = concept.id
        if concept.external_id:
            by_ref[concept.external_id] = concept.id
    ordered: list[int] = []
    for ref in refs:
        concept_id = by_ref.get(ref)
        if concept_id is None or concept_id in ordered:
            continue
        progress = introduced.get(concept_id)
        # Never a brand-new rule through the back door: a partner must be met.
        if progress is None or not _introduced(progress):
            continue
        ordered.append(concept_id)
    return ordered


def forge_plan(
    db: Session,
    user: Any,
    now: datetime | None = None,
    *,
    preferred_concept_id: int | None = None,
    budget_seconds: int | None = None,
) -> ForgePlan:
    """The rules a forge block works on, today first. Read-only."""

    from app.services.journey_rhythm import rhythm_of

    now = _aware(now) or datetime.now(UTC)
    rhythm = rhythm_of(user)
    budget = int(budget_seconds) if budget_seconds else forge_budget_seconds(user)
    budget = max(FORGE_MIN_SECONDS, budget)
    language = _language(user)
    rows = _progress_rows(db, user, language)
    progress_by_id = {concept.id: progress for progress, concept in rows}
    notes: list[str] = []

    errata_ids, due_ids, queue_contrast = _review_queue(db, user, now=now)
    anchor_id, reason, is_new = _anchor(
        db,
        user,
        now=now,
        language=language,
        rows=rows,
        preferred_concept_id=preferred_concept_id,
        errata_ids=errata_ids,
        due_ids=due_ids,
    )
    units: list[ForgeUnit] = []
    seen: set[int] = set()
    if anchor_id is not None:
        units.append(ForgeUnit(anchor_id, ROLE_TODAY, reason))
        seen.add(anchor_id)

    due_cap, contrast_cap = unit_caps(budget)
    due_units: list[int] = []
    for concept_id in due_ids:
        if len(due_units) >= due_cap:
            break
        if concept_id in seen:
            continue
        concept = db.get(GrammarConcept, concept_id)
        if not _usable(concept, language):
            continue
        due_units.append(concept_id)
        seen.add(concept_id)
    units.extend(ForgeUnit(concept_id, ROLE_DUE, "due") for concept_id in due_units)

    contrast_candidates = [
        *queue_contrast,
        *_partners(
            db,
            [unit.concept_id for unit in units],
            introduced=progress_by_id,
            language=language,
        ),
    ]
    contrast_units: list[int] = []
    for concept_id in contrast_candidates:
        if len(contrast_units) >= contrast_cap:
            break
        if concept_id in seen:
            continue
        progress = progress_by_id.get(concept_id)
        if progress is None or not _introduced(progress):
            continue
        contrast_units.append(concept_id)
        seen.add(concept_id)
    units.extend(ForgeUnit(concept_id, ROLE_CONTRAST, "contrast") for concept_id in contrast_units)

    if not units:
        notes.append("nothing to forge: no rule introduced, due, or allowed by the quota")
    return ForgePlan(
        units=tuple(units),
        budget_seconds=budget,
        reason=reason,
        rhythm=rhythm,
        new_concept_id=anchor_id if is_new else None,
        notes=tuple(notes),
    )


def forge_anchor_id(db: Session, user: Any, now: datetime | None = None) -> int | None:
    """Today's rule alone (the forge entry's ``concept``), or None."""

    plan = forge_plan(db, user, now)
    anchor = plan.anchor
    return anchor.concept_id if anchor is not None else None


def forge_anchor_brief(db: Session, user: Any, *, now: datetime | None = None) -> dict[str, Any] | None:
    """``{"concept_id", "title_native", "title_fr"}`` of today's rule, for the fold."""

    from app.services.concept_life import concept_brief
    from app.services.journey_contracts import normalize_control_language

    concept_id = forge_anchor_id(db, user, now)
    concept = db.get(GrammarConcept, concept_id) if concept_id is not None else None
    if concept is None:
        return None
    language = normalize_control_language(getattr(user, "native_language", None))
    try:
        brief = concept_brief(db, concept, control_language=language)
    except Exception:  # pragma: no cover - a brief is a nicety; the id is what matters
        brief = {}
    return {
        "concept_id": concept.id,
        "title_native": str(brief.get("title_native") or concept.name or ""),
        "title_fr": str(brief.get("title_fr") or ""),
    }


__all__ = [
    "ANCHOR_REASONS",
    "FOLDED_RHYTHMS",
    "FORGE_MIN_SECONDS",
    "FORGE_SECONDS",
    "ForgePlan",
    "ForgeRole",
    "ForgeUnit",
    "ROLE_CONTRAST",
    "ROLE_DUE",
    "ROLE_TODAY",
    "FORGE_RESERVE_SECONDS",
    "forge_anchor_brief",
    "forge_anchor_id",
    "forge_budget_seconds",
    "forge_is_folded",
    "forge_plan",
    "unit_caps",
]
