"""WP-09 — evidence-backed practical capability progress, and the journey keepsake.

The callables named in ``docs/implementation/atelier-v2/CONTRACTS.md`` §6:

* :func:`build_capability_summary` turns canonical learning evidence into the
  three practical-capability summaries of CONTRACTS §8.
* :func:`build_journey_capability_evidence` answers the same rubric for a
  single journey, so WP-02's finish recap reports the rubric's verdict instead
  of a second, simplified one of its own.
* :func:`mint_journey_keepsake` adds one source-unique collectible to the
  existing Atelier reward path when a daily journey is genuinely completed.
* :func:`build_register_summary` (WP-33) answers the same ladder for one more
  dimension — did the learner address the counterpart the way the counterpart
  addresses them? — from the turns already stored, through the same
  ``_summarize``. One rubric, four dimensions.

Neither commits: the daily-journey state machine owns the transaction.

Policy this module deliberately does **not** own:

* Evidence classification belongs to WP-05. This module reads
  :func:`app.services.journey_learning.read_journey_evidence` and never queries
  an SRS table, never re-derives what "supported" means, and never writes to a
  scheduler.
* Nothing here promotes CEFR or touches a due date. A capability label explains
  an observation; it is not a level.

Two ratified decisions from ``STATUS.md`` are load-bearing here:

* Observations are ordered by ``observed_at``, never by row order or
  ``created_at``. ``created_at`` is ``server_default=func.now()``, so every row
  written inside one PostgreSQL transaction shares a timestamp and ordering by
  it silently drops a later observation.
* A legacy row, or any row whose assistance was never recorded, reports
  ``unknown``. Independence is never inferred from a historic success boolean.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierCollectible
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.user import User
from app.services import pragmatics
from app.services.atelier_rewards import DAILY_JOURNEY_SOURCE_KIND, AtelierRewardService
from app.services.journey_contracts import (
    CAPABILITY_RUBRIC_VERSION,
    AssistanceLevel,
    CapabilityEvidenceView,
    CapabilityKey,
    CapabilityProgressView,
    CapabilityState,
    CapabilitySummary,
    ControlLanguage,
    EvidenceKind,
    InputMode,
    KeepsakeResult,
    StepKind,
    TaskOutcome,
    effect_source_key,
    normalize_control_language,
)
from app.services.journey_learning import JourneyEvidenceRecord, read_journey_evidence
from app.services.learner_copy import learner_text

logger = logging.getLogger(__name__)

#: Journey side effect name; the source key is ``journey:<id>:keepsake``.
KEEPSAKE_EFFECT = "keepsake"
#: Only an honest completion earns one.
KEEPSAKE_COMPLETION_KIND = "complete"

#: How much evidence one summary reads. Bounded so the endpoint stays cheap;
#: the rows come back newest-first.
EVIDENCE_READ_LIMIT = 500
#: The endpoint answers "what can I do", not "here is the whole ledger"
#: (WP-09 §5). Older evidence stays in the canonical records.
MAX_EVIDENCE_PER_CAPABILITY = 10
#: CONTRACTS §8: two independent uses must be at least a day apart.
REPEAT_USE_MIN_SEPARATION = timedelta(hours=24)

#: The scenario objectives: the keys a journey's evidence is *grouped by*.
#:
#: WP-37. Until the register dimension reached the wire this was
#: ``tuple(CapabilityKey)``, which was the same list. It is not any more:
#: ``CapabilityKey.REGISTER`` names a dimension re-read from those same turns,
#: not a fourth scenario, and it has no evidence of its own to read, no title in
#: ``_TITLES`` and no context sentence in ``_CONTEXTS``. Grouping by it would
#: ask the evidence reader for a scenario nothing writes and summarise it twice.
_SCENARIO_KEYS: tuple[CapabilityKey, ...] = tuple(
    key for key in CapabilityKey if key.value != "register"
)

#: Kept under its established name: every caller means "the scenario keys".
_CAPABILITY_ORDER: tuple[CapabilityKey, ...] = _SCENARIO_KEYS

_TITLES: dict[str, dict[CapabilityKey, str]] = {
    "en": {
        CapabilityKey.ORDER_AT_CAFE: "Order at a café",
        CapabilityKey.ARRANGE_MEETING: "Arrange a meeting",
        CapabilityKey.EXPLAIN_DELAY: "Explain a delay",
    },
    "de": {
        CapabilityKey.ORDER_AT_CAFE: "Im Café bestellen",
        CapabilityKey.ARRANGE_MEETING: "Ein Treffen vereinbaren",
        CapabilityKey.EXPLAIN_DELAY: "Eine Verspätung erklären",
    },
    "fr": {
        CapabilityKey.ORDER_AT_CAFE: "Commander au café",
        CapabilityKey.ARRANGE_MEETING: "Fixer un rendez-vous",
        CapabilityKey.EXPLAIN_DELAY: "Expliquer un retard",
    },
}

#: ``(detailed, bare)`` context lines. The detailed form is used only when the
#: journey actually recorded a location and a character, so no context string
#: ever invents a place the learner did not visit.
_CONTEXTS: dict[str, dict[CapabilityKey, tuple[str, str]]] = {
    "en": {
        CapabilityKey.ORDER_AT_CAFE: (
            "Ordered at {location} with {character}.",
            "Ordered at a café.",
        ),
        CapabilityKey.ARRANGE_MEETING: (
            "Arranged a meeting with {character} at {location}.",
            "Arranged a meeting.",
        ),
        CapabilityKey.EXPLAIN_DELAY: (
            "Explained a delay to {character} at {location}.",
            "Explained a delay.",
        ),
    },
    "de": {
        CapabilityKey.ORDER_AT_CAFE: (
            "Im {location} bei {character} bestellt.",
            "Im Café bestellt.",
        ),
        CapabilityKey.ARRANGE_MEETING: (
            "Ein Treffen mit {character} im {location} vereinbart.",
            "Ein Treffen vereinbart.",
        ),
        CapabilityKey.EXPLAIN_DELAY: (
            "{character} im {location} eine Verspätung erklärt.",
            "Eine Verspätung erklärt.",
        ),
    },
    "fr": {
        CapabilityKey.ORDER_AT_CAFE: (
            "Commande passée au {location} avec {character}.",
            "Commande passée au café.",
        ),
        CapabilityKey.ARRANGE_MEETING: (
            "Rendez-vous fixé avec {character} au {location}.",
            "Rendez-vous fixé.",
        ),
        CapabilityKey.EXPLAIN_DELAY: (
            "Retard expliqué à {character} au {location}.",
            "Retard expliqué.",
        ),
    },
}

_SUCCESSFUL_PRODUCTION = frozenset(
    {EvidenceKind.PRODUCED_SUPPORTED, EvidenceKind.PRODUCED_INDEPENDENT}
)

# --------------------------------------------------------------------------
# WP-33 — the `register` dimension
#
# It is graded by `_summarize` like every other dimension, so there is exactly
# one rubric. What is *not* settled yet is the wire contract: `CapabilityKey`
# lists the three scenario keys, and `schemas/daily_journey.py` validates
# against it. Until that enum gains the member — a one-line change owned by the
# integration pass, written out in WP-33-REGISTER.md — the dimension travels
# through `build_register_summary` and stays off the wire list, because a key
# pydantic has never heard of would turn the finish recap into a 500.
# --------------------------------------------------------------------------

#: The real enum member as soon as it exists; the plain string until then.
_REGISTER_KEY: CapabilityKey | str = getattr(CapabilityKey, "REGISTER", "register")
#: Whether the wire contract can carry it yet.
_REGISTER_IS_CONTRACTED = isinstance(_REGISTER_KEY, CapabilityKey)


# --------------------------------------------------------------------------
# Internal view types
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _StepContext:
    """One respond step of one of the learner's own journeys."""

    journey_id: UUID
    location_name: str | None
    character_name: str | None
    #: WP-33. What the learner wrote in this step's turns, and the register the
    #: counterpart used toward them. Both come from records that already exist —
    #: the register dimension adds no column and no writer.
    learner_texts: tuple[str, ...] = ()
    expected_register: str | None = None
    level_band: str | None = None


