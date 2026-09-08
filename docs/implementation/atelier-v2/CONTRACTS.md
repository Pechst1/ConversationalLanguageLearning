# Atelier V2 — shared implementation contracts

This document originated as the V1 proposal; implementation and ratified changes are recorded in CONTRACT-FREEZE.md and STATUS.md. Inspect the code before assuming any proposed field is implemented. WP-00 freezes fixtures against this document. WP-02 owns schema changes. If inspection reveals an incompatibility, record the concrete reason and coordinated revision before consumers proceed; do not invent a different private contract per package.

Specification revision 2: the functional contracts remain. Claude Design replaces the rejected Codex visual reference. Follow DELIVERY-PHASES.md; visual migration is not a prerequisite for implementing the domain APIs or testing the connected flow with existing components. The wire `contract_version: 1` below remains unchanged because this planning revision does not change the wire schema.

**2026-09-06 extension:** CONTINUOUS-STORY.md requires generated situation identities, semantic rubrics, provenance-bearing story context, and coordinated episode completion. WP-14A must freeze the compatible contract evolution before implementation. This requirement alone does not change the implemented wire version or invalidate active V1 journeys.

## 1. Architecture

Introduce a **DailyJourney** orchestration layer. It references existing learner, serial, learning-session, learning-moment, attempt, and credit records. It owns ordering, progress, a short time envelope, and idempotency. It does not own a second vocabulary scheduler, a second character memory, or a second copy of the learner’s authoritative answers.

New module families:

- `app/services/daily_journey.py`: state machine / transaction boundary (WP-02).
- `app/services/journey_content.py`: bounded scene content (WP-03).
- `app/services/journey_planner.py`: plan selection (WP-04).
- `app/services/journey_learning.py`: candidate selection and canonical evaluation/credit (WP-05).
- `app/services/journey_conversation.py`: bounded response and consequence proposal (WP-06).
- `app/services/journey_capabilities.py`: evidence-backed capability view (WP-09).
- `app/services/journey_events.py`: event constructors only; existing PilotEventService persists them (WP-11).

Prefer an adapter around an existing public method. If a service currently commits internally, add a narrow transaction-compatible path with regression tests; do not claim atomicity around multiple independently committed calls.

## 2. Persistent state

WP-02 owns an additive Alembic revision introducing:

1. `daily_journeys`: UUID, user_id, local_date, timezone snapshot, contract_version=1, content_version, status, revision, current_step_id, budget_seconds=300, estimated_active_seconds, optional serial_thread_id/episode_id, optional learning_session_id, created/started/completed timestamps, snapshot of the public-safe plan/recap. One journey per `(user_id, local_date)` and at most one preparing/active/paused journey per user. Implement the active constraint in PostgreSQL with an appropriate partial unique index plus transaction/locking behavior; SQLite tests alone are insufficient.
2. `daily_journey_steps`: UUID, journey_id, stable ordinal, kind, status, estimated_seconds, selected source references, public prompt snapshot, private evaluator/answer data, assistance state, canonical result reference, completion timestamp. Unique `(journey_id, ordinal)`; stable IDs through resume and generation retries.
3. `daily_journey_mutations`: UUID/idempotency key, journey_id/user_id, route/action scope, request digest, expected_revision, processing status, public response snapshot, canonical evidence references, timestamps. Unique key scope includes user and action. This is an idempotency receipt, not a duplicate learner transcript. Keep only the fields needed to replay the operation; retain canonical content under existing session privacy/deletion rules.

Preserve JSONB/SQLite variants used in current models. Register models in existing export/metadata paths. The integration owner assigns the migration’s actual revision/down_revision after inspecting current Alembic heads; no parallel uncoordinated migrations.

No migration changes historical SRS due dates, CEFR levels, completed sessions, collectible ownership, or serial episode indices. Account deletion/export must include the new records using existing ownership policies.

## 3. Journey and step states

Journey: `preparing → active ↔ paused → completed | ended_early`.

- `preparing → unavailable` when bounded recovery fails; a retry can resume preparation for the same ID.
- Completed/ended_early are terminal. Visiting them is a read, not another completion.
- An active journey from yesterday is resumed first; never silently reset it at midnight. After it ends, create today’s journey if the local date differs. No second journey on the same date; optional practice is separate.
- Store an IANA timezone snapshot. For accounts without one, use a validated client timezone on creation, otherwise UTC. Do not hardcode Berlin. A timezone change never rekeys or duplicates an existing active journey.

