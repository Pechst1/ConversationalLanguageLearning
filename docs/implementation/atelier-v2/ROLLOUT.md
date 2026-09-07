# Pilot rollout runbook — Atelier V2 daily journey (WP-13 §6 / WP-18)

How to switch the V2 daily journey on for a named cohort, watch it, price it, and
switch it off without stranding a learner. Written 2026-09-07 by the WP-18
preparation pass. **Nothing in production has been enabled and nothing has been
deployed**; every command below was run either against a throwaway PostgreSQL
database with the fake provider, or not at all — the ones that were not are
marked *owner action*.

Scope: the backend flags only. The native build has its own contract in
[../../testflight-production-flip-checklist.md](../../testflight-production-flip-checklist.md).

---

## 1. Prerequisites

| Prerequisite | State on 2026-09-07 |
|---|---|
| Commits on `codex/serial-season-engine-production` | `3cc56b5`, `904e856`, `ed8404f` (WP-15), `d6aa974` (WP-17), `21dd85b` (WP-19) |
| Alembic head | `a3b4c5d6e7f8` — the deploy must reach it (`RUN_MIGRATIONS=1` does this on `atelier-api`) |
| CI | Green as of `21dd85b`: backend pytest + nine node suites (`test:seance`, `test:story-model` included) |
| WP-16 (one daily Séance) | **In the working tree, not committed.** Landing it is a precondition for the cohort flip, not for this runbook |
| WP-17 fourteen-day paid runs | **Not bought.** Variety is proven deterministically only (ENGINE-IMPLEMENTATION §WP-17) |
| Backend deployed to Render | **Never.** The first deploy is an owner action (§9) |

---

## 2. The keys

Set on **both** Render services (`atelier-api` and `atelier-worker`) or the
worker will disagree with the API. A change to any of them restarts the service:
that is how the flag takes effect, because `journey_enabled_for` reads the
process-wide settings object.

| Key | Safe default (today) | Pilot value | What it does |
|---|---|---|---|
| `ATELIER_DAILY_JOURNEY_ENABLED` | `false` | `true` | Master switch. `false` stops *creation* only; open journeys keep draining (§6) |
| `ATELIER_DAILY_JOURNEY_COHORT` | `""` | `owner@email,five@study,…` | Comma-separated emails **or** user ids. In `APP_ENV=production` an empty value enables **nobody**; only the literal `*` enables every learner (development keeps empty = everyone for tests and harnesses). Shrink the pilot by removing entries, never by blanking |
| `ATELIER_STORY_ENGINE_ENABLED` | `true` (unreachable while the master switch is off) | `true` | Living-story generation. `false` sends *new* journeys to the authored scenario path; learners who already have an engine thread keep reading theirs (`living_story.manages_story`) |
| `ATELIER_STORY_MAX_ATTEMPTS` | `2` | `2` | Generation attempts per scene. `3` roughly doubles the worst-case cost of a bad day; `1` turns one bad draft into a lost day |
| `ATELIER_CORRECTION_LLM_ENABLED` | `true` | `true` | AI assessment of open answers. `false` = deterministic checking, open answers saved unassessed |
| `ATELIER_CORRECTION_LLM_MODEL` | `gpt-5-mini` | `gpt-5-mini` | Pinned in `render.yaml` since WP-15; `gpt-5-nano` graded badly |
| `ATELIER_CORRECTION_LLM_MAX_TOKENS` | `5000` | `5000` | 900 truncated real paragraph assessments |
| `ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS` | `60` | `60` | |
| `ATELIER_CORRECTION_LLM_REASONING_EFFORT` | `low` | `low` | Unset starves `gpt-5-*` of output tokens |
| `GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED` | `false` | `false` | Keep off for the pilot: no durable S3 storage yet, ≈ US$0.053 per panel |
| `PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD` | `2.00` | `2.00` | Weekly per-learner warning threshold (§5) |

