"""Draft a forged place: from a survey and a brief to the site file the game builds.

Everything here is in local metres round the place's anchor, the game's own frame: x east,
z south, y up. The steps:

1. **Buildings**: Overture's footprints, holes dropped, simplified to the half metre, cut into
   convex pieces (the kit roofs a convex footprint) with each edge marked as street or party
   wall. Floors come from ``num_floors`` (or the neighbours'), the style from the floors.
2. **Street space**: the open ground reachable from a street (courtyards are not), split into
   carriageway (each road buffered to its width, kept 1.8 m off the façades), pavement, paved
   squares and green.
3. **Fronts**: each street edge becomes a façade run in bays; the trades of Overture's places
   become shop fronts with a generic French fascia (never a business's own name), the house
   numbers become doors with their plaques, the rest ground-floor windows and carriage doors.
4. **Street furniture** from the data: lamps, benches, trees, bicycle hoops, glass bins, post
   boxes, zebra crossings; street-name plaques on the corners.
5. **What the data cannot say**, from the brief: the landmark (built by its own kit), the
   market's stalls, where you arrive, who stands where.
6. **The edge**: where a street leaves the walkable circle, a site hoarding closes it; the
   buildings go on beyond it to the haze.
"""
from __future__ import annotations

import math
import random
import re
from collections import defaultdict

import numpy as np
import shapely
from shapely import wkb
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union
from shapely.prepared import prep

# --------------------------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------------------------

# carriageway width in metres by road class (Overture's width_rules win when present)
CARRIAGEWAY = {
    "trunk": 16.0,
    "primary": 13.0,
    "secondary": 11.0,
    "tertiary": 9.0,
    "unclassified": 6.5,
    "residential": 6.0,
    "living_street": 4.5,
    "service": 3.6,
}
# classes that are streets you walk along (the seeds of street space)
STREETS = set(CARRIAGEWAY) | {"pedestrian"}

STYLE_BAY = {"haussmann": 3.0, "faubourg": 2.7, "moderne": 3.3}

# taxonomy.primary -> (fascia, second line, paint, open in the morning)
TRADES: dict[str, tuple[str, str | None, str, bool]] = {
    "bakery": ("Boulangerie", "pain · viennoiseries", "ochre", True),
    "pastry_shop": ("Pâtisserie", None, "vermilion", True),
    "butcher_shop": ("Boucherie", "volailles · charcuterie", "oxblood", True),
    "cheese_shop": ("Fromagerie", "crèmerie", "green", True),
    "fishmonger": ("Poissonnerie", "arrivage du jour", "cobalt", True),
    "grocery_store": ("Épicerie", None, "green", True),
    "organic_grocery_store": ("Épicerie bio", None, "green", True),
    "produce_store": ("Primeur", "fruits · légumes", "green", True),
    "convenience_store": ("Alimentation", "ouvert 7 j / 7", "cobalt", True),
    "supermarket": ("Supérette", None, "cobalt", True),
    "beer_wine_spirits_store": ("Cave", "vins · spiritueux", "oxblood", True),
    "liquor_store": ("Cave", "vins · spiritueux", "oxblood", True),
    "chocolatier": ("Chocolatier", None, "ochre", True),
    "tea_room": ("Salon de thé", None, "vermilion", True),
    "cafe": ("Café", None, "vermilion", True),
    "coffee_shop": ("Café", "torréfaction", "ink", True),
    "pharmacy": ("Pharmacie", None, "green", True),
    "restaurant": ("Restaurant", None, "ink", False),
    "french_restaurant": ("Bistrot", None, "oxblood", False),
    "pizza_restaurant": ("Pizzeria", None, "vermilion", False),
    "italian_restaurant": ("Trattoria", None, "green", False),
    "japanese_restaurant": ("Cantine japonaise", None, "ink", False),
    "chinese_restaurant": ("Restaurant chinois", None, "vermilion", False),
    "vietnamese_restaurant": ("Phở", "cuisine vietnamienne", "ochre", False),
    "lebanese_restaurant": ("Traiteur libanais", None, "green", True),
    "thai_restaurant": ("Cuisine thaïe", None, "ochre", False),
    "fast_food_restaurant": ("Snack", None, "vermilion", True),
    "sandwich_shop": ("Sandwicherie", None, "ochre", True),
    "caterer": ("Traiteur", None, "green", True),
    "pancake_house": ("Crêperie", None, "ochre", False),
    "bar": ("Bar", None, "ink", False),
    "cocktail_bar": ("Bar", None, "ink", False),
    "beer_bar": ("Bar à bières", None, "ochre", False),
    "wine_bar": ("Bar à vins", None, "oxblood", False),
    "tapas_bar": ("Bar à tapas", None, "vermilion", False),
    "hair_salon": ("Coiffure", None, "ink", True),
    "barber": ("Barbier", None, "ink", True),
    "beauty_salon": ("Institut", "soins · beauté", "vermilion", True),
    "nail_salon": ("Institut", "ongles", "vermilion", True),
    "clothing_store": ("Vêtements", None, "ink", True),
    "womens_clothing_store": ("Mode", None, "ink", True),
    "childrens_clothing_store": ("Vêtements enfants", None, "cobalt", True),
    "fashion_boutique": ("Boutique", None, "ink", True),
    "shoe_store": ("Chaussures", None, "oxblood", True),
    "shoe_repair": ("Cordonnerie", "clés minute", "ochre", True),
    "jewelry_store": ("Bijouterie", None, "ink", True),
    "eyewear_store": ("Opticien", None, "cobalt", True),
    "furniture_store": ("Meubles", None, "oxblood", True),
    "furniture_reupholstery": ("Tapissier", "réfection de sièges", "green", True),
    "home_goods_store": ("Maison", "arts de la table", "ochre", True),
    "hardware_store": ("Quincaillerie", None, "cobalt", True),
    "bookstore": ("Librairie", None, "oxblood", True),
    "vinyl_record_store": ("Disquaire", None, "ink", True),
    "art_gallery": ("Galerie", None, "ink", False),
    "flowers_and_gifts_store": ("Fleuriste", None, "green", True),
    "florist": ("Fleuriste", None, "green", True),
    "gift_shop": ("Cadeaux", None, "vermilion", True),
    "toy_store": ("Jouets", None, "sunflower", True),
    "fabric_store": ("Tissus", "mercerie", "ochre", True),
    "electronics_store": ("Téléphonie", "réparation", "cobalt", True),
    "bank": ("Banque", None, "cobalt", True),
    "real_estate_agent": ("Immobilier", None, "cobalt", True),
    "post_office": ("Bureau de poste", None, "sunflower", True),
    "laundromat": ("Laverie", "libre-service", "cobalt", True),
    "dry_cleaning": ("Pressing", None, "cobalt", True),
    "tobacco_shop": ("Tabac", "presse", "vermilion", True),
    "newsstand": ("Presse", None, "vermilion", True),
    "hotel": ("Hôtel", None, "ink", True),
}

