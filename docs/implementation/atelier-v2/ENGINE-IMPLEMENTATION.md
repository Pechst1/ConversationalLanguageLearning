# Living-story engine — implementation handoff

2026-09-06. Backend owner: Codex. UI owner: the separate Claude design implementation agent.

## Implemented behavior

New daily journeys ask an AI director for a short, original situation in the existing world. The director receives the current chapter, actual past events, unresolved promises, relationships, the current legacy beat when applicable, and recent situations to avoid repeating. It writes two to five cinematic panels, an opening, a communicative objective, and localized help. A second model call reviews the proposal before anything is published. Cast and location IDs, source references, chapter continuity and length also have deterministic validation.

The learner's response goes to an AI semantic interpreter and another independent review call. The interpreter handles the whole exchange, including refusal, negation, revised choices and new proposals. It produces the character's reply, an honest ending, exact learner evidence quotes, and proposed commitments. Models propose; ownership, provenance checks, the existing learning policy and a transaction decide what becomes durable. The critic is a separate call to the configured provider, not an independently trained model; it reduces risk but cannot guarantee semantic accuracy.

Canon stays in `SerialThread.state`, extended with `living_story`. Generated episodes use the existing `SerialEpisode`, `GraphicNovelScene` and `GraphicNovelPanel` tables. Completed exchanges update relationships and story memory through that same spine. The reader and the conversation resolve to the same immutable scene and journey IDs. Existing active legacy episodes are preserved; a generated daily side scene can share their thread without falsely completing them.

Chapters have a durable identity and a question that stays open until an actual exchange resolves it. The next scene then opens a new chapter rooted in the aftermath. Recent events and premises are bounded; unresolved commitments survive the rolling window. Historical scenes and recaps remain in the database. This is useful continuity, not unlimited perfect recall: the director sees the last 40 event sources and recent summaries, plus open commitments. There is no semantic search over every old episode yet.

Reading position is stored separately from plot progress. Navigation, replay, and word help do not complete scenes or award learning credit. Exact mutation retries use the existing durable receipts. A late canonical conflict rolls back the response, revision and learning effects. Legacy completion and image-rendering paths cannot reopen or complete engine scenes.

## Files and boundaries

- `app/services/living_story.py`: typed proposals, director/interpreter/critic prompts, validation, context, canonical publication and settlement.
- `app/services/daily_journey.py`, `journey_content.py`, `journey_conversation.py`, `journey_planner.py`: integrate the engine into the existing controller and learning policy.
- `app/services/serial.py`: shared locking, compatibility and public projections; prevents a second generator from advancing engine-managed stories.
- `app/api/v1/endpoints/story_engine.py`: owned episode reads, journey lookup, pagination and position writes.
- `web-frontend/types/daily-journey.ts`, `services/api.ts`, `services/daily-journey.ts`: shared types and transport. No redesign of the frontend owner's presentation files.
- `tests/test_living_story.py`: assembled daily API + real SQLite model tests with an injected provider. No real credentials.
- `scripts/review_living_story.py`: separate opt-in, maximum 12-request synthetic prose sample, no application DB connection. Without `--live` it makes no requests.

No migration is required: existing JSON state and scene tables are reused. No production flags or learner database records were changed.

## Configuration and failure behavior

The existing `ATELIER_DAILY_JOURNEY_ENABLED` and cohort gate control rollout; the flag remains false in the current configuration. `ATELIER_STORY_ENGINE_ENABLED` defaults true for new journeys when the daily gate is enabled. Legacy fixture tests explicitly select the authored compatibility path. `ATELIER_LLM_ENABLED=false` makes new scene generation unavailable; it does not silently select scripted scenes. Existing pinned journeys still resume.

`ATELIER_STORY_MAX_ATTEMPTS` defaults to two. Each draft and turn needs an independent review. Calls disable provider retries and cascaded provider fallback, use an 18-second network timeout, and reject results after the 75-second operation budget, leaving headroom under the 90-second journey claim. A network timeout is a per-operation socket timeout, not a hard process kill; late results are still discarded and revision/claim checks remain authoritative.

Provider failures or rejected interpretations return the existing unavailable/pending states. They never consume a learner turn or fabricate a reply. Explicit early exit produces an abandoned scene with no invented narrative ending. Generated objectives are opaque IDs; only an explicitly validated mapping to a registered capability can contribute to that capability. Novel goals never create arbitrary mastery categories.

Usage metadata records model/provider/tokens/estimated cost and stage without raw dialogue. This is diagnostic accounting, not a billing ledger: provider failures without usage and rolled-back transactions can leave unrecorded charges. Model quality and actual cost coverage need the live review.

## Verification and remaining gates

