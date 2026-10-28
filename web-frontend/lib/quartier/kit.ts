/**
 * Le Quartier · the Paris kit.
 *
 * A Haussmann street is a grammar more than a set of models: a tall stone ground floor with
 * shops, storeys whose windows line up in bays, a continuous balcony on the second and the fifth,
 * a cornice, and a zinc mansard with dormers and chimney pots. These functions speak that
 * grammar from a few numbers per building (the façade line, storeys, bays, which shops, which
 * windows are lit), so no two buildings repeat and none had to be modelled.
 *
 * Coordinates are metres: x east, z south, y up, street level at y = 0 and the pavements a kerb
 * higher. A façade is given by its foot from `a` to `b`, with the street on the right-hand side;
 * the kit builds it in that local frame (u along the façade, the street toward +z).
 */
import { Matrix4, Vector3 } from 'three';

import { CardPress, LACE, LacePress, PATTERN, Press, nextId, outward } from './geo';
import type { Paint, Rand, Shape2 } from './geo';
import { INKS, TONES, mix, rgb } from './palette';
import type { Hex } from './palette';

export const KERB = 0.14;

/** A light in the quarter: it pools on the ground (the light map) and glints on wet stone. */
export interface Lamp {
  pos: Vector3;
  color: [number, number, number];
  /** brightness at the centre of its pool */
  power: number;
  /** radius of its pool on the ground, metres */
  range: number;
  /** whether it shows as a streak on wet stone and water */
  glint: boolean;
  /** lit indoors only (the café's globes) */
  indoor?: boolean;
}

/** A card of text or a picture to print into the sign atlas, and where it hangs. */
export interface SignSpec {
  key: string;
  center: Vector3;
  normal: Vector3;
  width: number;
  height: number;
  /** pixels per metre on the atlas */
  density?: number;
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void;
  tilt?: number;
  /** hangs inside the café: lit by its globes rather than by the sky */
  indoor?: boolean;
}

export interface NavShape {
  shape: Shape2;
  /** walking height: a constant, or a ramp from one edge to the other */
  y: number | { from: [number, number]; to: [number, number]; y0: number; y1: number };
}

export interface Build {
  dry: Press;
  /** the small relief of the façades (window surrounds, sills, shutters, brackets): only drawn near you */
  fine: Press;
  /** the ground outside: the only surfaces that take the rain's glints */
  wet: Press;
  lace: LacePress;
  /** see-through panes (the café's windows and door) */
  glass: Press;
  cards: CardPress;
  signs: SignSpec[];
  lamps: Lamp[];
  walk: NavShape[];
  blocks: Shape2[];
  rand: Rand;
}

/* ------------------------------------------------------------------------------------------ */
/* frames and shapes                                                                          */
/* ------------------------------------------------------------------------------------------ */

export interface Frame {
  m: Matrix4;
  len: number;
  /** along the façade */
  t: Vector3;
  /** out, toward the street */
  n: Vector3;
  a: [number, number];
}

/** The local frame of a façade foot from `a` to `b` (street on the right), at height `y`. */
export function frameOf(a: [number, number], b: [number, number], y = 0): Frame {
  const t = new Vector3(b[0] - a[0], 0, b[1] - a[1]);
  const len = t.length();
  t.normalize();
  const n = new Vector3(-t.z, 0, t.x);
  const m = new Matrix4().makeBasis(t, new Vector3(0, 1, 0), n).setPosition(a[0], y, a[1]);
  return { m, len, t, n, a };
}

/** A local (u, w) point of a frame in world (x, z). */
export function worldOf(f: Frame, u: number, w: number): [number, number] {
  return [f.a[0] + f.t.x * u + f.n.x * w, f.a[1] + f.t.z * u + f.n.z * w];
}

/** A rectangle as a shape: x0..x1 by z0..z1. */
export function rect(x0: number, z0: number, x1: number, z1: number): Shape2 {
  return [
    [x0, z0],
    [x1, z0],
    [x1, z1],
    [x0, z1],
  ];
}

/** A rectangle along a frame: u0..u1 along, w0..w1 out. */
export function rectIn(f: Frame, u0: number, u1: number, w0: number, w1: number): Shape2 {
  return [worldOf(f, u0, w0), worldOf(f, u1, w0), worldOf(f, u1, w1), worldOf(f, u0, w1)];
}

/**
 * Pull a convex polygon's edges in by `insets[i]` (edge i runs from point i to point i + 1)
 * and return the corners of the smaller polygon. A zero inset keeps that edge where it is,
 * so a roof can slope from the street and the courtyard but rise straight at a party wall.
 */
export function insetPolygon(shape: Shape2, insets: number[]): Shape2 {
  const s = outward(shape);
  const flipped = s !== shape;
  const ins = flipped ? s.map((_, i) => insets[(s.length - 2 - i + s.length) % s.length]) : insets;
  const n = s.length;
  const lines = s.map((p, i) => {
    const q = s[(i + 1) % n];
    const dx = q[0] - p[0];
    const dz = q[1] - p[1];
    const len = Math.hypot(dx, dz) || 1;
    // the outward normal of an outward-wound edge is (-dz, dx); inward is the opposite
    const nx = dz / len;
    const nz = -dx / len;
    const d = ins[i] ?? 0;
    return { p: [p[0] + nx * d, p[1] + nz * d] as [number, number], d: [dx, dz] as [number, number] };
  });
  const out: Shape2 = [];
  for (let i = 0; i < n; i++) {
    const l0 = lines[(i - 1 + n) % n];
    const l1 = lines[i];
    const det = l0.d[0] * l1.d[1] - l0.d[1] * l1.d[0];
    if (Math.abs(det) < 1e-9) {
      out.push(l1.p);
      continue;
    }
    const t = ((l1.p[0] - l0.p[0]) * l1.d[1] - (l1.p[1] - l0.p[1]) * l1.d[0]) / det;
    out.push([l0.p[0] + l0.d[0] * t, l0.p[1] + l0.d[1] * t]);
  }
  return flipped ? out.reverse() : out;
}

/* ------------------------------------------------------------------------------------------ */
/* buildings                                                                                  */
/* ------------------------------------------------------------------------------------------ */

export type ShopKind = 'shop' | 'shutter' | 'none' | 'door' | 'wall' | 'window';

export interface Shop {
  /** first and last bay it takes on the ground floor */
  from: number;
  to: number;
  kind: ShopKind;
  /** the painted front (and the door, for a building's entrance) */
  color?: Hex;
  name?: string;
  /** a second line under the name, smaller */
  trade?: string;
  awning?: Hex;
  /** lit at night */
  lit?: boolean;
  /** a door's house number, on its blue plaque over the lintel */
  number?: string;
}

export interface Run {
  a: [number, number];
  b: [number, number];
  shops: Shop[];
  /** number of bays (default from the length) */
  bays?: number;
}

export interface BuildingSpec {
  runs: Run[];
  /** the whole footprint, any winding (default: the run pushed back by `depth`) */
  footprint?: Shape2;
  depth?: number;
  /** which footprint edges face a street (their roof slopes); the others are party walls */
  street?: boolean[];
  style: 'haussmann' | 'faubourg' | 'moderne';
  storeys: number;
  wall: Hex;
  /** storeys with a continuous balcony (1 is the first floor above the shops) */
  balconies?: number[];
  /** share of windows lit at night */
  lit?: number;
  /** windows with their shutters closed, as `run:storey:bay` */
  shut?: string[];
  /** lit on purpose (and never brighter than the street), as `run:storey:bay` */
  forceLit?: string[];
  /** leave the ground floor empty inside, for a room built separately (Le Mistral) */
  hollowGround?: boolean;
  /** 1: far from where you can walk, so none of the small relief (sills, shutters, lace) */
  lod?: number;
  seed: number;
}

