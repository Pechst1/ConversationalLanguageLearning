# Work packages — 2026-09-29 (engineering): make big changes safe to verify

Owner brief: turn the engineering leaps E-1..E-8 into work packages, and say
which model and how much reasoning each one needs.

## 1. Why these packages

Four product packages this week (WP-88..93) ran as three or four parallel agents
each, on separate files against agreed interfaces (about 50 commits). Writing the code was
never the bottleneck. Every real problem was at a seam or in verification:

- one agent's new step order broke another agent's tests (WP-93);
- a planner change quietly under-filled the 30-minute day (WP-93);
- a field was stored but never served by the API (WP-90 `alt_native`);
- tests passed alone and failed in the full run, four times (session-scoped
  SQLite in `tests/conftest.py:131,138`, never reset between tests);
- browser walks stalled on the hidden preview pane.

State on 2026-09-29: **404 commits** on `codex/serial-season-engine-production`
that main and CI have never seen; ~3,900 backend tests (~10 min full run) and
527 frontend tests; six modules between 4,000 and 5,800 lines; 129 settings.

## 2. Choosing the model

These are recommendations from the kind of work, not benchmark claims. Two
questions decide it:

1. **Is it judgement over a large, entangled surface** (which commits belong
   together, what a 5,000-line module really does, what is safe to delete)?
   Then **Opus 5.5**, at high reasoning effort.
2. **Is it well-trodden and mechanical once the design is fixed** (a
   Playwright script, a codegen step, updating 200 fixtures to one pattern)?
   Then **Sonnet 5.5**, at medium effort. It is faster and cheaper, and in
   parallel it covers more ground.

Effort levels follow the Claude Code scale: *low*, *medium*, *high*, *xhigh*.
Several packages split cleanly: **Opus designs and reviews, Sonnet executes in
bulk.** Anything outward-facing (pushes, PRs, deploys) stays owner-approved,
whatever the model.

| WP | Design / risky part | Bulk / mechanical part | Why |
|---|---|---|---|
| E-1 Land the branch | Opus 5.5 · high | Sonnet 5.5 · medium (CI fixes per PR) | Grouping 404 commits, conflicts, deploy config: judgement and the biggest risk |
| E-2 Trustworthy tests | Opus 5.5 · high | Sonnet 5.5 · medium (fixture migration) | One fixture change touches ~3,900 tests; order bugs are subtle |
| E-3 Walk harness | Sonnet 5.5 · high | Sonnet 5.5 · medium | Well-trodden (Playwright); the hard part is the clock shim and sign-in |
| E-4 Split the monoliths | Opus 5.5 · xhigh | Opus 5.5 · high (one module per agent) | Behaviour-preserving splits need the whole module held at once |
| E-5 Generated types | Sonnet 5.5 · medium | Sonnet 5.5 · low | Codegen plus a type migration; the compiler is the safety net |
| E-6 Flags & legacy | Opus 5.5 · medium (inventory, verdicts) | Sonnet 5.5 · medium (deletions) | Deciding what is dead is judgement; deleting it is not |
| E-7 Prompt regression | Opus 5.5 · high (fixture design, what to assert) | Sonnet 5.5 · medium (cache, runner) | Deciding what counts as a regression is the hard part |
| E-8 Package workflow | Opus 5.5 · medium | — | Small script; the design encodes this week's lessons |

## 3. Packages

Waves: **A** = safety first (E-2, E-1) · **B** = see what you ship (E-3, E-7)
· **C** = room to move (E-4, E-5, E-6) · **D** = one command per package (E-8).
Each package has a "done when" line so an agent can prove it.

### Wave A — safety first

#### E-2 · A test suite you can trust, fast
**Model:** Opus 5.5 · high for the fixture design and the first 20 order-dependent failures; Sonnet 5.5 · medium for migrating the rest.
- **Isolation:** every test runs inside a transaction (plus a SAVEPOINT for code that commits) that is rolled back at teardown; the session-scoped `db_engine` stays, the data does not. Tests that genuinely need committed data (post-commit hooks: `panel_art`, `coulisses`) get an explicit fixture that cleans up after itself.
- **Postgres in CI:** CI runs the suite against Postgres, which production uses, not SQLite. Local runs may keep SQLite behind a flag. Differences found on the way become tests.
- **Parallel:** `pytest-xdist` with one database per worker; the full run is under 3 minutes.
- **The known flakes:** `test_wp86_scene_floor`, `test_living_story_longitudinal::test_two_seeds…`, `test_long_horizon_evidence::test_two_lives_diverge` and the `test_atelier` starter test must pass in any order (`pytest-randomly` in CI).
- **The midnight flakes:** a few tests fail between 00:00 and 02:00 Berlin time (the UTC/local day split). A pinned clock fixture fixes them.
- **Done when:** three randomised full runs in a row pass on Postgres, each under 3 minutes, with no test marked "order-dependent".

