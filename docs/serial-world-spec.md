# Serial World — Engineering Spec (Missions × Feuilleton integration)

**Status:** Ready to build · **Audience:** engineering lead + subagents · **Decisions locked:** (1) mostly-linear with state flags (no full narrative forks in v1); (2) author-defined world bible, AI-generated episodes within it.

## Goal in one sentence
Turn two parallel mini-games (Missions, Feuilleton) into one ongoing life in French: the learner **acts** in a Mission → the world **replies** based on what they wrote → that writes a **state delta** → the next Feuilleton episode **dramatizes the consequence** and ends on a **cliffhanger** → the cliffhanger seeds the next Mission.

## Architecture (what we're adding)
A single lightweight spine entity, `SerialThread`, that both existing features hang off of. Everything else is **additive and nullable** — both features keep working standalone when `serial_thread_id` is null.

```
SerialThread                     one persistent story per user (a newcomer settling into a French town)
  ├─ world_bible : JSON          cast + setting + register map (author-seeded, stable)
  ├─ state       : JSON          flags set by what the learner did ("heating_fixed": false)
  ├─ news_seed   : JSON          today's editorial mechanic (keeps the news soul; refreshed per episode)
  └─ SerialEpisode[]             ordered installments, each ending on a hook
        ├─ mission_id  → RealWorldMission   (the "act" beat)      emits state_delta + hook
        └─ scene_id    → GraphicNovelScene  (the "see" beat)      reads state, ends on cliffhanger
```

## Prior art to lift (do not reinvent)
- `app/db/models/story.py` `Chapter.cliffhanger` JSON = `{text, hook, next_chapter_teaser}` → lift verbatim for our `hook` shape.
- `Chapter.branching_choices`, `Scene.consequences`, `Scene.transition_rules` → reference shapes for v2 forking.
- `app/db/models/npc.py` `NPC` (personality/speech_pattern), `NPCRelationship` (trust/mood), `NPCMemory` ("what the player said") → reference shapes for `world_bible.cast`.
- Mission `branch_state()` (`app/services/missions.py:2188`) and `objective_progress[].met` (correction schema `app/services/missions.py:46`) → the world-reply signal already exists.
- `GraphicNovelScene.mission_id` FK + continuation deep-link (`web-frontend/pages/graphic-novel.tsx:1650`) → cross-feature wiring already exists.

---

# Section 0 — Frozen contracts (owned by WP-1, every other WP codes against these)

These JSON shapes are the API between work packages. **No WP may change these without re-publishing.** All are stored as JSON columns / Pydantic `extra="allow"` dicts.

### `world_bible` (stable, author-seeded)
```json
{
  "logline": "A newcomer settles into the fictional town of Saint-Renan.",
  "setting": { "town": "Saint-Renan", "era": "present day", "tone": "warm, wry" },
  "protagonist": { "name": "Toi", "situation": "just arrived, renting an apartment" },
  "cast": [
    {
      "id": "landlord_marchand",
      "name": "M. Marchand",
      "role": "landlord",
      "register": "formal (vous)",
      "personality": "gruff but fair",
      "speech_pattern": "short, businesslike"
    }
  ],
  "register_map": { "landlord_marchand": "vous", "neighbor_lea": "tu" }
}
```

### `state` (mutable flags, the memory of the world)
Flat dict of namespaced booleans/short strings. Vocabulary is open but **namespaced by topic**; episodes read it, missions write deltas to it.
```json
{ "heating_fixed": false, "marchand_trust": "neutral", "has_met_neighbor": false }
```

### `state_delta` (what a completed Mission / choice-task emits)
```json
{
  "set": { "heating_fixed": true, "marchand_trust": "warmer" },
  "reason": "Learner's message was clear and hit all objectives.",
  "source": { "type": "mission", "id": "<uuid>", "score_0_4": 3.5 }
}
```

### `hook` (cliffhanger an episode ends on; lifted from `Chapter.cliffhanger`)
```json
{
  "text": "On rentre, et il y a une enveloppe glissée sous la porte.",
  "unresolved_question": "Who left the envelope, and what does it want?",
  "next_beat_kind": "mission",
  "teaser": "Demain : il faut répondre."
}
```

