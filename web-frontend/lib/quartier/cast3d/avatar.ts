/**
 * Le Quartier · anyone the avatar kit draws, in the round.
 *
 * The passers-by and the people a forged place names (a stallholder at the marché, the clerk at
 * the betting window) are drawn by the learner's own avatar kit (`components/avatar`), from a
 * record of parts: a face shape, a hair style and its colour, a hat, a top, a scarf, earrings.
 * This stands the same record up the way the troupe's own files do (`people/`): Romy's
 * proportions, since the kit draws everyone on them, a little different from one person to the
 * next; the head moulded on the drawn face, and the face printed from the kit's own drawing (its
 * eyes, brows, cheeks, freckles and beard); every other part of the record cut from the tailor's
 * kit in the record's own colours. A stallholder on paper and in the round is the same person.
 *
 * The kit draws hair that stands up (a quiff, a bun, an afro) smaller or not at all under a hat,
 * and so does this.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import type { Look } from '@/components/avatar/avatar-art';
import { BEARD_PATHS, COVERS_EARS, FACE_PATHS, FRECKLE_D, GOLD, INK, MOUSTACHED, NAVY, PAPER, lookOf } from '@/components/avatar/avatar-art';
import { BROW_WIDTH, EYES, LASHED, NOSE, avatarFigure, lash } from '@/components/avatar/avatar-figure';
import { ellipse } from '@/components/cast/rig-kit';
import type { Pt } from '@/components/cast/vivant/kit';
import type { AvatarConfig } from '@/lib/avatar';
import { deeper, isPale, lighter, mix } from '@/lib/avatar';

import { seeded } from '../geo';
import type { Hex } from '../palette';

import type { FaceLook, Mark } from './face';
import { vivantFace } from './face';
import type { HeadDef } from './head';
import { flick, hairCap, hairFall, onHead, round } from './head';
import type { Band, Build } from './kit';
import { PLATE, armAt, bandAt, button, cuff, frontZ, hand, ink, leg, neck, onFront, pelvis, shoe, skirt, sleeve, torsoBind, trunk } from './kit';
import type { Person } from './model';
import type { BodySpec, Side } from './rig';
import { B, sx } from './rig';
import type { Ink } from './sculpt';
import { between, smooth } from './sculpt';

/** The kit's own inks that `avatar-art.tsx` keeps to itself (the straw warmer, to read as straw in print). */
const RED = '#d8321a';
const WINE = '#9c2411';
const STRAW = '#d9bf84';
const YELLOW = '#f3c318';
const GREEN = '#2c6a5d';
const COBALT = '#1d3a8a';

/**
 * How round the pieces are up close: lighter than the troupe's own, since a street holds a crowd
 * of these (the trunk's segments, a sleeve's, a leg's, a hand's, a shoe's, a hair cap's, and the
 * head's mesh).
 */
const TRUNK = 20;
const SLEEVE = 10;
const LEG = 12;
const HAND = 8;
const SHOE = 14;
const CAP = 32;
const HEAD: [number, number] = [28, 20];

/**
 * Up close, or across the square: far off (past 30 m, where `ModelFigure` swaps the far body in
 * and a person is a few dozen pixels tall) every count is a share of the near one, and the small
 * things are not made at all (buttons, cuffs, a pin, a watch, glasses, earrings, a loose strand of
 * hair, the beret's stalk).
 */
interface Detail {
  round: number;
  trinkets: boolean;
}
const NEAR: Detail = { round: 1, trinkets: true };
const FAR: Detail = { round: 0.6, trinkets: false };
/** A count (of segments, rings, points round) at a detail. */
const lod = (q: Detail, n: number, min = 3) => Math.max(min, Math.round(n * q.round));

const TAU = Math.PI * 2;
const v = (x: number, y: number, z: number) => new Vector3(x, y, z);
const hex = (c: string): Hex => parseInt(c.slice(1), 16);
const k = (c: string, id: number): Ink => ink(hex(c), id);
/** how far round the back an angle is: 0 at the front, 1 straight behind */
const backOf = (th: number) => Math.abs(((th + Math.PI) % TAU) - Math.PI) / Math.PI;

/** Someone the kit draws, as the quarter knows them. */
export interface AvatarWho {
  key: string;
  name?: string;
  /** the top of the hair to the soles, metres, as their card is printed */
  height?: number;
  /** varies the body a little from one person to the next */
  seed?: number;
}

/** Everything a part needs: the record resolved, the body's width, the trunk it is laid on. */
interface Dress {
  look: Look;
  cfg: AvatarConfig;
  hatted: boolean;
  /** the shoulders' width against Romy's */
  w: number;
  /** the top's bands, once it is cut */
  bands: Band[];
  /** up close or far off */
  q: Detail;
}

/* ---- the face ------------------------------------------------------------------------------ */

const EYE_AT: [Pt, Pt] = [
  [-15, -4],
  [15, -4],
];

/** The dark lenses as the kit draws them. */
const SUNGLASSES = 'M-33,-16 L-2,-16 L-3,2 C-5,11 -27,11 -31,2 Z M33,-16 L2,-16 L3,2 C5,11 27,11 31,2 Z';

/** Beards that run round the jaw: the print wraps further round the head for them. */
const ROUND_JAW = new Set(['trois_jours', 'courte', 'pleine']);

function faceLook(look: Look): FaceLook {
  const { tone, hair, cfg } = look;
  const eye = EYES[cfg.eyes] ?? EYES.ronds;
  const under: Mark[] = [];
  if (cfg.blush) under.push({ d: `${ellipse(-22, 13, 6.5, 3.6)} ${ellipse(22, 13, 6.5, 3.6)}`, fill: tone.cheek, opacity: 0.75 });
  if (cfg.freckles) under.push({ d: FRECKLE_D, fill: mix(tone.shade, '#8f5534', 0.5) });
  if (cfg.hair === 'chauve') under.push({ d: ellipse(-10, -52, 10, 4.5), fill: lighter(tone.skin, 0.35) });
  // the beard, and past the drawing's edge on either side, so it runs on round the jaw
  const beard = hair.brow;
  const jaw = 'M-60,-4 L-36.5,-4 L-36.5,64 L-60,64 Z M36.5,-4 L60,-4 L60,64 L36.5,64 Z';
  if (cfg.beard === 'trois_jours') {
    const stubble = mix(tone.skin, beard, 0.3);
    under.push({ d: 'M-60,0 L-36.5,0 L-36.5,64 L-60,64 Z M36.5,0 L60,0 L60,64 L36.5,64 Z', fill: stubble }, { d: BEARD_PATHS.stubble, fill: stubble });
  } else if (cfg.beard === 'bouc') {
    under.push({ d: BEARD_PATHS.goatee, fill: beard });
  } else if (cfg.beard === 'courte') {
    under.push({ d: jaw, fill: beard }, { d: BEARD_PATHS.short, fill: beard }, { d: ellipse(0, 33, 14, 9.5), fill: tone.skin });
  } else if (cfg.beard === 'pleine') {
    under.push({ d: jaw, fill: beard }, { d: BEARD_PATHS.full, fill: beard }, { d: BEARD_PATHS.fullLines, stroke: hair.light, width: 1.6 }, { d: ellipse(0, 32, 13.5, 9), fill: tone.skin });
  }
  const over: Mark[] = MOUSTACHED.includes(cfg.beard) ? [{ d: BEARD_PATHS.moustache, fill: beard }] : [];
  // under sunglasses the eyes never show, even past the lenses' edge from the side
  if (cfg.glasses === 'soleil') over.push({ d: SUNGLASSES, fill: INK });
  const lashes = cfg.lashes && cfg.glasses !== 'soleil';
  return {
    skin: tone.skin,
    brow: hair.brow,
    browWidth: BROW_WIDTH[cfg.brows] ?? BROW_WIDTH.naturels,
    lidLine: 2.6,
    arcLine: 4,
    iris: look.iris,
    lash: lashes ? { states: Array.from(LASHED), path: (c, side) => lash(c, side, eye.ry), at: EYE_AT } : undefined,
    mouth: [-3.6, 1.8, 1.8],
    nose: { d: NOSE, fill: tone.shade, opacity: 0.5 },
    under,
    over,
    fx: { cheekL: [-22, 13], cheekR: [22, 13], temple: [31, -30], eyeL: [-15, -4], eyeR: [15, -4] },
    frame: [0, -6, 60],
  };
}

