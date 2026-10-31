/**
 * Le Quartier · a room of the season, written from the canon and built.
 *
 * The streets are surveyed (`site.ts`); a room is written. The forge reads a place in
 * `docs/story/season-1/10-lieux-et-images.md` and writes it down as a room file
 * (`world/rooms/<id>.json`, drafted from `scripts/forge/briefs/<id>.json`): the floors you walk and
 * the flights of stairs between them, the walls with their doors and windows, the lamps and the
 * circuit they are on, the things in the room, and the marks where the stage stands people. This
 * builds it with the pieces Le Mistral's room is built from (the wainscot wall, the façade's
 * lining, the globes, the round tables), so a room of the season and the café are the same print.
 *
 * A room has three zones. The room itself is lit by its own lamps and sheltered from the rain.
 * What you see but do not enter yet is `sealed` (Odile's kitchen through her door: dark, the street
 * light through the slats). What lies outside is `out` (a courtyard under the sky, through the
 * stair window). The coordinates are the quarter's: the stairwell stands inside Le Mistral's
 * building, where the quai's façade has its street door.
 */
import { Matrix4, Vector3 } from 'three';

import { chair, frameOf } from './kit';
import type { Build, Frame } from './kit';
import { PATTERN, Press, nextId } from './geo';
import type { Paint, PatternId } from './geo';
import type { Words } from './memory';
import { INKS, TONES, css, mix, rgb } from './palette';
import type { AmbianceId, Hex } from './palette';
import { SANS, SERIF } from './signs';

type XZ = [number, number];
type XYZ = [number, number, number];

/** The room itself, what is seen but not entered yet, and what is outside. */
export type Zone = 'room' | 'sealed' | 'out';

export type FloorFinish = 'cabochons' | 'boards' | 'tomettes' | 'cobbles' | 'stone';
export type WallFinish = 'wainscot' | 'plaster' | 'stone';

export interface RoomFloor {
  key: string;
  shape: XZ[];
  y: number;
  finish: FloorFinish;
  zone?: Zone;
  /** seen, not walked */
  walk?: boolean;
}

export interface RoomFlight {
  key: string;
  /** the middle of the first riser's foot, and the way the flight climbs (along x or z, for the walking grid) */
  from: XZ;
  dir: 'x+' | 'x-' | 'z+' | 'z-';
  width: number;
  y0: number;
  y1: number;
  risers: number;
  tread: number;
  /** the balustrade's side, looking up the flight */
  rail?: 'left' | 'right' | 'both';
}

export interface RoomWall {
  /** from a to b, the room on its right (as Le Mistral's walls) */
  a: XZ;
  b: XZ;
  /** the floor along it, at a and at b: a wall beside a flight climbs with it */
  base: number | [number, number];
  top: number | [number, number];
  finish: WallFinish;
  /** the upper wall's tone, and the wainscot's (`ROOM_TONES`) */
  tone?: string;
  dado?: string;
  zone?: Zone;
  /** no cornice under its top (a partition under a flight, a wall over a lower ceiling) */
  plain?: boolean;
}

export interface RoomDoor {
  key: string;
  /** the wall it stands in, and where along it (u from the wall's a) */
  wall: number;
  u0: number;
  u1: number;
  height: number;
  /** the jamb it hangs from, seen from the room; both for a pair of leaves */
  hinge: 'left' | 'right' | 'both';
  /** into the room, or away from it */
  swing: 'in' | 'out';
  tone: string;
  /** brass figures on the leaf, at eye height («1») */
  numeral?: string;
  /** the story opens it once (Odile's in T1), or it stays shut */
  opens?: 'never' | 'once';
  /** a doormat on the room's side */
  mat?: boolean;
}

export interface RoomWindow {
  key: string;
  wall: number;
  u0: number;
  u1: number;
  y0: number;
  y1: number;
  /** closed: the shutters outside, the street light through their slats in bars */
  shutters?: 'closed';
}

export interface RoomLight {
  key: string;
  /** a globe on its cord (Le Mistral's), a glass bowl on a wall bracket, a round lamp flat on the wall */
  kind: 'globe' | 'sconce' | 'hublot';
  /** where it hangs; its pool is laid on the floor under it */
  at: XYZ;
  /** lamps on one circuit go on and off together (the minuterie) */
  circuit?: string;
  power: number;
  range: number;
  /** the wall a sconce or a hublot is on faces this way */
  facing?: XZ;
  /** a globe's cord runs up to here */
  ceiling?: number;
}

/** A push-button of a circuit: the orange glow by the door that lights the stairs. */
export interface RoomSwitch {
  key: string;
  circuit: string;
  at: XYZ;
  facing: XZ;
}

/** A balustrade along an open edge: iron bars, a wooden handrail. */
export interface RoomRail {
  a: XYZ;
  b: XYZ;
}

export type ThingKind =
  | 'letterboxes'
  | 'mat'
  | 'radiator'
  | 'coat'
  | 'clock'
  | 'calendar'
  | 'table'
  | 'chair'
  | 'slippers'
  | 'camera'
  | 'cup'
  | 'stove'
  | 'patch'
  | 'doorway'
  | 'bed'
  | 'phone'
  | 'keys'
  | 'suitcase'
  | 'kitchenette';

export interface RoomThing {
  kind: ThingKind;
  /** where it stands (or hangs: a card's centre) */
  at: XYZ;
  /** its front faces (sin rot, cos rot) */
  rot?: number;
  zone?: Zone;
  /** what it says: the letterboxes' cards, a calendar's months, a stopped clock's hour */
  text?: string[];
  tone?: string;
  /** width and height, for what has a size of its own (a patch of paint, a doorway) */
  size?: [number, number];
  /** a tap on it says this (the phone's return ticket, the cold radiator) */
  look?: Words;
  /** and the end card remembers it so («Tu as regardé ton billet de retour.») */
  did?: Words;
}

/** A courtyard seen through a window: cobbles, the backs of the houses round it, a few lit windows. */
export interface RoomCourt {
  x0: number;
  z0: number;
  x1: number;
  z1: number;
  /** the side the room looks in from (no wall drawn there) */
  open: 'n' | 's' | 'e' | 'w';
  storeys: number;
  /** share of its windows lit */
  lit: number;
  seed: number;
  /** a mansard over each side: the zinc, its dormers, the chimney stacks (seen from a top floor) */
  roofs?: boolean;
}

export interface RoomSpec {
  id: string;
  version: number;
  kind: 'room';
  /** the place it is inside on the map (Le Mistral's building is on the quai de Valmy) */
  in: string;
  ambiance: AmbianceId;
  title: Words;
  can_do: Words;
  /** what the screen says as you come in (a room without a minuterie is lit, and says where you are) */
  arrive?: Words;
  start: { pos: XZ; look: XYZ };
  floors: RoomFloor[];
  flights: RoomFlight[];
  walls: RoomWall[];
  ceilings: Array<{ shape: XZ[]; y: number; zone?: Zone }>;
  doors: RoomDoor[];
  windows: RoomWindow[];
  /** a way through a wall with no door in it: the far face of a doorway, a passage into the next room */
  holes?: Array<{ wall: number; u0: number; u1: number; y0: number; y1: number }>;
  rails: RoomRail[];
  lights: RoomLight[];
  switches: RoomSwitch[];
  /** how many seconds a press keeps a circuit lit */
  timers: Record<string, number>;
  things: RoomThing[];
  courts: RoomCourt[];
  /** where the stage stands you and the cast */
  marks: Record<string, XYZ>;
  provenance: { canon: string; place: string; scenes: string[]; brief_round?: number };
}

export interface RoomBuilt {
  spec: RoomSpec;
  start: { pos: Vector3; look: Vector3 };
  marks: Record<string, Vector3>;
  /** the leaves, each built about its hinge, for the engine to swing */
  doors: Array<{ key: string; leaf: Press; hinge: Vector3; angle: number; sign: number; dir: number; max: number }>;
  /** each lamp's glass, lit and dark, so a circuit can go out */
  bulbs: Array<{ key: string; circuit: string | null; lit: Press; dark: Press }>;
  /** each door: whether the story opens it, its leaf between the knob and the number (to tap, to look at), and where you stand before it */
  openings: Array<{ key: string; opens: 'never' | 'once'; centre: Vector3; front: Vector3 }>;
  switches: Array<{ key: string; circuit: string; at: Vector3; facing: Vector3 }>;
  /** is (x, z) in the room itself (its lamps light it, it does not rain there)? */
  inside: (x: number, z: number) => boolean;
  /** what the room and everything it shows stand in (the light map, the walking grid) */
  bounds: { x0: number; z0: number; x1: number; z1: number };
  /** where it does not rain: x0, z0, x1, z1 */
  dry: [number, number, number, number];
}

/* ------------------------------------------------------------------------------------------ */
/* the pieces Le Mistral's room is built from                                                 */
/* ------------------------------------------------------------------------------------------ */

/** How high the wainscot runs, up to its rail. */
export const DADO = 1.1;
/** The cornice under a ceiling: [out into the room, up]. */
export const CORNICE: Array<[number, number]> = [[0, 0], [0.06, 0.04], [0.12, 0.16], [0.14, 0.22], [0, 0.22]];
/** The wainscot's rail, straddling the wall's face. */
const RAIL: Array<[number, number]> = [[-0.04, -0.035], [0.04, -0.035], [0.04, 0.035], [-0.04, 0.035]];

export interface WallPaints {
  wainscot: Paint;
  rail: Paint;
  upper: Paint;
  cornice: Paint;
}

/**
 * A wall seen from the room, standing on the right of a → b: the wainscot up to its rail, the
 * upper wall to the ceiling, the cornice under it (Le Mistral's back and north walls).
 */
export function wainscotWall(D: Press, a: XZ, b: XZ, floor: number, ceiling: number, p: WallPaints) {
  const f = frameOf(a, b);
  D.push(f.m);
  D.box(f.len / 2, 0.55 + floor, -0.05, f.len, DADO, 0.1, p.wainscot, { nz: false });
  D.box(f.len / 2, 1.13 + floor, 0.0, f.len, 0.07, 0.08, p.rail, { nz: false });
  D.box(f.len / 2, (floor + DADO + ceiling) / 2, -0.06, f.len, ceiling - floor - DADO, 0.1, p.upper, { nz: false });
  D.sweep(new Vector3(0, ceiling - 0.22, 0), new Vector3(f.len, ceiling - 0.22, 0), CORNICE, p.cornice, { caps: true });
  D.pop();
}

/**
 * The inner face of a wall with one opening in it (a shop front's glass, from the floor to
 * `openTop`): the lining above it, and the piers either side of `u0..u1`.
 */
export function facadeLining(D: Press, a: XZ, b: XZ, u0: number, u1: number, openTop: number, ceiling: number, paint: Paint) {
  const f = frameOf(a, b);
  D.push(f.m);
  D.box(f.len / 2, (openTop + ceiling) / 2, -0.02, f.len, ceiling - openTop, 0.04, paint, { nz: false });
  if (u0 > 0) D.box(u0 / 2, openTop / 2, -0.02, u0, openTop, 0.04, paint, { nz: false });
  if (u1 < f.len) D.box((u1 + f.len) / 2, openTop / 2, -0.02, f.len - u1, openTop, 0.04, paint, { nz: false });
  D.pop();
}