export interface BuildingInfo {
  cornice: number;
  ridge: number;
  footprint: Shape2;
  /** world centre of each window, by `run:storey:bay` */
  windows: Map<string, { center: Vector3; normal: Vector3; width: number; height: number }>;
}

/** The house paints of the quarter's walls: stone, cream, and the faint tints of rendered plaster. */
export const WALLS: Hex[] = [
  TONES.stone,
  TONES.stoneLight,
  mix(INKS.paper, INKS.ochre, 0.18),
  mix(INKS.paper, INKS.ochre, 0.26),
  mix(INKS.paper, INKS.cobalt, 0.07),
  mix(INKS.paper, INKS.vermilion, 0.07),
  mix(INKS.card, INKS.green, 0.06),
];

const STOREYS = {
  haussmann: { ground: 4.6, heights: [3.3, 3.15, 3.0, 2.9, 2.8, 2.7], bay: 3.0, window: 1.25 },
  faubourg: { ground: 3.7, heights: [2.85, 2.75, 2.7, 2.65, 2.6, 2.6], bay: 2.7, window: 1.05 },
  // the housing of the 1960s to the 80s: even floors, wide windows, a flat roof
  moderne: { ground: 3.4, heights: [2.75, 2.75, 2.75, 2.75, 2.75, 2.75, 2.75, 2.75, 2.75], bay: 3.3, window: 1.7 },
};

/** The height of a style's ground floor (the shops), where the first floor's band runs. */
export function groundOf(style: BuildingSpec['style']) {
  return STOREYS[style].ground;
}

/** Where the small relief and the lettering of a far building go: built, never drawn. */
function sink(B: Build): Build {
  return { ...B, fine: new Press(), lace: new LacePress(), signs: [] };
}

/** Build a whole building: façades, body, roof, chimneys. */
export function building(B0: Build, spec: BuildingSpec): BuildingInfo {
  const B = spec.lod ? sink(B0) : B0;
  const R = B.rand;
  const kind = STOREYS[spec.style];
  const heights = kind.heights.slice(0, spec.storeys);
  const ground = kind.ground;
  const cornice = ground + heights.reduce((s, h) => s + h, 0);
  const wallId = nextId();
  const wall: Paint = { color: spec.wall, id: wallId };
  const stoneBase: Paint = { color: mix(spec.wall, INKS.ink, 0.04), id: wallId, pattern: spec.style === 'haussmann' ? PATTERN.courses : PATTERN.none };
  const first: Run | undefined = spec.runs[0];
  const depth = spec.depth ?? 14;
  const footprint: Shape2 =
    spec.footprint ??
    (() => {
      if (!first) throw new Error('a building needs a footprint or a façade');
      const f = frameOf(first.a, first.b);
      return [worldOf(f, 0, 0), worldOf(f, f.len, 0), worldOf(f, f.len, -depth), worldOf(f, 0, -depth)];
    })();
  const streetEdges = spec.street ?? footprint.map((_, i) => i === 0);
  const windows: BuildingInfo['windows'] = new Map();

  // the façades (a far one only as painted as it needs to be from the end of the street)
  spec.runs.forEach((run, ri) => {
    if (spec.lod) facadeFar(B, spec, run, { ground, heights, cornice, wall, stoneBase, wallId, windows });
    else facade(B, spec, run, ri, { ground, heights, cornice, wall, stoneBase, wallId, windows });
  });

  // the body behind the façades: pulled back from the streets so the reveals have depth
  const body = insetPolygon(footprint, streetEdges.map((s) => (s ? 0.26 : 0)));
  B.dry.prism(body, spec.hollowGround ? ground - 0.3 : -0.4, cornice + 0.02, { color: TONES.partyWall, id: wallId }, { top: false, bottom: !!spec.hollowGround });
  if (!spec.hollowGround) B.blocks.push(footprint);

  if (spec.style === 'moderne') {
    // a flat roof behind a parapet, and the lift's housing on the bigger blocks
    const coping = mix(spec.wall, INKS.ink, 0.1);
    B.dry.prism(footprint, cornice, cornice + 0.95, { color: coping, id: wallId }, { top: false });
    B.dry.prism(insetPolygon(footprint, footprint.map(() => 0.28)), cornice + 0.55, cornice + 0.57, { color: TONES.zincTop, id: nextId() }, { sides: false });
    const box = footprint.reduce((a, p) => [Math.min(a[0], p[0]), Math.min(a[1], p[1]), Math.max(a[2], p[0]), Math.max(a[3], p[1])], [Infinity, Infinity, -Infinity, -Infinity]);
    if ((box[2] - box[0]) * (box[3] - box[1]) > 260) {
      const cx = (box[0] + box[2]) / 2;
      const cz = (box[1] + box[3]) / 2;
      B.dry.block(cx, cornice + 0.55, cz, 2.6, 2.4, 3.2, { color: mix(spec.wall, INKS.ink, 0.05), id: wallId });
    }
    return { cornice, ridge: cornice + 0.95, footprint, windows };
  }

  // the roof: a mansard on the street sides, straight up at the party walls
  const roofBase = cornice + 0.5;
  const isH = spec.style === 'haussmann';
  const rise = isH ? 3.1 : 2.6;
  const set = isH ? 1.7 : 2.3;
  const top = insetPolygon(footprint, streetEdges.map((s, i) => (s ? set : i % 2 === 1 && footprint.length === 4 ? 0 : 0)));
  const zinc: Paint = { color: isH ? TONES.zinc : mix(TONES.zinc, INKS.ochre, 0.25), pattern: PATTERN.seams, id: nextId() };
  const gable: Paint = { color: TONES.partyWall, id: wallId };
  B.dry.prism(footprint, cornice, roofBase, { color: mix(spec.wall, INKS.ink, 0.06), id: wallId }, { top: false });
  const fp = outward(footprint);
  const tp = outward(top);
  const flip = fp !== footprint;
  const streetOut = flip ? footprint.map((_, i) => streetEdges[(footprint.length - 2 - i + footprint.length) % footprint.length]) : streetEdges;
  for (let i = 0; i < fp.length; i++) {
    const j = (i + 1) % fp.length;
    const p0 = new Vector3(fp[i][0], roofBase, fp[i][1]);
    const p1 = new Vector3(fp[j][0], roofBase, fp[j][1]);
    const q1 = new Vector3(tp[j][0], roofBase + rise, tp[j][1]);
    const q0 = new Vector3(tp[i][0], roofBase + rise, tp[i][1]);
    B.dry.quad(p0, p1, q1, q0, streetOut[i] ? zinc : gable);
  }
  // the flat top, and a ridge of zinc
  const ridge = roofBase + rise;
  B.dry.prism(top, ridge - 0.01, ridge + 0.12, { color: TONES.zincTop, id: zinc.id }, {});

  if (!first) return { cornice, ridge, footprint, windows };

  // dormers along the first run's slope
  const f0 = frameOf(first.a, first.b);
  const bays0 = first.bays ?? Math.max(1, Math.round(f0.len / kind.bay));
  const bw0 = f0.len / bays0;
  B.dry.push(f0.m);
  for (let i = 0; i < bays0; i++) {
    if (!isH && i % 2 === 1) continue;
    const cu = (i + 0.5) * bw0;
    const lit = R.chance((spec.lit ?? 0.3) * 0.8);
    dormer(B, cu, roofBase, rise, set, lit, spec.style);
  }
  B.dry.pop();

  // chimney stacks on the party walls, with their pots
  const stacks = Math.max(2, Math.round(f0.len / 9));
  for (let s = 0; s < stacks; s++) {
    const u = s === 0 ? 0.55 : s === stacks - 1 ? f0.len - 0.55 : (f0.len * s) / (stacks - 1);
    const wDepth = -(depth * R.range(0.35, 0.6));
    const [x, z] = worldOf(f0, u, wDepth);
    const h = R.range(1.2, 2.2);
    const long = R.range(1.6, 2.6);
    B.dry.at(x, ridge, z, Math.atan2(-f0.t.z, f0.t.x), () => {
      B.dry.block(0, -0.4, 0, 0.75, h + 0.4, long, { color: TONES.chimney, id: nextId() });
      B.dry.block(0, h, 0, 0.86, 0.12, long + 0.1, { color: mix(TONES.chimney, INKS.paper, 0.3), id: nextId() });
      if (spec.lod) return;
      const pots = Math.max(2, Math.round(long / 0.38));
      const potId = nextId();
      for (let p = 0; p < pots; p++) {
        const pz = -long / 2 + 0.22 + (p * (long - 0.44)) / Math.max(1, pots - 1);
        const ph = R.range(0.35, 0.65);
        B.dry.cylinder(0, h + 0.12, pz, 0.11, 0.085, ph, 6, { color: TONES.pot, id: potId }, { flat: true });
      }
    });
  }

  return { cornice, ridge, footprint, windows };
}

