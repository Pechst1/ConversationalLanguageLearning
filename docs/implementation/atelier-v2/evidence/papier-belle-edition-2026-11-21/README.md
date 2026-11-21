# «Papier · la belle édition» — looked at in a browser (2026-11-21)

Branch `claude/papier-belle-edition` (from `claude/papier-integration`). Chromium through Playwright, 375 × 812,
deviceScaleFactor 2, every screen in the light and the dark theme (`-dark`). The round «N» badge of Next is hidden.

## The design, in ten lines

1. The newsroom's own paper objects are the interface: tape, proofs, slips, stamps, cuttings, a front page.
2. Only «av2»: its tokens, Garamond italic (the house serif is italic only) and the sans; no new colour or font.
3. Small caps are the sans in capitals, tracked 0.12–0.14 em — datelines, kickers, slugs, bylines, credits.
4. Rules carry the hierarchy: a 3 px rule under a masthead, hairlines between items, a column rule between columns.
5. Paper has 1–3 px corners, never pills; choices are set like type on the stone (square, hairline).
6. Red is the editor's ink (the grease pencil, the strike, the deleatur, the slip, the learner's byline), never decoration.
7. A mark appears only when the loop says so: no stamp before the answer, no loop before a pick, no solution before a retry.
8. The learner's own words are the page's key element: set larger, as the lead with a drop cap, signed in red.
9. Few movements, each ≤ 300 ms: a strip lifts and slides, the pencil draws, a stamp thuds, the page settles; none under reduced motion.
10. What the paper prints stays French; what the interface says (labels, reasons) follows the chrome-language rule.

## The shared pieces (`web-frontend/components/revue/papier/`, `styles/revue-papier.css`)

| piece | what | used in |
|---|---|---|
| `RvComptoirHead` (restyled, same props + `opening`) | ×, masthead «Le Papier», folio «2 / 5» (old-style figures), the column rule that inks page by page (still the progress bar) | all four players |
| `PpPlayerSection` / `PpSection` / `PpOpening` / `PpDateline` | the section head («LE FIL — Remettre en ordre»); on the first screen the masthead at display size, its rule and «PARIS · VENDREDI 20 NOVEMBRE · Nº 47» (day from the session, number from the week) | all four players, the chooser |
| `PpBareHead` | the chooser's head: the × alone, the masthead printed under it | `/revue` chooser |
| `PpFolio` | the page number | the head |
| `useFlip` | strips slide to their new places (FLIP, 200 ms) | «Le fil» order |
| wire tape (CSS on `.fl-strip`) + slug «DÉPÊCHE · B» | torn top/bottom, feed holes (masks), a press shadow when lifted, joined into one tape once in order | «Le fil» order, words |
| `PpPencilLoop`, `PpStrike`, `PpDeleatur` | the grease-pencil loop (draws in 300 ms), the strike across a refused proof, the delete mark on a word; «stet» under a word the article does say | «Le titre» three, trap |
| galley proof (CSS on `.rb-head`, `.rb-trap`) | printer's corner marks, headline at 23–26 px | «Le titre» |
| `PpInkDefs`, `PpStamp` | «VRAI» green / «INTOX» red, seeded tilt −4…4°, 120 ms thud, uneven ink by an alpha-only SVG filter | intox round, intox fix, intox page |
| `PpCutting` (and `.rb-quote`, `.ct-note__ex`, `.rv-claim`) | the pasted cutting, outlet as its footer | intox, titre, Romy's notes |
| slip + margin note (CSS on `.ct-mark`, `.ct-why-open`) | a hand-drawn wavy rule (SVG mask, token ink), the note hung from its word by a measured hairline | every «Romy corrige» |
| the slate (CSS on `.ct-q`), bylines (`.ct-bub__name`), stance tags | the question of the day chalked; names and sides in small caps | «Au comptoir», every bubble |
| `PpFrontPage`, `PpFrontCols`, `PpMine`, `PpLead`, `PpByline`, `PpLexique`, `PpFigure` | «La page»: masthead, dateline, kicker, display headline, deck, picture with caption and credit, drop cap, the signed piece (byline stamped last), Lexique sidebar beside a column rule | the four clippings (`FilClipping`, `TitreClipping`, `IntoxClipping`, `ComptoirClipping`, props kept, extras optional) |
| `papier-model.ts` | dateline, edition number, folio, tilt, loop and wave paths, drop cap, bylines, hairline x, FLIP deltas, page picture | — |
| `papier-copy.ts` | `PAPIER_FR` (what the paper prints) and `papierCopy` fr/de/en (labels, aria) | — |

## How it was run

- `mock-*`: the dev mock (`/revue?mock=1&<assignment>=1&pourquoi=1&photos=1&band=A2&lang=de`; intox `band=B1&lang=en`),
  driven by Playwright scripts. `-before` was taken on `claude/papier-integration` (712f4f72), `-after` on this branch,
  the same script, the same states.
- `walk-*`: the repo's walk stack (`e2e/lib/stack.mjs` + `e2e/lib/carte_server.py`, fake providers, throwaway
  database, dropped at the end), the switches for the walk's API only: `REVUE_ASSIGNMENTS_ENABLED`,
  `REVUE_POURQUOI_ENABLED`, `REVUE_PHOTOS_ENABLED` (with `--comptoir`). Walk-only seed: «Le bac» and «La Fête de la
  musique» as week-47 `revue_dossiers` rows; new learners (German A1, German A2, English B1) dealt by the real dealer
  until each family showed. No photo rows were seeded this time.
