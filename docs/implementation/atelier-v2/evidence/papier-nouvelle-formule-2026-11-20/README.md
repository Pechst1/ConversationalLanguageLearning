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

---

# «Le titre» and «L'intox express» — looked at in a browser (2026-11-20, second pass)

PR 962 (`claude/papier-titre-intox`) merged into this branch, then played the same way: the walk stack above
(`stack.mjs` + `carte_server.py`, fake providers, throwaway database), driven like `e2e/explore.mjs` on port 7791,
375 × 812, deviceScaleFactor 2, light theme. The switches set for the walk's API process only:
`REVUE_ASSIGNMENTS_ENABLED=true REVUE_POURQUOI_ENABLED=true REVUE_PHOTOS_ENABLED=true REVUE_PHOTOS_PER_STORY=3`
(with `--comptoir`), plus a `SECRET_KEY` for the walk API. Nothing else changed.

## Walk-only seeds

- «La Fête de la musique» (`evergreen-fete-de-la-musique`, the one story with hand-written headlines and statements,
  a June story) as a `revue_dossiers` row for week 47 (`period` 2026-W47, its evergreen payload with `week` set to
  2026-W47, builder `walk-seed`), so the kiosk offers it in November; its headlines and statements come from
  `evergreen/titre/` and `evergreen/intox/` by id. «Le bac» the same way for the retaken `a1de-f1-lire`.
- Three `revue_story_media` photo rows for each (neutral SVG placeholders as data URIs, Commons-shaped credits).
- Past Papiers per learner, as the tests' `make_user` (closed `revue_sessions` rows whose first `choice` event carries
  `mode`): dealt «Le titre» = last two played `comptoir`, `intox`; dealt «L'intox express» = last two `titre`,
  `comptoir`; dealt the counter = `titre`, `intox`; dealt «Le fil» on «Le bac» = `comptoir`.

## Screens

Prefixes: `t-` «Le titre» (1 Lire · 2 Trois titres · 3 Le piège · 4 À toi · 5 La page), `i-` «L'intox express»
(1 Lire · 2 Vrai ou faux · 3 Corrige · 4 La page); `a1de` German A1, `a2de` German A2, `b1en` English B1.
Every screen after the fixes below unless marked.

| file | what |
|---|---|
| i-a1de-00-chooser, t-a1de-00-chooser, i-b1en-00-chooser, t-b1en-00-chooser | the card of a story dealt titre / intox: no counter question (follow-up d) |
| a1de-00-chooser-dealt-comptoir | the same story dealt the counter: its question and regulars |
| i-*-1-lire, i-a1de-1-lire-strip, t-*-1-lire | Lire: picture, lead, then the photo strip (follow-up b and the Lire fix) |
| a1de-f1-lire, a1de-f1-lire-strip | «Le fil» Lire retaken: the lead's first line at y = 326 (was ≈ 620), every credit in the strip |
| a1de-c1-lire-after | the counter's Lire: lead and question before the strip |
| i-a1de-2-round, -reread | one statement, «Vrai» / «Faux», the lead one tap away |
| i-*-2-round-miss, -miss-false | two misses: a true one answered «faux», a false one answered «vrai»: verdict, why (mother tongue), lit quote with its source |
| i-a1de-2-round-right, -false, -last | right answers; the score |
| i-*-3-fix, -fix-miss, -fix-done | Corrige: struck words, the quote; a wrong pick (A1–A2) / a wrong rewrite (B1) first, then right |
| i-*-4-page (-full) | La page: the five lines, «On disait», the learner's rewrites (B1), the sources |
| t-*-2-three, -chosen, -wrong, -right, -shown | three headlines; a wrong pick first (role, why, claim); right (A1, B1) or shown after two (A2) |
| t-*-3-trap, -tapped, -miss, -right | the trap: a wrong word first («fête», «juin», «nuit»), then «tout le monde» |
| t-a1de-4-build, -built, -printed | A1 tiles, the built headline, printed |
| t-a2de-4-build-*, t-b1en-4-build-* | A2 frame / B1 free: the exaggerated element refused before sending (`-too-much`), a headline with two slips (`-typed`, `-marked`), each mark opened (`-why-0`, `-why-1`, follow-up a), one fixed (`-retry`, A2), settled with notes (`-fixed-notes`) |
| t-*-5-page | La page: the learner's headline over the lead, signed with its sources |
| mock-t0..t2, mock-i0..i2 | the dev mock: `/revue?mock=1&titre=1&pourquoi=1&photos=1&band=A2&lang=de`, `/revue?mock=1&intox=1&photos=1&band=B1&lang=en` (follow-up e) |

## Faults seen, and their fixes

| seen | fix |
|---|---|
| a1de-f1-lire: the picture and the strip put the lead's first line at ≈ 620 of 812 | `00b5ce09` strip after the text on every Lire |
| «Nicht ganz. Das stimmt.» / «Pas tout à fait. C'est vrai.» read as «not quite — right» | `aa3668c5` «Der Satz ist richtig / falsch» |
| a wrong pick of the off headline: «sagt etwas, das der Artikel nicht sagt: Stimmt, aber…» (false, two colons) | `aa3668c5` «Nicht diese.» on its own line |
| after tapping «nuit»: «The article does say these: nuit» — it does not | `aa3668c5` «Not these words: “nuit”.» |
| «Nimm diese Wörter heraus» named no words | `aa3668c5` names «tout le monde» |
| «à», «le» in the trap 35 and 37 px wide | `aa3668c5` min-width 44 px |
| La page reprinted the lead and the statements with no source | `aa3668c5` the byline «d'après …» |
| B1 Corrige: after a miss the field was emptied | `aa3668c5` keeps the last try |
| no scroll: Romy's line cut under the head on a new screen; a why or a verdict under the foot | `65bbfb99` the counter's scroll, shared |

