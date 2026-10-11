# Variety baseline, October 2026 (WP-164)

What a learner sees twice, measured before WP-166 changed the decks, and again after it.

## How it is measured

`scripts/variety_report.py`, run on demand. It is not part of the test run; its metric
functions are unit-tested in `tests/test_variety_report.py` on small fixtures.

```
PY=venv/bin/python
$PY scripts/variety_report.py --walk --days 15 \
  --evidence docs/implementation/atelier-v2/evidence/wp149-confirmation \
  --evidence docs/implementation/atelier-v2/evidence/loss-rate-2026-10-07
```

Two kinds of life feed it.

- **Walk lives.** The experience walk (`tests/test_experience_walk.py`), now recording each day's
  scene (place, speaker, premise, opening, season premise id, complication, every line). The
  baseline plays **3 lives × 15 days** (A1 average, A1 strong, B1 struggling), which takes
  **about 45 s**, far under the 10-minute budget. Two lives share a band on purpose: the season's
  pages are worded per band, so only same-band learners can show day-N sameness.
  **These lives use the fake provider.** Its director cycles seven places, picks the first premise
  the brief lists, and opens every generated page on «Il pleut sur le canal.» What the walk
  measures on generated days is what the brief offers and the guards allow, never what a model
  writes.
- **Paid evidence.** The season transcripts of WP-136 (`evidence/loss-rate-2026-10-07/run*`, top-ups)
  and WP-149 (`evidence/wp149-confirmation/a1`, `b1`): real generated days. The free `dry*` runs
  are left out. The transcripts do not print a generated day's `location_id`, so its place is
  **inferred from the first panel's description and the premise** (the earliest place word wins).
  Tentpole places come from the season files. Complications are not printed, so that column is 0.

