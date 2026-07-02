# Coverage Map, Vocabulary, Verbs/Conjugation & Missions — Final Design Plan

Handoff spec for the implementation agent. Self-contained: assumes no memory of prior
chat. Build top-to-bottom; the sequencing section gives the order.

**One-paragraph summary.** Give the learner a structured **Coverage Map** — an atlas of
"everything you need for CEFR level X" across three axes (noun *categories*, *verbs &
conjugation*, *grammar patterns*) with visible `nailed / total` progress, so they feel
*on track and not missing anything*. **Vocabulary** is the dedicated, fun SRS environment
that fills the noun/verb-lexicon parts of the map. **Verbs/conjugation** is the bridge:
verb *meaning* lives in vocab, conjugation *patterns* are the existing grammar concepts,
and *irregular forms* get a dedicated conjugation drill — all unified through the SRS so
the map rolls them up. **Missions** are lean, standalone real-world tasks built from the
words/verbs the learner *just nailed* (learn → use loop). The **Feuilleton/serial is not
touched** by any of this.

---

## 0. Data reality (read first — it sets the build order)

`vocabulary_words` holds **5,000 unique French words** (× 2 directions = 10,000 Anki
cards, deck `Französisch 5000`). Content is rich (translations + example sentences), but
the **structure the map needs does not exist**:

| Column | State today | Needed for |
|---|---|---|
| `part_of_speech` | empty (2 / 10,023) | noun vs verb vs adj tracks |
| `frequency_rank` | empty | level ordering |
| `difficulty_level` | all `1` | CEFR band |
| `topic_tags` | only on 23 mission phrases | noun categories |
| `deck_name` / `id` order | **not** frequency-sorted | — |

Tools already available: `spacy` + `fr_core_news_sm` (POS + lemma), the unified SRS
(`ItemType.VOCAB / GRAMMAR / ERROR`), FSRS scheduling, and 25 grammar concepts that
already teach conjugation (11 Tenses + 9 Verbs + 5 Conditionals).

→ **The foundation work package is a one-time enrichment pass (WP‑ENRICH).** Nothing else
can be built correctly until each word has `pos + category + cefr_band + frequency_rank`,
and verbs have conjugation data.

---

## 1. The spine — the Coverage Map (3 axes)

The learner always sees `nailed / total` rollups. "Nailed" = an item crossed an FSRS
mastery threshold (see Decisions), so progress is earned.

**Axis A — Noun/word categories.** ~16 thematic buckets (food, time, people,
transport, infrastructure, body, home, work, nature, emotions…), each `nailed / total`,
CEFR-banded. This is the "fruits, time, cars…" feeling.

**Axis B — Verbs & conjugation** (the new requirement; see §3). Three linked sub-tracks:
- *Verb lexicon*: do you know the verb's meaning → `X / 150 B1 verbs`.
- *Conjugation patterns*: the existing grammar concepts (present, passé composé,
  imparfait, futur, conditionnel, subjonctif) → mastered patterns.
- *Irregular forms*: can you actually produce the forms of high-value irregulars
  (`être, avoir, aller, faire, venir…`) → `X / 40 irregulars conjugatable`.

**Axis C — Grammar patterns.** The non-verb Atelier concepts (articles, negation,
pronouns, agreement, relative clauses…) already tracked by `ItemType.GRAMMAR`. Surface
them on the map for completeness.

Overall CEFR bar = union of A+B+C targets for the band ("B1 · 41%, 612 / 1500 mastered").

---

## WP‑ENRICH — enrich the 5,000 words (foundation)

A re-runnable, idempotent batch script (e.g. `scripts/enrich_vocabulary.py`) that fills
the existing columns. Process each unique French lemma once; write to both direction rows.

**Per-word output → columns**
- `part_of_speech` — from `spacy fr_core_news_sm` (lemma + POS); fall back to LLM for
  ambiguous tokens.
- `topic_tags` — one **primary category** from the fixed taxonomy below (+ optional
  secondary). Use an LLM classify call, batched (~50 words/call), schema-constrained to
  the taxonomy enum. Cache by lemma.
- `cefr_band` — A1–C1. Prefer joining an external French frequency list
  (Lexique3 / OpenSubtitles freq) on `normalized_word` → frequency → band cutoffs
  (e.g. top 500≈A1, –1000≈A2, –2000≈B1, –3500≈B2, –5000≈C1). LLM estimate as fallback.
  Store the ordinal in `difficulty_level` (1..5) **or** add a `cefr_level` column.
