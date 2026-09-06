# Atelier V2 — exact work packages

Revision 2: functionality first, Claude Design for final UI. All packages inherit [README.md](README.md), [CONTRACTS.md](CONTRACTS.md), and [DELIVERY-PHASES.md](DELIVERY-PHASES.md). The rejected Codex preview is not a visual implementation reference. Functional and visual milestones retain the same package owner; passing only a functional milestone does not close the entire package. Paths are repository-relative. New filenames below are **proposed deliverables**, not claims that those files exist. Record execution in [STATUS.md](STATUS.md).

## WP-00 — Preserve the baseline and freeze the integration contract

**Owner:** integration agent. **Dependencies:** none. **Scope:** preparation and contract fixtures, not product implementation.

**Read:** current worktree status, repository instructions, current CI, `docs/design-overhaul-2026-08-31.md`, this handoff, and DELIVERY-PHASES.md.

**Deliver:**

1. Record the current commit and a reproducible, reviewed snapshot of relevant tracked and untracked source changes. Exclude credentials, local databases, media caches, environment files, and build outputs. Do not clean/stash away another task’s work. Establish how each agent receives the same working-state baseline.
2. Inventory current Alembic heads, runtime versions, service startup recipe, feature flags, and existing test failures. Use the existing development auth flow; do not invent a production-accessible bypass.
3. Add `docs/implementation/atelier-v2/BASELINE.md` with commands, baseline identity, environmental prerequisites, and relevant failures.
4. Create `tests/fixtures/daily_journey_v1/` using the scenarios required by CONTRACTS §11. Separate `public/` and `private/`; maintain a fixture manifest that lists the intended endpoint/state. WP-02 adds executable schema validation once its schemas exist.
5. Freeze domain signatures and statuses with WP-02. Resolve genuine incompatibilities in CONTRACTS before dispatching consumers. Update ownership/leases in STATUS.

**Acceptance:** an implementation agent can reproduce the current app from the named baseline without missing the latest fixes; every public fixture has a complete frontend rendering path; migration ownership is assigned; dependencies are acyclic; no agent has to guess the API shapes or who owns a shared file.

**Verification:** baseline targeted backend/frontend checks plus startup smoke. Record actual output, not “should pass”. Do not repair unrelated baseline failures as part of this package.

**Handoff:** baseline reference, commands, fixture inventory, contract revision, active file leases. This package must close before parallel implementation begins.

## WP-01 — Claude Design system and learner-language controls

**Owner:** UI system agent. **Dependencies:** WP-00 plus an accessible, identified Claude artifact. Can run alongside functional work once the artifact is inspected; backend packages do not depend on this package.

**Read:** `web-frontend/styles/globals.css`, `lib/app-preferences.ts`, `lib/glosses.ts`, current mobile/UI components, the Claude reference recorded in DELIVERY-PHASES.md, and its actual exported code/assets when available.

**Own:** new `web-frontend/components/atelier-v2/ui/`, `styles/atelier-v2.css`, `lib/atelier-v2-copy.ts`, local production font assets/license, and the minimum global import/token changes. Do not reskin all old pages by overriding global element selectors.

**Implement:**

1. Inventory the selected Claude version/variant and map its typography, colors, spacing, radii, motion, assets, and component states. Record missing screens/states in DELIVERY-PHASES.md. Build scoped tokens from that design, compatible with existing theme and text-size settings, including dark/system variants.
2. Reusable semantic controls for primary/secondary/icon actions, progress, choices, word tiles, feedback, dialogs, empty/loading states, artwork, and character portraits. Names and presentation may follow Claude; typed props must cover disabled, pending, error, selected, and success states.
3. Use the actual Claude typography and assets, with licenses recorded and fonts served locally where permitted. Do not introduce the rejected preview’s font, flower, button style, or sample learner data. Identify any unavailable asset before substituting a coherent equivalent.
4. Controls and messages for en/de/fr, with language normalization/fallback. Word glosses keep the existing resolver. Include clear localized action names, not only translated headings.
5. A dev-only component gallery with all states. Keep its gate consistent with current `/mobile-visual-qa`; do not widen production auth.

**Acceptance:** keyboard focus remains visible; answered options remain legible after disabling; status is communicated by text/icon as well as color; dialog traps/restores focus and closes with Escape; controls have effective 44px touch targets; body/input text scales; artwork fails gracefully. One primary action hierarchy per composition. No broad override alters legacy pages while V2 is disabled.

