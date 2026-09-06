# Atelier V2 — implementation handoff

Updated 2026-09-06. Delivery specification revision: 3. The original functional implementation has been committed; see STATUS and NEXT-STEPS-REVIEW for verified results and gaps. Wire contracts retain their implemented version until a coordinated migration.

**New required scope:** the owner requires generated new situations within one continuing story, including opportunities that emerge from learner conversations. [WP-14 — Continuous story](CONTINUOUS-STORY.md) extends the original three-scenario foundation. The original functional pass alone no longer satisfies the intended product. Complete the correctness fixes in [NEXT-STEPS-REVIEW.md](NEXT-STEPS-REVIEW.md) and WP-14; final Claude UI and release gates remain required.

This handoff covers the functional redesign discussed with the owner. **The owner rejected the Codex visual proposal and selected their Claude Design direction for the UI.** The earlier `docs/atelier-redesign/` prototype is archived context and must not be implemented as the visual specification. The owner supplied the exact Claude link, recorded in DELIVERY-PHASES.md. It redirects to sign-in in the available browser; the design remains uninspected, and no substitute has been approved.

Implement the functional foundation first, with a thin integration into the existing UI for real end-to-end testing. Final visual implementation follows the identified Claude Design artifact. See [DELIVERY-PHASES.md](DELIVERY-PHASES.md) for phase gates and the UI handoff checklist.

## Product decision

The primary experience is one short, connected situation in the learner’s French life:

**Arrive in a scene → retrieve a few relevant things → respond with a purpose → see a consequence → finish.**

The learner should not have to complete a grammar worksheet to reach the story. Review and useful grammar live inside the situation. Standalone practice, longer conversations, reading, written missions, and advanced notebook tools remain accessible as optional activities.

First release: a five-minute target, one practical objective, one established character/location, at most two embedded recall moments, one bounded conversation, and a clear ending. An estimate is not a countdown: never auto-submit, truncate recording, penalise slowness, or claim every human can finish in exactly five minutes.

The existing API, SRS, error memory, serial thread, account data, and old in-progress sessions must survive. This is an additive migration, not a backend rewrite.

## Read these together

1. This file: decisions, dispatch order, ownership, release scope.
2. [CONTRACTS.md](CONTRACTS.md): shared API, state, evidence, timing, and interface contracts.
3. [WORK-PACKAGES.md](WORK-PACKAGES.md): exact task boundaries and acceptance criteria for WP-00 through WP-14.
4. [DELIVERY-PHASES.md](DELIVERY-PHASES.md): functional-first sequence and Claude Design source-of-truth record.
5. [CONTINUOUS-STORY.md](CONTINUOUS-STORY.md): required WP-14 extension, current architectural gaps, ownership, and longitudinal acceptance criteria.

Historical design documents remain context, not authority over the owner’s latest choice. The functional decisions remain: story-first daily practice, clear localized controls, short bounded sessions, contextual review, and preserved optional/legacy functionality. Typography, colors, shapes, artwork treatment, screen composition, animations, navigation arrangement, and reward appearance must come from the Claude Design artifact. Do not carry over the rejected prototype’s Manrope/palette/flower/button system or assume its four-tab arrangement is approved.

## Verified starting points

Paths below are repository-relative; confirm their current contents before editing.

| Existing system | Starting point | Reuse requirement |
|---|---|---|
| Fixed exercise ladder | `app/services/atelier.py`, `web-frontend/pages/atelier.tsx` | Keep legacy sessions and deep practice; do not use the 15-per-concept formula for V2 |
| Next activity selection | `web-frontend/lib/atelier-next.ts` | Add capability-aware precedence, preserve legacy branch |
| Unified due items | `app/services/unified_srs.py` | Select existing due items; do not introduce a second scheduler |
| Vocabulary credit | `app/services/vocabulary_credit.py` | Preserve exposure/recognition/production distinctions |
| Corrections | `app/services/error_memory.py`, `grammar_feedback.py` | Reuse validated corrections and identities |
| Conversational learning moments | `app/services/session_moment_planner.py`, `app/db/models/session.py` | Persist canonical learning evidence here or in existing attempt records |
| Story continuity | `app/services/serial.py`, `serial_arc_planner.py`, `app/db/models/serial.py` | Use `SerialThread.state`, episode briefs, and existing completion logic |
| Voice | `app/services/audio_session_service.py`, `web-frontend/pages/audio-session.tsx` | Retain transcription, TTS, retry, and native recording safeguards |
| Offline/resume | `web-frontend/lib/pilot-resilience.ts`, `pages/_app.tsx` | Extend existing account-cleared cache patterns |
| Progress/rewards | `app/services/cefr_progress.py`, `atelier_rewards.py`, `app/db/models/atelier.py` | Add evidence views and reward types without resetting progress |
| Pilot observability | `app/services/pilot_events.py`, `serial_costs.py`, `scripts/pilot_digest.py` | Extend; do not install another analytics SDK |