@dataclass(frozen=True, slots=True)
class _Opportunity:
    """One respond turn, collapsed from every target observation it produced.

    The *turn* is the unit CONTRACTS §8 counts, not the target: one response
    that used two words is one opportunity to order a coffee, not two.
    """

    capability_key: CapabilityKey | str
    journey_id: UUID
    step_id: UUID
    observed_on: date
    observed_at: datetime | None
    modality: InputMode
    independent: bool
    context_native: str
    #: WP-33. ``register_evaluated`` is false whenever nothing observable
    #: happened — no declared or demonstrated counterpart register, or a turn
    #: that addressed nobody. It is never a quiet pass.
    register_evaluated: bool = False
    register_respected: bool = False
    register_expected: str | None = None
    character_native: str | None = None


# --------------------------------------------------------------------------
# Capability summary (CONTRACTS §8)
# --------------------------------------------------------------------------

def build_capability_summary(
    db: Session, *, user: User, control_language: str = "en"
) -> CapabilityProgressView:
    """The learner's three practical capabilities, backed by real evidence.

    Never commits, never writes, never changes CEFR or a due date.

    The rubric, exactly as implemented:

    ``not_tried``
        No successful production recorded for this capability.
    ``with_support``
        At least one successful production in the scenario's response turn
        that does not clear the independent bar — the turn carried assistance,
        or it did not fulfil the objective.
    ``independent_once``
        At least one response turn with no recorded assistance at all, an open
        production (a choice or a tile drag can never qualify), and a
        ``met`` objective outcome.
    ``used_again_later``
        At least two such independent turns on **different journeys**, on
        **different learner-local dates**, at least **24 hours** apart. All
        three conditions, not any one of them.
    ``unknown``
        Historic evidence whose help usage was never recorded. It can raise the
        state out of ``not_tried`` but can never contribute independence.
    """

    language = normalize_control_language(control_language)
    by_capability, unknown_keys = _capability_opportunities(
        db, user=user, language=language
    )
    capabilities = [
        _summarize(
            capability_key=key,
            language=language,
            opportunities=by_capability[key],
            has_unknown_history=key in unknown_keys,
        )
        for key in _CAPABILITY_ORDER
    ]
    if _REGISTER_IS_CONTRACTED:
        # WP-33: one more dimension, scored by the function above and therefore
        # by the same rubric — never a second one. It joins the wire list only
        # once ``CapabilityKey`` carries the member, because
        # ``schemas/daily_journey.py`` validates against that enum and a key it
        # has never heard of would turn the recap into a 500. The one-line
        # enum addition is written out in WP-33-REGISTER.md under "Hooks owed";
        # until it lands, ``build_register_summary`` is the way to read this.
        capabilities.append(_register_summary(by_capability, language=language))
    return CapabilityProgressView(
        rubric_version=CAPABILITY_RUBRIC_VERSION,
        capabilities=capabilities,
    )


