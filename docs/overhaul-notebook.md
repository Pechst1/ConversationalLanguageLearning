# Overhaul — Notebook (`/notebook`, `/grammar`, `/vocabulary`)

Part of the journal-system overhaul; method and contract live in
`docs/JOURNAL_SYSTEM_OVERHAUL.md`. Audited 2026-07-18 against the three frontend routes,
their API client, and the grammar/vocabulary endpoints. This file completes the audit and
design-brief stage only. The visual port must wait for the owner-provided Claude Design
package; engineering should not invent that package.

## Purpose

The Notebook is the journal's reference layer: a persistent grammar index, vocabulary
ledger, and (when enabled) filed reading archive. It should let a learner inspect what they
know, see what is fragile or due, add personal notes, trace a word's biography, and launch a
targeted Atelier, Mission, or Feuilleton without turning reference browsing into a second
dashboard.

## 1. Works today (code-grounded)

- `/notebook` remembers and deep-links the grammar/vocabulary/library mode, preserving
  concept, word, book, episode, and locale query state (`pages/notebook.tsx:41-106`,
  `:108-190`). It embeds the real grammar and vocabulary surfaces instead of maintaining
  duplicate data views (`:219-231`).
- The shell shows real CEFR progression and today's Feuilleton/archive handoff
  (`pages/notebook.tsx:134-159`, `:207-208`, `:747-845`). When the library launch flag is
  enabled, saved episodes include comprehension, vocabulary, grammar, and production
  exercises (`:847-927`, `:927-1192`).
- Grammar browsing is functional: SWR-backed search/filter/list and selected-detail state
  (`pages/grammar.tsx:49-147`), responsive inline/mobile detail, due and recent errata,
  rule/trap/examples, the concept motif, and editable personal notes
  (`:214-355`, `:1048-1350`).
- The grammar API returns honest notebook list/detail fields—mastery, state, next review,
  due/recent errata counts, motif, blueprint quality, localized labels, rules, traps,
  examples, and notes—and persists notes
  (`app/api/v1/endpoints/grammar.py:94-150`, `:343-469`, `:474-627`).
- Vocabulary combines the due-context queue with the full searchable deck
  (`pages/vocabulary.tsx:668-780`, `:1224-1341`), real coverage and CEFR/category/verb
  tracks (`:653-660`, `:980-1165`), the French 5000 mastery map (`:1200-1222`), and the
  weekly dossier (`:1167-1198`).
- A vocabulary detail can record a review and launch a word-seeded Atelier, Mission, or
  Feuilleton (`pages/vocabulary.tsx:789-965`, `:1344-1490`). Word biography reconstructs
  encounters across Atelier, Missions, Feuilleton, and conversation
  (`pages/vocabulary.tsx:847-874`, `app/api/v1/endpoints/vocabulary.py:604-760`).
- Loading, empty, and retryable error states exist for the grammar list/detail and both
  vocabulary data sources (`pages/grammar.tsx:271-355`,
  `pages/vocabulary.tsx:530-568`, `:1271-1324`).
- The typed client already exposes all principal contracts: due context, coverage,
  mastery map, weekly dossier, word biography, grammar list/detail, and note updates
  (`web-frontend/services/api.ts:1439-1469`, `:1531-1564`).

## 2. Missing / should add

1. **Unify the information hierarchy.** `/notebook` adds progression and archive lead above
   embedded pages, while direct `/grammar` and `/vocabulary` use separate heroes and
   summaries. The same concept/word should have one visual and interaction contract in both
   embedded and direct-route contexts.
2. **Make "due" actionable without dashboard drift.** Grammar exposes due errata and next
   review, and vocabulary exposes due/fragile reasons, but their primary action language and
   placement differ. Design one compact "à revoir" convention that links into the Atelier
   with the existing seed parameters.
3. **Complete state coverage at shell level.** Child surfaces handle their own loading and
   errors, but CEFR progression and the Feuilleton archive lead silently collapse to empty
   on failure (`pages/notebook.tsx:134-159`). The new shell needs honest loading/error/absent
   variants for those optional modules.
4. **Reduce data density on phones.** Vocabulary currently stacks coverage atlas, weekly
   dossier, 5,000-cell map, filters, queue, deck, and detail in one route
   (`pages/vocabulary.tsx:1090-1490`). The package should establish progressive disclosure
   without removing any capability.
5. **Language consistency.** Publication-world headings and status copy mix English and
   French ("REFERENCE LAYER", "Weekly dossier", "Path review preview", "Deck browser").
   The redesign needs a complete French fiction copy deck, keeping English only for genuine
   instructional chrome.