### `episode` envelope (what `GET /serial/today` returns for the current installment)
```json
{
  "thread_id": "<uuid>",
  "episode_index": 3,
  "kind": "mission",            // "mission" | "feuilleton"
  "mission_id": "<uuid|null>",
  "scene_id": "<uuid|null>",
  "hook_from_previous": { ... }, // the hook this episode is answering, or null
  "status": "available"          // available | in_progress | completed
}
```

**Deliverable for WP-1:** publish `app/schemas/serial.py` with Pydantic models for all five shapes above, plus a one-page `docs/serial-contracts.md` quoting them, before WP-2/4/6 start.

---

# WP-1 — Serial spine (models + contracts) · BLOCKING, ship first
**Owner:** backend/data agent. **Depends on:** nothing. **Unblocks:** all.

### Scope
New tables + nullable columns on existing tables + frozen Pydantic contracts. No business logic.

### Tasks
1. **New model** `app/db/models/serial.py`:
   - `SerialThread`: `id` (UUID pk), `user_id` (FK users, cascade), `status` (str, default `"active"`), `world_bible` (JSONB/JSON), `state` (JSONB/JSON, default dict), `news_seed` (JSONB/JSON, default dict), `current_episode_index` (int, default 0), `created_at`, `updated_at`. Relationship `episodes`.
   - `SerialEpisode`: `id` (UUID pk), `thread_id` (FK serial_threads, cascade, index), `episode_index` (int), `kind` (str: `mission`|`feuilleton`), `mission_id` (FK real_world_missions, SET NULL, nullable), `scene_id` (FK graphic_novel_scenes, SET NULL, nullable), `hook` (JSONB/JSON, default dict — the hook THIS episode ends on), `hook_from_previous` (JSONB/JSON, default dict), `state_delta` (JSONB/JSON, default dict), `status` (str, default `"available"`), `created_at`, `completed_at` (nullable). `UniqueConstraint(thread_id, episode_index)`.
   - Follow the exact column style in `app/db/models/mission.py` (use `JSONB().with_variant(JSON(), "sqlite")`).
2. **Add nullable columns** to `RealWorldMission` (`app/db/models/mission.py`) and `GraphicNovelScene` (`app/db/models/graphic_novel.py`): `serial_thread_id` (FK serial_threads, SET NULL, nullable, index) and `episode_index` (int, nullable).
3. **Register** all new models in `app/db/models/__init__.py` (`__all__` + import).
4. **Alembic migration**: one revision following the naming/style of `alembic/versions/b4c5d6e7f8a9_add_real_world_missions.py`. Must up/down cleanly on **both** sqlite and postgres.
5. **Schemas** `app/schemas/serial.py`: `WorldBibleRead`, `SerialStateRead`, `StateDelta`, `HookRead`, `EpisodeRead`, `SerialThreadRead`, plus request models `SerialThreadCreateRequest` and `SerialAdvanceRequest`. Use `ConfigDict(extra="allow")` like `app/schemas/missions.py`.
6. **Publish** `docs/serial-contracts.md` (quote Section 0 verbatim).

### Acceptance
- `alembic upgrade head` then `downgrade -1` clean on sqlite + postgres.
- `tests/conftest.py` imports the new models without error (add to the model import list if it enumerates them).
- New `tests/test_serial.py::test_thread_episode_roundtrip` — create a thread + 2 episodes, serialize via schemas, assert shapes match Section 0.
- Existing `tests/test_missions.py` and `tests/test_graphic_novel.py` still green (new columns are nullable, no behavior change yet).

---

# WP-2 — Mission "world reply" engine (grade → consequence)
**Owner:** missions-backend agent. **Depends on:** WP-1 (`state_delta`, `hook`). **Touch only** `app/services/missions.py` (+ read `app/schemas/serial.py`).

### Scope
Make the in-fiction reply depend on what the learner wrote, and emit a `state_delta` + `hook` on completion. Keep the 0–4 score under the hood (it picks the reply branch; it is no longer the surfaced payoff).

**Golden reference:** `docs/serial-episode-01-reference.md` Beat A — exact objective→reply→`state_delta`→`hook` worked example. Match that structure.

