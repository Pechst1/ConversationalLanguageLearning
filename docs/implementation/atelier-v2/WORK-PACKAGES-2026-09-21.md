# Work packages — 2026-09-21: depth, long horizon, variety

Owner brief: coherence, consistent quality, fun, diversity of experience; the Courrier
(missions) and the Feuilleton need **depth and a long-horizon story that works without being
deterministic**.

## 1. Findings that drive the packages (code-cited)

**Feuilleton (living story, `app/services/living_story.py`)**
- Memory is a flat tail: `events[-40]`, `story_so_far[-8]`; nothing is compacted, so day 100
  cannot reference day 5 (`MAX_HISTORY`, `story_context`).
- Branches die with their chapter (`developments` capped per chapter); moods decay to neutral
  in ~2 scenes — a betrayal is forgotten in two days.
- No payoff/foreshadow ledger; cast `secret`s are static prompt text, reveals are never checked.
- Hard ceiling: 5 arcs × 22 stages ≈ 88 days, then `suggested_arc=None` — no finale, no
  season 2, no interlude in the living engine (`world_bible_paris_s2.json` uses
  `season_two_situation`, which `_season_projection` cannot read).
- Characters have no off-screen life; `open_threads` are prose with no state.
- Every chapter is the same 4 beats; `stale_problem` forbids any problem from recurring, so
  nothing can escalate; an arc stage advances whether or not its content happened.

**Courrier (missions, `app/services/missions.py`)**
- One-way coupling: story mood colours the letter, but no mission code writes
  `state["living_story"]`. A rude letter to Romy changes nothing tomorrow.
- `resolve_outcome` is a stub hard-coded to episode 1's radiator; otherwise two dead keys.
- Selection is fully deterministic (`_choose_variety` → `ordered[0]`, alphabetical tiebreak;
  fuel source `count % 3`).
- No correspondent continuity, no chains, no deadlines, no failure state; `stakes_level` inert.
- Success hinges on a keyword heuristic (`branch_state`); the debrief shows invented numbers
  (`naturalness = 55 + words*0.45`).
- Home has no Courrier entry; the main route in was the legacy serial, now bypassed.

**Daily experience**
- Day 1 = day 10 = day 40: one hard-validated template (scene → ≤2 recall → 1 respond →
  resolution, `journey_contracts.py:411-421`); 3 recall formats in the daily loop while 8 richer
  ones sit in the off-day Séance.
- Register is graded and never shown; achievements have an API and a settings toggle and no page;
  Dossier/Répétition are off-nav; English leftovers in `atelier.py` `why` templates and
  `product-shell.ts` ('Settings').

## 2. Principles for every package

1. **Non-deterministic, not random.** Variation comes from per-learner seeded dice
   (`sha256(thread_id:…)`, as WP-59 does) plus the model — reproducible in tests, different per
   learner, never a fixed catalogue order and never a hard-coded script.
2. **State over prose.** Anything the story must remember is a ledger row in
   `state["living_story"]`, written deterministically from accepted model output — not a hope
   that the prompt remembers.
3. **Consequences outlive their chapter**, and every surface that talks to a character reads
   and writes the same relationship state.
4. **Honest numbers only** (the July rule): no metric that is a formula over word count.
5. French chrome, av2 components, learner's language for explanations. No mascots, no social.
6. Budget rule stands: two attempts inside 75 s (`test_living_story_budget`); new context must be
   compact (chronicle ≤ ~1,200 chars).

## 3. Packages

### WP-62 — La mémoire longue (story long-term memory)  · wave 1 · owns `living_story.py`
- `chronicle[]`: when a chapter resolves, fold it deterministically into one digest (title,
  question, how it resolved, the development the learner made true, who, where, one source
  quote, day index). Never capped below a season; older seasons fold into a season digest.
- `consequences[]`: durable ledger of learner-made branches and mood breaks (|shift| ≥ 2, broken
  or kept commitments) with `weight` and `last_referenced`; survives chapters. Trust no longer
  decays; only surface mood does.
- `planted[]`: foreshadow ledger — a scene may plant a detail (`plant_fr`), a later scene may pay
  it (`pays_plant_id`); unpaid plants older than N chapters are offered to the director.
- `story_context` sends chronicle + top consequences + one seeded **callback candidate** per
  setup beat; `_scene_score` rewards a draft that truly references it (quote/entity overlap),
  guard `fabricated_callback` rejects an invented past.
- Secrets get state: `secrets{char_id: hidden|hinted|revealed}` advanced only when a scene's
  accepted output does it; reveal order seeded.
- Tests: 120-day fake-provider run — day 100 context contains a day-5 fact; context size bounded;
  budget test stays green.

### WP-63 — L'horizon de saison (agendas, threads, shapes, finale, season 2) · wave 2 after WP-62
- Character **agendas**: each cast member has an authored 4–6 step private agenda in the world
  bible; between chapters a seeded tick advances 0–1 of them off-screen and records a
  `meanwhile` event the learner can hear about second-hand (witness rules respected).
- `threads{}`: `open_threads` become stateful (open → developing → closed) and the season page
  shows them.
- Arc gating: honour `entry_requires` / `min_episodes_between_stages`; a stage advances only when
  the actor marks its content as happened (else the chapter counts as a side story).
- Escalation instead of the blanket `stale_problem` ban: a problem may return once as an
  escalation linked to a consequence or plant.
