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

import { KERB, WALLS, bench, building, chair, frameOf, planeTree, quayLamp } from './kit';
import type { Build, Frame, Shop } from './kit';
import { LACE, PATTERN, Press, nextId } from './geo';
import type { Paint, PatternId } from './geo';
import type { Words } from './memory';
import { AMBIANCES, INKS, TONES, css, mix, rgb } from './palette';
import type { AmbianceId, Hex } from './palette';
import { PLAN } from './quai';
import { SANS, SERIF } from './signs';

type XZ = [number, number];
type XYZ = [number, number, number];

/** The room itself, what is seen but not entered yet, and what is outside. */
export type Zone = 'room' | 'sealed' | 'out';

export type FloorFinish = 'cabochons' | 'boards' | 'parquet' | 'tomettes' | 'cobbles' | 'stone' | 'zinc';
export type WallFinish = 'wainscot' | 'plaster' | 'stone';

export interface RoomFloor {
  key: string;
  shape: XZ[];
  y: number;
  finish: FloorFinish;
  zone?: Zone;
  /** seen, not walked */
  walk?: boolean;
  /** false: the quarter already lays this ground (a street of the quai): walked, not drawn again */
  drawn?: boolean;
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
  /** closed: the shutters outside, the street light through their slats in bars; open: folded back against the façade */
  shutters?: 'closed' | 'open';
  /** a French window's iron guard outside it, a metre high, where the glass comes down to the floor */
  guard?: boolean;
  /** a narrow balcony outside it, this deep: its stone slab on two consoles, its ironwork */
  balcony?: number;
  /** the morning sun through it: its panes laid on the floor, the dust in the beam */
  sun?: boolean;
}

