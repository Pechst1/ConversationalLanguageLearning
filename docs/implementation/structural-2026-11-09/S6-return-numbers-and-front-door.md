# S6 · Return numbers from real days, and a repository that says what the product is

Written 9 Nov 2026 from `origin/main` at `ec60ae44`.
Implementation: Opus 5.5, medium effort, own worktree cut from `origin/main`, draft PR, nothing merges without the owner.

## The structural flaw

1. **The product's quality is known only from synthetic walks.** The rubric's «Would come back» is a walker's opinion. The ledger that could answer it for real learners exists (`pilot_events`: user, type, time, indexed; `streak_day`, one row per learner-local day), but every report is for a single day (`PilotEventService.daily_rollup`, `/analytics/pilot-daily`). Nothing asks «of the learners who started on day N, who came back on day N+1 and N+7», so the owner cannot tell whether a fix changed behaviour. The frontend records no usage events of its own, and the gate for showing l'or (O-0) was read from a walk, not from learners.
2. **The repository's front door describes another product.** It is public. `README.md` is titled «Conversational Language Learning Backend» and walks through an XP and NPC API. The root holds a retired React Native client (`package.json`, `jest.config.js`, `tsconfig.json`, `src/`, 26 files), one-off scripts (`fix_db.py`, `create_tables.py`, `restore_db.py`, `check_stories.py`, `test_image_gen.py`, `upload_moby_dick_task.py`, `seed_grammar.py`), an empty `data.db`, `response.json`, a Moby Dick dump (`pg2701-h/`, 1.9 MB), old planning notes, the owner's Excel tracker and an 11.8 MB personal Anki export. Live data sits beside them under misleading names (`templates/` is grammar TSV read by `seance_curriculum.py:21`; `vocabulary_fr_sample.csv` is read by `session_service.py:275` and the Dockerfile).
3. **Native release has no status.** `docs/testflight-production-flip-checklist.md` is a procedure with no marks. The last written state says Apple enrolment is an owner action and Render uses sandbox APNs. Nothing in the repository says whether that changed.

## Target structure

**A. A cohort view built on the existing ledger.**
- `app/services/cohorts.py`: from `streak_day` and `pilot_events`, per sign-up week and per learner: day-1, day-3, day-7 and day-14 return, days completed of days started, median active minutes per day, and the step where an unfinished day stopped (from the stored day plan once S2 lands; from journey steps until then).
- Synthetic accounts (walk accounts, the owner's test accounts) carry a flag on the user and are excluded by default.
- `/analytics/pilot-cohorts` (admin) and a section on `/pilot-ops`; `scripts/pilot_digest.py` prints the same table into the nightly digest issue, next to the rubric trend.
- Counts under 5 learners show the raw numbers, never a percentage.
- Product gates that were defined on walk scores get a learner-data twin written beside them in `docs/ops/`, so a gate can be read from either source and the difference is visible.

**B. A front door that matches the product.**
- `README.md` rewritten: what L'Atelier is, the four tabs and the day, how to run backend and `web-frontend`, where the walks and the ops docs are. The backend quickstart moves to `docs/dev/backend.md`. The Dockerfile copies the README, so the build is checked.
- Root cleaned by one rule: the root holds only what a build, a test run or a deploy reads.
  - Delete: the React Native client and its config, the one-off scripts, `data.db`, `response.json`, `pg2701-h/`.
  - Move: live data to `app/data/` (`templates/` → `app/data/grammar_catalog/`, `vocabulary_fr_sample.csv`), with the readers and the Dockerfile updated; old planning notes to `docs/archive/`.
  - Owner call: the Anki export and the Excel tracker (see decisions).
- A test lists the allowed root entries and fails on a new one.

**C. A release status file.** `docs/ops/release-status.md`, one table: Apple enrolment, App Store Connect record, APNs environment on Render, Sentry DSNs set, legal text final, last archive, last TestFlight build. Each row has a state, a date and who can change it. The fastlane `beta` lane appends the build it uploaded.

## Stages (each its own PR)

1. Root clean-up and README (B). Mechanical; every move is checked by the test suite, the Docker build and the release check.
2. Cohort service, endpoint, pilot-ops section and digest line (A).
3. Release status file and the lane hook (C).

## Done when

- The root-entries test passes and fails when a stray file is added. `docker build`, the backend suite and `verify-native-bundle.mjs` pass after the moves.
- `tests/test_cohorts.py` seeds learners with known return patterns under the test clock and asserts the table, including the small-count rule and the exclusion of synthetic accounts.
- The nightly digest shows the cohort table.
- `release-status.md` exists with every row filled as «unknown» or a dated state.

## Not in this package

- Recruiting learners, Apple enrolment and the App Store record: owner actions. This package makes their state visible and measurable.
- Any third-party analytics SDK.

## Owner decisions needed

1. The Anki export (11.8 MB, a personal deck that three scripts and the lexicon's provenance read) and the Excel tracker: keep in the public repository, move to private storage, or delete after the lexicon build no longer needs them?
2. May git history keep those files, or should they be purged (a history rewrite; disruptive with 38 open PRs)?
3. Which accounts count as synthetic.
