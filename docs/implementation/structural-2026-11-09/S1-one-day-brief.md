# S1 · One day brief: the rule and the words of the day are chosen once and stored

Written 9 Nov 2026 from `origin/main` at `ec60ae44`. Root cause #146, with #280, #576, #443, #596, #447 as children.
Implementation: Opus 5.5, medium effort, own worktree cut from `origin/main`, draft PR, nothing merges without the owner.

## The structural flaw

Nothing stores «today's rule». Each surface works it out again from live database state, at a different moment, with its own ladder:

| Surface | Chooser | Reads |
|---|---|---|
| Scene writer | `living_story.grammar_plan` (`living_story.py:8152`) | `concept_life.introduction_for_today` |
| Rule card | `DailyJourneyService._introduction_for_today` (`daily_journey.py:4915`) | the same function, called a second time |
| La Forge | `forge_picker._anchor` (`forge_picker.py:320`), a 7-step ladder | step 4 repeats the quota pick |
| Home | `_planned_rule_id` (`daily_journey.py:228`), then the live picker | `plan_selection["introduction"]` |
| Forge step in the day | `_forge_for_today`, `_forge_step`, `_forge_prompt_view`, `_forge_anchor_id` | four choices between four sources |
| Recall drills | `select_learning_candidates` and three `_with_*` feeders (`journey_learning.py:634`, `:983`, `:1045`, `:1167`) | scene-term overlap and SRS priority, never the day's rule |
| Courrier | `MissionBriefService._select_concepts` (`missions.py:2134`) | latest séance, due errata, last review |
| Journal | `JournalService.concepts_for` (`journal.py:989`) | first grammar step of the recalled day |
| Words | `ProgressService.get_vocabulary_recommendations` (`progress.py:497`) | the core list by frequency; scene lines are never read |