**Verify:** type-check/lint/build; visual gallery at 320/390/440/768/1280, both themes, large text and reduced motion. Add behavior tests for modal focus and button pending semantics where the existing harness supports them; do not add implementation-mirroring CSS snapshot tests.

**Handoff:** exact design reference/version, screen/state mapping, exported component/prop inventory, licenses, and screenshots compared with the selected design. WP-07/08/09 consume these primitives without introducing alternate buttons, fonts, or sheets.

## WP-02 — Durable daily journey state, schemas, and transport

**Owner:** journey infrastructure agent. **Dependencies:** WP-00.

**Read:** current Atelier/session models and endpoints, API auth dependencies, current transaction conventions, `web-frontend/services/api.ts`, native auth refresh, and CONTRACTS §§1–6,10.

**Own:** new `app/db/models/daily_journey.py`, `app/schemas/daily_journey.py`, `app/api/v1/endpoints/daily_journey.py`, `app/services/daily_journey.py`, one additive migration, their registrations, config capability flag/cohort logic, `web-frontend/types/daily-journey.ts`, `services/daily-journey.ts`, and required methods in the existing API service.

**Implement:**

1. The three tables, uniqueness/ownership checks, state transitions, revision control, and mutation receipts in CONTRACTS. Model/index/JSON behavior must work in PostgreSQL and existing test configuration.
2. Every specified endpoint, with real Pydantic/TypeScript discriminants and private/public payload separation. Use injected typed domain adapters until WP-03/04/05/06 land; test adapters cannot become production defaults.
3. One active journey and one per local date under concurrent creates; yesterday’s active journey takes precedence. Persist timezone snapshot and content version.
4. Durable claims for model work, matching-request replay before stale-revision rejection, conflict handling, processing 202 responses, and recovery from expired claims. No credit/episode/reward double apply.
5. Capability-aware, default-disabled behavior including draining old V2 sessions when creation is disabled. Preserve existing endpoints, tokens, and refresh behavior.
6. Add journey records to existing user export/deletion behavior through the relevant service owner; retain appropriate ownership cascades. Validate every WP-00 public fixture against the real response schemas.

**Acceptance:** create→read→help→attempt→advance→pause→resume→finish works with persisted IDs; a reload/midnight/request retry does not create a new plan; blank answers do not mutate learning records; unauthorized object references fail; private evaluator content never appears in any GET or early attempt response. Domain side effects and final receipt commit have a provable atomic/deduplicated path.

**Tests:** add `tests/test_daily_journey_api.py`, `test_daily_journey_state.py`, `test_daily_journey_concurrency.py`. Cover simultaneous creates, duplicate attempt in-flight and committed, same-key/different-body, stale version, out-of-order step, cross-user IDs/transcripts, timezone/DST, stopped/complete states, and flag rollback. Run migration upgrade/downgrade/upgrade only on disposable databases with representative legacy rows.

**Handoff:** executable fixture validation, endpoint examples, migration identifier, typed client, and integration seams. WP-02 retains ownership of state-machine wiring while domain modules are merged.

## WP-03 — Bounded scenario briefs and dependable content

**Owner:** content/generation agent. **Dependencies:** WP-00. **Can run alongside:** WP-02; WP-01 only when its design prerequisite is met.

**Read:** existing serial world bibles, `serial_arc_planner.py`, `serial.py`, `app/schemas/serial.py`, `graphic_novel.py`, and the existing location/character assets.

**Own:** new `app/services/journey_content.py`, `app/prompts/journey/`, `app/data/journey_scenarios/`, `tests/test_journey_content.py`. Do not edit serial completion/memory code; WP-06 owns it.

**Implement:**

1. Versioned scenario briefs for three concrete objective families: order at a café, arrange a meeting, explain a delay. Use existing cast/location IDs and current learner level; provide authored A1 and A2 examples plus graceful suitability fallback for other levels.
2. Each brief defines: story setup, practical objective, required facts, allowable outcomes, turn limit, target affordances, character/register, assets, estimated reading/response lengths, and private evaluator rubric. The final participation opportunity supports open text/voice; suggested replies remain assistance.
3. A content adapter that can derive a bounded scene from an existing current serial brief without advancing the episode or revealing future plot. If incompatible or not ready, use a coherent authored side scene; do not pretend it completed that serial episode.
4. Validate level-appropriate length, target relevance, answer integrity, contradictions, and real asset URLs. Reuse existing media URL conventions; no inline base64 images or new per-attempt image generation.
5. Bounded generation retries using existing generation/cost infrastructure. Cache versioned content at appropriate learner/story scope. A ready authored fallback is selectable without waiting for an image/model call; an unavailable state remains honest when no valid content exists.

