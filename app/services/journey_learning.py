"""WP-05 — canonical learning evidence, review, and correction policy.

Everything the daily journey learns about a learner is written into the records
that already exist: :class:`LearningSession`, :class:`SessionLearningMoment`,
``UserVocabularyProgress`` (through :class:`VocabularyCreditService`),
``UserGrammarProgress`` and ``UserError`` (through :class:`ErrorMemoryService`).

This module deliberately does **not**:

* create a scheduler, a "daily words" table, or a second answer store;
* import WP-02's ORM models — it takes ``journey_id`` / ``step_id`` as plain
  UUIDs and the frozen dataclasses of :mod:`app.services.journey_contracts`;
* commit. Every write goes through the caller's session; the journey state
  machine owns the transaction boundary.

The policy it enforces is CONTRACTS §7:

* reading or tapping is recognition, never production;
* a copied suggested response is never independent production;
* a retry never rewrites the first attempt as independently correct;
* an infrastructure failure is unscored, never a learner mistake;
* at most one foreground correction per turn, and no punishment event for a
  no-op correction, a fabricated span, or punctuation invented by ASR;
* an omitted *optional* target is not a lapse — a lapse needs an explicit
  elicitation obligation.

One record is written at the level of the *turn* rather than of a target: when
a response turn produces no target observation at all, the objective-level row
(``kind='journey_objective'``, source key
``journey:<journey>:<step>:objective:<scenario_key>:<evidence_kind>``) keeps
the turn visible to the CONTRACTS §8 capability rubric. It is capability
evidence only — it never credits a schedule, a lapse or a vocabulary word.
"""
from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.grammar import GrammarConcept
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.error_memory import ErrorMemoryService
from app.services.glosses import word_gloss
from app.services.grammar import (
    GrammarService,
    calculate_next_review,
    determine_state,
    is_machine_note,
    personal_note,
)
from app.services.journey_contracts import (
    AppliedEvidence,
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    Correction,
    EvidenceKind,
    InputMode,
    LearningCandidate,
    RecallEvaluation,
    RecallTask,
    ResponseEvaluation,
    ScenarioBrief,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
    evidence_source_key,
    normalize_answer_text,
    strongest_assistance,
)
from app.services.unified_srs import DueLearningItem, ItemType, UnifiedSRSService
from app.services.vocabulary_credit import VocabularyCreditService

JOURNEY_LEARNING_POLICY_VERSION = "journey-learning-v1"

#: ``SessionLearningMoment.source_type`` for every row this module writes.
JOURNEY_SOURCE_TYPE = "daily_journey"
#: ``LearningSession.conversation_style`` marker for the journey's session.
JOURNEY_SESSION_STYLE = "daily_journey"
#: ``LearningSession.topic`` prefix; the full topic is the idempotency marker.
JOURNEY_SESSION_TOPIC_PREFIX = "daily_journey:"
JOURNEY_SESSION_PLANNED_MINUTES = 5

#: ``SessionLearningMoment.kind`` values written by this module.
JOURNEY_MOMENT_KIND_BY_TARGET: dict[TargetKind, str] = {
    TargetKind.VOCABULARY: "journey_vocabulary",
    TargetKind.GRAMMAR: "journey_grammar",
    TargetKind.ERROR: "journey_error",
}
JOURNEY_CORRECTION_MOMENT_KIND = "journey_correction"
#: The turn-level record of the scenario's response turn. It exists so a learner
#: who fulfils the objective *without touching a tracked target* still leaves
#: capability evidence (CONTRACTS §8). It carries no SRS or error-memory credit.
JOURNEY_OBJECTIVE_MOMENT_KIND = "journey_objective"
JOURNEY_MOMENT_KINDS = frozenset(
    {
        *JOURNEY_MOMENT_KIND_BY_TARGET.values(),
        JOURNEY_CORRECTION_MOMENT_KIND,
        JOURNEY_OBJECTIVE_MOMENT_KIND,
    }
)

#: ``target_kind`` slot of the source key used for a foreground correction.
CORRECTION_SOURCE_KIND = "correction"
#: ``target_kind`` slot of the source key used for the turn-level objective
#: record. Deliberately not a :class:`TargetKind`: the objective is not a
#: schedulable item, and nothing may ever credit it as one.
OBJECTIVE_SOURCE_KIND = "objective"
#: ``target_id`` slot used when the journey's scenario key is unknown.
OBJECTIVE_TARGET_FALLBACK = "response_turn"

MAX_DUE_CANDIDATES = 2
MAX_NEW_CANDIDATES = 1

#: Per-candidate journey budget (CONTRACTS §9). Deliberately larger than the
#: flashcard estimates in :mod:`app.services.unified_srs`: a journey recall step
#: includes reading the scene line and typing, not a 8-second card flip.
CANDIDATE_SECONDS: dict[ItemType, int] = {
    ItemType.VOCAB: 30,
    ItemType.GRAMMAR: 45,
    ItemType.ERROR: 40,
}

#: How many *additional* validated errors may reach error memory behind the one
#: foreground correction. The learner's stored corrector preference stays
#: meaningful: the detailed view always receives every validated correction,
#: only the number of punishment events is bounded.
BACKGROUND_ERRATA_CAP: dict[str, int] = {"lenient": 0, "moderate": 1, "strict": 2}
DEFAULT_CORRECTION_LEVEL = "moderate"

#: Grammar evidence scores on the existing 0-10 scale (``app.services.grammar``).
GRAMMAR_EVIDENCE_SCORE: dict[EvidenceKind, float] = {
    EvidenceKind.RECOGNIZED: 5.0,
    EvidenceKind.PRODUCED_SUPPORTED: 7.0,
    EvidenceKind.PRODUCED_INDEPENDENT: 8.5,
    EvidenceKind.NOT_YET: 2.0,
}

#: Vocabulary credit events (``app.services.vocabulary_credit``).
VOCABULARY_EVIDENCE_EVENT: dict[EvidenceKind, str] = {
    EvidenceKind.RECOGNIZED: "recognized",
    EvidenceKind.PRODUCED_SUPPORTED: "produced_supported",
    EvidenceKind.PRODUCED_INDEPENDENT: "produced_correct",
    EvidenceKind.NOT_YET: "produced_incorrect",
}

#: ``(rating, repaired)`` for :meth:`ErrorMemoryService.review_error`.
ERROR_EVIDENCE_REVIEW: dict[EvidenceKind, tuple[int, bool]] = {
    EvidenceKind.RECOGNIZED: (3, False),
    EvidenceKind.PRODUCED_SUPPORTED: (3, True),
    EvidenceKind.PRODUCED_INDEPENDENT: (4, True),
    EvidenceKind.NOT_YET: (1, False),
}

LEVEL_BAND_DIFFICULTY: dict[str, int] = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 5}

#: How much prior journey evidence one candidate lookup reads. Bounded because
#: `select_learning_candidates` runs on the journey-creation path; older history
#: beyond this window is reported as absent rather than guessed at.
CANDIDATE_HISTORY_LIMIT = 400

#: Ordering used to pick the strongest observation for a target. `unscored` is
#: not here: an infrastructure failure is not evidence of anything.
EVIDENCE_STRENGTH: dict[EvidenceKind, int] = {
    EvidenceKind.NOT_YET: 0,
    EvidenceKind.RECOGNIZED: 1,
    EvidenceKind.PRODUCED_SUPPORTED: 2,
    EvidenceKind.PRODUCED_INDEPENDENT: 3,
}

#: `metadata["evidence_history"]` values. "unknown" is load-bearing: it is the
#: honest answer for pre-V2 rows and it must never be read as a demonstration.
EVIDENCE_HISTORY_NONE = "none"
EVIDENCE_HISTORY_UNKNOWN = "unknown"
EVIDENCE_HISTORY_RECORDED = "recorded"

#: Renderer/task types mapped onto what they can prove.
OpportunityKind = Literal["choice", "tiles", "reveal", "continue", "open_production"]
RECOGNITION_ONLY_OPPORTUNITIES: frozenset[str] = frozenset(
    {"choice", "tiles", "reveal", "continue"}
)

