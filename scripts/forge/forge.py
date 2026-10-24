#!/usr/bin/env python3
"""The forge: Le Quartier's world grows one corner of Paris at a time.

Run from the repository root, in a venv with ``scripts/forge/requirements.txt``::

    python scripts/forge/forge.py news                  # the map's news layer: every place the Papier names
    python scripts/forge/forge.py queue                 # places the Papier names that are not built yet
    python scripts/forge/forge.py survey marche_aligre  # open map data around it -> var/forge/<id>/survey.json
    python scripts/forge/forge.py draft marche_aligre   # survey + brief -> lib/quartier/world/sites/<id>.json
    python scripts/forge/forge.py check marche_aligre   # the site's invariants (also in site.test.js)
    python scripts/forge/forge.py publish marche_aligre # open it on the map (world.json, sites/index.ts)

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
BRIEFS = os.path.join(HERE, "briefs")
CACHE = os.path.join(ROOT, "var", "forge")
PAPIER = os.path.join(ROOT, "app", "services", "revue")

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


def cmd_queue(_args) -> None:
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


def cmd_draft(args) -> None:
    import draft

    place = place_of(args.id)
    brief = brief_of(args.id)
    survey = load_json(os.path.join(CACHE, args.id, "survey.json"))
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
    import draft

    site = load_json(os.path.join(SITES, f"{args.id}.json"))
    problems = draft.check(site)
    for p in problems:
        print(f"  ✗ {p}")
    if problems:
        raise SystemExit(1)
    print(f"{args.id}: ok")


def write_index() -> None:
    """`sites/index.ts`: one lazy import per site file, so a site's data loads only when you go there."""
    ids = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(SITES, "*.json")))
    lines = [
        "// Generated by scripts/forge/forge.py publish: one lazy import per forged place.",
        "import type { SiteSpec } from '../../site';",
        "",
        "export const SITE_FILES: Record<string, () => Promise<SiteSpec>> = {",
    ]
    for i in ids:
        lines.append(f"  {i}: () => import('./{i}.json').then((m) => (m.default ?? m) as unknown as SiteSpec),")
    lines.append("};")
    with open(os.path.join(SITES, "index.ts"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def cmd_publish(args) -> None:
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
    sub.add_parser("queue")
    sub.add_parser("news")
    s = sub.add_parser("survey")
    s.add_argument("id")
    s.add_argument("--release", default=None)
    for name in ("draft", "check", "publish", "plan"):
        sub.add_parser(name).add_argument("id")
    sub.add_parser("index")
    args = ap.parse_args()
    sys.path.insert(0, HERE)
    if args.cmd == "index":
        write_index()
        return
    {"queue": cmd_queue, "news": cmd_news, "survey": cmd_survey, "draft": cmd_draft, "check": cmd_check, "publish": cmd_publish, "plan": cmd_plan}[args.cmd](args)


if __name__ == "__main__":
    main()