**Acceptance:** all three scenes have a beginning, explicit communicative need, and achievable ending. Café dialogue does not suddenly switch to landlord paperwork. A missing image never blocks reading/responding. Reopening a journey uses its pinned brief; a prompt-version bump does not strand an active journey. Generation failures never produce unvalidated placeholder exercises presented as ready.

**Tests:** scene schema/length validation, unknown cast/location, incompatible level, missing media, rejected model output, bounded retries, valid fallback, content-version pinning, and a delayed/superseded serial source. Real model quality is evaluated later with a reviewed sample set, not asserted by deterministic unit tests.

**Handoff:** scenario keys/versions, public/private fixture pairs, supported-level matrix, cost-bearing calls, adapter signature, and known content limitations.

## WP-04 — Five-minute planner and integrated review selection

**Owner:** learning-flow agent. **Dependencies:** WP-02, WP-03, WP-05. **Can run alongside:** WP-06 once shared dependencies land.

**Read:** fixed ladder/pace logic in `app/services/atelier.py`, `unified_srs.py`, existing learning-moment selection, and CONTRACTS §§3,6,9.

**Own:** new `app/services/journey_planner.py`, planner-specific schemas/helpers within its module, `tests/test_journey_planner.py`. Submit state-machine hook to WP-02; do not change the legacy ladder or scheduler.

**Implement:**

1. Plan 3–5 explicit steps from a ScenarioBrief and WP-05 candidates: scene → zero/two recall opportunities → purposeful response → resolution. Daily grammar support is one focused task, not an expanded exercise set.
2. Select a maximum of two relevant existing due/fragile targets and at most one new target. Prefer scenario fit over inserting an unrelated urgent word. Preserve due status for omitted items; explain absence/empty queues honestly.
3. Compute per-step and whole-plan estimates including learner reading, answering, normal feedback, playback, and one repair allowance. Mandatory plan estimate must fit 300 seconds. Use bounded defaults until measured pace is sufficient.
4. Define deterministic shorter paths for slow pace, text instead of unavailable voice, no due items, known target demonstrated early, and no valid generated content. Persist chosen IDs/order; no rerandomization on refresh.
5. Do not add another task after the learner reaches the daily ending. “More practice” is an explicit new activity. If runtime runs long, allow honest partial ending or supported resolution; never imply unearned objective success.

**Acceptance:** returning and new learners both reach a real ending without the old 15-per-concept obligation. A learner who has already demonstrated a selected target skips only redundant recall, with the step explicitly marked skipped. A queue of 100 due words does not produce 100 obligations or quietly mark the unselected words reviewed.

**Tests:** table-driven plans for empty/large/fragile queues, unrelated targets, slow pace, text-only, partially known concepts, generation fallback, and minimum valid context. Assert ≤300 estimated seconds, ≤5 planned steps, at most one required repair, stable IDs/order, preserved unselected due dates, no answer leaks, and no accidental legacy formula use.

**Handoff:** planner truth table with sample input→plan, estimate assumptions, and real integration test against WP-02 state. Passing fixtures alone is not completion.

## WP-05 — Canonical learning evidence, review, and correction policy

**Owner:** learning backend agent. **Dependencies:** WP-02. **Can develop contracts earlier:** after WP-00.

**Read:** `VocabularyCreditService`, `UnifiedSRSService`, `ErrorMemoryService`, `SessionMomentPlanner`, current grammar evaluator, existing SRS/false-correction regression tests.

**Own:** new `app/services/journey_learning.py`; narrow changes to `vocabulary_credit.py`, `unified_srs.py`, `session_moment_planner.py`, `error_memory.py`, and legacy Atelier attempt adapters only if needed. Own `tests/test_journey_learning.py` and `test_journey_correction_policy.py`.

**Implement:**