_STOPWORDS = frozenset(
    {
        "the", "and", "for", "you", "your", "with", "that", "this", "une", "des",
        "les", "der", "die", "das", "und", "pour", "avec", "dans", "vous", "est",
        "sur", "par", "qui", "que", "aux", "ist", "ein", "eine", "von", "sie",
    }
)


# --------------------------------------------------------------------------
# Text folding
# --------------------------------------------------------------------------

def fold_for_comparison(value: str | None) -> str:
    """Case/accent/punctuation-insensitive form used for every answer compare.

    Folds iOS smart quotes first (``normalize_answer_text``), strips accents,
    and drops punctuation — including the full stops and commas a transcription
    provider invents, which must never turn a correct answer into a mistake.
    """

    text = normalize_answer_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^0-9a-z\s]+", " ", text)
    return " ".join(text.split())


def _tokens(value: str | None) -> list[str]:
    return [token for token in fold_for_comparison(value).split() if token]


def _content_tokens(value: str | None) -> set[str]:
    return {token for token in _tokens(value) if len(token) >= 3 and token not in _STOPWORDS}


def _contains_run(haystack: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start : start + len(needle)] == needle:
            return True
    return False


def answer_matches(answer: str | None, accepted: Iterable[str | None]) -> bool:
    """Is this a reasonable rendering of one of the accepted answers?

    Exact string comparison is not the test: correct but differently worded
    French must not be penalised. An answer counts when it folds to an accepted
    answer, contains it as a contiguous run of words, or is within a single
    typo of it.
    """

    folded = fold_for_comparison(answer)
    if not folded:
        return False
    answer_tokens = folded.split()
    for candidate in accepted:
        target = fold_for_comparison(candidate)
        if not target:
            continue
        if folded == target:
            return True
        target_tokens = target.split()
        if _contains_run(answer_tokens, target_tokens):
            return True
        if len(target) >= 6 and difflib.SequenceMatcher(None, folded, target).ratio() >= 0.92:
            return True
    return False


def _source_id_for(source_key: str) -> str:
    """Compact, stable ``SessionLearningMoment.source_id`` for a source key.

    ``session_learning_moments.source_id`` is ``VARCHAR(64)`` and the frozen
    source-key grammar is longer than that, so the column stores a deterministic
    digest of the key. The full key is written verbatim into ``prompt_payload``
    so nothing is lost and dedup stays exact.
    """

    digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    return f"dj-{digest[:40]}"


