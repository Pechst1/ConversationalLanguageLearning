# E-1 landing plan: `release/rc-2026-10-06` → `main`

Written 2026-10-06 for WP-135 (WORK-PACKAGES-2026-10-06-next.md §2, Track A), which supersedes the
branch state E-1 (WORK-PACKAGES-2026-09-29-engineering.md §3) assumed.

**Status: a proposal waiting for the owner's OK (decision ED-1).** Nothing has been pushed, no
PR is open, nothing is deployed, and no paid call was made. Every command in §6–§8 is for the
owner to run, or for an agent to run only after the owner says so in chat.

---

## 1. What lands

`release/rc-2026-10-06` is the one release candidate. It is local only, and its worktree is
`.claude/worktrees/rc-2026-10-06`. It holds:

| Part | Commits |
|---|---|
| `exp/wave3-integration` (20393c1) | `codex/serial-season-engine-production` up to fcdd312, plus waves 1–3 (96 commits, including cab1fb5, the 10-04 experience fixes) |
| `exp/loss-rate` | 0770a3b fix(director), ac24154 docs (merge 6076e9f) |
| `exp/tentpole-pricing` | 25c52c0 (merge 84485f8) |
| 09-30 production hardening (Codex, uncommitted until now) | 2b12cae |
| 10-03 test and Atelier fixes (uncommitted until now) | e218d3c |
| 10-06 work packages and status plan | 910c347 |
| One alembic head | fca2628 (merge revision `d2f4a6c8e0b1`) |
| Ruff clean | 4579e9e |
| CI-parallel and RC test fixes | 971dffc, b31c70e |
| EbookLib + PyMuPDF declared and pinned (owner, 2026-10-06) | 8111fa2 |
| This plan and `scripts/e1_landing_areas.py` | the commit that adds this file |

Still to come before landing: **WP-137** (`exp/wp137`, in progress in `.claude/worktrees/wp137`),
merged into the RC like loss-rate was. After that merge, the full suites in §5 are re-run.

Against `main` (068710f): about 590 commits (545 without merges), 1,791 files, +600k / −19k
lines. Most of the line count is docs, evidence, season content and art.

- `main` has 8 commits that the RC lacks. All 8 are the merge commits of PRs #49–#56 from the
  same working branch. `git merge-tree` of the RC and `main` is clean, and its tree is
  **identical** to the RC's, so landing needs no conflict resolution.
- `origin/codex/serial-season-engine-production` (4daab79, 09-25) is an ancestor of the RC.

## 2. Why the areas cannot be 12 independently green PRs

ED-1 asks for area PRs, squashed. The coupling stops each area from being green on its own.

- In `app/`, 108 modules form **one import cycle**: the daily journey, the planner, the season
  engine, missions, conversation, Forge, Revue, the reader's audio, SRS and the schemas
  (strongly connected component, 2026-10-06).
- A dry run of the area build (§6) confirms this. After each squashed area commit, `import
  app.main` fails at areas 02–08: first `AttributeError: RULE`, then the missing
  `forge_grading` and `revue.policy`. It imports again from area 09 onward. The final tree is
  byte-identical to the RC.
- CI also references files across areas. For example, the postgres job runs
  `tests/test_production_auth_pg.py` (area 03), and `ci.yml` is area 01.

**Proposal (A, recommended).** One landing branch `land/rc-2026-10-06` off `main` holds 12
squashed area commits in dependency order. It is opened as **one PR** and merged with **"Rebase
and merge"**.

- `main` gets 12 reviewable area commits: squash within each area, as ED-1 asks.
- CI is judged on the PR head, whose tree is exactly the RC's tree. `main` is green right after
  the merge.
- Review goes commit by commit. The PR description (§7) has one section per area, naming its
  risk.
- Full history stays on the archived RC branch (§6).

**Alternative (B).** Twelve stacked PRs: PR *k* targets PR *k−1*'s branch, and each holds the
same one area commit.

- Review gets separate threads per area.
- CI is red on PRs 02–08 by construction.
- Only the top PR, retargeted to `main`, is merged, with "Rebase and merge". The others are
  closed as "landed via #top".