def build_register_summary(
    db: Session, *, user: User, control_language: str = "en"
) -> CapabilitySummary:
    """The `register` dimension on its own, for callers the enum has not reached.

    Same opportunities, same ladder, same repeat arithmetic as
    :func:`build_capability_summary`. Reading register through a second scoring
    path is exactly the mistake CONTRACTS §8 records — two rubrics disagreeing
    about one journey — so there is only ever this one.
    """

    language = normalize_control_language(control_language)
    by_capability, _unknown = _capability_opportunities(db, user=user, language=language)
    return _register_summary(by_capability, language=language)


def _register_summary(
    by_capability: dict[CapabilityKey, list[_Opportunity]],
    *,
    language: ControlLanguage,
) -> CapabilitySummary:
    """Every respond turn re-read as one question: right person, right words?

    An opportunity counts as independent for this dimension when it was already
    independent *and* the register held. A turn that addressed nobody is not
    counted at all — with none to count, the state is ``unknown``, which the
    frontend prints as «non évalué» rather than as a pass.
    """

    every: list[_Opportunity] = [item for items in by_capability.values() for item in items]
    evaluated = [
        replace(
            item,
            capability_key=_REGISTER_KEY,
            independent=item.independent and item.register_respected,
            context_native=_register_context_line(item, language=language),
        )
        for item in every
        if item.register_evaluated
    ]
    return _summarize(
        capability_key=_REGISTER_KEY,
        language=language,
        opportunities=evaluated,
        # Turns happened but none of them exercised register: reportable, and
        # reportable as unknown.
        has_unknown_history=bool(every) and not evaluated,
        title_native=learner_text("capability.register_title", language),
    )


