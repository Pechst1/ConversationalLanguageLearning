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
  days apart, plus one correct, unaided spaced item (a Rappel format, not a
  reply) at least fourteen days after the introduction *and* at least
  :data:`HELD_SPACED_GAP_HOURS` hours after the learner's previous contact with
  the unit (WP-138): elapsed time since the introduction is not retention, a
  delayed recall is. ``held_at`` is written the first
  time that is true and never cleared: demotion stays invisible (WP-L7), a
  fragile held concept simply comes back through the scheduler.

WP-L7 reads :func:`concept_stage`, :func:`held_concept_ids` and
:func:`introduced_concept_ids`.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.srs.memory import Evidence, EvidenceFormat, grade_evidence
from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization, UserGrammarProgress

#: §2.2 — new grammar units a week, per rhythm.
#: 2026-10-03 (owner: «substantially faster than Duolingo»): doubled. The
#: intake throttle still halves it while reviews pile up or accuracy drops.
#: Intensif's 8 means one day of the week introduces two (the journey's rule
#: and the forge's).
NEW_CONCEPTS_PER_WEEK: dict[str, int] = {
    "leger": 2,
    "regulier": 4,
    "soutenu": 6,
    "intensif": 8,
}
#: Held needs two correct free uses at least this many days apart…
HELD_FREE_USE_GAP_DAYS = 7
#: …and one correct spaced item at least this many days after the introduction.
HELD_SPACED_AFTER_DAYS = 14
#: …and that spaced item must be a *delayed* recall: answered at least this many
#: hours after the learner last met the unit anywhere (WP-138, status plan
#: 2026-10-06). An item right after a lesson, a Forge séance or a reply that used
#: the form shows the rule is fresh, not that it was retained. Overnight, not
#: longer: the Forge picker still brings a practising unit back daily (as a
#: contrast partner), so a longer gap needs the picker to leave owed units alone.
HELD_SPACED_GAP_HOURS = 20
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


_UNSET: Any = object()


def is_delayed_recall(previous_contact_at: datetime | None, *, now: datetime) -> bool:
    """WP-138: was the unit left alone long enough for a success to show retention?

    ``None`` (no recorded contact, e.g. a legacy row) does not block it: the
    fourteen days since the introduction still apply.
    """

    previous = _aware(previous_contact_at)
    if previous is None:
        return True
    return (_aware(now) or datetime.now(UTC)) - previous >= timedelta(hours=HELD_SPACED_GAP_HOURS)


def note_concept_evidence(
    progress: Any,
    evidence: Evidence,
    *,
    now: datetime,
    previous_contact_at: Any = _UNSET,
) -> None:
    """Keep the concept's life up to date with one observation. Never commits.

    Called by ``apply_grammar_evidence`` for every observation it schedules,
    and by the journey for a same-day success it folds (the schedule moves
    once a day; the life still sees every use).

    ``previous_contact_at`` is when the learner last met the unit *before* this
    observation. Callers that have already stamped ``last_review`` with ``now``
    pass the earlier value; everyone else leaves it out and the row's
    ``last_review`` is read.
    """

    now = _aware(now) or datetime.now(UTC)
    if previous_contact_at is _UNSET:
        previous_contact_at = getattr(progress, "last_review", None)
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
    elif evidence.format in SPACED_ITEM_FORMATS and not evidence.assisted:
        # WP-138: evidence, not elapsed time. Fourteen days since the
        # introduction only opens the window; the success itself has to be an
        # unaided recall after the unit was left alone (HELD_SPACED_GAP_HOURS).
        introduced = _aware(progress.introduced_at)
        if (
            introduced is not None
            and now - introduced >= timedelta(days=HELD_SPACED_AFTER_DAYS)
            and is_delayed_recall(previous_contact_at, now=now)
        ):
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


# ---------------------------------------------------------------------------
# WP-130 A — one vocabulary for every progress surface
# ---------------------------------------------------------------------------
#
# The notebook (Cahier), its Relevé and the level (Dossier) name a unit's state
# with the same three words, and count them from the same function. Labels and
# reads only: the held conditions above are unchanged.