/* ---- tops ---------------------------------------------------------------------------------- */

/** A top's body from its hem up to the collar: Romy's jacket, as wide as the shoulders. */
function torso(b: Build, w: number, hem: number): Band[] {
  const { J } = b;
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;
  return [
    { y: hem, rx: 0.15 * w, rz: 0.108, square: 2.2 },
    { y: hip + 0.03, rx: 0.144 * w, rz: 0.104, square: 2.1 },
    { y: hip + 0.15, rx: 0.135 * w, rz: 0.097 },
    { y: ch - 0.03, rx: 0.14 * w, rz: 0.1, front: 0.012 },
    { y: ch + 0.08, rx: 0.15 * w, rz: 0.097, front: 0.006 },
    { y: sy - 0.045, rx: 0.158 * w, rz: 0.089, square: 2.6 },
    { y: sy - 0.004, rx: 0.118 * w, rz: 0.073, square: 2.4 },
    { y: sy + 0.022, rx: 0.05, rz: 0.046 },
  ];
}

/** The trunk at a height, grown by `out` (a ribbed hem, a stripe, a belt). */
function ring(bands: Band[], y: number, out: number): Band {
  const at = bandAt(bands, y);
  return { ...at, y, rx: at.rx + out, rz: at.rz + out };
}

/** A narrow upright strip on the front (a placket, a seam), its long sides cut into steps so it follows the chest. */
function strip(x: number, top: number, bottom: number, half: number, steps = 6): Array<[number, number]> {
  const side: number[] = [];
  for (let i = 0; i <= steps; i++) side.push(top + ((bottom - top) * i) / steps);
  return [...side.map((y) => [x - half, y] as [number, number]), ...side.reverse().map((y) => [x + half, y] as [number, number])];
}

/** A collar round the neck: a closed roll, dipping at the front. */
function collar(b: Build, q: Detail, k0: Ink, r: number, thick: number | [number, number], dip = 0.006) {
  const sy = b.J.shoulderY;
  const pts: Vector3[] = [];
  const n = lod(q, 18);
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU;
    pts.push(v(Math.sin(a) * r, sy + 0.02 - Math.max(0, Math.cos(a)) * dip, Math.cos(a) * r * 0.92 - 0.008));
  }
  b.S.tube(pts, thick, k0, torsoBind(b.J), { seg: lod(q, 6), closed: true });
}

/** A sleeve's radius along the arm (0 the shoulder, 2 the wrist). */
const LONG: Array<[number, number]> = [
  [0, 0.055],
  [0.45, 0.05],
  [1, 0.047],
  [1.6, 0.044],
  [1.92, 0.042],
];
function radiusAt(st: Array<[number, number]>, f: number) {
  for (let i = 0; i + 1 < st.length; i++) {
    if (f <= st[i + 1][0]) return st[i][1] + ((st[i + 1][1] - st[i][1]) * (f - st[i][0])) / (st[i + 1][0] - st[i][0]);
  }
  return st[st.length - 1][1];
}

