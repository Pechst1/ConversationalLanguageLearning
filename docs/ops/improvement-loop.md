# The improvement loop

Goal: the app gets a little better every day without anyone having to remember to
test it. Two walks find problems, issues hold them, small PRs fix them, the next walk
checks the fix.

```
 nightly (after the scripted walk)            on every PR
 ┌──────────────────────────────┐            ┌───────────────────────┐
 │ 1. scripted walk (CI)        │            │ scripted walk (CI)    │
 │ 2. explore walk, 2 personas  │            │ catches regressions   │
 │ 3. rank → issues             │            └───────────────────────┘
 │ 4. re-test merged fixes      │
 │ 5. fix top finding → draft PR│──► owner reviews and merges ──► Render deploys
 └──────────────────────────────┘                                        │
            ▲────────────────────── next night re-tests ◄────────────────┘
```

## The two walks

| | scripted walk | explore walk |
|---|---|---|
| what | `npm run walk`, 7 days × en/de/fr, fixed answers | `npm run explore`, an agent plays as a stranger and writes its own answers |
| judges | does it work: no errors, a way forward, one verdict, no English on French screens | does it make sense: orientation, task sense, reaction to what was written, consistency |
| where | GitHub Actions, nightly 02:17 UTC and on demand | a Claude Code routine in a cloud session |
| cost | free (fake provider) | agent time; model calls only in live mode |
| procedure | `.github/workflows/walk.yml` | `.claude/skills/explore-walk/SKILL.md` |

A finding from the explore walk that can be checked mechanically becomes a new
assertion in `e2e/lib/learner-walk.mjs`, so it can never come back unnoticed. That is
how the scripted walk grows.

## The nightly routine

A Claude Code routine fires a fresh cloud session each night and runs:

1. Pull `main`, read the last scripted walk's summary.
2. Run the explore walk (`explore-walk` skill) for two personas, rotating the third.
3. File or update `walk-finding` issues, ranked; write `docs/ops/walks/<date>.md`.
4. Re-test the issues whose fix merged; close the fixed ones with a screenshot.
5. Take the top finding that is small and not in the story engine, fix it on a
   branch, add the assertion that would have caught it, run the fast checks and the
   scripted walk, open a **draft** PR. It never merges and never deploys.
6. Story-engine findings get the `area:story-engine` label and go to whoever owns the
   story work, not into a quick fix.

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
