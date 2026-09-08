# Design audit — 30 July 2026

Scope: the visual system, not the product logic. Measured on the real render at
390 × 844 (the compositions in `pages/mobile-visual-qa.tsx`), plus static counts
across the six journal surfaces (`components/laune`, `epreuve`, `cahiers`,
`courrier`, `feuilleton`, `pages/atelier.tsx`).

## Status — all five journal surfaces converted (30 July)

Every surface now uses one six-step scale, in `rem`, with an 11 px floor:

```
LaUne       0 px / 47 tokens        Courrier    0 px / 66 tokens
Epreuve     0 px / 80 tokens        Feuilleton  0 px / 93 tokens
Cahiers     0 px / 89 tokens
```

Measured on the render, before → after:

| | La Une | L'Épreuve | Cahiers |
|---|---|---|---|
| distinct font sizes | 21 → **6** | 12 → **5** | 11 → **4** |
| uppercase labels | 20 → **5** | 15 → **9** (4 buttons) | 16 → **13** |
| text below 11 px | 24 → **0** | 13 → **0** | 18 → **0** |
| worst small-text contrast | 3.45 / 2.34 dark → **≥4.7** | 4.06 → **4.7** | 4.06 → **4.7** |
| height | 1714 → **1398 px** | 1052 → **1018 px** | 684 → **604 px** |

Token-level fixes that apply everywhere: `--app-ink-3` 3.45:1 → 5.0:1; the
newsprint tokens follow the theme instead of being pinned to light; red is
reserved for the correction mark rather than 11 px prose (WP-B5's own
direction).

**One defect was structural and existed on all five surfaces.** Element-scoped
resets (`.lu a`, `.nc button`, `.fe button`, `.cr button`) carry class+type
specificity and so outranked every component class, silently stripping border,
padding and type from chips, rows and links — the Cahiers filter chips were
rendering as run-together text. All five are now wrapped in `:where()`, which is
what a reset should always have had.

### The legacy layer — reachable surfaces done

Every surface a learner can actually open is now on the tokens, with **zero**
offset shadows and no hardcoded `black`/`white`/`gray`/`bauhaus` values:

settings · progress · achievements · practice · vocabulary · vocabulary/review ·
auth (signin, signup, forgot-password) · atelier · notebook · RedInkRepairSlip

Settings alone carried 141 hardcoded utilities plus a block of `!important`
overrides whose only job was to beat them; the utilities are tokens now and the
override block went with them.

`/progress` and `/achievements` are wired into the Cahier as a fourth **Progrès**
tab (both pages take an `embedded` prop and keep working standalone), so earned
achievements are viewable for the first time.

### Left standing on purpose

82 offset shadows remain, all inside one unreachable cluster that only links to
itself — `/stories`, `/story/[id]`, `/sessions`, `/learn/*` and the
`components/learning`, `components/story`, `components/audio` trees. Reskinning
pages nobody can open is waste; deleting them is a product call, not a design
one. They are listed here so the number is not mistaken for unfinished styling
work:

```
pages/story/[id].tsx 14   components/learning/ConversationHistory.tsx 9
pages/stories.tsx 12      components/learning/SessionSummary.tsx 7
pages/sessions.tsx 5      components/learning/InsightsCard.tsx 3
pages/learn/session/[id].tsx 4   components/learning/GrammarLevelGrid.tsx 3
pages/learn/new.tsx 4     components/story/UploadBookModal.tsx 2
                          components/audio/RoleplaySelection.tsx 2
                          components/learning/LiveStoryPickerModal.tsx 1
```

`/practice` is *not* in that cluster — La Une links to it ("Pratique libre"), so
it was reskinned.

`docs/pilot-density-pass.md` set the right hierarchy contract and then explicitly
removed nothing ("No content, state, routing, or control was removed"). That is
why the surfaces are still crowded: **you cannot fix "too much" by respacing it.**

## Verdict

The typography is genuinely excellent and the paper world is a real asset. The
problem is not the geometry — it is that every element is announced, boxed, and
ruled. One front page carries **21 distinct font sizes, 20 uppercase labels and
25 bordered elements** before the learner reads a single French word.

## Measured

| Metric | Now | Target |
|---|---|---|
| Distinct font sizes, one La Une screen | **21** (6.75 → 44 px) | 6 |
| Distinct font sizes, six journal surfaces | **49** | 6 |
| `font-size` declarations ≤ 10.5 px | **286 of 598 (48 %)** | 0 below 11 px |
| Uppercase letterspaced labels, one screen | **20** | ≤ 5 |
| `text-transform: uppercase` rules | **261** | ~40 |
| Bordered elements, one screen | **25** | ≤ 8 |
| Border declarations per surface | 42–69 | ≤ 20 |
| La Une page height | **1714 px** (2.0 viewports) | ~1 viewport + reach |
| Offset block shadows, journal surfaces | **0** | 0 |
| Offset block shadows, legacy pages | **187** | 0 |

Contrast, measured on the live render:

- La Une accent kickers on `--app-sheet`: **6.48 : 1** — fine.
- Grey micro-labels (`--app-ink-3`) at 8–9 px: **3.45 : 1** — fails AA. Affects
  "Le cours du français", "Demain dans votre édition", "Fin de l'édition".
