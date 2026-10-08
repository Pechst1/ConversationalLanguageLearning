# WP-29 — Coverage-controlled generation

Spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3
WP-29. Status: **items 1–6 landed; the hooks are applied** (2026-09-10, WP-29H — see
[Hooks](#5-hooks-applied-2026-09-10)). The guard **measures every scene and stores what it
found**; it does not yet *reject*, because the 821-lemma core list rejects 7 of 7 ordinary
A1 scenes. One constant, `living_story.COVERAGE_ENFORCED`, is the flip. Read §5.4 before
flipping it.

## 1. The problem

Every scene the story engine generates is aimed by *band label*. The director is told
"write for an A1 learner" and nothing afterwards checks the result against the words this
particular learner actually has. Sixteen deterministic guards police the scene's shape —
premise repetition, chapter continuity, gendered address, objective scope, scene length —
and not one of them looks at its vocabulary.

The reading research is unusually specific about what that costs. Comprehension **with
support** needs roughly **95 %** known-word coverage of the running text; unassisted
reading needs about **98 %** (Laufer & Ravenhorst-Kalovski 2010; Hu & Nation 2000). Below
that, a reader is decoding rather than reading, and the graded-reader literature treats
95 % as a floor rather than a target. A scene at 88 % is not "a bit ambitious": it is a
scene the learner cannot use.

So unknown words become a **budget** rather than an accident.

## 2. What shipped

`app/services/lexical_coverage.py`, `app/data/lexical/fr_core_lexicon.json`,
`scripts/coverage_report.py`, one additive line in `scripts/pilot_digest.py`,
`tests/test_lexical_coverage.py` (57 tests).

### 2.1 The known-word set (spec §3.1)

`known_word_set(db, user=…)` returns a `KnownWordSet` that is the union of:

* **FSRS-nailed words.** Every `UserVocabularyProgress` row for which
  `vocabulary_coverage.is_vocab_nailed` is true — retrievability ≥
  `NAILED_RETRIEVABILITY` (0.9) with two reviews and no lapse, or mastered, or 90+
  proficiency. That function is *imported*, never re-derived: a second nailed-rule is
  exactly how `recap.capability_evidence` and `GET /capabilities/progress` came to
  disagree about the same journey (CONTRACTS §8).
* **The CEFR core list** for every band at or below the learner's estimate, read from
  WP-25 via `CEFRProgressService.current(user, recompute_if_missing=False)` — read-only,
  never recomputed, never persisted from inside a guard.

`estimate_source` (`measured` / `placement` / `declared`) travels with the set and into
the scene metadata, so a reader can discount a number that rests on a signup dropdown.

**Why the core list is granted at all.** A learner on day one has no FSRS history. Counting
only nailed words would put every scene at ~0 % coverage and reject all of them — a guard
that costs a learner their day is a defect this codebase has already paid for twice (WP-17,
and the sixteen hint-less guards of 2026-09-07). The core list is an *assumption* and the
payload labels it as one; it is not evidence, and nothing here promotes a declaration into
one.

### 2.2 Coverage of a text (spec §3.2)

`text_coverage(text, known, targets=…, proper_nouns=…)` → `CoverageResult`.

* **Tokenisation** resolves elision (`l'` → `le`, `d'` → `de`, `j'` → `je`, `n'` → `ne`,
  `qu'` → `que`, `s'`, `c'`, `t'`, `m'`, `jusqu'`, `lorsqu'`, `puisqu'`, `quelqu'`) and
  hyphenated clitics (`qu'est-ce`, `va-t-il`, `celui-ci`; the euphonic `-t-` is dropped).
  `aujourd'hui`, `quelqu'un`, `d'abord`, `rendez-vous` and friends stay whole. Getting this
  wrong is not cosmetic — an apostrophe every other sentence, each counted as an unknown
  word, drags a perfectly readable A1 scene under the floor.
* **Accents are kept.** French minimal pairs (`a`/`à`, `ou`/`où`, `sur`/`sûr`) are
  different words. Accent-insensitive matching exists, but only as a last-resort fallback
  and only above `ACCENT_FALLBACK_MIN_LENGTH` (3), so `étudier` matches `etudier` while
  `sûr` never borrows `sur`'s status.
* **Lemmatisation is resolution against a vocabulary,** not a single guess. A resolver
  proposes ordered candidates and the first one the learner knows wins. `SpacyResolver`
  offers the `fr_core_news_sm` lemma first and then the curated candidates;
  `CuratedResolver` — the always-available fallback — uses the vendored irregular-form
  table plus suffix rules (plural `-s`/`-x`/`-aux`, feminine `-euse`/`-elle`/`-ère`/…,
  verb endings → `-er`/`-ir`/`-re`/`-oir`). A resolver that guessed one lemma and committed
  would turn every regular past participle into an unknown word.
* **Proper nouns** (this world's cast and locations, via `world_proper_nouns(context)`)
  count as known and are reported separately. Coverage research treats names that way, and
  it is the honest reading here: "Romy" is a name the scene introduces, not a word the
  learner failed to learn.
* **Coverage counts tokens; the unknown list counts types.** The 95 % figure is about
  running words.

### 2.3 Targets vs accidents (spec §3.2)

Unknown lemmas split into **targets** — today's due vocabulary and errata, passed in by the
caller, matched through the same resolver so an inflected `factures` still matches the
target `facture` — and **accidental** unknowns, which are the model reaching for a word
nobody chose. Targets still count against coverage (they *are* unknown running words); the
split only drives the budget. Unknowns are ranked by frequency, with off-list words sorted
last rather than first.

### 2.4 The guard (spec §3.3)

`check_scene_coverage(scene: SceneText, learner: LearnerLexicon) -> CoverageVerdict`.

| verdict | when |
|---|---|
| `accepted` | coverage ≥ 95 % **and** accidental unknown *types* ≤ the band budget |
| `rejected` / `lexical_coverage_low` | coverage below `SUPPORTED_COVERAGE_FLOOR` |
| `rejected` / `too_many_new_words` | budget exceeded, even at ≥ 95 % |
| `not_assessed` / `text_too_short` | under `MIN_ASSESSED_TOKENS` (20) running words |
| `not_assessed` / `known_set_unavailable` | the lexicon failed to load |

Band budgets (distinct accidental lemmas): **A1 1 · A2 2 · B1 3 · B2 4 · C1 5**. The same
absolute number is a different load at A1 and B2: an A1 scene is ~110 running words and a
beginner has no strategy for guessing from context.

`not_assessed` is never a rejection. An unmeasurable scene is not a bad scene, and a guard
that fails closed here would empty the product on a bad data day.

The hint names the words. Live example, A1 learner, the acceptance fixture:

> This scene runs at 92 % known-word coverage for an A1 learner; 95 % is the floor for
> reading with support, so they would be decoding it rather than reading it. Replace the
> words they have never met — « Aussitôt », « démarche », « bouleversée » — with everyday
> equivalents, and shorten the sentences that carry them. Keep « propriétaire » — that is
> today's target vocabulary and meant to be new.

That is the STATUS 2026-09-07 defect-1 rule: every guard that rejects a *draft* hands the
retry an instruction, never a bare token.

### 2.5 Scene metadata (spec §3.4)

`CoverageResult.as_metadata()` is the additive payload:

```json
{"version": "lexical-coverage-v1", "coverage": 0.9245, "running_words": 53,
 "known_words": 49, "unknown_words": 4, "unknown_lemmas": 4,
 "target_unknowns": [{"lemma": "propriétaire", "surface": "propriétaire", "count": 1,
                      "rank": 594, "band": "A2", "is_target": true}],
 "accidental_unknowns": [{"lemma": "aussitôt", "surface": "Aussitôt", "count": 1,
                          "rank": 711, "band": "B1", "is_target": false}],
 "target_count": 1, "accidental_count": 3, "band": "A1",
 "estimate_source": "placement", "resolver": "curated", "proper_noun_words": 2,
 "floor": 0.95, "budget": 1, "assessable": true}
```

The unknown lists are capped at `MAX_HINT_WORDS` (6) each — this is stored per learner per
day — while the counts are exact. Key: `lexical_coverage` (`SCENE_METADATA_KEY`).

### 2.6 Report and digest (spec §3.5)

`scripts/coverage_report.py --user-id <uuid> [--limit 30] [--stored-only] [--json]` prints
the per-scene rows and the distribution (median, min, max, share at the 95 % and 98 %
floors) over a learner's recent generated scenes.

Every row is labelled `stored` or `recomputed`. `stored` means the generator measured the
scene at generation time and the number is what the learner was actually served.
`recomputed` means the hook below has not landed and coverage was recomputed here from the
stored panels **against today's known-word set** — a learner who has since learned fifty
words reads better in that number than they did on the day. Useful for a distribution, not
as evidence about a particular day, and the label says so.

`scripts/pilot_digest.py` gained one line (import + print, nothing else touched):

```
Lexical coverage: 4/5 scene(s) measured · median 96.4% · min 91.0% · 3/4 at the 95% floor · 5 accidental unknown(s)
```

and, until the hook lands:

```
Lexical coverage: 5 scene(s), none measured (WP-29 hook not applied in living_story.py)
```

An unmeasured scene is not a scene at 0 %, and not a scene at 100 %.

## 3. The lexicon, and its provenance

`app/data/lexical/fr_core_lexicon.json` — **821 lemmas** (A1 505 · A2 198 · B1 118), 894
irregular surface→lemma forms, the elision table and the atomic-compound lists.

No permissively licensed French frequency list was vendored in this repo, and deriving one
from the `VocabularyWord` table would have made the guard depend on whichever Anki deck a
learner imported. So this is a **curated compact list**, and the file says so in its own
`provenance` block (a test pins that it does):

* **Function words** were seeded from `spacy.lang.fr.stop_words.STOP_WORDS` — MIT-licensed
  and already a dependency here — then reduced by hand to lemmas; the spaCy list ships
  inflected forms and archaisms (`allaient`, `anterieure`) that are neither lemmas nor A1.
* **Content words** were curated against the CEFR band descriptors and this app's own
  A1/A2 journey scenarios. No proprietary word list was copied.
* **`rank` is list order within band**, a coarse frequency proxy — *not* a corpus count.
  It orders the unknown list and appears in the metadata; nothing thresholds on it.

Consequences worth knowing before the first paid run: the list is small, so a scene using
ordinary French outside it reads as "unknown" and the guard is **stricter than the real
95 % rule**. That is the safe direction for a first pilot (the failure mode is a retry, not
an unreadable scene), but it is also the first thing to recalibrate once real rejection
rates exist. See [Open items](#6-open-items).

## 4. Lease

Written by WP-29: `app/services/lexical_coverage.py`,
`app/data/lexical/fr_core_lexicon.json`, `scripts/coverage_report.py`,
`tests/test_lexical_coverage.py`, this document, a 12-line append to `STATUS.md`, and six
additive lines in `scripts/pilot_digest.py`.

Written by WP-29H (the hooks, 2026-09-10): `app/services/living_story.py`,
`tests/test_wp29_hooks.py`, §5 of this document, four lines in `scripts/pilot_digest.py`,
an append to `STATUS.md`.

Read only: `app/services/vocabulary_coverage.py`, `app/db/models/progress.py`,
`app/services/cefr_progress.py`, `app/services/journey_errata.py`,
`app/services/unified_srs.py`.

Not touched by either: `lexical_coverage.py` (by WP-29H), `daily_journey.py`,
`journey_latency.py`, `journey_learning.py`, `journey_planner.py`, any schema, any
frontend file.

## 5. Hooks applied (2026-09-10)

Applied in `app/services/living_story.py` by WP-29H, with `tests/test_wp29_hooks.py` (10)
pinning them. What landed differs from the diffs written below in three places, each
because applying them verbatim would have broken something loudly; §5.4 is the one that
matters.

### 5.1 Guard registration — applied

`_check_coverage(learner_text, context)` is called from `_validate_scene` immediately
after `_check_objective_scope`, and raises `StoryUnavailable(reason, hint=…)` — the reason
is the machine token the reports record, the hint names the accidental words to replace
and the targets to keep.

**The lexicon is built in `generate_scene`, not in `story_context`.** The handover put it
in `story_context`, and that function has a second caller: `_turn_payload` builds the
*actor's* context from it. Two consequences, both bad. The actor would have been handed
the learner's whole known-word set — and the actor grades what was actually said; a grader
told in advance which words the learner cannot read is not a grader, which is exactly why
WP-28 §2 put the errata in `generate_scene` too. And `_json_call` does
`json.dumps({"data": payload, …})` on that context, so a `KnownWordSet` on it would have
raised `TypeError`, been swallowed by the `except Exception` there, and surfaced as
`story_provider_failed` on every turn. So `scene_lexicon(db, user, context, errata=…)`
is called once in `generate_scene`, beside `context["errata"]`.

**Nothing lexical reaches a prompt.** `_prompt_payload(context)` strips `lexicon` and
`lexical_coverage`, and is what `_approved` and `_turn_payload` are given. The validator
closes over the *unfiltered* context, so the coverage it writes back cannot leak into the
retry's prompt either.

**It fails open, twice.** `scene_lexicon` returns `{}` if the known set will not build,
and `_check_coverage` returns immediately when there is no `known` — so a learner on day
one is never refused a scene for want of a lexicon, and neither is a caller that never
registered one (every pre-existing `_validate_scene` test passes a bare context).

### 5.2 Scene metadata — applied

On the brief (`brief.story_context["lexical_coverage"]`) and on the persisted scene
(`script_payload["lexical_coverage"]`), which is where `stored_scene_coverage` looks
first. Three additive keys ride with `as_metadata()`: `verdict`, `verdict_reason` and
`enforced`, so a stored row says whether the scene *would* have been rejected.

`None` is stored whenever there is no measurement — the scene was under
`MIN_ASSESSED_TOKENS`, or no lexicon loaded. Not measured is neither 0 % nor 100 %.

**The JSON trap, resolved.** `_storable_context(context)` replaces the live lexicon with
its provenance before `context` is stored on `brief.story_context["source"]` — the band,
the estimate source, the nailed and core counts, the target and proper-noun counts, and
*not* the eight hundred lemmas. That dict is JSON-dumped into the prefetch cache and the
stored scene, and `test_the_brief_still_serialises_with_a_lexicon_on_the_context` is the
pin: it would have raised `TypeError` on the first prefetch.

### 5.3 Targets — applied

`coverage_targets(db, user, errata=…)` fills `lexicon["targets"]` from two sources:

* **The errata WP-28 already wired.** `due_errata()` is now read *once* per generation and
  serves both the director's hint (`errata_hints`, unchanged output — WP-28's test passes
  untouched) and the coverage targets. Same set as the prefetch key's, so the guard cannot
  excuse a word the plan never chose. Only the erratum's `example_correct` is read: its
  `label` names the *rule* («l'accord du participe passé») and whitelisting rule names
  would excuse words no scene is teaching.
* **Today's due vocabulary**, from `UnifiedSRSService.get_journey_candidate_pool` — the
  same pool `select_learning_candidates` ranks. That function could not be reused directly:
  it takes the `ScenarioBrief`, which does not exist yet when the scene is being generated.

A target is a *lenience* — it moves an unknown word out of the accidental budget, never
out of the coverage count — so every read here fails open to nothing. An unreadable queue
makes the guard stricter, never wronger. Cost: one extra query per generation.

### 5.4 Why the guard measures but does not yet reject

`COVERAGE_ENFORCED = False`, a module constant in `living_story.py` (the file's own stated
convention — "the engine must not depend on a flag another agent owns").

Measured the day the hook landed, against the seven-scene A1 fixture set in
`tests/test_living_story.py` — ordinary, deliberately varied A1 French:

| scene | coverage | accidental unknowns |
|---|---|---|
| 0 | 77.8 % | organiser, exposition, affiches, glisse, samedi, vitre |
| 1 | 80.0 % | + four, gardera, panne |
| 2 | 82.9 % | + vendre |
| 3 | 77.5 % | + colis, destinataire, facteur |
| 4 | 64.9 % | + jeux, soirée, vendredi, affiche, annonce |
| 5 | 68.4 % | + immeuble, cave, inondé, lundi |
| 6 | 81.6 % | + garder, poubelles |

**7 of 7 rejected.** Not because the scenes are unreadable, but because the 821-lemma core
list does not contain *samedi*, *vendredi*, *lundi*, *soirée*, *vendre* or *garder*. That
is open item 2 in §6, arriving earlier than expected.

Enforcing it would not have produced better scenes. `_approved` retries at most
`ATELIER_STORY_MAX_ATTEMPTS` times against the same lexicon, so a scene rejected on
vocabulary the list simply lacks is rejected three times and the learner gets
`story_generation_unavailable` — no journey at all. That is the defect §2.4 names in its
own words: *a guard that fails closed here would empty the product on a bad data day.*

So the order is: **measure first, reject second.** Every scene is measured and its verdict
stored from today, which is the distribution `scripts/coverage_report.py` and the digest
line need — and the only thing that can grow the core list from real rejections rather
than from guesses. §6 item 2 already says the lever is the list and not the threshold;
this is that advice in the only sequence that keeps the product alive while it happens.

Flipping `COVERAGE_ENFORCED = True` is the whole change, and
`test_a_scene_carrying_three_unplanned_b1_words_is_rejected_by_name` already runs the
guard in that state. Do not flip it before the stored distribution says an ordinary scene
clears the floor.

## 6. Open items

1. **The guard has never run against a paid generation.** US$0.00 was spent on this
   package; no live model call was made. Its arithmetic is tested and its calibration is
   not — the same open item WP-25 carries.
2. **The lexicon is small (821 lemmas) and therefore strict.** Real French outside the list
   reads as unknown. Expect the first live rejection rate to be higher than the research
   floor implies. The recalibration lever is the list, not the threshold: grow the core
   list from the rejection log rather than lowering 95 %.
3. **`estimate_source: "declared"` still grants the core list.** That is deliberate (§2.1)
   and labelled, but it means a self-declared B1 who is really A1 gets B1-sized coverage
   credit and an easier guard. WP-25's placement is the fix; the label is the warning.
4. **spaCy and the curated resolver do not always agree.** The default is spaCy when
   `fr_core_news_sm` loads, curated otherwise, and the resolver name is recorded in the
   metadata — so a distribution mixing the two is visible rather than silent. Neither is
   allowed to be the *only* answer: spaCy's lemma is offered first and the curated
   candidates always follow.
5. ~~**Targets are not wired**~~ — wired 2026-09-10 (§5.3). What is *not* wired is the
   prefetch cache key: `journey_latency.scene_cache_key` carries the errata but not the
   known-word set, so a scene prefetched last night is served this morning against a
   lexicon that has since grown. Harmless while the guard only measures — the stored
   number is then the one the learner was served, which is what it claims to be — but it
   must be added before `COVERAGE_ENFORCED` is flipped, or a warm scene will bypass a
   guard the cold path applies. That file is not this package's lease.
6. **Targets are matched as lemmas, not through the resolver.** `_target_keys` folds the
   target's *surface*, and `is_target` compares it against the scene word's *resolved
   lemma* — so a target given as «facture» matches an inflected `factures` in the scene,
   but a target given as «bouleversée» never matches `bouleverser`. Both target sources
   produce dictionary forms, so this is currently harmless; §2.3's wording promises more
   than the code does.
7. **One extra query per generation** (the due-vocabulary pool, §5.3), on the hot path
   that already gained two in WP-28. Fine at pilot size.
8. **Nothing writes a PilotEvent.** Coverage costs nothing to compute, so there is no spend
   row; the digest reads stored scene metadata instead. If coverage ever needs a per-call
   ledger entry, it belongs at the generation site, not here.