function top(b: Build, d: Dress) {
  const { S, J } = b;
  const { look, cfg, w, q } = d;
  const c = look.top;
  const dark = deeper(c);
  const skin2 = k(look.tone.skin, PLATE.skin2);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const arm = 0.92 + 0.08 * w;
  const long = LONG.map(([f, r]) => [f, r * arm] as [number, number]);
  const wrist = radiusAt(long, 1.86);
  const sleeves = (cloth: Ink, cuffInk: Ink | null) => {
    for (const side of ['L', 'R'] as const) {
      sleeve(b, side, cloth, long, { capEnd: true, seg: lod(q, SLEEVE) });
      if (cuffInk && q.trinkets) cuff(b, side, cuffInk, 1.86, wrist + 0.003, 0.05);
      hand(b, side, skin2, 0.95, { seg: lod(q, HAND, 6) });
    }
  };
  const cloth = k(c, PLATE.top);
  const rib = k(dark, PLATE.under);

  switch (cfg.top) {
    case 'tshirt': {
      const bands = torso(b, w, hip - 0.05);
      d.bands = bands;
      trunk(b, bands, cloth, { seg: lod(q, TRUNK) });
      collar(b, q, rib, 0.05, 0.008);
      for (const side of ['L', 'R'] as const) {
        sleeve(b, side, cloth, [[0, 0.057 * arm], [0.52, 0.054 * arm]], { capEnd: true, seg: lod(q, SLEEVE) });
        sleeve(b, side, skin2, [[0.35, 0.036 * arm], [1, 0.033 * arm], [1.6, 0.03 * arm], [1.95, 0.028 * arm]], { capEnd: true, seg: lod(q, SLEEVE) });
        hand(b, side, skin2, 0.95, { seg: lod(q, HAND, 6) });
      }
      break;
    }
    case 'chemise': {
      const bands = torso(b, w, hip - 0.06);
      d.bands = bands;
      const hem = bands[0].y;
      const pale = lighter(c, 0.35);
      trunk(b, bands, cloth, { seg: lod(q, TRUNK) });
      // the open neck, the collar's points either side of it
      onFront(b, bands, [[-0.028, sy + 0.016], [0.028, sy + 0.016], [0, sy - 0.05]], skin2, { lift: 0.002, rings: 3 });
      onFront(b, bands, [[-0.044, sy + 0.016], [-0.004, sy - 0.05], [-0.03, sy - 0.085], [-0.08, sy - 0.008]], k(pale, PLATE.under), { lift: 0.005, depth: 0.005, rings: 3 });
      onFront(b, bands, [[0.044, sy + 0.016], [0.08, sy - 0.008], [0.03, sy - 0.085], [0.004, sy - 0.05]], k(pale, PLATE.under), { lift: 0.005, depth: 0.005, rings: 3 });
      // the placket and its buttons, the pocket on the right of the chest
      onFront(b, bands, strip(0, sy - 0.05, hem + 0.004, 0.003), k(dark, PLATE.top), { lift: 0.002, depth: 0.003, rings: 2 });
      for (let i = 0; i < 4 && q.trinkets; i++) {
        const y = sy - 0.1 - ((sy - 0.1 - (hem + 0.05)) * i) / 3;
        button(b, v(0.014, y, frontZ(bands, 0.014, y) + 0.003), 0.006, k(isPale(c) ? dark : lighter(c, 0.6), PLATE.prop), B.spine);
      }
      onFront(b, bands, [[-0.112, sy - 0.07], [-0.06, sy - 0.07], [-0.06, sy - 0.13], [-0.112, sy - 0.13]], k(c, PLATE.under), { lift: 0.003, depth: 0.003, rings: 2 });
      sleeves(cloth, k(pale, PLATE.under));
      break;
    }
    case 'veste': {
      const bands = torso(b, w * 1.03, hip - 0.07);
      d.bands = bands;
      trunk(b, bands, cloth, { seg: lod(q, TRUNK) });
      // the white shirt in the V, the dark lapels either side
      onFront(b, bands, [[-0.044, sy + 0.015], [0.044, sy + 0.015], [0, sy - 0.135]], k(PAPER, PLATE.under), { lift: 0.002, rings: 4 });
      for (const s of [-1, 1]) {
        const pts: Array<[number, number]> = [[s * 0.044, sy + 0.016], [s * 0.088, sy - 0.008], [s * 0.022, sy - 0.18], [s * 0.001, sy - 0.135]];
        onFront(b, bands, s > 0 ? pts : pts.reverse(), k(dark, PLATE.bottom), { lift: 0.005, depth: 0.006, rings: 4 });
        onFront(b, bands, strip(s * 0.112 * w, sy - 0.1, hip - 0.04, 0.003), k(dark, PLATE.top), { lift: 0.002, depth: 0.003, rings: 2 });
      }
      if (q.trinkets) {
        for (const y of [hip + 0.13, hip + 0.04]) button(b, v(0.016, y, frontZ(bands, 0.016, y) + 0.004), 0.009, k(dark, PLATE.prop), B.spine);
      }
      sleeves(cloth, rib);
      break;
    }
    case 'sweat': {
      const bands = torso(b, w * 1.04, hip - 0.06);
      d.bands = bands;
      const hem = bands[0].y;
      trunk(b, bands, cloth, { seg: lod(q, TRUNK) });
      trunk(b, [ring(bands, hem - 0.006, -0.004), ring(bands, hem, 0.005), ring(bands, hem + 0.055, 0.005), ring(bands, hem + 0.062, 0)], rib, { seg: lod(q, TRUNK) });
      // the hood bunched round the neck, its strings, the pocket on the belly
      collar(b, q, rib, 0.072, [0.022, 0.03], 0.03);
      for (const s of [-1, 1]) {
        if (!q.trinkets) break;
        const top0 = v(s * 0.024, sy - 0.012, frontZ(bands, s * 0.024, sy - 0.012) + 0.012);
        const end = v(s * 0.03, sy - 0.12, frontZ(bands, s * 0.03, sy - 0.12) + 0.006);
        S.tube([top0, top0.clone().lerp(end, 0.5).add(v(0, 0, 0.004)), end], 0.0035, k(PAPER, PLATE.prop), torsoBind(J), { seg: 5, caps: true });
      }
      onFront(b, bands, [[-0.09 * w, hem + 0.23], [0.09 * w, hem + 0.23], [0.112 * w, hem + 0.085], [-0.112 * w, hem + 0.085]], rib, { lift: 0.004, depth: 0.004, rings: 3 });
      sleeves(cloth, rib);
      break;
    }
    case 'manteau': {
      const bands = torso(b, w * 1.05, hip - 0.02);
      d.bands = bands;
      trunk(b, bands, cloth, { seg: lod(q, TRUNK), capStart: false });
      // the skirt of the coat to below the knee, open a little at the front
      const below = bandAt(bands, hip + 0.04);
      skirt(b, cloth, { top: hip + 0.04, hem: J.knee.L.y - 0.07, rxTop: below.rx, rzTop: below.rz, rxHem: 0.178 * w, rzHem: 0.13, gap: [-0.06, 0.06], follow: 0.7, capTop: false, seg: lod(q, 24) });
      collar(b, q, rib, 0.058, [0.016, 0.02], 0.02);
      // where it closes, its belt and gold buckle, two rows of buttons
      onFront(b, bands, strip(0, sy - 0.06, hip, 0.003), k(dark, PLATE.top), { lift: 0.002, depth: 0.003, rings: 2 });
      trunk(b, [ring(bands, hip - 0.012, 0.005), ring(bands, hip + 0.03, 0.005)], rib, { seg: lod(q, TRUNK), capStart: false, capEnd: false });
      onFront(b, bands, [[-0.016, hip - 0.014], [0.016, hip - 0.014], [0.016, hip + 0.032], [-0.016, hip + 0.032]], k(GOLD, PLATE.prop), { lift: 0.008, depth: 0.003 });
      onFront(b, bands, [[-0.009, hip - 0.006], [0.009, hip - 0.006], [0.009, hip + 0.024], [-0.009, hip + 0.024]], rib, { lift: 0.0105, depth: 0.002 });
      for (const y of [sy - 0.15, sy - 0.26]) {
        if (!q.trinkets) break;
        for (const x of [-0.032, 0.032]) button(b, v(x, y, frontZ(bands, x, y) + 0.004), 0.009, k(dark, PLATE.prop), B.chest);
      }
      sleeves(cloth, rib);
      break;
    }
    case 'mariniere': {
      // cream, striped in the chosen colour, a boat neck
      const bands = torso(b, w, hip - 0.06);
      d.bands = bands;
      const hem = bands[0].y;
      const stripe = k(c, PLATE.top);
      trunk(b, bands, k(PAPER, PLATE.top), { seg: lod(q, TRUNK) });
      for (let y = sy - 0.035; y > hem + 0.012; y -= 0.042) {
        trunk(b, [ring(bands, y - 0.017, 0.0025), ring(bands, y, 0.0025)], stripe, { capStart: false, capEnd: false, seg: lod(q, TRUNK) });
      }
      collar(b, q, k(lighter(c, 0.5), PLATE.under), 0.056, [0.004, 0.006], 0.004);
      for (const side of ['L', 'R'] as const) {
        sleeve(b, side, k(PAPER, PLATE.top), long, { capEnd: true, seg: lod(q, SLEEVE) });
        for (let f = 0.3; f < 1.85 && q.trinkets; f += 0.3) cuff(b, side, stripe, f, radiusAt(long, f) + 0.002, 0.018);
        hand(b, side, skin2, 0.95, { seg: lod(q, HAND, 6) });
      }
      break;
    }
    default: {
      // the jumper: a ribbed hem, crew collar and cuffs in the darker tone
      const bands = torso(b, w, hip - 0.06);
      d.bands = bands;
      const hem = bands[0].y;
      trunk(b, bands, cloth, { seg: lod(q, TRUNK) });
      trunk(b, [ring(bands, hem - 0.006, -0.004), ring(bands, hem, 0.005), ring(bands, hem + 0.05, 0.005), ring(bands, hem + 0.057, 0)], rib, { seg: lod(q, TRUNK) });
      collar(b, q, rib, 0.05, 0.011);
      sleeves(cloth, rib);
      break;
    }
  }

  // the troupe's navy trousers and black shoes; a coat covers the hips
  const navy = k(NAVY, PLATE.bottom);
  if (cfg.top !== 'manteau') pelvis(b, navy, { waist: hip + 0.05, rx: 0.12 * w, rz: 0.09, seg: lod(q, 22) });
  for (const side of ['L', 'R'] as const) {
    leg(b, side, navy, { top: 0.068, thigh: 0.064, knee: 0.05, calf: 0.047, hem: 0.045 }, { seg: lod(q, LEG) });
    shoe(b, side, k(INK, PLATE.shoes), { width: 0.044, height: 0.062, seg: lod(q, SHOE) });
  }
}

/* ---- round the neck, on the chest, at the wrist -------------------------------------------- */