- B is A with more ceremony. Choose it only if per-area review threads matter.

**Rejected (C).** A plain merge commit of the RC (~590 commits on `main`) contradicts ED-1.

## 3. The areas, in landing order

The path rules are in `scripts/e1_landing_areas.py`. The first matching rule wins; every changed
path lands in exactly one area. "Commits" counts the non-merge commits in `main..RC` that touch
the area. Most commits touch several areas, so the counts overlap.

| # | Area | Files | Commits | Dates | Risk | Test evidence (files in the area) |
|---|---|---|---|---|---|---|
| 01 | Infra & CI: workflows, docker, render.yaml, pyproject, root/test conftest, launch config, restore scripts | 34 | 62 | 09-10 → 10-06 | **High.** First CI run since 09-10. The browser walk (`walk.yml`) now gates and is called from `ci.yml`; the image is published only after every job passes; Render deploys on `checksPass`; prod compose needs `APP_IMAGE`. Ruff in CI is unpinned (`ruff>=0.1`); clean locally on 0.14.5 and 0.15.7 | `test_wp85_ci`, `test_production_release`, `test_rollout_scripts` |
| 02 | Platform & schema: alembic (31 new revisions), models, schemas, config, `main.py`, core, celery, LLM/spend guards | 113 | 124 | 09-10 → 10-06 | **High.** Schema guard: production refuses to start behind the head, so the deploy must migrate (`RUN_MIGRATIONS=1`). Upload body limit middleware | 11 test files; alembic dry runs §4 |
| 03 | Auth & accounts: password-reset outbox, row locks, SMTP on the worker, Anki/book upload bounds, GDPR export, auth pages | 28 | 31 | 09-10 → 10-06 | **Medium.** Reset mail retries every 30 s through Celery beat. The outbox is encrypted with a key derived from `SECRET_KEY`: rotating it orphans pending mails. **Licence:** the book parser's new declared dependencies (area 02's `pyproject.toml`/`constraints.txt`) are PyMuPDF (AGPL-3.0 or Artifex commercial) and EbookLib (AGPL-3.0); see §11 | 8 backend + 3 frontend; PG race tests pass on a throwaway DB |
| 04 | Story engine: season 1 runtime, director, lanes, recovery, epilogue, panel art, prompts, season content, art scripts | 275 | 164 | 09-10 → 10-06 | **High.** The loss-rate fix is not yet confirmed by a paid read (WP-136). Until it is, the cohort stays closed | 65 backend + 2 frontend |
| 05 | Journey planner & learning: daily journey, planner, rhythm, vocabulary/SRS, grammar, can-do, band check, item bank, Atelier service and components | 363 | 294 | 09-10 → 10-06 | **High.** The largest area, carrying the A1→C1 content scope and the speed changes | 80 backend + 47 frontend |
| 06 | Conversation: journey conversation, missions, pragmatics, answer acceptance, correspondence/letters | 36 | 58 | 09-10 → 10-06 | Medium | 13 backend + 4 frontend |
| 07 | Reader & voices: feuilleton reader, cast rigs, line/episode audio, TTS, archive | 66 | 47 | 09-10 → 10-05 | **Medium.** Audio costs money once `ATELIER_EPISODE_AUDIO_ENABLED=true` | 8 backend + 7 frontend |
| 08 | Forge: item bank use, grading, picker, coaches, metrics | 38 | 36 | 09-24 → 10-06 | Medium | 13 backend + 9 frontend |
| 09 | Papier / Revue: kiosk, dossiers, encounter, Carte, Radio, Correcteur, Relecture, evergreens | 217 | 15 | 10-02 → 10-06 | **Medium.** Behind its flag. Keep it off in production until WP-139 (source licences) | 18 backend + 11 frontend |
| 10 | Frontend shell & iOS: pages, layout, shared lib, native config, `mobile/` | 234 | 133 | 09-10 → 10-06 | **Medium.** The serial welcome modal is removed from /atelier (10-03). `build` and `build:native` pass | 25 frontend |
| 11 | Walks & cross-cutting tests: learner walk, experience walk, walk checks | 58 | 115 | 09-10 → 10-06 | Low | 58 test files |
| 12 | Docs, evidence & design reference | 329 | 179 | 09-10 → 10-06 | Low | — |