#### E-1 · Land the branch
**Model:** Opus 5.5 · high to plan and review; Sonnet 5.5 · medium for CI fixes inside each PR. Every push, PR and deploy is owner-approved.
- **Plan:** group the 404 commits into about 8–12 reviewable PRs by area (infra & CI, auth & accounts, story engine, journey planner, conversation, reader & voices, Forge, docs), in dependency order. Rebase where history allows, squash where it doesn't, and write a PR description per group that names its risk.
- **Migrations:** one linear alembic history on main; a dry run of `alembic upgrade head` against a copy of the owner's database before the first merge.
- **CI:** green on every PR (backend, frontend, `build:native`). E-2 first, so green means something.
- **Staging:** a Render staging environment from `render.yaml` with the cohort set to `*`, S3 for panel art, and `ATELIER_EPISODE_AUDIO_ENABLED` on. Run the rollout verifier (`scripts/verify_daily_journey_cafe.py`) against it.
- **Afterwards:** the working branch is retired, and new work goes through short-lived branches with PRs.
- **Done when:** main contains everything, CI is green on main, staging serves a full day to a test learner, and `ROLLOUT.md` records the staging URL and the verifier result.

### Wave B — see what you ship

#### E-3 · A browser walk harness in the repo
**Model:** Sonnet 5.5 · high for the harness (clock shim, sign-in, fake provider); Sonnet 5.5 · medium for the day scripts.
- **The harness:** Playwright in `web-frontend/e2e/`, driving `backend-e2e` plus the frontend against a throwaway database created per run. Sign-in goes through the API with a minted session, never a typed password. The provider is the fake story-engine one (`scripts/dev_story_engine_server.py`), with an opt-in live mode.
- **Clock shim:** a server-side date override for test runs only (refused in production), so day 2..7 can be played in minutes.
- **The walk:** day 1 (hand-written) → day 7, covering the reader, the conversation thread, drills including dictation, the reading step, the recap, Home, Courrier and Feuilleton.
  - Screenshots at 375×812 in light and dark, and in en / de / fr.
  - Assertions for the known traps: no "not reached the server" banner while typing, Next never moves, one verdict per conversation, no English on French screens at B1+.
- **CI:** runs on every PR and publishes screenshots as an artifact. A nightly run keeps the last 7 walks.
- **Done when:** one command walks 7 days in all three languages in under 10 minutes and the screenshots attach to the PR.

#### E-7 · Prompt regression tests without paying each time
**Model:** Opus 5.5 · high to choose the fixtures and what to assert; Sonnet 5.5 · medium to build the cache and runner.
- **Golden transcripts:** real failures become fixtures — W7/W8 (Margaux forgets the coffee, B1 reply to A1), the WP-89 greeting-nudge bug, the WP-68 repeated premise, the invented quote, and one clean day per band.
- **A cache of real answers:** each prompt call is keyed by (prompt version, input digest). A run replays cached answers; only a changed prompt pays for one new real call per fixture, owner-approved and capped.
- **What is checked:** guards, word caps, no re-asked settled facts, no spoilers, register and level. Also a diff report of the text itself, for a human to read.
- **Done when:** changing the director or conversation prompt produces a pass/fail list plus a text diff in under 2 minutes, for under US$0.10 on a changed prompt and US$0 otherwise.

### Wave C — room to move

#### E-4 · Split the monoliths, safely
**Model:** Opus 5.5 · xhigh to design the seams; Opus 5.5 · high to execute, one module per agent, never two agents in one module.
- **Targets and seams:**
  - `living_story.py` (5.8k): director / actor / checks / memory & bookkeeping / scoring.
  - `missions.py` (5.7k): Courrier letters / corrector / chains / legacy missions.
  - `pages/atelier.tsx` (5.7k): the WP-16 split proposal (Home, legacy Séance, controllers).
  - `daily_journey.py` (4.8k): lifecycle / steps & attempts / snapshot / story bridge.
  - `journey_planner.py` (4.1k): pricing / candidates / day shapes / assembly.
  - `journey_conversation.py` (4.1k): authored grading / live replies / feedback policy.
- **Method:**
  1. Pin current behaviour with tests at the module's public functions, reusing the existing suites.
  2. Move code without changing it; each commit is a pure move and passes the suite.
  3. Then small cleanups, each in its own commit.
- **Rules:** public import paths stay stable (re-exported) until the callers have moved; no behaviour change in the same PR as a move.
- **Done when:** no module in `app/services` or `pages/` is over 2,000 lines; the full suites and the E-3 walk are unchanged; `git log --follow` still finds each function.

