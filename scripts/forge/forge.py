#!/usr/bin/env python3
"""The forge: Le Quartier's world grows one corner of Paris at a time.

Run from the repository root, in a venv with ``scripts/forge/requirements.txt``::

    python scripts/forge/forge.py news                  # the map's news layer: every place the Papier names
    python scripts/forge/forge.py queue                 # places the Papier names that are not built yet
    python scripts/forge/forge.py queue --season --from g3  # places the season's pages are set in, the next ones first
    python scripts/forge/forge.py queue --season --from api # the same, from the segments the season's learners are on
    python scripts/forge/forge.py queue --orders          # what the learners' stories left in the quarter, not built yet
    python scripts/forge/forge.py survey marche_aligre  # open map data around it -> var/forge/<id>/survey.json
    python scripts/forge/forge.py draft marche_aligre   # survey + brief -> lib/quartier/world/sites/<id>.json
    python scripts/forge/forge.py check marche_aligre   # the site's invariants (also in site.test.js)
    python scripts/forge/forge.py publish marche_aligre # open it on the map (world.json, sites/index.ts)
    python scripts/forge/forge.py stages                # the server's copy of the register (app/data/season/s1/stages.json)

A room of the season (``"kind": "room"`` in its brief: the stairwell, a flat) is written from the
canon, not surveyed: ``draft`` lays the brief out as ``lib/quartier/world/rooms/<id>.json``
(``room.py``), ``check`` and ``plan`` read that file, and it is never published by the forge: a
room stays ``locked`` until the story reaches it.

Between ``draft`` and ``publish`` the loop renders the site from several viewpoints
(``web-frontend/scripts/quartier/forge-render.mjs``), looks at the pictures, writes down what is
wrong in ``scripts/forge/briefs/<id>.md`` and changes the brief, at most three rounds. The
nightly routine (``.claude/skills/quartier-forge/SKILL.md``) runs the whole loop for the next
place in the queue.

Sources: Overture Maps (buildings with their floors, streets with their classes and widths,
places with their trades, street lamps, benches, crossings, trees, house numbers), the Papier's
article for what happens there, and the brief for what the data cannot say (which street is the
market, who stands where). Never Street View or any other imagery under terms that forbid
deriving a model from it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WEB = os.path.join(ROOT, "web-frontend")
WORLD = os.path.join(WEB, "lib", "quartier", "world", "world.json")
NEWS = os.path.join(WEB, "lib", "quartier", "world", "news.json")
SITES = os.path.join(WEB, "lib", "quartier", "world", "sites")
ROOMS = os.path.join(WEB, "lib", "quartier", "world", "rooms")
DETAILS = os.path.join(WEB, "lib", "quartier", "world", "details")
BRIEFS = os.path.join(HERE, "briefs")
CACHE = os.path.join(ROOT, "var", "forge")
PAPIER = os.path.join(ROOT, "app", "services", "revue")
SEASONS = os.path.join(ROOT, "app", "data", "season")
SEASON_WORLD = os.path.join(ROOT, "app", "services", "season", "world.py")
STAGES = os.path.join(SEASONS, "s1", "stages.json")

# Paris inside the périphérique, give or take: what the world map can show
PARIS_BOX = (2.224, 48.815, 2.47, 48.902)

LAYERS = {
    # name: (theme, type, columns)
    "buildings": ("buildings", "building", ["id", "geometry", "bbox", "names", "class", "subtype", "height", "num_floors", "roof_shape", "roof_color", "facade_color", "facade_material", "is_underground", "has_parts"]),
    "segments": ("transportation", "segment", ["id", "geometry", "bbox", "names", "subtype", "class", "subclass", "width_rules", "road_flags"]),
    "places": ("places", "place", ["id", "geometry", "bbox", "names", "basic_category", "taxonomy", "confidence", "operating_status", "brand"]),
    "infra": ("base", "infrastructure", ["id", "geometry", "bbox", "names", "subtype", "class", "height"]),
    "land": ("base", "land", ["id", "geometry", "bbox", "names", "subtype", "class"]),
    "landuse": ("base", "land_use", ["id", "geometry", "bbox", "names", "subtype", "class"]),
    "water": ("base", "water", ["id", "geometry", "bbox", "names", "subtype", "class"]),
    "addresses": ("addresses", "address", ["id", "geometry", "bbox", "number", "street", "postcode"]),
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data, compact: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def tidy(data, indent: int = 0) -> str:
    """JSON the way the world file is kept by hand: a key a line, small flat objects on one line."""
    pad = " " * (indent + 2)
    flat = lambda xs: all(not isinstance(v, (dict, list)) for v in xs)  # noqa: E731
    if isinstance(data, dict) and data:
        if indent >= 6 and flat(data.values()):
            return "{ " + ", ".join(f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}" for k, v in data.items()) + " }"
        return "{\n" + ",\n".join(f"{pad}{json.dumps(k, ensure_ascii=False)}: {tidy(v, indent + 2)}" for k, v in data.items()) + "\n" + " " * indent + "}"
    if isinstance(data, list) and data:
        if flat(data):
            return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in data) + "]"
        return "[\n" + ",\n".join(pad + tidy(v, indent + 2) for v in data) + "\n" + " " * indent + "]"
    return json.dumps(data, ensure_ascii=False)


def save_world(data: dict) -> None:
    with open(WORLD, "w", encoding="utf-8") as f:
        f.write(tidy(data) + "\n")
    write_stages(data["places"])


def world() -> dict:
    return load_json(WORLD)


def place_of(pid: str) -> dict:
    for p in world()["places"]:
        if p["id"] == pid:
            return p
    raise SystemExit(f"{pid} is not in world.json; add it from the queue first")


def brief_of(pid: str) -> dict:
    path = os.path.join(BRIEFS, f"{pid}.json")
    if not os.path.exists(path):
        raise SystemExit(f"no brief at {path}: write one (see briefs/marche_aligre.json)")
    return load_json(path)


def metres_per_degree(lat: float) -> tuple[float, float]:
    """(east, north) metres in a degree of longitude and of latitude here, on the WGS84 ellipsoid."""
    phi = math.radians(lat)
    north = 111132.954 - 559.822 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
    east = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi) + 0.118 * math.cos(5 * phi)
    return east, north


def box_around(lat: float, lon: float, radius: float) -> tuple[float, float, float, float]:
    east, north = metres_per_degree(lat)
    return lon - radius / east, lat - radius / north, lon + radius / east, lat + radius / north


# ---------------------------------------------------------------------------------------------
# queue: what the Papier talks about, and what the world already has
# ---------------------------------------------------------------------------------------------


def papier_places() -> list[dict]:
    """Every place an article of the Papier names, with its article."""
    out = []
    for path in sorted(glob.glob(os.path.join(PAPIER, "**", "*.json"), recursive=True)):
        try:
            d = load_json(path)
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        for p in d.get("places") or []:
            geo = p.get("geo") or {}
            if geo.get("lat") is None or geo.get("lon") is None:
                continue
            out.append({"id": p.get("id"), "name_fr": p.get("name_fr"), "brief": p.get("brief"), "geo": geo, "article": d.get("id"), "title_fr": d.get("title_fr"), "week": d.get("week"), "topic": d.get("topic"), "path": os.path.relpath(path, ROOT)})
    return out


def in_paris(geo: dict) -> bool:
    x0, y0, x1, y1 = PARIS_BOX
    return geo.get("precision") == "exact" and x0 <= geo["lon"] <= x1 and y0 <= geo["lat"] <= y1


def news_places() -> list[dict]:
    """The map's news layer: each place the Papier names with an exact position in Paris, once
    (the newest article that names it), newest first. The map pins every one at once, under
    scaffolding until the forge has built it; ``web-frontend/lib/quartier/news.test.js`` keeps
    this file in step with the articles."""
    best: dict[str, dict] = {}
    for p in papier_places():
        if not p["id"] or not in_paris(p["geo"]):
            continue
        week = p["week"] or ""
        if p["id"] not in best or week > (best[p["id"]]["article"]["week"] or ""):
            best[p["id"]] = {
                "id": p["id"],
                "name_fr": p["name_fr"],
                "lat": p["geo"]["lat"],
                "lon": p["geo"]["lon"],
                "article": {"id": p["article"], "title_fr": p["title_fr"], "week": p["week"], "topic": p["topic"]},
            }
    return sorted(best.values(), key=lambda n: (n["article"]["week"] or "", n["id"]), reverse=True)


def cmd_news(_args) -> None:
    places = news_places()
    with open(NEWS, "w", encoding="utf-8") as f:
        f.write(json.dumps({"places": places}, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {os.path.relpath(NEWS, ROOT)}: {len(places)} places the Papier names in Paris")


# ---------------------------------------------------------------------------------------------
# the season's places: what the story reaches next, and whether the world has built it
# ---------------------------------------------------------------------------------------------


def season_locations() -> dict[str, str]:
    """The places a season-1 page may be set in (``SEASON_ONE_LOCATIONS`` in
    ``app/services/season/world.py``), id to French name. Read from the source, not imported, so
    the forge's venv needs none of the app's packages."""
    import ast

    tree = ast.parse(open(SEASON_WORLD, encoding="utf-8").read())
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else (node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "SEASON_ONE_LOCATIONS" and isinstance(node.value, ast.Dict):
            out = {}
            for k, v in zip(node.value.keys, node.value.values, strict=True):
                name = ""
                if isinstance(v, ast.Dict):
                    for kk, vv in zip(v.keys, v.values, strict=True):
                        if isinstance(kk, ast.Constant) and kk.value == "name_fr" and isinstance(vv, ast.Constant):
                            name = vv.value
                out[k.value] = name
            return out
    raise SystemExit(f"no SEASON_ONE_LOCATIONS in {os.path.relpath(SEASON_WORLD, ROOT)}")


def _locations_in(node, out: list[str]) -> None:
    """Every ``location_id`` of a page, in the order the page reaches it."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "location_id" and isinstance(v, str) and v:
                if v not in out:
                    out.append(v)
            else:
                _locations_in(v, out)
    elif isinstance(node, list):
        for v in node:
            _locations_in(v, out)


