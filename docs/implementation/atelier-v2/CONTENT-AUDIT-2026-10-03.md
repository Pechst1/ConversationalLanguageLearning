# Content audit 2026-10-03 — grammar, vocabulary, story: A1 → C1

**Question (owner):** is the content comprehensive enough to carry a learner from the first day to
the end? Do we have all needed words and grammar concepts, and does the story engine carry the
journey? **Scope set by the owner on the same day:** grammar and vocabulary cover everything up to
and **including C1**; the season's difficulty adapts to the learner's CEFR level, never a fixed A2.

Method: three read-only audits (grammar pipeline, vocabulary pipeline, season journey) plus counts
over the data files and spot-checks of every headline claim against the code. No code was changed.

**Verdict.** The *inventories* are good for A1–B1 (grammar to B2). The *pipelines* that are meant to
feed those inventories to a learner are not connected. In production today a new learner gets
the 54-concept v1 grammar catalogue, has no planned source of new words, and does not get season 1.
The level gate requires 80 % of each sub-band's word list, but nothing delivers that list. Measured
against the C1 target, the gaps are:

- grammar: about 40 C1 units plus 7 missing A1–B2 topics;
- vocabulary: about 4–5k lemmas plus 1.5–2k multiword expressions;
- story: no level tiers below A2 or above B1;
- story content: runs out after day 59.

---

## 1. The journey as it runs today (production defaults)

| Phase | What the learner gets | Where it breaks |
|---|---|---|
| Sign-up | Placement probes up to B2.1 (`placement.py:62`); the level is self-declared until 40 attempts | No C1 probes. B2.2/C1 learners are capped. |
| Day 1 | `first_day_v1` → generated serial (v2 world → S2/S3 → interlude → reprise) | Season 1 is **off**: `ATELIER_SEASON_SCRIPT=""` (`config.py:502`), unset in `render.yaml` and the prod compose file |
| Grammar | **v1 catalogue, 54 concepts** (`ATELIER_GRAMMAR_CATALOG_VERSION="v1"`, `config.py:768`); 2 new units a week on Régulier (`concept_life.py:36`) | v2 (153 units) has never been seeded and every unit is `draft`. v1's 6 C1 concepts are unreachable: the scale clamps at B2.2 (`cefr_progress.py:45,114`). |
| Words | The drill introduces only `is_anki_card` rows (`progress.py:592`). The story's LLM picks 3–5 lexicon words per scene. | The 2,682-lemma core lexicon is **never loaded** into `vocabulary_words`. A learner without an Anki deck gets no planned new words. |
| Level-up | Each sub-band épreuve needs 85 % of the band's units held **and** 80 % of the band's words known on a card (`level_coverage.py`) | Nothing introduces the word list, so the word gate is reached only by chance. At about 4 words a day, B1.1 (435 of 543 words) is roughly 2 years away. |
| Comprehension guard | `known_word_set` = FSRS-nailed words ∪ **the whole core list up to the estimated level** (`lexical_coverage.py:470-490`) | A day-one A1 learner is assumed to know all 804 A1 lemmas, so the 95 % guard never protects a true beginner. The guard is also observe-only (`COVERAGE_ENFORCED=False`, `living_story.py:136`). |

### With `ATELIER_SEASON_SCRIPT=s1` (dev/walk only)