6. **Accessibility specification.** Preserve current semantic sections, live filter counts,
   labelled progress, focus styles, reduced-motion behavior, and 44px targets; explicitly
   design keyboard/focus and screen-reader names for rows, filters, sheets, and notes.

No new backend fields are required for the visual pass. Optional follow-up product work
(not part of this reskin) could add server-persisted notebook view preferences and a compact
cross-domain "recently filed" feed.

## 3. Design drift vs. the journal contract

- The cluster defines local light-only palettes instead of consuming the global contract.
  The audit found hardcoded hex values in all three routes (notebook: 12 occurrences,
  grammar: 51, vocabulary: 26), including root backgrounds and component states
  (`pages/notebook.tsx:235-378`, `pages/grammar.tsx:222-224`, `:372-430`,
  `pages/vocabulary.tsx:1508-2740`). Direct grammar explicitly renders
  `bg-[#f1ece1] text-[#14110d]` (`pages/grammar.tsx:372-374`).
- Local aliases such as `--paper`, `--ink`, `--blue`, and `--serif` are pinned to those
  palettes rather than derived consistently from theme-aware `--app-*` tokens. Dark mode
  therefore cannot be trusted even where later rules happen to use variables.
- The routes use related but separate furniture: a notebook shell hero, a grammar masthead,
  a vocabulary hero, coverage dashboard cards, and several bespoke empty states. They do
  not read as the back matter of La Une.
- Desktop-first density remains visible in wide grids and long scroll stacks; mobile rules
  adapt the layout but do not establish a phone-first reading order.
- Inline presentation styles in the vocabulary atlas (`pages/vocabulary.tsx:1042-1161`)
  make theme, focus, and responsive states harder to audit and reuse.

## 4. Weave-in vision — "Les Cahiers"

Treat the cluster as the edition's filed back matter: **Les Cahiers**. Grammar is the
annotated rules index; vocabulary is the word ledger; the optional library is the bound
reading file. The experience should feel quieter than La Une and L'Épreuve—reference paper,
tabs, marginalia, ruled entries, index marks—but unmistakably part of the same publication.
One masthead, one mode switch, one due marker, and one detail-sheet grammar should work
whether the learner enters through `/notebook`, `/grammar`, or `/vocabulary`.

The learner first sees a concise filing summary and the most useful next reference action.
The large atlas/map remains available as a fold-out, not an obstacle before search. Selecting
a concept or word opens a legible entry with provenance, mastery, repairs, notes, and the
existing contextual launch actions. Nothing is decorative data: every count and label maps
to the fields named below.

## 5. Claude Design brief — "Les Cahiers"

> Owner: copy from here into Claude Design. Return the package before implementation.

# Design brief: "Les Cahiers" — the journal's grammar and vocabulary back matter

## Context

Design the Notebook cluster of a phone-first French-learning app whose home is the newspaper
front page **La Une**, whose practice session is the print shop **L'Épreuve**, whose Missions
are **Le Courrier**, and whose serial is **Le Feuilleton**. Routes:

- `/notebook` — shared shell and mode switch; embeds grammar/vocabulary and optionally library.
- `/grammar` — grammar concept index and detail.
- `/vocabulary` — due queue, searchable French 5000 deck, coverage, word detail/biography.

Study `web-frontend/components/laune/LaUne.tsx`,
`web-frontend/components/epreuve/Epreuve.tsx`,
`web-frontend/components/courrier/Courrier.tsx`,
`web-frontend/components/feuilleton/Feuilleton.tsx`, and the global `--app-*` tokens in
`web-frontend/styles/globals.css`. Do not redesign the bottom navigation.

## Concept

This is **Les Cahiers**, the edition's filed reference back matter. Grammar is an annotated
rules index; vocabulary is a word ledger; the optional library is a bound reading file.
It is calm, dense only on demand, and designed for quick lookup. Use La Une's rules,
kickers, serif voice, stamps, notices, and paper hierarchy, but make the Notebook feel like
indexed reference stock rather than another front page.

## Real data contract

Grammar list/detail can use only:

- `display_title`, localized title/category/subskill, `level`, `category`, `subskill`
- `mastery`, `state`, `state_label`, `next_review`
- `due_errata_count`, `recent_errata_count`, `due_errata`, `recent_errata`
- `motif`, `blueprint_status`, `blueprint_quality`
- `core_rule`, `main_traps`, `anchor_examples`, `exercise_tags`, `description`, `examples`
- `personal_notes` (editable and persisted)

