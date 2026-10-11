"""WP-165 — paint a season place's own plate, or one light-and-weather variant of it.

    venv/bin/python scripts/art/season_plates.py plates odile_flat quai_de_valmy   # paint (skips existing files)
    venv/bin/python scripts/art/season_plates.py plates odile_flat --reroll        # paint again; the old one goes to var/
    venv/bin/python scripts/art/season_plates.py variant quai_de_valmy morning dry # the runtime's variant path, end to end
    venv/bin/python scripts/art/season_plates.py sheet                             # the contact sheet for the owner

``sheet`` writes ``docs/art/season-plates-2026-10/contact-sheet.jpg``: the places that had
their own plate before WP-165, the twelve painted for it, and every variant in
``var/art/season-plates/`` beside its base plate.

``plates`` paints from the place's brief in ``app/services/season/world.py``
(``SEASON_ONE_PLATE_BRIEFS``: name, three landmarks, the light) with the owner's people-free
``PLATE_STYLE``, palette-locks it, runs the style check (one repaint when it is not a flat
print) and writes ``web-frontend/public/assets/serial/locations/<place>.webp`` at the size
and quality of the other plates. Commit the file; switch nothing else.

``variant`` runs what a scene in another light does at runtime: ``schedule_variant`` queues
it, the background job paints an edit of the committed plate and stores it where
``panel_art`` stores durable art. It uses a throwaway SQLite file under ``var/art`` for the
``revue_places`` row, never the app's database. A copy lands in ``var/art/season-plates/``.

Every image call is logged with the API's token usage to ``var/art/season-plates/ledger.jsonl``.
About US$0.05 an image. Needs OPENAI_API_KEY in ``.env``; never prints it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "var" / "art" / "season-plates"
LEDGER = OUT / "ledger.jsonl"
COST_PER_IMAGE_USD = 0.05
_LEDGER_LOCK = threading.Lock()


def _record_usage() -> None:
    """Log every image response's usage (the pipeline itself keeps only the picture)."""

    import httpx

    original = httpx.Client.post

    def post(self, url, *args, **kwargs):  # noqa: ANN001
        started = time.time()
        response = original(self, url, *args, **kwargs)
        if "/images/" in str(url):
            try:
                usage = response.json().get("usage")
            except Exception:  # noqa: BLE001
                usage = None
            with _LEDGER_LOCK:
                OUT.mkdir(parents=True, exist_ok=True)
                with LEDGER.open("a", encoding="utf-8") as ledger:
                    ledger.write(json.dumps({
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "endpoint": str(url).rsplit("/", 1)[-1],
                        "status": response.status_code,
                        "seconds": round(time.time() - started, 1),
                        "usage": usage,
                        "label": threading.current_thread().name,
                    }) + "\n")
        return response

    httpx.Client.post = post


def paint_place(place_id: str, *, reroll: bool) -> str:
    from app.services.season import plates as season_plates
    from app.services.season.world import PUBLIC_ROOT, SEASON_ONE_LOCATIONS, place_brief

    threading.current_thread().name = place_id
    row = SEASON_ONE_LOCATIONS[place_id]
    target = PUBLIC_ROOT / row["plate"]
    if target.exists() and not reroll:
        return f"skip {place_id} (exists; --reroll to paint again)"
    brief = place_brief(place_id)
    if not brief:
        return f"skip {place_id} (no brief)"
    image, info = season_plates.paint_checked(season_plates.prompt_for(brief), label=place_id)
    if target.exists():
        rejected = OUT / "rejected"
        rejected.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), rejected / f"{place_id}-{int(time.time())}.webp")
    image.convert("RGB").save(target, quality=86)
    report = {k: round(v, 3) for k, v in info["report"].items()}
    return f"ok {place_id}: calls={info['calls']} first={info['problem']} kept={info['kept']} {report}"


def paint_variant(place_id: str, time_of_day: str, weather: str) -> str:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models.revue_place import RevuePlace
    from app.services.season import plates as season_plates

    OUT.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{OUT / 'variants.db'}")
    RevuePlace.__table__.create(bind=engine, checkfirst=True)
    db = sessionmaker(bind=engine)()
    key = season_plates.schedule_variant(db, place_id, time_of_day=time_of_day, weather=weather)
    if key is None:
        url = season_plates.plate_url_for(db, place_id, time_of_day=time_of_day, weather=weather)
        return f"nothing queued for {place_id} {time_of_day} {weather} (painted, base light, or off: {season_plates.generation_unavailable_reason()}); serves {url}"
    print(f"queued {key}; the base plate serves meanwhile: {season_plates.plate_url_for(db, place_id, time_of_day=time_of_day, weather=weather)}")
    season_plates._executor().shutdown(wait=True)  # noqa: SLF001 - a script waits; a request never does
    url = season_plates.plate_url_for(db, place_id, time_of_day=time_of_day, weather=weather)
    stored = Path(str(REPO / "var" / "graphic-novel-images")) / url.split("/media/graphic-novel/", 1)[-1] if url and url.startswith("/media/") else None
    if stored and stored.is_file():
        shutil.copy(stored, OUT / f"{place_id}-{time_of_day}-{weather}.webp")
    return f"ok {key} -> {url}"


