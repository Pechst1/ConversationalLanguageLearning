# Saison 1 · «La clé d'Odile» (season bible sketch)

> **Superseded by `00-season-bible.md` (2026-09-30).** This sketch is kept as history. It is what the owner approved, with decisions S-1..S-8. Three things changed since: Odile's flat is now on the **first** floor (the fire has to reach the café), and the fire's timing is now 23:00 upstairs, 1:30 in the back room. The fire and Odile's departure move from 2022 to **March–April 2023**, so that «trois ans» is true in December 2026.

*Writers' room, 2026-09-30. A sketch for the owner to judge the premise; not yet the WP-111 bible.*

## The central question

> **Ta grand-mère t'a laissé ce qu'il y a au-dessus du Mistral, et le feu qu'il y a eu dessous. Tu le gardes, tu le partages, ou tu le laisses partir ?**
>
> Your grandmother left you what is above Le Mistral, and the fire beneath it. Will you keep it, share it, or let it go?

The three endings answer it: **Garder** (Gus's position), **Partager** (Marin's), **Laisser partir** (Lila's). You arrive to sign papers and leave. Learning French is how you learn who she was. Her last letter is addressed «Pour toi. Quand tu parleras français.»

## Odile: what really happened

- **1951.** Odile Ferrand's parents open Le Mistral. The father is from Provence and names it after the wind. Odile grows up on the third floor.
- **1970.** At 22 she leaves for love, for «là-bas». The country is never named, so it works for any learner. She never speaks French to her children.
- **2009.** Widowed, she comes back at 61 and buys the small flat above the café. Every morning she drinks a café crème at the zinc. Gus's mother waits tables there in those years, for Margaux. Odile photographs everything and writes on the back of each Polaroid («Mardi. Marin pleure devant une pub. Encore.»).
- **2019.** In her notebook she drafts «Le Mistral à nous», a plan for the regulars to buy the walls together. Forty people pledge, among them «M. M. : oui, si Margaux reste.»
- **14 March 2022.** She forgets a pan on the stove. The fire falls through the old ceiling into the café's back room. She tells Margaux: «Ne dis rien. Sinon, ils vont me prendre ma maison.» Margaux tells the insurers the fire started downstairs, in the old wiring.
- **April 2022.** Her family fetches her. She says goodbye to Margaux as if to a customer. Nobody touches the flat again.
- **2026.** She dies and leaves the flat to you. The notary calls it «modeste».

**How she created the dispute.** Margaux's false declaration fell apart. The insurer wants its money back, and Margaux fell behind on the rent. M. Marchand, who owns the building, blames «her wiring» and will not renew her lease. He is 74, cannot climb his stairs any more, and has an offer from Solvel Immobilier for the whole building, which lacks only your floor. **The truth clears Margaux of negligence, but it exposes her lie and makes Odile's estate, which means you, liable for the fire.**

## What each of them believes

- **Margaux** knows everything and keeps her promise.
- **Marchand** thinks the wiring caused the fire, and that Odile left *because of him*, after six years of Sunday lunches.
- **Gus** thinks Marchand wants to erase the café. To him Odile was the lady who called him «le petit comte».
- **Marin** thinks «Paris l'a fatiguée», an accident and a bad sign.
- **Lila** thinks «elle est partie parce qu'elle était courageuse»: you can leave and come back. She doesn't want to know more.
- **Romy** knows Odile only as a line in the fire report. She reaches the file through her story on Solvel buying up cafés.

## The three arcs through eight tentpoles

| Ep. | The key and the café | Lila and Berlin | The future of Le Mistral |
|---|---|---|---|
| 1 · Le mauvais accueil | You are taken for Marchand's sale agent. **Choice:** whom you trust with the notary's letter and Solvel's offer. | She is the only one who laughs. | Gus uses his theatrical «vous» as a weapon. |
| 2 · En haut | The Polaroid box. «Augustin, 15 ans. Il dit qu'il sera comte.» **Enquête:** her calendar is full for May 2022, so she never «planned to go home». | Funny, nosy, she stays too late. | The page «Le Mistral à nous» turns up. |
| 3 · Deux promesses | — | — | Gus: don't sell, sign the petition. Marin: put the flat in the co-op. **Convaincre:** get Gus to invite Marchand. |
| 4 · La photographie | **Reversal:** your Polaroid wall shows the fire upstairs. | Her phone lights up: Berlin. | Margaux's lie is exposed, and the flat now carries a debt. |
| 5 · Berlin | — | She tells you, or you find the crate. | Marin's plan needs her workshop. |
| 6 · L'autre côté | Marchand and his grandchild Camille give their account. **Choice:** share Odile's notebook («J'ai demandé à Margaux de mentir») or keep it. | «Encore un secret.» | Marchand once pledged «si Margaux reste». |
| 7 · Le dernier soir | The plan your choices allow: the lease, the co-op vote, or the last service. | Confession, kiss, or friendship. | **Convaincre** Gus, or Margaux. |
| 8 · Ce qu'on garde | The letter; the painting above the zinc, signed «L.» | She leaves on 8 January. | Garder · Partager · Laisser partir |

## The flags that matter

| Flag | Set in | Changes |
|---|---|---|
| `s1.letter_trusted_to` | T1 | Who stands by you in T4 |
| `s1.lila_has_key` | T2 (generated) | Where T5-B happens; the key gesture in T8 |
| `s1.promised_to` (gus · marin · both_half) | T3 | The announcement T4 interrupts; the T7 plan |
| `s1.marchand_invited` | T3 | T4 exchange 3: Marchand, or Romy |
| **`s1.fire_photo` (wall · margaux)** | **T4** | **T5: she tells you, or you discover it** |
| `s1.lila_path` (romance · friendship) | What you *express* (T2, the dinner, the apology, T5) | The colour of T5, T7 and T8; never shown as a score |
| `s1.went_with_lila_to_marin` | T5 | Marin's trust in you in T6/T7 |
| `s1.evidence_shared` (public · marchand_only · kept) | T6 | Which endings are open |
| `s1.flat_decision` (keep · coop · sell) | T7 | The ending |

**Endings.**
- **Garder** requires `marchand_only` and `keep`.
- **Partager** requires the truth made public, Gus persuaded, and `coop`.
- **Laisser partir** is chosen with Margaux: `sell`.

Each ending has a cost, and none is a fail state.

## Lila: romance and friendship

- **Her future is hers.** Both paths share the same events, and she leaves for Berlin on 8 January in every version. What changes is what her lines carry.
- **What moves the path.** Only what the learner chooses to express. Grammar never does.
- **Romance.** Restraint: paint wiped off a hand, «Pas maintenant. Mais pas jamais.» A kiss only in T7. She keeps the key.
- **Friendship.** Accomplices and private jokes («ne refais jamais l'omelette»). She gives the key back: «Tu me la redonneras.»
- **Both paths.** Her portrait shows you from behind: «Je n'ai pas encore trouvé ton visage.» The app's rule of never showing your face becomes a line in the story.
- **Later.** Camille Marchand, rooted in the 10th, is seeded in T6 and T8 through disagreement.

## Canon changes assumed (owner to confirm)

1. **Marin and Lila are flatmates and oldest friends,** not a couple. They were together for two months in 2016 and laugh about it.
2. **Marin's «demande» becomes «la proposition»:** the co-op. The ring leaves season 1.
3. **Romy's romance with you is set aside.** She becomes the journalist whose story touches the café.
4. **Marchand owns Le Mistral's building.** Gus's mother waited tables there.
