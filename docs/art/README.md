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