1. A candidate adapter returning existing, learner-owned vocab/grammar/error identities with due/relevance context. No new scheduler or duplicate “daily words” database.
2. Evaluation adapters for recall/production using canonical learning sessions/moments/attempts. Store new journey source and assistance metadata with existing evidence records; do not duplicate raw answers into the journey receipt.
3. Record assistance through the help/reveal endpoint and renderer task type. Recognition, suggested response, translation, hint, supported retry, and independent open production must remain distinguishable.
4. Apply existing SRS/error credit exactly once using stable source keys. Ensure the same evidence submitted through a journey and a standalone activity cannot double-credit. If independent practice occurs between planning and submission, re-read progress and apply valid evidence to current state instead of stale queue snapshots.
5. Implement the foreground correction policy: one relevant correction; optional detailed view; no unvalidated/no-op/spelling-from-ASR erratum; omitted optional targets do not become lapses. Keep infrastructure failure separate from incorrect answer.
6. Expose evidence metadata for WP-09 and next-day planner selection. A known failed target can reappear later without a mandatory immediate worksheet.

**Acceptance:** a correct free response, a correct suggested reply, and a translated/copied response have different evidence classifications. A retry does not erase initial assistance/failure. Reading/tapping never counts as production. Correct but differently worded French is not penalised solely for failing an exact string comparison.

**Tests:** positive/negative rubric cases; no-op correction; fabricated quote span; empty text; ASR punctuation; missing optional/required target; solution reveal followed by correct answer; duplicated credit via two routes; delayed grading and concurrent standalone review; crash/retry. Rerun `tests/test_unified_srs.py`, `test_srs_review_cycle.py`, `test_atelier_quality_srs.py`, `test_atelier_transform_produce_fixes.py`, and relevant audio regressions.

**Handoff:** evidence mapping table, canonical storage location, source-key dedup mechanism, transaction boundaries, targeted regression results. WP-04 and WP-06 must use this adapter rather than calling schedulers directly.

## WP-06 — Purposeful conversation and grounded story consequences

**Owner:** conversation/story agent. **Dependencies:** WP-02, WP-03, WP-05.

**Read:** `audio_session_service.py`, missions turn/complete endpoints, `serial.py` relationship/callback/completion logic, `SerialThread.state`, `SerialEpisode.state_delta`, and existing audio/serial regressions.

**Own:** new `app/services/journey_conversation.py`; narrow changes to serial/arc and audio/mission services needed by the adapter; `tests/test_journey_conversation.py`, `test_journey_story_outcomes.py`. Coordinate changes to shared learning code through WP-05.

**Implement:**

1. Bounded text/voice participation for each WP-03 objective, maximum two normal learner turns plus one optional repair. Use the same character, register, scene facts, and objective across modalities.
2. Split communicative task outcome from linguistic polish. Accept understandable variants; clarify material ambiguity; preserve a natural character reply before offering optional correction. Use WP-05 for evaluation/credit effects.
3. Typed allowable consequences: e.g. indoor/outdoor meeting, chosen drink, revised arrival time. Derive them from the learner’s actual choice/utterance. The model may propose an outcome but may not write arbitrary keys into character memory.
4. Apply accepted consequences through the existing serial state/completion owner exactly once. Record source, character, and limited callback fact. Use existing relationship bounds and season/episode rules; no parallel memory store or invented “Romy read your message” event.
5. Distinguish a side scene from an actual serial episode completion. A side scene may add a grounded callback but cannot advance an unrelated unread episode. A real episode uses existing stale-scene/finale/idempotency safeguards.
6. Use existing microphone permission, transcription, TTS, and native flows. A text response is always available. Provider failure keeps the current answer/turn; do not present scripted canned dialogue as a live model response.

**Acceptance:** indoor/outdoor and café/tea choices produce coherent different replies and a subsequent eligible callback. A duplicate finish does not change relationship/episode state twice. Wrong grammar does not cause unrelated punitive plot outcomes. An unscored voice failure neither consumes a turn nor books a lapse.

**Tests:** paraphrase recognition, ambiguity, semantic success with form error, unsupported arbitrary memory field, target bypass, mid-turn timeout, repeated respond/end, microphone/transcription/TTS fallback, canonical character continuity, season finale, superseded scene, and side-scene non-advancement. Preserve `tests/test_serial.py`, `test_audio_story_regressions.py`, and relevant missions tests.

**Handoff:** bounded-turn policy, outcome schema/mapping, serial source references, modality states, evaluator fixtures, and a real end-to-end journey response/finish result.

## WP-07 — Today and the continuous daily-session frontend

**Owner:** daily-experience frontend agent. **Dependencies:** functional work starts after WP-02; functional completion requires WP-04/06. Visual completion additionally requires WP-01. The same owner retains both milestones.

