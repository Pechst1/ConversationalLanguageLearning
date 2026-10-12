/**
 * La troupe vivante · the jointed edition of the drawn cast.
 *
 * An addition, never a replacement: the rigs in `../rigs` keep drawing the cast everywhere they
 * do today. A vivant figure is the same drawing, kept line for line, cut at the shoulder, the
 * elbow, the wrist and the neck, so it can act: ten faces and six gestures per character, each
 * performed in that character's own way (their acting sheet sits at the top of their file).
 *
 * Everything that moves is CSS generated from the pose tables here, so a figure plays without
 * JavaScript, `still` or Reduce Motion freezes it on the gesture's clearest pose, and a canvas or
 * a server render shows the same thing.
 *
 *   joints   body (lean about the hips), head (about the neck), lu/lf/lh and ru/rf/rh (upper arm,
 *            forearm, hand; L is the viewer's left), lhp/rhp (a held prop kept upright)
 *   parts    named props and secondary pieces a figure declares (the cards, the tally light…)
 *   windows  when a hand shape, a face or a prop is shown within a gesture
 */
import type { ReactElement } from 'react';
import type { Brow, EyeParams, EyeState, EyeValues, RigDef } from '../rig-kit';
import { BASE_MOUTHS, SYMMETRIC_MOUTHS, ellipse, eye as rigEye, INK } from '../rig-kit';

export type Pt = [number, number];
export type Side = 'L' | 'R';

export type ExpressionId =
  | 'neutre' | 'joie' | 'malice' | 'fier' | 'surprise' | 'panique' | 'fache' | 'emu' | 'amour' | 'fatigue';
export type GestureId = 'salut' | 'bravo' | 'oups' | 'reflechit' | 'montre' | 'signature';

export const EXPRESSIONS: readonly ExpressionId[] = [
  'neutre', 'joie', 'malice', 'fier', 'surprise', 'panique', 'fache', 'emu', 'amour', 'fatigue',
];
export const GESTURES: readonly GestureId[] = ['salut', 'bravo', 'oups', 'reflechit', 'montre', 'signature'];

/** `ball` is the rigs' own round hand; the others are drawn by the kit about the palm centre. */
export type HandShape = 'ball' | 'fist' | 'open' | 'point' | 'thumb' | 'two' | 'pinch' | 'flat';

export type VEyeState = EyeState | 'squeeze' | 'tiny' | 'roll' | 'down' | 'sparkle' | 'smug';

/** Small drawn effects around the head, all in the figure's head frame. */
export type FxKind =
  | 'blush' | 'sweat' | 'tears' | 'sparkle' | 'hearts' | 'zzz' | 'vein' | 'steam' | 'shock' | 'question' | 'glint';

export interface ArmDef {
  shoulder: Pt;
  elbow: Pt;
  /** the hand's centre at rest */
  palm: Pt;
  /** palm radius, the rig's hand circle */
  r: number;
}

export interface FaceDef {
  eyes: [VEyeState, VEyeState];
  brows: [Brow, Brow];
  mouth: string;
  /** head pose for this face: tilt about the head centre, then a nudge */
  tilt?: number;
  dx?: number;
  dy?: number;
  /** pupils looking somewhere other than the rig's resting gaze */
  gaze?: Pt;
  fx?: FxKind[];
  /** mouth cycles through visemes (a line being said) */
  talk?: boolean;
}

export interface ExpressionDef extends FaceDef {
  /** the character's own name for it: Margaux's `malice` is «Oracle» */
  label: string;
  /** what the face is, in a few words, for the sheet */
  note: string;
  /** body language that comes with the face when no gesture plays */
  pose?: Key;
  hands?: Partial<Record<Side, HandShape>>;
  show?: string[];
  /** arms drawn in front of the head for this pose (a fist under the chin) */
  front?: Side[];
}

/** One arm in one key: a target for the hand (solved) or plain angles. */
export interface ArmKey {
  /** where the palm goes, in the figure's rest frame */
  to?: Pt;
  /** elbow tucked toward the body (true) or flung out (false); by default it stays on the
   *  side it came from, so a move never flips the arm inside out */
  tuck?: boolean;
  /** forearm reach: > 1 reads as the hand coming toward the camera */
  reach?: number;
  u?: number;
  f?: number;
  /** absolute finger direction, degrees: 0 up, 90 the viewer's right, 180 down */
  h?: number;
}

export interface PartKey {
  x?: number;
  y?: number;
  r?: number;
  s?: number;
  o?: number;
}

export interface Key {
  at: number;
  /** timing from this key to the next */
  ease?: string;
  L?: ArmKey;
  R?: ArmKey;
  body?: number;
  bodyY?: number;
  head?: number;
  headX?: number;
  headY?: number;
  parts?: Record<string, PartKey>;
}

export interface GestureDef {
  label: string;
  /** what the character says while doing it */
  line: string;
  note: string;
  seconds: number;
  /** one of the figure's ten faces, or a face of its own for this gesture */
  face?: ExpressionId | FaceDef;
  /** a second face from this point of the cycle on */
  then?: [number, ExpressionId | FaceDef];
  /** arms drawn in front of the head during the action (a camera to the eye) */
  front?: Side[];
  talk?: boolean;
  hands?: Partial<Record<Side, HandShape>>;
  /** props shown during the action: id → [from, to] (default: the action window) */
  show?: Record<string, [number, number] | true>;
  /** hide a resting prop during the action */
  hide?: Record<string, [number, number] | true>;
  keys: Key[];
  /** index of the key that stands for the whole gesture when nothing may move */
  peak: number;
}

export interface FigureDef {
  key: string;
  name: string;
  rig: RigDef;
  arms: Record<Side, ArmDef>;
  hips: Pt;
  neck: Pt;
  skin: string;
  shade: string;
  blink: number;
  idle: { kind: 'bob' | 'bounce' | 'sway' | 'nod'; seconds: number; amount: number };
  parts: Record<string, Pt>;
  expressions: Record<ExpressionId, ExpressionDef>;
  gestures: Record<GestureId, GestureDef>;
  /** anchor points in the head frame for the effects */
  fx: { cheekL: Pt; cheekR: Pt; temple: Pt; crown: Pt; side: Pt; eyeL: Pt; eyeR: Pt };
  Art: (p: { faces: Array<{ id: string; values: FaceValues }>; base: ExpressionId }) => ReactElement;
}

/* ------------------------------------------------------------------------------------------ */
/* Geometry                                                                                     */