`.env` on the owner's machine sets none of the journey keys, so the local
backend inherits the safe defaults above. (It does set
`GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED=true` locally; `render.yaml` sets
`false` for both deployed services.)

---

## 3. Cohort allowlist procedure

1. **Owner's account first, alone.** Set `ATELIER_DAILY_JOURNEY_COHORT` to the
   owner's email and `ATELIER_DAILY_JOURNEY_ENABLED=true`. Both services.
2. Wait for the redeploy, then check `/health` and `/ready` (200), and that the
   owner's `GET /api/v1/daily-journeys/today` answers `enabled: true` while a
   second, non-cohort account still answers `enabled: false` with `journey: null`.
3. Run one full journey on the owner's account. Then run the health and cost
   queries (§4, §5) and `scripts/pilot_digest.py --day <that day>`.
4. **Only if the first day is clean**, append the five study accounts (WP-22) to
   the same list, one comma-separated value, and redeploy.
5. To remove one learner, delete that entry and redeploy. Never empty the list
   while the master switch is on — that opens the pilot to everyone.

Identity matching is case-insensitive on email or user id
(`daily_journey.journey_enabled_for`); the server response is authoritative, so
a stale client cannot enter the cohort by itself.

---

## 4. Health queries

`scripts/rollout_health.py` runs exactly the queries this section documents, so
the runbook and the tool cannot drift:

```bash
.venv/bin/python scripts/rollout_health.py \
    --database-url "$PILOT_DATABASE_URL" --since 2026-09-08 [--user owner@email]
```

It refuses a local `language_learning` database outright; the remote Render
database is also named `language_learning`, so pointing it there needs an
explicit `--allow-production-name`.