function neckpiece(b: Build, d: Dress) {
  const { S, J } = b;
  const { look, cfg, bands, q } = d;
  const sy = J.shoulderY;
  const loop = (r: number, thick: [number, number], k0: Ink) => {
    const pts: Vector3[] = [];
    const n = lod(q, 18);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * TAU;
      pts.push(v(Math.sin(a) * r, sy + 0.012 - Math.cos(a) * 0.012, Math.cos(a) * r * 0.9 - 0.006));
    }
    S.tube(pts, thick, k0, B.chest, { seg: lod(q, 6), closed: true });
  };
  switch (cfg.neck) {
    case 'echarpe': {
      // round the neck, one end down the left of the chest, fringed
      const c = cfg.topColor === 'bordeaux' || cfg.topColor === 'rouge' ? '#e9e4d8' : WINE;
      const scarf = k(c, PLATE.under);
      loop(0.07, [0.024, 0.018], scarf);
      const yb = sy - 0.21;
      onFront(b, bands, [[0.012, sy - 0.006], [0.058, sy - 0.012], [0.07, yb], [0.026, yb + 0.004]], scarf, { lift: 0.009, depth: 0.012, rings: 3 });
      for (let i = 0; i < 5 && q.trinkets; i++) {
        const x = 0.03 + (i / 4) * 0.036;
        const z = frontZ(bands, x, yb) + 0.014;
        S.tube([v(x, yb + 0.004, z), v(x + 0.002, yb - 0.018, z + 0.001)], 0.003, scarf, B.chest, { seg: 4 });
      }
      break;
    }
    case 'foulard': {
      // the red neckerchief, knotted at the front, its two points and a few white dots
      const red = k(RED, PLATE.under);
      loop(0.055, [0.013, 0.01], red);
      const kz = frontZ(bands, 0, sy - 0.02) + 0.012;
      S.ball(v(0, sy - 0.02, kz), v(0.014, 0.012, 0.01), k(deeper(RED, 0.2), PLATE.prop), B.chest, { seg: lod(q, 8), rings: lod(q, 5) });
      onFront(b, bands, [[-0.006, sy - 0.026], [-0.036, sy - 0.09], [0.002, sy - 0.068]], red, { lift: 0.008, depth: 0.004, rings: 2 });
      onFront(b, bands, [[0.006, sy - 0.026], [0.004, sy - 0.07], [0.04, sy - 0.088]], red, { lift: 0.008, depth: 0.004, rings: 2 });
      for (const [x, y] of [[-0.02, sy - 0.05], [0.022, sy - 0.056], [-0.012, sy - 0.074]] as const) {
        if (!q.trinkets) break;
        S.ball(v(x, y, frontZ(bands, x, y) + 0.0125), 0.0035, k(PAPER, PLATE.prop), B.chest, { seg: 6, rings: 3 });
      }
      break;
    }
    case 'collier_cle': {
      // Margaux's key on its cord
      if (!q.trinkets) break;
      const cord: Vector3[] = [];
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const x = Math.sin((t - 0.5) * Math.PI) * 0.046;
        const y = sy + 0.014 - Math.sin(t * Math.PI) * 0.11;
        cord.push(v(x, y, frontZ(bands, x, y) + 0.004));
      }
      S.tube(cord, 0.0022, k(INK, PLATE.prop), torsoBind(J), { seg: 4 });
      const gold = k(GOLD, PLATE.prop);
      const ky = sy + 0.014 - 0.11 - 0.012;
      const kz = frontZ(bands, 0, ky) + 0.006;
      const bow: Vector3[] = [];
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * TAU;
        bow.push(v(Math.sin(a) * 0.011, ky + Math.cos(a) * 0.011, kz));
      }
      S.tube(bow, 0.0035, gold, B.chest, { seg: 5, closed: true });
      S.box(v(0, ky - 0.032, kz), v(0.006, 0.042, 0.004), gold, B.chest);
      S.box(v(0.006, ky - 0.044, kz), v(0.01, 0.006, 0.004), gold, B.chest);
      S.box(v(0.005, ky - 0.032, kz), v(0.008, 0.005, 0.004), gold, B.chest);
      break;
    }
    case 'badge_presse': {
      // the press card on its blue lanyard
      const card: Array<[number, number]> = [[-0.045, sy - 0.17], [0.045, sy - 0.17], [0.045, sy - 0.29], [-0.045, sy - 0.29]];
      for (const s of [-1, 1]) {
        const a = v(s * 0.046, sy + 0.016, -0.004);
        const m = v(s * 0.04, sy - 0.08, frontZ(bands, s * 0.04, sy - 0.08) + 0.004);
        const e = v(s * 0.024, sy - 0.17, frontZ(bands, s * 0.024, sy - 0.17) + 0.005);
        S.tube([a, m, e], 0.004, k(COBALT, PLATE.prop), torsoBind(J), { seg: lod(q, 4) });
      }
      onFront(b, bands, card, k(PAPER, PLATE.prop), { lift: 0.005, depth: 0.003, rings: 2 });
      onFront(b, bands, [[-0.045, sy - 0.17], [0.045, sy - 0.17], [0.045, sy - 0.196], [-0.045, sy - 0.196]], k(RED, PLATE.under), { lift: 0.0075, depth: 0.002 });
      onFront(b, bands, [[-0.036, sy - 0.21], [-0.01, sy - 0.21], [-0.01, sy - 0.25], [-0.036, sy - 0.25]], k(look.tone.skin, PLATE.under), { lift: 0.0075, depth: 0.002 });
      for (const [y, len] of [[sy - 0.218, 0.03], [sy - 0.232, 0.026], [sy - 0.246, 0.022]] as const) {
        onFront(b, bands, [[0.002, y + 0.002], [0.002 + len, y + 0.002], [0.002 + len, y - 0.002], [0.002, y - 0.002]], k(INK, PLATE.under), { lift: 0.0075, depth: 0.002 });
      }
      break;
    }
    default:
      break;
  }
}

function pin(b: Build, d: Dress) {
  const { S, J } = b;
  const { look, cfg, bands, q } = d;
  if (!q.trinkets) return;
  // on the right of the chest, as the kit draws it
  const x = -0.072;
  const y = J.shoulderY - 0.06;
  const z = frontZ(bands, x, y) + 0.004;
  if (cfg.pin === 'fleur') {
    const petal = k(isPale(look.top) ? RED : PAPER, PLATE.prop);
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * TAU;
      S.ball(v(x + Math.sin(a) * 0.011, y + Math.cos(a) * 0.011, z + 0.002), v(0.008, 0.008, 0.004), petal, B.chest, { seg: 7, rings: 4 });
    }
    S.ball(v(x, y, z + 0.005), v(0.0065, 0.0065, 0.004), k(YELLOW, PLATE.under), B.chest, { seg: 7, rings: 4 });
    S.tube([v(x + 0.004, y - 0.014, z + 0.002), v(x + 0.009, y - 0.034, z)], 0.0022, k(GREEN, PLATE.under), B.chest, { seg: 4 });
  } else if (cfg.pin === 'pins_atelier') {
    button(b, v(x, y, z), 0.019, k(GOLD, PLATE.prop), B.chest);
    button(b, v(x, y, z + 0.004), 0.015, k(RED, PLATE.under), B.chest);
    S.ball(v(x, y, z + 0.009), v(0.006, 0.006, 0.003), k(PAPER, PLATE.prop), B.chest, { seg: 4, rings: 2, flat: true });
  }
}

/** A ring round the forearm at `f` along the arm (2 the wrist). */
function bangle(b: Build, side: Side, f: number, r: number, thick: number | [number, number], k0: Ink) {
  const { S, J } = b;
  const c = armAt(J, side, f);
  const dir = armAt(J, side, f + 0.05).sub(armAt(J, side, f - 0.05)).normalize();
  const u = v(0, 0, 1).cross(dir).normalize();
  const w = dir.clone().cross(u).normalize();
  const pts: Vector3[] = [];
  for (let i = 0; i < 14; i++) {
    const a = (i / 14) * TAU;
    pts.push(c.clone().addScaledVector(u, Math.cos(a) * r).addScaledVector(w, Math.sin(a) * r));
  }
  S.tube(pts, thick, k0, B[`fore${side}` as const], { seg: 5, closed: true, up: dir });
}