export interface RoomLight {
  key: string;
  /** a globe on its cord (Le Mistral's), a glass bowl on a wall bracket, a round lamp flat on the wall,
   * a desk lamp (`at` its shade's mouth, `facing` the way it leans, its foot behind) */
  kind: 'globe' | 'sconce' | 'hublot' | 'desk';
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
  | 'kitchenette'
  | 'longtable'
  | 'armchair'
  | 'pen'
  | 'folder'
  | 'bookcase'
  | 'polaroids'
  | 'armoire'
  | 'drink'
  | 'skylight'
  | 'chimney'
  | 'edge'
  | 'easel'
  | 'crates'
  | 'board'
  | 'plan'
  | 'fridge'
  | 'crate'
  | 'canvas'
  | 'intercom'
  | 'gaze'
  | 'keyboard'
  | 'cabinet'
  | 'desk'
  | 'campbed'
  | 'frame';

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

/**
 * The quai de Valmy under a window on its façade, and the canal: our pavement, the road, the
 * strip of setts with its plane trees and lamps, the quay wall down to the water, and across it
 * the quai de Jemmapes with its houses. The quai's own plan (`quai.ts`), from z0 to z1.
 */
export interface RoomCanal {
  z0: number;
  z1: number;
  /** the houses across the water */
  storeys: number;
  seed: number;
  /** share of the far windows lit (none by day) */
  lit?: number;
}

/**
 * A boulevard seen from a window over it: the pavement under our façade, the roadway, the far
 * pavement, plane trees and lamps along both kerbs, and the stone houses across it with their
 * shops, balconies and mansards (the quai's own `building`).
 */
export interface RoomBoulevard {
  /** our façade's line: along x from x0 to x1, at z */
  x0: number;
  x1: number;
  z: number;
  /** the way the boulevard lies from our façade */
  side: 'n' | 's';
  /** façade to façade */
  width: number;
  storeys: number;
  seed: number;
  /** share of the far windows lit (none by day) */
  lit?: number;
  /** a stretch of our own kerb with no tree in it, so the windows over it see down to the street */
  clear?: [number, number];
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
  holes?: Array<{ wall: number; u0: number; u1: number; y0: number; y1: number; framed?: boolean }>;
  rails: RoomRail[];
  lights: RoomLight[];
  switches: RoomSwitch[];
  /** how many seconds a press keeps a circuit lit */
  timers: Record<string, number>;
  things: RoomThing[];
  courts: RoomCourt[];
  boulevards?: RoomBoulevard[];
  canals?: RoomCanal[];
  /**
   * The room stands in the quarter's own build (the quai, the canal, Le Mistral's building and its
   * neighbours): a room on Le Mistral's roof sees the quai as it is, from above.
   */
  quarter?: boolean;
  /** where the stage stands you and the cast */
  marks: Record<string, XYZ>;
  /**
   * The ways through the room the walking grid cannot hold: the climb past a storey (the grid is
   * one sheet, so no landing lies over another), a door into the flat. You stand at one end and
   * tap to be at the other; `door` swings that leaf as you go, and `until: 'story'` keeps it shut
   * until the learner's story has played here (`playedHere` in `world.ts`).
   */
  passages?: RoomPassage[];
  provenance: { canon: string; place: string; scenes: string[]; brief_round?: number };
}

export interface RoomPassage {
  key: string;
  a: XZ;
  b: XZ;
  look_a?: XYZ;
  look_b?: XYZ;
  /** what the button says at `a` (going to `b`), and at `b` */
  to_b: Words;
  to_a: Words;
  door?: string;
  until?: 'story';
  /** said when it is shut */
  shut?: Words;
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
  /** a polished table, waxed walnut */
  walnut: mix(mix(TONES.wood, INKS.ink, 0.38), INKS.vermilion, 0.06),
  /** an office chair's leather, oxblood gone brown */
  leather: mix(mix(TONES.oxblood, INKS.ochre, 0.25), INKS.ink, 0.2),
  /** a sealed flat's paper walls, a little dust-cobalt in them */
  dust: mix(mix(INKS.paper, INKS.cobalt, 0.1), INKS.card, 0.25),
  /** a made bed's counterpane, white cotton gone cream */
  counterpane: mix(INKS.card, INKS.ochre, 0.1),
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
  /** an old office's parquet, waxed dark and gone cold */
  parquet: { color: mix(mix(TONES.wood, INKS.ink, 0.38), INKS.cobalt, 0.08), pattern: PATTERN.planks },
  /** a kitchen's red tiles */
  tomettes: { color: mix(mix(INKS.vermilion, INKS.ochre, 0.5), INKS.paper, 0.3), pattern: PATTERN.tiles },
  cobbles: { color: mix(TONES.stoneGround, INKS.cobalt, 0.08), pattern: PATTERN.cobbles },
  stone: { color: TONES.stone, pattern: PATTERN.flags },
  /** a roof's zinc, its standing seams */
  zinc: { color: mix(TONES.zinc, INKS.ink, 0.12), pattern: PATTERN.seams },
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
  if (win.guard) {
    // the garde-corps: a top rail and a bottom rail across the opening outside, square bars
    // between them and a band of rings a hand's width under the top
    P.push(f.m);
    const iron = zoned(TONES.iron, 'out');
    const out = -WALL - 0.05;
    const top = y0 + 1.0;
    P.box((u0 + u1) / 2, top, out, u1 - u0, 0.04, 0.04, iron);
    P.box((u0 + u1) / 2, y0 + 0.08, out, u1 - u0, 0.03, 0.03, iron);
    P.box((u0 + u1) / 2, top - 0.2, out, u1 - u0, 0.015, 0.015, iron);
    const bars = Math.max(3, Math.round((u1 - u0) / 0.11));
    for (let k = 1; k < bars; k++) P.box(u0 + ((u1 - u0) * k) / bars, (y0 + top) / 2, out, 0.014, top - y0, 0.014, iron);
    for (let k = 0; k < bars; k++) P.ball(u0 + ((u1 - u0) * (k + 0.5)) / bars, top - 0.1, out, 0.035, 0.035, 0.008, iron, 0);
    P.pop();
  }
  if (win.shutters === 'open') {
    // the persiennes folded back flat against the façade, a leaf each side of the opening
    P.push(f.m);
    const slat = zoned(TONES.shutter, 'out', { pattern: PATTERN.ribs });
    const edge = zoned(mix(TONES.shutter, INKS.ink, 0.25), 'out');
    const leaf = (u1 - u0) / 2;
    for (const [a, b] of [[u0 - leaf - 0.04, u0 - 0.04], [u1 + 0.04, u1 + leaf + 0.04]]) {
      P.box((a + b) / 2, (y0 + y1) / 2, -WALL - 0.03, b - a, y1 - y0, 0.03, slat);
      P.box((a + b) / 2, y0 + (y1 - y0) * 0.45, -WALL - 0.05, b - a, 0.05, 0.012, edge);
    }
    P.pop();
  }
}

/**
 * A narrow balcony outside a French window (`win.balcony` deep): the stone slab at the floor's
 * level on two consoles, and the quai's own ironwork round its three sides.
 */
function balconyOut(B: Build, f: Frame, win: RoomWindow, floor: number) {
  const out = win.balcony ?? 0;
  if (out <= 0) return;
  const u0 = win.u0 - 0.3;
  const u1 = win.u1 + 0.3;
  const slab = zoned(mix(TONES.stone, INKS.paper, 0.2), 'out');
  const con = zoned(mix(TONES.stone, INKS.ink, 0.06), 'out');
  B.dry.push(f.m);
  B.dry.box((u0 + u1) / 2, floor - 0.06, -WALL - out / 2, u1 - u0, 0.14, out, slab);
  for (const cu of [u0 + 0.18, u1 - 0.18]) B.dry.box(cu, floor - 0.32, -WALL - 0.2, 0.14, 0.34, 0.4, con, { pz: false });
  B.dry.pop();
  const id = nextId();
  B.lace.push(f.m);
  const w = -WALL - out + 0.03;
  B.lace.panel(new Vector3(u1, floor, w), new Vector3(u0, floor, w), 1.0, LACE.balcony, id);
  B.lace.panel(new Vector3(u0 + 0.02, floor, w), new Vector3(u0 + 0.02, floor, -WALL), 1.0, LACE.balcony, id);
  B.lace.panel(new Vector3(u1 - 0.02, floor, -WALL), new Vector3(u1 - 0.02, floor, w), 1.0, LACE.balcony, id);
  B.lace.pop();
}

/**
 * The sun through a window, laid on the floor: each pane's light where the ray from the sky
 * meets the boards (the floor's own finish, lit), the bars between them in shadow.
 */
function sunThrough(B: Build, f: Frame, win: RoomWindow, floor: number, finish: FloorFinish, from: [number, number, number]) {
  const d = new Vector3(-from[0], -from[1], -from[2]).normalize();
  // the room is on +w of the wall's frame: the sun must come in through the glass, and down
  const inward = new Vector3(0, 0, 1).transformDirection(f.m);
  if (d.dot(inward) <= 0.05 || d.y >= -0.05) return;
  // the floor's own boards or tiles, in the sun: their pattern goes on under the light
  const light: Paint = { color: mix(mix(FLOORS[finish].color, INKS.sunflower, 0.35), INKS.card, 0.3), pattern: FLOORS[finish].pattern, glow: 0.45, id: nextId() };
  const onFloor = (u: number, y: number) => {
    const p = new Vector3(u, y, 0).applyMatrix4(f.m);
    return p.addScaledVector(d, (p.y - floor) / -d.y).setY(floor + 0.007);
  };
  const { u0, u1, y0, y1 } = win;
  const rows = Math.max(2, Math.round((y1 - y0) / 0.62));
  const mid = (u0 + u1) / 2;
  for (const [a, b] of [[u0 + 0.07, mid - 0.04], [mid + 0.04, u1 - 0.07]]) {
    for (let k = 0; k < rows; k++) {
      const ya = y0 + 0.09 + ((y1 - y0 - 0.15) * k) / rows + 0.02;
      const yb = y0 + 0.09 + ((y1 - y0 - 0.15) * (k + 1)) / rows - 0.02;
      B.dry.quad(onFloor(a, ya), onFloor(b, ya), onFloor(b, yb), onFloor(a, yb), light);
    }
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
  if (L.kind === 'desk') {
    // a desk lamp: its round foot on the desk behind, the arm up and over, a green shade tipped
    // down at the papers, the bulb's glow in its mouth
    const shade = zoned(mix(INKS.green, INKS.ink, 0.3), 'room', { wet: 0.5 });
    B.dry.at(at.x, at.y, at.z, rot, () => {
      B.dry.cylinder(0, -0.42, -0.24, 0.085, 0.095, 0.025, 14, brass, { flat: true, caps: true });
      B.dry.bar(new Vector3(0, -0.4, -0.24), new Vector3(0, 0.06, -0.18), 0.012, brass);
      B.dry.bar(new Vector3(0, 0.06, -0.18), new Vector3(0, 0.07, -0.03), 0.012, brass);
      B.dry.lathe(0, -0.02, 0, [[0.12, 0], [0.1, 0.05], [0.05, 0.11], [0.015, 0.13], [0, 0.13]], 14, shade);
    });
    for (const [P, g] of [[lit, glassLit], [dark, glassDark]] as Array<[Press, Paint]>) {
      P.at(at.x, at.y, at.z, rot, () => P.ball(0, 0.0, 0, 0.045, 0.03, 0.045, g, 1, { smooth: true }));
    }
    B.lamps.push({ pos: new Vector3(at.x, at.y - floor, at.z), color: rgb(mix(INKS.sunflower, INKS.card, 0.15)), power: L.power, range: L.range, glint: false, indoor: true });
    return { lit, dark };
  }
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

/** Lay one thing into the build (a room's, or a detail's in Le Mistral: `details.ts`). */
export function buildThing(B: Build, t: RoomThing, i: number) {
  thing(B, t, i);
}

/** What a cup holds, by the order in `text` («un café crème», «un noisette», «un thé», «un chocolat chaud»). */
function drinkOf(order: string) {
  const o = order.toLowerCase();
  if (/chocolat/.test(o)) return { cup: 'large' as const, top: mix(mix(INKS.ochre, INKS.ink, 0.62), INKS.vermilion, 0.08), tag: false };
  if (/th[ée]|infusion|tisane/.test(o)) return { cup: 'tea' as const, top: mix(mix(INKS.ochre, INKS.vermilion, 0.4), INKS.ink, 0.42), tag: true };
  if (/noisette|express|espresso|^(un )?(petit )?café( serré)?$/.test(o.trim())) return { cup: 'small' as const, top: /noisette/.test(o) ? mix(mix(INKS.ochre, INKS.ink, 0.45), INKS.card, 0.2) : mix(INKS.ochre, INKS.ink, 0.6), tag: false };
  return { cup: 'wide' as const, top: mix(mix(INKS.ochre, INKS.ink, 0.3), INKS.card, 0.42), tag: false };
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
      // the rim lies out from the wall, the dial printed on its face
      D.at(x, y, zz, rot, () => {
        D.push(new Matrix4().makeRotationX(Math.PI / 2));
        D.cylinder(0, 0, 0, 0.16, 0.16, 0.045, 16, rim, { flat: true, caps: true });
        D.pop();
      });
      const r0 = new Vector3(Math.sin(rot), 0, Math.cos(rot));
      card(B, key, [x + r0.x * 0.04, y, zz + r0.z * 0.04], rot, 0.28, 0.28, z, clockFaceArt(t.text?.[0] ?? '3:40'), 900);
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
    case 'longtable': {
      // a notary's table, long and waxed: the top with its sheen, the apron under it, four turned
      // legs (`at` is its middle; `size` its length and its width)
      const [w, d] = t.size ?? [2.2, 1.05];
      const tone = toneOf(t.tone, ROOM_TONES.walnut);
      const top = zoned(tone, z, { wet: 0.55 });
      const wood = zoned(mix(tone, INKS.ink, 0.12), z, { wet: 0.25 });
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.74, 0, w, 0.04, d, top);
        D.box(0, 0.67, 0, w - 0.16, 0.1, d - 0.16, wood, { py: false });
        for (const [lx, lz] of [[-w / 2 + 0.11, -d / 2 + 0.11], [w / 2 - 0.11, -d / 2 + 0.11], [-w / 2 + 0.11, d / 2 - 0.11], [w / 2 - 0.11, d / 2 - 0.11]] as Array<[number, number]>) {
          D.lathe(lx, 0, lz, [[0.032, 0], [0.026, 0.08], [0.042, 0.16], [0.028, 0.3], [0.026, 0.56], [0.04, 0.6], [0.04, 0.62], [0, 0.62]], 8, wood);
        }
      });
      B.blocks.push(centred(x, zz, rot, w + 0.08, d + 0.08));
      return;
    }
    case 'armchair': {
      // an office armchair: a wooden frame, the seat and the back in buttoned leather, open arms
      const wood = zoned(toneOf(undefined, ROOM_TONES.walnut), z, { wet: 0.25 });
      const hide = zoned(toneOf(t.tone, ROOM_TONES.leather), z, { wet: 0.2 });
      const seam = zoned(mix(toneOf(t.tone, ROOM_TONES.leather), INKS.ink, 0.35), z);
      D.at(x, y, zz, rot, () => {
        for (const [lx, lz] of [[-0.23, -0.2], [0.23, -0.2], [-0.23, 0.2], [0.23, 0.2]] as Array<[number, number]>) D.box(lx, 0.2, lz, 0.045, 0.4, 0.045, wood, { ny: false });
        D.box(0, 0.42, 0, 0.52, 0.06, 0.48, wood);
        D.box(0, 0.48, 0.01, 0.48, 0.07, 0.44, hide);
        // the back, leaning a little, with its row of buttons
        D.push(new Matrix4().makeTranslation(0, 0.5, -0.22).multiply(new Matrix4().makeRotationX(-0.12)));
        D.box(0, 0.27, 0, 0.5, 0.52, 0.05, wood);
        D.box(0, 0.27, 0.035, 0.44, 0.44, 0.04, hide);
        for (const bx of [-0.12, 0, 0.12]) D.ball(bx, 0.3, 0.057, 0.012, 0.012, 0.006, seam, 0);
        D.pop();
        // the arms, on their posts
        for (const sx of [-0.27, 0.27]) {
          D.box(sx, 0.68, -0.02, 0.05, 0.035, 0.42, wood);
          D.box(sx, 0.56, 0.16, 0.035, 0.22, 0.035, wood, { ny: false });
        }
      });
      B.blocks.push(centred(x, zz, rot, 0.6, 0.6));
      return;
    }
    case 'pen': {
      // a fountain pen lying on the table, capped: the black barrel, the cap with its gold band and
      // clip, the end of the nib showing (a little larger than life, so a phone shows it)
      const k = 1.3;
      const lacquer = zoned(mix(INKS.ink, INKS.cobalt, 0.08), z, { wet: 0.8 });
      const gold = zoned(TONES.brass, z, { wet: 0.8 });
      D.at(x, y, zz, rot, () => {
        D.push(new Matrix4().makeScale(k, k, k));
        D.bar(new Vector3(-0.072, 0.006, 0), new Vector3(0.0, 0.006, 0), 0.011, lacquer);
        D.bar(new Vector3(0.0, 0.0065, 0), new Vector3(0.064, 0.0065, 0), 0.013, lacquer);
        D.bar(new Vector3(-0.0005, 0.0065, 0), new Vector3(0.0035, 0.0065, 0), 0.0135, gold);
        D.bar(new Vector3(0.012, 0.0135, 0), new Vector3(0.056, 0.0135, 0), 0.003, gold);
        D.bar(new Vector3(-0.072, 0.006, 0), new Vector3(-0.08, 0.005, 0), 0.006, gold);
        D.pop();
      });
      return;
    }
    case 'folder': {
      // a closed dossier, buff card with its strap, and on its cover the label: what it is about
      const buff = zoned(mix(INKS.ochre, INKS.paper, 0.55), z);
      const strap = zoned(mix(INKS.ink, INKS.cobalt, 0.2), z);
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.007, 0, 0.33, 0.014, 0.245, buff, { ny: false });
        D.box(0.1, 0.0145, 0, 0.012, 0.002, 0.25, strap);
      });
      const lean = 0.06;
      const n = new Vector3(Math.sin(rot) * Math.sin(lean), Math.cos(lean), Math.cos(rot) * Math.sin(lean));
      const side = new Vector3(Math.cos(rot), 0, -Math.sin(rot));
      const c = new Vector3(x, y + 0.0152, zz).addScaledVector(side, -0.04);
      B.signs.push({ key, center: c, normal: n, width: 0.19, height: 0.06, density: 1800, draw: labelArt(t.text?.[0] ?? ''), indoor: (z ?? 'room') === 'room' });
      return;
    }
    case 'bookcase': {
      // shelves from a cupboard to the cornice, against the wall: law in bound volumes, the
      // spines in their reds, greens and blacks, no titles (`size` its width and its height)
      const [w, h] = t.size ?? [1.8, 2.7];
      const dd = 0.38;
      const wood = zoned(toneOf(t.tone, ROOM_TONES.walnut), z, { wet: 0.2 });
      const back = zoned(mix(toneOf(t.tone, ROOM_TONES.walnut), INKS.ink, 0.35), z);
      const spines = [TONES.oxblood, mix(INKS.green, INKS.ink, 0.35), mix(INKS.cobalt, INKS.ink, 0.4), mix(INKS.ink, INKS.ochre, 0.15), mix(INKS.ochre, INKS.paper, 0.35), mix(INKS.vermilion, INKS.ink, 0.25)].map((c) => zoned(c, z));
      const R = { v: 7919 + i * 131 };
      const rand = () => {
        R.v = (R.v * 16807) % 2147483647;
        return R.v / 2147483647;
      };
      const base = 0.86;
      D.at(x, y, zz, rot, () => {
        D.box(0, h / 2, 0.01, w, h, 0.02, back);
        for (const sx of [-w / 2 + 0.015, w / 2 - 0.015]) D.box(sx, h / 2, dd / 2, 0.03, h, dd, wood);
        D.box(0, h + 0.04, dd / 2 + 0.02, w + 0.08, 0.08, dd + 0.04, wood);
        // the cupboard under the shelves, its doors panelled
        D.box(0, base / 2, dd / 2 + 0.02, w, base, dd, wood, { ny: false });
        const doors = Math.max(2, Math.round(w / 0.6));
        for (let k = 0; k < doors; k++) {
          const cu = -w / 2 + ((k + 0.5) * w) / doors;
          D.box(cu, base / 2, dd + 0.025, w / doors - 0.08, base - 0.16, 0.012, back);
        }
        const rows = Math.max(1, Math.floor((h - base - 0.05) / 0.37));
        const pitch = (h - base) / rows;
        for (let r = 0; r < rows; r++) {
          const sy = base + r * pitch;
          D.box(0, sy + 0.012, dd / 2, w - 0.06, 0.025, dd - 0.02, wood);
          let u = -w / 2 + 0.04;
          while (u < w / 2 - 0.08) {
            const bw = 0.028 + rand() * 0.035;
            if (rand() < 0.06) {
              u += bw * 2;
              continue;
            }
            const bh = Math.min(pitch - 0.06, 0.24 + rand() * 0.08);
            D.box(u + bw / 2, sy + 0.025 + bh / 2, dd / 2 + 0.04, bw - 0.003, bh, 0.24, spines[Math.floor(rand() * spines.length)], { ny: false });
            u += bw;
          }
        }
      });
      B.blocks.push(footprint(x, zz, rot, w + 0.04, dd + 0.06));
      return;
    }
    case 'polaroids': {
      // a shoebox pulled out from under the bed, its lid off beside it, and the instant photos
      // spilled out of it across the boards: white frames, the picture a little dark in each
      // (`at` the box; the photos fall in front of it, `size` the spill's width and depth)
      const [sw, sd] = t.size ?? [1.1, 0.8];
      const box = zoned(mix(INKS.card, INKS.ochre, 0.3), z);
      const inner = zoned(mix(INKS.ochre, INKS.ink, 0.35), z);
      const frame = zoned(mix(INKS.card, INKS.paper, 0.2), z);
      const pictures = [mix(INKS.ochre, INKS.ink, 0.4), mix(INKS.green, INKS.ink, 0.45), mix(INKS.cobalt, INKS.ink, 0.45), mix(INKS.vermilion, INKS.ink, 0.5), mix(INKS.sunflower, INKS.ink, 0.45)].map((c) => zoned(c, z));
      const R = { v: 4421 + i * 37 };
      const rand = () => {
        R.v = (R.v * 16807) % 2147483647;
        return R.v / 2147483647;
      };
      D.at(x, y, zz, rot, () => {
        D.box(0, 0.06, 0, 0.34, 0.12, 0.2, box, { ny: false });
        D.box(0, 0.121, 0, 0.31, 0.003, 0.17, inner);
        // a few still standing in the box, their tops showing
        for (let k = 0; k < 5; k++) D.box(-0.12 + k * 0.06, 0.13, -0.01 + (rand() - 0.5) * 0.04, 0.012, 0.05, 0.1, frame);
        // the lid, upside down on the floor beside it
        D.push(new Matrix4().makeTranslation(-0.32, 0, 0.08).multiply(new Matrix4().makeRotationY(0.35)));
        D.box(0, 0.02, 0, 0.35, 0.04, 0.21, box, { ny: false });
        D.pop();
        for (let k = 0; k < 16; k++) {
          const px = (rand() - 0.5) * sw;
          const pz = 0.16 + rand() * sd;
          const a = rand() * Math.PI * 2;
          const lift = 0.002 + k * 0.0006;
          D.push(new Matrix4().makeTranslation(px, lift, pz).multiply(new Matrix4().makeRotationY(a)));
          D.box(0, 0.001, 0, 0.088, 0.002, 0.107, frame, { ny: false });
          D.box(0, 0.0025, -0.009, 0.078, 0.001, 0.078, pictures[Math.floor(rand() * pictures.length)]);
          D.pop();
        }
      });
      B.blocks.push(centred(x, zz, rot, 0.38, 0.24));
      return;
    }
    case 'drink': {
      // the learner's usual on its saucer, a spoon beside the cup and a wrapped sugar: the cup by
      // what it holds (a wide café crème, a small noisette, tea with its tag over the rim, a big
      // chocolat), its handle to your right (`text` the order, `rot` the side it is served to)
      const d = drinkOf(t.text?.[0] ?? '');
      const porcelain = zoned(INKS.card, z, { wet: 0.6 });
      const top = zoned(d.top, z, { wet: 0.4 });
      const steel = zoned(mix(INKS.paper, INKS.ink, 0.3), z, { wet: 0.8 });
      const paper = zoned(mix(INKS.card, INKS.vermilion, 0.12), z);
      const [r, h] = d.cup === 'small' ? [0.032, 0.05] : d.cup === 'large' ? [0.055, 0.08] : d.cup === 'tea' ? [0.045, 0.06] : [0.049, 0.068];
      const sr = d.cup === 'small' ? 0.06 : 0.08;
      D.at(x, y, zz, rot, () => {
        D.lathe(0, 0, 0, [[sr - 0.005, 0], [sr, 0.008], [sr * 0.8, 0.011], [0, 0.012]], 16, porcelain);
        D.lathe(0, 0.012, 0, [[r * 0.55, 0], [r * 0.82, 0.012], [r * 0.96, h * 0.72], [r, h], [r * 0.9, h], [r * 0.8, h * 0.35], [0, h * 0.3]], 16, porcelain);
        D.lathe(0, 0.012 + h - 0.009, 0, [[r * 0.89, 0], [0, 0.001]], 16, top);
        // the handle, on the right as it is served
        const hx = r + 0.002;
        D.sweep(new Vector3(hx, 0.012 + h * 0.8, 0), new Vector3(hx + 0.022, 0.012 + h * 0.6, 0), [[-0.005, -0.005], [0.005, -0.005], [0.005, 0.005], [-0.005, 0.005]], porcelain, { closed: true });
        D.sweep(new Vector3(hx + 0.022, 0.012 + h * 0.6, 0), new Vector3(hx, 0.012 + h * 0.3, 0), [[-0.005, -0.005], [0.005, -0.005], [0.005, 0.005], [-0.005, 0.005]], porcelain, { closed: true });
        // the spoon on the saucer, in front of the cup, and the sugar in its paper
        D.box(0.005, 0.014, sr - 0.022, 0.07, 0.003, 0.008, steel);
        D.ball(-0.036, 0.015, sr - 0.022, 0.012, 0.003, 0.009, steel, 0);
        D.box(-sr - 0.03, 0.006, 0.01, 0.028, 0.012, 0.02, paper, { ny: false });
        if (d.tag) {
          // the tea bag's string over the rim, its paper tag hanging on the outside
          D.bar(new Vector3(-r * 0.5, 0.012 + h - 0.004, 0), new Vector3(-r - 0.002, 0.012 + h + 0.004, 0), 0.0012, paper);
          D.bar(new Vector3(-r - 0.002, 0.012 + h + 0.004, 0), new Vector3(-r - 0.004, 0.012 + h * 0.55, 0), 0.0012, paper);
          D.box(-r - 0.006, 0.012 + h * 0.45, 0, 0.004, 0.026, 0.02, paper);
        }
      });
      return;
    }
    case 'skylight': {
      // a tabatière in the zinc over the stairs: its curb, the glazed lid propped open and laid
      // back, the top of the iron ladder coming up through it, and the stairwell's light below
      const [w, l] = t.size ?? [0.7, 0.9];
      const curb = zoned(mix(TONES.zinc, INKS.ink, 0.25), z);
      const frame = zoned(mix(TONES.zincDark, INKS.ink, 0.2), z, { wet: 0.5 });
      const pane = zoned(TONES.pane, z, { wet: 0.8 });
      const iron = zoned(TONES.iron, z);
      const below: Paint = { color: mix(INKS.sunflower, INKS.card, 0.35), glow: 0.85, id: nextId() };
      const ch = 0.14;
      const lean = 1.3; // the lid's angle from the zinc, laid back past upright
      D.at(x, y, zz, rot, () => {
        // the curb round the opening; the zinc runs under it, so the opening is the stairwell's
        // light coming up, a hand's breadth down inside the curb
        D.box(0, ch / 2, -l / 2 - 0.03, w + 0.12, ch, 0.06, curb);
        D.box(0, ch / 2, l / 2 + 0.03, w + 0.12, ch, 0.06, curb);
        D.box(-w / 2 - 0.03, ch / 2, 0, 0.06, ch, l, curb);
        D.box(w / 2 + 0.03, ch / 2, 0, 0.06, ch, l, curb);
        D.quadXYZ([-w / 2, 0.03, -l / 2, w / 2, 0.03, -l / 2, w / 2, 0.03, l / 2, -w / 2, 0.03, l / 2], below);
        // the lid on its hinge at the back, glass in an iron frame, and the stay that holds it
        const hy = ch;
        const hz = -l / 2 - 0.03;
        const fy = hy + Math.sin(lean) * l;
        const fz = hz + Math.cos(lean) * l;
        const corners = [new Vector3(-w / 2 - 0.04, hy, hz), new Vector3(w / 2 + 0.04, hy, hz), new Vector3(w / 2 + 0.04, fy, fz), new Vector3(-w / 2 - 0.04, fy, fz)];
        const flat = (ps: Vector3[]) => ps.flatMap((p) => [p.x, p.y, p.z]);
        D.quadXYZ(flat(corners), pane);
        D.quadXYZ(flat([corners[1], corners[0], corners[3], corners[2]]), pane);
        for (let k = 0; k < 4; k++) D.bar(corners[k], corners[(k + 1) % 4], 0.035, frame);
        D.bar(new Vector3(0, hy, hz), new Vector3(0, fy, fz), 0.02, frame);
        D.bar(new Vector3(w / 2 + 0.06, ch, l / 4), new Vector3(w / 2 + 0.06, (hy + fy) / 2, (hz + fz) / 2), 0.012, iron);
        // the ladder's stiles and its top rungs, up out of the opening
        for (const s of [-1, 1]) D.bar(new Vector3(s * 0.2, 0.03, l / 2 - 0.14), new Vector3(s * 0.2, 0.6, l / 2 - 0.2), 0.03, iron);
        for (const ry of [0.22, 0.5]) D.bar(new Vector3(-0.2, ry, l / 2 - 0.14 - ry * 0.1), new Vector3(0.2, ry, l / 2 - 0.14 - ry * 0.1), 0.02, iron);
      });
      B.blocks.push(centred(x, zz, rot, w + 0.24, l + 0.5));
      return;
    }
    case 'chimney': {
      // a stack of rendered brick on the zinc, its coping, a row of clay pots (as the quai's own)
      const [long, h] = t.size ?? [1.8, 1.5];
      const deep = 0.75;
      const stack = zoned(TONES.chimney, z);
      const cap = zoned(mix(TONES.chimney, INKS.paper, 0.3), z);
      const flash = zoned(mix(TONES.zinc, INKS.ink, 0.2), z);
      const pot = zoned(TONES.pot, z);
      D.at(x, y, zz, rot, () => {
        D.box(0, h / 2 - 0.05, 0, long, h + 0.1, deep, stack, { ny: false });
        D.box(0, h + 0.06, 0, long + 0.1, 0.12, deep + 0.1, cap);
        // the zinc flashing where it meets the roof
        D.box(0, 0.04, 0, long + 0.08, 0.08, deep + 0.08, flash, { ny: false });
        const pots = Math.max(2, Math.round(long / 0.38));
        for (let p = 0; p < pots; p++) {
          const px = -long / 2 + 0.22 + (p * (long - 0.44)) / Math.max(1, pots - 1);
          D.cylinder(px, h + 0.12, 0, 0.11, 0.085, 0.4 + 0.18 * ((p * 7) % 3) * 0.5, 6, pot, { flat: true });
        }
      });
      B.blocks.push(centred(x, zz, rot, long + 0.2, deep + 0.2));
      return;
    }
    case 'edge': {
      // where the flat of the roof ends and the mansard falls away: the zinc's rolled edge
      const [len] = t.size ?? [3, 0];
      const roll = zoned(mix(TONES.zinc, INKS.paper, 0.15), z, { wet: 0.5 });
      D.at(x, y, zz, rot, () => {
        D.bar(new Vector3(-len / 2, 0.03, 0), new Vector3(len / 2, 0.03, 0), 0.06, roll);
      });
      return;
    }
    case 'easel': {
      // a painter's easel, its canvas under a white sheet: the sheet thrown over the top and
      // falling in folds to the ledge and below it, the easel's mast up out of it (`size` the
      // canvas's width and height)
      const [cw, ch] = t.size ?? [1.0, 0.8];
      const wood = zoned(mix(TONES.wood, INKS.ochre, 0.25), z);
      if (cw <= 0) {
        // `size` [0, 0]: the easel with nothing on it, its canvas packed (paint on the ledge)
        const daub = [INKS.ochre, INKS.cobalt, INKS.vermilion].map((c) => zoned(c, z));
        const ledgeY = 0.72;
        const topY = 1.62;
        D.at(x, y, zz, rot, () => {
          D.bar(new Vector3(0, 0, -0.62), new Vector3(0, topY - 0.1, -0.06), 0.022, wood);
          D.push(new Matrix4().makeTranslation(0, 0, 0.1).multiply(new Matrix4().makeRotationX(-0.1)));
          for (const s of [-1, 1]) D.bar(new Vector3(s * 0.34, 0, 0), new Vector3(s * 0.07, topY + 0.32, 0), 0.024, wood);
          D.box(0, topY + 0.14, -0.015, 0.045, 0.5, 0.03, wood);
          D.box(0, ledgeY, 0.05, 0.9, 0.035, 0.1, wood);
          // the clamp at the top, wound down to nothing, and the paint dried on the ledge
          D.box(0, topY - 0.05, 0.03, 0.16, 0.05, 0.06, wood);
          daub.forEach((m, k) => D.box(-0.3 + k * 0.22, ledgeY + 0.02, 0.07, 0.06 + k * 0.02, 0.006, 0.05, m));
          D.pop();
        });
        B.blocks.push(centred(x, zz - 0.12 * Math.cos(rot), rot, 0.85, 0.9));
        return;
      }
      const sheet = zoned(mix(INKS.card, INKS.paper, 0.25), z);
      const shade = zoned(mix(mix(INKS.card, INKS.paper, 0.25), INKS.cobalt, 0.07), z);
      const fold = zoned(mix(mix(INKS.card, INKS.paper, 0.25), INKS.cobalt, 0.035), z);
      const ledge = 0.72;
      const top = ledge + 0.04 + ch;
      D.at(x, y, zz, rot, () => {
        // the back leg, standing out behind
        D.bar(new Vector3(0, 0, -0.62), new Vector3(0, top - 0.1, -0.06), 0.022, wood);
        // the easel leans back a little: front legs, mast, ledge, the canvas and its sheet
        D.push(new Matrix4().makeTranslation(0, 0, 0.1).multiply(new Matrix4().makeRotationX(-0.1)));
        for (const s of [-1, 1]) D.bar(new Vector3(s * 0.34, 0, 0), new Vector3(s * 0.07, top + 0.32, 0), 0.024, wood);
        D.box(0, top + 0.14, -0.015, 0.045, 0.5, 0.03, wood);
        D.box(0, ledge, 0.05, cw + 0.14, 0.035, 0.1, wood);
        D.box(0, ledge + 0.04 + ch / 2, 0.035, cw, ch, 0.025, shade);
        // the sheet over the top and down the front in folds, a little wider at its hem
        D.box(0, top + 0.012, 0.035, cw + 0.08, 0.025, 0.1, sheet);
        const folds = 9;
        const hem = 0.28;
        for (let k = 0; k < folds; k++) {
          const u0 = -0.5 + k / folds;
          const u1 = -0.5 + (k + 1) / folds;
          const out = k % 2 ? 0.1 : 0.075;
          const back = k % 2 ? 0.06 : 0.08;
          const xa = u0 * (cw + 0.08);
          const xb = u1 * (cw + 0.08);
          const ya = hem + (k * 37) % 5 * 0.025;
          const flare = 1.12;
          D.quadXYZ([xa * flare, ya, out + 0.04, xb * flare, ya, out + 0.04, xb, top + 0.02, back, xa, top + 0.02, back], k % 2 ? sheet : fold);
        }
        // and down the back, plain
        D.quadXYZ([(cw + 0.12) / 2, hem + 0.1, -0.03, -(cw + 0.12) / 2, hem + 0.1, -0.03, -(cw + 0.08) / 2, top + 0.02, 0.0, (cw + 0.08) / 2, top + 0.02, 0.0], shade);
        // its edges, falling at the sides
        for (const s of [-1, 1]) D.quadXYZ([s * (cw + 0.12) / 2 * 1.08, hem + 0.06, 0.12, s * (cw + 0.12) / 2, hem + 0.1, -0.03, s * (cw + 0.08) / 2, top + 0.02, 0.0, s * (cw + 0.08) / 2, top + 0.02, 0.1], sheet);
        D.pop();
      });
      B.blocks.push(centred(x, zz - 0.12 * Math.cos(rot), rot, cw + 0.45, 0.9));
      return;
    }
    case 'crates': {
      // wooden crates stacked against the wall, the bottles' necks showing in the top row
      // (`size` crates across and crates high)
      const [cols, rows] = t.size ?? [3, 3];
      const cw = 0.46;
      const chh = 0.3;
      const cd = 0.34;
      const tones = [mix(TONES.wood, INKS.paper, 0.2), mix(TONES.wood, INKS.ochre, 0.3), mix(TONES.wood, INKS.ink, 0.12)];
      const slat = zoned(mix(TONES.wood, INKS.ink, 0.45), z);
      const glass = zoned(mix(INKS.green, INKS.ink, 0.35), z, { wet: 0.5 });
      const R = { v: 977 + i * 53 };
      const rand = () => {
        R.v = (R.v * 16807) % 2147483647;
        return R.v / 2147483647;
      };
      D.at(x, y, zz, rot, () => {
        for (let c = 0; c < cols; c++) {
          const h = Math.max(1, rows - (c === cols - 1 ? 1 : 0));
          for (let r = 0; r < h; r++) {
            const wood = zoned(tones[Math.floor(rand() * tones.length)], z);
            const cx = (c - (cols - 1) / 2) * (cw + 0.02) + (rand() - 0.5) * 0.04;
            const cz = cd / 2 + (rand() - 0.5) * 0.04;
            const cy = r * chh;
            D.box(cx, cy + chh / 2, cz, cw, chh, cd, wood, { ny: r === 0 ? false : true });
            // the gap between the slats, and the hand-hole in the front board
            D.box(cx, cy + chh * 0.55, cz + cd / 2 + 0.002, cw - 0.04, 0.012, 0.004, slat);
            D.box(cx, cy + chh * 0.78, cz + cd / 2 + 0.002, 0.12, 0.035, 0.004, slat);
            if (r === h - 1) {
              for (let b = 0; b < 6; b++) D.cylinder(cx - 0.15 + (b % 3) * 0.15, cy + chh, cz - 0.08 + Math.floor(b / 3) * 0.16, 0.014, 0.014, 0.07, 6, glass, { flat: true });
            }
          }
        }
      });
      B.blocks.push(footprint(x, zz, rot, cols * (cw + 0.02) + 0.06, cd + 0.06));
      return;
    }
    case 'board': {
      // the electrical board on the wall: a pale metal cabinet with a smoked window over the rows
      // of breakers, the meter beside it, the cables' trunking up to the ceiling (`size` the
      // cabinet's width and height; the trunking runs up `text`-less to the given height)
      const [w, h] = t.size ?? [0.6, 0.9];
      const metal = zoned(mix(INKS.card, INKS.paper, 0.35), z, { wet: 0.2 });
      const smoke = zoned(mix(INKS.ink, INKS.cobalt, 0.2), z, { wet: 0.7 });
      const breaker = zoned(mix(INKS.card, INKS.ink, 0.12), z);
      const lever = zoned(INKS.ink, z);
      const meter = zoned(mix(INKS.card, INKS.green, 0.22), z);
      const trunk = zoned(INKS.card, z);
      D.at(x, y, zz, rot, () => {
        D.box(0, 0, 0.06, w, h, 0.12, metal);
        // the window in the door, and the breakers behind it in three rows
        D.box(0, 0.04, 0.121, w - 0.12, h * 0.62, 0.004, smoke);
        for (let r = 0; r < 3; r++) {
          const ry = 0.04 + h * 0.2 - r * h * 0.2;
          for (let k = 0; k < 8; k++) {
            const bx = -(w - 0.16) / 2 + 0.02 + k * ((w - 0.2) / 7);
            D.box(bx, ry, 0.124, 0.03, 0.07, 0.006, breaker);
            D.box(bx, ry + 0.012, 0.128, 0.012, 0.02, 0.006, lever);
          }
        }
        D.box(w / 2 - 0.06, -h / 2 + 0.07, 0.124, 0.03, 0.05, 0.01, lever);
        // the meter, to the side
        D.box(w / 2 + 0.16, h / 2 - 0.16, 0.05, 0.18, 0.26, 0.1, meter);
        D.box(w / 2 + 0.16, h / 2 - 0.12, 0.101, 0.1, 0.04, 0.003, smoke);
        // the trunking, up out of the top to the ceiling
        D.box(0, h / 2 + 0.6, 0.04, 0.12, 1.2, 0.06, trunk);
      });
      return;
    }
    case 'plan': {
      // a plan drawn by hand, pinned to the wall: the café's room and its back room, what each is
      // for, in felt-tip capitals (`text`: its title, the back room's square, then the room's)
      const [w, h] = t.size ?? [0.5, 0.36];
      card(B, key, [x, y, zz], rot, w, h, z, planArt(t.text ?? []), 1400);
      const pin = zoned(INKS.vermilion, z);
      D.at(x, y, zz, rot, () => {
        for (const [px, py] of [[-1, 1], [1, 1], [-1, -1], [1, -1]] as Array<[number, number]>) D.ball((px * (w - 0.04)) / 2, (py * (h - 0.04)) / 2, 0.02, 0.009, 0.009, 0.009, pin, 0);
      });
      return;
    }
    case 'fridge': {
      // a tall fridge against the wall, its white gone to cream, the freezer's drawer below and
      // the handle up its side. On its door, under magnets: a folder (`text[0]` its label, '' for
      // none), a card in a quick hand held by a sardine (the rest of `text`, a line a paragraph)
      // and a felt-tip drawing (`size` its width and height)
      const [w, h] = t.size ?? [0.6, 1.72];
      const d = 0.62;
      const body = zoned(mix(mix(INKS.paper, INKS.card, 0.15), INKS.cobalt, 0.05), z, { wet: 0.35 });
      const seam = zoned(mix(INKS.card, INKS.ink, 0.35), z);
      const grip = zoned(mix(INKS.paper, INKS.ink, 0.3), z, { wet: 0.6 });
      const split = h * 0.34;
      D.at(x, y, zz, rot, () => {
        D.box(0, h / 2, d / 2, w, h, d, body, { ny: false });
        D.box(0, split, d + 0.002, w - 0.01, 0.012, 0.004, seam);
        D.box(0, h - 0.01, d / 2, w + 0.004, 0.02, d - 0.04, seam);
        D.box(w / 2 - 0.05, split + 0.42, d + 0.022, 0.024, 0.36, 0.03, grip);
        D.box(0, split - 0.08, d + 0.02, w * 0.5, 0.024, 0.03, grip);
      });
      const c = Math.cos(rot);
      const s = Math.sin(rot);
      const on = (lx: number, ly: number, lz = d): XYZ => [x + lx * c + lz * s, y + ly, zz - lx * s + lz * c];
      const [label = '', ...note] = t.text ?? [];
      if (label) {
        card(B, `${key}:folder`, on(-0.1, split + 0.86), rot, 0.24, 0.32, z, folderFaceArt(label), 1600);
        D.ball(...on(-0.1, split + 1.0, d + 0.02), 0.016, 0.016, 0.01, zoned(INKS.vermilion, z), 0);
      }
      if (note.length) {
        // the card, and its sardine on top: a little blue fish with its tail
        card(B, `${key}:card`, on(0.12, split + 0.55, d + 0.004), rot, 0.17, 0.12, z, noteArt(note), 2600);
        const fish = zoned(mix(INKS.cobalt, INKS.paper, 0.35), z, { wet: 0.5 });
        D.at(...on(0.12, split + 0.6, d + 0.02), rot, () => {
          D.box(0, 0, 0, 0.07, 0.02, 0.012, fish);
          D.box(0.045, 0, 0, 0.014, 0.03, 0.01, fish);
        });
      }
      card(B, `${key}:drawing`, on(-0.08, split + 0.32, d + 0.006), rot, 0.21, 0.15, z, drawingArt(), 1600);
      D.ball(...on(-0.08, split + 0.39, d + 0.02), 0.014, 0.014, 0.01, zoned(INKS.ochre, z), 0);
      B.blocks.push(footprint(x, zz, rot, w + 0.04, d + 0.06));
      return;
    }
    case 'crate': {
      // a painting's shipping crate standing on its edge against the wall: plywood framed in
      // battens, screwed shut on three sides, its stencil on the face (`text`: the lines, the
      // first in red), `size` its width and height
      const [w, h] = t.size ?? [1.3, 1.05];
      const d = 0.3;
      const ply = zoned(mix(TONES.wood, INKS.paper, 0.35), z);
      const batten = zoned(mix(TONES.wood, INKS.ochre, 0.2), z);
      const screw = zoned(mix(INKS.paper, INKS.ink, 0.35), z, { wet: 0.6 });
      D.at(x, y, zz, rot, () => {
        D.box(0, h / 2 + 0.03, d / 2, w, h, d, ply, { ny: false });
        // the battens round the face, a little proud of it
        D.box(0, h + 0.005, d + 0.012, w, 0.07, 0.024, batten);
        D.box(0, 0.065, d + 0.012, w, 0.07, 0.024, batten);
        for (const sx of [-1, 1]) D.box(sx * (w / 2 - 0.035), h / 2 + 0.03, d + 0.012, 0.07, h - 0.07, 0.024, batten);
        // two skids under it, so it stands off the floor
        for (const sx of [-1, 1]) D.box(sx * (w / 2 - 0.15), 0.015, d / 2, 0.08, 0.03, d + 0.04, batten);
        for (const [sx, sy] of [[-1, 1], [1, 1], [-1, -1], [1, -1], [0, 1], [0, -1]] as Array<[number, number]>) {
          D.box(sx * (w / 2 - 0.035), h / 2 + 0.03 + sy * (h / 2 - 0.035), d + 0.026, 0.012, 0.012, 0.004, screw);
        }
      });
      const c = Math.cos(rot);
      const s = Math.sin(rot);
      card(B, key, [x + (d + 0.003) * s, y + h / 2 + 0.03, zz + (d + 0.003) * c], rot, w - 0.2, h - 0.2, z, stencilArt(t.text ?? []), 900);
      B.blocks.push(footprint(x, zz, rot, w + 0.04, d + 0.06));
      return;
    }
    case 'canvas': {
      // a canvas leaning on the wall with its face to it: the stretcher's back, the linen
      // nailed round it, and bubble wrap taped over its lower half (`size` its width and height)
      const [w, h] = t.size ?? [1.1, 0.85];
      const linen = zoned(mix(INKS.card, INKS.ochre, 0.18), z);
      const wood = zoned(mix(TONES.wood, INKS.paper, 0.25), z);
      const wrap = zoned(mix(mix(INKS.paper, INKS.card, 0.3), INKS.cobalt, 0.06), z, { wet: 0.9 });
      const bubble = zoned(mix(mix(INKS.paper, INKS.card, 0.2), INKS.cobalt, 0.04), z, { wet: 1 });
      const tape = zoned(mix(INKS.ochre, INKS.paper, 0.45), z, { wet: 0.4 });
      const tilt = 0.24 / h;
      D.at(x, y, zz, rot, () => {
        D.push(new Matrix4().makeTranslation(0, 0, 0.26).multiply(new Matrix4().makeRotationX(-tilt)));
        D.box(0, h / 2, 0.004, w, h, 0.008, linen);
        // the stretcher bars, and the brace across the middle
        D.box(0, 0.025, 0.03, w, 0.05, 0.045, wood);
        D.box(0, h - 0.025, 0.03, w, 0.05, 0.045, wood);
        for (const sx of [-1, 1]) D.box(sx * (w / 2 - 0.025), h / 2, 0.03, 0.05, h - 0.1, 0.045, wood);
        D.box(0, h / 2, 0.025, 0.04, h - 0.1, 0.035, wood);
        D.pop();
        // the bubble wrap round its lower half, a fat sheet taped across it, its loose end hanging
        const wh = h * 0.52;
        D.box(0, wh / 2, 0.225, w + 0.06, wh, 0.21, wrap);
        D.box(0, wh - 0.07, 0.358, w + 0.07, 0.045, 0.006, tape);
        D.quadXYZ([w / 2 + 0.03, 0.02, 0.33, w / 2 + 0.2, 0.0, 0.42, w / 2 + 0.16, wh, 0.38, w / 2 + 0.03, wh, 0.33], bubble);
      });
      card(B, `${key}:wrap`, [x + 0.331 * Math.sin(rot), y + (h * 0.52) / 2, zz + 0.331 * Math.cos(rot)], rot, w + 0.06, h * 0.52, z, bubbleArt(), 700);
      // and the roll of tape, left on the floor beside it
      D.at(x, y, zz, rot, () => D.cylinder(w / 2 + 0.32, 0.0, 0.32, 0.06, 0.06, 0.05, 12, tape, { flat: true, caps: true }));
      B.blocks.push(footprint(x, zz, rot, w + 0.4, 0.5));
      return;
    }
    case 'keyboard': {
      // a key board on the wall: a plank with rows of brass hooks, on most a key and its paper tag,
      // here and there a hook empty (`size` the board's width and height; `at` its centre)
      const [w, h] = t.size ?? [1.2, 0.9];
      const plank = zoned(mix(TONES.wood, INKS.ink, 0.2), z);
      const brass = zoned(TONES.brass, z, { wet: 0.6 });
      const steel = zoned(mix(INKS.paper, INKS.ink, 0.4), z, { wet: 0.6 });
      const tag = zoned(mix(INKS.card, INKS.ochre, 0.12), z);
      const ink = zoned(mix(INKS.ink, INKS.paper, 0.2), z);
      const R = { v: 4271 + i * 31 };
      const rand = () => {
        R.v = (R.v * 16807) % 2147483647;
        return R.v / 2147483647;
      };
      const rows = Math.max(1, Math.floor((h - 0.08) / 0.115));
      const cols = Math.max(1, Math.floor((w - 0.06) / 0.07));
      D.at(x, y, zz, rot, () => {
        D.box(0, 0, 0.012, w, h, 0.024, plank);
        // the rows' painted numbers, a strip of card along the top of each row
        for (let r = 0; r < rows; r++) {
          const ry = h / 2 - 0.06 - r * ((h - 0.08) / rows);
          D.box(0, ry + 0.025, 0.026, w - 0.05, 0.016, 0.003, tag);
          for (let k = 0; k < cols; k++) {
            const kx = -w / 2 + 0.05 + k * ((w - 0.08) / cols);
            D.box(kx, ry + 0.025, 0.028, 0.012, 0.006, 0.002, ink);
            D.box(kx, ry, 0.035, 0.008, 0.008, 0.024, brass);
            if (rand() < 0.16) continue;
            const tilt = (rand() - 0.5) * 0.06;
            D.box(kx + tilt, ry - 0.035, 0.044, 0.014, 0.05, 0.004, rand() < 0.3 ? brass : steel);
            D.box(kx + tilt * 1.6, ry - 0.08, 0.046, 0.028, 0.034, 0.002, tag);
          }
        }
      });
      return;
    }
    case 'cabinet': {
      // a grey metal filing cabinet against the wall: four drawers, their pulls and label holders
      // (`size` its width and height)
      const [w, h] = t.size ?? [0.47, 1.32];
      const d = 0.62;
      const grey = zoned(mix(mix(INKS.paper, INKS.ink, 0.38), INKS.cobalt, 0.06), z, { wet: 0.3 });
      const seam = zoned(mix(INKS.ink, INKS.cobalt, 0.15), z);
      const chrome = zoned(mix(INKS.paper, INKS.ink, 0.15), z, { wet: 0.8 });
      const label = zoned(INKS.card, z);
      const drawers = 4;
      D.at(x, y, zz, rot, () => {
        D.box(0, h / 2, d / 2, w, h, d, grey, { ny: false });
        for (let k = 0; k < drawers; k++) {
          const dy = 0.04 + (k + 0.5) * ((h - 0.08) / drawers);
          D.box(0, dy - (h - 0.08) / drawers / 2, d + 0.002, w - 0.02, 0.008, 0.004, seam);
          D.box(0, dy + 0.06, d + 0.006, 0.09, 0.045, 0.006, chrome);
          D.box(0, dy + 0.06, d + 0.01, 0.07, 0.03, 0.002, label);
          D.box(0, dy - 0.02, d + 0.02, 0.12, 0.022, 0.03, chrome);
        }
      });
      B.blocks.push(footprint(x, zz, rot, w + 0.04, d + 0.06));
      return;
    }
    case 'desk': {
      // an old office desk: its top with a green blotter, a pedestal of drawers on the sitter's
      // side (behind, -z), files stacked at one end (`size` its width and its depth)
      const [w, dd] = t.size ?? [1.4, 0.75];
      const wood = zoned(mix(TONES.wood, INKS.ink, 0.25), z, { wet: 0.2 });
      const dark = zoned(mix(TONES.wood, INKS.ink, 0.5), z);
      const blotter = zoned(mix(INKS.green, INKS.ink, 0.35), z);
      const buff = [mix(INKS.ochre, INKS.paper, 0.55), mix(INKS.cobalt, INKS.paper, 0.6), mix(INKS.vermilion, INKS.paper, 0.6), mix(INKS.paper, INKS.ink, 0.25)].map((c) => zoned(c, z));
      const brass = zoned(TONES.brass, z, { wet: 0.6 });
      const top = 0.76;
      D.at(x, y, zz, rot, () => {
        D.box(0, top - 0.02, 0, w, 0.04, dd, wood);
        // the modesty panel at the front, the pedestal of drawers at the right, a leg at the left
        D.box(0, top - 0.3, dd / 2 - 0.03, w - 0.1, 0.5, 0.025, wood);
        D.box(w / 2 - 0.22, (top - 0.04) / 2, 0, 0.4, top - 0.04, dd - 0.06, wood, { ny: false });
        for (let k = 0; k < 3; k++) {
          const ky = 0.12 + k * 0.22;
          D.box(w / 2 - 0.22, ky + 0.1, -dd / 2 + 0.02, 0.36, 0.19, 0.012, dark);
          D.box(w / 2 - 0.22, ky + 0.12, -dd / 2 + 0.002, 0.08, 0.014, 0.02, brass);
        }
        D.box(-w / 2 + 0.05, (top - 0.04) / 2, 0, 0.05, top - 0.04, dd - 0.06, wood, { ny: false });
        // the blotter, and the files at the left end in a slanting stack
        D.box(0.05, top + 0.003, -0.02, 0.62, 0.006, 0.42, blotter);
        for (let k = 0; k < 7; k++) D.box(-w / 2 + 0.24 + (k % 3) * 0.006, top + 0.012 + k * 0.022, 0.02 - (k % 2) * 0.015, 0.33, 0.02, 0.24, buff[k % buff.length]);
      });
      B.blocks.push(centred(x, zz, rot, w + 0.04, dd + 0.04));
      return;
    }
    case 'campbed': {
      // a camp bed made with hospital corners: its folding frame low on the floor, the grey
      // blanket pulled tight and tucked square, the sheet turned down over it at the head, a
      // pillow (`size` its length and width, along local x)
      const [len, wid] = t.size ?? [1.9, 0.7];
      const frame = zoned(mix(INKS.paper, INKS.ink, 0.45), z, { wet: 0.5 });
      const blanket = zoned(ROOM_TONES.blanket, z);
      const sheet = zoned(INKS.card, z);
      const crease = zoned(mix(ROOM_TONES.blanket, INKS.ink, 0.3), z);
      const ht = 0.4;
      D.at(x, y, zz, rot, () => {
        // the X legs at each end and the middle, the side rails
        for (const lx of [-len / 2 + 0.06, 0, len / 2 - 0.06]) {
          for (const s of [-1, 1]) D.bar(new Vector3(lx, 0, s * (wid / 2 - 0.04)), new Vector3(lx, ht - 0.06, -s * (wid / 2 - 0.04)), 0.012, frame);
        }
        for (const s of [-1, 1]) D.bar(new Vector3(-len / 2, ht - 0.05, s * (wid / 2)), new Vector3(len / 2, ht - 0.05, s * (wid / 2)), 0.015, frame);
        // the blanket, square at its corners, tucked down the sides
        D.box(0, ht - 0.01, 0, len - 0.02, 0.05, wid + 0.02, blanket);
        for (const s of [-1, 1]) D.box(0, ht - 0.09, s * (wid / 2 + 0.012), len - 0.02, 0.12, 0.006, blanket);
        for (const s of [-1, 1]) D.box(s * (len / 2 - 0.01), ht - 0.09, 0, 0.006, 0.12, wid + 0.03, blanket);
        // the hospital corners' fold, a diagonal crease at each corner
        for (const sx of [-1, 1]) for (const sz of [-1, 1]) D.bar(new Vector3(sx * (len / 2 - 0.0), ht - 0.15, sz * (wid / 2 + 0.016)), new Vector3(sx * (len / 2 - 0.12), ht - 0.03, sz * (wid / 2 + 0.016)), 0.004, crease);
        // the sheet turned down at the head, and the pillow squared on it
        D.box(-len / 2 + 0.42, ht + 0.018, 0, 0.16, 0.012, wid + 0.022, sheet);
        D.box(-len / 2 + 0.2, ht + 0.06, 0, 0.3, 0.08, wid - 0.12, sheet);
      });
      B.blocks.push(centred(x, zz, rot, len + 0.06, wid + 0.08));
      return;
    }
    case 'frame': {
      // a small photo frame standing on a desk, on its strut: with `text`, a Polaroid of two old
      // people laughing on a bench by a lake, its caption on the white border in a hand; without,
      // an old portrait gone sepia (`size` the frame's width and height)
      const [w, h] = t.size ?? [0.13, 0.16];
      const wood = zoned(mix(TONES.wood, INKS.ink, 0.35), z, { wet: 0.3 });
      D.at(x, y, zz, rot, () => {
        D.box(0, h / 2, 0, w, h, 0.012, wood);
        D.bar(new Vector3(0, h * 0.7, -0.006), new Vector3(0, 0, -0.07), 0.004, wood);
      });
      const c = Math.cos(rot);
      const s = Math.sin(rot);
      card(B, key, [x + 0.004 * s, y + h / 2, zz + 0.004 * c], rot, w - 0.02, h - 0.02, z, t.text?.length ? polaroidArt(t.text[0]) : portraitArt(), 3200);
      return;
    }
    case 'intercom': {
      // an old building's intercom beside its door: a brushed plate on the wall, the grille of the
      // speaker at the top, then a row a flat (a name on a card, its push-button), `text` the names
      // from the top floor down (`at` the plate's centre on the wall)
      const names = t.text ?? [];
      const rows = Math.max(1, Math.ceil(names.length / 2));
      const w = 0.2;
      const h = 0.12 + rows * 0.045;
      const steel = zoned(mix(mix(INKS.paper, INKS.ink, 0.3), INKS.ochre, 0.08), z, { wet: 0.6 });
      D.at(x, y, zz, rot, () => D.box(0, 0, 0.008, w + 0.02, h + 0.02, 0.016, steel));
      const c = Math.cos(rot);
      const sn = Math.sin(rot);
      card(B, key, [x + 0.005 * sn, y, zz + 0.005 * c], rot, w, h, z, intercomArt(names, rows), 2400);
      return;
    }
    case 'gaze': {
      // nothing to draw: a point you look at from where you can stand (a window up the street),
      // so the story can be tapped where the quarter already draws it
      return;
    }
    case 'armoire': {
      // a tall wardrobe against the wall: two panelled doors, a key in one, a cornice on top
      const [w, h] = t.size ?? [1.1, 2.2];
      const dd = 0.55;
      const wood = zoned(toneOf(t.tone, mix(TONES.wood, INKS.ink, 0.15)), z, { wet: 0.15 });
      const panel = zoned(mix(toneOf(t.tone, mix(TONES.wood, INKS.ink, 0.15)), INKS.ink, 0.18), z);
      const brass = zoned(TONES.brass, z, { wet: 0.6 });
      D.at(x, y, zz, rot, () => {
        D.box(0, h / 2 + 0.06, dd / 2, w, h - 0.12, dd, wood);
        D.box(0, 0.03, dd / 2 + 0.02, w + 0.04, 0.06, dd + 0.04, wood, { ny: false });
        D.box(0, h + 0.04, dd / 2 + 0.03, w + 0.12, 0.08, dd + 0.08, wood);
        D.box(0, h / 2 + 0.06, dd + 0.004, 0.008, h - 0.2, 0.006, panel);
        for (const s of [-1, 1]) {
          for (const [py, ph] of [[0.62, 0.7], [1.52, 0.85]]) D.box((s * w) / 4, py, dd + 0.006, w / 2 - 0.16, ph, 0.012, panel);
        }
        D.box(0.06, 1.1, dd + 0.015, 0.015, 0.05, 0.02, brass);
      });
      B.blocks.push(footprint(x, zz, rot, w + 0.12, dd + 0.08));
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

/**
 * Marin's plan, drawn by hand: the café's room with its long tables and the booth at the back,
 * and the back room's square with what it will be. `text`: the title, the back room's label
 * (written over two lines inside its square), then the labels of the room.
 */
function planArt(text: string[]) {
  const [title = '', back = '', ...room] = text;
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(INKS.card, INKS.paper, 0.15));
    ctx.fillRect(0, 0, w, h);
    const pencil = css(mix(INKS.ink, INKS.paper, 0.4));
    const felt = css(mix(INKS.cobalt, INKS.ink, 0.25));
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = felt;
    let s = Math.round(h * 0.085);
    ctx.font = SANS(s, 700);
    while (s > 6 && ctx.measureText(title).width > w * 0.9) ctx.font = SANS(--s, 700);
    ctx.fillText(title, w / 2, h * 0.09);
    // the café's room, the back room beside it
    const y0 = h * 0.2;
    const y1 = h * 0.92;
    const xa = w * 0.05;
    const xb = w * 0.6;
    const xc = w * 0.95;
    ctx.strokeStyle = pencil;
    ctx.lineWidth = Math.max(2, w * 0.006);
    ctx.strokeRect(xa, y0, xb - xa, y1 - y0);
    ctx.strokeStyle = felt;
    ctx.lineWidth = Math.max(2, w * 0.008);
    ctx.strokeRect(xb, y0, xc - xb, (y1 - y0) * 0.66);
    // the door between them
    ctx.fillStyle = css(mix(INKS.card, INKS.paper, 0.15));
    ctx.fillRect(xb - 2, y0 + (y1 - y0) * 0.08, 5, (y1 - y0) * 0.1);
    // the zinc along the back, the long tables, the booth
    ctx.strokeStyle = pencil;
    ctx.lineWidth = Math.max(1.5, w * 0.004);
    ctx.strokeRect(xb - w * 0.07, y0 + (y1 - y0) * 0.25, w * 0.035, (y1 - y0) * 0.55);
    for (const ty of [0.5, 0.72]) ctx.strokeRect(xa + w * 0.05, y0 + (y1 - y0) * ty, w * 0.36, (y1 - y0) * 0.08);
    ctx.strokeRect(xa + w * 0.02, y0 + (y1 - y0) * 0.06, w * 0.2, (y1 - y0) * 0.1);
    // the labels
    ctx.fillStyle = felt;
    const label = (t: string, cx: number, cy: number, max: number, size: number) => {
      let k = Math.round(size);
      ctx.font = SANS(k, 700);
      while (k > 5 && ctx.measureText(t).width > max) ctx.font = SANS(--k, 700);
      ctx.fillText(t, cx, cy);
    };
    const words = back.split(' ');
    const cut = Math.max(1, Math.ceil(words.length / 3));
    const lines = words.length > 2 ? [words.slice(0, cut).join(' '), words.slice(cut).join(' ')] : [back];
    const bcx = (xb + xc) / 2;
    const bcy = y0 + (y1 - y0) * 0.33;
    lines.forEach((t, k) => label(t, bcx, bcy + (k - (lines.length - 1) / 2) * h * 0.1, (xc - xb) * 0.86, h * 0.085));
    // in the room: by the long tables, by the booth, by the zinc (fractions of the room's plan)
    const spots: Array<[number, number, number]> = [[0.42, 0.42, 0.6], [0.22, 0.24, 0.36], [0.8, 0.88, 0.25]];
    room.forEach((t, k) => {
      const [px, py, max] = spots[k] ?? [0.42, 0.3, 0.6];
      label(t, xa + (xb - xa) * px, y0 + (y1 - y0) * py, (xb - xa) * max, h * 0.055);
    });
  };
}