#: The words for the three states a learner sees (singular, plural). German has
#: one word per state: «gefestigt» is «tenue» and nothing else.
STAGE_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "en": {
        STAGE_INTRODUCED: ("introduced", "introduced"),
        STAGE_PRACTISING: ("practising", "practising"),
        STAGE_HELD: ("held", "held"),
    },
    "de": {
        STAGE_INTRODUCED: ("eingeführt", "eingeführt"),
        STAGE_PRACTISING: ("in Übung", "in Übung"),
        STAGE_HELD: ("gefestigt", "gefestigt"),
    },
    "fr": {
        STAGE_INTRODUCED: ("découverte", "découvertes"),
        STAGE_PRACTISING: ("en route", "en route"),
        STAGE_HELD: ("tenue", "tenues"),
    },
}

#: The visible states, in the order a line lists them.
VISIBLE_STAGES: tuple[str, ...] = (STAGE_INTRODUCED, STAGE_PRACTISING, STAGE_HELD)


def progress_stage(progress: Any | None) -> str:
    """The stage every progress surface shows (WP-130 A).

    Like :func:`concept_stage`, except that *held* is the recorded «Tenue»
    (``held_at``): exactly the units the level counts
    (:func:`held_concept_ids`), so the notebook can never call a unit held that
    the level does not count, nor the other way round.
    """

    if progress is None:
        return STAGE_NEW
    if getattr(progress, "held_at", None) is not None:
        return STAGE_HELD
    if int(getattr(progress, "reps", 0) or 0) > 0:
        return STAGE_PRACTISING
    if getattr(progress, "introduced_at", None) is not None:
        return STAGE_INTRODUCED
    return STAGE_NEW


def stage_counts(progresses: Any) -> dict[str, int]:
    """``{"introduced": n, "practising": n, "held": n}`` over progress rows."""

    counts = dict.fromkeys(VISIBLE_STAGES, 0)
    for progress in progresses:
        stage = progress_stage(progress)
        if stage in counts:
            counts[stage] += 1
    return counts


def unit_stage_counts(db: Session, user_id: UUID, unit_ids: Any) -> dict[str, int]:
    """:func:`stage_counts` for some units of one learner (the level's band)."""

    ids = [int(unit_id) for unit_id in unit_ids]
    if not ids:
        return dict.fromkeys(VISIBLE_STAGES, 0)
    rows = (
        db.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user_id, UserGrammarProgress.concept_id.in_(ids))
        .all()
    )
    return stage_counts(rows)


def stage_label(stage: str, language: str | None = "en", *, count: int = 1) -> str | None:
    """The learner's word for a stage, or ``None`` for a unit not met yet."""

    table = STAGE_LABELS.get(str(language or "en")[:2].lower(), STAGE_LABELS["en"])
    pair = table.get(stage)
    if pair is None:
        return None
    # French puts 0 and 1 in the singular; English and German labels do not vary.
    return pair[0] if count <= 1 else pair[1]


#: What a unit still needs before it is held (:func:`held_missing`).
MISSING_FIRST_FREE_USE = "free_use_first"
MISSING_SECOND_FREE_USE = "free_use_second"
MISSING_SPACED = "spaced"


def held_missing(progress: Any | None) -> list[dict[str, Any]]:
    """The «Tenue» evidence a unit still lacks, in the order it can come.

    Each entry is ``{"code": …, "not_before": "YYYY-MM-DD" | None}``: the first
    free use; the second, on a day at least :data:`HELD_FREE_USE_GAP_DAYS`
    after the first; the spaced success, at least :data:`HELD_SPACED_AFTER_DAYS`
    after the introduction. Empty for a held unit and for one never met. Reads
    the same fields as :func:`held_conditions`.
    """

    if progress is None or progress_stage(progress) in {STAGE_HELD, STAGE_NEW}:
        return []
    missing: list[dict[str, Any]] = []
    free_use, spaced = held_conditions(progress)
    first = _aware(getattr(progress, "free_use_first_at", None))
    if not free_use:
        if first is None:
            missing.append({"code": MISSING_FIRST_FREE_USE, "not_before": None})
        else:
            day = first.date() + timedelta(days=HELD_FREE_USE_GAP_DAYS)
            missing.append({"code": MISSING_SECOND_FREE_USE, "not_before": day.isoformat()})
    if not spaced:
        introduced = _aware(getattr(progress, "introduced_at", None))
        day = (introduced + timedelta(days=HELD_SPACED_AFTER_DAYS)).date() if introduced else None
        missing.append({"code": MISSING_SPACED, "not_before": day.isoformat() if day else None})
    return missing