/**
 * A globe on its cord, a brass cap, and the warm pool it lays (Le Mistral's three). The glass goes
 * into `glass` (a room keeps it apart, to put it out with its circuit). The pool is laid on the
 * floor under the lamp: `floor` is its height (the light map knows only how high a lamp hangs).
 */
export function globeLamp(
  B: Build,
  at: Vector3,
  ceiling: number,
  p: { glass: Paint; cord: Paint; brass: Paint },
  lamp: { power: number; range: number; floor?: number },
  glass: Press = B.dry,
  r = 0.22,
) {
  const D = B.dry;
  // Le Mistral's globes are 0.22 across the middle; a smaller one keeps their proportions
  const k = r / 0.22;
  glass.ball(at.x, at.y, at.z, r, r, r, p.glass, 1, { smooth: true });
  D.bar(new Vector3(at.x, at.y + 0.2 * k, at.z), new Vector3(at.x, ceiling, at.z), 0.015, p.cord);
  D.cylinder(at.x, at.y + 0.16 * k, at.z, 0.07 * k, 0.05 * k, 0.08 * k, 6, p.brass, { flat: true });
  B.lamps.push({ pos: new Vector3(at.x, at.y - (lamp.floor ?? 0), at.z), color: rgb(mix(INKS.sunflower, INKS.card, 0.25)), power: lamp.power, range: lamp.range, glint: false, indoor: true });
}

/** A café's round table, marble on iron, and its chairs at the given angles (Le Mistral's). */
export function roundTable(B: Build, x: number, z: number, chairs: number[], floor: number) {
  const D = B.dry;
  const indoor = (p: Paint): Paint => ({ ...p, indoor: true });
  const iron: Paint = indoor({ color: mix(TONES.iron, INKS.ink, 0.3), id: nextId() });
  D.cylinder(x, floor, z, 0.22, 0.05, 0.06, 6, iron, { flat: true });
  D.cylinder(x, floor + 0.06, z, 0.03, 0.03, 0.66, 5, iron, { flat: true });
  D.cylinder(x, floor + 0.72, z, 0.32, 0.32, 0.035, 12, indoor({ color: TONES.marble, wet: 0.4, id: nextId() }));
  chairs.forEach((a) => chair(B, x + Math.sin(a) * 0.62, z + Math.cos(a) * 0.62, a + Math.PI, false, floor));
  B.blocks.push([[x - 0.55, z - 0.55], [x + 0.55, z - 0.55], [x + 0.55, z + 0.55], [x - 0.55, z + 0.55]]);
}

/* ------------------------------------------------------------------------------------------ */
/* inks                                                                                       */
/* ------------------------------------------------------------------------------------------ */

/** The tones a room file names, each a mix of the house inks. */
export const ROOM_TONES: Record<string, Hex> = {
  /** Le Mistral's upper wall, and an old stairwell's */
  ochre: mix(INKS.paper, INKS.ochre, 0.34),
  cream: mix(INKS.paper, INKS.ochre, 0.16),
  /** a stairwell's painted dado, the false marble of the 1900s gone brown */
  faux: mix(mix(TONES.oxblood, INKS.ochre, 0.3), INKS.ink, 0.12),
  wainscot: mix(TONES.wainscot, INKS.ink, 0.12),
  stone: TONES.stone,
  /** the quai's street door, inside as out */
  porch: mix(INKS.green, INKS.ink, 0.12),
  oxblood: TONES.oxblood,
  brown: mix(INKS.ochre, INKS.ink, 0.58),
  wood: TONES.wood,
  grey: mix(INKS.paper, INKS.ink, 0.32),
  /** a kitchen's old paint, a little green */
  celadon: mix(INKS.paper, INKS.green, 0.16),
  white: INKS.card,
  render: mix(INKS.paper, INKS.ochre, 0.26),
  /** a woman's coat, Odile's green (light and warm enough to read as green in the dark) */
  coat: mix(mix(INKS.green, INKS.sunflower, 0.16), INKS.paper, 0.14),
  /** the oilcloth on a kitchen table, its check faded */
  oilcloth: mix(INKS.cobalt, INKS.paper, 0.55),
  /** a grey wool blanket, a little blue */
  blanket: mix(mix(INKS.paper, INKS.ink, 0.45), INKS.cobalt, 0.12),
  /** a hard-shell suitcase, dark blue */
  navy: mix(INKS.cobalt, INKS.ink, 0.45),
};

const toneOf = (name: string | undefined, fallback: Hex): Hex => (name && ROOM_TONES[name] !== undefined ? ROOM_TONES[name] : fallback);

/** How much darker a sealed room is than the night outside its shutters. */
const SEALED_SHADE = 0.55;

/** A paint for a piece of the zone: the room's lamps light the room, the sky the rest. */
function zoned(color: Hex, zone: Zone | undefined, extra: Partial<Paint> = {}): Paint {
  const z = zone ?? 'room';
  return { color, id: nextId(), indoor: z === 'room', shade: z === 'sealed' ? SEALED_SHADE : undefined, ...extra };
}

const FLOORS: Record<FloorFinish, { color: Hex; pattern: PatternId }> = {
  /** a hall's pale stone with its small black squares */
  cabochons: { color: mix(INKS.card, INKS.ochre, 0.1), pattern: PATTERN.tiles },
  boards: { color: mix(TONES.wood, INKS.ochre, 0.3), pattern: PATTERN.planks },
  /** a kitchen's red tiles */
  tomettes: { color: mix(mix(INKS.vermilion, INKS.ochre, 0.5), INKS.paper, 0.3), pattern: PATTERN.tiles },
  cobbles: { color: mix(TONES.stoneGround, INKS.cobalt, 0.08), pattern: PATTERN.cobbles },
  stone: { color: TONES.stone, pattern: PATTERN.flags },
};

const pair = (v: number | [number, number]): [number, number] => (typeof v === 'number' ? [v, v] : v);

/* ------------------------------------------------------------------------------------------ */
/* walls, doors, windows                                                                      */
/* ------------------------------------------------------------------------------------------ */

/** A hole in a wall, in the wall's own frame: along it, and up. */
interface Hole {
  u0: number;
  u1: number;
  y0: number;
  y1: number;
}

/** What is left of the span a..b once the holes' spans are taken out. */
function minus(span: [number, number], holes: Array<[number, number]>): Array<[number, number]> {
  let out: Array<[number, number]> = [span];
  for (const [h0, h1] of holes) {
    out = out.flatMap(([a, b]): Array<[number, number]> => {
      if (h1 <= a || h0 >= b) return [[a, b]];
      const keep: Array<[number, number]> = [];
      if (h0 > a) keep.push([a, h0]);
      if (h1 < b) keep.push([h1, b]);
      return keep;
    });
  }
  return out;
}

/**
 * A wall of a level floor with its openings cut out, band by band: the wainscot, the upper wall,
 * the rail where nothing crosses it. Without openings it is Le Mistral's wall.
 */
function levelWall(P: Press, f: Frame, y0: number, y1: number, holes: Hole[], wainscot: boolean, p: WallPaints, cornice: boolean) {
  const L = f.len;
  const cuts = Array.from(new Set([0, L, ...holes.flatMap((h) => [h.u0, h.u1])]))
    .filter((u) => u >= 0 && u <= L)
    .sort((a, b) => a - b);
  const bands = wainscot
    ? [
        { from: y0, to: y0 + DADO, paint: p.wainscot, w: -0.05 },
        { from: y0 + DADO, to: y1, paint: p.upper, w: -0.06 },
      ]
    : [{ from: y0, to: y1, paint: p.upper, w: -0.06 }];
  for (let i = 0; i + 1 < cuts.length; i++) {
    const s0 = cuts[i];
    const s1 = cuts[i + 1];
    if (s1 - s0 < 0.005) continue;
    const mid = (s0 + s1) / 2;
    const over = holes.filter((h) => h.u0 <= mid && mid <= h.u1);
    for (const band of bands) {
      for (const [a, b] of minus([band.from, band.to], over.map((h): [number, number] => [h.y0, h.y1]))) {
        if (b - a > 0.005) P.box(mid, (a + b) / 2, band.w, s1 - s0, b - a, 0.1, band.paint, { nz: false });
      }
    }
    if (wainscot && !over.some((h) => h.y0 <= y0 + 1.16 && y0 + 1.1 <= h.y1)) P.box(mid, 1.13 + y0, 0, s1 - s0, 0.07, 0.08, p.rail, { nz: false });
  }
  if (cornice) P.sweep(new Vector3(0, y1 - 0.22, 0), new Vector3(L, y1 - 0.22, 0), CORNICE, p.cornice, { caps: true });
}

/**
 * A wall whose foot or head slopes (beside a flight, a partition under one): the wainscot climbs
 * with the steps, and keeps its height until a sloping head comes down to it.
 */
function slopedWall(P: Press, f: Frame, base: [number, number], top: [number, number], wainscot: boolean, p: WallPaints, cornice: boolean) {
  const L = f.len;
  const [b0, b1] = base;
  const [t0, t1] = top;
  const b = (u: number) => b0 + ((b1 - b0) * u) / L;
  const t = (u: number) => t0 + ((t1 - t0) * u) / L;
  const d = (u: number) => Math.min(b(u) + DADO, t(u));
  // where the head crosses a line this far above the foot, if it does
  const crossing = (above: number) => {
    const g0 = t0 - b0 - above;
    const g1 = t1 - b1 - above;
    return g0 * g1 < 0 ? (g0 / (g0 - g1)) * L : null;
  };
  const dado = crossing(DADO);
  const cuts = dado === null ? [0, L] : [0, dado, L];
  for (let i = 0; i + 1 < cuts.length; i++) {
    const u0 = cuts[i];
    const u1 = cuts[i + 1];
    if (!wainscot) {
      P.quadXYZ([u0, b(u0), -0.01, u1, b(u1), -0.01, u1, t(u1), -0.01, u0, t(u0), -0.01], p.upper);
      continue;
    }
    P.quadXYZ([u0, b(u0), 0, u1, b(u1), 0, u1, d(u1), 0, u0, d(u0), 0], p.wainscot);
    if (t(u0) > d(u0) + 0.01 || t(u1) > d(u1) + 0.01) P.quadXYZ([u0, d(u0), -0.01, u1, d(u1), -0.01, u1, t(u1), -0.01, u0, t(u0), -0.01], p.upper);
  }
  if (wainscot) {
    // the rail, where the wall stands clear above it
    const r = crossing(1.2);
    const [ra, rb] = r === null ? (t0 - b0 > 1.2 ? [0, L] : [0, 0]) : t0 - b0 > 1.2 ? [0, r] : [r, L];
    if (rb - ra > 0.05) P.sweep(new Vector3(ra, b(ra) + 1.13, 0), new Vector3(rb, b(rb) + 1.13, 0), RAIL, p.rail, { closed: true });
  }
  if (cornice && t0 === t1) P.sweep(new Vector3(0, t0 - 0.22, 0), new Vector3(L, t0 - 0.22, 0), CORNICE, p.cornice, { caps: true });
}

