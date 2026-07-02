# Atelier — Package I: Reward Economy (tokens, seals, the workshop, the almanac)

The detailed, backend-bearing realization of the reward half of
`ATELIER_FORMS_AND_REWARD_PLAN.md` (G), from the "Press Run" design package. This package
adds the economy that the (already-built) visual components feed into.

### Built components — consume, do NOT rebuild
All the reward visuals are implemented on the real stack + tokens:
- `web-frontend/components/ui/AtelierForms.tsx` — margin companions (neutral/correct/wrong).
- `web-frontend/components/ui/Seal.tsx` — exports `Seal`, `CoreForms`, `SealMini`,
  `LogoToken`/`CoreLogo`, `ReactForm` (per-exercise grin/sad scorekeeper), `Confetti`,
  the `SEAL_NAMES` catalogue and `sealForEdition(no)` (deterministic daily variant).
- Styles in `globals.css` (`.af-rail`, `.seal`, `.seal-mini`, `.rf`, `.logo-token`,
  `.confetti`, with reduced-motion gating). The ink-block shadow is reserved for the seal
  and logo token.
- Seal compositions available: `row`, `stack`, `nested`, `quad`, plus `orbit`, `frieze`
  (added for more daily variety). Add more by extending `CORE_SHAPES` + `SEAL_NAMES`.

The backend's job is to decide WHAT is minted and persist/serve the collection; the
frontend renders it with the components above.

## Design principles (from the design, keep them)
- **Mint by behaviour, never bought.** Every collectible is earned by something the
  learner *did*. No lives, no gems, no purchasable tokens, no streak you can lose, no
  countdown. The only currency is skill; the only pressure is curiosity.
- **Variable but dignified.** Rarer collectibles (gilt seals) mark genuinely flawless
  runs; the daily seal varies in composition so each day differs (variable
  reinforcement) — without manipulation.
- **Additive composing, never loss.** Spending in "the workshop" *composes* tokens into
  a larger collectible; you never lose a token, you set it into something bigger
  (endowed progress you can see filling).

## The three mints
| Collectible | Minted when | Art / note |
|---|---|---|
| **Logo token** | a recognize "screen of three" is **3/3 flawless** (all three correct first-try) | the three forms lock into the house mark; haptic tick `vibrate([12,26,12])`. The day's most repeatable mint. |
| **Gilt seal** | a **whole session** is flawless end-to-end (no slip on any screen) | the day's seal struck in gold instead of ink. Rare by design. |
| **Story seal** | a **Feuilleton beat** is completed | face = a **cropped panel** from that episode's illustration (see Story-seal art). Mint on beat-complete, not exercise-complete. |

## The workshop (composing)
- 7 logo tokens → **« Semaine » gilt plate**
- 3 story seals → **bound chapter plate**
- 4 gilt seals → **the annual colophon**
- Composing marks the consumed collectibles `composed=true` and links them to the new
  plate (preserved, shown nested in the almanac) — honoring "never lose, only compose".

---

## Task I1 — Data model (Alembic migration)

New table `atelier_collectibles`:

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | fk users | indexed |
| kind | str | `logo_token` / `gilt_seal` / `story_seal` / `plate_semaine` / `plate_chapter` / `colophon` |
| minted_at | ts | |
| source_kind | str | `screen` / `session` / `serial_beat` / `compose` |
| source_ref | str | session id / screen id / episode index — for idempotency |
| metadata | jsonb | seal variant + name + date; story-seal panel crop ref; plate member ids |
| composed | bool | true once set into a plate (default false) |
| composed_into_id | fk self (nullable) | the plate it was composed into |

Indexes: `(user_id, kind, composed)`, unique `(user_id, source_kind, source_ref, kind)`
to make minting **idempotent** (a screen/session/beat mints at most once).

## Task I2 — Flawless tracking + mint hooks (server-side, automatic)

Minting is **server-side on the achievement event** — never a client call. The client
learns of a mint from the attempt/complete response and plays the reward moment.

- **Per-screen flawless → logo token.** The recognize round is already 3 items
  ("screen of three"). Track first-try correctness per item in the attempt flow
  (`app/services/atelier.py` attempt/`complete` path). When a screen's 3 items are all
  correct on first try (no slip), mint a `logo_token` (idempotent on the screen id).
- **Per-session flawless → gilt seal.** If the entire session had no slip on any screen,
  mint a `gilt_seal` in `complete_session` (idempotent on session id). Assign the day's
  seal variant deterministically (date/edition → one of the design's variants:
  row/stack/nested/quad).
- **Serial beat → story seal.** Hook the serial/Feuilleton beat-completion
  (`app/services/graphic_novel.py` / serial service) to mint a `story_seal` with the
  episode's panel crop ref (idempotent on episode index).
- Return any newly-minted collectibles in the attempt / `complete_session` /
  beat-complete responses so the frontend can show the reward moment.

## Task I3 — Almanac + workshop API
- `GET /api/v1/atelier/almanac` → the user's collectibles grouped by kind, plus
  **endowed progress** (`logo_tokens: 5/7 toward Semaine`, `story_seals: 1/3`,
  `gilt_seals: 2/4`), and the composed plates with their nested members.
