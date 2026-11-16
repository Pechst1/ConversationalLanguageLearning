# S2 · One stored day plan: every screen reads the same steps, counts and minutes

Written 9 Nov 2026 from `origin/main` at `ec60ae44`. Root cause #143, with #123, #88, #443, #552, #470, #563 as children.
Implementation: Opus 5.5, medium effort, own worktree cut from `origin/main`, draft PR, nothing merges without the owner.

## The structural flaw

Main already has a first attempt: `DaySession` (`app/schemas/daily_journey.py:1326-1376`, built in `app/services/daily_session.py`) and its client reader `web-frontend/lib/day-plan.ts`. It did not end the disagreements, for four reasons.

1. **Two models of the same day.** The journey has stored steps of eight kinds (`DailyJourneyStep`, `StepKind` in `journey_contracts.py:348`). `DaySession` has four steps (scene, grammar, words, finish) and is **recomputed on every read** from several stores. Home's day mark is fed by both (`dayMarkState` from journey steps, `sessionMarkState` from the session, `pages/atelier.tsx:2875-2884`).
2. **The plan's numbers are not the session's numbers.** The plan sizes La Forge with `daily_session.forge_items` at a default 25 s per item. The real séance uses the learner's measured pace and a different budget table (`forge.py:1264-1341`, `core/forge.py:109`, against `forge_picker.FORGE_SECONDS`, `forge_picker.py:124`). That is «Séance 0/16» beside «8 of 12».
3. **«Done» has four definitions.** Scene done is any terminal journey status, including `ended_early` (`daily_journey.py:1346`). Grammar done is `blocks_today > 0` (`:3048`), while the journey's own forge step computes `forged` separately (`:1943`, `:253`). Day done is `DaySession.done`, while the streak marks today at first practice and the client corrects it (`homeDayChip`, `lib/day-session.ts:334`).
4. **Older sources still drive screens.** `/atelier/today` returns a legacy plan (`_atelier_day_progress`, `endpoints/atelier.py:385`) on a UTC day with hard-coded minutes. The device keeps its own ticks (`atelier.continue.wordsDone`, `atelier.firstDayRoute`, `atelier:progress:<UTC date>`). Minutes come from three places: `TodayEnvelope.time_estimate`, `session.steps[].minutes`, and the legacy `estimatedRemainingMinutes`. The URL (`?mode=forge&concept=&step=&from=day&budget=`) carries state that the Forge's back button does not check against any plan (`atelier.tsx:2346`).

## Target structure

