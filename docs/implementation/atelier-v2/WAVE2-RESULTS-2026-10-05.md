# Wave 2 — results (2026-10-05)

**Branch.** `exp/wave2-integration`, built from Wave 1 (`28ae22c`). It is local and not pushed. It holds, in merge order:
- WP-125B: credible fallback letters;
- WP-131: contextual words and reachable quotas;
- WP-128: the core day fits the chosen time;
- WP-129: B1+ practice, the D7 page review, and the owner decision on A1/A2;
- WP-130A: one grammar vocabulary across surfaces;
- WP-130B: «Tenue» evidence offered on time;
- a fix to the walk harness for daylight-saving time.

**Checks on the final commit.**
- The life walk: all 15 lives pass in one run (16 min).
- The learner walk `-m walk`: 5 of 5 pass.
- Frontend: `tsc` is clean and `npm test` passes 912 of 912.
- The full suite: 6,404 passed and 14 failed. None of the 14 failures comes from this wave:
  - 10 are the baseline: `wp69` ×5, `revue_relecture`, `wp96` ×2 (they need `.env`), `wp74` and `wp76`. The last two depend on test order.
  - 4 more depend on test order and pass when run alone: `wp131` numbers, `wp78` ×2 (they fail after any test that loads a grammar catalogue) and `wp91` first-request.

## Owner decisions taken during the wave
- **A1/A2 (2026-10-04): fewer replies, more items.** Léger and Régulier ask for 2 reply exchanges, or the page's minimum if it is higher. No authored turn that routes a choice or sets a flag is ever dropped.

## Before and after (15 lives × 30 days; before = the Wave 1 after-run)

| Measure | Before | After |
|---|---|---|
| A1 journey minutes vs estimate | 12.6–13.8 vs 6.8–7.6 | 7.6–9.1 vs 9.0–9.2 |
| days over 1.2× budget (A1 / A2 / B1+) | 21–25 / 9–17 / 0–6 | 2–9 / 1–6 / 0–5 |
| practice items/day (A1 / A2 / B1 / B2 / C1) | 11.5 / 11.5 / 3.6 / 3.6 / 3.3 | 4.9–6.4 / 5.9–8.4 / 4.4–5.1 / 4.9–5.7 / 6.3–6.7 |
| units held on day 30 (strong / average / struggling) | 0 everywhere | A1 4/2/2 · A2 2/1/2 · B1 6/5/3 · B2 7/5/5 · C1 8/8/6 |
| A2 average new words / known on day 30 | 117 / 82 | 221 / 169 |
| letters in 30 days; repeats within 7 days | 13–21; up to 12 | fewer; **0** (C1 gets about 1 a month until the WP-125B letters are approved) |
| level on day 30, strong (A1 / B1 / B2 / C1) | 36 / 19 / 13 / 8 % | 43 / 33 / 28 / 25 % |

The A1 practice-item count is lower than Wave 1's 11.5, and that is intended. Honest pricing (WP-128) showed the old A1 day ran about 14 min against a 10-min budget. With the owner's decision, A1 days that introduce no new unit hold about 7.5 items; days with a rule hold about 3.5, because the rule and its Essai fill the time.

**Season reach.** A2+ lives reach 8 headline days by day 30, against 10 in Wave 1. This is a calendar effect of the walk's start date, not a regression. The unchanged Wave 1 code, started on 2026-10-05, gives the identical sequence. The cause is that gap 3 takes one more day, which moves T5 «Berlin» to day 31.

**Evidence audit (WP-130B).** Before the fix, every B1+ unit held on the Wave 2 base was held because the walk's learner typed back the hidden model sentence of a WP-129 free sentence. A free sentence that reproduces a displayed sentence is now supported production, never free use. The walk's learner now writes its own sentence. Every held unit becomes held between day 14 and day 24 after its introduction.

## Per life after Wave 2

