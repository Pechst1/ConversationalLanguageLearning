"""A room of the season, written from the canon: the brief is the room, this lays it out.

The streets are surveyed (``draft.py``); a room is written. Its brief
(``scripts/forge/briefs/<id>.json``, ``"kind": "room"``) says what the canon says of the place in
the forge's own terms: the spaces you walk (a rectangle each, with its floor, ceiling and walls),
the walls that are not a space's (a stairwell's cage, a partition under the flight), the flights
of stairs, the doors, windows and plain holes in the walls by the wall's key, the lamps and the
circuit they are on with its push-buttons and its timer, the things in the room, a courtyard seen
through a window, and the marks where the stage stands people. ``draft`` turns the spaces into
floors, ceilings and walls (a side open to the next space is left out, a passage under a lintel
becomes a hole), resolves every opening onto its wall, and writes the room file the game reads
(``web-frontend/lib/quartier/world/rooms/<id>.json``, built by ``lib/quartier/room.ts``).
``check`` holds it to what the walking grid and the canon need (also in ``room.test.js``), and
``plan`` draws it from above.

Pure Python: a room is a few dozen rectangles, so nothing here needs the survey's libraries.
"""
from __future__ import annotations

import html
import math

FLOOR_FINISHES = {"cabochons", "boards", "tomettes", "cobbles", "stone"}
WALL_FINISHES = {"wainscot", "plaster", "stone"}
ZONES = {"room", "sealed", "out"}
TONES = {"ochre", "cream", "faux", "wainscot", "stone", "porch", "oxblood", "brown", "wood", "grey", "celadon", "white", "render", "coat", "oilcloth", "blanket", "navy"}
THINGS = {"letterboxes", "mat", "radiator", "coat", "clock", "calendar", "table", "chair", "slippers", "camera", "cup", "stove", "patch", "doorway", "bed", "phone", "keys", "suitcase", "kitchenette"}
LIGHTS = {"globe", "sconce", "hublot"}
DIRS = {"x+": (1, 0), "x-": (-1, 0), "z+": (0, 1), "z-": (0, -1)}

# the walking grid (nav.ts): half-metre cells, a step between neighbours under 0.35 m
CELL = 0.5
STEP = 0.35
# a wall's thickness (room.ts WALL), for a mark standing in a doorway
WALL = 0.25


# ---------------------------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------------------------


def rect(r):
    x0, z0, x1, z1 = r
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def sides_of(r):
    """A rectangle's sides, each walked with the room on its right (as room.ts reads a wall)."""
    x0, z0, x1, z1 = r
    return {
        "n": ([x0, z0], [x1, z0]),
        "e": ([x1, z0], [x1, z1]),
        "s": ([x1, z1], [x0, z1]),
        "w": ([x0, z1], [x0, z0]),
    }