The worktree already contains extensive uncommitted work. No agent may reset, clean, revert, or overwrite it to obtain a tidy baseline. WP-00 must preserve and identify the current working state before parallel implementation. Do not start from an older default-branch snapshot that omits the current fixes.

## Package index

| ID | Package | Depends on | Primary deliverable |
|---|---|---|---|
| WP-00 | Baseline, integration ownership, contract fixtures | — | Reproducible baseline and frozen shared fixtures |
| WP-01 | Claude Design translation and UI primitives | 00 + identified Claude artifact | Design-derived accessible React components and state coverage |
| WP-02 | Daily journey persistence and API | 00 | Durable state machine and idempotent transport |
| WP-03 | Scenario content and generation | 00 | Validated, bounded scene briefs and fallback content |
| WP-04 | Short-session planner | 02, 03, 05 | Story-first plan within the time envelope |
| WP-05 | Learning evidence and embedded review bridge | 02 | One canonical learning-credit path |
| WP-06 | Purposeful conversation and story consequences | 02, 03, 05 | Bounded response loop and grounded callbacks |
| WP-07 | Connected daily flow: functional, then Claude UI | Functional: 02,04,06; visual: 01 | Real end-to-end flow, then final presentation |
| WP-08 | Companion-screen visual migration | 01; final integration 06,07 visual | Claude-derived companion screens with features retained |
| WP-09 | Capability progress and notebook | Functional: 05,06; visual: 01 | Evidence/reward backend first, final notebook later |
| WP-10 | Resume, network recovery, and native integration | 02,07 functional | Recovery on the functional flow; recheck final UI |
| WP-11 | Events, duration measurement, and pilot digest | 02; functional integration 04–07,09 functional,10 | Evidence independent of final visual design |
| WP-12 | Functional QA, then final UI/learner validation | Functional: 02–07 functional,09 functional,10,11; final: 01,07 visual,08,09 visual | Separate functional and visual evidence gates |
| WP-13 | Controlled rollout and compatibility cleanup | 00,12 final,14 | Default-off wiring may be prepared earlier; release gate stays closed |
| WP-14 | Generated situations and one continuing story | Functional foundation; 14A contract freeze; R-1/R-2 before final integration | Causal new situations, emerging learner proposals, shared story progression, longitudinal QA |

“Functional” and “visual” are separate milestones inside a package, not new competing owners. Record both in STATUS. A package with pending visual work is not fully complete. Agents may build against WP-00 fixtures earlier; mocks are not shipping completion.

## Dispatch order

For the current continuation, preserve verified completed work, close the review findings, and follow WP-14A–F in CONTINUOUS-STORY.md. The sequence below records the original foundation and visual integration order; final WP-13 now also requires WP-14.

Use one integration owner throughout. The same agent may own WP-00 and WP-13, but they are separate tasks.

With three implementation agents plus an integration owner:

1. Finish WP-00. Run WP-02 and WP-03 independently. Identifying/mapping the Claude artifact can happen alongside these; it is not a backend blocker.
2. After WP-02, run WP-05 and begin WP-11. WP-07 can prepare a presentation-independent hook/client against fixtures; reuse current components for its temporary functional renderer.
3. After WP-03/05, run WP-04 and WP-06. Integrate one real café journey through WP-07 before expanding all scenario families. This verifies the architecture early.
4. Complete WP-09’s evidence/reward backend, WP-10, WP-11, and WP-12’s functional gate. This produces a tested functional foundation, not a visually finished release.
5. Once the Claude artifact is identified and its required state mapping is reviewed, run WP-01. Migrate WP-07’s renderer, WP-08’s companion screens, and WP-09’s notebook to that system. The existing hooks/APIs remain reusable.
6. Recheck WP-10/11 integration after the visual changes, run WP-12’s final visual/native/learner gates, then finish WP-13. Prepare flags/rollback earlier if useful; do not equate functional readiness with launch readiness.

Never dispatch all packages into the same checkout at once. Use isolated checkouts from the preserved WP-00 baseline when available. Merge in dependency order. If working in a shared checkout, maintain exclusive file leases in `STATUS.md`; do not edit a file leased to another package.

## Shared-file ownership

