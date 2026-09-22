# WP-69 — paid live review after Wave A (2026-09-22, owner-consented)

Engine at `205268f` (WP-69/70 landed, incl. WP-70's LLM wrapper: retries only on
retryable errors, one total deadline). Budget: owner approved ≈ US$0.30; a full 14-day
A2 + B1 pair costs ≈ US$0.55 at the measured ≈ US$0.0045/request, so B1 (the weaker
band) got the full fortnight and A2 eight days, with hard caps of 45 + 22 requests.

```bash
venv/bin/python -u -m scripts.review_living_story --live --level B1 --days 14 --attempts 2 \
  --seed wp68-B1-2026-09-21 --max-requests 45 --output var/reviews/atelier-story-review-B1-wp69.json
venv/bin/python -u -m scripts.review_living_story --live --level A2 --days 8 --attempts 2 \
  --seed wp68-A2-2026-09-21 --max-requests 22 --output var/reviews/atelier-story-review-A2-wp69.json
```

| run | spend | requests | accepted | stopped on | p50 / max request |
|---|---|---|---|---|---|
| B1 | US$0.157 | 34 | **8 of 14** | day 9 — both drafts refused (`objective_too_thin` ↔ `mixed_address_register` ↔ `chapter_not_advanced`) | 16.0 s / 23.1 s |
| A2 | US$0.089 | 22 | **6 of 8** | day 7 — the review's own request cap, not a refusal | 15.0 s / 22.9 s |

Total **US$0.247** (WP-68 running total US$0.924 → **US$1.171**).

## What it means now that WP-69 exists

The review script drives the engine without a database, so a refused day still ends
the script. In production that day is now served by WP-69's authored fallback for the
band (A2 content for B1+), recorded in `plan_selection.generation_fallback` — the learner
gets a day, but a *generic* one that is not part of their story. So the engine's own
refusal rate is still the quality number to drive down:

- **B1: the thin ↔ register ↔ closed-chapter pincer still refuses a whole day** (day 9).
  The feedback shows three guards pulling at once; the retry cannot satisfy all three.
- **Variety of speech acts is still weak.** A2: four of six objectives are «tell X to
  do Y and give a reason». B1 days 1–4 are all advice to Marin; day 4 asks a B1 learner
  for «one clear sentence» (should have tripped `objective_too_thin`).
- **B1 did move arcs** (Marin → Augustin's invented château on day 5), and no turn needed
  a fallback in either run.
- Latency p50 15–16 s per request with WP-70's single total deadline; no timeouts.

## Follow-ups (engine — Codex owns `living_story.py`)
1. Give the B1 pincer an exit: when the refusal set contains ≥2 different guards, the
   retry prompt names one priority order instead of all hints at once.
2. `objective_too_thin` missed «one clear sentence» at B1 — check the word/sentence
   heuristic.
3. Measure the production fallback rate once deployed (`generation_fallback` count per
   day) and alert above 10 %.