- Fourteen simulated daily journeys carry actual persisted events and commitments forward, resolve chapters and start new chapters. This proves state transitions with an injected provider, not fourteen days of real prose quality.
- Owned reader access, saved position, retry without duplicate story events, semantic-review rejection, fabricated-quote rejection, canonical ID validation, legacy route guards, late-conflict rollback and authored callback migration are covered.
- After fixing a lock-refresh regression, the engine/provider/story-outcome group passes **48 tests**. The broader compatibility runs and final totals are recorded below as they complete.
- Frontend TypeScript check passes with the new types and API methods.
- Full suite before the lock-refresh fix: **1371 passed, 15 failed, 1 xfailed**. Three engine-related legacy-ledger failures are now fixed and their complete module passes. Eleven failures are source assertions affected by the parallel frontend redesign; one is the previously documented grammar-summary 55-versus-54 failure. The whole repository is not green.
- Live generated prose review: prepared, explicit paid-call consent requested; not yet run. PostgreSQL row-lock races for the new story writer have not been exercised; existing SQLite concurrent daily-controller tests do not prove those locks.
- New panels currently use existing location art, explicitly labeled `setting_reference`. Their narration/dialogue/visual directions are AI-generated. Distinct AI illustrations per panel and full visual continuity are not implemented by this change.
- Frontend must connect its immersive reader to the shared episode API and the existing daily controller, as specified in `ENGINE-FRONTEND-CONTRACT.md`. Current frontend reader tests cover its older scene API, not this new integration.

Do not mark WP-14 or rollout complete until reader integration, real-provider prose review, concurrency verification and the combined release gates pass.

## Verification pass — 2026-09-06 (evening), continuing agent

Actual results, no paid calls. Both new tools live in `scripts/` and refuse the owner's `language_learning` database.

- **Combined suite after the frontend owner's test updates:** `pytest tests/` → 1 xfail (D-1b, authored path), and **3 failures**: the documented grammar-notebook 55-vs-54 baseline, plus `test_frontend_serial_surfaces` and `test_mobile_capture_harness` source assertions on `pages/serial/cast.tsx`, which the frontend owner was editing during the run (the failing assertion changed between two runs). Not engine-related. `tests/test_living_story.py` **12 passed**; the seven source-assertion modules listed above passed when run on their own.
- **PostgreSQL lock races — PASSED 33/33.** `scripts/verify_story_engine_pg.py` against `scripts/dev_story_engine_server.py` (real HTTP, throwaway PostgreSQL 15 database `atelier_story_pg_1788716642`, fake provider). Six concurrent creates → one journey, one thread, one episode, one scene; six identical-retry attempts fired at the same instant as three position writes → exactly one story event, scene completed once with its source key, `panel_index` not lost; stale-revision retries all 409; six concurrent finishes → one 200, one completed learning session, cursor advanced by exactly one; two learners creating simultaneously get distinct threads; the legacy `POST /graphic-novel/scenes` returns 409 `story_journey_required`. Second create after completion mints no new scene.
- **Browser walk on the authenticated route — PASSED, one frontend defect found.** Signed-in dev account, `/atelier` → Start today → the engine scene rendered in the immersive reader (3 panels, chapter, `setting_reference` label, Précédent/Suivant); Next twice → `PUT …/position` 200 and `panel_index=2` in the database; reload → Home shows "Continue today" and the reader reopens at 3/3; Continue → respond step with the engine's opening line; answer sent → "Merci ! On fait ça ensemble." → resolution "Vous promettez de venir aider."; `/graphic-novel?scene=<engine id>` → legacy GET 409 → replay-only projection; `/serial` lists "Épisode 1 · lu · Vous avez promis d'aider samedi." linking to that projection; `/serial/today` carries `story_engine`, `continue_href: /atelier`, `episodes_href`.
- **Defect (frontend owner): the auto-finish after the last step sends a stale revision.** `useDailyJourney.ts` `continueJourney` awaits `advance()` and then calls `finish('complete')`, but `finish` closes over the pre-advance `journey` (`const target = journey`), so the request carries the old `expected_revision` → 409 `journey_version_conflict`. Recovery refreshes, the journey is `active` with `current_step_id: null` and no recap, and the session renders an empty "Step 3 of 3" with no retry; Home then offers "Continue today" for a day that cannot continue. Finishing with the current revision through the API succeeds and the recap carries `story_outcome.callback_fr`. The server side is correct (the race driver finishes the same sequence). Fix: finish with the `advanced` snapshot's revision, and give the renderer an honest state for "all steps done, not finished".
- **Additive projection field:** every dialogue line now carries `character_name` from the owning thread's world bible (`null` when unknown). The reader currently labels unknown ids by capitalising the raw id ("Marin_leveque"); use the field instead of a client-side name table.
- **Still open:** real-provider prose review (`scripts/review_living_story.py --live`, needs explicit paid-call consent); R-1 on the authored grader still reproduces ("Je ne veux pas de café. Je ne veux pas rester en terrasse." → `met`, `served_at_terrace`); R-2's key override is blocked on the authored path; D-1b remains an honest `xfail` for the authored path — the engine path feeds prior events and commitments to the director (covered by the fourteen-day test), which is the intended replacement.