- `POST /api/v1/atelier/workshop/compose` `{ target: 'plate_semaine' | 'plate_chapter' |
  'colophon' }` → if enough uncomposed tokens of the required kind exist, compose them
  (mark `composed`, link `composed_into_id`) and mint the plate; else 409 with the
  shortfall. Composing is optional and additive.
- Schemas in `app/schemas/atelier.py`; endpoints in `app/api/v1/endpoints/atelier.py`.

## Task I4 — Story-seal art (serial image pipeline)
The story-seal face is a 1:1 crop of that episode's illustration. So each serial scene
asset must ship a **designated crop region**: a 1:1 mask + focal point. Add a
`seal_crop` field (focal point x/y + square region) to the scene/episode asset and have
the serial image generation (`app/services/serial*`/`graphic_novel`) emit it. On
story-seal mint, persist the crop ref in `metadata` so the almanac renders the cropped
panel. (Falls back to the house mark if no crop is available.)

---

## Frontend integration (consumes the above + the built AtelierForms)

### I5 — "Screen of three" drill with forms as scorekeepers
File: the recognize drill in `web-frontend/pages/atelier.tsx` (do-mode). Bind each of the
3 recognize items to a house form (circle/square/triangle) via the **already-built**
`AtelierForms` (or per-item form), reacting `correct`/`wrong` per item. On a 3/3 flawless
screen, play the **reward moment**: the forms lock into the logo, "LOGO TOKEN EARNED",
haptic `vibrate([12,26,12])` (gate on `isNativePlatform()` + `@capacitor/haptics`).
Coordinate edits with the parallel agent on `atelier.tsx`.

### I6 — The reward moment + the Seal component
Build `CoreForms`/`Seal` (from `press-forms.jsx`: `row`/`stack`/`nested`/`quad` variants
+ ring) as a component for the logo-token lock and the gilt/story seals. The session-end
"edition printed" seal (G-4 / E-4) uses the day's gilt-seal variant when earned.

### I7 — The almanac (seal collection) in Notebook
A new editorial collection surface (read mode) consuming `GET /almanac`: earned tokens,
seals, and composed plates, with the endowed-progress bars ("5/7 toward « Semaine »").
The workshop compose action lives here. Mirror the A5 page style.

### I8 — Session summary / stats
The press-run stats/summary screen (`press-stats.jsx`) at session end: what was minted
today, mastery climbing, tomorrow's serial hook.

---

## Guardrails (enforce in code + copy)
Deliberately absent: no lives, no gems, no purchasable tokens, no losable streak, no
countdown. Variability serves delight; composing is additive. If a future ask pushes
toward loss-aversion mechanics, push back — it breaks the brand and the ethics.

## Creative options & extensions (optional, all behaviour-bound)

More ways to mint and measure — none introduce loss, purchase, or time pressure. Pick
what fits; the `kind` column extends the same `atelier_collectibles` table.

### More medals (mint-by-behaviour)
| Medal | Minted when | Why it's good |
|---|---|---|
| **Le réparateur** (the repair mark) | you correct a slip in the repair step (turn a wrong into right) | rewards the *learning act* — recovering from a mistake — not just flawlessness. Growth-mindset, not perfectionism. |
| **Première édition** (first light) | the first session you finish on a given day, any time | a gentle "you showed up" presence mark — never a streak you can lose. |
| **Le lecteur** (the reader) | finishing a whole serial episode (not just a beat) | a reading milestone distinct from the per-beat story seal. |
| **Le mot juste** (vocabulary milestone) | N target words cross into "known" (FSRS mastery) | ties the vocab SRS into the collection. |
| **Le retour** (the return) | coming back after time away | framed warmly ("the press kept your seat") — celebrates returning, never punishes absence. |
| **La longue séance** (the long edition) | completing an opt-in full ~20-min edition | rewards depth for those who want it, opt-in only. |

### More daily seal variety
Beyond the 6 shipped compositions, add `cross`, `spiral`, `frieze-2`, or seasonal
recolours; the catalogue (`SEAL_NAMES` + `CORE_SHAPES`) is the single extension point, so
variety is cheap. Rarer "gala" seals could use a 2-ring medallion for flawless weeks.

### More statistics (for the session summary / a "press stats" surface)
All framed as encouragement, never pressure:
- first-try accuracy, flawless-screen rate (3/3 screens)
- the concept you **sharpened** today + one **fragile** concept to revisit
- new words encountered; mastery climb (CEFR sub-level progress)
- longest flawless run; repairs made (slips turned right — pairs with *Le réparateur*)
- the week's "press run" (sessions + seals this week)
- "your house form of the day" — which form grinned most (a light, characterful stat)

## Suggested PRs
1. PR I-1/I-2: collectibles model + flawless tracking + mint hooks (logo/gilt/story).
2. PR I-3: almanac + workshop compose API.
3. PR I-4: story-seal crop in the serial image pipeline.
4. PR I-5: screen-of-three forms-as-scorekeepers + logo-token reward moment.
5. PR I-6/I-7/I-8: Seal component, almanac surface, session summary.

## Definition of done
Playing well *mints* collectibles (logo tokens on flawless screens, rare gilt seals on
flawless sessions, story seals from serial beats); the almanac shows a dignified,
fillable collection with an additive workshop; nothing can be bought or lost; and the
reward moments reuse the built `AtelierForms` and the shared Seal component.