/** A folder's cover on a fridge door: buff card, its strap, and a white label in felt-tip capitals. */
function folderFaceArt(label: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(INKS.ochre, INKS.paper, 0.55));
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(mix(INKS.ink, INKS.cobalt, 0.2));
    ctx.fillRect(w * 0.8, 0, w * 0.035, h);
    ctx.fillStyle = css(INKS.paper);
    ctx.fillRect(w * 0.1, h * 0.14, w * 0.62, h * 0.3);
    ctx.fillStyle = css(mix(INKS.cobalt, INKS.ink, 0.25));
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const words = label.split(' ');
    const lines = words.length > 2 ? [words.slice(0, 2).join(' '), words.slice(2).join(' ')] : [label];
    let s = Math.round(h * 0.09);
    ctx.font = SANS(s, 700);
    while (s > 6 && Math.max(...lines.map((l) => ctx.measureText(l).width)) > w * 0.56) ctx.font = SANS(--s, 700);
    lines.forEach((l, k) => ctx.fillText(l, w * 0.41, h * (0.29 + (k - (lines.length - 1) / 2) * 0.11)));
  };
}

/**
 * A card written in a quick hand, a line a paragraph, wrapped to the card; the last paragraph
 * stops where it stops (an unfinished line is written as it is, with no full stop).
 */
