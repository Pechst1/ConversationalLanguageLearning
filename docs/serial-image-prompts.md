# Feuilleton — Persistent Asset Image Prompts (DB-1 / DB-2 / DB-3)

Ready-to-paste prompts for generating the persistent characters, locations, and props in **one consistent feuilleton style**. Built from the locked `art_direction` and `canonical_descriptor`s in [world_bible_paris_v1.json](../app/prompts/serial/world_bible_paris_v1.json). Each prompt is self-contained (the shared style is baked in) so you can paste it straight into a top image model.

---

## 0. How to use these (read once)

**The single house style.** Every asset shares the same look so the comic coheres episode to episode:
> Warm, ligne-claire European bande-dessinée style (clean confident black ink contours, flat cel-like color, à la Floc'h / Hergé / Jordi Lafebre), muted Parisian palette on a cream newsprint base, restrained paper grain, soft natural light, gentle and wry mood. Limited palette, no harsh shadows.

**Consistency workflow (important):**
1. **Generate Marin first** at high quality — he becomes the **style anchor**. Pick the best result.
2. For every other character/location/prop, attach Marin's image as a **style reference** (Midjourney `--sref`, Flux/SDXL IP-Adapter "style", or "match the art style of this reference" on a natural-language model) so line weight, palette, and texture stay identical.
3. **Lock one seed** per character across their turnaround + expression sheet so the face doesn't drift.
4. Generate each **character once as a model sheet** (turnaround + expressions on one sheet), then reuse that sheet as the character reference when generating panels.

**Recommended settings (model-agnostic):**
- Character model sheets: **landscape 3:2** (room for turnaround + expression row).
- Location plates: **vertical 2:3** (phone-first feuilleton panels).
- Props: **square 1:1**.
- Always include the negative block. **No text, no letters, no logos, no speech bubbles** — panel text is added later as an HTML overlay, so the art must be clean.

**Where outputs go (so they drop into the contract):**
```
web-frontend/public/assets/serial/characters/<id>/model-sheet.png   ← reference_images[0]
web-frontend/public/assets/serial/characters/<id>/model-sheet.png   ← style_ref
web-frontend/public/assets/serial/locations/<id>.png                ← locations.<id>.reference_images[0]
web-frontend/public/assets/serial/locations/<id>-variant.png        ← optional additional location variants
web-frontend/public/assets/serial/props/<id>.png                    ← props.<id>.reference_images[0]
```
`<id>` = the exact world-bible id (e.g. `marin_leveque`, `le_mistral`). DB-5 wires these paths in.

**Shared NEGATIVE block (append to every prompt):**
> Negative: text, words, letters, captions, speech bubbles, logos, watermark, signature, UI, modern 3D render, photorealism, anime, manga, harsh shadows, neon colors, oversaturation, cluttered background, extra fingers, deformed hands, multiple conflicting styles.

---

## 1. CHARACTER MODEL SHEETS (DB-1)

Each character is one sheet: a 3-pose turnaround (front, 3/4, profile) **plus** a row of the canonical expressions. Same person, neutral cream background, even lighting.

### 1.1 Marin Lévêque — `marin_leveque` (style anchor — generate first)
> Character model sheet in warm ligne-claire European bande-dessinée style: clean confident black ink contours, flat cel-like color, muted Parisian palette on a cream newsprint background, soft even lighting, subtle paper grain. **Subject:** a very tall, broad, slightly rumpled Breton man in his early 30s — dark curls, short beard, gentle warm eyes; oversized knit sweater, a weathered coat, an NGO canvas tote bag over one shoulder. Sea-green spot-colour accent (#2c6a5d) on his clothing. **Layout:** full-body turnaround — front view, three-quarter view, side profile — all the exact same character with identical proportions and outfit; below, a row of three head-and-shoulders expressions: (1) warm soft smile with protective posture, (2) confused with brow pinched but still kind, (3) vulnerable with eyes lowered. Consistent, model-sheet, neutral background.
> _Negative: [shared block]_

### 1.2 Lila Bonnet — `lila_bonnet`
> Character model sheet, same warm ligne-claire European bande-dessinée style, clean black ink contours, flat cel color, muted Parisian palette on cream newsprint, soft even light. **Subject:** a small, fast-moving Marseillaise woman, early 30s, dark hair pinned up and flecked with paint, bright thrifted layered clothing, ink-stained hands, sharp amused eyes. Marigold spot-colour accent (#c2890f). **Layout:** full-body turnaround — front, three-quarter, profile, identical character and outfit each time; below, a row of three expressions: (1) teasing with one eyebrow up, already plotting, (2) delighted with a wide grin and hands mid-gesture, (3) guarded with arms folded over paint-stained sleeves. Model-sheet, neutral cream background. _Match the art style of the reference._
> _Negative: [shared block]_

### 1.3 Augustin « Gus » de Roncourt — `augustin_de_roncourt`
> Character model sheet, same warm ligne-claire European bande-dessinée style, clean ink contours, flat cel color, muted Parisian palette on cream newsprint. **Subject:** a trim, composed Frenchman in his 30s wearing an immaculate three-piece suit with a pocket square, slicked-back hair, a too-polished showman's smile that hides nerves, theatrical posture. Burgundy spot-colour accent (#8a2f2a). **Layout:** full-body turnaround — front, three-quarter, profile, identical suit and character; below, three expressions: (1) deadpan, perfectly still performative calm, (2) delighted showman grin with one hand presenting the room, (3) vulnerable, smile cracked, shoulders less staged. Model-sheet, neutral cream background. _Match the art style of the reference._
> _Negative: [shared block]_

### 1.4 Romy Tremblay — `romy_tremblay`
> Character model sheet, same warm ligne-claire European bande-dessinée style, clean ink contours, flat cel color, muted Parisian palette on cream newsprint. **Subject:** a Québécoise woman in her early 30s, athletic with easy relaxed posture, shoulder-length brown hair; wearing a worn leather jacket, a small audio recorder or microphone clipped near her. Cold-blue spot-colour accent (#1d3a8a). **Layout:** full-body turnaround — front, three-quarter, profile, identical character and outfit; below, three expressions: (1) cool dry half-smile with a reporter's measuring gaze, (2) guarded with chin tipped down and steady eyes, (3) vulnerable with the microphone lowered and a direct, unguarded look. Model-sheet, neutral cream background. _Match the art style of the reference._
> _Negative: [shared block]_

### 1.5 Margaux — `margaux_barman`
> Character model sheet, same warm ligne-claire European bande-dessinée style, clean ink contours, flat cel color, muted Parisian palette on cream newsprint. **Subject:** a sturdy, unhurried older woman bartender, cropped grey hair, rolled-up shirtsleeves, an apron, a towel in one hand, a dry all-knowing calm. Warm amber spot-colour accent (#a85d24). **Layout:** full-body turnaround — front, three-quarter, profile; below, three expressions: (1) deadpan flat look over a drying glass, (2) warm, a barely-visible smile at the corner of the mouth, (3) "oracle," one finger raised before delivering a perfect line. Model-sheet, neutral cream background. _Match the art style of the reference._
> _Negative: [shared block]_

### 1.6 M. Marchand (the landlord) — `landlord_marchand`
> Character model sheet, same warm ligne-claire European bande-dessinée style, clean ink contours, flat cel color, muted Parisian palette on cream newsprint. **Subject:** an older Parisian landlord, compact controlled posture, neat grey overcoat, a precise scarf, wire-frame glasses, a phone of formal messages in hand. Ink-grey accent (#5b5346). **Layout:** full-body turnaround — front, three-quarter, profile; below, three expressions: (1) cool with a tight mouth and bureaucratic patience, (2) confused, glasses lowered, suspicious squint, (3) softened, a small reluctant nod with easing shoulders. Model-sheet, neutral cream background. _Match the art style of the reference._
> _Negative: [shared block]_

### 1.7 "Toi" — the protagonist — `user`
> Character model sheet, same warm ligne-claire European bande-dessinée style, clean ink contours, flat cel color, muted Parisian palette on cream newsprint. **Subject:** the protagonist, deliberately shown **ambiguously and anonymously** so any viewer can project onto them — always from behind, in three-quarter back view, or partially cropped; **never a clear front-facing face.** A slightly-too-heavy newcomer's coat, practical shoes, a phone always close in hand. Neutral ink accent (#14110d). **Layout:** three back/over-the-shoulder/cropped poses showing body language — (1) curious, head turned toward an unseen group, tentative but open, (2) nervous, shoulders lifted, phone held too tightly, (3) brave, standing straighter, one hand reaching for a door. Faceless or obscured throughout. Model-sheet, neutral cream background. _Match the art style of the reference._
> _Negative: [shared block] + clear front-facing face, detailed identifiable facial features._

---

## 2. LOCATION PLATES (DB-2)

Establishing shots, **no characters**, vertical 2:3 (phone-first). Same palette and ink so settings feel like one world.

| id | Prompt (prepend the house-style sentence + "_match the reference style_", append the negative block) |
|----|------|
| `le_mistral` | Establishing interior of **Le Mistral**, a narrow Parisian corner café-bar: a worn zinc counter, a cosy back booth, warm amber light, rain streaking the window, late-night feel, smells-of-coffee mood. Empty of people. |
| `user_apartment` | A small cold sixth-floor Paris walk-up studio: a temperamental old radiator, a single window onto zinc rooftops, sparse newcomer's boxes, blue-grey evening light. Empty. |
| `marin_lila_flat` | A cramped, art-covered two-room Paris flat near République: canvases and half-finished paintings, mismatched warm furniture, a pot of casserole on the stove, lived-in warmth. Empty of people. |
| `newsroom` | A glass-walled open-plan TV/online newsroom: screens and monitors everywhere, edit desks, cool blue screen-glow against warm overheads. Empty. |
| `ngo_office` | A cluttered environmental-NGO office: protest posters on the walls, stacks of paper, dying potted plants being nursed back, warm afternoon light. Empty. |
| `marche_canal` | An open-air market along the Canal Saint-Martin: fishmonger and cheese stalls, striped awnings, crates of produce, Sunday-morning light on the water. Empty of shoppers. |
| `buttes_chaumont` | Parc des Buttes-Chaumont: a hilly green park with a dramatic cliff-top folly and a footbridge, soft golden-hour light, the city beyond. No people. |
| `metro_platform` | A late-night Paris métro platform: tiled walls, a curving track, a single waiting bench, the cool glow of departure signs, last-train emptiness. No people. |
| `gus_loft` | An aggressively styled bachelor loft pretending to be aristocratic: faux-heraldic décor, a velvet armchair, theatrical lighting, slightly too much taste. Empty. |
| `brocante` | A weekend flea-market / brocante: trestle tables of antiques and junk, old frames, lamps and curios, soft overcast daylight. No people. |
| `office_admin` | A bureaucratic Paris admin office (préfecture / bank / town hall): a numbered ticket counter, plastic waiting chairs, fluorescent flatness, cool institutional mood. Empty. |

---

## 3. PROP / MOTIF PLATES (DB-3)

Single object, centered, square 1:1, cream background, same ink/palette. These carry continuity and gags across episodes.

| id | Prompt (house style + "_single object, centered, neutral cream background_" + negative block) |
|----|------|
| `phone_landlord_thread` | A small glowing smartphone seen from a slight angle, screen warm but with **no readable text**, suggesting an anxious message thread. |
| `le_mistral_booth` | The corner booth of a Parisian café — worn red-leather banquette, a small marble-top table, two coffee cups — the group's unofficial territory. |
| `hot_drink` | A plain white café cup of something hot with a faint amber warmth and a wisp of steam. |
| `grandmothers_ring` | A modest vintage engagement ring in a small worn velvet box, tender and a little secret. |
| `gus_carnet` | A small elegant leather pocket notebook (« le Carnet »), closed, with a ribbon marker — a showman's secret playbook. |
| `romy_microphone` | A handheld reporter's microphone or a compact audio recorder, practical and well-used. |

---

## 4. After generation — registering assets (DB-5, engineering)

Once files exist at the paths in §0, populate the contract so WP-4 uses them automatically:
```jsonc
// world_bible_paris_v1.json → visual_design.characters.marin_leveque
"reference_images": [
  "assets/serial/characters/marin_leveque/model-sheet.png"
],
"style_ref": "assets/serial/characters/marin_leveque/model-sheet.png"
```
…and the equivalent for `locations.<id>.reference_images` and `props.<id>.reference_images`. Character DB-1 and the delivered DB-2 plates are now registered with `visual_design.status = "assets-locked-v2"`; when the brocante plate and future DB-3 props arrive, add those references under the same contract and run the consistency proof through the WP-4 image path.