const DEG = 180 / Math.PI;
const angleOf = (a: Pt, b: Pt) => Math.atan2(b[1] - a[1], b[0] - a[0]) * DEG;
const dist = (a: Pt, b: Pt) => Math.hypot(b[0] - a[0], b[1] - a[1]);
const norm = (deg: number) => {
  let d = deg % 360;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return d;
};
const r2 = (n: number) => Math.round(n * 100) / 100;

/** Which way an arm bends: the side of the shoulder→hand line its elbow is on. */
export function bendOf(S: Pt, E: Pt, T: Pt): number {
  return Math.sign((T[0] - S[0]) * (E[1] - S[1]) - (T[1] - S[1]) * (E[0] - S[0])) || 1;
}

export interface ArmAngles {
  u: number;
  f: number;
  h: number;
  s: number;
}

/**
 * Two-bone reach: rotate the upper arm about the shoulder and the forearm about the elbow so the
 * palm lands on `to`. Out of reach, the arm points at it fully stretched.
 */
export function solveArm(arm: ArmDef, k: ArmKey | undefined, bend: number = bendOf(arm.shoulder, arm.elbow, arm.palm)): ArmAngles {
  if (!k) return { u: 0, f: 0, h: 0, s: 1 };
  const s = k.reach ?? 1;
  let u = k.u ?? 0;
  let f = k.f ?? 0;
  if (k.to) {
    const S = arm.shoulder;
    const a = dist(S, arm.elbow);
    const b = dist(arm.elbow, arm.palm) * s;
    const d = Math.min(Math.max(dist(S, k.to), Math.abs(a - b) + 0.01), a + b - 0.01);
    const th = angleOf(S, k.to);
    const al = Math.acos((a * a + d * d - b * b) / (2 * a * d)) * DEG;
    const elbowAt = (deg: number): Pt => [S[0] + a * Math.cos(deg / DEG), S[1] + a * Math.sin(deg / DEG)];
    const e1 = elbowAt(th + al);
    const e2 = elbowAt(th - al);
    const out = (e: Pt) => Math.abs(e[0] - 100);
    let E: Pt;
    if (k.tuck === undefined) E = bendOf(S, e1, k.to) === bend ? e1 : e2;
    else E = (out(e1) >= out(e2)) === !k.tuck ? e1 : e2;
    u = norm(angleOf(S, E) - angleOf(S, arm.elbow));
    f = norm(angleOf(E, k.to) - angleOf(arm.elbow, arm.palm) - u);
  }
  // the hand: fingers drawn pointing up; `h` is where they point in the world
  const h = k.h === undefined ? 0 : norm(k.h - u - f);
  return { u: r2(u), f: r2(f), h: r2(h), s };
}

/** The elbow's place for a solved pose. */
export function elbowAt(arm: ArmDef, a: ArmAngles): Pt {
  const t = a.u / DEG;
  const x = arm.elbow[0] - arm.shoulder[0];
  const y = arm.elbow[1] - arm.shoulder[1];
  return [arm.shoulder[0] + x * Math.cos(t) - y * Math.sin(t), arm.shoulder[1] + x * Math.sin(t) + y * Math.cos(t)];
}

/** Where the palm ends up for a solved pose (used by tests and by props that follow a hand). */
export function palmAt(arm: ArmDef, a: ArmAngles): Pt {
  const rot = (p: Pt, c: Pt, deg: number): Pt => {
    const t = deg / DEG;
    const x = p[0] - c[0];
    const y = p[1] - c[1];
    return [c[0] + x * Math.cos(t) - y * Math.sin(t), c[1] + x * Math.sin(t) + y * Math.cos(t)];
  };
  const E = rot(arm.elbow, arm.shoulder, a.u);
  const P0 = rot(arm.palm, arm.shoulder, a.u);
  const dir = rot(P0, E, a.f);
  return [E[0] + (dir[0] - E[0]) * a.s, E[1] + (dir[1] - E[1]) * a.s];
}

/* ------------------------------------------------------------------------------------------ */
/* Faces                                                                                        */

export interface VEye extends EyeValues {
  lower: string;
  lowerLine: string;
  spark: string;
  /** an open eye blinks; an arc does not */
  blinks: boolean;
  /** the blink lid: covers the white, its edge the closed line */
  blinkLid: string;
  blinkLine: string;
  /** pivot of the blink (top of the eye) */
  blinkTop: Pt;
}

const EMOTIONAL = new Set<VEyeState>(['wide', 'cross', 'sad', 'tiny']);