def season_segments(season_id: str = "s1") -> list[dict]:
    """The season's segments in play order: ``season.json``'s, then its epilogue's (``e1``…,
    played after the last tentpole; the server counts them as the season's too)."""
    root = os.path.join(SEASONS, season_id)
    segments = list(load_json(os.path.join(root, "season.json"))["segments"])
    epilogue = os.path.join(root, "epilogue.json")
    if os.path.exists(epilogue):
        segments += load_json(epilogue).get("segments") or []
    return segments


def season_needs(season_id: str = "s1") -> list[dict]:
    """Where the season's own pages are set, in the season's order: each tentpole's days
    (``t1.json``…), each gap's bridge page (``bridges.json``) and the epilogue's pages, one row per
    place a page reaches, with the segment, its position in the season and the page."""
    root = os.path.join(SEASONS, season_id)
    segments = season_segments(season_id)
    bridges = load_json(os.path.join(root, "bridges.json"))["bridges"]
    epilogue = os.path.join(root, "epilogue.json")
    after = {p["id"]: p for p in load_json(epilogue).get("pages") or []} if os.path.exists(epilogue) else {}
    rows = []
    for i, seg in enumerate(segments):
        pages = []
        if seg["kind"] == "tentpole":
            path = os.path.join(root, f"{seg['id']}.json")
            days = load_json(path).get("days", []) if os.path.exists(path) else (after.get(seg["id"]) or {}).get("days", [])
            pages = [(f"{seg['id']}.{d.get('day')}", d) for d in days]
        else:
            pages = [(f"{seg['id']}.bridge", b) for b in bridges if b.get("gap") == seg["id"]]
        for key, page in pages:
            locs: list[str] = []
            _locations_in(page, locs)
            rows.extend({"segment": seg["id"], "at": i, "page": key, "location": loc} for loc in locs)
    return rows


