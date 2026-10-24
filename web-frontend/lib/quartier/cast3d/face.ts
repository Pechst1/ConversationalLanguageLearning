/**
 * Le Quartier · faces printed onto the heads.
 *
 * A face in the round is the drawn troupe's own face: the same eyes, brows and mouths the rigs
 * and the troupe vivante compute (`rigValues`, `faceValues`), painted onto a small canvas and
 * printed onto the front of the head through a straight projection, so a head seen face-on shows
 * exactly the drawing. The canvas is an atlas of six cells for the expression of the moment: its
 * own mouth, the four mouths a line is spoken with (a, e, o, m) and a blink. A new expression
 * repaints the six cells (a few dozen paths); talking and blinking only choose a cell.
 *
 * Each cell is filled with the skin first, so the head's own ink and the print meet without a
 * seam, and the print fades out round the sides of the head before it could reach the back.
 */
import { CanvasTexture, LinearFilter, LinearMipmapLinearFilter, NoColorSpace, Vector2 } from 'three';

import type { EyeState, EyeValues, RigDef, RigMood, RigProps } from '@/components/cast/rig-kit';
import { INK, ellipse, rigValues } from '@/components/cast/rig-kit';
import type { ExpressionId, FigureDef, FxKind, MouthValues, Pt } from '@/components/cast/vivant/kit';
import { faceValues } from '@/components/cast/vivant/kit';

/** The six cells of a face's atlas, in order. */
export const CELLS = ['own', 'a', 'e', 'o', 'm', 'blink'] as const;
export type Cell = (typeof CELLS)[number];
const COLS = 3;
const ROWS = 2;
/** a cell's share of the atlas, in texture coordinates */
export const CELL_SCALE = new Vector2(1 / COLS, 1 / ROWS);

/** A mark painted on the face: a path, filled, stroked or both, in the head frame. */
export interface Mark {
  d: string;
  fill?: string;
  stroke?: string;
  width?: number;
  opacity?: number;
}

/** An eye as the print sees it: the rigs' eye, with the vivant's extra pieces when it has them. */
export interface PrintEye extends EyeValues {
  lower?: string;
  lowerLine?: string;
  spark?: string;
  blinks?: boolean;
  blinkLid?: string;
  blinkLine?: string;
}

/** One face, ready to paint. */
export interface FaceState {
  eL: PrintEye;
  eR: PrintEye;
  browL: string;
  browR: string;
  mouth: MouthValues;
  fx: FxKind[];
  /** the eyes' states, for marks that depend on them (Romy's lashes) */
  eyes: [string, string];
  /** paint the blink lids over the open eyes */
  blink: boolean;
  /** the expression it was made for */
  expression: string;
}

/** How the head sits for an expression: a tilt in degrees and a nudge, in head-frame units. */
export interface HeadPose {
  tilt: number;
  dx: number;
  dy: number;
}

/** Where a person's faces come from. */
export interface FaceSource {
  state(expression: string, mouth: string | null, blink: boolean): FaceState;
  pose(expression: string): HeadPose;
}

/** How a person's face is inked: the drawn troupe's colours and line weights, kept. */
export interface FaceLook {
  skin: string;
  brow: string;
  browWidth: number;
  lidLine: number;
  arcLine: number;
  /** a coloured iris (Romy's blue) */
  iris?: string;
  /** lashes over these eye states (Romy) */
  lash?: { states: string[]; path: (centre: Pt, side: -1 | 1) => string; at: [Pt, Pt] };
  /** a wet shine over the lower white for these expressions (Lila moved) */
  glassy?: string[];
  /** the mouth frame's place in the head frame: translate x, y, then scale */
  mouth: [number, number, number] | ((s: FaceState) => [number, number, number]);
  /** the drawn nose, printed over the modelled one */
  nose?: Mark;
  /** marks under the features (cheeks, freckles, lines, a beard) and over them (a moustache) */
  under?: Mark[] | ((s: FaceState) => Mark[]);
  over?: Mark[] | ((s: FaceState) => Mark[]);
  /** anchors for the drawn effects (blush, tears, sweat), in the head frame */
  fx: { cheekL: Pt; cheekR: Pt; temple: Pt; eyeL: Pt; eyeR: Pt };
  /** the square of the head frame the print covers: centre x, y and half its side */
  frame: [number, number, number];
}