# ---------------------------------------------------------------------------
# WP-130 B — timely evidence opportunities («Réemploi», spaced item)
# ---------------------------------------------------------------------------
#
# «Tenue» above is unchanged. What changes is *when* the journey asks for the
# evidence it needs: the second free use used to wait until the unit's
# stability reached 10 days and a reply happened to ask for it again (median
# hold lag 41 days). These helpers say which opportunity a unit is owed today,
# from the same fields :func:`held_conditions` reads; stability plays no part.

#: The opportunity that invites a free use (the reply asks for the unit, or a
#: coach's two-line scene; never an item that shows the form first).
OPPORTUNITY_FREE_USE = "free_use"
#: The opportunity that poses a spaced item (a Rappel format).
OPPORTUNITY_SPACED = "spaced"


def free_use_opens_on(progress: Any) -> date | None:
    """The first day a free use can move the unit towards «Tenue».

    At least :data:`HELD_FREE_USE_GAP_DAYS` after the introduction (the
    second free use's earliest day when the first came on the introduction
    day), and that long after the first free use when it came later. ``None``
    when no free use is owed, or the unit was never practised successfully.
    """

    introduced = _aware(getattr(progress, "introduced_at", None))
    if introduced is None or getattr(progress, "held_at", None) is not None:
        return None
    free_use, _spaced = held_conditions(progress)
    if free_use:
        return None
    first = _aware(getattr(progress, "free_use_first_at", None))
    if first is None and int(getattr(progress, "reps", 0) or 0) <= 0:
        # Not used successfully yet: the day's ordinary practice comes first.
        return None
    opens = introduced.date() + timedelta(days=HELD_FREE_USE_GAP_DAYS)
    if first is not None:
        opens = max(opens, first.date() + timedelta(days=HELD_FREE_USE_GAP_DAYS))
    return opens


def spaced_item_owed(progress: Any, *, now: datetime) -> bool:
    """Is a spaced item owed, and would a success *now* count (≥ 14 days in)?

    Compared on the clock, as :func:`note_concept_evidence` compares it, so an
    item posed on day 14 before the hour of the introduction is not posed for
    nothing: it opens the day after.
    """

    introduced = _aware(getattr(progress, "introduced_at", None))
    if introduced is None or getattr(progress, "held_at", None) is not None:
        return False
    if getattr(progress, "spaced_success_at", None) is not None:
        return False
    now = _aware(now) or datetime.now(UTC)
    return now - introduced >= timedelta(days=HELD_SPACED_AFTER_DAYS) and is_delayed_recall(
        getattr(progress, "last_review", None), now=now
    )


def held_opportunity(progress: Any | None, *, now: datetime) -> str | None:
    """The «Tenue» evidence opportunity a unit is owed today, if any.

    :data:`OPPORTUNITY_FREE_USE` once :func:`free_use_opens_on` has passed;
    :data:`OPPORTUNITY_SPACED` once :func:`spaced_item_owed`. When both are
    owed the day alternates them (a free use is never invited right after an
    item that showed the form the same day). A missed or failed opportunity
    writes nothing here, so the unit stays owed and is offered again.
    """

    if progress is None:
        return None
    now = _aware(now) or datetime.now(UTC)
    today = now.date()
    opens = free_use_opens_on(progress)
    free_use = opens is not None and today >= opens
    spaced = spaced_item_owed(progress, now=now)
    if free_use and spaced:
        return OPPORTUNITY_SPACED if today.toordinal() % 2 else OPPORTUNITY_FREE_USE
    if free_use:
        return OPPORTUNITY_FREE_USE
    if spaced:
        return OPPORTUNITY_SPACED
    return None


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


def weekly_concept_rate(db: Session, user: Any, *, now: datetime) -> float:
    """New units a week at this learner's rhythm, throttled (§2.2) — may be
    fractional: Léger's one a week, halved, is one every two weeks."""

    from app.services.journey_rhythm import rhythm_of
    from app.services.vocabulary_pace import intake_throttle_factor

    base = NEW_CONCEPTS_PER_WEEK.get(rhythm_of(user), NEW_CONCEPTS_PER_WEEK["regulier"])
    try:
        factor = float(intake_throttle_factor(db, user, now=now))
    except Exception:  # pragma: no cover - a broken read never stops the day
        factor = 1.0
    return base * max(0.0, min(1.0, factor))


def weekly_concept_quota(db: Session, user: Any, *, now: datetime) -> int:
    """New units this learner may take in a rolling week (rounded up)."""

    import math

    return int(math.ceil(weekly_concept_rate(db, user, now=now)))


