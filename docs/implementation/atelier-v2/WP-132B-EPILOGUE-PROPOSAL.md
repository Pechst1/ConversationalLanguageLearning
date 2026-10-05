# WP-132B · «La semaine d'après»: a written ending to season 1 (proposal)

*2026-10-05. Content program D8; EXPERIENCE-REVIEW 2026-10-04 §6 («the gap after the finale»);
WORK-PACKAGES-2026-10-04-experience WP-132 «B». **Status: proposal — owner approval required.**
Nothing in the story text below is canon until approved. The routing code that serves it is
committed (`app/services/season/epilogue.py`) and behaves correctly without it.*

Two patches go with this document:

| Patch | What it holds | Owner |
|---|---|---|
| [`WP-132B-EPILOGUE-PROPOSAL.patch`](WP-132B-EPILOGUE-PROPOSAL.patch) | The story text: `app/data/season/s1/epilogue.json` (new), `levels_epilogue.json` (new: A1 + `a1_native`, B2, C1 variants and level example replies), `tasks.json` (+10 plain tasks and «ask again» lines), the bible chapter `docs/story/season-1/12-la-semaine-dapres.md` (new) | Owner (story text) |
| [`WP-132B-HOOKS.patch`](WP-132B-HOOKS.patch) | Six short calls into `epilogue.py` from `format.load_season`, `runtime` (`today_for`, `context_block`, `season_script_finished`, `settle`) and `living_story.generate_scene`, plus `tests/test_season_one.py` made epilogue-aware | Orchestrator (shared files, WP-124b edits them in parallel) |

The hooks are useful **without** the story text: they give a season life an honest, authored
archive day at the end of T8 and a continuation that knows how the season ended.

---

## 1. What a learner meets after T8 today (traced)

Traced on the code at `dab9d98` with a learner put on T8 A (`season.admin.jump_to_day`, day 58) and
played through the real journey with the season suite's scripted provider:

| Day | Served | Why |
|---|---|---|
| 58, 59 | T8 A, T8 B as written | the tentpole path |
| 60 → | a generated day («Le quartier 0», «… 1»…) | `clock.position` is `finished`; `living_story.generate_scene` falls to the director with s1's world, **no brief, no arcs**, and nothing about the ending |
| a few days later | the interlude stage | `season_stage_after_chapter` sees `season_script_finished` |
| interlude chapter closes | `roll_over_season`: named interlude, then the *reprise season* | the Berlin S2 bible is already refused for a scripted world (D8 guard in `roll_over_season`) |

So the review's two fears do not happen as such: the life is never reset to the café of strangers
(WP-124a re-reads T8 B when a day is lost) and the old serial's Berlin season is never loaded.
What does happen is the third failure D8 names: **the season stops being written.** The director of
day 60 is told nothing of the ending the learner chose a day earlier (Le Mistral may be written open
after it closed in «Laisser partir»; Lila may appear at the zinc after her train), and the reprise
season is grown from `live["planted"]`, `consequences`, `threads_archive` and `world_flags`, none of
which a season life fills: the ending, the painting, Lila's key, Marchand's Sundays never reach it.

## 2. What is served after T8 now

```
T8 A ─ T8 B ─┬─ epilogue.json present ─ E1 A ─ E1 B ─ E2 A ─ E2 B ─ E3 A ─ E3 B ─┐
             │                                                                    ├─ continuation
             └─ no epilogue ───────── one archive day («La clé d'Odile») ─────────┘
```

* **The epilogue week** (this proposal): three two-day pages in the tentpole format, appended to the
  season as segments `e1`, `e2`, `e3` (`epilogue.attach_epilogue`, called from `load_season`). The
  clock, the reader, settle, the WP-124a reprise and both validators serve them exactly as they serve
  T1–T8. Variants are chosen by `when: {"s1.ending": …}` like T8's endings. A malformed epilogue is
  refused whole and logged (the season then ends on the archive day), never half-served.
