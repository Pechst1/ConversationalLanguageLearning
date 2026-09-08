# Copyable implementation prompt — remaining work

Written 2026-09-06 by the outgoing integration/frontend lead. Reflects the repository as
committed at `e31ef17`, plus the engine owner's in-flight uncommitted work.

---

You are the lead implementation agent for Atelier, an existing French language-learning
app. Substantial work is already committed. Your job is to finish it. Start implementing;
do not produce another plan.

Repository: `/Users/vincentpechstein/Downloads/Pixel-lab/ConversationalLanguageLearning`
Branch: `codex/serial-season-engine-production`

## Read first

`docs/implementation/atelier-v2/`: `README.md`, `CONTRACTS.md`, `CONTRACT-FREEZE.md`,
`CONTINUOUS-STORY.md`, `NEXT-STEPS-REVIEW.md`, `ENGINE-FRONTEND-CONTRACT.md`,
`FRONTEND-ENGINE-HANDOFF.md`, `BASELINE.md`, `QA-REPORT.md`, `STATUS.md`, plus applicable
repository instructions. Inspect the code; the specs describe intent, not always reality.

## Where things actually stand

Committed and verified:

| | |
|---|---|
| `b0f3602` | Daily journey functional milestone (WP-00, 02–07f, 09f, 10, 11, 12f) |
| `d83ebb0` | Claude design system, daily UI, Feuilleton reader |
| `e31ef17` | Backend host no longer guessed for credentialed calls |

Backend suite **1372 passed, 1 xfailed (deliberate), 1 pre-existing failure**. Café journey
**45/45** and interruption recovery **35/35** against the real authenticated API. Frontend
type-check, lint, build and seven test scripts pass.

**Uncommitted and in flight** (the engine owner was mid-task): `app/services/living_story.py`,
`app/api/v1/endpoints/story_engine.py`, `tests/test_living_story.py`, and edits to
`daily_journey.py`, `journey_content.py`, `journey_conversation.py`, `journey_planner.py`,
`journey_contracts.py`, `schemas/daily_journey.py`, `api.py`, `config.py`, `conftest.py`.
**Inspect and finish or reconcile this before starting anything new.** Do not discard it.

## What remains, in priority order

### 1. P1 correctness — `NEXT-STEPS-REVIEW.md` R-1 and R-2

* **R-1 — negation earns success.** "Je ne veux pas de café. Je ne veux pas rester en
  terrasse." grades `met` with `served_at_terrace`. The deterministic grader treats any
  mention of a drink or place as positive intent, so it contradicts the learner and feeds a
  false success downstream. Handle negation, refusal, correction of a prior choice, and
  ambiguity across turns. Do **not** fix it with one string special-case or by rejecting
  every sentence containing `pas`. Add regressions for all three families and an API-level
  check that a rejected or ambiguous choice cannot mint capability evidence or a reward.
* **R-2 — a model can reverse the learner's choice.** A schema-valid reply with a
  *different allowed* `outcome_key` replaces the grounded one. Reject output that conflicts
  with an established choice; validate reply and consequence together.

### 2. P1 — WP-14 continuous story (`CONTINUOUS-STORY.md`, 14A–14F)

Generated situations inside one continuing story, including opportunities emerging from
conversation. Includes **R-3 / D-1b**, still an honest `xfail`:
`recap.story_outcome.callback_fr` is produced and stored but **never read back**, so day 2
references nothing the learner did on day 1. Scenario rotation does not satisfy this.
Assert semantic grounding and provenance, not verbatim insertion. Remove the marker only
when it genuinely works.

### 3. Frontend remaining

* **WP-08** companion screens and navigation; **WP-09 visual** notebook. The design
  specifies Lexique, Cahier, Missions and Réglages fully — see `FRONTEND-ENGINE-HANDOFF.md`
  §1 for exact tokens, radii and press physics, and build from
  `components/atelier-v2/ui/`. Do not introduce alternate buttons, fonts or sheets.
* **Interactive verification on authenticated routes**: panel next/prev, word help and
  return, resume, stale-scene 409. Everything needed is in place — read §8 first.