Step kinds: `scene | recall | respond | resolution`.

Step states: `pending | active | completed | skipped`. Only one active step. `skipped` is not successful evidence. Budget removal is allowed only for optional recall steps, never the scene’s objective or resolution. Public step progress reflects actual remaining steps, not the legacy drill formula.

The five-minute plan has 3–5 steps: scene, zero to two recall moments, one bounded response, resolution. Each recall is one actual task, not a hidden 15-drill set. The response step can contain at most two learner turns and one optional repair. Explicitly requesting more conversation exits into optional practice without reopening the completed daily journey.

## 4. HTTP surface

Use the existing authenticated API under `/api/v1`. Register a new `/daily-journeys` router; preserve old endpoints.

| Method/path | Purpose |
|---|---|
| `GET /daily-journeys/today` | Capability, active/today snapshot, or available scenario descriptor. No costly generation or new journey creation on GET. |
| `POST /daily-journeys` | Create or return the existing date/active journey. Body: `mutation_id`, `timezone`, `budget_seconds:300`, preferred_input_mode `text|voice`. Return 201 for new ready, 200 for existing, 202 for preparing. |
| `GET /daily-journeys/{id}` | Owned persisted state, including terminal state; safe for reconnect/polling. |
| `POST /daily-journeys/{id}/steps/{step_id}/help` | Record hint/translation/answer reveal before returning it. Body: `mutation_id`, `expected_revision`, help_kind `hint|translation|solution`. |
| `POST /daily-journeys/{id}/steps/{step_id}/attempts` | `mutation_id`, `expected_revision`, input discriminant, answer/choice/tile IDs or owned transcript reference. Canonical server evaluation; client never supplies score/success. |
| `POST /daily-journeys/{id}/advance` | Acknowledge a read/resolution or accepted result and activate next eligible step. `mutation_id`, `expected_revision`, current_step_id. No advance over unanswered required work. |
| `POST /daily-journeys/{id}/pause` | `mutation_id`, `expected_revision`; preserve all completed work. |
| `POST /daily-journeys/{id}/resume` | `mutation_id`, `expected_revision`; return the same step/content, not a new plan. |
| `POST /daily-journeys/{id}/finish` | `mutation_id`, `expected_revision`, finish_kind `complete|early`. Complete requires resolved mandatory steps; early records partial participation without false completion/skill credit. |
| `POST /daily-journeys/{id}/retry` | Retry unavailable/preparing operation with bounded attempts; reuse its ID and durable generation claim. |
| `GET /daily-journeys/capabilities/progress` | Owned practical-capability summaries (WP-09); declare the static route before `/{id}`. |

WP-02 creates Pydantic discriminated schemas and matching TypeScript types, including all response variants; no `Record<string, any>` for new core payloads. Existing authenticated HTTP transport is used; do not add a parallel token refresh implementation. Audio capture/transcription continues through existing authorized endpoints and owned transcript identifiers.

`today` response:

```ts
type TodayEnvelope = {
  contract_version: 1;
  enabled: boolean;
  local_date: string; // YYYY-MM-DD
  timezone: string;
  journey: JourneySnapshot | null;
  available: ScenarioDescriptor | null;
  legacy_resume: { href: string; session_id: string } | null;
};

type JourneySnapshot = {
  id: string;
  contract_version: 1;
  revision: number;
  status: 'preparing'|'active'|'paused'|'completed'|'ended_early'|'unavailable';
  local_date: string;
  timezone: string;
  budget_seconds: 300;
  estimated_active_seconds: number;
  current_step_id: string | null;
  scenario: ScenarioDescriptor;
  steps: PublicStep[];
  recap: JourneyRecap | null;
  retry: { allowed: boolean; after_seconds: number } | null;
};
```

ScenarioDescriptor minimum: stable scenario_key, content_version, title_fr, objective_key plus localized objective, level band, character_id/name, location_id/name, resolved image URL or null, optional serial_thread_id/episode_id, estimated_seconds. PublicStep is a discriminated union with only renderer-needed prompts/options, IDs, status, and estimates. It must never contain target_answer, private rubric, privileged future story facts, or answer-key metadata before permitted reveal.