interface FacadeCtx {
  ground: number;
  heights: number[];
  cornice: number;
  wall: Paint;
  stoneBase: Paint;
  wallId: number;
  windows: BuildingInfo['windows'];
}

function facade(B: Build, spec: BuildingSpec, run: Run, ri: number, ctx: FacadeCtx) {
  const R = B.rand;
  const kind = STOREYS[spec.style];
  const f = frameOf(run.a, run.b);
  const W = f.len;
  const bays = run.bays ?? Math.max(1, Math.round(W / kind.bay));
  const bw = W / bays;
  const isM = spec.style === 'moderne';
  const ww = Math.min(kind.window, bw * (isM ? 0.6 : 0.52));
  const isH = spec.style === 'haussmann';
  const D = B.dry;
  const F = B.fine;
  D.push(f.m);
  F.push(f.m);
  B.lace.push(f.m);

  /* ground floor: shops, doors, rusticated stone */
  const shopAt = (i: number) => run.shops.find((s) => i >= s.from && i <= s.to);
  const g = ctx.ground;
  // the stone between and above the openings
  const openings: Array<[number, number]> = [];
  // a window at street level is narrower than its bay, and sits on a stone apron
  const sill = 0.95;
  const groundWin = (s: Shop): [number, number] => {
    const cu = ((s.from + s.to + 1) / 2) * bw;
    const w = Math.min(1.3, bw * 0.48);
    return [cu - w / 2, cu + w / 2];
  };
  for (const s of run.shops) {
    if (s.kind === 'wall') continue;
    if (s.kind === 'window') {
      openings.push(groundWin(s));
      continue;
    }
    const u0 = s.from * bw + 0.35;
    const u1 = (s.to + 1) * bw - 0.35;
    openings.push([u0, u1]);
  }
  openings.sort((x, y) => x[0] - y[0]);
  const openTop = g - 1.15;
  let cursor = 0;
  for (const [u0, u1] of openings) {
    if (u0 > cursor) D.box((cursor + u0) / 2, (g - 0.4) / 2 - 0.2 + 0.2, -0.13, u0 - cursor, g + 0.4, 0.26, ctx.stoneBase, { nz: false });
    cursor = u1;
  }
  if (cursor < W) D.box((cursor + W) / 2, (g - 0.4) / 2, -0.13, W - cursor, g + 0.4, 0.26, ctx.stoneBase, { nz: false });
  for (const [u0, u1] of openings) {
    D.box((u0 + u1) / 2, (openTop + g) / 2, -0.13, u1 - u0, g - openTop, 0.26, ctx.stoneBase, { nz: false });
  }
  // a plinth of darker stone, and the band over the ground floor
  D.box(W / 2, 0.25, 0.02, W, 0.5, 0.06, { color: mix(spec.wall, INKS.ink, 0.16), id: ctx.wallId }, { nz: false });
  D.sweep(new Vector3(0, g - 0.05, 0), new Vector3(W, g - 0.05, 0), [[0, 0], [0.12, 0.04], [0.16, 0.16], [0.08, 0.22], [0, 0.24]], { color: mix(spec.wall, INKS.paper, 0.25), id: nextId() }, { caps: true });

  for (const s of run.shops) {
    if (s.kind === 'wall' || s.kind === 'none') continue;
    if (s.kind === 'window') {
      const [u0, u1] = groundWin(s);
      D.box((u0 + u1) / 2, sill / 2, -0.13, u1 - u0, sill, 0.26, ctx.stoneBase, { nz: false });
      streetWindow(B, u0, u1, sill, openTop - 0.25);
      continue;
    }
    const u0 = s.from * bw + 0.35;
    const u1 = (s.to + 1) * bw - 0.35;
    if (s.kind === 'door') {
      porch(B, u0, u1, openTop, s.color ?? INKS.green);
      if (s.number) {
        const [x, z] = worldOf(f, (u0 + u1) / 2, 0.02);
        B.signs.push({ key: `numero:${s.number}`, center: new Vector3(x, openTop + 0.5, z), normal: f.n.clone(), width: 0.3, height: 0.24, density: 300, draw: numberArt(s.number) });
      }
    } else shopFront(B, f, u0, u1, openTop, s);
  }

  /* the storeys */
  let y = g;
  ctx.heights.forEach((h, k) => {
    const storey = k + 1;
    const y0 = y;
    const y1 = y + h;
    const isBalcony = (spec.balconies ?? []).includes(storey);
    const wy0 = y0 + (isH || storey < ctx.heights.length ? 0.08 : 0.5);
    const wy1 = y0 + h * (storey === 1 && isH ? 0.78 : 0.72);
    // piers, aprons and lintels: one stone, one id
    for (let i = 0; i <= bays; i++) {
      const left = i === 0 ? 0 : (i - 0.5) * bw + ww / 2;
      const right = i === bays ? W : (i + 0.5) * bw - ww / 2;
      if (right > left) D.box((left + right) / 2, (y0 + y1) / 2, -0.13, right - left, h, 0.26, ctx.wall, { nz: false, py: false, ny: false });
    }
    for (let i = 0; i < bays; i++) {
      const cu = (i + 0.5) * bw;
      if (wy0 > y0) D.box(cu, (y0 + wy0) / 2, -0.13, ww, wy0 - y0, 0.26, ctx.wall, { nz: false, ny: false });
      D.box(cu, (wy1 + y1) / 2, -0.13, ww, y1 - wy1, 0.26, ctx.wall, { nz: false, py: false });
      const key = `${storey}:${i}`;
      const shut = (spec.shut ?? []).includes(`${ri}:${key}`);
      const forced = (spec.forceLit ?? []).includes(`${ri}:${key}`);
      const lit = forced || (!shut && R.chance(spec.lit ?? 0.3));
      windowIn(B, cu, wy0, wy1, ww, { lit, shut, isH, storey, balcony: isBalcony, dim: forced, modern: isM });
      const [wx, wz] = worldOf(f, cu, -0.2);
      ctx.windows.set(`${ri}:${key}`, {
        center: new Vector3(wx, (wy0 + wy1) / 2, wz),
        normal: f.n.clone(),
        width: ww,
        height: wy1 - wy0,
      });
    }
    // the band at the floor line, and the balcony
    if (k > 0) D.sweep(new Vector3(0, y0 - 0.06, 0), new Vector3(W, y0 - 0.06, 0), [[0, 0], [0.07, 0.03], [0.08, 0.1], [0, 0.12]], { color: mix(spec.wall, INKS.paper, 0.2), id: ctx.wallId }, { caps: true });
    if (isBalcony) balcony(B, 0.12, W - 0.12, y0, bw, bays);
    y = y1;
  });

  /* the cornice */
  const c = ctx.cornice;
  const corniceProfile: Array<[number, number]> = isM
    ? [[0, 0], [0.05, 0], [0.05, 0.22], [0, 0.22]]
    : isH
      ? [[0, 0], [0.1, 0.06], [0.14, 0.18], [0.3, 0.24], [0.42, 0.34], [0.5, 0.44], [0.5, 0.52], [0, 0.56]]
      : [[0, 0], [0.12, 0.08], [0.22, 0.2], [0.26, 0.3], [0, 0.34]];
  D.sweep(new Vector3(-0.02, c, 0), new Vector3(W + 0.02, c, 0), corniceProfile, { color: mix(spec.wall, INKS.paper, 0.3), id: nextId() }, { caps: true });
  // brackets (modillions) under the Haussmann cornice
  if (isH) {
    const n = Math.round(W / 0.75);
    const mod = { color: mix(spec.wall, INKS.paper, 0.2), id: nextId() };
    for (let i = 0; i < n; i++) F.box((i + 0.5) * (W / n), c - 0.12, 0.12, 0.12, 0.2, 0.22, mod, { nz: false });
  }

  D.pop();
  F.pop();
  B.lace.pop();
}