| Section | Question it answers | Watch for |
|---|---|---|
| `journeys` | created / completed / ended early / still open per learner-local day | completion well below creation, or journeys still open from previous days |
| `states` | status × `unavailable_reason` × `retry_allowed`, max generation attempts | any `unavailable` row: a learner was offered nothing that day |
| `conflicts` | `journey_resume_conflict` events per day, split into `version_conflict` and `step_not_active`, against accepted mutations | conflicts rising with traffic — the client is holding stale revisions |
| `engine_cost` | scenes and US$ per learner-day from `graphic_novel_scenes.script_payload->'estimated_cost'` | per-learner-day cost above ≈ US$0.02 (the measured live rate is ≈ US$0.007 per scene) |
| `engine_ledger` | `journey_story_scene_cost` / `_turn_cost` / `_generation_failed` rows and their US$ | failed-generation spend: money with no scene behind it |
| `correction_cost` | Séance correction calls, tokens and US$ per day | token counts climbing (the learner's answer is unbounded on that endpoint) |
| `weekly_guardrail` | per-learner ISO-week spend against `--guardrail` | any `over_guardrail = true` row (§5) |

The same numbers reach the daily report through
`scripts/pilot_digest.py --day YYYY-MM-DD [--user-id …]`, which additionally
prints the journey funnel (WP-11 metrics) and the Séance correction line.

Actual output, against the throwaway database this package used (fake provider,
so every amount is honestly `0.000000`):

```
## Journeys per learner-local day
day        | created | completed | ended_early | still_open | learners
-----------+---------+-----------+-------------+------------+---------
2026-09-06 | 1       | 1         | 0           | 0          | 1
2026-09-07 | 1       | 0         | 0           | 1          | 1

## Journey states and unavailable reasons
status    | unavailable_reason | retry_allowed | journeys | max_generation_attempts
----------+--------------------+---------------+----------+------------------------
active    | -                  | True          | 1        | 1
completed | -                  | True          | 1        | 1

## 409 conflict rate per day
day        | conflicts | version_conflicts | step_not_active | accepted_mutations
-----------+-----------+-------------------+-----------------+-------------------
2026-09-07 | 0         | 0                 | 0               | 2

## Engine cost per learner-day (scene estimated_cost)
day        | email                             | scenes | story_usd | total_usd
-----------+-----------------------------------+--------+-----------+----------
2026-09-07 | drain-cohort-60b5536b@example.com | 2      | 0.000000  | 0.000000

## Engine cost ledger rows (pilot_events)
day        | event_type               | rows_written | cost_usd
-----------+--------------------------+--------------+---------
2026-09-07 | journey_story_scene_cost | 2            | 0.000000
2026-09-07 | journey_story_turn_cost  | 1            | 0.000000

## Séance correction cost per day
  (no rows)

## Weekly spend per learner against the guardrail
iso_year | iso_week | email                             | scenes | week_usd | over_guardrail
---------+----------+-----------------------------------+--------+----------+---------------
2026     | 37       | drain-cohort-60b5536b@example.com | 2      | 0.0000   | False
```

(The 2026-09-06 row is the drain driver dating day 1 back by one day to simulate
the next learner-local day; see §7.)

---

## 5. Cost and the weekly guardrail

- Engine spend is written twice, on purpose: once into
  `scene.script_payload.estimated_cost` (what `SerialGenerationCostService`
  and the guardrail read) and once as a `PilotEvent` row per accepted artifact.
  Both are written inside the transaction that publishes the artifact, so a
  rolled-back scene takes its cost row with it (WP-17 §5).
- `PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD` (2.00) is a **warning threshold on
  the admin endpoint `GET /api/v1/analytics/pilot-ops`**, not an enforcing limit: nothing stops
  generation when it is crossed. Crossing it is the signal to shrink the cohort
  (§3) or to drain (§6). At the measured ≈ US$0.007 per scene plus turn, one
  learner-day is ≈ US$0.01–0.02, so a single learner should not approach 2.00 in
  a week; a row that does means retries or a loop, not normal use.
- Séance correction cost is **per submit on the most-used endpoint** and is not
  covered by the serial weekly guardrail. Watch `correction_cost` daily.
- Panel images stay off. Turning them on adds ≈ US$0.053 × panels per scene and
  needs durable storage first.

---

## 6. Drain (the normal way to stop)

Set `ATELIER_DAILY_JOURNEY_ENABLED=false` on both services. That is all.

What stops: `POST /daily-journeys` and `POST /daily-journeys/{id}/retry` answer
**403** with `{"detail": {"code": "journey_disabled", "message": "The daily
journey is not enabled for this account."}}`.

What keeps working for a learner who is already inside today's journey:

- `GET /daily-journeys/today` — 200, `enabled: false`, the open journey still in
  the envelope;
- `GET /daily-journeys/{id}`, `advance`, `attempts`, `pause`, `resume`, `finish`;
- the engine reader (`GET /story-engine/episodes…`) and its position writes;
- the legacy Séance for everyone else, unchanged.

No row is deleted, downgraded or rewritten by the flip. Turning the flag back on
resumes the same serial thread on the next learner-local day.

---

## 7. Drain evidence

`scripts/verify_journey_drain.py` proves the above against a real HTTP surface,
a throwaway PostgreSQL 15 database (`atelier_wp18_1788800834`, created and
dropped by this pass) and `scripts/dev_story_engine_server.py`'s fake provider —
no paid call. It owns the server lifecycle and restarts it with the flag on,
off and on again, which is exactly what a Render env-var change does. The next
learner-local day is simulated by dating the previous day's journey rows one day
back; nothing else in the engine reads wall-clock time on that path.

```bash
createdb atelier_wp18_$(date +%s)
DATABASE_URL=postgresql://localhost/atelier_wp18_XXXX .venv/bin/alembic upgrade head
.venv/bin/python scripts/verify_journey_drain.py \
    --database-url postgresql://localhost/atelier_wp18_XXXX
```

Run 2026-09-07 on the working tree (which includes the in-flight WP-16 and
WP-21 edits), exit code 0:

```
Phase          | Check                                                               | Result | Detail
---------------+---------------------------------------------------------------------+--------+-------------------------------------------------------------------------------------------
1 · flag on    | cohort learner: today() enabled                                     | PASS   | True
1 · flag on    | cohort learner: create journey                                      | PASS   | 201
1 · flag on    | cohort learner: journey active, scene step first                    | PASS   | status=active step=scene
1 · flag on    | cohort learner: one step advanced before the flip                   | PASS   | 200 revision 2->3
1 · flag on    | outside-cohort learner: today() disabled, no journey                | PASS   | enabled=False journey=None
1 · flag on    | outside-cohort learner: create refused 403 journey_disabled         | PASS   | 403 journey_disabled
1 · flag on    | legacy learner: GET /atelier/today                                  | PASS   | 200
1 · flag on    | legacy learner: POST /atelier/sessions starts a real session        | PASS   | 201 session=511da297-fa3a-4d3c-9acd-086e02fd0e31 concepts=[1] exercise_sets=1
1 · flag on    | legacy learner: /atelier/sessions/active resumes that same session  | PASS   | 200 id=511da297-fa3a-4d3c-9acd-086e02fd0e31
2 · drained    | cohort learner: today() still answers 200                           | PASS   | 200
2 · drained    | cohort learner: today() reports disabled but keeps the open journey | PASS   | enabled=False journey=38228ce7-036b-40f2-86fb-eccc5bdf0186
2 · drained    | cohort learner: the journey is still readable                       | PASS   | 200
2 · drained    | cohort learner: the engine scene is still readable                  | PASS   | 200 episodes=1
2 · drained    | cohort learner: reading position still saves                        | PASS   | 200
2 · drained    | cohort learner: every remaining step completes while drained        | PASS   | steps=['respond', 'resolution']
2 · drained    | cohort learner: finish accepted while drained                       | PASS   | 200
2 · drained    | cohort learner: journey completed with a story outcome              | PASS   | status=completed story_outcome=True
2 · drained    | cohort learner: exactly one completed learning session              | PASS   | [{'status': 'completed'}]
2 · drained    | cohort learner: a new create is refused 403 journey_disabled        | PASS   | 403 journey_disabled
2 · drained    | the refusal carries the documented message                          | PASS   | 'The daily journey is not enabled for this account.'
2 · drained    | regeneration (retry) is refused too                                 | PASS   | 403 journey_disabled
2 · drained    | no journey row was deleted or downgraded by the flip                | PASS   | [{'status': 'completed'}]
2 · drained    | legacy learner: today() unchanged (200, disabled, no journey)       | PASS   | 200 enabled=False
2 · drained    | legacy learner: GET /atelier/today                                  | PASS   | 200
2 · drained    | legacy learner: POST /atelier/sessions starts a real session        | PASS   | 201 session=511da297-fa3a-4d3c-9acd-086e02fd0e31 concepts=[1] exercise_sets=1
2 · drained    | legacy learner: /atelier/sessions/active resumes that same session  | PASS   | 200 id=511da297-fa3a-4d3c-9acd-086e02fd0e31
2 · drained    | legacy learner: start/resume identical to the flag-on run           | PASS   | session=511da297-fa3a-4d3c-9acd-086e02fd0e31 concepts=[1] sets=1
3 · re-enabled | one serial thread exists after day 1                                | PASS   | ['316ebcf4-61c7-4e1e-acb4-8daf4300b4bc']
3 · re-enabled | day 2: a new journey is created again                               | PASS   | 201 id=0e7e2e38-7b83-4b5c-87ce-ab9310a68349
3 · re-enabled | day 2 reuses the same serial thread (no second thread)              | PASS   | threads=['316ebcf4-61c7-4e1e-acb4-8daf4300b4bc']
3 · re-enabled | day 2 is episode 2 of the same thread, day 1 stays completed        | PASS   | [{'status': 'completed', 'episode_index': 0}, {'status': 'available', 'episode_index': 1}]
3 · re-enabled | day 2's scene continues day 1's story event                         | PASS   | source_event_ids=['journey:38228ce7-036b-40f2-86fb-eccc5bdf0186:story']
3 · re-enabled | day 1's story event survived the whole flip cycle                   | PASS   | events=['journey:38228ce7-036b-40f2-86fb-eccc5bdf0186:story']
3 · re-enabled | exactly two engine scenes exist (one per day, none lost)            | PASS   | scenes=2

34/34 checks passed
```

What this run does **not** prove: real model behaviour (the provider is fake),
anything about the frontend, and anything under concurrency — the PostgreSQL
lock races are `scripts/verify_story_engine_pg.py` (33/33, 2026-09-06).

---

## 8. Kill-switch order and rollback

Least to most drastic. Each step is an env-var change on both services plus the
redeploy it triggers.

1. **Shrink the cohort** — remove entries from `ATELIER_DAILY_JOURNEY_COHORT`.
   Never blank it while the master switch is on.
2. **Drain** — `ATELIER_DAILY_JOURNEY_ENABLED=false` (§6). Reversible, loses
   nothing, and is the right response to a cost or quality surprise.
3. **Engine off, journey on** — `ATELIER_STORY_ENGINE_ENABLED=false`. New
   journeys fall back to the authored scenario path; learners who already have an
   engine thread keep reading it. Use only if generation itself is the problem.
4. **Corrections deterministic** — `ATELIER_CORRECTION_LLM_ENABLED=false`. Open
   answers are then saved unassessed. Use if correction spend or latency is the
   problem.
5. **Roll back the deploy** to the previous Render image.

Data rules, in every case:

- **Never downgrade the migration and never delete V2 rows.** `daily_journeys`,
  `daily_journey_steps`, `daily_journey_mutations`, the engine's
  `graphic_novel_scenes` and the `serial_threads.state.living_story` history are
  the learner's own record; a flag-off learner simply stops creating new ones.
- A rolled-back image still reads those tables. The reverse — an older image
  that predates head `a3b4c5d6e7f8` — does not; that is why the rollback target
  is the previous image, not an arbitrary older one.
- Cost rows live and die with their artifact's transaction; do not delete them
  to "clean up" a bad day, or the weekly rollup stops matching the ledger.

---

## 9. Who flips what

| Step | Owner | Agent |
|---|---|---|
| Render blueprint deploy, first migration to head | **Owner** | prepares `render.yaml`, checks `/health`, `/ready`, `alembic heads` |
| Any env-var flip in §2, §3, §8 | **Owner** (Render dashboard) | never; an agent may prepare the exact value to paste |
| `.env` on the owner's machine | **Owner** | never edits it |
| Cohort membership | **Owner** | prepares the list |
| Health / cost reading | either | runs `scripts/rollout_health.py`, `scripts/pilot_digest.py` and reports |
| Paid engine runs (WP-17) | **Owner** consents, with `--max-requests` set | runs them after consent |
| Study accounts and consent (WP-22) | **Owner** | prepares accounts, reads results |

---

## 10. Gates that remain, and cannot close here

- **Apple:** `bundle exec fastlane ios archive` stops at code signing — there is
  no Apple Developer team enrolled on this machine and no provisioning profile
  for `com.pixellab.feuilleton` (STATUS 2026-09-07 §WP-19.8). TestFlight, the
  privacy-manifest bounce and push in production all sit behind that.
- **Learner study:** the five-learner protocol (QA-REPORT §11) is unrun; it needs
  the cohort live and a build to hand out.
- **Live prose at length:** the four fourteen-day paid runs (≈ US$0.60, ceiling
  US$0.85) in ENGINE-IMPLEMENTATION §WP-17 are unbought; today's variety evidence
  is deterministic only.
- **Browser QA of the assembled V2** (WP-20) and the three WP-19 defects it
  inherits (D-1 resume target, D-2 Dynamic Type, D-3 header safe area).
- **WP-16** must land before the cohort flip, or a cohort learner sees two daily
  Séances.
