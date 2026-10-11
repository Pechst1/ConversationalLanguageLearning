# Art sets

The app can show its cast in two sets (WP-116):

- **painted**: the AI-painted portraits, character sheets and authored panels that shipped until October 2026;
- **drawn**: the SVG character rigs in `web-frontend/components/cast/`, placed over the painted location plates.

The location plates (`web-frontend/public/assets/serial/locations/`) belong to both sets. The image-generation pipeline (`app/services/panel_art.py`, `scripts/art/atelier_art.py`) stays in the codebase: it draws plates for new places, and the generative seasons will need it (WP-116 §12).

## Switching

| Where | How |
|---|---|
| One device | Settings › Affichage › Personnages, or the localStorage key `atelier.artSet` (`painted` or `drawn`) |
| Every learner | `artSet` in `web-frontend/launch-flags.json` and `ATELIER_ART_SET` on the backend, then redeploy |

## Keeping the painted set

- Git tag `art-painted-2026-10-01` (commit 647a9a3) holds every painted file.
- `docs/art/painted-set-2026-10-01.json` lists the 67 files with their sha256, and the code that reads them.
- `venv/bin/python scripts/art/art_set.py verify` checks that every painted file is present and unchanged.
- `venv/bin/python scripts/art/art_set.py restore` brings back a missing or changed file from the tag, using `git show` only.
- Nothing painted is moved or deleted before the owner's second yes (WP-116 phase 7).

## Season plates (WP-165)

Under the drawn set the image model paints places, never people: a panel is its place's plate with the SVG cast standing on it.

- **Every season place has its own plate.** The twelve places that borrowed another place's plate until October 2026 (Odile's flat, the quai de Valmy, the stairwell, the gérance Marchand, the mairie, the gare de l'Est, the roof, the notaire, the Mistral's back room, the rue de Lancry, the boulangerie, Lila's classroom) were painted once from their briefs and committed as WebP next to the originals. The briefs (name, three landmarks, the light) live in `SEASON_ONE_PLATE_BRIEFS` in `app/services/season/world.py`. Contact sheet: `docs/art/season-plates-2026-10/contact-sheet.jpg`.
- **Light and weather.** The director sets a page's `time_of_day` (morning, day, evening, night) and `weather` (dry, rain); an authored tentpole takes them from its panels' own direction. A place's committed plate has one light (`light` in its brief). Any other light is a variant: an edit of that plate, same layout, painted in the background the first time a scene asks for it and stored where panel art is stored (`var/` locally, S3/R2 in production). The base plate serves until the variant exists. At most seven variants a place, about US$0.05 each, painted once for every learner. The metro platform never changes.
- **The style check.** After the palette lock, `style_problem` measures smooth gradients on the raw paint and the share of the plate near a brand ink. A plate that fails is painted once more and the flatter of the two is kept.
- **Kill switch:** `ATELIER_SEASON_PLATES_ENABLED` (off: the committed plates only). The test suite keeps it off.

```
venv/bin/python scripts/art/season_plates.py plates odile_flat --reroll        # repaint one plate (the old one goes to var/)
venv/bin/python scripts/art/season_plates.py variant quai_de_valmy morning dry # the runtime variant path, end to end
venv/bin/python scripts/art/season_plates.py sheet                             # rebuild the contact sheet
```