/**
 * A façade seen from far off: one wall from the pavement to the cornice, its windows and shop
 * fronts painted flat on it (lit ones still glow at night), balcony slabs and the cornice. About a
 * tenth of a near façade's triangles, and the skyline reads the same.
 */
function facadeFar(B: Build, spec: BuildingSpec, run: Run, ctx: FacadeCtx) {
  const R = B.rand;
  const kind = STOREYS[spec.style];
  const f = frameOf(run.a, run.b);
  const W = f.len;
  const bays = run.bays ?? Math.max(1, Math.round(W / kind.bay));
  const bw = W / bays;
  const isM = spec.style === 'moderne';
  const ww = Math.min(kind.window, bw * (isM ? 0.6 : 0.52));
  const D = B.dry;
  const g = ctx.ground;
  const face = (u0: number, y0: number, u1: number, y1: number, z: number, paint: Paint, id?: number) =>
    D.quadXYZ([u0, y0, z, u1, y0, z, u1, y1, z, u0, y1, z], paint, id);
  D.push(f.m);
  face(0, g, W, ctx.cornice, 0, ctx.wall, ctx.wallId);
  face(0, -0.4, W, g, 0, ctx.stoneBase, ctx.wallId);
  // the shops and doors as their openings, the street windows as panes
  const openTop = g - 1.15;
  for (const s of run.shops) {
    if (s.kind === 'wall' || s.kind === 'none') continue;
    const u0 = s.from * bw + 0.35;
    const u1 = (s.to + 1) * bw - 0.35;
    if (s.kind === 'window') {
      const cu = (u0 + u1) / 2;
      const w = Math.min(1.3, bw * 0.48);
      face(cu - w / 2, 0.95, cu + w / 2, openTop - 0.25, 0.04, { color: TONES.pane, id: nextId(), wet: 0.6 });
    } else if (s.kind === 'door') face(u0, 0, u1, openTop, 0.04, { color: s.color ?? INKS.green, id: nextId() });
    else face(u0, 0, u1, openTop, 0.04, { color: s.lit ? TONES.paneLit : mix(TONES.pane, INKS.ink, 0.2), glow: s.lit ? 0.6 : 0, id: nextId() });
  }
  let y = g;
  ctx.heights.forEach((h, k) => {
    const storey = k + 1;
    const wy0 = y + (storey < ctx.heights.length ? 0.08 : 0.5);
    const wy1 = y + h * 0.72;
    for (let i = 0; i < bays; i++) {
      const cu = (i + 0.5) * bw;
      const lit = R.chance(spec.lit ?? 0.3);
      face(cu - ww / 2, wy0, cu + ww / 2, wy1, 0.04, lit ? { color: TONES.paneLit, glow: 1, id: nextId() } : { color: TONES.pane, id: nextId(), wet: 0.6 });
    }
    if ((spec.balconies ?? []).indexOf(storey) >= 0) D.box(W / 2, y - 0.08, 0.36, W - 0.24, 0.16, 0.72, { color: mix(TONES.stone, INKS.paper, 0.2), id: nextId() });
    y += h;
  });
  // the cornice, deep enough to close the top of the wall over the body behind it
  D.box(W / 2, ctx.cornice + 0.2, 0, W + 0.04, 0.4, 0.6, { color: mix(spec.wall, INKS.paper, 0.3), id: nextId() }, { nz: false });
  D.pop();
}

interface WindowOpts {
  lit: boolean;
  shut: boolean;
  isH: boolean;
  storey: number;
  balcony: boolean;
  /** the easel window: lit, but low */
  dim?: boolean;
  /** a plain opening of the housing estates: no surround, no shutters */
  modern?: boolean;
}