export function vEye(centre: Pt, p: EyeParams, state: VEyeState, side: -1 | 1, gaze?: Pt): VEye {
  const [cx, cy] = centre;
  const { rx, ry } = p;
  const base: EyeState =
    state === 'squeeze' ? 'shut'
      : state === 'tiny' ? 'wide'
        : state === 'roll' ? 'open'
          : state === 'down' ? 'heavy'
            : state === 'sparkle' ? 'open'
              : state === 'smug' ? 'open'
                : state;
  const o = rigEye(centre, p, base, side) as VEye;
  o.lower = '';
  o.lowerLine = '';
  o.spark = '';
  const hw = rx + 3.5;
  const lidAt = (yl: number, yr: number, bow: number) => {
    const top = cy - ry - 5;
    const mid = (yl + yr) / 2 - bow;
    o.lid = `M${cx - hw},${top} L${cx + hw},${top} L${cx + hw},${yr} Q${cx},${mid} ${cx - hw},${yl} Z`;
    const k = 3.5 / (2 * hw);
    o.lidLine = `M${cx - rx},${yl + (yr - yl) * k} Q${cx},${mid} ${cx + rx},${yr - (yr - yl) * k}`;
  };
  const lowerAt = (y: number, bow: number) => {
    const bottom = cy + ry + 5;
    o.lower = `M${cx - hw},${bottom} L${cx + hw},${bottom} L${cx + hw},${y} Q${cx},${y + bow} ${cx - hw},${y} Z`;
    o.lowerLine = `M${cx - rx * 0.8},${y + bow * 0.2} Q${cx},${y + bow} ${cx + rx * 0.8},${y + bow * 0.2}`;
  };
  // where the pupil sits: the rig's own place, moved by the new states, then by a gaze
  const centred = p.centreOnEmotion && EMOTIONAL.has(state);
  let px = cx + (centred ? 0 : p.dx || 0);
  let py = cy + (p.dy || 0) + 1;
  let r = p.pr;
  let redraw = Boolean(gaze);
  switch (state) {
    case 'squeeze': {
      const n = side < 0 ? 1 : -1; // the chevron points at the nose
      o.arc = `M${cx - n * rx * 0.85},${cy - ry * 0.55} L${cx + n * rx * 0.7},${cy + 0.5} L${cx - n * rx * 0.85},${cy + ry * 0.6}`;
      break;
    }
    case 'tiny':
      r = p.pr * 0.42;
      py = cy;
      redraw = true;
      break;
    case 'roll':
      lidAt(cy - ry * 0.42, cy - ry * 0.42, ry * 0.08);
      px = cx + (p.dx || 0) * 0.3;
      py = cy - ry * 0.48;
      redraw = true;
      break;
    case 'down':
      py = cy + ry * 0.38;
      redraw = true;
      break;
    case 'sparkle':
      r = p.pr * 1.08;
      redraw = true;
      break;
    case 'smug':
      lidAt(cy - ry * 0.08, cy - ry * 0.08, ry * 0.1);
      lowerAt(cy + ry * 0.42, -ry * 0.16);
      break;
    case 'wide':
      r = p.pr - 1;
      py = cy;
      break;
    case 'sad':
      py = cy + 3;
      break;
    default:
      break;
  }
  if (redraw && o.sD !== 'none') {
    if (gaze) {
      px = cx + Math.max(-rx * 0.42, Math.min(rx * 0.42, gaze[0]));
      py += Math.max(-ry * 0.4, Math.min(ry * 0.4, gaze[1]));
    }
    const pupil = state === 'tiny' ? 0.6 : 0.48;
    if (p.iris) {
      o.iris = ellipse(px, py, r, r);
      o.pupil = ellipse(px, py, r * pupil, r * pupil);
    } else {
      o.pupil = ellipse(px, py, r, r);
    }
    const g = state === 'sparkle' ? 0.46 : 0.32;
    o.glint = state === 'tiny' ? '' : ellipse(px + r * 0.4, py - r * 0.38, r * g, r * g);
    if (state === 'sparkle') o.spark = ellipse(px - r * 0.38, py + r * 0.4, r * 0.18, r * 0.18);
  }
  o.blinks = o.sD !== 'none';
  const top = cy - ry - 1.5;
  o.blinkTop = [cx, top];
  o.blinkLid = ellipse(cx, cy, rx + 1.6, ry + 1.6);
  o.blinkLine = `M${cx - rx},${cy + ry * 0.55} Q${cx},${cy + ry * 0.95} ${cx + rx},${cy + ry * 0.55}`;
  return o;
}

/** Mouths beyond the rigs' own, in the same local frame (centred near 2,16). [shape, teeth, tongue, line] */
export const VIVANT_MOUTHS: Record<string, [string, string?, string?, string?]> = {
  laugh: [
    'M-9,12.5 Q2,14 13,12.5 Q11.5,26 2,26 Q-7.5,26 -9,12.5 Z',
    'M-7.6,13.1 Q2,14.6 11.6,13.1 L11,15.6 Q2,17.4 -7,15.6 Z',
    'M-3.5,22.5 Q2,19.5 7.5,22.5 Q5.5,25.6 2,25.7 Q-1.5,25.6 -3.5,22.5 Z',
  ],
  teeth: [
    'M-7,13.5 Q2,17.5 11,13 Q9,21.5 2,21.5 Q-5,21.5 -7,13.5 Z',
    'M-6.2,14.1 Q2,17.9 10.2,13.7 L9.6,16.6 Q2,20 -5.6,16.8 Z',
  ],
  grimace: [
    'M-8,13 Q2,11.8 12,13 L11.6,19.6 Q2,20.8 -7.6,19.6 Z',
    'M-7,13.8 Q2,12.8 11,13.8 L10.7,18.8 Q2,19.8 -6.7,18.8 Z',
    '',
    'M-6.7,16.3 Q2,16.9 10.7,16.3 M-2,14 L-2,18.9 M2,13.5 L2,19.3 M6,13.8 L6,19',
  ],
  shout: [
    'M-7,12.5 Q2,10.5 11,12.5 Q10.5,24 2,24 Q-6.5,24 -7,12.5 Z',
    'M-6,13 Q2,11.3 10,13 L9.8,14.8 Q2,13.4 -5.8,14.8 Z',
    'M-3,21 Q2,18.6 7,21 Q5,23.6 2,23.7 Q-1,23.6 -3,21 Z',
  ],
  yawn: [
    'M-2.5,15 A4.5,7 0 1 0 6.5,15 A4.5,7 0 1 0 -2.5,15 Z',
    '',
    'M-0.5,19.5 Q2,17.8 4.5,19.5 Q3.6,21.6 2,21.7 Q0.4,21.6 -0.5,19.5 Z',
  ],
  bigO: [
    'M-2.5,16.5 A4.5,6 0 1 0 6.5,16.5 A4.5,6 0 1 0 -2.5,16.5 Z',
    '',
    'M-0.6,20 Q2,18.4 4.6,20 Q3.6,22.1 2,22.2 Q0.4,22.1 -0.6,20 Z',
  ],
  smileOpen: [
    'M-6,14 Q2,16 10,14 Q8,21 2,21 Q-4,21 -6,14 Z',
    '',
    'M-2,19 Q2,17.4 6,19 Q4,21 2,21 Q0,21 -2,19 Z',
  ],
  pout: ['M-1.5,15.5 Q2,12.6 5.5,15.5 Q2,18.8 -1.5,15.5 Z'],
  whistle: ['M0.2,16 A1.8,2.4 0 1 0 3.8,16 A1.8,2.4 0 1 0 0.2,16 Z'],
  tight: ['M-4,16 Q2,15.4 8,16 L8,17 Q2,17.6 -4,17 Z'],
  side: ['M-3,16.4 Q3,15.6 9.5,13.4 L9.9,14.9 Q3,17.3 -3,17.8 Z'],
  tremble: [
    'M-7,16 L-4.5,14.6 L-2,16 L0.5,14.6 L3,16 L5.5,14.6 L8,16 L10.5,14.6 L10.5,16.2 L8,17.6 L5.5,16.2 L3,17.6 L0.5,16.2 L-2,17.6 L-4.5,16.2 L-7,17.6 Z',
  ],
};

