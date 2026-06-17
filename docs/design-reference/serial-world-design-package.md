# Serial World — Design Work Package (for Claude Design)

**Audience:** the design agent. **Goal:** one seamless, beautiful, fully-integrated experience where Missions and Feuilleton feel like two camera angles on a single ongoing life in French — plus the **persistent character & world assets** that make the illustrated serial look consistent episode after episode.

**Read first:** [serial-world-spec.md](serial-world-spec.md) (engineering WPs), [serial-episode-01-reference.md](serial-episode-01-reference.md) (the worked episode), [world_bible_paris_v1.json](../app/prompts/serial/world_bible_paris_v1.json) (cast, locations, the `visual_design` block you will replace).

This package has two halves:
- **Part A — Experience design** (the seamless, integrated UI/UX across the act→see loop).
- **Part B — Persistent assets** (character model sheets, location plates, the visual system, and the asset *contract* the generator consumes). This is design backlog **DB-1/DB-2**, elevated and made concrete.

---

## North star
Today the learner sees "Mission" and "Feuilleton" — two mechanic names, two mini-games. After this work they should see **one living story they advance by speaking French**. The verbs change from *answer / read* to *act / witness*. The reward changes from *a correction* to *"I have to know what happens next."* Design's job is to make that single thread feel inevitable, warm, and worth returning to daily.

## Design principles (hold these throughout)
1. **One world, two camera angles.** Missions (you act: chat, decide, negotiate) and Feuilleton (you witness: illustrated, serial, cliffhangered) must share type, color, motion, and chrome so the seam disappears. A learner should never feel they "left one feature and opened another."
2. **Extend the existing editorial language — don't reinvent.** The app is already a newspaper/editorial system (see tokens below). A *feuilleton* IS a newspaper serial. Lean all the way into it: mastheads, datelines, "Previously on…", column rules, ink-on-paper. This is a gift — use it.
3. **The cliffhanger is the hero.** The last beat of every episode is an unresolved question, not a recap. The recap still exists but is demoted and quiet. Design the cliffhanger card as the most emotionally charged surface in the app.
4. **Warmth over gamification.** The retention engine is *caring about these people*, not points. Restraint with badges/scores; generosity with character, mood, and consequence.
5. **Phone-first.** Everything is designed for the phone shell first ([phone-first-product-shell.md](phone-first-product-shell.md)), then scaled up.

---

## The visual system you're inheriting (use these tokens)
From [ContinuationCard.tsx](../web-frontend/components/mobile/ContinuationCard.tsx) and the editorial components:

| Token | Value | Role |
|------|-------|------|
| `--paper` | `#f1ece1` | base "newsprint" background |
| `--paper-2` / sheet | `#f8f3e8` | raised card stock |
| `--ink` | `#14110d` | primary ink |
| `--ink-2` / `--ink-3` | `#4a4538` / `#8a826f` | secondary/tertiary ink |
| `--red` | `#d8321a` | editorial red — corrections, urgency, the "red ink" repair motif |
| `--blue` | `#1d3a8a` | grammar / structure |
| `--yellow` | `#f3c318` | highlight / vocabulary |

Existing chrome to reuse, not rebuild: `EditorialMasthead` (already has `missions` + `feuilleton` sections), `MobileBottomSheet`/`MobileSheet`, `MobileRow`, `MobileChip`, `StickyCTA`, `ContinuationCard`, `RedInkRepairSlip`, `VocabularyCreditBadge`, `FeedbackSlip`, `ContextAnchor` (all under [web-frontend/components/mobile/](../web-frontend/components/mobile)). Follow the handoff conventions in [mobile-implementation-agent-handoff.md](mobile-implementation-agent-handoff.md) and the parity bar in [mobile-design-parity-checklist.md](mobile-design-parity-checklist.md).

### One addition to the system: the character accent palette
Each recurring character owns one accent colour (already seeded in `world_bible.visual_design`). Make these first-class design tokens so a character's color follows them everywhere — chat bubble, name chip, panel border, "their reply" card:

| Character | Accent | Token to define |
|-----------|--------|------------------|
| Marin Lévêque | sea green | `--char-marin` |
| Lila Bonnet | marigold | `--char-lila` |
| Augustin "Gus" | burgundy | `--char-gus` |
| Romy Tremblay | cold blue | `--char-romy` |
| Margaux | warm amber | `--char-margaux` |
| M. Marchand (landlord) | ink-grey | `--char-marchand` |

---

# PART A — Experience design (deliverable: screen designs + flows)

Design these as one continuous flow. For each, deliver: mobile layout, states (loading/empty/error), motion notes, and how it reuses or extends existing components.

