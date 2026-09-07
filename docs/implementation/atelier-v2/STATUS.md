# Atelier V2 — execution status and file leases

Revision 2, functionality first, Claude UI.
**Scope extended 2026-09-06:** delivery revision 3 adds required [WP-14](CONTINUOUS-STORY.md). Original completion entries below are historical implementation reports; independent findings are in [NEXT-STEPS-REVIEW.md](NEXT-STEPS-REVIEW.md). Continuous new situations and integrated story progression are not implemented by those completion entries.
**Execution started 2026-09-05.** Integration owner: lead implementation agent.
Baseline: [BASELINE.md](BASELINE.md). Frozen wire contract: [CONTRACT-FREEZE.md](CONTRACT-FREEZE.md).

| Package | Status | Owner | Baseline / revision | Evidence / blockers |
|---|---|---|---|---|
| WP-00 | **Complete** | Integration owner | worktree @ `367082` + uncommitted work | BASELINE.md, CONTRACT-FREEZE.md, `app/services/journey_contracts.py`, 26 public + 9 private fixtures. Baseline: pytest 593 passed / 1 pre-existing failure; tsc, lint, atelier-next pass |
| WP-01 | **Complete** | frontend lead (subagent A) | `d83ebb0` + 2026-09-06 consistency pass | Owner's local export `docs/design-reference/claude/Atelier App.dc.html` inspected and mapped; `styles/atelier-v2.css`, `components/atelier-v2/ui`, dev gallery `/atelier-v2-gallery`. Consistency pass fixed the legacy-reset cascade and the reader fonts; see FRONTEND-ENGINE-HANDOFF §4, §4B, §4C |
| WP-02 | **Complete (functional)**, patches in flight | agent `wp02` | WP-00 baseline | 137 own tests; café journey proven end-to-end 44/44 vs real API; PG invariants verified by integration owner. Applying 8 review patches |
| WP-03 | **Complete (functional)** | agent `wp03` | WP-00 baseline | 50 tests pass; café/de/fr descriptors match frozen fixtures byte-for-byte (verified independently by `tests/test_journey_contract_parity.py`). Authored ceiling is A2 |
| WP-04 | **Complete (functional)** | agent `wp04` | WP-00 baseline | 62 tests; verified independently via the parity gate (100-due-word case, purity, determinism) |
| WP-05 | **Complete (functional)**, patch in flight | agent `wp05` | WP-00 baseline | 71 tests; SRS/audio regressions pass; canonical credit proven against PostgreSQL. Adding candidate evidence metadata for WP-04 |
| WP-06 | **Complete (functional)** | agent `wp06` | WP-00 baseline | 78 own tests; serial/audio/missions regressions 90 pass; outcome-schema escape and neutral-default verified by the parity gate |
| WP-07 functional | **Complete** | agent `wp07` + wiring agent | WP-00 baseline | Controller/renderer + WP-10 recovery wired; D-5/D-6/D-7 fixed and measured |
| WP-07 visual | **Complete** | frontend lead (subagent A) | `d83ebb0` | `JourneySession`/`JourneySteps`/`JourneyTodayCard` on the design's Séance chrome; streak omitted (no real count); verified by build, tests and cascade reproduction — not yet walked on the authed route |
| WP-08 | **Complete (visual)** — browser walk pending | frontend lead + 6 subagents | working tree, 2026-09-07 | Every learner-facing screen is on the av2 system: tab bar, masthead, Home (1a), Séance (legacy exercise session on the Séance chrome, `components/epreuve/Epreuve.tsx`), Feuilleton page (`pages/graphic-novel.tsx`, one column, every state; legacy `Feuilleton.tsx` deleted), Feuilleton index, reader, cast, replay, Missions, Réglages, Lexique, Cahier, story-engine reader/archive/409 transitions. Verified by tsc, lint, all node suites, every source-scanning backend test and a production build; authenticated routes not walked in a browser. `ATELIER_DAILY_JOURNEY_ENABLED` is still off, so learners see the (now migrated) legacy séance, not the daily journey |
| WP-09 functional | **Complete** | agent `wp09` | WP-00 baseline | Rubric unified with the recap; keepsake source-unique |
| WP-09 visual | **Complete (visual)** with WP-08 — browser walk pending | Cahier subagent | working tree, 2026-09-06 | Notebook, grammar fiche and Le Relevé on the av2 system (`components/cahiers/CahierV2.tsx`); capability/keepsake data unchanged; Home's Errata and Lexique tiles lead there |
| WP-10 | **Complete** | agent `wp10` + wiring agent | WP-00 baseline | 35/35 live; wired into the real render path; respond-draft prune bug fixed |
| WP-11 | **Complete** | agent `wp11` | WP-00 baseline | Ten events, payload allow-list verified hostile; `active_seconds` now measured |
| WP-12 functional | **Complete — conditional GO met** | agent `wp12` | WP-00 baseline | NO-GO on 10 defects; D-1..D-7 fixed and re-verified. D-1b, live-model review, device/learner gates remain open |
| WP-12 final | Waiting for visual milestones | Unassigned | — | Not started; visual gates stay pending |
| WP-13 | Waiting for 12 final and 14 | Unassigned | — | No rollout authorized or executed |
| WP-14 | Backend implemented; **frontend connected (14E)**; **PG lock races 33/33 and browser walk done 2026-09-06 evening**; live prose review and one frontend finish defect open | Codex engine owner + frontend lead | working tree, 2026-09-06 | [Engine implementation](ENGINE-IMPLEMENTATION.md), [reader contract](ENGINE-FRONTEND-CONTRACT.md). Frontend: scene step reads `GET /story-engine/episodes?journey_id` into the immersive reader, saves position by panel id, continues through the journey controller; archive lists generated episodes; 409 `story_episode_route` / `story_journey_required` handled as route transitions. Driven end to end in a browser on the authenticated route (`scripts/dev_story_engine_server.py`, fake provider) and under PostgreSQL concurrency (`scripts/verify_story_engine_pg.py`, 33/33); see ENGINE-IMPLEMENTATION.md. Live prose review run 2026-09-06 evening with owner consent (~US$0.15): ten defects found and fixed in `living_story.py`, three-scene sample accepted (ENGINE-IMPLEMENTATION.md §Live prose review). 2026-09-07 stabilization: stale-revision auto-finish fixed and browser-proven; learner address preference (Settings → engine) shipped; R-1/R-2/D-1b closed (xfail removed); CI plumbing green (ruff, alembic round trip, grammar denominator, port-8000 defaults, pre-hydration auth guard); WP-14F report delivered and its L-1..L-10 fixed as living-story-v2 (ENGINE-IMPLEMENTATION.md). Open: a fresh 14-day live run on v2 for variety, Lila's register (product), production stays off |

## File leases

One shared checkout (see BASELINE.md for why). **Do not edit a file leased to another
package.** Shared-file changes are submitted to the lease holder as a patch.

| File / directory | Package | Agent | Acquired | Released / handoff |
|---|---|---|---|---|
| `app/db/models/daily_journey.py` (new) | WP-02 | wp02 | 2026-09-05 | — |
| `app/schemas/daily_journey.py` (new) | WP-02 | wp02 | 2026-09-05 | — |
| `app/api/v1/endpoints/daily_journey.py` (new) | WP-02 | wp02 | 2026-09-05 | — |
| `app/services/daily_journey.py` (new) | WP-02 | wp02 | 2026-09-05 | — |
| `app/config.py` | WP-02 | wp02 | 2026-09-05 | WP-13 gets the config lease only after WP-02 closes |
| `app/api/v1/api.py` | WP-02 | wp02 | 2026-09-05 | — |
| `app/db/models/__init__.py` | WP-02 | wp02 | 2026-09-05 | — |
| `alembic/versions/e2f3a4b5c6d7_add_daily_journeys.py` (new) | WP-02 | wp02 | 2026-09-05 | revision id assigned by integration owner; `down_revision = "d1e2f3a4b5c6"` |
| `tests/conftest.py` | WP-02 | wp02 | 2026-09-05 | — |
| `tests/test_daily_journey_*.py` (new) | WP-02 | wp02 | 2026-09-05 | — |
| `web-frontend/types/daily-journey.ts` (new) | WP-02 | wp02 | 2026-09-05 | — |
| `web-frontend/services/daily-journey.ts` (new) | WP-02 | wp02 | 2026-09-05 | — |
| `web-frontend/services/api.ts` | WP-02 | wp02 | 2026-09-05 | later packages use the new facade, not parallel edits |
| `app/services/journey_content.py` (new) | WP-03 | wp03 | 2026-09-05 | **released 2026-09-05** |
| `app/data/journey_scenarios/` (new) | WP-03 | wp03 | 2026-09-05 | — |
| `app/prompts/journey/` (new) | WP-03 | wp03 | 2026-09-05 | — |
| `tests/test_journey_content.py` (new) | WP-03 | wp03 | 2026-09-05 | — |
| `app/services/journey_learning.py` (new) | WP-05 | wp05 | 2026-09-05 | **released 2026-09-05** |
| `app/services/vocabulary_credit.py` | WP-05 | wp05 | 2026-09-05 | narrow additive changes only |
| `app/services/unified_srs.py` | WP-05 | wp05 | 2026-09-05 | narrow additive changes only |
| `app/services/error_memory.py` | WP-05 | wp05 | 2026-09-05 | narrow additive changes only |
| `app/services/session_moment_planner.py` | WP-05 | wp05 | 2026-09-05 | narrow additive changes only |
| `tests/test_journey_learning.py`, `tests/test_journey_correction_policy.py` (new) | WP-05 | wp05 | 2026-09-05 | — |
| `app/services/journey_contracts.py` | WP-00 | integration owner | 2026-09-05 | **frozen** — change requests go through the integration owner |
| `tests/fixtures/daily_journey_v1/` | WP-00 | integration owner | 2026-09-05 | frozen; WP-02 adds validation in its own test file |
| `app/services/journey_planner.py`, `tests/test_journey_planner.py` (new) | WP-04 | wp04 | 2026-09-05 | — |
| `app/services/journey_conversation.py`, `tests/test_journey_conversation.py`, `tests/test_journey_story_outcomes.py` (new) | WP-06 | wp06 | 2026-09-05 | — |
| `app/services/serial.py`, `serial_arc_planner.py`, audio/mission services | WP-06 | wp06 | 2026-09-05 | narrow adapter changes only |
| `tests/test_journey_contract_parity.py`, `scripts/verify_daily_journey_cafe.py` (new) | WP-00 | integration owner | 2026-09-05 | cross-package gates |
| `docs/implementation/atelier-v2/*` | WP-00 | integration owner | 2026-09-05 | agents report; the owner writes |
| CI, root manifests, migration sequencing | Integration owner | — | 2026-09-05 | — |

