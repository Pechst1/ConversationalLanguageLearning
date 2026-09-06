# Atelier V2 — WP-00 frozen wire contract (contract_version 1)

Frozen 2026-09-05 by the integration owner against [CONTRACTS.md](CONTRACTS.md).
This file resolves CONTRACTS.md to exact field names so WP-02 (producer) and
WP-04/05/06/07/09/11 (consumers) cannot invent divergent private shapes.

`tests/fixtures/daily_journey_v1/` is the executable form of this document.
WP-02 adds schema validation of every `public/*.json` against the real Pydantic
response models (`tests/test_daily_journey_fixtures.py`).

## Documented extensions to CONTRACTS §4

Recorded here rather than as per-package inventions:

1. `TodayEnvelope.control_language: 'en'|'de'|'fr'` — CONTRACTS §10 requires
   learner-language controls; the envelope must state which language the
   `*_native` strings were resolved into. Explicit English fallback for other
   learner languages.
2. Every localized string is suffixed `_native` (control language) or `_fr`
   (French content). No mixed-language field.
3. `PublicStep.assistance_used: AssistanceLevel[]` — the renderer must show what
   was already revealed after a resume; server-recorded, never client-asserted.
4. Error bodies use the existing FastAPI `{"detail": ...}` convention with a
   structured object (§5 codes).

## Types