- `frequency_rank` — backfill from the frequency-list join; else rank within band by LLM
  confidence. (Needed so decks/selection are common-words-first, fixing the alphabetical bug.)

**Fixed noun taxonomy (v1, ~16):** people & relationships · body & health · food & drink ·
home & objects · clothing · time & calendar · transport & travel · places &
infrastructure · nature & weather · work & money · education · technology & media ·
society & politics · emotions & abstract · arts & leisure · communication. (Verbs, adjectives,
adverbs, function words get their own non-thematic tracks.)

**Acceptance:** ≥95% of the 5,000 words have non-null `pos`, `category`, `cefr_band`,
`frequency_rank`; script is idempotent and logs a coverage report.

---

## WP‑CONJ — verbs & conjugation (the bridge)

**Identify verbs.** From WP‑ENRICH `pos == verb`. Tag verb group (`-er / -ir / -re`),
regularity (regular / irregular), and auxiliary (`avoir / être`). Maintain a curated set
of ~40 essential irregulars per CEFR band.

**Generate conjugation tables deterministically.** Do NOT rely on the LLM for forms (it
hallucinates). Add `mlconjug3` (pure-Python French conjugator) and precompute, per verb,
the forms for the core tenses: présent, passé composé, imparfait, futur simple,
conditionnel présent, subjonctif présent (+ impératif). Store as a `verb_conjugations`
table (`lemma, tense, person, form, auxiliary, is_irregular, cefr_band`). Re-runnable.

**Conjugation as a first-class SRS item.** Add `ItemType.CONJUGATION` to `unified_srs.py`
and a `UserConjugationProgress` (or reuse the generic progress with a composite key
`verb:tense`). One SRS item = (verb × tense) for irregulars; **regular verbs auto-credit
from grammar-pattern mastery** (don't drill every regular form — that's what the pattern
concept teaches).

**Conjugation drill environment.** A focused runner (sibling of the vocab runner):
prompt = `venir · imparfait · tu →` , learner types `venais`, reveal shows the full table
with the target highlighted; rate Again/Hard/Good/Easy → FSRS. Visual, geometric-mark
feedback, dignified.

**Interweaving (the point):**
- *Vocab* teaches the verb's **meaning** (lexicon track).
- *Grammar/Atelier* (existing transform/tense exercises) drills **patterns in context** —
  already built; just credit conjugation coverage when a tense concept is nailed.
- *Conjugation drill* drills **irregular forms** explicitly.
- *Missions* force the learner to **produce** recently-nailed verbs in correct conjugated
  form in a real message — the strongest reinforcement.
- The *Coverage Map* rolls all three up so a verb shows as fully mastered only when the
  learner knows it, can conjugate it (pattern or irregular), and has used it.

---

## WP‑MAP — Coverage Map model, API, surface

- **Rollup service**: per (user × category) and (user × track × cefr_band) →
  `nailed / total`, reading `UserVocabularyProgress`, grammar progress, and
  `UserConjugationProgress`. Targets come from WP‑ENRICH/WP‑CONJ.
- **API**: `GET /vocabulary/coverage` → `{ cefr_bar, categories[], verb_tracks[],
  grammar_tracks[], next_best_set }`.
- **Surface**: the "mastery atlas" home — category tiles with progress rings, a "Verbs &
  conjugation" block (lexicon bar + tense pattern chips + irregulars bar), a CEFR level
  bar, and one clear "continue: <next best set>" CTA. This is the screen that creates the
  *on-track* feeling. (Mockup delivered in chat.)

---

## Block B — Vocabulary environment (fills axes A & B-lexicon)

Engine exists, unused as a first-class surface: FSRS in `unified_srs.py`,
`UserVocabularyProgress`, `pages/vocabulary/review.tsx`.

- **WP‑V1 — Decks = categories/tracks** from the enrichment, common-words-first by
  `frequency_rank`. Replace `_starter_vocabulary_items` / `select_atelier_vocabulary` in
  `app/services/atelier.py` (kills the "abaisser/abandon" alphabetical bug).
- **WP‑V2 — Visual SRS card runner**: rebuild `pages/vocabulary/review.tsx` on the FSRS
  rate flow — front/back flip, illustration/geometric mark per card, progress ring,
  session summary. No streak-loss; brand-consistent.