/** Mirror an absolute path about x = cx (M L Q C A Z only). */
export function mirrorPath(d: string, cx = 2): string {
  const tokens = d.match(/[MLQCAZ]|-?\d*\.?\d+(?:e-?\d+)?/gi) ?? [];
  const out: string[] = [];
  let cmd = '';
  let args: number[] = [];
  const flush = () => {
    if (!cmd) return;
    const c = cmd.toUpperCase();
    if (c === 'Z') {
      out.push('Z');
    } else if (c === 'A') {
      for (let i = 0; i + 6 < args.length + 1; i += 7) {
        const [rx, ry, rot, large, sweep, x, y] = args.slice(i, i + 7);
        out.push(`A${rx},${ry} ${-rot} ${large} ${sweep ? 0 : 1} ${r2(2 * cx - x)},${y}`);
      }
    } else {
      const pts: string[] = [];
      for (let i = 0; i + 1 < args.length; i += 2) pts.push(`${r2(2 * cx - args[i])},${args[i + 1]}`);
      out.push(`${c}${pts.join(' ')}`);
    }
  };
  for (const t of tokens) {
    if (/^[MLQCAZ]$/i.test(t)) {
      flush();
      cmd = t;
      args = [];
    } else {
      args.push(Number(t));
    }
  }
  flush();
  return out.join(' ');
}

const OPEN_MOUTHS = new Set(['a', 'o', 'e', 'f', 'grin', 'laugh', 'teeth', 'grimace', 'shout', 'yawn', 'bigO', 'smileOpen']);

export interface MouthValues {
  key: string;
  d: string;
  fill: string;
  teeth: string;
  tongue: string;
  line: string;
}

export function mouthFor(rig: RigDef, key: string): MouthValues {
  const mirrored = key.endsWith('~');
  const k = mirrored ? key.slice(0, -1) : key;
  const set = rig.mouthSet === 'symmetric' ? SYMMETRIC_MOUTHS : BASE_MOUTHS;
  const entry = (VIVANT_MOUTHS[k] ?? set[k] ?? set.rest) as [string, string?, string?, string?];
  const [shape, teeth = '', tongue = '', line = ''] = entry;
  const m = (d: string) => (d && mirrored ? mirrorPath(d) : d);
  return {
    key,
    d: m(shape),
    fill: OPEN_MOUTHS.has(k) ? INK : (rig.lips ?? INK),
    teeth: m(teeth),
    tongue: m(tongue),
    line: m(line),
  };
}

export interface FaceValues {
  eL: VEye;
  eR: VEye;
  browL: string;
  browR: string;
  mouths: MouthValues[];
  def: FaceDef;
}

const curve = (b: Brow) => `M${b[0]},${b[1]} Q${b[2]},${b[3]} ${b[4]},${b[5]}`;

export function faceValues(fig: FigureDef, face: FaceDef): FaceValues {
  const rig = fig.rig;
  const p = rig.eye!;
  const talk = face.talk ? ['a', 'e', 'o', 'm', face.mouth] : [face.mouth];
  return {
    eL: vEye(rig.eyeL!, p, face.eyes[0], -1, face.gaze),
    eR: vEye(rig.eyeR!, p, face.eyes[1], 1, face.gaze),
    browL: curve(face.brows[0]),
    browR: curve(face.brows[1]),
    mouths: talk.map((k) => mouthFor(rig, k)),
    def: face,
  };
}

/** Lift, lower or tilt a pair of brows (from a rig's mood brows). */
export function brows(b: [Brow, Brow], lift: [number, number] = [0, 0], inner: [number, number] = [0, 0]): [Brow, Brow] {
  const [l, r] = b;
  return [
    [l[0], l[1] - lift[0], l[2], l[3] - lift[0], l[4], l[5] - lift[0] + inner[0]],
    [r[0], r[1] - lift[1] + inner[1], r[2], r[3] - lift[1], r[4], r[5] - lift[1]],
  ];
}

/* ------------------------------------------------------------------------------------------ */
/* Hands                                                                                        */

export interface HandArt {
  palm: number;
  /** finger strokes: path, width */
  fingers: Array<[string, number]>;
  /** creases drawn in the shade over the skin */
  creases: string;
}

/**
 * A hand about its palm centre, fingers up, thumb toward the body (drawn for the viewer's right
 * hand; the left one is mirrored). Proportions follow the palm radius, so Marin's big hands and
 * Lila's small ones come from the same drawing.
 */
export function handArt(shape: HandShape, r: number): HandArt {
  const n = (v: number) => r2(v * r);
  const seg = (x1: number, y1: number, x2: number, y2: number) => `M${n(x1)},${n(y1)} L${n(x2)},${n(y2)}`;
  const thumbSide = -1; // toward the body for the viewer's right hand
  switch (shape) {
    case 'fist':
      return {
        palm: r,
        fingers: [[seg(thumbSide * 0.62, 0.05, thumbSide * 0.78, -0.45), 0.62 * r]],
        creases: `M${n(-0.55)},${n(-0.48)} Q${n(0.05)},${n(-0.78)} ${n(0.62)},${n(-0.45)} M${n(-0.05)},${n(-0.66)} L${n(-0.05)},${n(-0.2)} M${n(0.32)},${n(-0.6)} L${n(0.32)},${n(-0.18)}`,
      };
    case 'thumb':
      return {
        palm: r,
        fingers: [[seg(thumbSide * 0.25, -0.55, thumbSide * 0.3, -1.6), 0.62 * r]],
        creases: `M${n(0.95)},${n(-0.3)} L${n(-0.2)},${n(-0.3)} M${n(0.95)},${n(0.12)} L${n(-0.25)},${n(0.12)} M${n(0.9)},${n(0.52)} L${n(-0.2)},${n(0.52)}`,
      };
    case 'point':
      return {
        palm: r,
        fingers: [[seg(0.12, -0.5, 0.12, -2.05), 0.52 * r], [seg(thumbSide * 0.7, -0.05, thumbSide * 0.62, -0.62), 0.5 * r]],
        creases: `M${n(-0.2)},${n(-0.38)} Q${n(0.35)},${n(-0.62)} ${n(0.78)},${n(-0.32)} M${n(0.48)},${n(-0.52)} L${n(0.48)},${n(-0.12)}`,
      };
    case 'two':
      return {
        palm: r,
        fingers: [[seg(-0.22, -0.5, -0.32, -1.9), 0.48 * r], [seg(0.26, -0.5, 0.36, -1.82), 0.48 * r], [seg(thumbSide * 0.72, -0.02, thumbSide * 0.62, -0.58), 0.48 * r]],
        creases: `M${n(0.02)},${n(-0.62)} L${n(0.02)},${n(-1.2)} M${n(0.45)},${n(-0.42)} Q${n(0.75)},${n(-0.2)} ${n(0.8)},${n(0.15)}`,
      };
    case 'pinch':
      return {
        palm: r,
        fingers: [
          [`M${n(0.05)},${n(-0.5)} Q${n(0.1)},${n(-1.75)} ${n(-0.62)},${n(-1.85)}`, 0.46 * r],
          [`M${n(-0.72)},${n(-0.1)} Q${n(-1.25)},${n(-0.55)} ${n(-1.02)},${n(-1.2)}`, 0.5 * r],
        ],
        creases: `M${n(0.2)},${n(-0.5)} Q${n(0.6)},${n(-0.3)} ${n(0.82)},${n(0.05)}`,
      };
    case 'flat':
      return {
        palm: r * 0.94,
        fingers: [[seg(0.05, -0.4, 0.05, -1.62), 1.32 * r], [seg(thumbSide * 0.78, -0.05, thumbSide * 1.22, -0.72), 0.5 * r]],
        creases: `M${n(-0.18)},${n(-1.0)} L${n(-0.18)},${n(-2.1)} M${n(0.25)},${n(-1.0)} L${n(0.25)},${n(-2.12)}`,
      };
    case 'open': {
      const fan: Array<[number, number]> = [[-26, 1.28], [-9, 1.46], [8, 1.4], [25, 1.16]];
      const fingers: Array<[string, number]> = fan.map(([deg, len]) => {
        const t = (deg - 90) / DEG;
        const x0 = Math.cos(t) * 0.55;
        const y0 = Math.sin(t) * 0.55;
        return [seg(x0, y0, Math.cos(t) * (0.55 + len), Math.sin(t) * (0.55 + len)), 0.42 * r];
      });
      fingers.push([seg(thumbSide * 0.72, 0.05, thumbSide * 1.55, -0.62), 0.48 * r]);
      return { palm: r * 0.92, fingers, creases: `M${n(-0.35)},${n(0.15)} Q${n(0.05)},${n(0.42)} ${n(0.45)},${n(0.12)}` };
    }
    default:
      return { palm: r, fingers: [], creases: '' };
  }
}