The only stored value is `plan_selection["introduction"]`, and it is absent on review days, on days without an introduction and on day 1. Every fix so far (#443, #587, `_planned_rule_id`) added one more reader. The same holds for a miss: `slip_category` (`forge_grading.py:181`) knows three slips, and every other miss is explained with whatever rule the session carries.

## Target structure

**A. A `DayBrief`, written once when the day is planned, read by everything.**

Stored under `plan_selection["brief"]` (JSON, no migration), built by one function in a new `app/services/day_brief.py`:

```
rule            {concept_id, role: introduce | review | none, source}
review_rules    [concept_id]      at most one taught due rule (keeps #169)
scene_words     [word_id]         words the scene's lines use, in order of first use
new_word_ids    [word_id]         today's new words (replaces JOURNEY_NEW_WORDS_KEY)
example         {line, speaker}   the scene line that shows the rule, or null
decided_at, version
```

- `rule.role` is always set. A review day and a no-rule day are states of the brief, not missing keys.
- The brief is built after the scene is fixed, so `example` and `scene_words` come from the scene's own lines.
- `day_brief.for_day(journey)` is the only reader. `_planned_rule_id`, `forge_anchor_id` as called from the day, `_forge_for_today`, `_forge_prompt_view` and `grammar_introduce_key` are replaced by it.

**B. The pickers become inputs to the brief, not parallel answers.**
- `concept_life.introduction_for_today` is called once, by the scene writer's plan; its result is carried into the brief. The rule card reads the brief.
- `forge_picker.forge_plan` takes the brief's rule as its anchor whenever the séance belongs to the day (`origin` in `DAY_ORIGINS`). The 7-step ladder remains only for a séance opened from the Cahier with no day.
- `MissionBriefService._select_concepts` puts the brief's rule first when the letter belongs to the day.
- Recall feeders tag each drill with `relation: day_rule | review | repair`, and the day rule's items are served first. No drill reaches the learner without a relation.

**C. New words lean on the scene.**
- New words are drawn from `scene_words` first, up to the owner's share, then from the level list. The scene side already exists (`_scene_lexicon_candidates`, `journey_learning.py:1384`); it stops being a side path and becomes the first source for `day_words.make_plan`.

**D. A miss names its own slip, or says it has none.**
- One `explain_miss(item, learner_text, expected)` returns `{slip, concept_id, reason}`. `slip` comes from a table of detectors (extend `slip_category`: gender, number, elision, accent, COD/COI, order, word choice).
- When no detector fires, the reason is the neutral diff («tu as écrit … ; on attend …»). The day's rule is cited only when `concept_id` of the slip equals the item's concept.
- Journal and Courrier errata carry the slip's `concept_id` (today `journal._record_errata`, `journal.py:1131`, stores none), so the Cahier and the Forge review queue see them.

## Stages (each its own PR)

1. `day_brief.py`, the stored brief, and Home, rule card and the day's Forge step reading it. Delete `_planned_rule_id` and the three `_forge_*` choosers. Supersedes draft #587.
2. Scene writer hands its pick to the brief; `example` filled from the scene; drills tagged with `relation`.
3. Words from `scene_words` (#280).
4. `explain_miss` and errata concept ids (#596, #447). Build on the `check` block of the verdict stack (#642) if it has landed; otherwise return the same field names.
5. Courrier and Journal read the brief.

## Done when

- `tests/test_one_day_brief.py`: for an introduce day, a review day, a no-rule day and day 1, in `a1-de` and `b1-fr`, the rule id in the scene plan, the rule card, the Home entry, the Forge start payload, the first recall block and the Courrier objective is the brief's rule id. It fails on `ec60ae44`.
- A source guard: no module outside `day_brief.py` reads `plan_selection["introduction"]` or calls `introduction_for_today` on a read path.
- The rule card's example sentence is a line of that day's scene (the «Done when» of #146).
- Over a generated day, at least the agreed share of new words are in the scene's lines (#280).
- A table test feeds one miss of each slip kind to each drill type: the reason names the slip, and no off-rule miss cites the day's rule.
- `tests/test_forge_443.py`, `test_wp_s4_one_picker.py` and `test_forge_day_step_169.py` stay green or are rewritten against the brief.

## Not in this package

- What counts as right (#174) and failed checks (#333): the verdict stack #642–#654.
- Step order and completion: package S2 reads the brief but owns the plan.

## Owner decisions needed

1. Share of new words taken from the scene (#280 proposes at least half).
2. On a review day, does La Forge open on the reviewed rule (decision of 7 Nov, assumed yes)?
3. May a day have no rule at all, or does a no-introduction day always review one?

## Checked against main on 12 Nov 2026 (read this before building)

This document was written on 9 Nov, before the verdict ledger (package V) and story truth (#710) landed. A review against main found:

- **Still true.** Nothing stores the day's rule except `plan_selection["introduction"]` in `daily_journey.py`. The choosers are all still there: `_planned_rule_id`, `_forge_prompt_view`, `_forge_anchor_id`, `_introduction_for_today`, `_forge_for_today`, and `forge_picker._anchor`.
- **A chooser this document misses.** `_page_review_for_today` returns a list of review units. With the test-out offer it is the likely source of «four rules in one day».
- **Renamed or gone.** `living_story.grammar_plan` is now `grammar_plan_for`; `_forge_step` and `_scene_lexicon_candidates` do not exist. `get_vocabulary_recommendations` is in `app/api/v1/endpoints/progress.py`; `_select_concepts` is in `missions.py`; `concepts_for` and `_record_errata` are in `journal.py`.
- **Part C is largely built.** `day_words.py` (`scene_words`, `new_word_split`) stores the day's word plan on `VocabularyDrillBatch.plan`. The brief points at that plan and adds no second list of new words.
- **Stage 4 builds on the judge.** `judge.py` and `verdicts.py` have landed.
- **Missing finding.** #723 («Write what you said» over words the learner never wrote) belongs to the drill-relation stage.
- **Day contract and shared pages.** The card's `example` must come from the page as served.

Stages, one per pull request, each behind `DAY_BRIEF_ENABLED` (off in code, switched on in `render.yaml` after a clean nightly walk):

| Stage | What it does | Ends |
|---|---|---|
| S1.1 | Build and store the brief; nobody reads it; log where today's choosers disagree | — |
| S1.2 | Home, rule card, Forge step, Forge start and page review read the brief | #576, #443 |
| S1.3 | The scene writer's pick goes into the brief; `example`; drills carry `relation` | #723 |
| S1.4 | `explain_miss` on the judge; errata carry the concept id | #596, #447 |
| S1.5 | Courrier and Journal read the brief | #622 (a guess) |

A day planned before the flag has no brief: `day_brief.for_day` falls back to `introduction`, then to the RULE step. A brief is written only at planning and never recomputed for an existing journey.
