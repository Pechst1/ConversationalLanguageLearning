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

## Not done / not seen

- Home's Une hero only shows on the planner's Revue day; on a first-day walk learner the route trick of 20 Nov did not
  bring it, so no new Home screenshot. The card's change (the edition line «Édition du jour · Nº 47» in the week
  label's place in WP-81's budget, the square teaser, the small-caps kicker) is covered by `revue-render` and
  `p9-rooms` tests only.
- No dossier carries a dispatch time: the slug is the strip's letter.
- B1's «Corrige» stamp and the comptoir B1 walk after the intox were not retaken on the stack (the walker stopped there).
