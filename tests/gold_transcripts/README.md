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
python scripts/gold_transcripts.py trend                      # the runs so far
```

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

`--set` takes any app setting. To compare the model that writes the day's page ahead of
time (`STORY_WRITER_MODEL`), add a `page` surface: an adapter that calls
`story_split.draw` on captured contexts (as `tests/prompt_regression/harness.py` does with
replayed answers), a `sets/page.json`, and its criteria. The meter, judge, report and
trend need no change.

## Adding an input

Take it from a live-walk report (`docs/ops/live-walks/<date>.md`), keep the learner's words
exactly as the walk wrote them, name the walk in `source`, and fill `truth`. Keep each set
between 20 and 30 items (`tests/test_gold_transcripts.py` checks it). Changing a set
changes its version in the report, so say so in the PR.