```ts
export const DAILY_JOURNEY_CONTRACT_VERSION = 1;

export type ControlLanguage = 'en' | 'de' | 'fr';
export type JourneyStatus =
  | 'preparing' | 'active' | 'paused' | 'completed' | 'ended_early' | 'unavailable';
export type StepKind = 'scene' | 'recall' | 'respond' | 'resolution';
export type StepStatus = 'pending' | 'active' | 'completed' | 'skipped';
export type InputMode = 'text' | 'voice';
export type HelpKind = 'hint' | 'translation' | 'solution' | 'suggested_response';
export type AssistanceLevel =
  | 'none' | 'hint' | 'translation' | 'solution' | 'suggested_response';
export type TaskOutcome = 'met' | 'partially_met' | 'not_yet' | 'unscored';
export type CapabilityKey = 'order_at_cafe' | 'arrange_meeting' | 'explain_delay';
export type CapabilityState =
  | 'not_tried' | 'with_support' | 'independent_once' | 'used_again_later';
export type ScenarioKey = CapabilityKey;

export type TargetRef = {
  kind: 'vocabulary' | 'grammar' | 'error';
  id: string;                 // canonical existing record id (uuid or external id)
  label_fr: string;
  label_native: string | null;
};

export type ScenarioDescriptor = {
  scenario_key: ScenarioKey;
  content_version: string;          // e.g. "journey-content-v1"
  title_fr: string;
  objective_key: string;            // e.g. "order_at_cafe.counter_drink"
  objective_native: string;
  level_band: 'A1' | 'A2' | 'B1' | 'B2';
  character_id: string;             // existing world-bible cast id
  character_name: string;
  location_id: string;              // existing world-bible location id
  location_name: string;
  image_url: string | null;         // resolved existing media URL, null is valid
  serial_thread_id: string | null;
  serial_episode_id: string | null;
  estimated_seconds: number;
};

export type ScenePrompt = {
  setup_fr: string;
  setup_native: string;
  objective_native: string;
  character_line_fr: string | null;
  character_line_audio_url: string | null;
  image_url: string | null;
};

export type RecallOption = { id: string; text_fr: string };  // never carries correctness

export type RecallPrompt = {
  task_type: 'choice' | 'tiles' | 'short_answer';
  instruction_native: string;
  prompt_fr: string | null;
  options: RecallOption[];          // [] for short_answer
  target: TargetRef;
  optional: boolean;                // only optional recall may be dropped for budget
  help_available: HelpKind[];
};

export type RespondPrompt = {
  turn_index: number;               // 0-based
  max_turns: number;                // <= 2 normal turns
  repair_allowed: boolean;
  character_id: string;
  character_name: string;
  character_line_fr: string;
  character_line_audio_url: string | null;
  objective_native: string;
  input_modes: InputMode[];         // ['text'] when voice unavailable
  targets: TargetRef[];             // elicited targets; may be []
  help_available: HelpKind[];
};

export type ResolutionPrompt = {
  outcome_key: string;              // typed allowable consequence, e.g. 'served_at_terrace'
  character_line_fr: string;
  summary_native: string;
  image_url: string | null;
};

export type PublicStep =
  | { id: string; ordinal: number; kind: 'scene'; status: StepStatus;
      estimated_seconds: number; assistance_used: AssistanceLevel[]; prompt: ScenePrompt }
  | { id: string; ordinal: number; kind: 'recall'; status: StepStatus;
      estimated_seconds: number; assistance_used: AssistanceLevel[]; prompt: RecallPrompt }
  | { id: string; ordinal: number; kind: 'respond'; status: StepStatus;
      estimated_seconds: number; assistance_used: AssistanceLevel[]; prompt: RespondPrompt }
  | { id: string; ordinal: number; kind: 'resolution'; status: StepStatus;
      estimated_seconds: number; assistance_used: AssistanceLevel[]; prompt: ResolutionPrompt };

export type PracticedTarget = {
  target: TargetRef;
  evidence_kind:
    | 'recognized' | 'produced_supported' | 'produced_independent' | 'not_yet' | 'unscored';
  assistance_level: AssistanceLevel;
};

export type CapabilityEvidence = {
  capability_key: CapabilityKey;
  state: CapabilityState;
  modality: InputMode;
  observed_on: string;              // YYYY-MM-DD, learner-local
  context_native: string;
};

export type JourneyRecap = {
  completion_kind: 'complete' | 'early';
  objective_outcome: TaskOutcome;
  practiced_targets: PracticedTarget[];
  capability_evidence: CapabilityEvidence[];
  next_focus: { target: TargetRef; reason_native: string } | null;
  collectible_ids: string[];
  story_outcome: {
    serial_thread_id: string | null;
    serial_episode_id: string | null;
    outcome_key: string;
    callback_fr: string | null;
  } | null;
  active_seconds: number | null;    // measured; null when not measurable
};

export type JourneySnapshot = {
  id: string;
  contract_version: 1;
  revision: number;
  status: JourneyStatus;
  local_date: string;               // YYYY-MM-DD
  timezone: string;                 // IANA
  budget_seconds: 300;
  estimated_active_seconds: number;
  current_step_id: string | null;
  scenario: ScenarioDescriptor;
  steps: PublicStep[];
  recap: JourneyRecap | null;
  retry: { allowed: boolean; after_seconds: number } | null;
};

export type TodayEnvelope = {
  contract_version: 1;
  enabled: boolean;
  control_language: ControlLanguage;
  local_date: string;
  timezone: string;
  journey: JourneySnapshot | null;
  available: ScenarioDescriptor | null;
  legacy_resume: { href: string; session_id: string } | null;
};

export type JourneyCorrection = {
  span_fr: string;                  // must be a real substring of the learner answer
  corrected_fr: string;             // must differ from span_fr
  note_native: string;
};

export type NextTurn = { step_id: string; prompt: RespondPrompt };

export type AttemptResult = {
  contract_version: 1;
  evidence_ref: string;             // canonical learning record reference
  task_outcome: TaskOutcome;
  assistance_level: AssistanceLevel;
  correction: JourneyCorrection | null;   // at most ONE foreground correction
  character_reply_fr: string | null;
  reply_source: 'model' | 'authored' | 'none';  // revision 2: an authored fallback
                                                // may never pose as a live response
  next_turn: NextTurn | null;
  pending: boolean;                 // true => retryable grading, outcome 'unscored'
  journey: JourneySnapshot;
};

export type HelpResult = {
  contract_version: 1;
  step_id: string;
  help_kind: HelpKind;
  content_fr: string | null;
  content_native: string | null;
  assistance_level: AssistanceLevel;   // recorded BEFORE the content is returned
  journey: JourneySnapshot;
};

export type CapabilityProgress = {
  contract_version: 1;
  rubric_version: string;              // e.g. "capability-rubric-v1"
  capabilities: Array<{
    capability_key: CapabilityKey;
    title_native: string;
    state: CapabilityState | 'unknown';
    modalities: InputMode[];
    latest_qualifying_on: string | null;
    evidence: CapabilityEvidence[];
  }>;
};

export type JourneyErrorCode =
  | 'journey_version_conflict' | 'idempotency_conflict' | 'step_not_active'
  | 'journey_not_active' | 'empty_answer' | 'journey_disabled'
  | 'generation_unavailable' | 'processing'
  | 'help_unavailable';   // revision 2: a help kind the step does not offer (422)

export type JourneyErrorBody = {
  detail: {
    code: JourneyErrorCode;
    message: string;
    current_revision?: number;
    refresh_href?: string;
    retry_after_seconds?: number;
  };
};
```