**A. The day plan is a stored record with stored step status.**
- Store the plan on the journey row under `plan_selection["plan"]`: an ordered list of steps `{id, kind, status, size, seconds, href, session_ref}` with `kind` in scene, grammar, words (the owner's order stays written once, `DAY_STEP_ORDER`).
- `status` is `todo | open | done | stopped`, written by events, never inferred on read: scene finished or ended early, Forge séance completed or left, words marked done. `stopped` is its own state, so «the scene was left early» is not «the scene is done».
- `size` and `seconds` are fixed when the step is planned and are the numbers the step itself runs with. When La Forge starts, it takes its length from the plan step (`session_ref` links the `AtelierSession`). If the séance must change length, it writes the new size back to the plan. One number, both screens.
- `DaySession` becomes a view of this record. `session_view` keeps its shape, so the client contract and `tests/test_round3_daily_session.py` hold.

**B. One definition each for step done, day done and time left.**
- `day_plan.is_done(plan)`: every working step is `done`. The streak's `today_done`, `DaySession.done`, the Done screen and Home's chip read it. Remove the client correction in `homeDayChip`.
- `day_plan.seconds_left(plan)`: the only source of minutes. `TodayEnvelope.time_estimate` is derived from it; the step rows and the card can no longer differ.

**C. Remove the other sources.**
- Delete the legacy day plan from `/atelier/today` (`_atelier_day_progress`, `estimate_session_minutes` as a Home number) and the legacy Séance tile (`atelier.tsx:3059-3095`), or serve them from the plan if a flag still needs them.
- Delete the device ticks `atelier.continue.wordsDone`, `atelier:progress:*` and the first-day route's own done flags; `continuePlan` (`lib/continue-learning.ts:54`) goes with them. The first-day route reads the plan.
- The URL names a step (`/atelier?step=<id>`), nothing more. Concept, budget and origin are read from the plan step on the server. An unknown or finished step id redirects to the plan's next step.
- Every exit (finish, stop, back, recap closed, rule check passed or failed) calls one client function, `afterExit` in `lib/day-plan.ts`, with the server's fresh plan. The Forge back button is one of those exits.

## Stages (each its own PR)

1. Stored plan and stored step status on the server; `DaySession` served from it; Forge length taken from the plan step.
2. One done and one minutes function; streak and `time_estimate` read them; remove `homeDayChip`'s correction and `dayMarkState`'s journey-step fallback.
3. Step-id URLs; all exits through `afterExit`.
4. Delete the legacy plan, the legacy tile and the device ticks.

## Done when

- `tests/test_one_day_plan.py` plays a day through every exit path (finish, stop early, back, recap close, rule check) and asserts after each: Home's next step, the step counts, the minutes left and the done flag all come from the stored plan, and the Forge's «n of N» equals the plan step's size.
- A source guard: no client file reads `localStorage` for day progress, and no module outside `day_plan.py` computes day done or minutes left. It fails on `ec60ae44`.
- The explore walk plays `a1-de` days 1 and 2: no screen says the day is done before the last step, Home and La Forge show one count, the card and the plan show one number of minutes.
- `lib/day-plan.test.js`, `lib/day-order.test.js`, `tests/test_round3_daily_session.py`, `tests/test_journey_contract_parity.py` stay green (additive fields only).

## Not in this package

- Which rule and words the steps contain: package S1.
- Splitting `pages/atelier.tsx` (6,241 lines). Stage 4 shrinks it, but the split is agent E-4's work.

## Owner decisions needed

1. Does a scene left early count toward the day (today it does)? Proposal: it shows as `stopped`, the day can still be finished, and the streak counts it only if another step is done.
2. May the legacy Séance tile and `/atelier/today` plan be removed outright?

## Checked against main on 12 Nov 2026 (read this before building)

- **Still true.** `DaySession` is recomputed on each read (`daily_session.build_session`). `forge_items` assumes 25 s per item while the séance uses the measured pace (`forge.py`). The legacy plan is in `endpoints/atelier.py`; device-side ticks are in `lib/atelier-next.ts` and `lib/continue-learning.ts`; `homeDayChip` is in `lib/day-session.ts`.
- **Stale.** `afterExit` already exists (`lib/day-plan.ts`), so stage 3 routes exits through it and creates nothing. `sessionMarkState` is not on main; `dayMarkState` is in `components/atelier-v2/journey/day-mark.ts`. «Words done» is already stored (`daily_session.SESSION_KEY`) and is adopted. All line numbers have moved.

Stages, one per pull request, each behind `DAY_PLAN_STORED` (off in code, switched on in `render.yaml` after a clean nightly walk):

| Stage | What it does | Ends |
|---|---|---|
| S2.1 | Stored plan with event-written status, compared against `session_view` (shadow) | — |
| S2.2 | Forge length from the plan step; one «done» and one minutes function | children of #143 |
| S2.3 | Step-id URLs; every exit goes through `afterExit` | unclear goal for the day |
| S2.4 | Delete the legacy plan, the tile and the device-side ticks | — |

S2.2 waits for S1.2: both edit `daily_journey.py` and `forge.py`. The stored plan becomes the source only after the shadow comparison shows zero mismatches. Old rows read through `session_view` as now.

Neither S1 nor S2 changes how long an episode is. The stored step `size` in the plan is where a length would be set, by owner decision.
