# Atelier V2 — execution status and file leases

Revision 2, functionality first, Claude UI.
**Execution started 2026-09-05.** Integration owner: lead implementation agent.
Baseline: [BASELINE.md](BASELINE.md). Frozen wire contract: [CONTRACT-FREEZE.md](CONTRACT-FREEZE.md).

| Package | Status | Owner | Baseline / revision | Evidence / blockers |
|---|---|---|---|---|
| WP-00 | **Complete** | Integration owner | worktree @ `367082` + uncommitted work | BASELINE.md, CONTRACT-FREEZE.md, `app/services/journey_contracts.py`, 26 public + 9 private fixtures. Baseline: pytest 593 passed / 1 pre-existing failure; tsc, lint, atelier-next pass |
| WP-01 | Blocked | Unassigned | — | Claude artifact still redirects to sign-in; not inspected. Does not block functional work |
| WP-02 | **Complete (functional)**, patches in flight | agent `wp02` | WP-00 baseline | 137 own tests; café journey proven end-to-end 44/44 vs real API; PG invariants verified by integration owner. Applying 8 review patches |
| WP-03 | **Complete (functional)** | agent `wp03` | WP-00 baseline | 50 tests pass; café/de/fr descriptors match frozen fixtures byte-for-byte (verified independently by `tests/test_journey_contract_parity.py`). Authored ceiling is A2 |
| WP-04 | **Complete (functional)** | agent `wp04` | WP-00 baseline | 62 tests; verified independently via the parity gate (100-due-word case, purity, determinism) |
| WP-05 | **Complete (functional)**, patch in flight | agent `wp05` | WP-00 baseline | 71 tests; SRS/audio regressions pass; canonical credit proven against PostgreSQL. Adding candidate evidence metadata for WP-04 |
| WP-06 | **Complete (functional)** | agent `wp06` | WP-00 baseline | 78 own tests; serial/audio/missions regressions 90 pass; outcome-schema escape and neutral-default verified by the parity gate |
| WP-07 functional | **Complete** | agent `wp07` + wiring agent | WP-00 baseline | Controller/renderer + WP-10 recovery wired; D-5/D-6/D-7 fixed and measured |
| WP-07 visual | Waiting for 01 | Unassigned | — | Pending in this pass |
| WP-08 | Waiting for 01 | Unassigned | — | Pending in this pass |
| WP-09 functional | **Complete** | agent `wp09` | WP-00 baseline | Rubric unified with the recap; keepsake source-unique |
| WP-09 visual | Waiting for 01 | Unassigned | — | Pending in this pass |
| WP-10 | **Complete** | agent `wp10` + wiring agent | WP-00 baseline | 35/35 live; wired into the real render path; respond-draft prune bug fixed |
| WP-11 | **Complete** | agent `wp11` | WP-00 baseline | Ten events, payload allow-list verified hostile; `active_seconds` now measured |
| WP-12 functional | **Complete — conditional GO met** | agent `wp12` | WP-00 baseline | NO-GO on 10 defects; D-1..D-7 fixed and re-verified. D-1b, live-model review, device/learner gates remain open |
| WP-12 final | Waiting for visual milestones | Unassigned | — | Not started; visual gates stay pending |
| WP-13 | Waiting for 12 final | Unassigned | — | No rollout authorized or executed |

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
