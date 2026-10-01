/**
 * WP-116 · the drawn cast: what every rig shares.
 *
 * A rig is one character drawn in SVG (variant C, «rond», chosen 2026-10-01 on the
 * Claude Design canvas). Its body is fixed art in `rigs/<id>.tsx`; its face is
 * computed here from a small definition, so a mood, a mouth shape or a blink
 * changes a handful of path strings and nothing else.
 */
import type { ReactElement } from 'react';

export type RigMood = 'neutre' | 'ravie' | 'surprise' | 'fachee' | 'emue';
export type Viseme = 'rest' | 'a' | 'o' | 'e' | 'm' | 'f';
export type RigCrop = 'full' | 'bust' | 'head';
export type EyeState = 'open' | 'wry' | 'heavy' | 'level' | 'wide' | 'cross' | 'sad' | 'happy' | 'shut';
export type IdleKind = 'bob' | 'bounce' | 'sway' | 'nod';

export const RIG_MOODS: readonly RigMood[] = ['neutre', 'ravie', 'surprise', 'fachee', 'emue'];
export const VISEMES: readonly Viseme[] = ['rest', 'a', 'o', 'e', 'm', 'f'];

/** viewBox as [x, y, width, height]. */
export type Box = [number, number, number, number];
/** A brow: start, control, end of one quadratic curve. */
export type Brow = [number, number, number, number, number, number];

export interface EyeParams {
  rx: number;
  ry: number;
  /** pupil radius */
  pr: number;
  /** resting gaze offset */
  dx?: number;
  dy?: number;
  /** draw a coloured iris with a small pupil (Romy) */
  iris?: boolean;
  /** strong emotions bring a sideways gaze back to centre (Lila) */
  centreOnEmotion?: boolean;
  /** tears from both eyes when moved (Marin cries at adverts) */
  bothTears?: boolean;
}

export interface RigProps {
  mood: RigMood;
  mouth: Viseme | 'auto';
  blink: boolean;
  hold?: string;
  variant?: string;
}

export interface EyeValues {
  sD: string;
  sclera: string;
  iris: string;
  pupil: string;
  glint: string;
  lid: string;
  lidLine: string;
  arc: string;
  tear: string;
}

export interface RigValues {
  headT: string;
  eL: EyeValues;
  eR: EyeValues;
  browL: string;
  browR: string;
  mouthD: string;
  mouthFill: string;
  teethD: string;
  tongueD: string;
  extra: Record<string, string>;
}

export interface RigDef {
  id: string;
  name: string;
  head: [number, number];
  crops: Record<RigCrop, Box>;
  idle: { kind: IdleKind; seconds: number; amount: number };
  /** Toi is never seen face-on: no face values at all. */
  faceless?: boolean;
  tilt?: Partial<Record<RigMood, number>>;
  eyes?: Partial<Record<RigMood, [EyeState, EyeState]>>;
  brows?: Partial<Record<RigMood, [Brow, Brow]>>;
  eyeL?: [number, number];
  eyeR?: [number, number];
  eye?: EyeParams;
  mouths?: Partial<Record<RigMood, string>>;
  /** Romy's mouths are drawn symmetric */
  mouthSet?: 'base' | 'symmetric';
  /** fill for closed mouths; open mouths are always ink */
  lips?: string;
  holds?: readonly string[];
  variants?: readonly string[];
  extra?: (props: RigProps) => Record<string, string>;
  Art: (props: { v: RigValues }) => ReactElement;
}

export const INK = '#14110d';

export function ellipse(x: number, y: number, rx: number, ry: number): string {
  return `M${x - rx},${y} A${rx},${ry} 0 1 0 ${x + rx},${y} A${rx},${ry} 0 1 0 ${x - rx},${y} Z`;
}

export function circles(list: ReadonlyArray<readonly [number, number, number]>): string {
  return list.map((c) => ellipse(c[0], c[1], c[2], c[2])).join(' ');
}

