# Serial — Season Engine & Production-Readiness Plan

**Status:** Ready to build · **Audience:** implementing agent(s) · **Date:** 2026-06-11
**Predecessor specs:** `serial-world-spec.md` (WP-1..7, shipped), `serial-lifetime-and-scheduling.md` (WP-G1..G4, shipped).
**This spec covers what those docs deferred:** the season/arc engine, character relationship development, episode-creation quality + latency, and the remaining UI/UX production blockers.

## Problem statement (why the serial "isn't there yet")

The spine works end-to-end (thread → mission → state delta → feuilleton → hook → next mission), but the *story* doesn't develop:

1. **Episodes don't advance any arc.** `world_bible_paris_v1.json` authors five `season_one_situation` open threads (Marin's proposal, Lila's Berlin secret, Gus's hidden aristocracy, the Romy romance, the user settling in), but no code reads, schedules, or resolves them. Generation sees only flat `thread.state` flags + a 12-line rolling summary, so episode 14 has the same narrative altitude as episode 3.
2. **Every episode has the same skeleton.** `_serial_episode_plan` (`app/services/graphic_novel.py:1874`) hard-codes one `panel_plan`: panel 1 = consequence, panel 2 = always a tu/vous choice fork, one Romy news panel, final = cliffhanger that always sets `next_beat_kind: "mission"`. Structurally, every "see" beat is the same episode.
3. **The deterministic fallback replays the pilot forever.** When `self.llm` is unset or the call fails, `_serial_story_script` (`graphic_novel.py:1969`) emits radiator/Le-Mistral/first-night content (`twist_default`, `warmth_line`, the fixed `branch_target`) regardless of `episode_index`. A learner on episode 9 with a dead LLM key relives episode 1 with a different title.
4. **Characters don't deepen.** No per-character relationship state (closeness, vous→tu milestone, shared history); the rich `NPC`/`NPCRelationship`/`NPCMemory` models (`app/db/models/npc.py`) are unused by the serial. Missions past episode 0 always address "friend group" in "warm informal" (`app/services/serial.py:_mission_seed`) — the cast never individually receives a mission.
5. **Episode creation is synchronous and slow.** `GraphicNovelScheduler.create` generates the script *and all panel images inline in the HTTP request* (`graphic_novel.py:553–609`); the frontend shows a toast saying "This can take a few minutes" (`web-frontend/pages/graphic-novel.tsx:245`). Mission completion advances the thread and may generate the next scene in-request. Celery exists (`app/celery_app.py`) but is not used here.
6. **No story surfaces.** No episode archive (past episodes are unreachable), no cast page, no season progress. The story accrues in JSON nobody can see.

Known small bugs to fix on the way (verified in code):
- `graphic_novel.py:2016` filters chosen cast on id `"margaux"`, but the world-bible id is `"margaux_barman"` → Margaux is silently dropped from the deterministic cast; Gus (`augustin_de_roncourt`) is excluded entirely.
- `app/services/serial.py:_mission_seed` hard-codes `relationship="friend group"`, `register="warm informal"` for every episode ≥ 1, even when the hook concerns M. Marchand (register-critical).

---

## Frozen contracts (Section 0 of this spec)

All new shapes live in `thread.state` / `world_bible` JSON and `app/schemas/serial.py`. Additive only — never break the WP-1 contracts in `docs/serial-contracts.md`.

### `world_bible.season_arcs` (authored, world bible v2)
```json
{
  "season_arcs": [
    {
      "id": "romy_romance",
      "title": "La tension Romy",
      "characters": ["romy_tremblay"],
      "stages": [
        { "id": "spark",        "summary": "Unspoken tension; she notices you.",            "sets": {"romy.user_tension": "spark_unspoken"} },
        { "id": "first_real",   "summary": "A first real one-on-one conversation.",          "sets": {"romy.user_tension": "talking"},  "entry_requires": {"user.has_met_group": true} },
        { "id": "almost",       "summary": "An almost-moment, interrupted.",                 "sets": {"romy.user_tension": "almost"} },
        { "id": "setback",      "summary": "A misunderstanding pushes her away.",            "sets": {"romy.user_tension": "setback"} },
        { "id": "resolution",   "summary": "Honesty; whatever they are, it is named.",       "sets": {"romy.user_tension": "named"}, "tentpole": true }
      ],
      "min_episodes_between_stages": 3
    }
  ]
}
```
Five arcs authored in v2, one per `season_one_situation` open thread. `tentpole: true` stages must match an authored golden reference (see WP-S4).

### `thread.state.arcs` (engine-maintained)
```json
{
  "arcs": {
    "romy_romance": { "stage": "first_real", "stage_index": 1, "advanced_at_episode": 7 },
    "marin_proposal": { "stage": "spark", "stage_index": 0, "advanced_at_episode": 0 }
  },
  "cast_last_seen": { "romy_tremblay": 7, "augustin_de_roncourt": 4 },
  "relationships": { "...": "see below" }
}
```

### `thread.state.relationships` (per-character, engine-maintained)
```json
{
  "romy_tremblay": {
    "closeness": 2,
    "register": "tu",
    "register_switch_episode": 5,
    "last_summary": "She covered for you at the newsroom; you owe her a drink.",
    "callbacks": ["ton radiateur légendaire", "le whisky québécois"]
  }
}
```
`closeness` 0–5; `callbacks` capped at 5 short strings (in-joke fuel for generation).

### `EpisodeBrief` (planner → generator/mission, the new seam)
```json
{
  "episode_index": 8,
  "beat": "see",
  "a_plot": { "arc_id": "romy_romance", "stage_id": "almost", "stage_summary": "...", "characters": ["romy_tremblay"] },
  "b_plot": { "kind": "everyday", "seed": "Gus's 'Méthode' fails publicly at the brocante." },
  "required_cast": ["romy_tremblay", "augustin_de_roncourt"],
  "location_id": "brocante",
  "structure": "two_hander",
  "include_news_panel": false,
  "include_choice_fork": true,
  "stakes_level": 2,
  "hook_guidance": "End on the interruption of the almost-moment.",
  "tentpole_reference": null
}
```
`structure` ∈ `{"ensemble", "two_hander", "bottle", "callback_open", "news_edition"}`. Published as a Pydantic model in `app/schemas/serial.py`.