- **WP‑V3 — Card variety by mastery**: recognition → production (type) → audio (existing
  TTS/Whisper) → cloze-in-context, chosen by the word's FSRS state.
- **WP‑V4 — Nailed → coverage**: a successful review crossing the threshold increments
  the Coverage Map live.

---

## Block A — Missions (standalone, vocab/verb-fed)

Lean one-task screen (mockup delivered): frame (who / where / why, ≤2 lines) → ask
(1 line) → input → send. **Not connected to the serial.** CEFR-scaled via
`cefr_generation_profile`.

The hook: **missions are generated from the learner's recently-nailed words and verbs.**
"You just nailed 6 market nouns + the verb *vouloir* → write the *primeur* a real message
using them." Grading checks correctness **and** that the target words/verb forms were used.

- **WP‑M1 — Slim payload**: `{ frame, ask, input_kind, cefr_band, used_word_ids[],
  used_verb_lemmas[] }`. Stakes become one hidden difficulty knob, not learner copy.
- **WP‑M2 — Redesign `pages/missions.tsx`** to one focused screen (~70% smaller); fold
  objectives/stakes into at most one quiet chip.
- **WP‑M3 — Vocab/verb-fed generation** in `app/services/missions.py`: pull N recently-
  nailed items (+ a few due ones) from the active category; require them in the task;
  reward credits reinforcement back into the SRS.

---

## Data-model changes (summary for migrations)
- `vocabulary_words`: populate `part_of_speech`, `topic_tags`, `frequency_rank`; set CEFR
  via `difficulty_level` ordinal **or** new `cefr_level` column. (WP‑ENRICH)
- New `verb_conjugations` table (lemma, tense, person, form, auxiliary, is_irregular,
  cefr_band). (WP‑CONJ)
- `unified_srs.ItemType` += `CONJUGATION`; new `UserConjugationProgress` (or composite-key
  reuse). (WP‑CONJ)
- Optional `vocab_categories` reference table if you want editable taxonomy/targets rather
  than a code constant. (WP‑MAP)

## Suggested sequencing
1. **WP‑ENRICH** — structure the 5,000 words (unblocks everything).
2. **WP‑CONJ** — conjugation tables + `ItemType.CONJUGATION` + drill.
3. **WP‑MAP** — coverage rollup + atlas surface (the "on-track" payoff).
4. **Block B** — vocab decks + visual runner; nailed feeds the map.
5. **Block A** — lean missions fed by recently-nailed words/verbs.

## Concrete anchors in the repo
- Vocab model/columns: `app/db/models/vocabulary.py`.
- SRS engine + item types: `app/services/unified_srs.py` (`ItemType`, FSRS),
  `UserVocabularyProgress`, `app/api/v1/endpoints/vocabulary.py`.
- Grammar/conjugation concepts: `GrammarConcept` (categories Tenses/Verbs/Conditionals),
  Atelier transform exercises already drill them.
- CEFR scaling: `cefr_generation_profile` / `CEFR_RAMP` in `serial_arc_planner.py`.
- Surfaces to rebuild: `pages/missions.tsx`, `pages/vocabulary.tsx`,
  `pages/vocabulary/review.tsx`.
- Random injector to replace: `select_atelier_vocabulary` / `_starter_vocabulary_items`
  in `app/services/atelier.py`.
- Design language: ink-block shadow + geometric marks (`components/ui/Seal.tsx`, `globals.css`).
- POS/lemma tool: `spacy` + `fr_core_news_sm` (installed). Conjugation: add `mlconjug3`.

## Open decisions (confirm before build)
1. **CEFR assignment**: join an external frequency list (rigorous, adds a data step) vs.
   LLM estimate per word (faster, no dependency)?
2. **"Nailed" threshold**: which FSRS signal counts as mastered for coverage (e.g.
   retrievability ≥ 0.9 after ≥ 2 good reviews)? Same cutoff for vocab, conjugation, grammar?
3. **Conjugation depth**: which tenses are in-scope for v1 (suggest présent, passé composé,
   imparfait, futur, conditionnel; subjonctif at B2)? Drill irregulars only, or also
   regular-verb spot-checks?
4. **Taxonomy granularity**: ~16 broad categories vs. ~30 finer for a richer atlas.
5. **Card directions**: teach both fr→de and de→fr, or one direction first?
6. **Atelier target-word injection**: remove entirely, or keep as *due-word* reinforcement
   (never random)?
