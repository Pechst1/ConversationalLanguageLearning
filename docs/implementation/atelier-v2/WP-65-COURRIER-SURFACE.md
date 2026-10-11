# WP-65 — Le Courrier, surface

Frontend package. Spec: `WORK-PACKAGES-2026-09-21.md` §3 WP-65. Backend it renders:
`WP-64-COURRIER-IN-STORY.md` (commit `7c4a291`).

The finding this closes: WP-64 gave a letter a person, a thread, a chain, a soft
deadline, a lapse and a debrief with nothing invented in it — and none of it had a
surface. `/missions/today` was reached only from the Courrier page, so the chain
instalment and the story-born letter that call materialises were opened by nobody;
`missions.tsx:1108` still asked for `mission.recap.readiness`, a key the server had
stopped sending; and a `lapsed` letter arrived at a screen that would happily show it
a composer.

## What landed

### 1. `components/courrier/Correspondance.tsx` (new) — the surfaces

Presentational only, and deliberately free of `services/api`: every component takes
the shape the payload already has, so the node suite renders them without pulling
axios into a test process and no card here can print a field the server did not send.

- **`CrCorrespondent`** — who is writing (`correspondent.name` · `role`), how they
  feel (`mood_line`), which letter of the affair this is (`chain` → «2ᵉ lettre sur
  3»), by when (`expires_at` → «Répondez avant jeudi, si vous pouvez.»), and the
  letters already exchanged with the same person (`thread_history`, each with its
  date and its outcome word). Renders **nothing** when the letter has nobody behind
  it — a pre-WP-64 row, a serial act.
- **`CrLapsedNotice`** — «Restée sans réponse», who noticed, and that they will
  mention it once in their next letter (which is exactly what `lapse_overdue_letters`
  stores). No «échec», no score, no retry: the delay is past and a retry would be
  pretending it is not.
- **`CrDebrief`** — the honest debrief. Outcome as one French word, the measured
  rows, and what the letter left in the story.
- **`CrLetterRow`** — «Une lettre vous attend», as an `.av2-row`, for the screens
  that are not the Courrier.
- Pure helpers, each with its own tests: `crOutcomeLabel`, `crOutcomeSentence`,
  `crChainLabel`, `crExpiryLine`, `crMeasuredRows`, `crShortDate`, `crLetterHint`.

The French for an outcome: `kept` → «Parole tenue», `partial` → «En partie»,
`missed` → «Manqué cette fois», `ignored` → «Restée sans réponse». One of the four
celebrates; the other three describe, because a letter half answered is a thing that
happened, not a grade.

`CourrierCorrespondanceStyles` is mounted **by the components themselves**. styled-jsx
dedupes one global block by content, so a screen showing three of them ships one copy
of the CSS — and the Feuilleton and the gallery did not each have to learn to import a
stylesheet, which kept the foreign-file insertions down to one line each (see
*Ownership* below). Every rule is `.av2 .cr-…` (0,2,0) and `--av2-*` tokens only.

### 2. The honest debrief replaces the readiness tile (`pages/missions.tsx`)

```
-  {mission.recap?.readiness && (
-    <div className="cr-readiness"><span>Prêt pour la vraie vie</span>
-      <strong>{Number(mission.recap.readiness.overall || 0)}%</strong></div>)}
+  {measured ? <CrDebrief … /> : <div className="cr-recap-grid">…</div>}
```

`recap.measured` (`mission-debrief-v2`) drives it: objectives met over total, repairs
filed, phrases put aside, words written. A row whose number is zero prints only when
it is the objective count — «0 sur 2» is a fact the learner is owed, an absent repair
is an absence. A letter answered **before** WP-64 shipped has no `measured` block and
keeps the old three-count grid rather than losing its debrief.

Under the rows: `recap.story_event.summary_fr` as «Ce que Samira retient» — the event
the letter actually wrote into the living story, which is measured and current.

**The one honest deviation.** The spec asks the debrief to show «what the character
now thinks». `mood_line` is stamped into `prompt_payload.correspondence` when the
letter is *created*; the writeback that moves the mood runs inside `complete()`,
afterwards. So the value in a completed letter's payload is the mood the letter was
**written** with, one step stale. It is printed under «À la réception de votre lettre
— …» rather than as the character's current opinion, because a "now" label over a
before value is exactly the invented number WP-64 deleted. The next letter from that
person carries the moved mood, so the consequence is visible — one letter later.

*Seam for whoever owns `missions.py` next:* one line in `complete()`, after
`_write_letter_into_story`, would make it current —
`mission.recap_payload["correspondent_mood_after"] = courrier.mood_line(thread, mission.correspondent_id)`.
`CrDebrief` would then take that field and change its label to «Ce que {name} pense de
vous maintenant». Nothing else has to move.

### 3. `lapsed` is a real state on the Courrier page

`const lapsed = mission?.status === 'lapsed'` gates the situation card, the word
ribbon and the whole composer off the screen, adds `CrLapsedNotice`, and prints
«Sans réponse» as desk marginalia. The letter itself stays readable. Because the
composer is gone, one quiet press is put back — «Nouveau courrier» — so the screen
is not a dead end; it opens the *next* letter, never this one again.

### 4. La Une's entry (`components/courrier/courrier-waiting.tsx`, new)

