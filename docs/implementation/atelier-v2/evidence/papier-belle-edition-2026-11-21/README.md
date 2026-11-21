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

# Round 3 (21 Nov, on `claude/papier-integration`): La photo, Le micro and the rendez-vous in the belle édition

After merging `claude/papier-belle-edition`, `claude/papier-photo-micro` and `claude/papier-rendez-vous`, everything
that was still in the plain look was set with the same objects and tokens — no second visual language, no new font,
colour or soft geometry. Dev mock (`/revue?mock=1&photo=1|micro=1&pourquoi=1&photos=1[&rdv=1]&band=…&lang=…`,
`/revue/une?mock=1&items=1..6[&carte=1]`), Chromium through Playwright, 375 × 812, deviceScaleFactor 2, light and
`-dark`, German A1, German A2, English B1 (plus French chrome for the une). The belle édition's browser check (no
horizontal scroll; every screen as it opens at scroll 0 with its first line ≥ head + 12 px; every anchor after an act
≥ head + 12 px) ran on every shot: no violation in the final runs.

## What each new screen uses

| screen | made of |
|---|---|
| La photo · «La planche» | `PpSheet` (new): a contact sheet on the slate (`--pp-slate` / `--pp-chalk`, the counter's slate tokens), the frames on one sheet, the frame number in the margin under each, the credits listed under the sheet by number with their licence and source (`PpLinks`, new); the frame itself is the radio; `PpPencilLoop` round the pick, `PpStrike` across a refused frame; the day's headline as a slug line over the sheet |
| «Qu'est-ce qu'on voit ?» | the chosen print in a press frame; the words are caption labels (a punched hole), pinned on the print when tapped (the hole becomes a red pin head, the label turns a degree); a label the miss named is struck |
| «La légende» | `PpFigure` (credit + links) with its three captions set as caption proofs under it (`.pp-captions` over the galley proof markup): the loop on the pick; once found, the wrong fact struck with `PpDeleatur` (never split across lines) inside the loop; a right caption suspected gets the proofreader's green «stet» (`PpStet`, new), a caption of the other picture is struck; the fix set on the desk, the field a ruled line |
| «À toi» | the same sheet to choose the print, then the print large with the learner's caption set under it **as they type** («Ta légende», `PpFigure legend`), the words and facts as caption labels; Romy's proof (the shared slips and margin notes) |
| La photo · La page | `PpFrontPage top`: the picture leads the page, the learner's caption under it at 23 px signed «Légende · par toi, relue par Romy» (`legendeBylineFr`, agreed in French), credit and licence always under the print, then kicker, headline, scene line, sources, Lexique |
| Le micro · «Prépare tes questions» | Romy's notebook: a top-bound page (the spiral's holes), a double margin rule, ruled lines (`--pp-hair`), each note ending on a blank rule (`PpBlank`, new, never alone on a line); a chosen question numbered 1–3 in red in the margin, in the learner's order |
| «L'interview» | the notes kept at hand (compact notebook, a red tick on a filled blank); the transcript under a 2 px rule: the witness's face and «LILA · PROF» as its byline, «Q.» in red small caps before the learner's question (bold italic), «R.» before the witness's line (tappable, ▶, Traduire); a shrug printed as a stage direction «(Lila hausse les épaules.)»; the ask as the next «Q.» line |
| «Tes notes» | the same notebook page, one entry per note: the line with its blank, the witness's «R.» under it, the options as caption labels (a refused one struck, no box, no ✗), a typed note written on the line; once settled the value written on its blank in bold with a red rule |
| «Relis tes questions» | the questions as the notebook holds them («Q.1», «Q.2» in the margin); the app's rule for a slip hung under its question as a margin note (a red hairline, as Romy's notes); then the shared proof |
| Le micro · La page | `PpFrontPage`: kicker «L'interview · Lila», headline, the witness as deck, the scene line, the Q&A (questions bold italic, answers in the text face, each source once as a footnote), the witness's longest answer lifted as a pull quote between a 3 px and a 1 px rule after the first exchange, «Propos recueillis par …, relus par Romy», Lexique |
| Trois mots | a small dictionary on the page: numbered entries, the headword in the serif at 22 px, its sense set beside it once paired (a blank rule until then; a picture cue in a 104 px press frame with its credit), the cues as slips to set; the gap sentence a `PpCutting` with the gap as a blank rule; reasons as margin notes |
| La une de la semaine | the une is a front page: «Le Papier» at 52 px over its 3 px rule, «ÉDITION DE LA SEMAINE · Nº 47», the week's range in the serif; the lead at display size with its picture (credit + licence), its headline signed «Par toi»; the first opinion or interview lifted as the pull quote (red guillemets: the learner's words); the rest in a ruled column with the rubrique as kicker, briefs for 5–6 (two columns with a spanning odd one from 600 px); the week's Lexique; the count line as the footer rule. Composition is `uneLayout` (node-tested for 0–6 pieces: every piece printed once, no hole) |
| Carte de presse | a press card: «CARTE DE PRESSE» over a 3 px rule with the masthead, the learner's initial in the photo box and first name (from the session, never an e-mail; nothing when there is none), «STAGIAIRE · LE PAPIER», since when and how many pieces; the six rubriques as boxes — stamped in the editor's red (double ring, the stamp's ink filter, a seeded half-tilt) when filed, an empty dashed outline when not. No points, no streak |
| the memory line | an aside: off the column by 20 px behind a dotted rule, «Romy se souvient» / «Gus se souvient» in small caps (chrome language), the face, the line in the counter's voice set lighter; no box, so it never reads as the task |
| the chooser | the assignment dealt as the story's section head («LA PHOTO — Dein Auftrag», as «LE FIL — Remettre en ordre»); «Romys Vorschlag» dropped when it would be a second kicker; the dev mock now names «Le fil» and «Au comptoir» too |

## Tried and rejected

- A white contact sheet: the frames floated; the slate makes a sheet of them and holds the red loop in both themes.
- Frame buttons «Bild 1 / Bild 2» under each picture (the old look): the frame is the button now; its number is in the margin.
- Credits under each frame: four lines of credit under a 150 px frame; one numbered credit list under the sheet.
- A red notebook margin line: red stays the editor's ink — the margin is a double hairline.
- Chat bubbles in the interview: the transcript (Q./R.) is what a paper prints, and the learner's question is the bold line.
- The pull quote in the une as a plain article: it competed with the lead; lifted between rules it is the one quote of the page.
- «Toi · pour» under the opinion: every learner's piece is signed «Par toi» in red, as on La page.
- A strike drawn with `text-decoration` for the wrong fact: the deleatur loop is the mark the trap already uses.
- Underlining a field with `border-bottom`: a global `.av2 textarea { border … !important }` owns it — the rule is drawn on the label.

## Screenshots (final)

`photo-*`, `micro-*`, `mots-*`, `une-*`, `carte-*`, `souvenir-*`, `chooser-*`, each light and `-dark`;
`walk-micro-*`, `walk-une-*`, `walk-carte-*` from the walk stack (below).
Screenshots are 256-colour PNGs (Pillow median cut, dithered) to keep the folder small.

### The six to look at first

1. `une-de-6.png` (and `une-de-6-2`, `-end`, `-dark`) — the week as a front page: masthead, lead with its picture,
   the opinion lifted as the pull quote, the column, the briefs, the Lexique, the footer rule.
2. `photo-a1de-2-planche-chosen.png` — the contact sheet on the slate, the grease pencil round frame 2.
3. `photo-a1de-2-seen-right.png` — the caption labels pinned on the print, a red pin head each.
4. `micro-a2de-3-interview-shrug.png` — the transcript: «Q.» the learner's question in bold, «R.» with the shrug as a
   stage direction, the notebook kept at hand.
5. `photo-b1en-5-page.png` / `-dark` — the picture leads the page, the learner's caption under it, signed.
6. `carte-de.png` / `-dark` — the press card, three rubriques stamped, three outlined.

### The three I am least happy with

1. `photo-b1en-3-legende-found.png` — the strike across «the other picture»'s caption is the titre's corner-to-corner
   slash over a three-line caption: correct, but heavy; and the deleatur inside the loop crowds «juillet».
2. `micro-a2de-6-page.png` — the pull quote is the witness's longest answer: on the fake desk all of Lila's answers
   start «Mais arrête, c'est évident :», so the lifted line is her tic, not her best line.
3. `mots-a1de-photo-open.png` — the dictionary is right, the cues are not: the fake vocabulary's glosses
   («Lärm», «musique (de)») make the entries thin; a picture cue (the press frame) was never seen in a browser.

## Faults the browser showed (and their fixes)

- After the merge the rendez-vous tests were dealt «Le micro»: they now keep La photo and Le micro off the deal, as
  the rubriques' tests do (`948d651a`).
- A blank rule could stand alone on a line («Quand, la première fête ?» / «___») and the space before «?» broke:
  the last word and its blank never part, French punctuation keeps its non-breaking space.
- Fields drawn with `border-bottom` showed nothing (a global `textarea { border … !important }`): the rule is on the label.
- A refused option kept the old red box and «✗» inside the new labels: struck in red, no box.
- «Légende · par toi · corrigé par toi» said «par toi» twice and did not agree: `legendeBylineFr` («…, corrigée»,
  «relue par Romy»), the interview «relus par Romy» (node-tested).
- The memory line said «Un habitué se souvient» over Romy, who is not a regular: «Romy se souvient» (the speaker's name).
- Guards added (node): nothing marked on the sheet before a pick, the right frame not circled after one miss, no
  label pinned for the learner after a miss, the wrong fact struck only once found, the picture before the kicker
  on the photo page and its credit printed, the une's layout for 0–6 pieces, the press card never prints an e-mail.

## The walk stack (fake providers)

`walk-r3-*`: the repo's walk stack (`e2e/lib/stack.mjs` + `carte_server.py`, FAKE providers, throwaway database,
dropped at the end), switches for the walk's API only: `REVUE_ASSIGNMENTS_ENABLED REVUE_POURQUOI_ENABLED
REVUE_PHOTOS_ENABLED REVUE_MEMORY_ENABLED REVUE_TROIS_MOTS_ENABLED REVUE_UNE_ENABLED` (with `--comptoir`).
Walk-only seeds (not committed): «La Fête de la musique» and «Le bac» as week-47 `revue_dossiers` rows; the Fête's
two photographs as `revue_story_media` rows with the subjects the photo desk knows («Paris · Paris», «guitare
acoustique vue de face»), local prints as their files, a CC0 walk credit; per learner four closed past Papiers (the
other rubriques) so the dealer gives La photo or Le micro. Played with the mock's driving script against
`/revue?session=…`, then `/revue/une` and the Relevé for that learner. Seen: Le micro for German A1, German A2 and
English B1, La photo for English B1 (French chrome), Trois mots on their pages, the une composed from the seeded
pieces and the closed one, the press card on the Relevé with the session's name.

## Not done / not judged

- La photo was dealt on the stack only once (B1 en): the dealer's rotation gave Le micro or Le titre to the others.
- The memory line has no template for La photo and Le micro (`souvenirs/lines.json` is fil, titre, intox, opinion):
  no line on their first screens. Writing them is copy and backend work, not in this pass.
- The real proofreader, real glosses, real Commons photographs and a picture cue in Trois mots were not seen.
- Home's Sunday chip to the une was not reached.