## Functional milestone — final state (2026-09-06)

Backend **1372 passed, 1 xfailed, 1 pre-existing failure**. Café journey **45/45** and
recovery **35/35** against the live authenticated API. Frontend type-check, lint, build and
all five test suites green.

**Deliberately still open, not closed quietly:**

* **D-1b — "the next eligible day uses a grounded callback" is unimplemented.**
  `recap.story_outcome.callback_fr` is produced and stored; nothing reads it back. The
  rotation fix made its test pass *incidentally* (a different scene is not a grounded one),
  so the assertion was tightened to grounding only and it now fails on purpose as an
  `xfail`. This is a real CONTRACTS gap, not a test artifact.
* **Live-model content quality: never evaluated.** No provider was enabled; the model path
  is unvalidated for language quality. Protocol ready in QA-REPORT.md §9.
* **Every device, native, visual and learner gate: pending.** No physical device, no
  simulator run, no `build:native`, no `capture:mobile`, no Docker build.
* **The legacy feedback FAB is 36x36.** It lives in a widget mounted on every legacy page;
  fixing it means restyling legacy surfaces, which is out of scope here.
* **Three pre-existing CI failures** (ruff, `alembic downgrade base`, grammar-notebook) are
  documented in BASELINE.md with evidence that none is caused by this work.

A functional pass is not launch readiness. `ATELIER_DAILY_JOURNEY_ENABLED` remains
**false** and no rollout was performed.

## Provider-cost incident — 2026-09-05 (contained)

A WP-06 test fixture set `settings.ATELIER_LLM_ENABLED = True` globally, which also
enabled WP-03's generator. `app/config.py` loads the repository `.env`, which holds a
**live `OPENAI_API_KEY`**, so several intermediate test runs very likely made billable
calls. The exposure predates Atelier V2: `tests/conftest.py` used only
`os.environ.setdefault(...)` on the flags, which a runtime flip defeats.

Contained by the integration owner with a repository-root `conftest.py` that loads before
`app.config` reads `.env` and **overwrites** every provider credential with an obviously
fake value, plus `tests/test_provider_cost_guard.py` (8 tests) reproducing the incident
shape. **Never weaken this guard, and never rely on a real credential in a test** — patch
the client object instead (`journey_content.LLMService`,
`journey_conversation._conversation_llm`).

Residual owner action: review OpenAI billing for 2026-09-05 and rotate the `.env` key if
warranted. Agents must not rotate credentials.

## Open cross-package defect — capability rubric had two authorities

**2026-09-05, found by WP-09, verified by the integration owner.** `CONTRACTS.md` §8
defines one rubric, implemented by `journey_capabilities`. But
`DailyJourneyService._build_recap` computed `recap.capability_evidence` inline
(`MET + assistance none -> independent_once`), never consulting it. The same journey could
therefore read `independent_once` in the recap and `not_tried` on
`GET /capabilities/progress`; the inline rule can never yield `used_again_later` and
ignores §8's `is_open_production`, different-journey, different-local-date and 24-hour
conditions.

Contributing defect: a respond turn that fulfils the objective **without touching a
tracked target** writes no evidence at all, so the rubric legitimately reports
`not_tried`. WP-09 chose that false negative over a false positive, which was right.

Assigned as a coordinated fix (agent `wp-fix-capability`, both original owners closed):
the recap must delegate to the rubric through the existing adapter seam, and
`journey_learning` must record an objective-level opportunity for the respond turn —
capability evidence only, never SRS or error-memory credit. Status: in progress.

## Contract decisions

* **2026-09-05, ratified — candidate evidence metadata (WP-05, for WP-04).**
  `select_learning_candidates` now sets `metadata["last_evidence_kind"]` (only when
  genuinely known) and `metadata["evidence_history"]` (`recorded` | `unknown` | `none`).
  Semantics ratified as WP-05 implemented them: the strongest observation **that has not
  been superseded by a later failure**. A target demonstrated independently and since got
  wrong reports `not_yet`, so WP-04 will not skip its recall. This is the safe direction —
  a wrong "already demonstrated" silently removes a learner's practice. Legacy/pre-V2 rows
  raise only the `unknown` flag and can never contribute an evidence kind. Producer: WP-05.
  Consumers: WP-04, WP-09.
* **2026-09-05, ratified — `JourneyEvidenceRecord.observed_at`.** WP-05 found that
  ordering evidence by `created_at` is unsound: it is `server_default=func.now()`, and in
  PostgreSQL every row written inside one transaction shares the same timestamp, so a
  success and a later failure recorded in one journey transaction ordered arbitrarily —
  the failure could have been dropped, producing exactly the false "already demonstrated"
  this rule exists to prevent. Records now carry `observed_at` (from `completed_at`) and
  are ordered by it. WP-09 must use `observed_at`, not row order, to sequence two
  observations inside one learner-local day. Producer: WP-05. Consumers: WP-04, WP-09.


* Delivery-plan revision 2; wire `contract_version: 1` unchanged.
* **2026-09-05, WP-00 freeze.** Four documented extensions to CONTRACTS §4, recorded in
  CONTRACT-FREEZE.md: `TodayEnvelope.control_language`; the `_native` / `_fr` suffix
  rule for every localized string; `PublicStep.assistance_used`; structured
  `{"detail": {...}}` error bodies. Producer: WP-02. Consumers: WP-04–WP-11.
* **2026-09-05, WP-00 decoupling decision.** The §6 domain callables take the frozen
  dataclasses in `app/services/journey_contracts.py`, never WP-02's ORM rows. This lets
  WP-03 and WP-05 run concurrently with WP-02 instead of behind it. Producer: WP-00.
  Consumers: WP-02, WP-03, WP-04, WP-05, WP-06, WP-09, WP-11.
* **2026-09-05, WP-00 baseline decision.** Isolated git worktrees are not used, because
  the baseline is uncommitted and `git worktree` can only materialise committed history.
  Concurrency safety comes from the lease table above.
* **2026-09-05, contract revision 1 — `transcript_ref` is optional.** CONTRACTS §4
  assumes an owned transcript identifier for voice attempts; inspection of
  `app/api/v1/endpoints/audio.py` shows `/audio/transcribe` is stateless and persists
  no transcript row, and no transcript model exists. `transcript_ref` is therefore
  optional/nullable and the §5 cross-user transcript check is vacuous rather than
  skipped (WP-02 still validates a supplied ref). Modality stays first-class evidence.
  Full rationale and the rejected alternative are in CONTRACT-FREEZE.md.
  Producer: WP-02. Consumers: WP-05, WP-06, WP-07, WP-09, WP-10.
* **2026-09-05, decision — journey evidence keeps a digested `source_id`.**
  `session_learning_moments.source_id` is `VARCHAR(64)`; the frozen source-key grammar
  is longer. WP-05 stores `"dj-" + sha256(source_key)[:40]` (43 chars, 160 bits) and
  writes the full key verbatim into `prompt_payload["source_key"]`. Dedup stays exact
  and nothing is lost. **Rejected:** widening the column on an existing populated table
  for no functional gain. Producer: WP-05. Consumers: WP-02, WP-09, WP-11.
* **2026-09-05, decision — the journey's `LearningSession` closes only on an honest
  complete.** WP-05 creates one `LearningSession` per journey
  (`topic = "daily_journey:<journey_id>"`) and never closes it. Verified by inspection:
  the legacy resume path queries `AtelierSession`, not `LearningSession`, so an open
  journey session can never surface as a legacy resume. `AchievementService` counts
  `LearningSession.status == "completed"`, so WP-02 sets `status="completed"` **only**
  when `finish_kind == "complete"`; an `early` finish leaves it `in_progress` so a
  partial stop earns no achievement credit. WP-12 revalidates achievement counts.
  Producer: WP-02. Consumers: WP-05, WP-09, WP-11, WP-12.
* Claude Design remains the selected UI authority and remains uninspected; see
  [DELIVERY-PHASES.md](DELIVERY-PHASES.md).

## Package completion template

```text
Package and milestone (functional / visual / final):
Baseline / tested revision:
Owned files changed:
Shared-file patches integrated by:
Interfaces added/changed:
Acceptance cases demonstrated:
Commands and actual results:
Visual/native evidence:
Known gaps and blockers:
Rollback/data compatibility:
Downstream packages now unblocked:
```

## 2026-09-07 (evening) — next packages dispatched

Plan: [NEXT-WORK-PACKAGES-2026-09-07.md](NEXT-WORK-PACKAGES-2026-09-07.md). D-0 assumed as recommended (journey = daily Séance, legacy loop = «Plus de pratique») pending the owner's word.

| Package | Agent | Lease | Started |
|---|---|---|---|
| WP-15 | integration (Opus) | commits of the Codex working tree; `web-frontend/package.json` scripts, `.github/workflows/ci.yml`, `render.yaml`, `scripts/pilot_digest.py` | 2026-09-07 evening |
| WP-17 (14G) | story-engine (Opus) | `app/services/living_story.py`, its prompts, `scripts/longitudinal_story_review.py`, `scripts/review_living_story.py`, `tests/test_living_story*.py`; additive pilot-event cost rows. No paid calls. | 2026-09-07 evening |
| WP-19 | native (Opus) | `web-frontend/ios/App/App/**` (source), `project.pbxproj`, xcconfig, fastlane, `lib/native-push.ts`, notification services + tests, `docs/mobile-visual-checks/2026-09-07-wp19/` | 2026-09-07 evening |
| Codex | Séance rework | `app/services/atelier.py`, `grammar_feedback.py`, `seance_curriculum.py`, `pages/atelier.tsx` legacy branch | ongoing |