---

# Phase 0 — Production hardening (UI/UX blockers; ship first)

## WP-P1 — Background episode generation + progressive reveal
**Touch:** `app/services/graphic_novel.py`, `app/tasks/` (new `app/tasks/serial_generation.py`), `app/api/v1/endpoints/graphic_novel.py`, `app/api/v1/endpoints/missions.py`, `app/services/serial.py`, `web-frontend/pages/graphic-novel.tsx`, `web-frontend/services/api.ts`.

1. **Split script from images.** Refactor `GraphicNovelScheduler.create` so it (a) generates the script, (b) persists the scene with `status="generating"` and panels with `image_url=None`, (c) enqueues a Celery task `generate_scene_images(scene_id)` that renders panel images (reuse the existing semaphore logic) and flips `status="available"` when done, `status="generation_failed"` on unrecoverable error. Keep a `sync=True` escape hatch used by tests and by `GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED=false` paths.
2. **Pre-generate the next beat.** In `SerialThreadService.apply_completion`, after advancing the index, enqueue beat creation as a background task instead of awaiting it inline. `/serial/today` keeps its lazy-regeneration fallback for the cold case.
3. **Polling + progressive reveal.** `GET /graphic-novel/scenes/{id}` already returns the scene; ensure it includes per-panel `image_url` nulls and scene `status`. In `graphic-novel.tsx`, when a scene is `generating`, poll every 4s and reveal panels as their images arrive (skeleton frame with the panel's `beat` text in the meantime — readable story before art). Replace the minutes-long blocking toast.
4. **Timeout budget.** The scene-create endpoint must return in < 15s (script only). Add a regression test asserting `create(...)` with image generation enabled does not call the image service inline (mock and assert call count 0 before task execution).

**Acceptance:** completing a mission returns immediately and the next episode appears in `/serial/today` as `generating` then `available`; `tests/test_graphic_novel.py` + new `tests/test_celery_tasks.py::test_scene_image_task` green; existing sync tests still pass via the escape hatch.

## WP-P2 — Kill the pilot-replay fallback; honest degraded state
**Touch:** `app/services/graphic_novel.py`, `app/services/serial.py`, `web-frontend/pages/graphic-novel.tsx`.

1. For serial scenes with `episode_index >= 1`, when `_serial_episode_plan` returns `None` (LLM down), do **not** fall through to the pilot-flavored template. Instead raise a typed error; `/serial/today` then returns the episode with `status="delayed"` and a reader-facing "L'édition de demain est retardée" card with a retry affordance. Episode 0 may keep the deterministic pilot (it is authored, that's fine).
2. Fix the cast-filter bug (`"margaux"` → `"margaux_barman"`) and add Gus to the rotation pool (`graphic_novel.py:2016`).
3. Config: document in `.env.example` that `OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL` + API key must be set in production; add a startup log warning when the serial is enabled but the story LLM is not.

**Acceptance:** a serial scene at index ≥ 1 with LLM unavailable yields `delayed`, never radiator content (assert the script text does not contain "radiateur" for a fixture at index 5); Margaux/Gus appear in `chosen_cast` fixtures.

## WP-P3 — Shell cleanup + per-day progress block
**Touch:** `web-frontend/lib/product-shell.ts`, `next.config.js` redirects, legacy pages, `app/api/v1/endpoints/atelier.py`, `app/services/atelier.py`, `web-frontend/pages/atelier.tsx`.

1. Redirect legacy routes (`/dashboard`, `/sessions`, `/practice`, `/daily-practice`, `/learn`, `/index`) to `/atelier` (server-side redirects; keep deep session routes that are still used by the spine). Exclude `mobile-visual-qa.tsx` from production builds (rename to a dev-only route or guard on `NODE_ENV`).
2. Ship the backend per-day `progress` block on `getAtelierToday()` (`errataDue`, `vocabularyDue`, `missionDone`, `feuilletonDone`) — the standing Known Gap in `MASTER_CODEX.md` — and delete the localStorage derivation in the frontend.
3. Fix the `react-hooks/exhaustive-deps` warning at `atelier.tsx:275`.

**Acceptance:** lint clean; `tests/test_atelier.py` asserts the `progress` block; navigating to `/dashboard` lands on `/atelier`.

---

# Phase 1 — Season & character arc engine (the ongoing story)

## WP-S1 — World bible v2 + arc/relationship state (contracts)
**Touch:** `app/prompts/serial/world_bible_paris_v1.json` → add `world_bible_paris_v2.json`, `app/schemas/serial.py`, `app/services/serial.py` (`_sync_world_bible_assets` pattern for upgrade).

1. Author `season_arcs` (Section 0 shape) for the five open threads. Each arc: 4–6 stages, `min_episodes_between_stages`, exactly one `tentpole` stage. Keep all v1 keys; bump `world_bible_version`.
2. Publish `SeasonArc`, `ArcStage`, `ArcStateEntry`, `RelationshipEntry`, `EpisodeBrief` Pydantic models in `app/schemas/serial.py` (`extra="allow"`).
3. Extend the existing live-thread upgrade hook (`_sync_world_bible_assets`) to also merge `season_arcs` into active threads and initialize `state.arcs` / `state.relationships` / `state.cast_last_seen` for the current cast (idempotent).

**Acceptance:** `tests/test_serial.py::test_world_bible_v2_upgrade` — an existing v1 thread gains `season_arcs` + initialized `state.arcs` without losing `state` flags.

## WP-S2 — `SerialArcPlanner` (the episode brain)
**Touch:** new `app/services/serial_arc_planner.py`, `app/services/serial.py`.

1. `SerialArcPlanner(thread).plan_next_episode(beat: str) -> EpisodeBrief`, deterministic (no LLM), driven by:
   - **Arc rotation:** pick the A-plot arc = the eligible arc (entry conditions met, `min_episodes_between_stages` elapsed) with the oldest `advanced_at_episode`; advance its stage when the episode completes (wire into `apply_completion`).
   - **Cast rotation:** `required_cast` = A-plot characters + the main-cast member with the stalest `cast_last_seen` (every main character on stage at least every 4 episodes).
   - **Location rotation:** existing `_serial_location` rule, but planner-owned so missions and scenes share it.
   - **Structure rotation:** cycle `structure` so the same value never repeats twice; `include_choice_fork` true at most every other "see" beat; `include_news_panel` only when `structure == "news_edition"` or `episodes_completed % 7 == 0` (the weekly edition — closes the deferred WP-G2 item).
   - **Stakes:** keep `_stakes_level`, plus +1 when the A-plot stage is `tentpole`.
2. `SerialThreadService.start_mission_beat` / `start_feuilleton_beat` call the planner and persist the brief on the episode row (`SerialEpisode.hook_from_previous` stays; add the brief into a new `SerialEpisode.brief_payload` JSON column + tiny Alembic migration).
3. **Mission seeds become character-true.** Replace the hard-coded `("friend group", "warm informal")` in `_mission_seed` with the brief: address a `required_cast` character, register from `world_bible.register_map` overridden by `state.relationships[id].register` (tu after the switch milestone).

**Acceptance (all in `tests/test_serial.py`):**
- 10 simulated completions → at least 3 distinct arcs advanced; no arc advances twice within its `min_episodes_between_stages`.
- Every main-cast member appears in some `required_cast` within any 4-episode window.
- No `structure` repeats consecutively; news panel only on the weekly cadence.
- A mission brief addressing `landlord_marchand` carries `vous / polite formal`; one addressing a `register: "tu"` relationship carries tu.

## WP-S3 — Relationship & callback memory
**Touch:** `app/services/serial.py`, `app/services/missions.py` (consume only), `app/services/graphic_novel.py` (consume only).

1. In `apply_completion`: when the completed beat addressed character X (from the brief), update `state.relationships[X]`: `closeness` +1 on success (score ≥ 3), unchanged otherwise (never punitive); refresh `last_summary` from the mission outcome/scene hook; harvest at most one new `callback` (a short memorable phrase from the learner's own message — take it from `recap_payload.outcome.reply_text` context; LLM-extracted with a "skip" fallback, never blocking).
2. **Register milestone:** when `closeness` crosses 3 for a `tu`-eligible character (per `register_map`), set `register: "tu"`, record `register_switch_episode`, and emit it as the *authored beat* of the next episode brief (`hook_guidance`: "X offers the tu"). This makes the vous→tu switch a story event, which is the pedagogical heart of the serial.
3. Pass `relationships` (closeness, register, callbacks) for the present cast into `_serial_episode_plan`'s payload and into the mission system prompt, with the instruction: use callbacks as in-jokes, reflect closeness in warmth, never violate the current register.

**Acceptance:** full-loop test where two successful Romy beats flip her register to tu and the next brief contains the tu-switch guidance; callbacks appear in the generation payload (assert on the prompt dict, no LLM needed).

## WP-S4 — Tentpole golden references (content + gate)
**Touch:** `docs/serial-episode-XX-*.md` (new), `app/services/graphic_novel.py`.

1. Author golden references for the five tentpole stages (one per arc), same format as `docs/serial-episode-01-reference.md`: beat sheet, state in/out, hook. This is the deferred DB-4 work, now load-bearing.
2. When the planner emits `tentpole_reference`, inject the reference beat sheet into `_serial_episode_plan` as a "match this emotional structure" exemplar (not verbatim panels).
3. Generate the missing `brocante` location plate from `docs/serial-image-prompts.md` (closes DB-2).

**Acceptance:** tentpole episode fixture's generation payload contains the reference beat sheet; brocante plate exists and is wired in `visual_design.locations.brocante.reference_images`.

---

# Phase 2 — Episode-creation quality

## WP-Q1 — Brief-driven episode plans (structural variety)
**Touch:** `app/services/graphic_novel.py` (`_serial_episode_plan`, `_serial_story_script`), `app/prompts/feuilleton/*`.

1. Replace the fixed `panel_plan` with structure templates keyed by `EpisodeBrief.structure` (ensemble / two_hander / bottle / callback_open / news_edition), each defining panel-role guidance; choice fork and news panel only when the brief says so. The cliffhanger's `next_beat_kind` comes from the planner, not hard-coded `"mission"`.
2. Thread the A-plot/B-plot from the brief into the system prompt: "Advance the A-plot to stage X (summary). The B-plot is texture, one or two panels."
3. Add a `serial_v2` prompt variant in `style_pack_v2.yaml`/`visual_gag_writer_v2.yaml` documenting the structure templates.
4. **Continuity guard:** post-generation validator asserting required cast names appear in the panels and the final panel's hook contains an unresolved question (extend `_validate_script`); on failure, retry once with the validation errors (existing retry plumbing at `_generate_story`).

**Acceptance:** two consecutive generated episodes differ in `structure`; a `two_hander` fixture produces panels referencing exactly the two required cast members; regression — non-serial scenes untouched.

## WP-Q2 — CEFR ramp
**Touch:** `app/services/serial_arc_planner.py`, `app/services/missions.py`.

Map `user.proficiency_level` → caption complexity instruction + mission `min_words`/objective count (A2: 3 objectives/35 words … B2: 5/90). One function, one table, used by both beats. **Acceptance:** monotonic min_words across levels in tests.

---

# Phase 3 — Story surfaces (UI)

## WP-U1 — Episode archive ("Season 1")
**Touch:** `app/api/v1/endpoints/serial.py`, `app/services/serial.py`, new `web-frontend/pages/serial/index.tsx` + `web-frontend/pages/serial/episode/[index].tsx`, `web-frontend/lib/product-shell.ts` (Atelier-owned routes).

1. `GET /serial/threads/current/episodes` → list of completed episodes: `episode_label`, `kind`, title (mission title or scene title), first panel thumbnail, hook text, completed_at.
2. Archive page: newspaper-archive styling consistent with the Feuilleton masthead; tap an episode → read-only replay (scene panels without tasks, or the mission transcript). Entry point: a small "Season 1 · Episode N" link on the Atelier `SerialThreadCard` and on the Feuilleton page header.

**Acceptance:** `tests/test_serial.py` asserts the endpoint shape; new frontend contract test mirroring `tests/test_frontend_atelier_thread.py` style.

## WP-U2 — Cast page
**Touch:** new `web-frontend/pages/serial/cast.tsx`, endpoint addition in `serial.py` (`GET /serial/threads/current/cast`).

Character cards from `world_bible.cast` + `state.relationships`: model-sheet image (`/assets/serial/characters/<id>/model-sheet.png`), role, current register chip (vous/tu — tu shown as an earned badge), closeness as a subtle meter, `last_summary` line. No spoilers for arcs not yet started.

**Acceptance:** cast endpoint merges bible + relationship state; a character without relationship state renders defaults (vous, closeness 0).

## WP-U3 — "Tomorrow's edition" teaser
**Touch:** `web-frontend/pages/atelier.tsx`, `web-frontend/pages/graphic-novel.tsx`.

With WP-P1 pre-generation, the recap's serial card can show the real state: `generating` → "Tomorrow's edition is at the printer's…", `available` → the hook teaser ("Demain : …"), `delayed` → the honest delayed card (WP-P2). Use the existing `ContinuationCard` tones.

---

# Sequencing & ownership

| Phase | Packages | Parallelizable? |
|---|---|---|
| 0 | WP-P1, WP-P2, WP-P3 | P1/P2 same files — sequential; P3 parallel |
| 1 | WP-S1 → WP-S2 → WP-S3; WP-S4 content in parallel | S-chain sequential (contracts first) |
| 2 | WP-Q1, WP-Q2 | after S2; parallel to Phase 3 |
| 3 | WP-U1, WP-U2, WP-U3 | after S1 contracts; U3 after P1 |

**Hard rules carried over from `serial-world-spec.md`:** Section 0 shapes here are frozen once WP-S1 publishes them; WP-1 contracts in `docs/serial-contracts.md` are never broken; every WP keeps the standalone (non-serial) mission/feuilleton paths green; the serial stays behind `SERIAL_WORLD_ENABLED`.

# Definition of done (global)
1. Mission completion returns < 2s; next episode generates in the background and appears progressively.
2. No serial episode ≥ index 1 ever replays pilot content; LLM-down is an honest "delayed" state.
3. Over a 12-episode simulated season: ≥ 3 arcs advance, every main character appears ≥ 3 times, no structure repeats consecutively, one vous→tu switch occurs as a story beat, the tentpole episode uses its golden reference.
4. The learner can reread any past episode and see the cast page.
5. `tests/test_serial.py`, `tests/test_missions.py`, `tests/test_graphic_novel.py`, frontend contract tests, lint, type-check all green.

---

# Post-implementation review (2026-06-12) — status & next work packages

**Review verdict:** Phases 0–3 implemented in one pass and reviewed as good. The planner (`app/services/serial_arc_planner.py`), world bible v2 + contracts, relationship/callback/tu-switch engine, five tentpole references, brief-driven generation, CEFR ramp, background image generation with `generating`/`delayed` states + frontend polling, pilot-replay kill, cast bug fixes, redirects, archive/cast/replay pages, and the `brief_payload` migration are all in place. 17 serial/celery/contract tests + 33 mission/feuilleton regression tests green; type-check green; migration applied and idempotent. The 12-episode simulated-season test (`test_serial_arc_planner_rotates_arcs_cast_and_spacing`) locks the global DoD #3.

**Issues found in review → next work packages, in priority order:**

## WP-N1 — Delayed-episode recovery (bug; small)
A `delayed` feuilleton episode is terminal: `start_feuilleton_beat` short-circuits on `status == "delayed"` (`app/services/serial.py:396`) and nothing ever resets it; the frontend card offers "Try again" with no force path. Fix: in `SerialThreadService.today()`, when the current episode is `delayed`, re-attempt `start_feuilleton_beat` (clear the short-circuit for that call); optionally add `POST /serial/threads/current/retry` and wire the card's button. **Acceptance:** test with an LLM stub that fails once then succeeds — episode goes `delayed` → retry → `generating`/`available`; a still-failing LLM keeps it `delayed` without duplicating episodes.

## WP-N2 — Commit + live-loop verification (gate; do before building more)
The entire engine is uncommitted working-tree state (plus older unrelated changes). Split into reviewable commits (suggested: spine/planner backend · generation/graphic-novel · celery tasks · frontend surfaces · docs/migration). Then verify live with a running Celery worker (`./start-celery.sh`): complete the open episode-1 feuilleton on the real thread and assert in DB that an arc stage advanced, `cast_last_seen` updated, a relationship `closeness` ticked, and the next beat appeared via the background task (not just lazy regeneration). The live thread has never exercised the new completion path.

## WP-N3 — WP-P3 leftovers (small)
(a) Fix `react-hooks/exhaustive-deps` at `web-frontend/pages/atelier.tsx:274` (was an explicit WP-P3 task; still warns). (b) Guard `web-frontend/pages/mobile-visual-qa.tsx` out of production (notFound when `NODE_ENV === "production"`). (c) Run the established 319×734 signed-in mobile smoke over the three new routes: `/serial`, `/serial/cast`, `/serial/episode/[index]`.

## WP-N4 — Stale-generation cleanup + worker ops (small)
No Celery worker runs in the default dev flow, and a crashed worker would strand scenes in `generating` forever. Add a cleanup rule (on `/serial/today` or a periodic task): scenes `generating` longer than ~15 min → `generation_failed`, episode → `delayed` (recoverable via WP-N1). Tidy `create_next_serial_beat` (`app/tasks/serial_generation.py`): remove the duplicated thread fetch (lines 34–40) and call public service methods instead of `_current_episode`/`_start_next_beat`. Document the worker requirement in README/start scripts.

## WP-N5 — Callback quality (medium)
`_harvest_callback` (`app/services/serial.py:966`) takes the first 5 words of the learner's last message — that yields salutations ("Bonjour Monsieur Marchand je viens"), not in-jokes. Replace with one cheap LLM extraction call ("quote the single most memorable/funny phrase from this message, ≤ 6 words, or NONE"), deterministic skip on failure/NONE, same 5-item cap. **Acceptance:** salutation-only fixture yields no callback; a message with a distinctive phrase yields that phrase.

## WP-N6 — Season rollover (the next big feature)
When every arc reaches its final stage, `_select_arc_stage` falls into its fallback branch forever (last stage, `advance_on_completion=False`) — the season never ends and never renews. Build: (a) `season_complete` detection in the planner (all arcs at final stage); (b) an authored epilogue/finale episode brief; (c) season-2 loading — `world_bible_paris_s2.json` with new `season_arcs` on the same cast, merged by the existing `_sync_world_bible_assets` upgrade path, carrying `relationships`/`state` forward and re-seeding `state.arcs`; (d) content task: author the season-2 arc set. **Acceptance:** simulated season run to completion rolls into season 2 with relationships intact and fresh eligible arcs.

## WP-N7 — Cost observability (small)
Per-scene cost lives in `generation_metadata`/script metadata but is invisible in aggregate. Log a per-generation structured event (user, episode_index, story_usd, image_count, image_quality) and add a simple rollup query/script so weekly spend per learner is known before any wider launch.

---

# UX review & experience work packages (2026-06-12, after WP-N1..N7 shipped)

**Status:** WP-N1..N7 are implemented and committed (`c0e6184`..`58424f0`), working tree clean, 59 serial-related tests green. The live thread has exercised the engine: 3 episodes completed, `marin_proposal` arc at `spark`, two relationships at closeness 1, briefs attached from episode 2 on.

**UX verdict on the core loop:** the day-loop is coherent and the craft is high — "Today's edition" spine → review → "Living thread" serial card with real states (invite/act/see/printing/delayed/settled), cold-open prologue, WORLD REPLY + hook after a mission, progressive panel reveal, cliffhanger hero with "Answer in the next episode". The remaining problems are not in the beats; they are *around* them: the story surfaces are nearly undiscoverable, the loop has no pull from outside the app, the French is never heard, and a parallel legacy narrative system (Stories) muddies the IA.

## WP-X1 — Serial discoverability + season presence (small; do first)
The Season-1 archive (`/serial`) is reachable only from one link inside the Feuilleton header; the cast page only from the archive. Atelier's serial card and the done-state never link to them.
1. `SerialThreadCard` (`web-frontend/pages/atelier.tsx:1215`): make the `episodeLabel` row a "Season 1 · Episode N" link to `/serial`; in the `done` state add two quiet links — "Re-read the season" (`/serial`) and "The cast" (`/serial/cast`).
2. Add a season-progress strip at the top of `/serial`: a simple act/see timeline of completed episodes (no arc spoilers), current episode highlighted.
3. Mission page header: add the same `Season 1 / Épisode N` breadcrumb pair the Feuilleton already has (`graphic-novel.tsx:1012`).
**Acceptance:** from `/atelier` a user can reach archive and cast in one tap; contract test extends `tests/test_frontend_serial_surfaces.py`.

## WP-X2 — The return loop: "tomorrow's edition" notifications (medium; highest retention leverage)
Pre-generation exists, but nothing tells the learner the next episode is out — the cliffhanger pull dies when the tab closes. `app/db/models/push_subscription.py` + `app/services/notification_service.py` + `app/tasks/notifications.py` already exist with zero serial hooks.
1. When a background-generated scene flips to `available` (in `render_scene_images`) or a mission beat is created, enqueue a notification: in-fiction copy, e.g. "Épisode 4 est paru — Marin n'a pas fini sa phrase." Route through the existing notification service; respect existing quiet-hour/preference plumbing; add a settings toggle (`serial_edition_notifications`, default on).
2. Replace the static done-state copy on `SerialThreadCard` ("let the cliffhanger sit overnight") with the *real* next-episode teaser when it exists (`hook.teaser`) + "arrives with tomorrow's edition".
**Acceptance:** completing a beat with push enabled produces exactly one queued notification per generated episode (idempotent — re-renders don't re-notify); test in `tests/test_celery_tasks.py`.

## WP-X3 — Hear the episode: TTS for the Feuilleton (large; highest pedagogical value)
The serial's French is never heard. For a language product this is the single biggest missing modality, and the cast gives it voices.
1. Backend: per-panel audio for the French captions + speech bubbles. Generate in the existing image Celery task (after images), store URL/payload on `GraphicNovelPanel` (`audio_payload` JSON column + migration). Voice per character via a `voice_map` block in the world bible (`cast[].voice` hint → provider voice id); narrator voice for captions. Cache by text hash; config flag `FEUILLETON_AUDIO_ENABLED` + cost cap. Fold cost into WP-N7's rollup.
2. Frontend: a play button per panel and a "Lire l'épisode" continuous mode that steps panels as audio plays. Progressive: panels without audio yet just skip.
3. Missions: read M. Marchand's/NPC's reply aloud with the character voice (one call per reply, cached on the mission).
**Acceptance:** generated serial scene has audio for ≥ the French captions; audio task failure never blocks scene availability; cost appears in the rollup script.

## WP-X4 — First-run framing (medium)
There is no onboarding of any kind (no welcome state, no app-model explanation). The cold open is great fiction but doesn't explain the *product*: that this is a daily edition, that the serial is a persistent life your French moves, that the Notebook remembers everything.
1. One-time, skippable, 3-beat welcome interstitial on first `/atelier` visit (server-persisted flag on the user, not localStorage — must survive devices): ① "Your daily edition" (session+review), ② "Your serial life in Paris" (cast strip, "your French moves the story"), ③ "The Notebook remembers" (errata/vocab). Editorial-print styling consistent with the masthead.
2. Episode-1 steepness check for beginners: the episode-one mission contract hardcodes `min_words: 35`; respect the planner's CEFR profile (A1: 25) instead, and make sure quick replies render prominently for A1/A2.
**Acceptance:** flag round-trips through the API; second visit shows no interstitial; A1 fixture gets the lower word floor.

## WP-X5 — Cast page becomes the memory (small)
`/serial/cast` shows role/register/closeness but not the *history* — and the history is the bond.
1. Render `callbacks` as "private jokes" chips, `last_summary` as the latest-beat line, and the tu-switch as a dated event ("On se tutoie depuis l'épisode 5", from `register_switch_episode`).
2. Link each character card to their episodes (filter archive rows by `required_cast` from `brief_payload`).
**Acceptance:** cast endpoint already returns the fields; page renders them; a character with no history renders cleanly.

## WP-X6 — Read-first Feuilleton flow (medium; validate before building big)
In study mode, 5 tasks interleave with 6 panels — the learner is quizzed mid-scene, which fights the emotional read that powers the serial.
1. Add a "read-through" presentation: panels first, uninterrupted (tasks visible but collapsed), then a "Maintenant, à toi" task section before filing the edition. Keep the completion gate (all required tasks) unchanged; this reorders, not removes.
2. Make it the default for serial scenes; keep current inline order for standalone scenes (or behind a preference).
**Acceptance:** serial scene renders all panels before the first required task; filing still blocked until tasks complete; existing task tests unaffected.

## WP-X7 — Narrative IA cleanup: Stories vs. the Serial (decision + medium)
Two parallel narrative systems live under Atelier: the legacy book-chapter Stories/RPG (`/stories`, `/story/[id]`, NPC models, relationship meters) and the Serial. Both say "story"; only one is the product's spine now.
1. Decide (product call, options in order of recommendation): (a) reframe Stories as **"La Bibliothèque"** — imported-book reading practice, clearly distinct naming, reachable as an Atelier side quest; or (b) feature-flag it dark until it earns its place.
2. Whichever is chosen: rename surfaces/copy so "the story" unambiguously means the serial; sweep Atelier side-quest copy for the distinction.
**Acceptance:** no Atelier surface uses "story" for both systems; navigation contract tests updated.

## Sequencing
X1 (days, do immediately) → X2 (the retention loop) → X3 (the big modality bet; start the backend while X2 ships) → X4/X5 (polish, parallel) → X6 (validate with use first) → X7 (needs the product decision).

---

# Product direction packages (2026-06-12) — the promise, mission formats, la Bibliothèque

**Product framing (owner decision, recorded):** the app competes with Duolingo on engagement but wins on a different claim — *a credible, visible path to a CEFR level in one app* ("20 min/day for 50 days → A1.2"). The serial is the retention engine; the CEFR meter is the promise; missions are the bite-size problem-solving format inside the season; la Bibliothèque turns free French books into more serialized content.

**Where missions went (review finding):** missions were deliberately absorbed as the serial's "act" beats (the WP-6 "mechanic names recede" decision) — they still exist standalone at `/missions` and five template types exist in `MISSION_TEMPLATES` (`message`, `explain_plan`, `news_summary`, `travel_work`, `conversation`; `app/services/missions.py:33`). But the serial hard-passes `mission_type="message"`, so in practice every act beat is a text chat. The "voice-note version" exists only as a debrief teaser string (`missions.py:1889`). Format variety is the loss to repair — not the absorption itself.

**CEFR reality check:** `user.proficiency_level` is a static string (default `"beginner"`, `app/db/models/user.py:30`). The planner's CEFR ramp *consumes* it; nothing *measures or advances* it. The "A1.2 in 50 days" promise currently has no backing model.

## WP-Y1 — Mission formats inside the season (medium-large)
Restore the "solve a small problem" variety as planner-driven formats, all sharing the existing objectives/grading engine — only the surface changes.
1. **Contract.** `EpisodeBrief` gains `mission_format` ∈ `{"chat_message", "voicemail_reply", "email_formal", "admin_form", "phone_call"}`. Planner rotates formats (never the same twice in a row; `voicemail_reply` only once WP-X3's TTS lands; `phone_call` is v2, behind a flag).
2. **Voicemail beat** (the flagship): the NPC leaves a voicemail (TTS with the character's voice from WP-X3's voice map; transcript hidden by default, "afficher la transcription" affordance); the learner replies by text or voice (reuse `VoiceInput` + the existing audio-session transcription path). Grading unchanged (transcribed voice goes through the same correction service).
3. **Email/formal letter**: register-critical surface with subject line + salutation/closing conventions — maps to existing register objectives.
4. **Admin form** (très français): a small French form (préfecture/CAF/bank flavored, generated fields) the learner fills from the episode context; graded per field. Bounded: 4–6 fields, deterministic validation + one LLM-checked free-text field.
5. **Frontend:** `missions.tsx` renders per `mission_format` (the messenger shell already exists; voicemail/email/form are new presentation components, same submission plumbing).
**Acceptance:** planner emits rotating formats; a voicemail mission round-trips voice→transcription→correction; standalone missions unaffected; `tests/test_missions.py` + `tests/test_serial.py` extended.

## WP-Y2 — CEFR progress engine + the visible promise (large; the core product claim)
1. **Model** (`app/services/cefr_progress.py`): define sub-levels `A1.1 … B2.2` with thresholds over signals that already exist — FSRS-mastered vocabulary count, grammar concepts mastered (grammar catalog state), rolling error-rate trend (error_memory), mission/feuilleton scores. One calibratable threshold table, versioned. Nightly (or on-completion) recompute → persist `user.cefr_estimate` + history rows (new small table + migration).
2. **Forecast:** rolling 14-day pace (words/day, concepts/day) → projected date for the next sub-level at current pace, shown as a range, recalibrated weekly. Honest rules: no projection with < 7 active days of data ("come back in a week for your forecast"); cap optimism.
3. **Surface:** (a) level meter chip in the Atelier edition header ("A1.1 → A1.2 · ~31 jours à ce rythme"); (b) a Notebook "Progression" block with the threshold breakdown (words X/300, concepts Y/20…); (c) the post-edition "filed" moment shows the day's delta ("+9 mots actifs · +1 point de grammaire · l'histoire avance").
4. **Onboarding tie-in (with WP-X4):** ask target + minutes/day at first run; the welcome states the promise with their numbers.
**Acceptance:** deterministic unit tests on the threshold table and forecaster (fixed fixtures → fixed estimate/forecast); estimate never regresses from a single bad day (smoothing); API exposes estimate + forecast + deltas; meter renders on Atelier and Notebook.

## WP-Y3 — The 20-minute edition (medium)
The daily contract must be time-credible: session spine + review + serial beat ≈ 20 min, visibly.
1. Instrument actual durations (session rounds, review, mission, feuilleton) into analytics; derive p50 per activity per level.
2. Tune content volume to the budget (review cap, session round length, feuilleton task count) via config; show "≈ N min" on each spine node and a quiet "~12 min left in today's edition" line.
3. Make the finish line a moment: "Édition bouclée" stamp + WP-Y2's day-delta + tomorrow's teaser (ties into WP-X2's done-state copy).
**Acceptance:** every spine node shows a time estimate; an A2 fixture's full day at p50 durations sums to 18–22 min; the filed moment renders the delta.

## WP-Y4 — La Bibliothèque v1: free books become serialized episodes (large)
Reframe the legacy Stories system (per WP-X7 option a) into the book pipeline the product always wanted (prior art: `content-pipeline-gutenberg.md`, `petit-prince-prototype.md`, `upload_moby_dick_task.py`, the stories models + `ImportStoryModal`).
**v1 scope (shippable):** pick/upload a public-domain French text → pipeline: segment into scenes → level-adapt the French (A1/A2/B1 paraphrase, original displayed alongside, "texte original" toggle) → serialize into Bibliothèque episodes with hooks ("À suivre") → glosses + 3 overlay tasks per episode reusing the graphic-novel task engine → one generated cover per book. A "shelf" page (`/bibliotheque`) replaces `/stories`; reading progress per book; vocabulary encountered feeds the same FSRS/credit pipeline (counts toward the WP-Y2 meter).
**Explicitly v2 (do not build now):** the side-door interactive role from the pipeline doc (playing a character inside the book), branching, illustrated panels per scene, cast crossover with the serial.
**Acceptance:** import a Gutenberg text end-to-end → N level-adapted episodes with glosses/tasks; vocabulary credit flows to FSRS; legacy story routes redirect to `/bibliotheque`; naming sweep complete (WP-X7 acceptance folded in).

## Revised global sequencing (X + Y)
1. **X1** serial discoverability (days) → 2. **Y2** CEFR engine + meter (the claim everything hangs on) → 3. **X2** notifications + **Y3** 20-min edition (the daily contract) → 4. **X3** TTS + **Y1** mission formats (one voice investment, two payoffs) → 5. **X4** first-run (now states the promise) + **X5** cast memory → 6. **Y4** Bibliothèque v1 (absorbs X7) → 7. **X6** read-first flow.

---

# Feuilleton craft fixes (2026-06-12, from owner screenshot review of Episode 4)

**Diagnosis from the screenshots (verified in code):**
1. **The task layer is still episode-1 furniture.** The LLM episode plan authors only the *narrative* (titles, captions, hook); the 5 overlay tasks are hardcoded in the serial template — "Radiator phrase", "How do you enter?", "Introduce yourself", "News reaction", "Keep the thread alive" (`app/services/graphic_novel.py:2400–2509`). At episode 4 the learner is asked to introduce themselves to a group they've known for three episodes and to complete a radiator sentence from a plot that's over. Same for dialogue: the two speech lines are the hardcoded template bubbles (`_serial_bubbles`, `graphic_novel.py:2832` — "Viens, tu vas geler." / "C'est quoi la vraie histoire ?"), not lines from this episode's plan.
2. **Speech bubbles exist but are hidden on mobile.** Full overlay plumbing (`BubbleOverlay`, x/y, tones) is implemented; mobile CSS turns it off (`.feuilleton-page .bubble-layer { display:none }`, `graphic-novel.tsx:4172`) and dialogue drops to transcript blocks under each panel.
3. **The protagonist-as-coffee-mug is the image model resolving the authored convention** ("shown ambiguously from behind or partially cropped", `world_bible_paris_v2.json` → `visual_design.characters.user`) into a foreground prop in every panel.
4. **Page is overloaded:** header stacks title + chips + Previously + 4 vocabulary cards (with translations always visible) + a raw ACTUALITÉ news block with garbled summarizer text ("exprime sacolère", stray "I", "Personnes citées: …" artifacts) before the first panel.
5. **Choice tasks render without their option texts** in the end-of-read section (empty "A"/"B" inputs in the screenshots).
6. **Read-first (WP-X6) overshot:** collecting all tasks at the end disconnects them from their panels and re-prints panel context (owner feedback; revises X6's default).

## WP-F1 — Story-true tasks and dialogue (the root fix; large; do first)
1. Extend `_serial_episode_plan`'s response format: the plan also authors the overlay **tasks** (per panel: type from the existing task vocabulary — cloze/choice/short_sentence — prompt, expected/accepted answers, the day's grammar/vocab targets woven in) and **dialogue bubbles** (≤2 per panel: `speaker_id`, `fr`, `en`, `tone`, normalized `x`/`y`). Reuse the non-serial path's task generation + validation machinery rather than inventing new (the standalone Feuilleton already LLM-generates tasks).
2. Tasks must be **story-state aware**: pass `state` flags + relationship register into task generation with explicit rules (never "introduce yourself" once `user.has_met_group`; register tasks follow the current tu/vous per character).
3. Template tasks/bubbles (`graphic_novel.py:2400–2509`, `:2832`) become fallback-only for episode ≤ 1; for episodes ≥ 2 a plan without valid tasks is a validation error → existing retry path.
4. Fix the lost choice-option texts in the read-first aggregation (empty A/B inputs).
**Acceptance:** episode-≥2 fixture yields tasks referencing the episode's own beats/targets, none of the five template labels; choice tasks render real option lines; bubbles in `overlay_payload` come from the plan; task grading regression green.

## WP-F2 — Speech bubbles on the art (medium; rides on F1)
1. Re-enable the bubble layer on mobile with mobile-safe rules: max 2 bubbles/panel, top-band placement bias, smaller type, character-accent border (cast `ui_token` colors exist), tap toggles FR↔translation. Keep the transcript block as a11y fallback and for >2 lines.
2. Image-prompt side: add "leave clear headroom in the upper third; characters' heads in the lower two-thirds" composition guidance for panels with bubbles, and keep the no-text-in-image guardrail.
**Acceptance:** mobile 390px screenshots show legible bubbles not covering faces (manual QA pass per the mobile checklist); transcript still renders under `prefers-reduced-motion`/screen readers.

## WP-F3 — Create your own character (large; owner wish; parallel track)
1. First-run (or first serial visit) avatar builder: 3–4 guided choices (hair, build/style, vibe) + optional one-line free description → generate a model sheet in the established ink style (reuse the recipe in `docs/serial-image-prompts.md`) → learner approves or re-rolls (one re-roll) → stored per-user (`/assets/serial/characters/user-<id>/model-sheet.png` or object storage), written into `thread.world_bible.visual_design.characters.user.reference_images` (per-thread override; the sync hook must not clobber it).
2. Panels then render Toi as a real on-stage character; the current behind-the-shoulder "POV mode" stays as an explicit choice ("rester hors-champ"). Settings entry to regenerate later, with a continuity warning.
3. Safety: image-generation moderation on the free-text description; deterministic fallback to POV mode on generation failure.
**Acceptance:** avatar fixture appears in `human_characters`/image prompts with the user's reference image; `_sync_world_bible_assets` preserves the override; POV mode unchanged when no avatar.

## WP-F4 — Declutter the episode page (medium; quick win)
Target: at most **two** text blocks between any two panels; header fits one viewport above Panel 1.
1. Vocabulary cards → one collapsed chip row ("4 mots en jeu"), translations only on tap.
2. ACTUALITÉ block → one-line attribution beneath the news panel ("via RFI · ouvrir la source"), full text behind a tap; **fix the news summarizer garble** in `news_service` (broken token "sacolère", stray "I", "Personnes citées:" entity-dump artifacts).
3. Per panel: merge "PANEL N" + title into one small line; CONTEXT chip only when the word actually occurs in that panel's text; dialogue moves onto the art (F2) leaving the caption as the single text block.
**Acceptance:** 390px screenshot review against the budget; vocabulary/news content still reachable in ≤1 tap.

## WP-F5 — Tasks anchored to their panels (medium; revises WP-X6 default)
Replace the end-of-read aggregation: tasks render **inline, attached to their panel, collapsed** to a single "À toi —" line; submitting auto-expands the next unanswered task; reading straight through stays frictionless because collapsed tasks don't interrupt. Keep the completion gate and footer progress chip; drop the "Maintenant, à toi" section (or reduce it to a list of *unfinished* tasks at the end). Standalone scenes keep their current behavior.
**Acceptance:** every task is visually adjacent to its panel; a no-interaction scroll shows panels + captions only; gate/regression tests green.

## WP-F6 — Image-craft guardrails (small)
1. **Never depict phone/screen contents** (the key-icon problem): prompt rule — screens at an angle/from behind, reactions carry the information; validator flags image prompts matching "showing/displaying … on the screen".
2. **Foreground-prop dominance cap:** stop the giant mug/kettle in every frame — vary the POV signifier and limit foreground props to supporting scale (style-pack guidance).
3. **Shot variety:** structure templates carry a per-panel shot hint (wide establishing / medium / close-up / over-shoulder) so six panels stop being six medium shots of the same room.
**Acceptance:** prompts for a generated episode contain shot hints and no screen-content phrases; visual spot-check on the next live episode.

## Sequencing (F-series)
**F1** (root: story-true tasks + dialogue) → **F2** (bubbles, needs F1's bubble data) and **F4 + F6** (independent quick wins, parallel) → **F5** (task placement, after F1 so the inline tasks are worth anchoring) → **F3** (avatar, parallel long-lead image-pipeline track). F-series outranks the X/Y backlog except X1 (discoverability) and Y2 (CEFR engine), which stay queued as before — F1/F4/F6 fix what every learner sees every single day.
