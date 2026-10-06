# Content program 2026-10-03 — A1 → C1 grammar, vocabulary, adaptive season

Follows [CONTENT-AUDIT-2026-10-03.md](CONTENT-AUDIT-2026-10-03.md). Owner direction (2026-10-03):

- **Words:** use the Anki «Französisch 5000» frequency export
  (`Anki_cards___2025-11-01T13-09-36.csv`), or build our own list if it is not useful.
- **Grammar:** Claude reviews every unit. The explanations must be really good, and the frontend
  must present them well, with highlighting.
- **Everything else:** Claude decides.

## Decisions taken (owner delegated)

| # | Question | Decision |
|---|---|---|
| D1 | Word source | The Anki export gives **rank order, lemma, POS, gender (from the article) and IPA** for 5,000 words. These are factual frequency data, and we use them. Its glosses and example sentences come from a third-party deck whose licence is unknown, so they are **not shipped**. Glosses (en/de) and examples are authored fresh. B2/C1 beyond rank 5,000 and the multiword-expression inventory are authored by us. |
| D2 | Grammar review | Every v2 unit is reviewed and rewritten where needed: rule, when to use, traps, anchors, x-ray. Each unit gets an authored **rule card v2+** (en/de/fr) with highlighting markup. The review status becomes `reviewed`. |
| D3 | Catalogue flip | Once the review lands, v2 becomes the default (`ATELIER_GRAMMAR_CATALOG_VERSION="v2"`). The existing migration path seeds it and remaps errata. |
| D4 | Scale | The CEFR scale runs **A1.1 … C1.2** everywhere. C2 stays out of scope. |
| D5 | Season 1 in production | It goes on for **new lives once the level variants (C-9) exist**. Until then it stays dev/walk only, because an A1 learner reads A2 text at 86–92 % coverage. |
| D6 | Begun lives | **Revised while implementing:** begun lives do **not** join season 1, not even at a season boundary. The old serial already has the same cast at Le Mistral, so T1 (Gus greets the learner as a stranger who has come to sell the flat) would contradict months of shared story. A begun life keeps the generated serial, which has its own finales and interludes. Joining s1 can only be an explicit, fresh start that the learner chooses: a new thread, owner UI decision, not built. |
| D7 | Tentpole days | No *new* grammar unit is introduced on a tentpole day. The Règle step becomes a **review of a unit the tentpole actually uses**. That set is computed offline by running the detectors over the tentpole text at the learner's band and stored in the season files. Tentpoles get can-do ids. |
| D8 | After the finale | s1 gets an authored epilogue week, then a generated continuation in the s1 world with a real arc. The old Berlin S2 bible is never loaded after s1. |
| D9 | `llm:` detectors | Every unit gets a regex detector, approximate where necessary and documented. No unit is left un-detected. |

### Correction to the audit (2026-10-03, while implementing)

The audit called `known_word_set` assuming the whole A1 band for a beginner a P0. On closer reading,
every caller uses it as a **level-appropriateness gate**: the scene guard, the Courrier letter
check and the cast-reply check all ask "is this text written in the learner's band?", not "does
this learner know these words?". Tightening it to the learner's sub-band rejected the authored A1
letters, which use A1.2 words, and would starve beginners of scenes.

The change was reverted. Comprehension support for beginners comes from the native translation
plus the planned word supply (E-1). The dossier already labels the "assumed core" half separately
from nailed words. With lexicon v3 the gate extends to B2/C1 automatically, because
`core_lemmas(band)` reads the bands from the data.

## Shard formats (parallel authoring; integration merges them)

### Grammar units: `app/data/grammar_review/units_<BAND>.json`

```json
{"band": "A1", "reviewed": "2026-10-03", "units": [ { <every column of templates/french_core_grammar_v2.tsv> } ]}
```

- Every column must be present, with the TSV's conventions: `|` separates list items, and
  `xray_marks` uses `span=>role=>note||…`.
- `review_status` is `"reviewed"`.
- New units use fresh `FR2_<SUBBAND>_<NAME>` ids and a `teaching_order` that slots between
  their neighbours.

### Rule cards: `app/data/rule_cards/fr2_<BAND>.json`

```json
{"version": "rule-cards-v2", "cards": { "<FR2 id>": <card> }}
```

