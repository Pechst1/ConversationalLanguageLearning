# WP-168 dry run: the season writer may move the story

Run on 11 October 2026 against the real provider (`gpt-5-mini`, the story engine's model) and the real image model (`gpt-image-2`, through `season.plates.paint_plate`).

Reproduce with `venv/bin/python scripts/wp168_season_writer_dry_run.py --paint`.

## What was run

- **Three lives.** Each life played all of season 1: T1 to T8, the gaps and the epilogue week, 65 days. The three lives end differently, using the s1 flags:
  - `garder`: the flat is kept, the evidence goes to Marchand only, Margaux is persuaded.
  - `partager`: the co-op, the evidence made public, Gus persuaded.
  - `laisser_partir`: the flat is sold.
- **Carrying the ending.** Each ending was carried into the life the way the engine does it (`epilogue.carry_into_live`). That gives the ending's world flags and the s1 open question.
- **`living_story.roll_over_season` on day 66.** The writer is on and may move. The world bible is the s1 world, so the city is Paris.
- **The canon the writer is given:**
  - who departed: Lila after every ending, and Margaux after `laisser_partir`;
  - two continuation rules: the cast knows the learner, and «L.» is never revealed;
  - the ending's facts;
  - the closed places: Le Mistral after `laisser_partir`.
- **Synthetic material, five rows per life, in `scripts/wp168_season_writer_dry_run.py` (`LIFE_ROWS`).** These rows stand in for what ~60 generated days would have left open: unpaid plants, unpicked branches and open promises.
  - **Caveat: the rows are biased toward the sea.** Each life has at least one row that pulls toward water. In `garder` it is a Polaroid of a port. In `partager` it is a child's drawing of a house by the water. In `laisser_partir` it is Margaux's lighthouse card and Marin's father's boat, which is canon: Marin is Breton.
  - The next run should take the material from the experience walk's lives past day 66 instead.

## Two rounds

| | Prompt | Files |
|---|---|---|
| Round 1 | The first `SEASON_WRITER_MOVING`. | `round-1/` |
| Round 2 (shipped) | Adds: «the French-speaking world is wide … a town near the old city is the timid choice», the genre is chosen on purpose and unlike the previous season's, and a road trip that re-investigates the old questions is the default to avoid. The material is the same as in round 1. | top level |

Each `life-<ending>.json` holds:
- the material rows and the canon;
- the draft: logline, setting, arcs with the row each grows from, threads, places with plate briefs, and new characters with rig parameters;
- the critic's verdict (`grows_from_material`, `fresh`, `issues`);
- the merged world as the director will read it: city, places, who is `away`, and the new cast;
- the usage.

## The drafted seasons (round 2, shipped prompt)

### `garder`: «Le port d'Odile», Marseille

- **Genre:** a mystery and a documentary.
- **The move:** it grows from `b:peintre_l` (the promise to Marchand to find «L.»), and the Polaroid points to a port. The learner goes south with Romy and Marin and is the French voice of Romy's radio documentary.
- **Arcs:**
  - «Trouver L.» ← `b:peintre_l`
  - Romy's documentary ← `p:polaroid_port`
  - Gus's unopened letter, held at a Marseille notary ← `p:lettre_gus`
  - the painting compared at a gallery ← `thread:s1:0`
- **New places:** the Vieux-Port, a café in the Panier, a gallery, the painter's house, the fish market.
- **New faces:** Antoine Delacourt, a retired docker; Céline Martin, a notary's clerk; Maïté Roché, a gallery conservator.

### `partager`: «Le mariage à Concarneau»

- **Genre:** a small-town family drama with a gentle mystery.
- **The move:** it grows from `b:mariage_camille`. The learner goes to Camille's family wedding in Finistère with Camille, Gus and Romy.
- **Arcs:**
  - the wedding and the Marchand family ← `b:mariage_camille`
  - Gus's grandmother's letters ← `p:lettres_grand_mere`
  - translating Romy's interviews ← `c:interviews_romy`
  - choosing the setting of Marin's novel ← `b:roman_marin`
- **New places:** the mairie, the église Sainte-Anne, the port, the family house.
- **New faces:** Renée Le Gall, Camille's aunt; Loïc Morvan, a boat captain.

### `laisser_partir`: «La carte et le phare», Camaret-sur-Mer

- **Genre:** a coastal mystery and a coming-of-work story.
- **The move:** it grows from `p:carte_phare`, Margaux's card «Il y a du travail ici, si tu veux». Margaux is departed and is never on stage: the card brings the learner to Brittany. The learner takes a summer job on a fishing boat, with Marin, Romy and Gus.
- **Arcs:**
  - the lighthouse ← `p:carte_phare`
  - the boat ← `b:bateau_pere`
  - the brocante van and the painting ← `b:camion_tableau`
  - the Sunday photos for Lila, now from the sea ← `c:photos_lila`
- **New places:** the port, the Men lighthouse, Yann's boat, a brocante, Margaux's house.
- **New faces:** Yann Le Guen, «Marin's father»; Brigitte Lenoir, the brocante owner; Maël, the lighthouse keeper.

Round 1, the first prompt, gave the same three spines in the north-west instead:
- **`garder`:** Le Havre, «a gentle investigative road-trip».
- **`partager`:** Saint-Malo, «a road-mystery», with «La maison d'Odile» invented there.
- **`laisser_partir`:** Le Conquet, «a quiet road-trip».

## The critic

All six drafts passed. Every draft was judged `grows_from_material: true` and `fresh: true`. The critic listed 4 to 8 concrete issues for each, and they are useful notes for the director:
- keep «L.» unrevealed;
- keep the café question closed;
- keep the departed cast off stage;
- the register of new faces against «the whole cast knows the learner»;
- maritime vocabulary at A2.

The critic missed two canon slips:
- **Marin's father as «Yann Le Guen» (round 2).** Marin is a Lévêque.
- **«La maison d'Odile» in Saint-Malo (round 1).** Odile's life was in Paris.

After the run, the writer was told to keep a relative's family name and is given the cast's facts, and the critic was told to check family facts. The structural gate now allows «Yann Lévêque» on purpose, because only the first word decides the reader's face and voice. That fix has not been re-run live.

The structural gate never fired on these drafts. In the tests it refuses:
- a move that names no material row;
- a departed traveller;
- a kept closed place;
- a new face whose first name is a cast name.

## Pictures

- **`round-1/plate-*.webp`, three plates:** the Le Havre quay, the Concarneau/Saint-Malo port, and the Kermorvan lighthouse.
- **`plate-*.webp`, two plates:** the Vieux-Port with Notre-Dame-de-la-Garde, and Yann's boat.
- **The painting itself:** each plate was painted once through the shared plate interface, in about 30 s, people-free and in the owner's style.
- **`contact-sheet.png`:** the round-2 seasons' new faces drawn from their rig parameters and standing on the painted plates. `partager`'s mairie is shown on its stand-in, the office plate, which is what a learner sees before the painter is done. Below are all eight new faces in three moods.

## Judgement

**Do the three seasons differ from season 1?** Yes, clearly, on every axis the owner named:
- **City:** none of them is Paris.
- **Genre:** a mystery and documentary, a family drama, a coming-of-work story, against s1's café dramedy.
- **The learner's situation:** radio voice, wedding guest and translator, deckhand.
- **Places:** none is a café counter.
- **People:** two or three new faces each, and one to three cast members who travel while the rest are `away`.

The cast's goals change too:
- Gus opens his letter;
- Camille brings the learner into her family;
- Marin's novel needs a setting.

«Grow only from the learner's material» does not keep the season at Le Mistral. In every draft the move is motivated by a row, and the critic agrees.

**Do they differ from each other?** Only partly.
- **Where they differ:** the three spines, people and situations are distinct and follow each ending:
  - `garder` keeps the promise to Marchand;
  - `partager` follows Camille's family;
  - `laisser_partir` answers Margaux's card.
- **Where they converge:**
  - **The French coast.** Five of six drafts go to the Atlantic or Channel coast, three of them to Brittany. Only round 2 reached Marseille.
  - **S1's mystery.** All three keep the painting or «L.» as a thread.
  - **No one leaves France.** Nobody went to Brussels, Montréal or Dakar.
- **Why:**
  - Part of this is the synthetic material, which pulled each life toward water.
  - Part is canon, which points to Brittany: Marin's father and Margaux.
  - Part is that every life shares s1's open questions, «Who was Odile», «L.» and the painting.
- **What the round-2 prompt changed:** it widened one life, Le Havre to Marseille, and changed the genres. It did not change the gravity.

**Next steps**, not done here:
- run the writer on real walk lives past day 66, whose material is the lives' own;
- consider letting the learner's own profile be material (why they learn French, where they live);
- let WP-167's news days add pulls that are not local.

The rigs are varied but repeat a few choices: a navy cap appears three times and round glasses four times.

## Spend

| | US$ |
|---|---|
| First attempt (critic refused by the provider: the prompt lacked «JSON»; fixed, and the fix covers the WP-98 critic too) | 0.016 |
| Round 1: 3 lives × (writer + critic) | 0.063 |
| Round 2: 3 lives × (writer + critic) | 0.064 |
| Plates: 5 × ~0.06 (estimate; the image call reports no cost) | ~0.30 |
| **Total** | **~0.44** |