### A1. The serial on-ramp (Atelier)
Replace the two mechanic cards ("Mission" / "Feuilleton") at the Atelier recap ([atelier.tsx](../web-frontend/pages/atelier.tsx), cards ~`:885`) with **one prominent living-thread card**. Copy is narrative, not mechanical: "The landlord replied." / "Continue the story — Episode 4." / "Previously: you survived Romy's camera." It shows: the thread's current beat (act or see), a single character avatar/mood, and one clear CTA. This is the most-clicked surface in the app — make it feel like the next episode of a show you love.
- States: brand-new (Episode 1 invitation), act-pending ("Toi needs to reply"), see-pending ("New episode ready"), all-caught-up (quiet "rest" state).

### A2. The Act screen (Mission) — reply, not grade
The Mission chat/compose screen ([missions.tsx](../web-frontend/pages/missions.tsx)). The redesign: **the NPC's in-fiction reply is the visible payoff**; the 0–4 score recedes to a small, optional detail.
- Design the **character reply card**: the NPC's avatar (mood-aware — confused / warm / cool), their reply in their accent colour, in their voice. When objectives are met, the reply *resolves the situation* in-fiction; when not, the NPC is blocked/confused and asks for the missing detail.
- The objectives become a quiet "what the world still needs" checklist, not a graded rubric.
- The "repair" moments still use `RedInkRepairSlip`, but framed as the character not understanding, not a teacher marking.
- End state: an **outcome + hook** card that flows directly into the See beat ("See what happens →").

### A3. The See screen (Feuilleton) — the serial reader
The episode reader ([graphic-novel.tsx](../web-frontend/pages/graphic-novel.tsx)). Design the **illustrated serial reading experience**:
- **Masthead / dateline** per episode (newspaper feel): episode number, location, "this week in town" (the news line, via Romy).
- **Panel reader**: 6 panels, comic-page or vertical-scroll (design both; engineering supports `render_mode` page/panels). Captions as editorial text; speech in character-coloured bubbles.
- **Embedded tasks in-panel**: cloze / choice / short-sentence rendered as part of the art, not as a quiz overlay. The **choice fork** must *feel* like authoring the story — picking the line the protagonist says — with a satisfying micro-transition to the consequence panel.
- **"Previously on…" header** for episodes 2+ (continuity from `hook_from_previous`).

### A4. The cliffhanger card (the hero surface)
The final beat. Not a recap. Design a high-impact **cliffhanger card**: the unresolved question, a single charged image/mood, and one CTA that seeds the next act ("Answer Romy →"). The vocabulary recap renders *below* it, quiet and secondary. This card is what the learner remembers; give it the most craft.

### A5. The thread map / "the story so far"
A light **serial index**: episodes as a vertical timeline (dateline, location plate thumbnail, the hook that opened it, the choice you made). Lets a learner feel the accumulation — installment 8 should *look* like a history with these people. Reuse editorial list patterns; keep it browsable, not a dashboard.

### A6. Motion & transitions (where "seamless" is won or lost)
- **Act → See handoff:** the outcome/hook card morphs into the first panel — no hard page change. The learner's words "become" the comic.
- **Choice fork:** selecting a line gently redraws the next panel (cross-fade/ink-bleed), reinforcing *you authored this*.
- **Cliffhanger reveal:** the final panel lands, then the unresolved question types/draws in.
- **Page turns:** newspaper-fold or panel-advance, never a generic slide.
Deliver motion as short specs (trigger, duration, easing, what moves) so engineering can implement with the existing CSS-in-JS approach.

### A7. Surfaces to keep consistent across both features
Type scale, masthead, bottom sheets, chips, sticky CTA, empty/loading/error states, dark-on-paper contrast, and the character accent system — identical in Mission and Feuilleton so the seam vanishes.

---

# PART B — Persistent assets (deliverable: asset library + the contract the generator reads)

This is the part that makes a persistent-cast AI comic actually work. Without locked references, the AI redraws the characters slightly differently every panel and the illusion collapses. **This is backlog DB-1 (characters) and DB-2 (locations), now a hard deliverable.**