def _register_context_line(item: _Opportunity, *, language: ControlLanguage) -> str:
    """Evidence prose for one register observation.

    The detailed form is used only when the journey recorded both the register
    and the character, exactly as ``_context_line`` does for the scenario
    dimensions — a context sentence never names a person or a register the
    records do not carry. It says nothing about how anything was pronounced:
    the evidence is text either way (CONTRACTS §8, WP-27).
    """

    detailed = bool(item.register_expected and item.character_native)
    kind = "with" if detailed else "bare"
    slip = "" if item.register_respected else "slip_"
    return learner_text(
        f"capability.register_context_{slip}{kind}",
        language,
        register=item.register_expected or "",
        character=item.character_native or "",
    )


def build_journey_capability_evidence(
    db: Session,
    *,
    user: User,
    journey_id: UUID,
    control_language: str = "en",
) -> list[CapabilityEvidenceView]:
    """What the rubric says **one journey** proved. The recap's only source.

    Same opportunities, same repeat arithmetic and same state function as
    :func:`build_capability_summary`, filtered to the turns this journey
    recorded — so a finish recap can never claim a state the progress endpoint
    contradicts. A journey that proved nothing returns ``[]``; there is no
    fallback rule that invents a claim.

    Never commits and never writes.
    """

    language = normalize_control_language(control_language)
    by_capability, _unknown = _capability_opportunities(
        db, user=user, language=language
    )
    views: list[CapabilityEvidenceView] = []
    for key in _CAPABILITY_ORDER:
        opportunities = by_capability[key]
        repeats = _repeat_use_ids([item for item in opportunities if item.independent])
        mine = [item for item in opportunities if item.journey_id == journey_id]
        views.extend(
            _evidence_view(capability_key=key, item=item, repeats=repeats)
            for item in sorted(mine, key=_sort_key, reverse=True)
        )
    return views


@dataclass(frozen=True, slots=True)
class RegisterLine:
    """WP-66. The register verdict for one journey, ready to be shown.

    ``line_fr`` is one French sentence — the app's chrome language, beside the
    French ending it sits under. ``reason_native`` says *why* in the learner's
    own language, and is ``None`` when it would only repeat the French line
    (a learner whose control language is already French).
    """

    line_fr: str
    reason_native: str | None
    respected: bool


#: ``register_expected -> pragmatics copy key``. The explanation a slip gets is
#: the same sentence the live corrector would have shown for it, so the recap
#: and the correction can never say different things about one conversation.
_REGISTER_SLIP_COPY: dict[str, str] = {
    "vous": "pragmatics.register_use_vous",
    "tu": "pragmatics.register_use_tu",
}


def build_journey_register_line(
    db: Session,
    *,
    user: User,
    journey_id: UUID,
    control_language: str = "en",
) -> RegisterLine | None:
    """What this one journey showed about register, or ``None``.

    WP-33 graded this dimension and WP-66 is what finally shows it: until now it
    was scored on every respond turn and never printed anywhere, which is the
    phantom-loop mistake in miniature.

    ``None`` means *not evaluated* — no declared or demonstrated counterpart
    register, or a conversation that addressed nobody. That is never dressed up
    as a pass and never as a failure: the resolution step simply carries no
    register line, exactly as it did before this package.

    Reads through the same :func:`_capability_opportunities` and the same
    ``_register_verdict`` as :func:`build_register_summary`. There is one
    rubric; this is a projection of it, not a second opinion.
    """

    language = normalize_control_language(control_language)
    try:
        by_capability, _unknown = _capability_opportunities(
            db, user=user, language=language
        )
    except Exception:  # pragma: no cover - a recap line is never worth the day
        logger.exception("journey_register_line_unavailable")
        return None

    mine = [
        item
        for items in by_capability.values()
        for item in items
        if item.journey_id == journey_id and item.register_evaluated
    ]
    if not mine:
        return None
    # One conversation, one verdict: a slip anywhere in the exchange is the
    # verdict, exactly as `_register_verdict` decides it per step.
    respected = all(item.register_respected for item in mine)
    item = next((row for row in mine if not row.register_respected), mine[0])

    line_fr = _register_context_line(replace(item, register_respected=respected), language="fr")
    if respected:
        reason = _register_context_line(
            replace(item, register_respected=True), language=language
        )
    else:
        copy_key = _REGISTER_SLIP_COPY.get(
            str(item.register_expected or ""), "pragmatics.register_mixed"
        )
        reason = learner_text(copy_key, language)
    reason = (reason or "").strip() or None
    if reason and reason == line_fr:
        # French chrome plus the same sentence twice is not an explanation.
        reason = None
    return RegisterLine(line_fr=line_fr, reason_native=reason, respected=respected)