**Read:** `pages/atelier.tsx`, `lib/atelier-next.ts`, current session resume behavior, typed API, WP-00 public fixtures, DELIVERY-PHASES.md; use the mapped Claude design for the visual milestone.

**Own:** new `components/atelier-v2/journey/`, a `useDailyJourney` hook under that directory, V2 branch in `pages/atelier.tsx`, and capability-aware `lib/atelier-next.ts` behavior/tests. Keep hooks/state/actions independent of presentation. Do not port the rejected preview.

**Implement:**

1. Recommend one real daily scenario with a clear start/resume action. For the functional milestone, use existing components and navigation; for the visual milestone, use Claude’s mapped home composition. Capability disabled follows current behavior. Resume existing in-progress learning before proposing a fresh day; make an old-session resume explicit.
2. One connected session renderer using the public step union. Scene, embedded recall, text/voice response, resolution, and completion share one shell. No tab/navigation jump is required to complete the daily loop.
3. One prompt, one answer area, one clear main action. Help/translation/details open on demand. Distinct pending, wrong, supported, correct, unscored, retry, and finished states. Keep selected choices readable and focus stable.
4. Persist stable mutation IDs for retryable actions via WP-10’s interface. Double taps disable/reuse the same request. Handle 202/409/422 and stale content explicitly; never turn a transport error into a red wrong-answer card.
5. Real completion recap using server evidence; at most one correction/focus headline; optional keepsake. Partial stop is visibly partial. “More” does not reopen the day or inflate streaks.
6. Maintain the legacy exercise view for current deep links, selected concepts, and existing sessions. Do not delete old exercise modes when removing them from the daily default.

**Milestones:** functional delivers the typed controller/hook and thin current-style renderer integrated with real APIs. Visual replaces that renderer with Claude-derived components and layouts, reusing the same behavior. Do not add a competing visual system or reorganize navigation during the functional milestone.

**Acceptance:** a first-time and a returning learner can finish the scene without learning the terms La Une/Épreuve/Relevé or visiting three separate screens. Duration and progress come from real plan/evidence data, never demo values. Keyboard/input remains visible at 320px, large text, and native keyboard open. No primary action hidden behind bottom navigation.

**Tests:** update `lib/atelier-next.test.js` for capability/legacy/active/finished precedence; add behavioral UI coverage in the current harness for discriminated states, request replay, errors, and completion. Run type-check/lint/build and the affected existing frontend journey/word-bank regressions. Validate against actual WP-02/04/06 APIs before closing the functional milestone; repeat affected interaction/resilience checks after the visual migration.

**Handoff:** separately record functional and visual evidence: reusable hook/actions, full-journey state coverage, route compatibility, server fixture parity, exact resume/request contract handed to WP-10, and final Claude comparison screenshots. Mark the package complete only after both milestones.

## WP-08 — Companion navigation, Stories, Speak, and optional practice

**Owner:** companion-screens frontend agent. **Dependencies:** WP-01, WP-06, and WP-07 visual for completed integration. Existing navigation stays in place during the functional phase.

**Read:** `lib/product-shell.ts`, layout/nav components, `pages/graphic-novel.tsx`, `pages/serial/*`, `pages/audio-session.tsx`, `pages/missions.tsx`, and source launch flags.

**Own:** product shell/navigation files, reader/Feuilleton/Courrier/audio surface components and pages. WP-07 retains `pages/atelier.tsx`; WP-09 owns notebook/vocabulary. Coordinate the active V2 journey’s distraction-free shell with WP-07.

**Implement:**

1. Implement navigation from the mapped Claude design, with understandable localized labels and consistent active routes across responsive layouts. Today, Stories, Speak, and Notebook describe functional destinations, not a mandatory four-tab composition. Legacy URLs/deep links remain valid.
2. Reader: one chapter heading, legible art/dialogue, unobtrusive progress, tappable words, optional translation, one next action. Preserve real panel generation/retry/error behavior and saved reader position.
3. Speak: purposeful scenario/character entry with one obvious start/resume. Voice is a deliberate learner action. Keep an understandable route to existing written missions; its label and placement follow the Claude navigation mapping.
4. Make optional deep grammar, conjugation, vocabulary review, mission selection, and longer conversation discoverable without turning Today into a dashboard. Coordinate notebook destinations with WP-09.
5. Expose coherent empty/new-user, loading/delayed-generation, finished, and unavailable states. Keep the existing book-library flag independent of serial stories.
6. Apply WP-01 components to active surfaces; remove obsolete style blocks only after proving no remaining references. Keep full existing recording, feedback, settings, and media behavior.