* **Without an epilogue** (committed behaviour): one authored *archive day* — the eight «À suivre» of
  the learner's own branches, T1 → T8, at their level; the season's question as the one turn (task in
  the learner's language: «Season 1 is over. Answer its question in one sentence…»); T8 B's own last
  caption as its ending. Every French line on it is a bible line the learner has read. It sets
  nothing, counts no season day and closes the season (`state["ended"]`).
* **The continuation**: generated days in s1's world. The director's `season_script` block now
  carries `after_finale` — the ending, the painting, Lila's path and key, Marchand's Sundays, Camille
  on *vous*, Romy's card, the ending's facts (from the bible's «Who remembers what»), the open
  question «Who is «L.»…?» and the rules (the cast knows the learner; no stranger's welcome; never the
  old serial's season 2; Le Mistral closed in «Laisser partir»; L. is looked for, never revealed).
  The ending is also written into `live["world_flags"]` and the last page's open question into
  `live["threads_archive"]`, so the written and the reprise seasons grow their first arc from it.
* **Provider unavailable**: every page above needs no model. A lost continuation day is WP-124a's
  reprise of the last completed page — E3 B, or T8 B — never strangers, never Berlin, never a reset.
* **A life that ended before the epilogue ships** keeps its ending: once the archive day closed the
  season, `epilogue.position_for` reports it finished, so nobody three weeks into the continuation is
  pulled back to the morning after the train.

## 3. The epilogue week

*«La semaine d'après» · Sat 9 – Fri 15 January · six learner days.* Every ending keeps its own
consequences and converges on one open door, the rue de Lancry; the season's question for the next
authored season («Who is «L.»?») is never answered.

| Page | Days | Garder | Partager | Laisser partir |
|---|---|---|---|---|
| **E1 «Le premier matin»** | A sam. 9 · B dim. 10 | the painting upstairs; Margaux: what will you do with it? Marchand's Sundays (if offered in T8) | the co-op's first Saturday; the empty nail; Gus lies about the painting | the shutter down, the neon on the pavement; Marin's soup at Toi's studio |
| | B (common) | Lila's first message from Berlin; Toi writes back (path-coloured reply) | Romy's article, page three | Margaux's postcard of the sea, «Elle est grande.» |
| **E2 «Rue de Lancry»** | A mar. 12 | the street, the green door, Mme Diallo: who are you looking for? | the co-op meeting; Gus, cornered: «ma mère dit : rue de Lancry» | the brocante: sold, Saturday, to an old gentleman |
| | B mer. 13 (common) | Camille brings Marchand's registered letter: Odile walked by the rue de Lancry every Sunday; «À la prochaine dispute.» | | |
| **E3 «Le billet»** | A jeu. 14 | the booth, unchanged | the co-op's long table | Gus's loft, the Mistral's bench |
| | A (common) | Romy, camera off: «C'est quoi, la vraie histoire ?»; Marin's father calls: he is coming to Paris | | |
| | B ven. 15 (common) | the return ticket Toi has moved all season; Lila: are you taking it? (`user.stays`); last image per ending; the lit window on the rue de Lancry | | |

**State in:** `s1.ending`, `s1.painting`, `marchand.sundays`, `s1.lila_path`, `user.return_ticket`.
**State out (new flag, declared in `epilogue.json`):** `user.stays` = `stays` · `leaves_and_returns`
· `undecided` (E3 B), and `user.return_ticket = cancelled` when the learner stays.
**Never changed:** `s1.painting` (with you / with Gus / lost) stays season 2's door.

### Opening lines and last captions, per day and branch (A2)

| Day | Garder | Partager | Laisser partir |
|---|---|---|---|
| **E1 A** sam. 9 «Le premier matin» | GUS «Règle numéro un : on ne touche pas à la plaque.» · MARGAUX «Alors. Le tableau. Tu en fais quoi ?» | MARIN «Atelier peinture. Ils ont six ans. Ils peignent les murs.» · GUS «Tu me regardes comme un policier. Qu'est-ce qu'il y a ?» | MARIN «Bon. Qui veut une soupe ?» · «Le café est fermé. Lila est partie. Et toi, tu fais quoi ?» |
| ↳ mid-point (all) | SMS (Lila) «Berlin : il pleut. Comme à Paris. Et toi, ça va ?» · «Le premier matin sans Lila. À suivre…» | same | same |
| **E1 B** dim. 10 «Le dimanche» | MARCHAND «Le bus 46. Deux croissants. L'escalier, toujours le même.» (if `marchand.sundays`; else a silent window) · SMS «Alors ? Le tableau ? Raconte. Tout.» | ROMY «Page trois. Et ils veulent une suite. Je capote.» · SMS «Alors ? Le tableau ? Raconte. Tout.» | CARD «Elle est grande. — M.» · SMS «Alors ? Le tableau ? Raconte. Tout.» |
| ↳ À suivre | «Derrière le tableau : rue de Lancry. C'est à deux cents mètres. À suivre…» | «Gus garde le tableau. Et sa mère sait quelque chose. À suivre…» | «Les chaises du Mistral sont à la brocante. Et le tableau ? À suivre…» |
| **E2 A** mar. 12 | «Rue de Lancry»: MME DIALLO «C'est un tableau volé, ça ?» · «Vous cherchez qui ?» | «Rue de Lancry»: MARIN «Point numéro un : le tableau du Mistral. Qui sait où il est ?» · MARGAUX «J'ai rien entendu.» | «La brocante»: LE BROCANTEUR «Les chaises du Mistral ? Vingt euros. Pour vous, vingt-cinq.» · TOI «Et le tableau ?» |
| ↳ mid-point | «Au troisième, quelqu'un ferme la fenêtre. À suivre…» | «Gus n'a pas de tableau. Mais il a une adresse. À suivre…» | «Le tableau est quelque part dans Paris. Chez un vieux monsieur. À suivre…» |
| **E2 B** mer. 13 «La lettre recommandée» (all) | CAMILLE «De la part de mon grand-père. Il écrit en recommandé. Même à vous.» · LETTER «Le dimanche, Odile prenait toujours le même chemin, par la rue de Lancry. Elle ne m'a jamais dit pourquoi. Je ne lui ai jamais demandé. M. Marchand» | same | same |
| ↳ À suivre | «Tous les dimanches, Odile passait par la rue de Lancry. Pourquoi ? À suivre…» | same | same |
| **E3 A** jeu. 14 «La vraie histoire» | GUS «Une semaine ! Et rien n'a changé. C'est sublime.» | GUS «Tu m'as coûté une banquette. Je te pardonne. Un peu.» | GUS «Bienvenue au château. La banquette est d'époque. Moi aussi.» |
| ↳ (all) | ROMY «Pas pour un article. Pour moi. C'est quoi, la vraie histoire ?» · mid-point: MARIN «Papa ? … Tu viens à Paris ? Quand ?» · «Le père de Marin vient à Paris. À suivre…» | same | same |
| **E3 B** ven. 15 «Le billet» (all) | SMS «Rappel : votre billet retour, aujourd'hui, 18 h 12.» · SMS (Lila) «C'est aujourd'hui, ton billet. Tu le prends ?» | same | same |
| ↳ last image, then the season's last caption | the painting on the wall upstairs | Gus turns the painting round for the first time | the bare nail of the closed Mistral |
| ↳ À suivre (all) | «Rue de Lancry, au troisième, une fenêtre est encore allumée. À suivre…» | same | same |


## 4. Level variants and validators

Written to SEASON-LEVELS.md's rules: A1 in the present and futur proche, ≤ 10 words a line, one word
outside the A1 list a line, its own `a1_native` {en, de}; long documents (Marchand's letter) get a
30-word easy read; B2 and C1 variants for every line; level example replies (a1/b2/c1) for every
reply; a plain task (en/de/fr) and an «ask again» line (or `null`) for every turn. No `b1` variants:
B1 reads the A2 line. No glossed past chunk was needed.

```
$ venv/bin/python scripts/season_check.py            # proposal applied
t1: ok … t8: ok
epilogue: ok                                          # parse, cross-references, every ending × path × band
                                                      # reaches every day, world-cast addressees, bible fidelity
$ venv/bin/python scripts/season_levels.py --file epilogue --todo --strict
  epilogue a1:  95.4% of 607
  epilogue b2:  98.2% of 779
  epilogue c1:  97.8% of 850
still to write: (none)
0 problems
```

The whole season (`season_levels.py --strict --todo`) stays at 0 problems; t1–t8 coverage is unchanged.
`app/data/season/s1/lexicon.json` (WP-131's derived season lexicon) is regenerated in the patch
(`scripts/build_season_lexicon.py`), so `test_the_season_lexicon_file_is_current` holds.

Simplified at A1 (the plot holds): Gus's «Règle numéro un» becomes «Non, non ! La plaque reste comme
ça.»; «le premier matin» becomes «un matin»; «au troisième» becomes «en haut» (ordinals are B1.2);
Marchand's letter is told in the present («Le dimanche, Odile passe par la rue de Lancry…»).

## 5. Doubts for the owner

1. **A week of six learner days.** The engine's authored pages run over two days (Day A/Day B), so
   the week is three pages over the story dates 9–15 January. A seventh day would need a one-day
   page format.
2. **New facts about Odile and the cast** (none answers who L. is):
   - Marchand's letter: on Sundays Odile always walked by the rue de Lancry (bible §2 has the Sundays
     and the 46 bus, not the route).
   - Gus's mother «dit : rue de Lancry» (bible 08's note: season 2 can tie Gus's family to Odile).
   - The dealer sold the painting «à un vieux monsieur» who looked at its back «longtemps».
   - Mme Diallo comes out of the green door on the rue de Lancry; a third-floor door covered in paint.
   - Marin's father calls: he is coming to Paris (bible §10 lists it as a season 2 door).
3. **Lila is never in Paris**: she writes (SMS). Her grades («Sept sur vingt», «Dix-huit sur vingt»)
   are her running gag.
4. **The return ticket** is answered in E3 B. «Je reste» cancels it; the other answers leave it.
5. **Without approval** the committed code still ends the season honestly with the archive day;
   approving this text replaces that day with the week.

## 6. How it was proved

With both patches applied in the WP-132B worktree (then reverted):

* `tests/test_wp132b_epilogue.py`: 30 passed — for each ending × A1, B1, C1: jump to T8 A, play
  T8 A/B and the six epilogue days through the journey (no model call on any of them, each ending's
  own variant, lines at the learner's level, A1 lines all translated), then the continuation: the
  director is told the ending and the last page, `user.stays` and `user.return_ticket` carried,
  s1's world, no generic scene, no old season. Without the epilogue (forced): T8 → the archive day →
  the continuation, per ending. Provider off after the epilogue → re-read of E3 B; after the archive
  day → re-read of T8 B; a broken epilogue page → re-read of the previous page, the epilogue resumes.
* Season suites with both patches: `test_season_one.py` (epilogue-aware counts, in the hooks patch),
  `test_wp124a_season_reprise.py`, `test_season_levels.py`, `test_wp131_words_and_quotas.py`,
  `test_learner_walk.py` — all green.
* Full backend suite with both patches: 6,431 passed, 17 failed — the 10 baseline failures
  (`test_wp69_schema_guard` ×5, `test_revue_relecture`, `test_wp96_story_archive` ×2,
  `test_wp74_honest_data`, `test_wp76_latency`), the stale season lexicon (×2, since regenerated in
  the patch, 33/33 pass) and five order-dependent tests outside the season
  (`test_long_horizon_evidence::test_two_lives_diverge`, `test_wp78_practice_day` ×2,
  `test_wp91_voices` ×1, `test_wp131 …a1_numbers…`) that pass when run alone.
* Life walk (hooks + proposal), a1-de-fresh, b1-en, c1-de average: identical to the Wave 2 records
  within noise (a 30-day life never reaches day 58).

---

## Appendix · the full text (A2/B1, as in the bible chapter)

The complete page text with every turn, reply and owner note is
`docs/story/season-1/12-la-semaine-dapres.md` in the proposal patch; the level variants are in
`app/data/season/s1/levels_epilogue.json`.