### Tasks
1. **Condition the reply.** In `MissionConversationService.respond` (`missions.py:2126`), pass the latest `objective_progress` (from the most recent attempt/turn `correction_payload`) and `branch_state` into the system prompt so the NPC reply branches: vague / unmet objectives → NPC is confused or unhelpful and asks for the missing detail; objectives met → NPC resolves the request in-fiction. Reuse existing `branch_state()` (`missions.py:2188`) — do not rewrite it; consume its `state`.
2. **New method** `MissionConversationService.resolve_outcome(*, mission, final_attempt_or_turns) -> dict` returning a `state_delta` (Section 0) — map `score_0_4` + `objective_progress[].met` to flag sets. The flag namespace comes from `world_bible`/`state` when `mission.serial_thread_id` is set; when null, return an empty delta (standalone missions unaffected).
3. **New method** `resolve_hook(*, mission, state_delta) -> dict` returning a `hook` (Section 0) — a 1–2 sentence unresolved question that teases the next beat. LLM-generated with a deterministic fallback (mirror the `_fallback_response` pattern at `missions.py:2171`).
4. **Surface, don't hide.** Extend `serialize_mission` (`missions.py:2229`) to include an optional `outcome` block (`{reply_text, state_delta, hook}`) when present, so the frontend can render the reply as the visible result.

### Interfaces (freeze these for WP-6/WP-7)
```python
def resolve_outcome(self, *, mission, attempts, turns) -> dict   # returns state_delta
def resolve_hook(self, *, mission, state_delta) -> dict          # returns hook
# serialize_mission(...) gains optional "outcome": {reply_text, state_delta, hook}
```

### Acceptance
- `tests/test_missions.py`: with `objective_progress` all-met fixture, `resolve_outcome` sets the success flag; with none-met, sets/keeps the failure flag.
- Same submission text → different NPC reply text under met vs. unmet fixtures (assert they differ).
- `serialize_mission` includes `outcome` only when a thread/outcome exists; standalone missions unchanged (regression assert).

---

# WP-3 — Mission stakes spectrum + visible difficulty
**Owner:** missions-backend agent (sequential after WP-2). **Touch:** `app/services/missions.py`, `app/schemas/missions.py`.

### Scope
A 3-tier rising-stakes ladder, visible to the learner and to the recommender.

### Tasks
1. **Generator.** In `MissionGenerator` (`missions.py:207`), add `stakes_level: int` (1–3) computed from cadence/episode position (or passed in). Feed it into objective count/difficulty and `min_words` (currently hardcoded at `missions.py:279`). Write `stakes_level` into `prompt_payload` (`missions.py:266`) and persist on the mission.
2. **Tiers:** 1 = quick low-pressure text; 2 = multi-turn negotiation; 3 = high-stakes, register-critical (tone failures matter — wire into `branch_state` tone check at `missions.py:2197`).
3. **Schema/serialize.** Add `stakes_level` to `MissionRead` (`app/schemas/missions.py:63`) and `serialize_mission`. If a genuinely new `mission_type` is required, extend the regex at `app/schemas/missions.py:91`; otherwise leave it.
4. **Recommender.** Expose `stakes_level` from `MissionScheduler.today` (`missions.py:1845`) so WP-7's orchestrator can pick a rising next beat.

### Acceptance
- `tests/test_missions.py`: same concept set yields 3 distinguishable tiers (objective count and `min_words` differ monotonically).
- Serialized mission exposes `stakes_level`; absent value defaults to 1 (back-compat).

---

# WP-4 — Feuilleton serial generation (state-aware panels + cliffhanger)
**Owner:** feuilleton-backend agent. **Depends on:** WP-1 (`world_bible`, `state`, `news_seed`, `hook`), WP-2 (`state_delta` shape). **Touch:** `app/services/graphic_novel.py`, `app/prompts/feuilleton/*`.

### Scope
Generate an episode that (a) uses the persistent cast, (b) reflects prior Mission outcomes via `state`, (c) ends the final panel on an unresolved hook instead of a clean resolution, (d) **rotates location** so the comic doesn't get visually stale, (e) **renders characters consistently**. **Keep the news mechanic.**

**Golden reference:** `docs/serial-episode-01-reference.md` Beat B — 6-panel beat sheet showing state-aware panels, news-via-Romy, embedded tasks, and the cliffhanger-not-recap final panel.

