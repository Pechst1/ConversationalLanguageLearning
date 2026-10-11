"""WP-119 phase 4 evidence: the six W40 site plates and two second views, for the owner's review.

    .venv/bin/python docs/design-reference/revue/plates/phase4/paint_evidence.py [--dry]

Uses the production path's own pieces (``plates.brief_for``, ``prompt_for``, ``_call``,
``looks_wrong`` with one repaint, ``palette_lock``) but writes no ``revue_places`` row and
does not need the flag: the files land next to this script. About US$0.05 per image.
The briefs follow §8.1 (name + three landmarks + light; typed when the place is private
or unremarkable); they are the briefs the builder should write, not the W40 JSON's.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.services.revue import plates  # noqa: E402
from app.services.revue.dossier import Place  # noqa: E402
from app.services.revue.weekly import load_week  # noqa: E402

OUT = Path(__file__).resolve().parent
WEEK = "2026-W40"

#: dossier id → (role, place id, name_fr, brief). "site" = places[0] (arrive/facts), "second" = places[1].
PLATES: list[tuple[str, str, str, str, str]] = [
    ("2026-w40-budget-2027", "site", "hemicycle_assemblee", "L'hémicycle de l'Assemblée nationale",
     "l'hémicycle de l'Assemblée nationale, Palais Bourbon, Paris: the semicircle of red velvet benches rising "
     "in tiers, the high marble tribune with the president's desk above it, the glass ceiling over the chamber, "
     "soft afternoon daylight"),
    ("2026-w40-budget-2027", "second", "salle_quatre_colonnes", "La salle des Quatre-Colonnes",
     "la salle des Quatre-Colonnes, Palais Bourbon: the long lobby where deputies meet the press, four fluted "
     "marble columns, bronze statues on plinths, a chequered marble floor, the tall doors to the hémicycle, "
     "warm evening lamplight"),
    ("2026-w40-ce-qui-change-1er-octobre", "site", "cuisine_facture_gaz", "Une petite cuisine, la facture de gaz sur la table",
     "a small Paris apartment kitchen: an old white gas stove with a kettle, an open energy bill and a pen on an "
     "oilcloth table, a wall calendar, a window onto a courtyard, grey morning light"),
    ("2026-w40-goncourt-roman-retire", "site", "librairie_rentree_litteraire", "Une librairie à Paris, à la rentrée littéraire",
     "a small Paris bookshop at the rentrée littéraire: the window stacked with new novels in plain cream covers "
     "and red paper bands, a wooden table of books inside, a library ladder against tall shelves, a wet pavement "
     "outside, warm lamplight at dusk"),
    ("2026-w40-goncourt-roman-retire", "second", "restaurant_drouant", "Le salon Goncourt du restaurant Drouant",
     "le restaurant Drouant, place Gaillon, Paris 2e: the Goncourt dining room on the first floor, a long oval "
     "table set with white linen and ten chairs, the Art Deco staircase with its wrought-iron rail, tall windows "
     "onto the place Gaillon fountain, soft midday light"),
    ("2026-w40-paris-plan-canicules", "site", "rue_paris_voile_ombrage", "Une rue de Paris sous un voile d'ombrage",
     "a narrow Paris street of cream Haussmann stone: closed grey shutters and wrought-iron balconies, a white "
     "shade sail stretched high between the buildings, young plane trees in iron grates, a green Wallace "
     "fountain on the corner, hard summer light"),
    ("2026-w40-prix-de-l-arc-de-triomphe", "site", "hippodrome_longchamp", "L'hippodrome de ParisLongchamp",
     "l'hippodrome de ParisLongchamp, bois de Boulogne: the wide green turf track curving away, the modern "
     "grandstand with its long thin cantilevered roof, the old moulin de Longchamp near the start, autumn "
     "chestnut trees, a race crowd small in the distance, soft afternoon light"),
    ("2026-w40-prix-produits-frais", "site", "etal_fruits_legumes", "Un étal de fruits et légumes au marché",
     "a Paris street-market stall: autumn fruit and vegetables under a striped awning, wooden crates of apples, "
     "pears, leeks and squash, small blank slate boards on sticks, a weighing scale on the counter, "
     "early morning light"),
]


def checked() -> list[dict]:
    dossiers = {d.id: d for d in load_week(WEEK)}
    rows = []
    for dossier_id, role, place_id, name_fr, brief in PLATES:
        place = Place(id=place_id, name_fr=name_fr, brief=brief)
        normal = plates.brief_for(place, dossiers[dossier_id])  # raises on a refused brief
        rows.append({"dossier": dossier_id, "role": role, "id": place_id, "name_fr": name_fr, "brief": normal,
                     "prompt": plates.prompt_for(normal)})
    return rows


def paint_one(row: dict) -> dict:
    started = time.monotonic()
    image = plates._call(row["prompt"]).convert("RGB")  # noqa: SLF001
    flagged = plates.looks_wrong(image)
    if flagged:
        image.save(OUT / f"{row['id']}-dropped.webp", quality=80)
        image = plates._call(row["prompt"]).convert("RGB")  # noqa: SLF001
    plates.palette_lock(image).save(OUT / f"{row['id']}.webp", quality=plates.PLATE_WEBP_QUALITY)
    return {**row, "seconds": round(time.monotonic() - started, 1), "looks_wrong_first": flagged,
            "looks_wrong_final": plates.looks_wrong(image) if flagged else False,
            "calls": 2 if flagged else 1, "status": "ok", "prompt_version": plates.PROMPT_VERSION}


def contact_sheet(rows: list[dict]) -> None:
    thumb_w, thumb_h, pad, caption = 576, 384, 16, 34
    cols = 2
    lines = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * pad, lines * (thumb_h + caption + pad) + pad), (241, 236, 225))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for i, row in enumerate(rows):
        x = pad + (i % cols) * (thumb_w + pad)
        y = pad + (i // cols) * (thumb_h + caption + pad)
        path = OUT / f"{row['id']}.webp"
        if path.exists():
            sheet.paste(Image.open(path).convert("RGB").resize((thumb_w, thumb_h)), (x, y))
        label = f"{row['role']} · {row['name_fr']}"
        draw.text((x, y + thumb_h + 8), label, fill=(20, 17, 13), font=font)
    sheet.save(OUT / "contact-sheet.webp", quality=88)


def main() -> None:
    rows = checked()
    if "--dry" in sys.argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    if "--sheet" in sys.argv:
        logged = json.loads((OUT / "log.json").read_text())
        contact_sheet(logged["plates"] if isinstance(logged, dict) else logged)
        return
    with ThreadPoolExecutor(max_workers=4) as pool:
        done = []
        for result in pool.map(lambda r: _safe(paint_one, r), rows):
            done.append(result)
            print(result["id"], result.get("status"), result.get("seconds"), result.get("looks_wrong_first"))
    (OUT / "log.json").write_text(json.dumps(done, ensure_ascii=False, indent=2) + "\n")
    contact_sheet(done)


def _safe(fn, row: dict) -> dict:
    try:
        return fn(row)
    except Exception as exc:  # noqa: BLE001 - one refusal must not lose the others
        return {**row, "status": "error", "error": str(exc)[:300]}


if __name__ == "__main__":
    main()