### B1. Character model sheets (the core asset — one per cast member)
For each of the 6 characters (`marin_leveque`, `lila_bonnet`, `augustin_de_roncourt`, `romy_tremblay`, `margaux`, `landlord_marchand`), produce a **reference/model sheet**:
- **Canonical face & turnaround** (front, 3/4, profile) so the generator keeps the face stable.
- **Expression sheet** (≈6 moods that the story needs: warm, confused, cool/guarded, delighted, deadpan, vulnerable) — these map to the mood-aware reply card in A2.
- **Wardrobe & silhouette** (the fixed signature look from the world bible: Marin's knit + tote, Gus's three-piece suit, Romy's leather jacket / on-air blazer, etc.).
- **Accent colour** locked (the palette above).
- **Seed image(s) / style-reference image(s)** in whatever form the image pipeline consumes (image refs, IP-adapter/style-ref images, or a tuned seed) — coordinate exact format with the WP-4 engineer.
- **Canonical text descriptor** (the precise phrase that goes into every image prompt) — this replaces the placeholder text in `world_bible.visual_design.characters`.

### B2. Location plates (DB-2)
For each entry in `world_bible.setting.recurring_locations` (Le Mistral, the apartment, Marin & Lila's flat, the newsroom, the NGO office, the Canal market, Buttes-Chaumont, métro, Gus's loft, the brocante, the admin office): a **location plate** — establishing look, palette, time-of-day variants, and a canonical text descriptor. This is what stops rotated settings from looking off-brand and keeps Le Mistral *the same café* every time it recurs.

### B3. Prop & motif library
The small recurring objects that carry continuity and gags: the glowing phone (landlord thread), the booth at Le Mistral, the hot drink, Marin's grandmother's ring, Gus's Carnet, Romy's microphone. Canonical descriptors + refs.

### B4. The comic art direction one-pager
Lock the house style so every episode coheres: line treatment (warm ligne-claire-inflected European comic), palette discipline (muted Parisian base + the one character accent), panel framing, caption typography, bubble style, how news/editorial elements appear. One page, authoritative.

### B5. UI/iconography assets
The serial's own marks: a serial/thread glyph, the "Previously on…" stamp, the cliffharger flourish, mood indicators, the dateline lockup. Match `web-frontend/public/icons/` conventions and the existing `atelier-mark.svg`.

### B6. The asset contract (how design output reaches the generator)
This is the seam between design and code. Today `world_bible.visual_design.characters.<id>` holds **text placeholders**; WP-4 already pipes those into image prompts. You will replace them with the real asset manifest. Proposed shape (confirm exact fields with the WP-4 engineer):

```json
"visual_design": {
  "status": "locked-v1",
  "art_direction_doc": "assets/serial/art-direction.md",
  "characters": {
    "romy_tremblay": {
      "canonical_descriptor": "Québécoise woman, early 30s, shoulder-length brown hair, athletic, leather jacket; cold-blue accent",
      "accent_colour": "#1d3a8a",
      "reference_images": ["assets/serial/characters/romy/turnaround.png", "assets/serial/characters/romy/expressions.png"],
      "style_ref": "assets/serial/characters/romy/style_ref.png",
      "expressions": { "warm": "...", "guarded": "...", "deadpan": "..." }
    }
  },
  "locations": {
    "le_mistral": {
      "canonical_descriptor": "narrow corner café-bar, worn zinc counter, warm amber light, rain on glass",
      "reference_images": ["assets/serial/locations/le_mistral.png"]
    }
  }
}
```
Deliver assets under a stable path (e.g. `web-frontend/public/assets/serial/...` or wherever the image pipeline can reach them) and update the `visual_design` block to point at them. Keep keys aligned to the existing world-bible character/location **ids** — that's the join key the generator uses.

---

## Dependencies & coordination
- **Engineering ↔ design seam:** the `visual_design` JSON contract (B6) and the `render_mode` (page/panels) and per-panel `overlay_payload` shapes are owned by the Feuilleton engineer (WP-4/WP-5 in [serial-world-spec.md](serial-world-spec.md)). Agree the exact reference-image format the image model accepts **before** producing the full set — produce one character end-to-end as a pipeline test first.
- **DB-1 gates Feuilleton *visual quality*** (not function): WP-4 ships on text seeds, then swaps to your locked refs with no code change once B1/B6 land.
- **Copy:** the narrative on-ramp/cliffhanger copy (A1/A4) should match the world bible's voice and `season_one_situation` threads.

## Definition of done
1. **Part A:** designs for A1–A6 delivered in the established handoff format ([design-handoffs/](design-handoffs)), phone-first, with states + motion specs, reusing the existing component library; Mission and Feuilleton are visually indistinguishable as "one story."
2. **Part B:** model sheets for all 6 characters (B1), plates for all 11 locations (B2), prop/motif library (B3), art-direction one-pager (B4), serial UI marks (B5).
3. **The contract (B6) is real:** `world_bible.visual_design` updated from text placeholders to point at delivered assets, keyed by existing character/location ids, validated end-to-end on at least one character through the WP-4 image path.
4. **Consistency proof:** the same character rendered across 3 different episodes/locations reads as unmistakably the same person.
5. Nothing breaks the existing editorial design language or the phone shell parity checklist.