def _capability_opportunities(
    db: Session, *, user: User, language: ControlLanguage
) -> tuple[dict[CapabilityKey, list[_Opportunity]], set[CapabilityKey]]:
    """Every countable response turn, grouped by capability, plus unknown history."""

    records = read_journey_evidence(
        db,
        user=user,
        scenario_keys=[str(key) for key in _CAPABILITY_ORDER],
        include_legacy=True,
        limit=EVIDENCE_READ_LIMIT,
    )

    respond_steps = _respond_step_context(
        db,
        user=user,
        step_ids={
            record.step_id
            for record in records
            if record.step_id is not None and not record.is_legacy
        },
    )

    unknown_keys: set[CapabilityKey] = set()
    grouped: dict[tuple[CapabilityKey, UUID, UUID], list[JourneyEvidenceRecord]] = {}

    for record in records:
        capability_key = _capability_key_of(record)
        if capability_key is None:
            continue
        if record.is_legacy or not record.assistance_known:
            # Ratified: unknown help usage is reportable as unknown and can
            # never become independence.
            unknown_keys.add(capability_key)
            continue
        step_id = record.step_id
        if step_id is None or step_id not in respond_steps:
            # Recall practice is practice of a target, not of the capability's
            # objective. Only the scenario's response turn is the opportunity.
            continue
        grouped.setdefault((capability_key, respond_steps[step_id].journey_id, step_id), []).append(
            record
        )

    opportunities: list[_Opportunity] = []
    for (capability_key, journey_id, step_id), step_records in grouped.items():
        opportunity = _collapse_turn(
            capability_key=capability_key,
            journey_id=journey_id,
            step_id=step_id,
            records=step_records,
            context=respond_steps[step_id],
            language=language,
        )
        if opportunity is not None:
            opportunities.append(opportunity)

    by_capability: dict[CapabilityKey, list[_Opportunity]] = {
        key: [] for key in _CAPABILITY_ORDER
    }
    for opportunity in opportunities:
        by_capability[opportunity.capability_key].append(opportunity)

    return by_capability, unknown_keys


def _capability_key_of(record: JourneyEvidenceRecord) -> CapabilityKey | None:
    """The capability a record belongs to, including for a legacy row.

    Legacy rows carry no ``capability_key`` — they predate it — but their
    learning session still names the scenario, which is what makes a historic
    café session reportable as *unknown* rather than invisible.
    """

    key = record.capability_key
    if key is None:
        try:
            key = CapabilityKey(str(record.scenario_key))
        except (TypeError, ValueError):
            return None
    # WP-37: `register` is a dimension, not a scenario. Nothing writes evidence
    # under it, and a record that somehow carried it would be grouped under a
    # key `_SCENARIO_KEYS` does not hold.
    return key if key in _SCENARIO_KEYS else None


def _collapse_turn(
    *,
    capability_key: CapabilityKey,
    journey_id: UUID,
    step_id: UUID,
    records: list[JourneyEvidenceRecord],
    context: _StepContext,
    language: ControlLanguage,
) -> _Opportunity | None:
    """One respond turn's records become at most one opportunity.

    A turn counts as *independent* only when nothing in it was assisted. A hint
    revealed for one target still helped the sentence that used the other, so
    the whole turn is supported production (CONTRACTS §7).
    """

    successes = [
        record
        for record in records
        if record.evidence_kind in _SUCCESSFUL_PRODUCTION and record.is_open_production
    ]
    if not successes:
        return None

    modalities = [record.modality for record in successes if record.modality is not None]
    if not modalities:
        # A record without a recorded modality cannot be described honestly:
        # calling it text would be a guess, calling it voice would be a claim
        # about pronunciation nobody observed.
        return None

    unassisted = all(
        record.assistance is AssistanceLevel.NONE
        for record in records
        if record.assistance is not None
    )
    met = any(record.task_outcome is TaskOutcome.MET for record in successes)
    open_independent = any(
        record.evidence_kind is EvidenceKind.PRODUCED_INDEPENDENT
        and record.is_open_production
        and record.assistance is AssistanceLevel.NONE
        for record in successes
    )

    latest = max(
        successes,
        key=lambda record: (
            record.observed_at or datetime.min.replace(tzinfo=UTC),
            record.observed_on,
        ),
    )
    evaluated, respected = _register_verdict(context)
    return _Opportunity(
        register_expected=context.expected_register,
        character_native=(context.character_name or "").strip() or None,
        capability_key=capability_key,
        journey_id=journey_id,
        step_id=step_id,
        observed_on=latest.observed_on,
        observed_at=latest.observed_at,
        # Voice only when a voice observation actually backs the turn.
        modality=InputMode.VOICE if InputMode.VOICE in modalities else InputMode.TEXT,
        independent=bool(unassisted and met and open_independent),
        context_native=_context_line(
            capability_key=capability_key, language=language, context=context
        ),
        register_evaluated=evaluated,
        register_respected=respected,
    )


