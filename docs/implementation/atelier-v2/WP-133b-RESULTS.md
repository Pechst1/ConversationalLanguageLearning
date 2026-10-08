# WP-133b: results of the capped live read (2026-10-06)

The read followed the [manifest](WP-133b-MANIFEST.md) on `exp/wave3-integration` at `667df06`. That head holds Waves 1 to 3 and the owner-approved bridges, epilogue and letters. The transcripts and the records for each run are in [wp133b/](wp133b/).

**Cost: US$1.63 of the fresh US$4 cap** (approved on 2026-10-06), over 452 calls.

**The first attempt on 2026-10-05.** The report writer crashed on the first WP-124b bridge page, after the paid calls. The transcripts and the spend total were lost. The per-run caps bound that attempt's spend at **≤ US$3.10**, and it was most likely under US$1; only the provider's usage page can confirm it. The harness has since been fixed (`c108b76`): the report is written after every day, the spend after every call, and a crash keeps what the run had.

**Runs 7 and 8 first failed on every call** (`story_provider_failed`, no spend), straight after runs 1 to 6. A single test call afterwards succeeded, and both runs passed on retry, so the cause was transient, probably rate limiting. The figures below are from the retries.

## Counts

| Run | Band, days | Generated-day attempts | Lost | Re-read | Bridge | Jump to the next tentpole | Critic refused twice, draft served | Drafts with today's unit / woven | Cost |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | A1, 1–10 | 6 | 0 | 0 | 0 | 0 | 2 | 10 / 4 | 0.262 |
| 2 | B1, 1–10 | 6 | 3 | 2 | 1 | 0 | 1 | 0 / – | 0.198 |
| 3 | C1, 1–10 | 6 | 3 | 2 | 1 | 0 | 2 | 0 / – | 0.220 |
| 4 | A2, 1–10 | 6 | 1 | 1 | 0 | 0 | 2 | 6 / 1 | 0.234 |
| 5 | B1, 25–32 (seeded) | 4 | 4 | 2 | 1 | 1 | 0 | 0 / – | 0.157 |
| 6 | A1, 33–41 (seeded) | 5 | 4 | 2 | 0 | 2 | 1 | 0 / – | 0.198 |
| 7 | C1, 42–50 (seeded) | 6 | 2 | 1 | 0 | 1 | 1 | 0 / – | 0.246 |
| 8 | B2, 51–62 (seeded) | 3 | 2 | 1 | 0 | 1 | 0 | 0 / – | 0.119 |
| **All** | | **42** | **19 (45 %)** | **11** | **3** | **5** | **9** | **16 / 5** | **1.634** |

- **Provider failure rate.** Days 1–10 lost 7 of 24 generated days (29 %), against 4 of 19 on 2026-10-04. The seeded later runs lost 12 of 18 (67 %).
- **The seeded runs carry a limitation.** `jump_to_day` starts a learner on the default flags, so part of their `wrong_beat` / `chapter_not_advanced` losses may come from a state no real learner reaches. That has not been separated out yet.
- **Recovery rate: 19 of 19.** Every loss recovered honestly:
  - 11 re-reads;
  - 3 bridges (g1 ×2, g4);
  - 5 jumps to the next tentpole, made only where no required moment was owed.
- **What never happened:** no stranger scene, no Berlin season, no reset, and never two re-reads in a row. The finale reached the epilogue, and the continuation followed.
- **Guard reasons for the losses:**

  | Reason | Count |
  |---|---:|
  | `wrong_beat` | 5 |
  | `chapter_not_advanced` | 4 |
  | `invalid_story_output` | 3 |
  | `resolution_repeats_turn` | 2 |
  | `mixed_address_register` | 2 |
  | `unknown_panel_character` | 2 |
  | `objective_too_thin` | 1 |

- **Rule in scene.** Only A1/A2 generated days carried a unit to introduce (16 drafts), and 5 wove it in (31 %). B1+ generated days carried none. This confirms WP-133a: the core journey, not the scene, must teach the unit (WP-129).
- **The critic** refused 9 drafts twice, and they were served anyway, about 1 in 3 generated days.

## Hand read against the rubric (6 of the 23 generated days, read in full)