def journey_session_topic(journey_id: UUID | str) -> str:
    """The idempotency marker stored in ``LearningSession.topic``."""

    return f"{JOURNEY_SESSION_TOPIC_PREFIX}{journey_id}"


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; comparisons need one tz convention."""

    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _local_date(now: datetime, timezone: str | None) -> tuple[date, str | None]:
    if timezone:
        try:
            return now.astimezone(ZoneInfo(timezone)).date(), timezone
        except Exception:  # noqa: BLE001 - an unknown IANA name must not lose evidence
            logger.warning("journey_learning_unknown_timezone", timezone=timezone)
    return now.astimezone(UTC).date(), None


# --------------------------------------------------------------------------
# 1. Candidate adapter
# --------------------------------------------------------------------------

def _target_ref_for_item(item: DueLearningItem) -> TargetRef | None:
    metadata = item.metadata or {}
    if item.item_type is ItemType.VOCAB:
        word_id = metadata.get("word_id")
        if word_id is None:
            return None
        return TargetRef(
            kind=TargetKind.VOCABULARY,
            id=str(word_id),
            label_fr=item.display_title,
            label_native=metadata.get("answer") or None,
        )
    if item.item_type is ItemType.GRAMMAR:
        concept_id = metadata.get("concept_id")
        if concept_id is None:
            return None
        return TargetRef(
            kind=TargetKind.GRAMMAR,
            id=str(concept_id),
            label_fr=item.display_title,
            label_native=metadata.get("category") or None,
        )
    if item.item_type is ItemType.ERROR:
        return TargetRef(
            kind=TargetKind.ERROR,
            id=str(item.original_id),
            label_fr=metadata.get("correction") or item.display_title,
            label_native=metadata.get("why_wrong") or None,
        )
    return None


def _scenario_terms(scenario: ScenarioBrief) -> set[str]:
    task = scenario.response_task
    parts: list[str] = [
        scenario.title_fr,
        scenario.setup_fr,
        scenario.setup_native,
        scenario.objective_native,
        scenario.objective_key.replace(".", " ").replace("_", " "),
        scenario.opening_line_fr or "",
        task.objective_native,
        task.opening_line_fr,
        task.rubric_native,
        task.suggested_response_fr or "",
        task.hint_native or "",
        task.translation_native or "",
        *(intent.replace("_", " ") for intent in task.required_intents),
        *(intent.replace("_", " ") for intent in task.optional_intents),
        *(target.label_fr for target in task.targets),
        *scenario.resolution_lines.values(),
        *scenario.resolution_summaries.values(),
    ]
    return _content_tokens(" ".join(part for part in parts if part))


def _relevance_for(target: TargetRef, scenario: ScenarioBrief, terms: set[str]) -> float:
    for declared in scenario.response_task.targets:
        if declared.kind == target.kind and declared.id == target.id:
            return 1.0
    label_tokens = _content_tokens(target.label_fr)
    if not label_tokens or not terms:
        return 0.0
    overlap = len(label_tokens & terms) / len(label_tokens)
    return round(min(overlap, 1.0) * 0.8, 4)


def _candidate_evidence_history(
    db: Session, *, user: User
) -> dict[tuple[str, str], tuple[EvidenceKind | None, bool]]:
    """Strongest still-standing observation per target, in one batched read.

    Read-only: it reads `SessionLearningMoment` rows that were already written
    and never touches a schedule, a due date or a priority.

    Two rules keep this honest, because a wrong "already demonstrated" silently
    removes a learner's practice:

    * A later `not_yet` supersedes earlier successes. Only observations recorded
      strictly after the target's most recent scored failure can demonstrate it,
      so a target the learner has since got wrong is never reported as
      demonstrated. The comparison uses `observed_at`, not row order: every row
      written inside one transaction shares the same `created_at`.
    * Pre-V2 rows recorded no help usage. They only raise the *unknown* flag and
      never contribute an evidence kind, so legacy history can never be read as
      independent production.
    """

    records = read_journey_evidence(
        db, user=user, include_legacy=True, limit=CANDIDATE_HISTORY_LIMIT
    )
    floor = datetime.min.replace(tzinfo=UTC)

    has_unknown: dict[tuple[str, str], bool] = {}
    last_failure: dict[tuple[str, str], datetime] = {}
    scored: dict[tuple[str, str], list[tuple[datetime, EvidenceKind]]] = {}

    for record in records:
        if record.target is None:
            # An objective-level record names no schedulable item. It is
            # capability evidence, never a reason to skip or repeat a target.
            continue
        identity = (str(record.target.kind), record.target.id)
        if record.is_legacy or record.evidence_kind is None:
            has_unknown[identity] = True
            continue
        kind = record.evidence_kind
        if kind is EvidenceKind.UNSCORED:
            # An infrastructure failure is not evidence of anything.
            continue
        at = record.observed_at or floor
        if kind is EvidenceKind.NOT_YET:
            last_failure[identity] = max(last_failure.get(identity, floor), at)
        scored.setdefault(identity, []).append((at, kind))

    history: dict[tuple[str, str], tuple[EvidenceKind | None, bool]] = dict.fromkeys(
        has_unknown, (None, True)
    )
    for identity, observations in scored.items():
        failed_at = last_failure.get(identity)
        best: EvidenceKind | None = None
        for at, kind in observations:
            if kind is EvidenceKind.NOT_YET:
                continue
            if failed_at is not None and at <= failed_at:
                continue  # superseded by a later failure
            if best is None or EVIDENCE_STRENGTH[kind] > EVIDENCE_STRENGTH[best]:
                best = kind
        if best is None and failed_at is not None:
            best = EvidenceKind.NOT_YET
        history[identity] = (best, has_unknown.get(identity, False))
    return history


def _history_metadata(
    history: dict[tuple[str, str], tuple[EvidenceKind | None, bool]], target: TargetRef
) -> dict[str, Any]:
    """`last_evidence_kind` only when it is actually known (WP-04 reads this)."""

    best, has_unknown = history.get((str(target.kind), target.id), (None, False))
    if best is not None:
        return {
            "last_evidence_kind": str(best),
            "evidence_history": EVIDENCE_HISTORY_RECORDED,
        }
    return {
        "evidence_history": (
            EVIDENCE_HISTORY_UNKNOWN if has_unknown else EVIDENCE_HISTORY_NONE
        )
    }


def _exposure_sort_key(item: DueLearningItem) -> str:
    """Older exposure sorts first; unknown exposure counts as oldest."""

    metadata = item.metadata or {}
    for key in ("last_review_date", "next_review_date", "due_at", "next_review"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def select_learning_candidates(
    db: Session,
    *,
    user: User,
    scenario: ScenarioBrief,
    limit: int = 3,
    now: datetime | None = None,
) -> list[LearningCandidate]:
    """Existing due/fragile identities the learner already owns, ranked for this scene.

    Read-only. No due date is moved to fit a scene and nothing is marked
    reviewed: an omitted candidate stays exactly as due as it was. When the
    queue is genuinely empty the result is ``[]`` — no item is invented and
    nothing is claimed to be due.
    """

    if limit <= 0:
        return []
    now = now or datetime.now(UTC)
    terms = _scenario_terms(scenario)
    # One batched read for the whole candidate set, never one per candidate.
    history = _candidate_evidence_history(db, user=user)

    pool = UnifiedSRSService(db).get_journey_candidate_pool(user.id, now=now)
    scored: list[tuple[float, float, int, str, LearningCandidate]] = []
    seen: set[tuple[str, str]] = set()
    for item in pool:
        target = _target_ref_for_item(item)
        if target is None:
            continue
        identity = (str(target.kind), target.id)
        if identity in seen:
            continue
        seen.add(identity)
        relevance = _relevance_for(target, scenario, terms)
        candidate = LearningCandidate(
            target=target,
            priority_score=float(item.priority_score or 0.0),
            due_since_days=int(item.due_since_days or 0),
            estimated_seconds=CANDIDATE_SECONDS.get(item.item_type, 40),
            is_new=False,
            relevance=relevance,
            source_item_type=str(item.item_type),
            metadata={
                "queue_item_id": item.id,
                "original_id": str(item.original_id),
                "display_subtitle": item.display_subtitle,
                "level": item.level,
                **{
                    key: item.metadata.get(key)
                    for key in ("word_id", "concept_id", "review_mode", "state", "lapses")
                    if key in (item.metadata or {})
                },
                **_history_metadata(history, target),
            },
        )
        scored.append(
            (
                -relevance,
                -float(item.priority_score or 0.0),
                -int(item.due_since_days or 0),
                _exposure_sort_key(item),
                candidate,
            )
        )

    scored.sort(key=lambda row: row[:4])
    due_cap = min(MAX_DUE_CANDIDATES, limit)
    selected = [row[4] for row in scored[:due_cap]]

    new_cap = min(MAX_NEW_CANDIDATES, limit - len(selected))
    if new_cap > 0:
        anchor = _new_vocabulary_anchor(
            db,
            user=user,
            scenario=scenario,
            terms=terms,
            exclude={(str(c.target.kind), c.target.id) for c in selected},
            history=history,
        )
        if anchor is not None:
            selected.append(anchor)
    return selected


def _new_vocabulary_anchor(
    db: Session,
    *,
    user: User,
    scenario: ScenarioBrief,
    terms: set[str],
    exclude: set[tuple[str, str]],
    history: dict[tuple[str, str], tuple[EvidenceKind | None, bool]] | None = None,
) -> LearningCandidate | None:
    """One level-appropriate word from the scene the learner has never met.

    Marked ``is_new=True`` with ``due_since_days=0``: it is an anchor, not a
    due item, and it is only offered when the scene actually contains it.
    """

    if not terms:
        return None
    language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
    max_difficulty = LEVEL_BAND_DIFFICULTY.get((scenario.level_band or "A1").upper(), 3)
    words = (
        db.query(VocabularyWord)
        .filter(
            VocabularyWord.language == language,
            VocabularyWord.normalized_word.in_(sorted(terms)),
            or_(
                VocabularyWord.difficulty_level.is_(None),
                VocabularyWord.difficulty_level <= max_difficulty,
            ),
        )
        .order_by(
            VocabularyWord.frequency_rank.asc().nullslast(),
            VocabularyWord.id.asc(),
        )
        .limit(20)
        .all()
    )
    if not words:
        return None
    known = {
        row[0]
        for row in db.query(UserVocabularyProgress.word_id)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id.in_([word.id for word in words]),
        )
        .all()
    }
    for word in words:
        if word.id in known:
            continue
        if (str(TargetKind.VOCABULARY), str(word.id)) in exclude:
            continue
        target = TargetRef(
            kind=TargetKind.VOCABULARY,
            id=str(word.id),
            label_fr=word.word,
            label_native=word_gloss(word, user.native_language) or None,
        )
        return LearningCandidate(
            target=target,
            priority_score=0.0,
            due_since_days=0,
            estimated_seconds=CANDIDATE_SECONDS[ItemType.VOCAB],
            is_new=True,
            relevance=1.0,
            source_item_type=str(ItemType.VOCAB),
            metadata={
                "word_id": word.id,
                "anchor": "scenario_new_word",
                **_history_metadata(history or {}, target),
            },
        )
    return None


# --------------------------------------------------------------------------
# 2. Canonical learning session
# --------------------------------------------------------------------------

def ensure_journey_learning_session(
    db: Session,
    *,
    user: User,
    journey_id: UUID,
    scenario_key: str,
) -> LearningSession:
    """The one canonical :class:`LearningSession` behind a journey.

    Idempotent per ``journey_id``: the marker lives in ``LearningSession.topic``
    (``daily_journey:<journey_id>``), so a retried creation finds the existing
    row instead of opening a second session. Never commits.
    """

    marker = journey_session_topic(journey_id)
    existing = (
        db.query(LearningSession)
        .filter(LearningSession.user_id == user.id, LearningSession.topic == marker)
        .order_by(LearningSession.created_at.asc(), LearningSession.id.asc())
        .first()
    )
    if existing is not None:
        if scenario_key and not existing.scenario:
            existing.scenario = str(scenario_key)[:50]
            db.add(existing)
        return existing

    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=JOURNEY_SESSION_PLANNED_MINUTES,
        topic=marker,
        conversation_style=JOURNEY_SESSION_STYLE,
        difficulty_preference=str(getattr(user, "proficiency_level", "") or "")[:20] or None,
        scenario=str(scenario_key or "")[:50] or None,
        status="in_progress",
    )
    db.add(session)
    db.flush([session])
    logger.info(
        "journey_learning_session_created",
        user_id=str(user.id),
        journey_id=str(journey_id),
        session_id=str(session.id),
        scenario_key=scenario_key,
    )
    return session


# --------------------------------------------------------------------------
# 3. Evidence classification
# --------------------------------------------------------------------------

def classify_evidence(
    *,
    opportunity: OpportunityKind,
    is_correct: bool,
    assistance: AssistanceLevel,
) -> EvidenceKind:
    """The core rubric.

    * A choice, a tile drag, a revealed translation and a pressed Continue are
      recognition — never production, whatever the assistance level was.
    * An open production is independent only with ``AssistanceLevel.NONE``.
      A copied suggested response, a revealed solution and a repair after a
      correction all carry assistance, so they are supported production.
    """

    if not is_correct:
        return EvidenceKind.NOT_YET
    if opportunity in RECOGNITION_ONLY_OPPORTUNITIES:
        return EvidenceKind.RECOGNIZED
    if strongest_assistance([assistance]) is AssistanceLevel.NONE:
        return EvidenceKind.PRODUCED_INDEPENDENT
    return EvidenceKind.PRODUCED_SUPPORTED


def classify_observation(
    *,
    target: TargetRef,
    opportunity: OpportunityKind,
    is_correct: bool,
    assistance: AssistanceLevel,
    modality: InputMode,
    elicited: bool = True,
    learner_text: str | None = None,
    corrected_text: str | None = None,
) -> TargetObservation | None:
    """Build one observation, or ``None`` when there is nothing to record.

    ``elicited=False`` means the task never obliged the learner to use this
    target. A correct phrase that simply does not contain an optional word is
    not a vocabulary lapse, so an unelicited failure produces no observation at
    all — the target keeps its existing schedule.
    """

    if not is_correct and not elicited:
        return None
    return TargetObservation(
        target=target,
        evidence_kind=classify_evidence(
            opportunity=opportunity, is_correct=is_correct, assistance=assistance
        ),
        assistance=assistance,
        modality=modality,
        learner_text=learner_text,
        corrected_text=corrected_text,
    )


def unscored_recall_evaluation(
    *, assistance: AssistanceLevel, reason: str
) -> RecallEvaluation:
    """An infrastructure failure. Never a learner mistake, never a mutation."""

    return RecallEvaluation(
        outcome=TaskOutcome.UNSCORED,
        assistance=assistance,
        observations=[],
        correction=None,
        pending=True,
        failure_reason=reason,
    )


def is_infrastructure_failure(answer: AttemptAnswer) -> bool:
    """A voice attempt that carried no text is a transcription failure.

    ``transcript_ref`` is optional (contract revision 1), so the modality plus
    an empty transcript is the signal — not the presence of a reference.
    """

    if answer.mode is not InputMode.VOICE:
        return False
    return not normalize_answer_text(answer.text) and not answer.option_id and not answer.tile_ids


def _accepted_answers(task: RecallTask) -> list[str]:
    accepted = [text for text in task.accepted_answers if text]
    if task.solution_fr:
        accepted.append(task.solution_fr)
    if not accepted and task.prompt_fr:
        accepted.append(task.prompt_fr)
    return accepted


def _selected_option_id(task: RecallTask, answer: AttemptAnswer) -> str | None:
    if answer.option_id:
        return answer.option_id
    folded = fold_for_comparison(answer.text)
    if not folded:
        return None
    for option in task.options:
        if fold_for_comparison(option.get("text_fr")) == folded:
            return option.get("id")
    return None


def _option_text(task: RecallTask, option_id: str | None) -> str | None:
    for option in task.options:
        if option.get("id") == option_id:
            return option.get("text_fr")
    return None


def evaluate_recall(
    db: Session,
    *,
    user: User,
    task: RecallTask,
    answer: AttemptAnswer,
    assistance: AssistanceLevel,
) -> RecallEvaluation:
    """Grade one recall opportunity. Pure policy — writes nothing."""

    del db, user  # canonical writes happen in apply_learning_evidence

    if is_infrastructure_failure(answer):
        return unscored_recall_evaluation(
            assistance=assistance, reason="transcription_unavailable"
        )

    modality = answer.mode
    if answer.is_blank:
        # An empty submission is not a demonstrated mistake: record nothing so
        # the target keeps its schedule instead of collecting a free lapse.
        return RecallEvaluation(
            outcome=TaskOutcome.NOT_YET,
            assistance=assistance,
            observations=[],
            correction=None,
            pending=False,
            failure_reason="empty_answer",
        )

    if task.task_type == "choice":
        selected = _selected_option_id(task, answer)
        is_correct = bool(selected) and selected == task.correct_option_id
        learner_text = _option_text(task, selected) or answer.text
        opportunity: OpportunityKind = "choice"
    elif task.task_type == "tiles":
        expected = [str(tile) for tile in task.correct_tile_order]
        submitted = [str(tile) for tile in answer.tile_ids]
        is_correct = bool(expected) and submitted == expected
        learner_text = " ".join(submitted) if submitted else answer.text
        opportunity = "tiles"
    else:
        is_correct = answer_matches(answer.text, _accepted_answers(task))
        learner_text = answer.text
        opportunity = "open_production"

    observation = classify_observation(
        target=task.target,
        opportunity=opportunity,
        is_correct=is_correct,
        assistance=assistance,
        modality=modality,
        elicited=True,
        learner_text=learner_text,
        corrected_text=task.solution_fr if not is_correct else None,
    )
    correction = None
    if not is_correct:
        correction = build_correction(
            learner_text=learner_text,
            corrected_fr=task.solution_fr or (task.accepted_answers[0] if task.accepted_answers else None),
            note_native=task.hint_native or task.instruction_native,
        )
    return RecallEvaluation(
        outcome=TaskOutcome.MET if is_correct else TaskOutcome.NOT_YET,
        assistance=assistance,
        observations=[observation] if observation is not None else [],
        correction=correction,
        pending=False,
        failure_reason=None,
    )


# --------------------------------------------------------------------------
# 4. Correction policy
# --------------------------------------------------------------------------

def build_correction(
    *, learner_text: str | None, corrected_fr: str | None, note_native: str | None
) -> Correction | None:
    """A validated correction, or ``None``.

    Rejects the no-op (span equals correction, or they differ only by folding,
    which is where ASR punctuation and smart quotes end up) and any span the
    learner did not write.
    """

    span = normalize_answer_text(learner_text)
    corrected = normalize_answer_text(corrected_fr)
    if not span or not corrected:
        return None
    if fold_for_comparison(span) == fold_for_comparison(corrected):
        return None
    candidate = Correction(
        span_fr=span,
        corrected_fr=corrected,
        note_native=note_native or "",
    )
    if not candidate.is_valid_for(span):
        return None
    return candidate


def validate_correction(correction: Correction | None, learner_text: str | None) -> bool:
    """True when a proposed correction may be shown and may inform memory."""

    if correction is None:
        return False
    normalized = normalize_answer_text(learner_text)
    if not correction.is_valid_for(normalized):
        return False
    # A "correction" that only re-punctuates or re-accents the learner's own
    # words is a stylistic preference, not an error worth a punishment event.
    return fold_for_comparison(correction.span_fr) != fold_for_comparison(correction.corrected_fr)


def correction_relevance(correction: Correction, targets: Sequence[TargetRef]) -> float:
    """How close a correction sits to what the step was actually teaching."""

    span_tokens = _content_tokens(correction.span_fr) | _content_tokens(correction.corrected_fr)
    if not span_tokens:
        return 0.0
    best = 0.0
    for target in targets:
        label_tokens = _content_tokens(target.label_fr)
        if not label_tokens:
            continue
        overlap = len(label_tokens & span_tokens) / len(label_tokens)
        best = max(best, overlap)
    return best


def select_foreground_correction(
    *,
    user: User,
    learner_text: str | None,
    candidates: Sequence[Correction],
    targets: Sequence[TargetRef] = (),
) -> tuple[Correction | None, list[Correction]]:
    """At most one foreground correction, plus the conservative remainder.

    Returns ``(foreground, background)``. ``background`` is capped by the
    learner's stored ``grammar_correction_level`` so one response cannot
    manufacture several punishment events — but every validated correction is
    still returned to the caller for the optional detailed view, so a stored
    "strict" preference is never silently downgraded to nothing.
    """

    validated = [c for c in candidates if validate_correction(c, learner_text)]
    if not validated:
        return None, []
    validated.sort(key=lambda c: correction_relevance(c, targets), reverse=True)
    foreground = validated[0]
    level = str(getattr(user, "grammar_correction_level", None) or DEFAULT_CORRECTION_LEVEL).lower()
    cap = BACKGROUND_ERRATA_CAP.get(level, BACKGROUND_ERRATA_CAP[DEFAULT_CORRECTION_LEVEL])
    return foreground, validated[1 : 1 + cap]


# --------------------------------------------------------------------------
# 5. Canonical evidence storage
# --------------------------------------------------------------------------

@dataclass(slots=True)
class _CreditOutcome:
    applied: bool
    detail: dict[str, Any] = field(default_factory=dict)


def _existing_moment(db: Session, *, user: User, source_key: str) -> SessionLearningMoment | None:
    return (
        db.query(SessionLearningMoment)
        .filter(
            SessionLearningMoment.user_id == user.id,
            SessionLearningMoment.source_type == JOURNEY_SOURCE_TYPE,
            SessionLearningMoment.source_id == _source_id_for(source_key),
        )
        .order_by(SessionLearningMoment.created_at.asc())
        .first()
    )


def _prior_step_assistance(
    db: Session,
    *,
    user: User,
    session: LearningSession,
    journey_id: UUID,
    step_id: UUID,
    target_kind: str,
    target_id: str,
) -> list[AssistanceLevel]:
    """Assistance already recorded for this target inside this same step.

    Scoped to the journey's own LearningSession, so this stays a handful of
    rows however much evidence the learner accumulates.
    """

    prefix = f"journey:{journey_id}:{step_id}:{target_kind}:{target_id}:"
    rows = (
        db.query(SessionLearningMoment)
        .filter(
            SessionLearningMoment.user_id == user.id,
            SessionLearningMoment.session_id == session.id,
            SessionLearningMoment.source_type == JOURNEY_SOURCE_TYPE,
        )
        .all()
    )
    levels: list[AssistanceLevel] = []
    for row in rows:
        payload = row.prompt_payload or {}
        key = payload.get("source_key")
        if not isinstance(key, str) or not key.startswith(prefix):
            continue
        raw = payload.get("assistance_level")
        try:
            levels.append(AssistanceLevel(raw))
        except ValueError:
            continue
    return levels


def _resolve_evidence_kind(
    db: Session,
    *,
    user: User,
    session: LearningSession,
    journey_id: UUID,
    step_id: UUID,
    observation: TargetObservation,
) -> tuple[EvidenceKind, AssistanceLevel]:
    """A retry never erases the first attempt's assistance.

    Inside one step, once help has been revealed for a target, a later correct
    answer is supported production. The earlier row is left untouched: both
    observations stay in the record.
    """

    assistance = strongest_assistance(
        [
            observation.assistance,
            *_prior_step_assistance(
                db,
                user=user,
                session=session,
                journey_id=journey_id,
                step_id=step_id,
                target_kind=str(observation.target.kind),
                target_id=observation.target.id,
            ),
        ]
    )
    kind = observation.evidence_kind
    if kind is EvidenceKind.PRODUCED_INDEPENDENT and assistance is not AssistanceLevel.NONE:
        kind = EvidenceKind.PRODUCED_SUPPORTED
    return kind, assistance


# ---------------------------------------------------------------------------
# WP-16 / decision D-0 — one daily Séance, one source of evidence
# ---------------------------------------------------------------------------
#
# The daily journey is the day's Séance; the legacy exercise loop is the
# «Plus de pratique» drill activity. Both write into the same
# LearningSession / SessionLearningMoment / SRS records, so a target the
# journey already credited today must not be credited a second time when the
# learner chooses to drill it afterwards, and the streak must move once.
#
# Both helpers live here, in the WP-05 adapter, rather than in the legacy
# Atelier service: `app/services/atelier.py` is under a concurrent lease and
# the policy belongs to the evidence owner in any case.


def journey_credited_today(
    db: Session,
    *,
    user: User,
    target_kind: str,
    target_id: str,
    on_date: date | None = None,
) -> bool:
    """Did today's daily journey already apply SRS credit for this target?

    Read from the journey's own evidence moments — the row `apply_learning_evidence`
    writes with `srs_credit_applied` and the target in its payload. No new table
    and no second ledger: the evidence record *is* the ledger.
    """

    day = on_date or datetime.now(UTC).date()
    stmt = (
        select(SessionLearningMoment)
        .where(
            SessionLearningMoment.user_id == user.id,
            SessionLearningMoment.source_type == JOURNEY_SOURCE_TYPE,
            SessionLearningMoment.srs_credit_applied.is_(True),
        )
        .order_by(SessionLearningMoment.created_at.desc())
        .limit(200)
    )
    wanted_kind = str(target_kind)
    wanted_id = str(target_id)
    for moment in db.execute(stmt).scalars():
        payload = dict(moment.prompt_payload or {})
        if str(payload.get("observed_on") or "") != day.isoformat():
            continue
        target = dict(payload.get("target") or {})
        if str(target.get("kind") or "") == wanted_kind and str(target.get("id") or "") == wanted_id:
            return True
    return False


def record_daily_practice_streak(db: Session, user: User, *, on_date: date | None = None) -> int:
    """Move the learner's practice streak, at most once per local day.

    Byte-for-byte the rule the legacy Atelier session already applies
    (`AtelierService._update_streak`), deliberately: both surfaces write the
    same three user columns and both are no-ops once the day is marked, so a
    learner who finishes the journey and then drills gets one increment, not
    two. Returns the streak after the call.
    """

    day = on_date or date.today()
    last = getattr(user, "grammar_last_review_date", None)
    if last == day:
        return int(getattr(user, "grammar_streak_days", 0) or 0)
    if last == day - timedelta(days=1):
        user.grammar_streak_days = (user.grammar_streak_days or 0) + 1
    else:
        user.grammar_streak_days = 1
    user.grammar_last_review_date = day
    user.grammar_longest_streak = max(
        user.grammar_longest_streak or 0, user.grammar_streak_days or 0
    )
    user.mark_activity(day)
    db.add(user)
    db.flush([user])
    return int(user.grammar_streak_days or 0)


def _apply_vocabulary_credit(
    db: Session,
    *,
    user: User,
    target: TargetRef,
    evidence_kind: EvidenceKind,
    observation: TargetObservation,
    session: LearningSession,
    source_key: str,
) -> _CreditOutcome:
    try:
        word_id = int(target.id)
    except (TypeError, ValueError):
        return _CreditOutcome(False, {"skipped": "invalid_word_id"})
    word = db.get(VocabularyWord, word_id)
    if word is None:
        return _CreditOutcome(False, {"skipped": "word_missing"})
    event = VOCABULARY_EVIDENCE_EVENT.get(evidence_kind)
    if event is None:
        return _CreditOutcome(False, {"skipped": "unscored"})
    result = VocabularyCreditService(db).apply(
        user=user,
        word=word,
        event_type=event,
        source_type=JOURNEY_SOURCE_TYPE,
        learner_text=observation.learner_text,
        corrected_text=observation.corrected_text,
        session=session,
        source_payload={"source_key": source_key, "policy_version": JOURNEY_LEARNING_POLICY_VERSION},
    )
    return _CreditOutcome(True, result.to_dict())


def _apply_grammar_credit(
    db: Session,
    *,
    user: User,
    target: TargetRef,
    evidence_kind: EvidenceKind,
    now: datetime,
) -> _CreditOutcome:
    """Grammar credit written through the caller's transaction.

    ``GrammarService.record_review`` commits, and the journey state machine owns
    the transaction boundary, so the same scoring rules are applied here without
    a commit. Learner-written notes are preserved exactly as that method does.
    """

    try:
        concept_id = int(target.id)
    except (TypeError, ValueError):
        return _CreditOutcome(False, {"skipped": "invalid_concept_id"})
    concept = db.get(GrammarConcept, concept_id)
    if concept is None or not concept.active:
        return _CreditOutcome(False, {"skipped": "concept_missing"})
    score = GRAMMAR_EVIDENCE_SCORE.get(evidence_kind)
    if score is None:
        return _CreditOutcome(False, {"skipped": "unscored"})

    progress = GrammarService(db).get_or_create_progress(user_id=user.id, concept_id=concept_id)
    progress.score = score
    progress.reps = (progress.reps or 0) + 1
    progress.last_review = now
    progress.next_review = now + calculate_next_review(score)
    progress.state = determine_state(score, progress.reps)
    note = f"[{JOURNEY_SOURCE_TYPE}] {evidence_kind}"
    if not is_machine_note(note) or not personal_note(progress.notes):
        progress.notes = note
    progress.updated_at = now
    db.add(progress)
    db.flush([progress])
    return _CreditOutcome(
        True,
        {
            "concept_id": concept_id,
            "score": score,
            "state": progress.state,
            "next_review": progress.next_review.isoformat(),
        },
    )


def _apply_error_credit(
    db: Session,
    *,
    user: User,
    target: TargetRef,
    evidence_kind: EvidenceKind,
) -> _CreditOutcome:
    try:
        error_id = UUID(str(target.id))
    except (TypeError, ValueError):
        return _CreditOutcome(False, {"skipped": "invalid_error_id"})
    review = ERROR_EVIDENCE_REVIEW.get(evidence_kind)
    if review is None:
        return _CreditOutcome(False, {"skipped": "unscored"})
    rating, repaired = review
    reviewed = ErrorMemoryService(db).review_error(
        user=user, error_id=error_id, rating=rating, repaired=repaired
    )
    if reviewed is None:
        return _CreditOutcome(False, {"skipped": "error_missing"})
    db.flush([reviewed])
    return _CreditOutcome(
        True,
        {
            "error_id": str(reviewed.id),
            "rating": rating,
            "repaired": repaired,
            "state": reviewed.state,
            "next_review_date": (
                reviewed.next_review_date.isoformat() if reviewed.next_review_date else None
            ),
        },
    )


def _credit_for(
    db: Session,
    *,
    user: User,
    observation: TargetObservation,
    evidence_kind: EvidenceKind,
    session: LearningSession,
    source_key: str,
    now: datetime,
) -> _CreditOutcome:
    if evidence_kind is EvidenceKind.UNSCORED:
        return _CreditOutcome(False, {"skipped": "unscored"})
    if evidence_kind is EvidenceKind.NOT_YET and not normalize_answer_text(observation.learner_text):
        # No utterance, no obligation evidence: keep the schedule as it is.
        return _CreditOutcome(False, {"skipped": "no_elicitation_evidence"})
    target = observation.target
    if target.kind is TargetKind.VOCABULARY:
        return _apply_vocabulary_credit(
            db,
            user=user,
            target=target,
            evidence_kind=evidence_kind,
            observation=observation,
            session=session,
            source_key=source_key,
        )
    if target.kind is TargetKind.GRAMMAR:
        return _apply_grammar_credit(
            db, user=user, target=target, evidence_kind=evidence_kind, now=now
        )
    if target.kind is TargetKind.ERROR:
        return _apply_error_credit(db, user=user, target=target, evidence_kind=evidence_kind)
    return _CreditOutcome(False, {"skipped": "unknown_target_kind"})


def _record_correction_erratum(
    db: Session,
    *,
    user: User,
    session: LearningSession,
    correction: Correction,
    modality: InputMode,
    source_key: str,
    foreground: bool,
) -> dict[str, Any] | None:
    return ErrorMemoryService(db).record_erratum(
        user=user,
        erratum={
            "display_label": f"Reprise : {correction.span_fr}"[:120],
            "learner_text": correction.span_fr,
            "corrected_target": correction.corrected_fr,
            "why_wrong": correction.note_native or "Cette forme demande une reprise.",
            "repair_hint": correction.corrected_fr,
            "severity": 2,
            "recurring": True,
            "task_error_type": "journey_correction",
            "external_id": None,
        },
        source_type=JOURNEY_SOURCE_TYPE,
        learning_session_id=session.id,
        source_payload={
            "source_key": source_key,
            "policy_version": JOURNEY_LEARNING_POLICY_VERSION,
            "modality": str(modality),
            "foreground": foreground,
        },
    )


def _objective_evidence_kind(
    *, outcome: TaskOutcome, assistance: AssistanceLevel
) -> EvidenceKind:
    """What the response turn itself proves, independently of any target.

    A met or partially met objective is an open production of the scenario's
    task; anything else is ``not_yet``. ``unscored`` never reaches here — an
    infrastructure failure returns before any row is written.
    """

    if outcome in (TaskOutcome.MET, TaskOutcome.PARTIALLY_MET):
        return classify_evidence(
            opportunity="open_production", is_correct=True, assistance=assistance
        )
    return EvidenceKind.NOT_YET


def _record_objective_evidence(
    db: Session,
    *,
    user: User,
    journey_id: UUID,
    step_id: UUID,
    session: LearningSession,
    evaluation: ResponseEvaluation,
    modality: InputMode,
    scenario_key: str | None,
    observed_on: date,
    resolved_tz: str | None,
    now: datetime,
) -> tuple[str, UUID | None, bool]:
    """Record the response turn as a capability opportunity in its own right.

    WP-09 counts the *turn*, not the target (CONTRACTS §8), so a learner who
    fulfils the objective without touching any tracked target must still leave
    an opportunity behind. Without this row such a turn is invisible to the
    rubric and the learner is reported ``not_tried`` for something they
    demonstrably did.

    Deliberately **not** a credit path: no scheduler write, no lapse, no
    vocabulary/grammar/error credit, no ``score_0_10``. ``srs_credit_applied``
    stays ``False``. The identity is
    ``journey:<journey>:<step>:objective:<scenario_key>:<evidence_kind>``, so
    the ordinary source-key dedup makes it replay-safe exactly like a target
    observation.

    Returns ``(source_key, moment_id, deduplicated)``.
    """

    target_id = str(scenario_key or OBJECTIVE_TARGET_FALLBACK)
    assistance = strongest_assistance(
        [
            evaluation.assistance,
            *[
                observation.assistance
                for observation in evaluation.observations
                if observation.assistance is not None
            ],
            *_prior_step_assistance(
                db,
                user=user,
                session=session,
                journey_id=journey_id,
                step_id=step_id,
                target_kind=OBJECTIVE_SOURCE_KIND,
                target_id=target_id,
            ),
        ]
    )
    evidence_kind = _objective_evidence_kind(
        outcome=evaluation.outcome, assistance=assistance
    )
    source_key = evidence_source_key(
        journey_id=journey_id,
        step_id=step_id,
        target_kind=OBJECTIVE_SOURCE_KIND,
        target_id=target_id,
        evidence_kind=str(evidence_kind),
    )
    existing = _existing_moment(db, user=user, source_key=source_key)
    if existing is not None:
        return source_key, existing.id, True

    is_open_production = evidence_kind in {
        EvidenceKind.PRODUCED_SUPPORTED,
        EvidenceKind.PRODUCED_INDEPENDENT,
    }
    moment = SessionLearningMoment(
        session_id=session.id,
        user_id=user.id,
        anchor_message_id=None,
        kind=JOURNEY_OBJECTIVE_MOMENT_KIND,
        source_type=JOURNEY_SOURCE_TYPE,
        source_id=_source_id_for(source_key),
        status="completed",
        prompt_payload={
            "policy_version": JOURNEY_LEARNING_POLICY_VERSION,
            "journey_id": str(journey_id),
            "step_id": str(step_id),
            "scenario_key": scenario_key,
            "source_key": source_key,
            "evidence_scope": OBJECTIVE_SOURCE_KIND,
            "assistance_level": str(assistance),
            "modality": str(modality),
            "task_outcome": str(evaluation.outcome),
            "observed_on": observed_on.isoformat(),
            "timezone": resolved_tz,
        },
        completed_at=now,
    )
    db.add(moment)
    db.flush([moment])
    # Capability evidence only: no credit was applied and none may be inferred
    # from this row, so it carries no score.
    moment.srs_credit_applied = False
    moment.score_0_10 = None
    moment.result_payload = {
        "evidence_kind": str(evidence_kind),
        "assistance_level": str(assistance),
        "modality": str(modality),
        "is_open_production": is_open_production,
        "evidence_scope": OBJECTIVE_SOURCE_KIND,
        "credit": {"skipped": "objective_evidence_is_not_scheduled"},
    }
    flag_modified(moment, "result_payload")
    db.add(moment)
    db.flush([moment])
    return source_key, moment.id, False


def apply_learning_evidence(
    db: Session,
    *,
    user: User,
    journey_id: UUID,
    step_id: UUID,
    session: LearningSession,
    evaluation: RecallEvaluation | ResponseEvaluation,
    modality: InputMode,
    timezone: str | None = None,
    now: datetime | None = None,
) -> AppliedEvidence:
    """Write one step's evidence into the canonical records, exactly once.

    Writes through the caller's session and never commits. Each observation
    claims its ``evidence_source_key`` with a :class:`SessionLearningMoment`
    row; a replay of the same key (HTTP retry, worker retry, another surface)
    returns the same result with the key in ``deduplicated_source_keys`` and
    applies no second credit.

    Progress is re-read at write time, so independent practice between planning
    and submission is respected: credit lands on the learner's current state,
    never on a stale queue snapshot.
    """

    now = now or datetime.now(UTC)
    observed_on, resolved_tz = _local_date(now, timezone)
    evidence_ref = f"journey:{journey_id}:{step_id}"

    source_keys: list[str] = []
    deduplicated: list[str] = []
    applied_target_ids: list[str] = []
    first_moment_id: UUID | None = None
    # CONTRACTS §7: one response must not manufacture several punishment
    # events. A vocabulary lapse already writes the erratum that carries the
    # learner's text and the target form, so the foreground correction is shown
    # but not booked a second time.
    punishment_recorded = False

    if evaluation.pending or evaluation.outcome is TaskOutcome.UNSCORED:
        # Infrastructure failure. No attempt, no lapse, no credit, no row.
        logger.info(
            "journey_evidence_unscored",
            user_id=str(user.id),
            journey_id=str(journey_id),
            step_id=str(step_id),
            reason=getattr(evaluation, "failure_reason", None),
        )
        return AppliedEvidence(
            evidence_ref=evidence_ref,
            source_keys=[],
            applied_target_ids=[],
            deduplicated_source_keys=[],
            learning_session_id=session.id,
            learning_moment_id=None,
        )

    scenario_key = session.scenario
    for observation in evaluation.observations:
        evidence_kind, assistance = _resolve_evidence_kind(
            db,
            user=user,
            session=session,
            journey_id=journey_id,
            step_id=step_id,
            observation=observation,
        )
        source_key = evidence_source_key(
            journey_id=journey_id,
            step_id=step_id,
            target_kind=str(observation.target.kind),
            target_id=observation.target.id,
            evidence_kind=str(evidence_kind),
        )
        source_keys.append(source_key)
        applied_target_ids.append(observation.target.id)

        existing = _existing_moment(db, user=user, source_key=source_key)
        if existing is not None:
            deduplicated.append(source_key)
            if first_moment_id is None:
                first_moment_id = existing.id
            continue

        moment = SessionLearningMoment(
            session_id=session.id,
            user_id=user.id,
            anchor_message_id=None,
            kind=JOURNEY_MOMENT_KIND_BY_TARGET.get(observation.target.kind, "journey_evidence"),
            source_type=JOURNEY_SOURCE_TYPE,
            source_id=_source_id_for(source_key),
            status="completed",
            prompt_payload={
                "policy_version": JOURNEY_LEARNING_POLICY_VERSION,
                "journey_id": str(journey_id),
                "step_id": str(step_id),
                "scenario_key": scenario_key,
                "source_key": source_key,
                "target": observation.target.as_public(),
                "assistance_level": str(assistance),
                "modality": str(observation.modality or modality),
                "task_outcome": str(evaluation.outcome),
                "observed_on": observed_on.isoformat(),
                "timezone": resolved_tz,
            },
            completed_at=now,
        )
        db.add(moment)
        db.flush([moment])

        credit = _credit_for(
            db,
            user=user,
            observation=observation,
            evidence_kind=evidence_kind,
            session=session,
            source_key=source_key,
            now=now,
        )
        moment.srs_credit_applied = credit.applied
        punishment_recorded = punishment_recorded or bool(credit.detail.get("erratum_id"))
        moment.score_0_10 = _score_for(evidence_kind)
        moment.result_payload = {
            "evidence_kind": str(evidence_kind),
            "assistance_level": str(assistance),
            "modality": str(observation.modality or modality),
            "is_open_production": evidence_kind
            in {EvidenceKind.PRODUCED_SUPPORTED, EvidenceKind.PRODUCED_INDEPENDENT},
            "learner_text": observation.learner_text,
            "corrected_text": observation.corrected_text,
            "credit": credit.detail,
        }
        flag_modified(moment, "result_payload")
        db.add(moment)
        db.flush([moment])
        if first_moment_id is None:
            first_moment_id = moment.id

    if isinstance(evaluation, ResponseEvaluation) and not evaluation.observations:
        # The turn fulfilled (or failed) the scenario's objective without
        # touching a tracked target. WP-09 counts turns, so record the turn.
        objective_key, objective_moment_id, objective_seen = _record_objective_evidence(
            db,
            user=user,
            journey_id=journey_id,
            step_id=step_id,
            session=session,
            evaluation=evaluation,
            modality=modality,
            scenario_key=scenario_key,
            observed_on=observed_on,
            resolved_tz=resolved_tz,
            now=now,
        )
        source_keys.append(objective_key)
        if objective_seen:
            deduplicated.append(objective_key)
        if first_moment_id is None:
            first_moment_id = objective_moment_id

    correction = getattr(evaluation, "correction", None)
    # Defence in depth. The evaluator already filtered the correction against
    # the learner's answer; here the answer is only available through the
    # observations, so re-check the span whenever one carries it, and always
    # re-check the no-op rule.
    learner_text = next(
        (
            observation.learner_text
            for observation in evaluation.observations
            if normalize_answer_text(observation.learner_text)
        ),
        None,
    )
    if correction is not None and validate_correction(
        correction, learner_text if learner_text else correction.span_fr
    ):
        correction_key = evidence_source_key(
            journey_id=journey_id,
            step_id=step_id,
            target_kind=CORRECTION_SOURCE_KIND,
            target_id=hashlib.sha256(
                f"{correction.span_fr}->{correction.corrected_fr}".encode()
            ).hexdigest()[:16],
            evidence_kind=str(EvidenceKind.NOT_YET),
        )
        source_keys.append(correction_key)
        existing_correction = _existing_moment(db, user=user, source_key=correction_key)
        if existing_correction is not None:
            deduplicated.append(correction_key)
            if first_moment_id is None:
                first_moment_id = existing_correction.id
        else:
            moment = SessionLearningMoment(
                session_id=session.id,
                user_id=user.id,
                anchor_message_id=None,
                kind=JOURNEY_CORRECTION_MOMENT_KIND,
                source_type=JOURNEY_SOURCE_TYPE,
                source_id=_source_id_for(correction_key),
                status="completed",
                prompt_payload={
                    "policy_version": JOURNEY_LEARNING_POLICY_VERSION,
                    "journey_id": str(journey_id),
                    "step_id": str(step_id),
                    "scenario_key": scenario_key,
                    "source_key": correction_key,
                    "assistance_level": str(evaluation.assistance),
                    "modality": str(modality),
                    "observed_on": observed_on.isoformat(),
                    "timezone": resolved_tz,
                },
                completed_at=now,
            )
            db.add(moment)
            db.flush([moment])
            erratum = None
            if not punishment_recorded:
                erratum = _record_correction_erratum(
                    db,
                    user=user,
                    session=session,
                    correction=correction,
                    modality=modality,
                    source_key=correction_key,
                    foreground=True,
                )
                punishment_recorded = bool(erratum)
            moment.srs_credit_applied = bool(erratum)
            moment.result_payload = {
                "span_fr": correction.span_fr,
                "corrected_fr": correction.corrected_fr,
                "note_native": correction.note_native,
                "erratum": erratum,
                "suppressed_reason": None if erratum else "one_punishment_event_per_turn",
            }
            flag_modified(moment, "result_payload")
            db.add(moment)
            db.flush([moment])
            if first_moment_id is None:
                first_moment_id = moment.id

    logger.info(
        "journey_evidence_applied",
        user_id=str(user.id),
        journey_id=str(journey_id),
        step_id=str(step_id),
        source_keys=len(source_keys),
        deduplicated=len(deduplicated),
    )
    return AppliedEvidence(
        evidence_ref=evidence_ref,
        source_keys=source_keys,
        applied_target_ids=applied_target_ids,
        deduplicated_source_keys=deduplicated,
        learning_session_id=session.id,
        learning_moment_id=first_moment_id,
    )


def _score_for(evidence_kind: EvidenceKind) -> float | None:
    return {
        EvidenceKind.RECOGNIZED: 6.0,
        EvidenceKind.PRODUCED_SUPPORTED: 7.5,
        EvidenceKind.PRODUCED_INDEPENDENT: 9.0,
        EvidenceKind.NOT_YET: 2.0,
    }.get(evidence_kind)


# --------------------------------------------------------------------------
# 6. Evidence metadata for WP-09 and next-day planning
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class JourneyEvidenceRecord:
    """One readable observation. ``None`` means *unknown*, never *independent*.

    ``target`` is ``None`` on an objective-level record (``is_objective``): the
    scenario's response turn is an opportunity in its own right and belongs to
    no schedulable item. Anything that credits a schedule must skip those rows.
    """

    target: TargetRef | None
    evidence_kind: EvidenceKind | None
    assistance: AssistanceLevel | None
    modality: InputMode | None
    observed_on: date
    task_outcome: TaskOutcome | None
    journey_id: UUID | None
    step_id: UUID | None
    scenario_key: str | None
    capability_key: CapabilityKey | None
    source_key: str | None
    is_open_production: bool
    learning_session_id: UUID | None
    timezone: str | None = None
    is_legacy: bool = False
    #: True for the turn-level record of a response step. Capability evidence
    #: only: it never carried credit and it names no target.
    is_objective: bool = False
    #: The exact instant the observation was recorded. `observed_on` is the
    #: learner-local *date*; this is what orders two observations inside one
    #: day, and inside one database transaction, where `created_at` cannot
    #: (Postgres gives every row in a transaction the same `now()`).
    observed_at: datetime | None = None

    @property
    def assistance_known(self) -> bool:
        return self.assistance is not None


_LEGACY_KIND_TO_TARGET: dict[str, TargetKind] = {
    "vocab_check": TargetKind.VOCABULARY,
    "vocab_boost": TargetKind.VOCABULARY,
    "grammar_challenge": TargetKind.GRAMMAR,
    "grammar_repair": TargetKind.GRAMMAR,
    "error_repair": TargetKind.ERROR,
}


def _enum_or_none(enum_cls, value):  # noqa: ANN001, ANN202 - tiny local helper
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return None


def read_journey_evidence(
    db: Session,
    *,
    user: User,
    journey_ids: Sequence[UUID] | None = None,
    scenario_keys: Sequence[str] | None = None,
    since: date | None = None,
    include_legacy: bool = False,
    limit: int = 500,
) -> list[JourneyEvidenceRecord]:
    """Per-target, per-capability evidence for WP-09 and next-day selection.

    Returns evidence kind, assistance level, modality (``text``/``voice``) and
    the learner-local observation date, so the CONTRACTS §8 rubric can be built
    without re-deriving policy here.

    ``include_legacy=True`` also returns pre-V2 learning moments. Those rows
    carry no recorded help usage, so their ``evidence_kind`` and ``assistance``
    come back as ``None`` — reportable as *unknown*. Independence is never
    inferred from a legacy success boolean.
    """

    query = (
        db.query(SessionLearningMoment, LearningSession)
        .join(LearningSession, SessionLearningMoment.session_id == LearningSession.id)
        .filter(
            SessionLearningMoment.user_id == user.id,
            SessionLearningMoment.status == "completed",
        )
    )
    if not include_legacy:
        query = query.filter(SessionLearningMoment.source_type == JOURNEY_SOURCE_TYPE)
    if scenario_keys:
        query = query.filter(LearningSession.scenario.in_([str(key) for key in scenario_keys]))
    if journey_ids:
        # Every moment of a journey lives in that journey's own LearningSession,
        # so the marker filters in SQL rather than after the row limit.
        query = query.filter(
            LearningSession.topic.in_([journey_session_topic(value) for value in journey_ids])
        )
    rows = (
        query.order_by(
            SessionLearningMoment.completed_at.desc().nullslast(),
            SessionLearningMoment.created_at.desc(),
        )
        .limit(max(1, limit))
        .all()
    )

    wanted = {str(value) for value in journey_ids} if journey_ids else None
    records: list[JourneyEvidenceRecord] = []
    for moment, learning_session in rows:
        prompt = moment.prompt_payload if isinstance(moment.prompt_payload, dict) else {}
        result = moment.result_payload if isinstance(moment.result_payload, dict) else {}
        is_journey = moment.source_type == JOURNEY_SOURCE_TYPE

        if is_journey and moment.kind == JOURNEY_CORRECTION_MOMENT_KIND:
            continue
        if is_journey and wanted is not None and str(prompt.get("journey_id")) not in wanted:
            continue

        if is_journey:
            is_objective = moment.kind == JOURNEY_OBJECTIVE_MOMENT_KIND
            target: TargetRef | None = None
            if not is_objective:
                raw_target = prompt.get("target") or {}
                kind = _enum_or_none(TargetKind, raw_target.get("kind"))
                if kind is None or not raw_target.get("id"):
                    continue
                target = TargetRef(
                    kind=kind,
                    id=str(raw_target.get("id")),
                    label_fr=str(raw_target.get("label_fr") or ""),
                    label_native=raw_target.get("label_native"),
                )
            observed_raw = prompt.get("observed_on")
            observed_at = _as_utc(moment.completed_at or moment.created_at)
            try:
                observed_on = date.fromisoformat(str(observed_raw))
            except (TypeError, ValueError):
                observed_on = (observed_at or datetime.now(UTC)).date()
            record = JourneyEvidenceRecord(
                target=target,
                evidence_kind=_enum_or_none(EvidenceKind, result.get("evidence_kind")),
                assistance=_enum_or_none(AssistanceLevel, prompt.get("assistance_level")),
                modality=_enum_or_none(InputMode, prompt.get("modality")),
                observed_on=observed_on,
                task_outcome=_enum_or_none(TaskOutcome, prompt.get("task_outcome")),
                journey_id=_uuid_or_none(prompt.get("journey_id")),
                step_id=_uuid_or_none(prompt.get("step_id")),
                scenario_key=prompt.get("scenario_key") or learning_session.scenario,
                capability_key=_enum_or_none(
                    CapabilityKey, prompt.get("scenario_key") or learning_session.scenario
                ),
                source_key=prompt.get("source_key"),
                is_open_production=bool(result.get("is_open_production")),
                learning_session_id=learning_session.id,
                timezone=prompt.get("timezone"),
                is_legacy=False,
                observed_at=observed_at,
                is_objective=is_objective,
            )
        else:
            kind = _LEGACY_KIND_TO_TARGET.get(moment.kind or "")
            if kind is None or not moment.source_id:
                continue
            observed = _as_utc(moment.completed_at or moment.created_at) or datetime.now(UTC)
            record = JourneyEvidenceRecord(
                target=TargetRef(
                    kind=kind,
                    id=str(moment.source_id),
                    label_fr=str((moment.prompt_payload or {}).get("title") or ""),
                    label_native=None,
                ),
                # Pre-V2 rows never recorded help usage. Unknown, not independent.
                evidence_kind=None,
                assistance=None,
                modality=None,
                observed_on=observed.date(),
                task_outcome=None,
                journey_id=None,
                step_id=None,
                scenario_key=learning_session.scenario,
                capability_key=None,
                source_key=None,
                is_open_production=False,
                learning_session_id=learning_session.id,
                timezone=None,
                is_legacy=True,
                observed_at=observed,
            )
        if since is not None and record.observed_on < since:
            continue
        records.append(record)
    return records


def _uuid_or_none(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


__all__ = [
    "BACKGROUND_ERRATA_CAP",
    "CANDIDATE_HISTORY_LIMIT",
    "CANDIDATE_SECONDS",
    "EVIDENCE_HISTORY_NONE",
    "EVIDENCE_HISTORY_RECORDED",
    "EVIDENCE_HISTORY_UNKNOWN",
    "EVIDENCE_STRENGTH",
    "CORRECTION_SOURCE_KIND",
    "JOURNEY_CORRECTION_MOMENT_KIND",
    "JOURNEY_LEARNING_POLICY_VERSION",
    "JOURNEY_MOMENT_KINDS",
    "JOURNEY_MOMENT_KIND_BY_TARGET",
    "JOURNEY_OBJECTIVE_MOMENT_KIND",
    "OBJECTIVE_SOURCE_KIND",
    "JOURNEY_SESSION_STYLE",
    "JOURNEY_SESSION_TOPIC_PREFIX",
    "JOURNEY_SOURCE_TYPE",
    "JourneyEvidenceRecord",
    "OpportunityKind",
    "answer_matches",
    "apply_learning_evidence",
    "build_correction",
    "classify_evidence",
    "classify_observation",
    "correction_relevance",
    "ensure_journey_learning_session",
    "evaluate_recall",
    "fold_for_comparison",
    "is_infrastructure_failure",
    "journey_session_topic",
    "read_journey_evidence",
    "select_foreground_correction",
    "select_learning_candidates",
    "unscored_recall_evaluation",
    "validate_correction",
]
