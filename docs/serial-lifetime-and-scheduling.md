# Serial — Scheduling & Lifetime Continuation (plan)

Answers to: *when do Feuilletons appear in the learning journey?* and *how does the storyline keep going over a learner's whole lifetime in the app?* — plus the remaining work packages from the latest review.

---

## What was just fixed (this pass)
- **The "all caught up" bug (root cause).** `SerialThreadService.apply_completion()` existed but **nothing ever called it** — finishing a mission only ran `MissionScheduler.complete()`, so the thread froze at episode 0 and the Atelier on-ramp fell back to "rest / caught up". Now **both `/missions/{id}/complete` and `/graphic-novel/scenes/{id}/complete` advance the serial thread** (resilient: if the next beat fails to generate, the index has already advanced and `/serial/today` regenerates it lazily). Idempotent + rollback-guarded. Locked by `test_mission_complete_endpoint_advances_serial_thread`.
- **"Carry the mission into practice" pedagogy card removed** for serial missions (the legacy `MissionBridgePanel` now only renders for non-serial missions).
- **World assets confirmed present & linked**: 7 character model sheets + style refs, 10/11 location plates (only `brocante` missing), 1 prop — all wired into `visual_design.*.reference_images`. The Feuilleton image prompts already consume them.

---

## 1. When are Feuilletons scheduled in the learning journey?

**Model: one serial *beat* per day, surfaced at the daily recap, alternating act → see.**

The daily Atelier flow is: **session (6 rounds) → review → the serial beat.** The serial alternates:
- **Act day (Mission):** you *do* something in French (text the landlord, propose to meet, negotiate).
- **See day (Feuilleton):** the illustrated consequence of what you did, ending on a cliffhanger.

So a typical week reads: *Mon you message Marchand → Tue you see the cold-flat/café episode → Wed you act on the café hook → Thu you see it play out…* This gives a **daily reason to return** ("what happened after my message?") and paces image-generation cost to ~one Feuilleton every other day.

**Two cadence anchors on top of the daily beat:**
- **The daily beat** is the engine (above).
- **A weekly "edition"** (Sunday Feuilleton): a richer illustrated installment that folds in the week's real French news via Romy — this is the literal newspaper-*feuilleton* beat and keeps the news engine alive on a predictable rhythm.

**Where it surfaces:** the serial beat is the prominent on-ramp at the end of the Atelier session/review recap (`resolveRecommendedNext` already prefers the serial action over the legacy day-flags). The grammar/vocab from that day's session is the **fuel** the next beat is generated from.

**Pacing rule:** never force the story. If a learner skips days, the thread waits — no guilt, no decay. A "Previously on…" header re-onboards returning users.

---

## 2. How the storyline continues over the learner's whole lifetime

Six mechanisms, layered, so the serial never runs out and never goes stale across months/years:

**a) Seasons & arcs (authored rails).** The lifetime is structured as **seasons** (~8–12 episodes each). Each season advances and resolves one or two of the world bible's `open_threads` (Marin's proposal, Lila's Berlin secret, Gus's exposure, the Romy romance, you settling in) and opens new ones. When season 1's threads resolve, **season 2** introduces fresh situations on the *same persistent cast* (a new job, an apartment move, a trip, a new recurring character). Season bibles are authored; the cast and town persist.

**b) Procedural episodes within those rails (AI-generated).** Between the authored "tentpole" beats (season openers, finales, thread-resolving episodes), the **LLM episode generator** (`_serial_episode_plan`) produces fresh episodes from: world bible + current season arc + `thread.state` + the day's news. This is infinite content that still stays on-model. Authored tentpoles guarantee the big emotional beats land; generation fills the everyday.

**c) Difficulty ramps with the learner (CEFR).** As proficiency climbs A2 → B1 → B2 → C1, the **mission `stakes_level`** rises (quick text → negotiation → high-stakes register-critical) and the Feuilleton's French gets richer. Same cast and town, harder situations and register. The story complexity tracks the learner.

**d) State accretion = personalization.** `thread.state` grows with every choice and outcome (relationships, flags, the branch you picked). Episode 60 reads from a rich state, so the story is genuinely *yours* — and two learners' threads diverge via the choice forks (WP-5).

**e) The news engine keeps it current.** Every episode can pull the day's real French news through Romy, so even episode 200 feels of-the-moment. This is the renewable fuel that prevents staleness over years.

**f) Rolling "story so far" memory (continuity at scale).** A short, rolling summary of the arc is maintained and fed into generation — long-term coherence without sending hundreds of episodes of history each time (keeps cost bounded and the cast consistent across the whole lifetime).

The net retention promise: the reward for practicing French is never "a correction" — it's **the next installment of a life you're building in Paris with people you've come to care about**, that keeps pace with your level and never repeats.

---

## Work packages — status

### WP-G1 — The cold open / "Episode 0" (story on-ramp) · ✅ IMPLEMENTED
A `cold_open` block was added to the world bible (eyebrow/title/dateline/paragraphs/cta/footer), surfaced into the Episode 1 mission `source_snapshot`, and rendered by a new `ColdOpen` component on the missions page — a full-bleed ink prologue (the rainy first night, you know no one, the radiator) shown **before** the first mission, dismissed once per thread via localStorage ("Begin Episode 1"). The mission no longer opens cold on a form. Locked by a `test_full_loop` assert on `source_snapshot.cold_open`.

### WP-G2 — Scheduling/cadence · ✅ IMPLEMENTED (v1)
Alternation act→see is driven by the hook's `next_beat_kind` (now reliably triggered by the completion→advance fix). `serialize_episode` now exposes `episode_label` ("Episode N"), `beat` ("act"/"see"), and `previously` (the prior hook text) so the on-ramp and "Previously on…" re-onboarding render from real data. *Deferred:* the dedicated weekly "Sunday news edition" cadence (currently the daily beat already routes news through Romy).

### WP-G3 — Rolling memory + arc continuity · ✅ IMPLEMENTED (rolling memory); season engine deferred
`apply_completion` now records a short beat summary into `thread.state["story_so_far"]` (capped to the last 12) plus an `episodes_completed` counter. This rolling memory feeds the next mission seed (`Story so far: …`) and flows into the Feuilleton generator via `thread.state`, keeping long threads coherent without replaying full history (bounded cost). Locked by `test_full_loop` asserts. *Deferred (needs authoring):* multi-season bibles + thread-resolution scripting + the CEFR→stakes auto-ramp curve. The `_stakes_level` ladder already rises with mission count as an interim.

### WP-G4 — Mission visibly *yields* story · ✅ IMPLEMENTED
Completion → `state_delta` merges into `thread.state` → the next Feuilleton reads state (warm vs. cold apartment, Marchand trust) and the next mission seed references the rolling summary + prior hook. The act now demonstrably moves the plot.

### Remaining follow-ups (not code)
- Generate the missing **`brocante`** location plate (the one gap in DB-2) from the prompt in `docs/serial-image-prompts.md`.
- **Enable the story LLM in production** so the Feuilleton "see" beats are freshly generated; the deterministic fallback still replays the templated pilot (see #1 in the generator review). This is config, not code.
- **Authored season 2 bible** when season 1's open threads resolve (content task).
