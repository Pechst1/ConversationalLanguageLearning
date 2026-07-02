# Missions Overhaul — Final Work Package (handoff, v2)

A Mission is a short, standalone, real-world French moment you play through: someone
messages you, you handle it in French, the world reacts in character, and **the mission
resolves the instant you have actually solved the real-life problem.** It must be FUN,
REAL, CREATIVE — and it must teach (spaced repetition + repair), without ever feeling
like a worksheet.

This v2 fixes what the first build got wrong (see the critique at the end).

---

## Locked decisions
1. Missions and the serial are **fully separate features**. "Mission" = standalone,
   vocab-fed real-life moment in the home. The Feuilleton is pure story, never "Mission."
2. **No separate design agent.** Build to the lean Mission mockup. Simplicity is a hard
   requirement: one frame card → chat → debrief. Nothing else.

## North star (acceptance criteria, not vibes)
- **FUN:** ~2–4 min, the world reacts to what you wrote, small humour/twists, you win by
  getting what you needed; completion mints a reward — never a score, never grammar labels.
- **REAL:** authentic everyday situations, authentic channels (text / email / voice / counter
  / form), authentic register (tu/vous), real in-fiction consequences.
- **CREATIVE:** a variety engine so no two missions share domain, contact, channel, or tone.

---

## ★ The completion model (the missing backbone)
This is the single most important addition. The old build had no notion of "done," so the
conversation dragged on past the goal and the user never knew if they'd succeeded.

- Every mission declares **2–4 concrete success objectives** = the real-life things that
  must be accomplished. (Delivery example: ① confirm your address · ② flag that the photo
  shows the wrong door · ③ give the tracking number / order ref.)
- The in-character agent **steers toward the unmet objectives** in-fiction (it naturally
  asks for whatever is still missing — never a checklist on screen).
- The mission **RESOLVES the moment all objectives are met**: the character gives one warm
  closing line ("Parfait, je relance la livraison pour demain — bonne journée !"), the
  header flips to RESOLVED, the token mints. It must NOT keep asking filler questions after
  the goal is reached.
- If the learner stalls, the agent gives a gentle in-fiction nudge toward the missing
  objective (it never says "you forgot objective 2").
- **Acceptance:** the delivery mission ends right after the tracking ref is given, with a
  satisfying close — not three more questions.

## ★ Words + spaced repetition (the weave — answers "what about the words?")
The old build showed a disconnected chip strip (durée · séance · site) that the scenario
never used. Replace entirely:
- Target items = the learner's **due + recently-nailed SRS words** AND the **active grammar
  focus**, fed to generation so the scenario is built to *naturally require them*. (If
  "colis / livraison / adresse" are due, the delivery scene is chosen.) No chip strip.
- Using a target word or the focus structure in the conversation **credits it back to the
  SRS / Coverage Map** (real-life use = the strongest reinforcement).
- **Acceptance:** the words shown (if any) are ones the scene actually needs; using them
  advances the atlas; no alphabetical junk.

## ★ Errors → repair (answers "why are errors not corrected?")
Correcting mid-scene would break immersion (the character is a person, not a tutor — already
fixed). So:
- Every user message is **silently graded in the background** (reuse `correct_submission` /
  the errata pipeline). Nothing is shown during the scene.
- At resolution, a short, calm **debrief** appears: "Handled ✓ · 2 to repair," listing the
  exact fixes from this conversation ("*ma* porte, not *mon* porte"; "bien *sûr*";
  "Chartreuse"). Each becomes a **repair slip / erratum that enters spaced repetition** and
  surfaces later in the Repair queue.
- **Acceptance:** the `mon porte` / `bien sur` errors from the screenshot are captured and
  show up in the post-scene debrief and the Repair queue — not lost.

## ★ Token semantics (answers "what does TOKEN WAITING mean?")
"TOKEN WAITING" was a confusing pending-state card. Remove it. There is one token, minted
**only on resolution** (all objectives met). It's the geometric-form reward for solving a
real situation. No waiting state, no duplicated task text.

---

## Declutter to the concept (answers "too crowded")
The screen is exactly three regions, nothing more:
1. **Frame card** — icon · "MISSION" · one-line scene ("Service client · a delivery photo
   that isn't your door") · the ask in one sentence · Translate. (Drop the ghosted domain
   title, the repeated task text, the chip strip, the separate "TOKEN WAITING" card.)
2. **Chat thread** — incoming bubbles (with Translate) and your replies. That's it.
3. **Resolution** — RESOLVED header → debrief (handled ✓ · repairs) → token → "Coverage
   map" / "New moment."

---

## Work packages

- **WP‑M1 — SRS-fed generation.** `MissionScheduler.today` builds a standalone mission from
  **due + recently-nailed words + active grammar focus**, choosing a scenario domain that
  *needs* them; CEFR-scaled; FUN/REAL/CREATIVE prompt; emits **2–4 success objectives**.
- **WP‑M2 — Completion model.** Track objectives; agent steers to unmet ones; resolve the
  instant all are met with a warm close; gentle nudges if stalled. (The backbone.)
- **WP‑M3 — Lean screen.** Rebuild `missions.tsx` to the three regions above; ~70% smaller;
  Translate everywhere; no chips, no token-waiting, no repeated text.
- **WP‑M4 — Errors → repair debrief.** Background-grade each turn; at resolution show the
  debrief and push errata into the SRS Repair queue; credit used target words to coverage.
- **WP‑M5 — Variety engine.** No repeat of domain/contact/channel/tone across recent
  missions; rotate vocab / theme / news-seed fuel.
- **WP‑M6 — Home entry + serial decouple.** Add a "Mission" step to the home `pathSteps`;
  ensure the serial never surfaces as "Mission."

## Sequencing
WP‑M1 → WP‑M2 (completion) → WP‑M3 (lean screen) → WP‑M4 (repair debrief) → WP‑M5 (variety)
→ WP‑M6 (home + decouple, last).

## Anchors
- Engine: `app/services/missions.py` (`MissionGenerator`, `MissionScheduler`,
  `MissionConversationService`, `correct_submission`), `app/api/v1/endpoints/missions.py`.
- SRS feed/credit: `app/services/vocabulary_coverage.py` (`recently_nailed_vocabulary`),
  `ProgressService.get_vocabulary_recommendations`, `ErrorMemoryService` (errata),
  `app/services/unified_srs.py`.
- CEFR: `cefr_generation_profile` in `serial_arc_planner.py`. Reward: `atelier_rewards.py`.
- Home pathway: `pathSteps` in `web-frontend/pages/atelier.tsx`.
- Screen: `web-frontend/pages/missions.tsx`. Translate: `/atelier/translate`.

## What the first build got wrong (for the agent's awareness)
- No completion model → conversation dragged past the solved goal.
- Target words were a disconnected chip strip (durée/séance/site) the scene never used.
- Errors (`mon porte`, `bien sur`) were never captured or corrected anywhere.
- "TOKEN WAITING" card + repeated task text + chips = clutter, far from the simple concept.
- Not woven into spaced repetition (due words/grammar in; errors/used-words out).