### Tasks
1. **Inject world + state into generation.** In the story-bible/script builder (`graphic_novel.py:2200–2360`), when `scene.serial_thread_id` is set: seed characters from `world_bible.cast` (instead of generating fresh ones at `graphic_novel.py:2240`), and pass `thread.state` into the prompt so panel beats branch on flags (e.g. `heating_fixed` → warm apartment; else → protagonist in a coat).
2. **Preserve the news soul.** Keep calling `fetch_feuilleton_daily_seed()` (`app/services/news_service.py:279`); inject today's `news_mechanic` as **"this week in town"** texture rather than the whole premise. `story_bible.news_mechanic` and `source_usage` attribution (`graphic_novel.py:2235`, `:2352`) stay intact.
3. **Cliffhanger, not recap.** Make the **final panel** pose an `unresolved_question` and write a `hook` (Section 0) onto the scene's episode. The vocabulary recap still renders but is demoted from the emotional last beat (WP-6 handles the visual ordering).
4. **Location rotation.** Pick the episode's setting from `world_bible.recurring_locations` per the `generation_guardrails.location_rotation` rule — **do not default to Le Mistral every episode** (never the same location two episodes in a row unless the plot demands it). The chosen `location_id` is written onto the episode for variety tracking.
5. **Character visual consistency.** Pass each present character's `visual_design` seed (and, once available, the locked reference from Design Backlog **DB-1**) into the image prompt so a character looks like themselves across panels and episodes. Until DB-1 lands, the seed fields are the best-effort source — wire the plumbing now so DB-1 drops in without code change.
6. **Prompt variant.** Add a `serial` variant to `app/prompts/feuilleton/style_pack_v2.yaml` / `visual_gag_writer_v2.yaml` that instructs: persistent cast, state-conditioned beats, location rotation, end-on-hook.

### Acceptance
- `tests/test_graphic_novel.py`: generated serial scene's final panel carries a `hook` with `unresolved_question`.
- Two different `state` fixtures (heating fixed vs. not) produce materially different final-panel beats.
- Two consecutive generated episodes do not reuse the same `location_id`.
- Image prompts include the character `visual_design` seed for each present cast member.
- News attribution (`source_usage`) still present in `script_payload`.
- Standalone (non-thread) scene generation unchanged (regression assert).

---

# WP-5 — Feuilleton choice-tasks become forks (authoring, not answering)
**Owner:** feuilleton-backend agent (sequential after WP-4). **Touch:** `app/services/graphic_novel.py`.

### Scope
Turn 1–2 `choice` overlay tasks into genuine branch points. Bounded/pre-authored continuations only (matches the locked "feeling of consequence" decision — no open generation per choice).

**Golden reference:** `docs/serial-episode-01-reference.md` Beat B, Panel 2 — the `choice` fork (shy `vous` vs. warm `tu`) with its `branch_target` → `state_delta` → next-panel change.

### Tasks
1. **Schema.** In the overlay normalizer (`_normalize_overlay`, `graphic_novel.py:2401`), accept a new optional `branch_target` on `choice` tasks: `{ "<option_value>": { "state_delta": {...}, "next_panel_beat": "..." } }`. The `choice` task already carries `options`/`expected_answer`/`accepted_answers`/`scene_function` (`graphic_novel.py:2429`) — extend, don't replace.
2. **Apply on submit.** In `GraphicNovelCorrectionService.submit_attempt` (called from `app/api/v1/endpoints/graphic_novel.py:129`), when a forked choice is answered, write the option's `state_delta` to `thread.state` and surface the chosen `next_panel_beat` so the following panel renders the branch.
3. **Generator authors both branches** up front (cheap, bounded) so there is no runtime image regeneration; pre-render both panel variants or pick a text-overlay-only delta if image regen is too costly for v1.

### Acceptance
- `tests/test_graphic_novel.py`: a `choice` task with `branch_target` yields two different subsequent panel beats depending on the answer.
- Submitting the choice persists the option's `state_delta` into the thread's `state`.
- Non-forked choice tasks behave exactly as today (regression).

---

# WP-6 — Atelier on-ramp + serial UI (the seamless surface)
**Owner:** frontend agent. **Depends on:** WP-1 serialized shapes (can stub against frozen contracts before WP-2/4/7 land). **Touch:** `web-frontend/pages/atelier.tsx`, `web-frontend/pages/missions.tsx`, `web-frontend/pages/graphic-novel.tsx`, `web-frontend/lib/atelier-next.ts`.

