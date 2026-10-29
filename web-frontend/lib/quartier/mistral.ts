/**
 * Le Mistral, inside and out (canon: `docs/story/season-1/10-lieux-et-images.md`).
 *
 * A narrow corner café-bar on the quai de Valmy: the worn zinc with its hinged flap, Odile's
 * small round-topped stool at the far end, the ox-blood booth at the back with Gus's corner seat,
 * the long mirror behind the zinc, the till with an old photograph, «L.»'s small painting above
 * the zinc, warm amber globes, and outside the vertical red neon. The room is built into the
 * hollow ground floor of the corner building, so you walk in through the door and see the street
 * through the windows, and from the quai you see Gus on the bench through the glass.
 *
 * The marks are where people stand in the season's scenes; the stage director (`stage.ts`)
 * blocks every beat with them.
 */
import { Group, Vector3 } from 'three';

import type { Seat } from './cast';
import { KERB, awning, chair, fitText, frameOf, rectIn, worldOf } from './kit';
import type { Build, BuildingInfo, Frame } from './kit';
import { PATTERN, Press, nextId } from './geo';
import type { Paint, Shape2 } from './geo';
import { INKS, TONES, css, mix, rgb } from './palette';
import { letteringArt, slateArt, SERIF, SANS } from './signs';
import { facadeLining, globeLamp, roundTable, wainscotWall } from './room';

/** The café's room, in world coordinates. */
export const ROOM = {
  x0: -37.6,
  x1: -27.26,
  z0: -18.75,
  z1: -6.26,
  floor: 0.16,
  ceiling: 4.25,
};

export const MARKS = {
  /** outside, where the door is reached */
  doorOut: new Vector3(-27.75, KERB, -6.75),
  /** just inside the door */
  doorIn: new Vector3(-29.35, ROOM.floor, -8.65),
  /** where you stand at the zinc */
  atZinc: new Vector3(-33.85, ROOM.floor, -13.3),
  /** behind the zinc, on the duckboard (the floor there is raised, so the bar is at her waist) */
  zincInside: new Vector3(-36.15, ROOM.floor + 0.3, -13.4),
  odileStool: new Vector3(-34.25, ROOM.floor, -16.9),
  /** the booth: Gus's corner seat, and the bench he stands on */
  boothCorner: new Vector3(-28.35, ROOM.floor, -18.25),
  boothBench: new Vector3(-29.6, ROOM.floor + 0.45, -18.3),
  boothMiddle: new Vector3(-31.2, ROOM.floor, -18.25),
  boothLeft: new Vector3(-32.7, ROOM.floor, -18.25),
  /** the chair opposite the booth that Marin pulls out */
  pulledChair: new Vector3(-30.4, ROOM.floor, -16.55),
  /** Gus, leaning on the zinc beside you */
  zincBeside: new Vector3(-34.1, ROOM.floor, -11.3),
  /** where Gus stops to bow, off to your right so the booth stays in view */
  bowStop: new Vector3(-32.0, ROOM.floor, -14.6),
  /** where the camera looks for the key on the zinc */
  zincTop: new Vector3(-35.15, ROOM.floor + 1.1, -13.35),
  doorway: new Vector3(-28.75, ROOM.floor, -7.75),
  painting: new Vector3(-37.5, 3.15, -13.6),
};

export interface MistralParts {
  /** the two door leaves, hinged, for the director to open */
  doors: Group[];
  /** the bell over the door (for the sound's position) */
  bell: Vector3;
  /** where the neon hangs, and its blade's two faces */
  neon: { center: Vector3; normal: Vector3; tangent: Vector3; height: number; width: number };
  /** lights whose glow the director may dim (the globes) */
  globes: Vector3[];
  /** the chair Marin pulls out for you (a moving part, tucked under its table at first) */
  chair: Group;
}

/** Where the pulled chair stands tucked in, and where Marin leaves it for you. */
export const CHAIR = {
  tucked: new Vector3(-30.5, ROOM.floor, -17.0),
  pulled: new Vector3(-30.2, ROOM.floor, -16.1),
};

/** The two ordinary stools along the zinc. */
const STOOLS = [new Vector3(-34.25, ROOM.floor, -15.0), new Vector3(-34.25, ROOM.floor, -12.2)];

/**
 * Where people sit (the cast in the round, `cast3d/figure.ts`): the booth's three places, on its
 * leather and facing the room, and the stools at the zinc, facing it but turning a long way round
 * to whoever they talk to. A paper card stands on these marks.
 */
export const SEATS: Seat[] = [
  ...[MARKS.boothCorner, MARKS.boothMiddle, MARKS.boothLeft].map((at) => ({ at, height: 0.56, yaw: 0, turn: 0.8 })),
  ...[...STOOLS, MARKS.odileStool].map((at, i) => ({ at, height: i < 2 ? 0.81 : 0.78, yaw: -Math.PI / 2, turn: 1.3, high: true })),
];

/** A café crème on its saucer, for Margaux to set down in front of you (built about its foot). */
export function cafeCreme(): Press {
  const P = new Press();
  const porcelain: Paint = { color: INKS.card, wet: 0.6, id: nextId(), indoor: true };
  P.lathe(0, 0, 0, [[0.075, 0], [0.082, 0.008], [0.06, 0.011], [0.03, 0.012], [0, 0.012]], 16, porcelain);
  P.lathe(0, 0.012, 0, [[0.026, 0], [0.04, 0.012], [0.047, 0.05], [0.049, 0.068], [0.044, 0.068], [0, 0.064]], 16, porcelain);
  P.lathe(0, 0.0765, 0, [[0.043, 0], [0, 0.001]], 16, { color: mix(INKS.ochre, INKS.card, 0.55), id: porcelain.id, indoor: true });
  P.sweep(new Vector3(0.046, 0.06, 0), new Vector3(0.07, 0.045, 0), [[-0.006, -0.006], [0.006, -0.006], [0.006, 0.006], [-0.006, 0.006]], porcelain, { closed: true });
  P.sweep(new Vector3(0.07, 0.045, 0), new Vector3(0.046, 0.03, 0), [[-0.006, -0.006], [0.006, -0.006], [0.006, 0.006], [-0.006, 0.006]], porcelain, { closed: true });
  return P;
}