/** One window in its reveal: pane, frame, shutters, surround, sill and guard. */
function windowIn(B: Build, cu: number, y0: number, y1: number, w: number, o: WindowOpts) {
  const D = B.dry;
  const F = B.fine;
  const R = B.rand;
  const h = y1 - y0;
  const paneId = nextId();
  if (o.shut) {
    // persiennes closed: two leaves of slats in the opening
    const slats: Paint = { color: TONES.shutter, pattern: PATTERN.ribs, id: nextId() };
    D.box(cu - w / 4, (y0 + y1) / 2, -0.12, w / 2 - 0.02, h, 0.04, slats, { nz: false });
    D.box(cu + w / 4, (y0 + y1) / 2, -0.12, w / 2 - 0.02, h, 0.04, slats, { nz: false });
  } else {
    const pane: Paint = o.lit
      ? { color: o.dim ? mix(TONES.paneLit, INKS.ochre, 0.35) : TONES.paneLit, glow: o.dim ? 0.55 : 1, id: paneId }
      : { color: TONES.pane, id: paneId, wet: 0.6 };
    D.quadXYZ([cu - w / 2, y0, -0.2, cu + w / 2, y0, -0.2, cu + w / 2, y1, -0.2, cu - w / 2, y1, -0.2], pane, paneId);
    if (o.lit && !o.dim) {
      // a curtain drawn to one side, lit from behind
      const side = R.chance(0.5) ? -1 : 1;
      const cw = w * R.range(0.22, 0.4);
      const cx = cu + side * (w / 2 - cw / 2);
      F.box(cx, (y0 + y1) / 2 + 0.05, -0.17, cw, h - 0.1, 0.02, { color: mix(TONES.curtain, INKS.sunflower, 0.25), glow: 0.7, id: nextId() }, { nz: false });
    }
    // frame: the meeting stiles and a transom under the fanlight
    const frame: Paint = { color: mix(INKS.card, INKS.ink, 0.12), id: nextId() };
    F.box(cu, (y0 + y1) / 2, -0.17, 0.06, h, 0.05, frame, { nz: false });
    F.box(cu, y1 - h * 0.2, -0.17, w, 0.06, 0.05, frame, { nz: false });
    // folded shutters in the reveal
    if (!o.modern && (!o.isH || R.chance(0.6))) {
      const sh: Paint = { color: TONES.shutter, id: nextId() };
      F.box(cu - w / 2 + 0.05, (y0 + y1) / 2, -0.1, 0.08, h - 0.04, 0.17, sh, { nz: false });
      F.box(cu + w / 2 - 0.05, (y0 + y1) / 2, -0.1, 0.08, h - 0.04, 0.17, sh, { nz: false });
    }
  }
  // the surround: a raised stone frame, a cornice over the first floor's windows
  const sur: Paint = { color: mix(TONES.stoneLight, INKS.ochre, 0.05), id: nextId() };
  if (o.modern) {
    F.box(cu, y0 - 0.02, 0.02, w + 0.06, 0.04, 0.08, sur, { nz: false });
    if (!o.shut) F.box(cu, y0 + 0.5, 0.02, w, 0.04, 0.04, { color: TONES.iron, id: nextId() }, { nz: false });
    return;
  }
  if (o.isH) {
    F.box(cu - w / 2 - 0.07, (y0 + y1) / 2, 0.02, 0.14, h, 0.04, sur, { nz: false });
    F.box(cu + w / 2 + 0.07, (y0 + y1) / 2, 0.02, 0.14, h, 0.04, sur, { nz: false });
    F.box(cu, y1 + 0.07, 0.02, w + 0.28, 0.14, 0.04, sur, { nz: false });
    if (o.storey === 1 || o.storey === 2) {
      F.box(cu, y1 + 0.28, 0.08, w + 0.5, 0.1, 0.16, sur, { nz: false });
      F.box(cu, y1 + 0.18, 0.06, 0.18, 0.2, 0.08, sur, { nz: false });
    }
  } else {
    F.box(cu, y1 + 0.06, 0.015, w + 0.16, 0.12, 0.03, sur, { nz: false });
  }
  // sill
  F.box(cu, y0 - 0.03, 0.03, w + 0.2, 0.06, 0.14, sur, { nz: false });
  // a guard across the French window, unless a balcony runs in front
  if (!o.balcony && !o.shut && (o.isH || o.storey > 0)) {
    B.lace.panel(new Vector3(cu - w / 2, y0 + 0.04, 0.03), new Vector3(cu + w / 2, y0 + 0.04, 0.03), 0.95, LACE.guard, nextId());
  }
}

/** A continuous balcony: slab, consoles, and the iron lace along its edge. */
function balcony(B: Build, u0: number, u1: number, y: number, bw: number, bays: number) {
  const D = B.dry;
  const slab: Paint = { color: mix(TONES.stone, INKS.paper, 0.2), id: nextId() };
  const out = 0.72;
  D.box((u0 + u1) / 2, y - 0.08, out / 2, u1 - u0, 0.16, out, slab);
  const con: Paint = { color: mix(TONES.stone, INKS.ink, 0.06), id: nextId() };
  for (let i = 0; i <= bays; i++) {
    const cu = Math.min(Math.max(i * bw, u0 + 0.15), u1 - 0.15);
    B.fine.box(cu, y - 0.34, 0.25, 0.16, 0.36, 0.5, con, { nz: false });
  }
  const id = nextId();
  B.lace.panel(new Vector3(u0, y, out - 0.03), new Vector3(u1, y, out - 0.03), 1.0, LACE.balcony, id);
  B.lace.panel(new Vector3(u0 + 0.02, y, 0), new Vector3(u0 + 0.02, y, out - 0.03), 1.0, LACE.balcony, id);
  B.lace.panel(new Vector3(u1 - 0.02, y, out - 0.03), new Vector3(u1 - 0.02, y, 0), 1.0, LACE.balcony, id);
}

/** A dormer on the mansard's street slope. */
function dormer(B: Build, cu: number, base: number, rise: number, set: number, lit: boolean, style: BuildingSpec['style']) {
  const D = B.dry;
  const w = style === 'haussmann' ? 1.25 : 1.05;
  const h = 1.9;
  const front = -0.35;
  const id = nextId();
  const cheek: Paint = { color: mix(TONES.stoneLight, INKS.ochre, 0.06), id };
  // the cheeks and front run back into the slope
  const back = -set * 0.95;
  D.box(cu, base + h / 2 + 0.1, (front + back) / 2, w + 0.3, h, front - back, cheek, { nz: false });
  const paneId = nextId();
  const pane: Paint = lit ? { color: TONES.paneLit, glow: 1, id: paneId } : { color: TONES.pane, id: paneId, wet: 0.5 };
  D.quadXYZ([cu - w / 2 + 0.12, base + 0.35, front + 0.012, cu + w / 2 - 0.12, base + 0.35, front + 0.012, cu + w / 2 - 0.12, base + h - 0.15, front + 0.012, cu - w / 2 + 0.12, base + h - 0.15, front + 0.012], pane, paneId);
  D.box(cu, base + (h + 0.2) / 2, front + 0.03, 0.05, h - 0.5, 0.03, { color: INKS.card, id: nextId() }, { nz: false });
  // a little gable of zinc
  const z0 = front + 0.12;
  const z1 = back;
  const yb = base + h + 0.1;
  const half = (w + 0.42) / 2;
  const peak = yb + 0.55;
  const roof: Paint = { color: TONES.zincDark, id: nextId() };
  D.quadXYZ([cu - half, yb, z0, cu, peak, z0, cu, peak, z1, cu - half, yb, z1], roof);
  D.quadXYZ([cu, peak, z0, cu + half, yb, z0, cu + half, yb, z1, cu, peak, z1], roof);
  D.tri(new Vector3(cu - half + 0.1, yb, z0 - 0.02), new Vector3(cu + half - 0.1, yb, z0 - 0.02), new Vector3(cu, peak - 0.06, z0 - 0.02), cheek, id);
  void rise;
}

