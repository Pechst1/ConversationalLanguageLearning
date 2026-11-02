# Gold transcripts

Fixed learner inputs, taken from the live walks, run every Sunday against the production
prompts and models and scored by a judge on fixed written criteria. A story fix counts as
proven when it moves its surface's score here.

| surface | what runs (production code) | inputs |
|---|---|---|
| `scene` | the scene's reply lanes (`story_lanes.run_reply_lanes`: the grade with its correction, and the character's reply) | 28 |
| `forge` | La Forge free text: the Atelier corrector's sentence round, then the second-check merge (`_merge_relecture`) | 28 |
| `courrier` | the Courrier correspondent's reply (`MissionConversationService.respond`) | 24 |
| `correction` | the correction under a letter (`MissionCorrectionService.correct_submission`) | 26 |
| `page` (asked for, not weekly) | the night writer's page written ahead of time: `story_split.draw` (planner, author, aids) inside the production retry loop with the story critic and the scene guards, on a captured `story_context()` | 24 |
| `day` (its own weekly run) | a whole day of acts (Phase 2 «Folge in Akten»): the page («Le fil»), then each later act an Intensif learner at the day's level plays («Le soir»; on B1 also «À côté»), each written as the night writes it (`living_story.draft_later_act`: planner, author, aids, the critic reading it as an act and dropping it when it refuses). As at night, no act is written after a dropped one | 3 days (A1, A2, B1), one a week |

The judge of the weekly run is `claude-sonnet-5-5` (31 Oct: on the same answers it agreed
with `gpt-6.1-sol` on 87–91% of verdicts and scored 2–7 points lower). The script gives
`ANTHROPIC_API_KEY` the environment's `ATELIER_ANTHROPIC_API_KEY`. The `page` surface is
judged by `gpt-6.1-sol` (a Claude judge is refused there: the writer is a Claude model) on
the story judge's questions (`app/services/season/story_judge.py`) rated 1–5; a page's score
is the mean of (rating − 1) / 4, and the report adds days lost and seconds per page against
the prefetch's 330 s. A judge change restarts the trend, like a criteria change.

The `day` surface is judged the same way, act by act: each act is a page of its own on the
story judge's questions, and a later act is also asked «new» against the day's first act
(`story_judge.ACT_NEW`: the question is new, and the place or the lead changes). A dropped
act scores 0 and the acts after it are not written; a day's score is the mean of its acts'.
The report adds a table per act: written or dropped (and why), lead and place, seconds,
cost, the median rating per question, the story judge's gate on that act alone and its mean
rating against «Le fil». The day has a criteria version of its own
(`criteria.OWN_VERSION`), so its runs never move the weekly trend.

## Files

- `sets/<surface>.json`: the inputs. Each item names its walk (`source`) and whether it is
  quoted verbatim or reconstructed around the fragments the report quotes, and carries a
  `truth` block: the real errors, whether the learner refuses, what is off-script. The
  judge is told the truth; it is never told what the app answered on the walk night.
- `criteria.py`: the criteria, each a yes/no question. `check` criteria are decided in code
  (did a fallback show, does the verdict match the truth, are quoted words the learner's);
  `judge` criteria go to the judge model. Editing a criterion changes `CRITERIA_VERSION`,
  and the trend only compares runs with the same version.
- `surfaces.py`: one adapter per surface, driving the production functions with the model
  client handed in. No database: cost-ledger writes are dropped, lookups find nothing.
- `runner.py`: the spending meter, the production profile (`render.yaml`'s values for
  `atelier-api`), the judge, the scoring and the report.

## Running

```
python scripts/gold_transcripts.py plan                       # no key, no spend: calls and worst-case cost
python scripts/gold_transcripts.py run --max-usd 1.5 --post   # the weekly run (posts on #121)
python scripts/gold_transcripts.py run --surface day --max-usd 2 --post   # the week's day of acts (its own comment)
python scripts/gold_transcripts.py trend                      # the runs so far
```

The day of acts runs on its own (it refuses to share a run with another surface): one day
of `sets/day.json` a week, in turn by ISO week (`--date` picks the week, `--id` names a day
and is not posted). It writes an act only while the act at its dearest and the judge's
readings still fit under the cap (`surfaces.ACT_AT_MOST_USD`); the rest are reported as not
written. What the night writer costs is kept in `runner.NIGHT_WRITER_USD` from these runs:
`plan` prices a day with it, and `tests/test_story_acts_budget.py` checks render.yaml's spend
bounds against the writer it names, so a writer nobody measured here cannot write a night.

The run needs `OPENAI_API_KEY` (and `ANTHROPIC_API_KEY` for a Claude model), refuses
without `--max-usd`, refuses a cap above US$2 and refuses inside CI. Every call, the app's
and the judge's, is priced before it is sent and refused once it could pass the cap; the
items left are reported as «not run». A full run costs about US$0.40–0.60.

Scoring: each item scores the share of its applicable criteria it passes; an item whose
answer was a fallback (a «second check stopped», a stock Courrier line, a failed lane)
scores 0 and is not sent to the judge. A surface's score is the mean over its items, 0–100.

The report goes to the night-shift digest issue (#121) as its own comment, with a hidden
`<!-- gold-scores {...} -->` line; those lines are the history the trend reads.

## Comparing models (the night writing model, Phase 2)

Run the same inputs with other settings under another label; a comparison run is kept out
of the production trend and is not posted unless asked:

```
python scripts/gold_transcripts.py run --label luna-vs-haiku --set STORY_LIVE_MODEL=claude-haiku-5-5 --max-usd 1
python scripts/gold_transcripts.py run --label sonnet-judge --judge-model claude-sonnet-5-5 --max-usd 1
```

`--set` takes any app setting. The night writer (`STORY_WRITER_MODEL`) is compared on the
`page` surface:

```
python scripts/gold_transcripts.py run --surface page --label writer-opus \
    --set STORY_WRITER_MODEL=claude-opus-5-5 --set STORY_WRITER_REASONING_EFFORT=medium --max-usd 1.5
python scripts/gold_transcripts.py rejudge var/gold/<date>-production.json --judge-model gpt-5.5 --max-usd 1
```

A page costs about US$0.04 on Haiku 5.5, US$0.21 on Sonnet 5.5 and US$0.30 on Opus 5.5
(31 Oct, critic included). The page contexts are recaptured with
`GOLD_CAPTURE_PAGES=1 python -m pytest tests/gold_transcripts/test_capture_pages.py` when the
story context changes shape. `rejudge` scores a saved run's answers with another judge and
prints how often the two agree: run it before changing the judge.

## Adding an input

Take it from a live-walk report (`docs/ops/live-walks/<date>.md`), keep the learner's words
exactly as the walk wrote them, name the walk in `source`, and fill `truth`. Keep each set
between 20 and 30 items (`tests/test_gold_transcripts.py` checks it). Changing a set
changes its version in the report, so say so in the PR.