/* ---- sources ------------------------------------------------------------------------------ */

/** The troupe vivante's ten faces. `own` swaps in a figure's own mouths (Gus's indignation). */
export function vivantFace(fig: FigureDef, own?: (m: MouthValues) => MouthValues): FaceSource {
  const exprOf = (e: string) => fig.expressions[e as ExpressionId] ?? fig.expressions.neutre;
  return {
    state(expression, mouth, blink) {
      const def = exprOf(expression);
      const v = faceValues(fig, { ...def, talk: false, mouth: mouth ?? def.mouth });
      const m = own ? own(v.mouths[0]) : v.mouths[0];
      return { eL: v.eL, eR: v.eR, browL: v.browL, browR: v.browR, mouth: m, fx: def.fx ?? [], eyes: def.eyes, blink, expression };
    },
    pose(expression) {
      const d = exprOf(expression);
      return { tilt: d.tilt ?? 0, dx: d.dx ?? 0, dy: d.dy ?? 0 };
    },
  };
}

/** The ten expressions in a rig's five moods, for the people drawn only as rigs. */
export const MOOD_OF: Record<string, RigMood> = {
  neutre: 'neutre',
  joie: 'ravie',
  malice: 'ravie',
  fier: 'ravie',
  amour: 'ravie',
  surprise: 'surprise',
  panique: 'surprise',
  fache: 'fachee',
  emu: 'emue',
  fatigue: 'neutre',
};

const RIG_EYES: Record<RigMood, [EyeState, EyeState]> = {
  neutre: ['open', 'open'],
  ravie: ['happy', 'happy'],
  surprise: ['wide', 'wide'],
  fachee: ['cross', 'cross'],
  emue: ['sad', 'sad'],
};

export function rigFace(def: RigDef, variant?: string): FaceSource {
  return {
    state(expression, mouth, blink) {
      const mood = MOOD_OF[expression] ?? 'neutre';
      const v = rigValues(def, { mood, mouth: (mouth ?? 'auto') as RigProps['mouth'], blink, variant });
      const m: MouthValues = { key: v.mouth ?? 'rest', d: v.mouthD, fill: v.mouthFill, teeth: v.teethD, tongue: v.tongueD, line: '' };
      const eyes = def.eyes?.[mood] ?? RIG_EYES[mood];
      // the rig closes its own eyes for a blink, so the print paints no lid over them
      return { eL: v.eL, eR: v.eR, browL: v.browL, browR: v.browR, mouth: m, fx: [], eyes, blink: false, expression };
    },
    pose(expression) {
      const mood = MOOD_OF[expression] ?? 'neutre';
      return { tilt: def.tilt?.[mood] ?? 0, dx: 0, dy: 0 };
    },
  };
}

/* ---- painting ----------------------------------------------------------------------------- */

const STAR_DROP = 'M0,-7 C2.6,-2.6 4.6,0.4 4.6,2.8 A4.6,4.6 0 1 1 -4.6,2.8 C-4.6,0.4 -2.6,-2.6 0,-7 Z';
const VEIN = 'M-5,-1.6 Q-1.6,-1.6 -1.6,-5 M1.6,-5 Q1.6,-1.6 5,-1.6 M5,1.6 Q1.6,1.6 1.6,5 M-1.6,5 Q-1.6,1.6 -5,1.6';

type Ctx = CanvasRenderingContext2D;

function path(ctx: Ctx, d: string | undefined, fill?: string, stroke?: string, width = 1, opacity = 1) {
  if (!d) return;
  const p = new Path2D(d);
  ctx.globalAlpha = opacity;
  if (fill) {
    ctx.fillStyle = fill;
    ctx.fill(p);
  }
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.stroke(p);
  }
  ctx.globalAlpha = 1;
}