def length(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def along(a, b, u):
    ln = length(a, b) or 1.0
    return [a[0] + (b[0] - a[0]) * u / ln, a[1] + (b[1] - a[1]) * u / ln]


def inside(shape, x, z):
    c = False
    j = len(shape) - 1
    for i in range(len(shape)):
        xi, zi = shape[i]
        xj, zj = shape[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            c = not c
        j = i
    return c


def bbox(shape):
    xs = [p[0] for p in shape]
    zs = [p[1] for p in shape]
    return min(xs), min(zs), max(xs), max(zs)


def r3(v):
    return round(v, 3)


def flight_plan(f):
    """The flight's footprint, its walking ramp and the ramp's shape (half a tread past each end, as room.ts)."""
    dx, dz = DIRS[f["dir"]]
    run = (f["risers"] - 1) * f["tread"]
    right = (-dz, dx)
    h = f["width"] / 2

    def at(s, w):
        return [f["from"][0] + dx * s + right[0] * w, f["from"][1] + dz * s + right[1] * w]

    t2 = f["tread"] / 2
    return {
        "run": run,
        "rise": (f["y1"] - f["y0"]) / f["risers"],
        "shape": [at(0, -h), at(run, -h), at(run, h), at(0, h)],
        "walk": [at(-t2, -h), at(run + t2, -h), at(run + t2, h), at(-t2, h)],
        "ramp": {"from": at(-t2, 0), "to": at(run + t2, 0), "y0": f["y0"], "y1": f["y1"]},
    }


def ramp_y(ramp, x, z):
    fx, fz = ramp["from"]
    tx, tz = ramp["to"]
    dx, dz = tx - fx, tz - fz
    t = ((x - fx) * dx + (z - fz) * dz) / (dx * dx + dz * dz or 1.0)
    t = max(0.0, min(1.0, t))
    return ramp["y0"] + (ramp["y1"] - ramp["y0"]) * t


def walks(room):
    """The ground you walk, in the order the game lays it: the floors, then the flights over them."""
    out = []
    for fl in room["floors"]:
        if fl.get("zone", "room") == "room" and fl.get("walk", True):
            out.append({"key": fl["key"], "shape": fl["shape"], "y": lambda x, z, y=fl["y"]: y})
    for f in room["flights"]:
        p = flight_plan(f)
        out.append({"key": f["key"], "shape": p["walk"], "y": lambda x, z, r=p["ramp"]: ramp_y(r, x, z)})
    return out


def walk_y(room, x, z):
    """The walking height at (x, z), the last ground laid there winning (as nav.ts), or None."""
    y = None
    for w in walks(room):
        if inside(w["shape"], x, z):
            y = w["y"](x, z)
    return y


# ---------------------------------------------------------------------------------------------
# draft: the brief's spaces into floors, ceilings and walls
# ---------------------------------------------------------------------------------------------


def _space_walls(sp, warnings):
    """A space's sides as walls: a side open all the way is left out, a passage under a lintel is a hole."""
    walls_of = sp.get("walls")
    if walls_of is None:
        return [], []
    finish = walls_of.get("finish", "wainscot")
    out = []
    holes = []
    opens = sp.get("open", {})
    for side, (a, b) in sides_of(sp["rect"]).items():
        if side in sp.get("skip", []):
            continue
        ln = length(a, b)
        spans = opens.get(side, [])
        full = sorted([s["u"] for s in spans if "top" not in s])
        # the wall pieces between the openings that go all the way up
        pieces = []
        u = 0.0
        for u0, u1 in full:
            if u0 - u > 0.01:
                pieces.append((u, u0))
            u = max(u, u1)
        if ln - u > 0.01:
            pieces.append((u, ln))
        if not full:
            pieces = [(0.0, ln)]
        for k, (p0, p1) in enumerate(pieces):
            key = f"{sp['key']}.{side}" if len(pieces) == 1 else f"{sp['key']}.{side}{k + 1}"
            wall = {
                "key": key,
                "a": [r3(v) for v in along(a, b, p0)],
                "b": [r3(v) for v in along(a, b, p1)],
                "base": sp["floor"],
                "top": sp["ceiling"],
                "finish": finish,
                "side": f"{sp['key']}.{side}",
                "u_off": r3(p0),
            }
            for f in ("tone", "dado", "plain"):
                if f in walls_of:
                    wall[f] = walls_of[f]
            if sp.get("zone"):
                wall["zone"] = sp["zone"]
            out.append(wall)
        # passages with a head: holes in the piece they fall in
        for s in spans:
            if "top" not in s:
                continue
            u0, u1 = s["u"]
            host = next((w for w in out if w["side"] == f"{sp['key']}.{side}" and w["u_off"] - 0.01 <= u0 and u1 <= w["u_off"] + length(w["a"], w["b"]) + 0.01), None)
            if not host:
                warnings.append(f"{sp['key']}.{side}: the passage {s['u']} falls across an opening")
                continue
            holes.append({"wall": host["key"], "u0": r3(u0 - host["u_off"]), "u1": r3(u1 - host["u_off"]), "y0": r3(sp["floor"] - 0.01), "y1": r3(s["top"])})
    return out, holes


def draft(brief: dict, place: dict | None = None):
    """The brief, laid out as the room file the game reads, and a report of what is in it."""
    warnings: list[str] = []
    floors, ceilings, walls, holes = [], [], [], []
    for sp in brief.get("spaces", []):
        fl = {"key": sp["key"], "shape": rect(sp["rect"]), "y": sp["floor"], "finish": sp.get("finish", "boards")}
        if sp.get("zone"):
            fl["zone"] = sp["zone"]
        if sp.get("walk") is False:
            fl["walk"] = False
        floors.append(fl)
        if sp.get("ceiling") is not None and sp.get("walls") is not None and not sp.get("open_above"):
            c = {"shape": rect(sp["rect"]), "y": sp["ceiling"]}
            if sp.get("zone"):
                c["zone"] = sp["zone"]
            ceilings.append(c)
        w, h = _space_walls(sp, warnings)
        walls.extend(w)
        holes.extend(h)
    for fl in brief.get("floors", []):
        floors.append(dict(fl))
    for c in brief.get("ceilings", []):
        ceilings.append(dict(c))
    for w in brief.get("walls", []):
        w = dict(w)
        w.setdefault("side", w["key"])
        w.setdefault("u_off", 0.0)
        walls.append(w)

    keys = [w["key"] for w in walls]
    if len(set(keys)) != len(keys):
        warnings.append("two walls with one key")

    def resolve(ref: str, u0: float, u1: float, what: str):
        """A wall by its key, or by its side's key with u along the whole side."""
        for i, w in enumerate(walls):
            if w["key"] == ref:
                return i, u0, u1
        for i, w in enumerate(walls):
            ln = length(w["a"], w["b"])
            if w["side"] == ref and w["u_off"] - 0.01 <= u0 and u1 <= w["u_off"] + ln + 0.01:
                return i, u0 - w["u_off"], u1 - w["u_off"]
        raise SystemExit(f"{what}: no wall «{ref}» holds u {u0}..{u1}")

    doors = []
    for d in brief.get("doors", []):
        i, u0, u1 = resolve(d["wall"], d["u"][0], d["u"][1], f"door {d['key']}")
        out = {k: v for k, v in d.items() if k not in ("wall", "u")}
        out.update({"wall": i, "u0": r3(u0), "u1": r3(u1)})
        doors.append(out)
    windows = []
    for wn in brief.get("windows", []):
        i, u0, u1 = resolve(wn["wall"], wn["u"][0], wn["u"][1], f"window {wn['key']}")
        out = {"key": wn["key"], "wall": i, "u0": r3(u0), "u1": r3(u1), "y0": wn["y"][0], "y1": wn["y"][1]}
        if wn.get("shutters"):
            out["shutters"] = wn["shutters"]
        windows.append(out)
    for hl in brief.get("holes", []):
        i, u0, u1 = resolve(hl["wall"], hl["u"][0], hl["u"][1], "hole")
        holes.append({"wall": i, "u0": r3(u0), "u1": r3(u1), "y0": hl["y"][0], "y1": hl["y"][1]})
    # the passages found in the spaces name their wall by key
    for h in holes:
        if isinstance(h["wall"], str):
            h["wall"] = keys.index(h["wall"])

    canon = brief.get("canon", {})
    room = {
        "id": brief["id"],
        "version": 1,
        "kind": "room",
        "in": brief["in"],
        "ambiance": brief.get("ambiance", "nuit"),
        "title": brief["title"],
        "can_do": brief["can_do"],
        **({"arrive": brief["arrive"]} if brief.get("arrive") else {}),
        "start": brief["start"],
        "floors": floors,
        "flights": brief.get("flights", []),
        "walls": [{k: v for k, v in w.items() if k not in ("side", "u_off")} for w in walls],
        "ceilings": ceilings,
        "doors": doors,
        "windows": windows,
        "holes": holes,
        "rails": brief.get("rails", []),
        "lights": brief.get("lights", []),
        "switches": brief.get("switches", []),
        "timers": brief.get("timers", {}),
        "things": brief.get("things", []),
        "courts": brief.get("courts", []),
        "marks": brief.get("marks", {}),
        "provenance": {
            "canon": canon.get("doc", ""),
            "place": canon.get("place", ""),
            "scenes": canon.get("scenes", []),
            "brief_round": brief.get("round", 1),
        },
    }
    report = {
        "counts": {
            "floors": len(floors),
            "walls": len(room["walls"]),
            "flights": len(room["flights"]),
            "doors": len(doors),
            "windows": len(windows),
            "holes": len(holes),
            "lights": len(room["lights"]),
            "switches": len(room["switches"]),
            "things": len(room["things"]),
            "marks": len(room["marks"]),
        },
        "warnings": warnings + check(room),
    }
    return room, report


# ---------------------------------------------------------------------------------------------
# check: what the walking grid, the kit and the canon need
# ---------------------------------------------------------------------------------------------


def _grid_steps(room, f, bounds):
    """
    The worst step between neighbouring cells of the walking grid (as nav.ts fills it) up the
    flight and onto the floors at either end. A flight's long sides drop to the floor beside it:
    the balustrade and the cells blocked under it keep the walker off, so those are not steps.
    """
    x0, z0, _x1, _z1 = bounds
    fp = flight_plan(f)
    dx, dz = DIRS[f["dir"]]
    right = (-dz, dx)
    h = f["width"] / 2

    def local(x, z):
        ox, oz = x - f["from"][0], z - f["from"][1]
        return ox * dx + oz * dz, ox * right[0] + oz * right[1]

    worst = 0.0
    where = None
    sx0, sz0, sx1, sz1 = bbox(fp["walk"])
    for iz in range(math.floor((sz0 - z0) / CELL) - 2, math.floor((sz1 - z0) / CELL) + 3):
        for ix in range(math.floor((sx0 - x0) / CELL) - 2, math.floor((sx1 - x0) / CELL) + 3):
            x = x0 + (ix + 0.5) * CELL
            z = z0 + (iz + 0.5) * CELL
            s, w = local(x, z)
            if abs(w) > h:
                continue
            nx, nz = x + dx * CELL, z + dz * CELL
            ns, _nw = local(nx, nz)
            # a pair up the flight, one of them on it
            if not (-f["tread"] / 2 <= s <= fp["run"] + f["tread"] / 2 or -f["tread"] / 2 <= ns <= fp["run"] + f["tread"] / 2):
                continue
            y = walk_y(room, x, z)
            ny = walk_y(room, nx, nz)
            if y is None or ny is None:
                continue
            if abs(ny - y) > worst:
                worst = abs(ny - y)
                where = (round(x, 2), round(z, 2))
    return worst, where


def bounds_of(room):
    pts = []
    for f in room["floors"]:
        pts += f["shape"]
    for w in room["walls"]:
        pts += [w["a"], w["b"]]
    for c in room.get("courts", []):
        pts += [[c["x0"], c["z0"]], [c["x1"], c["z1"]]]
    for f in room["flights"]:
        pts += flight_plan(f)["shape"]
    x0, z0, x1, z1 = bbox(pts)
    return x0 - 2, z0 - 2, x1 + 2, z1 + 2


def in_doorway(room, x, z):
    for d in room["doors"]:
        w = room["walls"][d["wall"]]
        a, b = w["a"], w["b"]
        ln = length(a, b) or 1.0
        tx, tz = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
        nx, nz = -tz, tx
        u = (x - a[0]) * tx + (z - a[1]) * tz
        v = (x - a[0]) * nx + (z - a[1]) * nz
        if d["u0"] - 0.05 <= u <= d["u1"] + 0.05 and -WALL - 0.05 <= v <= 0.35:
            return True
    return False


def check(room: dict) -> list[str]:
    """What is wrong with a room file, if anything."""
    p: list[str] = []
    rid = room.get("id", "?")
    if room.get("kind") != "room" or room.get("version") != 1:
        p.append("a room file is kind room, version 1")
    for k in ("title", "can_do"):
        w = room.get(k) or {}
        if not all(w.get(lang) for lang in ("fr", "en", "de")):
            p.append(f"{k} in three languages")
    if not room.get("in"):
        p.append("a room is in a place on the map (`in`)")
    for f in room["floors"]:
        if f["finish"] not in FLOOR_FINISHES:
            p.append(f"floor {f['key']}: finish {f['finish']}")
        if f.get("zone", "room") not in ZONES:
            p.append(f"floor {f['key']}: zone {f.get('zone')}")
    for w in room["walls"]:
        if w["finish"] not in WALL_FINISHES:
            p.append(f"wall {w['key']}: finish {w['finish']}")
        for t in ("tone", "dado"):
            if w.get(t) and w[t] not in TONES:
                p.append(f"wall {w['key']}: {t} {w[t]} is not one of the kit's tones")
        if length(w["a"], w["b"]) < 0.05:
            p.append(f"wall {w['key']} has no length")
    # you start on ground you can walk
    sx, sz = room["start"]["pos"]
    if walk_y(room, sx, sz) is None:
        p.append(f"the start {room['start']['pos']} is off the walkable ground")
    # the flights: straight, gentle enough for the walking grid, and their ramps meet the floors
    bounds = bounds_of(room)
    for f in room["flights"]:
        if f["dir"] not in DIRS:
            p.append(f"flight {f['key']}: it climbs along x or z")
            continue
        fp = flight_plan(f)
        slope = (f["y1"] - f["y0"]) / (fp["run"] + f["tread"])
        if slope >= 0.7:
            p.append(f"flight {f['key']}: slope {slope:.2f} is too steep for the walking grid (under 0.7)")
        rise = fp["rise"]
        if not 0.14 <= rise <= 0.2:
            p.append(f"flight {f['key']}: a riser of {rise:.3f} m is not a stair's")
        worst, where = _grid_steps(room, f, bounds)
        if worst >= STEP:
            p.append(f"flight {f['key']}: a step of {worst:.2f} m between cells near {where}: the walker cannot climb it")
    # walkable ground at two heights must not lie over itself in plan (the grid has one height a cell)
    ws = walks(room)
    for i in range(len(ws)):
        for j in range(i + 1, len(ws)):
            a, b = ws[i], ws[j]
            ax0, az0, ax1, az1 = bbox(a["shape"])
            bx0, bz0, bx1, bz1 = bbox(b["shape"])
            x0, z0, x1, z1 = max(ax0, bx0), max(az0, bz0), min(ax1, bx1), min(az1, bz1)
            if x1 - x0 < 0.02 or z1 - z0 < 0.02:
                continue
            n = 12
            for k in range(n * n):
                x = x0 + (x1 - x0) * ((k % n) + 0.5) / n
                z = z0 + (z1 - z0) * ((k // n) + 0.5) / n
                if inside(a["shape"], x, z) and inside(b["shape"], x, z) and abs(a["y"](x, z) - b["y"](x, z)) > STEP:
                    p.append(f"{a['key']} and {b['key']} lie over each other at ({x:.2f}, {z:.2f}): the walking grid has one height a cell")
                    break
    # openings stand in their walls
    for kind, items in (("door", room["doors"]), ("window", room["windows"]), ("hole", room.get("holes", []))):
        for o in items:
            if not 0 <= o["wall"] < len(room["walls"]):
                p.append(f"{kind} {o.get('key', '')}: no wall {o['wall']}")
                continue
            w = room["walls"][o["wall"]]
            ln = length(w["a"], w["b"])
            if not (-0.001 <= o["u0"] < o["u1"] <= ln + 0.001):
                p.append(f"{kind} {o.get('key', '')} on {w['key']}: u {o['u0']}..{o['u1']} outside the wall's {ln:.2f} m")
            base = w["base"] if isinstance(w["base"], (int, float)) else min(w["base"])
            top = w["top"] if isinstance(w["top"], (int, float)) else min(w["top"])
            if kind == "door" and base + o["height"] > top - 0.05:
                p.append(f"door {o['key']}: {o['height']} m does not fit under {w['key']}'s top")
            if kind != "door" and not (base - 0.02 <= o["y0"] < o["y1"] <= top + 0.01):
                p.append(f"{kind} {o.get('key', '')}: y {o['y0']}..{o['y1']} outside {w['key']}")
    for d in room["doors"]:
        if d.get("hinge") not in ("left", "right", "both") or d.get("swing") not in ("in", "out"):
            p.append(f"door {d['key']}: hinge left/right/both, swing in/out")
        if d.get("opens", "never") not in ("never", "once"):
            p.append(f"door {d['key']}: it opens never or once")
        if d.get("numeral") and not str(d["numeral"]).isdigit():
            p.append(f"door {d['key']}: a brass numeral is figures")
        if d.get("tone") and d["tone"] not in TONES:
            p.append(f"door {d['key']}: tone {d['tone']}")
    # the light: every lamp on a circuit that has a button and a timer, every button lighting something
    circuits = {lamp.get("circuit") for lamp in room["lights"] if lamp.get("circuit")}
    buttons = {s["circuit"] for s in room["switches"]}
    for lamp in room["lights"]:
        if lamp["kind"] not in LIGHTS:
            p.append(f"light {lamp['key']}: kind {lamp['kind']}")
        if lamp["kind"] != "globe" and not lamp.get("facing"):
            p.append(f"light {lamp['key']}: a lamp on a wall says which way it faces")
    for c in circuits:
        if c not in buttons:
            p.append(f"circuit {c}: no push-button lights it")
        if not room["timers"].get(c):
            p.append(f"circuit {c}: no timer (a minuterie goes out)")
    for c in buttons - circuits:
        p.append(f"the buttons of {c} light nothing")
    for s in room["switches"]:
        x, y, z = s["at"]
        fy = walk_y(room, x + s["facing"][0] * 0.55, z + s["facing"][1] * 0.55)
        if fy is None:
            p.append(f"switch {s['key']}: nobody can stand in front of it")
        elif not 1.0 <= y - fy <= 1.7:
            p.append(f"switch {s['key']}: {y - fy:.2f} m above the floor, out of a hand's reach")
    for t in room["things"]:
        if t["kind"] not in THINGS:
            p.append(f"thing {t['kind']} is not one the kit draws")
        if t.get("tone") and t["tone"] not in TONES:
            p.append(f"thing {t['kind']}: tone {t['tone']}")
        for k in ("look", "did"):
            if k in t and not all((t[k] or {}).get(lang) for lang in ("fr", "en", "de")):
                p.append(f"thing {t['kind']}: its {k} in three languages")
        if t.get("did") and not t.get("look"):
            p.append(f"thing {t['kind']}: the end card remembers a look the room never gives")
    if room.get("arrive") and not all(room["arrive"].get(lang) for lang in ("fr", "en", "de")):
        p.append("arrive in three languages")
    # the marks: on the ground at its height, in a doorway, or a sight in a room not entered yet
    for k, (x, y, z) in room["marks"].items():
        wy = walk_y(room, x, z)
        if wy is not None:
            if abs(wy - y) > 0.3:
                p.append(f"mark {k}: at {y} m, the ground there is at {wy:.2f}")
            continue
        if in_doorway(room, x, z):
            continue
        if any(f.get("zone", "room") != "room" and inside(f["shape"], x, z) for f in room["floors"]):
            continue
        p.append(f"mark {k} {[x, y, z]} is neither on the ground, nor in a doorway, nor in a room you see into")
    # a courtyard lies outside the room
    for c in room.get("courts", []):
        for f in room["floors"]:
            if f.get("zone", "room") == "room":
                fx0, fz0, fx1, fz1 = bbox(f["shape"])
                if fx0 < c["x1"] - 0.3 and c["x0"] + 0.3 < fx1 and fz0 < c["z1"] - 0.3 and c["z0"] + 0.3 < fz1:
                    p.append(f"the courtyard overlaps {f['key']}")
    # the canon: a door the story opens once is the season's (Odile's «1»)
    for d in room["doors"]:
        if d.get("opens") == "once" and not d.get("numeral"):
            p.append(f"door {d['key']}: the door the story opens has its number")
    _ = rid
    return p


# ---------------------------------------------------------------------------------------------
# plan: the room from above
# ---------------------------------------------------------------------------------------------


def plan(room: dict) -> str:
    """An SVG of the room from above: floors by height, walls, doors, windows, flights, lamps, marks."""
    x0, z0, x1, z1 = bounds_of(room)
    S = 40.0  # pixels a metre
    W = int((x1 - x0) * S)
    H = int((z1 - z0) * S)

    def P(x, z):
        return f"{(x - x0) * S:.1f},{(z - z0) * S:.1f}"

    def xy(x, z):
        return (x - x0) * S, (z - z0) * S

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="background:#efe8da" font-family="sans-serif">']
    for c in room.get("courts", []):
        out.append(f'<polygon points="{" ".join(P(*q) for q in rect([c["x0"], c["z0"], c["x1"], c["z1"]]))}" fill="#c9cdd6" stroke="#6f7380" stroke-dasharray="4 3"/>')
    paint = {"room": "#e8dcc0", "sealed": "#b8b2c8", "out": "#c9cdd6"}
    for f in sorted(room["floors"], key=lambda f: f["y"]):
        tint = min(0.45, f["y"] / 12)
        out.append(f'<polygon points="{" ".join(P(*q) for q in f["shape"])}" fill="{paint[f.get("zone", "room")]}" fill-opacity="{1 - tint:.2f}" stroke="#8a7d66" stroke-width="0.6"/>')
        cx = sum(q[0] for q in f["shape"]) / len(f["shape"])
        cz = sum(q[1] for q in f["shape"]) / len(f["shape"])
        out.append(f'<text x="{xy(cx, cz)[0]:.0f}" y="{xy(cx, cz)[1]:.0f}" font-size="11" fill="#5a5144" text-anchor="middle">{html.escape(f["key"])} {f["y"]:.2f}</text>')
    for f in room["flights"]:
        fp = flight_plan(f)
        out.append(f'<polygon points="{" ".join(P(*q) for q in fp["shape"])}" fill="#d8c99b" stroke="#8a7d66"/>')
        dx, dz = DIRS[f["dir"]]
        right = (-dz, dx)
        h = f["width"] / 2
        for i in range(f["risers"]):
            s = i * f["tread"]
            a = [f["from"][0] + dx * s - right[0] * h, f["from"][1] + dz * s - right[1] * h]
            b = [f["from"][0] + dx * s + right[0] * h, f["from"][1] + dz * s + right[1] * h]
            out.append(f'<line x1="{xy(*a)[0]:.1f}" y1="{xy(*a)[1]:.1f}" x2="{xy(*b)[0]:.1f}" y2="{xy(*b)[1]:.1f}" stroke="#8a7d66" stroke-width="0.7"/>')
        ax, az = xy(*fp["ramp"]["from"])
        bx, bz = xy(*fp["ramp"]["to"])
        out.append(f'<line x1="{ax:.1f}" y1="{az:.1f}" x2="{bx:.1f}" y2="{bz:.1f}" stroke="#d8321a" stroke-width="1.4" marker-end="url(#up)"/>')
    for w in room["walls"]:
        col = {"room": "#14110d", "sealed": "#5d5873", "out": "#6f7380"}[w.get("zone", "room")]
        ax, az = xy(*w["a"])
        bx, bz = xy(*w["b"])
        out.append(f'<line x1="{ax:.1f}" y1="{az:.1f}" x2="{bx:.1f}" y2="{bz:.1f}" stroke="{col}" stroke-width="{3 if w.get("plain") else 4}"/>')
    for d in room["doors"]:
        w = room["walls"][d["wall"]]
        a = along(w["a"], w["b"], d["u0"])
        b = along(w["a"], w["b"], d["u1"])
        out.append(f'<line x1="{xy(*a)[0]:.1f}" y1="{xy(*a)[1]:.1f}" x2="{xy(*b)[0]:.1f}" y2="{xy(*b)[1]:.1f}" stroke="{"#d8321a" if d.get("opens") == "once" else "#2c6a5d"}" stroke-width="6"/>')
        mx, mz = xy((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        out.append(f'<text x="{mx:.0f}" y="{mz - 6:.0f}" font-size="11" fill="#d8321a" text-anchor="middle">{html.escape(d["key"])}{" «" + d["numeral"] + "»" if d.get("numeral") else ""}</text>')
    for wn in room["windows"]:
        w = room["walls"][wn["wall"]]
        a = along(w["a"], w["b"], wn["u0"])
        b = along(w["a"], w["b"], wn["u1"])
        out.append(f'<line x1="{xy(*a)[0]:.1f}" y1="{xy(*a)[1]:.1f}" x2="{xy(*b)[0]:.1f}" y2="{xy(*b)[1]:.1f}" stroke="#1d3a8a" stroke-width="6"/>')
    for r in room["rails"]:
        out.append(f'<line x1="{xy(r["a"][0], r["a"][2])[0]:.1f}" y1="{xy(r["a"][0], r["a"][2])[1]:.1f}" x2="{xy(r["b"][0], r["b"][2])[0]:.1f}" y2="{xy(r["b"][0], r["b"][2])[1]:.1f}" stroke="#2c6a5d" stroke-width="2" stroke-dasharray="3 2"/>')
    for lamp in room["lights"]:
        x, z = xy(lamp["at"][0], lamp["at"][2])
        out.append(f'<circle cx="{x:.1f}" cy="{z:.1f}" r="{lamp["range"] * S:.0f}" fill="#f3c318" fill-opacity="0.12"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{z:.1f}" r="5" fill="#f3c318" stroke="#14110d"/>')
    for s in room["switches"]:
        x, z = xy(s["at"][0], s["at"][2])
        out.append(f'<circle cx="{x:.1f}" cy="{z:.1f}" r="4" fill="#e8742a" stroke="#14110d"/>')
    for t in room["things"]:
        x, z = xy(t["at"][0], t["at"][2])
        out.append(f'<rect x="{x - 3:.1f}" y="{z - 3:.1f}" width="6" height="6" fill="#7a4a2a"/>')
        out.append(f'<text x="{x + 5:.0f}" y="{z + 4:.0f}" font-size="9" fill="#7a4a2a">{t["kind"]}</text>')
    for k, (x, _y, z) in room["marks"].items():
        px, pz = xy(x, z)
        out.append(f'<circle cx="{px:.1f}" cy="{pz:.1f}" r="3" fill="none" stroke="#1d3a8a" stroke-width="1.5"/>')
        out.append(f'<text x="{px + 4:.0f}" y="{pz - 4:.0f}" font-size="10" fill="#1d3a8a">{html.escape(k)}</text>')
    sx, sz = xy(*room["start"]["pos"])
    out.append(f'<circle cx="{sx:.1f}" cy="{sz:.1f}" r="8" fill="none" stroke="#d8321a" stroke-width="3"/>')
    out.insert(1, '<defs><marker id="up" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#d8321a"/></marker></defs>')
    out.append("</svg>")
    return "\n".join(out)