* The design's font family aliasing (`AtelierSerif`/`AtelierSans`) should be reversed to
  the real names **as part of WP-08**, once legacy surfaces are migrated deliberately.

### 4. Release blockers that are not features

* **CI is red from three pre-existing failures**, none caused by this work, all documented
  in `BASELINE.md`: `ruff check .` (11 findings, 9 auto-fixable), `alembic downgrade base`
  (`grammar_enhancements` drops `grammar_longest_streak` twice), and
  `test_grammar_notebook` (55 vs 54 denominator). A red gate does not pass because its
  origin is documented.
* **`pages/api/proxy/stories/[...params].ts`** still defaults to `http://localhost:8000` —
  a different project on this machine — and is a server-side proxy. Same for
  `services/api.ts`, `services/websocket.ts`, `scripts/capture-mobile-states.mjs` (QA
  defect D-8), `lib/native-auth.ts`. `lib/api-host.ts` is the pattern to follow.
* **Auth hydration gap**: the sign-in form has no native-safe submit; a scripted submit put
  credentials in a GET URL before hydration.

### 5. Gates never executed — mark pending, never assume

Live-model content and correction quality (**no provider has ever been enabled**; bounded
protocol in `QA-REPORT.md` §9), real voice transcription, physical device and native
lifecycle, `build:native` on device, `capture:mobile`, Docker build, and the prepared
five-learner study (materials written, nobody contacted).

## Traps that already cost this project time — do not repeat them

1. **The design's PNGs are the BEFORE.** `docs/design-reference/claude/ref/*.png` are board
   0, "Current build, recreated from source — for reference". An earlier pass briefed two
   agents to reproduce exactly what the design criticises. **Read the `.dc.html` text.**
   `Atelier App.dc.html` is the resolved design and implements home direction 1a.
2. **The Browser pane is hidden, so `requestAnimationFrame`/`requestIdleCallback` never
   fire and Next never hydrates.** An unhydrated page measures as "0 controls, 0 overflow",
   which reads as a clean pass. Before trusting any browser measurement, assert
   `reactMounted`, and force a render with
   `await window.next.router.replace(window.next.router.asPath)`. See §8 of the handoff.
3. **CI builds without `API_URL`.** A naive fail-fast turns the pipeline permanently red.
   Guard the dangerous capability, not the application's behaviour — an earlier provider
   guard forced feature flags off and broke seven unrelated tests.
4. **Port 8000 belongs to a different project.** Never bind, kill, or default to it. The
   backend is 8010.
5. **The baseline is a dirty worktree.** Never `git reset`, `git checkout -- .`,
   `git clean`, or `git stash`. Stage explicitly; another agent's work is often in flight.
6. **Never migrate or write to the `language_learning` database.** Use `createdb`/`dropdb`
   throwaways and drop them after.
7. **`.env` holds a live `sk-` key** and `app/config.py` loads it. The root `conftest.py`
   neutralises credentials for pytest only — **outside pytest you can still spend money.**
   Never weaken that guard and never add feature-flag defaults to it.

## The failure mode this project actually has

Every package passed its own tests while the two worst defects lived **in the seams**: the
café had no ending for a learner who fails, so a failing learner was shown a success; and
the recap and capability endpoint used two different rubrics and disagreed about the same
journey. Both were found by typing nonsense into the real API and reading what came back,
not by a test suite.

So: **drive the real thing and read what it says.** Ask whether one surface contradicts
another, or claims something the learner's behaviour does not support. Then encode the
answer as a cross-package test — `tests/test_journey_contract_parity.py` is where those
live, and it is what caught the second instance of the missing-honest-ending bug after the
first was found by hand.

## Non-negotiable

Reuse existing SRS, evidence, error-memory, story, audio and telemetry services. Preserve
authentication, ownership checks, learner history, legacy sessions and optional tools.
Narrative content and character replies come from AI generation — never scripted dialogue,
canned endings, fabricated streaks, invented durations, or mock data presented as real.
When generation fails, preserve the learner's work and show an honest loading/retry/
unavailable state. Retries and completion stay idempotent.

Report actual results, with real output. Mark unexecuted gates pending rather than passed.
The feature stays default-off; do not deploy or enable production.