**Acceptance:** every old nav/deep link resolves to a functioning destination; the active daily journey is resumable after optional exploration; no “Speak” screen hides all writing features; reader still handles 409 superseded scenes and delayed images; permission denial offers text without resetting the task.

**Tests:** route mapping and capability-on/off navigation; native deep links; Stories→word→back position; Speak→Write→mission; audio resume and permission failure. Run existing thread-destination, serial-surface, audio, and missions regressions appropriate to changed behavior. Capture every mapped destination in both themes.

**Handoff:** explicit old→new destination map, remaining legacy surfaces, preserved optional feature inventory, and UI screenshots.

## WP-09 — Honest capability progress, personal notebook, and keepsakes

**Owner:** notebook/progress agent. **Dependencies:** functional evidence/reward work requires WP-05/06; visual notebook completion additionally requires WP-01. The same owner retains both milestones.

**Read:** existing CEFR/progress logic, `SessionLearningMoment` evidence, `atelier_rewards.py`, collectible source uniqueness, notebook/Cahiers/Relevé components and current vocabulary filters.

**Own:** new `app/services/journey_capabilities.py`, capability schema under a dedicated new module, new `components/atelier-v2/notebook/`, notebook/vocabulary/Relevé/Cahiers surfaces, narrow reward/achievement service changes. Send capability endpoint registration to WP-02. Any unavoidable new migration is allocated and integrated by the migration owner.

**Implement:**

1. Derive the three practical capability summaries from canonical evidence using CONTRACTS §8. Expose task, support level, modality, source context, and latest qualifying date. Do not turn a legacy success boolean into independent speaking evidence.
2. Keep CEFR and SRS intact. New capability states explain observed abilities; they do not replace existing algorithms or automatically promote CEFR.
3. For the visual milestone, implement Claude’s notebook/progress composition while preserving access to words, useful grammar, personal progress/keepsakes, search, and a due filter. Functional QA may expose real data through existing summary/list components. Use real learner-owned collections and existing gloss resolution. Keep imports, deck settings, conjugation, and detailed stats in secondary tools.
4. Add a completion keepsake to the existing source-unique collectible path for completed daily journeys; its final appearance follows Claude Design. No completion keepsake for failed/early-exit completion; no duplicate on HTTP retry. Preserve old collections and thresholds.
5. Use correct empty states: no discovered words, no evidence yet, unknown historic assistance, and no earned keepsakes. Make progress evidence available on demand instead of printing a full ledger above the activity.

**Acceptance:** “recognised,” “with support,” and “used independently” are distinguishable and defensible. Repeating a suggested reply never unlocks independent capability. Successful text does not claim pronunciation. A 24-hour later independent use changes the appropriate state without changing historic attempts. The notebook never displays the global vocabulary table as the learner’s collection.

**Tests:** add `tests/test_journey_capabilities.py`, `test_journey_rewards.py`; supported→independent→later transitions; unknown legacy assistance; different modality; 24-hour/local-date boundary; replayed evidence; another user’s data; retry/early-stop reward behavior. Preserve existing notebook modes, vocabulary biography, SRS due-cycle, achievements, and user export tests.

**Handoff:** functional milestone: rubric version, source-backed API examples, reward deduplication and unknown-history behavior. Visual milestone: preserved advanced-tool map and notebook/recap screenshots against Claude Design. Record both separately; the whole package closes only after both.

## WP-10 — Interruption recovery, connectivity, and native lifecycle

**Owner:** resilience/native agent. **Dependencies:** WP-02 and WP-07 functional. Recheck the affected lifecycle, focus, and keyboard behavior after WP-07/08/09 visual integration, before WP-12 final.

**Read:** `lib/pilot-resilience.ts`, `pages/_app.tsx`, auth sign-out/cache clearing, native recording/auth hooks, current service worker and mobile edge-flow tests.

**Own:** resilience cache module, root app resume hook, journey recovery hook/module, and necessary native lifecycle/service-worker changes. Do not change WP-07’s rendering privately; expose typed integration props/actions.

**Implement:**