The card is a superset of the WP-L10 schema (`web-frontend/lib/rule-card.ts`). In French strings,
`[x]` marks the rule-carrying part (drawn red) and `{x}` marks letters that are written but silent
(drawn grey).

| Field | Status | Content |
|---|---|---|
| `speaker` | optional | Cast id |
| `example` | required | `{fr, tr: {en, de}}`; `fr` carries the markup |
| `rule` | required | `{en, de, fr}`: one sentence, plain language, no jargon without an example |
| `pattern` | optional | `{kind: "rows", rows: [{shape, label, fr}]}` or `{kind: "table", verb, rows: [{p, fr}], note?}` |
| `contrast` | required | `{wrong, right}`; `right` carries the markup |
| `more` | required | `{en, de, fr}`: the fuller «why», 2–4 sentences |
| `how` | new | `{en, de, fr}`: how to build it, as numbered steps separated by `\n` |
| `examples` | new | `[{fr, tr: {en, de}}]`, 2–4 extra marked examples, everyday and varied |
| `traps` | new | `[{wrong, right, why: {en, de, fr}}]`, 1–3 of the real mistakes learners make |
| `contrast_with` | new | `[{id, note: {en, de, fr}}]`, linking to the partner units |

### Review notes: `docs/implementation/atelier-v2/grammar-review/<BAND>.md`

One line per unit: what changed and why. Flagged doubts go here as well.

### Lexicon: `app/data/lexical/fr_core_lexicon.json` → `fr-core-lexicon-v3`

- Bands A1–C1.
- Per-lemma fields gain `pos`, `gender`, `freq_rank`, `numeral`, `gloss: {en, de}`.
- A new `expressions` map holds the multiword expressions.

## Packages and status (2026-10-03, end of day)

| Package | Status | Where |
|---|---|---|
| L-1 lexicon v3 | **done** — 6,952 lemmas A1.1–C1.2 (96 numerals flagged) + 2,776 expressions | `app/data/lexical/fr_core_lexicon.json`, `scripts/build_lexicon_v3.py`, `LEXICON-V3.md` |
| L-2 glosses | **done** — en/de for every lemma and expression, authored fresh (D1) | `glosses_src.json` → builder |
| E-1 word supply | **done** — core list synced at deploy; drill introduces it in learning order from the learner's band; story-taught words first; imported decks first, then core; one card per lemma | `app/services/core_lexicon.py`, `scripts/sync_core_lexicon.py`, `docker/entrypoint.sh`, `progress.py` |
| G-A1 … G-B2 review | **done** — 161 units reviewed, 9 new (plurals, on = nous, quel exclamatif, -er spelling, savoir/connaître, si on + imparfait, de plus en plus, comme si…); every detector matches its own sentences | `app/data/grammar_review/`, `grammar-review/*.md` |
| G-C1 | **done** — 45 units C1.1/C1.2 + 14 can-dos | `units_C1.json`, `can_dos_C1.json` |
| Rule cards | **done** — 206 authored cards en/de/fr (how, examples, traps, compare-with) | `app/data/rule_cards/fr2_*.json` |
| E-2 merge + flip | **done** — `scripts/merge_grammar_review.py` → TSV (206 reviewed units); v2 is the product default (D3; the suite still pins v1); new units sorted by sub-band; B1/B2 fallback serves the unit's own sentences | `app/config.py`, `atelier.py` |
| F-1 grammar frontend | **done** — card with progressive disclosure, red/grey marks + key, x-ray component, unit page by sub-band, gallery | `RuleCard.tsx`, `XraySentence.tsx`, `pages/grammar.tsx` |
| G-FORGE | **done for A1/A2 + 4 B1 units**; engine gaps for subjonctif, plus-que-parfait tense, accent-only traps listed | `FORGE-NEW-UNITS.md` |
| S-1 scale to C1.2 | **done** | `cefr_progress`, `level_coverage`, `grammar_catalog`, `placement` (C1.1 rung), `schemas/user`, `settings.tsx` |
| T-1 tentpole grammar | **done** — no new unit on tentpole days; the forge reviews a unit the page uses; tentpoles credit a can-do | `scripts/season_units.py` → `units.json`, `daily_journey.py`, `forge_picker.py` |
| T-2 season levels | **done** — 524 lines × a1/b2/c1 + level example replies for 115 turns; validator 0 problems | `app/data/season/s1/levels_*.json`, `scripts/season_levels.py`, `SEASON-LEVELS.md` |
| T-3 after the finale | **done (engine)** — a finished scripted season goes to the interlude, then writer/reprise in its own world; never the Berlin S2 | `living_story.py`, `season/runtime.py` |
| D5 season 1 in production | **config set** — `ATELIER_SEASON_SCRIPT=s1` in `render.yaml` (new lives) | — |