| Life | Day (journey) | Planner's estimate | Days over budget | Drill | Letters | Onboarding (total) | All surfaces | French share | Items/day | Rules/30 d | New words/30 d | Due peak | Known words d30 | Units held d30 | Level d30 | Placement offered (day) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| a1-de-fresh strong | 7.6 | 9.2 | 2 | 3.4 | 2.4 | 0.0 | 13.4 | 86% | 4.9 | 15 | 239 | 22 | 184 | 4 | A1.1 · 43 % | — |
| a1-de-fresh average | 7.8 | 9.2 | 2 | 4.7 | 1.8 | 0.0 | 14.3 | 84% | 5.0 | 15 | 239 | 29 | 178 | 2 | A1.1 · 37 % | — |
| a1-de-fresh struggling | 9.1 | 9.0 | 9 | 2.7 | 1.5 | 0.0 | 13.3 | 83% | 6.4 | 8 | 64 | 19 | 46 | 2 | A1.1 · 13 % | — |
| a2-de-placed strong | 7.1 | 8.6 | 2 | 3.8 | 1.9 | 11.6 | 13.2 | 84% | 5.9 | 16 | 232 | 22 | 183 | 2 | A2.1 · 27 % | 1 |
| a2-de-placed average | 7.1 | 8.5 | 1 | 4.9 | 1.6 | 13.0 | 14.0 | 82% | 6.7 | 14 | 221 | 25 | 169 | 1 | A2.1 · 22 % | 1 |
| a2-de-placed struggling | 8.3 | 8.4 | 6 | 2.6 | 1.0 | 18.8 | 12.6 | 79% | 8.4 | 8 | 56 | 23 | 34 | 2 | A2.1 · 9 % | 1 |
| b1-en strong | 7.3 | 8.4 | 0 | 3.3 | 1.5 | 9.8 | 12.5 | 83% | 4.4 | 17 | 232 | 16 | 193 | 6 | B1.1 · 33 % | 1 |
| b1-en average | 7.3 | 8.2 | 1 | 5.0 | 1.1 | 10.9 | 13.7 | 81% | 4.6 | 15 | 232 | 27 | 175 | 5 | B1.1 · 28 % | 1 |
| b1-en struggling | 7.8 | 8.1 | 5 | 2.7 | 1.0 | 16.1 | 12.1 | 78% | 5.1 | 10 | 78 | 29 | 41 | 3 | B1.1 · 11 % | 1 |
| b2-en strong | 6.3 | 7.6 | 0 | 3.8 | 0.8 | 9.0 | 11.2 | 79% | 4.9 | 16 | 232 | 29 | 183 | 7 | B2.1 · 28 % | 1 |
| b2-en average | 6.5 | 7.5 | 0 | 4.8 | 0.5 | 10.2 | 12.1 | 77% | 5.1 | 16 | 232 | 32 | 180 | 5 | B2.1 · 23 % | 1 |
| b2-en struggling | 7.0 | 7.3 | 2 | 2.8 | 0.5 | 19.5 | 11.1 | 74% | 5.7 | 10 | 92 | 20 | 55 | 5 | B2.1 · 15 % | 1 |
| c1-de strong | 6.3 | 6.8 | 0 | 3.6 | 0.1 | 7.5 | 10.2 | 78% | 6.3 | 16 | 232 | 19 | 193 | 8 | C1.1 · 25 % | 1 |
| c1-de average | 6.4 | 6.8 | 0 | 5.3 | 0.1 | 8.3 | 12.1 | 76% | 6.5 | 15 | 232 | 38 | 181 | 8 | C1.1 · 24 % | 1 |
| c1-de struggling | 7.0 | 6.6 | 2 | 2.9 | 0.0 | 16.8 | 10.5 | 71% | 6.7 | 10 | 95 | 26 | 63 | 6 | C1.1 · 15 % | 1 |

## Found and fixed during integration
- **WP-128 with WP-125B and WP-131:** three practice-volume tests failed on the combined branch. WP-129's A1/A2 decision and its Forge-floor fix resolved all three.
- **The walk harness:** a whole-day offset from a real "now" just after midnight crossed 2026-10-25 (CEST → CET), and every life failed on day 22. Each walk day is now lived at local noon (`465e023`).

## Open owner questions
1. **WP-125B letters proposal:** 22 new texts, 9 letters at B1–C1, 7 follow-ups and 6 story frames. Two of the letters touch Season 1 arcs.
2. **Optional A1/A2 reply exchanges:** should they be offered («Continuer la conversation»)? That needs contract and UI work.
3. **B1 rule days:** should they also give up a reply exchange? They hold about 3 items today.
4. **Rule-card examples:** should a story reply that copies the example word for word count as supported rather than free use?
5. **Still open from Wave 1:**
   - the A1 rule-card example («vous êtes le nouveau voisin»);
   - the WP-134A wording, including whether a test-out counts as «tenue».

## Notes for Wave 3 and the record
- **Deploy:** WP-131 re-syncs the catalogue once, about 6,900 row upserts.
- **Codex conflict:** `web-frontend/pages/atelier.tsx` has the WP-128 chip estimates, and Codex edits the same file.
- **Not checked visually:** no UI from this wave was checked at 375 px in light/dark, because the preview's sign-in gate blocks it. It was checked with `tsc` and unit tests only.