## Request bodies

| Route | Body |
|---|---|
| `POST /daily-journeys` | `{ mutation_id, timezone, budget_seconds: 300, preferred_input_mode: 'text'\|'voice' }` |
| `POST …/steps/{step_id}/help` | `{ mutation_id, expected_revision, help_kind }` |
| `POST …/steps/{step_id}/attempts` | `{ mutation_id, expected_revision, input: AttemptInput }` |
| `POST …/advance` | `{ mutation_id, expected_revision, current_step_id }` |
| `POST …/pause` \| `…/resume` | `{ mutation_id, expected_revision }` |
| `POST …/finish` | `{ mutation_id, expected_revision, finish_kind: 'complete'\|'early' }` |
| `POST …/retry` | `{ mutation_id }` |

```ts
export type AttemptInput =
  | { mode: 'choice'; option_id: string }
  | { mode: 'tiles'; tile_ids: string[] }
  | { mode: 'text'; text: string }
  | { mode: 'voice'; text: string; transcript_ref?: string | null };
```

The client never supplies score, success, outcome, or assistance level.

### Contract revision 1 — `transcript_ref` is optional (2026-09-05)

CONTRACTS §4 asks a voice attempt to carry an "owned transcript reference".
**Inspection shows no such identifier exists.** `POST /api/v1/audio/transcribe`
(`app/api/v1/endpoints/audio.py`) is stateless: it authenticates the caller, reads
the upload, returns `{"text": ...}`, and persists **no transcript row**. There is
no transcript table anywhere in `app/db/models/`.

Resolution, coordinated across WP-02 / WP-05 / WP-06 / WP-07 / WP-10:

* `transcript_ref` becomes **optional and nullable**. Voice attempts submit the
  text returned by the existing authorized transcription endpoint, with
  `mode: 'voice'` recording the modality.
* The §5 cross-user transcript ownership check is **vacuous, not skipped**: there
  are no transcript rows to own, so there is nothing to leak. WP-02 must still
  validate any `transcript_ref` it *is* given and reject one it cannot attribute
  to the caller, so the check turns on if persistence is added later.
* Modality (`text` vs `voice`) is still first-class evidence: WP-05 records it,
  and WP-09's rubric must never let a written result claim pronunciation.
* Rejected alternative: adding a transcript table. That would be a second store
  for content the learning records already hold, and CONTRACTS §4 explicitly
  requires audio capture to keep flowing through the existing endpoints.
* WP-10 must therefore **not** cache audio blobs to reconstruct a transcript;
  it persists the drafted/returned text only, exactly as §3 of WP-10 already says.

## Domain interfaces (CONTRACTS §6)

Frozen in `app/services/journey_contracts.py` (owned by WP-02, created by WP-00 so
all packages import the same dataclasses). Implementations live in their packages:

Every callable takes the caller's `Session` and writes through it — the state
machine owns the commit. None of them accept an ORM `DailyJourneyStep` row: they
take the frozen dataclasses, so WP-03/04/05/06 do not depend on WP-02's models.

