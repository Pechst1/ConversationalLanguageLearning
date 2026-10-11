# WP-166: paid check of the varied first day and the invented gap days (2026-10-11, US$0.199)

**Setup.** Branch `wp/166-variety-decks`, model `gpt-5-mini` through `LLMService`, every call
counted against a hard cap (`tests/test_season_one.py::_live_model`). Harness:
`tests/test_wp166_paid_check.py` (skipped unless `WP166_OUT` is set). Free dry runs of both parts
came first.

| Run | What | Calls | Spend |
|---|---|---|---|
| openings 1 | 3 day-1 openings (A1 de, B1 en, C1 de) | 5 | US$0.0144 |
| openings 2 | the same, after the fixes below | 3 | US$0.0088 |
| openings 3 | the same, after the second fixes (`openings.md`, `openings.json`) | 3 | US$0.0091 |
| days A1 | A1.1, days 1–4: T1 A (opening written inline), T1 B, g1.1, g1.2 (`a1/`) | 29 | US$0.1044 |
| days B1 | B1.1, days 35–36 (season jump): g5.1, g5.2, a gap with no required moment (`b1/`) | 13 | US$0.0623 |
| **Total** | | 53 | **US$0.199** |

## Day 1: four openings, different in substance

| Learner | Hour, weather | Where, doing what | The room the learner walks into |
|---|---|---|---|
| A1 de (`openings.md`) | 19:30, drizzle | gare de l'Est, suitcase, envelope, key | an improvised scene, Gus «Hier je jouais dans la rue» |
| B1 en (`openings.md`) | 19:50, mild | the quai, photographing the red neon for someone at home | a cheese-naming game, Gus cheating, Lila catching him |
| C1 de (`openings.md`) | 18:10, rain and wind | climbing out of the metro at Jacques-Bonsergent | a quiz night only Margaux takes seriously («Vingt et une. Et pas un mot de triche.») |
| A1 en, in the real day (`a1/A1.1.md`, day 1) | 17:40, mild | gare de l'Est, asking a taxi for the quai de Valmy | a football match on the radio, «Ils vont perdre encore.» |

Each opening hands over to T1 as written (`a.p3` onward: the cicada key, Gus's mistaken identity,
Camille at the door). No two share a sentence; the authored opening («Il pleut. Tu as une valise…»)
is what every learner of a band read before.

**Honest judgment.** The situations differ in substance: the hour, the weather, the place of
arrival and what the regulars are doing are different evenings, not rewordings. What repeats is
character: Marin quotes his grandmother in all four rooms and Gus performs in all four. Those are
the cast's running gags, and the prompt names them, so this is wording-level sameness. Small
defects remain: the B1 visual says «rain-slick street» on a mild evening (a direction, not a learner
line); the C1 Gus still mentions «le duc» from the authored anecdote; the A1 opening ignored its
spark's hour and weather, which it is allowed to do.

**What the first two runs found, and what changed.**
- Run 1 wrote 1 of 3. A1 wrote a caption too long for A1, then a 500-character direction (a schema
  failure). B1 gave speakers as «Gus», «Marin» instead of ids, then a null caption. C1 was written,
  but Gus greeted the newcomer («Vous arrivez toujours au meilleur moment»).
  - Fixed: names map to ids, a long direction is cut, a null caption is empty, the word limits are
    explicit, a greeting is refused, and a shape slip is retried once.
- Run 2 wrote 3 of 3, but they were too alike. Two of three arrived under the café's awning
  counting house numbers (one random spark drawn twice). All three rooms gossiped about «someone
  with a key» (the prompt suggested it). C1's room copied the authored panel (Gus on the bench,
  Marin's spoon, Lila's chin), because the authored panels were passed as «avoid».
  - Fixed: 20 arrivals tied to five places, 20 room situations, no key gossip, and a short
    do-not-reuse list of motifs instead of the authored text.

## Gap days: invented when the gap lets it

- **A1, g1.1 «La soupe au radiateur mort»** is set in the learner's studio. It is the gap's
  `soupe_de_marin` premise, twisted: the boiler, Lila already there with a mug, Gus in the
  doorway.
- **A1, g1.2 «La même chose ?»** is the gap's required moment, at the Mistral. Its premise is set
  there, so it is exempt from the cap.
- In gap 1, three of five days are required moments, so invention has little room.
- **B1, g5.1 «La carte sur la table»** has premise id **null**. It is an invented day in the back
  room: Bastien measuring, Gus throwing Bastien's cards like confetti, Marin's far breton, and
  the learner asked to get Bastien to come back «calmly», with a condition. The new complication
  card «Bastien leaves his card on every table, and Gus collects them all» sparked it.
- **B1, g5.2** continues the same chapter as its complication. Bastien threatens to sign today.
  The new small moment `radio_plus_fort` (Margaux turning the radio up whenever his laser beeps)
  is staged.

**Judgment.** The B1 days are a situation no deck lists, built from a spark and the gap's threads.
They differ in substance, not wording. The A1 days took the deck's premises, as gap 1's required
schedule makes them. Across the four gap days the places were the studio, the Mistral (required)
and the back room twice: a Mistral share of 1 in 4 generated days, against 50–67 % in the
WP-136/WP-149 reads. This is a small sample: four days, not a rate.

## Defects seen that are not WP-166's (for follow-up)

- «Tu as l'air congelé» passed the gender guard: `congelé` is not in its adjective list.
- g1.1's premise mixes «vous êtes au milieu du salon» with «tu».
- Bastien says «Toi, tu peux…» and then «Restez» to the learner. He has no season register.
- g5.1's premise has «Toi dois convaincre» (grammar).

Raw output: `openings.json` / `openings.md`, `a1/A1.1.{md,json,spend.json}`,
`b1/B1.1.{md,json,spend.json}`.