function wristpiece(b: Build, d: Dress) {
  const { cfg } = d;
  if (cfg.wrist === 'aucun' || !d.q.trinkets) return;
  // the watch on the left wrist, everything else on the right
  const side: Side = cfg.wrist === 'montre' ? 'L' : 'R';
  const f = 1.95;
  const r = cfg.top === 'tshirt' ? 0.029 : radiusAt(LONG, 1.86) + 0.006;
  if (cfg.wrist === 'jonc') bangle(b, side, f, r + 0.003, 0.0045, k(GOLD, PLATE.prop));
  else if (cfg.wrist === 'bracelet') {
    bangle(b, side, f, r + 0.002, [0.0035, 0.007], k(RED, PLATE.prop));
    bangle(b, side, f, r + 0.0045, [0.0015, 0.0025], k(YELLOW, PLATE.under));
  } else {
    bangle(b, side, f, r + 0.001, [0.0025, 0.008], k(INK, PLATE.prop));
    const { S, J } = b;
    const c = armAt(J, side, f).add(v(sx(side) * (r + 0.006), 0, 0.004));
    S.ball(c, v(0.005, 0.013, 0.013), k(GOLD, PLATE.prop), B[`fore${side}` as const], { seg: 10, rings: 5 });
    S.ball(c.clone().add(v(sx(side) * 0.003, 0, 0)), v(0.003, 0.0095, 0.0095), k(PAPER, PLATE.under), B[`fore${side}` as const], { seg: 10, rings: 4 });
  }
}

/* ---- the hair ------------------------------------------------------------------------------ */