#### E-5 · Generate the frontend types from the backend
**Model:** Sonnet 5.5 · medium; the migration at low effort.
- **Generation:** OpenAPI from FastAPI (the journey, story-engine, line-audio and vocabulary schemas first) turned into TypeScript (`openapi-typescript`) under `web-frontend/types/generated/`, with a CI check that the generated file is current.
- **Migration:** `types/daily-journey.ts` re-exports the generated types. Hand-written narrowings stay only where the frontend genuinely narrows.
- **Clean-up:** the contract-parity tests that compared hand copies are deleted once the generated types cover them.
- **Done when:** adding a field to a backend schema without regenerating fails CI, and a field the frontend reads but the API doesn't send is a type error.

#### E-6 · Flag and legacy cleanup
**Model:** Opus 5.5 · medium for the inventory and verdicts; Sonnet 5.5 · medium for the deletions.
- **Inventory:** list all 129 settings, each marked *product switch* (stays), *permanent* (delete the flag, keep the code path), *dead* (delete both) or *owner call*. Include module constants such as `DUAL_DRAFTS_ENABLED`, `BONUS_ATTEMPT_ENABLED` and `CRITIC_ENABLED`.
- **Legacy code:** the legacy Séance (`SessionView`/`Epreuve`) behind the journey, legacy serial and graphic-novel generation, off-system pages, the dead `sm2.py`.
- **Owner calls:** decisions are listed for the owner, never taken silently. Each deletion is its own commit with the reason.
- **Done when:** every remaining flag has a one-line "why it's still a switch" in `config.py`, the suites and walk are green, and the line count drops measurably (reported).

### Wave D — one command per package

#### E-8 · Make the package pipeline a saved workflow
**Model:** Opus 5.5 · medium.
- **The workflow:** a saved workflow (`.claude/workflows/package.js`) encoding this week's pipeline:
  1. Read the package spec.
  2. Write the shared interfaces as stubs and commit them first.
  3. Run parallel agents on separate files (at most four; each commits only its own paths with `git commit -- <paths>`).
  4. Pass requests between agents.
  5. Integrate.
  6. Run the full suites (E-2) and the walk (E-3).
  7. Update the plan doc's status and the memory.
- **Guards learned the hard way:** no `git checkout`/`stash`; a single editor per file per round; every "done" report states test counts; any schema change needs a migration on the e2e copy.
- **Done when:** `run package WP-94` produces the commits, test counts, walk screenshots and a status note with no manual relaying.

## 4. Order

1. **E-2** first: the merge in E-1 needs test results you can believe.
2. **E-1**: the biggest risk; the pilot needs main and staging.
3. **E-3 and E-7** together: the walk and the prompt fixtures protect the product while it keeps changing.
4. **E-4, then E-5 and E-6** — after E-1, so the splits land on main rather than on a branch.
5. **E-8** last, once the pieces it calls exist.

## 5. Owner decisions

| # | Decision | Recommendation |
|---|---|---|
| ED-1 | PR grouping and whether to squash history | Squash within each area PR; keep the history in the retired branch |
| ED-2 | Staging on Render: plan, S3 bucket, domain | Smallest plan, one bucket shared with production under a prefix |
| ED-3 | E-7's cap on real calls when a prompt changes | US$1 per run, owner-approved above it |
| ED-4 | E-6's owner-call list | Reviewed in one sitting when the inventory is done |
| ED-5 | Budget split between Opus and Sonnet | As in §2: Opus designs and reviews, Sonnet does the bulk |

## 6. How to start a package (ready-made subagents)

Each package has a subagent definition in `.claude/agents/` with its model and
reasoning effort in the frontmatter (`model`, `effort`), the package brief, and
the shared ground rules: shared checkout, commit only your own paths,
outward-facing steps stop for the owner, no paid calls, test commands, and the
report format.

| Agent | Model · effort | Starts |
|---|---|---|
| `e-2-test-suite` | Opus · high | E-2 (run first) |
| `e-1-land-branch` | Opus · high | E-1 — writes the landing plan, then stops for ED-1 |
| `e-3-walk-harness` | Sonnet · high | E-3 |
| `e-7-prompt-regression` | Opus · high | E-7 |
| `e-4-split-monoliths` | Opus · xhigh | E-4, **one module per run** (name it in the task) |
| `e-5-generated-types` | Sonnet · medium | E-5 |
| `e-6-flag-cleanup` | Opus · medium | E-6 — inventory, then stops for ED-4 |
| `e-8-package-workflow` | Opus · medium | E-8 (last) |
| `e-bulk-executor` | Sonnet · medium | Bulk work a lead hands over (pattern + files + check) |

To start one, ask in a Claude Code session, for example:

- `@"e-2-test-suite (agent)" start E-2`
- `Use the e-4-split-monoliths agent on app/services/journey_planner.py`
- or in a session's own words: "run E-2 with its subagent".

Run E-2 → E-1 → E-3 + E-7 → E-4/E-5/E-6 → E-8 (§4). At most four agents at a
time; two agents must never edit the same module in the same round.