function noteArt(paragraphs: string[]) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(INKS.card, INKS.paper, 0.6));
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(mix(INKS.cobalt, INKS.ink, 0.35));
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    const pad = w * 0.07;
    const wrap = (size: number) => {
      ctx.font = SERIF(size, 500);
      const rows: string[] = [];
      for (const p of paragraphs) {
        let row = '';
        for (const word of p.split(' ')) {
          const next = row ? `${row} ${word}` : word;
          if (row && ctx.measureText(next).width > w - 2 * pad) {
            rows.push(row);
            row = word;
          } else row = next;
        }
        rows.push(row);
      }
      return rows;
    };
    let size = Math.round(h * 0.1);
    let rows = wrap(size);
    while (size > 6 && rows.length * size * 1.22 > h - 2 * pad) rows = wrap(--size);
    rows.forEach((r, k) => ctx.fillText(r, pad, pad + size + k * size * 1.22));
  };
}

/**
 * A drawing in felt-tip from a dinner that went wrong: a pan with its omelette, the smoke going
 * up in three curls, and the smoke alarm in the corner shouting. No one in it.
 */
function drawingArt() {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(INKS.paper);
    ctx.fillRect(0, 0, w, h);
    const ink = css(mix(INKS.ink, INKS.cobalt, 0.2));
    ctx.lineCap = 'round';
    ctx.lineWidth = Math.max(2, w * 0.012);
    // the pan, its handle out to the left, the omelette in it
    ctx.strokeStyle = ink;
    ctx.beginPath();
    ctx.ellipse(w * 0.46, h * 0.74, w * 0.2, h * 0.09, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(w * 0.27, h * 0.76);
    ctx.lineTo(w * 0.06, h * 0.86);
    ctx.stroke();
    ctx.fillStyle = css(mix(INKS.ochre, INKS.paper, 0.15));
    ctx.beginPath();
    ctx.ellipse(w * 0.47, h * 0.73, w * 0.13, h * 0.05, 0.1, 0, Math.PI * 2);
    ctx.fill();
    // the smoke, three curls
    ctx.strokeStyle = css(mix(INKS.ink, INKS.paper, 0.45));
    for (const k of [0, 1, 2]) {
      const sx = w * (0.38 + k * 0.08);
      ctx.beginPath();
      ctx.moveTo(sx, h * 0.62);
      ctx.bezierCurveTo(sx - w * 0.05, h * 0.5, sx + w * 0.05, h * 0.4, sx - w * 0.02, h * 0.26);
      ctx.stroke();
    }
    // the alarm on the ceiling, top right, and its shout
    ctx.strokeStyle = ink;
    ctx.beginPath();
    ctx.ellipse(w * 0.82, h * 0.14, w * 0.07, h * 0.05, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = css(INKS.vermilion);
    for (const k of [0, 1, 2]) {
      ctx.beginPath();
      ctx.moveTo(w * (0.74 - k * 0.02), h * (0.24 + k * 0.05));
      ctx.lineTo(w * (0.68 - k * 0.04), h * (0.3 + k * 0.07));
      ctx.stroke();
    }
    ctx.fillStyle = css(INKS.vermilion);
    ctx.font = SANS(Math.round(h * 0.12), 800);
    ctx.textAlign = 'center';
    ctx.fillText('BIIIP', w * 0.8, h * 0.42);
  };
}

/** Bubble wrap seen close: rows of soft bubbles, each with its catch of light, no outline. */
function bubbleArt() {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(mix(INKS.paper, INKS.card, 0.3), INKS.cobalt, 0.06));
    ctx.fillRect(0, 0, w, h);
    const r = Math.max(3, h * 0.035);
    const step = r * 2.6;
    for (let row = 0, y = r * 1.4; y < h; row++, y += step * 0.87) {
      for (let x = (row % 2 ? step / 2 : 0) + r * 1.2; x < w; x += step) {
        ctx.fillStyle = css(mix(mix(INKS.paper, INKS.card, 0.15), INKS.cobalt, 0.1));
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = css(INKS.paper);
        ctx.beginPath();
        ctx.arc(x - r * 0.35, y - r * 0.35, r * 0.3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  };
}

/** A crate's stencil: the first line in red, the rest in black, sprayed through a stencil. */
function stencilArt(lines: string[]) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const sizes = [0.14, 0.22, 0.09];
    const ys = [0.22, 0.5, 0.76];
    lines.forEach((t, k) => {
      ctx.fillStyle = css(k === 0 ? mix(INKS.vermilion, INKS.ink, 0.15) : mix(INKS.ink, INKS.paper, 0.08));
      let s = Math.round(h * (sizes[k] ?? 0.09));
      ctx.font = SANS(s, 800);
      while (s > 6 && ctx.measureText(t).width > w * 0.92) ctx.font = SANS(--s, 800);
      ctx.fillText(t, w / 2, h * (ys[k] ?? 0.76 + (k - 2) * 0.12));
    });
    // the stencil's bridges: thin gaps across the letters
    ctx.globalCompositeOperation = 'destination-out';
    for (let k = 0; k < 40; k++) ctx.fillRect((k / 40) * w + w * 0.008, 0, Math.max(1, w * 0.002), h);
    ctx.globalCompositeOperation = 'source-over';
  };
}