/** A window at street level: deep in its reveal, behind a grille, curtained for the passers-by. */
function streetWindow(B: Build, u0: number, u1: number, y0: number, y1: number) {
  const D = B.dry;
  const F = B.fine;
  const w = u1 - u0;
  const cu = (u0 + u1) / 2;
  const paneId = nextId();
  D.quadXYZ([u0, y0, -0.22, u1, y0, -0.22, u1, y1, -0.22, u0, y1, -0.22], { color: mix(TONES.pane, INKS.cobalt, 0.15), wet: 0.6, id: paneId }, paneId);
  // a net curtain over the lower half
  F.box(cu, y0 + (y1 - y0) * 0.3, -0.2, w - 0.12, (y1 - y0) * 0.55, 0.01, { color: mix(TONES.curtain, INKS.ink, 0.08), id: nextId() }, { nz: false });
  const iron: Paint = { color: TONES.iron, id: nextId() };
  const bars = Math.max(3, Math.round(w / 0.14));
  for (let i = 1; i < bars; i++) F.box(u0 + (i * w) / bars, (y0 + y1) / 2, -0.02, 0.025, y1 - y0, 0.025, iron, { nz: false });
  F.box(cu, y0 + 0.1, -0.02, w, 0.04, 0.04, iron, { nz: false });
  F.box(cu, y1 - 0.1, -0.02, w, 0.04, 0.04, iron, { nz: false });
  F.box(cu, y0 - 0.03, 0.03, w + 0.16, 0.06, 0.12, { color: mix(TONES.stoneLight, INKS.ochre, 0.05), id: nextId() }, { nz: false });
}

/** A building's carriage door: two leaves of painted wood under a fanlight. */
function porch(B: Build, u0: number, u1: number, top: number, color: Hex) {
  const D = B.dry;
  const w = u1 - u0;
  const cu = (u0 + u1) / 2;
  const id = nextId();
  const wood: Paint = { color, id };
  const dark: Paint = { color: mix(color, INKS.ink, 0.35), id };
  D.box(cu, top / 2, -0.18, w, top, 0.06, wood, { nz: false });
  // panels and the meeting stile
  D.box(cu, top / 2, -0.14, 0.05, top, 0.03, dark, { nz: false });
  for (const s of [-1, 1]) {
    D.box(cu + (s * w) / 4, top * 0.3, -0.135, w / 2 - 0.3, top * 0.34, 0.025, dark, { nz: false });
    D.box(cu + (s * w) / 4, top * 0.68, -0.135, w / 2 - 0.3, top * 0.3, 0.025, dark, { nz: false });
  }
  // brass knob
  D.ball(cu + 0.12, top * 0.48, -0.1, 0.05, 0.05, 0.05, { color: TONES.brass, wet: 0.6, id: nextId() }, 0);
  D.box(cu, top + 0.02, -0.2, w + 0.1, 0.06, 0.12, { color: mix(TONES.stoneLight, INKS.ochre, 0.05), id: nextId() }, { nz: false });
}

/** A shop front: painted frame, display windows, a door, the fascia, maybe an awning. */
function shopFront(B: Build, f: Frame, u0: number, u1: number, top: number, s: Shop) {
  const D = B.dry;
  const color = s.color ?? INKS.green;
  const id = nextId();
  const paint: Paint = { color, id };
  const w = u1 - u0;
  const cu = (u0 + u1) / 2;
  if (s.kind === 'shutter') {
    // closed for the night: a roller shutter, ribbed, a little rust
    D.box(cu, top / 2, -0.06, w, top, 0.05, { color: mix(TONES.curb, INKS.cobalt, 0.12), pattern: PATTERN.ribs, id: nextId() }, { nz: false });
    D.box(cu, top - 0.18, 0.0, w + 0.1, 0.36, 0.12, paint, { nz: false });
  } else {
    // pilasters and the stall riser
    D.box(u0 + 0.1, top / 2, -0.02, 0.2, top, 0.12, paint, { nz: false });
    D.box(u1 - 0.1, top / 2, -0.02, 0.2, top, 0.12, paint, { nz: false });
    D.box(cu, 0.35, -0.04, w, 0.7, 0.1, paint, { nz: false });
    // the glass: lit or dark, with shelves showing through when lit
    const paneId = nextId();
    const glow = s.lit ? 0.95 : 0;
    const glassTone = s.lit ? mix(TONES.paneLit, INKS.card, 0.25) : mix(TONES.pane, INKS.cobalt, 0.2);
    D.quadXYZ([u0 + 0.2, 0.7, -0.12, u1 - 0.2, 0.7, -0.12, u1 - 0.2, top - 0.35, -0.12, u0 + 0.2, top - 0.35, -0.12], { color: glassTone, glow, wet: s.lit ? 0 : 0.6, id: paneId }, paneId);
    if (s.lit) {
      const shelf: Paint = { color: mix(color, INKS.ink, 0.4), id: nextId() };
      for (let k = 1; k <= 3; k++) D.box(cu, 0.7 + k * 0.6, -0.15, w - 0.6, 0.05, 0.04, shelf, { nz: false });
      const [lx, lz] = worldOf(f, cu, 1.4);
      B.lamps.push({ pos: new Vector3(lx, 1.8, lz), color: rgb(mix(INKS.sunflower, INKS.card, 0.35)), power: 0.75, range: 5.5, glint: false });
    }
    // glazing bars and the door's frame
    const bar: Paint = { color, id };
    const n = Math.max(1, Math.round(w / 1.6));
    for (let k = 1; k < n; k++) D.box(u0 + (k * w) / n, (0.7 + top - 0.35) / 2, -0.1, 0.07, top - 1.05, 0.06, bar, { nz: false });
    D.box(cu, top - 0.35 - 0.04, -0.1, w - 0.3, 0.08, 0.06, bar, { nz: false });
  }
  // the fascia: painted board with the name
  D.box(cu, top + 0.45, 0.02, w + 0.3, 0.9, 0.14, paint, { nz: false });
  if (s.name) {
    const [x, z] = worldOf(f, cu, 0.1);
    // the key says everything the lettering depends on, so two fronts alike print it once
    const width = Math.round(Math.min(w, Math.max(2.4, s.name.length * 0.32)) * 10) / 10;
    B.signs.push({
      key: `fascia:${s.name}:${s.trade ?? ''}:${isDark(color) ? 'light' : 'dark'}`,
      center: new Vector3(x, top + 0.45, z),
      normal: f.n.clone(),
      width,
      height: 0.72,
      draw: (ctx, cw, ch) => fasciaArt(ctx, cw, ch, s.name ?? '', s.trade, color),
    });
  }
  if (s.awning) awning(B, u0 - 0.1, u1 + 0.1, top + 0.02, s.awning);
}

/** A canvas awning, sloping out over the pavement, with a scalloped valance. */
export function awning(B: Build, u0: number, u1: number, y: number, color: Hex) {
  const D = B.dry;
  const out = 1.7;
  const drop = 0.75;
  const id = nextId();
  const cloth: Paint = { color, id };
  const stripe: Paint = { color: mix(color, INKS.paper, 0.75), id };
  const n = Math.max(2, Math.round((u1 - u0) / 0.55));
  for (let i = 0; i < n; i++) {
    const a = u0 + ((u1 - u0) * i) / n;
    const b = u0 + ((u1 - u0) * (i + 1)) / n;
    const p = i % 2 === 0 ? cloth : stripe;
    D.quadXYZ([a, y, 0.05, b, y, 0.05, b, y - drop, out, a, y - drop, out], p, id);
    // the valance: a strip with a scallop
    D.quadXYZ([a, y - drop, out, b, y - drop, out, b, y - drop - 0.22, out, a, y - drop - 0.22, out], p, id);
    D.tri(new Vector3(a, y - drop - 0.22, out), new Vector3(b, y - drop - 0.22, out), new Vector3((a + b) / 2, y - drop - 0.36, out), p, id);
  }
  // the arms
  const arm: Paint = { color: TONES.iron, id: nextId() };
  for (const u of [u0 + 0.1, u1 - 0.1]) {
    D.bar(new Vector3(u, y - 1.3, 0.02), new Vector3(u, y - drop, out - 0.05), 0.04, arm);
  }
}

