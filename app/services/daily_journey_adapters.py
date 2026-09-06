"""Typed domain seams for the daily journey state machine (WP-02).

WP-02 owns ordering, persistence and idempotency. It owns **none** of the
domain work. Everything the state machine needs from another package arrives
through :class:`JourneyAdapters`, whose members resolve at runtime to:

===========================  ==========================================
Adapter member               Real implementation (owner)
===========================  ==========================================
``content``                  ``app.services.journey_content`` (WP-03)
``planner``                  ``app.services.journey_planner`` (WP-04)
``learning``                 ``app.services.journey_learning`` (WP-05)
``conversation``             ``app.services.journey_conversation`` (WP-06)
``capabilities``             ``app.services.journey_capabilities`` (WP-09)
``events``                   ``app.services.journey_events`` (WP-11)
===========================  ==========================================

Resolution has exactly three outcomes, and the difference between the last two
is the whole point:

1. **The real module imports and exports the frozen callable** — it wins. A stub
   can never shadow a real implementation.
2. **The module is genuinely absent** (a ``ModuleNotFoundError`` naming that very
   module: the package has not been written yet) — a deterministic
   ``_Missing*Adapter`` stands in and a warning is logged, so the HTTP surface
   stays testable before WP-06/09/11 land. Stubs are **not** production
   behaviour: their content is tagged ``journey-content-stub-v0``, they never
   write to a learning record, a serial thread or a collectible, and every
   evidence reference they mint is prefixed ``stub:``.
3. **The module exists but cannot be imported** — a syntax error, null bytes, a
   missing dependency of *its own*. This is **never** stubbed. Silently swapping
   a broken ``journey_learning`` for a stub would keep the API answering 200
   while no canonical learning credit was written at all. The seam resolves to
   :class:`_BrokenAdapter`, every call raises :class:`AdapterUnavailable`, and
   the state machine turns that into an honest ``unavailable`` journey or a 503
   ``generation_unavailable``.

Seams with no stub at all (the planner and the conversation, now that WP-04 and
WP-06 have landed) take path 3 for absence too: a journey assembled by a fake
planner, or a reply invented by a fake conversation, is not a journey.
"""
from __future__ import annotations

import logging
from importlib import import_module
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.services.journey_contracts import (
    AppliedEvidence,
    AssistanceLevel,
    AttemptAnswer,
    CapabilityEvidenceView,
    CapabilityKey,
    CapabilityProgressView,
    CapabilityState,
    CapabilitySummary,
    ContentUnavailable,
    ControlLanguage,
    EvidenceKind,
    InputMode,
    KeepsakeResult,
    LearningCandidate,
    PlannedJourney,
    RecallEvaluation,
    RecallTask,
    ResponseEvaluation,
    ResponseTask,
    ScenarioBrief,
    ScenarioContextResult,
    StoryOutcomeProposal,
    StoryOutcomeRef,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
    normalize_answer_text,
)

logger = logging.getLogger(__name__)

STUB_CONTENT_VERSION = "journey-content-stub-v0"
STUB_EVIDENCE_PREFIX = "stub:"


class AdapterUnavailable(RuntimeError):
    """A domain seam cannot serve this call, and pretending otherwise would lie.

    Raised by :class:`_BrokenAdapter` when a module that *exists* could not be
    imported, or when a seam that has no stub is missing. The state machine maps
    it onto an ``unavailable`` journey / 503 ``generation_unavailable`` — never
    onto a success response.
    """

    def __init__(self, module_name: str, reason: str) -> None:
        super().__init__(f"app.services.{module_name} is unavailable: {reason}")
        self.module_name = module_name
        self.reason = reason


class _BrokenAdapter:
    """Fails loudly on every call. Never fakes a result."""

    is_stub = False
    is_broken = True

    def __init__(self, module_name: str, reason: str) -> None:
        self.module_name = module_name
        self.reason = reason

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):  # pragma: no cover - attribute protocol
            raise AttributeError(name)

        def _refuse(*_args: Any, **_kwargs: Any) -> Any:
            raise AdapterUnavailable(self.module_name, self.reason)

        return _refuse


# ---------------------------------------------------------------------------
# Protocols — the exact frozen signatures from CONTRACT-FREEZE.md
# ---------------------------------------------------------------------------


