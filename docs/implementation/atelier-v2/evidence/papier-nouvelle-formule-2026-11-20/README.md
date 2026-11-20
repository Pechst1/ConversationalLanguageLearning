# «Le Papier» nouvelle formule — looked at in a browser (2026-11-20)

Branch `claude/papier-integration` (PRs 959 photos, 960 pourquoi, 961 assignments + «Le fil» merged, plus the
follow-ups and the fixes below). Chromium through Playwright, 375 × 812, deviceScaleFactor 2, light theme.

## How it was run

- **Full stack**, the repo's walk tooling: `web-frontend/e2e/lib/stack.mjs` with `e2e/lib/carte_server.py`
  (throwaway PostgreSQL database, `next dev`, FAKE Revue / story / pictogram providers: no model call, no network
  call to Commons), driven like `e2e/explore.mjs`. The new switches were turned on for the walk's API process only:
  `REVUE_ASSIGNMENTS_ENABLED=true REVUE_POURQUOI_ENABLED=true REVUE_PHOTOS_ENABLED=true REVUE_PHOTOS_PER_STORY=3`
  (with `--comptoir`). No default, `render.yaml` or gate was changed.
- Walk-only seeds in the throwaway database: three `revue_story_media` photo rows per story (neutral SVG placeholders
  as data URIs, Commons-shaped credits and links), and «Le bac» (the one evergreen with a wire; it is a June story)
  as a `revue_dossiers` row for week 47 so the kiosk offers it in November. A learner who should be dealt «Le fil»
  got one past Papier played as «Au comptoir» (the dealer avoids the last two shapes), as the tests do.
- Some second sessions were started through `POST /revue/sessions {dossier_id}` (what «Autre sujet ?» sends): the
  ended view has no chooser.
- The Une hero only shows on the planner's Revue day; for `b1en-home-une*` the walk answered the day's `day_shape`
  as `revue` (Playwright route), everything else real.
- `mock-*`: the dev mock, `/revue?mock=1&fil=1&comptoir=1&pourquoi=1&photos=1&band=A2&lang=de`.
- The round «N» bottom left is the Next dev-tools badge, not the app.

## Screens

Prefixes: `a1de` German A1, `a2de` German A2, `b1en` English B1. `c` = «Au comptoir», `f` = «Le fil»
(1 Lire · 2 Remettre en ordre · 3 Les mots du fil · 4 Raconter · 5 La page).

| file | what |
|---|---|
| a1de-00-chooser | the chooser (comptoir story) |
| a1de-c1-lire, a1de-c1-lire-strip-end | comptoir «Lire» with the gallery (full page; the strip scrolled to the CC0 photo — taken before fix `a1fcea7d`) |
| a1de-c2-takes, a1de-c3-intox, a1de-c3-intox-found | the takes, the intox (a wrong guest first, then the right one) |
| a1de-c4-avis, a1de-c4-avis-printed, a1de-c5-page | A1 «Ton avis» (tiles: no marks at A1), printed, «La page» |
| a1de-f1-lire | «Le fil» Lire with the gallery (follow-up b) |
| a1de-f2-ordre, -hint, -moved, -right | the order: shown, wrong once (German reason, after fix `94ce7dde`), moved with ↑, right |
| a1de-f3-mots, -placed, -miss, -right | A1 words: slots, placed wrong, the two misses, right |
| a1de-f4-raconter, -refused, -told | A1 tiles; «enfin» first refused with its reason; told |
| a1de-f5-page, -page-2 | «La page» |
| a2de-00-chooser | chooser, learner dealt the counter |
| a2de-00-chooser-before-fil | **before fix `1cf3d1ce`**: the card promises «Au comptoir» to a learner dealt «Le fil» |
| a2de-c1-lire, a2de-c2-takes | comptoir A2 |
| a2de-c4-avis-typed, -marked | two (three) slips, Romy's marks |
| a2de-c4-avis-why-le, -why-1, -why-2 | each mark opened: the rule in German, never the answer (after fix `989021c7`) |
| a2de-c4-avis-fixed-notes, a2de-c5-page | fixed: the notes, the full why with the fix, La Forge line; «La page» |
| a2de-f1-lire | fil Lire, A2 |
| a2de-f2-ordre, -hint, -swap-selected | wrong once; swap by tapping two numbers (no drag) |
| a2de-f3-mots, -miss, -right | A2 options; a miss explained inside its dispatch (fix `2a1e57d2`); right |
| a2de-f4-raconter, -typed, -marked | frames; a telling with two slips; marks (follow-up a) |
| a2de-f4-raconter-why-0, -why-1 | each mark opened (German rule, no answer) |
| a2de-f4-raconter-retry | one slip fixed, one left: try 2 of 2, «Romy soll es korrigieren» |
| a2de-f4-raconter-fixed-notes, a2de-f5-page | settled notes; «La page» |
| b1en-home-une, -gallery | Home's Une card: the button on the first screen, the strip after it (fix `fa7f1819`) |
| b1en-00-chooser | chooser, learner dealt the counter (French chrome from B1) |
| b1en-00-chooser-dealt-fil | after fix `1cf3d1ce`: a learner dealt «Le fil» gets «Le bac» with no counter promise |
| b1en-c1-lire, b1en-c2-takes | comptoir B1 |
| b1en-c4-avis-marked, -why-0, -why-1 | «le» (also earlier in the sentence) and «content»: both open their rule (fix `fb0d0df0`) |
| b1en-c4-avis-fixed-notes, b1en-c5-page | notes in English under French chrome; «La page» |
| b1en-f1-lire, b1en-f2-ordre | fil B1 |
| b1en-f2-ordre-hint | the order's reason in English under French chrome (fix `4788a650`) |
| b1en-f2-ordre-unchanged | the same order again: the check waits for a move (fix `a87deb73`) |
| b1en-f2-ordre-shown | second wrong try: «Voici le bon ordre.» |
| b1en-f3-mots, -miss, -unchanged | options; a miss in English inside its dispatch; the held check |
| b1en-f4-raconter, -typed, -marked, -why-0, -why-1 | free telling with two sequence words and two slips; both marks opened |
| b1en-f4-raconter-fixed-notes, b1en-f5-page | settled notes; «La page» |
| mock-00-chooser, mock-f1-lire, mock-f2-ordre | the dev mock's «Le fil» session with its three pictures |

## Not judged here

The fake providers write the French of the takes, the glosses («baccalauréat (de)»), the kept words («partir») and
the whys from a small table (the «il sont» why speaks of articles and adjectives): their quality, and real Commons
results, cannot be judged on this stack.