### Scope
The thread becomes the prominent on-ramp; mechanic names recede; the cliffhanger replaces the recap as the last beat; the Mission NPC reply renders as the visible outcome.

### Tasks
1. **Living-thread copy.** Replace the `"Mission"` / `"Feuilleton"` mechanic cards at `atelier.tsx:885–902` and the resolver `resolveRecommendedNext` (`atelier-next.ts:37`) with thread-driven copy — e.g. "The landlord replied", "Continue the story" — surfaced prominently at the session recap. Add a `RecommendedAction` variant `{ kind: 'serial'; threadId; episodeKind; query }` (`atelier-next.ts:14`).
2. **Cliffhanger card.** Rework `FeuilletonContinuationCard` (`graphic-novel.tsx:1637`) and the mission completion view so the **last beat is the cliffhanger** ("→ Next episode"), not the vocab recap. Vocab recap stays available but secondary. Reuse the existing `ContinuationCard` component (`web-frontend/components/mobile/ContinuationCard.tsx`) — it already has `feuilleton`/`mission` tones and focus chips.
3. **Render the reply.** In `missions.tsx`, render WP-2's `outcome.reply_text` (the NPC's in-fiction reply) as the visible result of a submission, with the score de-emphasized.
4. **Deep-link continuity.** Keep carrying `serial_thread_id`/`atelier_session_id` through the existing query-pair plumbing (`graphic-novel.tsx:1650`).

### Acceptance
- Atelier session recap shows one prominent serial on-ramp (not two parallel mechanic cards).
- Completing a Mission shows the NPC reply + a "next episode" hook card.
- Completing a Feuilleton episode ends on a cliffhanger card; recap demoted.
- `web-frontend/lib/atelier-next.test.js` and `tests/test_frontend_atelier_thread.py` updated and green.

---

# WP-7 — Serial orchestration + endpoints (the glue) · ship last
**Owner:** backend/orchestration agent (ideally same as WP-1). **Depends on:** WP-1..WP-5. **Touch:** new `app/services/serial.py`, new `app/api/v1/endpoints/serial.py`, `app/main.py`.

### Scope
The service that creates/advances a thread and routes each episode to the right feature with the right context.

### Tasks
1. **`SerialThreadService`** in `app/services/serial.py`:
   - `get_or_create_thread(user) -> SerialThread` — seed `world_bible` from the author template at **`app/prompts/serial/world_bible_paris_v1.json`** (Paris + the five-person HIMYM-style cast) and `thread.state` from that file's `initial_state` block; seed `news_seed` from `fetch_feuilleton_daily_seed()`. Note: the world bible's `generation_guardrails.news_integration` says to route the daily news seed through **Romy (the journalist character)** — pass that instruction into WP-4's generation prompt.
   - `today(user) -> dict` — return the current `episode` envelope (Section 0): is the next beat an act (Mission) or a see (Feuilleton)?
   - `start_mission_beat(thread)` — call `MissionScheduler(db).create(...)` (`missions.py:create`, signature includes `atelier_session_id`, `preferred_concept_ids`, `use_news`, etc.) passing thread context; link the resulting mission via `serial_thread_id`/`episode_index` and a `SerialEpisode` row.
   - `start_feuilleton_beat(thread)` — call `GraphicNovelScheduler(db).create(...)` (`graphic_novel.py:create`, signature includes `mission_id`, `atelier_session_id`, `use_news`, `preferred_concept_ids`, `target_vocabulary_ids`) passing thread `state` + `news_seed`; link via `serial_thread_id`/`episode_index`.
   - `apply_completion(thread, *, mission=None, scene=None)` — on Mission/Feuilleton completion, merge the emitted `state_delta` into `thread.state`, store the `hook` on the episode, advance `current_episode_index`, and decide the next `next_beat_kind` (alternate act/see, biased by `stakes_level` from WP-3).
2. **Router** `app/api/v1/endpoints/serial.py`: `GET /serial/today`, `POST /serial/threads` (create/seed), `POST /serial/threads/{id}/advance` (apply completion + return next episode). Mirror auth via `get_atelier_user` like `app/api/v1/endpoints/missions.py:13`.
3. **Wire** the router into `app/main.py` (follow how missions/graphic-novel routers are included).
4. **Feature flag.** Gate the whole spine behind a setting (e.g. `SERIAL_WORLD_ENABLED` in `app/config.py`) so it can ship dark and light up per-user.