function fasciaArt(ctx: CanvasRenderingContext2D, w: number, h: number, name: string, trade: string | undefined, color: Hex) {
  ctx.clearRect(0, 0, w, h);
  const light = isDark(color);
  ctx.fillStyle = light ? '#f8f3e8' : '#14110d';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const size = Math.round(h * (trade ? 0.5 : 0.62));
  ctx.font = `italic 500 ${size}px AtelierSerif, 'EB Garamond', Georgia, serif`;
  fitText(ctx, name, w * 0.94, size, `italic 500 {s}px AtelierSerif, 'EB Garamond', Georgia, serif`);
  ctx.fillText(name, w / 2, trade ? h * 0.4 : h * 0.54);
  if (trade) {
    const ts = Math.round(h * 0.22);
    ctx.font = `600 ${ts}px AtelierSans, 'Instrument Sans', system-ui, sans-serif`;
    ctx.fillText(trade, w / 2, h * 0.8);
  }
}

/** A house number: white on the blue enamel, a white rule round it, as on every Paris door. */
export function numberArt(n: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    const r = h * 0.14;
    ctx.fillStyle = '#1d3a8a';
    ctx.beginPath();
    ctx.moveTo(r, 0);
    ctx.arcTo(w, 0, w, h, r);
    ctx.arcTo(w, h, 0, h, r);
    ctx.arcTo(0, h, 0, 0, r);
    ctx.arcTo(0, 0, w, 0, r);
    ctx.fill();
    ctx.strokeStyle = '#f8f3e8';
    ctx.lineWidth = Math.max(1.5, h * 0.05);
    ctx.strokeRect(h * 0.1, h * 0.1, w - h * 0.2, h - h * 0.2);
    ctx.fillStyle = '#f8f3e8';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const size = fitText(ctx, n, w * 0.74, Math.round(h * 0.62), "700 {s}px AtelierSans, 'Instrument Sans', system-ui, sans-serif");
    ctx.font = `700 ${size}px AtelierSans, 'Instrument Sans', system-ui, sans-serif`;
    ctx.fillText(n, w / 2, h * 0.54);
  };
}

export function fitText(ctx: CanvasRenderingContext2D, text: string, maxW: number, size: number, template: string) {
  let s = size;
  ctx.font = template.replace('{s}', String(s));
  while (s > 8 && ctx.measureText(text).width > maxW) {
    s -= 2;
    ctx.font = template.replace('{s}', String(s));
  }
  return s;
}

export function isDark(h: Hex) {
  const [r, g, b] = rgb(h);
  return 0.299 * r + 0.587 * g + 0.114 * b < 0.55;
}

/* ------------------------------------------------------------------------------------------ */
/* the street's furniture                                                                     */
/* ------------------------------------------------------------------------------------------ */

const IRON = TONES.iron;

/** A Paris quay lamp: fluted cast-iron post, a glass lantern, a crown. */
export function quayLamp(B: Build, x: number, z: number, y = KERB, lit = true) {
  const D = B.dry;
  const id = nextId();
  const iron: Paint = { color: IRON, id };
  D.lathe(x, y, z, [[0.24, 0], [0.23, 0.18], [0.15, 0.3], [0.12, 0.55], [0.09, 0.62], [0.085, 1.4], [0.065, 3.1], [0.1, 3.22], [0.06, 3.36]], 8, iron);
  // the lantern: an upturned six-sided glass, lit
  const glass: Paint = { color: lit ? mix(INKS.sunflower, INKS.card, 0.45) : mix(INKS.cobalt, INKS.paper, 0.55), glow: lit ? 1 : 0, id: nextId() };
  D.lathe(x, y, z, [[0.1, 3.36], [0.26, 3.92], [0.23, 3.98]], 6, glass, { flat: true });
  D.lathe(x, y, z, [[0.3, 3.96], [0.27, 4.04], [0.08, 4.3], [0.04, 4.42], [0.0, 4.5]], 6, iron, { flat: true });
  D.ball(x, y + 4.5, z, 0.05, 0.07, 0.05, iron, 0);
  B.blocks.push(circle(x, z, 0.35));
  if (lit) B.lamps.push({ pos: new Vector3(x, y + 3.7, z), color: rgb(mix(INKS.sunflower, INKS.card, 0.4)), power: 1.0, range: 11, glint: true });
}

/** A wall lantern on a bracket (the narrow streets). */
export function wallLamp(B: Build, f: Frame, u: number, y: number, lit = true) {
  const D = B.dry;
  D.push(f.m);
  const iron: Paint = { color: IRON, id: nextId() };
  D.bar(new Vector3(u, y + 0.4, 0), new Vector3(u, y + 0.25, 0.7), 0.05, iron);
  D.bar(new Vector3(u, y, 0), new Vector3(u, y + 0.25, 0.7), 0.04, iron);
  D.lathe(u, y - 0.25, 0.75, [[0.06, 0], [0.16, 0.38], [0.14, 0.42]], 6, { color: lit ? mix(INKS.sunflower, INKS.card, 0.45) : TONES.glass, glow: lit ? 1 : 0, id: nextId() }, { flat: true });
  D.lathe(u, y - 0.25, 0.75, [[0.19, 0.4], [0.03, 0.62]], 6, iron, { flat: true });
  D.pop();
  if (lit) {
    const [x, z] = worldOf(f, u, 0.75);
    B.lamps.push({ pos: new Vector3(x, y, z), color: rgb(mix(INKS.sunflower, INKS.card, 0.4)), power: 0.85, range: 8.5, glint: true });
  }
}

/**
 * A plane tree in November: mottled trunk, three limbs, a crown of ochre and sunflower clumps.
 * A `far` one (seen only over the rooftops) has coarser clumps and no twigs or grate.
 */
export function planeTree(B: Build, x: number, z: number, y = KERB, scale = 1, far = false) {
  const D = B.dry;
  const R = B.rand;
  const trunkId = nextId();
  const bark: Paint = { color: TONES.bark, id: trunkId, pattern: PATTERN.mottle };
  const trunkH = 3.4 * scale;
  D.lathe(x, y - 0.1, z, [[0.3 * scale, 0], [0.24 * scale, 0.4], [0.2 * scale, trunkH * 0.6], [0.17 * scale, trunkH]], 7, bark);
  // the grate round its foot
  if (!far) D.box(x, y + 0.005, z, 1.5, 0.02, 1.5, { color: mix(IRON, INKS.ink, 0.3), id: nextId() }, { ny: false });
  const limbs = 3 + R.int(0, 1);
  const crown: Array<[number, number, number]> = [];
  for (let i = 0; i < limbs; i++) {
    const a = (i / limbs) * Math.PI * 2 + R.range(-0.4, 0.4);
    const reach = R.range(1.2, 2.2) * scale;
    const top = new Vector3(x + Math.cos(a) * reach, y + trunkH + R.range(1.6, 2.6) * scale, z + Math.sin(a) * reach);
    D.bar(new Vector3(x, y + trunkH - 0.2, z), top, 0.17 * scale, bark, trunkId);
    crown.push([top.x, top.y, top.z]);
    // a twig or two past the leaves, bare already
    if (!far) D.bar(top, top.clone().add(new Vector3(Math.cos(a) * 0.9, 1.1, Math.sin(a) * 0.9).multiplyScalar(scale)), 0.06, { color: TONES.barkDark, id: nextId() });
  }
  const leaves = [TONES.leafSun, TONES.leafOchre, TONES.leafRust, TONES.leafOchre, TONES.leafSun];
  const clumps = 7 + R.int(0, 3);
  const leafId = nextId();
  for (let i = 0; i < clumps; i++) {
    const c = crown[i % crown.length];
    const r = R.range(1.1, 1.8) * scale;
    const cx = c[0] + R.range(-1.4, 1.4) * scale;
    const cz = c[2] + R.range(-1.4, 1.4) * scale;
    const cy = c[1] + R.range(-0.6, 1.3) * scale;
    const tone = leaves[(i + R.int(0, 4)) % leaves.length];
    D.ball(cx, cy, cz, r, r * 0.78, r, { color: tone, id: leafId + (i % 2) }, far ? 0 : 1, { smooth: true });
  }
  B.blocks.push(circle(x, z, 0.45));
  return { crownTop: y + trunkH + 4 * scale };
}

