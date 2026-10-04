# Experience review response — 2026-10-04

**Status: proposed work packages, not implementation or rollout approval.**
This is an evaluation of [EXPERIENCE-REVIEW-2026-10-04.md](EXPERIENCE-REVIEW-2026-10-04.md), checked against the current working tree and the [content program](CONTENT-PROGRAM-2026-10-03.md). It defines WP-123–134. The review remains unchanged as the original evidence record.

## 1. Recommendation

Prioritize a reliable, appropriately demanding daily experience before adding more surfaces. Preserve the authored story, consequential choices, calm presentation and named grading contract. Fix the seams around them: failed days, initial level, time budgeting, practice selection and the meaning of progress.

The reviewer is persuasive about concrete defects and the mismatch between levels. The proposed remedies need refinement in four places:

1. **A recovery day must preserve causality.** Re-reading a completed page is sound. Jumping to the next tentpole after two failures is safe only if its prerequisites are satisfied or an authored bridge supplies the missing events. Never fabricate learner choices to get there.
2. **Shorter placement must still distinguish evidence from inference.** Offer placement after the first ending and start vocabulary checks high. Do not treat one small recognition sample as proof that every word in every lower band is mastered.
3. **A time budget is a planning constraint.** Adding “+ words” to a ten-minute label does not solve an overloaded day. Fit the recommended core path to the selected budget, then show genuinely optional extensions with separate estimates. Do not force advanced learners through filler to reach ten items.
4. **Make progress observable without weakening its meaning.** Schedule opportunities for delayed independent use and align the notebook with the level view. Keep the existing evidence required for “Tenue”; do not award it because three weeks elapsed.

**Start by landing the review's fixes (WP-123a) and measuring the current generated-day failure rate (WP-133a).** Then ship Wave 1, the small and medium packages with the largest learner-visible effect, before the larger timing, practice and authoring work (§4). Run the full live evaluation against the assembled changes and use its result to decide wider rollout.