1. Account- and journey-scoped cache for the last public snapshot, draft, active step, scroll/reading position, and pending mutation key. Clear it at sign-out/account switch using existing policies. Treat storage denial/corruption as recoverable.
2. Exact resume after refresh/app suspension/restart, with server reconciliation. A stale local revision cannot overwrite newer server completion. Resume yesterday’s active journey without recreating it.
3. Retry the same pending mutation after an ambiguous network failure. Persist only what is needed, not audio blobs/tokens or parallel transcript logs. Avoid automatic retries of non-idempotent legacy operations.
4. Offline means readable cached content and preserved drafts, with an honest connection state. Do not fake grading, invent a completion, apply offline SRS, or call scripted dialogue live. Submit after reconnection with explicit pending/synced feedback.
5. Native: safe areas, software keyboard, audio interruption/route changes, background transitions, permission denial, token expiry, and push/deep-link interaction. A deep link must not silently discard an unsent draft.

**Acceptance:** app kill after accepted attempt but before response receipt returns to the correct step without duplicate credit; kill mid-draft preserves text; airplane-mode cold start shows an owned cached scene; another account sees none of the previous account’s content; expired auth refresh does not cause a second attempt; native keyboard does not cover the response/action.

**Tests:** targeted resume/cache tests and existing mobile edge flows, plus manual native lifecycle checks on available device/simulator. Record unavailable physical-device tests explicitly. Include storage-full, offline, 401 refresh, 202 pending, 409 reconcile, two-device completion, and midnight cases.

**Handoff:** cache schema/version, retry ownership rules, cleanup behavior, reproducible interruption test results, and any remaining device-only gate.

## WP-11 — Journey observability and honest duration reporting

**Owner:** instrumentation agent. **Dependencies:** WP-02 to start; integrate functional producers from WP-04–07, WP-09 functional, and WP-10 before functional completion. Recheck producer wiring after the final UI migration. WP-08 visual work does not block functional instrumentation.

**Read:** `PilotEventService`, existing pilot event model, generation cost ledger, `scripts/pilot_digest.py`, pilot operations UI, and current client-error reporting.

**Own:** new `app/services/journey_events.py`, narrow pilot service/digest/ops changes, `tests/test_journey_events.py`. Other packages call typed event constructors; they do not write divergent event names/payloads.

**Implement:**

1. Versioned events: `journey_created`, `journey_started`, `journey_step_completed`, `journey_help_used`, `journey_paused`, `journey_completed`, `journey_ended_early`, `journey_generation_fallback`, `journey_provider_failed`, `journey_resume_conflict`.
2. Deduplicate authoritative transition events using the canonical mutation/source identity. A duplicate HTTP request is observable as a retry if useful but never another completion.
3. Attach IDs, level band, input mode, budget/estimated seconds, step kind, assistance/outcome category, and cost references. Do not copy raw utterances, audio, email, or personal free-text into telemetry.
4. Measure active reading/response/playback/feedback time with foreground and idle handling; report model/network waiting separately. Client timing is diagnostic, not trusted evidence for rewards or ability.
5. Extend the daily digest with start/completion/early-stop counts, step drop-off, help use, active duration distribution, provider waiting, retry/fallback rate, and known cost coverage. Null/unknown cost is not zero.

**Acceptance:** one sample day can be reconstructed without double-counting retries. A slow provider is distinguishable from a slow learner. The digest shows denominators/sample size and insufficient-data states. Existing non-journey pilot reports still work.

**Tests:** duplicate events, partial days, missing cost, idle/background intervals, provider wait, day/timezone attribution, deleted/other-user records, and backward-compatible rollups. Use existing event retention/access behavior.

**Handoff:** event dictionary with producer/trigger/fields, example digest, definition of each duration, and release metric queries.

## WP-12 — Integration QA and learner-validation package

**Owner:** independent QA/integration agent. **Dependencies:** functional gate requires WP-02–06, WP-07 functional, WP-09 functional, WP-10/11. Final gate additionally requires WP-01, WP-07 visual, WP-08, and WP-09 visual, with affected WP-10/11 checks rerun. Earlier test planning may start after WP-00.

**Own:** new `tests/test_journey_end_to_end.py`, `docs/implementation/atelier-v2/QA-REPORT.md`, scenario fixtures/seeder scoped to explicit test accounts, and the validation protocol. CI/capture-harness edits go through the integration owner.

**Implement and execute:**