### Still open

1. **La Forge engine:** subjonctif, plus-que-parfait tense, accent-sensitive traps, double pronouns/dont filters. B1.2–C1 units are served by LLM pools and the (now sound) fallback until then.
2. **An authored epilogue for s1:** the interlude/reprise is generic; a written last week would be better.
3. **Season 2 in the new format:** for a 4–7-year journey to C1, generated seasons parametrised by level (C-11).
4. **Owner review of doubts** in `grammar-review/*.md`, `SEASON-LEVELS.md` and `LEXICON-V3.md`.
5. **The suite pins v1:** move suites written against v1 concept ids to v2 ids.
6. **Not mine, but seen:** `test_wp69_schema_guard` fails on the other session's unapplied migration; `test_revue_api.py` has random UUIDs in parameter ids (breaks xdist).

## Speed package (owner, 2026-10-03: «substantially faster than Duolingo»)

Seasons are **level-agnostic**. Everyone starts at T1 after the placement and reads the same story; only the French (level variants), the grammar and the words adapt to the placement's CEFR rating.

| Lever | What changed | Where |
|---|---|---|
| 1. Skip known words | «Vérification du lexique»: 24 meaning choices per sub-band below the learner's level. A ≥ 90 % pass gives that sub-band's core words settled, known cards (the missed ones excepted), with a light check in 10–45 days. | `app/services/band_check.py`, `GET/POST /vocabulary/band-check…`, frontend (SPEED-1-FE) |
| 2. Words from reading | A word a scene taught, met in ≥ 3 different sentences on ≥ 3 different days and never kept as a card, counts as known for the level gate. | `level_coverage.read_lemmas` |
| 3. Skip known grammar | «Je connais déjà — vérifier» in the rule step runs the forge test-out in the journey; a pass holds the unit and does not use a slot of the weekly quota. | SPEED-3 |
| 4. Quotas doubled | Units/week Léger 2 · Régulier 4 · Soutenu 6 · Intensif 8 (one per day at most). Words/day 5 · 10 · 18 · 30 (the rhythm sets it; a change of rhythm updates `new_words_per_day`). The throttle still halves intake while reviews pile up. | `concept_life.py`, `vocabulary_pace.py`, `level_forecast.py`, `services/users.py` |

The forecast for a Régulier beginner to A1 drops from about 5–6 months to about 3–4 months. It is held up mainly by WP-L4's «Tenue»: a unit is held only after two correct free uses at least a week apart, plus one spaced item at least 14 days after its introduction. Placed learners skip most of the lower bands through levers 1 and 3.

## QA round after the owner's test (2026-10-03 evening)

**Done**
- QA-STORY: A1 lines get their own translations (`a1_native`); 182 A1 lines rewritten in context; an off-target reply gets an in-character ask-again (`app/data/season/s1/tasks.json`); per-turn task, hint and translation; Camille named correctly; no verdict on story replies; plain tasks.
- QA-PRACTICE: «Wer hat das gesagt?» removed; unscramble misses show the correct order; article-optional recall; plural copy; no English glosses for de learners.
- QA-FORGE: the judgement is posed as a question with buttons; no English for de/fr learners; header overlap fixed; 2,340 items read and templates fixed.

**Running when the session paused** (resume by messaging the agents, or relaunch from these briefs)
- FORGE-DE: German renderings in the item bank, so de learners get meaning cues and translation steps.
- EXERCISE-QA: inventory, feedback and answer-acceptance contracts, language-hygiene test, level fit, learner-walk harness. Writes `EXERCISE-INVENTORY.md` and `EXERCISE-QA-2026-10-03.md`.

**Test setup**
- Database `atelier_test_1003`; `.claude/launch.json` → `backend-test-1003` (port 8010) and `web-frontend` (port 3000).
- Test accounts are in the session scratchpad. Restart the backend after Python changes.