| Files / area | Exclusive implementation owner |
|---|---|
| `app/config.py`, `app/api/v1/api.py`, model export registration, journey migration, `app/schemas/daily_journey.py`, `web-frontend/types/daily-journey.ts` | WP-02; WP-13 gets the config lease only after WP-02 closes |
| `app/services/daily_journey.py` state orchestration | WP-02; domain packages implement new modules and hand off integration calls to this owner |
| `app/services/atelier.py` and existing Atelier start/attempt endpoints | WP-05 owns any necessary learning-adapter changes; WP-04 must not rewrite this ladder |
| `app/services/serial.py`, `serial_arc_planner.py`, serial completion hooks | WP-06; WP-03 implements a separate content adapter |
| `app/services/vocabulary_credit.py`, `unified_srs.py`, `session_moment_planner.py`, `error_memory.py` | WP-05 |
| `web-frontend/services/api.ts` | WP-02 adds journey methods and shared transport; subsequent agents use a new facade rather than parallel edits |
| New UI primitives, `styles/globals.css`, font assets | WP-01 |
| `pages/atelier.tsx`, new daily UI components, `lib/atelier-next.ts` | WP-07 |
| `lib/product-shell.ts`, `components/layout/*` | WP-08 |
| Reader, missions, audio pages and their surface components | WP-08 |
| Notebook, vocabulary pages, Relevé/Cahiers; capability progress and reward services | WP-09 |
| `pages/_app.tsx`, `lib/pilot-resilience.ts`, native lifecycle hooks, `public/sw.js` if needed | WP-10 |
| Existing pilot event service, digest, pilot operations view | WP-11 |
| CI, root build manifests, capture harness, migration sequencing | Integration owner; execute WP-12 requests serially |

A dependency on another owner’s file is a handoff, not permission for simultaneous edits. Submit the intended signature/call-site patch to the owner. Integration ownership includes retaining the ability to run affected tests before accepting a patch.

## Release boundaries

**Original functional foundation:** real five-minute journey, three scenario families, speech/text, review credit, grounded outcomes, evidence summaries, recovery and telemetry, exercised through existing UI components. No new visual system or navigation reorganisation is required for this milestone.

**Pilot MVP:** all packages complete, including WP-14 generated situations and causal story progression; the above functionality presented through the Claude Design UI, learner-language controls (en/de/fr), existing light/dark/system and text-size behavior preserved, and working legacy fallback.

**Explicitly deferred:** social/leaderboards, a new currency or reward economy, a new SRS algorithm, large branching story trees, automatic microphone activation, rewriting all optional grammar content, adaptive ten/fifteen-minute modes, and deleting old APIs. Existing longer sessions stay available as optional practice.

Do not remove written missions, Anki import, conjugation, settings, achievements, or the feature-flagged library because a design omits them. Preserve existing access during functional work and map them deliberately into the final Claude information architecture. `storyFeatureVisible` currently controls the book/library feature; do not accidentally use it to disable the serial Feuilleton.

## Common definition of done

- All package acceptance cases work against real application state; shipping paths have no fixture learner names, fake streaks, static dates, scripted “AI”, or invented durations.
- Authentication, ownership checks, existing SRS behavior, previous learning history, and legacy in-progress sessions remain intact.
- Tests cover behavioral failure modes, not just static strings or snapshots that mirror implementation.
- Run targeted tests during implementation; the integration owner runs the full existing CI gate once the candidate is assembled. Fix relevant regressions; record unrelated baseline failures without hiding them.
- Frontend validation: current type-check, lint, web build, and affected navigation tests. Native-affecting packages also run the existing native environment tests/build recipe from CI, using CI-only placeholder flags solely in non-production validation.
- New migrations are tested on disposable databases, including populated legacy data and concurrent writes. Never use a learner’s live DB for destructive migration tests.
- Visual checks at 320, 390, 440, 768, and 1280 CSS px; light/dark/system; large text; keyboard and reduced motion; no obscured primary action with the software keyboard open.
- Package handoff lists changed files, new interfaces, exact commands/results, screenshots for visual changes, unresolved risks, and rollback impact. No deployment, publishing, external messages, or user-data cleanup is included in these packages.

## Copyable agent assignment

For a lead agent coordinating the complete functional implementation, use [IMPLEMENTATION-PROMPT.md](IMPLEMENTATION-PROMPT.md). The shorter assignment below is for an individual package owner.

> Implement **WP-XX [functional or visual milestone where applicable]** from `docs/implementation/atelier-v2/WORK-PACKAGES.md`. First read `README.md`, `CONTRACTS.md`, `DELIVERY-PHASES.md`, and the latest `STATUS.md`, plus applicable repository instructions. The owner rejected the Codex visual prototype; Claude Design is the UI authority. Use existing UI components during the functional milestone and do not implement an invented replacement design. Use the preserved current-worktree baseline from WP-00. Own only allocated files, reuse existing services, preserve legacy behavior, and keep application logic outside presentation components. Deliver code, targeted behavioral tests, relevant UI verification, and a precise handoff. Coordinate shared-file patches. Do not execute another package, unilaterally change contracts, mark fixture-only or functional-only work fully complete, deploy, or discard pre-existing changes.