- **Chapter shapes** dealt by seeded dice: standard 4-beat, two-hander (3), bottle (one
  location, 4), ensemble (5), letter chapter (a Courrier letter is the turn beat — hook for WP-64).
- Season end: when arcs are ≥ 80 % complete, a finale chapter built from the heaviest
  consequences and unpaid plants; then an authored interlude and season 2 (fix the s2 bible
  key; carry chronicle/consequences/trust across).
- Tests: 200-day fake run never reaches `suggested_arc=None` without a finale; two seeds give
  different arc orders, shapes and agenda timings.

### WP-64 — Le Courrier vit dans l'histoire (missions backend) · wave 1 · owns `missions.py`
- New `app/services/story_correspondence.py` (no edits to `living_story.py` beyond imports):
  on completion, write an `events[]` row (witness = the correspondent), apply mood/trust via the
  existing mood structure, open/close commitments for promises made in the letter. Replace the
  `resolve_outcome` stub with the corrector's per-objective flags → `kept | partial | missed`.
- **Correspondent threads**: prior letters with the same contact (last 3, summarised) go into
  `build_payload` and the actor prompt; `callbacks` finally written.
- **Chains**: a mission may be letter 1..n of a 2–4 letter affair across days with escalating
  `stakes_level`; outcome of letter k shapes letter k+1 (seeded + model). Letters get a soft
  `expires_at`; an ignored letter is a consequence (correspondent cools, mentions it), never a
  punishment screen.
- **Story-born letters**: after a journey resolution the engine may (seeded, ≤ 2/week) have a
  character write to the learner about what just happened; living-story threads stop depending
  on `SERIAL_WORLD_ENABLED`.
- **Selection**: seeded weighted sampling over domain × contact × format with recency penalties;
  replace `ordered[0]` and `count % 3`.
- Success = objective flags from the corrector, not `branch_state` keywords; delete the invented
  debrief numbers (keep only measured: objectives met, repairs, words learned).
- Tests: writeback reaches tomorrow's `story_context`; two seeds → different first three
  missions; chain of 3 with a missed middle letter.

### WP-65 — Le Courrier, surface (frontend) · wave 2 after WP-64
- Home entry for the Courrier (unread letter = the day's second action, one-CTA rule kept).
- Correspondent view: the thread with one person over weeks, their current mood line, chain
  progress («2ᵉ lettre sur 3»), soft expiry («répond avant jeudi»).
- Honest debrief (objectives, repairs, what the character now thinks) — av2, French chrome.
- Feuilleton reader shows «une lettre vous attend» when a story-born letter exists.

### WP-66 — Des journées qui ne se ressemblent pas (journey shapes + formats) · wave 1 · owns `journey_*.py`, `journey/*`
- **Day shapes**, seeded per learner per week, validated as a set instead of one template:
  standard · *jour de lettre* (respond step is a Courrier letter) · *jour d'écoute* (scene heard
  first, dictation-style recall) · *jour de reprise* (errata-led, at chapter end, with a chapter
  recap) · *jour court* (3 steps, after a missed day). No two identical shapes on consecutive
  days; chapter beat informs shape (resolution beat → reprise).
- Bring three Séance formats into recall: `transform`, `classify`, `word_bank` (no-spoil gates
  stay aligned — see the three-gates rule), rotated by seeded dice and by target type.
- **Register shown**: the graded register result appears on the resolution step as one French
  line with the learner-language reason.
- Contract parity tests + frontend model tests updated; a 28-day planner run shows ≥ 4 shapes
  and ≥ 5 formats, none > 50 %.

### WP-67 — Une seule qualité (consistency + phantom loops) · wave 1 · owns `atelier.py` copy, shell, settings
- Translate the remaining English `why`/fallback strings through `learner_copy`
  (`atelier.py:1571,1586-1589,3120-3126,4550`), `resolveProductTitle` 'Settings', settings hint.
- Achievements: mount one honest av2 «Distinctions» section inside the Dossier fed by the
  existing API — or remove the toggle and endpoints' UI promise; no phantom loop stays.
- Reachability: Dossier and Répétition get real entries (Home row / Cahier), per WP-37 hooks;
  F-27 «Écouter d'abord» before the first planche; F-30 Séance ladder starts at the placement
  estimate.
- A static test that fails on English chrome strings in learner-facing av2 components.

### WP-68 — La preuve (long-horizon evidence) · wave 3
- One fake-provider harness that plays 120 days of journey + Courrier for two seeds and asserts:
  callbacks to old chapters, consequences referenced, agendas ticking, finale reached, mission
  writeback visible in the next scene, day-shape/format distribution, context + budget bounds.
- Prepared (not run) paid live review: `scripts/review_living_story.py --live --days 14` at A2
  and B1 with the new ledgers, cost estimate stated; owner consents before any spend.

Out of scope: per-panel illustration (WP-23, owner-deferred), pronunciation (WON'T-DO),
owner-only rollout steps (Render, cohort, Apple team, TTS_PROVIDER).

## 4. Dispatch

Wave 1 in parallel (≤ 4 agents — more stall): WP-62, WP-64, WP-66, WP-67.
Wave 2: WP-63 (needs WP-62), WP-65 (needs WP-64). Wave 3: WP-68.
Rules for every agent: Codex shares this checkout — never `git checkout`/`stash`/`reset`;
commit only your own files by name; don't touch another package's owned files; per-file pytest
(full suite is ~35 min); tsc + lint + node suites for frontend; write `WP-NN-*.md` evidence.