| Owner | Callable (module `app.services.<module>`) | Result type |
|---|---|---|
| 03 | `journey_content.build_scenario_context(db, *, user, scenario_key=None, input_mode) ` | `ScenarioBrief \| ContentUnavailable` |
| 05 | `journey_learning.select_learning_candidates(db, *, user, scenario, limit)` | `list[LearningCandidate]` |
| 04 | `journey_planner.plan_journey(*, scenario, candidates, budget_seconds, pace, input_mode=InputMode.TEXT)` | `PlannedJourney`; raises `PlanUnavailable` |
| 05 | `journey_learning.ensure_journey_learning_session(db, *, user, journey_id, scenario_key)` | `LearningSession` |
| 05 | `journey_learning.evaluate_recall(db, *, user, task: RecallTask, answer: AttemptAnswer, assistance)` | `RecallEvaluation` |
| 06 | `journey_conversation.evaluate_response(db, *, user, scenario, task: ResponseTask, answer, turn_index, assistance, history)` | `ResponseEvaluation` |
| 05 | `journey_learning.apply_learning_evidence(db, *, user, journey_id, step_id, session, evaluation, modality, timezone=None, now=None)` | `AppliedEvidence` |
| 06 | `journey_conversation.apply_story_outcome(db, *, user, journey_id, scenario, proposal, source_key)` | `StoryOutcomeRef` |
| 09 | `journey_capabilities.build_capability_summary(db, *, user, control_language)` | `CapabilityProgressView` |
| 09 | `journey_capabilities.mint_journey_keepsake(db, *, user, journey_id, scenario_key, completion_kind)` | `KeepsakeResult` |
| 11 | `journey_events.record_journey_event(db, *, event_name, user_id, source_key, metadata)` | `PilotEvent \| None` |

`AttemptAnswer` is the normalized server-side view of `AttemptInput`:

```python
@dataclass(frozen=True)
class AttemptAnswer:
    mode: InputMode                  # text | voice
    text: str                        # already-normalized, non-empty
    option_id: str | None = None
    tile_ids: list[str] = []
    transcript_ref: str | None = None
```

Answer normalization (`app.services.journey_contracts.normalize_answer_text`)
folds smart quotes/apostrophes before any comparison — iOS inserts U+2019.

## Source-key grammar (CONTRACTS §7)

`journey:{journey_id}:{step_id}:{target_kind}:{target_id}:{evidence_kind}`
and for story/reward effects `journey:{journey_id}:{effect}`. Stable across HTTP
retry, worker retry, and alternate UI surfaces.

## Frontend recommendation precedence (WP-07 / WP-08)

`web-frontend/lib/atelier-next.ts::resolveRecommendedNext` currently resolves, in order:
active legacy session → `start_session` → unread serial episode → review → mission →
studio → library → feuilleton → serial reread → rest.

WP-07 adds a **capability-aware branch in front of that chain** and preserves the
existing chain verbatim underneath it. Frozen precedence when
`TodayEnvelope.enabled === true`:

1. `journey.status` is `active` or `paused` → **resume the journey**.
2. `journey.status` is `preparing` → **show preparing with the server's retry hint**;
   never silently start a second journey.
3. `journey.status` is `unavailable` → **offer retry**, then fall through to the
   legacy chain. An unavailable generation is not a finished day.
4. `journey.status` is `completed` or `ended_early` → the day's journey is **done**;
   fall through to the legacy chain for optional practice. Re-entering it is a read
   and must not inflate progress or streaks.
5. No journey and `available !== null` → **start today's journey**.
6. Anything else → the existing legacy chain, unchanged.

`legacy_resume` is **orthogonal to all six branches**. When it is non-null the UI must
always surface an explicit, separately-labelled resume entry for that old Atelier
session (CONTRACTS §10). A V2 journey never silently converts, replaces, or completes
a legacy session, and choosing the journey must not hide the legacy resume.

When `enabled === false` the resolver must return exactly what it returns today —
`atelier-next.test.js` proves this and must keep passing unchanged for that case.


## Contract revision 2 — ratified deviations (2026-09-05)

Reviewed by the integration owner after WP-02 and WP-04 landed. All are additive; the
wire `contract_version` stays 1 because no existing field changed meaning.