/**
 * A Polaroid: a lake under trees, a bench, two old people laughing on it (small, from where an
 * arm held the camera; no faces to read), and on the white border below, its caption in a hand.
 */
function polaroidArt(caption: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(INKS.card);
    ctx.fillRect(0, 0, w, h);
    const m = w * 0.07;
    const ph = h * 0.72;
    // the picture: sky, trees, the lake, the bank
    ctx.fillStyle = css(mix(INKS.cobalt, INKS.paper, 0.6));
    ctx.fillRect(m, m, w - 2 * m, ph - m);
    ctx.fillStyle = css(mix(INKS.green, INKS.ink, 0.15));
    ctx.fillRect(m, m + (ph - m) * 0.22, w - 2 * m, (ph - m) * 0.2);
    ctx.fillStyle = css(mix(INKS.cobalt, INKS.paper, 0.35));
    ctx.fillRect(m, m + (ph - m) * 0.42, w - 2 * m, (ph - m) * 0.2);
    ctx.fillStyle = css(mix(INKS.ochre, INKS.paper, 0.45));
    ctx.fillRect(m, m + (ph - m) * 0.62, w - 2 * m, (ph - m) * 0.38);
    // the bench, and the two of them on it, leaning into each other
    const by = m + (ph - m) * 0.78;
    ctx.fillStyle = css(mix(TONES.wood, INKS.ink, 0.3));
    ctx.fillRect(w * 0.22, by, w * 0.56, h * 0.025);
    ctx.fillRect(w * 0.22, by - h * 0.08, w * 0.56, h * 0.02);
    const person = (cx: number, coat: number, lean: number) => {
      ctx.fillStyle = css(coat);
      ctx.beginPath();
      ctx.ellipse(cx + lean, by - h * 0.05, w * 0.075, h * 0.07, lean * 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = css(mix(INKS.paper, INKS.ink, 0.35));
      ctx.beginPath();
      ctx.arc(cx + lean * 2, by - h * 0.135, w * 0.04, 0, Math.PI * 2);
      ctx.fill();
    };
    person(w * 0.4, mix(INKS.green, INKS.sunflower, 0.15), w * 0.02);
    person(w * 0.6, mix(INKS.ink, INKS.cobalt, 0.3), -w * 0.02);
    // the caption, in her hand
    ctx.fillStyle = css(mix(INKS.cobalt, INKS.ink, 0.35));
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    let sz = Math.round(h * 0.075);
    ctx.font = SERIF(sz, 500);
    while (sz > 5 && ctx.measureText(caption).width > w * 0.9) ctx.font = SERIF(--sz, 500);
    ctx.fillText(caption, w / 2, ph + (h - ph) / 2);
  };
}

