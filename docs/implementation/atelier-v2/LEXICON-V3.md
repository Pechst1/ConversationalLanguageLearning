# fr-core-lexicon-v3 (content program L-1, 2026-10-03)

`app/data/lexical/fr_core_lexicon.json`, built by `scripts/build_lexicon_v3.py`. The build is
deterministic: running it twice gives a byte-identical file. Use `--check` to see the report
without writing the file.

## Sources

| Input | Used for |
|---|---|
| v2 lexicon (git blob `e3c68b8`, read with `git cat-file`, or `--base <file>`) | A1–B1 base: band, sub_band, order, forms, elisions, atomic lists |
| `app/data/lexical/fr_core_pos.json` (unchanged) | POS and gender of the v2 lemmas |
| `Anki_cards___2025-11-01T13-09-36.csv` («Französisch 5000», FR → DE notes) | rank 1–5000 → `freq_rank`, lemma, POS, gender from the article, `ipa` |
| `app/data/lexical/authored_b2_c1.json` | curation (re-banding, deck overrides, register, headwords, spelling) and the authored B2/C1 lemmas |
| `app/data/lexical/expressions_src.json` | the authored multiword expressions |
| `app/data/lexical/glosses_src.json` | the authored learner glosses (en, de), package L-2 |
| mlconjug3 (Verbiste templates, MIT, a declared dependency) | verb paradigms for `forms` |

**Licence note (D1).** From the deck, only factual data is read: rank order, lemma, part of
speech, gender (from le/la/un/une) and the IPA transcription. The parser never captures the
deck's German glosses or example sentences, which are third-party text of unknown licence. The
deck's ranks appear to come from a published frequency dictionary built on a formal corpus
(parliament and press), so we use them as a frequency signal only. The authored lemmas and
every expression were written for this repository and no list was copied. The `gloss` field
(package L-2, below) is authored too: nothing comes from the deck or a dictionary.

## Shape (backward-compatible)

All v2 keys are kept: `version`, `language`, `provenance` (the v2 keys plus `v3`, `deck`,
`forms_v3`, `expressions`), `bands`, `lemmas`, `forms`, `elisions`, `atomic_apostrophe` and
`atomic_hyphen`. The file adds `sub_bands` and `expressions`.

Each lemma has these fields:
`{band, sub_band, rank, pos, gender?, freq_rank, numeral, register, source, ipa?, headword?, gloss}`

- `pos` uses the vocabulary of `fr_core_pos.json`: noun, verb, adjective, adverb, function,
  number, interjection. Deck codes are mapped to it: nm/nf → noun, adj → adjective,
  v/vi/vt/vr → verb, prep/art/pro/det/conj → function, num → number, intj → interjection.
  v2 lemmas keep their curated POS. The A1.1 grammar words stay `function`.
- `gender` is m, f or mf, and is present on every noun.
- `rank` is the global list order: A1 first, C1 last. Inside a band the order is the v2 order,
  then deck rank, then authoring order. `freq_rank` is the deck rank, or null.
- `numeral` is true for the 96 compound numerals (all A1). Counts and word feeds should skip
  them.
- `register` is null, "familier" or "soutenu". `source` is "v2", "anki_rank" or "authored".
- `headword` is the dictionary form when it differs from the lemma, for example «s'asseoir»,
  «se réfugier».

Each expression has these fields:
`{band, sub_band, kind, register, lemmas, variable, gloss}`

- `kind` is one of: chunk, idiom, collocation, connector, discourse.
- The key is the canonical lowercase surface. A slot at the edge is dropped («avoir besoin de»).
  A slot inside the expression stays as « … » («avoir … ans»).
- `lemmas` are the component lemmas, resolved against this lexicon. About 200 fossil words that
  only occur inside idioms («fur», «catimini», «aloi») are deliberately not lemmas. They stay
  in `lemmas` as written.

## Glosses (content program L-2, 2026-10-03)

Every lemma (6,952) and every expression (2,776) has `gloss: {en, de}`. The source is
`app/data/lexical/glosses_src.json`; `scripts/build_lexicon_v3.py` merges it in (`apply_glosses`).
A missing gloss is a build warning, and the report counts `glossed`. The glosses were authored for
this repository (D1): nothing comes from the Anki deck or a third-party dictionary. The 96
compound numerals are spelled out by rule.

Conventions (shown on vocabulary cards and as in-story glosses):

- 1–3 equivalents, most common sense first; `;` separates distinct senses.
- Nouns: English without an article; German always with der/die/das, plural-only as
  «die Ferien (Pl.)». mf person nouns give both forms («der Zahnarzt, die Zahnärztin»).