@runtime_checkable
class ContentAdapter(Protocol):
    def build_scenario_context(
        self,
        db: Any,
        *,
        user: Any,
        scenario_key: str | None = None,
        input_mode: InputMode,
    ) -> ScenarioContextResult: ...

    # Optional, WP-03: the pinned lookup used to rebuild an already-planned
    # journey's brief from its stored content_version and level_band.
    def resolve_scenario_brief(
        self,
        db: Any,
        *,
        user: Any,
        scenario_key: Any,
        content_version: str | None = None,
        level_band: str | None = None,
        input_mode: InputMode = InputMode.TEXT,
        allow_generation: bool = True,
        bind_serial: bool = True,
    ) -> ScenarioContextResult: ...


@runtime_checkable
class PlannerAdapter(Protocol):
    def plan_journey(
        self,
        *,
        scenario: ScenarioBrief,
        candidates: list[LearningCandidate],
        budget_seconds: int,
        pace: Any,
    ) -> PlannedJourney: ...


@runtime_checkable
class LearningAdapter(Protocol):
    def select_learning_candidates(
        self, db: Any, *, user: Any, scenario: ScenarioBrief, limit: int
    ) -> list[LearningCandidate]: ...

    def ensure_journey_learning_session(
        self, db: Any, *, user: Any, journey_id: UUID, scenario_key: str
    ) -> Any: ...

    def evaluate_recall(
        self,
        db: Any,
        *,
        user: Any,
        task: RecallTask,
        answer: AttemptAnswer,
        assistance: AssistanceLevel,
    ) -> RecallEvaluation: ...

    def apply_learning_evidence(
        self,
        db: Any,
        *,
        user: Any,
        journey_id: UUID,
        step_id: UUID,
        session: Any,
        evaluation: Any,
        modality: InputMode,
        timezone: str | None = None,
    ) -> AppliedEvidence: ...


@runtime_checkable
class ConversationAdapter(Protocol):
    def evaluate_response(
        self,
        db: Any,
        *,
        user: Any,
        scenario: ScenarioBrief,
        task: ResponseTask,
        answer: AttemptAnswer,
        turn_index: int,
        assistance: AssistanceLevel,
        history: list[dict[str, str]] | None = None,
    ) -> ResponseEvaluation: ...

    def story_outcome_source_key(self, journey_id: UUID | str) -> str: ...

    #: Normal turns plus at most one optional repair (CONTRACTS §3).
    def turn_budget(self, task: ResponseTask) -> int: ...

    #: "authored" | "model" | "none" — an authored line must never be shown as
    #: a live model response.
    def reply_source(self, evaluation: ResponseEvaluation) -> str: ...

    #: The NEUTRAL declared fallback, used when nothing actually got across.
    def default_outcome_key(self, task: ResponseTask, scenario_key: str) -> str | None: ...

    def resolution_line(self, scenario: ScenarioBrief, outcome_key: str) -> str | None: ...

    def resolution_summary(
        self, scenario: ScenarioBrief, outcome_key: str
    ) -> str | None: ...

    def apply_story_outcome(
        self,
        db: Any,
        *,
        user: Any,
        journey_id: UUID,
        scenario: ScenarioBrief,
        proposal: StoryOutcomeProposal,
        source_key: str,
    ) -> StoryOutcomeRef: ...


@runtime_checkable
class CapabilitiesAdapter(Protocol):
    def build_capability_summary(
        self, db: Any, *, user: Any, control_language: ControlLanguage
    ) -> CapabilityProgressView: ...

    #: The CONTRACTS §8 rubric's verdict on one journey. The finish recap has
    #: no rubric of its own: WP-09 is the single authority, so the recap and
    #: ``GET /capabilities/progress`` cannot disagree about the same journey.
    def build_journey_capability_evidence(
        self, db: Any, *, user: Any, journey_id: UUID, control_language: ControlLanguage
    ) -> list[CapabilityEvidenceView]: ...

    def mint_journey_keepsake(
        self,
        db: Any,
        *,
        user: Any,
        journey_id: UUID,
        scenario_key: str,
        completion_kind: str,
    ) -> KeepsakeResult: ...


@runtime_checkable
class EventsAdapter(Protocol):
    def record_journey_event(
        self,
        db: Any,
        *,
        event_name: str,
        user_id: UUID | None,
        source_key: str,
        metadata: dict[str, Any],
    ) -> Any: ...


