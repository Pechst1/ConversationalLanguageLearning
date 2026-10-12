# WP-167: paid read of news days (11 October 2026, about US$0.44)

**Harness.** `tests/test_wp167_live_news_day.py`, which is skipped unless `WP167_OUT` is set.
- A learner is put on a season-1 gap day (`season.admin.jump_to_day`) with a news day due.
- The director writes the day from that evening's real headlines: 141 fresh French items from the 10 registry feeds, all of them, with no topic filter (`run2/headlines.json`).
- The pick, the director and the critic are the real models (`gpt-5-mini`, dual drafts, as in production).
- The day's plate is then painted with `season.plates.paint_plate` (`gpt-image-2`, medium, 1536×1024).
- No turns are played: the read covers the page, the headline, the credit and the plate.

```
WP167_OUT=<dir> SEASON_REPORT_LIVE=1 SEASON_REPORT_MAX_USD=0.8 WP167_BANDS=A2.1:4,B1.1:12,C1.1:20 \
  python -m pytest tests/test_wp167_live_news_day.py -q -s -p no:randomly
```

## Spend

| Run | Text (LLMService ledger) | Plates (estimated, US$0.06 each) |
|---|---|---|
| run1 (crashed after the A2 plate) | US$0.0449 | 1 |
| run2 (A2, B1, C1) | US$0.0918 | 2 |
| run3-a2 | US$0.0350 | 0 |
| run4-a2 | US$0.0248 | 1 |
| **Total** | **US$0.197** | **4 plates, about US$0.24** |

A news day's text costs about US$0.03. The pick is US$0.002 of that, and the rest is the director's usual drafts and critic.

## The days

| Run | Band, day | Headline (outlet) | Used on the page? | Plate |
|---|---|---|---|---|
| run2 | A2, g1.2 | SNCF Réseau teste un système d'effarouchement des animaux (Franceinfo) | **No.** The required moment «La même chose ?» was staged and the news dropped. It was credited all the same, which led to the fix below. | none: no notes |
| run2 | B1, g2.3 | Des aurores boréales visibles en France (Franceinfo) | **Yes.** Marin sees the green sky, the neighbours climb to the roof, and Lila's gift question turns public. | `run2/B11-plate.webp` |
| run2 | C1, g3.3 | the same aurora | **Yes, the best day.** The scheduled «Sur le toit» moment is set off by the aurora, and Marchand's torch catches the learner on the roof. | `run2/C11-plate.webp` |
| run3-a2 | A2, g1.4 | Affaire Thélyson Orélien : l'édition face à l'IA (RFI) | **No**, again under «La même chose ?». It is now not credited, and the news is owed (`skipped: news_unused`). | none |
| run4-a2 | A2, g2.1 | the same RFI headline | **Thinly.** Romy's phone alert («les journalistes cherchent des preuves») hangs over Marin asking whether he may use Odile's plan. The authorship question echoes the headline, but the page could almost do without it. | `run4-a2/A21-plate.webp` |

The picker chose with intent every time. Its `why` names a thread each time:
- the trains strand the return ticket;
- the aurora brings the cast to the roof;
- the AI-authorship affair threatens Marin's novel and Odile's notebook.

## What the read changed (all in the PR)

1. **The credit named a photographer.** RFI puts the photo credit in `<source>` («© JF Paga»). The credit now always names the outlet from the registry.
2. **Both first drafts forgot `news_day_notes`.** The payload now says to write them, and missing notes are a soft retry. A page whose served draft has no notes is **not credited**: the news is owed to the next generated day (`mark_brief`).
3. **The first plate showed the café's usual menu, not the news** (`run1/A21-plate.webp`). The rule now asks for objects a reader recognises as today's story, with two examples. The plate-brief scrub also drops:
   - clauses naming a cast member («a badge on Gus's sweater»);
   - French people words (the C1 brief was written in French and said «un homme âgé»);
   - single-quoted readable text.

## The plates, looked at

All four plates fit the owner's people-free flat poster style:
- flat screen-print fills in the Bauhaus palette (red, blue, ochre, green, cream);
- paper grain;
- no people, no animals, no readable text;
- room in the foreground for the drawn cast.

| Plate | What it shows |
|---|---|
| B1 | The green aurora through Odile's kitchen window, the framed Polaroid on the table, the damp towel. It reads as «tonight» at once. |
| C1 | The roof: the open skylight, the bunting on the ground, the canal below, the aurora overhead. |
| A2 (run4) | Odile's kitchen with a smoking pan, the torn notebook page and a phone showing an abstract alert. The news is only a hint. |
| run1 A2 | Le Mistral's counter in the rain. Beautiful, but it shows nothing of the news: that is the brief problem that was fixed. |

Two honest caveats:
- The aurora skies (B1, C1) and the smoke carry soft gradients. The style says «no gradients», but they read as print texture rather than airbrush.
- The phone's «alert» and the menu board are drawn as abstract bars, never as letters.

## What it says about the feature

- **Strong at B1 and C1.** A rare, visual piece of news (the aurora) became a reason for the cast to be somewhere together tonight.
- **Weak at A2.**
  - When the gap has a scheduled moment («La même chose ?»), the director at A2 stages the moment and drops the news. That is 2 of 3 A2 tries, both in g1, which schedules three moments in five days.
  - On a free day, the A2 news was present but thin.
- The honesty guard now keeps a dropped news day uncredited and owed.
- A later package could give A2 a smaller news task: one line of news and one consequence for the cast.
- Unrelated to WP-167: the C1 objective printed «monté·e». The inclusive-dot scrub does not run on `objective_native`.