1. Golden path against real endpoints/UI: new learner → café setup → relevant recall → open response → natural outcome → completion → notebook evidence → next eligible day uses a grounded callback/target. Use a controllable clock in tests, not writes to production history.
2. Regression matrix: existing unfinished legacy session, imported vocabulary, empty queue, many overdue words, advanced learner suitability, unavailable image/model, malformed content, superseded scene, missing mic/TTS, ambiguous network response, offline/reconnect, account switch, two clients, local midnight/DST.
3. Evaluate all three scenario families with exact-answer variants, plausible paraphrases, correct French with an omitted optional target, grammatical errors that preserve intent, irrelevant answers, nonsense, answer-key injection, and unsupported story-memory proposals. A model response is untrusted data and cannot override ownership, outcome schema, or grading policy.
4. Review a documented sample of live generated content/corrections within configured dev cost limits. Unit fixtures alone cannot establish language quality. Record model/version, prompt version, judgments, and failures without publishing learner data.
5. Check essential usability/recovery in the functional renderer; the final milestone validates Claude design fidelity, responsive, dark/system, large text, keyboard/screen-reader essentials, reduced motion, keyboard-safe areas, and native pause/resume. Use actual CSS viewport measurements.
6. Run assembled CI-equivalent gates: Ruff, backend suite, current word-bank audit, frontend type-check/lint/tests/build, native checks/build, mobile capture, and disposable migration validation. Report any pre-existing failures separately with baseline evidence.
7. Prepare a short learner study: five representative learners, including at least two beginners, asked to start the recommended activity, finish a question, recover from a mistake, resume, and revisit a saved word without guidance. Do not recruit/contact people automatically. Provide tasks, consent-aware local note template, and report layout for the owner to run.

**Gate separation:** functional QA verifies real APIs, learning credit, outcomes, recovery, and current-renderer behavior. Final QA additionally verifies Claude-derived screens, navigation, complete accessibility/native coverage, and records learner validation. A functional pass is not final release readiness.

**Release gates:** zero unresolved data-loss/double-credit/auth/answer-leak regressions; all mandatory API/UI transitions verified; all generated validation samples reviewed; an honest fallback for every provider failure; no horizontal overflow or hidden actions in the agreed matrix; existing history and advanced tools remain accessible. Fixture plans all meet the 300-second expected envelope. Initial usability target: at least four of five learners find/start the right activity without explanation; median active completion near five minutes and upper-tail overruns investigated. These are pilot targets, not established facts.

**Acceptance:** QA report explicitly separates automated passes, manual browser passes, real-model quality review, physical-device validation, and learner study. Missing external/device/learner evidence is marked pending, never fabricated as passed. Package can hand over an engineering-tested candidate while the broader rollout gate remains closed.

**Handoff:** issue list with reproduction, exact tested revision/configuration, screenshots and commands/results, coverage gaps, and go/no-go recommendation per gate.

## WP-13 — Controlled enablement, rollback, and migration cleanup

**Owner:** integration owner from WP-00. **Dependencies:** WP-12 final evidence; no unresolved release-blocking engineering failures. Default-off wiring/runbook preparation may happen earlier, but final enablement readiness cannot be declared from functional QA alone.

**Own:** final flag/cohort configuration lease, rollout runbook, final integration changes, and a proved-unused legacy UI cleanup list. No automatic production deployment or deletion of live data.

**Implement:**

1. Verify all packages against the final assembled revision, not only individual branches. Record fixture/contract/content/rubric versions and migration order.
2. Default V2 off; prepare an explicit pilot allowlist and documented enable/disable procedure. Existing clients without V2 capability continue to work.
3. Rollback disables creation immediately while allowing already-created journeys to read/resume/finish safely. Keep persisted data and canonical learning history. Do not downgrade/delete live V2 rows as a rollback technique.
4. Verify legacy in-progress sessions, native cold start, push destinations, exports, and old deep links with flag both on and off.
5. After Claude UI integration, remove only UI/CSS proven unused after migration and only after the relevant regression passes. Keep old APIs, SRS logic, and unfinished-session support. Produce a deferred deprecation list instead of an opportunistic cleanup rewrite.
6. Write `docs/implementation/atelier-v2/ROLLOUT.md` with prerequisites, precise config keys, pilot scope, health queries, rollback/drain steps, ownership, and remaining human/device gates.

**Acceptance:** a staged cohort can use the real flow; disabling the flag preserves their active work; legacy learners still start/resume successfully; each capability/metric/reward is based on real data. Production enablement is a separate explicit action, not part of an agent’s interpretation of “implementation complete”.

**Handoff:** final release candidate, test report links, migration/config checklist, drain demonstration, and concise list of remaining externally required actions. Update STATUS with actual results and leave unexecuted gates pending.