/** A green bench on cast-iron feet, facing `rot` (radians about y). */
export function bench(B: Build, x: number, z: number, rot: number, y = KERB) {
  const D = B.dry;
  D.at(x, y, z, rot, () => {
    const iron: Paint = { color: IRON, id: nextId() };
    const wood: Paint = { color: mix(INKS.green, INKS.paper, 0.15), id: nextId() };
    for (const sx of [-0.8, 0.8]) {
      D.box(sx, 0.22, 0, 0.06, 0.44, 0.5, iron);
      D.box(sx, 0.62, -0.25, 0.06, 0.5, 0.06, iron);
    }
    for (let i = 0; i < 4; i++) D.box(0, 0.46, 0.18 - i * 0.12, 1.8, 0.04, 0.09, wood);
    for (let i = 0; i < 3; i++) D.box(0, 0.62 + i * 0.13, -0.27, 1.8, 0.09, 0.03, wood);
  });
  B.blocks.push(boxShape(x, z, 1.9, 0.6, rot));
}

/** A Morris column: dark green drum, posters, a dome with a crown. */
export function morrisColumn(B: Build, x: number, z: number, posters: Array<{ key: string; draw: SignSpec['draw'] }>, y = KERB) {
  const D = B.dry;
  const green: Paint = { color: mix(INKS.green, INKS.ink, 0.35), id: nextId() };
  D.lathe(x, y, z, [[0.78, 0], [0.78, 0.25], [0.68, 0.35], [0.68, 3.0], [0.8, 3.1], [0.82, 3.3], [0.74, 3.36], [0.7, 3.5], [0.52, 3.9], [0.24, 4.15], [0.1, 4.3], [0, 4.4]], 12, green);
  D.ball(x, y + 4.45, z, 0.1, 0.12, 0.1, green, 0);
  posters.forEach((p, i) => {
    const a = (i / posters.length) * Math.PI * 2 + 0.3;
    const n = new Vector3(Math.cos(a), 0, Math.sin(a));
    B.signs.push({
      key: p.key,
      center: new Vector3(x + n.x * 0.7, y + 1.75, z + n.z * 0.7),
      normal: n,
      width: 0.62,
      height: 1.6,
      density: 220,
      draw: p.draw,
    });
  });
  B.blocks.push(circle(x, z, 0.9));
}

/** A bollard of the Paris kind: a slim post with a ring. */
export function bollard(B: Build, x: number, z: number, y = KERB) {
  const p: Paint = { color: mix(INKS.green, INKS.ink, 0.5), id: nextId() };
  B.dry.lathe(x, y, z, [[0.07, 0], [0.065, 0.7], [0.08, 0.74], [0.08, 0.8], [0.05, 0.86], [0, 0.9]], 6, p, { flat: true });
}

/** A bistro table and two chairs tipped against it for the night. */
export function terraceSet(B: Build, x: number, z: number, rot: number, y = KERB, tipped = true) {
  const D = B.dry;
  D.at(x, y, z, rot, () => {
    const iron: Paint = { color: mix(IRON, INKS.ink, 0.2), id: nextId() };
    const top: Paint = { color: TONES.marble, id: nextId(), wet: 0.5 };
    D.cylinder(0, 0, 0, 0.22, 0.04, 0.06, 6, iron, { flat: true });
    D.cylinder(0, 0.06, 0, 0.025, 0.025, 0.64, 5, iron, { flat: true });
    D.cylinder(0, 0.7, 0, 0.3, 0.3, 0.035, 12, top);
    for (const s of [-1, 1]) chair(B, s * 0.55, 0, s > 0 ? Math.PI / 2 : -Math.PI / 2, tipped);
  });
  B.blocks.push(circle(x, z, 0.9));
}

/** A bentwood chair (rattan seat, the café's), optionally tipped forward onto its table. */
export function chair(B: Build, x: number, z: number, rot: number, tipped = false, y = 0) {
  const D = B.dry;
  const m = new Matrix4().makeRotationY(rot).setPosition(x, y, z);
  if (tipped) m.multiply(new Matrix4().makeRotationX(0.32));
  D.push(m);
  const wood: Paint = { color: TONES.wood, id: nextId() };
  const seat: Paint = { color: mix(INKS.ochre, INKS.paper, 0.35), id: nextId(), pattern: PATTERN.tiles };
  for (const [lx, lz] of [[-0.18, -0.18], [0.18, -0.18], [-0.17, 0.18], [0.17, 0.18]] as Array<[number, number]>) {
    D.bar(new Vector3(lx * 1.15, 0, lz * 1.15), new Vector3(lx, 0.45, lz), 0.03, wood);
  }
  D.cylinder(0, 0.45, 0, 0.22, 0.22, 0.035, 10, seat);
  // the back: a bent hoop
  D.bar(new Vector3(-0.17, 0.45, -0.18), new Vector3(-0.15, 0.9, -0.22), 0.03, wood);
  D.bar(new Vector3(0.17, 0.45, -0.18), new Vector3(0.15, 0.9, -0.22), 0.03, wood);
  D.bar(new Vector3(-0.15, 0.9, -0.22), new Vector3(0.15, 0.9, -0.22), 0.035, wood);
  D.bar(new Vector3(-0.15, 0.7, -0.21), new Vector3(0.15, 0.7, -0.21), 0.025, wood);
  D.pop();
}

/* ------------------------------------------------------------------------------------------ */
/* small shapes                                                                               */
/* ------------------------------------------------------------------------------------------ */

export function circle(x: number, z: number, r: number, seg = 8): Shape2 {
  const out: Shape2 = [];
  for (let i = 0; i < seg; i++) {
    const a = (i / seg) * Math.PI * 2;
    out.push([x + Math.cos(a) * r, z + Math.sin(a) * r]);
  }
  return out;
}

export function boxShape(x: number, z: number, w: number, d: number, rot: number): Shape2 {
  const c = Math.cos(rot);
  const s = Math.sin(rot);
  const pts: Array<[number, number]> = [
    [-w / 2, -d / 2],
    [w / 2, -d / 2],
    [w / 2, d / 2],
    [-w / 2, d / 2],
  ];
  // the press's rotation about y: x' = x cos + z sin, z' = -x sin + z cos
  return pts.map(([px, pz]) => [x + px * c + pz * s, z - px * s + pz * c] as [number, number]);
}

export { INKS, TONES };