function point(c: readonly [number, number, number], r: number, deg: number): string {
  const rad = (deg * Math.PI) / 180;
  return `${(c[0] + r * Math.cos(rad)).toFixed(2)},${(c[1] + r * Math.sin(rad)).toFixed(2)}`;
}

/** A short highlight arc on the upper-left of each curl. */
export function curlArcs(list: ReadonlyArray<readonly [number, number, number]>): string {
  return list
    .map((c) => {
      const r = c[2] * 0.62;
      return `M${point(c, r, 205)} A${r.toFixed(2)},${r.toFixed(2)} 0 0 1 ${point(c, r, 285)}`;
    })
    .join(' ');
}

/** A spiral-ish inner line for tight curls (Lila). */
export function curlSpirals(list: ReadonlyArray<readonly [number, number, number]>): string {
  return list
    .map((c) => {
      const r = c[2] * 0.55;
      return `M${point(c, r, 150)} A${r.toFixed(2)},${r.toFixed(2)} 0 1 1 ${point(c, r, 60)}`;
    })
    .join(' ');
}

export function dots(list: ReadonlyArray<readonly [number, number]>, r: number): string {
  return list.map((d) => ellipse(d[0], d[1], r, r)).join(' ');
}

function curve(b: Brow): string {
  return `M${b[0]},${b[1]} Q${b[2]},${b[3]} ${b[4]},${b[5]}`;
}

export function eye(centre: [number, number], params: EyeParams, state: EyeState, side: -1 | 1): EyeValues {
  const [cx, cy] = centre;
  const { rx, ry } = params;
  const hw = rx + 3.5;
  const top = cy - ry - 5;
  const left = side < 0;
  const emotional = state === 'wide' || state === 'cross' || state === 'sad';
  const o: EyeValues = {
    sD: 'inline',
    sclera: ellipse(cx, cy, rx, ry),
    iris: '',
    pupil: '',
    glint: '',
    lid: '',
    lidLine: '',
    arc: '',
    tear: '',
  };
  let px = cx + (params.centreOnEmotion && emotional ? 0 : params.dx || 0);
  let py = cy + (params.dy || 0) + 1;
  let r = params.pr;
  const lidAt = (yl: number, yr: number, bow: number) => {
    const mid = (yl + yr) / 2 - bow;
    o.lid = `M${cx - hw},${top} L${cx + hw},${top} L${cx + hw},${yr} Q${cx},${mid} ${cx - hw},${yl} Z`;
    const k = 3.5 / (2 * hw);
    o.lidLine = `M${cx - rx},${yl + (yr - yl) * k} Q${cx},${mid} ${cx + rx},${yr - (yr - yl) * k}`;
  };
  switch (state) {
    case 'wide':
      o.sclera = ellipse(cx, cy - 1, rx + 1, ry + 1.5);
      r -= 1;
      py = cy;
      break;
    case 'wry':
      lidAt(cy - ry * 0.28, cy - ry * 0.28, ry * 0.18);
      break;
    case 'heavy':
      lidAt(cy + ry * 0.02, cy + ry * 0.02, ry * 0.12);
      break;
    case 'level':
      lidAt(cy - ry * 0.34, cy - ry * 0.34, 0);
      break;
    case 'cross':
      lidAt(left ? cy - ry * 0.62 : cy + ry * 0.08, left ? cy + ry * 0.08 : cy - ry * 0.62, 0);
      break;
    case 'sad':
      lidAt(left ? cy - ry * 0.08 : cy - ry * 0.66, left ? cy - ry * 0.66 : cy - ry * 0.08, 0);
      py = cy + 3;
      if (left || params.bothTears) {
        const tx = cx + (left ? -1 : 1) * rx * 0.85;
        o.tear = `M${tx},${cy + ry * 0.7} c3,5 3,8 0,8 c-3,0 -3,-3 0,-8 Z`;
      }
      break;
    case 'happy':
      o.sD = 'none';
      o.arc = `M${cx - rx},${cy + 3} Q${cx},${cy - ry * 0.75} ${cx + rx},${cy + 3}`;
      break;
    case 'shut':
      o.sD = 'none';
      o.arc = `M${cx - rx},${cy + 1} Q${cx},${cy + ry * 0.5} ${cx + rx},${cy + 1}`;
      break;
    default:
      break;
  }
  if (params.iris) {
    o.iris = ellipse(px, py, r, r);
    o.pupil = ellipse(px, py, r * 0.48, r * 0.48);
  } else {
    o.pupil = ellipse(px, py, r, r);
  }
  o.glint = ellipse(px + r * 0.4, py - r * 0.38, r * 0.32, r * 0.32);
  return o;
}

