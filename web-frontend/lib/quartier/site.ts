/**
 * Le Quartier · a forged place, built.
 *
 * The forge (`scripts/forge`) surveys a corner of Paris from open map data and drafts it as a
 * site file (`world/sites/<id>.json`): the ground cut into carriageway, pavements, squares and
 * planted beds; every building as convex pieces with its façades on the street, its shops, doors
 * and house numbers; the plaques at the corners, the lamps, the trees, the crossings; a market's
 * stalls, the landmarks the place is known by, and the hoardings where the walkable world ends.
 * This lays a site into a build with the same kit as the quai, so a forged street and the
 * hand-drawn one are the same print.
 */
import { ShapeUtils, Vector2, Vector3 } from 'three';

import { KERB, WALLS, bench, building, frameOf, groundOf, planeTree, quayLamp, worldOf } from './kit';
import type { Build, BuildingSpec, Run, Shop, ShopKind } from './kit';
import { PATTERN, area2 } from './geo';
import type { Paint, Press, Shape2 } from './geo';
import { glassBin, halle, hoarding, hoop, pavillon, postBox } from './landmarks';
import type { LandmarkBuilt, LandmarkSpec } from './landmarks';
import { stall } from './market';
import type { GoodsKind, StallInfo } from './market';
import type { Words } from './memory';
import { inside } from './nav';
import { INKS, TONES, mix } from './palette';
import type { AmbianceId, Hex } from './palette';
import { plaqueArt } from './signs';

type XZ = [number, number];

export interface SitePolygon {
  outer: XZ[];
  holes: XZ[][];
}

export interface SiteShop {
  from: number;
  to: number;
  kind: ShopKind;
  /** a house paint (`PAINTS`) */
  paint?: string;
  name?: string;
  trade?: string;
  awning?: string;
  number?: string;
}

export interface SiteBuilding {
  /** a convex piece of a building, wound the kit's way (negative area in x, z) */
  fp: XZ[];
  /** 1 where the edge from corner i to i + 1 faces a street */
  street: number[];
  runs?: Array<{ e: number; bays: number; shops: SiteShop[] }>;
  storeys: number;
  style: BuildingSpec['style'];
  /** an index into the kit's `WALLS` */
  wall: number;
  balconies?: number[];
  lit?: number;
  seed: number;
  /** 1: far from where you can walk (no small relief, no lettering) */
  lod?: number;
}

/** Someone who keeps a stall or a counter: where they stand, and which goods they sell. */
export interface SitePerson {
  key: string;
  name: Words;
  goods?: GoodsKind;
  /** a counter inside a landmark, found when the landmark is built */
  in?: string;
  pos: XZ;
  rot: number;
  /** the same seed, the same face */
  seed?: number;
  /** what the avatar kit dresses them in over the seed's roll (`lib/avatar.ts` slots) */
  look?: Record<string, string | boolean>;
  /** an errand that leads you to them, the first time */
  goal?: Words;
}

export interface SiteSpec {
  id: string;
  version: number;
  /** the centre, lat and lon: x is metres east of it, z metres south */
  origin: [number, number];
  radius: { walk: number; build: number };
  ambiance: AmbianceId;
  title: Words;
  can_do: Words;
  /** on the street plaques, «12e Arrt» */
  arrondissement?: string;
  start: { pos: XZ; look: [number, number, number] };
  ground: {
    street: SitePolygon[];
    carriageway: SitePolygon[];
    pavement: SitePolygon[];
    squares: SitePolygon[];
    gravel: SitePolygon[];
    green: SitePolygon[];
  };
  walk: SitePolygon[];
  /** where you can walk, as rings the grid fills in order */
  nav: { kerb: XZ[][]; road: XZ[][]; islands: XZ[][]; holes: XZ[][] };
  buildings: SiteBuilding[];
  landmarks: LandmarkSpec[];
  /** a street's name on building `b`'s edge `e`, `u` metres along it */
  plaques: Array<{ b: number; e: number; u: number; text: string }>;
  lamps: XZ[];
  trees: Array<[number, number, number]>;
  benches: Array<[number, number, number]>;
  hoops: Array<[number, number, number]>;
  bins: XZ[];
  posts: Array<[number, number, number]>;
  /** zebra crossings: the middle, the road's direction there, the width to cross */
  crossings: Array<{ c: XZ; t: XZ; w: number }>;
  stalls: Array<{ c: XZ; rot: number; w: number; goods: GoodsKind }>;
  fences: XZ[][];
  /** where the passers-by go, and how long some stay */
  spots: Array<{ at: XZ; linger?: [number, number] }>;
  people: SitePerson[];
  provenance: { data: string; release: string; surveyed: string; papier?: string; brief_round?: number };
}

