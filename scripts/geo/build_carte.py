#!/usr/bin/env python3
"""Build La Carte's three drawings and their projection file (WP-120 §5.1).

Run from the repository root::

    python scripts/geo/build_carte.py            # reads var/geo/ or downloads into it
    python scripts/geo/build_carte.py --offline  # var/geo/ only, or the hand-made fallback

Writes ``web-frontend/public/assets/carte/{france,idf,paris}.svg`` and
``carte-projection.json``. Python standard library only (json, math, urllib).

Sources (both under the Licence Ouverte / Open Licence of Etalab, derived from IGN
ADMIN EXPRESS; attribution «IGN – Admin Express» kept in the projection file):

* Departments, metropolitan and overseas:
  https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-avec-outre-mer.geojson
  (repository gregoiredavid/france-geojson, «Licence ouverte», data © IGN Admin Express)
* Paris's 20 arrondissements municipaux:
  https://geo.api.gouv.fr/communes?type=arrondissement-municipal&codeDepartement=75&format=geojson&geometry=contour&fields=nom,code
  (API Découpage administratif, Etalab, Licence Ouverte 2.0, data © IGN Admin Express)
* The Seine through Paris: a hand-drawn centreline (bridge to bridge) authored here,
  no third-party data.

Pipeline:

1. **Lambert-93** (EPSG:2154): the Lambert conformal conic with two standard
   parallels on GRS80 (φ1 = 44°, φ2 = 49°, φ0 = 46.5°, λ0 = 3°, X0 = 700 000 m,
   Y0 = 6 600 000 m), written out below (:func:`lambert93`). The overseas departments
   are not in Lambert-93's domain; each is drawn in its own box with a local
   equirectangular projection (x = (λ − λ0)·cos φ0, y = φ), the French convention.
2. **Topology-preserving Douglas–Peucker**: rings are cut into arcs at the vertices
   where the set of departments sharing them changes, each arc is simplified once
   (memoised on its canonical direction) so neighbours keep the same border, and small
   islands are dropped at the France scale.
3. **SVG in the av2 style**: no colour in the files; classes only (``carte-land``,
   ``carte-border`` on the same path, ``carte-seine``, ``carte-inset``, ``carte-label``),
   coloured by ``web-frontend/styles/carte.css`` from the av2 tokens: sea = paper,
   land = paper tint, borders = an ink hairline.
4. **carte-projection.json**: the Lambert-93 constants, and per drawing the 6-number
   affine ``[a, b, c, d, e, f]`` (SVG matrix order: x = a·X + c·Y + e, y = b·X + d·Y + f)
   from projected metres to SVG user units, the drawing's lat/lon bounds, and the
   overseas insets (box + equirectangular constants), plus a few check points the
   tests use to prove the client lands a lat/lon where this script does.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "var" / "geo"
OUT = ROOT / "web-frontend" / "public" / "assets" / "carte"

DEPARTMENTS_URL = (
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-avec-outre-mer.geojson"
)
ARRONDISSEMENTS_URL = (
    "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&codeDepartement=75"
    "&format=geojson&geometry=contour&fields=nom,code"
)
SOURCES = {
    "departements": {
        "url": DEPARTMENTS_URL,
        "licence": "Licence Ouverte / Open Licence (Etalab)",
        "attribution": "IGN – Admin Express, via gregoiredavid/france-geojson",
    },
    "arrondissements": {
        "url": ARRONDISSEMENTS_URL,
        "licence": "Licence Ouverte / Open Licence 2.0 (Etalab)",
        "attribution": "IGN – Admin Express, via geo.api.gouv.fr (API Découpage administratif)",
    },
    "seine": {"url": None, "licence": "authored", "attribution": "hand-drawn centreline, WP-120"},
}

IDF_CODES = ("75", "77", "78", "91", "92", "93", "94", "95")
OVERSEAS = (("971", "Guadeloupe"), ("972", "Martinique"), ("973", "Guyane"), ("974", "La Réunion"), ("976", "Mayotte"))

# ---------------------------------------------------------------------------
# Lambert-93
# ---------------------------------------------------------------------------

GRS80_A = 6378137.0
GRS80_F = 1 / 298.257222101
GRS80_E = math.sqrt(2 * GRS80_F - GRS80_F**2)
LAT1, LAT2, LAT0, LON0 = 44.0, 49.0, 46.5, 3.0
X0, Y0 = 700000.0, 6600000.0


def _m(phi: float) -> float:
    return math.cos(phi) / math.sqrt(1 - (GRS80_E * math.sin(phi)) ** 2)


def _t(phi: float) -> float:
    es = GRS80_E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - es) / (1 + es)) ** (GRS80_E / 2)


_P1, _P2, _P0 = math.radians(LAT1), math.radians(LAT2), math.radians(LAT0)
LAMBERT_N = (math.log(_m(_P1)) - math.log(_m(_P2))) / (math.log(_t(_P1)) - math.log(_t(_P2)))
#: a·F, the cone constant in metres.
LAMBERT_C = GRS80_A * _m(_P1) / (LAMBERT_N * _t(_P1) ** LAMBERT_N)
LAMBERT_RHO0 = LAMBERT_C * _t(_P0) ** LAMBERT_N


def lambert93(lat: float, lon: float) -> tuple[float, float]:
    """Degrees → Lambert-93 metres (EPSG:2154)."""

    rho = LAMBERT_C * _t(math.radians(lat)) ** LAMBERT_N
    theta = LAMBERT_N * math.radians(lon - LON0)
    return X0 + rho * math.sin(theta), Y0 + LAMBERT_RHO0 - rho * math.cos(theta)


def apply_affine(affine: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = affine
    return a * x + c * y + e, b * x + d * y + f


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def _fetch(name: str, url: str, *, offline: bool) -> dict | None:
    path = CACHE / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        return None
    try:
        with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - fixed public URL
            body = response.read()
    except OSError as exc:
        print(f"! download failed for {url}: {exc}", file=sys.stderr)
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return json.loads(body)


def _polygons(geometry: dict) -> list[list[list[tuple[float, float]]]]:
    """GeoJSON (Multi)Polygon → polygons of rings of (lon, lat), closing point dropped."""

    coords = geometry["coordinates"]
    polys = coords if geometry["type"] == "MultiPolygon" else [coords]
    out = []
    for poly in polys:
        rings = []
        for ring in poly:
            pts = [(float(p[0]), float(p[1])) for p in ring]
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                rings.append(pts)
        if rings:
            out.append(rings)
    return out


def _features(collection: dict, code_key: str = "code", name_key: str = "nom") -> list[dict]:
    return [
        {"code": str(f["properties"][code_key]), "name": str(f["properties"][name_key]), "polys": _polygons(f["geometry"])}
        for f in collection["features"]
    ]


def _fallback_features() -> tuple[list[dict], list[dict]]:
    """A hand-made, very coarse France, Île-de-France and Paris: proves the pipeline offline.

    Every shape is a handful of real coordinates (hexagon corners, Paris's ring road);
    the drawings it produces are flagged ``"fallback": true`` in the projection file.
    """

    def box(lon0: float, lat0: float, lon1: float, lat1: float) -> list:
        return [[[(lon0, lat0), (lon1, lat0), (lon1, lat1), (lon0, lat1)]]]

    france = [
        {"code": "FR", "name": "France (fallback)", "polys": [[[
            (-1.78, 43.36), (3.08, 42.43), (4.8, 43.4), (7.53, 43.78), (6.6, 46.4), (8.23, 48.97),
            (6.36, 49.47), (2.54, 51.09), (1.58, 50.87), (-1.94, 49.72), (-4.79, 48.4), (-1.15, 46.3),
        ]]]},
        {"code": "2A", "name": "Corse (fallback)", "polys": [[[(8.6, 41.4), (9.4, 41.6), (9.5, 43.0), (8.7, 42.6)]]]},
        {"code": "75", "name": "Paris", "polys": box(2.224, 48.815, 2.47, 48.903)},
        {"code": "77", "name": "Seine-et-Marne", "polys": box(2.47, 48.12, 3.56, 49.12)},
        {"code": "78", "name": "Yvelines", "polys": box(1.44, 48.44, 2.224, 49.08)},
        {"code": "95", "name": "Val-d'Oise", "polys": box(1.6, 48.903, 2.6, 49.24)},
        {"code": "91", "name": "Essonne", "polys": box(1.91, 48.28, 2.47, 48.815)},
    ]
    for code, name in OVERSEAS:
        lat0, lat1, lon0, lon1 = INSET_BBOXES[code]
        france.append({"code": code, "name": name, "polys": box(lon0 + 0.1 * (lon1 - lon0), lat0 + 0.1 * (lat1 - lat0),
                                                                 lon1 - 0.1 * (lon1 - lon0), lat1 - 0.1 * (lat1 - lat0))})
    paris = [
        {"code": "751" + str(i).zfill(2), "name": f"Paris {i}e", "polys": box(2.224 + (i - 1) % 5 * 0.0492, 48.815 + (i - 1) // 5 * 0.022,
                                                                              2.224 + ((i - 1) % 5 + 1) * 0.0492, 48.815 + ((i - 1) // 5 + 1) * 0.022)}
        for i in range(1, 21)
    ]
    return france, paris


# ---------------------------------------------------------------------------
# Topology-preserving simplification
# ---------------------------------------------------------------------------


def _seg_dist2(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    if dx == 0 and dy == 0:
        return (p[0] - ax) ** 2 + (p[1] - ay) ** 2
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return (p[0] - ax - t * dx) ** 2 + (p[1] - ay - t * dy) ** 2


def douglas_peucker(points: list[tuple[float, float]], tolerance: float) -> list[int]:
    """Indices kept (first and last always)."""

    if len(points) <= 2:
        return list(range(len(points)))
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    tol2 = tolerance * tolerance
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        best, index = -1.0, -1
        for k in range(i + 1, j):
            d = _seg_dist2(points[k], points[i], points[j])
            if d > best:
                best, index = d, k
        if index >= 0 and best > tol2:
            keep[index] = True
            stack.append((i, index))
            stack.append((index, j))
    return [k for k, flag in enumerate(keep) if flag]


def _ring_area(points: list[tuple[float, float]]) -> float:
    return 0.5 * sum(points[i - 1][0] * points[i][1] - points[i][0] * points[i - 1][1] for i in range(len(points)))


def simplify_features(features: list[dict], project, tolerance: float, *, min_island_area: float = 0.0) -> list[dict]:
    """Project and simplify every ring; shared borders stay shared."""

    owners: dict[tuple[float, float], set[int]] = {}
    for index, feature in enumerate(features):
        for poly in feature["polys"]:
            for ring in poly:
                for pt in ring:
                    owners.setdefault(pt, set()).add(index)
    projected: dict[tuple[float, float], tuple[float, float]] = {pt: project(pt[1], pt[0]) for pt in owners}
    memo: dict[tuple, list[tuple[float, float]]] = {}

    def simplify_arc(arc: list[tuple[float, float]]) -> list[tuple[float, float]]:
        key = tuple(arc)
        rev = tuple(reversed(arc))
        canonical, flipped = (key, False) if key <= rev else (rev, True)
        if canonical not in memo:
            pts = [projected[p] for p in canonical]
            memo[canonical] = [canonical[i] for i in douglas_peucker(pts, tolerance)]
        kept = memo[canonical]
        return list(reversed(kept)) if flipped else kept

    out = []
    for feature in features:
        polys_out = []
        for poly in feature["polys"]:
            rings_out = []
            for ring_index, ring in enumerate(poly):
                n = len(ring)
                sets = [frozenset(owners[p]) for p in ring]
                nodes = [i for i in range(n) if len(sets[i]) > 2 or sets[i] != sets[i - 1] or sets[i] != sets[(i + 1) % n]]
                if not nodes:
                    start = min(range(n), key=lambda i: ring[i])
                    sx, sy = projected[ring[start]]
                    far = max(range(n), key=lambda i: (projected[ring[i]][0] - sx) ** 2 + (projected[ring[i]][1] - sy) ** 2)
                    nodes = sorted({start, far})
                kept: list[tuple[float, float]] = []
                for k, node in enumerate(nodes):
                    nxt = nodes[(k + 1) % len(nodes)]
                    arc = ring[node : nxt + 1] if nxt > node else ring[node:] + ring[: nxt + 1]
                    simplified = simplify_arc(arc)
                    kept.extend(simplified[:-1])
                pts = [projected[p] for p in kept]
                if len(pts) < 3:
                    continue
                isolated = all(len(owners[p]) == 1 for p in ring)
                if ring_index == 0 and isolated and abs(_ring_area(pts)) < min_island_area:
                    break  # a small island: the whole polygon goes
                rings_out.append(pts)
            if rings_out:
                polys_out.append(rings_out)
        out.append({**feature, "rings": polys_out})
    return out


# ---------------------------------------------------------------------------
# SVG writing
# ---------------------------------------------------------------------------


def _num(value: float) -> str:
    text = f"{value:.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    if text == "-0":
        text = "0"
    return text


def path_data(polys: list[list[list[tuple[float, float]]]], affine: list[float]) -> str:
    """Relative path commands on the 0.1-unit grid (rounded absolutes, so no drift)."""

    parts: list[str] = []
    for poly in polys:
        for ring in poly:
            grid = []
            for x, y in ring:
                sx, sy = apply_affine(affine, x, y)
                point = (round(sx * 10), round(sy * 10))
                if not grid or grid[-1] != point:
                    grid.append(point)
            if len(grid) < 3:
                continue
            x0, y0 = grid[0]
            cmd = [f"M{_num(x0 / 10)} {_num(y0 / 10)}l"]
            deltas = []
            for (ax, ay), (bx, by) in zip(grid, grid[1:], strict=False):
                deltas.append(f"{_num((bx - ax) / 10)} {_num((by - ay) / 10)}")
            cmd.append(" ".join(deltas))
            cmd.append("z")
            parts.append("".join(cmd))
    return "".join(parts)


def _bounds(points) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _all_points(features: list[dict]):
    for feature in features:
        for poly in feature["polys"]:
            for ring in poly:
                yield from ring


def _centroid(ring: list[tuple[float, float]]) -> tuple[float, float]:
    area = _ring_area(ring)
    if abs(area) < 1e-9:
        return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    cx = cy = 0.0
    for i in range(len(ring)):
        x0, y0 = ring[i - 1]
        x1, y1 = ring[i]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (6 * area), cy / (6 * area)


def _svg(view_w: float, view_h: float, body: list[str], title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_num(view_w)} {_num(view_h)}" '
        f'class="carte-drawing" role="img" aria-label="{title}">\n' + "\n".join(body) + "\n</svg>\n"
    )


def _fit_affine(bounds: tuple[float, float, float, float], width: float, pad: float, ox: float = 0.0, oy: float = 0.0):
    """Projected metres (north up) → SVG units, ``width`` wide inside ``pad``."""

    x_min, y_min, x_max, y_max = bounds
    scale = (width - 2 * pad) / (x_max - x_min)
    height = (y_max - y_min) * scale + 2 * pad
    return [scale, 0.0, 0.0, -scale, ox + pad - scale * x_min, oy + pad + scale * y_max], height


def _latlon_bounds(features: list[dict], margin: float = 0.002) -> dict:
    lon_min, lat_min, lon_max, lat_max = _bounds(list(_all_points(features)))
    return {
        "lat_min": round(lat_min - margin, 3),
        "lat_max": round(lat_max + margin, 3),
        "lon_min": round(lon_min - margin, 3),
        "lon_max": round(lon_max + margin, 3),
    }


#: (lat_min, lat_max, lon_min, lon_max) per overseas department — the same boxes as
#: ``app/services/revue/geo.py`` FRANCE_BBOXES, so a pin and the Geo check agree.
INSET_BBOXES = {
    "971": (15.8, 16.55, -61.85, -60.95),
    "972": (14.35, 14.9, -61.25, -60.8),
    "973": (2.1, 5.8, -54.65, -51.6),
    "974": (-21.4, -20.85, 55.2, 55.85),
    "976": (-13.05, -12.6, 44.95, 45.35),
}

FRANCE_W = 1000.0
PAD = 12.0
INSET_GAP = 10.0
INSET_H = 170.0
INSET_LABEL = 38.0


def build_france(departments: list[dict]) -> tuple[str, dict]:
    metro = [f for f in departments if f["code"] not in dict(OVERSEAS)]
    overseas = {f["code"]: f for f in departments if f["code"] in dict(OVERSEAS)}
    lambert_pts = [lambert93(lat, lon) for lon, lat in _all_points(metro)]
    bounds = _bounds(lambert_pts)
    affine, map_h = _fit_affine(bounds, FRANCE_W, PAD)
    simplified = simplify_features(metro, lambert93, tolerance=1000.0, min_island_area=(9000.0**2))

    body = ['<g class="carte-land-layer">']
    for feature in simplified:
        body.append(f'<path class="carte-land carte-border" data-code="{feature["code"]}" data-name="{feature["name"]}" d="{path_data(feature["rings"], affine)}"/>')
    body.append("</g>")

    insets = []
    box_w = (FRANCE_W - 2 * PAD - 4 * INSET_GAP) / 5
    top = map_h + INSET_GAP
    body.append('<g class="carte-insets">')
    for index, (code, name) in enumerate(OVERSEAS):
        bx = PAD + index * (box_w + INSET_GAP)
        lat_min, lat_max, lon_min, lon_max = INSET_BBOXES[code]
        feature = overseas.get(code)
        pts = list(_all_points([feature])) if feature else [(lon_min, lat_min), (lon_max, lat_max)]
        lon0 = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
        lat0 = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
        coslat = math.cos(math.radians(lat0))

        def local(lat: float, lon: float, lon0=lon0, lat0=lat0, coslat=coslat) -> tuple[float, float]:
            return (lon - lon0) * coslat, lat - lat0

        lx = [local(p[1], p[0])[0] for p in pts]
        ly = [local(p[1], p[0])[1] for p in pts]
        inner_w, inner_h = box_w - 16, INSET_H - INSET_LABEL - 16
        k = min(inner_w / max(1e-6, max(lx) - min(lx)), inner_h / max(1e-6, max(ly) - min(ly)))
        cx, cy = bx + box_w / 2, top + 8 + inner_h / 2
        mid_x, mid_y = (max(lx) + min(lx)) / 2, (max(ly) + min(ly)) / 2
        inset_affine = [k, 0.0, 0.0, -k, cx - k * mid_x, cy + k * mid_y]
        body.append(f'<rect class="carte-inset" x="{_num(bx)}" y="{_num(top)}" width="{_num(box_w)}" height="{_num(INSET_H)}" rx="6"/>')
        if feature:
            tol = 0.6 / k  # ~0.6 svg units, in local degrees
            simple = simplify_features([feature], local, tolerance=tol, min_island_area=(2.5 / k) ** 2)[0]
            body.append(f'<path class="carte-land carte-border" data-code="{code}" data-name="{name}" d="{path_data(simple["rings"], inset_affine)}"/>')
        body.append(f'<text class="carte-label carte-label--inset" x="{_num(bx + box_w / 2)}" y="{_num(top + INSET_H - 10)}" text-anchor="middle">{name}</text>')
        insets.append({
            "code": code,
            "name_fr": name,
            "box": [round(bx, 2), round(top, 2), round(box_w, 2), round(INSET_H, 2)],
            "bbox": {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
            "equirect": {"lon0": round(lon0, 6), "lat0": round(lat0, 6), "cos_lat0": round(coslat, 9)},
            "affine": [round(v, 6) for v in inset_affine],
        })
    body.append("</g>")
    total_h = top + INSET_H + PAD
    svg = _svg(FRANCE_W, total_h, body, "La France, ses départements et l'outre-mer")
    meta = {
        "viewBox": [0, 0, FRANCE_W, round(total_h, 2)],
        "projection": "lambert93",
        "affine": [round(v, 9) for v in affine],
        "bounds": {"lat_min": 41.3, "lat_max": 51.15, "lon_min": -5.2, "lon_max": 9.6},
        "insets": insets,
    }
    return svg, meta


def build_idf(departments: list[dict]) -> tuple[str, dict]:
    idf = [f for f in departments if f["code"] in IDF_CODES]
    bounds = _bounds([lambert93(lat, lon) for lon, lat in _all_points(idf)])
    affine, height = _fit_affine(bounds, FRANCE_W, PAD)
    simplified = simplify_features(idf, lambert93, tolerance=90.0)
    body = ['<g class="carte-land-layer">']
    for feature in simplified:
        cls = "carte-land carte-border carte-land--paris" if feature["code"] == "75" else "carte-land carte-border"
        body.append(f'<path class="{cls}" data-code="{feature["code"]}" data-name="{feature["name"]}" d="{path_data(feature["rings"], affine)}"/>')
    body.append("</g>")
    body.append('<g class="carte-labels">')
    for feature in simplified:
        biggest = max((poly[0] for poly in feature["rings"]), key=lambda r: abs(_ring_area(r)))
        x, y = apply_affine(affine, *_centroid(biggest))
        label = "Paris" if feature["code"] == "75" else feature["name"]
        dy = -14 if feature["code"] == "75" else 0
        body.append(f'<text class="carte-label" x="{_num(x)}" y="{_num(y + dy)}" text-anchor="middle">{label}</text>')
    body.append("</g>")
    svg = _svg(FRANCE_W, height, body, "L'Île-de-France et ses départements")
    meta = {
        "viewBox": [0, 0, FRANCE_W, round(height, 2)],
        "projection": "lambert93",
        "affine": [round(v, 9) for v in affine],
        "bounds": _latlon_bounds(idf),
        "insets": [],
    }
    return svg, meta


#: The Seine through Paris, upstream to downstream, bridge by bridge (lat, lon). Authored.
SEINE: tuple[tuple[float, float], ...] = (
    (48.8205, 2.4185), (48.8236, 2.4090), (48.8262, 2.3990), (48.8277, 2.3913), (48.8316, 2.3825),
    (48.8355, 2.3780), (48.8380, 2.3747), (48.8417, 2.3717), (48.8443, 2.3657), (48.8478, 2.3622),
    (48.8503, 2.3592), (48.8525, 2.3560), (48.8558, 2.3505), (48.8570, 2.3470), (48.8577, 2.3413),
    (48.8583, 2.3375), (48.8596, 2.3333), (48.8606, 2.3291), (48.8619, 2.3247), (48.8637, 2.3198),
    (48.8640, 2.3136), (48.8640, 2.3104), (48.8630, 2.3020), (48.8620, 2.2970), (48.8601, 2.2927),
    (48.8554, 2.2876), (48.8530, 2.2846), (48.8504, 2.2803), (48.8467, 2.2753), (48.8430, 2.2722),
    (48.8393, 2.2694), (48.8365, 2.2628), (48.8345, 2.2560), (48.8330, 2.2480),
)
SEINE_WIDTH_M = 140.0


def build_paris(arrondissements: list[dict]) -> tuple[str, dict]:
    bounds = _bounds([lambert93(lat, lon) for lon, lat in _all_points(arrondissements)])
    affine, height = _fit_affine(bounds, FRANCE_W, PAD)
    simplified = simplify_features(arrondissements, lambert93, tolerance=12.0)
    body = ['<g class="carte-land-layer">']
    for feature in sorted(simplified, key=lambda f: f["code"]):
        body.append(f'<path class="carte-land carte-border" data-code="{feature["code"]}" data-name="{feature["name"]}" d="{path_data(feature["rings"], affine)}"/>')
    body.append("</g>")
    seine = [apply_affine(affine, *lambert93(lat, lon)) for lat, lon in SEINE]
    d = "M" + " L".join(f"{_num(x)} {_num(y)}" for x, y in seine)
    body.append(f'<path class="carte-seine" d="{d}" fill="none" stroke-width="{_num(SEINE_WIDTH_M * affine[0])}" stroke-linecap="round" stroke-linejoin="round"/>')
    body.append('<g class="carte-labels">')
    for feature in simplified:
        biggest = max((poly[0] for poly in feature["rings"]), key=lambda r: abs(_ring_area(r)))
        x, y = apply_affine(affine, *_centroid(biggest))
        number = int(feature["code"][-2:]) if feature["code"][-2:].isdigit() else 0
        label = "1er" if number == 1 else f"{number}e"
        body.append(f'<text class="carte-label carte-label--arr" x="{_num(x)}" y="{_num(y)}" text-anchor="middle" dominant-baseline="central">{label}</text>')
    body.append("</g>")
    svg = _svg(FRANCE_W, height, body, "Paris, ses vingt arrondissements et la Seine")
    meta = {
        "viewBox": [0, 0, FRANCE_W, round(height, 2)],
        "projection": "lambert93",
        "affine": [round(v, 9) for v in affine],
        "bounds": _latlon_bounds(arrondissements),
        "insets": [],
    }
    return svg, meta


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

#: Check points: the tests place these with the client's projection and expect the
#: build's own coordinates (± 2 svg units).
CHECKS = (
    ("france", "Lyon", 45.764, 4.8357),
    ("france", "Brest", 48.3904, -4.4861),
    ("france", "Ajaccio", 41.9192, 8.7386),
    ("france", "Saint-Denis (La Réunion)", -20.8821, 55.4504),
    ("france", "Cayenne", 4.9372, -52.326),
    ("idf", "Versailles", 48.8049, 2.1204),
    ("idf", "Hôtel de Ville de Paris", 48.8564, 2.3524),
    ("paris", "Place d'Aligre", 48.849, 2.378),
    ("paris", "Hippodrome de ParisLongchamp", 48.8573, 2.2338),
    ("paris", "Assemblée nationale", 48.862, 2.3185),
)


def project_point(meta: dict, lat: float, lon: float) -> tuple[float, float] | None:
    """The same placement the client does (``components/carte/carte-projection.ts``)."""

    for inset in meta.get("insets") or []:
        box = inset["bbox"]
        if box["lat_min"] <= lat <= box["lat_max"] and box["lon_min"] <= lon <= box["lon_max"]:
            eq = inset["equirect"]
            return apply_affine(inset["affine"], (lon - eq["lon0"]) * eq["cos_lat0"], lat - eq["lat0"])
    bounds = meta["bounds"]
    if not (bounds["lat_min"] <= lat <= bounds["lat_max"] and bounds["lon_min"] <= lon <= bounds["lon_max"]):
        return None
    return apply_affine(meta["affine"], *lambert93(lat, lon))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--offline", action="store_true", help="never download; var/geo/ or the hand-made fallback")
    parser.add_argument("--fallback", action="store_true", help="force the hand-made fallback (proves the pipeline)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    fallback = args.fallback
    departments_raw = None if fallback else _fetch("departements-avec-outre-mer.geojson", DEPARTMENTS_URL, offline=args.offline)
    arrondissements_raw = None if fallback else _fetch("paris-arrondissements.geojson", ARRONDISSEMENTS_URL, offline=args.offline)
    if departments_raw is None or arrondissements_raw is None:
        if not fallback:
            print("! FALLBACK: sources unavailable — drawing the hand-made coarse France and Paris", file=sys.stderr)
        fallback = True
        departments, arrondissements = _fallback_features()
    else:
        departments, arrondissements = _features(departments_raw), _features(arrondissements_raw)

    args.out.mkdir(parents=True, exist_ok=True)
    drawings = {}
    for name, builder, features in (
        ("france", build_france, departments),
        ("idf", build_idf, departments),
        ("paris", build_paris, arrondissements),
    ):
        svg, meta = builder(features)
        (args.out / f"{name}.svg").write_text(svg, encoding="utf-8")
        drawings[name] = meta
        print(f"{name}.svg  {len(svg.encode('utf-8')) / 1024:.1f} KB")

    checks = []
    for drawing, label, lat, lon in CHECKS:
        point = project_point(drawings[drawing], lat, lon)
        if point is not None:
            checks.append({"drawing": drawing, "label": label, "lat": lat, "lon": lon,
                           "x": round(point[0], 2), "y": round(point[1], 2)})

    projection = {
        "about": "La Carte (WP-120 §5.1): built by scripts/geo/build_carte.py. Do not edit by hand.",
        "fallback": fallback,
        "sources": SOURCES,
        "lambert93": {
            "ellipsoid": "GRS80",
            "e": GRS80_E,
            "n": LAMBERT_N,
            "c": LAMBERT_C,
            "rho0": LAMBERT_RHO0,
            "lon0": LON0,
            "x0": X0,
            "y0": Y0,
        },
        "drawings": drawings,
        "checks": checks,
    }
    (args.out / "carte-projection.json").write_text(json.dumps(projection, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"carte-projection.json  fallback={fallback}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
