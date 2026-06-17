# Fix package — the Mission/Episode experience (the "Le radiateur" screen)

**Problem (observed):** pressing "Start first episode" lands the learner on a grading stack — `PARTIAL · 3/4 clarity`, `1 VOCABULARY TARGET MISSING`, `RED INK REPAIR` — with no story, no character reply, no forward pull, and three heavy dark cards crowded together. The backend already produces the landlord's in-fiction reply + a cliffhanger hook (WP-2); the screen ignores them and foregrounds the score.

**Goal:** the act beat should read as **a scene you're living**, not a test you're passing. Lead with story → let you write to a character → show the character's *reply* as the payoff → end on a hook into the next beat. Grading becomes a quiet, optional footnote.

**Root cause:** WP-6 wired serial *copy* and *tokens* but never adopted the WP-2 `recap.outcome` (`reply_text` + `hook`) into the Mission render, and never gave the Mission screen episode/story chrome. The UI still renders `correction` (score, missing targets, red-ink) as the hero.

---

## WP-F1 (Frontend) — Make the reply the hero; demote grading · **highest impact**
Owner: frontend agent. File: [missions.tsx](../web-frontend/pages/missions.tsx).
- Render the NPC's in-fiction **reply** (`mission.recap.outcome.reply_text`, and the per-turn assistant reply) as the centerpiece after a send — in M. Marchand's character accent (`--char-marchand`), as a person speaking, not a correction.
- Collapse the grading stack into **one quiet, tappable "writing notes"** affordance (progressive disclosure). The `clarity score`, `missing targets`, and `RedInkRepairSlip` live *inside* that, closed by default. Never show three correction cards at once.
- Surface the **hook** (`recap.outcome.hook`) as the single forward CTA ("See what happens →" / "Answer downstairs →") that hands off to the See beat.
- Acceptance: after submitting Episode 1, the visible hierarchy is **reply > one-line status > (collapsed) notes > hook CTA**; the clarity score is not the first thing the eye lands on.

## WP-F2 (Frontend) — Episode/story chrome + the on-ramp landing
Owner: frontend agent. Files: [missions.tsx](../web-frontend/pages/missions.tsx), [atelier.tsx](../web-frontend/pages/atelier.tsx).
- "Start first episode" should land on a **scene-set intro**, not a bare form: episode header ("Episode 1 · Le radiateur"), 1–2 lines of story (the cold flat, the dead radiator, the silence), then the diegetic task ("Text your landlord, M. Marchand").
- Add a **"Previously on…"** strip for episodes 2+ (from `hook_from_previous`).
- Frame the compose box as *writing to a person* ("To: M. Marchand"), not a worksheet.
- Acceptance: the first thing on screen is the scene + who you're writing to, in the feuilleton editorial style — not a score.

## WP-D1 (Design) — Redesign the act screen as a story scene
Owner: design agent (extends [serial-world-design-package.md](serial-world-design-package.md) Part A2).
- Define the **layout & hierarchy** for the act beat: episode dateline → scene intro → addressee → compose → **reply card** → collapsed notes → hook.
- Define the **reply card** states (mood-aware): Marchand *confused/blocked* when objectives unmet, *cool* on register failure (tu vs vous), *softened/resolved* when clear — tied to WP-2's branch states.
- Lighten the visuals: fewer heavy black cards, editorial paper base, character accent as spot ink. Specify the collapsed "writing notes" component.
- Acceptance: a redesign that makes Mission and Feuilleton feel like one story; one primary action per screen.

## WP-D2 (Design) — One-thing-at-a-time / declutter system
Owner: design agent.
- Replace the simultaneous verdict + vocab-missing + red-ink stack with **progressive disclosure** rules (what shows immediately, what's tucked into "notes", what only appears on request).
- Reusable across both features so corrections never crowd the story.

## WP-B1 (Backend, small) — Surface the reply + hook per turn, not only at complete
Owner: missions-backend agent. File: [missions.py](../app/services/missions.py), [endpoints/missions.py](../app/api/v1/endpoints/missions.py).
- Today the `outcome` (reply_text + hook) is written into `recap_payload` at `complete()`. Expose the **in-fiction reply on each turn/submit response** (the assistant turn already exists — ensure it's framed as Marchand and returned prominently), and make the **hook available before complete** so the act screen can show the forward CTA as soon as objectives are met.
- Keep the score under the hood (it still picks the reply branch).
- Acceptance: the submit/turn API response carries the character reply and (when ready) the hook, so WP-F1 doesn't have to wait for completion.

## WP-C1 (Content) — Better Episode 1 brief framing + register steer
Owner: content. File: world bible / Episode 1 contract.
- The brief should diegetically steer toward **vous/formality** and the target words so a learner isn't left writing "tu as un problème ou qoui ?" — soft in-fiction guidance ("He's your landlord — you've never met. Keep it polite."), not a grammar lecture.
- Acceptance: the framing nudges register and target vocabulary without breaking fiction.

---

## Sequence
1. **WP-B1** (tiny) unblocks the reply/hook in the API →
2. **WP-D1/WP-D2** define the redesign →
3. **WP-F1** (hero reply + declutter) then **WP-F2** (episode chrome) implement it.

WP-F1 is the highest-impact single change: it converts the screen from "you scored 3/4" to "Marchand wrote back."