/** The wall's depth round an opening: the jambs, the head, and a window's sill. */
function reveal(P: Press, h: Hole, paint: Paint, depth: number, sill: boolean) {
  const mid = (h.y0 + h.y1) / 2;
  P.box(h.u0 - 0.02, mid, -depth / 2, 0.04, h.y1 - h.y0, depth, paint);
  P.box(h.u1 + 0.02, mid, -depth / 2, 0.04, h.y1 - h.y0, depth, paint);
  P.box((h.u0 + h.u1) / 2, h.y1 + 0.02, -depth / 2, h.u1 - h.u0 + 0.08, 0.04, depth, paint);
  if (sill) P.box((h.u0 + h.u1) / 2, h.y0 - 0.02, -depth / 2 + 0.03, h.u1 - h.u0 + 0.08, 0.04, depth + 0.06, paint);
}

/** How thick the walls are, for the reveals and for where a leaf hangs. */
const WALL = 0.25;

/** A wall: the room's walls in their finish, a courtyard's in render; a plain hole has no reveal of its own. */
function buildWall(P: Press, w: RoomWall, holes: Hole[], windows: Set<Hole>, plain: Set<Hole>) {
  const f = frameOf(w.a, w.b);
  const [b0, b1] = pair(w.base);
  const [t0, t1] = pair(w.top);
  const z = w.zone;
  const upperTone = toneOf(w.tone, w.finish === 'stone' ? TONES.stone : ROOM_TONES.ochre);
  const p: WallPaints = {
    upper: zoned(upperTone, z, w.finish === 'stone' ? { pattern: PATTERN.courses } : {}),
    wainscot: zoned(toneOf(w.dado, ROOM_TONES.wainscot), z),
    rail: zoned(TONES.wood, z),
    cornice: zoned(mix(upperTone, INKS.paper, 0.3), z),
  };
  const wainscot = w.finish === 'wainscot';
  if (b0 === b1 && t0 === t1) {
    // a level wall without an opening is Le Mistral's own
    if (!holes.length && wainscot && !w.plain) wainscotWall(P, w.a, w.b, b0, t0, p);
    else {
      P.push(f.m);
      levelWall(P, f, b0, t0, holes, wainscot, p, !w.plain);
      P.pop();
    }
  } else {
    P.push(f.m);
    slopedWall(P, f, [b0, b1], [t0, t1], wainscot, p, !w.plain);
    P.pop();
  }
  const revealed = holes.filter((h) => !plain.has(h));
  if (revealed.length) {
    P.push(f.m);
    revealed.forEach((h) => reveal(P, h, p.upper, WALL, windows.has(h)));
    P.pop();
  }
}

/** Brass figures as strokes in a unit box (x across, y up), for a door's number. */
const FIGURES: Record<string, Array<[number, number, number, number]>> = {
  '0': [[0.15, 0.1, 0.15, 0.9], [0.85, 0.1, 0.85, 0.9], [0.15, 0.9, 0.85, 0.9], [0.15, 0.1, 0.85, 0.1]],
  '1': [[0.55, 0, 0.55, 1], [0.55, 1, 0.2, 0.74], [0.25, 0, 0.85, 0]],
  '2': [[0.15, 0.85, 0.5, 1], [0.5, 1, 0.85, 0.8], [0.85, 0.8, 0.15, 0], [0.15, 0, 0.85, 0]],
  '3': [[0.15, 1, 0.85, 1], [0.85, 1, 0.45, 0.58], [0.45, 0.58, 0.85, 0.32], [0.85, 0.32, 0.5, 0], [0.5, 0, 0.15, 0.12]],
  '4': [[0.65, 0, 0.65, 1], [0.65, 1, 0.1, 0.3], [0.1, 0.3, 0.9, 0.3]],
  '5': [[0.85, 1, 0.2, 1], [0.2, 1, 0.15, 0.55], [0.15, 0.55, 0.85, 0.45], [0.85, 0.45, 0.6, 0], [0.6, 0, 0.15, 0.08]],
  '6': [[0.75, 1, 0.2, 0.5], [0.2, 0.5, 0.2, 0.05], [0.2, 0.05, 0.85, 0.05], [0.85, 0.05, 0.85, 0.5], [0.85, 0.5, 0.2, 0.5]],
  '7': [[0.1, 1, 0.9, 1], [0.9, 1, 0.4, 0]],
  '8': [[0.2, 0.55, 0.8, 0.55], [0.15, 0, 0.85, 0], [0.2, 1, 0.8, 1], [0.15, 0, 0.15, 0.55], [0.85, 0, 0.85, 0.55], [0.2, 0.55, 0.2, 1], [0.8, 0.55, 0.8, 1]],
  '9': [[0.25, 0, 0.8, 0.5], [0.8, 0.5, 0.8, 0.95], [0.8, 0.95, 0.15, 0.95], [0.15, 0.95, 0.15, 0.5], [0.15, 0.5, 0.8, 0.5]],
};

/** A number in brass rod on a face at z, its middle at (x, y), `h` high. */
function figures(P: Press, text: string, x: number, y: number, z: number, h: number, paint: Paint) {
  const chars = text.split('').filter((c) => FIGURES[c]);
  const w = h * 0.62;
  const gap = h * 0.22;
  const total = chars.length * w + (chars.length - 1) * gap;
  chars.forEach((c, i) => {
    const x0 = x - total / 2 + i * (w + gap);
    for (const [ax, ay, bx, by] of FIGURES[c]) {
      P.bar(new Vector3(x0 + ax * w, y - h / 2 + ay * h, z), new Vector3(x0 + bx * w, y - h / 2 + by * h, z), h * 0.14, paint);
    }
  });
}

/**
 * A door's leaf built about its hinge (x along the leaf from the hinge, `sign` the way it runs; z
 * out to the room): two raised panels a face, the knob and the keyhole on the free side, and its
 * brass number toward the room.
 */
export function doorLeaf(w: number, h: number, sign: number, wood: Paint, brass: Paint, numeral?: string): Press {
  const P = new Press();
  const t = 0.05;
  const x = (u: number) => sign * u;
  // the panels and their mouldings print their own outlines, so a door reads as a door in the dark
  const panel: Paint = { ...wood, color: mix(wood.color, INKS.ink, 0.22), id: nextId() };
  const moulding: Paint = { ...wood, color: mix(wood.color, INKS.paper, 0.12), id: nextId() };
  P.box(x(w / 2), h / 2, 0, w, h, t, wood);
  for (const face of [1, -1]) {
    const z = face * (t / 2 + 0.006);
    for (const [cy, ph] of [[h * 0.27, h * 0.34], [h * 0.69, h * 0.42]] as Array<[number, number]>) {
      const pw = w - 0.26;
      P.box(x(w / 2), cy, z, pw, ph, 0.012, panel);
      P.box(x(w / 2), cy + ph / 2 + 0.012, z, pw + 0.048, 0.024, 0.018, moulding);
      P.box(x(w / 2), cy - ph / 2 - 0.012, z, pw + 0.048, 0.024, 0.018, moulding);
      P.box(x(w / 2 - pw / 2 - 0.012), cy, z, 0.024, ph, 0.018, moulding);
      P.box(x(w / 2 + pw / 2 + 0.012), cy, z, 0.024, ph, 0.018, moulding);
    }
  }
  // the knob and the keyhole's escutcheon, on the side away from the hinge
  for (const face of [1, -1]) {
    P.ball(x(w - 0.09), 1.02, face * (t / 2 + 0.04), 0.035, 0.035, 0.035, brass, 0);
    P.box(x(w - 0.09), 0.88, face * (t / 2 + 0.004), 0.04, 0.09, 0.008, brass);
  }
  // its number in brass, big enough to read from the top of the stairs
  if (numeral) figures(P, numeral, x(w / 2), 1.6, t / 2 + 0.03, 0.17, brass);
  return P;
}

/** The moulded frame round a doorway, on the room's side. */
function architrave(P: Press, u0: number, u1: number, y0: number, y1: number, paint: Paint) {
  P.box(u0 - 0.05, (y0 + y1 + 0.1) / 2, 0.015, 0.1, y1 - y0 + 0.1, 0.03, paint);
  P.box(u1 + 0.05, (y0 + y1 + 0.1) / 2, 0.015, 0.1, y1 - y0 + 0.1, 0.03, paint);
  P.box((u0 + u1) / 2, y1 + 0.05, 0.015, u1 - u0 + 0.2, 0.1, 0.03, paint);
}

/** A tall window: its casement in two leaves with glazing bars, the panes, and the shutters outside if closed. */
function windowIn(B: Build, P: Press, f: Frame, win: RoomWindow, zone: Zone | undefined) {
  const frame = zoned(mix(INKS.card, INKS.ochre, 0.12), zone);
  const { u0, u1, y0, y1 } = win;
  const w = -WALL * 0.55;
  P.push(f.m);
  // the casement: the outer frame, the meeting stiles, the bars
  P.box((u0 + u1) / 2, y1 - 0.03, w, u1 - u0, 0.06, 0.06, frame);
  P.box((u0 + u1) / 2, y0 + 0.04, w, u1 - u0, 0.08, 0.06, frame);
  P.box(u0 + 0.03, (y0 + y1) / 2, w, 0.06, y1 - y0, 0.06, frame);
  P.box(u1 - 0.03, (y0 + y1) / 2, w, 0.06, y1 - y0, 0.06, frame);
  P.box((u0 + u1) / 2, (y0 + y1) / 2, w, 0.07, y1 - y0, 0.06, frame);
  const rows = Math.max(2, Math.round((y1 - y0) / 0.62));
  for (let k = 1; k < rows; k++) P.box((u0 + u1) / 2, y0 + ((y1 - y0) * k) / rows, w, u1 - u0, 0.035, 0.04, frame);
  P.pop();
  // the panes
  const corner = (u: number, y: number) => {
    const p = new Vector3(u, y, w - 0.01).applyMatrix4(f.m);
    return [p.x, p.y, p.z];
  };
  B.glass.quadXYZ([...corner(u0 + 0.06, y0 + 0.08), ...corner(u1 - 0.06, y0 + 0.08), ...corner(u1 - 0.06, y1 - 0.06), ...corner(u0 + 0.06, y1 - 0.06)], { color: TONES.glass, id: 61 }, 61);
  if (win.shutters === 'closed') {
    // the persiennes outside, shut: dark slats with the street light showing between them
    P.push(f.m);
    const slat = zoned(mix(TONES.shutter, INKS.ink, 0.55), zone, { pattern: PATTERN.ribs });
    const gapLit: Paint = { color: mix(INKS.sunflower, INKS.card, 0.35), glow: 0.85, id: nextId() };
    P.box((u0 + u1) / 2, (y0 + y1) / 2, -WALL - 0.02, u1 - u0 + 0.04, y1 - y0, 0.03, slat, { pz: true });
    for (let y = y0 + 0.16; y < y1 - 0.08; y += 0.14) P.box((u0 + u1) / 2, y, -WALL + 0.0, u1 - u0 - 0.14, 0.012, 0.004, gapLit);
    P.pop();
  }
}