Attempt response minimum: canonical evidence reference; `task_outcome: met|partially_met|not_yet|unscored`; assistance level; at most one foreground correction; optional next-turn payload; updated JourneySnapshot. Grade errors/timeouts yield a retryable pending result, never `not_yet` by default.

Recap minimum: completion kind, objective outcome, real practiced targets, capability evidence descriptors, optional one next-focus item, minted collectible IDs, and existing story outcome reference. No fabricated fluent/100%-correct messages.

## 5. Retry, concurrency, and ownership

- Check authenticated ownership of journey, step, referenced exercise, transcript, and serial thread. Another user’s ID returns the existing application’s non-disclosing 404 convention; never trust user_id from the body.
- Look up a matching idempotency receipt before checking a now-stale revision. The identical committed request returns its stored response; the same key with a different digest returns 409 `idempotency_conflict`.
- A new request with the wrong revision returns 409 `journey_version_conflict` with a safe current-state refresh reference. Out-of-order steps return 409 `step_not_active`.
- An identical operation still processing returns 202 with retry guidance; callers reuse the key. Duplicate requests cannot apply credit, consume a turn, advance a story, or mint rewards twice.
- Claim expensive generation/evaluation work durably. Do external model calls outside long-held row locks, then verify the revision/claim and commit final state and domain effects together. A crashed worker has a bounded, documented recovery path.
- Database transaction tests must exercise simultaneous HTTP requests, not only two sequential service calls.
- Empty/blank answer: 422, no attempt/lapse/credit mutation. Missing audio permission, transcription failure, provider timeout, malformed model output: recoverable infrastructure states, not learner mistakes.

## 6. Shared domain interfaces

Define these typed interfaces in WP-00 fixtures and WP-02 schema modules. Implementations belong to the named packages. They use the caller’s DB transaction for final writes.

| Owner | Interface | Result |
|---|---|---|
| 03 | `build_scenario_context(user, serial_snapshot, level, input_mode)` | Validated ScenarioBrief; deterministic unavailable/fallback result |
| 05 | `select_learning_candidates(user, scenario, limit)` | Source-backed due/fragile candidates with typed identities |
| 04 | `plan_journey(user, scenario, candidates, budget_seconds, pace)` | Immutable PlannedJourney with private/public step separation |
| 05 | `evaluate_recall(step, answer, assistance)` | Validated evaluation referencing canonical learning record |
| 06 | `evaluate_response(context, answer, turn_index, assistance)` | Task outcome, response, and constrained consequence proposal |
| 05 | `apply_learning_evidence(evaluation, source_key)` | Canonical refs and deduplicated SRS/error-memory effects |
| 06 | `apply_story_outcome(journey, proposal, source_key)` | Existing serial ledger reference; no model-invented fact write |
| 09 | `build_capability_summary(user, evidence_refs)` | Evidence-backed practical ability levels |
| 09 | `mint_journey_keepsake(journey, completion)` | Existing collectible mint result; source-unique |
| 11 | `record_journey_event(event_name, source_key, metadata)` | Existing PilotEvent record with deduplication |

These can be dataclasses/Pydantic types rather than literal dictionaries. Null/empty candidate and outcome cases must be typed. No producer may solve a missing interface by inspecting another package’s private payload format.

## 7. Learning and correction policy

- One source key per `(journey_id, step_id, canonical_response_id, target_id, evidence_kind)`; stable across HTTP retry, worker retry, and alternate UI surfaces.
- Recognition is distinct from production. Seeing a phrase, opening a translation, pressing Continue, or copying a suggested response does not demonstrate independent production.
- Assistance is server-recorded per target/opportunity: `none | hint | translation | solution | suggested_response`. A hint before a response is relevant to that response; replaying the original audio alone is not automatically a hint. Map renderer/task types explicitly. No trusted self-report from the client.
- A correction or retry may yield successful **supported** production. Do not overwrite the first attempt as independently correct. A later, different unassisted opportunity may provide stronger evidence.
- A correct phrase that happens to omit an optional target is not a vocabulary lapse. Require an explicit elicitation obligation before recording a missed target.
- Foreground at most one actionable correction per turn, chosen by relevance to the task/learning target. Communication-blocking ambiguity may prompt clarification. Other validated errors may inform existing memory conservatively, but do not manufacture several punishment events from one response.
- No error record for stylistic preference, identical before/after strings, invalid quoted spans, punctuation invented by transcription, or model output that cannot be validated.
- Keep existing corrector settings meaningful. Detailed correction remains an optional view; V2 changes timing/presentation, not silently disables the user’s stored preference.