| Days | Segment | Notes |
|---|---|---|
| 1–2 | T1 | Replaces `first_day_v1` |
| 3–57 | T2…T7 with gaps g1…g7 | 16 tentpole days in total (authored, no model call), 43 gap days (generated from a brief). Weekend flex is ±1 day per gap. |
| 58–59 | T8 | Ending: garder / partager / laisser partir |
| **60+** | — | **Nothing authored.** The director writes unbriefed days in the s1 world, which has no arcs, so the finale comes only after 40 chapters (`SEASON_MAX_CHAPTERS`). Rollover then loads the old Berlin `world_bible_paris_s2.json`, which contradicts T5/T8 (Lila's Berlin story is already resolved). |

Only lives **not yet begun** can join (`season/runtime.py:94`). Every existing life stays on the old
engine for good.

**Where the season leaves a learner.** On Régulier the season covers about 17 new grammar units and
590 words at most. A true beginner ends it at roughly **A1.2**, yet T1 is written at A2.

**The scale problem.** Reaching C1 takes roughly 800–1,000 guided hours (common French
guided-learning estimates; treat them as a planning order of magnitude). At 20–30 min a day that is
**4–7 years** of daily story. One authored season is about 15–20 hours. Authoring does not scale
to C1; only level-parametrised *generated* seasons, validated offline against the bands, can carry
the whole journey.

---

## 2. Grammar

### Inventory: `templates/french_core_grammar_v2.tsv`, 153 units

| Band | Units | Detector | X-ray | In a can-do | Forge item bank | Authored rule card |
|---|---|---|---|---|---|---|
| A1 | 34 | 34 | 34 | 33 | **34** | 0 (v2 ids) |
| A2 | 34 | 34 | 34 | 27 | **34** | 0 |
| B1 | 40 | 40 | 40 | 30 | **0** | 0 |
| B2 | 45 | 45 | 45 | 31 | **0** | 0 |
| C1 | **0** | — | — | — | — | — |

All 153 are `review_status=draft`. 146 detectors are regex. The 7 `llm:` detectors are **never
executed**: no code path runs them (`grammar_units.py:19-20,339`). They are A1 adjective agreement,
A2 imparfait vs passé composé, B1 narration, and B2 indicative/subjunctive, si mixte,
nominalisation and verb meaning by preposition.

### Defects

- **P0 — v2 is not live.** It needs the WP-L2 pre-flip list: human review of the 153 units, v2
  séance challenges (`seance_curriculum.py:19` is v1-only), and the "20 generated sets pass all three
  gates" sample, which has no record. The errata remap is done.
- **P0 — B1/B2 practice is degraded under v2.** There is no item bank for 85 units, and no
  pregenerated pool above A1. The deterministic fallback serves wrong sentences for 39 of the
  85 B-units:
  - 27 get the placeholder «Je pratique cette règle dans une phrase claire.» (`atelier.py:3531`);
  - 12 get «Il faut que tu sois prêt.» three times, including `B22_APRES_QUE`, which teaches the
    *indicative*.
- **P1 — rule cards.** The 24 cards are keyed to v1 ids and `rule_card_for` (`rule_cards.py:32`) does
  an exact lookup without the v1→v2 map. Under v2 the Cahier → Règles and concept payloads show
  the legacy English panel for **all 153** units. The journey's built card is fine.
- **P1 — ordering ignores sub-band.** `is_foundation DESC, difficulty_order` (`atelier.py:2378`)
  pushes A1.1 `IL_Y_A`/`FAIRE_PRENDRE` behind 12 A1.2 units, and A2.1 `PASSE_RECENT`/`EN_TRAIN_DE`
  behind 14 A2.2 units.
- **P1 — detector quality.** 15 regex detectors miss their own anchor or x-ray sentence (e.g.
  `NUMBERS` misses «J'ai quarante-deux ans»; `PASSIVE_TENSES` misses «sera livré»). False negatives:
  - «Nous irons» (futur simple);
  - «que nous parlions» (subjonctif);
  - «Le gâteau est mangé» (passive);
  - «Je voyagerais si j'avais…» (si clause);
  - «Il est huit heures» (time).
  
  False positives: «Il est parti» matches c'est/il est. Generic detectors fire everywhere: `LE_LA`
  on 269 of 612 catalogue sentences.
- **P2** — `recognition_pair` is always None for B levels (it needs bank units); 32 units appear in
  no can-do; tentpole can-dos are never credited (see §4).

### Missing topics, A1–B2 (each checked against the catalogue first)

1. Noun plurals as their own unit (-al → -aux, -eau → -eaux, -s/-x/-z)
2. Spelling-change verbs: -cer, -ger, -e_er, -é_er, -eler/-eter, -yer
3. *Savoir* vs *connaître*
4. *Quel* exclamatif («Quelle belle vue !»)
5. Irregular imperatives: *sois, aie, sache, veuillez*
6. *On* = *nous* as subject
7. *Si on* + imparfait as a suggestion

### C1 band to add (C1.1 / C1.2, about 35–45 units, matching B2's density)

Topics are grouped by kind.

**Tenses and moods**
- passé antérieur
- subjonctif imparfait and plus-que-parfait (recognition)
- full concordance des temps, indicative and subjunctive
- passé surcomposé (optional)

**Participle clauses and concession**
- absolute participle clauses («Le repas terminé…», «une fois arrivé»)
- concessives: *avoir beau*, *quelque… que*, *si/aussi… que*, *tout… que*, *où que / qui que*,
  *quand bien même*
- sentence-initial *Que* + subjonctif («Qu'il soit venu m'étonne»)

**Constructions**
- literary lone *ne* (*je ne saurais*, *n'ose*, *ne cesse*)
- impersonal constructions: *il s'agit de, il convient de, il reste/manque*
- perception verbs + infinitive
- ellipsis and nominal sentences

**Discourse and register**
- anaphora and cohesion: *ce dernier, celui-ci, ledit*
- formal connectors: *pour autant, quitte à, en ce sens que*
- register shift (familier ↔ soutenu) as taught units

The catalogue already covers stylistic inversion, ne explétif, dislocation, nominalisation and
argument connectors at B2. C1 extends them; it does not re-teach them.

### Code that caps the scale at B2.2 and must admit C1.1/C1.2

| Place | What caps it |
|---|---|
| `cefr_progress.py:45` | `CEFR_LEVELS` |
| `cefr_progress.py:52-60` | `PERFORMANCE_GATES` |
| `cefr_progress.py:114` | C1 clamp |
| `level_coverage.py:47` | `SUB_BANDS` |
| `grammar_catalog.py:54` | `SUB_BANDS` |
| `level_forecast.py:44,468` | reads the sub-band list |
| `level_checkpoint.py:81,237` | reads the sub-band list |
| `placement.py:62` | `PLACEMENT_BANDS` |
| `schemas/user.py:375` | target-level regex |
| `fr_core_can_dos_v2.json` | 8 sub-bands only |
| `tests/test_wp_l2_syllabus.py:465` | pins exactly 6 lexicon sub-bands |
| `web-frontend/pages/settings.tsx:181` | `cefrSublevels` |

Already C1-aware: `atelier.py:2173`, `daily_journey.py:133`, `intake.py:120`, `lexical_coverage.py`,
`grammar.tsx:87`, `language-rule.ts:21`.

---

## 3. Vocabulary

### Inventory: `app/data/lexical/fr_core_lexicon.json`, 2,682 lemmas

| Band | Lemmas | Realistic receptive target (lemmas) | Gap |
|---|---|---|---|
| A1 | 804 (≈100 of them compound numerals) | ~700 | ok |
| A2 | 794 | cumulative ~1,500 | ok |
| B1 | 1,084 | cumulative ~2,500–3,000 | roughly ok |
| B2 | **0** | cumulative ~4,000–5,000 | **~1.5–2.5k** |
| C1 | **0** | cumulative ~6,000–8,000 | **~3.5–5.5k** |
| Multiword expressions | **0** (no spaced lemma; 13 atomic items) | ~1,500–2,000 for B2/C1 | **all** |

The targets are order-of-magnitude figures from the vocabulary-size literature (Milton & Alexiou;
Nation) and should be verified before they are quoted. A1–B1 topic sets are complete in a 381-item
probe: numbers, days, months, seasons, colours, family, weather, professions, transport, connectors.

### Defects

- **P0 — no planned introduction of the core list.** The lexicon is never loaded into
  `vocabulary_words`; the only seed is the 50-word sample CSV. The drill admits only `is_anki_card`
  rows, and `include_shared_phrases` is never True. «Mots à placer» (5 core lemmas per generated
  scene, in sub-band/rank order, `living_story.py:6468`) is director-only: those words create no
  card and get no gloss. The story's scene lexicon is the LLM's free choice.
- **P0 — beginners are assumed to know A1** (`known_word_set`, §1).
- **P1 — cross-learner leak.** `VocabularyWord` has no owner column. One learner's imported Anki rows
  become every learner's "new" words (`progress.py:586-609`).
- **P1 — no multiword expressions.** 36 of 38 essential chunks are missing (il y a, il faut, avoir
  besoin/envie/faim/peur, s'il vous plaît, bien sûr, tout de suite, à cause de, …). The hyphenated
  pseudo-phrases `en-effet`, `rendre-visite`, `point-de-vue` and `par-conséquent` can never match
  tokenized text. *d'accord* and *d'ailleurs* split into de + accord/ailleurs. The coverage guard
  counts opaque idioms as known when their parts are known.
- **P1 — taught-but-unpractised story words are never scheduled.** A scene word enters the Lexique
  only once practised (`kept_words.py:446`).
- **P1 — no B2/C1 words.** `words_met` is vacuously True for an empty band (`level_coverage.py:277`),
  so B2 is gated by grammar alone.
- **P2:**
  - no glosses in the lexicon;
  - about 100 numerals inflate A1;
  - mis-banding: *malgré* is at A1; *d'accord, peur, doigt, sucre* are at A2;
  - missing headwords: *s'asseoir, seconde*;
  - story words never get `example_sentence`, so the cloze rung is unreachable;
  - the schema allows 100 new words a day while the doc says 50;
  - `VOCAB_STORY_PILOT_ENABLED` is off.

### Sources for B2/C1 (none vendored; verify every licence before use)

| Source | What it gives | Licence (to verify) |
|---|---|---|
| Lexique 3.83 | Frequencies, POS, gender | Believed CC BY-SA 4.0; ShareAlike affects redistribution of the derived list |
| FLELex | CEFR-graded A1–C2 lemmas | Believed non-commercial; likely unusable for a product, but useful as a reference to check banding against |
| Wiktextract / Kaikki | fr→en/de glosses | CC BY-SA + GFDL |
| OpenSubtitles frequency lists | Spoken-register frequency | Believed CC BY-SA |

---

## 4. Story engine

### Level is fixed

- `Say` / `Wording` (`season/format.py:55-75`) carry `a2` plus an optional `b1`; the model forbids
  extra fields.
- An A1 learner reads the A2 line with a native translation.
- B1, B2 and C1 learners get `b1` where one exists, which is only 23–50 % of lines per tentpole;
  everywhere else they read A2.
- No `a1`, `b2` or `c1` line exists. The season `question` exists only as `a2`.
- Measured coverage: A1 learners reading the A2 text have **86–92 %** known-word coverage per
  tentpole (target ≥ 95 %). T5, T6 and T8 contain 47–88-word letters. Difficulty does not ramp from
  T1 to T8.
- Learner turns are level-blind: one `suggested_response` for everyone, and the same turn counts for
  every band.
- Gap days *do* get level, lexicon band, «mots à placer», can-dos and the grammar plan. But the brief
  has no level fields (4–6 panels / 2–3 exchanges at every band), the critic is told «Judge the
  story, not the French level» (`director.py:81`), and the coverage guard only observes.

### Story and curriculum disconnect

- **P1 — tentpole days ignore the grammar.** The Règle step introduces a unit on tentpole days
  (`daily_journey.py:3216`). But `generate_scene` returns the authored page before the grammar plan,
  story words or can-do menu are built (`living_story.py:6905`). So on 16 of 59 days the scene never
  uses the unit just taught.
- **P1 — tentpole can-dos are never credited.** Tentpoles have `can_do_id=None`. The season files
  declare no FR2 units.

### Other story defects

- **P1 — 7 solves still defaulted (WP-112):** enquête in T2A and T4A (T4A's only learner turn),
  déchiffrer ×4 (T5A, T6A), and the S-9 balloon (T1B). The comment at `page.py:360` still calls
  convaincre unposed, which is stale.
- **P1 — Courrier is not season-aware.** `CAST_ROLES_FR` calls Marchand «votre propriétaire»;
  Romy can write before she appears; there is no spoiler guard for Berlin or the Polaroid.
- **P1 — Revue runs dry.** All 12 evergreens have 2026 date windows, and only one hand-authored week
  exists (2026-W40).
- **P2** — the S-12 neutral wordings for T7 and g6 are missing.

### Level-adaptive design (fits the current code)

The bible ⊆ file fidelity check (`fidelity.missing_lines`) does **not** block extra variants; only
the schema does.

- **Data.** Add optional `a1`, `b1` (fill the gaps), `b2` and `c1` fields to `Say` / `Wording`,
  including convaincre objections and déchiffrer documents. The bible's A2 line stays canonical.
- **Generation (offline, not at request time).** Use a model, constrained to the band's lemma set
  plus the allowed and avoided grammar units for that band.
- **Validator (offline), with four checks:**
  - ≥ 95 % lexical coverage against the band;
  - no grammar detector above the band;
  - a meaning-equivalence judge against the canonical line;
  - `source_hash`, so a variant goes stale when its bible line changes.
- **Selection.** `Say.text(band)` picks the nearest variant at or below the learner's band. A native
  translation stays available as a toggle, not as a crutch for A1.
- **Learner turns.** Per-band `examples` / `lands_examples` (A1: at most 6 words). At A1, reply
  examples become tap cards via `card_choice`. Long letters get an «easy read» tier plus glosses.
  `min_turns` stays unchanged.
- **Gap days.**
  - per-band shape in the brief (A1: 3–4 panels, 1–2 exchanges; C1: denser, register shifts);
  - band variants of the brief's French moments;
  - a level-aware critic;
  - enforce the coverage guard once `known_word_set` is honest.

---

## 5. Proposed work, in order

**Phase 0 — make the journey that exists actually work** (blocks every learner)

| # | Package | Fixes |
|---|---|---|
| C-1 | **Word supply.** Load the core lexicon into `vocabulary_words` with glosses and POS/gender. Add a sequenced new-word feed (sub-band → rank, numerals de-weighted). Let the drill admit core words. «Mots à placer» become cards. Schedule taught-but-unpractised story words. Make `known_word_set` honest: nailed words plus a placement-based core floor, not the whole band. | §1 level gate, §3 P0s |
| C-2 | **Anki ownership.** Add an owner column and scope the new-word query to it. | §3 leak |
| C-3 | **Grammar v2 flip.** Owner/human review of the 153 units. Order by sub-band. Map v1 cards through `v1_to_v2` and author the rest (A1–A2 first). Fix the 39 bad B fallbacks. Repair the 15 detectors and the false positives/negatives. Implement the `llm:` detector path or replace those 7 with regex. Pregenerate and validate B1/B2 pools (or extend the Forge bank). | §2 |
| C-4 | **Season reachability.** Decide on enabling s1 in prod and on a join policy for begun lives. Write a post-T8 continuation in the new season format and retire the Berlin S2 bible. | §1 |
| C-5 | **Tentpole ↔ grammar.** Either introduce no new unit on tentpole days, or annotate tentpoles with the FR2 units they exercise and let Règle pick from those. Give tentpoles can-do ids. | §4 |

**Phase 1 — A1 → C1 scope**

| # | Package |
|---|---|
| C-6 | Scale to C1.2 everywhere (the §2 table), including placement probes, forecast and can-dos for C1.1/C1.2. |
| C-7 | Grammar: the 7 missing A1–B2 units plus a C1 band of about 35–45 units (detectors, x-ray, rule cards, can-dos). |
| C-8 | Vocabulary: B2/C1 bands from a licence-cleared frequency source (about +4–5k lemmas), glosses, an MWE inventory (about 1.5–2k, with tokenizer support for spaced and elided chunks), a re-band pass, and an un-pinned sub-band test. |

**Phase 2 — the adaptive story**

| # | Package |
|---|---|
| C-9 | Level variants for season 1 (the §4 design), level-aware gap briefs and critic, A1 tap-card replies. |
| C-10 | Remaining defaulted solves (WP-112), a season-aware Courrier, Revue evergreens beyond 2026, the S-12 neutral lines. |
| C-11 | **A generated-season pipeline parametrised by level.** This is the only way to carry 4–7 years of daily story to C1. The s1 format (tentpole + gap + flags + validator) is the template; the offline validators from C-9 become its gate. |

### Owner decisions needed

1. **Vocabulary licence.** Is CC BY-SA acceptable (attribution plus ShareAlike on the derived word
   list)? This decides between Lexique/Wiktextract and building our own list.
2. **Grammar review.** Who reviews the 153 v2 units plus the new C1 units before the flip?
3. **Season 1 rollout.** Turn it on in prod now (A2 text, A1 with translations) or after the C-9
   variants exist? And may begun lives join at a season boundary?
4. **Tentpole days.** No new grammar on those days, or authored unit annotations?