Areas 01–03 come first so that their review (CI, schema, security) is not buried. Areas 04–09
follow the import direction of the cycle, as far as a cycle has one. Tests that belong to one
feature land with that feature.

## 4. Migrations: one linear head

- Heads before: `b1d3f5a7c9e2` (the WP-119–122 merge) and `b9d1f3a5c7e0`
  (`password_reset_deliveries`, 09-30). Head now: **`d2f4a6c8e0b1`**, a merge revision with no
  schema change.
- The owner's database `language_learning` was **not touched**. Dry runs, 2026-10-06, each on a
  throwaway copy made with `pg_dump` (dropped afterwards, see §9):

| Database | Was at | `alembic upgrade head` |
|---|---|---|
| `atelier_rc_1006` (copy of `atelier_test_1003`) | both heads | ran the merge only → `d2f4a6c8e0b1` |
| `atelier_rc_1006b` (copy of `atelier_e2e_0926`) | `b9d1f3a5c7e0` | ran the six Revue revisions + both merges → `d2f4a6c8e0b1` |
| `atelier_ci_rc1006` (empty) | — | 74 upgrades; `downgrade base` 74; upgrade again 74 (CI's own sequence) |

- **Before the first production deploy:** run the same dry run on a `pg_dump` of the
  *production* database (owner action; the command is in §8).

## 5. CI, rehearsed locally on the RC

| CI job / step | Local result (2026-10-06) |
|---|---|
| Ruff `ruff check .` | clean: ruff 0.14.5 (venv) and 0.15.7 (.venv). 71 findings fixed in 4579e9e |
| Backend pytest `-n auto --dist loadfile` | see the test counts at the end of this section |
| OpenAPI `npm run types:check` | current |
| Frontend `tsc --noEmit` / `lint` / `npm test` | 0 errors / 0 errors (1 warning) / 914 of 914 pass |
| Frontend `npm run build` / `build:native` | both pass (with CI's placeholder API env) |
| PostgreSQL alembic up / down base / up | pass (§4) |
| PostgreSQL word-bank audit | 0 flagged rows |
| PostgreSQL-only tests (wp69 savepoint, rollout queries, production auth/recovery) | 10 of 10 pass on `atelier_ci_rc1006` |
| Not rehearsed | Docker image build, story-engine row-lock script, journey drain, mobile viewport smoke, browser walk (`walk.yml`), the 30-day learner walk job |

One CI blocker was found and fixed on the way (971dffc). `tests/test_revue_api.py` built its
parameter ids with `uuid4()`, so every xdist worker collected different tests, and CI's `-n
auto` run stopped at collection on the wave-3 tip.

Backend suite on the RC, 2026-10-06, `-n 5 --dist loadfile`. The wave-3 tip (20393c1, with the
same `test_revue_api` collection fix, or it cannot run at all) is the baseline:

| Run | RC | wave-3 baseline |
|---|---|---|
| `.venv` (3.11, the CI target, pytest-randomly seed 20261006) | **6681 passed, 5 failed, 33 skipped** (before b31c70e; the two wp96 failures are fixed there) | 6548 passed, 14 failed, 53 errors, 25 skipped |
| `.venv`, seed 1006, at 8111fa2 | **6683 passed, 3 failed, 33 skipped** | — |
| `venv` (3.14) | 6667 passed, 10 failed, 37 skipped (before 971dffc / b31c70e) | 6569 passed, 11 failed, 29 skipped |

The baseline's 53 errors are pytest-randomly's seed overflow, fixed by the 10-03 `conftest.py`
fold.

The RC failures that remain are all pre-existing on the baseline, and each passes alone. They
are order-dependent on the shared SQLite catalogue, which is E-2's work:
- `test_wp86_scene_floor` (a known E-2 flake);
- `test_wp78_practice_day::…without_leaking_a_key`;
- `test_journey_letter_day` (409 `step_not_active`);
- with seed 1006: `test_wp75…[some-A2]` (only `tiles`, no `choice`) and
  `test_progress::…exclude_shared_mission_phrases…` (the baseline fails a sibling
  `test_progress` test).

On 3.14 only, `test_revue_relecture::test_routes_offer_answer_and_read_the_pair` fails with a
pydantic forward-ref error; it passes on 3.11.

**The short life walk** (`LIFE_DAYS=7 -m walk tests/test_experience_walk.py`) gives 6 passed and
9 failed. All nine are B1, B2 or C1 lives, each averaging 2.9–3.9 practice items a day where 4
are needed, and 2.3–3.7 on days without a new rule where 5 are needed.

This is a calibration artefact of the short life, not a regression:
- On the wave-3 tip, on `exp/tentpole-pricing` alone and on `exp/loss-rate` alone, the same
  personas fail the same way (3.0–3.9 a day).
- At the walk's own 30 days, the RC passes them (b1-en-average and c1-de-strong: 2 of 2,
  9 min).

The thresholds are month averages that a B1+ first week, with its rule days, does not reach.
Either the thresholds scale with `LIFE_DAYS`, or the short walk is not a gate. That is an
owner/E-2 call. The 30-day `test_learner_walk` CI job is a separate check.

The plan is re-run after WP-137 merges.

## 6. Building the landing branch (agent, after the OK)

```bash
cd /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning
git worktree add .claude/worktrees/land-rc-2026-10-06 -b land/rc-2026-10-06 main
.venv/bin/python .claude/worktrees/rc-2026-10-06/scripts/e1_landing_areas.py build \
  --worktree .claude/worktrees/land-rc-2026-10-06 --tip release/rc-2026-10-06
# The script refuses to finish unless the landing tree equals the RC tree.
```

## 7. Push and PR: owner runs, or says "push it" in chat

```bash
cd /Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning
# 1. The full history, kept as the retired branch (ED-1).
git push origin release/rc-2026-10-06:refs/heads/archive/serial-season-engine-2026-10-06
# 2. The landing branch.
git push -u origin land/rc-2026-10-06
# 3. One PR, merged later with "Rebase and merge" so main keeps the 12 area commits.
gh pr create --repo Pechst1/ConversationalLanguageLearning --base main --head land/rc-2026-10-06 \
  --title "Land the release candidate 2026-10-06: 12 area commits (E-1 / WP-135)" \
  --body-file docs/implementation/atelier-v2/E1-LANDING-PLAN.md
# 4. After CI is green and the area commits are reviewed:
gh pr merge <number> --repo Pechst1/ConversationalLanguageLearning --rebase
```

The PR body is this file. Its table in §3 is the per-area risk statement.

Optional, after the merge: retire the old working branch on the remote. This deletes a remote
branch, so it is the owner's call:
`git push origin --delete codex/serial-season-engine-production`. Its history is in
`archive/serial-season-engine-2026-10-06`.

## 8. Staging and production preconditions: prepared, not run

These are owner actions. Render, secrets and paid services are involved.

1. **Production database dry run:** `pg_dump -Fc <prod-url> > prod.dump`, then
   `scripts/restore_drill.sh prod.dump` (restores into `wp73_drill_*`, verifies heads and
   columns, drops it). Then `DATABASE_URL=<drill copy> alembic upgrade head` on a `--keep` copy.
2. **Staging service from `render.yaml`:**
   - `ATELIER_DAILY_JOURNEY_COHORT=*`
   - S3 for panel art (ED-2: one bucket, a `staging/` prefix)
   - `ATELIER_EPISODE_AUDIO_ENABLED=true`
   - SMTP to a test inbox
   - `RUN_MIGRATIONS=1`
3. **Verifier:** `python scripts/verify_daily_journey_cafe.py --base-url <staging-url>` with a
   test learner. Record the URL and the result in `ROLLOUT.md`.
4. **Keep closed:** the Revue flag stays off (WP-139). The pilot cohort stays closed until
   WP-136 confirms the loss rate.

## 9. The shared checkout: the owner decides, and Codex must be told

The shared checkout is on `codex/serial-season-engine-production` at fcdd312, with a dirty tree.

- Everything in that dirty tree is now in the RC: clusters 1 and 2 as 2b12cae and e218d3c.
- Cluster 3 was byte-identical to cab1fb5 in every file, except one README line, which is
  superseded in 910c347.
- A backup is at
  `/private/tmp/claude-501/…/scratchpad/dirty-backup-2026-10-06/` (`tracked.patch`,
  `untracked.tgz`).

**Proposed sequence:**

1. Tell Codex to stop editing the shared checkout and to commit nothing more on the old
   branch.
2. Check that nothing changed since the backup:
   `git diff HEAD | diff - <backup>/tracked.patch` must print nothing. `git status --porcelain`
   must list only the files in `untracked.txt`. If either differs, the new edits are replayed
   onto the RC first.
3. Move the shared checkout. A branch can be checked out in only one worktree, so pick one of:
   - after the PR merges: `git fetch origin && git checkout -f main && git pull`;
   - before that: `git checkout -f -B codex/next release/rc-2026-10-06`.

   `-f` discards the now-redundant dirty tree, which is why step 2 comes first. Untracked files
   that the RC now tracks are overwritten with identical content.
4. Codex then works on short-lived branches from `main` with PRs (E-1 "afterwards").

## 10. Local branches that become redundant

Every one of these is fully contained in the RC (`git branch --merged release/rc-2026-10-06`).
Their worktrees and branches can go once the PR is merged. This is local cleanup, but it is
the owner's call:

- `exp/`: fix-director, fix-lanes, forge-fixes, gate-123a, loss-rate, practice-band,
  tentpole-pricing, wave1-integration, wave2-integration, wave3-integration, wp123b, wp124a,
  wp124b, wp125a, wp125b, wp126-127, wp128, wp129, wp130a, wp130b, wp131, wp132a-134a,
  wp132b, wp133a, wp133b, wp133b-reread, wp133b-run.
- Others: `experience-review-2026-10-04`, `feat/forge-wp-s1-instant-feedback`,
  `feat/forge-wp-s3`, `feat/forge-wp-s4-one-picker`,
  `fix/courrier-language-mood-2026-09-24`, `fix/one-language-remaining-2026-09-24`,
  `wp-s6-forge-beauty`, `wp-s7-momentum`, and the 27 `worktree-agent-*` branches.
- **Not redundant:** `exp/wp137`. It is still at the wave-3 tip and its work is in progress;
  merge it into the RC first.

Per worktree: `git worktree remove <path>`, then `git branch -d <branch>`. `-d` refuses
anything unmerged.

The throwaway databases from §4 (`atelier_rc_1006`, `atelier_rc_1006b`, `atelier_rc_1006c`,
`atelier_ci_rc1006`) can be dropped with `dropdb`.

## 11. Decisions for the owner

0. **Licensing:** PyMuPDF is AGPL-3.0 or Artifex commercial, and EbookLib is AGPL-3.0. Both are
   now declared dependencies of a network service. Before production, the owner chooses one:
   comply with the AGPL, buy the PyMuPDF commercial licence, or drop the EPUB/PDF import
   paths.
1. **ED-1 mechanics:** one PR with 12 area commits and rebase-merge (A), or stacked PRs (B).
2. **Area boundaries:** are the rules in `scripts/e1_landing_areas.py` acceptable, or should
   some area split or join (for example, 05 at 363 files)?
3. **Push:** the archive branch + the landing branch + `gh pr create`, as in §7.
4. **The serial welcome removal** (10-03, Codex): keep it. It is in e218d3c and the
   capture-harness test now pins it.
5. **Staging (§8):** create the Render staging service, the S3 prefix and the SMTP test inbox.
6. **Moving the shared checkout (§9),** and telling Codex.