/**
 * The street light through a shut window's slats, laid as bars on the floor of the room behind
 * it: the light comes in a little downward and aslant, one bar a gap.
 */
function slatLight(B: Build, f: Frame, win: RoomWindow, floor: number, reach: number) {
  const bar: Paint = { color: mix(INKS.sunflower, INKS.card, 0.45), glow: 0.5, id: nextId() };
  const down = 0.42;
  const slant = 0.32;
  for (let y = win.y0 + 0.16; y < win.y1 - 0.08; y += 0.14 * 2) {
    const d = (y - floor) / down;
    if (d > reach || d < 0.3) continue;
    const th = 0.05 + d * 0.012;
    const pt = (u: number, dd: number) => new Vector3(u + dd * slant, floor + 0.006, dd).applyMatrix4(f.m);
    const a = pt(win.u0 + 0.08, d);
    const b = pt(win.u1 - 0.08, d);
    const c = pt(win.u1 - 0.08, d + th);
    const e = pt(win.u0 + 0.08, d + th);
    B.dry.quad(a, e, c, b, bar);
  }
}

/* ------------------------------------------------------------------------------------------ */
/* stairs and balustrades                                                                     */
/* ------------------------------------------------------------------------------------------ */

const DIRS: Record<RoomFlight['dir'], XZ> = { 'x+': [1, 0], 'x-': [-1, 0], 'z+': [0, 1], 'z-': [0, -1] };

/** The flight's footprint, from its first riser to its last, and the walking ramp along it. */
export function flightPlan(F: RoomFlight) {
  const [dx, dz] = DIRS[F.dir];
  const run = (F.risers - 1) * F.tread;
  const right: XZ = [-dz, dx];
  const at = (s: number, w: number): XZ => [F.from[0] + dx * s + right[0] * w, F.from[1] + dz * s + right[1] * w];
  const h = F.width / 2;
  return {
    run,
    rise: (F.y1 - F.y0) / F.risers,
    right,
    at,
    shape: [at(0, -h), at(run, -h), at(run, h), at(0, h)] as XZ[],
    // the walking ramp runs half a tread past each end, so it meets the floors level and no cell of
    // the walking grid steps more than a riser and a bit (the forge checks it: `room.py`)
    walk: [at(-F.tread / 2, -h), at(run + F.tread / 2, -h), at(run + F.tread / 2, h), at(-F.tread / 2, h)] as XZ[],
    ramp: { from: at(-F.tread / 2, 0), to: at(run + F.tread / 2, 0), y0: F.y0, y1: F.y1 },
  };
}

/** An iron balustrade along a straight run from a to b (both at the walking surface), with its handrail. */
function balustrade(B: Build, a: Vector3, b: Vector3, zone: Zone | undefined, every = 0.135) {
  const iron = zoned(mix(TONES.iron, INKS.ink, 0.35), zone);
  const rail = zoned(mix(TONES.wood, INKS.ink, 0.2), zone, { wet: 0.25 });
  const len = Math.hypot(b.x - a.x, b.z - a.z);
  const n = Math.max(1, Math.round(len / every));
  for (let i = 0; i <= n; i++) {
    const p = a.clone().lerp(b, i / n);
    B.dry.bar(p.clone().setY(p.y + 0.04), p.clone().setY(p.y + 0.9), 0.016, iron);
  }
  B.dry.sweep(a.clone().setY(a.y + 0.12), b.clone().setY(b.y + 0.12), [[-0.012, -0.012], [0.012, -0.012], [0.012, 0.012], [-0.012, 0.012]], iron, { closed: true });
  B.dry.sweep(a.clone().setY(a.y + 0.93), b.clone().setY(b.y + 0.93), [[-0.032, -0.03], [0.032, -0.03], [0.036, 0.0], [0.03, 0.03], [-0.03, 0.03], [-0.036, 0.0]], rail, { closed: true });
}

/**
 * A flight of worn wooden steps: the treads and risers, a paler track up the middle where three
 * centuries of feet went, the stringer on the open side with its balustrade and a turned newel at
 * the foot, and the soffit under it.
 */
function buildFlight(B: Build, F: RoomFlight) {
  const plan = flightPlan(F);
  const { run, rise, at } = plan;
  const [dx, dz] = DIRS[F.dir];
  const h = F.width / 2;
  const tread = zoned(mix(TONES.wood, INKS.ochre, 0.22), 'room', { pattern: PATTERN.planks });
  const worn = zoned(mix(mix(TONES.wood, INKS.ochre, 0.22), INKS.paper, 0.28), 'room', { pattern: PATTERN.planks });
  const riser = zoned(mix(TONES.wood, INKS.ink, 0.25), 'room');
  const string = zoned(mix(TONES.wood, INKS.ink, 0.3), 'room');
  const soffit = zoned(mix(ROOM_TONES.ochre, INKS.ink, 0.08), 'room');
  const P = B.dry;
  const pt = (s: number, w: number, y: number) => {
    const [x, z] = at(s, w);
    return new Vector3(x, y, z);
  };
  // each step a block from its nosing back to the next riser
  for (let i = 0; i < F.risers - 1; i++) {
    const s0 = i * F.tread - 0.03;
    const s1 = (i + 1) * F.tread;
    const y1 = F.y0 + (i + 1) * rise;
    const [cx, cz] = at((s0 + s1) / 2, 0);
    const sx = Math.abs(dx) * (s1 - s0) + Math.abs(dz) * F.width;
    const sz = Math.abs(dz) * (s1 - s0) + Math.abs(dx) * F.width;
    P.box(cx, y1 - 0.025, cz, sx, 0.05, sz, tread, { ny: false });
    // the riser under the nosing
    const [rx, rz] = at(i * F.tread + 0.01, 0);
    P.box(rx, y1 - rise / 2 - 0.025, rz, Math.abs(dx) * 0.02 + Math.abs(dz) * F.width, rise - 0.05, Math.abs(dz) * 0.02 + Math.abs(dx) * F.width, riser, { py: false, ny: false });
    // the worn track, a little nearer the wall than the rail (across, then up the flight: it faces up)
    const off = (F.rail === 'left' ? 1 : F.rail === 'right' ? -1 : 0) * h * 0.1;
    P.quad(pt(s0 + 0.05, off - h * 0.32, y1 + 0.003), pt(s0 + 0.05, off + h * 0.32, y1 + 0.003), pt(s1 - 0.04, off + h * 0.32, y1 + 0.003), pt(s1 - 0.04, off - h * 0.32, y1 + 0.003), worn);
  }
  // the last riser, up to the landing
  {
    const [rx, rz] = at((F.risers - 1) * F.tread + 0.01, 0);
    P.box(rx, F.y1 - rise / 2 - 0.025, rz, Math.abs(dx) * 0.02 + Math.abs(dz) * F.width, rise - 0.05, Math.abs(dz) * 0.02 + Math.abs(dx) * F.width, riser, { py: false, ny: false });
  }
  // the soffit: a sloped ceiling under the steps, seen from below
  P.quad(pt(0, -h, F.y0 - 0.12), pt(run, -h, F.y1 - 0.3), pt(run, h, F.y1 - 0.3), pt(0, h, F.y0 - 0.12), soffit);
  // the stringers and the balustrade on the open side(s)
  const sides = F.rail === 'both' ? [-1, 1] : F.rail === 'right' ? [1] : F.rail === 'left' ? [-1] : [];
  for (const side of sides) {
    const w = side * (h + 0.04);
    P.sweep(pt(-0.05, w, F.y0 - 0.1), pt(run + 0.02, w, F.y1 - 0.1), [[-0.04, -0.2], [0.04, -0.2], [0.04, 0.16], [-0.04, 0.16]], string, { closed: true, caps: true });
    // the newel at the foot, turned, a brass knob
    const [nx, nz] = at(0.1, w);
    P.lathe(nx, F.y0, nz, [[0.07, 0], [0.07, 0.12], [0.05, 0.16], [0.045, 0.8], [0.06, 0.86], [0.06, 0.96], [0, 0.98]], 8, string);
    P.ball(nx, F.y0 + 1.02, nz, 0.045, 0.045, 0.045, zoned(TONES.brass, 'room', { wet: 0.7 }), 0);
    balustrade(B, pt(0.25, w, F.y0 + rise * 1.4 + 0.02), pt(run, w, F.y1 + 0.02), 'room', F.tread / 2);
    // the walker keeps off the balustrade
    const b0 = at(0, w - side * 0.08);
    const b1 = at(run + F.tread / 2, w - side * 0.08);
    const b2 = at(run + F.tread / 2, w + side * 0.08);
    const b3 = at(0, w + side * 0.08);
    B.blocks.push([b0, b1, b2, b3]);
  }
}

/* ------------------------------------------------------------------------------------------ */
/* lamps and switches                                                                         */
/* ------------------------------------------------------------------------------------------ */

function lampOf(B: Build, L: RoomLight, floor: number): { lit: Press; dark: Press } {
  const lit = new Press();
  const dark = new Press();
  const at = new Vector3(L.at[0], L.at[1], L.at[2]);
  // Le Mistral's globe glass, and the same glass gone out
  const glassLit: Paint = { color: mix(INKS.card, INKS.sunflower, 0.35), glow: 1, id: nextId(), indoor: true };
  const glassDark: Paint = { color: mix(INKS.card, INKS.cobalt, 0.25), id: glassLit.id, indoor: true };
  const brass = zoned(TONES.brass, 'room', { wet: 0.6 });
  const cord = zoned(INKS.ink, 'room');
  if (L.kind === 'globe') {
    // Le Mistral's globe, smaller for a hall
    globeLamp(B, at, L.ceiling ?? at.y + 0.6, { glass: glassLit, cord, brass }, { power: L.power, range: L.range, floor }, lit, 0.17);
    dark.ball(at.x, at.y, at.z, 0.17, 0.17, 0.17, glassDark, 1, { smooth: true });
    return { lit, dark };
  }
  const [fx, fz] = L.facing ?? [0, 1];
  const rot = Math.atan2(fx, fz);
  if (L.kind === 'sconce') {
    // a brass arm off the wall, a tulip of glass on it
    B.dry.at(at.x, at.y, at.z, rot, () => {
      B.dry.box(0, -0.22, -0.26, 0.09, 0.14, 0.02, brass);
      B.dry.bar(new Vector3(0, -0.2, -0.26), new Vector3(0, -0.12, -0.02), 0.016, brass);
    });
    for (const [P, g] of [[lit, glassLit], [dark, glassDark]] as Array<[Press, Paint]>) {
      P.at(at.x, at.y, at.z, rot, () => P.lathe(0, -0.12, 0, [[0.03, 0], [0.09, 0.07], [0.11, 0.14], [0.1, 0.16], [0, 0.11]], 10, g));
    }
  } else {
    // a round lamp flat on the wall, its glass a dome in a brass ring
    B.dry.at(at.x, at.y, at.z, rot, () => {
      B.dry.cylinder(0, -0.13, -0.235, 0.15, 0.15, 0.03, 12, brass, { flat: true });
    });
    for (const [P, g] of [[lit, glassLit], [dark, glassDark]] as Array<[Press, Paint]>) {
      P.at(at.x, at.y, at.z, rot, () => P.ball(0, 0, -0.2, 0.12, 0.12, 0.07, g, 1, { smooth: true }));
    }
  }
  B.lamps.push({ pos: new Vector3(at.x, at.y - floor, at.z), color: rgb(mix(INKS.sunflower, INKS.card, 0.25)), power: L.power, range: L.range, glint: false, indoor: true });
  return { lit, dark };
}