- `mock-a2de-titre-page-reduced-motion`: the same page with `prefers-reduced-motion: reduce` (at rest, the same states).

## Before / after pairs (mock)

`chooser`, `fil-lire`, `fil-ordre-lifted`, `fil-ordre-right` (joined tape), `fil-mots-done`, `fil-page`, `titre-three`
(loop on the honest proof, strike on the refused), `titre-trap` (deleatur), `titre-page`, `intox-round` (stamp + cutting),
`intox-fix`, `intox-page`, `comptoir-lire-slate`, `comptoir-takes`, `pourquoi-why` (wavy slip, margin note),
`comptoir-page`; each `-before`/`-after`, light and `-dark`.

## Tried and rejected

- A blackletter or roman masthead: the house serif is Garamond italic only (the roman falls back to Times); the
  masthead is the italic at 800.
- Small caps from the font: not in the vendored subset; synthetic small caps looked bruised — the tracked sans instead.
- Torn edges with `clip-path`: it clipped the lift shadow; masks on a pseudo-element, the shadow a second torn layer.
- `vector-effect: non-scaling-stroke` on the pencil loop: Chrome then dashes it in screen space and the loop drew only
  two thirds of itself.
- A wavy rule as an inline SVG inside each mark: it changed the marks' markup the players' tests read; an SVG mask on
  `::after` paints the same wave in the token's red.
- Tags «Refusé» / «Retenu» beside the proofs: they repeated the role label («Il en dit trop», «Honnête»), now coloured.
- A tilt on the counter's notes: legibility first; only stamps and cuttings are off true.
- The scene line in the page kicker («LE FIL DE ROMY · UNE SALLE D'EXAMEN…»): too long in capitals; it is the deck.

## Round 2 (art direction, 21 Nov) — what changed

All `-after` files were retaken after these changes (light and dark); `-before` files are unchanged.

1. **Head air.** `HEAD_AIR` = 12 px in the players' scroll (`comptoir/scroll.ts`), `scroll-padding-top` on the page,
   «Le fil» now opens each screen at its top as the others do, and La page no longer anchors itself (it opens the
   screen; Romy's thanks follow it). Guarded in the browser check: every screen as it opens is at scroll 0 with its
   first line ≥ head + 12 px, and every anchored part after an act ≥ head + 12 px — no violation in the last runs.
2. **Translations quiet.** One «Tout traduire / Alles übersetzen / Translate all» text control in the section head for
   sets (the wire's strips, the three proofs, the statements); per-item and Romy's «Anhören / Übersetzen» are text
   links. Every one keeps a 44 px tap area (::after).
3. **No long tracked capitals.** Credits, cutting footers and La page's sources are the small sans in sentence case,
   the sources a short list.
4. **One masthead on La page.** The head shows × and the folio only.
5. **The picture on La page**, in a press frame under the standfirst, with caption and credit: the story's own plate,
   else its first picture; with none, the scene line becomes the deck (no hole).
6. **«Ton titre / Dein Titel / Your headline»** over the learner's headline (`papierCopy.page_kicker_mine`). The dev
   mock now marks the headline's agreement slips («gratuit», «musicien»), so it prints corrected text.
7. **La page on a phone:** one column, no hyphenation, `text-wrap: pretty`; the Lexique a ruled full-width box with
   two columns of words; the side-by-side layout from 600 px. No drop cap when the second character is not a letter.
8. **The vignette** after a ruled break, with bottom scroll padding.
9. **The tape:** slug and text, a folio numeral in the margin (still the 44 px swap control), one move row (grip, ↑, ↓,
   each 44 px), ≈ 84 px for a one-line dispatch; feed holes painted (paper dot, ring) so they show in both themes.
10. **Selection** is a lift and an ink hairline; the pink is only for a strip the check named.
11. **Loop** hugs the text block (`width: fit-content`, rounded corners that keep the letters inside); **strike** is one
    clean corner-to-corner slash across the refused proof.
12. **Stamp** about twice the size, over the slip's top-right corner, tilt 2.5–4°; «INTOX» uses the deep red on light
    and the bright red on dark, as strong as «VRAI».
13. **Chooser:** the other stories are teasers of the same edition (topic kicker, headline, standfirst, plate).
14. **Home's Une card:** `mock-une-*` (dev mock `?mock=1&une=1`, the card as La Une prints it, its real word budget):
    «Édition du jour · Nº 40» now outranks the topic line, «Nº 40» alone when a long question leaves no room.

`walk-*` were retaken on the walk stack after round 2 (A1 de: counter, wire; A2 de: counter, intox; B1 en: titre,
wire). Their La page sources were captured just before the sentence-case fix of the sources list (the mock pages
show it).

## Not done / not seen

- Home itself on the Revue day was not reached on the walk stack (a first-day learner never gets the Revue day); the
  card is shown through the dev mock instead (`mock-une-*`).
- The walk's FAKE proofreader passed «Fête est gratuit pour les musicien amateurs» as clean, so `walk-b1en-t-5-page`
  prints it under «relu par Romy»: the page says what the server's proof state says; the real proofreader is the fix.
- No dossier carries a dispatch time: the slug is the strip's letter.