def is_built(place: dict) -> bool:
    """The hand-drawn quarter, or a place the forge has written a room or a site for."""
    return place.get("kind") == "home" or bool(place.get("room")) or bool(place.get("site"))


def stage_of(location: str, places: list[dict] | None = None) -> dict | None:
    """The built place a season location plays in (the register: ``stages`` in world.json), a room
    or site for exactly that place before the quarter it is inside; None while nothing stages it."""
    places = world()["places"] if places is None else places
    built = [p for p in places if is_built(p) and location in (p.get("stages") or [])]
    return next((p for p in built if p.get("kind") != "home"), built[0] if built else None)


def built_stages(places: list[dict] | None = None) -> dict[str, str]:
    """Each place of the season the world has built, to the built place a page set there plays in.
    The server reads it (``app/data/season/s1/stages.json``): the night writes a page only where
    the world can play it."""
    places = world()["places"] if places is None else places
    out = {}
    for loc in season_locations():
        stage = stage_of(loc, places)
        if stage:
            out[loc] = stage["id"]
    return out


def stages_file(places: list[dict] | None = None) -> dict:
    return {
        "_about": "Written by scripts/forge/forge.py from web-frontend/lib/quartier/world/world.json "
        "(python scripts/forge/forge.py stages): each place of the season the 3D world has built, "
        "to the built place a page set there plays in. The night writer sets a generated page only "
        "at these places (app/services/season/world.py).",
        "stages": built_stages(places),
    }


def write_stages(places: list[dict] | None = None) -> bool:
    """Write ``stages.json`` from the world; True when it changed."""
    data = stages_file(places)
    if os.path.exists(STAGES) and load_json(STAGES) == data:
        return False
    save_json(STAGES, data)
    return True


def stages_problems() -> list[str]:
    if not os.path.exists(STAGES) or load_json(STAGES) != stages_file():
        return [f"{os.path.relpath(STAGES, ROOT)} is not the world's register: run `forge.py stages`"]
    return []