/**
 * Mouth shapes in a small local frame centred near (2, 16); each rig places and
 * scales them. [shape, teeth, tongue]. The six visemes come first.
 */
const BASE_MOUTHS: Record<string, [string, string?, string?]> = {
  rest: ['M-6,15.5 Q2,16.5 9,14.5 Q2,18 -6,15.5 Z'],
  a: [
    'M-6,13.5 Q2,12 9,13 Q8,22.5 2,22.5 Q-4.5,22 -6,13.5 Z',
    'M-5,13.6 Q2,12.4 8,13.2 L7.8,14.8 Q2,14.2 -4.8,15.2 Z',
    'M-2.5,20 Q2,18 6,20 Q5,22.3 2,22.4 Q-1,22.3 -2.5,20 Z',
  ],
  o: ['M-1.2,16.5 A3.2,4.2 0 1 0 5.2,16.5 A3.2,4.2 0 1 0 -1.2,16.5 Z', '', 'M0,18.6 Q2,17.4 4,18.6 Q3.2,20.4 2,20.5 Q0.8,20.4 0,18.6 Z'],
  e: ['M-7.5,14 Q2,12.5 10.5,13.5 Q9,18.5 2,18.5 Q-5.5,18.2 -7.5,14 Z', 'M-6.5,14 Q2,12.9 9.5,13.8 L9.2,15.4 Q2,14.8 -6.2,15.6 Z'],
  m: ['M-6,15 Q2,14.2 9,14.4 L9,16.2 Q2,16.8 -6,16.6 Z'],
  f: ['M-6,14 Q2,13 9,13.5 L9,15.8 Q2,16.4 -6,16.2 Z', 'M-5.4,14 Q2,13.3 8.4,13.8 L8.4,15.2 Q2,15.4 -5.4,15.4 Z'],
  smirk: ['M-6,15 Q1,17.5 9,12.5 Q2,19.5 -6,15 Z'],
  smile: ['M-6,14.5 Q2,19 10,14 Q2,21.5 -6,14.5 Z'],
  soft: ['M-5,15 Q2,18 8,14.5 Q2,19.8 -5,15 Z'],
  grin: [
    'M-8,13 Q2,15 11,12 Q9,23 1,23 Q-6,22 -8,13 Z',
    'M-6.6,13.5 Q2,15.4 9.8,12.7 L9.3,15.2 Q2,17.4 -6,15.6 Z',
    'M-3,20.5 Q1,18 5,20.5 Q3,23 1,23 Q-1,23 -3,20.5 Z',
  ],
  frown: ['M-6,17.5 Q2,13.5 9,17 Q2,16 -6,17.5 Z'],
  wobble: ['M-6,17 Q-2,14.5 2,16.5 Q6,14.5 9,17 Q5,16.4 2,18 Q-2,16.4 -6,17 Z'],
  flat: ['M-6,15.6 L9,15.2 L9,16.6 L-6,17 Z'],
};

