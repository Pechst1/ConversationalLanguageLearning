# The improvement loop

Goal: the app gets a little better every day without anyone having to remember to
test it. The walks find problems, issues hold them as a queue, the night shift fixes
as many as it can in parallel, the owner merges in the morning, the next walk checks
the fix.

```
 Berlin   02:17 scripted walk (CI, fake provider)
          03:43 live walk (Mac, real model, production)  ─┐
          04:57 explore walk (cloud, fake provider)       ├─► issues + triage → queue:ready
          06:30 night shift (cloud): plan → fix ×15 in waves of 5 → verify → digest
 morning  owner merges (ready-to-merge list first) ──► CI on main ──► Render deploys
 next     live walk checks /health release, re-tests deployed fixes, closes or reopens
```

## The two walks

| | scripted walk | explore walk |
|---|---|---|
| what | `npm run walk`, 7 days × en/de/fr, fixed answers | `npm run explore`, an agent plays as a stranger and writes its own answers |
| judges | does it work: no errors, a way forward, one verdict, no English on French screens | does it make sense: the 22 questions of `docs/ops/walk-rubric.md`, scored 1–5 per day |
| where | GitHub Actions, nightly 02:17 UTC and on demand | a Claude Code routine in a cloud session |
| cost | free (fake provider) | agent time; model calls only in live mode |
| procedure | `.github/workflows/walk.yml` | `.claude/skills/explore-walk/SKILL.md` |

Both judging walks, the cloud explore walk and the app walk on the Mac simulator,
score the same rubric, `docs/ops/walk-rubric.md`, so their numbers compare. Each report
puts the scores beside the previous walk's, which makes every question a trend line:
a fix should move its question up, and a drop flags a regression no assertion catches.

A finding from the explore walk that can be checked mechanically becomes a new
assertion in `e2e/lib/learner-walk.mjs`, so it can never come back unnoticed. That is
how the scripted walk grows.

## The queue

The open `walk-finding` issues are the queue. Every walk ends with **triage**: each
new or changed finding gets exactly one state, one lane and one size, and a comment
that starts with **Done when:** and names the check a fix must pass.

| label | meaning |
|---|---|
| `queue:ready` | reproduced, has a done-when, small enough for one night |
| `queue:working` | claimed by a night-shift agent (never two on one issue) |
| `queue:pr` | a PR that fixes it is open, or merged and waiting for the live check |
| `queue:owner` | needs the owner: a product decision, a device check, or another thread owns it |
| `lane:code` / `lane:story` | how it is fixed and proven (below) |
| `size:S` / `size:M` | one focused change / several files or one subsystem; larger work is split or goes to `queue:owner` |

`scripts/loop/loop_queue.py` does the label moves (`claim`, `release`, `mark-pr`),
lists the queue in fix order (`ready`: severity, then size, then age), creates the
labels (`ensure-labels`) and writes the digest (`digest`).

Lanes:

- **code** (UI, drills, API, copy): the PR adds the test or walk assertion that fails
  without the fix. Small ones outside the owner-only paths get `loop:merge-ready`.
- **story** (prompts, guards, authored lines): the PR adds a deterministic guard or the
  smallest prompt change, plus a test that feeds the walk's **exact** text and asserts
  it is caught. Always a draft with `needs-owner-review`. No paid model calls in tests.

## The nightly routines

1. **Live walk** (Mac, 03:43, `atelier-live-walk` scheduled task, `docs/ops/live-walk.md`):
   checks `/health` `release` against main, plays today's real day, files findings,
   re-tests the `queue:pr` issues whose PR is merged **and deployed**, closes the fixed
   ones and reopens the rest, triages.
2. **Explore walk** (cloud, 04:57, `explore-walk` skill): fake provider, two personas,
   report in `docs/ops/walks/<date>.md`, files findings, re-tests merged code-lane
   fixes, triages. It no longer fixes anything itself.
3. **Night shift** (cloud, 06:30, `night-shift` skill and `.claude/workflows/night-shift.js`):
   - plans clusters from `queue:ready` so no two agents touch the same file;
   - takes up to 3 `root-cause` issues first, each with its ready children;
   - fixes up to 15 clusters (at most 3 story) in waves of 5, each agent in its own
     worktree and branch `claude/night-<date>-<issue>`;
   - writes the test first and shows it failing on the unfixed code; before opening the PR
     the fixer runs `scripts/loop/red_green.py`, which puts every non-test change back
     to main and requires the PR's tests to fail there and pass with the fix;
   - has a second agent review every PR against the done-when and run `red_green.py`
     again; only a passing review with a proven red/green adds `loop:merge-ready`. A PR
     that fails is closed with `loop:failed-verify` (`loop_queue.py pr-reject`), and its
     issues go back to `queue:ready` with the reviewer's notes, so the next night starts
     from them; after two failed attempts an issue goes to `queue:owner`;
   - posts the digest: queue counts, tonight's PRs, the ones ready to merge, anything
     left `queue:working`, and what waits for the owner.
   With 30 or more night-shift PRs open it opens nothing new.
   Cloud sessions block GitHub GraphQL, so the loop never calls `gh issue` or `gh pr`:
   `loop_queue.py` talks REST through `gh api` and also covers reading an issue,
   commenting, opening a PR, its diff and the verifier's verdict.
   Every cloud session runs `scripts/loop/session_start.sh` on start (the SessionStart
   hook in `.claude/settings.json`): `setup_env.sh` builds the Python 3.11 venv and
   node_modules (a worktree links the main checkout's), and the local Postgres starts on
   :5432 like CI's. No fixer or verifier has to remember it.

The loop never pushes to main. By default it does not merge either: the owner merges;
for the small code fixes, `python scripts/loop/loop_queue.py merge-ready` lists the PRs whose
every check is green, that are under 400 lines and touch no owner-only path (story
engine, data model, deploy, CI, the loop's own rules), and `--merge` merges exactly
those with the owner's login, so CI runs on main and Render deploys. It merges nothing
while the newest CI run on main is red.

**Auto-merge (owner switch).** With `autoMerge: true` in the night shift's args, the
digest step runs `merge-ready --merge --max 4` itself: only code-lane PRs that the
verifier proved red/green and labelled, all checks green, under 400 lines, outside the
owner-only paths, onto a green main. Story-lane PRs always wait for the owner. The next
live walk re-tests each merged fix once it is deployed.

**Trend.** `python scripts/loop/rubric_trend.py --write` turns every walk report's score
table into `docs/ops/walks/TREND.md`: each rubric question, night by night, fake-provider
and live walks apart. The explore walk regenerates it with each report.

**Merged is not live.** Render deploys only after main's checks pass, so the live
walk compares `GET /health` → `release` (the deployed commit) with the merge commit
before it re-tests a fix.

## Live mode (owner decision)

Fake-provider walks cannot judge whether the story answers the learner: replies are
matched by keywords and the authored fallback wins. Two ways to judge it live:

- **Local stack with a model key:** add `OPENAI_API_KEY` as a secret in the cloud
  environment the routine runs in, and give `e2e/explore.mjs` a `--live` switch that
  starts the API without the fake provider (not built yet: the harness refuses live
  mode today). Cost: one season day is a handful of small classifier and
  correction calls per persona.
- **Production:** add `atelier-api-3njh.onrender.com` to the environment's allowed
  domains and allow a walk test address in `REGISTRATION_ALLOWED_EMAILS`. Tests what
  learners really get, but writes test learners into the production database.