# --------------------------------------------------------------------------------------------
# frame
# --------------------------------------------------------------------------------------------


class Local:
    """Longitude and latitude to the game's metres round an anchor (x east, z south)."""

    def __init__(self, lat: float, lon: float):
        phi = math.radians(lat)
        self.north = 111132.954 - 559.822 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
        self.east = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi) + 0.118 * math.cos(5 * phi)
        self.lat = lat
        self.lon = lon

    def xz(self, lon: float, lat: float) -> tuple[float, float]:
        return (lon - self.lon) * self.east, -(lat - self.lat) * self.north

    def geom(self, row: dict):
        g = row["geometry"]
        raw = bytes.fromhex(g) if isinstance(g, str) else g
        geo = wkb.loads(raw)

        def to_local(c: np.ndarray) -> np.ndarray:
            out = np.empty_like(c)
            out[:, 0] = (c[:, 0] - self.lon) * self.east
            out[:, 1] = -(c[:, 1] - self.lat) * self.north
            return out

        return shapely.transform(geo, to_local)


def name_of(row: dict) -> str | None:
    n = row.get("names")
    if isinstance(n, dict):
        return n.get("primary")
    return None


def r2(v: float) -> float:
    return round(float(v), 2)


def ring(coords) -> list[list[float]]:
    pts = [[r2(x), r2(z)] for x, z in list(coords)]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def polygons(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]


def lines(g) -> list[LineString]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    out: list[LineString] = []
    for p in getattr(g, "geoms", []):
        out += lines(p)
    return out


def poly_out(p: Polygon) -> dict:
    return {"outer": ring(p.exterior.coords), "holes": [ring(h.coords) for h in p.interiors if Polygon(h).area > 0.6]}


# --------------------------------------------------------------------------------------------
# convex pieces
# --------------------------------------------------------------------------------------------


def cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def drop_collinear(pts: list[tuple[float, float]], tol: float = 0.05) -> list[tuple[float, float]]:
    out = list(pts)
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            ab = math.dist(a, b)
            bc = math.dist(b, c)
            if ab < 0.15 or bc < 0.15 or abs(cross(a, b, c)) / max(ab + bc, 1e-9) < tol:
                out.pop(i)
                changed = True
                break
    return out


def is_convex(pts: list[tuple[float, float]], tol: float = 1e-3) -> bool:
    sign = 0
    n = len(pts)
    for i in range(n):
        c = cross(pts[i], pts[(i + 1) % n], pts[(i + 2) % n])
        if abs(c) < tol:
            continue
        s = 1 if c > 0 else -1
        if sign and s != sign:
            return False
        sign = s
    return True


def convex_pieces(poly: Polygon) -> list[list[tuple[float, float]]]:
    """Hertel–Mehlhorn: triangulate (constrained Delaunay, no new points), then merge neighbours
    while the union stays convex. Every edge of a piece is an edge of the polygon or a diagonal."""
    pts = drop_collinear(list(orient(poly, 1.0).exterior.coords)[:-1])
    if len(pts) < 3:
        return []
    if is_convex(pts):
        return [pts]
    tris = shapely.constrained_delaunay_triangles(Polygon(pts))
    pieces = [list(orient(t, 1.0).exterior.coords)[:-1] for t in tris.geoms if t.area > 0.01]
    key = lambda p: (round(p[0], 3), round(p[1], 3))  # noqa: E731
    merged = True
    while merged:
        merged = False
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                a, b = pieces[i], pieces[j]
                ka = [key(p) for p in a]
                kb = [key(p) for p in b]
                shared = None
                for s in range(len(a)):
                    e0, e1 = ka[s], ka[(s + 1) % len(a)]
                    for t in range(len(b)):
                        if kb[t] == e1 and kb[(t + 1) % len(b)] == e0:
                            shared = (s, t)
                            break
                    if shared:
                        break
                if not shared:
                    continue
                s, t = shared
                # walk a from its edge's end round to its start, then b likewise
                ring_ = [a[(s + 1 + k) % len(a)] for k in range(len(a))]  # starts at a's edge end
                ring_ = ring_[:-1]  # drops a's edge start (b brings it)
                ring_ += [b[(t + 1 + k) % len(b)] for k in range(len(b) - 1)]
                cand = drop_collinear(ring_, 0.02)
                if len(cand) >= 3 and is_convex(cand):
                    pieces[i] = cand
                    pieces.pop(j)
                    merged = True
                    break
            if merged:
                break
    return pieces


# --------------------------------------------------------------------------------------------
# the draft
# --------------------------------------------------------------------------------------------