# ---------------------------------------------------------------------------
# Deterministic stubs — clearly non-production
# ---------------------------------------------------------------------------

_STUB_TARGET = TargetRef(
    kind=TargetKind.VOCABULARY,
    id="stub-target-un-cafe",
    label_fr="un café",
    label_native="a coffee",
)


def _stub_response_task() -> ResponseTask:
    return ResponseTask(
        objective_native="Say what you would like to drink and where you want to sit.",
        character_id="margaux_barman",
        character_name="Margaux",
        opening_line_fr="Alors, qu'est-ce que je vous sers ?",
        max_turns=2,
        repair_allowed=True,
        targets=[_STUB_TARGET],
        required_intents=["order_drink"],
        allowed_outcomes=["served_at_counter", "served_at_terrace"],
        rubric_native="STUB rubric: any non-trivial French answer counts as met.",
        suggested_response_fr="Je voudrais un café, s'il vous plaît.",
        hint_native="Start with 'Je voudrais…'.",
        translation_native="So, what can I get you?",
        estimated_seconds=120,
    )


class _MissingContentAdapter:
    """Deterministic stand-in for WP-03 ``journey_content``."""

    is_stub = True

    def build_scenario_context(
        self,
        db: Any,
        *,
        user: Any,
        scenario_key: str | None = None,
        input_mode: InputMode = InputMode.TEXT,
    ) -> ScenarioContextResult:
        return ScenarioBrief(
            scenario_key=CapabilityKey.ORDER_AT_CAFE,
            content_version=STUB_CONTENT_VERSION,
            title_fr="Un café au Mistral",
            objective_key="order_at_cafe.counter_drink",
            objective_native=(
                "Order a hot drink at the counter and say where you want to sit."
            ),
            level_band="A1",
            character_id="margaux_barman",
            character_name="Margaux",
            location_id="le_mistral",
            location_name="Le Mistral",
            image_url=None,
            setup_fr="Il pleut sur le canal. Tu pousses la porte du Mistral.",
            setup_native="It is raining on the canal. You push open the door of Le Mistral.",
            opening_line_fr="Tiens, bonjour !",
            response_task=_stub_response_task(),
            resolution_lines={
                "served_at_counter": "Un café pour vous, au comptoir.",
                "served_at_terrace": "Un café en terrasse, ça arrive.",
            },
            resolution_summaries={
                "served_at_counter": "Margaux served your coffee at the counter.",
                "served_at_terrace": "Margaux served your coffee on the terrace.",
            },
            estimated_seconds=264,
            is_authored_fallback=True,
        )


class _MissingLearningAdapter:
    """Deterministic stand-in for WP-05 ``journey_learning``.

    It never writes to ``UserVocabularyProgress``, ``ReviewLog``, ``UserError``
    or any other canonical learning record. Evidence references are ``stub:``.
    """

    is_stub = True

    def select_learning_candidates(
        self, db: Any, *, user: Any, scenario: ScenarioBrief, limit: int
    ) -> list[LearningCandidate]:
        if limit <= 0:
            return []
        return [
            LearningCandidate(
                target=_STUB_TARGET,
                priority_score=0.0,
                due_since_days=0,
                estimated_seconds=45,
                is_new=False,
                relevance=1.0,
                source_item_type="stub",
            )
        ]

    def ensure_journey_learning_session(
        self, db: Any, *, user: Any, journey_id: UUID, scenario_key: str
    ) -> Any:
        return None

    def evaluate_recall(
        self,
        db: Any,
        *,
        user: Any,
        task: RecallTask,
        answer: AttemptAnswer,
        assistance: AssistanceLevel,
    ) -> RecallEvaluation:
        correct = False
        if task.correct_option_id and answer.option_id:
            correct = answer.option_id == task.correct_option_id
        elif task.correct_tile_order and answer.tile_ids:
            correct = list(answer.tile_ids) == list(task.correct_tile_order)
        elif task.accepted_answers:
            normalized = normalize_answer_text(answer.text).casefold()
            correct = any(
                normalize_answer_text(candidate).casefold() == normalized
                for candidate in task.accepted_answers
            )
        if correct:
            evidence = EvidenceKind.RECOGNIZED
            outcome = TaskOutcome.MET
        else:
            evidence = EvidenceKind.NOT_YET
            outcome = TaskOutcome.NOT_YET
        return RecallEvaluation(
            outcome=outcome,
            assistance=assistance,
            observations=[
                TargetObservation(
                    target=task.target,
                    evidence_kind=evidence,
                    assistance=assistance,
                    modality=answer.mode,
                    learner_text=answer.text or answer.option_id,
                )
            ],
        )

    def apply_learning_evidence(
        self,
        db: Any,
        *,
        user: Any,
        journey_id: UUID,
        step_id: UUID,
        session: Any,
        evaluation: Any,
        modality: InputMode,
        timezone: str | None = None,
    ) -> AppliedEvidence:
        return AppliedEvidence(
            evidence_ref=f"{STUB_EVIDENCE_PREFIX}{journey_id}:{step_id}",
            source_keys=[],
            applied_target_ids=[],
        )