| Day | Continuity / register | Premise | Teacher voice | Progress | Level | Reactions |
|---|---|---|---|---|---|---|
| A1 d3 «La même chose ?» | **Fails.** Margaux asks «Je suis Margaux et vous êtes… ? Vous êtes l'héritier ?»: she switches to «vous» after T1, re-introduces herself, and «l'héritier» marks the learner's gender. This is the A1 rule card's example woven in verbatim. | repeats T1 | ok | weak | ok | ok |
| A1 d4 «Romy pose la question» | Romy says «vous» where the gap's register rule says «tu». «qu'en pensez-vous de Solvel» is ungrammatical. | ok | ok | ok | ok | ok |
| C1 d7 «Le cadeau» | Lila: «pauvre toi, **gelé**». The resolution: «tu n'es pas encore **décidé**». Both agree with the learner's gender, and the guard does not check reactions or resolutions. | ok | ok | ok | ok | partly |
| C1 d48 «Ce qu'on donne» | ok | ok | ok | ok | ok | **Fails.** Lila echoes the learner («Merci pour la soupe»), says «Pardon, je reste ou resterai encore un peu ?», and keeps the cactus she has just given away. |
| B2 d62 (after the epilogue) | **Fails, blocking.** The setup says «le matin après le départ de Lila», yet Lila stands on the quay and speaks. «de la canal» is wrong. | ok | ok | ok | ok | ok |
| B2 d62 (continuation) | The continuation does know the epilogue's last image, the lit window on the rue de Lancry, and the question of «L.». | | | | | |

The learner's replies are the harness's scripted lines, so they never answer the task. Reactions are therefore judged only on their own coherence.

## Blocking findings, before any cohort
1. **The continuation brings back a character the ending removed** (Lila after «Laisser partir» / Berlin). WP-132B's `after_finale` block reaches the director, but nothing enforces it. A deterministic guard is needed for cast who are gone.
2. **The A1 rule-card example is woven in verbatim.** «Je suis Margaux. Et vous, vous êtes le nouveau voisin ?» yields a «vous» from a «tu» character, a gendered noun, and a stranger re-introduction. This is the owner item from Wave 1, now confirmed with the real model.
3. **Gender agreement in the reaction and resolution lanes is not guarded** («gelé», «décidé»).
4. **Reply lanes echo the learner, or swap roles** (C1 d48).

## Recommendation
**No cohort yet.** Recovery works: all 19 losses were honest, with no stranger scene and no reset. Prose continuity after the finale and gender agreement in the reply lanes are not yet acceptable. Fix findings 1–4, then repeat runs 1, 3 and 8 at about US$0.60 in all. The higher loss rate in the seeded later runs needs separating from the `jump_to_day` artefact first: play a learner there through real days, or seed the flags of a real life. A zero-loss sample would still not guarantee production reliability.

## Re-read after the fixes (2026-10-06, `861d0b6`, US$0.61)

The four findings were fixed:
- **Findings 1 and 2** in `exp/fix-director`:
  - departed cast never appear on the page after the finale;
  - the A1 être example is now «Je suis au café. Et toi, tu es où ?», and two other examples were fixed;
  - the season's «tu» register is enforced per character;
  - nouns that would give the learner a gender are caught.
- **Findings 3 and 4** in `exp/fix-lanes`:
  - agreement is checked on reactions, resolutions and summaries;
  - a reaction that echoes the learner is caught;
  - the voice lane is told who is who;
  - the self-repair question no longer puts the learner's «je» in a character's mouth.

Runs 1, 3 and 8 were read again under caps of US$0.40, 0.40 and 0.30. Transcripts: `wp133b/reread-r*`.

| Run | Generated-day attempts | Lost | Recovery | Cost |
|---|---:|---:|---|---:|
| 1 A1, days 1–10 | 7 | 2 (`two_hander_crowded`, `invalid_story_output`) | 2 re-reads | 0.260 |
| 3 C1, days 1–10 | 6 | 3 (`objective_too_thin`, `invalid_story_output`, `wrong_beat`) | 2 re-reads, 1 bridge | 0.245 |
| 8 B2, days 51–62 | 3 | 3 (`gendered_agreement`, `invalid_story_output`, `wrong_beat`) | 2 re-reads, 1 jump to T8 | 0.108 |

**The findings did not recur.**
- **Tooling.** A scan of every page and reaction in the three runs found none of the following:
  - agreement with the learner;
  - a gendered noun for the learner;
  - «vous» from a «tu» character;
  - a reaction that echoes the learner;
  - Lila on the page after T8.
- **A1, day 3.** The day that failed before now reads «Tu restes ? Ça me va. Prends ce que tu veux, mais reste.»: Margaux says «tu», and no rule-card example appears.
- **The guard at work.** One B2 draft was refused for `gendered_agreement` and recovered.

**What the re-read could not show.**
- **The continuation day after the epilogue (day 62) was lost** (`wrong_beat`) and re-read, so finding 1 was not exercised live. The deterministic guard and its integration test cover it.
- **Roles and objects** are a prompt-only fix. No swap appeared in these runs, but the sample is small.

**The loss rate stays high: 8 of 16 attempts.** It was 19 of 42 before. Every loss recovered honestly. The recurring reasons, `invalid_story_output`, `wrong_beat`, `objective_too_thin` and `two_hander_crowded`, call for a director and prompt pass of their own, not for weaker guards.

**Recommendation, updated.** The blocking prose findings are resolved in the sample. Before a cohort:
1. Reduce the generated-day loss rate.
2. Read one continuation day after the epilogue live, about US$0.10.
3. Separate the `jump_to_day` effect from the losses in the seeded runs.