def cmd_stages(_args) -> None:
    changed = write_stages()
    built = load_json(STAGES)["stages"]
    print(f"{'wrote' if changed else 'unchanged'} {os.path.relpath(STAGES, ROOT)}: {len(built)} places of the season built")
    for loc, place in built.items():
        print(f"  {loc:18} {place}")


def waits_for_kit(location: str) -> bool:
    """A place the forge looked at and no kit can build yet: its notes start «Waits for a kit:»."""
    path = os.path.join(BRIEFS, f"{location}.md")
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        return f.read().lstrip().lower().startswith("waits for a kit")


def season_queue(frontier: str | list[str] | None = None, season_id: str = "s1") -> list[dict]:
    """Every place the season's pages are set in, with what the world has for it, the next one
    the story reaches first. ``frontier`` is the segment a learner is on (``g3``), or the
    segments several are on (``forge.py queue --season --from api`` reads them from the
    server): a place comes sooner the fewer days of the season lie between a learner and the
    first page of theirs set there; places only needed behind every learner follow, for the
    learners still to come."""
    needs = season_needs(season_id)
    segments = season_segments(season_id)
    segs = [s["id"] for s in segments]
    fronts = [frontier] if isinstance(frontier, str) else list(frontier or [])
    for f in fronts:
        if f not in segs:
            raise SystemExit(f"{f} is not a segment of {season_id}: {', '.join(segs)}")
    starts = sorted({segs.index(f) for f in fronts}) or [0]
    first_day = [sum(int(s.get("days") or 1) for s in segments[:i]) for i in range(len(segments))]

    def soon(n: dict) -> int | None:
        """Days from the nearest learner before this page to it, None when every learner is past it."""
        ahead = [first_day[n["at"]] - first_day[s] for s in starts if n["at"] >= s]
        return min(ahead) if ahead else None

    places = world()["places"]
    names = season_locations()
    by_loc: dict[str, dict] = {}
    for n in needs:
        row = by_loc.get(n["location"])
        if row is None:
            row = by_loc[n["location"]] = {"location": n["location"], "name_fr": names.get(n["location"], ""), "first": n, "next": None}
        days = soon(n)
        if days is not None and (row["next"] is None or days < row["soon"]):
            row["next"], row["soon"] = n, days
    out = []
    for row in by_loc.values():
        stage = stage_of(row["location"], places)
        entry = next((p for p in places if row["location"] in (p.get("stages") or [])), None)
        row["stage"] = stage["id"] if stage else None
        row["status"] = "built" if stage else ("no kit" if waits_for_kit(row["location"]) else ("locked" if entry else "new"))
        row["entry"] = entry["id"] if entry else None
        need = row["next"] or row["first"]
        row["need"] = need
        row["ahead"] = row["next"] is not None
        row.setdefault("soon", None)
        out.append(row)
    out.sort(key=lambda r: (0, r["soon"], needs.index(r["need"])) if r["ahead"] else (1, r["need"]["at"], needs.index(r["need"])))
    return out


#: Where the nightly forge reads the segments the season's learners are on (``--from api``).
API = os.environ.get("FORGE_API", "https://atelier-api-3njh.onrender.com")


def api_json(path: str):
    """GET one of the server's public routes for the forge (``FORGE_API``), as JSON."""
    import ssl
    import urllib.request

    cafile = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    context = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    url = f"{API}{path}"
    if not url.startswith(("https://", "http://")):
        raise SystemExit(f"FORGE_API must be an http(s) address, not {API!r}")
    # a server asleep on its free plan takes up to a minute to wake
    with urllib.request.urlopen(url, timeout=90, context=context) as r:  # noqa: S310 - http(s) only, checked above
        return json.load(r)


def live_frontier(season_id: str = "s1") -> list[str]:
    """The segments the season's recently active learners are on, from the server
    (``GET /api/v1/story-engine/season-frontier``). Empty when it cannot be read: the queue
    then starts at the season's beginning, and says so."""
    try:
        data = api_json(f"/api/v1/story-engine/season-frontier?season={season_id}")
    except Exception as exc:  # noqa: BLE001 - the queue still runs from the season's start
        print(f"! the learners' segments are unreadable ({exc}): the queue starts at the season's beginning", file=sys.stderr)
        return []
    return [str(s) for s in data.get("segments") or [] if s]


# ---------------------------------------------------------------------------------------------
# the story's orders: what the learners' pages left in the quarter
# ---------------------------------------------------------------------------------------------


def fold(text) -> str:
    """A name as an order is matched: case and spacing aside."""
    return " ".join(str(text or "").casefold().split())