/** The minuterie's push-button: a round plate and its orange glow, lit day and night. */
function switchAt(B: Build, s: RoomSwitch) {
  const rot = Math.atan2(s.facing[0], s.facing[1]);
  const plate = zoned(mix(INKS.card, INKS.ochre, 0.18), 'room');
  const glow: Paint = { color: mix(INKS.vermilion, INKS.sunflower, 0.55), glow: 1, id: nextId(), indoor: true };
  B.dry.at(s.at[0], s.at[1], s.at[2], rot, () => {
    B.dry.box(0, 0, 0.006, 0.085, 0.12, 0.012, plate);
    B.dry.cylinder(0, 0, 0.0, 0.022, 0.022, 0.03, 10, glow);
  });
}

/* ------------------------------------------------------------------------------------------ */
/* things                                                                                     */
/* ------------------------------------------------------------------------------------------ */

/** A wall card printed into the sign atlas, facing (sin rot, cos rot). */
function card(B: Build, key: string, at: XYZ, rot: number, w: number, h: number, zone: Zone | undefined, draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void, density = 420) {
  const n = new Vector3(Math.sin(rot), 0, Math.cos(rot));
  B.signs.push({ key, center: new Vector3(at[0], at[1], at[2]).addScaledVector(n, 0.012), normal: n, width: w, height: h, density, draw, indoor: (zone ?? 'room') === 'room' });
}