Per learner the report counts the share of scenes per place (and scenes that showed a borrowed
plate), the 5-day windows in which Le Mistral took more than 2 days (WP-166's cap), the longest
run of days in one room, repeated (character, place) pairs, repeated openings (the first narration
sentence, normalised), repeated premises (the season premise id, else the premise text) and
complications, and sentences of four words or more read on two different days. Across learners it
gives the mean Jaccard overlap of day-N sentences, tentpole and generated days apart, for every
pair and for same-band pairs.

## Baseline (before WP-166)

### Walk lives (fake provider), 3 lives × 15 days

| Learner | scenes (gen.) | Mistral share (gen.) | 5-day windows over the Mistral cap | places (gen.) | longest room run | repeated pairs | repeated openings (gen.) | repeated premises | repeated complications | text seen twice | borrowed plate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a1-de-fresh-average | 15 (9) | 20% (11%) | 0 of 11 | 9 (6) | 2 × le_mistral | 1 over 1 pairs | 8 (8) | 0 | 0 | 5 | 7 |
| a1-de-fresh-strong | 15 (9) | 20% (11%) | 0 of 11 | 9 (6) | 2 × le_mistral | 1 over 1 pairs | 8 (8) | 0 | 0 | 5 | 7 |
| b1-en-struggling | 15 (9) | 13% (0%) | 0 of 11 | 9 (6) | 2 × le_mistral | 2 over 2 pairs | 8 (8) | 0 | 0 | 6 | 8 |

Across learners: tentpole days 37 % (18 pairs), generated days 81 % (27 pairs); same-band pairs
tentpole 100 % (6), generated **100 %** (9). Same-band pairs opening day 1 on the same sentence:
**100 %**. Pairs of lives staging the same season premise on a generated day N: **81 %**.

### Paid evidence (real model)

| Read | scenes (gen.) | Mistral share (gen.) | 5-day windows over the Mistral cap | places (gen.) | longest room run | repeated pairs | repeated openings (gen.) | repeated premises | text seen twice | borrowed plate |
|---|---|---|---|---|---|---|---|---|---|---|
| WP-136 C1 (run1) | 10 (6) | 50% (50%) | 3 of 6 | 5 (3) | 5 × le_mistral | 3 over 2 pairs | 0 | 2 | 2 | 4 |
| WP-136 B1 (run2) | 8 (5) | 38% (0%) | 0 of 4 | 2 (1) | 5 × marin_lila_flat | 3 over 1 pair | 1 | 1 | 6 | 0 |
| WP-136 A1 (run3) | 10 (5) | 50% (60%) | 3 of 6 | 5 (3) | 5 × le_mistral | 2 over 1 pair | 0 | 0 | 2 | 3 |
| WP-149 A1 | 10 (6) | 60% (67%) | 4 of 6 | 4 (3) | 5 × le_mistral | 3 over 1 pair | 0 | 1 | 1 | 4 |
| WP-149 B1 | 8 (5) | 50% (20%) | 1 of 4 | 2 (2) | 3 × le_mistral | 3 over 1 pair | 0 | 2 | 1 | 4 |

Across learners: tentpole days 47 % (14 pairs), generated days 0 % (23 pairs); same-band pairs
tentpole 100 % (6), generated 0 % (11). Same-band pairs opening day 1 on the same sentence:
**100 %**. Pairs of reads staging the same season premise on a generated day N: **60 %**. Generated
days with no premise id (a day of the director's own): 8 of 27 in the five tabled reads.

### What the baseline says

1. **The real model already writes different generated days for different learners** (0 % shared
   sentences on generated days). Generated-day sameness across learners is a fake-provider artefact.
2. **Le Mistral is the room.** In the real reads it takes 50–60 % of scenes and up to two thirds of
   the generated ones; in 11 of 26 five-day windows it took 3 days or more; four of five reads have a
   5-day run in one room. Only 1–3 places are visited on generated days.
3. **Premises repeat inside a gap:** the director comes back to the same premise id on 2–3 days
   (`la_dispute` three days running in WP-149 B1, `le_billet` and `romy_enquete` twice in C1).
4. **Day 1 is the same text for every learner of a band** (100 %), by design until now.
5. **Borrowed plates:** 3–4 scenes in 10 show another place's plate (Odile's flat, the stairwell and
   the quai borrow); WP-165 owns that number.

### The numbers each package intends to move

| Package | Number | Baseline | Target |
|---|---|---|---|
| WP-165 | borrowed-plate scenes | 3–4 in 10 | 0 |
| WP-166 | Mistral share of generated days | 50–67 % (real) | ≤ 40 %, and no 5-day window over 2 |
| WP-166 | places on generated days | 1–3 per 5–6 days | ≥ 4 |
| WP-166 | repeated premise ids per gap | 1–2 | 0, unless the gap's required moment is retried |
| WP-166 | same-band day-1 opening | 100 % | 0 % (the authored opening only as the fallback) |
| WP-167 | news days carrying a headline mechanic | 0 | 1 day in 2 generated days (owner decision 5) |
| WP-168 | places of a written season outside S1's 22 | 0 | owner decision 4: may move |

The `repetition_budget` thresholds are the owner's call after reading this table (§3 decision 1).

## After WP-166 (same lives, same length)

### Walk lives (fake provider), 3 lives × 15 days, ~50 s

| Learner | scenes (gen.) | Mistral share (gen.) | 5-day windows over the Mistral cap | places (gen.) | longest room run | repeated pairs | repeated openings (gen.) | repeated premises | repeated complications | text seen twice | borrowed plate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a1-de-fresh-average | 15 (9) | 20% (11%) | 0 of 11 | 9 (6) | 2 × le_mistral | 1 over 1 pairs | 8 (8) | 0 | 0 | 5 | 7 |
| a1-de-fresh-strong | 15 (9) | 20% (11%) | 0 of 11 | 9 (5) | 4 × boulangerie | 2 over 2 pairs | 8 (8) | 0 | 0 | 5 | 9 |
| b1-en-struggling | 15 (9) | 13% (0%) | 0 of 11 | 9 (5) | 4 × boulangerie | 3 over 3 pairs | 8 (8) | 0 | 0 | 6 | 9 |

Pairs of lives staging the same season premise on a generated day N: **81 % → 18 %**. Across-learner
text overlap, openings and day 1 did not move (37 %/81 % and 100 %).

- **What moved, and why.** The brief now deals each gap's premises in a per-learner order. The fake
  stages the first premise it is shown, as a model's first-item bias would, so learners stopped
  staging the same premise on the same day. The wider decks also stop the premises running dry:
  before, every life had two generated days in gap 2 with no premise left; after, none.
- **What could not move.** The fake writes the same lines every day («Il pleut sur le canal.»,
  «Tu as une minute ?») and cycles seven places. It reads neither the novelty memory nor the
  place rule, so openings, text overlap and the Mistral share are the fake's own. The «4 ×
  boulangerie» runs are a bottle chapter dealt by a thread id that is random per run: run-to-run
  noise, not this change.
- **Day 1 in the walk** is still the authored opening for everyone, by design: the walk runs with
  the model off, and the authored opening is the fallback.

### Real model (the paid check, US$0.199, `evidence/wp166-variety/`)

| Number | Before (WP-136/WP-149 reads) | After (WP-166 check) |
|---|---|---|
| Same-band pairs opening day 1 on the same sentence | 100 % | **0 of 6** pairs among the four new openings |
| Mistral share of generated days | 50–67 % per read | **1 of 4** (the gap's required moment, set there) |
| Places on generated days | 1–3 per read | 3 in 4 days (the studio, the Mistral, the back room) |
| Generated days of the director's own (no premise id) | 8 of 27 | 2 of 4 (both in gap 5, which has no required moment) |
| Repeated premise ids | 1–2 per read | 0 |

Four generated days and four openings are a sample, not a rate. The judgment of substance against
wording is in `evidence/wp166-variety/README.md`. In short: the openings and the gap-5 days differ in
situation, not only in wording; the cast's running gags (Marin's grandmother, Gus performing)
repeat by design; and gap 1's days follow its required schedule.

### Not done here

- The `repetition_budget` walk check waits for the owner's thresholds.
- `SHAPE_DECK` keeps its six cards. A second «letter» and «two_hander» would change every
  learner's seeded chapter shapes, and the guards that check those shapes are another package's
  risk.
- A paid run of 6+ consecutive gap days would measure the place spread and the novelty memory
  over a full gap. About US$0.30.