def _register_verdict(context: _StepContext) -> tuple[bool, bool]:
    """``(evaluated, respected)`` for one respond step's whole exchange.

    Every learner line in the step is assessed with the same deterministic
    detectors the grader used live (``app.services.pragmatics``), so the
    dimension and the correction the learner saw can never disagree. One slip
    anywhere in the exchange makes the turn a slip: a scene is one
    conversation, and getting it right after being told is what the *next*
    journey is for.
    """

    evaluated = False
    respected = True
    for text in context.learner_texts:
        assessment = pragmatics.assess_register(
            text,
            expected_register=context.expected_register,
            level_band=context.level_band,
        )
        if not assessment.evaluated:
            continue
        evaluated = True
        if not assessment.respected:
            respected = False
    return evaluated, evaluated and respected


def _context_line(
    *, capability_key: CapabilityKey, language: ControlLanguage, context: _StepContext
) -> str:
    detailed, bare = _CONTEXTS.get(language, _CONTEXTS["en"])[capability_key]
    location = (context.location_name or "").strip()
    character = (context.character_name or "").strip()
    if location and character:
        return detailed.format(location=location, character=character)
    return bare


def _sort_key(opportunity: _Opportunity) -> tuple[datetime, date, str]:
    return (
        opportunity.observed_at or datetime.min.replace(tzinfo=UTC),
        opportunity.observed_on,
        str(opportunity.step_id),
    )


def _repeat_use_ids(independent: list[_Opportunity]) -> set[UUID]:
    """Step ids of the independent turns that close a genuine repeat pair.

    All three CONTRACTS §8 conditions must hold together: a different journey,
    a different learner-local date, and at least 24 hours of separation.
    Ordering uses ``observed_at`` because two turns inside one journey share a
    ``created_at``.
    """

    ordered = sorted(independent, key=_sort_key)
    repeats: set[UUID] = set()
    for index, later in enumerate(ordered):
        if later.observed_at is None:
            continue
        for earlier in ordered[:index]:
            if earlier.observed_at is None:
                continue
            if earlier.journey_id == later.journey_id:
                continue
            if earlier.observed_on == later.observed_on:
                continue
            if later.observed_at - earlier.observed_at < REPEAT_USE_MIN_SEPARATION:
                continue
            repeats.add(later.step_id)
            break
    return repeats


def _evidence_view(
    *, capability_key: CapabilityKey, item: _Opportunity, repeats: set[UUID]
) -> CapabilityEvidenceView:
    """One opportunity's own state. The single place a state is named.

    Both the progress endpoint and the finish recap render evidence through
    this function, which is what makes them incapable of disagreeing.
    """

    return CapabilityEvidenceView(
        capability_key=capability_key,
        state=(
            CapabilityState.USED_AGAIN_LATER
            if item.step_id in repeats
            else CapabilityState.INDEPENDENT_ONCE
            if item.independent
            else CapabilityState.WITH_SUPPORT
        ),
        modality=item.modality,
        observed_on=item.observed_on,
        context_native=item.context_native,
    )