function hair(b: Build, d: Dress): number {
  const { S, J, head, hc } = b;
  const { look, cfg, hatted, bands, q } = d;
  const style = cfg.hair;
  const hairInk = k(style === 'rase' ? mix(look.hair.hair, look.tone.skin, 0.3) : look.hair.hair, PLATE.hair);
  const second = k(look.hair.hair, PLATE.under);
  const light = k(look.hair.light, PLATE.under);
  const sy = J.shoulderY;
  const lat = (y: number) => head.latOf(y);
  // under a hat the hair lies flat
  const flat = (t: number) => (hatted ? Math.min(t, 0.012) : t);
  const front = (th: number) => Math.max(0, Math.cos(th));
  const cap = (edge: (th: number) => number, thick: (th: number, u: number) => number, opts: { seg?: number; rows?: number } = {}) => {
    const t = (th: number, u: number) => flat(thick(th, u));
    hairCap(S, head, hc, { edge, thick: t, ink: hairInk, bind: B.head, ...opts });
    // a point on the cap, `out` above it
    return (th: number, y: number, out = 0.0015) => {
      const e = lat(edge(th));
      const f = Math.min(1, Math.max(0, (Math.PI / 2 - lat(y)) / (Math.PI / 2 - e)));
      return onHead(head, hc, lat(y), th, t(th, 1 - f) + out);
    };
  };
  const strand = (pts: Vector3[], width = 0.0026) => {
    if (q.trinkets) S.tube(pts, width, light, B.head, { seg: 4, caps: true });
  };
  const fallBind = (p: Vector3) => between(B.head, B.chest, smooth(J.chin + 0.03, sy - 0.07, p.y));
  const clearBody = (y: number): [number, number] | null => {
    if (y > sy + 0.03) return null;
    const band = bandAt(bands, y);
    const shoulder = smooth(sy + 0.03, sy - 0.02, y) * (1 - smooth(sy - 0.08, sy - 0.16, y));
    return [band.rx + 0.012 + 0.03 * shoulder, band.rz + 0.012];
  };
  // the hairline above visible ears, down behind them to the nape
  const SHORT: Array<[number, number]> = [[1.25, -16], [1.55, -14], [1.78, -12], [2.1, 4], [2.5, 14], [Math.PI, 20]];
  const both = (pts: Array<[number, number]>) => round(pts.concat(pts.filter(([a]) => a > 0 && a < Math.PI).map(([a, y]) => [-a, y] as [number, number])));

  switch (style) {
    case 'court':
    case 'rase':
    case 'meche': {
      const rase = style === 'rase';
      const quiff = style === 'meche' && !hatted;
      const edge = both([[0, rase ? -54 : quiff ? -48 : -46], [0.5, rase ? -50 : -44], [0.95, rase ? -38 : -34], ...SHORT]);
      const at = cap(
        edge,
        (th, u) => {
          if (rase) return 0.004 + 0.003 * u;
          // the quiff rises off the front of the crown and settles toward the back
          const lift = quiff ? 0.05 * Math.pow(Math.sin(u * Math.PI), 0.8) * front(th) ** 2 + 0.012 * smooth(0, 1, u) : 0;
          return 0.007 + 0.03 * Math.pow(u, 0.55) + 0.012 * front(th) * u + lift;
        },
        { seg: lod(q, CAP), rows: lod(q, 10) },
      );
      if (quiff) {
        const a = at(-0.5, -56, 0.004);
        const c = at(0.1, -62, 0.006);
        const e = at(0.7, -54, 0.004);
        flick(S, [a, a.clone().lerp(c, 0.5).add(v(0, 0.01, 0.008)), c, e], [0.01, 0.018, 0.018, 0.007], light, B.head, { flat: 0.35, up: v(0, 1, 0) });
      } else if (!rase && !hatted) strand([at(-0.6, -52), at(-0.2, -56), at(0.25, -56), at(0.6, -52)]);
      break;
    }
    case 'boucles': {
      const edge = both([[0, -50], [0.9, -40], [1.3, -20], [1.6, 2], [2.2, 16], [Math.PI, 22]]);
      cap(edge, (_th, u) => 0.012 + 0.012 * u, { seg: lod(q, CAP), rows: lod(q, 10) });
      let n = 0;
      const curl = (th: number, y: number, r: number) => {
        const p = onHead(head, hc, lat(y), th, flat(0.016) + r * 0.3);
        S.ball(p, r, n++ % 2 ? second : hairInk, B.head, { seg: lod(q, 6), rings: lod(q, 4) });
      };
      // the curls along the hairline, unless a hat comes down over them
      for (let i = 0; i < 7 && !hatted; i++) {
        const th = -1.0 + (2.0 * i) / 6;
        curl(th, edge(th) - 4, 8 * head.s);
      }
      const rows: Array<[number, number, number, number]> = [
        [-56, 10.5, 5, 0.9],
        [-38, 10.5, 9, 1.15],
        [-19, 10, 10, 1.35],
        [0, 9.5, 10, 1.55],
        [17, 8, 8, 1.95],
      ];
      rows.forEach(([y, r, count, start], ri) => {
        if (hatted && y < -40) return;
        for (let i = 0; i < count; i++) {
          const f = count === 1 ? 0.5 : i / (count - 1);
          curl(start + (TAU - 2 * start) * f + (ri % 2 ? 0.12 : 0), y, r * head.s);
        }
      });
      break;
    }
    case 'afro': {
      const big = hatted ? 0.7 : 1;
      const edge = both([[0, -50], [0.8, -44], [1.2, -24], [1.5, -2], [Math.PI / 2, 8], [2.2, 18], [Math.PI, 22]]);
      hairCap(S, head, hc, {
        edge,
        thick: (th, u) => 0.014 + big * (0.1 * Math.pow(Math.sin((u * Math.PI) / 2), 0.7) + 0.03 * (1 - front(th)) * smooth(0, 0.3, u)),
        ink: hairInk,
        bind: B.head,
        seg: lod(q, CAP),
        rows: lod(q, 12),
      });
      // the curls along the hairline, unless a hat comes down over them
      for (let i = 0; i < 9 && !hatted; i++) {
        const th = -0.95 + (1.9 * i) / 8;
        const p = onHead(head, hc, lat(edge(th) - 2), th, 0.016);
        S.ball(p, 8 * head.s, i % 2 ? second : hairInk, B.head, { seg: lod(q, 7), rings: lod(q, 4) });
      }
      return 0.014 + 0.13 * big;
    }
    case 'carre': {
      // the bob and its straight fringe
      const edge = both([[0, -31], [0.6, -31], [0.95, -29], [1.25, -18], [Math.PI / 2, 0], [2.2, 14], [Math.PI, 20]]);
      const at = cap(edge, (_th, u) => 0.007 + 0.034 * Math.pow(u, 0.5), { seg: lod(q, CAP), rows: lod(q, 10) });
      const jaw = hc.y + (head.y0 - 30) * head.s;
      hairFall(S, head, hc, {
        top: -30,
        open: 1.22,
        end: (th) => jaw + 0.012 * smooth(0.4, 1, backOf(th)),
        thick: (th) => 0.028 + 0.008 * smooth(0.45, 1, backOf(th)),
        lift: 0.012,
        flare: -0.004,
        ink: hairInk,
        bind: (p) => between(B.head, B.neck, smooth(jaw + 0.04, jaw - 0.02, p.y) * 0.4),
        cols: lod(q, 24),
        rows: lod(q, 12),
      });
      if (!hatted) {
        for (const th of [-0.5, -0.17, 0.17, 0.5]) strand([at(th, -33), at(th, -48), at(th * 0.9, -60)], 0.0018);
      }
      break;
    }
    case 'mi_long':
    case 'long': {
      const isLong = style === 'long';
      // mi-long: the fringe swept across from the left; long: parted in the middle
      const edge = isLong
        ? both([[0, -56], [0.08, -53], [0.4, -50], [0.58, -46], [1.0, -36], [1.26, -16], [1.42, 6], [Math.PI / 2, 16], [2.3, 34], [Math.PI, 40]])
        : round([[0, -50], [-0.4, -42], [-0.8, -30], [-1.1, -16], [-1.4, -4], [-Math.PI / 2, 6], [-2.3, 20], [Math.PI, 26], [2.3, 20], [Math.PI / 2, 6], [1.4, -10], [1.1, -32], [0.75, -48], [0.35, -54]]);
      const at = cap(edge, (th, u) => 0.004 + (0.04 - 0.016 * front(th) * (1 - u)) * Math.pow(u, 0.45) + 0.008 * u * u, { seg: lod(q, CAP), rows: lod(q, 12) });
      hairFall(S, head, hc, {
        top: isLong ? -40 : -36,
        open: isLong ? 1.2 : 1.28,
        end: isLong ? (th) => sy - 0.005 - 0.16 * smooth(0.4, 1, backOf(th)) : (th) => J.chin - 0.035 - 0.025 * smooth(0.3, 1, backOf(th)),
        thick: (th) => 0.028 + 0.008 * smooth(0.45, 1, backOf(th)),
        body: clearBody,
        lift: 0.012,
        flare: isLong ? 0.02 : 0.012,
        ink: hairInk,
        bind: fallBind,
        cols: lod(q, 24),
        rows: lod(q, isLong ? 14 : 10),
      });
      if (!hatted) {
        if (isLong) {
          for (const s of [-1, 1]) strand([at(s * 0.62, -46, 0.004), at(s * 0.95, -34, 0.006), at(s * 1.16, -18, 0.006)]);
        } else strand([at(0.5, -54), at(0.05, -50), at(-0.4, -44), at(-0.8, -32)]);
      }
      break;
    }
    case 'queue':
    case 'chignon': {
      // slicked back from the face
      const edge = both([[0, -56], [0.6, -52], [1.0, -38], [1.3, -16], ...SHORT.slice(1)]);
      const at = cap(edge, (_th, u) => 0.006 + 0.016 * Math.pow(u, 0.6), { seg: lod(q, CAP), rows: lod(q, 10) });
      if (style === 'queue') {
        // the ponytail from the back of the head, hanging to the left of the back, its red tie
        const base = at(Math.PI - 0.3, -30, 0.006);
        const out = v(0.03, 0, -0.03);
        const path = [base, base.clone().add(v(0.012, -0.03, -0.03)), base.clone().add(out).add(v(0.012, -0.1, 0)), base.clone().add(out).add(v(0.02, -0.18, 0.006)), base.clone().add(out).add(v(0.018, -0.25, 0.016))];
        S.tube(path, [0.026, 0.03, 0.028, 0.02, 0.006], hairInk, path.map((p) => fallBind(p)), { seg: lod(q, 10), caps: 0.004 });
        strand([path[1].clone().add(v(0.012, 0, -0.022)), path[2].clone().add(v(0.014, 0, -0.024)), path[3].clone().add(v(0.012, 0, -0.018))], 0.0022);
        const tie: Vector3[] = [];
        const tc = base.clone().add(v(0.006, -0.016, -0.016));
        const n = lod(q, 10);
        for (let i = 0; i < n; i++) {
          const a = (i / n) * TAU;
          tie.push(tc.clone().add(v(Math.cos(a) * 0.026, Math.sin(a) * 0.012, Math.sin(a) * 0.022)));
        }
        S.tube(tie, 0.0065, k(RED, PLATE.prop), B.head, { seg: lod(q, 5), closed: true });
      } else if (!hatted) {
        // the bun on top, its red tie, a light across it
        const crown = at(0, -64, 0);
        // as the kit draws it: r 19 against the face's 76 across
        const r = 19 * head.s;
        const bun = crown.clone().add(v(0, r * 0.95, -0.014));
        S.ball(bun, v(r, r * 0.9, r * 0.95), hairInk, B.head, { seg: lod(q, 16), rings: lod(q, 9) });
        const tie: Vector3[] = [];
        const n = lod(q, 14);
        for (let i = 0; i < n; i++) {
          const a = (i / n) * TAU;
          tie.push(bun.clone().add(v(Math.sin(a) * r * 0.8, -r * 0.62, Math.cos(a) * r * 0.76)));
        }
        S.tube(tie, [0.007, 0.01], k(RED, PLATE.prop), B.head, { seg: lod(q, 5), closed: true });
        strand([bun.clone().add(v(-r * 0.62, r * 0.5, r * 0.5)), bun.clone().add(v(0, r * 0.8, r * 0.44)), bun.clone().add(v(r * 0.62, r * 0.5, r * 0.5))], 0.003);
      }
      break;
    }
    case 'tresses': {
      const edge = both([[0, -56], [0.5, -52], [0.95, -36], [1.25, -14], [Math.PI / 2, 4], [2.2, 16], [Math.PI, 22]]);
      cap(edge, (_th, u) => 0.006 + 0.018 * Math.pow(u, 0.6), { seg: lod(q, CAP), rows: lod(q, 10) });
      // two braids from behind the ears, down over the front of the shoulders, tied in red
      for (const s of [-1, 1]) {
        const start = onHead(head, hc, lat(8), s * 1.72, 0.012);
        let p = start.clone();
        for (let i = 0; i < 7; i++) {
          const y = start.y - 0.026 - i * 0.042;
          const x = s * Math.max(0.1, Math.abs(start.x) - i * 0.004);
          const body = y < sy + 0.04 ? frontZ(bands, Math.min(Math.abs(x), 0.1) * s, y) + 0.02 : -1;
          p = v(x, y, Math.max(start.z + i * 0.004, body));
          const r = (8 - i * 0.4) * head.s * 0.95;
          S.ball(p, v(r, r * 1.12, r), i % 2 ? light : hairInk, fallBind(p), { seg: lod(q, 8), rings: lod(q, 5) });
        }
        const tieAt = p.clone().add(v(0, -0.03, 0));
        S.ball(tieAt, v(0.014, 0.012, 0.014), k(RED, PLATE.prop), fallBind(tieAt), { seg: lod(q, 8), rings: lod(q, 4) });
        for (const dx of [-0.008, 0, 0.008]) {
          if (!q.trinkets) break;
          const t0 = tieAt.clone().add(v(dx * 0.5, -0.008, 0));
          S.tube([t0, t0.clone().add(v(dx, -0.03, 0.002))], 0.0035, hairInk, fallBind(t0), { seg: 4, caps: true });
        }
      }
      break;
    }
    default:
      // bald: the shine is printed
      return 0;
  }
  return hatted ? 0.012 : 0.03;
}

/* ---- hats ---------------------------------------------------------------------------------- */