export interface SiteBuilt {
  spec: SiteSpec;
  /** the stalls in the open, in the order of `spec.stalls` */
  stalls: StallInfo[];
  landmarks: LandmarkBuilt[];
  start: { pos: Vector3; look: Vector3 };
  /** under a roof you can walk under (the market hall): the lamps there light the room */
  under: (x: number, z: number) => boolean;
  /** the carriageway, at street level (the rest of the ground is a kerb higher) */
  onRoad: (x: number, z: number) => boolean;
}

/** The painted fronts and doors, by the names the forge gives them. */
export const PAINTS: Record<string, Hex> = {
  green: INKS.green,
  greenDark: mix(INKS.green, INKS.ink, 0.3),
  cobalt: INKS.cobalt,
  oxblood: TONES.oxblood,
  ink: mix(INKS.ink, INKS.cobalt, 0.15),
  ochre: mix(INKS.ochre, INKS.ink, 0.25),
  vermilion: INKS.vermilion,
  sunflower: INKS.sunflower,
};

const GROUND = {
  under: { color: mix(TONES.pavement, INKS.ink, 0.14), id: 11 } as Paint,
  road: { color: TONES.asphalt, pattern: PATTERN.grit, id: 1 } as Paint,
  walk: { color: TONES.pavement, pattern: PATTERN.grit, id: 2 } as Paint,
  setts: { color: mix(TONES.stoneGround, INKS.cobalt, 0.08), pattern: PATTERN.cobbles, id: 3 } as Paint,
  gravel: { color: mix(INKS.paper, INKS.ochre, 0.3), pattern: PATTERN.grit, id: 9 } as Paint,
  grass: { color: mix(INKS.green, INKS.sunflower, 0.32), pattern: PATTERN.grit, id: 10 } as Paint,
  kerb: { color: TONES.curb, id: 5 } as Paint,
  kerbTop: { color: mix(TONES.curb, INKS.paper, 0.35), id: 5 } as Paint,
  gutter: { color: mix(TONES.asphalt, INKS.ink, 0.25), id: 1 } as Paint,
  zebra: { color: mix(INKS.card, INKS.ink, 0.08), id: 6 } as Paint,
};

/** Lay a polygon (with its holes) flat at height `y`, faces up. */
function flat(P: Press, poly: SitePolygon, y: number, paint: Paint) {
  if (poly.outer.length < 3) return;
  const outer = poly.outer.map(([x, z]) => new Vector2(x, z));
  const holes = poly.holes.filter((h) => h.length >= 3).map((h) => h.map(([x, z]) => new Vector2(x, z)));
  const tris = ShapeUtils.triangulateShape(outer, holes);
  // the triangulation counts the holes' points after the outline's, in order
  const pts = holes.reduce((all, h) => all.concat(h), outer.slice());
  tris.forEach(([a, b, c]) => {
    const pa = pts[a];
    const pb = pts[b];
    const pc = pts[c];
    if (!pa || !pb || !pc) return;
    const cross = (pb.x - pa.x) * (pc.y - pa.y) - (pb.y - pa.y) * (pc.x - pa.x);
    if (Math.abs(cross) < 1e-6) return;
    const A = new Vector3(pa.x, y, pa.y);
    const B = new Vector3(pb.x, y, pb.y);
    const C = new Vector3(pc.x, y, pc.y);
    // a negative area in (x, z) faces up
    if (cross < 0) P.tri(A, B, C, paint, paint.id);
    else P.tri(A, C, B, paint, paint.id);
  });
}

/** A convex quad flat at `y`, faces up whatever its winding. */
function flatQuad(P: Press, pts: XZ[], y: number, paint: Paint) {
  const s = area2(pts) > 0 ? pts.slice().reverse() : pts;
  const v = s.map(([x, z]) => new Vector3(x, y, z));
  P.quad(v[0], v[1], v[2], v[3], paint, paint.id);
}