def _summarize(
    *,
    capability_key: CapabilityKey | str,
    language: ControlLanguage,
    opportunities: list[_Opportunity],
    has_unknown_history: bool,
    title_native: str | None = None,
) -> CapabilitySummary:
    independent = [item for item in opportunities if item.independent]
    supported = [item for item in opportunities if not item.independent]
    repeats = _repeat_use_ids(independent)

    if repeats:
        state = CapabilityState.USED_AGAIN_LATER
        # The state is backed by the whole run of independent uses, but it was
        # *reached* on the day the repeat closed.
        backing = independent
        qualifying = [item for item in independent if item.step_id in repeats]
    elif independent:
        state = CapabilityState.INDEPENDENT_ONCE
        backing = qualifying = independent
    elif supported:
        state = CapabilityState.WITH_SUPPORT
        backing = qualifying = supported
    elif has_unknown_history:
        state = CapabilityState.UNKNOWN
        backing = qualifying = []
    else:
        state = CapabilityState.NOT_TRIED
        backing = qualifying = []

    modalities = [
        mode for mode in (InputMode.TEXT, InputMode.VOICE)
        if any(item.modality is mode for item in backing)
    ]
    latest_qualifying_on = max((item.observed_on for item in qualifying), default=None)

    evidence = [
        _evidence_view(capability_key=capability_key, item=item, repeats=repeats)
        for item in sorted(opportunities, key=_sort_key, reverse=True)[
            :MAX_EVIDENCE_PER_CAPABILITY
        ]
    ]

    return CapabilitySummary(
        capability_key=capability_key,
        title_native=title_native
        or _TITLES.get(language, _TITLES["en"])[capability_key],
        state=state,
        modalities=modalities,
        latest_qualifying_on=latest_qualifying_on,
        evidence=evidence,
    )


def _respond_step_context(
    db: Session, *, user: User, step_ids: set[UUID]
) -> dict[UUID, _StepContext]:
    """Map each step id that is a *respond* step of the learner's own journey.

    Only the scenario's response turn can demonstrate the practical objective,
    so this is what keeps a one-word recall gap-fill from being reported as
    "ordered at a café independently". Ownership is re-checked here even though
    the evidence rows are already the learner's own.
    """

    if not step_ids:
        return {}
    resolved: dict[UUID, _StepContext] = {}
    ordered = list(step_ids)
    for start in range(0, len(ordered), 200):
        chunk = ordered[start : start + 200]
        rows = (
            db.query(
                DailyJourneyStep.id,
                DailyJourney.id,
                DailyJourney.scenario_snapshot,
                DailyJourneyStep.private_task,
                DailyJourneyStep.public_prompt,
                DailyJourney.content_version,
                DailyJourney.level_band,
            )
            .join(DailyJourney, DailyJourneyStep.journey_id == DailyJourney.id)
            .filter(
                DailyJourneyStep.id.in_(chunk),
                DailyJourneyStep.kind == str(StepKind.RESPOND),
                DailyJourney.user_id == user.id,
            )
            .all()
        )
        for (
            step_id,
            journey_id,
            snapshot,
            private_task,
            public_prompt,
            content_version,
            level_band,
        ) in rows:
            payload = snapshot if isinstance(snapshot, dict) else {}
            learner_texts, character_texts = _turn_texts(private_task, public_prompt)
            resolved[step_id] = _StepContext(
                journey_id=journey_id,
                location_name=payload.get("location_name"),
                character_name=payload.get("character_name"),
                learner_texts=learner_texts,
                expected_register=_expected_register(
                    scenario_key=payload.get("scenario_key"),
                    content_version=content_version,
                    character_texts=character_texts,
                ),
                level_band=str(level_band) if level_band else None,
            )
    return resolved