WP-16 starts after WP-15 lands; WP-21 after one of the three above finishes. Max three concurrent agents.

## 2026-09-07 — WP-15

Landed the Codex Séance rework and wired it into the checks. No production flag
changed; no server was started or restarted by this package.

### Commits

| Commit | Contents |
|---|---|
| `3cc56b5` | Curriculum + backend grading: `app/api/v1/endpoints/atelier.py`, `app/config.py`, `app/services/atelier.py`, `app/services/grammar_feedback.py`, `app/services/seance_curriculum.py`, `app/data/seance_challenges.txt`, `tests/test_atelier.py`, `tests/test_atelier_quality_srs.py`, `tests/test_seance_contract.py` |
| `904e856` | Frontend + docs: `web-frontend/pages/atelier.tsx`, `web-frontend/styles/atelier-v2.css`, `web-frontend/lib/seance-feedback.ts`, `web-frontend/lib/seance-feedback.test.js`, `tests/test_frontend_atelier_word_bank.py`, SEANCE-REWORK-2026-09-07, STABILIZATION-2026-09-06, NEXT-WORK-PACKAGES-2026-09-07 |
| _(this commit)_ | CI wiring (`web-frontend/package.json`, `.github/workflows/ci.yml`), `render.yaml` correction-model block, this section |

`tests/test_frontend_atelier_word_bank.py` is a source-scanning test pinned to
`pages/atelier.tsx`, so it travels with the frontend commit rather than the
backend one; splitting it the other way would have left `3cc56b5` red on its own.

Not touched, because they belong to the concurrent WP-17 and WP-19 agents:
`app/services/living_story.py`, `web-frontend/ios/**`, `web-frontend/ios/.gitignore`.

### Commands and actual results

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_seance_contract.py tests/test_atelier.py tests/test_atelier_quality_srs.py tests/test_frontend_atelier_word_bank.py` | `168 passed in 47.62s`, exit 0 |
| `node --test lib/seance-feedback.test.js` (web-frontend) | `# pass 1 # fail 0`, exit 0 |
| `npm run type-check` | exit 0, no output |
| `npm run lint` | `✔ No ESLint warnings or errors` |
| `npm run test:seance` (new script) | `# pass 1 # fail 0`, exit 0 |
| `python -c "yaml.safe_load(open('render.yaml'))"` | parses; both `atelier-api` and `atelier-worker` carry the four `ATELIER_CORRECTION_LLM_*` keys |

### Deploy manifest

`render.yaml` now sets `ATELIER_CORRECTION_LLM_MODEL=gpt-5-mini`,
`ATELIER_CORRECTION_LLM_MAX_TOKENS=5000`,
`ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS=60` and
`ATELIER_CORRECTION_LLM_REASONING_EFFORT=low` explicitly on both backend
services, instead of inheriting them from `app/config.py`. The cost change is
therefore visible in the blueprint and reversible without a code deploy.

### Gap: the Atelier correction call has no cost telemetry — TODO for WP-16

WP-15 §3 asked for a correction line item in `scripts/pilot_digest.py`. **It
cannot be written honestly today, so nothing was added to the digest.** The
data does not exist:

- `PilotEventService.record(..., cost_usd=...)` is the only cost source the
  digest reads for LLM spend (`pilot_events.py:125`, into `other_llm_usd`).
- `app/api/v1/endpoints/atelier.py` records `plan_started`, `plan_adjusted`,
  `plan_completed`, `erratum_repair` and one more event — **none** on the
  correction path, and every one with the default `cost_usd=0.0`.
- `AtelierCorrectionService`'s LLM call in `app/services/atelier.py` keeps no
  usage metadata at all: no token counts, no model cost, nothing persisted.
- `AtelierGenerationEvent` (the other Atelier log) has `model` and `payload`
  but no cost or token columns, so it cannot stand in either.

A digest line would have printed `$0.0000` for every learner while the real
per-submit cost just rose from gpt-5-nano/900 tokens to gpt-5-mini/5,000 tokens
on the most-used endpoint. That is worse than no line.

The fix belongs at the correction call site in `app/services/atelier.py`, which
is under the Codex lease for this package, so WP-15 did not edit it.

**TODO (WP-16, or WP-17 §5 if it lands the ledger first):** capture the OpenAI
usage metadata already returned by the correction call, price it, and write one
`PilotEvent` per correction with `event_type="atelier_correction"` and a real
`cost_usd`; then add the line item to `format_daily_digest`. Until that exists,
`PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD` does not cover Séance corrections.

### Other findings from the diff review

- `web-frontend/lib/seance-feedback.test.js` resolves `sucrase` through
  `require('../node_modules/sucrase/register/ts')`. `sucrase` is not a declared
  dependency; it is hoisted from `tailwindcss@3.4.18` and is only in the lock
  file transitively. CI's `npm ci` installs it today, but a Tailwind bump can
  break `test:seance` for a reason that has nothing to do with the Séance.
- `test:story-model` exists in `package.json` but is not in the CI node block
  (CI runs eight of the nine suites). Not fixed here — outside the WP-15 files.
- `_curated_payload` in `app/services/atelier.py` sets
  `show_correct = int(lesson['teaching_order']) % 20 == 0`, so the classify item
  reads "À corriger" for roughly 19 of every 20 lessons. Its own comment says
  classification "must not train the learner to click the same label every
  time"; at 1-in-20 it does exactly that. Codex-owned; flagged, not changed.
- `_compact_llm_answer` now sends the learner's answer with no length cap at
  all (previously 520 chars for text, 220 × 5 for keyed answers). Correct for
  full-paragraph assessment, but it makes request size learner-controlled on a
  paid endpoint with no ceiling. Worth a bound in WP-16.

### Owner action still open

Set `TTS_PROVIDER=openai` in `.env` and restart the backend on **port 8010**.
The agent did not edit `.env` and did not restart any server. Port 8000 belongs
to a different project and must not be touched.
| WP-16 | daily-experience (Opus) | `lib/atelier-next.ts`, `HomeScreen.tsx`, `daily_journey.py`/schemas (additive `practice_href`, `practice_targets`), journey recap components, WP-05 adapters for dedup, `pages/atelier.tsx` today-view query handling; narrow `# WP-16 additive` edits in `app/services/atelier.py` (correction cost event, answer bound) | 2026-09-07 evening, after WP-15 landed (`3cc56b5`, `904e856`, `ed8404f`) |
| WP-21 | content (Opus) | corrector/erratum/toast/badge copy via the native_language resolver, POS override file + audit script, Anki gloss backfill script (dry-run only) | 2026-09-07 evening, after WP-17 landed (`d6aa974`) |

## 2026-09-07 — WP-19

Native release readiness and the WP-10 lifecycle recheck, run by the
resilience/native agent. Everything below was executed on this machine today;
where a gate could not run, the concrete blocker is named instead of a claim.

### 1. Privacy manifest (ITMS-91053)

`web-frontend/ios/App/App/PrivacyInfo.xcprivacy`, registered in the Xcode project
(file reference + `Copy Bundle Resources`). Declares `NSPrivacyTracking=false`,
an empty `NSPrivacyTrackingDomains`, two required-reason API categories and five
collected data types.

The API categories were **audited, not guessed**. Capacitor 8.4.0 ships its own
`PrivacyInfo.xcprivacy` in `Capacitor.framework` and `Cordova.framework`, and
both declare `NSPrivacyAccessedAPITypes` as an empty array. A grep of the iOS
sources of the three linked plugins (`@capacitor/haptics` 8.0.2,
`@capacitor/push-notifications` 8.1.2, `capacitor-secure-storage-plugin` 0.13.0)
plus `nm` over the built `Capacitor.framework`, `Cordova.framework`,
`CapApp-SPM.o`, `SecureStoragePlugin.o` and `SwiftKeychainWrapper.o` found **no**
`UserDefaults`, `systemUptime`, `mach_absolute_time`, `getattrlist`, `statfs`,
`volumeAvailableCapacity*` or `NSFileModificationDate` symbols. So:

- Declared `NSPrivacyAccessedAPICategoryFileTimestamp` (C617.1) — Capacitor's
  `WebViewAssetHandler.swift:61` reads `resourceValues(forKeys: [.fileSizeKey])`
  on the bundled web assets, which goes through the file-metadata syscalls Apple
  groups under this category.
- Declared `NSPrivacyAccessedAPICategoryUserDefaults` (CA92.1) — the bridge and
  WKWebView shell read preferences belonging to this app only.
- **Not** declared: system boot time (35F9.1), disk space (E174.1), active
  keyboards (54BD.1). Nothing this app links uses them. The manifest carries the
  audit as a comment so a future ITMS-91053 bounce can add the named category
  with its reason instead of re-guessing.

Collected data types match what the backend actually stores: email address,
other user content (written French), audio data (uploaded for transcription, not
retained), other usage data (SRS/streaks/journey evidence/pilot events,
`AppFunctionality` + `Analytics`) and crash data (`client_crash`). All linked to
identity, none used for tracking.

**Verified in a real bundle**, not just on disk: a simulator build produced
`App.app/PrivacyInfo.xcprivacy` (947 bytes after plist compilation) and
`plutil -p` on the shipped copy shows all seven entries.

### 2. Signing without a committed team id

