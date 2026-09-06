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