_CAPABILITY_TITLES: dict[CapabilityKey, str] = {
    CapabilityKey.ORDER_AT_CAFE: "Order at a café",
    CapabilityKey.ARRANGE_MEETING: "Arrange a meeting",
    CapabilityKey.EXPLAIN_DELAY: "Explain a delay",
}


class _MissingCapabilitiesAdapter:
    """Deterministic stand-in for WP-09 ``journey_capabilities``.

    Returns the typed empty summary CONTRACTS §8 demands for a learner with no
    evidence: every capability ``not_tried``, never an inferred success.
    """

    is_stub = True

    def build_capability_summary(
        self, db: Any, *, user: Any, control_language: ControlLanguage = "en"
    ) -> CapabilityProgressView:
        from app.services.journey_contracts import CAPABILITY_RUBRIC_VERSION

        return CapabilityProgressView(
            rubric_version=CAPABILITY_RUBRIC_VERSION,
            capabilities=[
                CapabilitySummary(
                    capability_key=key,
                    title_native=title,
                    state=CapabilityState.NOT_TRIED,
                    modalities=[],
                    latest_qualifying_on=None,
                    evidence=[],
                )
                for key, title in _CAPABILITY_TITLES.items()
            ],
        )

    def build_journey_capability_evidence(
        self,
        db: Any,
        *,
        user: Any,
        journey_id: UUID,
        control_language: ControlLanguage = "en",
    ) -> list[CapabilityEvidenceView]:
        # A stub has no evidence, so it claims nothing. The recap shows what
        # the rubric found, and the rubric found nothing.
        return []

    def mint_journey_keepsake(
        self,
        db: Any,
        *,
        user: Any,
        journey_id: UUID,
        scenario_key: str,
        completion_kind: str,
    ) -> KeepsakeResult:
        return KeepsakeResult(minted=False, collectible_ids=[])