/** The ring wound so that its edges' right-hand normal (−t.z, t.x) points the way `sign` says. */
function wound(ring: XZ[], sign: 1 | -1): XZ[] {
  return Math.sign(area2(ring)) === sign ? ring : ring.slice().reverse();
}

/**
 * The kerbstones along a carriageway's outline: a face down to the road, a pale top on the
 * pavement side, the gutter's dark band on the road. `roadInside`: the road is inside the ring
 * (its outline), not outside it (an island). Edges out at the edge of the built disc are not kerbs.
 */
function kerbRing(B: Build, ring: XZ[], roadInside: boolean, rMax: number) {
  // a ring with positive area has its right-hand normal pointing in
  const pts = wound(ring, roadInside ? 1 : -1);
  const far = (p: XZ) => Math.hypot(p[0], p[1]) > rMax - 0.8;
  for (let i = 0; i < pts.length; i++) {
    const p0 = pts[i];
    const p1 = pts[(i + 1) % pts.length];
    if (far(p0) && far(p1)) continue;
    const len = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
    if (len < 0.02) continue;
    const tx = (p1[0] - p0[0]) / len;
    const tz = (p1[1] - p0[1]) / len;
    // toward the road
    const nx = -tz;
    const nz = tx;
    B.dry.quad(new Vector3(p0[0], 0, p0[1]), new Vector3(p1[0], 0, p1[1]), new Vector3(p1[0], KERB, p1[1]), new Vector3(p0[0], KERB, p0[1]), GROUND.kerb, GROUND.kerb.id);
    flatQuad(B.dry, [p0, p1, [p1[0] - nx * 0.2, p1[1] - nz * 0.2], [p0[0] - nx * 0.2, p0[1] - nz * 0.2]], KERB + 0.004, GROUND.kerbTop);
    flatQuad(B.wet, [p0, p1, [p1[0] + nx * 0.35, p1[1] + nz * 0.35], [p0[0] + nx * 0.35, p0[1] + nz * 0.35]], 0.003, GROUND.gutter);
  }
}

/** Is (x, z) inside the polygon and out of its holes? */
function within(poly: SitePolygon, x: number, z: number) {
  return inside(poly.outer, x, z) && !poly.holes.some((h) => inside(h, x, z));
}