def detail_specs() -> list[dict]:
    return [load_json(f) for f in sorted(glob.glob(os.path.join(DETAILS, "*.json")))]


def story_orders(source: str | None = None, season_id: str = "s1") -> list[dict]:
    """What the season's recent lives left in Le Quartier, most asked for first: the server's
    ``GET /api/v1/story-engine/world-orders`` (``source`` None or ``api``), or a saved copy of it
    (a path). Empty when it cannot be read, and says so."""
    if source in (None, "", "api"):
        try:
            data = api_json(f"/api/v1/story-engine/world-orders?season={season_id}")
        except Exception as exc:  # noqa: BLE001 - the forge goes on with the season's own queue
            print(f"! the story's orders are unreadable ({exc})", file=sys.stderr)
            return []
    else:
        data = load_json(source)
    return [
        o
        for o in (data or {}).get("orders") or []
        if isinstance(o, dict) and o.get("kind") in ("thing", "place") and str(o.get("name_fr") or "").strip()
    ]


def orders_queue(orders: list[dict], places: list[dict] | None = None) -> list[dict]:
    """The story's orders against what the world has, the next one to build first.

    A thing (``kind: thing``) is a detail of the built place its page was set in: ``built`` when
    a detail file waits on that mark, ``new`` when its place is built, ``waits`` when the place
    is not (the season queue builds the place first). A place the story named is ``built``
    when the world has it, ``season`` when it is a place of the season not built yet (the
    season queue has it), ``new`` when the world has never heard of it. Among the same status,
    what more lives left comes first."""
    places = places if places is not None else world()["places"]
    stages = built_stages(places)
    laid = {(fold(d["mark"].get("name_fr")), d["mark"].get("location_id")) for d in detail_specs() if isinstance(d.get("mark"), dict)}
    names = season_locations()
    built_names = {fold((p.get("name") or {}).get("fr")) for p in places if is_built(p)} | {fold(names.get(loc)) for loc in stages}
    season_names = {fold(name): loc for loc, name in names.items()}
    rows = []
    for o in orders:
        loc = o.get("location_id") or None
        row = {**o, "location_id": loc, "stage": stages.get(loc) if loc else None}
        if o["kind"] == "thing":
            if (fold(o["name_fr"]), loc) in laid:
                status = "built"
            else:
                status = "new" if row["stage"] else "waits"
        else:
            loc = loc or season_names.get(fold(o["name_fr"]))
            if (loc and loc in stages) or fold(o["name_fr"]) in built_names:
                status = "built"
            elif loc and loc in names:
                status = "season"
            else:
                status = "new"
        rows.append({**row, "status": status})
    rank = {"new": 0, "waits": 1, "season": 2, "built": 3}
    rows.sort(key=lambda r: (rank[r["status"]], -int(r.get("lives") or 0), -int(r.get("times") or 0), fold(r["name_fr"])))
    return rows


def cmd_orders_queue(args) -> None:
    rows = orders_queue(story_orders(args.frontier))
    for r in rows:
        where = r["location_id"] or "-"
        if r["stage"]:
            where += f" -> {r['stage']}"
        print(f"{r['status']:6} {r['kind']:5} {int(r.get('lives') or 0)} lives, {int(r.get('times') or 0)}x  «{r['name_fr']}» at {where}  {r.get('look') or ''}".rstrip())
    thing = next((r for r in rows if r["kind"] == "thing" and r["status"] == "new"), None)
    place = next((r for r in rows if r["kind"] == "place" and r["status"] == "new"), None)
    print(f"next detail: «{thing['name_fr']}» in {thing['stage']} (mark: {thing['location_id']})" if thing else "next detail: none; every thing the stories left where the world is built is laid")
    if place:
        print(f"next place: «{place['name_fr']}», named by {int(place.get('lives') or 0)} lives")


def register_problems(place: dict) -> list[str]:
    """A room of the season is the stage of the season's places it says (``stages``): without
    one, no page ever plays there."""
    known = season_locations()
    stages = place.get("stages") or []
    problems = [] if stages else [f"{place['id']}: world.json gives it no «stages» (the season places a page set there plays in)"]
    for loc in stages + (place.get("sees") or []):
        if loc not in known:
            problems.append(f"{place['id']}: «{loc}» is not a place of the season (app/services/season/world.py)")
    return problems