function marks(ctx: Ctx, list: Mark[] | ((s: FaceState) => Mark[]) | undefined, s: FaceState) {
  if (!list) return;
  const ms = typeof list === 'function' ? list(s) : list;
  for (const m of ms) path(ctx, m.d, m.fill, m.stroke, m.width ?? 1, m.opacity ?? 1);
}

function eye(ctx: Ctx, look: FaceLook, e: PrintEye, state: string, side: -1 | 1, s: FaceState, centre: Pt) {
  const open = e.sD !== 'none';
  if (open) {
    path(ctx, e.sclera, '#ffffff');
    if (look.iris) path(ctx, e.iris, look.iris);
    path(ctx, e.pupil, INK);
    path(ctx, e.glint, '#ffffff');
    path(ctx, e.spark, '#ffffff');
    if (look.glassy && look.glassy.indexOf(s.expression) >= 0) {
      const [x, y] = centre;
      const [rx, ry] = eyeRadii(e);
      path(ctx, `M${x - rx * 0.86},${y + ry * 0.3} Q${x},${y + ry * 1.2} ${x + rx * 0.86},${y + ry * 0.3} Q${x},${y + ry * 0.78} ${x - rx * 0.86},${y + ry * 0.3} Z`, '#bcd6f0', undefined, 1, 0.9);
    }
  }
  path(ctx, e.lid, look.skin);
  path(ctx, e.lidLine, undefined, INK, look.lidLine);
  if (e.lower) {
    path(ctx, e.lower, look.skin);
    path(ctx, e.lowerLine, undefined, INK, look.lidLine * 0.8);
  }
  if (open && look.lash && look.lash.states.indexOf(state) >= 0) {
    path(ctx, look.lash.path(look.lash.at[side < 0 ? 0 : 1], side), undefined, INK, 2.8);
  }
  path(ctx, e.arc, undefined, INK, look.arcLine);
  path(ctx, e.tear, '#1d3a8a');
  if (s.blink && e.blinks && e.blinkLid) {
    path(ctx, e.blinkLid, look.skin);
    path(ctx, e.blinkLine, undefined, INK, look.lidLine);
  }
}

/** an open eye's radii, read back from its white (an ellipse path `Mx-rx,y A rx,ry …`) */
function eyeRadii(e: PrintEye): [number, number] {
  const m = /A([\d.]+),([\d.]+)/.exec(e.sclera);
  return m ? [Number(m[1]), Number(m[2])] : [9, 10];
}

function fx(ctx: Ctx, look: FaceLook, kinds: FxKind[]) {
  const a = look.fx;
  const at = (p: Pt, draw: () => void) => {
    ctx.save();
    ctx.translate(p[0], p[1]);
    draw();
    ctx.restore();
  };
  for (const k of kinds) {
    if (k === 'blush') {
      for (const c of [a.cheekL, a.cheekR]) {
        at(c, () => {
          path(ctx, ellipse(0, 0, 9, 5), '#e5604a', undefined, 1, 0.42);
          path(ctx, 'M-5,2.4 L-2.6,-2.4 M-0.8,2.4 L1.6,-2.4 M3.4,2.4 L5.8,-2.4', undefined, '#d8321a', 1.3, 0.7);
        });
      }
    } else if (k === 'tears') {
      [a.eyeL, a.eyeR].forEach((c, i) => {
        const x = i ? 1 : -1;
        at(c, () => path(ctx, `M${x * 4},4 C${x * 7},12 ${x * 3},18 ${x * 6},26`, undefined, '#1d3a8a', 3.4, 0.85));
      });
    } else if (k === 'sweat') {
      at(a.temple, () => {
        path(ctx, STAR_DROP, '#5b86c8');
        path(ctx, ellipse(-1.4, 2.2, 1.2, 1.8), '#f8f3e8');
      });
    } else if (k === 'vein') {
      at(a.temple, () => path(ctx, VEIN, undefined, '#d8321a', 2.2));
    }
  }
}

