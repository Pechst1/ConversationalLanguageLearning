"""Le Quartier forge · a venue: the place where the news happens, drafted as a set.

A street is drafted building by building (`draft.py`). A venue (a racecourse, a stadium) is a
set the kit draws from a few measures, and the survey gives the measures: where the grandstand
stands and which way it looks, how far its front is from the track, which way the horses run.
The kit (`web-frontend/lib/quartier/hippodrome.ts`) draws the stand, the straight, the rails,
the post and the board from them; the director (`course.ts`) runs the race.

Today the one kind is `hippodrome`. The brief names it:

    "venue": {"kind": "hippodrome", "turn": "right", "race": {...}}

`turn` is the way the course turns (Longchamp runs right-handed: the infield on the horses'
right), and `race` what the article says about the race (its name, distance and hour, and the
number of runners).
"""

from __future__ import annotations

import datetime as dt
import math

from draft import Local, name_of, r2
from shapely.geometry import Point, Polygon

# metres across, from the stand's front to the far rail: the esplanade, the lawn, the track
ESPLANADE = 14.0
LAWN = 12.0
TRACK = 24.0


def _unit(x: float, z: float) -> tuple[float, float]:
    d = math.hypot(x, z) or 1.0
    return x / d, z / d


def draft(survey: dict, brief: dict, place: dict) -> tuple[dict, dict]:
    v = brief["venue"]
    if v.get("kind") != "hippodrome":
        raise SystemExit(f"no venue kit for {v.get('kind')!r}")
    loc = Local(*survey["anchor"])
    warnings: list[str] = []

    # the track: the course's land use (the largest such polygon)
    track = None
    for row in survey["layers"]["landuse"]:
        if row.get("class") in ("track", "racetrack") or (name_of(row) or "").lower().startswith("hippodrome"):
            g = loc.geom(row)
            if g.geom_type in ("Polygon", "MultiPolygon") and (track is None or g.area > track.area):
                track = g
    if track is None:
        raise SystemExit("no racetrack in the survey's land use")
    edge = track.exterior if isinstance(track, Polygon) else track.boundary

    # the grandstand: of the large buildings, the one nearest the track
    big = [loc.geom(row) for row in survey["layers"]["buildings"]]
    big = [g for g in big if not g.is_empty and g.area > 2500 and not track.contains(g.centroid)]
    if not big:
        raise SystemExit("no large building beside the track to stand the grandstand on")
    stand_geom = min(big, key=lambda g: g.distance(edge))
    rect = stand_geom.minimum_rotated_rectangle
    pts = list(rect.exterior.coords)[:4]
    e0 = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    e1 = (pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
    long_e, short_e = (e0, e1) if math.hypot(*e0) >= math.hypot(*e1) else (e1, e0)
    length = math.hypot(*long_e)
    depth = math.hypot(*short_e)
    ax = _unit(*long_e)
    c = rect.centroid

    # the home straight's rail: the track's edge nearest the stand
    near = edge.interpolate(edge.project(c))
    # n: from the stand across the track, square to the stand's long side
    nx, nz = -ax[1], ax[0]
    if (near.x - c.x) * nx + (near.y - c.y) * nz < 0:
        nx, nz = -nx, -nz
    gap = (near.x - c.x) * nx + (near.y - c.y) * nz - depth / 2
    if not 10 <= gap <= 70:
        warnings.append(f"the stand's front is {gap:.0f} m from the track; drew {ESPLANADE + LAWN:.0f} m")
        gap = ESPLANADE + LAWN
    lawn = min(LAWN, gap * 0.45)
    esplanade = gap - lawn
    # the way they run: a right-handed course has its infield (n) on the horses' right
    turn = v.get("turn", "right")
    ux, uz = (nz, -nx) if turn == "right" else (-nz, nx)

    # the winning post: on the rail, square to the stand's middle
    post = (c.x + nx * (depth / 2 + gap), c.y + nz * (depth / 2 + gap))
    # the site's origin: the middle of the ground between the stand and the rail, at the post
    mid_n = -gap / 2
    ox, oz = post[0] + nx * mid_n, post[1] + nz * mid_n

    def xz(u: float, n: float) -> tuple[float, float]:
        return post[0] + ux * u + nx * n - ox, post[1] + uz * u + nz * n - oz

    def pt(u: float, n: float) -> list[float]:
        x, z = xz(u, n)
        return [r2(x), r2(z)]

    half = min(length / 2, 44.0)
    # stand along u, relative to the post
    s_u0 = -length / 2
    s_u1 = length / 2
    walk_ring = [pt(-half, -gap + 0.6), pt(half, -gap + 0.6), pt(half, -0.7), pt(-half, -0.7)]
    poly = Polygon(walk_ring)
    if poly.exterior.is_ccw:
        walk_ring = walk_ring[::-1]
    walk = [{"outer": walk_ring, "holes": []}]

    guichet_u = -13.0
    clerk = pt(guichet_u, -gap + 3.4)
    rail = pt(4.0, -1.4)
    start = pt(-9.0, -lawn - 2.0)
    look_at = xz(-60.0, TRACK * 0.5)
    spots = []
    for k, (u, n, linger) in enumerate(
        [
            (-30, -2.2, (20, 60)),
            (-21, -1.8, (30, 80)),
            (-6, -1.6, (40, 90)),
            (9, -1.9, (30, 80)),
            (17, -2.4, (20, 60)),
            (27, -1.7, (30, 70)),
            (36, -2.1, (20, 50)),
            (-36, -6.0, None),
            (-18, -8.0, None),
            (0, -7.0, None),
            (14, -9.0, None),
            (30, -7.5, None),
            (-26, -gap + 5.0, None),
            (-4, -gap + 6.0, None),
            (22, -gap + 5.5, None),
        ]
    ):
        s = {"at": pt(u, n)}
        if linger:
            s["linger"] = list(linger)
        spots.append(s)
        if not poly.contains(Point(*xz(u, n))):
            warnings.append(f"crowd spot {k} off the ground")

    race = dict(v["race"])
    race.setdefault("seed", 2026)
    site = {
        "id": brief["id"],
        "version": 1,
        "origin": [round(loc.lat - oz / loc.north, 6), round(loc.lon + ox / loc.east, 6)],
        "radius": brief["radius"],
        "ambiance": brief.get("ambiance", "matin"),
        "title": brief["title"],
        "can_do": brief["can_do"],
        "arrondissement": brief.get("arrondissement", ""),
        "start": {"pos": start, "look": [r2(look_at[0]), 1.6, r2(look_at[1])]},
        "ground": {"street": [], "carriageway": [], "pavement": [], "squares": [], "gravel": [], "green": []},
        "walk": walk,
        "nav": {"kerb": [walk_ring], "road": [], "islands": [], "holes": []},
        "buildings": [],
        "landmarks": [],
        "plaques": [],
        "lamps": [],
        "trees": [],
        "benches": [],
        "hoops": [],
        "bins": [],
        "posts": [],
        "crossings": [],
        "stalls": [],
        "fences": [],
        "spots": spots,
        "people": [
            {**p, "pos": clerk if p["key"] == "guichetiere" else rail, "rot": 0.0}
            for p in brief.get("people", [])
        ],
        "venue": {
            "kind": "hippodrome",
            "post": pt(0, 0),
            "u": [round(ux, 4), round(uz, 4)],
            "n": [round(nx, 4), round(nz, 4)],
            "track": TRACK,
            "lawn": r2(lawn),
            "esplanade": r2(esplanade),
            "stand": {"u0": r2(s_u0), "u1": r2(s_u1), "depth": r2(depth), "height": float(v.get("stand_height", 21))},
            "guichet": guichet_u,
            "board": 26.0,
            "moulin": v.get("moulin"),
            "race": race,
        },
        "provenance": {
            "data": survey["attribution"],
            "release": survey["release"],
            "surveyed": survey.get("surveyed", dt.date.today().isoformat()),
            "papier": brief.get("papier"),
            "brief_round": brief.get("round", 1),
        },
    }
    report = {
        "counts": {
            "stand": f"{length:.0f} x {depth:.0f} m",
            "front to rail": f"{gap:.0f} m",
            "walk": f"{poly.area:.0f} m2",
            "spots": len(spots),
            "people": len(site["people"]),
        },
        "warnings": warnings,
    }
    return site, report