**Revision (2026-10-04, after the reviewer's reply).**
- WP-123 is split, so that one large baseline package no longer gates everything.
- WP-124 is split, so that the worst break (the stranger scene) is removed before any bridges are authored.
- A capped live read moves to the start, because the current failure rate sizes WP-124.
- WP-127 and WP-128 are scoped to what can be validated without real learner data.
- The average-learner throttle oscillation joins WP-131.
- Listening joins the claims audit (WP-134A).
- The review's points accepted here: «a sixth» of the season is 16/59 ≈ 27 %, and its time critique overlooked `PAGE_READING_FACTOR = 2.0`.

## 2. What the evidence supports

### Confirmed in the current code

| Finding | Current implementation | Implication |
|---|---|---|
| Failed story generation can serve an unrelated scene | `daily_journey._authored_fallback_brief` rotates generic scenes with `bind_serial=False`; their authored ceiling is A2 | The continuity problem is real. Recovery needs a season-specific path, including completion and replay semantics. |
| Placement arrives late and cannot start at B2/C1 | `placement.PLACEMENT_OFFER_MIN_DAYS = 3`; `StartingPoint` supports only new/some/comfortable | Change both the registration contract and offer timing. Changing the offer constant alone leaves day one at the wrong level. |
| Own-band success triggers “above-band” evidence | `journey_placement_evidence` accepts `band >= current_band` | Require genuinely higher-band evidence for unsolicited beginner placement; preserve a voluntary check. |
| Vocabulary checks proceed from the bottom | `band_check.checkable` and the frontend sequence are ascending; `PASS_SHARE = 0.9` | Top-down flow needs coordinated API, state and UI changes, not just reversing a list. |
| The timing model starts every level alike | Default 0.45 s/token, trusted bound 0.30–0.70, plus `PAGE_READING_FACTOR = 2` | Calibrate the complete model. Applying the proposed new priors without considering the page multiplier could overcorrect. |
| An unused letter target still becomes an error | `missions._apply_vocabulary_feedback` creates an erratum and downgrades accepted to partial; `vocabulary_credit` also handles missed targets as negative events | This is unfinished grading correctness and should move ahead of practice enrichment. |
| Tentpole grammar is outside the core journey | `daily_journey` suppresses introduction and sends page units to the Forge | D7 already specifies a contextual rule review. This is an implementation gap against an existing decision, not a new feature proposal. |
| The drill limits new words independently of the rhythm | `pages/vocabulary/review.tsx` requests 8; Encore deliberately requests 0; the server already calculates remaining allowance | Make the normal drill honor the remaining allowance while retaining the bounded review-only Encore contract. |
| The light-check repair affects new credits | `band_check.credit_schedule` is used when `credit` creates rows; existing progress rows are skipped | New accounts improving does not establish that previously credited accounts recover. Audit and repair existing affected data by provenance. |

The review's dedicated regression suite was independently run during this evaluation:

```text
venv/bin/python -m pytest tests/test_experience_review_2026_10_04.py -q
44 passed in 0.57s
```

The full suite, 15 long lives, frontend checks and live providers were **not** rerun here. Their numbers in the review remain reported results. The checkout contains extensive uncommitted changes from several workstreams; “fixed in the working tree” must not be described as “deployed.”

### Limits that affect the next decisions

- **Zero detected problems is not zero experience problems.** The final checks cover selected invariants. They do not assert adequate advanced practice, truthful timing, season prose quality or learner return. The final 15-life result also combines runs before and after the last fixes; rerun all lives on one candidate before declaring the wave closed.
- **The minutes are modeled, not observed human times.** Gap-day prose and learner replies are scripted, placement grading is scripted, and the letter corrector is disabled. The timing tables establish useful hypotheses, not precise production durations or learning rates.
- **The surfaces are not exhaustively tested.** La Forge is offered but not played; audio is absent. Those paths and production provider behavior need their own evidence.
- **Thirty days is too short for the new light-check intervals.** The fix spreads some checks out to 365 days. Check the future workload and memory estimates as well as the first-month backlog; otherwise the overload may simply move beyond the walk.
- **The paid A2 read is a useful failure case, not a production failure-rate estimate.** Three failures in eight generated days warrant action but are a small, older sample. Repeat at the changed code/prompt version and retain counts and denominators.
- **The proposed vocabulary threshold trades one error for another.** Under a simple independent-item binomial model, a learner with 92% per-item accuracy fails the present 22/24 threshold about 30.1% of the time, versus 12.1% at 21/24. But a learner with 80% accuracy passes about 11.5% versus 26.4%. These are mathematical illustrations, not calibrated estimates of vocabulary knowledge. Treat 21/24 as a candidate policy to validate, especially before crediting lower bands.
- **The learning-speed comparison is not an effectiveness result.** Internal syllabus gates, modeled minutes, classroom hours and a receptive-skill study do not establish comparable outcomes. Do not turn the review's Duolingo extrapolation into a product promise. External references in the review have not been independently verified in this evaluation.
- **Some important findings were omitted from the top ten.** Add advanced scene lexicons, repetitive fallback letters, contextual vocabulary ordering, tentpole review and the authored epilogue. Conversely, the repeated match grid is a small selection-quality improvement, not a reason to delay continuity work.

There is also a documentation inconsistency: 16 of 59 tentpole days is approximately 27%, not “a sixth.” More importantly, `CONTENT-PROGRAM` D5 is already configured as `ATELIER_SEASON_SCRIPT=s1` in `render.yaml`. Verify actual deployment/cohort state before calling the next step a first launch; the repository setting alone does not establish what is live.

## 3. Package map

Sizes are relative scope estimates: S = contained, M = cross-file, L = stateful or substantial cross-surface work. They are not delivery-date promises. Every package below is **proposed / not started**.

| Package | Outcome | Priority | Size | Dependencies |
|---|---|---|---|---|
| WP-123a | Land the 19 fixes; one-candidate 15-life rerun; CI job | P0 | S | None |
| WP-123b | Walk coverage (Forge, outages, timestamps), 365-day workload, data audit | P1 | M | 123a; runs in parallel |
| WP-124a | A failed day replays the last page, never a stranger scene | P0 | S / M | 123a |
| WP-124b | Authored bridges so failures cannot stall the season | P1 | L | 124a; 133a failure rate |
| WP-125 | Honest letter assessment and credible fallback letters | P0 scoring; P1 content | M | 123a |
| WP-126 | Level-appropriate day one and earlier optional placement | P1 | M | 123a |
| WP-127 | Bounded top-down vocabulary calibration | P1 | L | 126 contract |
| WP-128 | A daily plan and estimate that fit the learner | P1 | L | 123a; 126 for final scenarios |
| WP-129 | Useful advanced practice and contextual tentpole review | P1 | L | 128 budget contract |
| WP-130 | Timely grammar reuse and consistent progress labels | P1 | M | 128; coordinate with 129 |
| WP-131 | Contextual vocabulary supply and reachable rhythm quotas | P1 | M | 127 credit contract; 128 budget contract |
| WP-132 | Repair the two story beats and author the epilogue | P1 | M / L | 124b recovery contract for epilogue |
| WP-133a | Early capped baseline read of generated days | P0 | S | Cost approval |
| WP-133b | Generated-day quality, live checks, pilot and rollout evidence | P0 release gate | M + iteration | Final run after relevant packages |
| WP-134 | Honest proficiency claims and external calibration | P0 claim audit; P2 study | S / L | 123a evidence; stable assessment for study |

### WP-123a — Land the review fixes and the minimal gate

**Why first.** The 19 fixes sit uncommitted in a shared checkout with dozens of dirty files from other workstreams. Losing or mixing them is the largest current risk, and every later package builds on them.

**Scope.**
- Land the review's files as one reviewed change, with the owner's approval and committed by explicit path. Keep other sessions' files out of it.
- Rerun all 15 lives on that one candidate, in a single run, and retain the machine-readable records plus readable examples.
- Add the experience walk to CI with its own runtime budget. The existing browser job has a 30-minute timeout, so do not append a nominal 15-minute suite blindly. Keep a short PR gate and a complete scheduled or manual gate.
- Exercise the actual v2 catalogue and configuration explicitly; the general test fixture still defaults to v1.
- Record a disposition for every full-suite failure, by its owning workstream.

**Primary files:** the review's changed files (listed in its §9), `tests/experience_walk.py`, `tests/test_experience_walk.py`, `tests/walk_checks.py`, `.github/workflows/walk.yml`.

**Done when:** the fixes are in an identified commit; the complete life matrix passes on it in one run; CI runs the walk; every baseline failure has a disposition. This is not complete on the strength of the 44-test run alone.

### WP-123b — Walk coverage, long-horizon workload and data audit (parallel)

**Scope.**
- **Coverage.** Extend the walk to play La Forge and to inject provider outages. Fix the clock-dependent timestamp evidence (database defaults do not follow the test clock) before using the walk's measured forecast.
- **Workload.** Extend scheduling simulations to 365 days and report true due counts, review minutes and retention assumptions. The current 150-card check is a regression alarm, not a usability target.
- **Data.** **First establish whether production holds any affected rows.** The vocabulary check and these error paths landed on 2026-10-03, and may exist only on test copies.
  - Only if affected rows exist: deliver a dry-run report and a narrowly scoped, idempotent repair for records whose provenance proves they were affected.
  - Preserve legitimate errors, independent reviews and imported cards.

**Primary files:** `tests/experience_walk.py`, `band_check.py`, the progress and error models; a scoped repair script only if needed.

**Done when:** forced-failure and Forge cases are represented in the walk. The 365-day workload is reported. The data question has an answer; if a repair is needed, it is demonstrated on disposable fixtures with zero unrelated rows changed. **WP-123b gates nothing else.**

### WP-124a — A failed day never leaves the season

**Scope.** For a season life, a failed gap day serves an honest reprise of the last completed, resolved page instead of the generic authored scenes. The reprise uses the page's actual branch and level support, A1 translations included. It earns only the learning evidence actually produced; it does not reapply choices, rewards or story consequences. The generic scenes are never served to a season life.

Separate generation attempts from completed learner days, so the reprise does not count as a played season day. Define the no-previous-page case (the first day of a gap after a tentpole) and old stored journeys.

**Primary files:** `daily_journey.py` (`_authored_fallback_brief`, `_serve_authored_fallback`), `season/runtime.py`, journey/reader recovery copy.

**Done when:** a failed gap day never produces a stranger scene, a «vous» from a character who says «tu», or untranslated A1 lines. Reloads and concurrent requests do not duplicate consequences. Existing non-season lives keep their current fallback.

### WP-124b — Recovery that cannot stall the season

**Scope.** On repeated failures, use a deterministic authored continuation rather than an indefinite reprise loop.
- **The next tentpole**, only when its prerequisites already hold.
- **Otherwise a short authored bridge** that supplies the indispensable events first.
  - Build the bridges from the moments each gap already marks as `required` in `gaps.json`. There are 7 gaps, and those required moments are what a blind skip would drop.
  - Preserve choices, secrets and relationship state.
  - The bridges are new story text, so they need owner approval like any bible change, and `season_check`'s deviation record.
- **Record shortened gaps explicitly.** Do not pretend skipped episodes were played.
- **Define the edge cases:** recovery after the finale, successful-generation reset and prefetch invalidation.

Size the package by WP-133a's measured failure rate. A low rate may justify fewer bridges first, for the gaps that hold gates.

**Primary files:** `living_story.py`, `season/runtime.py`, `season/clock.py`, `season/director.py`, `app/data/season/s1/`.

**Done when:** consecutive outages and mixed success/failure cannot produce an indefinite reprise loop. A deterministic all-provider-down season reaches the ending with prerequisites and learner choices intact.

**Boundary:** the review's “two failures → next tentpole” becomes a recovery policy with prerequisites, not a blind cursor increment.

### WP-125 — Letter omissions are not language errors

**Scope A, ship first.** Represent an unused suggested word as an unobserved learning opportunity. It does not create an erratum, lower the letter's verdict, count as a failed recall or advance its mastery. Preserve its existing schedule; do not pull a future review forward merely because the word was unused. A genuinely incorrect use or omitted communicative requirement can still affect the corresponding assessment.

Apply this distinction through the corrector merge, vocabulary events/credit, objective completion, debrief and story consequences. Removing the displayed repair while leaving an underlying “partial” outcome is insufficient. Add provenance-specific handling for historical bogus omission repairs in coordination with WP-123b.

**Scope B.** Rotate fallback letters by level, recent correspondence and story state. Prefer fewer credible letters over repeated beginner prompts. Respect the optional time allocation from WP-128. Keep unassessed feedback neutral when the provider is absent.

**Primary files:** `missions.py`, `vocabulary_credit.py`, `story_correspondence.py`, `learner_copy.py`, Courrier rendering and feedback tests.

**Done when:** two otherwise equivalent successful letters receive the same communicative verdict whether or not they use a suggested synonym; omission adds no lapse or repair; genuine language errors still behave correctly. Replay is idempotent. A month of provider-off letters has level-appropriate content and no unexplained repeat of a completed request within seven days; deliberate follow-ups reference the prior exchange.

### WP-126 — Appropriate day one, placement after the first ending

**Scope.** Extend sign-up to five plain-language starting points covering A1–C1, with optional CEFR labels. Use C1 rather than an ambiguous “C1+”: the agreed scale ends at C1.2. Keep self-declaration distinct from measured placement. Day one uses that declaration for story language, practice and correspondence.

Offer placement immediately after the first completed ending for non-beginners, with skip and resume. Avoid turning the ending into a compulsory chain of assessments. For “new,” only genuinely above-band independent evidence should trigger an unsolicited offer; use explicit band ordering and count distinct qualifying days. Keep a manual check available so a learner is not trapped by a conservative initial choice. Reconcile prefetched/unstarted plans after placement without rewriting a day already in progress.

**Primary files:** `app/schemas/user.py`, `app/services/placement.py`, `web-frontend/lib/onboarding-signup.ts`, `pages/auth/signup.tsx`, placement page, journey-ending integration, generated API types if affected.

**Done when:** B2 and C1 declarations receive appropriate content on day one; the offer appears after that ending; own-band A1 success alone never triggers it. Skipping, resuming, manual entry and older three-option clients work. A declined offer does not nag the learner daily. Browser tests cover the actual end-of-day transition, which the present life walk checks only at the next day's start.

### WP-127 — Short vocabulary calibration with honest credit

**Scope.** Start at the highest eligible sub-band below placement. On a miss, descend; on a pass, stop the ladder. Bound a visit to at most two 24-item checks, with explicit stop/resume and useful partial results. Do not move the whole bottom-up marathon to day one.

Credit lower bands conservatively and mark it as **inferred**, separately from directly sampled recognition and productive use. It must not masquerade as demonstrated production or full CEFR competence. The existing light checks remain the safety net: an inferred word the learner misses returns to the ordinary supply.

Keep the validation proportionate. There is no real learner data yet, so evaluation sets would be synthetic and prove little.
- Document the threshold trade-off with the binomial illustration.
- Include synthetic learners with uneven vocabulary in the walk.
- Validate the rule in the learner pilot (WP-133b) before tightening or loosening it.
- Keep 21/24 as a candidate, not an unquestioned constant change.
- Record policy version, sampled items and actual misses, so the pilot can measure it.

Use persistent assessment identity so reload, midnight and retries do not change the answer key or double-credit words. Never overwrite an established weakness with inferred credit. Retain the improved credit schedule and apply long-horizon workload checks from WP-123b.

**Primary files:** `band_check.py`, vocabulary endpoints/schemas, `components/atelier-v2/band-check/`, `tests/test_band_check.py`, vocabulary provenance/coverage consumers.

**Done when:** the common strong C1 path ends within one high-band check plus any short confirmation; no visit exceeds 48 items. The selected rule and its expected false-pass/false-fail trade-off are documented, and the pilot measures it. Existing weak/missed words remain learnable, skip/resume is stable, and inferred credit is visible as such. No assessment creates a future review flood merely outside the 30-day window.

### WP-128 — Fit the core day to the chosen time

**Product contract.** The selected rhythm budgets the recommended core path: the story and its required practice/review. Optional words, Courrier, Forge and reading show their own estimates and do not become hidden completion requirements. If a quota cannot fit today, defer intake or offer a clearly timed continuation; do not silently expand the day.

**Start small.** The planner already adapts to each learner's measured pace after three observed days (`MIN_PACE_OBSERVATIONS = 3`), but only within 0.30–0.70 s a token. The first step is to make the prior level-aware, widen that bound, and instrument the error between estimated and actual active time. The fuller cost model below follows once real timings exist (WP-133b).

**Scope.** Separate French reading, native instructions, composition, help and normal feedback costs. Introduce level-aware priors, then adapt from active time after enough observations. Calibrate the page factor and measured bounds together; the review's constants are starting hypotheses. Exclude idle/background time and measure provider waits separately. Keep estimation separate from enforcement: no timed answers, truncation or penalty for being slower.

Trim optional/new intake before necessary learning support. For an authored page that intrinsically exceeds the rhythm, show a longer estimate before starting and provide a natural resumable boundary. Preserve the story and required feedback. Carry one shared estimate to Home, entry chips, the plan and the ending.

**Primary files:** `journey_planner.py`, `daily_journey.py`, existing pace/event services, journey contract, `JourneyTodayCard` and optional activity entries, `tests/experience_walk.py`.

**Done when:** ordinary core-day fixtures at every level/quality fit the selected budget within a proposed 20% tolerance; indivisible longer pages are explicitly identified before start. Independent timing fixtures and a small observed learner sample validate estimates rather than feeding the planner's own estimate back as truth. Home totals match the selected path. Report distributions and outliers, not only the overall mean.

### WP-129 — Better practice at B1+ and grammar from the page

**Scope.** Fill available practice time with relevant production, transformation and contrasts between already introduced partner units. Treat 8–10 items and roughly half interleaved as starting design targets for a ten-minute day, subordinate to WP-128's budget, learner need and exercise quality. Include free responses; ten near-identical transforms are not the intended outcome.

Complete D7 in the core journey: after a tentpole's ending, use one actual line from the level-resolved page for a short contextual review, reusing the rule card/x-ray components. Select a unit the learner has already met. If none qualifies, show an optional observation or omit the review; do not disguise a new unit as review or consume an introduction slot. Keep story interaction uninterrupted.

Deduplicate materially overlapping grids and items in one day. Coordinate scene vocabulary with WP-131 and delayed reuse with WP-130 so each consumes the same budget and evidence contracts.

**Primary files:** `journey_planner.py`, `journey_learning.py`, `grammar_items.py`, `daily_journey.py`, `season/runtime.py`, `app/data/season/s1/units.json`, rule/x-ray components.

**Done when:** B1/B2/C1 days contain meaningful productive and mixed-unit practice within their budget; no item exists solely to meet a count. Eligible tentpole days review a previously introduced unit in a line the learner actually saw. No new unit or mastery is credited by reading the x-ray. Lower-level learners and short rhythms retain a complete, appropriately supported day.

### WP-130 — Grammar reuse that can produce visible progress

**Scope.** Offer a suitable independent-use opportunity 7–10 days after introduction, once the unit has been successfully used, and retain a spaced item at least 14 days after introduction. A stability threshold must not prevent either evidence opportunity. Use a context that invites the form without supplying the answer. If the story cannot naturally carry it, use a short separate practice context within the daily budget.

Preserve “Tenue”: two correct independent uses on days at least seven days apart plus the spaced success. Hints, copied suggestions, transformations and displayed examples must retain their actual assistance/evidence category. A failed or missed opportunity leaves the unit in progress and schedules another suitable opportunity.

Expose introduced/practising/held consistently in the notebook and level summary, with counts such as “6 en route · 0 tenues.” Explain the missing evidence where useful. Recalibrate the forecast only after the lifecycle change is measured; do not hard-code a three-week promise.

**Primary files:** `concept_life.py`, `journey_learning.py`, `grammar_items.py`, `level_coverage.py`, `cefr_progress.py`, `level_forecast.py`, notebook/Cahier views.

**Done when:** a deterministic successful learner can meet the unchanged held conditions around days 14–21; this is possible, not guaranteed for every learner. Assisted or insufficiently spaced evidence never holds a unit. Strong/average/struggling 30-day runs show accurate transitions and consistent counts across surfaces.

### WP-131 — Contextual words and reachable quotas

**Scope.** Give B1/B2/C1 tentpole variants their own useful lexical anchors, including expressions when supported, chosen from the actual rendered lines. Preserve the review's difficulty floor for new words while allowing genuinely due foundational weaknesses to be reviewed.

Improve new-word ordering with scene relevance, learner interests and basic diversity constraints alongside frequency. Avoid long consecutive numeral runs and uncontextualized blocks of newspaper vocabulary. This changes selection and context, not the legitimacy of advanced news vocabulary or the owner's source list.

Smooth the intake throttle for learners near its threshold. It enters below 80 % review accuracy and exits at 85 %, so an average learner around 78 % flips between about 8 and 3 new words a day on noise. A longer window or a graded factor would remove the flipping; the throttle's purpose stays unchanged.

Let the normal drill request the server's remaining daily allowance, accounting for words already introduced or reserved by the journey, throttle, local day and total queue capacity. Reachability may require an explicit bounded continuation; do not force all remaining words into a short session. Keep the existing review-only “Encore 5 minutes” semantics.

**Primary files:** `core_lexicon.py`, `progress.py`, `vocabulary_pace.py`, vocabulary endpoints, `pages/vocabulary/review.tsx`, season lexicon data and projection, quota tests.

**Done when:** an average learner's daily intake no longer swings on noise around the throttle threshold. An eligible learner can access the remaining 18/30-word rhythm allowance without bypassing server limits or adding duplicate introductions. Due review and time bounds still apply. Journey-first/drill-first, reloads and concurrent tabs behave consistently. Advanced scene practice uses genuine scene words; curated first-week samples show varied useful vocabulary.

### WP-132 — Editorial repairs and a written ending to the season

**A, deliver early.** Give T2 day B's “double” choice an immediate visible reaction, consistent with its existing flag and later consequences. Repair A1 references to Odile's past with the smallest comprehensible wording. Glossed chunks such as “elle est partie,” “c'était” and “elle savait” are suitable candidates, with their translations and learner support included.

Update the level validator with narrowly scoped, documented phrase exceptions if necessary. Do not count an entire multiword chunk as one lexical token merely to preserve the coverage percentage: report token coverage and supported chunks separately. Keep clues, dates and branch meaning intact across variants. Update the authored source/approval record together with generated or derived files.

**B, before learners reach the finale.** Author the epilogue week required by content-program D8. Carry the actual ending, choices, cast relationships and unresolved threads into it and into the subsequent continuation. Define what is served when the continuation provider is unavailable. A complete second season is a separate follow-up, not a prerequisite for these immediate repairs.

**Primary files:** `app/data/season/s1/`, `scripts/season_check.py`, `scripts/season_levels.py`, `season/runtime.py`, continuation integration in `living_story.py`, `SEASON-LEVELS.md`.

**Done when:** all supported branches have a meaningful immediate response; A1 readers can understand that Odile's departure happened in the past. Validators pass without blanket relaxations. Every finale variant reaches a coherent authored epilogue, with an honest continuation and no reset to strangers or the unrelated Berlin season.

### WP-133a — Early capped baseline read

**Why early.** The current generated-day failure rate sizes WP-124b. The same read shows whether generated days actually carry today's grammar unit (`grammar_plan.introduce`), which WP-129 depends on. The last paid read (2026-09-30, A2, 3 of 8 generated days lost) predates several prompt and guard changes.

**Scope.** Ten learner-days each at A1, B1 and C1 on the current code, under an approved cost cap (the review proposed US$3). Report generated-day counts, failures with their guard reasons, rule-in-scene compliance and a short prose read. Prepare the run manifest, rubric and stop conditions first.

**Done when:** the failure rate (with denominators), guard reasons and compliance are published, and WP-124b and WP-129 are sized from them.

### WP-133b — Live quality evaluation and rollout evidence

**Scope.** Prepare the run manifest, rubric and stop conditions before paid execution. Begin with the review's proposed ten learner-days each at A1, B1 and C1; report how many are generated days. Include current A2 regression fixtures and exercise difficult branches. Extend coverage to later gaps and finale transitions through targeted seeded runs; the first ten days cannot validate the whole season.

Measure provider failure rate separately from successful recovery rate. Read for repeated premises, teacher-like character dialogue, causal progress, level fit, rule-in-scene compliance and the naturalness of reactions to varied answers. Fix root causes in the gap brief, selection, validators or prompts before rerunning affected cases. Keep representative failures as regression fixtures. Do not weaken guards just to reduce the fallback count.

The review's **US$3 is a proposed allowance, not spend already approved by this planning request**. At execution, resolve the applicable spending authorization and enforce the cap across retries and relevant provider calls; exclude media generation unless separately budgeted. Stop with an incomplete coverage report rather than silently exceed it. Paid generation and rollout are distinct actions.

Add a small observed learner pilot spanning beginners and advanced learners. Include a full chosen routine, actual active time, comprehension, perceived challenge and voluntary return. The goal is to test the modeled timing and product hypotheses; a small pilot does not establish a causal retention uplift.

**Primary files:** existing season/live review scripts and reports, `living_story.py`, `season/director.py`, golden fixtures, browser walk, pilot events/digest, `ROLLOUT.md`.

**Done when:** an identified candidate has no observed continuity breaks or false grading in the evaluated cases; all provider failures recover honestly; sampled prose passes the declared rubric; recurring material defects are fixed and rechecked. Publish actual counts, costs, remaining uncertainty and a cohort recommendation. Verify what is already deployed before changing exposure. A zero-failure sample is not a production reliability guarantee.

### WP-134 — Proficiency claims and external assessment

**A, audit now.** Inventory level labels, forecasts, onboarding and marketing copy. Clearly distinguish self-declaration, placement estimate, syllabus coverage and demonstrated proficiency. A forecast should name the internal milestone it estimates; an “estimate” suffix alone does not justify a promise of CEFR competence. Remove or qualify unsupported comparative learning-speed claims if they exist. No audio is deployed today, so the daily practice is read, not heard. Claims must not imply listening competence until it exists.

**B, after assessment stabilizes.** Design an external calibration study using suitable official CEFR-aligned tasks, including the skills the product actually claims. DELF material can inform A1–B2 evaluation; C1 requires an appropriate C1 assessment. A few sample papers or an LLM judge alone do not validate four-skill proficiency. Define independent scoring, consent, participant sampling and the comparison rule before gathering results. Treat absent listening/speaking capability as an explicit limit on claims.

**Primary files:** `cefr_progress.py`, `level_forecast.py`, checkpoint/épreuve code, progress and onboarding copy, research protocol and results document.

**Done when A:** no learner-facing claim equates internal completion or the review's modeled speed comparison with validated CEFR attainment. **Done when B:** a documented external comparison supports the scope of any stronger claim, with limitations and disagreement rates reported. Do not block the continuity and grading repairs on completion of this study.

## 4. Delivery order and shared boundaries

**Start:** WP-123a (land the fixes, the minimal gate), and WP-133a once its cost cap is approved. WP-123b runs in parallel throughout and gates nothing.

**Wave 1: the largest learner-visible wins, small and medium.**
- WP-124a: no stranger scenes.
- WP-125A: omissions are not errors.
- WP-126: offer timing, the beginner-offer fix and the five starting points.
- WP-127 in its basic top-down form.
- WP-132A: the two story beats.
- WP-134A: the claim audit.

Review changed story lines with their exact variants and derived checks.

**Wave 2: the learning day, against one time contract.**
- WP-128 first, in its small form.
- Then WP-129 → WP-130.
- Then integrate WP-131 and WP-125B against the same budget.

**Wave 3: authoring and validation.**
- WP-124b, sized by WP-133a.
- WP-132B, before the first exposed cohort can reach the finale.
- WP-133b: the final matrix, live read, browser checks and pilot, then a documented rollout decision.
- WP-134B continues as a separate research track.

**Deliberately not in this plan:** a dedicated package for struggling learners (owner, 2026-10-04). The review's findings for them stay on record for a later round.

Keep one editor at a time for shared files. `daily_journey.py` and `journey_planner.py` are shared by recovery, timing and practice; `journey_learning.py` by practice and lifecycle; `missions.py` and `vocabulary_credit.py` by letter semantics and data repair; vocabulary endpoints/API types by placement checks and quotas. Assign those integration edits serially. This plan does not require a new architecture or monolith split before the experience fixes.

Every package handoff includes changed contracts/data, behavioral test results, screenshots for changed UI, evidence provenance, migration/repair impact where applicable and a rollback approach. Use additive state/contracts where needed, preserve in-progress journeys, and never recompute legitimate history merely to make the new progress display look better. The plan itself performs no product changes, paid calls, data repair or deployment.

## 5. Traceability to the review

| Review recommendation / omitted finding | Resolution |
|---|---|
| Decision 1: keep lost days in-season | WP-124a (reprise) then WP-124b; prerequisite-aware bridges from `required` gap moments replace blind skipping |
| Decision 2: earlier placement, top-down check, 21/24 | WP-126–127; threshold validated and visits bounded |
| Decision 3: truthful time promise | WP-128; core budget plus genuinely optional extensions |
| Decision 4: B1+ volume/interleaving | WP-129; useful work constrained by time and need |
| Decision 5: visible grammar progress | WP-130; earlier opportunities, unchanged evidence standard |
| Decision 6: unused letter word | WP-125A, promoted to immediate grading correctness |
| Decision 7: two bible edits | WP-132A; semantic clarity and honest coverage accounting |
| Decision 8: capped live read | WP-133a early baseline; WP-133b for later gaps, provider/recovery rates and the pilot |
| Decision 9: drill quotas | WP-131; normal allowance and bounded continuation, Encore preserved |
| Decision 10: level claims | WP-134; immediate wording audit and separate calibration study |
| Existing 19 fixes and CI gap | WP-123a; land, reproduce on one candidate, CI |
| Average-learner throttle oscillation | WP-131 |
| No audio / listening | WP-134A claim limit |
| Struggling learners | Deferred by the owner (2026-10-04) |
| Tentpole grammar / D7 | WP-129; complete existing required behavior |
| Advanced scene lexicon, frequency-order problems | WP-131 |
| Repetitive fallback letters | WP-125B |
| Epilogue / D8 | WP-132B |
| Overlapping match grids | WP-129; low priority within selection work |
| No observed time/return evidence; Forge and long-term schedule gaps | WP-123b, WP-128, WP-133b |