const SYMMETRIC_MOUTHS: Record<string, [string, string?, string?]> = {
  ...BASE_MOUTHS,
  rest: ['M-6,15.5 Q2,17 10,15.5 Q2,18.6 -6,15.5 Z'],
  a: [
    'M-6,13.5 Q2,12 10,13.5 Q8.5,22.5 2,22.5 Q-4.5,22.5 -6,13.5 Z',
    'M-5,13.6 Q2,12.4 9,13.6 L8.8,15 Q2,14.2 -4.8,15 Z',
    'M-2.5,20 Q2,18 6.5,20 Q5,22.3 2,22.4 Q-1,22.3 -2.5,20 Z',
  ],
  e: ['M-7.5,14 Q2,12.5 11.5,14 Q9.5,18.5 2,18.5 Q-5.5,18.5 -7.5,14 Z', 'M-6.5,14 Q2,12.9 10.5,14 L10.2,15.4 Q2,14.8 -6.2,15.4 Z'],
  m: ['M-6,15 Q2,14.2 10,15 L10,16.4 Q2,17 -6,16.4 Z'],
  f: ['M-6,14 Q2,13 10,14 L10,15.8 Q2,16.4 -6,15.8 Z', 'M-5.4,14 Q2,13.3 9.4,14 L9.4,15.2 Q2,15.4 -5.4,15.2 Z'],
  soft: ['M-5,15 Q2,18 9,15 Q2,20 -5,15 Z'],
  grin: [
    'M-8,13 Q2,15.5 12,13 Q10,23 2,23 Q-6,23 -8,13 Z',
    'M-6.6,13.5 Q2,15.8 10.6,13.5 L10.2,15.6 Q2,17.6 -6.2,15.8 Z',
    'M-2,20.6 Q2,18.2 6,20.6 Q4,23 2,23 Q0,23 -2,20.6 Z',
  ],
  frown: ['M-6,17.5 Q2,13.5 10,17.5 Q2,16 -6,17.5 Z'],
};

const DEFAULT_EYES: Record<RigMood, [EyeState, EyeState]> = {
  neutre: ['open', 'open'],
  ravie: ['happy', 'happy'],
  surprise: ['wide', 'wide'],
  fachee: ['cross', 'cross'],
  emue: ['sad', 'sad'],
};

const DEFAULT_MOUTHS: Record<RigMood, string> = {
  neutre: 'smile',
  ravie: 'grin',
  surprise: 'o',
  fachee: 'frown',
  emue: 'soft',
};

const NO_EYE: EyeValues = { sD: 'none', sclera: '', iris: '', pupil: '', glint: '', lid: '', lidLine: '', arc: '', tear: '' };

export function rigValues(def: RigDef, props: RigProps): RigValues {
  const extra = def.extra ? def.extra(props) : {};
  if (def.faceless || !def.eye || !def.eyeL || !def.eyeR || !def.brows) {
    return {
      headT: `translate(${def.head[0]} ${def.head[1]})`,
      eL: NO_EYE,
      eR: NO_EYE,
      browL: '',
      browR: '',
      mouthD: '',
      mouthFill: INK,
      teethD: '',
      tongueD: '',
      extra,
    };
  }
  const mood = props.mood;
  const states: [EyeState, EyeState] = props.blink ? ['shut', 'shut'] : (def.eyes?.[mood] ?? DEFAULT_EYES[mood]);
  const brows = def.brows[mood] ?? def.brows.neutre!;
  const key = props.mouth !== 'auto' ? props.mouth : (def.mouths?.[mood] ?? DEFAULT_MOUTHS[mood]);
  const set = def.mouthSet === 'symmetric' ? SYMMETRIC_MOUTHS : BASE_MOUTHS;
  const [shape, teeth = '', tongue = ''] = set[key] ?? set.rest;
  const open = Boolean(teeth) || key === 'o' || key === 'a';
  return {
    headT: `translate(${def.head[0]} ${def.head[1]}) rotate(${def.tilt?.[mood] ?? 0})`,
    eL: eye(def.eyeL, def.eye, states[0], -1),
    eR: eye(def.eyeR, def.eye, states[1], 1),
    browL: curve(brows[0]),
    browR: curve(brows[1]),
    mouthD: shape,
    mouthFill: open ? INK : (def.lips ?? INK),
    teethD: teeth,
    tongueD: tongue,
    extra,
  };
}
