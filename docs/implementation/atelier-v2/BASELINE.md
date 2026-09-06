# Atelier V2 — WP-00 baseline

Recorded 2026-09-05 by the integration owner. This is the exact working state every
implementation agent builds on. **It is the current worktree, not `HEAD`.**

## Baseline identity

| Field | Value |
|---|---|
| Branch | `codex/serial-season-engine-production` |
| HEAD commit | `367082134d8894563fef5d73d2c980aac9d52b74` ("docs: record journal overhaul status") |
| Working tree | **dirty and authoritative**: 284 modified, 22 deleted, 78 untracked entries |
| Baseline snapshot | `git status --porcelain` output frozen in this document's sibling table below |

The uncommitted work is the product, not noise. It contains the pilot event ledger,
`app/services/daily_words.py`, `glosses.py`, `pilot_events.py`,
`recommendation_reasons.py`, three unmerged Alembic revisions, the
`web-frontend/lib/pilot-resilience.ts` resilience layer, native build scripts, and the
PNG→WebP serial asset migration (the 22 deleted `.png` files are **replaced** by the
matching untracked `.webp` files — that deletion is intentional).

**No agent may run `git reset`, `git checkout -- .`, `git clean`, or `git stash`.**
A checkout of `367082` alone is *not* this baseline.

### How each agent receives the baseline

All packages execute in this single shared checkout. Isolated worktrees were rejected
for this pass: `git worktree add` can only materialise committed history, and the
baseline is uncommitted, so an isolated checkout would silently drop the work above.
Concurrency safety therefore comes from the **exclusive file leases** in
[STATUS.md](STATUS.md), which the integration owner updates before dispatching.

## Environment

| Item | Value |
|---|---|
| Backend interpreter | `.venv/bin/python` — CPython 3.11.14 (system `python3` is 3.14 and is **not** the project interpreter) |
| Backend deps | already installed in `.venv` |
| Frontend | `web-frontend/`, Node/npm with `node_modules` present |
| Test DB | in-memory SQLite via `tests/conftest.py` (`StaticPool`) |
| Postgres | CI-only (`postgres:15`); no local instance is assumed |
| Backend dev port | 8010 — **port 8000 belongs to a different project, never bind or kill it** |
| Auth in tests | existing `tests/conftest.py` token fixtures; no new production bypass |

## Alembic

* 41 revisions, **exactly one head: `d1e2f3a4b5c6`**
  (`alembic/versions/d1e2f3a4b5c6_add_pilot_events_and_onboarding.py`).
* The WP-02 journey migration must use `down_revision = "d1e2f3a4b5c6"`.
* Only the integration owner assigns migration identifiers. No parallel heads.
* Migrations are tested on disposable databases only.

## Feature flags

Existing pattern in `app/config.py` (`ATELIER_LLM_ENABLED`, `SERIAL_WORLD_ENABLED`, …).
WP-02 adds `ATELIER_DAILY_JOURNEY_ENABLED: bool = False` plus a server-side cohort
allowlist. Default off; the server response is authoritative.

## Baseline verification — actual results

Commands run from the repository root on 2026-09-05.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **1 failed, 593 passed** |
| `cd web-frontend && npm run type-check` | pass (exit 0) |
| `cd web-frontend && npm run lint` | pass — "No ESLint warnings or errors" |
| `cd web-frontend && npm run test:atelier-next` | pass — "atelier-next resolver tests passed" |
| `.venv/bin/ruff check app/services/journey_contracts.py` | pass |

### Pre-existing failure (do not fix inside these packages)

```
FAILED tests/test_grammar_notebook.py::test_grammar_summary_denominator_matches_the_notebook_index
  assert body["total_concepts"] == len(notebook.json())
  AssertionError: assert 55 == 54
```

An off-by-one between the grammar summary denominator and the notebook index when a
stray `language="French"` concept escapes archival. Unrelated to the daily journey.
It must still fail identically after this work; any *new* failure is ours.

### Pre-existing failure 2 — `alembic downgrade base` (found 2026-09-05, during WP-02 review)

Local PostgreSQL 15 turned out to be available, so the integration owner ran the real
migration cycle on a **throwaway** database (`atelier_v2_migration_check_*`, since
dropped). The live `language_learning` database was never migrated, written, or read
beyond one table count, per the "never use a learner's live DB" rule.

```
alembic upgrade head        -> OK (42 revisions, head e2f3a4b5c6d7)
alembic downgrade -1        -> OK (journey tables dropped, all 53 legacy tables intact)
alembic upgrade head        -> OK
alembic downgrade base      -> FAILS
  Running downgrade grammar_enhancements -> merge_story_chapter_features
  psycopg2.errors.UndefinedColumn: column "grammar_longest_streak" of relation "users"
  does not exist
  [SQL: ALTER TABLE users DROP COLUMN grammar_longest_streak]
```

**Root cause:** two migrations drop the same column on the way down.
`d7e8f9a0b1c2_add_user_settings_and_auth_sessions.py` drops `grammar_longest_streak`
during its downgrade, and the older `grammar_enhancements.py` then tries to drop it
again. Both files are modified in the baseline worktree, so this came from the
pre-existing uncommitted work.

**Proven pre-existing, not ours:** on a second throwaway database upgraded only to
`d1e2f3a4b5c6` (the pre-WP-02 head, with the journey migration absent from the chain
entirely), `alembic downgrade base` fails at exactly the same revision with exactly the
same error. WP-02's own down-migration is clean.

**Impact:** CI's "Verify Alembic migrations" step runs
`alembic upgrade head && alembic downgrade base && alembic upgrade head`, so the
assembled CI gate is red on this today, independently of Atelier V2. WP-12 must report
it as a pre-existing failure rather than a V2 regression.