## Live prose review — 2026-09-06 (evening), owner-authorised paid calls

`scripts/review_living_story.py --live` (synthetic context, no database), `gpt-5-mini`, eight bounded runs, **~90 requests, about US$0.15 in total**. Reports: `var/reviews/atelier-story-review-2026-09-06*.json` (run 7 is the complete three-scene sample; run 8 has two scenes plus a capped third). The script now takes `--attempts` (production uses 2) and `--max-requests`.

**Defects found and fixed in `living_story.py` during the review (each backed by the sample that exposed it):**

| # | Observed live | Fix |
|---|---|---|
| 1 | Director call timed out at 18 s; with default reasoning effort `gpt-5-mini` spends the 2,500-token budget on reasoning and returns **no content** after ~25 s | `reasoning_effort="low"` (valid draft in ~10–15 s); per-call window 25 s inside the unchanged 75 s budget (`REQUEST_TIMEOUT_SECONDS`, `OPERATION_BUDGET_SECONDS`) |
| 2 | Character reply was a verbatim copy of the learner's sentence; critic accepted it | deterministic `reply_echoes_learner` guard (case/punctuation-insensitive) + actor prompt |
| 3 | Corrections manufactured on correct answers ("split into two questions", "10h → 10 h") | actor prompt: only real errors, never style or typography; span verbatim |
| 4 | Critic rejected a valid refusal because the learner wrote *vous* to friends | critic prompt: the learner's own register/spelling is never grounds for rejection |
| 5 | Director once chose `you` (the learner) as `character_id`; validator caught it but the retry feedback was opaque | director prompt names the id rules explicitly |
| 6 | Two attempts lost to `unknown_learning_target` with an empty target list | invented target ids are now ignored (observations were already filtered to the task's targets, so no credit could ever leak) |
| 7 | Critic returned `accepted` with an advisory "consider adding a note"; the loop treated any non-empty `issues` as rejection | an accepted review passes; issues feed retries only on rejection |
| 8 | Director invented a past learner promise on day 1 ("tu avais dit 18h") with no event; suggested reply was a slash-separated list of three alternatives | director prompt: nothing before the first event, one single suggested sentence; critic rejects references to unrecorded learner promises |
| 9 | Refusal turn twice missed `resolution_fr`/`summary_native` because the actor treated the exchange as still open | actor prompt: one exchange per scene, every non-clarifying reply ends it |
| 10 | Days 2 and 3 replayed day 1 ("first order at the counter") and re-used a chapter day 1 had resolved; the self-reported `novelty_key` differed each time | `chapter_not_advanced` (resolved chapter's question may not return) and a premise-overlap check (Jaccard ≥ 0.6 on content words over the last five situations) |

Engine tests updated for 2, 10 (`tests/test_living_story.py`).

**What the final samples look like (run 7, run 8):** natural, in-character French (Lila's teasing, Margaux's terse "Tu veux quoi ?"), an honest `not_yet` with a coherent character response and an open chapter when the learner refuses, day 2 and day 3 citing the actual prior event ids, no manufactured corrections, commitments extracted only from explicit learner offers. Cost per scene (draft + review + turn + review) ≈ US$0.007; latency ≈ 10–13 s draft, 2–3 s review, 6–7 s turn — inside the 75 s budget with one retry.

**Still observed, not fixed (owner decisions or later work):**

- **Situational variety is narrow.** Even with the overlap rule, a learner with no history is steered to "order at the Mistral" first; run 8 day 2 opened a new chapter but stayed at the same counter. The synthetic context has no learner needs, so the director defaults to the café. Real journeys carry planner targets; judge variety on the 14-session longitudinal run, not this sample.
- **Learner gender is not known to the engine**; the cast alternates *ma puce* / *mon grand* / *elle*, and once resorted to inclusive spelling (*trempé·e*, *mystérieux·se*), which is unreadable at A1. Needs a learner-profile field or a prompt rule to avoid gendered address.
- **Register:** Lila's world-bible voice includes affectionate *putain*; it appeared once in a reply to an A1 learner. Product decision, not a defect.
- **Narration says *vous*, dialogue says *tu*** in several premises. Cosmetic; a director rule could align them.
- The critic is a second call to the same model. It caught nothing on its own in these runs that the deterministic rules did not; its value is unproven, its cost is ~25% of each scene.
- This sample validates prompts and guards, not fourteen days of real prose; the 14-session run with a real provider remains WP-14F's job.

## WP-14F follow-up — 2026-09-07 (living-story-v2)

[WP14F-REPORT.md](WP14F-REPORT.md) (independent QA, 23 deterministic tests in `tests/test_living_story_longitudinal.py`, five live runs ≈ US$0.42) judged the generation obligation unmet: 34 of 47 simulated days produced no usable scene. Fixes applied the same day in `living_story.py`, prompt revision bumped to **living-story-v2** (reader and legacy guards now match on the `living-story-` prefix, so v1 scenes stay readable):

| Finding | Fix |
|---|---|
| L-1 director cites situation ids as sources, whole day lost | recent situations reach the director without ids; unknown source ids are dropped, not fatal |
| L-2 same task reworded for five days | objectives are part of the repetition check (Jaccard ≥ 0.6 on the last five); director asked for a new development per scene and to vary character and location |
| L-3 reply recites the private suggested answer | deterministic `reply_leaks_suggestion` guard |
| L-4 no commitments recorded | actor prompt names when a learner promise becomes a commitment |
| L-5 learner's proposal credited to a character | critic rejects authorship inversion |
| L-6 gendered address violated | deterministic `inclusive_dot_form` / `gendered_address` guards on every learner-facing text, keyed to the Settings preference |
| L-6b/L-7 B1 served A1 drills; replies above level | director level guidance per band; `reply_above_level` bound (A1 40 words, A2 60) |
| L-8 "Désolé" from Margaux | cast projection carries `gender` from the world bible |
| L-9 wrong error corrected | correction priority: structural before cosmetic |
| L-10 a mismatched refusal became an outage | critic: the learner's own turn is evidence; time/place mismatch is clarification; a clarifying turn drops state changes instead of failing |

Verbatim-quote check now ignores punctuation and case (day 3 of the confirmation run had failed on "19h" vs "19 h").

**Confirmation run** (`scripts/longitudinal_story_review.py --level A1 --address neutral --days 14 --attempts 2`, 59 requests, US$0.14): **9 of 13 non-skipped days accepted** (before the fixes: 1 of 13 in the comparable A1 run), 9 distinct premises, 5 commitments recorded from the learner's words, outcomes 5 met / 4 not_yet, median request 9 s, max 16 s, no request errors. The four lost days were one proposal during a clarification (since made non-fatal), one punctuation-only quote mismatch (since relaxed), one off-topic answer where the reply leaked the suggestion twice (guard working as intended), and one critic rejection of a refusal (critic prompt since clarified). Still narrow: all 14 days at Le Mistral with Lila only, one chapter. Real 14-day variety with the v2 prompts is not yet demonstrated; that is the next paid run.

## WP-17 (14G) — 2026-09-07 deterministic pass

Story-engine agent, **no paid calls in this pass**. Everything below is deterministic
work that had to exist before the fourteen-day paid runs are worth buying. Prompt
revision stays `living-story-v2` (no reader/guard change); the director and actor system
prompts gained rules, the guards behind them are new.

### What changed

| # | Change | Where |
|---|---|---|
| 1 | **Location and character rotation, data-driven from the world bible.** `story_context` now carries `variety`: every cast id and location id from the bible, the ones unused in the last six situations, the last five (character, location) pairs, and `must_change` when the last `PAIR_REPEAT_LIMIT` (3) situations all used one pair. The director prompt is told to rotate and to obey `must_change`; `_validate_scene` rejects a fourth scene on the same pair with `setting_not_rotated`. | `living_story._variety`, `story_context`, `DIRECTOR` |
| 2 | **Chapter turnover.** A chapter now also ends when the learner has resolved `CHAPTER_RESOLVED_COMMITMENT_LIMIT` (3) commitments inside it (`chapter_state()` exposes `exhausted`), not only when the model says `chapter_resolved`. `bind_journey` retires the closing chapter's question into `living_story.resolved_chapter_questions` and mints a new chapter. `chapter_not_advanced` now rejects any draft whose dramatic question repeats — or is a 0.6-Jaccard rewording of — *any* retired question, not just the last one. | `living_story.chapter_state`, `_validate_scene`, `bind_journey`, `settle_resolution` |
| 3 | **Premise overlap on the triple.** In addition to the content-word Jaccard on premise and objective (≥ 0.6), a draft is rejected as `repeated_premise_triple` when a situation in the last five had the *same character in the same location* with an objective overlapping ≥ 0.4. Same person, same place, same ask is one situation however it is reworded. | `living_story._validate_scene` |
| 4 | **Register.** Below B1 the cast projection is stripped of coarse vocabulary (`_cast_for_level`, `VULGAR_TERMS`): Lila keeps her *putain* in the bible, an A1/A2 learner never sees it, and `vulgar_register` rejects any learner-facing scene or reply text that carries one at those levels. Narration and the addressed character must use one register: `mixed_address_register` rejects narration in *vous* with dialogue in *tu* (and the reverse); an ambiguous passage with both markers — a plural *vous* to a group — is not a signal and is never rejected. A director rule and an actor rule state both. | `living_story._check_register`, `_check_scene_address_register`, `DIRECTOR`, `ACTOR` |
| 5 | **Cost ledger.** Per-call `journey_story_model_call` rows are now zero-cost diagnostics carrying `call_cost_usd`; each accepted artifact gets exactly one cost-bearing row — `journey_story_scene_cost` (draft + critic, all attempts) in `bind_journey`, `journey_story_turn_cost` in `settle_resolution` — and a failed generation writes `journey_story_generation_failed` with what it spent, so no attempt's spend is lost or counted twice. Both rows are written inside the transaction that publishes the artifact, so a rollback (late canonical conflict) takes the row with it: **no phantom rows**. The same amounts are written to `scene.script_payload.estimated_cost`, which is what `SerialGenerationCostService.weekly_rollup` and `PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD` read — the weekly guardrail now covers engine scenes. `pilot_events.daily_rollup` skips the two scene-attributed event types when summing so the daily report does not count the same dollar twice. | `living_story._approved`, `_record_cost`, `bind_journey`, `settle_resolution`, `pilot_events` |
| 6 | **Critic A/B preparation.** `living_story.CRITIC_ENABLED` (module flag, never a persisted setting) and `scripts/longitudinal_story_review.py --no-critic` run the whole loop with the deterministic guards and no review call — two requests per day instead of four. Not run live in this pass. | `living_story._approved`, `scripts/longitudinal_story_review.py` |

`scripts/longitudinal_story_review.py` also now mirrors the real context exactly: the
level-filtered cast with `gender`, `level_register`, `variety` recomputed per day, the
chapter's `exhausted` view, retired chapter questions, and situations that record
`objective_native`, `character_id` and `location_id` (without them the rotation and
triple checks were blind in the review harness).

### Tests

New deterministic tests with the fake provider — 7 in `tests/test_living_story.py`
(world-bible variety in the director context; three-scene rotation and both ways out of
it; the (character, location, objective) triple; chapter exhaustion by resolved
commitments; retired questions never returning; Lila's *putain* stripped below B1 and
rejected in generated text while B1 keeps it; narration/dialogue register alignment
including the ambiguous plural case) plus 3 for the ledger (one row per accepted
scene/turn with the amounts the weekly rollup reads; no phantom row after a 409
rollback; a rejected generation still recorded) and 1 for `--no-critic`. 2 new tests in
`tests/test_living_story_longitudinal.py` drive the assembled API for fourteen days and
assert ≥ 3 locations, ≥ 3 characters, ≥ 2 chapters, no three consecutive scenes on one
pair, and a chapter closing on resolved commitments alone.

```
.venv/bin/python -m pytest tests/test_living_story.py tests/test_living_story_longitudinal.py \
    tests/test_journey_story_outcomes.py tests/test_daily_journey_api.py
117 passed in 36.68s

.venv/bin/python -m pytest tests/test_pilot_work_packages.py tests/test_journey_events.py \
    tests/test_journey_content.py tests/test_serial_costs.py tests/test_analytics.py
116 passed in 1.84s

.venv/bin/ruff check app/services/living_story.py scripts tests/test_living_story*.py
All checks passed!
```

A wider regression selection also passes — `pytest tests -k "journey or serial or story
or pilot or graphic"` → **1032 passed, 546 deselected in 130.44s**. The repository as a
whole is still not green for the reasons recorded in the earlier passes, none of them
engine-related.

The review script itself was exercised end to end with the scripted fake provider
(6 days, 20 requests with the critic, 10 without) — no live request was made anywhere in
this pass.

### The paid runs the owner should now buy

Four runs, all from the repository root with the repo `.venv`. `--max-requests` is a hard
stop inside the script, so each run's ceiling is exact. At the measured `gpt-5-mini`
rate (≈ US$0.0035 per request, ≈ US$0.014 per full day with the critic) the four runs
together are **≈ US$0.60, ceiling US$0.85** at 240 requests total.

```bash
# A1, with the critic (baseline; 14 days, 4 requests/day + retries)
.venv/bin/python scripts/longitudinal_story_review.py --live --level A1 --address neutral \
    --days 14 --attempts 2 --max-requests 70 \
    --output var/reviews/atelier-longitudinal-A1-critic.json

# A2, with the critic
.venv/bin/python scripts/longitudinal_story_review.py --live --level A2 --address neutral \
    --days 14 --attempts 2 --max-requests 70 \
    --output var/reviews/atelier-longitudinal-A2-critic.json

# A1, without the critic (the A/B half; 2 requests/day)
.venv/bin/python scripts/longitudinal_story_review.py --live --level A1 --address neutral \
    --days 14 --attempts 2 --no-critic --max-requests 50 \
    --output var/reviews/atelier-longitudinal-A1-nocritic.json

# A2, without the critic
.venv/bin/python scripts/longitudinal_story_review.py --live --level A2 --address neutral \
    --days 14 --attempts 2 --no-critic --max-requests 50 \
    --output var/reviews/atelier-longitudinal-A2-nocritic.json
```

Each run writes its own report; `summary.estimated_cost_usd` is the actual spend. Stop
and report rather than re-running if a run ends with `stopped_early:
review_request_limit`.

### Acceptance thresholds (WP-17)

Read them off `summary` in each report:

- ≥ **11 of 14** accepted days at each level (`days_accepted`, with `days_skipped` = 1 by
  the scripted behaviour, so ≥ 11 of the 13 non-skipped days);
- ≥ **3 distinct locations** and ≥ **3 distinct characters** across the run
  (`distinct_locations`, `distinct_characters`);
- ≥ **2 chapters** (`chapters`);
- **median request < 12 s** (`median_request_seconds`);
- cost per learner-day recorded in the ledger — in production this is now the
  `journey_story_scene_cost` / `journey_story_turn_cost` rows and the scene's
  `estimated_cost`; in the review harness it is `estimated_cost_usd / days_accepted`;
- the critic keeps its ~25 % of each scene's cost **only** if the with-critic runs reject
  something the deterministic guards missed. Compare `days_failed` and the rejection
  reasons in `requests[]` between the two halves and record the answer either way.

## WP-17 paid runs — 2026-09-07

Owner-authorised, four runs, `gpt-5-mini`, **US$0.4463 in total** (164 requests), reports
in `var/reviews/atelier-longitudinal-{A1,A2}-{critic,nocritic}.json`. Fourteen simulated
days each, one scripted skip, so thirteen days can be judged.

| run | accepted (≥ 11/13) | locations (≥ 3) | characters (≥ 3) | chapters (≥ 2) | median request (< 12 s) | requests | cost | cost / accepted day |
|---|---|---|---|---|---|---|---|---|
| A1 + critic | **12/13** ✓ | 7 ✓ | 5 ✓ | **1** ✗ | 10.7 s ✓ | 61 | $0.1420 | $0.0118 |
| A2 + critic | **6/13** ✗ | 5 ✓ | 5 ✓ | 3 ✓ | 17.1 s ✗ | 47 | $0.1274 | $0.0212 |
| A1 no critic | **12/13** ✓ | 7 ✓ | 5 ✓ | **1** ✗ | 18.2 s ✗ | 29 | $0.0870 | $0.0072 |
| A2 no critic | **12/13** ✓ | 5 ✓ | 5 ✓ | 3 ✓ | 18.6 s ✗ | 27 | $0.0899 | $0.0075 |

Distinct premises: 12, 6, 12, 12 (a day's premise is never a reworded twin of the last
five). The single lost day in each of the three 12/13 runs was a guard doing its job:
`repeated_situation` (A1 both runs, day 12) and `gendered_address` (A2 no critic, day 12).
The A2 + critic run lost seven, which is what the rest of this section is about.

### Latency: the blended median is the wrong metric

The `< 12 s` threshold was set on `summary.median_request_seconds`, which is the median
over *all* requests — and the critic's reviews are the fast ones (4-5 s), so adding the
critic **lowers** the number while making the learner wait longer. Per stage:

| run | draft (p50 / max) | turn (p50 / max) | review (p50) | learner wait: scene | learner wait: whole day |
|---|---|---|---|---|---|
| A1 + critic | 20.5 s / 25.0 s | 13.5 s / 17.7 s | 4.2-5.2 s | ≈ 25.8 s | ≈ 43.4 s |
| A2 + critic | 21.8 s / 24.4 s | 14.6 s / 18.3 s | 4.6-5.1 s | ≈ 26.9 s | ≈ 46.1 s |
| A1 no critic | 20.8 s / 25.0 s | 13.5 s / 21.2 s | — | ≈ 20.8 s | ≈ 34.3 s |
| A2 no critic | 19.8 s / 24.4 s | 14.9 s / 22.3 s | — | ≈ 19.8 s | ≈ 34.7 s |

The draft call is the same ~20-22 s in every run; the "10.7 s vs 18.2 s" difference
between the A1 runs is entirely the critic's fast calls entering the median. **The
threshold belongs on the two stages the learner actually waits for**, measured
separately: draft p50 and p95 (the scene the journey blocks on) and turn p50/p95, plus
the end-to-end operation including retries. As a first proposal from these numbers:
draft p50 < 22 s and p95 < 25 s, turn p50 < 16 s, scene generation end-to-end < 30 s —
all well inside `OPERATION_BUDGET_SECONDS` (75 s), but note the draft p50 is already
close to the 25 s `REQUEST_TIMEOUT_SECONDS`, which is what the six request errors across
the four runs look like. That window, not the model, is the next latency risk.

**Variety is fixed; turnover and repetition are not.** WP-17's rotation work did what it
was for: 5 of 5 cast members and 5-7 locations in every run, 12 distinct premises in
three of the four (against fourteen days at one counter with one character in the WP-14F
confirmation run). Two thresholds were missed, and both had a real cause, not a threshold
problem. Median latency is provider-side variance around a 25 s per-call window: the
first run of the batch measured 10.7 s and the three later ones 17-19 s with the same
prompts.

### Defects the paid runs exposed, and the fixes (all in `living_story.py`)

| # | Observed live | Fix |
|---|---|---|
| P-1 | **A2 lost five consecutive days re-proposing one scene.** Days 9-12 and 14 were literally "Marin proposes to call the seller", reworded, twice per day. The retry only ever saw the opaque token `repeated_premise_triple`, so the model answered a repetition refusal by rewording the same scene, once moving to `ngo_office` while keeping the same objective. | `StoryUnavailable` now carries a `hint`; every repetition/rotation/chapter guard names the offending character, location and objective, the objectives already used, and the ids still free (`_variety_hint`). `_approved` feeds `reason: hint` into `previous_rejections`, and the recorded machine reason is unchanged. `variety.used_objectives` puts the same facts in the context *before* the first attempt, and the director prompt is told to obey `previous_rejections` literally. |
| P-2 | **The 0.4 objective-overlap threshold was not the problem.** The rejected drafts were the same scene, not similar-but-different A2 objectives, so loosening the guard would only have let repeats through. | Threshold kept at 0.4 for the triple and 0.6 for plain content words. |
| P-3 | **A1 spent all twelve accepted days in one chapter, with no commitment ever recorded.** Ten of twelve days ended `needs_clarification`, which correctly drops commitments and chapter closure — so neither turnover trigger could ever fire. The cause is upstream: A1 objectives chained three asks ("accept or decline, give a reason about budget or schedule, **and** ask for the meeting time and place"), which one A1 sentence cannot satisfy. | `_check_objective_scope`: at A1 one clause separator and ≤ 16 words, at A2 two and ≤ 24; B1/B2 unrestricted. Director prompt states the same rule. |
| P-4 | A chapter with no promises and no resolution never ends. | Third deterministic turnover trigger: `CHAPTER_MAX_SCENES = 5` scenes exhausts a chapter regardless of commitments or `chapter_resolved`. |
| P-5 | **A2 ended with two open commitments for one promise** ("Venir dimanche au marché et se retrouver à 11h au pont." and, six days later, "Tu viens dimanche au marché."). | `_same_promise` merges a restatement of an **open** commitment (content-word containment ≥ 0.6, ≥ 2 shared words); the fuller wording survives and the restatement's own text, quote and event id are kept under `restatements`, so no learner words are lost. The actor prompt now says a restated open promise is not a new commitment, and that a commitment is written as what the learner will do (the run produced "Tu viens…", a line addressed *to* the learner). **Known trade-off:** bag-of-words containment cannot separate "Apporter les affiches samedi" from "Apporter le gâteau samedi" — Jaccard scores that false pair *higher* than the real duplicate — so those would merge too. The merge is non-destructive by design for exactly that reason; the alternative, a model call per commitment, was rejected as extra cost. |
| P-6 | **The chapter's title and question were never address- or register-checked.** A1 carried "Est-ce que tu acceptes l'aide des nouveaux amis ou tu restes réservé·e ?" as durable chapter state for fourteen days — the WP-14F L-6 inclusive-dot rule with a hole in it. | Both chapter fields join the learner-facing text in `_check_address` and `_check_register`. |
| P-6b | **`understood_intent` was outside the address check** — the A2 run wrote "Le·a apprenant·e" there and only the critic saw it. | The interpreter's own reading of the learner joins `reply_fr` and `resolution_fr` in `_check_address`. |

Guards that worked as intended in the runs: `gendered_address` refused a scene on day 12
of A2-no-critic, and the repetition guards refused every repeat listed above — the defect
was the feedback loop after the refusal, not the refusal.

### Critic A/B — verdict: review turns, not scenes

**Did the critic's rejections cascade into the A2 stall? No.** Reconstructing the request
sequence per day settles it (`stage` order per day in the report):

| A2 + critic day | requests | who refused |
|---|---|---|
| 5, 10, 11, 12, 14 | `SceneDraft → SceneDraft` | both attempts refused by the deterministic guards; **the critic was never called** |
| 9 | `SceneDraft!ERR → SceneDraft` | one attempt lost to a provider error, the other to a guard |
| 13 | `SceneDraft → Review:ACC → SemanticTurn → Review:REJ → SemanticTurn → Review:REJ` | the one genuine critic-caused loss |

Six of the seven lost A2 days never reached a critic call: 20 drafts were sent and only 7
scene reviews happened, because the guards refused the other 13 first. The stall is P-1
(opaque retry feedback), not the critic and not sample variance. One structural
interaction is real and worth keeping in mind: `ATELIER_STORY_MAX_ATTEMPTS` is shared, so
**a scene-stage critic rejection costs the guards one of their two attempts**.

**What the critic actually caught, both runs (26 reviews):**

| stage | reviews | rejections | unique to the critic? |
|---|---|---|---|
| scene (`director/Review`) | 19 | 1 | **No.** The single rejection (A1 day 5) was `gendered_address` — a rule the deterministic guard already owns; it fired there because the violation sat in the chapter question, the one field the guard did not see. P-6 closes that. |
| turn (`actor/Review`) | 7 | 5 | **Yes, three of five.** A2 day 4: `Le·a apprenant·e` in `understood_intent` (now a deterministic check). A2 day 13: a gendered third-person pronoun about the learner, and a quoted line putting *tu* on the seller while attributing the learner's €20 to them — semantic, not guardable. A1 days 3 and 13 were rubric-completeness rejections caused by the chained objectives of P-3; both recovered on the retry. |

**Recommendation: keep the critic for turns only** (`CRITIC_STAGES = {"SemanticTurn"}`).

- It keeps every unique catch: all three came from turn reviews.
- It removes a review that caught nothing in 19 live scenes.
- It returns both attempts to the deterministic scene guards, which is exactly where the
  A2 run ran out of road.
- It cuts a day from four calls to three: ≈ 25 % fewer requests and ≈ US$0.003 per
  learner-day, and takes ≈ 5 s off the wait for the scene the learner is blocked on.

The mechanism is implemented and defaults to **both stages** — no behaviour change
without the owner's word. `scripts/longitudinal_story_review.py --critic {all,turns,none}`
(with `--no-critic` kept as an alias for `none`) measures each configuration; the next
A/B should be `all` versus `turns`, not `all` versus `none`, since `none` is now the only
option the evidence argues against.

### Tests

Regression tests for every defect above, all with the fake provider: retry feedback names
the triple and the free ids; the hint actually reaches `previous_rejections`; the exact
A1 and A2 objectives from the runs are rejected as `objective_too_complex` while one-act
objectives pass; a chapter ends after `CHAPTER_MAX_SCENES`; the chapter question is held
to the address and register rules; `understood_intent` is address-checked; the run's own
duplicate commitment pair merges end to end while a genuinely different promise still
opens its own commitment; and `CRITIC_STAGES = {"SemanticTurn"}` reviews the turn and
only the turn.

```
.venv/bin/python -m pytest tests/test_living_story.py tests/test_living_story_longitudinal.py \
    tests/test_journey_story_outcomes.py tests/test_daily_journey_api.py
134 passed in 38.65s

.venv/bin/ruff check app/services/living_story.py scripts tests/test_living_story*.py
All checks passed!

pytest tests -k "journey or serial or story or pilot" -p no:randomly
1034 passed, 717 deselected in 122.94s
```

The same selection in random order failed once, in `auth.register_user` with a float
reaching a UUID column during registration — an ordering flake in the shared fixtures,
not in the engine; it passes on its own and in fixed order.

**Not yet demonstrated:** these fixes are deterministic and tested, but no paid run has
been made with them. The next A/B — A1 and A2, `--critic all` against `--critic turns`,
four runs at the same ceilings, ≈ US$0.40 — is what shows whether A1 now records
commitments and turns its chapter over, whether the retry hints break the A2 repetition
loop, and whether turn-only review keeps every catch. Judge it on the per-stage latency
numbers above, not on `median_request_seconds`.


### Decision — 2026-09-07 late: critic default is turns only

Fifth paid run, A2 `--critic turns` on the follow-up fixes: **13/13** non-skipped days accepted, 13 distinct
premises, 4 chapters, 6 locations, 5 characters, 0 request errors, US$0.13
(`var/reviews/atelier-longitudinal-A2-turns.json`). `CRITIC_STAGES` now defaults to
`{"SemanticTurn"}`; `--critic all` restores scene reviews for a future A/B. Engine spend today US$0.58.