function thing(B: Build, t: RoomThing, i: number) {
  const D = B.dry;
  const z = t.zone;
  const rot = t.rot ?? 0;
  const [x, y, zz] = t.at;
  const key = `room:${t.kind}:${i}`;
  switch (t.kind) {
    case 'letterboxes': {
      // a cabinet of small wooden boxes, a card in each slot's frame
      const labels = t.text ?? [];
      const cols = 3;
      const rows = Math.ceil(Math.max(1, labels.length) / cols);
      const bw = 0.32;
      const bh = 0.24;
      const wood = zoned(toneOf(t.tone, ROOM_TONES.brown), z);
      const slot = zoned(mix(toneOf(t.tone, ROOM_TONES.brown), INKS.ink, 0.45), z);
      D.at(x, y, zz, rot, () => {
        D.box(0, 0, 0.1, cols * bw + 0.06, rows * bh + 0.06, 0.2, wood, { nz: false });
        for (let r = 0; r < rows; r++) {
          for (let c = 0; c < cols; c++) {
            const cx = (c - (cols - 1) / 2) * bw;
            const cy = ((rows - 1) / 2 - r) * bh;
            D.box(cx, cy + 0.06, 0.205, bw - 0.08, 0.016, 0.01, slot);
            D.box(cx, cy - 0.01, 0.204, bw - 0.03, 0.006, 0.008, slot);
          }
        }
      });
      labels.forEach((text, k) => {
        if (!text) return;
        const c = k % cols;
        const r = Math.floor(k / cols);
        const n = new Vector3(Math.sin(rot), 0, Math.cos(rot));
        const side = new Vector3(Math.cos(rot), 0, -Math.sin(rot));
        const p = new Vector3(x, y + ((rows - 1) / 2 - r) * bh - 0.05, zz).addScaledVector(side, (c - (cols - 1) / 2) * bw).addScaledVector(n, 0.21);
        card(B, `${key}:${k}`, [p.x, p.y, p.z], rot, bw - 0.06, 0.06, z, labelArt(text), 900);
      });
      B.blocks.push(footprint(x, zz, rot, cols * bw + 0.1, 0.3));
      return;
    }
    case 'mat': {
      const mat = zoned(mix(INKS.ochre, INKS.ink, 0.42), z, { pattern: PATTERN.ribs });
      D.at(x, y, zz, rot, () => D.box(0, 0.01, 0, 0.78, 0.02, 0.48, mat, { ny: false }));
      return;
    }
    case 'radiator': {
      // cast iron in columns, painted with the walls, on its feet
      const iron = zoned(mix(toneOf(t.tone, ROOM_TONES.ochre), INKS.ink, 0.18), z);
      D.at(x, y, zz, rot, () => {
        for (let k = 0; k < 9; k++) D.box(-0.36 + k * 0.09, 0.47, 0.1, 0.06, 0.62, 0.16, iron);
        D.box(0, 0.16, 0.1, 0.8, 0.04, 0.12, iron);
        D.box(0, 0.79, 0.1, 0.8, 0.04, 0.12, iron);
      });
      B.blocks.push(footprint(x, zz, rot, 0.9, 0.3));
      return;
    }
    case 'coat': {
      // a hook, and a woman's coat hanging from it by its loop, flat against the wall: the collar,
      // the shoulders falling away from the hook, the sleeves at its sides, buttoned (a coat, never
      // a figure: it hangs from a point, wider at the hem than at the shoulders)
      const tone = toneOf(t.tone, ROOM_TONES.coat);
      const coat = zoned(tone, z);
      const fold = zoned(mix(tone, INKS.ink, 0.3), z);
      const lining = zoned(mix(tone, INKS.ink, 0.6), z);
      const brass = zoned(TONES.brass, z, { wet: 0.6 });
      const body: XZ[] = [[0.04, -0.03], [0.1, -0.06], [0.21, -0.14], [0.25, -0.2], [0.3, -1.0], [-0.3, -1.0], [-0.25, -0.2], [-0.21, -0.14], [-0.1, -0.06], [-0.04, -0.03]];
      const sleeve: XZ[] = [[0.2, -0.17], [0.255, -0.21], [0.285, -0.74], [0.215, -0.76]];
      // drawn from the front: u across, v up (the prism's depth is out from the wall)
      const flat = (pts: XZ[], mirror = 1): XZ[] => pts.map(([u, v]) => [u * mirror, -v]);
      D.at(x, y, zz, rot, () => {
        D.bar(new Vector3(0, 0.02, 0.0), new Vector3(0, 0.0, 0.08), 0.018, brass);
        D.push(new Matrix4().makeRotationX(Math.PI / 2));
        D.prism(flat(body), 0.03, 0.15, coat);
        D.prism(flat(sleeve), 0.15, 0.175, fold);
        D.prism(flat(sleeve, -1), 0.15, 0.175, fold);
        D.pop();
        // the lapels' V, the opening down to the hem, the buttons, the pockets
        D.bar(new Vector3(-0.08, -0.07, 0.155), new Vector3(0.02, -0.32, 0.155), 0.022, lining);
        D.bar(new Vector3(0.09, -0.07, 0.155), new Vector3(0.02, -0.32, 0.155), 0.022, lining);
        D.box(0.025, -0.66, 0.152, 0.01, 0.68, 0.006, lining);
        for (const v of [-0.38, -0.52, -0.66]) D.ball(0.0, v, 0.158, 0.017, 0.017, 0.012, brass, 0);
        for (const u of [-0.15, 0.17]) D.box(u, -0.64, 0.153, 0.12, 0.014, 0.006, lining);
        for (const u of [-0.25, 0.25]) D.box(u, -0.745, 0.163, 0.07, 0.03, 0.03, lining);
      });
      return;
    }
    case 'clock': {
      const rim = zoned(mix(INKS.card, INKS.ink, 0.12), z);
      D.at(x, y, zz, rot, () => D.cylinder(0, 0, 0.0, 0.16, 0.16, 0.035, 16, rim, { flat: true, caps: true }));
      const r0 = new Vector3(Math.sin(rot), 0, Math.cos(rot));
      // the cylinder stands up: lay its face toward the room by printing the dial in front of it
      card(B, key, [x + r0.x * 0.03, y, zz + r0.z * 0.03], rot, 0.28, 0.28, z, clockFaceArt(t.text?.[0] ?? '3:40'), 900);
      return;
    }
    case 'calendar': {
      card(B, key, [x, y, zz], rot, 0.34, 0.5, z, calendarArt(t.text ?? ['AVRIL 2023']), 700);
      const nail = zoned(INKS.ink, z);
      D.at(x, y, zz, rot, () => D.box(0, 0.27, 0.015, 0.012, 0.012, 0.03, nail));
      return;
    }
    case 'table': {
      // a kitchen table under its oilcloth, the check faded
      const wood = zoned(mix(TONES.wood, INKS.paper, 0.15), z);
      const cloth = zoned(toneOf(t.tone, ROOM_TONES.oilcloth), z, { pattern: PATTERN.tiles });
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.745, 0, 0.92, 0.03, 0.66, cloth);
        D.box(0, 0.7, 0, 0.84, 0.07, 0.58, wood, { py: false });
        for (const [lx, lz] of [[-0.38, -0.25], [0.38, -0.25], [-0.38, 0.25], [0.38, 0.25]] as Array<[number, number]>) D.box(lx, 0.33, lz, 0.05, 0.67, 0.05, wood, { ny: false });
      });
      return;
    }
    case 'chair': {
      // a kitchen chair, straight and plain, pulled out a little
      const wood = zoned(toneOf(t.tone, mix(TONES.wood, INKS.paper, 0.1)), z);
      D.at(x, y, zz, rot, () => {
        for (const [lx, lz] of [[-0.18, -0.17], [0.18, -0.17], [-0.18, 0.17], [0.18, 0.17]] as Array<[number, number]>) D.box(lx, 0.22, lz, 0.035, 0.44, 0.035, wood, { ny: false });
        D.box(0, 0.455, 0, 0.42, 0.03, 0.4, wood);
        for (const lx of [-0.18, 0.18]) D.box(lx, 0.7, -0.185, 0.035, 0.5, 0.035, wood, { ny: false });
        D.box(0, 0.88, -0.185, 0.42, 0.09, 0.025, wood);
        D.box(0, 0.68, -0.185, 0.36, 0.04, 0.02, wood);
      });
      return;
    }
    case 'slippers': {
      // felt slippers side by side, toes out
      const felt = zoned(toneOf(t.tone, mix(TONES.oxblood, INKS.paper, 0.2)), z);
      D.at(x, y, zz, rot, () => {
        for (const sx of [-0.07, 0.07]) {
          D.box(sx, 0.025, 0, 0.09, 0.05, 0.25, felt, { ny: false });
          D.box(sx, 0.06, 0.06, 0.08, 0.04, 0.11, felt, { ny: false });
        }
      });
      return;
    }
    case 'camera': {
      // an old instant camera: the cream body, the black bellows box, the lens
      const body = zoned(mix(INKS.card, INKS.ochre, 0.1), z);
      const black = zoned(mix(INKS.ink, INKS.cobalt, 0.1), z);
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.05, 0, 0.15, 0.1, 0.11, body, { ny: false });
        D.box(0, 0.11, -0.01, 0.15, 0.03, 0.09, black, { ny: false });
        D.cylinder(0.03, 0.05, 0.055, 0.025, 0.025, 0.02, 10, black, { flat: true });
      });
      return;
    }
    case 'cup': {
      // a café crème cup on its saucer, a dried brown ring inside
      const porcelain = zoned(INKS.card, z, { wet: 0.4 });
      const ring = zoned(mix(INKS.ochre, INKS.ink, 0.35), z);
      D.lathe(x, y, zz, [[0.075, 0], [0.08, 0.008], [0.06, 0.011], [0, 0.012]], 14, porcelain);
      D.lathe(x, y + 0.012, zz, [[0.026, 0], [0.04, 0.012], [0.047, 0.05], [0.049, 0.068], [0.044, 0.068], [0, 0.064]], 14, porcelain);
      D.lathe(x, y + 0.03, zz, [[0.042, 0], [0.04, 0.004], [0, 0.004]], 14, ring);
      return;
    }
    case 'stove': {
      // an enamelled gas cooker: the hob, its burners, the oven door, the knobs
      const enamel = zoned(mix(INKS.card, INKS.cobalt, 0.06), z, { wet: 0.3 });
      const black = zoned(mix(INKS.ink, INKS.cobalt, 0.12), z);
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.43, 0, 0.6, 0.86, 0.58, enamel, { ny: false });
        for (const [bx, bz] of [[-0.14, -0.12], [0.14, -0.12], [-0.14, 0.13], [0.14, 0.13]] as Array<[number, number]>) D.cylinder(bx, 0.86, bz, 0.07, 0.07, 0.02, 8, black, { flat: true });
        D.box(0, 0.42, 0.295, 0.46, 0.4, 0.012, black);
        for (let k = 0; k < 4; k++) D.cylinder(-0.18 + k * 0.12, 0.74, 0.3, 0.018, 0.018, 0.03, 6, black, { flat: true });
      });
      B.blocks.push(footprint(x, zz, rot, 0.65, 0.62));
      return;
    }
    case 'patch': {
      // a patch of paint a whiter white than the wall round it
      const [w, h] = t.size ?? [0.9, 0.7];
      const white = zoned(mix(INKS.card, 0xffffff, 0.35), z);
      D.at(x, y, zz, rot, () => D.quadXYZ([-w / 2, -h / 2, 0.004, w / 2, -h / 2, 0.004, w / 2, h / 2, 0.004, -w / 2, h / 2, 0.004], white));
      return;
    }
    case 'doorway': {
      // the open way into the next room, dark: its frame, and the dark beyond it
      const [w, h] = t.size ?? [0.86, 2.1];
      const frame = zoned(mix(INKS.card, INKS.ochre, 0.14), z);
      const dark = zoned(mix(INKS.ink, INKS.cobalt, 0.25), z);
      D.at(x, y, zz, rot, () => {
        D.quadXYZ([-w / 2, 0, -0.2, w / 2, 0, -0.2, w / 2, h, -0.2, -w / 2, h, -0.2], dark);
        architrave(D, -w / 2, w / 2, 0, h, frame);
      });
      return;
    }
    case 'bed': {
      // a single divan against the wall: the frame on short legs, the mattress, the pillow at the
      // head (the back), a grey wool blanket over the rest and hanging over the sides and the foot
      const [w, d] = t.size ?? [0.9, 1.95];
      const frame = zoned(mix(TONES.wood, INKS.ink, 0.25), z);
      const sheet = zoned(mix(INKS.card, INKS.paper, 0.5), z);
      const wool = zoned(toneOf(t.tone, ROOM_TONES.blanket), z, { pattern: PATTERN.ribs });
      D.at(x, y, zz, rot, () => {
        for (const [lx, lz] of [[-w / 2 + 0.05, -d / 2 + 0.05], [w / 2 - 0.05, -d / 2 + 0.05], [-w / 2 + 0.05, d / 2 - 0.05], [w / 2 - 0.05, d / 2 - 0.05]] as Array<[number, number]>) D.box(lx, 0.07, lz, 0.05, 0.14, 0.05, frame, { ny: false });
        D.box(0, 0.2, 0, w, 0.12, d, frame);
        D.box(0, 0.33, 0, w - 0.04, 0.14, d - 0.04, sheet);
        D.box(0, 0.445, -d / 2 + 0.24, w - 0.22, 0.09, 0.36, sheet);
        D.box(0, 0.415, 0.2, w + 0.04, 0.03, d - 0.62, wool);
        for (const sx of [-1, 1]) D.box(sx * (w / 2 + 0.01), 0.32, 0.2, 0.02, 0.2, d - 0.62, wool);
        D.box(0, 0.32, d / 2 + 0.01, w + 0.04, 0.2, 0.02, wool);
        // the sheet turned down over the blanket's edge, and a plain headboard
        D.box(0, 0.437, -d / 2 + 0.53, w + 0.03, 0.025, 0.14, sheet);
        D.box(0, 0.46, -d / 2 - 0.015, w, 0.64, 0.03, frame);
      });
      B.blocks.push(centred(x, zz, rot, w + 0.06, d + 0.04));
      return;
    }
    case 'phone': {
      // a phone lying on a fold of the blanket, its screen lit and turned a little toward you, and
      // on it what it says (the return ticket): body and screen tilt together
      const lean = 0.3;
      const black = zoned(mix(INKS.ink, INKS.cobalt, 0.1), z, { wet: 0.5 });
      const glow: Paint = { color: mix(INKS.card, INKS.cobalt, 0.1), glow: 1, id: nextId() };
      D.at(x, y, zz, rot, () => {
        D.push(new Matrix4().makeRotationX(lean));
        D.box(0, 0.0, 0, 0.078, 0.009, 0.16, black);
        D.quadXYZ([-0.034, 0.0052, 0.072, 0.034, 0.0052, 0.072, 0.034, 0.0052, -0.072, -0.034, 0.0052, -0.072], glow);
        D.pop();
      });
      const n = new Vector3(Math.sin(rot) * Math.sin(lean), Math.cos(lean), Math.cos(rot) * Math.sin(lean));
      const c = new Vector3(x, y, zz).addScaledVector(n, 0.0055);
      B.signs.push({ key, center: c, normal: n, width: 0.064, height: 0.138, density: 2400, draw: phoneArt(t.text ?? []), indoor: (z ?? 'room') === 'room' });
      return;
    }
    case 'keys': {
      // Odile's key ring lying flat: the old brass key, its ring, and the small enamel cicada,
      // green and gold, face up (a little larger than life, so a phone shows it)
      const brass = zoned(TONES.brass, z, { wet: 0.6 });
      const enamel = zoned(mix(INKS.green, INKS.sunflower, 0.14), z, { wet: 0.5 });
      const gold = zoned(mix(INKS.sunflower, INKS.ochre, 0.4), z, { wet: 0.6 });
      const k = 1.35;
      D.at(x, y, zz, rot, () => {
        for (let i = 0; i < 12; i++) {
          const a0 = (i / 12) * Math.PI * 2;
          const a1 = ((i + 1) / 12) * Math.PI * 2;
          D.bar(new Vector3(Math.cos(a0) * 0.022 * k, 0.004, Math.sin(a0) * 0.022 * k), new Vector3(Math.cos(a1) * 0.022 * k, 0.004, Math.sin(a1) * 0.022 * k), 0.0035 * k, brass);
        }
        D.cylinder(0.042 * k, 0.001, 0, 0.013 * k, 0.013 * k, 0.005, 10, brass, { flat: true, caps: true });
        D.box(0.09 * k, 0.003, 0, 0.075 * k, 0.005, 0.008 * k, brass);
        D.box(0.122 * k, 0.003, 0.009 * k, 0.014 * k, 0.005, 0.016 * k, brass);
        D.ball(-0.042 * k, 0.007, 0, 0.012 * k, 0.007 * k, 0.021 * k, enamel, 0);
        D.ball(-0.042 * k, 0.01, -0.013 * k, 0.009 * k, 0.006 * k, 0.007 * k, gold, 0);
      });
      return;
    }
    case 'suitcase': {
      // a hard-shell cabin suitcase standing on its wheels, its handle down, two ribs down the shell
      const tone = toneOf(t.tone, ROOM_TONES.navy);
      const shell = zoned(tone, z, { wet: 0.35 });
      const rib = zoned(mix(tone, INKS.ink, 0.3), z);
      const black = zoned(mix(INKS.ink, INKS.cobalt, 0.1), z);
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.33, 0, 0.4, 0.56, 0.24, shell);
        for (const lx of [-0.11, 0.11]) D.box(lx, 0.33, 0.123, 0.06, 0.5, 0.01, rib);
        D.box(0, 0.62, -0.085, 0.17, 0.025, 0.035, black);
        for (const lx of [-0.16, 0.16]) D.box(lx, 0.025, -0.09, 0.03, 0.05, 0.05, black, { ny: false });
      });
      B.blocks.push(centred(x, zz, rot, 0.44, 0.28));
      return;
    }
    case 'kitchenette': {
      // a studio's kitchen against a wall: a cupboard under its worktop, the sink and its tap, two
      // hot plates, a shelf above (its back on the wall, its front to the room)
      const w = t.size?.[0] ?? 1.2;
      const d = 0.58;
      const front = zoned(mix(INKS.card, INKS.paper, 0.4), z);
      const seam = zoned(mix(INKS.card, INKS.ink, 0.35), z);
      const top = zoned(mix(TONES.wood, INKS.paper, 0.2), z);
      const steel = zoned(mix(INKS.paper, INKS.ink, 0.3), z, { wet: 0.8 });
      const basin = zoned(mix(INKS.paper, INKS.ink, 0.55), z, { wet: 0.8 });
      const black = zoned(mix(INKS.ink, INKS.cobalt, 0.12), z);
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.43, d / 2, w, 0.86, d, front, { ny: false });
        D.box(0, 0.88, d / 2 + 0.01, w + 0.02, 0.04, d + 0.03, top);
        D.box(0, 0.43, d + 0.003, 0.008, 0.78, 0.004, seam);
        for (const u of [-0.06, 0.06]) D.box(u, 0.72, d + 0.012, 0.016, 0.07, 0.016, black);
        // the sink, a little left; its tap from the wall
        D.box(-w / 4, 0.902, d / 2, 0.42, 0.006, 0.36, steel);
        D.box(-w / 4, 0.906, d / 2, 0.34, 0.004, 0.28, basin);
        D.bar(new Vector3(-w / 4, 0.9, 0.07), new Vector3(-w / 4, 1.12, 0.07), 0.012, steel);
        D.bar(new Vector3(-w / 4, 1.12, 0.07), new Vector3(-w / 4, 1.1, 0.22), 0.011, steel);
        // two hot plates, a little right
        for (const u of [w / 4 - 0.11, w / 4 + 0.12]) D.cylinder(u, 0.9, d / 2, 0.085, 0.085, 0.012, 12, black, { flat: true, caps: true });
        // the shelf
        D.box(0, 1.55, 0.12, w, 0.025, 0.24, top);
      });
      B.blocks.push(footprint(x, zz, rot, w + 0.04, d + 0.04));
      return;
    }
    default:
      return;
  }
}