- Verbs: «to …» / German infinitive. Pronominal headwords gloss the reflexive meaning
  («s'asseoir»: «to sit down» / «sich setzen»).
- Function words give the equivalent or a bracketed role. Fragment keys that only live in a
  phrase are glossed through that phrase («parce»: «(parce que) because»).
- Register: familier → « (coll.)» / « (ugs.)», soutenu → « (formal)» / « (gehoben)». Vulgar words
  (merde, putain, con, cul, chier, bordel, foutre, connerie, chiant …) → « (vulg.)» on both sides.
- Expressions gloss the whole chunk idiomatically. Slots are «sth/sb» and «etw./jdn».

Validation at build time: 100 % coverage and no empty strings. Every German noun gloss starts
with an article, except vingtaine, trentaine, quinzaine, quarantaine and cinquantaine, whose
first sense is «etwa zwanzig» … . About 370 English glosses equal the headword. These are true
cognates (table, restaurant, question, crime …) and names of languages or peoples (Latin, Basque,
Islam). The German side is never identical. A 40-per-band self-review of lemmas and of
expressions was done.

## Banding method

1. **v2 is kept** as the curated A1–B1 base, with these defects fixed:
   - compound numerals are flagged `numeral`;
   - the X-cent / X-cents and quatre-vingt / quatre-vingts pairs are merged: the -s spelling
     is the lemma and the other spelling is a form;
   - en-effet, rendre-visite, point-de-vue, par-conséquent, d'accord and d'ailleurs are removed
     from the lemmas and moved to `expressions`.
2. **Deck lemmas missing from v2** are banded in this order:
   1. Curated overrides (`deck_band_overrides`, about 430 words): everyday words that the
      formal corpus ranks low go to A1.2–B1.2. Examples: seconde, kilomètre, casser,
      cigarette, banc, réveil, cauchemar.
   2. Ranks up to 600 → B1.
   3. Next by rank → B2, until the cumulative B2 count reaches about 4,500.
   4. The rest → C1. The B2/C1 cut falls at deck rank 3554.

   Inside a band, the first half by rank is .1 and the second half is .2.
3. **Authored lemmas** were added at their declared sub-band, about 1,550 of them:
   - B2: modern everyday life, housing, health, law and economy;
   - C1: argumentation, politics, science, environment, media, emotions and nuance,
     literary and soutenu verbs, familier vocabulary;
   - a few A1.2–B1.2 words the curriculum needs: appétit, promenade, savon, oreiller.
4. **Forms.** Verb paradigms come from Verbiste. Noun and adjective plurals and feminines come
   from rules. A form is stored only when the suffix rules cannot already reach its lemma. When
   a more frequent lemma already owns the surface, it wins: «tue» is tuer, «vins» is vin. The
   file now has 23,312 forms, up from 3,599.

## Re-banded words

| Word | v2 band | v3 band |
|---|---|---|
| peur, doigt, sucre, beurre, avion | A2 | A1.2 |
| malgré | A1.2 | A2.2 |
| dès, or | A1.2 | A2.2 |
| parmi, selon | A1.2 | A2.1 |
| toit | B1.1 | A2.1 |
| valoir | B1.1 | A2.2 |

New headwords:

- seconde and ci are now A1.2 lemmas.
- «s'asseoir» is the headword of asseoir; «se dépêcher» and «se promener» are also headwords.
- d'accord is now an A1.1 expression.
- d'ailleurs is now a B1.1 connector expression.

## Counts

| Sub-band | Lemmas (non-numeral) | Numerals | Cumulative |
|---|---|---|---|
| A1.1 | 377 | 50 | |
| A1.2 | 338 | 46 | A1 715 |
| A2.1 | 471 | | |
| A2.2 | 451 | | A2 1,637 |
| B1.1 | 597 | | |
| B1.2 | 756 | | B1 2,990 |
| B2.1 | 798 | | |
| B2.2 | 784 | | B2 4,572 |
| C1.1 | 1,343 | | |
| C1.2 | 941 | | C1 6,856 |

There are 6,952 lemmas in total:

- by source: v2 2,667, anki_rank 2,730, authored 1,555;
- 4,978 lemmas have a `freq_rank` and an `ipa`;
- by register: familier 115, soutenu 32.

There are 2,776 expressions. 605 of them have a variable slot.

| Band | chunk | collocation | connector | discourse | idiom | Total |
|---|---|---|---|---|---|---|
| A1 | 152 | 43 | 6 | 29 | | 230 |
| A2 | 141 | 124 | 38 | 80 | | 383 |
| B1 | 179 | 212 | 71 | 74 | 82 | 618 |
| B2 | 235 | 261 | 62 | 85 | 258 | 901 |
| C1 | 161 | 180 | 40 | 64 | 199 | 644 |

## Known follow-ups (code, not data)

The package report lists these with file:line references:

- the tests that pin v2;
- target matching against an inflected target;
- `scene_items.BAND_RANK_CEILING`;
- a numeral and register filter in the word feeds;
- `scripts/build_lexicon_pos.py`. It is superseded for the lexicon, because every lemma now
  carries `pos`. Do not re-run it against v3.