/** Paint one face into the current transform (the head frame). */
export function paintFace(ctx: Ctx, look: FaceLook, s: FaceState, eyeCentres: [Pt, Pt]) {
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  marks(ctx, look.under, s);
  eye(ctx, look, s.eL, s.eyes[0], -1, s, eyeCentres[0]);
  eye(ctx, look, s.eR, s.eyes[1], 1, s, eyeCentres[1]);
  path(ctx, s.browL, undefined, look.brow, look.browWidth);
  path(ctx, s.browR, undefined, look.brow, look.browWidth);
  if (look.nose) path(ctx, look.nose.d, look.nose.fill, look.nose.stroke, look.nose.width ?? 1, look.nose.opacity ?? 1);
  const [tx, ty, k] = typeof look.mouth === 'function' ? look.mouth(s) : look.mouth;
  ctx.save();
  ctx.translate(tx, ty);
  ctx.scale(k, k);
  const m = s.mouth;
  path(ctx, m.d, m.fill);
  path(ctx, m.teeth, '#ffffff');
  path(ctx, m.tongue, '#d8321a');
  path(ctx, m.line, undefined, INK, 0.7);
  ctx.restore();
  marks(ctx, look.over, s);
  fx(ctx, look, s.fx);
}

/* ---- the atlas ---------------------------------------------------------------------------- */

const VISEME: Record<Cell, string | null> = { own: null, a: 'a', e: 'e', o: 'o', m: 'm', blink: null };

/**
 * A person's face print: the atlas canvas, its texture, and where each cell is. Without a DOM
 * (a test, a server render) it keeps the arithmetic and paints nothing.
 */
export class FacePrint {
  readonly texture: CanvasTexture | null;
  readonly cell: number;
  expression = '';
  private canvas: HTMLCanvasElement | null = null;
  private eyeCentres: [Pt, Pt];

  constructor(
    readonly look: FaceLook,
    readonly source: FaceSource,
    eyeCentres: [Pt, Pt],
    cell = 256,
  ) {
    this.cell = cell;
    this.eyeCentres = eyeCentres;
    if (typeof document !== 'undefined') {
      this.canvas = document.createElement('canvas');
      this.canvas.width = cell * COLS;
      this.canvas.height = cell * ROWS;
      const t = new CanvasTexture(this.canvas);
      t.colorSpace = NoColorSpace;
      t.minFilter = LinearMipmapLinearFilter;
      t.magFilter = LinearFilter;
      t.anisotropy = 4;
      this.texture = t;
    } else {
      this.texture = null;
    }
  }

  /** Repaint the six cells for an expression; nothing happens when it is already printed. */
  draw(expression: string) {
    if (expression === this.expression) return;
    this.expression = expression;
    const ctx = this.canvas?.getContext('2d');
    if (!ctx || !this.canvas) return;
    const c = this.cell;
    const [fx0, fy0, h] = this.look.frame;
    const scale = c / (2 * h);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = this.look.skin;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    CELLS.forEach((cell, i) => {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      ctx.save();
      ctx.beginPath();
      ctx.rect(col * c, row * c, c, c);
      ctx.clip();
      ctx.setTransform(scale, 0, 0, scale, col * c + c / 2 - fx0 * scale, row * c + c / 2 - fy0 * scale);
      const s = this.source.state(expression, VISEME[cell], cell === 'blink');
      paintFace(ctx, this.look, s, this.eyeCentres);
      ctx.restore();
    });
    if (this.texture) this.texture.needsUpdate = true;
  }

  /** A cell's corner in the atlas, in texture coordinates (the canvas is flipped on upload). */
  offset(cell: Cell, out = new Vector2()): Vector2 {
    const i = CELLS.indexOf(cell);
    const col = i % COLS;
    const row = Math.floor(i / COLS);
    return out.set(col / COLS, 1 - (row + 1) / ROWS);
  }

  /** Where a head-frame point (x right, y down) lands in a cell, from 0 to 1. */
  uv(x: number, y: number): [number, number] {
    const [fx0, fy0, h] = this.look.frame;
    return [(x - (fx0 - h)) / (2 * h), 1 - (y - (fy0 - h)) / (2 * h)];
  }

  dispose() {
    this.texture?.dispose();
  }
}