/** A rectangle round (x, z) turned by `rot`, `w` across its front and `d` deep. */
function footprint(x: number, z: number, rot: number, w: number, d: number): XZ[] {
  const c = Math.cos(rot);
  const s = Math.sin(rot);
  return [[-w / 2, 0], [w / 2, 0], [w / 2, d], [-w / 2, d]].map(([px, pz]): XZ => [x + px * c + pz * s, z - px * s + pz * c]);
}

/** A rectangle centred on (x, z), turned by `rot`, `w` across its front and `d` deep. */
function centred(x: number, z: number, rot: number, w: number, d: number): XZ[] {
  const c = Math.cos(rot);
  const s = Math.sin(rot);
  return [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]].map(([px, pz]): XZ => [x + px * c + pz * s, z - px * s + pz * c]);
}

/** A phone's lit screen: the ticket's lines, the first in bold (the screen is the light here). */
function phoneArt(lines: string[]) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(INKS.card, INKS.cobalt, 0.06));
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(mix(INKS.cobalt, INKS.ink, 0.2));
    ctx.fillRect(0, 0, w, h * 0.16);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = css(INKS.ink);
    lines.forEach((text, i) => {
      let s = Math.round(w * (i === 0 ? 0.15 : 0.1));
      ctx.font = SANS(s, i === 0 ? 700 : 500);
      while (s > 6 && ctx.measureText(text).width > w * 0.9) {
        s -= 1;
        ctx.font = SANS(s, i === 0 ? 700 : 500);
      }
      ctx.fillText(text, w / 2, h * (0.36 + i * 0.13));
    });
  };
}

/** A letterbox's card: a name typed on a slip. */
function labelArt(text: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(INKS.card);
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(INKS.ink);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    let s = Math.round(h * 0.62);
    ctx.font = SANS(s, 600);
    while (s > 6 && ctx.measureText(text).width > w * 0.92) ctx.font = SANS(--s, 600);
    ctx.fillText(text, w / 2, h * 0.54);
  };
}

/** A kitchen clock's face, its hands stopped at `hour` («3:40»). */
function clockFaceArt(hour: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2;
    const cy = h / 2;
    const r = Math.min(w, h) * 0.48;
    ctx.fillStyle = css(INKS.card);
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = css(INKS.ink);
    for (let i = 0; i < 12; i++) {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate((i / 12) * Math.PI * 2);
      ctx.fillRect(-r * 0.025, -r * 0.9, r * 0.05, r * (i % 3 === 0 ? 0.16 : 0.09));
      ctx.restore();
    }
    const [hh, mm] = hour.split(':').map(Number);
    const hand = (a: number, len: number, wid: number) => {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(a);
      ctx.fillRect(-wid / 2, -len, wid, len + r * 0.1);
      ctx.restore();
    };
    hand((((hh % 12) + (mm || 0) / 60) / 12) * Math.PI * 2, r * 0.5, r * 0.08);
    hand(((mm || 0) / 60) * Math.PI * 2, r * 0.74, r * 0.05);
  };
}

/** A wall calendar: the month's name over its grid, the next month's top below (T2 reads it). */
function calendarArt(months: string[]) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(INKS.card);
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(INKS.vermilion);
    ctx.fillRect(0, 0, w, h * 0.13);
    ctx.fillStyle = css(INKS.card);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = SERIF(Math.round(h * 0.085), 700);
    ctx.fillText(months[0] ?? '', w / 2, h * 0.067);
    ctx.strokeStyle = css(mix(INKS.ink, INKS.paper, 0.45));
    ctx.lineWidth = Math.max(1, w * 0.004);
    const grid = (y0: number, rows: number) => {
      for (let r = 0; r <= rows; r++) {
        ctx.beginPath();
        ctx.moveTo(w * 0.06, y0 + r * h * 0.075);
        ctx.lineTo(w * 0.94, y0 + r * h * 0.075);
        ctx.stroke();
      }
      for (let c = 0; c <= 7; c++) {
        ctx.beginPath();
        ctx.moveTo(w * 0.06 + (c * w * 0.88) / 7, y0);
        ctx.lineTo(w * 0.06 + (c * w * 0.88) / 7, y0 + rows * h * 0.075);
        ctx.stroke();
      }
    };
    grid(h * 0.17, 5);
    if (months[1]) {
      ctx.fillStyle = css(INKS.ink);
      ctx.font = SERIF(Math.round(h * 0.06), 700);
      ctx.fillText(months[1], w / 2, h * 0.6);
      grid(h * 0.66, 4);
    }
  };
}

/* ------------------------------------------------------------------------------------------ */
/* a courtyard                                                                                */
/* ------------------------------------------------------------------------------------------ */

/** The backs of the houses round a courtyard, rendered and plain, windows in rows, a few lit. */
function court(B: Build, c: RoomCourt) {
  const D = B.dry;
  const R = { v: c.seed };
  const rand = () => {
    R.v = (R.v * 16807) % 2147483647;
    return R.v / 2147483647;
  };
  const render = zoned(ROOM_TONES.render, 'out');
  const pane = zoned(TONES.pane, 'out', { wet: 0.6 });
  const lit: Paint = { color: mix(INKS.sunflower, INKS.card, 0.2), glow: 1, id: nextId() };
  const sill = zoned(mix(ROOM_TONES.render, INKS.paper, 0.35), 'out');
  const zinc = zoned(TONES.zincDark, 'out');
  const cobbles = zoned(FLOORS.cobbles.color, 'out', { pattern: PATTERN.cobbles });
  D.prism([[c.x0, c.z0], [c.x1, c.z0], [c.x1, c.z1], [c.x0, c.z1]], -0.2, 0, cobbles, { sides: false });
  const g = 4.6;
  const heights = [3.3, 3.15, 3.0, 2.9, 2.8, 2.7].slice(0, c.storeys);
  const top = g + heights.reduce((s, h) => s + h, 0);
  // each side seen from the courtyard: the courtyard on its right
  const sides: Array<{ k: RoomCourt['open']; a: XZ; b: XZ }> = [
    { k: 'n', a: [c.x0, c.z0], b: [c.x1, c.z0] },
    { k: 'e', a: [c.x1, c.z0], b: [c.x1, c.z1] },
    { k: 's', a: [c.x1, c.z1], b: [c.x0, c.z1] },
    { k: 'w', a: [c.x0, c.z1], b: [c.x0, c.z0] },
  ];
  for (const s of sides) {
    if (s.k === c.open) continue;
    const f = frameOf(s.a, s.b);
    D.push(f.m);
    D.box(f.len / 2, top / 2, -0.1, f.len, top, 0.2, render, { nz: false });
    const bays = Math.max(1, Math.round(f.len / 2.6));
    let y = g;
    heights.forEach((h) => {
      for (let i = 0; i < bays; i++) {
        const u = ((i + 0.5) * f.len) / bays;
        const on = rand() < c.lit;
        D.quadXYZ([u - 0.45, y + 0.5, 0.01, u + 0.45, y + 0.5, 0.01, u + 0.45, y + h * 0.78, 0.01, u - 0.45, y + h * 0.78, 0.01], on ? lit : pane);
        D.box(u, y + 0.46, 0.05, 1.0, 0.06, 0.1, sill);
      }
      y += h;
    });
    // the ground floor: a door, a low window
    D.quadXYZ([f.len * 0.3 - 0.5, 0, 0.01, f.len * 0.3 + 0.5, 0, 0.01, f.len * 0.3 + 0.5, 2.3, 0.01, f.len * 0.3 - 0.5, 2.3, 0.01], zoned(mix(INKS.green, INKS.ink, 0.45), 'out'));
    // a drainpipe down the wall
    D.bar(new Vector3(f.len * 0.85, 0, 0.08), new Vector3(f.len * 0.85, top, 0.08), 0.09, zinc);
    if (c.roofs) mansard(D, f.len, top, () => rand() < c.lit, lit, pane);
    D.pop();
  }
  // bins against the wall, green with their lids
  const bin = zoned(mix(INKS.green, INKS.ink, 0.2), 'out');
  const lid = zoned(mix(INKS.sunflower, INKS.ochre, 0.3), 'out');
  for (let i = 0; i < 2; i++) {
    const bx = c.x0 + 1.2 + i * 0.75;
    const bz = c.z0 + 0.55;
    D.box(bx, 0.5, bz, 0.6, 1.0, 0.7, bin, { ny: false });
    D.box(bx, 1.03, bz, 0.64, 0.06, 0.74, lid);
  }
  // a lamp over the courtyard door, and its pool on the cobbles
  B.lamps.push({ pos: new Vector3((c.x0 + c.x1) / 2, 2.8, c.z0 + 0.6), color: rgb(mix(INKS.sunflower, INKS.card, 0.2)), power: 0.7, range: 5.5, glint: true });
}

/**
 * A mansard over a side of a courtyard, in its frame (the courtyard on +w): the gutter, the steep
 * zinc brisis with a dormer a bay, the shallow terrasson behind it, and the chimney stacks with
 * their pots. What a top floor sees across the courtyard at night.
 */
function mansard(D: Press, len: number, top: number, on: () => boolean, lit: Paint, pane: Paint) {
  const zinc = zoned(TONES.zinc, 'out', { pattern: PATTERN.seams });
  const zincDark = zoned(TONES.zincDark, 'out', { pattern: PATTERN.seams });
  const cheek = zoned(TONES.zincDark, 'out');
  const stack = zoned(TONES.chimney, 'out');
  const pot = zoned(TONES.pot, 'out');
  const frame = zoned(mix(INKS.card, INKS.ochre, 0.12), 'out');
  const rise = 2.7;
  const back = 1.0;
  const crest = 3.4;
  const far = 4.2;
  D.box(len / 2, top + 0.06, 0.04, len, 0.12, 0.18, cheek);
  D.quadXYZ([0, top, 0, len, top, 0, len, top + rise, -back, 0, top + rise, -back], zinc);
  D.quadXYZ([0, top + rise, -back, len, top + rise, -back, len, top + crest, -far, 0, top + crest, -far], zincDark);
  const bays = Math.max(1, Math.round(len / 2.6));
  for (let i = 0; i < bays; i++) {
    const u = ((i + 0.5) * len) / bays;
    // the dormer: its cheeks in zinc, a painted frame round its window, a cap over it
    D.box(u, top + 1.05, -0.45, 1.1, 1.7, 0.5, cheek);
    D.quadXYZ([u - 0.45, top + 0.36, -0.195, u + 0.45, top + 0.36, -0.195, u + 0.45, top + 1.78, -0.195, u - 0.45, top + 1.78, -0.195], frame);
    D.quadXYZ([u - 0.34, top + 0.46, -0.19, u + 0.34, top + 0.46, -0.19, u + 0.34, top + 1.66, -0.19, u - 0.34, top + 1.66, -0.19], on() ? lit : pane);
    D.box(u, top + 1.95, -0.46, 1.24, 0.1, 0.62, zincDark);
  }
  // the stacks on the party walls, three pots each
  const stacks = Math.max(1, Math.round(len / 5.5));
  for (let k = 0; k < stacks; k++) {
    const u = ((k + 0.5) * len) / stacks + 0.6;
    D.box(u, top + 3.55, -2.6, 0.95, 1.3, 0.45, stack);
    D.box(u, top + 4.24, -2.6, 1.05, 0.08, 0.55, stack);
    for (let j = 0; j < 3; j++) D.cylinder(u - 0.3 + j * 0.3, top + 4.28, -2.6, 0.075, 0.09, 0.36, 8, pot);
  }
}