def cmd_season_queue(args) -> None:
    frontier = args.frontier
    if frontier == "api":
        frontier = live_frontier()
        print(f"learners on: {', '.join(frontier) if frontier else 'none'}")
    elif frontier:
        frontier = [f.strip() for f in frontier.split(",") if f.strip()]
    rows = season_queue(frontier)
    unknown = sorted({r["location"] for r in rows} - set(season_locations()))
    for r in rows:
        where = r["stage"] or (f"{r['entry']} (no room or site yet)" if r["entry"] else "not in world.json")
        side = "" if r["ahead"] else "  (behind the frontier)"
        print(f"{r['status']:7} {r['location']:18} {r['need']['page']:10} {where}{side}")
    todo = [r for r in rows if r["status"] in ("new", "locked")]
    if unknown:
        print(f"! not places of the season (app/services/season/world.py): {', '.join(unknown)}")
    if todo:
        r = todo[0]
        print(f"next: {r['location']} ({r['name_fr']}), first needed at {r['need']['page']}")
    else:
        print("next: none; every place the season's pages are set in is built")


def cmd_queue(args) -> None:
    if getattr(args, "orders", False):
        cmd_orders_queue(args)
        return
    if getattr(args, "season", False):
        cmd_season_queue(args)
        return
    have = {p["id"]: p for p in world()["places"]}
    rows = []
    for p in papier_places():
        if not in_paris(p["geo"]):
            continue
        w = have.get(p["id"])
        status = w["status"] if w else "new"
        if w and w.get("site"):
            status = "built"
        rows.append((status, p))
    order = {"en_chantier": 0, "new": 1, "locked": 2, "built": 3, "open": 3}
    rows.sort(key=lambda r: (order.get(r[0], 9), r[1].get("week") or ""))
    for status, p in rows:
        print(f"{status:12} {p['id']:28} {p['geo']['lat']:.5f},{p['geo']['lon']:.5f}  {p['title_fr']}  ({p['path']})")
    if not rows:
        print("nothing to forge: no article names an exact place in Paris that the world lacks")


# ---------------------------------------------------------------------------------------------
# survey: the open map data around a place
# ---------------------------------------------------------------------------------------------


def cmd_survey(args) -> None:
    import overture

    place = place_of(args.id)
    brief = brief_of(args.id)
    radius = float(brief.get("radius", {}).get("build", 170)) + 60
    box = box_around(place["lat"], place["lon"], radius)
    release = args.release or overture.latest_release()
    print(f"surveying {args.id} at {place['lat']},{place['lon']} (r {radius:.0f} m) from Overture {release}", file=sys.stderr)
    layers = {}
    for name, (theme, typ, cols) in LAYERS.items():
        layers[name] = overture.read_box(release, theme, typ, box, cols)

    def enc(v):
        if isinstance(v, (bytes, bytearray)):
            return v.hex()
        return str(v)

    out = {"id": args.id, "release": release, "attribution": overture.ATTRIBUTION, "anchor": [place["lat"], place["lon"]], "box": box, "radius": radius, "surveyed": dt.date.today().isoformat(), "layers": layers}
    path = os.path.join(CACHE, args.id, "survey.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, default=enc, ensure_ascii=False)
    print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024} kB)")


# ---------------------------------------------------------------------------------------------
# draft, check, publish
# ---------------------------------------------------------------------------------------------


def is_room(pid: str) -> bool:
    path = os.path.join(BRIEFS, f"{pid}.json")
    return os.path.exists(path) and load_json(path).get("kind") == "room"


def cmd_draft(args) -> None:
    if is_room(args.id):
        # a room is written from the canon: no survey, the brief is the room
        import room

        place = place_of(args.id)
        data, report = room.draft(brief_of(args.id), place)
        path = os.path.join(ROOMS, f"{args.id}.json")
        os.makedirs(ROOMS, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(tidy(data) + "\n")
        save_json(os.path.join(CACHE, args.id, "draft-report.json"), report)
        print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024} kB)")
        for k, v in report["counts"].items():
            print(f"  {k:14} {v}")
        for w in report["warnings"]:
            print(f"  ! {w}")
        write_index()
        return
    import draft

    place = place_of(args.id)
    brief = brief_of(args.id)
    survey = load_json(os.path.join(CACHE, args.id, "survey.json"))
    if brief.get("venue"):
        # where the news happens: a set the kit draws from the survey's measures
        import venue

        site, report = venue.draft(survey, brief, place)
    else:
        site, report = draft.draft(survey, brief, place)
    path = os.path.join(SITES, f"{args.id}.json")
    save_json(path, site, compact=True)
    report_path = os.path.join(CACHE, args.id, "draft-report.json")
    save_json(report_path, report)
    print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024} kB)")
    for k, v in report["counts"].items():
        print(f"  {k:14} {v}")
    for w in report["warnings"]:
        print(f"  ! {w}")