/* ------------------------------------------------------------------------------------------ */
/* Motion: the generated CSS                                                                    */

const pct = (v: number) => `${r2(v * 100)}%`;
const EPS = 0.001;

interface Track {
  frames: Array<{ at: number; value: string; ease?: string }>;
}

function keyframes(name: string, t: Track, prop = 'transform'): string {
  const lines = t.frames.map((f) => `${pct(f.at)}{${prop}:${f.value};${f.ease ? `animation-timing-function:${f.ease};` : ''}}`);
  return `@keyframes ${name}{${lines.join('')}}`;
}

/** A shown/hidden window as an opacity track with near-instant edges. */
function windowTrack(from: number, to: number, inside: boolean): Track {
  const on = inside ? '1' : '0';
  const off = inside ? '0' : '1';
  const a = Math.max(from, EPS);
  const b = Math.min(to, 1 - EPS);
  return {
    frames: [
      { at: 0, value: off },
      { at: a - EPS, value: off },
      { at: a, value: on },
      { at: b, value: on },
      { at: b + EPS, value: off },
      { at: 1, value: off },
    ],
  };
}

function unwrap(values: number[]): number[] {
  const out: number[] = [];
  values.forEach((v, i) => {
    if (i === 0) {
      out.push(v);
      return;
    }
    let x = v;
    const prev = out[i - 1];
    while (x - prev > 180) x -= 360;
    while (x - prev < -180) x += 360;
    out.push(r2(x));
  });
  return out;
}

const NAMED_EASE: Record<string, [number, number, number, number]> = {
  linear: [0, 0, 1, 1],
  ease: [0.25, 0.1, 0.25, 1],
  'ease-in': [0.42, 0, 1, 1],
  'ease-out': [0, 0, 0.58, 1],
  'ease-in-out': [0.42, 0, 0.58, 1],
};

/** A CSS timing function as a function of progress (cubic-bezier and the named ones). */
export function easing(ease?: string): (x: number) => number {
  let c = NAMED_EASE[ease ?? 'linear'];
  const m = ease?.match(/cubic-bezier\(([^)]+)\)/);
  if (m) c = m[1].split(',').map(Number) as [number, number, number, number];
  if (!c) c = NAMED_EASE.linear;
  const [x1, y1, x2, y2] = c;
  const bx = (t: number) => 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3;
  const by = (t: number) => 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3;
  return (x: number) => {
    let lo = 0;
    let hi = 1;
    for (let i = 0; i < 30; i += 1) {
      const mid = (lo + hi) / 2;
      if (bx(mid) < x) lo = mid;
      else hi = mid;
    }
    return by((lo + hi) / 2);
  };
}

export interface ArmFrame {
  at: number;
  /** CSS timing to the next frame (only on frames the in-betweening left alone) */
  ease?: string;
  a: ArmAngles;
}

/**
 * One arm's frames over a gesture. Between two keys the hand travels the straight line between
 * its two places (eased as the key says) and the elbow follows the nearer bend, sampled into
 * in-betweens: interpolating the joint angles alone would swing the arm wide on the way.
 */
/**
 * How an arm turns from one pose to the next: upper arm and forearm each turn evenly, one way
 * round or the other, and of those four swings the one whose hand stays nearest the straight
 * path wins (lifting a camera comes up past the chest, not round by the hip).
 */
function swing(arm: ArmDef, from: { E: Pt; P: Pt; s: number }, to: { E: Pt; P: Pt; s: number }) {
  const S = arm.shoulder;
  const upper = dist(S, arm.elbow);
  const fore = dist(arm.elbow, arm.palm);
  const ways = (x: number, y: number) => {
    const t = norm(y - x);
    return [t, t - Math.sign(t || 1) * 360];
  };
  const fromE = angleOf(S, from.E);
  const fromF = angleOf(from.E, from.P);
  let best = { turnE: 0, turnF: 0, off: Infinity };
  for (const turnE of ways(fromE, angleOf(S, to.E))) {
    for (const turnF of ways(fromF, angleOf(to.E, to.P))) {
      let off = 0;
      for (let i = 1; i < 8; i += 1) {
        const p = i / 8;
        const e = (fromE + turnE * p) / DEG;
        const f = (fromF + turnF * p) / DEG;
        const b = fore * (from.s + (to.s - from.s) * p);
        const x = S[0] + upper * Math.cos(e) + b * Math.cos(f);
        const y = S[1] + upper * Math.sin(e) + b * Math.sin(f);
        off += Math.hypot(x - (from.P[0] + (to.P[0] - from.P[0]) * p), y - (from.P[1] + (to.P[1] - from.P[1]) * p));
      }
      if (off < best.off) best = { turnE, turnF, off };
    }
  }
  return { fromE, fromF, turnE: best.turnE, turnF: best.turnF };
}