def introductions_in_window(
    db: Session, user: Any, *, now: datetime, days: int = INTAKE_WINDOW_DAYS
) -> list[datetime]:
    since = now - timedelta(days=days)
    rows = (
        db.query(UserGrammarProgress.introduced_at)
        .filter(
            UserGrammarProgress.user_id == user.id,
            UserGrammarProgress.introduced_at.isnot(None),
            # 2026-10-03 (speed): a unit the learner tested out of was already
            # known; it does not use a slot of the week's intake.
            UserGrammarProgress.tested_out_at.is_(None),
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

    Régulier's four a week are at least a day apart (7 // quota), so a week
    is not four new rules in a row and none after.
    """

    now = _aware(now) or datetime.now(UTC)
    rate = weekly_concept_rate(db, user, now=now)
    if rate <= 0:
        return False
    quota = int(-(-rate // 1))  # ceil
    whole = float(rate).is_integer()
    # The unthrottled rhythm keeps its window (7 // quota days apart); a
    # throttled, fractional rate spreads further (Léger halved: 14 days).
    spacing = max(1, INTAKE_WINDOW_DAYS // quota) if whole else max(1, round(INTAKE_WINDOW_DAYS / rate))
    recent = introductions_in_window(db, user, now=now, days=max(INTAKE_WINDOW_DAYS, spacing))
    in_week = [stamp for stamp in recent if stamp > now - timedelta(days=INTAKE_WINDOW_DAYS)]
    if len(in_week) >= quota:
        return False
    if recent:
        # More than seven a week (Intensif's 8) needs a day with two: the day's
        # cap is ceil(quota / 7), and the spacing then only separates days.
        per_day = max(1, -(-quota // INTAKE_WINDOW_DAYS))
        today = [stamp for stamp in recent if stamp.date() == now.date()]
        if per_day > 1:
            return len(today) < per_day and len(in_week) < quota
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
    # EXERCISE-QA: the first unit in line that can actually be introduced. Taking
    # only the first one let a unit with too little to practise (a B1/C1 Essai
    # is built from ✗/✓ pairs) refuse its introduction every single day and hold
    # the learner's whole grammar track behind it.
    picked = AtelierScheduler(db).next_new_concepts(user, limit=INTRODUCTION_LOOKAHEAD, language=language)
    for concept in picked:
        brief = concept_brief(db, concept, control_language=control_language)
        if brief.get("rule_card") and brief.get("examples") and introducible(brief):
            return brief
    return None


#: How many units in line :func:`introduction_for_today` looks at.
INTRODUCTION_LOOKAHEAD = 3


def introducible(brief: dict[str, Any]) -> bool:
    """Can this unit's Essai hold two items whatever today's scene says?

    From B1 the Essai is written repairs, one per ✗/✓ pair (``grammar_items.
    guided_items``), so it needs two pairs. Below B1 the items come from the
    scene and the authored examples; the planner decides on the day.
    """

    from app.services.chrome_language import french_chrome

    if not french_chrome(brief.get("level")):
        return True
    return len(brief.get("contrast_pairs") or []) >= 2


__all__ = [
    "HELD_FREE_USE_GAP_DAYS",
    "HELD_SPACED_AFTER_DAYS",
    "HELD_SPACED_GAP_HOURS",
    "MISSING_FIRST_FREE_USE",
    "MISSING_SECOND_FREE_USE",
    "MISSING_SPACED",
    "NEW_CONCEPTS_PER_WEEK",
    "OPPORTUNITY_FREE_USE",
    "OPPORTUNITY_SPACED",
    "STAGE_LABELS",
    "STAGE_HELD",
    "STAGE_INTRODUCED",
    "STAGE_NEW",
    "STAGE_PRACTISING",
    "VISIBLE_STAGES",
    "concept_brief",
    "concept_stage",
    "free_use_opens_on",
    "held_concept_ids",
    "held_conditions",
    "held_missing",
    "held_opportunity",
    "introduced_concept_ids",
    "introduction_due",
    "introduction_for_today",
    "introducible",
    "is_free_use",
    "is_delayed_recall",
    "is_held",
    "mark_introduced",
    "note_concept_evidence",
    "progress_stage",
    "spaced_item_owed",
    "stage_counts",
    "stage_label",
    "unit_stage_counts",
    "weekly_concept_quota",
    "weekly_concept_rate",
]
