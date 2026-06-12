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