SHEET = REPO / "docs" / "art" / "season-plates-2026-10" / "contact-sheet.jpg"
#: The places that borrowed another place's plate until WP-165.
WP165_PLACES = (
    "odile_flat", "quai_de_valmy", "stairwell", "marchand_office", "mairie", "gare_de_lest",
    "toit", "notaire", "mistral_back_room", "rue_de_lancry", "boulangerie", "ecole",
)


def contact_sheet() -> str:
    from PIL import Image, ImageDraw, ImageFont

    from app.services.season.world import PUBLIC_ROOT, SEASON_ONE_LOCATIONS

    thumb, gap, label, cols = (384, 256), 12, 26, 4
    font = ImageFont.load_default(size=17)
    title_font = ImageFont.load_default(size=26)
    new = [(place, PUBLIC_ROOT / SEASON_ONE_LOCATIONS[place]["plate"]) for place in WP165_PLACES]
    originals = [
        (place, PUBLIC_ROOT / row["plate"])
        for place, row in SEASON_ONE_LOCATIONS.items()
        if place not in WP165_PLACES
    ]
    variants = []
    for path in sorted(OUT.glob("*-*-*.webp")):
        place, time_of_day, weather = path.stem.rsplit("-", 2)
        if place in SEASON_ONE_LOCATIONS:
            variants += [(f"{place} (base)", PUBLIC_ROOT / SEASON_ONE_LOCATIONS[place]["plate"]),
                         (f"{place}: {time_of_day}, {weather}", path)]
    sections = [("WP-165: the twelve new plates", new), ("The originals (own plates before WP-165)", originals)]
    if variants:
        sections.append(("Variants painted lazily: base plate, then the variant", variants))
    height = sum(48 + -(-len(items) // cols) * (thumb[1] + label + gap) for _, items in sections) + gap
    sheet = Image.new("RGB", (cols * (thumb[0] + gap) + gap, height), "#f8f3e8")
    draw = ImageDraw.Draw(sheet)
    y = gap
    for title, items in sections:
        draw.text((gap, y + 8), title, fill="#14110d", font=title_font)
        y += 48
        for index, (name, path) in enumerate(items):
            x = gap + (index % cols) * (thumb[0] + gap)
            row_y = y + (index // cols) * (thumb[1] + label + gap)
            with Image.open(path) as image:
                sheet.paste(image.convert("RGB").resize(thumb, Image.Resampling.LANCZOS), (x, row_y + label))
            draw.text((x, row_y + 3), name, fill="#14110d", font=font)
        y += -(-len(items) // cols) * (thumb[1] + label + gap)
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(SHEET, quality=84, optimize=True)
    return f"ok {SHEET.relative_to(REPO)} ({sheet.size[0]}x{sheet.size[1]}, {SHEET.stat().st_size // 1024} KB)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    plates = sub.add_parser("plates")
    plates.add_argument("places", nargs="+")
    plates.add_argument("--reroll", action="store_true")
    plates.add_argument("--parallel", type=int, default=3)
    variant = sub.add_parser("variant")
    variant.add_argument("place")
    variant.add_argument("time_of_day", choices=("morning", "day", "evening", "night"))
    variant.add_argument("weather", choices=("dry", "rain"))
    sub.add_parser("sheet")
    args = parser.parse_args()

    if args.cmd == "sheet":
        print(contact_sheet())
        return
    _record_usage()
    if args.cmd == "plates":
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
            for line in pool.map(lambda place: paint_place(place, reroll=args.reroll), args.places):
                print(line, flush=True)
    else:
        print(paint_variant(args.place, args.time_of_day, args.weather), flush=True)
    rows = [json.loads(line) for line in LEDGER.open(encoding="utf-8")] if LEDGER.exists() else []
    paid = sum(1 for row in rows if int(row.get("status") or 0) < 400)
    print(f"ledger: {paid} image calls so far ({len(rows) - paid} refused), about US${paid * COST_PER_IMAGE_USD:.2f}")


if __name__ == "__main__":
    main()