/* ------------------------------------------------------------------------------------------ */
/* the room                                                                                   */
/* ------------------------------------------------------------------------------------------ */

/** Is (x, z) inside the polygon? */
function inPoly(shape: XZ[], x: number, z: number) {
  let c = false;
  for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
    const [xi, zi] = shape[i];
    const [xj, zj] = shape[j];
    if (zi > z !== zj > z && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
}

/** The room's own floors and flights, the ground its lamps light. */
export function roomGround(spec: RoomSpec): XZ[][] {
  return spec.floors
    .filter((f) => (f.zone ?? 'room') === 'room')
    .map((f) => f.shape)
    .concat(spec.flights.map((F) => flightPlan(F).shape));
}

/** Lay the room into the build. */
export function buildRoom(B: Build, spec: RoomSpec): RoomBuilt {
  /* ---- floors and ceilings ----------------------------------------------------------------- */
  spec.floors.forEach((fl) => {
    const finish = FLOORS[fl.finish];
    const paint = zoned(finish.color, fl.zone, { pattern: finish.pattern });
    // a landing over the stairwell shows the thickness of its floor
    const thick = fl.y > 1 ? 0.32 : 0.2;
    B.dry.prism(fl.shape, fl.y - thick, fl.y, paint, { sides: fl.y > 1, bottom: fl.y > 1 });
    if ((fl.zone ?? 'room') === 'room' && fl.walk !== false) B.walk.push({ shape: fl.shape, y: fl.y });
  });
  spec.ceilings.forEach((c) => {
    B.dry.prism(c.shape, c.y, c.y + 0.05, zoned(mix(ROOM_TONES.cream, INKS.paper, 0.4), c.zone), { top: false, sides: false, bottom: true });
  });

  /* ---- walls, with the doors and windows that stand in them -------------------------------- */
  const holesOf = spec.walls.map((): Hole[] => []);
  const windowHoles = new Set<Hole>();
  spec.doors.forEach((d) => {
    const w = spec.walls[d.wall];
    const [b0] = pair(w.base);
    holesOf[d.wall].push({ u0: d.u0, u1: d.u1, y0: b0 - 0.01, y1: b0 + d.height });
  });
  spec.windows.forEach((win) => {
    const h = { u0: win.u0, u1: win.u1, y0: win.y0, y1: win.y1 };
    holesOf[win.wall].push(h);
    windowHoles.add(h);
  });
  const plainHoles = new Set<Hole>();
  (spec.holes ?? []).forEach((o) => {
    const h = { u0: o.u0, u1: o.u1, y0: o.y0, y1: o.y1 };
    holesOf[o.wall].push(h);
    plainHoles.add(h);
  });
  spec.walls.forEach((w, i) => buildWall(B.dry, w, holesOf[i], windowHoles, plainHoles));

  /* ---- the doors: their frames, their leaves on hinges, their mats ------------------------- */
  const doors: RoomBuilt['doors'] = [];
  spec.doors.forEach((d) => {
    const w = spec.walls[d.wall];
    const f = frameOf(w.a, w.b);
    const [b0] = pair(w.base);
    const zone = w.zone;
    B.dry.push(f.m);
    const frame = zoned(mix(toneOf(w.tone, ROOM_TONES.ochre), INKS.paper, 0.25), zone);
    architrave(B.dry, d.u0, d.u1, b0, b0 + d.height, frame);
    // the stop the leaf shuts against, on the side it does not swing to: no gap shows round it
    const stop = d.swing === 'out' ? -WALL + 0.09 : -0.09;
    B.dry.box(d.u0 + 0.012, b0 + d.height / 2, stop, 0.024, d.height, 0.02, frame);
    B.dry.box(d.u1 - 0.012, b0 + d.height / 2, stop, 0.024, d.height, 0.02, frame);
    B.dry.box((d.u0 + d.u1) / 2, b0 + d.height - 0.012, stop, d.u1 - d.u0, 0.024, 0.02, frame);
    if (d.mat) B.dry.box((d.u0 + d.u1) / 2, b0 + 0.01, 0.3, Math.min(0.8, d.u1 - d.u0 - 0.05), 0.02, 0.48, zoned(mix(INKS.ochre, INKS.ink, 0.42), zone, { pattern: PATTERN.ribs }), { ny: false });
    B.dry.pop();
    const wood = zoned(toneOf(d.tone, ROOM_TONES.brown), zone, { wet: 0.15 });
    const brass = zoned(TONES.brass, zone, { wet: 0.7 });
    const leaves: Array<[number, number, number]> =
      d.hinge === 'both'
        ? [
            [d.u0, 1, (d.u1 - d.u0) / 2],
            [d.u1, -1, (d.u1 - d.u0) / 2],
          ]
        : d.hinge === 'left'
          ? [[d.u0, 1, d.u1 - d.u0]]
          : [[d.u1, -1, d.u1 - d.u0]];
    leaves.forEach(([u, sign, width], k) => {
      const depth = d.swing === 'out' ? -WALL + 0.05 : -0.05;
      const p = new Vector3(u + sign * 0.01, b0, depth).applyMatrix4(f.m);
      doors.push({
        key: leaves.length > 1 ? `${d.key}:${k}` : d.key,
        leaf: doorLeaf(width - 0.02, d.height - 0.01, sign, wood, brass, k === 0 ? d.numeral : undefined),
        hinge: p,
        angle: Math.atan2(-f.t.z, f.t.x),
        sign,
        // a leaf swings toward the side it opens to: away from the room is -z in the wall's frame
        dir: d.swing === 'out' ? 1 : -1,
        max: 1.38,
      });
    });
  });

  /* ---- windows ---------------------------------------------------------------------------- */
  spec.windows.forEach((win) => {
    const w = spec.walls[win.wall];
    const f = frameOf(w.a, w.b);
    windowIn(B, B.dry, f, win, w.zone);
    if (win.shutters === 'closed') {
      const [b0] = pair(w.base);
      slatLight(B, f, win, b0, 4.2);
    }
  });

  /* ---- the stairs, the balustrades ------------------------------------------------------- */
  spec.flights.forEach((F) => {
    buildFlight(B, F);
    const plan = flightPlan(F);
    B.walk.push({ shape: plan.walk, y: plan.ramp });
  });
  spec.rails.forEach((r) => {
    const a = new Vector3(r.a[0], r.a[1], r.a[2]);
    const b = new Vector3(r.b[0], r.b[1], r.b[2]);
    balustrade(B, a, b, 'room');
    const len = Math.hypot(b.x - a.x, b.z - a.z) || 1;
    const nx = (-(b.z - a.z) / len) * 0.08;
    const nz = ((b.x - a.x) / len) * 0.08;
    B.blocks.push([[a.x - nx, a.z - nz], [b.x - nx, b.z - nz], [b.x + nx, b.z + nz], [a.x + nx, a.z + nz]]);
  });

  /* ---- lamps, the switches of their circuits -------------------------------------------- */
  // each lamp's pool is laid on the floor under it (a landing's lamp lights the landing)
  const floorUnder = (x: number, y: number, z: number) => Math.max(0, ...spec.floors.filter((f) => f.y < y && inPoly(f.shape, x, z)).map((f) => f.y));
  const bulbs: RoomBuilt['bulbs'] = spec.lights.map((L) => ({ key: L.key, circuit: L.circuit ?? null, ...lampOf(B, L, floorUnder(L.at[0], L.at[1], L.at[2])) }));
  spec.switches.forEach((s) => switchAt(B, s));

  /* ---- things, and the courtyards ------------------------------------------------------- */
  spec.things.forEach((t, i) => thing(B, t, i));
  spec.courts.forEach((c) => court(B, c));

  /* ---- where it all stands --------------------------------------------------------------- */
  const ground = roomGround(spec);
  const inside = (x: number, z: number) => ground.some((s) => inPoly(s, x, z) || nearPoly(s, x, z, 0.2));
  const pts: XZ[] = [
    ...spec.floors.flatMap((f) => f.shape),
    ...spec.walls.flatMap((w) => [w.a, w.b]),
    ...spec.courts.flatMap((c): XZ[] => [[c.x0, c.z0], [c.x1, c.z1]]),
    ...spec.flights.flatMap((F) => flightPlan(F).shape),
  ];
  const xs = pts.map((p) => p[0]);
  const zs = pts.map((p) => p[1]);
  const bounds = { x0: Math.min(...xs) - 2, z0: Math.min(...zs) - 2, x1: Math.max(...xs) + 2, z1: Math.max(...zs) + 2 };
  const shelter = spec.floors.filter((f) => (f.zone ?? 'room') !== 'out').flatMap((f) => f.shape).concat(spec.flights.flatMap((F) => flightPlan(F).shape));
  const sx = shelter.map((p) => p[0]);
  const sz = shelter.map((p) => p[1]);
  const marks: Record<string, Vector3> = {};
  Object.keys(spec.marks).forEach((k) => {
    const [x, y, z] = spec.marks[k];
    marks[k] = new Vector3(x, y, z);
  });
  const [px, pz] = spec.start.pos;
  return {
    spec,
    start: { pos: new Vector3(px, 0, pz), look: new Vector3(spec.start.look[0], spec.start.look[1], spec.start.look[2]) },
    marks,
    doors,
    bulbs,
    openings: spec.doors.map((d) => {
      const w = spec.walls[d.wall];
      const f = frameOf(w.a, w.b);
      const [b0] = pair(w.base);
      const u = (d.u0 + d.u1) / 2;
      return { key: d.key, opens: d.opens ?? 'never', centre: new Vector3(u, b0 + 1.45, 0.02).applyMatrix4(f.m), front: new Vector3(u, b0, 0.7).applyMatrix4(f.m) };
    }),
    switches: spec.switches.map((s) => ({ key: s.key, circuit: s.circuit, at: new Vector3(s.at[0], s.at[1], s.at[2]), facing: new Vector3(s.facing[0], 0, s.facing[1]).normalize() })),
    inside,
    bounds,
    dry: [Math.min(...sx) - 0.4, Math.min(...sz) - 0.4, Math.max(...sx) + 0.4, Math.max(...sz) + 0.4],
  };
}

/** Is (x, z) within `r` of the polygon's outline? */
function nearPoly(shape: XZ[], x: number, z: number, r: number) {
  for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
    const [ax, az] = shape[j];
    const [bx, bz] = shape[i];
    const dx = bx - ax;
    const dz = bz - az;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1)));
    if (Math.hypot(x - (ax + dx * t), z - (az + dz * t)) < r) return true;
  }
  return false;
}