### Acceptance
- New `tests/test_serial.py::test_full_loop`: create thread → Mission (heating message, objectives met) → `state.heating_fixed=true` → Feuilleton episode generated reflects warm apartment + ends on hook → next Mission seeded from the hook.
- Back-compat: `tests/test_missions.py` / `tests/test_graphic_novel.py` green; both features still creatable standalone with `serial_thread_id=null`.
- With `SERIAL_WORLD_ENABLED=false`, `/serial/*` returns disabled and the two features behave exactly as today.

---

# Design backlog (content & art — parallel, non-engineering, but DB-1 gates WP-4 quality)

These are **design/content tasks**, not code. They run alongside engineering. Owner: design + content (not the subagents). Track separately from WP-1..WP-7. **Full brief: [serial-world-design-package.md](serial-world-design-package.md)** — Part A (seamless integrated UX) and Part B (persistent character/location assets + the `visual_design` contract). DB-1/DB-2 below are delivered through that package.

| ID | Task | Why it matters | Blocks |
|----|------|----------------|--------|
| **DB-1** | **Delivered:** character visual reference sheets for `user`, `marin_leveque`, `lila_bonnet`, `augustin_de_roncourt`, `romy_tremblay`, `margaux_barman`, and `landlord_marchand` are stored under `web-frontend/public/assets/serial/characters/<id>/model-sheet.png` and wired into `world_bible_paris_v1.json` as `assets-locked-v2`. | A persistent-cast AI comic falls apart if characters morph between panels. This is the single biggest art risk. | Complete for the current cast; future cast additions must include the same asset contract before they enter generated panels. |
| **DB-2** | **Mostly delivered:** location plates are wired for Le Mistral, the user's apartment, Marin & Lila's flat, the newsroom, Marin's NGO office, the Canal market, Buttes-Chaumont, the métro platform, Gus's loft, and the admin office. `brocante` still needs a dedicated plate. | Prevents the "always Le Mistral" monotony the rotation rule fixes mechanically; keeps new locations on-brand. | WP-4 polish; brocante remains the only missing recurring-location asset. |
| **DB-3** | **Expand the world bible / cast over time** — deepen secondary characters, add recurring guests, evolve `season_one_situation` open threads into authored arc beats. `world_bible_paris_v1.json` is v1 of an ongoing content asset. | The bond and serial pull deepen with authored continuity, not just generation. | Ongoing; not a launch blocker. |
| **DB-4** | **Author more episode golden references** beyond Episode 1 (`docs/serial-episode-01-reference.md`) — at least one mid-season episode showing a non-Mistral location and a state-heavy branch. | Gives WP-4/WP-5 more than one target to match; de-risks generation quality. | Quality, not launch. |

# Sequencing & ownership

| Phase | Packages | Agents (parallel) |
|------|----------|--------------------|
| 1 (blocking) | **WP-1** | data agent |
| 2 (parallel) | **WP-2 → WP-3** · **WP-4 → WP-5** · **WP-6 (stubbed)** | missions agent · feuilleton agent · frontend agent |
| 3 (integrate) | **WP-7**, then frontend swaps stubs for real payloads | orchestration agent + frontend agent |

**Hard rule:** WP-1's Section 0 contracts are frozen before Phase 2 begins. If a Phase-2 agent needs a contract change, it goes back through WP-1 and is re-published — agents do not edit each other's contracts ad hoc.

**File-ownership boundaries (avoid collisions):**
- missions agent → `app/services/missions.py`, `app/schemas/missions.py` only.
- feuilleton agent → `app/services/graphic_novel.py`, `app/prompts/feuilleton/*` only.
- frontend agent → the four `web-frontend` files listed in WP-6 only.
- data/orchestration agent → `app/db/models/serial.py`, `app/schemas/serial.py`, `app/services/serial.py`, `app/api/v1/endpoints/serial.py`, `app/main.py`, `app/config.py`, the migration.

# Global acceptance (definition of done)
1. Full loop test green (WP-7).
2. Both features still pass their existing suites standalone (back-compat).
3. News attribution preserved end-to-end (WP-4).
4. Spine is feature-flagged and ships dark by default.
5. Migration reversible on sqlite + postgres.
6. No WP touched a file outside its ownership boundary.
