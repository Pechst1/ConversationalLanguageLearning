# WP-133a — results of the capped baseline read (2026-10-04)

The run followed the [manifest](WP-133a-MANIFEST.md) on commit `cab1fb5`. The transcripts and the per-draft records are in [wp133a/](wp133a/).

## Counts

| Band | Generated-day attempts | Lost | Guard reasons for the lost days | Critic refused twice, draft served | Cost |
|---|---:|---:|---|---:|---:|
| A1.1 | 7 | 2 | `invalid_story_output` (d4), `repeated_situation` (d8) | 2 | US$0.2724 / 103 calls |
| B1.1 | 6 | 1 | `story_provider_failed` (d3) | 2 | US$0.2334 / 95 calls |
| C1.1 | 6 | 1 | `wrong_beat` (d10, the first gap day after T2) | 2 | US$0.2190 / 80 calls |
| **All** | **19** | **4 (21 %)** | four different reasons | **6** | **US$0.7248** of the US$3 cap |

Every lost day served the generic authored scene: `order_at_cafe` three times and `arrange_meeting` once. The C1 learner's lost day was served at B1, which is the authored ceiling. These are the F-5 stranger scenes that WP-124a removes. The 09-30 A2 read lost 3 of 8 generated days. A rate of 4 in 19 on the current code says the failure is not rare, and WP-124b's bridges are needed.

## Rule in scene (`grammar_plan.introduce`)

Each line below is one draft; a day may have two.
- **A1:** 3 of 7 drafts carried a unit to introduce. 2 of those 3 wove it (2 uses, with the question inviting it). The 3rd («Un, une, des») did not. The other 4 drafts had no unit, because no introduction was planned for those days.
- **B1:** 1 of 8 drafts carried a unit («Raconter : imparfait, passé composé, plus-que-parfait»), and it did not weave it (0 uses).
- **C1:** none of the 5 drafts carried a unit.

**Finding.** On generated days the plan rarely carries an introduction: at the practice-day cadence, only 4 of 20 drafts did. Where it does, compliance is 2 of 4. `grammar_weave_gap` is only a hint, so a draft that does not weave the rule is still accepted. WP-129 should not assume that generated days teach today's unit.

## Critic

At every band, the critic twice refused a draft and the refused draft was served anyway: 6 times in 19 attempts. The refusals asked for a visible change at the end of the page, for example «Make the day's meaningful change visible», «Rendre la différence explicite», or «Montrer le radiateur». This is a prose-quality signal for WP-133b, not a failure.

## Sizing

- **WP-124b:** at about 1 lost day in 5, a 59-day season loses about 9 days. Two failures in a row are plausible within a gap. Bridges are needed for every gap that holds a gate, not only for a few.
- **WP-129:** practice cannot rely on a generated scene to carry the new unit. The core journey must provide it.
- **The prose read** against the manifest's rubric has not been done yet. The transcripts are kept for it, and it belongs to WP-133b.