def cmd_check(args) -> None:
    if is_room(args.id):
        import room

        problems = room.check(load_json(os.path.join(ROOMS, f"{args.id}.json")))
        problems += register_problems(place_of(args.id))
        problems += stages_problems()
    else:
        import draft

        problems = draft.check(load_json(os.path.join(SITES, f"{args.id}.json")))
    for p in problems:
        print(f"  ✗ {p}")
    if problems:
        raise SystemExit(1)
    print(f"{args.id}: ok")


def write_index() -> None:
    """`sites/index.ts` and `rooms/index.ts`: one lazy import per file, so a place's data loads only when you go there."""
    for folder, kind, what, name in ((SITES, "SiteSpec", "site", "SITE_FILES"), (ROOMS, "RoomSpec", "room", "ROOM_FILES")):
        if not os.path.isdir(folder):
            continue
        ids = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(folder, "*.json")))
        lines = [
            f"// Generated by scripts/forge/forge.py {'publish' if what == 'site' else 'draft'}: one lazy import per forged {'place' if what == 'site' else 'room'}.",
            f"import type {{ {kind} }} from '../../{what}';",
            "",
            f"export const {name}: Record<string, () => Promise<{kind}>> = {{",
        ]
        for i in ids:
            lines.append(f"  {i}: () => import('./{i}.json').then((m) => (m.default ?? m) as unknown as {kind}),")
        lines.append("};")
        with open(os.path.join(folder, "index.ts"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def cmd_publish(args) -> None:
    if is_room(args.id):
        raise SystemExit(f"{args.id} is a room of the season: it stays locked until the story reaches it, and the story opens it")
    import draft

    site = load_json(os.path.join(SITES, f"{args.id}.json"))
    problems = draft.check(site)
    if problems:
        raise SystemExit("not publishing, the site fails its checks:\n  " + "\n  ".join(problems))
    w = world()
    for p in w["places"]:
        if p["id"] == args.id:
            p["status"] = "open"
            p["site"] = args.id
    w["updated"] = dt.date.today().isoformat()
    save_world(w)
    write_index()
    print(f"{args.id} is open on the map")


def cmd_plan(args) -> None:
    """A top-down drawing of the site (var/forge/<id>/plan.svg), to look at before rendering."""
    if is_room(args.id):
        import room

        path_out = os.path.join(CACHE, args.id, "plan.svg")
        os.makedirs(os.path.dirname(path_out), exist_ok=True)
        with open(path_out, "w", encoding="utf-8") as f:
            f.write(room.plan(load_json(os.path.join(ROOMS, f"{args.id}.json"))))
        print(f"wrote {os.path.relpath(path_out, ROOT)}")
        return
    site = load_json(os.path.join(SITES, f"{args.id}.json"))
    rb = site["radius"]["build"]
    S = 4.0  # pixels a metre
    W = int(rb * 2 * S)

    def P(x, z):
        return f"{(x + rb) * S:.1f},{(z + rb) * S:.1f}"

    def path(poly):
        d = ""
        for ring_ in [poly["outer"], *poly["holes"]]:
            d += "M" + " L".join(P(x, z) for x, z in ring_) + "Z"
        return d

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{W}" viewBox="0 0 {W} {W}" style="background:#efe8da">']
    paints = {"pavement": "#d9d2c4", "squares": "#cfc2a4", "gravel": "#d8c99b", "green": "#9fb98a", "carriageway": "#6f7380"}
    for layer in ("pavement", "squares", "gravel", "green", "carriageway"):
        for poly in site["ground"][layer]:
            out.append(f'<path d="{path(poly)}" fill="{paints[layer]}" fill-rule="evenodd"/>')
    for poly in site["walk"]:
        out.append(f'<path d="{path(poly)}" fill="none" stroke="#2c6a5d" stroke-width="1.5" stroke-dasharray="6 4" fill-rule="evenodd"/>')
    for b in site["buildings"]:
        fp = b["fp"]
        fill = {"haussmann": "#e8dcc0", "faubourg": "#e3cfa6", "moderne": "#c9cdd6"}[b["style"]]
        out.append(f'<polygon points="{" ".join(P(x, z) for x, z in fp)}" fill="{fill}" stroke="#8a7d66" stroke-width="0.6"/>')
        for i, flag in enumerate(b["street"]):
            if flag:
                a, c = fp[i], fp[(i + 1) % len(fp)]
                out.append(f'<line x1="{P(*a).split(",")[0]}" y1="{P(*a).split(",")[1]}" x2="{P(*c).split(",")[0]}" y2="{P(*c).split(",")[1]}" stroke="#d8321a" stroke-width="1.6"/>')
        for r in b.get("runs", []):
            a, c = fp[r["e"]], fp[(r["e"] + 1) % len(fp)]
            ln = ((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5
            for sh in r["shops"]:
                if sh["kind"] not in ("shop", "door"):
                    continue
                u = (sh["from"] + sh["to"] + 1) / 2 / r["bays"]
                x, z = a[0] + (c[0] - a[0]) * u, a[1] + (c[1] - a[1]) * u
                col = "#1d3a8a" if sh["kind"] == "shop" else "#2c6a5d"
                out.append(f'<circle cx="{P(x, z).split(",")[0]}" cy="{P(x, z).split(",")[1]}" r="{2.2 if sh["kind"] == "shop" else 1.2}" fill="{col}"/>')
    for lm in site["landmarks"]:
        cx, cz = lm["c"]
        ux, uz = lm["u"]
        vx, vz = -uz, ux
        hl, hw = lm["len"] / 2, lm["wid"] / 2
        pts = [(cx + ux * a * hl + vx * b * hw, cz + uz * a * hl + vz * b * hw) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        out.append(f'<polygon points="{" ".join(P(x, z) for x, z in pts)}" fill="#c2890f" fill-opacity="0.55" stroke="#14110d"/>')
    for c in site["crossings"]:
        out.append(f'<circle cx="{P(*c["c"]).split(",")[0]}" cy="{P(*c["c"]).split(",")[1]}" r="3" fill="#f8f3e8" stroke="#14110d"/>')
    for x, z, s in site["trees"]:
        out.append(f'<circle cx="{P(x, z).split(",")[0]}" cy="{P(x, z).split(",")[1]}" r="{6 * s:.1f}" fill="#2c6a5d" fill-opacity="0.45"/>')
    for x, z in site["lamps"]:
        out.append(f'<circle cx="{P(x, z).split(",")[0]}" cy="{P(x, z).split(",")[1]}" r="2" fill="#f3c318" stroke="#14110d" stroke-width="0.5"/>')
    for st in site["stalls"]:
        x, z = st["c"]
        out.append(f'<circle cx="{P(x, z).split(",")[0]}" cy="{P(x, z).split(",")[1]}" r="4" fill="#d8321a" fill-opacity="0.8"/>')
    for f in site["fences"]:
        out.append(f'<polyline points="{" ".join(P(x, z) for x, z in f)}" fill="none" stroke="#2c6a5d" stroke-width="4"/>')
    for sp in site["spots"]:
        x, z = sp["at"]
        out.append(f'<circle cx="{P(x, z).split(",")[0]}" cy="{P(x, z).split(",")[1]}" r="1.6" fill="none" stroke="#1d3a8a"/>')
    for pl in site["plaques"]:
        b = site["buildings"][pl["b"]]
        a, c = b["fp"][pl["e"]], b["fp"][(pl["e"] + 1) % len(b["fp"])]
        ln = ((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5
        x, z = a[0] + (c[0] - a[0]) * pl["u"] / ln, a[1] + (c[1] - a[1]) * pl["u"] / ln
        out.append(f'<text x="{P(x, z).split(",")[0]}" y="{P(x, z).split(",")[1]}" font-size="11" font-family="sans-serif" fill="#1d3a8a">{pl["text"]}</text>')
    sx, sz = site["start"]["pos"]
    out.append(f'<circle cx="{P(sx, sz).split(",")[0]}" cy="{P(sx, sz).split(",")[1]}" r="7" fill="none" stroke="#d8321a" stroke-width="3"/>')
    out.append("</svg>")
    path_out = os.path.join(CACHE, args.id, "plan.svg")
    os.makedirs(os.path.dirname(path_out), exist_ok=True)
    with open(path_out, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"wrote {os.path.relpath(path_out, ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue")
    q.add_argument("--season", action="store_true", help="the season's places instead of the Papier's")
    q.add_argument("--orders", action="store_true", help="what the learners' stories left in the quarter (the server's world-orders) instead")
    q.add_argument("--from", dest="frontier", default=None, help="the segment a learner is on (g3), several (g3,t1), or api: the segments the server says the season's learners are on; with --orders: api (the default) or a saved world-orders file")
    sub.add_parser("news")
    s = sub.add_parser("survey")
    s.add_argument("id")
    s.add_argument("--release", default=None)
    for name in ("draft", "check", "publish", "plan"):
        sub.add_parser(name).add_argument("id")
    sub.add_parser("index")
    sub.add_parser("stages")
    args = ap.parse_args()
    sys.path.insert(0, HERE)
    if args.cmd == "index":
        write_index()
        return
    {"queue": cmd_queue, "news": cmd_news, "survey": cmd_survey, "draft": cmd_draft, "check": cmd_check, "publish": cmd_publish, "plan": cmd_plan, "stages": cmd_stages}[args.cmd](args)


if __name__ == "__main__":
    main()