const OXBLOOD = TONES.oxblood;
const FRONT = mix(INKS.green, INKS.ink, 0.42);
const GILT = mix(INKS.sunflower, INKS.ochre, 0.45);

export function buildMistral(B: Build, building: BuildingInfo): MistralParts {
  void building;
  const D = B.dry;
  const indoor = (p: Paint): Paint => ({ ...p, indoor: true });
  const R = ROOM;
  const g = 4.6;
  const openTop = g - 1.15;

  /* ---- the room's shell ------------------------------------------------------------------ */
  const wallUpper: Paint = indoor({ color: mix(INKS.paper, INKS.ochre, 0.34), id: nextId() });
  const wainscot: Paint = indoor({ color: mix(TONES.wainscot, INKS.ink, 0.12), id: nextId() });
  const rail: Paint = indoor({ color: TONES.wood, id: nextId() });
  const ceiling: Paint = indoor({ color: mix(INKS.paper, INKS.ochre, 0.22), id: nextId() });
  const floor: Paint = indoor({ color: mix(INKS.card, INKS.ochre, 0.06), pattern: PATTERN.tiles, id: nextId() });
  // floor and ceiling (the chamfer cuts the south-east corner)
  // the chamfer's inner face: the line x + z = -36, pulled 0.26 m into the room
  const cornerQ: [number, number] = [R.x1, -9.11];
  const cornerL: [number, number] = [-30.11, R.z1];
  const plan: Shape2 = [[R.x0, R.z0], [R.x1, R.z0], cornerQ, cornerL, [R.x0, R.z1]];
  D.prism(plan, R.floor - 0.2, R.floor, floor, { sides: false });
  D.prism(plan, R.ceiling, R.ceiling + 0.05, ceiling, { top: false, sides: false, bottom: true });
  // back wall (west), behind the zinc, and the north wall behind the booth: wainscot, rail, upper
  // wall, the cornice in the ceiling's paint (the room kit's wall, `room.ts`); walls run with the
  // room on their right
  const shell = { wainscot, rail, upper: wallUpper, cornice: ceiling };
  wainscotWall(D, [R.x0, R.z1], [R.x0, R.z0], R.floor, R.ceiling, shell);
  wainscotWall(D, [R.x0, R.z0], [R.x1, R.z0], R.floor, R.ceiling, shell);
  // the façades' inner lining: above the openings, and the piers (inner faces of the façades,
  // walked with the room on the right)
  facadeLining(D, cornerQ, [R.x1, R.z0], 0.24, 9.29, openTop, R.ceiling, wallUpper);
  facadeLining(D, cornerL, cornerQ, 0.244, 3.784, openTop, R.ceiling, wallUpper);
  facadeLining(D, [R.x0, R.z1], cornerL, 1.38, 7.25, openTop, R.ceiling, wallUpper);

  /* ---- the shop front, outside ----------------------------------------------------------- */
  const quai = frameOf([-27, -9], [-27, -28.5]);
  const cham = frameOf([-30, -6], [-27, -9]);
  const lan = frameOf([-53, -6], [-30, -6]);
  const front: Paint = { color: FRONT, id: nextId() };
  const glassRuns: Array<{ f: Frame; u0: number; u1: number; door?: [number, number] }> = [
    { f: quai, u0: 0.35, u1: 9.4 },
    { f: cham, u0: 0.35, u1: 3.89, door: [1.42, 2.82] },
    { f: lan, u0: 16.78, u1: 22.65 },
  ];
  for (const run of glassRuns) {
    D.push(run.f.m);
    const { u0, u1 } = run;
    // pilasters, stall riser, transom rail, the frame's head
    D.box(u0 + 0.09, openTop / 2, -0.04, 0.18, openTop, 0.14, front, { nz: false });
    D.box(u1 - 0.09, openTop / 2, -0.04, 0.18, openTop, 0.14, front, { nz: false });
    D.box((u0 + u1) / 2, openTop - 0.15, -0.06, u1 - u0, 0.3, 0.1, front, { nz: false });
    const spans: Array<[number, number]> = run.door ? [[u0 + 0.18, run.door[0]], [run.door[1], u1 - 0.18]] : [[u0 + 0.18, u1 - 0.18]];
    for (const [a, b] of spans) {
      D.box((a + b) / 2, 0.38, -0.08, b - a, 0.76, 0.1, front, { nz: false });
      D.box((a + b) / 2, 0.78, -0.03, b - a + 0.02, 0.05, 0.16, { color: mix(FRONT, INKS.paper, 0.15), id: front.id }, { nz: false });
      // glass, and its glazing bars
      B.glass.quadXYZ([a, 0.8, -0.1, b, 0.8, -0.1, b, openTop - 0.3, -0.1, a, openTop - 0.3, -0.1], { color: TONES.glass, id: 61 }, 61);
      const n = Math.max(1, Math.round((b - a) / 1.5));
      for (let k = 1; k < n; k++) D.box(a + ((b - a) * k) / n, (0.8 + openTop - 0.3) / 2, -0.09, 0.06, openTop - 1.1, 0.06, front, { nz: false });
      D.box((a + b) / 2, openTop - 0.75, -0.09, b - a, 0.05, 0.06, front, { nz: false });
      // the nav sees the glass as a wall
      const shape = rectIn(run.f, a, b, -0.2, 0.05);
      B.blocks.push(shape);
    }
    if (run.door) {
      const [a, b] = run.door;
      D.box(a - 0.04, openTop / 2, -0.06, 0.08, openTop, 0.12, front, { nz: false });
      D.box(b + 0.04, openTop / 2, -0.06, 0.08, openTop, 0.12, front, { nz: false });
      D.box((a + b) / 2, 2.72, -0.06, b - a, 0.1, 0.12, front, { nz: false });
      B.glass.quadXYZ([a, 2.78, -0.1, b, 2.78, -0.1, b, openTop - 0.3, -0.1, a, openTop - 0.3, -0.1], { color: TONES.glass, id: 61 }, 61);
      // a step up at the threshold
      D.box((a + b) / 2, R.floor / 2, 0.15, b - a + 0.2, R.floor, 0.4, { color: TONES.marble, id: nextId() }, { ny: false });
    }
    D.pop();
  }
  // the fascia boards with gilt lettering
  const fascia = (f: Frame, u0: number, u1: number, text: string, key: string) => {
    D.push(f.m);
    D.box((u0 + u1) / 2, openTop + 0.48, 0.03, u1 - u0, 0.82, 0.12, front, { nz: false });
    D.pop();
    const [x, z] = worldOf(f, (u0 + u1) / 2, 0.1);
    B.signs.push({ key, center: new Vector3(x, openTop + 0.48, z), normal: f.n.clone(), width: Math.min(u1 - u0 - 0.3, 4.6), height: 0.66, density: 200, draw: letteringArt(text, GILT, { serif: true, weight: 600 }) });
  };
  fascia(quai, 0.35, 9.4, 'Le Mistral', 'fascia:mistral-quai');
  fascia(lan, 16.78, 22.65, 'Le Mistral', 'fascia:mistral-lancry');
  fascia(cham, 0.35, 3.89, 'Café · Bar', 'fascia:mistral-corner');
  // gilt lettering on the glass
  {
    const [x, z] = worldOf(quai, 4.9, -0.08);
    B.signs.push({ key: 'glass:vins', center: new Vector3(x, 2.2, z), normal: quai.n.clone(), width: 2.6, height: 0.42, density: 220, draw: letteringArt('Vins · Café · Bières', GILT, { serif: true }) });
    const [x2, z2] = worldOf(lan, 19.7, -0.08);
    B.signs.push({ key: 'glass:depuis', center: new Vector3(x2, 2.2, z2), normal: lan.n.clone(), width: 2.2, height: 0.4, density: 220, draw: letteringArt('depuis 1998', GILT, { serif: true }) });
  }
  // the awning over the quai windows, oxblood and paper
  D.push(quai.m);
  awning(B, 0.3, 9.45, openTop + 0.02, OXBLOOD);
  D.pop();
  // the slate by the door
  {
    const [x, z] = worldOf(quai, 0.9, 0.5);
    const slate = { color: mix(TONES.wood, INKS.ink, 0.4), id: nextId() };
    D.at(x, KERB, z, Math.atan2(quai.n.x, quai.n.z), () => {
      D.bar(new Vector3(-0.32, 0, 0.2), new Vector3(-0.3, 1.25, 0), 0.05, slate);
      D.bar(new Vector3(0.32, 0, 0.2), new Vector3(0.3, 1.25, 0), 0.05, slate);
      D.bar(new Vector3(-0.32, 0, -0.25), new Vector3(-0.3, 1.25, 0), 0.04, slate);
      D.bar(new Vector3(0.32, 0, -0.25), new Vector3(0.3, 1.25, 0), 0.04, slate);
    });
    B.signs.push({ key: 'slate', center: new Vector3(x + quai.n.x * 0.12, KERB + 0.78, z + quai.n.z * 0.12), normal: quai.n.clone(), width: 0.62, height: 0.92, density: 240, tilt: 0.16, draw: slateArt(['Ce soir', 'Soupe à l’oignon', 'Croque-monsieur', 'Café crème · 2,60']) });
    B.blocks.push(rectIn(quai, 0.5, 1.3, 0.2, 0.85));
  }
  // the corner pavement in front of the chamfer
  B.wet.tri(new Vector3(-30, KERB, -6), new Vector3(-27, KERB, -6), new Vector3(-27, KERB, -9), { color: TONES.pavement, pattern: PATTERN.grit, id: 2 }, 2);
  B.walk.push({ shape: [[-30, -6], [-27, -6], [-27, -9]], y: KERB });
  B.walk.push({ shape: rectIn(cham, 1.42, 2.82, -0.9, 0.45), y: R.floor });

  /* ---- the zinc ------------------------------------------------------------------------- */
  const zx = -34.8; // the zinc's front face
  const zN = -17.4;
  const zS = -11.5;
  const wood: Paint = indoor({ color: mix(INKS.green, INKS.ink, 0.3), id: nextId() });
  const woodDark: Paint = indoor({ color: mix(INKS.green, INKS.ink, 0.48), id: wood.id });
  const zinc: Paint = indoor({ color: TONES.pewter, wet: 1, id: nextId() });
  const brass: Paint = indoor({ color: TONES.brass, wet: 0.8, id: nextId() });
  D.box(zx - 0.38, R.floor + 0.52, (zN + zS) / 2, 0.72, 1.04, zS - zN, wood, { ny: false });
  // panels on the front
  const panels = Math.round((zS - zN) / 0.9);
  for (let i = 0; i < panels; i++) {
    const z = zN + ((i + 0.5) * (zS - zN)) / panels;
    D.box(zx + 0.012, R.floor + 0.55, z, 0.02, 0.62, (zS - zN) / panels - 0.16, woodDark, { nx: false });
  }
  // the zinc top with its rolled edge
  D.sweep(new Vector3(zx - 0.8, R.floor + 1.04, zS + 0.04), new Vector3(zx - 0.8, R.floor + 1.04, zN - 0.04), [[0, 0], [0.86, 0], [0.9, 0.025], [0.88, 0.06], [0, 0.06]], zinc, { caps: true });
  // the hinged flap: the top continues over the gap, a hinge line, no panel beneath
  const flap: Paint = indoor({ color: mix(TONES.pewter, INKS.ink, 0.06), wet: 1, id: nextId() });
  D.box(zx - 0.38, R.floor + 1.07, zS + 0.42, 0.84, 0.05, 0.76, flap);
  D.box(zx - 0.38, R.floor + 1.1, zS + 0.03, 0.6, 0.02, 0.04, brass);
  D.box(zx - 0.38, R.floor + 0.52, zS + 0.82, 0.72, 1.04, 0.06, wood, { ny: false });
  // the foot rail
  D.sweep(new Vector3(zx + 0.12, R.floor + 0.18, zS), new Vector3(zx + 0.12, R.floor + 0.18, zN), [[-0.025, -0.025], [0.025, -0.025], [0.025, 0.025], [-0.025, 0.025]], brass, { closed: true });
  B.blocks.push([[R.x0, zN - 0.1], [zx + 0.15, zN - 0.1], [zx + 0.15, zS + 0.9], [R.x0, zS + 0.9]]);

  // Odile's stool: small, round-topped, at the far end
  {
    const s = MARKS.odileStool;
    D.lathe(s.x, R.floor, s.z, [[0.16, 0], [0.14, 0.05], [0.05, 0.12], [0.04, 0.62], [0.17, 0.66], [0.19, 0.7], [0.17, 0.76], [0, 0.79]], 10, indoor({ color: mix(TONES.wood, INKS.ochre, 0.15), id: nextId() }));
    D.lathe(s.x, R.floor + 0.25, s.z, [[0.13, 0], [0.13, 0.03]], 10, brass);
    B.blocks.push([[s.x - 0.25, s.z - 0.25], [s.x + 0.25, s.z - 0.25], [s.x + 0.25, s.z + 0.25], [s.x - 0.25, s.z + 0.25]]);
  }
  // two ordinary stools further along
  for (const s of STOOLS) {
    D.lathe(s.x, R.floor, s.z, [[0.2, 0], [0.04, 0.1], [0.035, 0.7], [0.18, 0.74], [0.18, 0.8], [0, 0.82]], 8, indoor({ color: mix(INKS.ink, INKS.cobalt, 0.2), id: nextId() }));
  }

  /* ---- behind the zinc: back bar, bottles, the long mirror, the machine, the till -------- */
  const backX = R.x0 + 0.02;
  // the duckboard: slats on a raised floor, so whoever serves stands a head above the zinc
  D.box((backX + 0.64 + zx - 0.74) / 2, R.floor + 0.15, (zN + zS) / 2, zx - 0.74 - backX - 0.64, 0.3, zS - zN, indoor({ color: mix(TONES.wood, INKS.ochre, 0.2), pattern: PATTERN.planks, id: nextId() }), { ny: false });
  D.box(backX + 0.32, R.floor + 0.46, (zN + zS) / 2 - 0.4, 0.64, 0.92, zS - zN + 1.6, woodDark, { ny: false });
  D.box(backX + 0.34, R.floor + 0.94, (zN + zS) / 2 - 0.4, 0.68, 0.04, zS - zN + 1.7, indoor({ color: TONES.marble, id: nextId() }));
  // the mirror, and the frame round it
  const mirror: Paint = indoor({ color: mix(INKS.cobalt, INKS.ink, 0.55), wet: 1, id: nextId() });
  D.quadXYZ([backX + 0.01, R.floor + 1.25, zN + 0.2, backX + 0.01, R.floor + 1.25, zS - 0.2, backX + 0.01, R.floor + 2.55, zS - 0.2, backX + 0.01, R.floor + 2.55, zN + 0.2], mirror);
  const frameP: Paint = indoor({ color: GILT, id: nextId() });
  D.box(backX + 0.03, R.floor + 2.6, (zN + zS) / 2, 0.06, 0.1, zS - zN - 0.3, frameP);
  D.box(backX + 0.03, R.floor + 1.2, (zN + zS) / 2, 0.06, 0.1, zS - zN - 0.3, frameP);
  // shelves of bottles on the mirror, two rows
  const bottleTones = [mix(INKS.green, INKS.ink, 0.2), mix(INKS.ochre, INKS.vermilion, 0.2), mix(INKS.card, INKS.cobalt, 0.15), INKS.green, mix(INKS.sunflower, INKS.ochre, 0.4), mix(INKS.vermilion, INKS.ink, 0.3)];
  for (const sy of [1.55, 2.1]) {
    D.box(backX + 0.12, R.floor + sy, (zN + zS) / 2, 0.22, 0.03, zS - zN - 0.5, indoor({ color: GILT, id: frameP.id }));
    for (let z = zN + 0.5; z < zS - 0.4; z += B.rand.range(0.13, 0.2)) {
      const h = B.rand.range(0.24, 0.36);
      D.lathe(backX + 0.12, R.floor + sy + 0.015, z, [[0.035, 0], [0.035, h * 0.62], [0.012, h * 0.8], [0.012, h], [0, h]], 6, indoor({ color: B.rand.pick(bottleTones), id: nextId(), wet: 0.4 }), { flat: true });
    }
  }
  // the coffee machine: brass dome and chrome body
  {
    const z = zS - 0.9;
    const chrome: Paint = indoor({ color: mix(INKS.card, INKS.cobalt, 0.12), wet: 1, id: nextId() });
    D.box(backX + 0.32, R.floor + 1.2, z, 0.5, 0.5, 0.75, chrome);
    D.lathe(backX + 0.32, R.floor + 1.45, z, [[0.18, 0], [0.16, 0.2], [0.08, 0.32], [0.02, 0.4], [0, 0.42]], 10, brass);
    for (const dz of [-0.2, 0.2]) D.cylinder(backX + 0.62, R.floor + 1.1, z + dz, 0.035, 0.035, 0.14, 6, chrome);
  }
  // the till at the far end of the zinc (clear of Margaux), a photograph tucked behind it
  {
    const z = zN + 0.55;
    const till: Paint = indoor({ color: mix(INKS.ink, INKS.cobalt, 0.2), id: nextId() });
    D.box(zx - 0.42, R.floor + 1.2, z, 0.42, 0.26, 0.36, till);
    D.box(zx - 0.48, R.floor + 1.38, z, 0.3, 0.12, 0.32, indoor({ color: mix(INKS.card, INKS.ochre, 0.2), id: nextId() }));
    B.signs.push({ key: 'till-photo', center: new Vector3(zx - 0.64, R.floor + 1.42, z), normal: new Vector3(1, 0, 0), width: 0.12, height: 0.16, density: 900, tilt: -0.15, draw: oldPhotoArt, indoor: true });
  }
  // «L.»'s painting above the zinc, in its gilt frame
  {
    const p = MARKS.painting;
    D.box(p.x + 0.03, p.y, p.z, 0.06, 0.62, 0.78, frameP);
    B.signs.push({ key: 'painting-L', center: new Vector3(p.x + 0.075, p.y, p.z), normal: new Vector3(1, 0, 0), width: 0.62, height: 0.48, density: 600, draw: paintingArt, indoor: true });
  }
  // the slate inside: tonight's soup
  B.signs.push({ key: 'slate-in', center: new Vector3(R.x0 + 0.08, 2.45, -9.0), normal: new Vector3(1, 0, 0), width: 0.8, height: 1.0, density: 240, draw: slateArt(['Soupe du jour', 'à l’oignon', 'Œufs mayo', 'Tarte Tatin']), indoor: true });
  // above the booth, two old posters in black frames (in T4 this wall becomes the Polaroids),
  // and the clock over the far end of the zinc
  {
    const z = R.z0 + 0.02;
    const frameInk: Paint = indoor({ color: mix(INKS.ink, OXBLOOD, 0.2), id: nextId() });
    const posters: Array<[number, string, (ctx: CanvasRenderingContext2D, w: number, h: number) => void]> = [
      [-32.15, 'poster-canal', canalPosterArt],
      [-28.3, 'poster-bal', balPosterArt],
    ];
    for (const [x, key, draw] of posters) {
      D.box(x, 2.5, z, 0.78, 1.06, 0.03, frameInk);
      B.signs.push({ key, center: new Vector3(x, 2.5, z + 0.02), normal: new Vector3(0, 0, 1), width: 0.7, height: 0.98, density: 360, draw, indoor: true });
    }
    B.signs.push({ key: 'clock', center: new Vector3(-35.9, 3.05, R.z0 + 0.03), normal: new Vector3(0, 0, 1), width: 0.52, height: 0.52, density: 480, draw: clockArt, indoor: true });
  }

  /* ---- the booth at the back: ox-blood leather, Gus's corner ---------------------------- */
  {
    const bz = R.z0;
    const x0 = -33.7;
    const x1 = R.x1 + 0.02;
    const leather: Paint = indoor({ color: OXBLOOD, id: nextId() });
    const leather2: Paint = indoor({ color: mix(OXBLOOD, INKS.ink, 0.15), id: nextId() });
    D.box((x0 + x1) / 2, R.floor + 0.22, bz + 0.33, x1 - x0, 0.44, 0.66, woodDark, { ny: false });
    D.box((x0 + x1) / 2, R.floor + 0.5, bz + 0.3, x1 - x0, 0.12, 0.6, leather);
    // the back, tufted in vertical rolls
    const rolls = Math.round((x1 - x0) / 0.42);
    for (let i = 0; i < rolls; i++) {
      const xa = x0 + ((x1 - x0) * i) / rolls;
      const xb = x0 + ((x1 - x0) * (i + 1)) / rolls;
      D.box((xa + xb) / 2, R.floor + 0.95, bz + 0.08, xb - xa - 0.02, 0.78, 0.14, i % 2 ? leather : leather2);
    }
    D.box((x0 + x1) / 2, R.floor + 1.38, bz + 0.06, x1 - x0, 0.06, 0.16, wood);
    // the booth's end at the zinc side
    D.box(x0 - 0.05, R.floor + 0.7, bz + 0.33, 0.1, 1.4, 0.66, woodDark);
    // two tables in front, marble on iron
    for (const tx of [-31.9, -29.1]) {
      D.box(tx, R.floor + 0.74, bz + 1.0, 1.15, 0.04, 0.62, indoor({ color: TONES.marble, wet: 0.4, id: nextId() }));
      D.cylinder(tx, R.floor, bz + 1.0, 0.04, 0.04, 0.72, 6, indoor({ color: mix(TONES.iron, INKS.ink, 0.3), id: nextId() }), { flat: true });
      D.box(tx, R.floor + 0.02, bz + 1.0, 0.6, 0.04, 0.4, indoor({ color: mix(TONES.iron, INKS.ink, 0.3), id: nextId() }));
      B.blocks.push([[tx - 0.62, bz + 0.6], [tx + 0.62, bz + 0.6], [tx + 0.62, bz + 1.36], [tx - 0.62, bz + 1.36]]);
    }
    B.blocks.push([[x0 - 0.1, bz], [x1, bz], [x1, bz + 0.68], [x0 - 0.1, bz + 0.68]]);
    // Marin's bowl of soup, a glass, a carafe
    D.lathe(-31.6, R.floor + 0.76, bz + 1.05, [[0.05, 0], [0.09, 0.05], [0.1, 0.08], [0, 0.08]], 10, indoor({ color: mix(INKS.card, INKS.cobalt, 0.08), id: nextId() }));
    D.lathe(-29.3, R.floor + 0.76, bz + 0.95, [[0.035, 0], [0.04, 0.12], [0, 0.12]], 8, indoor({ color: mix(INKS.vermilion, INKS.ink, 0.35), wet: 0.6, id: nextId() }));
    D.lathe(-28.9, R.floor + 0.76, bz + 1.1, [[0.06, 0], [0.07, 0.12], [0.03, 0.22], [0.03, 0.28], [0, 0.28]], 8, indoor({ color: mix(INKS.cobalt, INKS.paper, 0.6), wet: 0.8, id: nextId() }));
  }
  // chairs opposite the booth (one of them is Marin's to pull out)
  chair(B, -31.9, -16.75, Math.PI, false, R.floor);
  chair(B, -29.1, -16.75, Math.PI, false, R.floor);
  // each chair blocks its own square, so the way out of the booth runs between them
  B.blocks.push([[-32.2, -17.05], [-31.6, -17.05], [-31.6, -16.45], [-32.2, -16.45]]);
  B.blocks.push([[-29.4, -17.05], [-28.8, -17.05], [-28.8, -16.45], [-29.4, -16.45]]);

  /* ---- tables by the windows -------------------------------------------------------------- */
  roundTable(B, -28.25, -14.6, [Math.PI / 2 + 0.3, -Math.PI / 2 - 0.2], R.floor);
  roundTable(B, -28.25, -11.4, [Math.PI / 2, 0.1], R.floor);
  roundTable(B, -33.4, -7.25, [Math.PI, 0.6], R.floor);
  roundTable(B, -35.8, -7.25, [Math.PI + 0.3], R.floor);
  // the coat stand by the door, a coat on it
  {
    const x = -27.75;
    const z = -9.6;
    const stand: Paint = indoor({ color: TONES.wood, id: nextId() });
    D.cylinder(x, R.floor, z, 0.03, 0.03, 1.85, 6, stand, { flat: true });
    D.cylinder(x, R.floor, z, 0.25, 0.08, 0.06, 6, stand, { flat: true });
    D.ball(x, R.floor + 1.45, z + 0.1, 0.22, 0.5, 0.14, indoor({ color: mix(INKS.ochre, INKS.ink, 0.3), id: nextId() }), 1);
    B.blocks.push([[x - 0.3, z - 0.3], [x + 0.3, z - 0.3], [x + 0.3, z + 0.3], [x - 0.3, z + 0.3]]);
  }
  // the back door, to the kitchen
  D.box(R.x0 + 0.05, R.floor + 1.1, -18.1, 0.06, 2.2, 0.9, indoor({ color: mix(INKS.green, INKS.ink, 0.35), id: nextId() }));

  /* ---- light: three amber globes, a sconce over the booth --------------------------------- */
  const globes = [new Vector3(-31.6, 3.25, -15.6), new Vector3(-31.6, 3.25, -11.0), new Vector3(-30.0, 3.25, -8.0)];
  const globePaint: Paint = indoor({ color: mix(INKS.card, INKS.sunflower, 0.35), glow: 1, id: nextId() });
  const cord: Paint = indoor({ color: INKS.ink, id: nextId() });
  for (const p of globes) globeLamp(B, p, R.ceiling, { glass: globePaint, cord, brass }, { power: 1.0, range: 7.5 });
  {
    const s = new Vector3(-30.2, 2.2, R.z0 + 0.12);
    D.lathe(s.x, s.y - 0.12, s.z + 0.1, [[0.06, 0], [0.12, 0.15], [0.1, 0.2], [0, 0.2]], 8, globePaint, { flat: true });
    B.lamps.push({ pos: new Vector3(s.x, 2.0, s.z + 0.5), color: rgb(mix(INKS.sunflower, INKS.ochre, 0.3)), power: 0.8, range: 4.5, glint: false, indoor: true });
  }
  // the light the room throws out through its windows onto the wet pavement
  for (const [x, z] of [[-26.2, -10.6], [-26.2, -14.0], [-26.2, -17.2], [-33.2, -5.2], [-27.9, -6.9]] as Array<[number, number]>) {
    B.lamps.push({ pos: new Vector3(x, 1.4, z), color: rgb(mix(INKS.sunflower, INKS.vermilion, 0.12)), power: 0.5, range: 5.2, glint: true });
  }

  /* ---- the walkable room ----------------------------------------------------------------- */
  B.walk.push({ shape: plan, y: R.floor });
  // the rest of the hollow ground floor stays solid
  B.blocks.push([[-53, -28.5], [-27, -28.5], [-27, R.z0 - 0.05], [-53, R.z0 - 0.05]]);
  B.blocks.push([[-53, R.z0 - 0.05], [R.x0 - 0.05, R.z0 - 0.05], [R.x0 - 0.05, -6], [-53, -6]]);
  // façade piers between the window runs, and the corners
  B.blocks.push(rectIn(quai, 9.3, 19.5, -0.4, 0.02));
  B.blocks.push(rectIn(lan, 0, 16.9, -0.4, 0.02));
  B.blocks.push(rectIn(quai, -0.1, 0.45, -0.4, 0.02));
  B.blocks.push(rectIn(cham, -0.1, 0.45, -0.4, 0.02));
  B.blocks.push(rectIn(cham, 3.8, 4.4, -0.4, 0.02));
  B.blocks.push(rectIn(lan, 22.55, 23.1, -0.4, 0.02));

  /* ---- the door leaves (moving parts), the bell, the neon ----------------------------- */
  const doors: Group[] = [];
  const [a, b] = glassRuns[1].door ?? [1.42, 2.82];
  for (const [hinge, sign] of [[a, 1], [b, -1]] as Array<[number, number]>) {
    const leaf = new Press();
    const w = (b - a) / 2;
    const p: Paint = { color: FRONT, id: nextId() };
    // built about the hinge at the origin, the leaf extending along +u (or -u)
    leaf.box((sign * w) / 2, 1.36, 0, w, 0.18, 0.06, p);
    leaf.box((sign * w) / 2, 0.12, 0, w, 0.24, 0.06, p);
    leaf.box((sign * w) / 2, 2.58, 0, w, 0.14, 0.06, p);
    leaf.box(sign * 0.05, 1.33, 0, 0.1, 2.66, 0.06, p);
    leaf.box(sign * (w - 0.05), 1.33, 0, 0.1, 2.66, 0.06, p);
    leaf.box(sign * (w - 0.14), 1.3, 0.05, 0.03, 0.3, 0.04, { color: TONES.brass, wet: 0.8, id: nextId() });
    const g2 = new Group();
    const [hx, hz] = worldOf(cham, hinge, -0.12);
    g2.position.set(hx, R.floor, hz);
    g2.rotation.y = Math.atan2(-cham.t.z, cham.t.x);
    g2.userData.press = leaf;
    g2.userData.sign = sign;
    doors.push(g2);
  }
  const [bx, bz] = worldOf(cham, 2.12, -0.3);
  const bell = new Vector3(bx, 2.75, bz);

  const neonCenter = new Vector3(-28.5 + 0.707 * 0.62, 7.1, -7.5 + 0.707 * 0.62);
  const neon = { center: neonCenter, normal: new Vector3(0.707, 0, -0.707), tangent: new Vector3(0.707, 0, 0.707), height: 4.0, width: 0.82 };
  // the bracket that holds the blade off the corner
  const iron: Paint = { color: TONES.iron, id: nextId() };
  for (const y of [5.25, 8.95]) {
    D.bar(new Vector3(-28.5 + 0.707 * 0.05, y, -7.5 + 0.707 * 0.05), new Vector3(neonCenter.x + 0.707 * 0.42, y, neonCenter.z + 0.707 * 0.42), 0.05, iron);
  }
  B.lamps.push({ pos: new Vector3(neonCenter.x + 0.4, 6.0, neonCenter.z + 0.4), color: rgb(INKS.vermilion), power: 1.6, range: 10, glint: true });
  // the chair Marin pulls out: built about its own foot, so the director can slide it
  const chairPress = new Press();
  chair({ ...B, dry: chairPress }, 0, 0, Math.PI, false, 0);
  const pulled = new Group();
  pulled.position.copy(CHAIR.tucked);
  pulled.userData.press = chairPress;
  return { doors, bell, neon, globes, chair: pulled };
}