function hat(b: Build, d: Dress, clear: number) {
  const { S, head, hc } = b;
  const { look, cfg, q } = d;
  const c = look.hat;
  const dark = deeper(c);
  const felt = k(c, PLATE.prop);
  const band = k(dark, PLATE.under);
  const lat = (y: number) => head.latOf(y);
  /** a ring round the head at a head-frame height, `out` off it */
  const around = (y: number | ((th: number) => number), out: number, thick: number | [number, number], k0: Ink) => {
    const pts: Vector3[] = [];
    const n = lod(q, 28);
    for (let i = 0; i < n; i++) {
      const th = (i / n) * TAU;
      pts.push(onHead(head, hc, lat(typeof y === 'number' ? y : y(th)), th, out));
    }
    S.tube(pts, thick, k0, B.head, { seg: lod(q, 6), closed: true });
  };
  const crown = (edge: (th: number) => number, thick: (u: number) => number) => hairCap(S, head, hc, { edge, thick: (_th, u) => clear + thick(u), ink: felt, bind: B.head, seg: lod(q, 32), rows: lod(q, 9) });
  /** a brim from the crown's edge (`off` off the head there), `out` further out and `drop` down, `thick` through */
  const brim = (edge: (th: number) => number, off: number, out: number, drop: number, thick: number, k0: Ink) => {
    const n = lod(q, 36);
    const pts: Vector3[] = [];
    const tris: Array<[number, number, number]> = [];
    for (let i = 0; i < n; i++) {
      const th = (i / n) * TAU;
      const p = onHead(head, hc, lat(edge(th)), th, off);
      const rim = p.clone().addScaledVector(v(p.x - hc.x, 0, p.z - hc.z).normalize(), out).add(v(0, -drop, 0));
      pts.push(p, rim, p.clone().add(v(0, -thick, 0)), rim.clone().add(v(0, -thick, 0)));
    }
    for (let i = 0; i < n; i++) {
      const a = i * 4;
      const c = ((i + 1) % n) * 4;
      // over, under, and round the outside
      tris.push([a, a + 1, c + 1], [a, c + 1, c], [a + 2, c + 3, a + 3], [a + 2, c + 2, c + 3], [a + 1, a + 3, c + 3], [a + 1, c + 3, c + 1]);
    }
    S.mesh(pts, tris, k0, B.head);
  };
  const top = onHead(head, hc, Math.PI / 2, 0, clear);
  switch (cfg.hat) {
    case 'beret': {
      // soft and flat over the crown, slipped back and to the left
      const tilt = new Quaternion().setFromAxisAngle(v(0, 0, 1), -0.14).multiply(new Quaternion().setFromAxisAngle(v(1, 0, 0), -0.12));
      S.ball(top.clone().add(v(0.012, -0.01, -0.012)), v(0.15, 0.048, 0.145), felt, B.head, { seg: lod(q, 20), rings: lod(q, 9), rot: tilt });
      around((th) => -50 + 6 * backOf(th), clear + 0.008, [0.007, 0.011], band);
      if (q.trinkets) S.tube([top.clone().add(v(0.006, 0.03, -0.006)), top.clone().add(v(0.01, 0.052, -0.006))], 0.0045, band, B.head, { seg: 5, caps: true });
      break;
    }
    case 'bonnet': {
      // the beanie, its turned-up cuff and a pompom
      const rim = (th: number) => -34 + 10 * backOf(th);
      crown(rim, (u) => 0.008 + 0.03 * Math.pow(u, 1.3));
      around((th) => rim(th) - 7, clear + 0.012, [0.012, 0.02], band);
      const pom = onHead(head, hc, Math.PI / 2, 0, clear + 0.038 + 0.028);
      S.ball(pom, 0.034, k(isPale(c) ? dark : PAPER, PLATE.under), B.head, { seg: lod(q, 10), rings: lod(q, 6) });
      break;
    }
    case 'casquette': {
      // the cap and its peak, turned a little to the left
      crown((th) => -42 + 10 * backOf(th), (u) => 0.008 + 0.012 * u);
      if (q.trinkets) S.ball(onHead(head, hc, Math.PI / 2, 0, clear + 0.02), v(0.011, 0.007, 0.011), band, B.head, { seg: 8, rings: 4 });
      const yaw = 0.28;
      const p = onHead(head, hc, lat(-40), yaw, clear + 0.004);
      const peak: Array<[number, number]> = [];
      for (let i = 0; i <= 10; i++) {
        const a = (i / 10) * Math.PI;
        peak.push([Math.cos(a) * 0.092, Math.sin(a) * 0.078]);
      }
      peak.push([-0.07, -0.03], [0.07, -0.03]);
      const turned = new Quaternion().setFromAxisAngle(v(0, 1, 0), yaw).multiply(new Quaternion().setFromAxisAngle(v(1, 0, 0), Math.PI / 2 + 0.16));
      S.slab(peak, 0.006, new Matrix4().compose(p, turned, v(1, 1, 1)), band, B.head);
      break;
    }
    case 'bob': {
      // the bucket hat: a low crown, the brim sloping down all round from its edge
      const rim = (th: number) => -46 + 6 * backOf(th);
      crown(rim, (u) => 0.01 + 0.014 * u);
      brim(rim, clear + 0.012, 0.056, 0.03, 0.007, band);
      break;
    }
    case 'canotier': {
      // the straw boater: a flat top, its ribbon in the chosen colour, the wide brim
      const yb = hc.y + (head.y0 + 50) * head.s + clear * 0.5;
      const yt = yb + 0.095;
      const rc = head.wide * head.s * 0.98 + clear + 0.014;
      const rb = rc + 0.085;
      const m = new Matrix4().makeTranslation(hc.x, 0, hc.z - 0.012);
      S.lathe([[0, yt], [rc, yt]], lod(q, 24), m, k(lighter(STRAW, 0.4), PLATE.under), B.head, { flat: true });
      S.lathe([[rc, yt], [rc, yb]], lod(q, 24), m, k(STRAW, PLATE.prop), B.head);
      S.lathe([[rc + 0.002, yb + 0.034], [rc + 0.002, yb + 0.004]], lod(q, 24), m, k(c, PLATE.under), B.head);
      S.lathe([[rc - 0.004, yb + 0.004], [rb, yb], [rb, yb - 0.008], [rc - 0.004, yb - 0.006]], lod(q, 32), m, k(deeper(STRAW, 0.18), PLATE.bottom), B.head);
      break;
    }
    default:
      break;
  }
}

/* ---- glasses and earrings ------------------------------------------------------------------ */

