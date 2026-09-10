# WP-29 — Coverage-controlled generation

Spec: [INNOVATION-WORK-PACKAGES-2026-09-10.md](INNOVATION-WORK-PACKAGES-2026-09-10.md) §3
WP-29. Status: **items 1–5 landed, guard not registered** (living_story.py is leased to
WP-28 — see [Hooks owed](#5-hooks-owed)).

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
`tests/test_lexical_coverage.py` (56 tests).

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

Written: `app/services/lexical_coverage.py`, `app/data/lexical/fr_core_lexicon.json`,
`scripts/coverage_report.py`, `tests/test_lexical_coverage.py`, this document, a 12-line
append to `STATUS.md`, and six additive lines in `scripts/pilot_digest.py`.

Read only: `app/services/vocabulary_coverage.py`, `app/db/models/progress.py`,
`app/services/cefr_progress.py`, `app/services/living_story.py`.

Not touched: `living_story.py`, `daily_journey.py`, `journey_planner.py`, any schema, any
frontend file.

## 5. Hooks owed

Two diffs for `app/services/living_story.py`, owed by whoever holds that lease next
(WP-28). Until they land, the guard is dark and generation behaves exactly as before.

### 5.1 Guard registration

Add the import beside the other service imports at the top of `living_story.py`:

```python
from app.services.lexical_coverage import (
    LearnerLexicon,
    SceneText,
    check_scene_coverage,
    known_word_set,
    world_proper_nouns,
)
```

`_validate_scene(draft, context)` has no `db`/`user` in scope, so the known-word set is
built once in `story_context` and carried on the context. In `story_context(db, user)`,
after the existing `cast = _cast_for_level(cast, level)` line:

```python
    # WP-29: built once per generation, never inside the retry loop — it is a
    # database read, and `_approved` may call the validator three times.
    lexicon = {
        "known": known_word_set(db, user=user),
        "targets": frozenset(),  # WP-28/WP-24: today's due-vocabulary + errata lemmas
        "proper_nouns": world_proper_nouns({"world": {"cast": cast, "locations": locations}}),
    }
```

and add one key to the returned dict, beside `"variety"`:

```python
        "lexicon": lexicon,
```

Then, in `_validate_scene`, immediately after the existing
`_check_objective_scope(draft.objective_native, context.get("level"))` line:

```python
    # WP-29: the scene must be readable by *this* learner, not by the band label.
    # 95 % known-word coverage is the floor for reading with support; accidental
    # unknowns are a budget that scales with the band.
    lexicon = context.get("lexicon") or {}
    if lexicon.get("known") is not None:
        verdict = check_scene_coverage(
            SceneText(text=" ".join(learner_text), proper_nouns=lexicon["proper_nouns"]),
            LearnerLexicon(known=lexicon["known"], targets=lexicon["targets"]),
        )
        # `_brief` receives this same dict, so the metadata rides back out on it.
        context["lexical_coverage"] = verdict.result.as_metadata() if verdict.result else None
        if verdict.rejected:
            raise StoryUnavailable(verdict.reason, hint=verdict.hint)
```

`learner_text` at that point already holds the premise, opening line, suggested response,
every narration and every dialogue line — exactly the French a learner reads — plus the
chapter title and question, which is a slight over-count and errs toward strictness.

Two notes for whoever applies it:

* `known_word_set` runs one query per generation, not per attempt, because it lives in
  `story_context`. It must **not** move inside `_approved`'s retry loop.
* `context` is serialised into `brief.story_context["source"]` and stored. `KnownWordSet`
  is a frozen dataclass and is **not** JSON-serialisable, so either drop the `lexicon` key
  before that dump or store `lexicon["known"].as_dict()` in its place. This is the one part
  of the hook that will break loudly if skipped — `_brief` calls
  `draft.model_dump(mode="json")` on the draft but stores `context` as-is.

### 5.2 Scene metadata

In `_brief(draft, context, usage=…)`, inside the `story_context` dict:

```python
        story_context={
            "version": VERSION,
            "source": context,
            "draft": draft.model_dump(mode="json"),
            "generation_usage": usage,
            "lexical_coverage": context.get("lexical_coverage"),   # WP-29, may be None
        },
```

The validator in §5.1 already stashes it there: `_approved` calls
`lambda p: _validate_scene(p, context)` and `_brief(draft, context, usage=…)` receives the
very same dict, so nothing else has to be threaded through. A rejected draft never reaches
`_brief`, and a `not_assessed` verdict stores `None` — which the report reads as
"not measured", not as zero.

And in `bind_journey`, on the persisted scene so the report and the digest can read it
without re-deriving anything:

```python
        script_payload={
            "title": brief.title_fr,
            "location_id": brief.location_id,
            "story_engine": VERSION,
            "lexical_coverage": brief.story_context.get("lexical_coverage"),
        },
```

`scripts/coverage_report.py` and `format_coverage_line` read `script_payload` first and
`source_snapshot` second, so either location works.

### 5.3 Targets (WP-28 or WP-24 owner)

`lexicon["targets"]` is an empty frozenset above. Filling it is what turns "3 unknown words"
into "1 target, 2 accidents". The lemmas come from the journey plan that produced the
scene: `journey_errata.errata_targets_for_user` and the due-vocabulary candidates in
`journey_learning.select_learning_candidates`. Until it is filled, every unknown is
accidental, and the A1 budget of 1 is tight — so fill it in the same pass that registers
the guard, or raise `ACCIDENTAL_UNKNOWN_BUDGET` temporarily and say so.

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
5. **Targets are not wired** (§5.3).
6. **Nothing writes a PilotEvent.** Coverage costs nothing to compute, so there is no spend
   row; the digest reads stored scene metadata instead. If coverage ever needs a per-call
   ledger entry, it belongs at the generation site, not here.