export function armFrames(fig: FigureDef, keys: Key[], side: Side): ArmFrame[] {
  const arm = fig.arms[side];
  let bend = bendOf(arm.shoulder, arm.elbow, arm.palm);
  const poses = keys.map((k) => {
    const a = solveArm(arm, k[side], bend);
    const E = elbowAt(arm, a);
    const P = palmAt(arm, a);
    if (k[side]?.to) bend = bendOf(arm.shoulder, E, P);
    else if (!k[side]) bend = bendOf(arm.shoulder, arm.elbow, arm.palm);
    return { a, P, E, bend, hand: a.u + a.f + a.h, ik: Boolean(k[side]?.to) };
  });
  const frames: ArmFrame[] = [];
  for (let i = 0; i < keys.length; i += 1) {
    const k = keys[i];
    const here = poses[i];
    frames.push({ at: k.at, ease: k.ease, a: here.a });
    const next = poses[i + 1];
    if (!next) break;
    const moved = dist(here.P, next.P);
    const turned = Math.abs(here.a.u - next.a.u) + Math.abs(here.a.f - next.a.f);
    if (!(here.ik || next.ik) || (moved < 6 && turned < 25)) continue;
    frames[frames.length - 1].ease = undefined;
    const ease = easing(k.ease);
    // in-betweens: upper arm and forearm each turn evenly, so the hand travels in arcs, the ends
    // land exactly and the elbow never snaps to the other bend
    const { fromE, turnE, fromF, turnF } = swing(arm, { E: here.E, P: here.P, s: here.a.s }, { E: next.E, P: next.P, s: next.a.s });
    const steps = Math.min(16, Math.max(4, Math.round(moved / 6), Math.round(Math.max(Math.abs(turnE), Math.abs(turnF)) / 12)));
    for (let j = 1; j < steps; j += 1) {
      const q = j / steps;
      const p = ease(q);
      const lerp = (x: number, y: number) => x + (y - x) * p;
      const reach = lerp(here.a.s, next.a.s);
      const u = norm(fromE + turnE * p - angleOf(arm.shoulder, arm.elbow));
      const f = norm(fromF + turnF * p - angleOf(arm.elbow, arm.palm) - u);
      const hand = lerp(here.hand, next.hand);
      frames.push({ at: r2((k.at + (keys[i + 1].at - k.at) * q) * 10000) / 10000, a: { u: r2(u), f: r2(f), h: r2(norm(hand - u - f)), s: r2(reach * 1000) / 1000 } });
    }
  }
  (['u', 'f', 'h'] as const).forEach((j) => {
    const un = unwrap(frames.map((fr) => fr.a[j]));
    frames.forEach((fr, i) => {
      fr.a[j] = un[i];
    });
  });
  return frames;
}

/** When one arm is busy: from halfway into its first move to halfway out of its last. */
export function sideWindow(g: GestureDef, side: Side): [number, number] | null {
  const k = g.keys;
  const busy = k.map((key) => Boolean(key[side]));
  const first = busy.indexOf(true);
  const last = busy.lastIndexOf(true);
  if (first < 0) return null;
  const from = first > 0 ? (k[first - 1].at + k[first].at) / 2 : 0;
  const to = last < k.length - 1 ? (k[last].at + k[last + 1].at) / 2 : 1;
  return [r2(from), r2(to)];
}

export interface SolvedKey {
  at: number;
  ease?: string;
  L: ArmAngles;
  R: ArmAngles;
  body: [number, number];
  head: [number, number, number];
  parts: Record<string, PartKey>;
}

export function solveKeys(fig: FigureDef, keys: Key[]): SolvedKey[] {
  const rest = (side: Side) => bendOf(fig.arms[side].shoulder, fig.arms[side].elbow, fig.arms[side].palm);
  const bend: Record<Side, number> = { L: rest('L'), R: rest('R') };
  const arm = (k: Key, side: Side) => {
    const a = solveArm(fig.arms[side], k[side], bend[side]);
    if (k[side]?.to) bend[side] = bendOf(fig.arms[side].shoulder, elbowAt(fig.arms[side], a), palmAt(fig.arms[side], a));
    else if (!k[side]) bend[side] = rest(side);
    return a;
  };
  const solved = keys.map((k) => ({
    at: k.at,
    ease: k.ease,
    L: arm(k, 'L'),
    R: arm(k, 'R'),
    body: [k.body ?? 0, k.bodyY ?? 0] as [number, number],
    head: [k.head ?? 0, k.headX ?? 0, k.headY ?? 0] as [number, number, number],
    parts: k.parts ?? {},
  }));
  (['L', 'R'] as Side[]).forEach((side) => {
    (['u', 'f', 'h'] as const).forEach((j) => {
      const un = unwrap(solved.map((s) => s[side][j]));
      solved.forEach((s, i) => {
        s[side][j] = un[i];
      });
    });
  });
  return solved;
}

export const armTransform = {
  u: (a: ArmAngles) => `rotate(${a.u}deg)`,
  f: (a: ArmAngles) => (a.s !== 1 ? `rotate(${a.f}deg) scale(${a.s})` : `rotate(${a.f}deg)`),
  h: (a: ArmAngles) => `rotate(${a.h}deg)`,
  p: (a: ArmAngles) => `rotate(${r2(-(a.u + a.f + a.h))}deg)`,
};

const bodyT = (b: [number, number]) => `translate(0px,${b[1]}px) rotate(${b[0]}deg)`;
const headT = (h: [number, number, number]) => `translate(${h[1]}px,${h[2]}px) rotate(${h[0]}deg)`;

/** Every part key carries the full transform so missing values hold their previous value. */
function partFrames(solved: SolvedKey[], id: string) {
  let last: Required<PartKey> = { x: 0, y: 0, r: 0, s: 1, o: 1 };
  return solved.map((k) => {
    const p = k.parts[id];
    last = { ...last, ...(p ?? {}) };
    if (k.at === 0 || k.at === 1) {
      // the cycle starts and ends at rest unless the key says otherwise
      last = { x: 0, y: 0, r: 0, s: 1, o: 1, ...(p ?? {}) };
    }
    return { at: k.at, ease: k.ease, t: `translate(${last.x}px,${last.y}px) rotate(${last.r}deg) scale(${last.s})`, o: String(last.o) };
  });
}