| # | Change | Owner | Rationale |
|---|---|---|---|
| 1 | `JourneyErrorCode` gains `help_unavailable` (422) | WP-02 | a client asking for a help kind the step does not offer needs a structured refusal; well-behaved clients never hit it because `help_available` is accurate |
| 2 | `GET /daily-journeys/today?timezone=<IANA>` optional query param | WP-02 | a GET has no body, and the first journey needs a validated client zone before one exists |
| 3 | `POST /daily-journeys` returns 200 when a new journey lands in `unavailable`; 503 `generation_unavailable` with **no row created** when even the provider-free catalog is empty | WP-02 | 201/202 would imply a usable journey |
| 4 | `resume` on an already-active journey is an accepted no-op that does **not** bump the revision | WP-02 | keeps resume idempotent for WP-10's retry path |
| 5 | `budget_seconds` is `Literal[300]`, so another value yields FastAPI's plain 422 | WP-02 | accepted for the functional milestone; §9 fixes the MVP budget |
| 6 | `AttemptResult.evidence_ref` is `""` while `pending` | WP-02 | there is no canonical record yet; inventing a reference would be worse |
| 7 | ~~`JourneyRecap.active_seconds` is always `null`~~ — **CLOSED 2026-09-05** | WP-11 | WP-11 measures it from the event ledger (pauses excluded, idle capped at 3x the step estimate, provider wait subtracted) and WP-02 now calls `measure_journey_active_seconds`. Verified live: a scripted run against a 211 s plan reported **4 s**, so it is a real measurement and never the estimate. An unmeasurable day still reports `null` |
| 8 | Extra journey columns (`level_band`, `generation_attempts`, `unavailable_*`, `response_status`) | WP-02 | additive; `level_band` is pinned alongside `content_version` so a learner level change cannot swap the variant mid-journey |
| 9 | Deterministic refusals (409/422) are stored on the receipt as `committed`, so replaying the key returns the identical error; only recoverable failures are marked `failed` | WP-02 | makes retries safe without masking real faults |
| 10 | `apply_learning_evidence` gains `timezone=` / `now=` trailing kwargs | WP-05 | `observed_on` must be learner-local for §8's 24-hour rule |
| 11 | `plan_journey` gains a trailing keyword-only `input_mode` | WP-04 | `RespondPrompt.input_modes` must state whether voice is offered, and the frozen `ScenarioBrief` carries no modality. Sniffing WP-03's private voice rubric was the rejected alternative |
| 12 | `plan_journey` raises `PlanUnavailable(.reason)` rather than returning a union | WP-04 | the frozen return type is `PlannedJourney`; WP-02 maps `.reason` onto `generation_unavailable` with `retry_allowed=False` |
| 13 | `selected_target_ids` / `omitted_candidate_ids` carry the composite `"{kind}:{id}"` | WP-04 | a vocabulary row and a grammar concept can share a primary key |

**Rejected — one deviation was sent back.** WP-02 originally degraded a domain module to
its deterministic stub whenever the import raised *anything*, not only when the module was
absent. A broken `journey_learning` would then have kept returning HTTP success while
writing no canonical learning credit — exactly the "mock data presented as real
functionality" failure this project forbids. The required behavior: a genuinely absent
module still degrades to a stub with a logged warning; a module that exists but raises on
import must fail the operation honestly (`unavailable` with `retry_allowed=False`, or 503
`generation_unavailable`), never silently succeed.

| 14 | `daily_journeys.plan_selection` JSONB column | WP-02 | stores WP-04's `selected_target_ids` / `omitted_candidate_ids` / `rationale` verbatim, including the composite `{kind}:{id}` identities; never appears in a public payload |
| 15 | `AttemptResult.reply_source` (`model` \| `authored` \| `none`), optional with a `"none"` default | WP-02/WP-06 | requirement 6: an authored fallback line may never be presented as a live model response. Optional so the frozen v1 fixtures keep validating; the two attempt fixtures carrying a reply now declare it, and `test_journey_fixture_bundle` enforces that any fixture with a `character_reply_fr` states its provenance |
