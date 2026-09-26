"""Draw the authored scenes' graphic-novel pages (2026-09-25).

The first day and the story engine's stand-in are authored scenes; each variant's
page lives in app/data/journey_scenarios/<version>/<scenario>.json under
``variants[].panels``. A1 and A2 share one drawing per panel (same shot, different
text), so each distinct ``image_asset`` is drawn once, from the first variant that
names it, through the same pipeline as story-engine panels (app/services/panel_art.py):
the approved style, the place, who is in frame, and their approved portraits as
references.

    venv/bin/python scripts/art/draw_authored_pages.py              # draw what is missing
    venv/bin/python scripts/art/draw_authored_pages.py --redraw     # draw everything again

About US$0.05 a panel. Needs OPENAI_API_KEY in `.env`; never prints it.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402

from app.services import panel_art  # noqa: E402
from app.services.serial import SerialThreadService  # noqa: E402

CONTENT = REPO / "app/data/journey_scenarios/journey-content-v1"
PUBLIC = REPO / "web-frontend/public"
MAX_SIDE = 1536


def jobs() -> list[tuple[Path, object]]:
    world = SerialThreadService._load_world_bible()
    seen: dict[str, tuple[Path, object]] = {}
    for path in sorted(CONTENT.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        scene = SimpleNamespace(id=spec["scenario_key"], script_payload={"location_id": spec["location_id"]})
        for variant in spec.get("variants") or []:
            for index, raw in enumerate(variant.get("panels") or []):
                asset = str(raw.get("image_asset") or "").lstrip("/")
                if not asset or asset in seen:
                    continue
                panel = SimpleNamespace(
                    panel_index=index,
                    image_prompt=raw["visual_direction"],
                    overlay_payload={"dialogue": raw.get("dialogue") or []},
                )
                seen[asset] = (
                    PUBLIC / asset,
                    panel_art.panel_job(
                        scene, panel, world,
                        location_id=raw.get("location_id"), in_frame=raw.get("in_frame"),
                    ),
                )
    return list(seen.values())


def save(raw: bytes, target: Path) -> None:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="WEBP", quality=82, method=6)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--redraw", action="store_true", help="draw panels that already exist too")
    parser.add_argument("only", nargs="*", help="asset paths to (re)draw, e.g. assets/serial/scenes/x/panel-2.webp")
    args = parser.parse_args()
    wanted = {PUBLIC / item.lstrip("/") for item in args.only}

    def due(target: Path) -> bool:
        if wanted:
            return target in wanted
        return args.redraw or not target.is_file()

    todo = [(target, job) for target, job in jobs() if due(target)]
    print(f"{len(todo)} panel(s) to draw")
    for target, job in todo:
        print(f"  {target.relative_to(PUBLIC)}  refs={list(job.references)}", flush=True)
        save(panel_art.draw(job), target)
    print("done")


if __name__ == "__main__":
    main()