`useCourrierHomeEntry()` reads `/missions/today` — the same call the Courrier page
makes, on purpose: WP-64 materialises the day's second letter *inside* it
(`_sweep_correspondence` → `_ensure_ad_hoc_letter`). Any cheaper read would leave the
chain instalment and the story-born letter unopened until the learner found the
Courrier by hand, which is the loop WP-64's "Still open" note warned about. It is
coalesced through `oncePerLoad('missions/today', …)` under one key, so La Une and the
Feuilleton ask once between them, and a failed read leaves the row off.

In `pages/atelier.tsx` that is **three lines**: an import, `const courrierEntry =
useCourrierHomeEntry();`, and `...(courrierEntry ? [courrierEntry] : [])` at the head
of `homeEntries` — the list `HomeScreen` already renders as `.av2-row` links beside
«Votre dossier». So the unread letter is the day's **second** action: a quiet row,
never a second red press. The label is «Une lettre vous attend», or «Votre réponse est
commencée» for a half-answered one; the hint says which letter it is and how long
there is («2ᵉ lettre sur 3, de Samira · répondez avant jeudi, si vous pouvez.»).
A `completed` or `lapsed` letter waits on nobody and raises no row.

### 5. The Feuilleton says so (`pages/graphic-novel.tsx`)

`<CrStoryLetterRow />` in the reader's banner, one line beside `ReaderCastLink`. It
renders only when the waiting letter's `courrier.origin === 'story_born'` — a
character who picked up a pen about a scene the learner just played. The weekly
Courrier has nothing to do with the episode and advertising it there would turn the
reader into a second Home screen.

### 6. Types (`services/api.ts`, additive)

`MissionCorrespondent`, `MissionChain`, `MissionThreadLetter`, `MissionCourrier`,
`MissionMeasured`; `RealWorldMission` gains `correspondent`, `chain`, `expires_at`,
`thread_history`, `courrier`, and `'lapsed'` in its status union. `outcome` is typed
only inside `MissionCourrier`, mirroring the backend's reason for putting it there.
Every read site takes the flat field **or** the `courrier` block, so a payload from
either side of WP-64's deploy renders.

## Ownership and the shared checkout

Four agents share this checkout. Files owned and edited by this package:
`pages/missions.tsx`, `components/courrier/*`, mission types in `services/api.ts`
(additive only), `pages/atelier-v2-gallery.tsx`, `tests/test_frontend_courrier_surface.py`.

Foreign files were touched at exactly one insertion point each, re-read immediately
before editing, with no foreign hunk reverted:

| File | Owner | Change |
| --- | --- | --- |
| `pages/atelier.tsx` | WP-67 | 1 import + 1 hook call + 1 spread into `homeEntries` |
| `pages/graphic-novel.tsx` | — | 1 import + `<CrStoryLetterRow />` in the reader banner |
| `web-frontend/package.json` | — | 1 test script |

`components/atelier-v2/journey/*` (WP-66) and `components/atelier-v2/home/*` were not
touched: the Home row needed no new component there because `HomeEntry` already exists
and already renders as a row. No backend service was edited.

## Tests

- `web-frontend/components/courrier/courrier-correspondance.test.js` — 20 checks, the
  `courrier-intake.test.js` harness (node + sucrase, no framework). Failure modes, not
  snapshots: no percentage anywhere in the debrief and no successor to
  `readiness.overall`; the mood line labelled with *when* it was measured; the deadline
  a sentence ending «si vous pouvez» and silent once past; the lapse free of «échec»,
  of a score and of a retry; the waiting letter a row and not a press; French ordinals;
  every outcome carrying its word and not colour alone; `.av2 .cr-…` scoping and
  token-only colours. `npm run test:courrier-correspondance`.
- `tests/test_frontend_courrier_surface.py` — 10 checks over the *wiring*: the payload
  fields typed and read (flat and blocked), the correspondent view mounted, the
  readiness tile gone, `lapsed` gating the composer, Home reading `/missions/today`,
  the Feuilleton gated on `story_born`, the CSS scoped, and a gallery specimen for each
  new component. It strips comments before scanning for forbidden strings — these files
  explain themselves, and the sentence a surface must never *print* is one its comments
  must be free to name.

Results: `courrier-correspondance` 20/20 · `courrier-intake` 21/21 · `atelier-ui`
green · `tsc --noEmit` clean · `next lint --dir components/courrier --dir pages`
clean · `next build` green · `pytest tests/test_frontend_courrier_surface.py
tests/test_frontend_serial_surfaces.py tests/test_frontend_pilot_experience.py
tests/test_frontend_thread_destinations.py tests/test_frontend_continuation_card.py
tests/test_frontend_wp16_one_seance.py` → 47 passed · `ruff check` clean.

Not verified in a browser: the preview cannot render an authed route (recorded
2026-09-19). Specimens for all four components are on `/atelier-v2-gallery`, with
fixed dates so the deadline sentence is the same at every review.

## Still open

- The mood line at debrief time is one letter stale — the one-line backend seam above.
- The Home row costs a `/missions/today` on every La Une load, which is where
  `ensure_weekly` lives. Nothing new is generated (the weekly row is unique per ISO
  week, the ad-hoc letter is capped at one open at a time), but the week's first
  generation now happens when Home opens rather than when the Courrier does.
- The correspondent thread on the Courrier page is whatever the payload carried;
  `GET /missions/{id}` refreshes it at read time and `/missions/today` does not, so a
  letter reached from La Une shows the history it was written with. Correct for an
  unread letter; the page re-reads by id whenever the learner arrives with `?mission=`,
  which is the path every row here uses.
- No surface yet lists *all* correspondents — the thread is per letter. A «Vos
  correspondants» page would be the natural next package if chains become common.