class _MissingEventsAdapter:
    """Deterministic stand-in for WP-11 ``journey_events``. Records nothing."""

    is_stub = True

    def record_journey_event(
        self,
        db: Any,
        *,
        event_name: str,
        user_id: UUID | None,
        source_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return None


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class JourneyAdapters:
    """The injection seam. Pass explicit members in tests; resolve otherwise."""

    __slots__ = ("content", "planner", "learning", "conversation", "capabilities", "events")

    def __init__(
        self,
        *,
        content: ContentAdapter,
        planner: PlannerAdapter,
        learning: LearningAdapter,
        conversation: ConversationAdapter,
        capabilities: CapabilitiesAdapter,
        events: EventsAdapter,
    ) -> None:
        self.content = content
        self.planner = planner
        self.learning = learning
        self.conversation = conversation
        self.capabilities = capabilities
        self.events = events

    def _members(self) -> tuple[Any, ...]:
        return (
            self.content,
            self.planner,
            self.learning,
            self.conversation,
            self.capabilities,
            self.events,
        )

    @property
    def uses_stubs(self) -> bool:
        return any(getattr(member, "is_stub", False) for member in self._members())

    @property
    def broken_modules(self) -> list[str]:
        """Seams that will refuse every call instead of faking one."""

        return [
            member.module_name
            for member in self._members()
            if getattr(member, "is_broken", False)
        ]


def _absent(module_name: str, stub: Any, detail: str) -> Any:
    """The package has not been written yet: stub it, loudly, or fail honestly."""

    if stub is None:
        logger.error(
            "daily_journey: app.services.%s is unavailable (%s) and has no stub; "
            "affected journeys will report generation_unavailable.",
            module_name,
            detail,
        )
        return _BrokenAdapter(module_name, detail)
    logger.warning(
        "daily_journey: app.services.%s is unavailable (%s); using %s. "
        "This stub is not production behaviour.",
        module_name,
        detail,
        type(stub).__name__,
    )
    return stub


def _resolve(module_name: str, required: tuple[str, ...], stub: Any) -> Any:
    """Prefer the real module. Never paper over a broken one.

    A module that is *absent* may be stubbed. A module that *exists but raises
    on import* may not: swapping it for a stub would keep the API answering 200
    while nothing canonical was written.
    """

    target = f"app.services.{module_name}"
    try:
        module = import_module(target)
    except ModuleNotFoundError as exc:
        if exc.name == target:
            return _absent(module_name, stub, "not written yet")
        # ModuleNotFoundError for one of *its* dependencies: the package exists
        # and is broken. That is an error to fix, not a reason to fake success.
        logger.exception(
            "daily_journey: app.services.%s exists but its dependency %r is "
            "missing; refusing to stub it.",
            module_name,
            exc.name,
        )
        return _BrokenAdapter(module_name, "import_failed")
    except Exception:
        logger.exception(
            "daily_journey: app.services.%s exists but failed to import; "
            "refusing to stub it. Fix the module.",
            module_name,
        )
        return _BrokenAdapter(module_name, "import_failed")

    missing = [name for name in required if not callable(getattr(module, name, None))]
    if missing:
        return _absent(module_name, stub, f"does not export {', '.join(missing)}")
    return module


def build_default_adapters() -> JourneyAdapters:
    """Resolve every domain seam, preferring the real module every time."""

    return JourneyAdapters(
        content=_resolve(
            "journey_content", ("build_scenario_context",), _MissingContentAdapter()
        ),
        # WP-04 has landed: there is deliberately no planner stub. A journey
        # assembled by a fake planner is a fake journey.
        planner=_resolve("journey_planner", ("plan_journey",), None),
        learning=_resolve(
            "journey_learning",
            (
                "select_learning_candidates",
                "ensure_journey_learning_session",
                "evaluate_recall",
                "apply_learning_evidence",
            ),
            _MissingLearningAdapter(),
        ),
        # WP-06 has landed: no conversation stub either. A scripted reply
        # presented as a live one is exactly what reply_source exists to stop.
        conversation=_resolve(
            "journey_conversation",
            ("evaluate_response", "apply_story_outcome"),
            None,
        ),
        capabilities=_resolve(
            "journey_capabilities",
            (
                "build_capability_summary",
                "build_journey_capability_evidence",
                "mint_journey_keepsake",
            ),
            _MissingCapabilitiesAdapter(),
        ),
        events=_resolve(
            "journey_events", ("record_journey_event",), _MissingEventsAdapter()
        ),
    )


def preview_scenario(
    adapters: JourneyAdapters, db: Any, *, user: Any, input_mode: InputMode
) -> ScenarioBrief | ContentUnavailable:
    """Cheap ``available`` descriptor for ``GET /today``.

    ``GET`` must never pay for generation (CONTRACTS §4), so the provider-free
    routes are tried first:

    1. ``describe_available_scenario`` — reserved for a future explicit preview.
    2. WP-03's ``list_available_scenarios``, which documents itself as costing
       nothing: generation off, no image produced.
    3. ``build_scenario_context`` — only reached with the deterministic stub,
       which never calls a provider either.
    """

    describe = getattr(adapters.content, "describe_available_scenario", None)
    if callable(describe):
        result = describe(db, user=user, input_mode=input_mode)
        if result is not None:
            return result

    catalog = getattr(adapters.content, "list_available_scenarios", None)
    if callable(catalog):
        offered = catalog(db, user=user, input_mode=input_mode)
        if offered:
            return offered[0]
        return ContentUnavailable(reason="no_scenario_content", retry_allowed=False)

    return adapters.content.build_scenario_context(
        db, user=user, scenario_key=None, input_mode=input_mode
    )


__all__ = [
    "AdapterUnavailable",
    "CapabilitiesAdapter",
    "ContentAdapter",
    "ConversationAdapter",
    "EventsAdapter",
    "JourneyAdapters",
    "LearningAdapter",
    "PlannerAdapter",
    "STUB_CONTENT_VERSION",
    "STUB_EVIDENCE_PREFIX",
    "build_default_adapters",
    "preview_scenario",
]
