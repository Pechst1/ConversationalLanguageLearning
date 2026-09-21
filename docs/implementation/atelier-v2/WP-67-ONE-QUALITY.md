# WP-67 — Une seule qualité

*Consistency and phantom loops. Landed 2026-09-21, alongside WP-62/64/66 in the
same checkout; this package touched `app/services/learner_copy.py`,
`app/services/atelier.py` (copy + the ladder's floor),
`app/api/v1/endpoints/atelier.py` (one serve-time helper), the product shell,
Réglages, Home's entries, and its own two test files.*

**US$0.00 — no model call was made by this package**, and none of what it
changed can make one: a copy table, a dictionary walk on the way out of an
endpoint, a `WHERE level = …` that runs in a different order, one removed
settings row and one deleted component.

---

## 1. The language of the app

### 1.1 What was actually left in English

The package brief named five sites. Reading them showed one class of defect in
three places, and a fourth place with the *mirror* defect — French prose shown
to a learner who may not read French yet.

| Where | What a German learner read |
|---|---|
| `_fill_erratum`, `_classify_erratum`, `_word_bank_errata` | «You used present `appelle` in the result clause…», «Background vs event», «Word order» |
| `_correct_transform_rule_based`, the output ladder, `_si_output_ladder_analysis` | «Missing rewrite», «Future result», «You put `arriverons` inside the si-clause…» |
| `_label_for` / `_why_for` / `_repair_for` with no concept | «Grammar target», «The answer does not match the requested grammar target.» |
| `_fallback_transform_items`, `_fallback_output_item` | «Rewrite 'veux' as 'voudrais' so the request sounds polite.» |
| `_apply_produce_length_gate`, `_lexical_gap_why` | «Paragraphe trop court», and a sentence half English half French |

All of them are now rows in `learner_copy`, in the three languages we ship —
**126 new keys**. The English column is the sentence that was there, verbatim, so
every pin written before this package still holds; `de` and `fr` are new.

### 1.2 One bug found on the way

`_word_bank_errata` ended with

```python
if label == "Word bank" and sorted(learner_tokens) == sorted(target_tokens):
    label = "Word order"
```

but `label` had come from `learner_copy` since WP-56. For a German learner it was
«Wortbank», the comparison never matched, and a learner who had every chip right
and only the order wrong was told the **sentence** was wrong rather than the
order. The branch now asks a `label_is_default` flag. Pinned by
`test_a_word_bank_mis_ordering_is_still_recognised_in_german`.

### 1.3 Shared content cannot be written in one learner's language

An exercise set is generated once and reused by every learner
(`atelier_exercise_sets`, `use_shared_cache`), so a fallback instruction cannot
be written in German at generation time without giving every learner German.
The answer is the one `_with_fr_titles` already uses for the concept title:
**localize on the way out**.

* the fallback builders now emit `instruction` (the English sentence, which the
  structural validator and the AI critic were calibrated on and still read) plus
  `instruction_key`;
* `_with_learner_instructions` in `app/api/v1/endpoints/atelier.py` walks the
  payload in `_session_response` and swaps in the learner's column;
* payloads **already cached** carry no key, so the helper falls back to
  `learner_text_for_english`, a reverse index derived from the table's own `en`
  column. No generator version was bumped, so no cached set had to be
  regenerated and no model call was provoked.

Nothing the corrector grades against is touched — `expected_answer`, `source`,
`correct_answer`, `labels`. That is deliberate and tested: a classify label is
compared against what the learner sends back, so translating it on the way out
would mark a right answer wrong. See §5.2.

### 1.4 `resolveProductTitle`

`/settings` returned the literal `'Settings'` under a French masthead. It now
returns `settingsCopy(resolveSettingsLanguage(language)).page_label` —
Einstellungen / Settings / Réglages — because Réglages is the one surface the
owner carved out of the French-chrome rule (WP-46). `EditorialMasthead` passes
the learner's language, read from the cache the profile load leaves behind, in an
effect (never during render: that is a hydration mismatch) and never from the
network (F-20 is already about one page load asking the same question nine
times).

---

## 2. Achievements: the toggle went, the section already existed

The brief offered two ways out — mount an honest «Distinctions» section in the
Dossier, or remove the toggle's promise and say so. **The second, for two
reasons.**

**The section already exists and is honest.** `components/releve/Releve.tsx`
§«La Collection», mounted at `/notebook` (Cahier › Le Relevé), reads
`GET /achievements/my`, filters to `item.completed`, maps `achievement_key` to
French copy, prints the `unlocked_at` date beside each one and shows an empty
state when there is nothing. Building a second «Distinctions» in the Dossier
would have been the same ledger in two places — the phantom-loop failure in its
other form.

**The note the toggle promised does not exist.** «Un avis lorsqu'une distinction
est classée» — `achievement_notifications` is written by signup and by the
settings save, and is read by *no sender anywhere in `app/`*. Pinned by
`test_reglages_no_longer_promises_a_distinction_notice`, which fails the moment a
sender appears (at which point the row should come back).

While reading it, three further facts about the achievement ledger, recorded here
because they belong to whoever next touches it and not to this lease:

* `session_streak_3/7/30` read `user.current_streak`, and **nothing in the
  codebase writes that column** — the Atelier keeps `grammar_streak_days`. Three
  of the ten definitions are unreachable.
* `xp_bronze/silver/gold` read `user.total_xp`, written by the legacy story,
  session and audio flows; the Atelier séance and the journey do not write it.
* `vocabulary_learner/expert/master` count `UserVocabularyProgress.state ==
  "mastered"`, a state every caller *reads* and none assigns.

So for an av2 learner the reachable set is essentially `first_session`. That is a
catalogue problem, not a surface problem, and La Collection is honest about it:
it prints what was earned and nothing else.

The row is gone from Réglages; the stored preference is untouched and still
round-trips through the page's save, so nothing is destroyed if a sender is
written later. `components/learning/GrammarAchievements.tsx` — imported by no
page — is deleted. (Its `git rm` was swept into WP-62's commit `77b3d93` by a
concurrent `git add` in the shared checkout; the deletion is right, the
attribution is not.)

---

## 3. Reachability

* **«Votre dossier»** was already a Home row (WP-37 §2) and stays: it is the
  learner's standing answer to "what does this thing believe about me", and that
  is true every day.
* **«Votre répétition»** appeared only on a debrief day. It now also appears
  while a rehearsal is `declared`, `ready`, `not_prepared` or `rehearsing` —
  the four states with turns still to spend — with its own hint («Elle vous
  attend, quand vous voulez.»). A finished or abandoned rehearsal still shows
  nothing, and a failed read still shows nothing: an entry nobody can open is
  worse than no entry.
* **The one-CTA rule holds.** Both are `av2-row` links under the tiles, never an
  `Action`, never a `tone`. `HomeScreen.tsx` still contains exactly one
  `tone="primary"`, which the WP-37 test pins.

Not done: a Cahier link to either. `pages/notebook.tsx` is not this package's
lease, and the Cahier's own three tabs are a different agent's surface.

---

## 4. F-30 — the ladder starts at the placement estimate

`_cefr_levels_at_or_below` read `user.cefr_estimate` and capped the cold-start
pick at that band. Two things were wrong with that for a learner who had just
been placed at A2.2:

1. `cefr_estimate` only folds a placement in once `CEFRProgressService.recompute`
   has run, so a fresh placement could still be sitting behind the signup
   default; and
2. even with the right ceiling, the query ordered by
   `is_foundation DESC, difficulty_order ASC` across *every* eligible level, so
   it always returned the easiest A1 rule in the catalogue. The ceiling was read;
   the floor never was.

Now: `placement_band(db, user)` asks the placement service for a result worth
trusting (it owns that judgement — complete, levelled, above its own confidence
floor — and this code never second-guesses it); the ceiling is the higher of that
and the estimate, so **a measurement can only ever raise it**; and the cold-start
pick walks down from the learner's own band, dropping to a lower one only when
that band has nothing left. A learner who has never been measured still starts at
A1, because A1 is then their band.

---

## 5. The tests

### 5.1 `tests/test_frontend_av2_chrome_language.py` (5 tests)

The guard the brief asked for. It reads only text a learner can receive — JSX
text nodes with `{expressions}` stripped, and string literals given to a
rendering or announced prop (`label`, `hint`, `title`, `placeholder`,
`aria-label`, …, including the object form Home's `entries` rows use) — across
`components/atelier-v2/**` and the seven av2 pages, and fails on any sentence
containing a word from a list of English function words **with no French
homograph** (so «question», «sentence», «note», «on», «a», «or», «car», «plus»
cannot raise a false alarm).

Réglages (`pages/settings.tsx`, `lib/settings-copy.ts`) and the gallery / QA
harness are exempt, by name, in their own test: the first is in the learner's
language by design and has its own guard in `tests/test_settings_language.py`;
the second two are tooling.

It found **nothing** when it was written — the av2 tree is clean — so it is a
guard, not a repair. Two tests prove it is not vacuous: one plants
`<p>Settings</p>` and a `label="Close the day"` and asserts both are caught; one
feeds it real French chrome and asserts silence.

### 5.2 `tests/test_wp67_one_quality.py` (15 tests)

The erratum prose in all three languages for si / negation / tense, the word-bank
relabelling bug, the no-concept floors, the fallback instruction's key and its
no-spoil property, the serve-time swap by key **and** by stored English, that a
model-written instruction is left alone, that an English reader's payload comes
back object-for-object identical, that the graded fields do not move, the
placement ceiling and floor, and the two phantom removals.

### 5.3 Runs

```
TZ=UTC .venv/bin/python -m pytest \
  tests/test_wp67_one_quality.py tests/test_frontend_av2_chrome_language.py \
  tests/test_atelier.py tests/test_learner_copy_localization.py \
  tests/services/test_atelier_validation.py tests/test_atelier_quality_srs.py \
  tests/test_atelier_transform_produce_fixes.py tests/test_atelier_honest_edition.py \
  tests/test_atelier_epreuve_learning_moments.py tests/test_settings_language.py \
  tests/test_core_mobile_edge_flows.py tests/test_core_mobile_user_flows.py \
  tests/test_frontend_pilot_experience.py tests/test_placement.py \
  tests/test_atelier_serial_conversation.py                      # all green

cd web-frontend && npm run type-check && npm run lint && npm run build   # clean
npm run test:settings-copy && npm run test:dossier && npm run test:atelier-ui
npm run test:journey && npm run test:rehearsal                            # all pass
```

`tests/test_atelier.py::test_atelier_api_today_session_attempt_and_complete`
fails when run **alone** and passes in file order, on its
`minted_collectibles[0]` assertion. That is the known shared-database order
dependence (memory: *"conftest db is session-scoped SQLite without per-test
cleanup"*, and commit `a9a050f`), it is about the reward economy's cap and not
about anything this package touched — an A1 learner's selection is byte-identical
before and after §4.

---

## 6. Leftovers

1. **F-27 («Écouter d'abord» before the first planche) was not done.** It lives
   in `components/atelier-v2/journey/StoryEpisode*`, which WP-66 holds. Handed on
   as a WP-66 follow-up.
2. **The grammar catalogue's own prose is English, catalogue-wide.**
   `rule_panel.rule` is `concept.core_rule`; `when` / `pattern` / `check` come
   from `grammar_feedback.py`'s profile table. Both are English for *every*
   concept, not just the three in-code fallbacks the brief named, and
   `grammar_concept_localizations` carries a `title` per locale but no body. This
   is the largest remaining language debt and it is a data + `grammar_feedback`
   job, not an `atelier.py` one — translating the three fallback rows alone would
   have hidden it. **Not done, deliberately.**
3. **Model-written instructions stay in whatever language the model wrote.** The
   serve-time localizer only re-reads rows the copy table holds. Generated
   exercise sets are shared, so the real fix is to ask the generator for a copy
   key or to key the cache by language.
4. **Classify labels are still English** (`article changes`, `background/habit`).
   They are compared against what the learner sends back, so localizing them
   needs the grading to compare label *ids* — a wire-contract change, not a copy
   change.
5. **The achievement catalogue's dead inputs** (§2): `current_streak`,
   `total_xp` and the `mastered` vocabulary state. Three of ten definitions are
   unreachable by design accident. Worth one package of its own, or a decision
   to retire them.
6. **Nothing here has been walked by a person.** The preview cannot render authed
   routes (memory), so this package is `tsc` + `lint` + `next build` + node
   suites + pytest, and no browser.