Vocabulary can use only:

- due-context cards: word, translation, bucket/mastery state, proficiency, due/fragility reason
- deck word, translation, part of speech, frequency rank, difficulty
- coverage: CEFR bands, category tracks, verb tracks, grammar tracks, `next_best_set`
- mastery-map cells and state totals
- weekly dossier headline, repairs/reviews/seen/used, fragile threads, next actions
- biography origin, progress, examples, and chronological events

Shell modules can use only CEFR progress, current Feuilleton payload, route/query state, and
the launch flag. Design an absent state; never invent counts, dates, or editorial copy as data.

## Required mobile views (390px)

1. Notebook landing, grammar active: compact filing summary, optional Feuilleton file, mode
   switch, grammar index with one selected/due entry.
2. Grammar entry detail: title/level/state, rule, examples, traps, motif, due and recent
   errata, personal notes idle/editing/saving/error, action into Atelier.
3. Vocabulary landing: useful next set first, compact due/fragile summary, search and filters,
   queue/deck distinction, the atlas/map available by progressive disclosure.
4. Vocabulary entry sheet: word hero, translation/metadata, fragility reason, review action,
   biography entry, and seeded Atelier/Mission/Feuilleton actions.
5. Vocabulary fold-out: CEFR/category/verb coverage plus mastery map without forcing 5,000
   tiny cells into the default reading path.
6. Optional library mode: bound books/episodes and the existing exercise runner, visually
   within the same filing system.
7. Direct-route variants for `/grammar` and `/vocabulary` that reuse the same primitives
   without duplicating a second hero.

## Required states

- Loading: press/file skeleton, not a generic spinner.
- Empty: no concepts/words for the current filter; first-use state; no optional Feuilleton.
- Partial data: shell progression or archive module unavailable while reference data works.
- Error: labelled press notice with message and Retry.
- Populated, selected, due/fragile, mastered, unsaved note, saving, and save error.
- Light and dark for every primary view; narrow phone and at least one 430px check.
- Reduced motion, keyboard focus, long French/German strings, and large dynamic text.

## Copy deck

Use French inside the publication:

- Section: **LES CAHIERS**
- Modes: **Grammaire · Vocabulaire · Bibliothèque**
- Grammar index: **Index des règles**
- Vocabulary ledger: **Registre des mots**
- Due marker: **À revoir**
- Recent repairs: **Errata récents**
- Notes: **Notes en marge**
- Coverage fold-out: **Atlas des acquis**
- Weekly summary: **Dossier de la semaine**
- Search placeholders: **Chercher une règle…**, **Chercher un mot…**
- Loading: **Classement en cours**
- Empty: **Aucune fiche dans ce classement**
- Error label: **Avis du bureau des archives**

English may remain only for instructional actions such as Retry where the product currently
uses English chrome. Do not mix languages within one line.

## Component deliverables

Provide production-oriented React/CSS component specs and state frames for:

- `NcShell`, `NcMasthead`, `NcModeTabs`, `NcFilingSummary`
- `NcIndex`, `NcIndexRow`, `NcDueMark`, `NcStateStamp`
- `NcEntry`, `NcRule`, `NcExamples`, `NcErrata`, `NcMarginNotes`
- `NcWordRow`, `NcWordEntry`, `NcBiography`
- `NcAtlasFoldout`, `NcCoverageTrack`, `NcMasteryMap`
- `NcSkeleton`, `NcNotice`, `NcEmpty`

Show which existing La Une notice/stamp/skeleton primitives should be reused instead of
duplicated. Include exact class/state contracts and a migration map from current markup.

## Hard constraints

- `--app-*` colors and typography only; derived values must use `color-mix` and be documented.
- Light/dark/system themes; no `:root` palette, hardcoded hex, or theme pinning.
- Phone-first single column, safe-area aware, 44px targets. Desktop enhancement is secondary.
- Preserve every functional capability and existing route/query contract.
- Honest data only. Optional data disappears or has an explicitly designed unavailable state.
- Motion uses transform/opacity/filter only and respects `prefers-reduced-motion`.
- Keep semantic headings, labelled sections/progress, focus-visible treatment, live filter
  summaries, and accessible bottom sheets.

## Package requested

1. High-fidelity 390px frames for views 1-7, with light/dark for views 1-5.
2. All required loading/empty/error/partial/editing states.
3. Component source/spec and token-only CSS.
4. Copy sheet with every visible string.
5. Data-to-prop mapping and migration notes for `pages/notebook.tsx`,
   `pages/grammar.tsx`, and `pages/vocabulary.tsx`.