- `web-frontend/ios/App/Debug.xcconfig` — `#include "../debug.xcconfig"` (keeps
  Capacitor's `CAPACITOR_DEBUG`) + `#include? "Signing.xcconfig"`.
- `web-frontend/ios/App/Release.xcconfig` — `#include? "Signing.xcconfig"`.
- `web-frontend/ios/App/Signing.example.xcconfig` — committed template.
- `web-frontend/ios/App/Signing.xcconfig` — **gitignored**
  (`web-frontend/ios/.gitignore`), written by `fastlane ios archive` from
  `FEUILLETON_DEVELOPMENT_TEAM` / `APPLE_TEAM_ID` / `DEVELOPMENT_TEAM`.
- The App target's Debug and Release configurations now use these as their
  `baseConfigurationReference`.

Verified with `xcodebuild -showBuildSettings`:

| State | `DEVELOPMENT_TEAM` | `CAPACITOR_DEBUG` (Debug) |
|---|---|---|
| no `Signing.xcconfig` | absent | `true` |
| placeholder `Signing.xcconfig` | `ABCDE12345` | `true` |

`git status` never reports `ios/App/Signing.xcconfig`. With no team id at all the
lane refuses with a named message rather than producing an unsigned archive:
`No signing team. Export APPLE_TEAM_ID (or FEUILLETON_DEVELOPMENT_TEAM)…`.

Two bugs in the existing archive lane were fixed while proving this out:

1. `write_signing_xcconfig` first failed with `Errno::ENOENT … ios/App/Signing.xcconfig`
   because fastlane runs lanes with `fastlane/` as the working directory. Now
   resolved from `__dir__`.
2. `increment_build_number` uses `agvtool`, which also rewrites
   `App/Info.plist`, replacing `$(CURRENT_PROJECT_VERSION)` with a literal and
   leaving a dirty working tree after every archive (it did exactly that here;
   the file was restored by hand, since this checkout is shared with Codex and
   `git checkout` is forbidden). The lane now passes
   `xcargs: "CURRENT_PROJECT_VERSION=#{build_number}"` to `build_app` instead. A
   second archive run afterwards left `Info.plist` and `project.pbxproj` clean.

### 3. AppIcon set

Seventeen sizes generated with `sips` from the existing
`AppIcon-512@2x.png` (1024×1024, RGB, no alpha), plus the marketing icon:
20/29/40/60 pt at @2x/@3x for iPhone, 20/29/40/76 pt at @1x/@2x and 83.5 pt @2x
for iPad, 1024 for `ios-marketing`. `Contents.json` rewritten to the per-idiom
form; every referenced file exists and every output is alpha-free. The compiled
bundle carries `Assets.car` plus the extracted `AppIcon60x60@2x.png` /
`AppIcon76x76@2x~ipad.png`, and `Info.plist` in the bundle now has
`CFBundleIcons` and `CFBundleIcons~ipad` with `CFBundleIconName = AppIcon`.

### 4. Crash reporting — first-party, and now proven by a test

The path is `pages/_app.tsx` (`window.addEventListener('error' | 'unhandledrejection')`
→ `apiService.recordClientError`) → `POST /api/v1/analytics/client-error`
(`app/api/v1/endpoints/analytics.py:128`) → `PilotEventService.record("client_crash")`,
counted in `_FAILURE_EVENT_TYPES` and surfaced by `daily_rollup`. Nothing tested
the endpoint end to end before; `tests/test_wp19_notifications.py` now asserts
401 without auth, 204 with auth, and that the event appears as
`client_crash: 1` in the pilot daily ledger for that learner with
`totals.failures >= 1`.

**Recommendation: keep first-party, do not add Sentry yet.** The pilot has zero
learners. Sentry would add a third-party SDK to the privacy manifest and the App
Store data disclosure, a paid dependency, and a second place to look for the
same information, in exchange for symbolication and breadcrumbs that only matter
once real crashes arrive from devices we do not hold. The one thing the
first-party path cannot see is a native crash that kills the WebView before the
JS handler runs; that is a real gap, and the honest trigger for revisiting is the
first WP-22 learner reporting a hang or silent quit that no `client_crash` row
explains.

### 5. Daily-journey morning push

`app/services/serial_notifications.py` gains `DAILY_JOURNEY_MORNING_TITLE`
(`"Votre scène du jour est prête"`) and `daily_journey_morning_copy(db, user, today=…)`.
It returns `None` for anyone `journey_enabled_for()` rejects — so the flag and
the cohort list stay the single gate — and also for a learner whose journey for
that local date is already `completed`/`ended_early`, because "your scene is
ready" after the fact would be a lie. When a `preparing`/`active`/`paused`
journey exists, the body offers to resume with the journey's real budget.

Scheduling reuses the existing serial scheduler rather than adding one:
`app/tasks/notifications.py::_morning_copy` (called by the celery-beat task
`send_morning_editions`, which already dedupes per learner-day through the
`morning_edition_sent` pilot event and already sends
`data={"route": "/atelier", …}`) delegates to the new helper first and falls
through to the legacy edition copy for everyone else. That is a four-line call
site in a file outside the WP-19 lease; it is the only edit made there and it is
flagged here.

`tests/test_wp19_notifications.py` — 10 tests, all passing: flag off, outside
cohort, in cohort, resume copy carries the real budget ("5 minutes"), silence
after today's scene is finished, yesterday's finished scene does not silence
today, the scheduler picks the journey title for a cohort learner, and the
legacy "édition" title survives for everyone else.

### 6. Simulator lifecycle walk (WP-10 recheck)

Setup: throwaway fake-provider backend (`scripts/dev_story_engine_server.py`) on
**port 8011** against the throwaway Postgres `atelier_story_pg_1788716642`, with
`ATELIER_DAILY_JOURNEY_ENABLED=true` for that process only; nothing in `.env`,
`render.yaml` or port 8010/8000 was touched. Native bundle built with
`ALLOW_LOCAL_NATIVE_API=true NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8011/api/v1
NEXT_PUBLIC_NATIVE_PUSH_ENABLED=true npm run cap:sync:ios`, then
`xcodebuild … -destination id=<iPhone 16> CODE_SIGN_IDENTITY="-"`. Device:
**iPhone 16, iOS 26.0.1, 393 × 852 pt** (the 390 pt iPhone 13/14 profile is not
installed; 393 pt is the nearest available and is recorded as such).

Screenshots in `docs/mobile-visual-checks/2026-09-07-wp19/`:

| # | File | What it shows |
|---|---|---|
| 01 | `01-signed-in-journey-home.png` | signed in, V2 journey offered ("Your next chapter", 5 min) |
| 02 | `02-resume-exact-activity-after-kill.png` | kill + relaunch → exact activity, session persisted |
| 03 | `03-offline-cold-start-cached-edition.png` | backend down, cold start → cached edition renders |
| 04 | `04-offline-honest-state-and-retry.png` | "HORS LIGNE … Vérifiez la connexion puis réessayez" + Réessayer |
| 05 | `05-large-text-accessibility-large-no-effect.png` | Dynamic Type at `accessibility-large` |
| 06 | `06-kill-after-attempt-no-duplicate-credit.png` | kill after an accepted attempt → still 1/8, same step |
| 07 | `07-home-honest-resume-state.png` | home shows journey + "Unfinished practice session … kept separately" |
| 08 | `08-v2-journey-scene-reader.png` | V2 living-story scene, step 1 of 3 |
| 09 | `09-draft-typed-and-pending-banner.png` | draft typed; "Something you did has not reached the server yet" |
| 10 | `10-draft-preserved-after-kill-mid-draft.png` | after kill, the draft comes back verbatim at step 2 of 3 |
| 11 | `11-software-keyboard-does-not-cover-response-or-send.png` | software keyboard open, field **and** Send both visible |
| 12 | `12-mic-denied-respond-step-text-only.png` | microphone denied, respond step fully usable |

WP-10 acceptance lines:

| Acceptance line | Result |
|---|---|
| Kill after an accepted attempt, before receipt → correct step, no duplicate credit | **PASS** (06: 1/8 before and after, same "Classer" step) |
| Kill mid-draft preserves text | **PASS** (10: draft returned verbatim, step 2 of 3) |
| Airplane-mode cold start shows an owned cached scene | **PASS in substance** (03/04). Exercised by taking the backend down, not by toggling iOS airplane mode, which `simctl` cannot do; the app's own state is "hors ligne" either way |
| Native keyboard does not cover the response/action | **PASS** (11) |
| Permission denial offers text without resetting the task | **PARTIAL** (12): with `simctl privacy … deny microphone`, the V2 respond step is text-only and unaffected. The dedicated voice surface (Studio / `audio-session`) was **not** exercised |
| Another account sees none of the previous account's content | **NOT RUN** — one account only |
| Expired auth refresh does not cause a second attempt | **NOT RUN** — needs a short-lived token build |

Observations worth a defect line for WP-20:

- **D-1 (resume target).** Cold start after a kill inside the V2 journey landed
  on the **legacy** Séance, not the V2 scene, three times out of three. Nothing
  is lost — the home surfaces both, honestly labelled, and one tap returns to the
  scene with the draft intact — but `readResumeActivity()` prefers the older
  practice session over the active journey.
- **D-2 (Dynamic Type).** `simctl ui … content_size accessibility-large` produced
  no visible change (05): the WKWebView does not follow iOS Dynamic Type. The
  "large text" gate as written cannot be exercised through the OS setting; it
  needs an in-app text-size control or `-webkit-text-size-adjust` work.
- **D-3 (header safe area).** In the V2 journey the sticky progress header draws
  under the status bar and overlaps the clock (08, 11). Cosmetic, reproducible.
- Not a defect: a horizontal scroll offset seen once on the Séance after keyboard
  interaction did not reproduce after relaunch, so it is not reported as overflow.

### 7. Commands actually run

| Command | Result |
|---|---|
| `npm run type-check` | pass |
| `npm run lint` | pass — "No ESLint warnings or errors" |
| `npm run test:native-env` | 6/6 pass |
| `pytest tests/test_wp19_notifications.py tests/test_notifications.py tests/test_pilot_work_packages.py` | 28 passed |
| `pytest … test_journey_events.py` (earlier run) | 68 passed |
| `npm run cap:sync:ios` (local API) | pass — sync finished, 3 plugins |
| `xcodebuild … -destination id=<iPhone 16> build` | **BUILD SUCCEEDED** |
| `bundle install` | pass (created `web-frontend/Gemfile.lock`, fastlane 2.230.0) |
| `bundle exec fastlane ios archive` | **FAILS — blocked, not a code defect** |

Mid-session note: `npm run cap:sync:ios` failed once on
`lib/atelier-next.ts(111)` `practice_targets` vs `practiced_targets`, a
concurrent agent's in-flight edit outside this lease. It was not touched; the
build was re-run after that agent's tree settled and passed.

### 8. The one gate that cannot pass here

`bundle exec fastlane ios archive` reaches code signing and stops at:

```
error: No profiles for 'com.pixellab.feuilleton' were found: Xcode couldn't find
any iOS App Development provisioning profiles matching 'com.pixellab.feuilleton'.
```

`security find-identity -v -p codesigning` lists exactly one identity on this
machine (`gdb-certificate`) and `~/Library/MobileDevice/Provisioning Profiles/`
is empty. There is no Apple Developer team enrolled here, so no App Store
archive can be produced, with or without the new xcconfig. This is the same
owner action the TestFlight checklist already carries (Apple enrollment and the
App Store Connect app record). Everything the repository controls is verified:
the project loads, the Release configuration resolves `DEVELOPMENT_TEAM` from
the gitignored xcconfig, the lane refuses cleanly without a team, the app
compiles and links, and the privacy manifest and full icon set land in the
bundle. The WP-19 acceptance line "`bundle exec fastlane ios archive` succeeds
locally" stays **pending on Apple enrollment**, and the two WP-10 lines above
stay pending on a second test account and a short-lived-token build.
| WP-18 (prep) | integration (Opus) | `ROLLOUT.md` (new), `scripts/verify_journey_drain.py`, `scripts/rollout_health.py`, `tests/test_rollout_scripts.py`; throwaway PostgreSQL only | 2026-09-07 evening, after WP-19 landed (`21dd85b`) |

WP-20 inherits from WP-19: D-1 cold start after a kill inside the V2 journey resumes the legacy Séance (`readResumeActivity()` prefers the older practice session); D-2 the WKWebView ignores iOS Dynamic Type; D-3 the V2 sticky progress header draws under the status bar.

## 2026-09-07 — WP-21

Language and data debt: the deterministic corrector, the Courrier's authored
erratum prose, the review card's visual-cue badge and the mic/transcription
toasts now follow the learner's `native_language`; the part-of-speech heuristic
is no longer the last word on what a word is; the Anki deck's missing English
column has a bounded, unrun backfill script.

**Owner:** content agent. No file owned by another lease was touched.

### 1. Localization

New resolvers, one per side:

- `app/services/learner_copy.py` — 41 keys × en/de/fr (123 strings). Keys, never
  English sentences, so a grep for English in learner-facing code stays
  meaningful; a missing column is a test failure, not a silent English fallback.
- `web-frontend/lib/atelier-v2-copy.ts` — 7 new chrome keys for the microphone
  and transcription failures, in all three tables.
- `web-frontend/lib/visual-cues.ts` (new) — the 14 scene cues plus the default,
  each with its shape, its matching signals and its label/caption in three
  languages.
- `web-frontend/lib/learner-language.ts` (new) — the three screens with no
  journey envelope (Le Lexique's deck, Le Courrier, Le Studio) resolve the
  learner's language from the cached profile, then from `GET /users/me/settings`,
  then `en`.

Routed through them:

| Surface | What was single-language |
| --- | --- |
| `app/core/error_detection/rules.py`, `detector.py` | 4 rule messages, 4 false-friend explanations, the default suggestion, both summaries — English only |
| `app/services/error_memory.py` | erratum labels, the "use X here" repair hint, the `why_wrong` fallback, the serialized last-resort labels — English only |
| `app/services/brief_exercise_service.py` | the fallback verdicts — hardcoded **German** ("Leider falsch", "Das passt zur Grammatikaufgabe") for every learner, plus one English repair hint |
| `app/services/missions.py` | the authored fallback erratum prose and both deterministic rules (`vous avet`, `probleme`) — English only |
| `pages/vocabulary/review.tsx`, `pages/missions.tsx`, `pages/audio-session.tsx` | mic / transcription failure toasts — French only |
| `pages/vocabulary/review.tsx` | the visual-cue badge labels — French only |

`DetectedError` gained `message_key`; the detector renders it in
`explanation_language`, which it now also resolves per call. Provider-authored
messages are untouched — the prompt already writes those in the learner's
language.

`tests/test_learner_copy_localization.py` (new) scans the six backend and three
frontend surfaces for a sentinel list of the exact strings that were shipped in
one language, ignoring comments, and checks that every copy row carries all three
languages with matching placeholders.
`tests/test_frontend_vocabulary_biography.py` re-pinned: the cue assertions moved
to `lib/visual-cues.ts` and now pin all three languages, plus a new test for the
deck's mic toasts. `tests/test_inline_moments.py` re-pinned: the brief-exercise
verdict is read from the table instead of asserting German.

**Remaining English:** `app/services/atelier_assets.py` still authors the
sentence-x-ray prose and the family contrast/trap lists in English (~60 strings).
They belong to the same table but sit behind `infer_grammar_profile`, whose
`GrammarProfile.label/principle/repair` live in `grammar_feedback.py` — held by
the Codex lease. Those two must move together, so they are deferred rather than
half-done. `pages/practice.tsx` and `pages/learn/session/[id].tsx` also carry
English toasts; both are on the WP-20 deletion list.

### 2. Part of speech

`app/services/vocabulary_coverage.inferred_part_of_speech` resolves in order:
curated override → a tagger's answer attached as `spacy_pos` → the deck's
`part_of_speech` column → the suffix heuristic (now split out as
`heuristic_part_of_speech`). `normalize_pos_tag` folds spaCy's tags, the deck's
spellings and the heuristic's into one vocabulary. A missing or malformed
override file degrades to the old behaviour rather than blanking the card.

`scripts/audit_pos_heuristic.py` (new) measures the suffix rule against
`FRENCH_NLP_MODEL` and exits 0 with a message when spaCy is unavailable. Run on
the shipped deck (5062 French rows, `fr_core_news_sm`):

```
rows compared             : 2724
heuristic mismatches      : 664
heuristic mismatch rate   : 24.38%
confident comparisons     : 1112
confident mismatches      : 329  (these become overrides)
residual after overrides  : 335 (12.30%)
worst endings             : -ent:150, -ire:93, -ier:60, -tre:45, -ure:40, -ère:31
```

"Confident" means both readings — the word inside its example sentence and the
bare word — agree, *and* the correction is one the tagger is trustworthy on: a
verb→noun/function fix is accepted, a verb→adjective/adverb one on an -er/-ir
surface is refused, because French infinitives are exactly where
`fr_core_news_sm` fails (it calls `diminuer` an adverb and `prier` an adjective).

`app/data/pos_overrides.json` (new): 333 entries — 329 from the audit plus 27
hand-checked corrections in the script's `CURATED_CORRECTIONS` (the tagger's own
errors: `pratiquement`, `analyste`, `poète`, `été`; and the -ir/-aire nouns and
-ier adjectives that started this, `exemplaire`, `souvenir`, `plaisir`,
`avenir`, `dernier`, `premier`).

The WP's "< 2 % mismatch" acceptance line is **not** met and should not be: the
residual 12.3 % is where `fr_core_news_sm` and the suffix rule disagree and
neither is demonstrably right. Encoding the tagger's answer there would replace
one wrong label on the card with another. What is fixed is the set the card
demonstrably got wrong. Raising the covered share needs a better tagger
(`fr_core_news_md`/`_lg`) or a dictionary, not a wider trust radius.
`tests/test_pos_overrides.py` (new) pins the order, the known-wrong set, that
real verbs are untouched, and the degrade-to-heuristic path.

### 3. Anki English glosses — prepared, NOT run

`scripts/backfill_anki_glosses.py` (new), on `backfill_anki_examples.py`'s
pattern. Dry run is the default; `--live` refuses to start without both
`--max-rows` and `--max-cost-usd`; the cost ceiling is enforced between batches,
not at the end; only NULL/blank `english_translation` rows are selected and each
row is re-checked before the write, so nothing is ever overwritten; every written
row gets `[english_gloss_backfill: anki-gloss-backfill-v1; model=…; at=…]`
appended to `usage_notes`.

Dry run, 2026-09-07:

```
rows missing english_translation : 5394
  of those, Anki-imported        : 5388
  of those, with a German gloss  : 5389
rows this run would translate    : 5388
DRY RUN — nothing was called and nothing was written.
```

**No paid call was made.** The exact live command, for the owner, with the
ceiling to start on (one batch of 250 to price the run before committing to the
rest):

```
.venv/bin/python scripts/backfill_anki_glosses.py --live --max-rows 250 --max-cost-usd 2.00
```

Owner consent and the cost ceiling are recorded here; the full 5388 rows should
only be started after that first 250 has been read for quality and its actual
cost multiplied out.

### 4. Verification

```
$ .venv/bin/python -m pytest -q tests/test_frontend_vocabulary_biography.py tests/test_missions.py \
    tests/test_error_detection_rules.py tests/test_error_detector.py tests/test_vocabulary.py \
    tests/test_vocabulary_coverage_conjugation.py tests/test_vocabulary_credit.py \
    tests/test_vocabulary_enrichment.py tests/test_vocabulary_handoffs.py \
    tests/test_learner_copy_localization.py tests/test_pos_overrides.py \
    tests/test_backfill_anki_glosses.py tests/test_inline_moments.py
191 passed

$ .venv/bin/ruff check app scripts tests
Found 4 errors.   # all pre-existing, in files under other leases:
                  # app/services/atelier.py, app/services/daily_journey.py,
                  # tests/test_wp16_correction_telemetry.py, tests/test_wp16_one_evidence_source.py

$ cd web-frontend && npm run type-check      # clean
$ cd web-frontend && npm run lint            # ✔ No ESLint warnings or errors
```

Not caused by this package, seen while running the wider suite and left for the
owner of `app/services/atelier.py`: `test_atelier.py::test_select_atelier_vocabulary_uses_curated_starter_for_new_user`
and three `test_progress.py::test_vocabulary_recommendations_*` fail on the
starter-vocabulary selection returning `mot0`/`maison` instead of the seeded
words. That code is inside the Codex lease and was not touched here.

### Files changed

Backend: `app/services/learner_copy.py` (new), `app/data/pos_overrides.json`
(new), `app/core/error_detection/rules.py`, `app/core/error_detection/detector.py`,
`app/services/error_memory.py`, `app/services/brief_exercise_service.py`,
`app/services/missions.py`, `app/services/vocabulary_coverage.py`.
Scripts: `scripts/audit_pos_heuristic.py` (new), `scripts/backfill_anki_glosses.py` (new).
Frontend: `web-frontend/lib/visual-cues.ts` (new), `web-frontend/lib/learner-language.ts` (new),
`web-frontend/lib/atelier-v2-copy.ts`, `web-frontend/pages/vocabulary/review.tsx`,
`web-frontend/pages/missions.tsx`, `web-frontend/pages/audio-session.tsx`.
Tests: `tests/test_learner_copy_localization.py` (new), `tests/test_pos_overrides.py` (new),
`tests/test_backfill_anki_glosses.py` (new), `tests/test_frontend_vocabulary_biography.py`,
`tests/test_inline_moments.py`.

## 2026-09-07 — WP-18 preparation

The enablement half of WP-18: runbook, drain proof, health tooling. **No flag was
flipped, no server on 8010/8000 was touched, nothing was deployed, `.env` and
`render.yaml` were not edited.** All work ran against a throwaway PostgreSQL 15
database (`atelier_wp18_1788800834`, migrated to head `a3b4c5d6e7f8`, dropped
at the end) with `scripts/dev_story_engine_server.py`'s fake provider, so no
paid call was possible.

### What exists now

| File | What it is |
|---|---|
| `docs/implementation/atelier-v2/ROLLOUT.md` | The WP-13 §6 runbook: prerequisites, the eleven env keys with safe defaults and pilot values, the cohort procedure (owner first, then the five study accounts), health and cost queries, the weekly guardrail, the drain, the kill-switch order, who flips what, and the gates that cannot close here |
| `scripts/verify_journey_drain.py` | Drives the whole flag cycle over real HTTP: it starts, stops and restarts the dev server with `ATELIER_DAILY_JOURNEY_ENABLED` on → off → on (a settings object is built once per process, exactly like a Render env-var change), and reads the canonical rows back. Prints a table, exits non-zero on any failure, refuses the owner's database and ports 8000/8010 |
| `scripts/rollout_health.py` | The seven runbook queries (`journeys`, `states`, `conflicts`, `engine_cost`, `engine_ledger`, `correction_cost`, `weekly_guardrail`) against an explicit `--database-url` with `--since`, `--user`, `--guardrail`, `--json`. Read-only; refuses a local `language_learning` and requires `--allow-production-name` for the remote pilot database, which carries the same name |
| `tests/test_rollout_scripts.py` | 19 tests: the database guards (local always refused, remote needs the opt-in), the query set (every query bounded by `:since`, narrowable by `:email`, free of write verbs, reading the same cost source as the guardrail), table rendering, the drain driver's port and database refusals through the real CLI, and its report/exit-code behaviour |

### Commands actually run

| Command | Result |
|---|---|
| `createdb atelier_wp18_1788800834` + `alembic upgrade head` | head `a3b4c5d6e7f8` |
| `.venv/bin/python scripts/verify_journey_drain.py --database-url postgresql://localhost/atelier_wp18_1788800834` | **34/34 checks passed**, exit 0 (full table in ROLLOUT.md §7) |
| `.venv/bin/python scripts/rollout_health.py --database-url … --since 2026-09-01` | all seven sections printed, exit 0 (output in ROLLOUT.md §4) |
| `WP18_HEALTH_DATABASE_URL=… .venv/bin/pytest tests/test_rollout_scripts.py` | `19 passed in 0.66s` — including the opt-in section that executes every health query against real PostgreSQL |
| `.venv/bin/ruff check scripts tests/test_rollout_scripts.py` | `All checks passed!` |
| `dropdb atelier_wp18_1788800834` | done |

The drain run was made on the working tree, which at that moment contained the
in-flight WP-16 and WP-21 edits of the two concurrent agents.

### What the drain proves

Flag on, cohort of one: the cohort learner starts a journey and advances a step;
a learner outside the cohort gets `enabled: false` and a 403 `journey_disabled`.
Flag off: that learner still reads the journey and its engine scene, saves a
reading position, answers the respond step, finishes with a story outcome and one
completed learning session, while a new create **and** a retry are refused 403
`journey_disabled` with the documented message, and no row is deleted or
downgraded; the outside-cohort learner's `/atelier/today`,
`POST /atelier/sessions` and `/atelier/sessions/active` return the identical
session, concepts and exercise sets as before the flip. Flag back on, next
learner-local day (simulated by dating day 1's rows one day back): the same
serial thread, episode 2 of the same thread with day 1 completed, and the new
scene's `source_event_ids` pointing at day 1's story event.

It does not prove model behaviour (fake provider), the frontend, or concurrency —
the lock races remain `scripts/verify_story_engine_pg.py` (33/33, 2026-09-06).

### Owner-only steps that remain

1. **Render deploy.** The backend has still never been deployed. Owner runs the
   blueprint; an agent can then check `/health`, `/ready`, that migrations
   reached `a3b4c5d6e7f8`, and the first `scripts/pilot_digest.py --day …`.
2. **The cohort flip**, in the ROLLOUT.md §3 order: `ATELIER_DAILY_JOURNEY_ENABLED=true`
   with `ATELIER_DAILY_JOURNEY_COHORT` = the owner's account **alone** on both
   Render services; the five study accounts only after one clean day. Never blank
   the cohort while the master switch is on — that opens the pilot to everyone.
3. **WP-16 must land first**, or a cohort learner is offered two daily Séances.
4. Still blocked elsewhere: Apple enrolment for the archive (WP-19 §8), the four
   fourteen-day paid engine runs (≈ US$0.60, owner consent), the five-learner
   study (WP-22), and WP-20's browser walk.

## 2026-09-07 — WP-16

Decision **D-0** taken as recommended: the V2 daily journey **is** the daily
Séance for cohort learners, and the legacy exercise Séance (Codex's 09-07
rework) becomes the explicit **«Plus de pratique»** drill activity, entered by a
grammar concept or by the errata queue and never by "today". No production flag
changed; no server on 8000 or 8010 was touched.

Everything below is inert while `ATELIER_DAILY_JOURNEY_ENABLED=false`: every new
branch is gated on the server's own `TodayEnvelope.enabled`, and a flag-off Home
renders exactly what it rendered before this package (screenshot 03).

### Changes

| Area | File | What |
|---|---|---|
| Routing | `web-frontend/lib/atelier-next.ts` | `resolvePracticeEntry`, `practiceHref`, `PRACTICE_LABEL`; `resolveLegacyRecommendedNext(…, { skipSession })`; with the capability on, `resolveRecommendedNext` drops the legacy Séance from the *primary* chain |
| Home | `components/atelier-v2/home/HomeScreen.tsx`, `styles/atelier-v2.css` | `HomeTile.secondary` — one quiet line under a tile, rendered as a **sibling** of the tile control (`av2-day-tile-cell` / `av2-day-tile__more`), never nested inside its button |
| Today view | `pages/atelier.tsx` | `practiceEntry` on the Séance tile; `journeyOwnsPrimary` suppresses La Une's own 3D-press action, because-clause, overrun clause and adjust link when the journey card is on screen; `?mode=practice&concept=` / `&queue=errata` entry; the «Plus de pratique» strip above `SessionView` |
| Envelope | `app/schemas/daily_journey.py`, `app/services/daily_journey.py` | `TodayEnvelope.practice_href` (defaulted, additive — `contract_version` unchanged) seated on the learner's most urgent due grammar concept; `PracticedTarget.practice_href` on every recap target |
| Recap | `components/atelier-v2/journey/JourneySession.tsx`, `journey-copy.ts` | `onPractice` + an inline `practice_this` control per practised target; the recap's `morePractice` button is finally wired from `pages/atelier.tsx` |
| Evidence | `app/services/journey_learning.py`, `grammar.py`, `vocabulary_credit.py` | `journey_credited_today` + `record_daily_practice_streak`; the drill loop no longer re-credits what the journey credited today; the journey now moves the streak |
| Cost + bound | `app/services/atelier_correction_cost.py` (new), `app/services/atelier.py` (+49 lines, every hunk `# WP-16 additive`), `scripts/pilot_digest.py` | one priced `PilotEvent("atelier_correction")` per real checker call; a 4,000-character bound on the learner answer, declared as `assessment_truncated`; a digest line item |
| Tests | `lib/atelier-next.test.js`, `tests/test_wp16_one_evidence_source.py`, `tests/test_wp16_correction_telemetry.py`, `tests/test_frontend_wp16_one_seance.py`, re-pins in `tests/test_atelier_honest_edition.py` and `tests/test_frontend_pilot_experience.py` | |

### Two deliberate deviations from the brief

1. **`practice_targets` vs `practiced_targets`.** The brief asked for a new
   `practice_targets` list on the recap. The recap already carries
   `practiced_targets`; a second, near-identical list would be two answers to
   one question. `practice_href` was added **to** `PracticedTarget` instead.
   `null` for a vocabulary target: the drill loop is keyed by a grammar concept
   or by the errata queue, and a bare word id is neither — a link there would
   open an unrelated drill set.
2. **`pages/atelier.tsx` was not split** (WP-16 §4 of the plan), as instructed:
   Codex must agree first. Proposal below.

### One evidence source — what was verified, and what was fixed

Verified by inspection and by `tests/test_wp16_one_evidence_source.py`: the
journey writes a real `LearningSession` and `SessionLearningMoment` rows through
the WP-05 adapters, which is where the legacy loop's own credit lands too.

Two things did **not** hold and are now fixed **in the WP-05 adapters, not in
`atelier.py`**:

* **Double credit.** `GrammarService.record_review` and
  `VocabularyCreditService.apply` — the two calls `AtelierService` makes at
  session completion — now consult `journey_learning.journey_credited_today` and
  keep the schedule the journey already set for that target **today**. A
  *failure* is never folded away: a real mistake reaches the schedule and the
  errata queue whenever it happens.
* **The streak.** The journey did not touch it at all, so a cohort learner who
  did only the journey had no streak. `finish` now calls
  `journey_learning.record_daily_practice_streak`, which is byte-for-byte the
  rule `AtelierService._update_streak` applies and is a no-op once the day is
  marked — so journey + drill loop on one day is **one** increment. Confirmed in
  the browser walk: "1 · 1ᵉʳ jour" after the journey alone (screenshot 06).

**Known gap, recorded rather than papered over:** the guard is one-directional.
It stops the drill loop from re-crediting what the journey credited today, which
is the D-0 order of play. The reverse (drill loop first, journey second) still
double-credits, because closing it needs a claim written from `atelier.py`'s own
call sites — a Codex-leased file this package did not edit. See "For Codex".

### For Codex — three items this package did not touch

1. **`_curated_payload`'s `show_correct`** is still
   `int(lesson['teaching_order']) % 20 == 0`, so the classify item reads
   "À corriger" for roughly 19 lessons in 20 — exactly the "same label every
   time" its own comment forbids. Flagged by WP-15, deliberately **not** changed
   here. It needs a distribution decision (a per-session coin flip, or alternating
   within the lesson's own items), which is Codex's to make.
2. **A same-day credit claim at the legacy call sites**, so the reverse
   direction of the dedup above closes. The helper to call is
   `journey_learning.journey_credited_today` / a claim written next to it.
3. **`web-frontend/lib/seance-feedback.test.js`** resolves `sucrase` through
   `require('../node_modules/sucrase/register/ts')`. `sucrase` is not a declared
   dependency — it is hoisted transitively from `tailwindcss@3.4.18`. `npm ci`
   installs it today, but a Tailwind bump breaks `test:seance` for a reason that
   has nothing to do with the Séance. Declare it in `devDependencies`.

### Proposed split of `pages/atelier.tsx` (6,900 lines) — for Codex to agree

Three files, no behaviour change, in this order:

| New file | Contents | Owner |
|---|---|---|
| `components/atelier/JourneyShell.tsx` | the `view === 'journey'` branch, the `JourneyTodayCard` entry, `useDailyJourney` wiring, `practiceEntry` | Claude sessions |
| `components/atelier/TodayView.tsx` | `TodayView` and its La Une mapping helpers (already one self-contained component) | Claude sessions |
| `pages/atelier.tsx` | the page shell, the legacy `SessionView` state machine and every attempt handler | Codex |

The source-scanning backend tests pinned to `pages/atelier.tsx`
(`test_frontend_atelier_word_bank`, `test_atelier_honest_edition`,
`test_frontend_pilot_experience`, `test_core_mobile_*`, `test_frontend_wp16_one_seance`)
must be re-pointed in the same change, or the split lands red.

### Commands and actual results

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_daily_journey_api.py tests/test_journey_contract_parity.py tests/test_journey_learning.py tests/test_atelier.py tests/test_progress.py tests/test_frontend_*.py tests/test_core_mobile_*.py tests/test_atelier_*.py tests/test_wp16_*.py` | `1 failed, 374 passed in 59.03s` — the one failure is `test_audio_call_states_never_lie_or_dead_end`, which **fails identically on committed HEAD** (verified in a `git worktree` at `0f39b7e`) |
| `.venv/bin/python -m pytest -q -p no:randomly` (whole suite) | one failure, the same pre-existing one. The same command at HEAD fails **four** tests (`test_frontend_pilot_experience`, both `test_grammar_notebook` cases, `test_vocabulary_due_context_rejects_invalid_direction`) — this suite is order-fragile independently of WP-16 |
| `npm run type-check` | exit 0, no output |
| `npm run lint` | `✔ No ESLint warnings or errors` |
| `npm run test:atelier-next` | `atelier-next resolver tests passed` |
| `npm run test:journey` | `daily journey frontend tests passed` |
| `npm run test:atelier-ui` | `atelier v2 design system tests passed` |
| `npm run test:seance` | `# pass 1 # fail 0` |
| `npm run build` | succeeded; route table unchanged |

**Pre-existing failure, not WP-16's:** `test_audio_call_states_never_lie_or_dead_end`
asserts `"Autorisez-le dans les réglages du navigateur"` in
`pages/audio-session.tsx`. WP-21's copy localisation (`0a863b5`) moved that
string into the copy table without re-pinning the test. It is WP-21's to fix;
this package did not touch that file.

### Browser walk — fake-provider harness, throwaway PostgreSQL

Throwaway `atelier_wp16_*` database (`createdb` + `alembic upgrade head`, dropped
afterwards), `scripts/dev_story_engine_server.py` on **port 8027**, a dev
frontend on **3021**. Ports 8000 and 8010 untouched; no paid call was made.
Screenshots in `docs/mobile-visual-checks/2026-09-07-wp16/` (390 pt, dark):

| Shot | What it shows |
|---|---|
| `01-home-one-primary-action-journey.png` | flag on: **one** 3D-press action, the journey's «Commencer». La Une draws none of its own. Séance tile reads "1 règle · exercices" with «Plus de pratique» under it |
| `02-plus-de-pratique-opens-the-drill-loop.png` | `/atelier?mode=practice&concept=1` → the «Plus de pratique» strip naming *Genre et nombre : les bases*, over Codex's drill loop seated on that concept |
| `03-flag-off-home-unchanged.png` | flag off: the legacy «Continuer» primary, the because-clause, the overrun clause and «Ajuster le temps de l'édition» all back; no journey card and no «Plus de pratique» |
| `04-recap-points-into-the-drill-loop.png` | the finished recap: «Retravailler» inline on the practised target, plus «Plus de pratique» as the secondary action |
| `05-recap-pointer-opens-the-concept-drill.png` | that pointer followed — the drill loop on concept 1 |
| `06-home-after-the-journey-legacy-stays-secondary.png` | after finishing: "La scène du jour est terminée", streak **1 · 1ᵉʳ jour** (the journey moved it), the old legacy session offered separately as "Séance précédente non terminée", «Plus de pratique» still only a secondary line |

Live envelope from that server:
`practice_href = /atelier?mode=practice&concept=1`; recap
`practiced_targets[0].practice_href = /atelier?mode=practice&concept=1`.

A bug the unit tests missed and the walk caught: `_practice_href` read `.id` off
`GrammarService.get_due_concepts`' `(concept, progress)` **tuple** and silently
produced the bare `/atelier?mode=practice`. Fixed, with a regression test.

### Remaining for acceptance

* The `pages/atelier.tsx` split (plan §4) — needs Codex's agreement.
* The reverse dedup direction (drill loop first, journey second) — needs a claim
  at `atelier.py`'s call sites.
* Correction-policy convergence (plan §3): Codex's "unassessed on provider
  failure" state is not yet the shared infrastructure-failure state for both
  loops. The journey already keeps infrastructure failure separate from a wrong
  answer (CONTRACTS §5); the two vocabularies have not been unified.
* The walk used the fake provider: it proves routing, the envelope, the recap
  pointer and the evidence path, never prose quality.

## Codex handoff resolution — 2026-09-07

The four WP-16 handoff items have been reviewed.

### Page split decision: agreed, with a controller-lifetime boundary

Proceed with the proposed three-file split, in this order: extract
`components/atelier/JourneyShell.tsx`, then
`components/atelier/TodayView.tsx` and its La Une mapping helpers; leave the
legacy SessionView state machine and all attempt handlers in
`pages/atelier.tsx`. The proposed ownership remains unchanged.

One refinement: keep `useDailyJourney` and the shared `practiceEntry` resolution
mounted unconditionally in the page, passing the controller and navigation
callbacks into JourneyShell and the entry card. Moving that hook into a
conditionally mounted journey branch would reset its lifecycle when returning
to Today. Extract shared types into a neutral module when needed; extracted
components must not import the page. Repoint the source-scanning tests listed
in the proposal to the appropriate owning component, preserving their behavior
assertions. No behavior change or routing change belongs in the extraction.

This closes the request for Codex's agreement. The extraction itself is a
separate implementation task for the proposed owners; it is not claimed as done.

### Classification distribution: fixed

Curated lessons alternate correct and incorrect authored sentences by stable
catalog position, giving 27 of each across 54 lessons. The teaching-order
number is no longer treated as a probability. The label always matches the
authored sentence/foil; repeat generation remains deterministic. Generator
version is now `atelier-v11`, invalidating the previously skewed cached sets.

### Drill-first credit: fixed

Successful vocabulary credit from the Atelier service and successful grammar
credit at legacy completion now record a claim in the canonical
LearningSession/SessionLearningMoment ledger. A single completed
`atelier_credit` learning session groups the day's drill claims, with zero
planned duration and no invented XP. Claim creation shares the credit
transaction, uses a deterministic user/day session identifier, and is
idempotent per target. No schema migration or separate ledger is introduced.

The journey retains its answer evidence but reports
`credited_in_drill_today` and does not advance SRS again for an already-claimed
target. Failed/unassessed drill work does not claim success; real failures in
either direction still reach SRS. Cross-surface schedule checks and writes take
the same user-row lock. Drill claims use UTC days, matching the legacy guard's
default clock; this does not introduce learner-timezone scheduling for legacy
practice. The guard no longer silently forgets credit after 200 newer moments.

### Sucrase: declared

`sucrase: ^3.35.0` is now a direct devDependency in both package manifests.
The existing lockfile already contains version 3.35.0 and its integrity hash;
that resolved dependency was preserved. The test loads
`sucrase/register/ts` by package name. An offline npm metadata refresh was
unavailable, so only the root dependency declaration was added to the existing
lockfile; `npm ls sucrase --depth=0` verifies the direct installed dependency.

### Verification

- 237 tests pass across Atelier, séance contract, journey learning, and WP-16
  evidence, including new reverse-order, expiry, idempotency, failure, and
  balanced-label regressions.
- Another 70 tests pass across vocabulary credit, grammar notebook, daily journey
  state, and WP-16 frontend contracts.
- Frontend `test:seance`, TypeScript checking, and ESLint pass.
- No paid provider call or deployment was needed for these fixes.

## 2026-09-07 — WP-20

Assembled V2 browser QA and the legacy-page disposition, run by the independent
QA agent (WP-12 final). Full report:
[QA-REPORT-WP20-2026-09-07.md](QA-REPORT-WP20-2026-09-07.md). No production flag
was changed, no paid call was made, and ports 8000 / 8010 and the owner's
`language_learning` database were not touched: the walk ran against
`scripts/dev_story_engine_server.py` (fake provider) on port 8031 over a
throwaway `atelier_wp20_*` PostgreSQL, with a dev frontend on 3031.

### The three WP-19 defects handed over

| | Status | What was done |
|---|---|---|
| **D-1** — a cold start after a kill resumed the legacy Séance, not the open journey | **Fixed** | New `web-frontend/lib/journey-resume.ts`: `useDailyJourney` writes a `pilot:journey-resume:v1` mark while the envelope is enabled and the journey is `preparing`/`active`/`paused`, and clears it otherwise; `resolveResumeHref()` prefers that mark and otherwise falls through to `readResumeActivity()` unchanged; `pages/_app.tsx` calls the resolver; `pages/atelier.tsx` gained a `?view=journey` entry (guarded on `journeyEnabled`, outside Codex's `SessionView` branch) so the redirect lands *inside* the scene. A finished, abandoned, foreign or >48 h-old journey never wins. `lib/journey-resume.test.js` — 11 cases — is wired into `package.json` and CI as `test:resume-target` |
| **D-2** — the WKWebView ignores iOS Dynamic Type | **Answered; no setting exists** | Capacitor 8.4.0's iOS config surface was read from `@capacitor/cli/dist/declarations.d.ts` and carries no text-size key; the only web mechanism is CSS, and `globals.css` pins the rem base (`:root[data-font-size]` 14.5/16/19 px, `-webkit-text-size-adjust: 100%`). The remediation WP-19 asked for already ships as Réglages → Apparence → «Corps du texte», exercised in this walk. Recorded, not invented. Recommendation for the native owner, **not applied**: `ios: { zoomEnabled: true }` — pinch-zoom is off by default, so with Dynamic Type ignored the in-app control is a learner's only text-size channel |
| **D-3** — the V2 sticky progress header drew under the status bar | **Fixed** | `.av2 .av2-session__head` now uses `padding: calc(12px + env(safe-area-inset-top, 0px)) …`, matching `Epreuve.tsx`'s `.ep-top`. Source parity only — the inset is `0px` in a browser, so the visual proof needs the WP-19 simulator run again |

### Legacy-page disposition

Deleted, with every inbound link, in one change: `pages/practice.tsx`,
`daily-practice.tsx`, `sessions.tsx`, `dashboard.tsx`, `stories.tsx`,
`pages/stories/**`, `pages/story/[id].tsx`, `achievements.tsx`, `almanac.tsx`,
`progress.tsx`, plus `components/AnkiSync.tsx`,
`components/ui/CollapsibleSection.tsx` and nine now-orphaned story components.
Links removed from `lib/product-shell.ts`, `components/layout/Layout.tsx` and
`pages/learn/session/[id].tsx`; `/progress`, `/achievements` and `/almanac`
gained redirect stubs in `next.config.js` so old bookmarks and push payloads do
not 404. **Every API was kept.**

Migrated onto the av2 system: the **Studio** (`pages/audio-session.tsx`, real
recap and correction states preserved) and the **Bibliothèque** (the three
`/bibliotheque/**` routes were one-line re-exports of the deleted `/stories`
reader and are now real pages, with eight `components/stories/**` components and
`UploadBookModal` rewritten). The **serial episode replay and cast** were found
already on the system (`047ae8e`) and verified rather than assumed.

`next build` route count: **44 → 33** (45 → 34 table rows including `/_app`) —
exactly the eleven deleted routes, nothing else moved.

One capability went with a deleted page and has no successor: the almanac's
panel-crop **story seals**. Le Relevé keeps the collectible ledger, not the art;
`test_frontend_serial_surfaces.py` now pins the ledger and says so.

### Browser walk

147 screenshots in `docs/mobile-visual-checks/2026-09-07-wp20/`: 105 route
captures (15 authenticated routes × 320/390/768 px, light and dark, large text at
390 and 320, reduced motion) and 42 flow captures playing the whole V2 journey —
scene reader, recall, respond, graded feedback, resolution, recap — plus the
Feuilleton page, its unknown-scene state and the Cahier, at three combinations.

**No horizontal overflow on 104 of 105 route captures**; QA-REPORT §D-6 (the
respond field clipped at 320 px with large text) did not reproduce. Keyboard
order follows DOM order and every av2 control draws the design's focus ring under
real key events.

Eleven new defects, D-4 … D-15 (D-8 filed then **withdrawn** — the missing focus
ring was a measurement artifact of `element.focus()`, which does not match
`:focus-visible`; anyone measuring focus rings here must dispatch real key
events). The substantive ones: two identical ✕ controls and two progress bars
stacked in the journey scene reader (D-4); the step header advancing to "Step 3
of 3" while step 2's feedback is still on screen (D-5); the answer field and its
three helpers staying live after the answer is graded (D-6); `Today · ` rendering
with a dangling separator on the day's primary card, because the engine's
`available` descriptor ships an empty `location_name` (D-7); the 36 × 36
neo-brutal feedback FAB now being the only off-system element left, and sitting
over the reader's action bar (D-9); 24 sub-44 px controls in Réglages from one
class, plus Cahier, Lexique, Missions and Home (D-10); and the grammar fiche
overflowing horizontally at 320 px with large text — the single overflow in the
whole matrix (D-15). All are handed to the daily-experience and frontend leads;
none were fixed here beyond the three WP-19 defects this package owned.

### Commands and actual results

| Command | Result |
|---|---|
| `npm run type-check` | exit 0, no diagnostics |
| `npm run lint` | `✔ No ESLint warnings or errors` |
| `npm run build` | exit 0; route table 45 → 34 rows |
| Eleven node suites (`atelier-next`, `journey`, `recovery`, `resume-target`, `atelier-ui`, `graphic-novel-images`, `reader`, `story-model`, `api-host`, `native-env`, `seance`) | all pass — `journey resume tests passed (11)`, `# pass 37 # fail 0`, `# pass 13 # fail 0`, `# pass 7 # fail 0`, `# pass 6 # fail 0`, `# pass 1 # fail 0` |
| `.venv/bin/python -m pytest tests/ -p no:randomly` | `1748 passed, 1 skipped in 253.70s (0:04:13)` |
| `.venv/bin/python -m pytest tests/` (random order) | `1750 passed, 1 skipped in 250.39s (0:04:10)` |
| `.venv/bin/ruff check .` | `All checks passed!` |

Source-scanning tests re-pinned rather than weakened:
`test_reachable_surfaces_carry_no_neo_brutalist_styling` now covers 17 surfaces
instead of 11; `test_achievements_have_no_manual_progress_gate` asserts the
promise across the whole frontend instead of one deleted file;
`test_story_reading_flow_is_parked_behind_launch_flag_without_deleting_contracts`
and `test_story_flow_handles_auth_fetch_locked_and_incomplete_chapter_edges` were
re-pointed at the migrated Bibliothèque with the new strings; two new tests
(`test_the_off_system_legacy_pages_are_gone`,
`test_no_frontend_surface_links_to_a_deleted_page`) keep the deletion honest.

### Still open

The WP-19 simulator walk must be re-run to prove D-1 and D-3 on a notched device
(the D-1 redirect only fires on `isNativePlatform()`, so the browser proof stops
at the mark and the `?view=journey` landing, both verified live). D-4 … D-15 are
unowned by this package. The learner gates are unchanged: WP-22's five-learner
study and the journey conversation's live-model review are still the last things
between the pilot and a real answer, and nothing in this walk says anything about
prose — it ran entirely on the fake provider.

## 2026-09-07 — end-of-day integration summary

All packages from [NEXT-WORK-PACKAGES-2026-09-07.md](NEXT-WORK-PACKAGES-2026-09-07.md) except WP-22 (learner study) and WP-23 (deferred) have landed on `codex/serial-season-engine-production`; only the owner-side steps remain.

| Commit | Package |
|---|---|
| `3cc56b5` `904e856` `ed8404f` `6440e0b` | WP-15 — Codex Séance rework committed, CI wiring, render.yaml correction block |
| `d6aa974` `98c4eb5` | WP-17 — variety guards, cost ledger, critic stages; paid-run follow-up |
| `21dd85b` | WP-19 — privacy manifest, signing xcconfig, icons, journey push, simulator walk |
| `0a863b5` `9191a6d` `114face` | WP-21 — learner-language copy, POS overrides, gloss backfill (+ starvation and language-scope fixes) |
| `0f39b7e` `db78d65` | WP-18 preparation — ROLLOUT.md, drain proof 34/34, health queries; production empty-cohort guard |
| `4b9bde6` `59237d3` | WP-16 — one daily Séance, practice mode, shared evidence + streak, correction cost telemetry |
| `7ee9178` | Codex follow-up — classify alternation, generator v11, drill-first credit lock |
| `c184ac4` | WP-20 — browser QA, resume-target fix, legacy-page disposition (44 → 33 routes) |

Paid runs with owner consent: four 14-day engine runs (US$0.45; A1 12/13 both modes, A2 6/13 with critic → 12/13 without; fixes in `98c4eb5`), one A2 run with `--critic turns` in progress, Anki gloss backfill (French deck, ≈US$0.02 per 250 rows).

**Owner-only steps:** `TTS_PROVIDER=openai` in `.env` + backend restart on 8010; Apple team enrolment (archive); first Render deploy and cohort flip per ROLLOUT.md (owner account alone first); decision on `CRITIC_STAGES` default after the turns-only run; WP-22 learner study.
**For Codex:** the `pages/atelier.tsx` split proposal (WP-16 section); `sucrase` undeclared in `lib/seance-feedback.test.js`; ~60 English x-ray/contrast strings in `atelier_assets.py` tied to `grammar_feedback.GrammarProfile` (WP-21 section).
**Open defects:** WP-20 D-4…D-15 in QA-REPORT-WP20-2026-09-07.md (none blocking).

**2026-09-07 late — gloss backfill executed (owner consent):** two live batches (`--max-rows 250` then `--max-rows 5000 --language fr`), 5,014 rows written, US$0.41 total, model gpt-5-mini, provenance `anki-gloss-backfill-v1` in `usage_notes`. Six French rows remain without a gloss (skipped by the model; inspect by hand). The first launch starved at 1,200 tokens without `reasoning_effort` (fixed in `9191a6d`); 14 rows of the separate German deck were glossed before the language scope landed (`114face`) — harmless.