/** The faces a gesture brings: their ids (a gesture's own face is `g-<gesture>`, `g-<gesture>-2`). */
export function gestureFaces(fig: FigureDef, id: GestureId): { act?: [string, FaceDef]; then?: [number, string, FaceDef] } {
  const g = fig.gestures[id];
  const out: { act?: [string, FaceDef]; then?: [number, string, FaceDef] } = {};
  if (g.face) out.act = typeof g.face === 'string' ? [g.face, fig.expressions[g.face]] : [`g-${id}`, g.face];
  if (g.then) {
    const f = g.then[1];
    out.then = typeof f === 'string' ? [g.then[0], f, fig.expressions[f]] : [g.then[0], `g-${id}-2`, f];
  }
  return out;
}

/** The action window: from halfway into the first move to halfway out of the last. */
export function actionWindow(g: GestureDef): [number, number] {
  const k = g.keys;
  if (k.length < 3) return [0, 1];
  return [r2((k[0].at + k[1].at) / 2), r2((k[k.length - 2].at + k[k.length - 1].at) / 2)];
}

export interface PoseSnapshot {
  L: ArmAngles;
  R: ArmAngles;
  body: [number, number];
  head: [number, number, number];
}

/** The static transforms of one solved key, by joint class. */
export function snapshot(s: SolvedKey | PoseSnapshot): Record<string, string> {
  return {
    body: bodyT(s.body),
    head: headT(s.head),
    lu: armTransform.u(s.L),
    lf: armTransform.f(s.L),
    lh: armTransform.h(s.L),
    lhp: armTransform.p(s.L),
    ru: armTransform.u(s.R),
    rf: armTransform.f(s.R),
    rh: armTransform.h(s.R),
    rhp: armTransform.p(s.R),
  };
}

/**
 * The CSS for one figure: expression poses and faces, and every gesture's keyframes. Scoped by
 * the figure's class, so several figures share a page.
 */
/** The head's pose for a face: tilt about the head centre, then a nudge. */
export function headPose(f: FaceDef): string {
  return `rotate(${f.tilt ?? 0}deg) translate(${f.dx ?? 0}px,${f.dy ?? 0}px)`;
}

export function figureCss(fig: FigureDef, only?: { expression?: ExpressionId; gesture?: GestureId | null }): string {
  const root = `.tv--${fig.key}`;
  const out: string[] = [];
  // expressions: body language and which face is shown (all-faces mode) without a gesture
  const exprs = only ? [only.expression ?? 'neutre'] : (Object.keys(fig.expressions) as ExpressionId[]);
  for (const id of exprs) {
    const e = fig.expressions[id];
    const sel = `${root}.tv-e--${id}:not(.tv--acting)`;
    if (e.pose) {
      const s = solveKeys(fig, [{ ...e.pose, at: 0 }])[0];
      const snap = snapshot(s);
      for (const [j, t] of Object.entries(snap)) out.push(`${sel} .tv-j--${j}{transform:${t}}`);
    }
    for (const side of ['L', 'R'] as Side[]) {
      const shape = e.hands?.[side];
      if (shape) out.push(`${sel} .tv-hand--${side}-rest{opacity:0}`, `${sel} .tv-hand--${side}-${shape}{opacity:1}`);
    }
    for (const prop of e.show ?? []) out.push(`${sel} .tv-show--${prop}{opacity:1}`);
    for (const side of e.front ?? []) out.push(`${sel} .tv-back--${side}{opacity:0}`, `${sel} .tv-front--${side}{opacity:1}`);
    out.push(`${root}.tv--all.tv-e--${id} .tv-face--${id}{display:inline;opacity:1}`);
    out.push(`${root}.tv-e--${id} .tv-hp{transform:${headPose(e)}}`);
  }
  const gestures = only ? (only.gesture ? [only.gesture] : []) : (Object.keys(fig.gestures) as GestureId[]);
  for (const id of gestures) out.push(gestureCss(fig, id, only?.expression));
  return out.join('\n');
}

function mergeIntervals(ivs: Array<[number, number]>): Array<[number, number]> {
  const sorted = [...ivs].sort((a, b) => a[0] - b[0]);
  const out: Array<[number, number]> = [];
  for (const iv of sorted) {
    const last = out[out.length - 1];
    if (last && iv[0] <= last[1] + EPS) last[1] = Math.max(last[1], iv[1]);
    else out.push([iv[0], iv[1]]);
  }
  return out;
}

/** Opacity 1 inside the intervals, 0 outside, with near-instant edges. */
function intervalsTrack(ivs: Array<[number, number]>): Track {
  const frames: Track['frames'] = [];
  const inside = (t: number) => ivs.some(([a, b]) => t >= a && t <= b);
  frames.push({ at: 0, value: inside(0) ? '1' : '0' });
  for (const [a, b] of ivs) {
    if (a > 0) frames.push({ at: a - EPS, value: '0' }, { at: a, value: '1' });
    if (b < 1) frames.push({ at: b, value: '1' }, { at: b + EPS, value: '0' });
  }
  frames.push({ at: 1, value: inside(1) ? '1' : '0' });
  return { frames: frames.filter((f) => f.at >= 0 && f.at <= 1).sort((x, y) => x.at - y.at) };
}

