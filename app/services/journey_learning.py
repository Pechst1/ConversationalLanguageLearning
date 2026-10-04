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

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.srs.memory import Evidence, EvidenceFormat, format_for_name
from app.db.models.grammar import GrammarConcept
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.error_memory import ErrorMemoryService
from app.services.glosses import word_gloss
from app.services.grammar import (
    GrammarService,
    apply_grammar_evidence,
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
    article_optional,
    evidence_source_key,
    normalize_answer_text,
    split_article,
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
#: WP-78. A ``limit`` above ``MAX_DUE_CANDIDATES + MAX_NEW_CANDIDATES`` is a
#: practice day asking for its pool: up to this many new scene words, the rest
#: due items. The planner still elicits at most two due targets and one new
#: anchor in the reply — the extra candidates become quick items.
MAX_PRACTICE_NEW_CANDIDATES = 2
#: Words the learner kept from a story (tap-to-keep) that are not due yet are
#: still offered, this many at most, so a kept word comes back the next day.
MAX_KEPT_EXTRA_CANDIDATES = 2
#: WP-78. Words the learner already owns, offered to a practice day as the
#: *other* cards of a matching or listen-and-tap item — never as a target, so
#: they gain no evidence and no schedule moves (``metadata["partner_only"]``).
MAX_PARTNER_WORDS = 5
#: WP-78. When too little is due for a practice day, *fragile* words — ones the
#: learner has studied that come due within this window — fill the quick items
#: (CONTRACTS §9 already names due **or fragile** targets). Recognition only is
#: credited for them, and nothing is rescheduled until the learner answers.
FRAGILE_WINDOW_DAYS = 2
PRACTICE_TARGET_POOL = 5

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

#: WP-L3: what each journey observation proves, on the one evidence ladder
#: (`app.core.srs.memory`), for a grammar concept and an erratum alike. A journey target is posed inside the scene's reply,
#: so producing it is free production (with or without help), and getting it
#: wrong there is a lapse.
JOURNEY_EVIDENCE: dict[EvidenceKind, Evidence] = {
    EvidenceKind.RECOGNIZED: Evidence(EvidenceFormat.RECOGNISE, correct=True),
    EvidenceKind.PRODUCED_SUPPORTED: Evidence(EvidenceFormat.PRODUCE, correct=True, assisted=True),
    EvidenceKind.PRODUCED_INDEPENDENT: Evidence(EvidenceFormat.PRODUCE, correct=True),
    EvidenceKind.NOT_YET: Evidence(EvidenceFormat.PRODUCE, correct=False),
}


def grammar_journey_evidence(
    evidence_kind: EvidenceKind,
    *,
    task_format: str | None = None,
    assistance: AssistanceLevel = AssistanceLevel.NONE,
) -> Evidence:
    """WP-L4: what one journey observation proves about a grammar unit.

    A reply (no format) is free production (:data:`JOURNEY_EVIDENCE`). A
    recall item proves what its format proves: a pick is recognition, tiles and
    a word bank are guided, a transform is a transform — so an intro day's
    guided items write weak and medium evidence, and only the reply writes
    strong evidence. A wrong answer in an easier format is a Hard, not a lapse.
    """

    fmt = format_for_name(task_format) if task_format else None
    if fmt is None or fmt is EvidenceFormat.PRODUCE:
        return JOURNEY_EVIDENCE[evidence_kind]
    return Evidence(
        fmt,
        correct=evidence_kind is not EvidenceKind.NOT_YET,
        assisted=strongest_assistance([assistance]) is not AssistanceLevel.NONE
        or evidence_kind is EvidenceKind.PRODUCED_SUPPORTED,
    )


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

    from app.services.answer_acceptance import fold_all

    # EXERCISE-QA: «œ»/«æ» are spelled out first («sœur» = «soeur»); the old
    # fold dropped them, so a German keyboard's «soeur» was graded wrong.
    text = fold_all(normalize_answer_text(value))
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


#: An answer may hold the accepted one inside a short frame («c'est un
#: appartement», «Bonjour, un café, s'il vous plaît, merci»): at most this many
#: extra words, or as many as the answer itself has. «euh je ne sais pas» is not
#: an answer of «pas» (the learner walk found it graded right).
CONTAINED_ANSWER_PADDING = 2


def _recall_accent_policy(db: Session | None, task: RecallTask) -> str:
    """QA-CLOSE (owner decision c): accents are strict on a spelling unit's items
    (``FR2_A12_ER_SPELLING``) and on an item whose source or options differ from
    the key by accents alone; lenient-but-named everywhere else."""

    from app.services.answer_acceptance import accent_policy

    unit = None
    if db is not None and task.target.kind == TargetKind.GRAMMAR and str(task.target.id).isdigit():
        try:
            from app.db.models.grammar import GrammarConcept

            concept = db.get(GrammarConcept, int(task.target.id))
            unit = getattr(concept, "external_id", None)
        except Exception:  # noqa: BLE001 - a policy lookup never fails a grade
            unit = None
    keys = _accepted_answers(task)
    others = [task.source_fr, *(str(option.get("text") or option.get("label_fr") or "") for option in task.options or [])]
    return accent_policy(unit=unit, target=keys[0] if keys else None, others=[o for o in others if o])


def answer_matches(
    answer: str | None,
    accepted: Iterable[str | None],
    *,
    accents: str = "lenient",
    within_reply: bool = False,
) -> bool:
    """Is this a reasonable rendering of one of the accepted answers?

    EXERCISE-QA: the one acceptance contract (``answer_acceptance.judge``) —
    typography never counts, an accent slip is forgiven unless the accent is
    grammar (a/à, ou/où, a final «-é»), one typo is forgiven unless it makes
    another form («parle/parles», «du/de» never pass). A word or short phrase
    also counts when the answer holds it as a run of words.
    """

    from app.services.answer_acceptance import judge

    folded = fold_for_comparison(answer)
    if not folded:
        return False
    answer_tokens = folded.split()
    for candidate in accepted:
        target = fold_for_comparison(candidate)
        if not target:
            continue
        if judge(answer, [candidate], accents=accents).correct:
            return True
        target_tokens = target.split()
        # A recall answer may frame the key in a few words; a free reply
        # (``within_reply``: a target used in the learner's own sentence) may be
        # any length — «Un café en terrasse, s'il vous plaît» uses «en terrasse».
        short_enough = within_reply or len(answer_tokens) <= len(target_tokens) + max(
            CONTAINED_ANSWER_PADDING, len(target_tokens)
        )
        if short_enough and _contains_run(answer_tokens, target_tokens):
            if judge(" ".join(_original_run(answer, len(target_tokens), target_tokens)), [candidate], accents=accents).correct:
                return True
    return False


def _original_run(answer: str | None, length: int, target_tokens: list[str]) -> list[str]:
    """The learner's own words (accents as typed) that fold to ``target_tokens``."""

    from app.services.answer_acceptance import fold_typography

    words = fold_typography(answer).replace("'", "' ").split()
    folded = [fold_for_comparison(word) for word in words]
    for start in range(len(words) - length + 1):
        if folded[start : start + length] == target_tokens:
            return words[start : start + length]
    return words


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
        # WP-L1: `display_title` is the English catalogue name. The chip is
        # French and its gloss is in the learner's own language.
        return TargetRef(
            kind=TargetKind.GRAMMAR,
            id=str(concept_id),
            label_fr=metadata.get("title_fr") or item.display_title,
            label_native=metadata.get("title_native") or item.display_title or None,
            concept_title=True,
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


#: WP-L6. A word is *held* once its memory stability reaches three weeks;
#: below that, a word the learner has reviewed is "drilled but not held" and a
#: scene or a recall prefers it (§5.1). A planning prior until WP-L3's
#: held rule lands.
HELD_STABILITY_DAYS = 21.0


def drilled_not_held(candidate: LearningCandidate) -> bool:
    """A vocabulary target the learner has reviewed but does not hold yet."""

    if candidate.target.kind is not TargetKind.VOCABULARY or candidate.is_new:
        return False
    metadata = candidate.metadata or {}
    if metadata.get("fragile"):
        return True
    try:
        stability = float(metadata.get("stability") or 0.0)
    except (TypeError, ValueError):
        return False
    state = str(metadata.get("state") or "").lower()
    return state not in {"", "new"} and stability < HELD_STABILITY_DAYS


def _mark_story_need(candidate: LearningCandidate) -> LearningCandidate:
    """WP-115c: a word today's story needs from the learner — fully relevant, so the
    planner ranks it first and the reply may require it."""

    from dataclasses import replace

    return replace(candidate, relevance=1.0, metadata={**(candidate.metadata or {}), "story_need": True})


def select_learning_candidates(
    db: Session,
    *,
    user: User,
    scenario: ScenarioBrief,
    limit: int = 3,
    now: datetime | None = None,
    new_word_quota: int | None = None,
    budget_seconds: int | None = None,
) -> list[LearningCandidate]:
    """Existing due/fragile identities the learner already owns, ranked for this scene.

    WP-L4: on a practice day the due grammar units come from the one Rappel
    queue (``UnifiedSRSService.plan_review_items``), at most
    :func:`grammar_rappel_room` of them, and every grammar candidate carries
    its unit brief (``metadata["grammar_brief"]``) so the planner can pose it.

    Read-only. No due date is moved to fit a scene and nothing is marked
    reviewed: an omitted candidate stays exactly as due as it was. When the
    queue is genuinely empty the result is ``[]`` — no item is invented and
    nothing is claimed to be due.

    WP-L6: ``new_word_quota`` is what the learner's vocabulary pace leaves for
    today (:func:`app.services.vocabulary_pace.journey_new_word_room`): no more
    than that many ``is_new`` candidates are offered, so the day and the word
    drill never introduce more than the day's quota together. ``None`` keeps
    the pre-WP-L6 behaviour. Among equally relevant words, one the learner is
    drilling but does not hold yet comes first (§5.1): the story doubles as
    its review, and the reply gives it strong evidence.
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
                    for key in (
                        "word_id",
                        "concept_id",
                        "review_mode",
                        "state",
                        "lapses",
                        "stability",
                        # An erratum is posed as a repair of the learner's own
                        # wording; the planner needs it next to the target.
                        "original_text",
                    )
                    if key in (item.metadata or {})
                },
                **_history_metadata(history, target),
            },
        )
        scored.append(
            (
                -relevance,
                0 if drilled_not_held(candidate) else 1,
                -float(item.priority_score or 0.0),
                -int(item.due_since_days or 0),
                _exposure_sort_key(item),
                candidate,
            )
        )

    # WP-115c: the words today's story was written to need come first, and the reply
    # may require them — the scene is built around retrieving them.
    story_ids = {
        str(row.get("word_id"))
        for row in ((getattr(scenario, "story_context", None) or {}).get("story_words") or [])
        if isinstance(row, dict) and row.get("word_id") is not None
    }
    if story_ids:
        scored = [
            (
                (-1.0, -1, *row[2:5], _mark_story_need(row[5]))
                if row[5].target.kind is TargetKind.VOCABULARY and row[5].target.id in story_ids
                else row
            )
            for row in scored
        ]
    practice = limit > MAX_DUE_CANDIDATES + MAX_NEW_CANDIDATES
    kept = _kept_words(db, user=user, now=now) if practice else {}
    if kept:
        scored = [
            (
                (-1.0, *row[1:5], _mark_kept(row[5], kept))
                if _kept_id(row[5]) in kept
                else row
            )
            for row in scored
        ]
    scored.sort(key=lambda row: row[:5])
    if practice:
        new_room = MAX_PRACTICE_NEW_CANDIDATES
        due_cap = max(MAX_DUE_CANDIDATES, limit - new_room)
    else:
        new_room = MAX_NEW_CANDIDATES
        due_cap = min(MAX_DUE_CANDIDATES, limit)
    selected = [row[5] for row in scored[:due_cap]]

    if practice and kept:
        # A kept word that is not due yet still comes back tomorrow: keeping it
        # was the learner asking to see it again.
        present = {c.target.id for c in selected if c.target.kind is TargetKind.VOCABULARY}
        extras = _kept_extra_candidates(
            db, user=user, kept=kept, exclude=present, history=history
        )
        selected = extras[:MAX_KEPT_EXTRA_CANDIDATES] + selected

    # WP-86: the scene's words are recorded on every day (the director's
    # lexicon history reads them back); they are *practised* on a practice day.
    lexicon = _scene_lexicon_candidates(
        db,
        user=user,
        scenario=scenario,
        exclude={c.target.id for c in selected if c.target.kind is TargetKind.VOCABULARY},
        history=history,
    )
    lexicon = lexicon if practice else []
    if new_word_quota is not None:
        # WP-L6: the scene's new words past the day's quota stay in the scene,
        # read and glossed, but are not introduced today.
        admitted = 0
        within: list[LearningCandidate] = []
        for candidate in lexicon:
            if candidate.is_new:
                if admitted >= new_word_quota:
                    continue
                admitted += 1
            within.append(candidate)
        lexicon = within
        new_room = min(new_room, max(0, new_word_quota - admitted))
    selected.extend(lexicon)
    # WP-86: the scene's own words are today's new anchors; a scene that named
    # none still gets the classic one looked up from its text.
    new_cap = 0 if lexicon else min(new_room, limit - len(selected))
    for _ in range(max(0, new_cap)):
        anchor = _new_vocabulary_anchor(
            db,
            user=user,
            scenario=scenario,
            terms=terms,
            exclude={(str(c.target.kind), c.target.id) for c in selected},
            history=history,
        )
        if anchor is None:
            break
        selected.append(anchor)
    if practice:
        targets = sum(1 for c in selected if not (c.metadata or {}).get("partner_only"))
        # WP-L6: a longer rhythm asks for a larger pool, and the fragile shelf
        # (drilled, not held) fills it.
        pool_target = max(PRACTICE_TARGET_POOL, limit - MAX_PRACTICE_NEW_CANDIDATES - 1)
        if targets < pool_target:
            selected.extend(
                _fragile_words(
                    db,
                    user=user,
                    now=now,
                    exclude={
                        c.target.id for c in selected if c.target.kind is TargetKind.VOCABULARY
                    },
                    room=pool_target - targets,
                    history=history,
                )
            )
        selected.extend(
            _partner_words(
                db,
                user=user,
                exclude={c.target.id for c in selected if c.target.kind is TargetKind.VOCABULARY},
            )
        )
        selected = _with_grammar_rappel(
            db, user=user, selected=selected, now=now, budget_seconds=budget_seconds
        )
        selected = _with_practice_units(
            db, user=user, selected=selected, scenario=scenario, now=now,
            budget_seconds=budget_seconds,
        )
    selected = _one_target_per_word(selected)
    if scenario.control_language == "fr" and user.native_language != "fr":
        # The catalogue's stored translation is English/German. French tasks
        # use the scene's sentence instead of posing that foreign gloss.
        selected = [replace(candidate, target=replace(candidate.target, label_native=None))
                    if candidate.target.kind is TargetKind.VOCABULARY else candidate
                    for candidate in selected]
    else:
        selected = _glosses_in_language(db, selected, str(scenario.control_language))
    return _with_grammar_briefs(db, user=user, candidates=selected)


def _one_target_per_word(candidates: list[LearningCandidate]) -> list[LearningCandidate]:
    """QA-PRACTICE: the scene's «appartement» and the deck's «un appartement» are
    one word. Two targets for it made a day ask its gender twice and put both in
    one matching grid. The first (the higher-ranked source) is kept."""

    seen: set[str] = set()
    kept: list[LearningCandidate] = []
    for candidate in candidates:
        if candidate.target.kind is TargetKind.VOCABULARY:
            _article, noun = split_article(candidate.target.label_fr)
            key = fold_for_comparison(noun)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
        kept.append(candidate)
    return kept


def _glosses_in_language(
    db: Session, candidates: list[LearningCandidate], language: str
) -> list[LearningCandidate]:
    """QA-PRACTICE: a German learner was asked «Welcher französische Ausdruck
    bedeutet „a letter“?» — ``word_gloss`` falls back to another language's gloss
    when the learner's own is missing, which is right for a word list and wrong
    for a question. A vocabulary gloss that is a catalogue row's gloss *in
    another language* is replaced by the row's own-language gloss, or dropped
    (the planner then poses the word in a format that needs no meaning)."""

    from app.services.glosses import _GLOSS_COLUMNS

    own_column = _GLOSS_COLUMNS.get(language)
    if own_column is None:
        return candidates
    ids = {
        int(candidate.target.id)
        for candidate in candidates
        if candidate.target.kind is TargetKind.VOCABULARY
        and candidate.target.label_native
        and str(candidate.target.id).isdigit()
    }
    if not ids:
        return candidates
    try:
        with db.begin_nested():
            words = {word.id: word for word in db.query(VocabularyWord).filter(VocabularyWord.id.in_(ids)).all()}
    except Exception:  # noqa: BLE001 - a gloss check never costs the day
        logger.warning("journey_learning_gloss_language_check_unavailable")
        return candidates
    checked: list[LearningCandidate] = []
    for candidate in candidates:
        target = candidate.target
        word = words.get(int(target.id)) if str(target.id).isdigit() else None
        if word is None or target.kind is not TargetKind.VOCABULARY or not target.label_native:
            checked.append(candidate)
            continue
        gloss = fold_for_comparison(target.label_native)
        own = " ".join(str(getattr(word, own_column, None) or "").split())
        foreign = {
            fold_for_comparison(getattr(word, column, None))
            for code, column in _GLOSS_COLUMNS.items()
            if code != language and getattr(word, column, None)
        }
        if gloss in foreign and gloss != fold_for_comparison(own):
            target = replace(target, label_native=own or None)
            candidate = replace(candidate, target=target)
        checked.append(candidate)
    return checked


#: WP-L4 — due grammar units a day's Rappel poses, by rhythm budget. One
#: interleaved item per unit (§2.4), and never more than the Réemploi's two a
#: day on the shortest rhythm's scale.
GRAMMAR_RAPPEL_ROOM: dict[int, int] = {300: 1, 600: 2, 1200: 3, 1800: 4}


def grammar_rappel_room(budget_seconds: int | None) -> int:
    from app.services.journey_contracts import rhythm_caps

    return GRAMMAR_RAPPEL_ROOM.get(rhythm_caps(budget_seconds).budget_seconds, 1)


def _with_grammar_rappel(
    db: Session,
    *,
    user: User,
    selected: list[LearningCandidate],
    now: datetime,
    budget_seconds: int | None,
) -> list[LearningCandidate]:
    """Due grammar from the one Rappel queue, in its interleaved order."""

    room = grammar_rappel_room(budget_seconds)
    present = {c.target.id for c in selected if c.target.kind is TargetKind.GRAMMAR}
    room -= len(present)
    if room <= 0:
        return selected
    try:
        queue = UnifiedSRSService(db).plan_review_items(
            user.id, budget_seconds=int(budget_seconds or 300), now=now
        )
    except Exception:  # pragma: no cover - a queue that cannot be read costs the items
        logger.exception("journey_grammar_rappel_unavailable")
        return selected
    extra: list[LearningCandidate] = []
    for item in queue:
        if item.item_type is not ItemType.GRAMMAR or room <= 0:
            continue
        target = _target_ref_for_item(item)
        if target is None or target.id in present:
            continue
        present.add(target.id)
        room -= 1
        extra.append(
            LearningCandidate(
                target=target,
                priority_score=float(item.priority_score or 0.0),
                due_since_days=int(item.due_since_days or 0),
                estimated_seconds=CANDIDATE_SECONDS[ItemType.GRAMMAR],
                is_new=False,
                relevance=0.0,
                source_item_type=str(item.item_type),
                metadata={
                    "queue_item_id": item.id,
                    "original_id": str(item.original_id),
                    "rappel": True,
                    **{
                        key: item.metadata.get(key)
                        for key in ("concept_id", "state", "lapses", "stability", "review_mode")
                        if key in (item.metadata or {})
                    },
                },
            )
        )
    return [*selected, *extra]


#: WP-129 (owner decision 4) — introduced units a B1+ practice day may also
#: practise in its free time (interleaved, contrasted with their partners), by
#: rhythm budget, besides the due Rappel units.
PRACTICE_UNIT_ROOM: dict[int, int] = {300: 2, 600: 5, 1200: 6, 1800: 8}
ADVANCED_PRACTICE_BANDS = frozenset({"B1", "B2", "C1", "C2"})


def _with_practice_units(
    db: Session,
    *,
    user: User,
    selected: list[LearningCandidate],
    scenario: ScenarioBrief,
    now: datetime,
    budget_seconds: int | None,
) -> list[LearningCandidate]:
    """WP-129: units the learner has *already been introduced to*, for a B1+ day.

    Marked ``practice_unit``: the planner never makes them a reply obligation;
    it poses them as mixed-unit practice after the ending (a contrast with a
    partner unit, a repair, a free sentence) while the day has time. Only
    units introduced before now (``concept_life``: first evidence or a rule
    read) — practising a unit never introduces one. First the units whose
    catalogue ``contrast_partners`` are introduced too, then the most recently
    introduced; a held unit last. Read-only.
    """

    band = str(getattr(scenario, "level_band", "") or "").upper()[:2]
    if band not in ADVANCED_PRACTICE_BANDS:
        return selected
    from app.db.models.grammar import UserGrammarProgress
    from app.services.grammar_catalog import concept_syllabus
    from app.services.journey_contracts import rhythm_caps

    room = PRACTICE_UNIT_ROOM.get(rhythm_caps(budget_seconds).budget_seconds, 2)
    present = {c.target.id for c in selected if c.target.kind is TargetKind.GRAMMAR}
    try:
        with db.begin_nested():
            rows = (
                db.query(UserGrammarProgress, GrammarConcept)
                .join(GrammarConcept, GrammarConcept.id == UserGrammarProgress.concept_id)
                .filter(
                    UserGrammarProgress.user_id == user.id,
                    UserGrammarProgress.introduced_at.isnot(None),
                    UserGrammarProgress.introduced_at < now,
                    GrammarConcept.active.is_(True),
                )
                .all()
            )
    except Exception:  # noqa: BLE001 - practice units are never worth the day
        logger.warning("journey_practice_units_unavailable")
        return selected
    introduced = {str(concept.external_id or ""): concept for _progress, concept in rows}

    def partnered(concept: GrammarConcept) -> bool:
        own = str(concept.external_id or "")
        named = concept_syllabus(concept).get("contrast_partners") or []
        if any(ref in introduced and ref != own for ref in named):
            return True
        return any(
            own in (concept_syllabus(other).get("contrast_partners") or [])
            for ref, other in introduced.items() if ref != own
        )

    def introduced_at(progress: Any) -> float:
        value = progress.introduced_at
        if value is None:
            return 0.0
        value = value if value.tzinfo else value.replace(tzinfo=UTC)
        return value.timestamp()

    rows.sort(
        key=lambda row: (
            0 if partnered(row[1]) else 1,
            1 if row[0].held_at is not None else 0,
            -introduced_at(row[0]),
            row[1].id,
        )
    )
    from app.services.chrome_language import user_chrome_language
    from app.services.grammar_units import localized_titles

    language = str(user_chrome_language(user))

    def titles(concept: GrammarConcept) -> dict[str, str]:
        try:
            return localized_titles(concept)
        except Exception:  # noqa: BLE001 - a title is a label, never the day
            return {}

    extra: list[LearningCandidate] = []
    for progress, concept in rows:
        if len(extra) >= room:
            break
        if str(concept.id) in present:
            continue
        present.add(str(concept.id))
        extra.append(
            LearningCandidate(
                target=TargetRef(
                    kind=TargetKind.GRAMMAR,
                    id=str(concept.id),
                    label_fr=titles(concept).get("fr") or str(concept.name or ""),
                    label_native=titles(concept).get(language) or str(concept.name or "") or None,
                    concept_title=True,
                ),
                priority_score=0.0,
                due_since_days=0,
                estimated_seconds=CANDIDATE_SECONDS[ItemType.GRAMMAR],
                is_new=False,
                relevance=0.0,
                source_item_type=str(ItemType.GRAMMAR),
                metadata={
                    "practice_unit": True,
                    "concept_id": concept.id,
                    "stability": float(progress.stability or 0.0),
                },
            )
        )
    return [*selected, *extra]


def _with_grammar_briefs(
    db: Session, *, user: User, candidates: list[LearningCandidate]
) -> list[LearningCandidate]:
    """Attach each grammar candidate's unit brief (what the planner poses it from)."""

    if not any(c.target.kind is TargetKind.GRAMMAR for c in candidates):
        return candidates
    from app.services.chrome_language import user_chrome_language
    from app.services.concept_life import concept_brief

    language = user_chrome_language(user)
    out: list[LearningCandidate] = []
    for candidate in candidates:
        if candidate.target.kind is not TargetKind.GRAMMAR:
            out.append(candidate)
            continue
        try:
            concept = db.get(GrammarConcept, int(candidate.target.id))
            brief = (
                concept_brief(
                    db,
                    concept,
                    control_language=language,
                    stability=(candidate.metadata or {}).get("stability"),
                )
                if concept is not None
                else None
            )
        except Exception:  # pragma: no cover - a brief is never worth the day
            logger.exception("journey_grammar_brief_unavailable")
            brief = None
        if brief is None:
            out.append(candidate)
            continue
        brief = spaced_item_pending(db, user=user, brief=brief)
        brief = _with_coach_scene(brief, language=str(language))
        if concept is not None:
            # WP-129: the catalogue's partner units, for the B1+ contrast items.
            from app.services.grammar_catalog import concept_syllabus

            brief = {
                **brief,
                "contrast_partners": list(concept_syllabus(concept).get("contrast_partners") or []),
            }
        out.append(
            replace(candidate, metadata={**dict(candidate.metadata or {}), "grammar_brief": brief})
        )
    return out


def _lexicon_label(word: Any) -> str:
    """A noun is taught with its article, so its gender can be asked about."""

    lemma = str(word.lemma)
    if str(word.part_of_speech or "").lower() not in {"noun", "nom", "n"} or not word.gender:
        return lemma
    if lemma[:1].lower() in "aeiouyhàâéèêëîïôûœ":
        return ("une " if word.gender == "f" else "un ") + lemma
    return ("la " if word.gender == "f" else "le ") + lemma


def _scene_lexicon_candidates(
    db: Session,
    *,
    user: User,
    scenario: ScenarioBrief,
    exclude: set[str],
    history: dict[tuple[str, str], tuple[EvidenceKind | None, bool]],
) -> list[LearningCandidate]:
    """WP-86. The words today's scene teaches, as candidates with relevance 1.0.

    Matched to the catalogue (or entered in it, learner-safely) by
    :func:`app.services.kept_words.record_scene_lexicon`, inside a SAVEPOINT: a
    lexicon that cannot be recorded costs the words, never the day. A word the
    learner has never studied is ``is_new``; the gloss is the scene's own, in the
    learner's language, and the sentence it was taught in rides along so the
    planner can rebuild or blank it.
    """

    from app.services.kept_words import record_scene_lexicon
    from app.services.scene_items import draft_of, lexicon_of, sentence_of

    entries = lexicon_of(scenario)
    if not entries:
        # WP-131: a B1+ season tentpole carries no bible lexicon (it is written
        # for A1–A2). Its words are derived from the lines at the learner's own
        # level — new anchors at the band and one below, a foundational word only
        # when the learner holds it due (app/services/season_lexicon).
        from app.services.season_lexicon import scene_entries

        try:
            with db.begin_nested():
                entries = scene_entries(db, user=user, scenario=scenario)
        except Exception:  # noqa: BLE001 - the words are a bonus, the day is not
            logger.warning("journey_learning_season_lexicon_unavailable")
            entries = []
    if not entries:
        return []
    draft = draft_of(scenario)
    sentences = {
        " ".join(str(entry.get("lemma") or entry.get("surface_fr") or "").split()): sentence_of(draft, entry)
        for entry in entries
    }
    try:
        with db.begin_nested():
            words = record_scene_lexicon(
                db, user=user, entries=entries, sentences=sentences, level=scenario.level_band
            )
    except Exception:  # noqa: BLE001 - the words are a bonus, the day is not
        logger.warning("journey_learning_scene_lexicon_unavailable")
        return []
    candidates: list[LearningCandidate] = []
    for word in words:
        if str(word.word_id) in exclude:
            continue
        exclude.add(str(word.word_id))
        target = TargetRef(
            kind=TargetKind.VOCABULARY,
            id=str(word.word_id),
            label_fr=_lexicon_label(word),
            label_native=word.gloss or None,
        )
        candidates.append(
            LearningCandidate(
                target=target,
                priority_score=0.0,
                due_since_days=0,
                estimated_seconds=CANDIDATE_SECONDS[ItemType.VOCAB],
                is_new=not word.studied,
                relevance=1.0,
                source_item_type=str(ItemType.VOCAB),
                metadata={
                    "word_id": word.word_id,
                    "anchor": "scene_lexicon",
                    "surface_fr": word.surface,
                    "example_fr": word.sentence,
                    **_history_metadata(history, target),
                },
            )
        )
    return candidates


def _fragile_words(
    db: Session,
    *,
    user: User,
    now: datetime,
    exclude: set[str],
    room: int,
    history: dict[tuple[str, str], tuple[EvidenceKind | None, bool]],
) -> list[LearningCandidate]:
    """WP-78. Studied words about to come due, soonest first — read-only."""

    if room <= 0:
        return []
    horizon = now + timedelta(days=FRAGILE_WINDOW_DAYS)
    try:
        with db.begin_nested():
            rows = (
                db.query(VocabularyWord, UserVocabularyProgress)
                .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
                .filter(
                    UserVocabularyProgress.user_id == user.id,
                    UserVocabularyProgress.reps > 0,
                    UserVocabularyProgress.due_at.isnot(None),
                    UserVocabularyProgress.due_at <= horizon,
                )
                .order_by(UserVocabularyProgress.due_at.asc(), VocabularyWord.id.asc())
                .limit(room * 3)
                .all()
            )
    except Exception:  # noqa: BLE001 - a fuller day is never worth the day
        logger.warning("journey_learning_fragile_words_unavailable")
        return []
    fragile: list[LearningCandidate] = []
    for word, _progress in rows:
        if str(word.id) in exclude:
            continue
        gloss = word_gloss(word, user.native_language)
        target = TargetRef(
            kind=TargetKind.VOCABULARY,
            id=str(word.id),
            label_fr=str(word.word),
            label_native=gloss or None,
        )
        fragile.append(
            LearningCandidate(
                target=target,
                priority_score=0.0,
                due_since_days=0,
                estimated_seconds=CANDIDATE_SECONDS[ItemType.VOCAB],
                is_new=False,
                relevance=0.0,
                source_item_type=str(ItemType.VOCAB),
                metadata={
                    "word_id": word.id,
                    "anchor": "fragile_word",
                    "fragile": True,
                    **_history_metadata(history, target),
                },
            )
        )
        if len(fragile) >= room:
            break
    return fragile


def _partner_words(db: Session, *, user: User, exclude: set[str]) -> list[LearningCandidate]:
    """WP-78. A few glossed words the learner has already studied.

    Context cards only: a matching item needs four meanings on the table and a
    listen-and-tap item three, and a learner with one due word still deserves
    the format. Read-only, and flagged so the planner never makes them a target.
    """

    try:
        with db.begin_nested():
            rows = (
                db.query(VocabularyWord)
                .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
                .filter(
                    UserVocabularyProgress.user_id == user.id,
                    UserVocabularyProgress.reps > 0,
                )
                .order_by(
                    UserVocabularyProgress.last_review_date.desc().nullslast(),
                    VocabularyWord.id.asc(),
                )
                .limit(MAX_PARTNER_WORDS * 3)
                .all()
            )
    except Exception:  # noqa: BLE001 - context cards never cost the day
        logger.warning("journey_learning_partner_words_unavailable")
        return []
    partners: list[LearningCandidate] = []
    for word in rows:
        if str(word.id) in exclude:
            continue
        gloss = word_gloss(word, user.native_language)
        if not gloss:
            continue
        partners.append(
            LearningCandidate(
                target=TargetRef(
                    kind=TargetKind.VOCABULARY,
                    id=str(word.id),
                    label_fr=str(word.word),
                    label_native=gloss,
                ),
                priority_score=0.0,
                due_since_days=0,
                estimated_seconds=0,
                is_new=False,
                relevance=0.0,
                source_item_type=str(ItemType.VOCAB),
                metadata={"word_id": word.id, "partner_only": True},
            )
        )
        if len(partners) >= MAX_PARTNER_WORDS:
            break
    return partners


def _kept_id(candidate: LearningCandidate) -> int | None:
    if candidate.target.kind is not TargetKind.VOCABULARY:
        return None
    try:
        return int(candidate.target.id)
    except (TypeError, ValueError):
        return None


def _kept_words(db: Session, *, user: User, now: datetime) -> dict[int, Any]:
    """WP-78. The learner's recently kept words; ``{}`` when they cannot be read.

    Best effort inside a SAVEPOINT (WP-69): the preference is worth a lot less
    than the day.
    """

    from app.services.kept_words import recent_kept_words

    try:
        with db.begin_nested():
            return recent_kept_words(db, user_id=user.id, now=now)
    except Exception:  # noqa: BLE001 - a preference never costs the day
        logger.warning("journey_learning_kept_words_unavailable")
        return {}


def _mark_kept(candidate: LearningCandidate, kept: dict[int, Any]) -> LearningCandidate:
    row = kept.get(_kept_id(candidate) or -1)
    if row is None:
        return candidate
    # Ranked first by the caller, but its *relevance* is left alone: a kept word
    # the scene does not use must not become an obligation in the reply.
    return replace(
        candidate,
        metadata={**candidate.metadata, "kept": True, "example_fr": row.example_fr},
    )


def _kept_extra_candidates(
    db: Session,
    *,
    user: User,
    kept: dict[int, Any],
    exclude: set[str],
    history: dict[tuple[str, str], tuple[EvidenceKind | None, bool]],
) -> list[LearningCandidate]:
    """Kept words the due pool did not already return, as practice candidates."""

    extras: list[LearningCandidate] = []
    for word_id, row in kept.items():
        if str(word_id) in exclude:
            continue
        word = db.get(VocabularyWord, word_id)
        if word is None:
            continue
        target = TargetRef(
            kind=TargetKind.VOCABULARY,
            id=str(word_id),
            label_fr=str(word.word),
            label_native=word_gloss(word, user.native_language) or row.gloss or None,
        )
        extras.append(
            LearningCandidate(
                target=target,
                priority_score=0.0,
                due_since_days=0,
                estimated_seconds=CANDIDATE_SECONDS[ItemType.VOCAB],
                is_new=False,
                relevance=0.0,
                source_item_type=str(ItemType.VOCAB),
                metadata={
                    "word_id": word_id,
                    "anchor": "kept_word",
                    "kept": True,
                    "example_fr": row.example_fr,
                    **_history_metadata(history, target),
                },
            )
        )
    return extras


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
    # EXPERIENCE-REVIEW 2026-10-04: «level-appropriate» had only a ceiling, and the
    # scene's most frequent uncarded word is always a grammar word: the B2 and C1
    # walks drilled «pas», «moi», «elle», «nous», «cinq», «vingt» as their day's new
    # words. From B1 a new word is at most one level below the learner, and never a
    # closed-class word (those are taught by the grammar units, not by cards).
    min_difficulty = max(1, max_difficulty - 1) if max_difficulty >= 3 else 1
    if max_difficulty >= 3:
        from app.services.level_coverage import CLOSED_CLASS_WORDS

        terms = {term for term in terms if term not in CLOSED_CLASS_WORDS}
        if not terms:
            return None
    words = (
        db.query(VocabularyWord)
        .filter(
            VocabularyWord.language == language,
            VocabularyWord.normalized_word.in_(sorted(terms)),
            or_(
                VocabularyWord.difficulty_level.is_(None),
                and_(
                    VocabularyWord.difficulty_level <= max_difficulty,
                    VocabularyWord.difficulty_level >= min_difficulty,
                ),
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
    if task.task_type == "short_answer" and not task.prompt_fr and article_optional(task.target):
        # The bare noun: ``answer_matches`` accepts any answer that holds it as a
        # run of words, so «appartement», «l'appartement» (U+2019 too) and
        # «un appartement» all count.
        _article, noun = split_article(task.target.label_fr)
        accepted.append(noun)
    return accepted


#: Formats answered by placing tiles in order.
TILE_ORDER_FORMATS = frozenset({"tiles", "word_bank", "unscramble"})
#: Formats graded by option id or tile order — never the learner's own French.
IDENTITY_GRADED_FORMATS = TILE_ORDER_FORMATS | {"choice", "classify", "listen_tap", "who_said", "match_pairs"}
#: QA-PRACTICE: what a rebuilt sentence got wrong, in the learner's language.
_ORDER_NOTES: dict[str, dict[str, str]] = {
    "from": {
        "en": "From “{word}” on, the order is off. The right order is above.",
        "de": "Ab „{word}“ stimmt die Reihenfolge nicht mehr. Oben steht die richtige.",
        "fr": "À partir de « {word} », l'ordre ne va plus. Le bon ordre est au-dessus.",
    },
    "first": {
        "en": "The sentence does not start with “{word}”. The right order is above.",
        "de": "Der Satz beginnt nicht mit „{word}“. Oben steht die richtige Reihenfolge.",
        "fr": "La phrase ne commence pas par « {word} ». Le bon ordre est au-dessus.",
    },
    "missing": {
        "en": "Some words are missing. The whole sentence is above.",
        "de": "Es fehlen Wörter. Oben steht der ganze Satz.",
        "fr": "Il manque des mots. La phrase entière est au-dessus.",
    },
    "extra": {
        "en": "Some tiles were not needed. The sentence is above.",
        "de": "Manche Bausteine gehörten nicht dazu. Oben steht der Satz.",
        "fr": "Certains mots étaient en trop. La phrase est au-dessus.",
    },
}


def _tile_texts(task: RecallTask, tile_ids: Sequence[str]) -> list[str]:
    by_id = {str(option.get("id")): str(option.get("text_fr") or "") for option in task.options}
    return [by_id[str(tile)] for tile in tile_ids if by_id.get(str(tile))]


def recall_learner_text(task: RecallTask, answer: AttemptAnswer) -> str:
    """What the learner actually *said* with this attempt, as French text.

    A tile answer arrives as ids; its correction must show the words the
    learner placed («tile_3f… tile_a1…» is not a sentence, and the old
    ``answer.text`` was empty, so the correction was dropped and a wrong
    unscramble showed «Noch nicht» without the sentence).
    """

    if task.task_type in {"tiles", "word_bank", "unscramble"} and answer.tile_ids:
        return " ".join(_tile_texts(task, answer.tile_ids))
    # A pick is corrected on the device (the right card lights up); its typed
    # text, if any, is what the server's correction is checked against.
    return normalize_answer_text(answer.text)


def tile_order_note(task: RecallTask, tile_ids: Sequence[str], language: str) -> str | None:
    """Where a rebuilt sentence went wrong, in the learner's language."""

    expected = [str(tile) for tile in task.correct_tile_order]
    submitted = [str(tile) for tile in tile_ids]
    table = lambda key: _ORDER_NOTES[key].get(language) or _ORDER_NOTES[key]["en"]  # noqa: E731
    if not expected or submitted == expected:
        return None
    if any(tile not in expected for tile in submitted):
        return table("extra")
    if len(submitted) < len(expected) and submitted == expected[: len(submitted)]:
        return table("missing")
    index = next((i for i, (got, want) in enumerate(zip(submitted, expected, strict=False)) if got != want), None)
    if index is None:
        return table("missing")
    word = (_tile_texts(task, [submitted[index]]) or [""])[0]
    if not word:
        return None
    return table("first" if index == 0 else "from").format(word=word)


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


def match_pairs_target_correct(task: RecallTask, tile_ids: Sequence[str]) -> bool:
    """Did the learner pair the day's target right the *first* time?

    ``correct_tile_order`` is ``[fr, native, …]`` with the target first. The
    submission is every pairing the learner made, in order, wrong ones
    included. Only the first pairing that touches either of the target's two
    cards counts: a learner who found the target's meaning by eliminating the
    other three still paired it right, and one who tried it against the wrong
    meaning first did not know it.
    """

    order = [str(item) for item in task.correct_tile_order]
    if len(order) < 2:
        return False
    target_fr, target_native = order[0], order[1]
    submitted = [str(item) for item in tile_ids]
    for index in range(0, len(submitted) - 1, 2):
        pair = submitted[index], submitted[index + 1]
        if target_fr in pair or target_native in pair:
            return pair == (target_fr, target_native)
    return False


def _is_free_sentence(task: RecallTask) -> bool:
    from app.services.grammar_items import FREE_SENTENCE_FORMAT

    return (
        task.task_type == "short_answer"
        and task.evidence_format == FREE_SENTENCE_FORMAT
        and task.target.kind is TargetKind.GRAMMAR
    )


def _free_sentence_uses_unit(db: Session | None, task: RecallTask, text: str | None) -> bool:
    """WP-129: does the learner's free sentence use the unit (its regex detector)?"""

    from app.services import grammar_items, grammar_units

    concept = None
    try:
        concept = db.get(GrammarConcept, int(task.target.id)) if db is not None else None
    except Exception:  # noqa: BLE001 - an unreadable unit grades nothing as met
        logger.warning("journey_free_sentence_unit_unavailable")
    if concept is None:
        return False
    brief = {
        "detectors": grammar_units.regex_patterns(grammar_units.unit_detectors(concept)),
        "noun_phrase": grammar_units.is_noun_phrase_unit(concept),
    }
    return grammar_items.free_sentence_uses_unit(brief, text)


def evaluate_recall(
    db: Session,
    *,
    user: User,
    task: RecallTask,
    answer: AttemptAnswer,
    assistance: AssistanceLevel,
) -> RecallEvaluation:
    """Grade one recall opportunity. Pure policy — writes nothing."""

    # Canonical writes happen in apply_learning_evidence; ``db`` only names the
    # grammar unit (accent policy) and ``user`` the note language.
    accents = _recall_accent_policy(db, task)

    if is_infrastructure_failure(answer):
        return unscored_recall_evaluation(
            assistance=assistance, reason="transcription_unavailable"
        )
    typed_verdict = None

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

    # WP-66 brought three Séance formats into the journey. Two of them are
    # answered with the renderers that already exist, so they are graded by the
    # same two branches: a `classify` is an option pick (two contrastive
    # labels), and a `word_bank` is a tile order — with distractor chips, so an
    # answer that uses a chip it should not have used is simply not the
    # expected order. `transform` is free text and falls through to open
    # production, which is what it is.
    # WP-78: `listen_tap` is a pick, `unscramble` a tile order, and a
    # `match_pairs` item is graded on the day's target alone (see
    # `match_pairs_target_correct`). All three are recognition.
    if task.task_type == "dictation":
        # WP-91: its own verdict ladder (met / accents / not yet).
        return evaluate_dictation(task=task, answer=answer, assistance=assistance)
    if task.task_type in {"choice", "classify", "listen_tap", "who_said"}:
        selected = _selected_option_id(task, answer)
        is_correct = bool(selected) and selected == task.correct_option_id
        learner_text = _option_text(task, selected) or answer.text
        opportunity: OpportunityKind = "choice"
    elif task.task_type == "match_pairs":
        is_correct = match_pairs_target_correct(task, answer.tile_ids)
        learner_text = task.target.label_fr if is_correct else None
        opportunity = "tiles"
    elif _is_free_sentence(task):
        # WP-129: the learner's own sentence, graded by the unit's detector —
        # never against the one model sentence (shown after a miss).
        # The model sentence itself, typed with a forgiven slip («meme» for
        # «même»), is the unit used too: the detector reads accents literally.
        from app.services.answer_acceptance import judge

        typed_verdict = judge(answer.text, _accepted_answers(task), accents=accents)
        is_correct = _free_sentence_uses_unit(db, task, answer.text) or bool(
            typed_verdict is not None and typed_verdict.correct
        )
        if not (typed_verdict is not None and typed_verdict.correct):
            typed_verdict = None
        learner_text = answer.text
        opportunity = "open_production"
    elif task.task_type in {"tiles", "word_bank", "unscramble"}:
        expected = [str(tile) for tile in task.correct_tile_order]
        submitted = [str(tile) for tile in answer.tile_ids]
        is_correct = bool(expected) and submitted == expected
        # The words placed, not their ids: the correction shows this span.
        learner_text = recall_learner_text(task, answer) if submitted else answer.text
        opportunity = "tiles"
    else:
        is_correct = answer_matches(answer.text, _accepted_answers(task), accents=accents)
        learner_text = answer.text
        opportunity = "open_production"
        from app.services.answer_acceptance import judge

        typed_verdict = judge(
            answer.text, _accepted_answers(task), article_optional=article_optional(task.target), accents=accents
        )

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
    if task.task_type == "who_said":
        # WP-86. Knowing who said a line is reading the story, not knowing the
        # word the line holds: the item is graded, and nothing is scheduled.
        observation = None
    if observation is not None:
        # WP-L4: a grammar unit is credited with the weight of the format.
        # WP-94: the Rappel's coach mini-scene proves free use, not a transform.
        observation = replace(observation, task_format=task.evidence_format or task.task_type)
    correction = None
    typed = typed_verdict
    if not is_correct:
        note = task.hint_native or task.instruction_native
        if task.task_type in {"tiles", "word_bank", "unscramble"} and answer.tile_ids:
            from app.services.chrome_language import user_chrome_language

            note = tile_order_note(task, answer.tile_ids, str(user_chrome_language(user))) or note
        elif typed is not None and typed.note is not None:
            # EXERCISE-QA: the why a fold can see (an accent that is grammar, an
            # ending, an elision, a gender) beats the item's generic hint.
            from app.services.answer_acceptance import feedback_note
            from app.services.chrome_language import user_chrome_language

            note = feedback_note(typed, str(user_chrome_language(user))) or note
        expected = task.solution_fr or (task.accepted_answers[0] if task.accepted_answers else None)
        correction = build_correction(learner_text=learner_text, corrected_fr=expected, note_native=note)
        if correction is None and typed is not None and typed.note == "accent" and learner_text and expected:
            # EXERCISE-QA: refused for an accent that is grammar («Il à mangé»):
            # the folds see no difference, the learner must still see the answer.
            candidate = Correction(
                span_fr=normalize_answer_text(learner_text),
                corrected_fr=normalize_answer_text(expected),
                note_native=note or "",
            )
            correction = candidate if candidate.is_valid_for(normalize_answer_text(learner_text)) else None
        if correction is None and _is_free_sentence(task) and learner_text and expected:
            # WP-129: a free sentence that did not use the unit is not a slip in
            # one span: the learner sees a model sentence that does, whole.
            candidate = Correction(
                span_fr=normalize_answer_text(learner_text),
                corrected_fr=normalize_answer_text(expected),
                note_native=note or "",
            )
            correction = candidate if candidate.is_valid_for(normalize_answer_text(learner_text)) else None
    slip_note = None
    if is_correct and typed is not None and typed.correct and (typed.accent_slip or typed.typo):
        # QA-CLOSE (owner decision d): a forgiven slip is named on a hit, one line.
        from app.services.answer_acceptance import feedback_note
        from app.services.chrome_language import user_chrome_language

        slip_note = feedback_note(typed, str(user_chrome_language(user)))
    return RecallEvaluation(
        outcome=TaskOutcome.MET if is_correct else TaskOutcome.NOT_YET,
        assistance=assistance,
        observations=[observation] if observation is not None else [],
        correction=correction,
        pending=False,
        failure_reason=None,
        slip_note_native=slip_note,
    )


# --------------------------------------------------------------------------
# WP-91 — «Dictée»: what was heard, written down
# --------------------------------------------------------------------------

#: Every apostrophe and quote a keyboard (iOS above all) may insert.
_DICTATION_APOSTROPHES = str.maketrans({
    "\u2019": "'", "\u2018": "'", "\u201b": "'", "\u2032": "'", "\u00b4": "'", "`": "'",
})
#: The correction's margin note, in the learner's language.
_DICTATION_NOTE: dict[str, dict[str, str]] = {
    "accents": {
        "en": "Almost: only the accents are missing.",
        "de": "Fast: nur die Akzente fehlen.",
        "fr": "Presque : il ne manque que les accents.",
    },
    "words": {
        "en": "Listen again: this is what was said.",
        "de": "Hör noch einmal hin: Das wurde gesagt.",
        "fr": "Réécoutez : voici ce qui a été dit.",
    },
}


def _dictation_language(task: RecallTask) -> str:
    """The learner's language, read off the instruction the planner wrote."""

    from app.services.journey_planner import _DICTATION_INSTRUCTION

    for language, text in _DICTATION_INSTRUCTION.items():
        if text == task.instruction_native:
            return language
    return "en"


def dictation_form(value: str | None, *, keep_accents: bool = True) -> str:
    """The form a dictation is compared in.

    Case, punctuation (guillemets and the typographer's quotes included),
    apostrophe variants — ``’`` ``‘`` fold to ``'`` — hyphens and whitespace
    never count. ``keep_accents=False`` also strips diacritics: the second rung
    of the ladder.
    """

    text = normalize_answer_text(value).translate(_DICTATION_APOSTROPHES).lower()
    text = unicodedata.normalize("NFC", text)
    if not keep_accents:
        text = "".join(
            char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
        )
    # Words and apostrophes survive; «», “”, ?!.,;: and hyphens become spaces.
    text = re.sub(r"[^\w']+", " ", text)
    # «j' ai», «j 'ai» and «j'ai» are the same thing typed three ways.
    text = re.sub(r"\s*'\s*", "' ", text)
    return " ".join(text.replace("_", " ").split())


def _dictation_credits_target(task: RecallTask) -> bool:
    """Does the dictated line hold the item's word? Only then is it evidence."""

    label = dictation_form(task.target.label_fr, keep_accents=False)
    line = dictation_form(task.solution_fr, keep_accents=False)
    if not label or not line:
        return False
    return f" {label} " in f" {line} " or f" {re.sub(r'^(le|la|les|un|une|des|du) ', '', label)} " in f" {line} "


def evaluate_dictation(
    *, task: RecallTask, answer: AttemptAnswer, assistance: AssistanceLevel
) -> RecallEvaluation:
    """Grade one dictation.

    * the same words (case, punctuation, quotes and spacing aside) — **met**;
    * the same words with a missing or wrong accent — **partially met**, with
      the line as the correction;
    * anything else — **not yet**, with the line as the correction.

    Listening, then transcribing, is recognition of the word the line holds —
    never production. A line that does not hold the item's word is graded and
    schedules nothing (as «Qui a dit ça ?»).
    """

    expected = task.solution_fr or (task.accepted_answers[0] if task.accepted_answers else "")
    learner = normalize_answer_text(answer.text)
    if dictation_form(learner) and dictation_form(learner) == dictation_form(expected):
        outcome = TaskOutcome.MET
    elif dictation_form(learner, keep_accents=False) and dictation_form(
        learner, keep_accents=False
    ) == dictation_form(expected, keep_accents=False):
        outcome = TaskOutcome.PARTIALLY_MET
    else:
        outcome = TaskOutcome.NOT_YET
    heard = outcome is not TaskOutcome.NOT_YET
    observation = None
    if _dictation_credits_target(task):
        observation = classify_observation(
            target=task.target,
            opportunity="tiles",
            is_correct=heard,
            assistance=assistance,
            modality=answer.mode,
            elicited=True,
            learner_text=learner,
            corrected_text=None if outcome is TaskOutcome.MET else expected,
        )
        if observation is not None:
            observation = replace(observation, task_format=task.task_type)
    correction = None
    if outcome is not TaskOutcome.MET and learner and expected:
        # Built directly: `build_correction` folds accents away, and an accent
        # is exactly what the partial verdict is about.
        correction = Correction(
            span_fr=learner,
            corrected_fr=normalize_answer_text(expected),
            note_native=_DICTATION_NOTE[
                "accents" if outcome is TaskOutcome.PARTIALLY_MET else "words"
            ][_dictation_language(task)],
        )
    return RecallEvaluation(
        outcome=outcome,
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
# Cross-surface credit claims live with the canonical evidence owner.


def journey_credited_today(
    db: Session,
    *,
    user: User,
    target_kind: str,
    target_id: str,
    on_date: date | None = None,
    source_type: str = JOURNEY_SOURCE_TYPE,
) -> bool:
    """Check canonical credited moments for a target/day and source surface.

    Defaults to the journey; "atelier" selects the reverse-direction drill claim.
    """

    day = on_date or datetime.now(UTC).date()
    stmt = (
        select(SessionLearningMoment)
        .where(
            SessionLearningMoment.user_id == user.id,
            SessionLearningMoment.source_type == source_type,
            SessionLearningMoment.srs_credit_applied.is_(True),
        )
        .order_by(SessionLearningMoment.created_at.desc())
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


def lock_learning_credit(db: Session, user: User) -> None:
    """Serialize cross-surface schedule checks and writes until caller commit."""
    db.execute(select(User.id).where(User.id == user.id).with_for_update()).scalar_one()


def record_drill_credit(
    db: Session, *, user: User, target_kind: str, target_id: str,
    now: datetime | None = None,
) -> None:
    """Record successful legacy credit in the canonical evidence ledger.

    One completed practice session per UTC day holds these claims. Failed and
    unassessed answers never call this helper. It flushes; the caller commits.
    """
    now = now or datetime.now(UTC)
    day = now.date()
    lock_learning_credit(db, user)
    if journey_credited_today(
        db, user=user, target_kind=target_kind, target_id=target_id,
        on_date=day, source_type="atelier",
    ):
        return

    session_id = uuid5(NAMESPACE_URL, f"atelier-credit:{user.id}:{day.isoformat()}")
    session = db.get(LearningSession, session_id)
    if session is None:
        session = LearningSession(
            id=session_id, user_id=user.id, planned_duration_minutes=0,
            scenario="atelier_credit", status="completed", completed_at=now,
        )
        db.add(session)
        db.flush([session])
    db.add(SessionLearningMoment(
        session_id=session.id, user_id=user.id, kind="drill_credit",
        source_type="atelier", source_id=f"{target_kind}:{target_id}",
        status="completed", completed_at=now, srs_credit_applied=True,
        prompt_payload={"observed_on": day.isoformat(), "timezone": "UTC",
                        "target": {"kind": target_kind, "id": str(target_id)}},
        result_payload={"credit": "applied"},
    ))
    db.flush()


def record_daily_practice_streak(db: Session, user: User, *, on_date: date | None = None) -> int:
    """Move the learner's practice streak, at most once per local day.

    WP-80: a thin door onto :mod:`app.services.streak`, the one place the rule
    lives (local day, checked on read, one «jour de relâche» per full week).
    The legacy Atelier session (`AtelierService._update_streak`) goes through
    the same function, and both are no-ops once the day is marked, so a
    learner who finishes the journey and then drills gets one increment, not
    two. Returns the streak after the call.
    """

    from app.services.streak import record_practice_day

    return record_practice_day(db, user, on_date=on_date).days


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
        source_payload={
            "source_key": source_key,
            "policy_version": JOURNEY_LEARNING_POLICY_VERSION,
            # WP-115e: the review log records the format (``reply`` for the reply).
            "task_type": observation.task_format or "reply",
        },
        # EXPERIENCE-REVIEW 2026-10-04: a missed practice item lapses the word; only
        # the learner's own French (the reply) opens a repair. A recall miss used to
        # come back as «Schreib richtig, was du gesagt hast: clé» — a tapped card,
        # or «euh je ne sais pas», posed as the learner's sentence.
        record_erratum=(observation.task_format or "reply") == "reply",
    )
    return _CreditOutcome(True, result.to_dict())


def _apply_grammar_credit(
    db: Session,
    *,
    user: User,
    target: TargetRef,
    evidence_kind: EvidenceKind,
    now: datetime,
    task_format: str | None = None,
    assistance: AssistanceLevel = AssistanceLevel.NONE,
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
    # WP-L3: the one door (`apply_grammar_evidence`), with the weight of what
    # the journey observed; the concept's own memory carries the history.
    evidence = grammar_journey_evidence(
        evidence_kind, task_format=task_format, assistance=assistance
    )
    apply_grammar_evidence(progress, evidence, now=now, score=score)
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
            "stability": progress.stability,
            "evidence_format": str(evidence.format),
        },
    )


def _grammar_success_credited_today(
    db: Session, *, user: User, concept_id: str, observed_on: date
) -> bool:
    """WP-L4: a journey success already moved this unit's schedule today.

    One day, one success on the schedule (D-0's «one séance, one credit»
    inside the journey): an introduction day's guided items and its reply
    all see the unit, and only the first success schedules it. A failure
    always lands, and the life (``note_concept_evidence``) sees every use.
    """

    stmt = select(SessionLearningMoment).where(
        SessionLearningMoment.user_id == user.id,
        SessionLearningMoment.source_type == JOURNEY_SOURCE_TYPE,
        SessionLearningMoment.kind == JOURNEY_MOMENT_KIND_BY_TARGET[TargetKind.GRAMMAR],
        SessionLearningMoment.srs_credit_applied.is_(True),
    )
    for moment in db.execute(stmt).scalars():
        payload = dict(moment.prompt_payload or {})
        if str(payload.get("observed_on") or "") != observed_on.isoformat():
            continue
        if str((payload.get("target") or {}).get("id") or "") != str(concept_id):
            continue
        result = dict(moment.result_payload or {})
        if str(result.get("evidence_kind") or "") != str(EvidenceKind.NOT_YET):
            return True
    return False


def _note_folded_grammar_use(
    db: Session,
    *,
    user: User,
    observation: TargetObservation,
    evidence_kind: EvidenceKind,
    now: datetime,
) -> None:
    """A folded success still counts for the unit's life (free use, spaced item)."""

    try:
        concept_id = int(observation.target.id)
    except (TypeError, ValueError):
        return
    from app.db.models.grammar import UserGrammarProgress
    from app.services.concept_life import note_concept_evidence

    progress = (
        db.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept_id)
        .first()
    )
    if progress is None:
        return
    note_concept_evidence(
        progress,
        grammar_journey_evidence(
            evidence_kind, task_format=observation.task_format, assistance=observation.assistance
        ),
        now=now,
    )
    db.add(progress)
    db.flush([progress])


def _apply_error_credit(
    db: Session,
    *,
    user: User,
    target: TargetRef,
    evidence_kind: EvidenceKind,
    now: datetime,
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
        user=user, error_id=error_id, rating=rating, repaired=repaired, now=now,
        evidence=JOURNEY_EVIDENCE[evidence_kind],
    )
    if reviewed is None:
        return _CreditOutcome(False, {"skipped": "error_missing"})
    db.flush([reviewed])
    detail: dict[str, Any] = {
        "error_id": str(reviewed.id),
        "rating": rating,
        "repaired": repaired,
        "state": reviewed.state,
        "next_review_date": (
            reviewed.next_review_date.isoformat() if reviewed.next_review_date else None
        ),
    }
    if reviewed.concept_id:
        # WP-L1: a repair is evidence on the concept the erratum belongs to, as
        # the unified queue's repair already treats it (`UnifiedSRSService.
        # _credit_linked_grammar_from_error`). Written through this transaction.
        detail["concept_credit"] = _apply_linked_concept_credit(
            db, user=user, concept_id=reviewed.concept_id, evidence_kind=evidence_kind, now=now
        ).detail
    return _CreditOutcome(True, detail)


def _apply_linked_concept_credit(
    db: Session,
    *,
    user: User,
    concept_id: int,
    evidence_kind: EvidenceKind,
    now: datetime,
) -> _CreditOutcome:
    """Grammar evidence reached through an erratum rather than a concept target.

    A success folds into a credit the concept already earned today, on either
    surface (WP-16 / D-0: one séance, one credit); a lapse always lands.
    """

    if evidence_kind is not EvidenceKind.NOT_YET and any(
        journey_credited_today(
            db, user=user, target_kind=str(TargetKind.GRAMMAR), target_id=str(concept_id),
            on_date=now.date(), source_type=source_type,
        )
        for source_type in (JOURNEY_SOURCE_TYPE, "atelier")
    ):
        return _CreditOutcome(False, {"concept_id": concept_id, "skipped": "credited_today"})
    return _apply_grammar_credit(
        db,
        user=user,
        target=TargetRef(kind=TargetKind.GRAMMAR, id=str(concept_id), label_fr=""),
        evidence_kind=evidence_kind,
        now=now,
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
            db, user=user, target=target, evidence_kind=evidence_kind, now=now,
            task_format=observation.task_format, assistance=observation.assistance,
        )
    if target.kind is TargetKind.ERROR:
        return _apply_error_credit(
            db, user=user, target=target, evidence_kind=evidence_kind, now=now
        )
    return _CreditOutcome(False, {"skipped": "unknown_target_kind"})


def attempted_answer(learner_text: str | None, expected: str | None) -> bool:
    """Was this an attempt at an answer, rather than a give-up?

    A give-up is «je ne sais pas» and its kin, a bare «?», or a sentence in the
    learner's own language: no French was tried, so there is nothing to repair.
    Wrong French — even the wrong word — is an attempt.
    """

    import re as _re

    from app.services.answer_acceptance import fold_all
    from app.services.season.turns import reply_is_not_french

    given = fold_all(learner_text)
    if not given or not _re.search(r"[a-z]", given):
        return False
    if _re.search(r"\b(?:je\s+(?:ne\s+)?sais\s+pas|sais\s+pas|aucune\s+idee|keine\s+ahnung|weiss\s+(?:ich\s+)?nicht|i\s+don'?t\s+know|no\s+idea|idk)\b", given):
        return False
    return not reply_is_not_french(str(learner_text))


def _record_correction_erratum(
    db: Session,
    *,
    user: User,
    session: LearningSession,
    correction: Correction,
    modality: InputMode,
    source_key: str,
    foreground: bool,
    concept_id_hint: int | None = None,
) -> dict[str, Any] | None:
    service = ErrorMemoryService(db)
    # WP-L1: the erratum names its concept, as `record_detected_error` does, so
    # the mistake can make that concept due and a later repair can credit it.
    # WP-L4: when the step itself observed one grammar unit going wrong (a
    # guided item, or a reply the unit's detector saw), the erratum is that
    # unit's — so its lapse is booked once, and its repair credits it.
    concept_id = concept_id_hint or service.infer_concept_id_for_correction(
        learner_text=correction.span_fr,
        corrected_text=correction.corrected_fr,
        note=correction.note_native,
    )
    return service.record_erratum(
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
        concept_id=concept_id,
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
    # Concepts this step already booked a lapse on, so a correction about the
    # same concept does not book a second one.
    lapsed_concepts: set[str] = set()

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
    lock_learning_credit(db, user)

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

        # Preserve the journey evidence, but do not advance a schedule that
        # today's drill already advanced. A real failure still reaches SRS.
        folded = (
            evidence_kind != EvidenceKind.NOT_YET
            and observation.target.kind in {TargetKind.GRAMMAR, TargetKind.VOCABULARY}
            and journey_credited_today(
                db, user=user, target_kind=str(observation.target.kind),
                target_id=str(observation.target.id), on_date=now.date(),
                source_type="atelier",
            )
        )
        folded_reason = "credited_in_drill_today"
        if (
            not folded
            and evidence_kind is not EvidenceKind.NOT_YET
            and observation.target.kind is TargetKind.GRAMMAR
            and _grammar_success_credited_today(
                db, user=user, concept_id=str(observation.target.id), observed_on=observed_on
            )
        ):
            folded, folded_reason = True, "credited_in_journey_today"
        if folded and observation.target.kind is TargetKind.GRAMMAR:
            _note_folded_grammar_use(
                db, user=user, observation=observation, evidence_kind=evidence_kind, now=now
            )
        credit = (
            _CreditOutcome(False, {"skipped": folded_reason})
            if folded else _credit_for(
                db, user=user, observation=observation, evidence_kind=evidence_kind,
                session=session, source_key=source_key, now=now,
            )
        )
        moment.srs_credit_applied = credit.applied
        punishment_recorded = punishment_recorded or bool(credit.detail.get("erratum_id"))
        if (
            credit.applied
            and evidence_kind is EvidenceKind.NOT_YET
            and observation.target.kind is TargetKind.GRAMMAR
        ):
            lapsed_concepts.add(str(observation.target.id))
        moment.score_0_10 = _score_for(evidence_kind)
        moment.result_payload = {
            "evidence_kind": str(evidence_kind),
            "assistance_level": str(assistance),
            "modality": str(observation.modality or modality),
            "is_open_production": evidence_kind
            in {EvidenceKind.PRODUCED_SUPPORTED, EvidenceKind.PRODUCED_INDEPENDENT},
            "learner_text": observation.learner_text,
            "corrected_text": observation.corrected_text,
            "task_format": observation.task_format,
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
    # QA-PRACTICE: a sentence rebuilt from tiles in the wrong order is shown its
    # correction, but the order was the app's shuffle, not the learner's own
    # French: it is not an erratum to drill later.
    # The same holds for every format graded by identity: a wrong card
    # («féminin» for «un appartement») is not French to repair later.
    rebuilt = any(
        getattr(observation, "task_format", None) in IDENTITY_GRADED_FORMATS
        for observation in evaluation.observations
    )
    # EXPERIENCE-REVIEW 2026-10-04: «euh je ne sais pas» for «appartement» is a word
    # not yet retrieved, not French to repair: it came back two days later as
    # «Schreib richtig, was du gesagt hast: euh je ne sais pas». A miss of a practice
    # item opens a repair only when it was an attempt at the answer.
    if correction is not None and learner_text and not rebuilt and any(
        getattr(observation, "task_format", None) not in (None, "reply")
        for observation in evaluation.observations
    ):
        rebuilt = not attempted_answer(learner_text, correction.corrected_fr)
    if correction is not None and not rebuilt and validate_correction(
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
                    concept_id_hint=_single_lapsed_concept(lapsed_concepts),
                )
                punishment_recorded = bool(erratum)
            concept_credit = None
            concept_id = (erratum or {}).get("concept_id")
            if concept_id and str(concept_id) not in lapsed_concepts:
                # WP-L1: the mistake makes its concept due again (the lapse
                # interval), through the same history-aware journey credit.
                concept_credit = _apply_linked_concept_credit(
                    db, user=user, concept_id=int(concept_id),
                    evidence_kind=EvidenceKind.NOT_YET, now=now,
                ).detail
            moment.srs_credit_applied = bool(erratum)
            moment.result_payload = {
                "span_fr": correction.span_fr,
                "corrected_fr": correction.corrected_fr,
                "note_native": correction.note_native,
                "erratum": erratum,
                "concept_credit": concept_credit,
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


def _single_lapsed_concept(lapsed: set[str]) -> int | None:
    if len(lapsed) != 1:
        return None
    value = next(iter(lapsed))
    return int(value) if value.isdigit() else None


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


# --------------------------------------------------------------------------
# WP-94 — the Rappel's coach mini-scene (free use elicited, not hoped for)
# --------------------------------------------------------------------------

_COACH_SCENE_INSTRUCTION: dict[str, str] = {
    "en": "{name} is talking to you. Reply in French: “{meaning}”",
    "de": "{name} spricht dich an. Antworte auf Französisch: „{meaning}“",
    "fr": "{name} vous parle. Répondez en français : « {meaning} »",
}


def coach_scene_review_task(
    brief: dict[str, Any], *, language: str, day_key: str
) -> RecallTask | None:
    """A strong unit's Rappel: the rule's coach says a line, the learner replies.

    Past :data:`grammar_items.REEMPLOI_STABILITY_DAYS` (10 days) of stability
    the Rappel used to pose nothing and *hope* the reply would use the unit.
    WP-94 poses the Forge's two-line scene instead (``item_bank`` +
    ``forge_coaches.mini_scene``, the same one ``item_bank.scene_item``
    builds): the coach's line in French, the reply's meaning as the cue. It is
    a ``short_answer`` on the wire (every client renders one), graded by
    :func:`answer_matches` against the scene's reply and the frame's accepted
    variants, and credited as free use (``evidence_format="conversation"``).
    ``None`` when the unit has no bank templates, no coach, or no item that
    can be a scene with that coach — then the reply asks for it, as before.
    """

    from app.services import forge_coaches, grammar_items, item_bank

    external_id = str(brief.get("external_id") or "")
    if not external_id or brief.get("concept_id") is None:
        return None
    units = item_bank.units_for_external_id(external_id)
    coach = forge_coaches.coach_for_concept(external_id)
    if not units or not coach:
        return None
    unit = units[0]
    candidates = item_bank.default_bank().generate(
        unit, 8, seed=f"rappel-scene|{external_id}|{day_key}", detector=item_bank.unit_detector(unit)
    )
    for item in candidates:
        scene = forge_coaches.mini_scene(item, coach)
        if scene is None:
            continue
        line = scene["lines"][0]
        name = str(coach.get("name") or "")
        template = _COACH_SCENE_INSTRUCTION.get(language, _COACH_SCENE_INSTRUCTION["en"])
        accepted = list(dict.fromkeys([scene["reply"], *[a for a in item.accepted if a]]))
        return RecallTask(
            task_type="short_answer",
            # FORGE-DE: a German learner reads the German meaning when the item has one.
            instruction_native=template.format(
                name=name, meaning=(scene.get("reply_de") if language == "de" else None) or scene["reply_en"]
            ),
            prompt_fr=f"{name} : « {line['fr']} »",
            options=[],
            target=grammar_items.grammar_target(brief),
            optional=False,
            accepted_answers=accepted,
            solution_fr=scene["reply"],
            translation_native=(str(line.get("en") or "") or None) if language == "en" else None,
            estimated_seconds=40,
            evidence_format="conversation",
        )
    return None


def spaced_item_pending(db: Session, *, user: User, brief: dict[str, Any]) -> dict[str, Any]:
    """WP-99 / O-4: a strong unit still owed its «Tenue» spaced item keeps the transform Rappel.

    From :data:`grammar_items.REEMPLOI_STABILITY_DAYS` the Rappel poses the
    coach's free-use mini-scene. «Held» also needs one correct *spaced item*
    at least 14 days after the introduction (``concept_life``), and a unit
    whose stability passed 10 days before day 14 would otherwise never be
    posed one again. Until ``spaced_success_at`` is set, the brief's stability
    is held just under the threshold (the real one kept as
    ``stability_measured``, and ``spaced_item_pending`` set), so the planner
    poses the medium band's transform. The simulation does the same
    (``simulation.rappel_format(..., spaced_done=...)``).
    """

    from app.db.models.grammar import UserGrammarProgress
    from app.services import grammar_items

    try:
        stability = float(brief.get("stability") or 0.0)
    except (TypeError, ValueError):
        return brief
    if stability < grammar_items.REEMPLOI_STABILITY_DAYS or brief.get("concept_id") is None:
        return brief
    progress = (
        db.query(UserGrammarProgress)
        .filter(
            UserGrammarProgress.user_id == user.id,
            UserGrammarProgress.concept_id == int(brief["concept_id"]),
        )
        .first()
    )
    if progress is None or getattr(progress, "spaced_success_at", None) is not None:
        return brief
    return {
        **brief,
        "stability": round(grammar_items.REEMPLOI_STABILITY_DAYS - 0.1, 2),
        "stability_measured": stability,
        "spaced_item_pending": True,
    }


def _with_coach_scene(brief: dict[str, Any], *, language: str) -> dict[str, Any]:
    """WP-94: a strong unit's brief carries its coach mini-scene for the planner.

    JSON-safe (the planner stays pure: it rebuilds the ``RecallTask`` from this
    and the brief's own target). Seeded by the day, so one day asks one scene.
    """

    from app.services import grammar_items

    if grammar_items.review_band(brief.get("stability")) != "high":
        return brief
    try:
        task = coach_scene_review_task(
            brief, language=language, day_key=datetime.now(UTC).date().isoformat()
        )
    except Exception:  # pragma: no cover - a Rappel item is never worth the day
        logger.exception("journey_coach_scene_unavailable")
        task = None
    if task is None:
        return brief
    return {
        **brief,
        "coach_scene": {
            "task_type": task.task_type,
            "instruction_native": task.instruction_native,
            "prompt_fr": task.prompt_fr,
            "options": [],
            "optional": task.optional,
            "accepted_answers": list(task.accepted_answers),
            "solution_fr": task.solution_fr,
            "translation_native": task.translation_native,
            "estimated_seconds": task.estimated_seconds,
            "evidence_format": task.evidence_format,
        },
    }


def measured_avoidance_rate(db: Session, *, limit: int = 500) -> dict[str, Any]:
    """WP-94 harness honesty: how often a reply asked for a unit and avoided it.

    Reads WP-L4's ``concept_evidence`` on the most recent respond steps
    (``correct`` / ``error`` / ``avoided``; ``undetected`` is left out — no
    detector, no verdict). ``rate`` is ``None`` under 20 verdicts.
    """

    from app.db.models.daily_journey import DailyJourneyStep
    from app.services.journey_contracts import StepKind

    rows = db.scalars(
        select(DailyJourneyStep.private_task)
        .where(DailyJourneyStep.kind == str(StepKind.RESPOND))
        .order_by(DailyJourneyStep.completed_at.desc().nullslast())
        .limit(limit)
    ).all()
    counts = {"correct": 0, "error": 0, "avoided": 0}
    for private in rows:
        for item in (private or {}).get("concept_evidence") or []:
            outcome = item.get("outcome") if isinstance(item, dict) else None
            if outcome in counts:
                counts[outcome] += 1
    total = sum(counts.values())
    return {**counts, "total": total, "rate": (counts["avoided"] / total) if total >= 20 else None}


__all__ = [
    "coach_scene_review_task",
    "measured_avoidance_rate",
    "spaced_item_pending",
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