def draft(survey: dict, brief: dict, place: dict) -> tuple[dict, dict]:
    L = Local(place["lat"], place["lon"])
    layers = survey["layers"]
    r_walk = float(brief.get("radius", {}).get("walk", 110))
    r_build = float(brief.get("radius", {}).get("build", 170))
    centre = Point(0, 0)
    disc_build = centre.buffer(r_build, 96)
    disc_walk = centre.buffer(r_walk, 96)
    seed = sum(ord(c) for c in brief["id"]) * 7919
    rng = random.Random(seed)  # noqa: S311 - a seeded layout, not security
    warnings: list[str] = []
    level = set(brief.get("level_streets", []))

    # ---- landmarks named in the brief ---------------------------------------------------
    marks = brief.get("landmarks", [])
    landmark_rows: dict[str, tuple[dict, Polygon]] = {}

    # ---- buildings ----------------------------------------------------------------------
    raw: list[tuple[dict, Polygon]] = []
    for row in layers["buildings"]:
        if str(row.get("is_underground")) == "True" or row.get("class") == "roof":
            continue
        g = L.geom(row)
        for p in polygons(g):
            p = Polygon(p.exterior).buffer(0)
            if p.is_empty or p.area < 10 or p.centroid.distance(centre) > r_build:
                continue
            nm = name_of(row)
            mark = next((m for m in marks if nm and m["match"].lower() in nm.lower()), None)
            if mark and mark["match"] not in landmark_rows:
                landmark_rows[mark["match"]] = (row, p)
                continue
            raw.append((row, p))
    for m in marks:
        if m["match"] not in landmark_rows:
            warnings.append(f"landmark {m['match']!r} not found in the buildings")

    built = unary_union([p for _, p in raw] + [p for m, (_, p) in landmark_rows.items() if next(x for x in marks if x["match"] == m)["kind"] != "halle"])

    # ---- streets ------------------------------------------------------------------------
    roads: list[tuple[dict, LineString, str | None, str]] = []
    for row in layers["segments"]:
        if row.get("subtype") != "road":
            continue
        cls = row.get("class") or ""
        g = L.geom(row)
        if g.distance(centre) > r_build + 40:
            continue
        for ln in lines(g):
            roads.append((row, ln, name_of(row), cls))
    seeds = unary_union([ln.buffer(1.2) for _, ln, _, cls in roads if cls in STREETS])
    open_ = disc_build.difference(built)
    street = unary_union([c for c in polygons(open_) if c.intersects(seeds)])
    street = street.buffer(0)
    street_p = prep(street)

    # carriageway
    halle = [p for m, (_, p) in landmark_rows.items() if next(x for x in marks if x["match"] == m)["kind"] == "halle"]
    keep_off = built.buffer(1.8)
    if halle:
        keep_off = keep_off.union(unary_union(halle).buffer(2.4))
    ways = []
    for row, ln, nm, cls in roads:
        if cls not in CARRIAGEWAY or (nm and nm in level):
            continue
        w = CARRIAGEWAY[cls]
        rules = row.get("width_rules")
        if isinstance(rules, list) and rules and isinstance(rules[0], dict) and rules[0].get("value"):
            try:
                w = max(3.0, min(20.0, float(rules[0]["value"])))
            except (TypeError, ValueError):
                pass
        ways.append(ln.buffer(w / 2, quad_segs=3, cap_style="round", join_style="round"))
    carriage = unary_union(ways).intersection(street).difference(keep_off) if ways else Polygon()
    carriage = carriage.buffer(-0.4).buffer(0.4)
    carriage = unary_union([p for p in polygons(carriage) if p.area > 12])

    # squares (paved, level), parks (gravel), green (planted, not walked on)
    squares, gravel, green = [], [], []
    for row in layers["landuse"]:
        cls = row.get("class")
        g = L.geom(row)
        if g.distance(centre) > r_build:
            continue
        if cls == "pedestrian" or (row.get("subtype") == "pedestrian"):
            squares += polygons(g)
        elif cls in ("park",):
            gravel += polygons(g)
        elif cls in ("grass", "flowerbed", "garden"):
            green += polygons(g)
    for _row, ln, nm, cls in roads:
        if cls == "pedestrian" or (nm and nm in level and cls in STREETS):
            squares.append(ln.buffer(4.5, quad_segs=3))
    squares_u = unary_union(squares).intersection(street).difference(carriage) if squares else Polygon()
    green_u = unary_union(green).intersection(street).difference(carriage).buffer(-0.2) if green else Polygon()
    gravel_u = unary_union(gravel).intersection(street).difference(carriage).difference(green_u) if gravel else Polygon()
    squares_u = squares_u.difference(gravel_u).difference(green_u)
    pavement = street.difference(carriage).difference(squares_u).difference(gravel_u).difference(green_u)

    walk_area = street.intersection(disc_walk).difference(green_u)
    walk_area = unary_union([p for p in polygons(walk_area) if p.area > 30])
    walk_p = prep(walk_area)
    walkfoot_p = prep(walk_area.difference(carriage))

    # ---- buildings to the kit -------------------------------------------------------------
    floors_known = []
    for row, p in raw:
        f = row.get("num_floors")
        if f not in (None, "None"):
            try:
                floors_known.append((p.centroid, int(float(f))))
            except ValueError:
                pass

    def floors_near(c: Point) -> int:
        near = sorted(floors_known, key=lambda t: t[0].distance(c))[:5]
        if not near:
            return 6
        vals = sorted(f for _, f in near)
        return vals[len(vals) // 2]

    runs_all: list[dict] = []  # every façade run, for shops, doors and plaques
    out_buildings = []
    n_parts = 0
    for bi, (row, p) in enumerate(sorted(raw, key=lambda t: (round(t[1].centroid.x), round(t[1].centroid.y)))):
        simple = p.simplify(0.35, preserve_topology=True)
        if not isinstance(simple, Polygon) or simple.area < 8:
            continue
        f = row.get("num_floors")
        try:
            floors = int(float(f)) if f not in (None, "None") else floors_near(p.centroid)
        except ValueError:
            floors = floors_near(p.centroid)
        floors = max(1, min(12, floors))
        # Paris counts the attic floors too: an R+5 under its mansard is seven or eight levels.
        # Only a flat roof, a great height or a housing estate's name says the building is modern.
        nm = (name_of(row) or "").lower()
        flat = str(row.get("roof_shape")) == "flat"
        modern = (flat and floors >= 4) or floors >= 10 or (floors >= 8 and p.area >= 700) or nm.startswith(("résidence", "village", "cité", "ensemble"))
        if modern:
            style = "moderne"
            storeys = max(1, min(9, floors - 1))
        elif floors >= 7:
            style = "haussmann"
            storeys = min(6, floors - 2)
        elif floors >= 5:
            style = "haussmann" if rng.random() > float(brief.get("faubourg_share", 0.4)) else "faubourg"
            storeys = min(5, floors - 1)
        else:
            style = "faubourg"
            storeys = max(1, floors - 1)
        wall = rng.randrange(7)
        if style == "haussmann":
            balconies = [2, min(5, storeys)] if storeys >= 4 else [2]
        elif style == "faubourg":
            balconies = [1] if rng.random() < 0.35 else []
        else:
            balconies = []
        near_walk = p.distance(walk_area) < 30
        pieces = convex_pieces(simple)
        if not pieces:
            continue
        # the street edges of the whole outline, by their end points
        outline = drop_collinear(list(orient(simple, 1.0).exterior.coords)[:-1])
        k = lambda q: (round(q[0], 3), round(q[1], 3))  # noqa: E731
        street_edges = set()
        for i in range(len(outline)):
            a, b = outline[i], outline[(i + 1) % len(outline)]
            ln = math.dist(a, b)
            if ln < 1.6:
                continue
            # outward normal of a CCW outline in (x, z): (dz, -dx)
            nx, nz = (b[1] - a[1]) / ln, -(b[0] - a[0]) / ln
            hits = 0
            tests = 0
            for t in (0.25, 0.5, 0.75) if ln > 6 else (0.5,):
                for d in (1.2, 2.6):
                    tests += 1
                    q = Point(a[0] + (b[0] - a[0]) * t + nx * d, a[1] + (b[1] - a[1]) * t + nz * d)
                    if street_p.contains(q):
                        hits += 1
            if hits * 2 > tests:
                street_edges.add((k(a), k(b)))
        for pi, piece in enumerate(pieces):
            # the kit's winding: negative signed area in (x, z), so each edge's street side is
            # on its right (the outline above was CCW, so reverse it)
            fp = list(reversed(piece))
            flags = []
            runs = []
            for i in range(len(fp)):
                a, b = fp[i], fp[(i + 1) % len(fp)]
                is_street = (k(b), k(a)) in street_edges
                flags.append(1 if is_street else 0)
                ln = math.dist(a, b)
                if is_street and ln >= 2.2:
                    bays = max(1, round(ln / STYLE_BAY[style]))
                    run = {"e": i, "bays": bays, "shops": [], "_a": a, "_b": b, "_len": ln, "_b_i": len(out_buildings), "_style": style}
                    runs.append(run)
                    runs_all.append(run)
            n_parts += 1
            out_buildings.append(
                {
                    "fp": [[r2(x), r2(z)] for x, z in fp],
                    "street": flags,
                    "runs": runs,
                    "storeys": storeys,
                    "style": style,
                    "wall": wall,
                    "balconies": balconies,
                    "lit": round(rng.uniform(0.2, 0.4), 2),
                    "seed": seed + bi * 31 + pi,
                    **({"lod": 1} if not near_walk else {}),
                }
            )

    # ---- what stands at the ground floor ---------------------------------------------------
    def run_at(x: float, z: float, reach: float):
        best = None
        for run in runs_all:
            a, b = run["_a"], run["_b"]
            seg = LineString([a, b])
            d = seg.distance(Point(x, z))
            if d < reach and (best is None or d < best[0]):
                u = seg.project(Point(x, z))
                best = (d, run, u)
        return best

    def free_bay(run: dict, want: int) -> int | None:
        taken = set()
        for s in run["shops"]:
            taken.update(range(s["from"], s["to"] + 1))
        for off in (0, 1, -1, 2, -2, 3, -3):
            i = want + off
            if 0 <= i < run["bays"] and i not in taken:
                return i
        return None

    shops_n = 0
    trades_seen: dict[str, int] = defaultdict(int)
    for row in layers["places"]:
        tax = row.get("taxonomy")
        primary = tax.get("primary") if isinstance(tax, dict) else None
        if primary not in TRADES or row.get("operating_status") == "permanently_closed":
            continue
        try:
            conf = float(row.get("confidence") or 0)
        except (TypeError, ValueError):
            conf = 0
        if conf < 0.45:
            continue
        g = L.geom(row)
        if g.distance(centre) > r_build:
            continue
        hit = run_at(g.x, g.y, 9.0)
        if not hit:
            continue
        _, run, u = hit
        bw = run["_len"] / run["bays"]
        i = free_bay(run, int(u // bw))
        if i is None:
            continue
        name, trade, paint, morning = TRADES[primary]
        trades_seen[name] += 1
        open_now = morning or brief.get("ambiance") != "matin"
        shop = {"from": i, "to": i, "kind": "shop" if open_now else "shutter", "paint": paint, "name": name}
        if trade:
            shop["trade"] = trade
        if open_now and name in ("Boulangerie", "Primeur", "Fromagerie", "Boucherie", "Poissonnerie", "Café", "Fleuriste", "Épicerie"):
            shop["awning"] = paint if paint != "ink" else "vermilion"
        # a wide shop takes the next bay too
        if run["bays"] - i > 1 and rng.random() < 0.35 and free_bay(run, i + 1) == i + 1:
            shop["to"] = i + 1
        run["shops"].append(shop)
        shops_n += 1

    doors_n = 0
    numbers_seen = set()
    for row in layers["addresses"]:
        num = str(row.get("number") or "").strip()
        if not num or not re.match(r"^\d+( ?(bis|ter))?$", num):
            continue
        g = L.geom(row)
        if g.distance(centre) > r_build:
            continue
        hit = run_at(g.x, g.y, 7.0)
        if not hit:
            continue
        _, run, u = hit
        key = (num, row.get("street"))
        if key in numbers_seen:
            continue
        numbers_seen.add(key)
        bw = run["_len"] / run["bays"]
        i = free_bay(run, int(u // bw))
        if i is None:
            continue
        run["shops"].append({"from": i, "to": i, "kind": "door", "paint": rng.choice(["green", "greenDark", "cobalt", "oxblood", "ink"]), "number": num})
        doors_n += 1

    # the rest of each ground floor: windows behind bars, a carriage door, now and then a closed shop
    commerce = float(brief.get("commerce", 0.5))
    for run in runs_all:
        has_door = any(s["kind"] == "door" for s in run["shops"])
        for i in range(run["bays"]):
            if free_bay(run, i) != i:
                continue
            roll = rng.random()
            if not has_door and run["bays"] >= 3 and i == run["bays"] // 2:
                run["shops"].append({"from": i, "to": i, "kind": "door", "paint": rng.choice(["green", "greenDark", "cobalt", "oxblood"])})
                has_door = True
            elif roll < commerce * 0.22:
                run["shops"].append({"from": i, "to": i, "kind": "shutter", "paint": rng.choice(["cobalt", "green", "oxblood", "ink", "ochre"])})
            elif roll < 0.82:
                run["shops"].append({"from": i, "to": i, "kind": "window"})
            else:
                run["shops"].append({"from": i, "to": i, "kind": "wall"})
        run["shops"].sort(key=lambda s: s["from"])

    # ---- which street a run looks onto, for the plaques -----------------------------------------
    named = [(nm, ln) for _, ln, nm, cls in roads if nm and cls in STREETS]
    plaques = []
    by_street: dict[str, list] = defaultdict(list)
    for run in runs_all:
        a, b = run["_a"], run["_b"]
        ln = run["_len"]
        nx, nz = -(b[1] - a[1]) / ln, (b[0] - a[0]) / ln  # the kit's outward normal (street side)
        mid = Point((a[0] + b[0]) / 2 + nx * 3, (a[1] + b[1]) / 2 + nz * 3)
        if mid.distance(centre) > r_walk + 12:
            continue
        best = None
        for nm, sl in named:
            d = sl.distance(mid)
            if d < 14 and (best is None or d < best[0]):
                # roughly parallel
                q = sl.interpolate(sl.project(mid))
                q2 = sl.interpolate(min(sl.length, sl.project(mid) + 1.0))
                tx, tz = q2.x - q.x, q2.y - q.y
                tl = math.hypot(tx, tz) or 1
                if abs((tx * (b[0] - a[0]) + tz * (b[1] - a[1])) / (tl * ln)) > 0.85:
                    best = (d, nm)
        if best:
            run["_street"] = best[1]
            by_street[best[1]].append(run)
    # every junction of two named streets: on each corner building, the plaque of the street
    # its façade looks onto, a metre from the corner, as Paris hangs them
    by_name: dict[str, list[LineString]] = defaultdict(list)
    for nm, sl in named:
        by_name[nm].append(sl)
    merged = {nm: unary_union(ls) for nm, ls in by_name.items()}
    junctions: list[tuple[Point, set[str]]] = []
    names_ = sorted(merged)
    for i, n1 in enumerate(names_):
        for n2 in names_[i + 1 :]:
            x = merged[n1].intersection(merged[n2].buffer(1.0))
            if x.is_empty:
                continue
            q = x.centroid
            if q.distance(centre) > r_walk + 8:
                continue
            got = next((j for j in junctions if j[0].distance(q) < 6), None)
            if got:
                got[1].update((n1, n2))
            else:
                junctions.append((q, {n1, n2}))
    for jq, streets_here in junctions:
        for nm in sorted(streets_here):
            ends = []
            for run in by_street.get(nm, []):
                for end in ("a", "b"):
                    p = run["_a"] if end == "a" else run["_b"]
                    d = jq.distance(Point(p))
                    if d < 22:
                        ends.append((d, run, end))
            ends.sort(key=lambda t: t[0])
            used_sides: list[tuple[float, float]] = []
            for _, run, end in ends:
                a, b, ln = run["_a"], run["_b"], run["_len"]
                nx, nz = -(b[1] - a[1]) / ln, (b[0] - a[0]) / ln
                # one plaque per side of the street at each junction
                if any(nx * sx + nz * sz > 0.5 for sx, sz in used_sides):
                    continue
                used_sides.append((nx, nz))
                # on the corner pier, clear of the first window and of any fascia
                u = min(0.45, ln / 2) if end == "a" else max(ln - 0.45, ln / 2)
                plaques.append({"b": run["_b_i"], "e": run["e"], "u": r2(u), "text": nm})
                if len(used_sides) == 2:
                    break

    # ---- street furniture ---------------------------------------------------------------------
    def on_foot(x: float, z: float) -> bool:
        return walkfoot_p.contains(Point(x, z))

    def spaced(pts: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for p in pts:
            if all(math.dist(p, q) >= gap for q in out):
                out.append(p)
        return out

    def facing_street(x: float, z: float) -> float:
        """The angle (about y) that turns a bench's seat away from the nearest façade."""
        c = Point(x, z)
        if built.is_empty:
            return 0.0
        q = nearest_points(built.boundary, c)[0]
        return math.atan2(x - q.x, z - q.y)

    lamps, benches, hoops, bins, posts = [], [], [], [], []
    for row in layers["infra"]:
        cls = row.get("class")
        g = L.geom(row)
        if not isinstance(g, Point) or g.distance(centre) > r_walk + 25:
            continue
        x, z = g.x, g.y
        inside_walk = street_p.contains(g) and not carriage.contains(g)
        if cls == "street_lamp" and inside_walk:
            lamps.append((x, z))
        elif cls == "bench" and inside_walk:
            benches.append((x, z))
        elif cls == "bicycle_parking" and street_p.contains(g):
            hoops.append((x, z))
        elif cls == "recycling" and street_p.contains(g):
            bins.append((x, z))
        elif cls == "post_box" and inside_walk:
            posts.append((x, z))
    lamps = spaced(lamps, 9.0)
    trees = []
    for row in layers["land"]:
        if row.get("class") != "tree":
            continue
        g = L.geom(row)
        if isinstance(g, Point) and g.distance(centre) < r_build - 5 and street_p.contains(g) and not carriage.buffer(0.6).contains(g):
            trees.append((g.x, g.y))
    trees = spaced(trees, 3.2)

    crossings = []
    drive_lines = [ln for row, ln, nm, cls in roads if cls in CARRIAGEWAY and not (nm and nm in level)]
    for row in layers["infra"]:
        if row.get("class") != "crossing":
            continue
        g = L.geom(row)
        if not isinstance(g, Point) or g.distance(centre) > r_walk + 10 or not carriage.contains(g):
            continue
        best = min(drive_lines, key=lambda ln: ln.distance(g), default=None)
        if best is None or best.distance(g) > 4:
            continue
        s = best.project(g)
        q0 = best.interpolate(max(0, s - 1))
        q1 = best.interpolate(min(best.length, s + 1))
        tx, tz = q1.x - q0.x, q1.y - q0.y
        tl = math.hypot(tx, tz) or 1
        tx, tz = tx / tl, tz / tl
        # the chord across the carriageway through the point
        far = LineString([(g.x - tz * 20, g.y + tx * 20), (g.x + tz * 20, g.y - tx * 20)])
        chord = far.intersection(carriage)
        seg = next((c for c in lines(chord) if c.distance(g) < 0.3), None)
        if seg is None:
            continue
        crossings.append({"c": [r2(seg.centroid.x), r2(seg.centroid.y)], "t": [round(tx, 3), round(tz, 3)], "w": r2(seg.length)})
    crossings_out = []
    for c in crossings:
        if all(math.dist(c["c"], d["c"]) > 4 for d in crossings_out):
            crossings_out.append(c)

    # ---- landmarks --------------------------------------------------------------------------
    landmarks = []
    for m in marks:
        got = landmark_rows.get(m["match"])
        if not got:
            continue
        row, p = got
        rect = p.minimum_rotated_rectangle
        cs = list(rect.exterior.coords)[:4]
        e0 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
        e1 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
        l0, l1 = math.hypot(*e0), math.hypot(*e1)
        if l0 >= l1:
            ux, uz, length, width = e0[0] / l0, e0[1] / l0, l0, l1
        else:
            ux, uz, length, width = e1[0] / l1, e1[1] / l1, l1, l0
        c = rect.centroid
        h = row.get("height")
        try:
            height = float(h) if h not in (None, "None") else None
        except ValueError:
            height = None
        landmarks.append(
            {
                "kind": m["kind"],
                "name": m.get("name", ""),
                "c": [r2(c.x), r2(c.y)],
                "u": [round(ux, 4), round(uz, 4)],
                "len": r2(length),
                "wid": r2(width),
                **({"height": r2(height)} if height else {}),
            }
        )

    # ---- the market -------------------------------------------------------------------------
    stalls = []
    obstacles = [Point(x, z).buffer(0.6) for x, z in trees] + [Point(x, z).buffer(0.5) for x, z in lamps]
    for lm in landmarks:
        obstacles.append(_rect_poly(lm).buffer(2.0))
    blocked = unary_union(obstacles) if obstacles else Polygon()
    for mk in brief.get("market", []):
        goods = mk.get("goods") or ["fruits"]
        spacing = float(mk.get("spacing", 3.6))
        gi = 0
        if mk.get("street"):
            classes = set(mk.get("classes") or [])
            segs = [ln for _, ln, nm, cls in roads if nm == mk["street"] and (not classes or cls in classes)]
            if not segs:
                warnings.append(f"market street {mk['street']!r} not found")
                continue
            for ln in segs:
                ln = ln.intersection(disc_walk.buffer(-6))
                for part in lines(ln):
                    s = spacing / 2
                    while s < part.length - spacing / 2:
                        q0 = part.interpolate(max(0, s - 0.5))
                        q1 = part.interpolate(min(part.length, s + 0.5))
                        q = part.interpolate(s)
                        tx, tz = q1.x - q0.x, q1.y - q0.y
                        tl = math.hypot(tx, tz) or 1
                        tx, tz = tx / tl, tz / tl
                        for side in (-1, 1):
                            nx, nz = -tz * side, tx * side
                            # how far the façade is on this side
                            reach = 0.0
                            for d in [x * 0.25 for x in range(1, 60)]:
                                if not street_p.contains(Point(q.x + nx * d, q.y + nz * d)):
                                    break
                                reach = d
                            if reach < 5.2 or reach > 13:
                                continue
                            back = reach - 1.7  # a pavement's width left behind the stall
                            cx, cz = q.x + nx * (back - 0.8), q.y + nz * (back - 0.8)
                            foot = Point(cx, cz).buffer(1.5)
                            if blocked.intersects(foot) or not walk_p.contains(Point(cx, cz)):
                                continue
                            stalls.append({"c": [r2(cx), r2(cz)], "rot": round(math.atan2(-nx, -nz), 3), "w": 2.8, "goods": goods[gi % len(goods)]})
                            gi += 1
                        s += spacing
        elif mk.get("area"):
            area = [polygons(L.geom(r)) for r in layers["landuse"] if name_of(r) == mk["area"]]
            polys_ = [p for ps in area for p in ps]
            if not polys_:
                warnings.append(f"market area {mk['area']!r} not found")
                continue
            region = unary_union(polys_).intersection(walk_area).difference(carriage).buffer(-1.5)
            away = next((lm for lm in landmarks if lm["name"] == mk.get("away_from")), None)
            if away:
                region = region.difference(_rect_poly(away).buffer(5))
            rect = region.minimum_rotated_rectangle if not region.is_empty else None
            if rect is None or rect.is_empty:
                continue
            cs = list(rect.exterior.coords)[:4]
            ux, uz = cs[1][0] - cs[0][0], cs[1][1] - cs[0][1]
            ul = math.hypot(ux, uz) or 1
            ux, uz = ux / ul, uz / ul
            vx, vz = -uz, ux
            cx0, cz0 = rect.centroid.x, rect.centroid.y
            span = max(region.bounds[2] - region.bounds[0], region.bounds[3] - region.bounds[1])
            row_gap = float(mk.get("rows", 7.0))
            most = int(mk.get("max", 24))
            rows_ = int(span // row_gap) + 2
            # rows of tables back to back in pairs, an aisle between the pairs, nearest the middle first
            cells = []
            for j in range(-rows_, rows_ + 1):
                for i in range(-rows_ * 2, rows_ * 2 + 1):
                    x = cx0 + ux * i * spacing + vx * j * row_gap
                    z = cz0 + uz * i * spacing + vz * j * row_gap
                    cells.append((math.hypot(x - cx0, z - cz0), x, z, j))
            cells.sort()
            n_here = 0
            for _, x, z, j in cells:
                if n_here >= most:
                    break
                foot = Point(x, z).buffer(1.4)
                if not region.contains(foot) or blocked.intersects(foot):
                    continue
                facing = 1 if j % 2 == 0 else -1
                stalls.append({"c": [r2(x), r2(z)], "rot": round(math.atan2(vx * facing, vz * facing), 3), "w": 2.4, "goods": goods[gi % len(goods)]})
                gi += 1
                n_here += 1
    stalls_poly = unary_union([Point(*s["c"]).buffer(1.6) for s in stalls]) if stalls else Polygon()

    # ---- where you arrive ----------------------------------------------------------------------
    st = brief.get("start", {})
    start = None
    toward = next((lm for lm in landmarks if lm["name"] == st.get("toward")), None)
    target = Point(*toward["c"]) if toward else centre
    st_classes = set(st.get("classes") or [])
    segs = [ln for _, ln, nm, cls in roads if nm == st.get("street") and (not st_classes or cls in st_classes)]
    cands = []
    for ln in segs:
        for part in lines(ln.intersection(disc_walk.buffer(-5))):
            for t in [i / 20 for i in range(21)]:
                q = part.interpolate(t, normalized=True)
                if walk_p.contains(q) and not stalls_poly.contains(q):
                    cands.append(q)
    if cands:
        q = max(cands, key=lambda c: c.distance(target)) if st.get("far", True) else min(cands, key=lambda c: c.distance(target))
        start = {"pos": [r2(q.x), r2(q.y)], "look": [r2(target.x), 3.0, r2(target.y)]}
    else:
        q = nearest_points(walk_area, centre)[0]
        start = {"pos": [r2(q.x), r2(q.y)], "look": [0, 3.0, 0]}
        warnings.append("start street not found; starting at the centre")

    # ---- the hoarding where the walkable world ends ---------------------------------------------
    fences = []
    for ln in lines(street.intersection(disc_walk.exterior)):
        if ln.length > 0.8:
            pts = [[r2(x), r2(z)] for x, z in ln.simplify(0.3).coords]
            fences.append(pts)

    # ---- where the crowd goes ---------------------------------------------------------------------
    spots = []
    foot_area = walk_area.difference(carriage).difference(stalls_poly).buffer(-0.8)
    minx, minz, maxx, maxz = foot_area.bounds if not foot_area.is_empty else (0, 0, 0, 0)
    fa = prep(foot_area)
    tries = 0
    while len(spots) < 36 and tries < 6000:
        tries += 1
        x, z = rng.uniform(minx, maxx), rng.uniform(minz, maxz)
        if fa.contains(Point(x, z)) and all(math.dist((x, z), s["at"]) > 11 for s in spots):
            spots.append({"at": [r2(x), r2(z)]})
    for s in stalls[::2]:
        # in front of a stall, where people stop and look
        a = s["rot"]
        x = s["c"][0] + math.sin(a) * 1.9
        z = s["c"][1] + math.cos(a) * 1.9
        if walk_p.contains(Point(x, z)) and not stalls_poly.contains(Point(x, z)):
            spots.append({"at": [r2(x), r2(z)], "linger": [4, 11]})

    # ---- who stands where ---------------------------------------------------------------------------
    people = []
    for person in brief.get("people", []):
        at = person.get("at", "")
        pos = None
        rot = 0.0
        if at.startswith("stall:"):
            want = at.split(":")[1]
            idx = int(at.split(":")[2]) if at.count(":") >= 2 else 0
            pick = [s for s in stalls if s["goods"] == want]
            if len(pick) > idx:
                s = pick[idx]
                a = s["rot"]
                pos = [r2(s["c"][0] - math.sin(a) * 1.3), r2(s["c"][1] - math.cos(a) * 1.3)]
                rot = a
        elif at.startswith("landmark:"):
            lm = next((x for x in landmarks if x["name"] == at.split(":", 1)[1]), None)
            if lm:
                pos = [r2(lm["c"][0] + lm["u"][0] * lm["len"] * 0.2), r2(lm["c"][1] + lm["u"][1] * lm["len"] * 0.2)]
        elif at.startswith("xz:"):
            x, z = (float(v) for v in at[3:].split(","))
            pos = [r2(x), r2(z)]
        if pos is None:
            warnings.append(f"no place for {person.get('key')} at {at!r}")
            continue
        people.append({**{k: v for k, v in person.items() if k != "at"}, "pos": pos, "rot": round(rot, 3)})

    # ---- out ------------------------------------------------------------------------------------
    for run in runs_all:
        for k_ in [k_ for k_ in run if k_.startswith("_")]:
            del run[k_]
    for b in out_buildings:
        if not b["runs"]:
            del b["runs"]

    def polys_out(g) -> list[dict]:
        return [poly_out(p) for p in polygons(g) if p.area > 1.0]

    site = {
        "id": brief["id"],
        "version": 1,
        "origin": [place["lat"], place["lon"]],
        "radius": {"walk": r_walk, "build": r_build},
        "ambiance": brief.get("ambiance", "matin"),
        "title": brief.get("title"),
        "can_do": brief.get("can_do"),
        "start": start,
        "ground": {
            "street": polys_out(street.simplify(0.05)),
            "carriageway": polys_out(carriage.simplify(0.1)),
            "pavement": polys_out(pavement.simplify(0.1)),
            "squares": polys_out(squares_u.simplify(0.1)),
            "gravel": polys_out(gravel_u.simplify(0.1)),
            "green": polys_out(green_u.simplify(0.1)),
        },
        "walk": polys_out(walk_area.simplify(0.1)),
        "nav": nav_rings(walk_area, carriage),
        "buildings": out_buildings,
        "landmarks": landmarks,
        "plaques": plaques,
        "lamps": [[r2(x), r2(z)] for x, z in lamps],
        "trees": [[r2(x), r2(z), round(rng.uniform(0.82, 1.08), 2)] for x, z in trees],
        "benches": [[r2(x), r2(z), round(facing_street(x, z), 3)] for x, z in benches],
        "hoops": [[r2(x), r2(z), round(facing_street(x, z), 3)] for x, z in hoops],
        "bins": [[r2(x), r2(z)] for x, z in bins],
        "posts": [[r2(x), r2(z), round(facing_street(x, z), 3)] for x, z in posts],
        "crossings": crossings_out,
        "stalls": stalls,
        "fences": fences,
        "spots": spots,
        "people": people,
        "provenance": {
            "data": survey.get("attribution"),
            "release": survey.get("release"),
            "surveyed": survey.get("surveyed"),
            "papier": brief.get("papier"),
            "brief_round": brief.get("round", 1),
        },
    }
    if brief.get("arrondissement"):
        site["arrondissement"] = brief["arrondissement"]
    report = {
        "counts": {
            "buildings": len(raw),
            "pieces": n_parts,
            "runs": len(runs_all),
            "shops": shops_n,
            "doors": doors_n,
            "plaques": len(plaques),
            "lamps": len(lamps),
            "trees": len(trees),
            "benches": len(benches),
            "crossings": len(crossings_out),
            "stalls": len(stalls),
            "fences": len(fences),
            "spots": len(spots),
            "people": len(people),
            "walk_m2": round(walk_area.area),
        },
        "trades": dict(sorted(trades_seen.items(), key=lambda t: -t[1])),
        "warnings": warnings,
    }
    return site, report


def nav_rings(walk_area, carriage) -> dict:
    """Where you can walk, as rings the game's grid fills in order: the pavement's outlines at kerb
    height, then the carriageway's at street level, its islands back at kerb height, and the
    blocks of houses (the holes) closed."""
    walk = walk_area.simplify(0.1)
    road = walk_area.intersection(carriage).simplify(0.1)
    return {
        "kerb": [ring(p.exterior.coords) for p in polygons(walk) if p.area > 1],
        "road": [ring(p.exterior.coords) for p in polygons(road) if p.area > 1],
        "islands": [ring(h.coords) for p in polygons(road) for h in p.interiors if Polygon(h).area > 0.6],
        "holes": [ring(h.coords) for p in polygons(walk) for h in p.interiors if Polygon(h).area > 0.6],
    }


def _rect_poly(lm: dict) -> Polygon:
    cx, cz = lm["c"]
    ux, uz = lm["u"]
    vx, vz = -uz, ux
    hl, hw = lm["len"] / 2, lm["wid"] / 2
    return Polygon([(cx + ux * a * hl + vx * b * hw, cz + uz * a * hl + vz * b * hw) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))])


# --------------------------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------------------------


def area2(pts) -> float:
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def check(site: dict) -> list[str]:
    """What must hold for the game to build the site and walk it. The same rules run in
    `web-frontend/lib/quartier/site.test.js`."""
    out: list[str] = []
    for i, b in enumerate(site.get("buildings", [])):
        fp = b["fp"]
        if len(fp) < 3:
            out.append(f"building {i}: fewer than three corners")
            continue
        if area2(fp) >= 0:
            out.append(f"building {i}: footprint wound the wrong way (the kit wants negative area)")
        if not is_convex([tuple(p) for p in fp], 1e-2):
            out.append(f"building {i}: footprint not convex")
        if len(b["street"]) != len(fp):
            out.append(f"building {i}: street flags do not match the footprint")
        for r in b.get("runs", []):
            if not (0 <= r["e"] < len(fp)) or not b["street"][r["e"]]:
                out.append(f"building {i}: run on edge {r['e']} is not a street edge")
            cover = set()
            for s in r["shops"]:
                for k in range(s["from"], s["to"] + 1):
                    if k in cover:
                        out.append(f"building {i}: two fronts share bay {k}")
                    cover.add(k)
            if any(k >= r["bays"] for k in cover):
                out.append(f"building {i}: a front past the last bay")
        if b["style"] not in STYLE_BAY:
            out.append(f"building {i}: unknown style {b['style']}")
    walk = [Polygon(p["outer"], p["holes"]) for p in site.get("walk", [])]
    walk_u = unary_union(walk) if walk else Polygon()
    if walk_u.is_empty:
        out.append("no walkable ground")
        return out
    st = site.get("start") or {}
    if not st or not walk_u.contains(Point(*st["pos"])):
        out.append("the start is not on walkable ground")
    for s in site.get("stalls", []):
        if not walk_u.contains(Point(*s["c"])):
            out.append(f"stall at {s['c']} off the walkable ground")
    for p in site.get("people", []):
        if not walk_u.buffer(0.5).contains(Point(*p["pos"])):
            out.append(f"{p.get('key')} stands off the walkable ground")
    for s in site.get("spots", []):
        if not walk_u.contains(Point(*s["at"])):
            out.append(f"crowd spot {s['at']} off the walkable ground")
    names = {s.get("name") for b in site.get("buildings", []) for r in b.get("runs", []) for s in r["shops"] if s.get("name")}
    allowed = {t[0] for t in TRADES.values()}
    for n in names - allowed:
        out.append(f"fascia {n!r} is not a generic trade")
    return out

