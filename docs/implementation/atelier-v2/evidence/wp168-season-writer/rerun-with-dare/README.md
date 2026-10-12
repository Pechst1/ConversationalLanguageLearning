# WP-168 rerun with the dare (12 October 2026, about US$0.13)

The first dry run sent 5 of 6 drafts to the French coast and none left France. Each writer
call now carries a `dare`: one corner of the French-speaking world and one genre, drawn at
random (`season_writer.compass`). The writer must weigh the dare before choosing its own idea.

Same three synthetic lives, same material, `scripts/wp168_season_writer_dry_run.py --only …`:

| Life | First run (11 Oct) | With the dare (12 Oct) |
|---|---|---|
| garder | Marseille, mystery/documentary | **Papeete**, a cooking competition with a light mystery (critic: grows ✓, fresh ✓) |
| partager | Concarneau, family drama at a wedding | **Ganvié and Cotonou (Benin)**, workplace comedy |
| laisser_partir | Camaret-sur-Mer, a summer job on a boat | **Brussels** (the EU quarter and Matongé), heist / investigative comedy |

**The garder life lost three drafts on the way, each fixed in code:**
- `life-garder-refused-why-too-long.json`: a 301-character `setting.why`. Prose past a field's limit is now cut at a sentence boundary.
- `life-garder-refused-by-critic.json`: a draft set in Fort-de-France that ignored the open promise about the painter «L.». A refused season now gets one more draft carrying the critic's reasons, when the time budget allows.
- `life-garder-refused-arc-id.json`: a draft set in Douarnenez with the arc id «arc:follow_the_polaroid». Ids of arcs, places and new characters are now repaired into slugs.
- The first refusal of the run (id «marie-jo_boudreau», Acadia) had the same cause and the same fix.

One drafted season still takes the writer about 60–95 s, and the rollover runs on the learner's request path. Moving it to a background job is a follow-up.