/** The photograph tucked behind the till: faded, a woman and a girl at the zinc. */
function oldPhotoArt(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.fillStyle = css(INKS.card);
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = css(mix(INKS.ochre, INKS.paper, 0.55));
  ctx.fillRect(w * 0.08, h * 0.07, w * 0.84, h * 0.72);
  ctx.fillStyle = css(mix(INKS.ochre, INKS.ink, 0.25));
  ctx.beginPath();
  ctx.ellipse(w * 0.38, h * 0.36, w * 0.09, h * 0.08, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillRect(w * 0.26, h * 0.44, w * 0.24, h * 0.35);
  ctx.beginPath();
  ctx.ellipse(w * 0.64, h * 0.48, w * 0.07, h * 0.06, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillRect(w * 0.55, h * 0.54, w * 0.18, h * 0.25);
}

/** An old travel poster of the canal: the iron footbridge, plane trees, the water in green. */
function canalPosterArt(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const m = w * 0.06;
  ctx.fillStyle = css(INKS.card);
  ctx.fillRect(0, 0, w, h);
  // sky, a low sun, the water
  ctx.fillStyle = css(mix(INKS.cobalt, INKS.paper, 0.3));
  ctx.fillRect(m, m, w - 2 * m, h * 0.62);
  ctx.fillStyle = css(INKS.sunflower);
  ctx.beginPath();
  ctx.arc(w * 0.66, h * 0.36, w * 0.13, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = css(INKS.green);
  ctx.fillRect(m, h * 0.6, w - 2 * m, h * 0.3);
  ctx.fillStyle = css(mix(INKS.green, INKS.paper, 0.45));
  for (let i = 0; i < 5; i++) ctx.fillRect(w * (0.2 + (i % 2) * 0.22 + i * 0.05), h * (0.66 + i * 0.045), w * 0.22, h * 0.012);
  // plane trees on both banks
  ctx.fillStyle = css(mix(INKS.ochre, INKS.green, 0.35));
  for (const [x, y, r] of [[0.14, 0.4, 0.15], [0.24, 0.46, 0.11], [0.9, 0.42, 0.14]] as Array<[number, number, number]>) {
    ctx.beginPath();
    ctx.ellipse(w * x, h * y, w * r, h * r * 0.75, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  // the footbridge: two stairs and a flat arch, the railing in ink
  const ink = css(INKS.ink);
  ctx.strokeStyle = ink;
  ctx.fillStyle = ink;
  ctx.lineWidth = h * 0.018;
  ctx.beginPath();
  ctx.moveTo(m, h * 0.6);
  ctx.lineTo(w * 0.22, h * 0.47);
  ctx.quadraticCurveTo(w * 0.5, h * 0.41, w * 0.78, h * 0.47);
  ctx.lineTo(w - m, h * 0.6);
  ctx.stroke();
  ctx.lineWidth = h * 0.007;
  ctx.beginPath();
  ctx.moveTo(w * 0.22, h * 0.43);
  ctx.quadraticCurveTo(w * 0.5, h * 0.37, w * 0.78, h * 0.43);
  ctx.stroke();
  for (let i = 0; i <= 12; i++) {
    const t = i / 12;
    const x = w * (0.22 + 0.56 * t);
    const y = h * (0.47 - 0.06 * 4 * t * (1 - t) * 0.5);
    ctx.fillRect(x - w * 0.003, y - h * 0.04, w * 0.006, h * 0.04);
  }
  // the arch's shadow on the water
  ctx.fillStyle = css(mix(INKS.green, INKS.ink, 0.4));
  ctx.beginPath();
  ctx.moveTo(w * 0.3, h * 0.6);
  ctx.quadraticCurveTo(w * 0.5, h * 0.66, w * 0.7, h * 0.6);
  ctx.fill();
  // the lettering
  ctx.fillStyle = ink;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  let s = fitText(ctx, 'CANAL SAINT-MARTIN', w - 2.4 * m, Math.round(h * 0.06), SANS(0, 700).replace('0px', '{s}px'));
  ctx.font = SANS(s, 700);
  ctx.fillText('CANAL SAINT-MARTIN', w / 2, h * 0.935);
  s = fitText(ctx, 'Paris', w * 0.5, Math.round(h * 0.09), SERIF(0, 600).replace('0px', '{s}px'));
  ctx.font = SERIF(s, 600);
  ctx.fillStyle = css(INKS.card);
  ctx.fillText('Paris', w * 0.3, h * 0.13);
}

/** The bal of the 14th of July on the quai: lanterns on a string, the word large. */
function balPosterArt(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const m = w * 0.06;
  ctx.fillStyle = css(INKS.card);
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = css(INKS.cobalt);
  ctx.fillRect(m, m, w - 2 * m, h - 2 * m);
  // a string of lanterns across the top
  ctx.strokeStyle = css(mix(INKS.cobalt, INKS.paper, 0.45));
  ctx.lineWidth = h * 0.005;
  ctx.beginPath();
  ctx.moveTo(m, h * 0.12);
  ctx.quadraticCurveTo(w / 2, h * 0.3, w - m, h * 0.12);
  ctx.stroke();
  const tones = [INKS.vermilion, INKS.sunflower, INKS.card];
  for (let i = 1; i < 8; i++) {
    const t = i / 8;
    const x = m + (w - 2 * m) * t;
    const y = h * 0.12 + h * 0.18 * 4 * t * (1 - t) * 0.5 + h * 0.025;
    ctx.fillStyle = css(tones[i % 3]);
    ctx.beginPath();
    ctx.arc(x, y, w * 0.04, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = css(INKS.card);
  let s = fitText(ctx, 'Bal', w * 0.8, Math.round(h * 0.3), SERIF(0, 700).replace('0px', '{s}px'));
  ctx.font = SERIF(s, 700);
  ctx.fillText('Bal', w / 2, h * 0.48);
  ctx.fillStyle = css(INKS.sunflower);
  s = fitText(ctx, 'du 14 juillet', w * 0.76, Math.round(h * 0.075), SERIF(0, 500).replace('0px', '{s}px'));
  ctx.font = SERIF(s, 500);
  ctx.fillText('du 14 juillet', w / 2, h * 0.64);
  ctx.fillStyle = css(INKS.vermilion);
  ctx.fillRect(w * 0.3, h * 0.71, w * 0.4, h * 0.008);
  ctx.fillStyle = css(INKS.card);
  s = fitText(ctx, 'QUAI DE VALMY · 22 H', w * 0.78, Math.round(h * 0.045), SANS(0, 700).replace('0px', '{s}px'));
  ctx.font = SANS(s, 700);
  ctx.fillText('QUAI DE VALMY · 22 H', w / 2, h * 0.8);
  ctx.font = SANS(Math.round(s * 0.8), 600);
  ctx.fillText('au Mistral', w / 2, h * 0.86);
}

/** The café's clock: a card face in a gilt ring; the hands say ten past nine. */
function clockArt(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.clearRect(0, 0, w, h);
  const cx = w / 2;
  const cy = h / 2;
  const r = Math.min(w, h) * 0.48;
  ctx.fillStyle = css(GILT);
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = css(INKS.card);
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.86, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = css(INKS.ink);
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const long = i % 3 === 0;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(a);
    ctx.fillRect(-r * (long ? 0.035 : 0.02), -r * 0.8, r * (long ? 0.07 : 0.04), r * (long ? 0.16 : 0.1));
    ctx.restore();
  }
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = SERIF(Math.round(r * 0.16), 600);
  ctx.fillText('Le Mistral', cx, cy + r * 0.36);
  const hand = (a: number, len: number, wid: number) => {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(a);
    ctx.fillRect(-wid / 2, -len, wid, len + r * 0.08);
    ctx.restore();
  };
  hand(((9 + 10 / 60) / 12) * Math.PI * 2, r * 0.45, r * 0.07);
  hand((10 / 60) * Math.PI * 2, r * 0.68, r * 0.045);
  ctx.fillStyle = css(INKS.vermilion);
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.05, 0, Math.PI * 2);
  ctx.fill();
}

/** «L.»'s small oil: the café's corner in a strong wind, blue and ochre, signed lower right. */
function paintingArt(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const cob = css(INKS.cobalt);
  const och = css(INKS.ochre);
  ctx.fillStyle = css(mix(INKS.cobalt, INKS.paper, 0.35));
  ctx.fillRect(0, 0, w, h);
  // wind in the sky: long strokes
  ctx.strokeStyle = css(mix(INKS.cobalt, INKS.paper, 0.6));
  ctx.lineWidth = h * 0.02;
  for (let i = 0; i < 7; i++) {
    ctx.beginPath();
    const y = h * (0.08 + i * 0.07);
    ctx.moveTo(w * 0.02, y + h * 0.05);
    ctx.quadraticCurveTo(w * 0.4, y - h * 0.04, w * 0.98, y + h * 0.02);
    ctx.stroke();
  }
  // the corner building, from slightly above
  ctx.fillStyle = och;
  ctx.beginPath();
  ctx.moveTo(w * 0.22, h * 0.95);
  ctx.lineTo(w * 0.22, h * 0.3);
  ctx.lineTo(w * 0.52, h * 0.22);
  ctx.lineTo(w * 0.78, h * 0.32);
  ctx.lineTo(w * 0.78, h * 0.95);
  ctx.fill();
  ctx.fillStyle = css(mix(INKS.ochre, INKS.ink, 0.25));
  ctx.beginPath();
  ctx.moveTo(w * 0.52, h * 0.22);
  ctx.lineTo(w * 0.78, h * 0.32);
  ctx.lineTo(w * 0.78, h * 0.95);
  ctx.lineTo(w * 0.52, h * 0.95);
  ctx.fill();
  ctx.fillStyle = cob;
  for (let r = 0; r < 4; r++) for (let c = 0; c < 3; c++) ctx.fillRect(w * (0.26 + c * 0.08), h * (0.36 + r * 0.13), w * 0.04, h * 0.07);
  // the red neon, a slash on the corner
  ctx.fillStyle = css(INKS.vermilion);
  ctx.fillRect(w * 0.5, h * 0.38, w * 0.035, h * 0.34);
  // a tree bent by the wind
  ctx.strokeStyle = css(mix(INKS.ink, INKS.cobalt, 0.4));
  ctx.lineWidth = w * 0.02;
  ctx.beginPath();
  ctx.moveTo(w * 0.1, h * 0.98);
  ctx.quadraticCurveTo(w * 0.12, h * 0.6, w * 0.2, h * 0.42);
  ctx.stroke();
  ctx.fillStyle = och;
  ctx.beginPath();
  ctx.ellipse(w * 0.2, h * 0.42, w * 0.1, h * 0.1, 0.5, 0, Math.PI * 2);
  ctx.fill();
  // the signature
  ctx.fillStyle = css(INKS.ink);
  ctx.font = SERIF(Math.round(h * 0.12), 600);
  ctx.textAlign = 'right';
  ctx.fillText('L.', w * 0.95, h * 0.94);
}