## 8. Practical capability rubric

Initial versioned keys: `order_at_cafe`, `arrange_meeting`, `explain_delay`.

States: `not_tried`, `with_support`, `independent_once`, `used_again_later`.

- `with_support`: at least one successful relevant production with assistance.
- `independent_once`: at least one successful unassisted open production fulfilling the objective; choice selection alone cannot qualify.
- `used_again_later`: at least two independent successful opportunities, on different journey IDs and learner-local dates, separated by at least 24 hours. This is a transparent initial product rule, not a validated psychometric score.
- Show the evidence date/context and text vs voice mode. A written result never proves pronunciation; none of these labels independently changes CEFR.
- Historical data with unknown help usage remains `unknown` evidence; do not infer independence from a legacy success boolean. Preserve stronger and weaker evidence histories without rewriting SRS.

## 9. Budget and selection rules

MVP default budget 300 seconds. Existing user daily_goal_minutes is not overwritten. Explain that the daily scenario is short and offer existing optional practice for the rest of the chosen goal. Do not build new 10/15-minute plan modes in this release.

- Start with explicit per-step estimates including reading, learner production, playback, feedback, resolution, and a retry allowance. Mandatory expected total ≤300 seconds for all fixture plans.
- Prefer at most two relevant due targets, one optional new target, and one practical objective. If the current queue is empty, use a level-appropriate new/known anchor; do not claim something is due.
- Rank candidates by task relevance, existing urgency/fragility, and recent exposure. Do not modify the underlying due date merely to fit a scene. An omitted candidate remains due.
- Repair at most once inside the daily flow, then allow a supported resolution and schedule valid follow-up. No endless retry gate or silently appended worksheet.
- Use measured active pace after enough observations; exclude background/idle time and track provider waiting separately. A poor network should be visible in the duration evidence rather than disguised as learning time.
- If the runtime materially exceeds the estimate, offer an honest stopping point without false success. Never force a five-minute cutoff on text or recording.

## 10. Rollout, navigation, and language

Backend flag `ATELIER_DAILY_JOURNEY_ENABLED`, default false, plus an explicit server-side pilot cohort allowlist. Server response is authoritative; no production auth bypass. With the flag off: do not create new journeys, retain read/resume/finish for already-created journeys, and retain the legacy entry point. This draining behavior is part of rollback.

Existing routes `/atelier`, `/graphic-novel`, `/audio-session`, `/notebook`, and `/missions` remain supported. During functional implementation keep existing navigation and entry points. The final labels/grouping/tab count follow the Claude Design mapping; Today/Stories/Speak/Notebook are functional destination names in this specification, not an approved visual arrangement. Written missions must remain discoverable. An old in-progress Atelier session receives a real resume entry instead of being silently converted into V2.

Control/instruction language comes from the learner’s supported native language (en/de/fr for the pilot), with explicit English fallback for others. Content/character dialogue stays French. Reuse gloss/language normalization. Do not use a global CSS rename to force all legacy text into another language.

The selected Claude Design artifact is authoritative for typography, palette, brand treatment, geometry, layout, navigation composition, and motion. Record the exact artifact/version before deriving tokens or replacing current styles. Do not implement the rejected prototype’s Manrope, palette, flower, button geometry, or screen compositions. During functional work reuse current components. Final tokens must preserve accessibility and existing light/dark/system/text-size settings; missing design states should be identified and resolved using Claude’s design language. Domain state and API contracts must not depend on CSS, tab count, typography, or decorative rewards.

## 11. Required fixture set

WP-00 creates a versioned JSON fixture bundle, with no credentials or real learner records:

`first_day`, `returning_due`, `empty_queue`, `active_legacy`, `voice_unavailable`, `preparing`, `generation_unavailable`, `wrong_then_supported`, `unassisted_success`, `completed`, `ended_early`, `stale_revision`, `duplicate_submit`, `midnight_resume`, `content_superseded`, `unknown_legacy_assistance`.

Include a complete café example from Today through finish, an indoor/outdoor consequence, a late-arrival scenario with one real repair, en/de/fr controls, and null-art fallback. Public fixtures must pass schema validation and contain no private answers. The paired private evaluator fixtures stay in tests and are not serialized to the UI.