The before-fix screenshots of these were overwritten by the retakes; the commits quote what was on screen.

## Judged, not changed

- A false statement's why in the round («Das Fest ist am 21. Juni … nicht am 14. Juli») names the value Corrige asks
  for; Corrige itself prints the quote with the settling words lit (spec §11.4), so the value is on that screen by
  design. Left as specified.
- A1–A2 Corrige offers two options: after one miss the other is the answer («Versuch 2 von 2»). As specified.
- The A2 word count includes the frame («5 von 12 Wörtern» before typing). Left.

## Not judged here

Fake providers: Romy's marks and whys come from a small table (two kinds, one sentence each), and the kept words
are the fake's; the quality of model-written headlines, statements, whys and corrections, and real Commons photos,
cannot be judged on this stack. «Le fil»'s player (RvFil) has no scroll-on-act effect either: read in the code, not walked again.

---

# «La photo» and «Le micro» — looked at in a browser (2026-11-21, third pass)

Branch `claude/papier-photo-micro`. Played with `web-frontend/e2e/papier-photo-micro-shots.mjs`: the walk's throwaway
stack (`stack.mjs` + `carte_server.py`, fake providers, throwaway database, no network) for a signed-in learner, then
the dev mock's sessions — `/revue?mock=1&photo=1` and `/revue?mock=1&micro=1` with `band=A1|A2|B1` and `lang=de|en`
(`&pourquoi=1` at A2) — at 375 × 812, deviceScaleFactor 2, light theme. Nothing else changed. The script prints, per
screen, the buttons under 44 px, a horizontal scroll and whether the newest part sits under the foot.

## Screens

Prefixes: `p-` «La photo» (1 Lire · 2 La planche · 3 La légende · 4 À toi · 5 La page), `m-` «Le micro» (1 Lire ·
2 Prépare tes questions · 3 L'interview · 4 Tes notes · 5 Relis tes questions · 6 La page); `a1de` German A1, `a2de`
German A2, `b1en` English B1 (the mock keeps the `lang` chrome at B1; the server's is French from B1).

| file | what |
|---|---|
| p-*-00-chooser, m-*-00-chooser | the chooser names the assignment dealt: «Dein Auftrag · La photo» |
| p-a1de-2-planche, -miss | two pictures side by side, each with its credit and licence links; a wrong pick: «Nicht dieses. Auf diesem Bild sieht man: Paris.» (no answer) |
| p-a1de-2-seen, -seen-miss, -seen-right | «Qu'est-ce qu'on voit ?»: «Paris» tapped: «Das ist auf einem anderen Bild … Es fehlen noch 1.», then right |
| p-a1de-3-legende, -legende-miss | three captions; the «other» one picked: its why in German; nothing else revealed |
| p-a1de-3-fix, -fix-miss, -fix-done | the wrong words struck, a pick, one miss, then right |
| p-a1de-4-build, -built, -printed | A1 tiles: a picture, a thing seen, a fact; printed with no model call |
| p-a2de-4-build*, p-b1en-4-build* | A2 frame / B1 two sentences; the B1 refusal («Two sentences…») in view; Romy's marks, a mark opened, fixed |
| p-b1en-3-fix* | B1 rewrite: «…le 14 juillet» refused, then right |
| p-*-5-page | La page: the picture large, the learner's caption, the credit, «Romy Tremblay, avec toi · d'après …» |
| m-a1de-2-prepare, -chosen | Romy's notes with their holes; three chosen |
| m-a1de-3-interview* | A1: question tiles, the witness (Lila) answers in her bubble, a hole ticked |
| m-a2de-3-interview-shrug | a question the story cannot answer: the shrug, «Keine Antwort: Diese Frage zählt nicht» |
| m-a2de-3-interview-slip | «Pourquoi elle est gratuite ?» answered, nothing said about its form |
| m-*-4-notes* | the holes filled from the witness's lines (pick A1–A2, typed B1; a miss first) |
| m-a2de-5-review | the questions and the app's rules for the two slips in German, never the corrected question |
| m-b1en-5-review-marked, -fixed | Romy's mark on «tres», fixed by the learner |
| m-*-6-page | La page: Q. / R. with each answer's source, «Propos recueillis par toi» |

## Faults seen, and their fixes

| seen | fix |
|---|---|
| La légende's correction: an empty foot bar under the options | `ac9ea815` no foot while the correction is answered on the page |
| the false caption printed plain in the correction | `ac9ea815` its wrong words struck (as the intox) |
| «Combien ça coûte ?___» (the hole glued to the «?») | `ac9ea815` a non-breaking space |
| La page: the learner's caption small and grey under the credit | `ac9ea815` body size, ink |
| B1 À toi: «Two sentences…» refused under the foot, below the field | this pass: a refusal is brought into view as a verdict is |

## Not judged here

The mock's edit is the comptoir mock's small table (it marks «tres», not the missing inversion, so the A2 page prints
«Pourquoi elle est gratuite ?» as written) and its sources are the story's; the pictures are neutral placeholders.
No prompt has run on a real model and no real Commons photo was seen.