def _turn_texts(private_task: Any, public_prompt: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(learner lines, counterpart lines)`` of one respond step, oldest first.

    WP-02 already persists the exchange as ``private_task["turns"]``; this reads
    it and derives nothing else from it. Evaluator material never leaves this
    module — only a boolean about register does.
    """

    private = private_task if isinstance(private_task, dict) else {}
    prompt = public_prompt if isinstance(public_prompt, dict) else {}
    learner: list[str] = []
    character: list[str] = []
    opening = prompt.get("character_line_fr")
    if isinstance(opening, str) and opening.strip():
        character.append(opening)
    for entry in private.get("turns") or []:
        if not isinstance(entry, dict):
            continue
        for key, bucket in (("learner", learner), ("character", character)):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                bucket.append(value)
    return tuple(learner), tuple(character)


def _expected_register(
    *, scenario_key: Any, content_version: Any, character_texts: tuple[str, ...]
) -> str | None:
    """The register the counterpart used with this learner, in *this* journey.

    What the character actually said comes first: a generated scene may reuse an
    authored scenario key and still tutoie the learner, and the evidence of the
    scene outranks the declaration about it. The authored
    ``counterpart_register`` is the fallback, and ``None`` — no declaration, no
    unambiguous demonstration — is reported as "non évalué".
    """

    observed = pragmatics.counterpart_register(list(character_texts))
    if observed is not None:
        return observed
    declared = pragmatics.declared_counterpart_register(
        str(scenario_key) if scenario_key else None,
        content_version=str(content_version) if content_version else None,
    )
    return declared.expected if declared is not None else None


# --------------------------------------------------------------------------
# Keepsake (WP-09 §4)
# --------------------------------------------------------------------------

def mint_journey_keepsake(
    db: Session,
    *,
    user: User,
    journey_id: UUID,
    scenario_key: str,
    completion_kind: str,
) -> KeepsakeResult:
    """Add one keepsake to the existing source-unique collectible path.

    * No keepsake for an early exit or any other non-completion.
    * Keyed by ``journey:<journey_id>:keepsake``, so an HTTP retry finds the
      collectible it already minted and reports ``already_minted`` instead of
      minting a second one.
    * Never commits: the row is claimed with a flush inside a SAVEPOINT and the
      daily-journey transaction commits it.
    * Existing collections and thresholds are untouched — this is an ordinary
      logo token from a new source, exactly like the mission token.
    """

    if completion_kind != KEEPSAKE_COMPLETION_KIND:
        logger.info(
            "journey_keepsake_skipped",
            extra={"journey_id": str(journey_id), "completion_kind": completion_kind},
        )
        return KeepsakeResult(minted=False, collectible_ids=[])

    journey = db.get(DailyJourney, journey_id)
    if journey is not None and journey.user_id != user.id:
        # Never mint into the caller's collection for someone else's journey.
        logger.warning(
            "journey_keepsake_ownership_refused", extra={"journey_id": str(journey_id)}
        )
        return KeepsakeResult(minted=False, collectible_ids=[])

    snapshot: dict[str, Any] = {}
    if journey is not None and isinstance(journey.scenario_snapshot, dict):
        snapshot = journey.scenario_snapshot

    source_ref = effect_source_key(journey_id=journey_id, effect=KEEPSAKE_EFFECT)
    service = AtelierRewardService(db)
    item, created = service.mint_daily_journey_keepsake(
        user_id=user.id,
        source_ref=source_ref,
        metadata={
            "name": "Daily journey keepsake",
            "date": (journey.local_date.isoformat() if journey is not None else None)
            or datetime.now(UTC).date().isoformat(),
            "journey_id": str(journey_id),
            "scenario_key": str(scenario_key),
            "scenario_title_fr": snapshot.get("title_fr"),
            "location_name": snapshot.get("location_name"),
            "character_name": snapshot.get("character_name"),
            "completion_kind": completion_kind,
            "source": "daily_journey",
            "credit": 3,
        },
        commit=False,
    )
    return KeepsakeResult(
        minted=created,
        collectible_ids=[str(item.id)],
        already_minted=not created,
    )


def journey_keepsake(db: Session, *, user: User, journey_id: UUID) -> AtelierCollectible | None:
    """The keepsake already minted for a journey, if any. Read-only helper."""

    return (
        db.query(AtelierCollectible)
        .filter(
            AtelierCollectible.user_id == user.id,
            AtelierCollectible.source_kind == DAILY_JOURNEY_SOURCE_KIND,
            AtelierCollectible.source_ref
            == effect_source_key(journey_id=journey_id, effect=KEEPSAKE_EFFECT),
        )
        .first()
    )


__all__ = [
    "EVIDENCE_READ_LIMIT",
    "KEEPSAKE_COMPLETION_KIND",
    "KEEPSAKE_EFFECT",
    "MAX_EVIDENCE_PER_CAPABILITY",
    "REPEAT_USE_MIN_SEPARATION",
    "RegisterLine",
    "build_capability_summary",
    "build_journey_capability_evidence",
    "build_journey_register_line",
    "build_register_summary",
    "journey_keepsake",
    "mint_journey_keepsake",
]