/** An old studio portrait gone sepia: a woman's head and shoulders in an oval, no features drawn. */
function portraitArt() {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(INKS.ochre, INKS.paper, 0.7));
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = css(mix(INKS.ochre, INKS.ink, 0.25));
    ctx.beginPath();
    ctx.ellipse(w / 2, h / 2, w * 0.4, h * 0.42, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = css(mix(INKS.ochre, INKS.paper, 0.4));
    ctx.beginPath();
    ctx.ellipse(w / 2, h * 0.42, w * 0.14, h * 0.13, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(w / 2, h * 0.82, w * 0.3, h * 0.2, 0, Math.PI, 0);
    ctx.fill();
  };
}

/** A letterbox's card: a name typed on a slip. */
/** An intercom's face: the speaker's grille, then two columns of name cards and their buttons. */
function intercomArt(names: string[], rows: number) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = css(mix(mix(INKS.paper, INKS.ink, 0.22), INKS.ochre, 0.08));
    ctx.fillRect(0, 0, w, h);
    const top = h * (0.12 / (0.12 + rows * 0.045));
    // the grille: rows of small holes
    ctx.fillStyle = css(mix(INKS.ink, INKS.paper, 0.15));
    for (let gy = top * 0.25; gy < top * 0.8; gy += top * 0.14) {
      for (let gx = w * 0.32; gx < w * 0.68; gx += w * 0.045) {
        ctx.beginPath();
        ctx.arc(gx, gy, Math.max(1, w * 0.008), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const rh = (h - top) / rows;
    const cw = w / 2;
    names.forEach((name, i) => {
      const col = i % 2;
      const row = Math.floor(i / 2);
      const x0 = col * cw + cw * 0.06;
      const y0 = top + row * rh + rh * 0.14;
      const lw = cw * 0.66;
      const lh = rh * 0.72;
      ctx.fillStyle = css(INKS.card);
      ctx.fillRect(x0, y0, lw, lh);
      ctx.fillStyle = css(INKS.ink);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      let s = Math.round(lh * 0.62);
      ctx.font = SANS(s, 500);
      while (s > 5 && ctx.measureText(name).width > lw * 0.9) ctx.font = SANS(--s, 500);
      ctx.fillText(name, x0 + lw * 0.05, y0 + lh * 0.54);
      // the button
      ctx.fillStyle = css(mix(INKS.paper, INKS.ink, 0.5));
      ctx.beginPath();
      ctx.arc(x0 + lw + cw * 0.14, y0 + lh / 2, lh * 0.32, 0, Math.PI * 2);
      ctx.fill();
    });
  };
}

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

const MOIS = ['JANVIER', 'FÉVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN', 'JUILLET', 'AOÛT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DÉCEMBRE'];

/**
 * A wall calendar: the month's name over its grid, the next month's top below (T2 reads it).
 * After the two months, what is written on it in a hand («12/4 dentiste» on the 12th of April,
 * «Tous les dimanches : M.» on every Sunday): then the days have their numbers too.
 */
function calendarArt(text: string[]) {
  const months = text.slice(0, 2);
  const notes = text.slice(2);
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
    const cw = (w * 0.88) / 7;
    const rh = h * 0.075;
    const grid = (y0: number, rows: number) => {
      for (let r = 0; r <= rows; r++) {
        ctx.beginPath();
        ctx.moveTo(w * 0.06, y0 + r * rh);
        ctx.lineTo(w * 0.94, y0 + r * rh);
        ctx.stroke();
      }
      for (let c = 0; c <= 7; c++) {
        ctx.beginPath();
        ctx.moveTo(w * 0.06 + c * cw, y0);
        ctx.lineTo(w * 0.06 + c * cw, y0 + rows * rh);
        ctx.stroke();
      }
    };
    // the days of a month in its grid, Monday first, and what is written in them
    const ink = mix(INKS.cobalt, INKS.ink, 0.35);
    const days = (label: string, y0: number, rows: number) => {
      const [name, year] = label.split(' ');
      const m = MOIS.indexOf(name);
      if (m < 0 || !notes.length) return;
      const yr = Number(year);
      const first = (new Date(yr, m, 1).getDay() + 6) % 7;
      const count = new Date(yr, m + 1, 0).getDate();
      const sundays = notes.find((n) => /^Tous les dimanches/.test(n))?.split(':')[1]?.trim();
      for (let d = 1; d <= count; d++) {
        const k = first + d - 1;
        const r = Math.floor(k / 7);
        if (r >= rows) break;
        const cx = w * 0.06 + (k % 7) * cw;
        const cy = y0 + r * rh;
        ctx.textAlign = 'left';
        ctx.fillStyle = css(mix(INKS.ink, INKS.paper, 0.3));
        ctx.font = SANS(Math.round(rh * 0.26), 600);
        ctx.fillText(String(d), cx + cw * 0.08, cy + rh * 0.2);
        const own: string[] = [];
        notes.forEach((n) => {
          const e = /^(\d+)\/(\d+)\s+(.*)$/.exec(n);
          if (e && Number(e[1]) === d && Number(e[2]) === m + 1) own.push(e[3]);
        });
        const said = own.length ? own : k % 7 === 6 && sundays ? [sundays] : [];
        if (!said.length) continue;
        ctx.fillStyle = css(ink);
        ctx.textAlign = 'center';
        said[0].split(' — ').forEach((line, j) => {
          let sz = Math.round(rh * 0.3);
          ctx.font = SERIF(sz, 600);
          while (sz > 5 && ctx.measureText(line).width > cw * 0.96) ctx.font = SERIF(--sz, 600);
          ctx.fillText(line, cx + cw / 2, cy + rh * (0.55 + j * 0.3));
        });
      }
      ctx.textAlign = 'center';
    };
    grid(h * 0.17, 5);
    days(months[0] ?? '', h * 0.17, 5);
    if (months[1]) {
      ctx.fillStyle = css(INKS.ink);
      ctx.textAlign = 'center';
      ctx.font = SERIF(Math.round(h * 0.06), 700);
      ctx.fillText(months[1], w / 2, h * 0.6);
      grid(h * 0.66, 4);
      days(months[1], h * 0.66, 4);
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

/* ------------------------------------------------------------------------------------------ */
/* a boulevard                                                                                */
/* ------------------------------------------------------------------------------------------ */

const FRONTS: Hex[] = [mix(INKS.green, INKS.ink, 0.35), mix(INKS.cobalt, INKS.ink, 0.3), mix(INKS.vermilion, INKS.ink, 0.45), mix(INKS.ink, INKS.ochre, 0.2)];
const AWNINGS: Hex[] = [mix(INKS.vermilion, INKS.ink, 0.15), mix(INKS.green, INKS.ink, 0.2), mix(INKS.ochre, INKS.vermilion, 0.3), mix(INKS.cobalt, INKS.ink, 0.15)];

/**
 * The boulevard under a window: the pavements and the roadway between them, plane trees and lamps
 * along both kerbs, a bench or two, and across it a row of stone houses with their shops (no names
 * on them), balconies on the second and the fifth floors, and their zinc.
 */
function boulevard(B: Build, b: RoomBoulevard, night: boolean) {
  const s = b.side === 'n' ? -1 : 1;
  const walkW = Math.min(6, b.width * 0.22);
  const far = b.z + s * b.width;
  const near = b.z;
  const span = (z0: number, z1: number): XZ[] => [[b.x0, Math.min(z0, z1)], [b.x1, Math.min(z0, z1)], [b.x1, Math.max(z0, z1)], [b.x0, Math.max(z0, z1)]];
  const walk: Paint = { color: TONES.pavement, pattern: PATTERN.grit, id: nextId() };
  const road: Paint = { color: TONES.asphalt, pattern: PATTERN.grit, id: nextId() };
  const curb: Paint = { color: TONES.curb, id: nextId() };
  B.wet.prism(span(near, near + s * walkW), -0.2, KERB, walk, { sides: false });
  B.wet.prism(span(far, far - s * walkW), -0.2, KERB, walk, { sides: false });
  B.wet.prism(span(near + s * walkW, far - s * walkW), -0.2, 0, road, { sides: false });
  for (const kz of [near + s * walkW, far - s * walkW]) B.dry.box((b.x0 + b.x1) / 2, KERB / 2, kz, b.x1 - b.x0, KERB, 0.2, curb, { ny: false });
  // the white dashes down the middle
  const dash: Paint = { color: mix(INKS.card, INKS.paper, 0.4), id: nextId() };
  for (let x = b.x0 + 1; x < b.x1 - 3; x += 6) B.dry.box(x + 1.5, 0.005, (near + far) / 2, 3, 0.01, 0.14, dash, { ny: false });
  // plane trees along both kerbs, lamps between them, and a bench on the far pavement
  const R0 = B.rand;
  for (const ours of [true, false]) {
    const kz = ours ? near + s * (walkW - 1.1) : far - s * (walkW - 1.1);
    for (let x = b.x0 + 3 + (ours ? 0 : 3.5); x < b.x1 - 2; x += 8) {
      const tx = x + R0.range(-0.4, 0.4);
      if (ours && b.clear && tx > b.clear[0] && tx < b.clear[1]) continue;
      planeTree(B, tx, kz, KERB, 1.15);
    }
    for (let x = b.x0 + 7 + (ours ? 0 : 4); x < b.x1 - 2; x += 24) quayLamp(B, x, kz, KERB, night);
  }
  for (let x = b.x0 + 11; x < b.x1 - 4; x += 24) bench(B, x, far - s * (walkW - 2.2), b.side === 'n' ? 0 : Math.PI, KERB);
  // the houses across it, a few to the length, each with its own stone and shops
  const R = { v: b.seed * 7 + 3 };
  const rand = () => {
    R.v = (R.v * 16807) % 2147483647;
    return R.v / 2147483647;
  };
  let u = b.x0;
  let n = 0;
  while (u < b.x1 - 6) {
    const w = Math.min(b.x1 - u, 12 + rand() * 7);
    const bays = Math.max(3, Math.round(w / 3.0));
    const shops: Shop[] = [];
    for (let k = 0; k < bays; ) {
      const roll = rand();
      if (roll < 0.2 && k < bays - 1) {
        shops.push({ from: k, to: k, kind: 'door', color: FRONTS[Math.floor(rand() * FRONTS.length)] });
        k += 1;
      } else if (roll < 0.75) {
        const to = Math.min(bays - 1, k + (rand() < 0.5 ? 1 : 0));
        shops.push({ from: k, to, kind: 'shop', color: FRONTS[Math.floor(rand() * FRONTS.length)], awning: rand() < 0.5 ? AWNINGS[Math.floor(rand() * AWNINGS.length)] : undefined, lit: night });
        k = to + 1;
      } else {
        shops.push({ from: k, to: k, kind: 'shutter' });
        k += 1;
      }
    }
    const a: XZ = b.side === 'n' ? [u, far] : [u + w, far];
    const c: XZ = b.side === 'n' ? [u + w, far] : [u, far];
    building(B, { runs: [{ a, b: c, bays, shops }], depth: 14, style: 'haussmann', storeys: b.storeys, wall: WALLS[Math.floor(rand() * 3)], balconies: [2, 5], lit: b.lit ?? 0, seed: b.seed + n });
    u += w;
    n++;
  }
}

/* ------------------------------------------------------------------------------------------ */
/* the canal                                                                                  */
/* ------------------------------------------------------------------------------------------ */

/**
 * The quai de Valmy and the canal under a window on its façade, laid from the quai's own plan:
 * our pavement, the road and its zebra to the café's corner, the strip of setts with its plane
 * trees (where the quai has them, and the gap by the corner), the lamps on the edge, the quay
 * walls and their coping, the water, and across it the quai de Jemmapes and its houses.
 */
function canal(B: Build, c: RoomCanal, night: boolean) {
  const P = PLAN;
  const { z0, z1 } = c;
  const span = (x0: number, x1: number, za = z0, zb = z1): XZ[] => [[x0, za], [x1, za], [x1, zb], [x0, zb]];
  const walk: Paint = { color: TONES.pavement, pattern: PATTERN.grit, id: nextId() };
  const road: Paint = { color: TONES.asphalt, pattern: PATTERN.grit, id: nextId() };
  const setts: Paint = { color: mix(TONES.stoneGround, INKS.cobalt, 0.08), pattern: PATTERN.cobbles, id: nextId() };
  const curb: Paint = { color: TONES.curb, id: nextId() };
  const L = P.lancry;
  // our side: the pavement (the rue de Lancry crosses it), the road, the strip
  B.wet.prism(span(P.valmy.walk[0], P.valmy.walk[1], z0, Math.min(z1, L.road[0])), -0.2, KERB, walk, { sides: false });
  if (z1 > L.road[1]) B.wet.prism(span(P.valmy.walk[0], P.valmy.walk[1], L.road[1], z1), -0.2, KERB, walk, { sides: false });
  if (z1 > L.road[0]) B.wet.prism(span(P.valmy.walk[0] - 6, P.valmy.walk[1], Math.max(z0, L.road[0]), Math.min(z1, L.road[1])), -0.2, 0, road, { sides: false });
  B.wet.prism(span(P.valmy.road[0], P.valmy.road[1]), -0.2, 0, road, { sides: false });
  B.wet.prism(span(P.valmy.strip[0], P.valmy.strip[1] - 0.45), -0.2, KERB, setts, { sides: false });
  // across the water
  B.wet.prism(span(P.jemmapes.strip[0] + 0.45, P.jemmapes.strip[1]), -0.2, KERB, setts, { sides: false });
  B.wet.prism(span(P.jemmapes.road[0], P.jemmapes.road[1]), -0.2, 0, road, { sides: false });
  B.wet.prism(span(P.jemmapes.walk[0], P.jemmapes.walk[1]), -0.2, KERB, walk, { sides: false });
  for (const x of [P.valmy.walk[1], P.valmy.strip[0], P.jemmapes.strip[1], P.jemmapes.walk[0]]) B.dry.box(x, KERB / 2, (z0 + z1) / 2, 0.16, KERB, z1 - z0, curb, { ny: false });
  // the zebra over the quai to the café's corner
  const zebra: Paint = { color: mix(INKS.card, INKS.ink, 0.08), id: nextId() };
  for (let x = P.valmy.road[0] + 0.25; x < P.valmy.road[1] - 0.4; x += 1.0) B.dry.box(x + 0.25, 0.004, -10.3, 0.5, 0.008, 2.6, zebra, { ny: false });
  // the quay walls down to the water, their coping, and the water
  const quayWall: Paint = { color: TONES.quayWall, pattern: PATTERN.courses, id: nextId() };
  const coping: Paint = { color: mix(TONES.quayStone, INKS.paper, 0.25), id: nextId() };
  const tide: Paint = { color: mix(TONES.quayWall, INKS.green, 0.45), id: nextId() };
  for (const side of [-1, 1] as const) {
    const xEdge = side * P.canal.x1;
    B.dry.quadXYZ(
      side < 0
        ? [xEdge, P.water - 0.8, z1, xEdge, P.water - 0.8, z0, xEdge, KERB, z0, xEdge, KERB, z1]
        : [xEdge, P.water - 0.8, z0, xEdge, P.water - 0.8, z1, xEdge, KERB, z1, xEdge, KERB, z0],
      quayWall,
    );
    B.dry.box(xEdge + side * 0.22, KERB + 0.06, (z0 + z1) / 2, 0.5, 0.12, z1 - z0, coping, { ny: false });
    B.dry.box(xEdge - side * 0.006, P.water + 0.25, (z0 + z1) / 2, 0.01, 0.5, z1 - z0, tide, { ny: false, py: false });
  }
  B.wet.quadXYZ([P.canal.x0, P.water, z1, P.canal.x1, P.water, z1, P.canal.x1, P.water, z0, P.canal.x0, P.water, z0], { color: TONES.water, wet: 0.9, id: nextId() });
  // the plane trees where the quai has them, the lamps on the edge, the benches facing the water
  const R0 = B.rand;
  for (let z = P.zMin + 4; z < P.zMax - 2; z += 8.5) {
    if (z > z0 - 4 && z < z1 + 4) {
      if (!(z > P.bridge.z0 - 4 && z < P.bridge.westFoot + 3) && !(z > -12.5 && z < -7)) planeTree(B, -14.3, z, KERB, R0.range(0.92, 1.12));
      if (!(z > P.bridge.eastFoot - 3 && z < P.bridge.z1 + 4)) planeTree(B, 14.3, z + 4, KERB, R0.range(0.92, 1.12));
    }
  }
  for (let z = P.zMin + 10; z < P.zMax; z += 23) {
    if (z > z0 && z < z1) quayLamp(B, -11.2, z, KERB, night);
    if (z + 11.5 > z0 && z + 11.5 < z1) quayLamp(B, 11.2, z + 11.5, KERB, night);
  }
  if (z0 < -12.4 && -12.4 < z1) quayLamp(B, -24.6, -12.4, KERB, night);
  for (const z of [-90, -20, 10, 55]) if (z > z0 && z < z1) bench(B, 12.4, z, -Math.PI / 2, KERB);
  // the houses across the water, a few to the length, their shops shut or open, no names on them
  const R = { v: c.seed * 7 + 3 };
  const rand = () => {
    R.v = (R.v * 16807) % 2147483647;
    return R.v / 2147483647;
  };
  const face = P.jemmapes.face;
  let u = z0;
  let n = 0;
  while (u < z1 - 6) {
    const w = Math.min(z1 - u, 12 + rand() * 9);
    const bays = Math.max(3, Math.round(w / 3.1));
    const shops: Shop[] = [];
    for (let k = 0; k < bays; ) {
      const roll = rand();
      if (roll < 0.2 && k < bays - 1) {
        shops.push({ from: k, to: k, kind: 'door', color: FRONTS[Math.floor(rand() * FRONTS.length)] });
        k += 1;
      } else if (roll < 0.7) {
        const to = Math.min(bays - 1, k + (rand() < 0.5 ? 1 : 0));
        shops.push({ from: k, to, kind: 'shop', color: FRONTS[Math.floor(rand() * FRONTS.length)], awning: rand() < 0.45 ? AWNINGS[Math.floor(rand() * AWNINGS.length)] : undefined, lit: night });
        k = to + 1;
      } else {
        shops.push({ from: k, to: k, kind: 'shutter' });
        k += 1;
      }
    }
    building(B, { runs: [{ a: [face, u], b: [face, u + w], bays, shops }], depth: 14, style: rand() < 0.6 ? 'haussmann' : 'faubourg', storeys: c.storeys - (rand() < 0.35 ? 1 : 0), wall: WALLS[Math.floor(rand() * 3)], balconies: [2, 5], lit: c.lit ?? 0, seed: c.seed + n });
    u += w;
    n++;
  }
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
/** A floor you walk: the room's, or one under the sky (a roof); never a room seen and not entered. */
function walked(f: RoomFloor) {
  return (f.zone ?? 'room') !== 'sealed' && f.walk !== false;
}

/** The sheltered ground: what counts as indoors (the camera's reach, the lamps' pools); a roof is not. */
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
    if (fl.drawn !== false) B.dry.prism(fl.shape, fl.y - thick, fl.y, paint, { sides: fl.y > 1, bottom: fl.y > 1 });
    if (walked(fl)) B.walk.push({ shape: fl.shape, y: fl.y });
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
    if (!o.framed) plainHoles.add(h);
  });
  spec.walls.forEach((w, i) => buildWall(B.dry, w, holesOf[i], windowHoles, plainHoles));
  // a doorway with no door in it: its jambs, and the architrave round it on this side
  (spec.holes ?? [])
    .filter((o) => o.framed)
    .forEach((o) => {
      const w = spec.walls[o.wall];
      B.dry.push(frameOf(w.a, w.b).m);
      architrave(B.dry, o.u0, o.u1, o.y0 + 0.01, o.y1, zoned(mix(toneOf(w.tone, ROOM_TONES.ochre), INKS.paper, 0.25), w.zone));
      B.dry.pop();
    });

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
    const [b0] = pair(w.base);
    if (win.shutters === 'closed') slatLight(B, f, win, b0, 4.2);
    balconyOut(B, f, win, b0);
    if (win.sun && win.shutters !== 'closed') {
      const p = new Vector3((win.u0 + win.u1) / 2, 0, 0.5).applyMatrix4(f.m);
      const under = spec.floors.find((fl) => Math.abs(fl.y - b0) < 0.05 && inPoly(fl.shape, p.x, p.z));
      sunThrough(B, f, win, b0, under?.finish ?? 'boards', AMBIANCES[spec.ambiance].sunDir);
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
  (spec.boulevards ?? []).forEach((b) => boulevard(B, b, spec.ambiance === 'nuit'));
  (spec.canals ?? []).forEach((c) => canal(B, c, spec.ambiance === 'nuit'));

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
    // a room under the sky has nowhere dry
    dry: shelter.length ? [Math.min(...sx) - 0.4, Math.min(...sz) - 0.4, Math.max(...sx) + 0.4, Math.max(...sz) + 0.4] : [0, 0, -1, -1],
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