- Dark mode, red kicker on sheet: **2.34 : 1** — fails badly. `--app-red`
  (#ff5a42) is tuned for paper, not for #211d16.
- The type is `px` throughout (≈360 declarations vs 6 `rem`), so Settings →
  Apparence → font size moves almost nothing.

## Is it too brutal? — the honest answer

**Two different visual languages are running at once, and only one of them is
brutalist.**

1. **The journal system** (La Une, Épreuve, Cahiers, Courrier, Feuilleton):
   1 px hairlines, no shadows, no radii, letterpress serif. It contains **zero**
   offset block shadows. This is not brutalism; it is Swiss editorial, and it is
   the best thing in the product.
2. **The legacy layer** (settings, progress, practice, stories, story, sessions,
   achievements, learn/*): 187 hard offset shadows, 4 px `#000` borders,
   `rounded-lg`, hardcoded greys that break dark mode. *This* is neo-brutalism,
   it is dated, it is off-world, and it should go.

So the "too brutal" feeling has two different causes depending on where it hits:

- On Settings or Progress, the instinct is exactly right — that language does not
  belong to this product and should be deleted, not softened.
- On La Une or the Épreuve, what reads as "brutal" is not the boxes. It is
  **density**: 21 type sizes, 20 shouted labels, 25 compartments. The eye has
  nowhere to rest, so the squareness gets blamed for the noise.

**Recommendation: do not round the corners.** The squared, ruled, letterpress
geometry is the one thing that makes this app look like nothing else, and
softening it would cost the identity while leaving the actual problem — the
quantity of labelled compartments — untouched. Remove compartments instead. A
newspaper is mostly white space and rules; it is calm *because* the grid is
strict, not in spite of it.

Where softening genuinely is right: hairlines can drop to a lighter ink so they
separate without drawing attention, and most blocks should have **no** border at
all — whitespace and a single rule already say "new section".

## Concrete defects

1. **Link styling is silently overridden.** `.lu a, .lu button { font: inherit;
   color: inherit }` (`LaUne.tsx:648`) outranks every per-component link rule.
   `.lu-prescription-adjust` declares 9 px / 800 / `--ink-3` and renders at
   **16 px / 400 / full ink** — the secondary action is the loudest text in the
   block. Same for the Lexique card link.
2. **The brand and the gear appear twice** on the same screen — once in the app
   masthead, once in `LuMasthead`.
3. **Two identical primary CTAs.** "Continuer" and "Commencer la séance" are both
   full-width black bars; neither wins, and on most days they start the same
   session.
4. **6.75 px text exists** (the `3ᴱ` streak superscript). There is no legible
   floor.
5. **Nine section announcements in two screens**, each with a decorative `.tail`
   rule: VOTRE ÉDITION / LE FEUILLETON / LA SÉANCE DU JOUR / LE LEXIQUE / ERRATA /
   LA PHRASE D'HIER / LE COURS DU FRANÇAIS / DEMAIN DANS VOTRE ÉDITION / FIN DE
   L'ÉDITION. The serif hero under each one already says what the block is.
6. **Boxing is inconsistent.** Prescription, Lead and Séance are rule-separated
   sections; Phrase, Cours and the Lexique/Errata duo are bordered cards. No rule
   distinguishes the two.
7. **Daily epigrams become furniture.** "La mémoire s'use si l'on ne s'en sert.",
   "La rédaction corrige ses fautes d'hier.", "Fin de l'édition" — charming once,
   noise on day nine.

## Plan, in order

**1. One type scale.** Six steps in `rem`: 0.6875 (11 px floor) / 0.8125 / 1 /
1.25 / 1.75 / 2.75. Nothing below 11 px, ever. Mechanical, and it makes the
font-size setting real. Biggest single win.

**2. Delete labels, don't respace them.** Drop the kicker + `.tail` pattern
wherever the hero says it already. Keep a label only when the word carries
information the hero cannot (a count, "Paru", a state). Target ≤ 5 per screen.

**3. Decide card vs section once.** Recommended: everything is a rule-separated
section; a border is reserved for exactly one meaning (e.g. "not today's work").
Target ≤ 8 bordered elements per screen.

**4. One brand, one gear, one primary action per screen.** Fold `LuMasthead` into
the app masthead; demote the second CTA to a text link.

**5. Fix the link override and the contrast floor.** Scope the `.lu a` reset so
it cannot beat component rules; darken `--app-ink-3` to ≥ 4.5 : 1, and give the
dark theme its own accent values (the red is unreadable there).

**6. Retire the legacy layer.** 187 offset shadows and the hardcoded `#000`/
`bg-white` greys in settings, progress, practice, stories, story, achievements,
sessions, learn/*. Either give them the journal treatment or delete the page —
several are already unreachable, so deletion is often the honest answer.

**7. Cut the epigrams and the colophon.**

Expected outcome: La Une from ~1714 px to roughly one viewport plus a reach,
21 type sizes to 6, 20 labels to ≤ 5 — with the geometry untouched.

## Not recommended

- Rounding corners or softening the grid. It would erase the identity and leave
  the density.
- Another CSS-only spacing pass. That was tried; the contract was written and the
  content was kept.
- Mascots or illustration to "warm it up". The cast portraits already do that job.
