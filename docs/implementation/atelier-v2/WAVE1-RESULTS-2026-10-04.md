# Wave 1 — results (2026-10-04)

**Branch.** `exp/wave1-integration`, built from `cab1fb5`. It holds:
- WP-123a: the gate run and the CI text;
- WP-124a, WP-125A, WP-126, the basic WP-127 and WP-132A, which the owner approved;
- WP-133a: the paid read;
- WP-134A: the claims audit, still a proposal.

**Checks on the final commit.**
- The life walk: all 15 lives pass in one run (16 min).
- The learner walk `-m walk`: 5 of 5 pass.
- Frontend: `npm test` passes 898 of 898 and `tsc` is clean.
- The full suite: 6,228 passed and 10 failed. All 10 failures belong to other workstreams or are order-dependent:
  - `wp69` ×5;
  - `revue_relecture` ×1;
  - `wp96` ×2, which need `SERIAL_WORLD_ENABLED` from `.env`;
  - `wp74` ×1 and `wp76_latency` ×1, which fail depending on test order and pass when run alone.

## Before and after, per package (15 lives × 30 days)

| Package | Signal | Before (`cab1fb5`) | After |
|---|---|---|---|
| WP-124a | days served the off-season stranger scene | 3 (one per A1 life) | **0**; the lost day is re-read instead (1 reprise per A1 life) |
| WP-124a | season reached (headline days by day 30) | A1 8, others 10 | unchanged: A1 8, others 10 |
| WP-125A | «Use target word» errata on letters | 230 | **0** |
| WP-126 | placement first offered | day 4 (non-beginners); A1 day 5 / 16 | **day 1** (non-beginners); **never** for A1 «Nouveau» |
| WP-126 | day 1 at the declared band (B2, C1) | B1.1 | **B2.1, C1.1** |
| WP-127 | onboarding minutes, B2 strong / C1 strong / C1 struggling | 17.3 / 18.4 / 26.6 | **9.0 / 7.5 / 16.9** |
| WP-127 | known words on day 30, B2 strong / C1 strong | 167 / 168 | **197 / 196** |
| WP-127 | due-card peak (≤ 150 enforced) | 16–29 | 16–42 |
| WP-132A | the T2 «double» beat; Odile's past at A1 | — | applied; `season_check` ok and `season_levels` reports 0 problems |

Full per-life table after the wave:

| Life | Day (journey) | Planner's estimate | Days over budget | Drill | Letters | Onboarding (total) | All surfaces | French share | Items/day | Rules/30 d | New words/30 d | Due peak | Known words d30 | Units held d30 | Level d30 | Placement offered (day) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| a1-de-fresh strong | 13.8 | 7.6 | 21 | 3.5 | 4.0 | 0.0 | 21.3 | 88% | 11.5 | 16 | 237 | 21 | 200 | 0 | A1.1 · 36 % | — |
| a1-de-fresh average | 13.7 | 7.6 | 24 | 4.7 | 2.8 | 0.0 | 21.2 | 86% | 11.5 | 16 | 237 | 23 | 189 | 0 | A1.1 · 34 % | — |
| a1-de-fresh struggling | 12.6 | 6.8 | 25 | 2.6 | 2.1 | 0.0 | 17.2 | 84% | 11.6 | 8 | 63 | 20 | 39 | 0 | A1.1 · 7 % | — |
| a2-de-placed strong | 9.9 | 7.7 | 17 | 3.7 | 2.0 | 11.6 | 16.0 | 84% | 11.4 | 16 | 230 | 16 | 191 | 0 | A2.1 · 22 % | 1 |
| a2-de-placed average | 8.7 | 7.4 | 9 | 3.6 | 2.7 | 13.0 | 15.5 | 83% | 11.5 | 8 | 117 | 21 | 82 | 0 | A2.1 · 9 % | 1 |
| a2-de-placed struggling | 9.8 | 7.2 | 10 | 2.5 | 1.5 | 19.0 | 14.5 | 79% | 11.6 | 8 | 56 | 23 | 37 | 0 | A2.1 · 4 % | 1 |
| b1-en strong | 7.2 | 6.5 | 3 | 3.4 | 2.1 | 9.8 | 13.0 | 84% | 3.6 | 17 | 232 | 18 | 206 | 0 | B1.1 · 19 % | 1 |
| b1-en average | 7.6 | 6.6 | 6 | 4.8 | 1.8 | 11.0 | 14.7 | 83% | 3.6 | 17 | 232 | 25 | 190 | 0 | B1.1 · 17 % | 1 |
| b1-en struggling | 6.5 | 6.2 | 2 | 2.9 | 0.9 | 21.1 | 11.0 | 78% | 3.0 | 8 | 66 | 26 | 46 | 0 | B1.1 · 4 % | 1 |
| b2-en strong | 5.7 | 6.6 | 0 | 3.6 | 1.7 | 9.0 | 11.4 | 80% | 3.6 | 16 | 232 | 29 | 197 | 0 | B2.1 · 13 % | 1 |
| b2-en average | 5.8 | 6.5 | 0 | 5.1 | 1.3 | 10.1 | 12.5 | 77% | 3.6 | 16 | 232 | 30 | 186 | 0 | B2.1 · 13 % | 1 |
| b2-en struggling | 5.5 | 6.2 | 0 | 2.8 | 1.3 | 19.5 | 10.2 | 74% | 3.0 | 9 | 78 | 21 | 55 | 0 | B2.1 · 3 % | 1 |
| c1-de strong | 4.9 | 5.8 | 0 | 3.5 | 1.6 | 7.5 | 10.3 | 79% | 3.3 | 16 | 232 | 25 | 196 | 0 | C1.1 · 8 % | 1 |
| c1-de average | 5.0 | 5.9 | 0 | 5.2 | 1.2 | 8.3 | 11.6 | 76% | 3.4 | 16 | 232 | 42 | 186 | 0 | C1.1 · 7 % | 1 |
| c1-de struggling | 4.9 | 5.8 | 0 | 2.8 | 0.9 | 16.9 | 9.1 | 70% | 3.1 | 11 | 93 | 24 | 69 | 0 | C1.1 · 2 % | 1 |

## Found during integration and fixed

- **The WP-124a reprise and the rule step.** A reprise was treated as a tentpole and introduced no unit, so the next day's grammar plan was unchanged. One deterministic refusal therefore repeated every day. The A1 lives re-read T1 B for 28 days and met 0 rules. The fix: a reprise is a practice day (`4fea646`, with a regression test).
- **The A1 rule-card example is an owner item.** «Je suis Margaux. Et vous, vous êtes le nouveau voisin ?» (`app/data/rule_cards/fr2_A1.json`) trips the gender guard whenever a director weaves it verbatim.

## Open

- **WP-124b.** Repeated failures still re-read the same page; the WP-133a rate is 4 of 19 generated days.
- **WP-134A.** The 40 claims rows wait for owner wording decisions, including whether the test-out counts as «tenue».
- **WP-127.** Inferred credit reaches about 2,000–2,800 words at B2/C1. WP-123b should check months 2–12.