**Not fixed here.** Repairing it means changing the semantics of an old migration; that
is the owner's call, not a side effect of this work. The minimal fix is to make the
older `grammar_enhancements.downgrade()` drop the column defensively (check
`information_schema.columns` first, or remove the duplicate drop).

### Pre-existing failure 3 — `ruff check .` (found 2026-09-05, running the assembled gate)

CI runs `ruff check .`. It reports **11 errors across 10 files**, and **none of them is
in a file Atelier V2 created**:

```
app/services/pilot_events.py            2  (I001 import block, F401 unused `User`)
app/api/v1/endpoints/analytics.py       1
app/services/missions.py                1
app/tasks/notifications.py              1
alembic/versions/d1e2f3a4b5c6_...py     1
tests/conftest.py                       1
tests/test_atelier.py                   1
tests/test_frontend_continuation_card.py 1
tests/test_pilot_work_packages.py       1
tests/test_srs_review_cycle.py          1
```

`app/services/pilot_events.py` is the only one an Atelier V2 package touched (WP-11, four
additive changes). Both findings there pre-date it: the import block is **byte-identical**
to the pre-WP-11 content snapshot, and the unused `User` import was already flagged in
that snapshot. Every other file is untouched by this work.

9 of the 11 are auto-fixable (`ruff check --fix`). Not fixed here: WP-00's verification
rule is that packages do not repair unrelated baseline failures, and a lint sweep across
ten unrelated files is the owner's call, not a side effect of this work.

### The assembled CI gate has three independent pre-existing failures

For WP-12's honest reporting, none of these is caused by Atelier V2:

| CI step | State | Cause |
|---|---|---|
| `ruff check .` | **red** | 11 findings in 10 pre-existing files (above) |
| `pytest` | **1 failure** | `test_grammar_notebook.py::test_grammar_summary_denominator_matches_the_notebook_index` |
| `alembic upgrade/downgrade/upgrade` | **red** | `grammar_enhancements` drops `grammar_longest_streak` twice (Pre-existing failure 2) |

Everything else in the gate — the backend suite, the word-bank audit, frontend
type-check/lint/tests/build — is green.

### Verified on PostgreSQL 15 (2026-09-05, throwaway database)

Closing the two gaps WP-02 could not close in a SQLite-only environment:

| Invariant | Result |
|---|---|
| `uq_daily_journeys_one_open_per_user` (partial unique index) | second OPEN journey on a different date **refused**; a `completed` one on another date **allowed** — the index really is partial |
| 6 genuinely concurrent connections opening a journey | exactly **1 won, 5 refused** at the database level |
| `uq_daily_journeys_user_date` | duplicate `(user, local_date)` **refused** |
| JSONB round-trip incl. non-ASCII | `{"scenario_key": "order_at_cafe", "nested": {"fr": "café ☕"}}` intact |
| FK cascade on learner delete | journeys removed with the user |

Not run at baseline (recorded, not claimed): `npm run build:native`,
`npm run capture:mobile`, and the Docker build. WP-12 owns the assembled gate.

## Reusable starting points confirmed by inspection

| System | Confirmed surface |
|---|---|
| `UnifiedSRSService` | `get_due_summary`, `get_daily_practice_queue`, `complete_item`; `DueLearningItem`, `ItemType` |
| `VocabularyCreditService` | `apply(...) -> VocabularyCreditResult`, `apply_many`, `summarize` |
| `ErrorMemoryService` | `due_error_records`, `due_errata`, `record_atelier_attempt`, `record_detected_error`, `record_erratum`, `review_error`, `submit_review_attempt` |
| `PilotEventService` | `record(event_type, *, user_id, entity_type, entity_id, payload, cost_usd)`, `daily_rollup` |
| `SerialThreadService` | `current_episode`, `serialize_thread/episode`, `_apply_episode_brief_completion`, `_update_relationship_state`, `SerialThread.state` |
| `SessionLearningMoment` | canonical evidence row: `kind`, `source_type`, `source_id`, `status`, `prompt_payload`, `result_payload`, `score_0_10`, `srs_credit_applied` |
| World bible | `app/prompts/serial/world_bible_paris_v2.json` — cast ids `margaux_barman`, `lila_bonnet`, `romy_tremblay`, `marin_leveque`, `augustin_de_roncourt`; locations `le_mistral`, `marche_canal`, `metro_platform`, `user_apartment`, `newsroom`, … |
| Serial art | `web-frontend/public/assets/serial/{characters,locations,props}/*.webp` |
| User fields | `native_language`, `cefr_estimate`, `proficiency_level`, `daily_goal_minutes` — no `timezone` column, so the journey stores its own IANA snapshot |
| Model conventions | `Mapped[...] / mapped_column`, `PG_UUID(as_uuid=True)`, `JSONB().with_variant(JSON(), "sqlite")` (see `app/db/models/pilot_event.py`) |
| Frontend | `web-frontend/services/api.ts` (2092 lines, `ApiService` with native token refresh), `lib/atelier-next.ts` (317 lines) |

## Frozen contract artifacts

| Artifact | Purpose |
|---|---|
| [CONTRACT-FREEZE.md](CONTRACT-FREEZE.md) | exact wire field names, request bodies, error codes |
| `app/services/journey_contracts.py` | typed cross-package domain dataclasses/enums and source-key helpers |
| `tests/fixtures/daily_journey_v1/` | 26 public fixtures, 9 private evaluator pairs, `manifest.json` |

No credentials, learner records, databases, media caches, or build outputs are part of
any baseline artifact.