function glasses(b: Build, d: Dress) {
  const { S, head, hc } = b;
  const kind = d.cfg.glasses;
  if (kind === 'aucunes' || !d.q.trinkets) return;
  const frame = k(kind === 'rondes' ? GOLD : kind === 'grandes' ? RED : INK, PLATE.prop);
  const tube = kind === 'rondes' ? 0.0026 : 0.0032;
  const out = 0.015;
  /** a head-frame point on the plane of the lens about the eye (ex, ey), turned with the face */
  const lensPoint = (ex: number, ey: number) => {
    const c = head.at(ex, ey, head.frontAt(ex, ey) + out).add(hc);
    const q = new Quaternion().setFromAxisAngle(v(0, 1, 0), ((ex - head.x0) / head.wide) * 0.55);
    return (x: number, y: number) => v((x - ex) * head.s, (ey - y) * head.s, 0).applyQuaternion(q).add(c);
  };
  for (const s of [-1, 1]) {
    const ex = s * 15;
    const at = lensPoint(ex, -4);
    if (kind === 'soleil') {
      // the dark lenses, cut as the kit draws them
      const lens: Array<[number, number]> = [[-32, -15], [-3, -15], [-4, 1], [-10, 7.5], [-22, 7.5], [-30, 1]].map(([x, y]) => [s < 0 ? x : -x, y] as [number, number]);
      const c = at(ex, -4);
      const m = new Matrix4().compose(c, new Quaternion().setFromAxisAngle(v(0, 1, 0), (ex / head.wide) * 0.55), v(1, 1, 1));
      S.slab(lens.map(([x, y]) => [(x - ex) * head.s, (-4 - y) * head.s] as [number, number]), 0.004, m, frame, B.head);
    } else {
      const ring: Vector3[] = [];
      if (kind === 'carrees') {
        // a rounded rectangle, x 2…29 out from the middle, y -17…8, as the kit draws it
        const [x0, x1, y0, y1, r] = [2, 29, -17, 8, 3.5];
        const corners: Array<[number, number, number]> = [
          [x1 - r, y0 + r, -Math.PI / 2],
          [x1 - r, y1 - r, 0],
          [x0 + r, y1 - r, Math.PI / 2],
          [x0 + r, y0 + r, Math.PI],
        ];
        for (const [cx, cy, a0] of corners) {
          for (let i = 0; i <= 3; i++) {
            const a = a0 + (i / 3) * (Math.PI / 2);
            ring.push(at(s * (cx + Math.cos(a) * r), cy + Math.sin(a) * r));
          }
        }
      } else {
        const r = kind === 'grandes' ? 16 : 13.5;
        for (let i = 0; i < 20; i++) {
          const a = (i / 20) * TAU;
          ring.push(at(ex + Math.cos(a) * r, -4 + Math.sin(a) * r));
        }
      }
      S.tube(ring, tube, frame, B.head, { seg: 5, closed: true });
    }
    // the arm back to the ear
    const edge = kind === 'grandes' ? 31 : kind === 'soleil' ? 32 : 28.5;
    const f0 = at(s * edge, -7);
    const ear = head.at(head.x0 + s * (head.width(-3) + 1), -3, -0.006).add(hc);
    const mid = f0.clone().lerp(ear, 0.5).add(v(s * 0.008, 0, 0));
    S.tube([f0, mid, ear], tube * 0.85, frame, B.head, { seg: 4 });
  }
  if (kind !== 'grandes') {
    const at = lensPoint(0, -6);
    const y = kind === 'carrees' ? -9 : -7;
    S.tube([at(-2.5, y), at(0, y - 3), at(2.5, y)], tube, frame, B.head, { seg: 4 });
  }
}

function earpieces(b: Build, d: Dress) {
  const { S, head, hc } = b;
  const kind = d.cfg.ears;
  if (kind === 'aucunes' || !d.q.trinkets) return;
  const gold = k(GOLD, PLATE.prop);
  for (const s of [-1, 1]) {
    const lobe = (y: number, dx = -1, z = -0.004) => head.at(head.x0 + s * (head.width(y) + dx), y, z).add(hc);
    if (kind === 'anneaux') {
      const p = lobe(16);
      const r = 5 * head.s;
      const ring: Vector3[] = [];
      for (let i = 0; i < 14; i++) {
        const a = (i / 14) * TAU;
        ring.push(p.clone().add(v(s * 0.004, -r + Math.cos(a) * r, Math.sin(a) * r)));
      }
      S.tube(ring, 0.0022, gold, B.head, { seg: 5, closed: true });
    } else if (kind === 'perles') {
      S.ball(lobe(14, 1).add(v(0, 0, 0.004)), 3.2 * head.s, k(PAPER, PLATE.prop), B.head, { seg: 8, rings: 5 });
    } else if (kind === 'boucles_or') {
      S.ball(lobe(13, 1), 2.2 * head.s, gold, B.head, { seg: 6, rings: 4 });
      const drop = lobe(22, 1.5);
      S.ball(drop, v(3 * head.s, 6 * head.s, 2.4 * head.s), gold, B.head, { seg: 8, rings: 5 });
      S.ball(drop.clone().add(v(s * 0.003, 0.004, 0.006)), 2 * head.s, k(RED, PLATE.under), B.head, { seg: 6, rings: 4 });
    } else if (kind === 'crayon' && s > 0) {
      // the pencil tucked behind the left ear, its point up
      const p0 = lobe(10, 3, -0.016);
      const p1 = lobe(-32, 7, -0.022);
      const dir = p1.clone().sub(p0).normalize();
      const r = 0.0058;
      S.tube([p0, p1], r, k(YELLOW, PLATE.prop), B.head, { seg: 6 });
      S.tube([p1, p1.clone().addScaledVector(dir, 0.018), p1.clone().addScaledVector(dir, 0.026)], [r, r * 0.4, 0.0008], k('#e6dfcf', PLATE.under), B.head, { seg: 6 });
      S.tube([p0.clone().addScaledVector(dir, -0.012), p0], r, k('#a59e8f', PLATE.under), B.head, { seg: 6 });
      S.tube([p0.clone().addScaledVector(dir, -0.022), p0.clone().addScaledVector(dir, -0.012)], r, k('#f07f86', PLATE.skin2), B.head, { seg: 6, caps: 0.003 });
    }
  }
}

/* ---- the person ---------------------------------------------------------------------------- */

function build(b: Build, d: Dress) {
  neck(b, k(d.look.tone.skin, PLATE.skin2), 0.036, { seg: lod(d.q, 14) });
  top(b, d);
  neckpiece(b, d);
  pin(b, d);
  wristpiece(b, d);
  const clear = hair(b, d);
  if (d.hatted) hat(b, d, clear);
  glasses(b, d);
  earpieces(b, d);
}

/** The body for a record: Romy's proportions, a little different from one seed to the next. */
function bodyOf(height: number, seed: number): BodySpec {
  const R = seeded(seed * 31 + 7);
  return {
    height,
    head: R.range(0.345, 0.37),
    neck: R.range(0.062, 0.075),
    shoulders: R.range(0.14, 0.166),
    hips: R.range(0.07, 0.08),
    legs: R.range(0.41, 0.43),
    arm: 0.33,
    hand: 0.115,
    foot: R.range(0.2, 0.225),
  };
}

/** Someone the avatar kit draws, from their record, as a person in the round. */
export function avatarPerson(cfg: AvatarConfig, who: AvatarWho): Person {
  const look = lookOf(cfg);
  const seed = who.seed ?? 1;
  const name = who.name ?? 'Passant';
  // their card's height is to the top of the hair; the body stops at the crown
  const body = bodyOf((who.height ?? 1.7) * 0.965, seed);
  const fig = avatarFigure(cfg, name);
  const hatted = cfg.hat !== 'aucun';
  const bearded = ROUND_JAW.has(cfg.beard);
  const energy = seeded(seed * 17 + 3).range(0.85, 1.25);
  const head: HeadDef = {
    outline: FACE_PATHS[cfg.face] ?? FACE_PATHS.ovale,
    nose: NOSE,
    noseDepth: 0.75,
    ears: COVERS_EARS.has(cfg.hair)
      ? []
      : [
          [-38, 2, 7, 11],
          [38, 2, 7, 11],
        ],
    chin: cfg.beard === 'pleine' ? 17 : cfg.beard === 'courte' ? 15 : 13,
    wrap: bearded ? [2.05, 2.6] : undefined,
  };
  const dress = (q: Detail): Dress => ({ look, cfg, hatted, w: body.shoulders / 0.15, bands: [], q });
  return {
    key: who.key,
    name,
    skin: hex(look.tone.skin),
    body,
    head,
    look: faceLook(look),
    face: () => vivantFace(fig),
    eyes: EYE_AT,
    headMesh: HEAD,
    build: (b) => build(b, dress(NEAR)),
    // across the square: the ears are less than a pixel
    far: { head: { ...head, ears: [] }, headMesh: [lod(FAR, HEAD[0]), lod(FAR, HEAD[1])], build: (b) => build(b, dress(FAR)) },
    manner: { energy },
  };
}