/** Lay the whole site into the build. */
export function buildSite(B: Build, site: SiteSpec): SiteBuilt {
  const rBuild = site.radius.build;
  const night = site.ambiance === 'nuit';
  const onRoad = (x: number, z: number) => site.ground.carriageway.some((p) => within(p, x, z));
  const yAt = (x: number, z: number) => (onRoad(x, z) ? 0 : KERB);

  /* ---- the ground ------------------------------------------------------------------------ */
  // a floor under everything, out past the last houses, so no gap shows the sky below
  {
    const r = rBuild + 140;
    const n = 48;
    const disc: XZ[] = [];
    for (let i = 0; i < n; i++) disc.push([Math.cos((i / n) * Math.PI * 2) * r, Math.sin((i / n) * Math.PI * 2) * r]);
    flat(B.wet, { outer: disc, holes: [] }, -0.08, GROUND.under);
  }
  site.ground.carriageway.forEach((p) => flat(B.wet, p, 0, GROUND.road));
  site.ground.pavement.forEach((p) => flat(B.wet, p, KERB, GROUND.walk));
  site.ground.squares.forEach((p) => flat(B.wet, p, KERB, GROUND.setts));
  site.ground.gravel.forEach((p) => flat(B.wet, p, KERB, GROUND.gravel));
  site.ground.green.forEach((p) => flat(B.dry, p, KERB + 0.03, GROUND.grass));
  site.ground.carriageway.forEach((p) => {
    kerbRing(B, p.outer, true, rBuild);
    p.holes.forEach((h) => kerbRing(B, h, false, rBuild));
  });
  // the zebra crossings: bands along the road, a metre apart across it
  site.crossings.forEach(({ c, t, w }) => {
    const ax = -t[1];
    const az = t[0];
    for (let s = -w / 2 + 0.5; s <= w / 2 - 0.5; s += 1.0) {
      const cx = c[0] + ax * s;
      const cz = c[1] + az * s;
      const L = 1.4;
      const H = 0.25;
      flatQuad(
        B.wet,
        [
          [cx - t[0] * L - ax * H, cz - t[1] * L - az * H],
          [cx + t[0] * L - ax * H, cz + t[1] * L - az * H],
          [cx + t[0] * L + ax * H, cz + t[1] * L + az * H],
          [cx - t[0] * L + ax * H, cz - t[1] * L + az * H],
        ],
        0.006,
        GROUND.zebra,
      );
    }
  });

  /* ---- the buildings --------------------------------------------------------------------- */
  const shopOf = (s: SiteShop): Shop => ({
    from: s.from,
    to: s.to,
    kind: s.kind,
    color: s.paint ? PAINTS[s.paint] ?? INKS.green : undefined,
    name: s.name,
    trade: s.trade,
    awning: s.awning ? PAINTS[s.awning] : undefined,
    lit: s.kind === 'shop',
    number: s.number,
  });
  site.buildings.forEach((b) => {
    const fp = b.fp;
    const runs: Run[] = (b.runs ?? []).map((r) => ({ a: fp[r.e], b: fp[(r.e + 1) % fp.length], bays: r.bays, shops: r.shops.map(shopOf) }));
    building(B, {
      runs,
      footprint: fp as Shape2,
      street: b.street.map((s) => s === 1),
      style: b.style,
      storeys: b.storeys,
      wall: WALLS[b.wall % WALLS.length],
      balconies: b.balconies,
      lit: b.lit,
      lod: b.lod,
      seed: b.seed,
    });
  });
  // the street plaques, on the first floor's corner pier
  site.plaques.forEach((p) => {
    const b = site.buildings[p.b];
    if (!b || b.lod) return;
    const f = frameOf(b.fp[p.e], b.fp[(p.e + 1) % b.fp.length]);
    const [x, z] = worldOf(f, p.u, 0.03);
    B.signs.push({ key: `plaque:${p.text}`, center: new Vector3(x, groundOf(b.style) + 0.6, z), normal: f.n.clone(), width: 0.9, height: 0.4, density: 260, draw: plaqueArt(p.text, site.arrondissement ?? '') });
  });

  /* ---- the street's furniture ------------------------------------------------------------- */
  site.lamps.forEach(([x, z]) => quayLamp(B, x, z, yAt(x, z), night));
  // past where you can walk, a tree is only ever seen over the rooftops
  const farTree = site.radius.walk + 10;
  site.trees.forEach(([x, z, s]) => planeTree(B, x, z, yAt(x, z), s, Math.hypot(x, z) > farTree));
  site.benches.forEach(([x, z, rot]) => bench(B, x, z, rot, yAt(x, z)));
  site.hoops.forEach(([x, z, rot]) => hoop(B, x, z, rot, yAt(x, z)));
  site.bins.forEach(([x, z]) => glassBin(B, x, z, yAt(x, z)));
  site.posts.forEach(([x, z, rot]) => postBox(B, x, z, rot, yAt(x, z)));

  /* ---- the market and the landmarks ------------------------------------------------------- */
  const stalls = site.stalls.map((s, i) => stall(B, s.c[0], s.c[1], s.rot, s.w, s.goods, 500 + i, yAt(s.c[0], s.c[1])));
  const landmarks = site.landmarks.map((l, i) => (l.kind === 'halle' ? halle(B, l, 7 + i) : pavillon(B, l)));
  site.fences.forEach((pts, i) => hoarding(B, pts, i));

  /* ---- where you can walk ----------------------------------------------------------------- */
  site.nav.kerb.forEach((r) => B.walk.push({ shape: r, y: KERB }));
  site.nav.road.forEach((r) => B.walk.push({ shape: r, y: 0 }));
  site.nav.islands.forEach((r) => B.walk.push({ shape: r, y: KERB }));
  site.nav.holes.forEach((r) => B.blocks.push(r));

  const halls = site.landmarks.filter((l) => l.kind === 'halle');
  const under = (x: number, z: number) =>
    halls.some((l) => {
      const dx = x - l.c[0];
      const dz = z - l.c[1];
      const along = dx * l.u[0] + dz * l.u[1];
      const across = -dx * l.u[1] + dz * l.u[0];
      return Math.abs(along) < l.len / 2 && Math.abs(across) < l.wid / 2;
    });
  const [sx, sz] = site.start.pos;
  return {
    spec: site,
    stalls,
    landmarks,
    start: { pos: new Vector3(sx, 0, sz), look: new Vector3(site.start.look[0], site.start.look[1], site.start.look[2]) },
    under,
    onRoad,
  };
}