export function gestureCss(fig: FigureDef, id: GestureId, forBase?: ExpressionId): string {
  const g = fig.gestures[id];
  const root = `.tv--${fig.key}.tv-g--${id}`;
  const name = (t: string) => `tv-${fig.key}-${id}-${t}`;
  const solved = solveKeys(fig, g.keys);
  const peak = solved[g.peak] ?? solved[0];
  const css: string[] = [];
  const run = (sel: string, anim: string) => {
    css.push(`${root} ${sel}{animation:${anim} ${g.seconds}s linear 1 both}`);
    css.push(`${root}.tv--loop ${sel}{animation-iteration-count:infinite}`);
  };
  const still: string[] = [];
  const track = (joint: string, frames: Array<{ at: number; value: string; ease?: string }>, peakValue: string) => {
    css.push(keyframes(name(joint), { frames }));
    run(`.tv-j--${joint}`, name(joint));
    still.push(`.tv-j--${joint}{animation:none;transform:${peakValue}}`);
  };
  const snapPeak = snapshot(peak);
  track('body', solved.map((s) => ({ at: s.at, ease: s.ease, value: bodyT(s.body) })), snapPeak.body);
  track('head', solved.map((s) => ({ at: s.at, ease: s.ease, value: headT(s.head) })), snapPeak.head);
  for (const side of ['L', 'R'] as Side[]) {
    const l = side.toLowerCase();
    const fr = armFrames(fig, g.keys, side);
    track(`${l}u`, fr.map((s) => ({ at: s.at, ease: s.ease, value: armTransform.u(s.a) })), snapPeak[`${l}u`]);
    track(`${l}f`, fr.map((s) => ({ at: s.at, ease: s.ease, value: armTransform.f(s.a) })), snapPeak[`${l}f`]);
    track(`${l}h`, fr.map((s) => ({ at: s.at, ease: s.ease, value: armTransform.h(s.a) })), snapPeak[`${l}h`]);
    track(`${l}hp`, fr.map((s) => ({ at: s.at, ease: s.ease, value: armTransform.p(s.a) })), snapPeak[`${l}hp`]);
  }
  const partIds = new Set<string>();
  g.keys.forEach((k) => Object.keys(k.parts ?? {}).forEach((p) => partIds.add(p)));
  for (const p of Array.from(partIds)) {
    const frames = partFrames(solved, p);
    const pk = frames[g.peak] ?? frames[0];
    css.push(keyframes(name(`p-${p}`), { frames: frames.map((f) => ({ at: f.at, ease: f.ease, value: f.t })) }));
    css.push(keyframes(name(`po-${p}`), { frames: frames.map((f) => ({ at: f.at, ease: f.ease, value: f.o })) }, 'opacity'));
    css.push(`${root} .tv-p--${p}{animation:${name(`p-${p}`)} ${g.seconds}s linear 1 both}`);
    css.push(`${root}.tv--loop .tv-p--${p}{animation-iteration-count:infinite}`);
    css.push(`${root} .tv-po--${p}{animation:${name(`po-${p}`)} ${g.seconds}s linear 1 both}`);
    css.push(`${root}.tv--loop .tv-po--${p}{animation-iteration-count:infinite}`);
    still.push(`.tv-p--${p}{animation:none;transform:${pk.t}}`, `.tv-po--${p}{animation:none;opacity:${pk.o}}`);
  }
  // windows: hand shapes, props, faces
  const win = actionWindow(g);
  const peakAt = solved[g.peak]?.at ?? 0.5;
  const windowed = (sel: string, from: number, to: number, inside: boolean, tag: string) => {
    css.push(keyframes(name(tag), windowTrack(from, to, inside), 'opacity'));
    css.push(`${root} ${sel}{animation:${name(tag)} ${g.seconds}s linear 1 both}`);
    css.push(`${root}.tv--loop ${sel}{animation-iteration-count:infinite}`);
    const visibleAtPeak = peakAt >= from && peakAt <= to ? inside : !inside;
    still.push(`${sel}{animation:none;opacity:${visibleAtPeak ? 1 : 0}}`);
  };
  for (const side of ['L', 'R'] as Side[]) {
    const shape = g.hands?.[side];
    const w = sideWindow(g, side) ?? win;
    if (shape) {
      windowed(`.tv-hand--${side}-rest`, w[0], w[1], false, `${side}-rest`);
      windowed(`.tv-hand--${side}-${shape}`, w[0], w[1], true, `${side}-${shape}`);
    }
    if (g.front?.includes(side)) {
      windowed(`.tv-back--${side}`, w[0], w[1], false, `back-${side}`);
      windowed(`.tv-front--${side}`, w[0], w[1], true, `front-${side}`);
    }
  }
  for (const [prop, w] of Object.entries(g.show ?? {})) {
    const [a, b] = w === true ? win : w;
    windowed(`.tv-show--${prop}`, a, b, true, `show-${prop}`);
  }
  for (const [prop, w] of Object.entries(g.hide ?? {})) {
    const [a, b] = w === true ? win : w;
    windowed(`.tv-rest--${prop}`, a, b, false, `hide-${prop}`);
  }
  const gf = gestureFaces(fig, id);
  if (gf.act) {
    // which face shows when: the figure's own face outside the action window, the gesture's
    // face (then its second face) inside it. Written for every possible own face, so the
    // all-faces mode (a canvas switching faces by class) and a single render share it.
    const [w0, w1] = win;
    const actId = gf.act[0];
    const then = gf.then;
    for (const base of forBase ? [forBase] : EXPRESSIONS) {
      const vis: Record<string, Array<[number, number]>> = {};
      const add = (f: string, a: number, b: number) => {
        if (b > a) (vis[f] ??= []).push([a, b]);
      };
      add(base, 0, w0);
      add(base, w1, 1);
      if (then) {
        add(actId, w0, then[0]);
        add(then[1], then[0], w1);
      } else {
        add(actId, w0, w1);
      }
      for (const [f, ivs] of Object.entries(vis)) {
        const merged = mergeIntervals(ivs);
        const sel = `${root}.tv-e--${base} .tv-face--${f}`;
        const atPeak = merged.some(([a, b]) => peakAt >= a && peakAt <= b);
        if (merged.length === 1 && merged[0][0] <= 0 && merged[0][1] >= 1) {
          css.push(`${sel}{display:inline;animation:none;opacity:1}`);
          continue;
        }
        const tag = `vis-${merged.map(([a, b]) => `${Math.round(a * 1000)}-${Math.round(b * 1000)}`).join('-')}`;
        if (!css.some((c) => c.startsWith(`@keyframes ${name(tag)}{`))) {
          css.push(keyframes(name(tag), intervalsTrack(merged), 'opacity'));
        }
        css.push(`${sel}{display:inline;animation:${name(tag)} ${g.seconds}s linear 1 both}`);
        css.push(`${root}.tv--loop.tv-e--${base} .tv-face--${f}{animation-iteration-count:infinite}`);
        css.push(`${root}.tv--still.tv-e--${base} .tv-face--${f}{animation:none;opacity:${atPeak ? 1 : 0}}`);
        css.push(`@media (prefers-reduced-motion: reduce){${sel}{animation:none;opacity:${atPeak ? 1 : 0}}}`);
      }
    }
  }
  const stillSel = (s: string) => `${root}.tv--still ${s}`;
  const reduced = (s: string) => `${root} ${s}`;
  css.push(still.map((s) => stillSel(s)).join('\n'));
  css.push(`@media (prefers-reduced-motion: reduce){${still.map((s) => reduced(s)).join('\n')}}`);
  return css.join('\n');
}
