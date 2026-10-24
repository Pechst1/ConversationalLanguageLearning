/**
 * Le Quartier · heads moulded from the drawings.
 *
 * A drawn head is a silhouette: the rig's skin outline, face-on. The head in the round keeps that
 * silhouette exactly, so the face print (which is the drawing, projected straight on) lands where
 * the drawing put it, and finds the depth a head has round it: a face a little flatter than a
 * ball, a skull that runs back further than the face runs forward, a jaw that narrows toward the
 * neck and a chin that comes forward. The nose is modelled on top, where the drawing puts it, so
 * it catches the light and throws the small shadow a print gives a nose.
 *
 * Hair is a cap moulded on the same head: it follows the skull, stands off it by its own
 * thickness (the drawing's hair stands out of the outline by that much), and stops along a
 * hairline traced round the head, folding into the skin there so its edge prints as one clean
 * line. Curls, tufts, buns and fringes are laid on the cap.
 *
 * The head frame is the drawings' own: x to the right, y down, in the rig's units. Head space is
 * the figure's: metres, y up, centred on the middle of the head.
 */
import { Quaternion, Vector3 } from 'three';

import type { Pt } from '@/components/cast/vivant/kit';

import type { BindAt, FaceProjection, FaceUv, Ink, Sculptor } from './sculpt';
import { smooth } from './sculpt';

const TAU = Math.PI * 2;

/* ---- reading a drawn outline -------------------------------------------------------------- */

/** An absolute SVG path (M L H V C Q Z) as polylines, curves cut into `steps` pieces. */
export function polylines(d: string, steps = 14): Pt[][] {
  const tokens = d.match(/[MLHVCQZ]|-?\d*\.?\d+(?:e-?\d+)?/gi) ?? [];
  const out: Pt[][] = [];
  let cur: Pt[] = [];
  let x = 0;
  let y = 0;
  let sx = 0;
  let sy = 0;
  let i = 0;
  let cmd = 'M';
  const num = () => Number(tokens[i++]);
  while (i < tokens.length) {
    if (/^[MLHVCQZ]$/i.test(tokens[i])) cmd = tokens[i++].toUpperCase();
    if (cmd === 'M') {
      if (cur.length) out.push(cur);
      x = num();
      y = num();
      sx = x;
      sy = y;
      cur = [[x, y]];
      cmd = 'L';
    } else if (cmd === 'L') {
      x = num();
      y = num();
      cur.push([x, y]);
    } else if (cmd === 'H') {
      x = num();
      cur.push([x, y]);
    } else if (cmd === 'V') {
      y = num();
      cur.push([x, y]);
    } else if (cmd === 'C') {
      const x1 = num();
      const y1 = num();
      const x2 = num();
      const y2 = num();
      const x3 = num();
      const y3 = num();
      for (let k = 1; k <= steps; k++) {
        const t = k / steps;
        const u = 1 - t;
        cur.push([u * u * u * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3, u * u * u * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3]);
      }
      x = x3;
      y = y3;
    } else if (cmd === 'Q') {
      const x1 = num();
      const y1 = num();
      const x2 = num();
      const y2 = num();
      for (let k = 1; k <= steps; k++) {
        const t = k / steps;
        const u = 1 - t;
        cur.push([u * u * x + 2 * u * t * x1 + t * t * x2, u * u * y + 2 * u * t * y1 + t * t * y2]);
      }
      x = x2;
      y = y2;
    } else if (cmd === 'Z') {
      cur.push([sx, sy]);
      x = sx;
      y = sy;
      out.push(cur);
      cur = [];
    } else {
      i++;
    }
  }
  if (cur.length) out.push(cur);
  return out;
}

/** Where a horizontal line crosses the outline: its leftmost and rightmost x, or null. */
export function spanAt(lines: Pt[][], y: number): [number, number] | null {
  let lo = Infinity;
  let hi = -Infinity;
  for (const pl of lines) {
    for (let k = 0; k + 1 < pl.length; k++) {
      const [x1, y1] = pl[k];
      const [x2, y2] = pl[k + 1];
      if ((y1 <= y && y2 >= y) || (y2 <= y && y1 >= y)) {
        const x = y1 === y2 ? Math.min(x1, x2) : x1 + ((y - y1) / (y2 - y1)) * (x2 - x1);
        const xb = y1 === y2 ? Math.max(x1, x2) : x;
        lo = Math.min(lo, x);
        hi = Math.max(hi, xb);
      }
    }
  }
  return lo <= hi ? [lo, hi] : null;
}

export function bounds(lines: Pt[][]): [number, number, number, number] {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const pl of lines) {
    for (const [x, y] of pl) {
      x0 = Math.min(x0, x);
      y0 = Math.min(y0, y);
      x1 = Math.max(x1, x);
      y1 = Math.max(y1, y);
    }
  }
  return [x0, y0, x1, y1];
}

/* ---- the head ----------------------------------------------------------------------------- */

export interface HeadDef {
  /** the drawn skin outline, face-on, in the head frame */
  outline: string;
  /** the drawn nose; its box places the modelled nose */
  nose: string;
  /** how far the nose stands out, as a share of its drawn width (0.75) */
  noseDepth?: number;
  /** the drawn ears: centre x, y and radii */
  ears?: Array<[number, number, number, number]>;
  /** depth of the skull behind the middle, as a share of the half-width (1.12) */
  back?: number;
  /** depth of the face in front of the middle, as a share of the half-width (0.9) */
  front?: number;
  /** how far the chin comes forward, in head-frame units (14) */
  chin?: number;
  /** how far round the head the print reaches before it fades: start and end, radians */
  wrap?: [number, number];
}

/** A head made from its drawing, at a height in metres (chin to crown). */
export class HeadShape {
  /** metres per head-frame unit */
  readonly s: number;
  /** the head frame's point at the middle of the head */
  readonly x0: number;
  readonly y0: number;
  readonly top: number;
  readonly bottom: number;
  /** the widest half-width, head-frame units */
  readonly wide: number;
  private table: number[] = [];
  private readonly rows = 96;
  private nose: [number, number, number, number];

  constructor(readonly def: HeadDef, readonly height: number) {
    const lines = polylines(def.outline);
    const [bx0, by0, bx1, by1] = bounds(lines);
    this.top = by0;
    this.bottom = by1;
    this.s = height / (by1 - by0);
    this.y0 = (by0 + by1) / 2;
    let wide = 0;
    let centre = (bx0 + bx1) / 2;
    for (let k = 0; k <= this.rows; k++) {
      const y = by0 + ((by1 - by0) * k) / this.rows;
      const span = spanAt(lines, y);
      const w = span ? (span[1] - span[0]) / 2 : 0;
      this.table.push(w);
      if (span && w > wide) {
        wide = w;
        centre = (span[0] + span[1]) / 2;
      }
    }
    this.wide = wide;
    this.x0 = centre;
    this.nose = bounds(polylines(def.nose));
  }

  /** Half the head's width at a head-frame height, in head-frame units. */
  width(y: number): number {
    const f = ((y - this.top) / (this.bottom - this.top)) * this.rows;
    if (f <= 0 || f >= this.rows) return 0;
    const k = Math.floor(f);
    const t = f - k;
    return this.table[k] * (1 - t) + this.table[k + 1] * t;
  }

  /** A head-frame point on the front plane, in head space (metres). */
  at(x: number, y: number, z = 0): Vector3 {
    return new Vector3((x - this.x0) * this.s, (this.y0 - y) * this.s, z);
  }

  /** The head-frame height of a latitude of the moulding sphere. */
  heightOf(lat: number): number {
    return this.y0 - (lat / (Math.PI / 2)) * ((this.bottom - this.top) / 2);
  }

  latOf(y: number): number {
    return ((this.y0 - y) / ((this.bottom - this.top) / 2)) * (Math.PI / 2);
  }

  /** The head's surface for a direction of the moulding sphere, in head space. */
  mould = (d: Vector3): Vector3 => {
    const lat = Math.asin(Math.max(-1, Math.min(1, d.y)));
    const t = lat / (Math.PI / 2);
    const y = this.heightOf(lat);
    const w = this.width(y);
    const phi = Math.abs(d.x) + Math.abs(d.z) < 1e-9 ? 0 : Math.atan2(d.x, d.z);
    const sp = Math.sin(phi);
    const cp = Math.cos(phi);
    const front = this.def.front ?? 0.9;
    const back = this.def.back ?? 1.12;
    // the skull runs back; the jaw narrows toward the neck
    const kBack = back + (0.56 - back) * smooth(-0.05, -0.55, t);
    // the chin comes forward
    const zc = (this.def.chin ?? 14) * smooth(-0.45, -1, t);
    // a face a little flatter than a ball, between the brows and the mouth
    const n = cp > 0 ? 2 + 0.55 * smooth(-0.75, -0.3, t) * (1 - smooth(0.35, 0.75, t)) : 2;
    const pw = 2 / n;
    const x = Math.sign(sp) * Math.pow(Math.abs(sp), pw) * w;
    const z = zc + Math.sign(cp) * Math.pow(Math.abs(cp), pw) * w * (cp > 0 ? front : kBack);
    return new Vector3(x * this.s, (this.y0 - y) * this.s, z * this.s);
  };

  /** The front of the face at a head-frame point: how far forward the surface is there (metres). */
  frontAt(x: number, y: number): number {
    const w = this.width(y);
    if (w <= 0) return 0;
    const u = Math.max(-0.999, Math.min(0.999, (x - this.x0) / w));
    // invert the mould along this height: the angle whose x is u
    const lat = this.latOf(y);
    const t = lat / (Math.PI / 2);
    const n = 2 + 0.55 * smooth(-0.75, -0.3, t) * (1 - smooth(0.35, 0.75, t));
    const pw = 2 / n;
    const sp = Math.sign(u) * Math.pow(Math.abs(u), 1 / pw);
    const cp = Math.sqrt(Math.max(0, 1 - sp * sp));
    const zc = (this.def.chin ?? 14) * smooth(-0.45, -1, t);
    return (zc + Math.pow(cp, pw) * w * (this.def.front ?? 0.9)) * this.s;
  }

  /**
   * The face print's projection: straight on, from the head frame square `frame` (centre x, y,
   * half side) to a cell's 0–1, fading out round the sides.
   */
  projection(frame: [number, number, number]): FaceProjection {
    const [fx, fy, h] = frame;
    const [a0, a1] = this.def.wrap ?? [1.62, 1.95];
    return (p: Vector3, d: Vector3): FaceUv => {
      const x = p.x / this.s + this.x0;
      const y = this.y0 - p.y / this.s;
      const phi = Math.abs(Math.atan2(d.x, d.z));
      const w = 1 - smooth(a0, a1, phi);
      return [(x - (fx - h)) / (2 * h), 1 - (y - (fy - h)) / (2 * h), w];
    };
  }

  /** The drawn nose's box: x0, y0, x1, y1. */
  get noseBox() {
    return this.nose;
  }
}

/* ---- the pieces of a head ----------------------------------------------------------------- */

/** The head itself, centred on `centre` (bind-pose metres), with its face print. */
export function sculptHead(S: Sculptor, head: HeadShape, centre: Vector3, frame: [number, number, number], ink: Ink, bind: BindAt) {
  S.facePrint(head.projection(frame));
  S.moulded(centre, head.mould, ink, bind, { seg: 36, rings: 26 });
  sculptNose(S, head, centre, ink, bind);
  S.facePrint(null);
}

/** The nose: a small loft from the bridge to the tip, standing out of the face where it is drawn. */
export function sculptNose(S: Sculptor, head: HeadShape, centre: Vector3, ink: Ink, bind: BindAt) {
  const [nx0, ny0, nx1, ny1] = head.noseBox;
  const cx = (nx0 + nx1) / 2;
  const hw = (nx1 - nx0) / 2;
  const depth = (head.def.noseDepth ?? 0.75) * hw * 2;
  const rows = 9;
  const seg = 12;
  const pts: Vector3[] = [];
  const tris: Array<[number, number, number]> = [];
  const tipAt = 0.78;
  for (let i = 0; i <= rows; i++) {
    const f = i / rows;
    const y = ny0 + (ny1 - ny0) * f;
    // the profile: a thin bridge swelling to the tip, then tucked under to the base
    const rise = f < tipAt ? Math.sin((f / tipAt) * Math.PI * 0.5) ** 1.4 : Math.cos(((f - tipAt) / (1 - tipAt)) * Math.PI * 0.5);
    const r = hw * (0.42 + 0.58 * (f < tipAt ? f / tipAt : 1)) * (f < tipAt ? 1 : 0.55 + 0.45 * rise);
    const out = depth * rise;
    const zf = head.frontAt(cx, y) / head.s;
    for (let j = 0; j < seg; j++) {
      const th = (TAU * j) / seg;
      const x = cx + Math.sin(th) * r;
      // the back half sinks into the face
      const z = zf - r * 0.9 + out * 0.55 + Math.cos(th) * (r * 0.9 + out * 0.45);
      pts.push(head.at(x, y, z * head.s).add(centre));
    }
  }
  const tip = head.at(cx, ny1, head.frontAt(cx, ny1)).add(centre);
  tip.z -= 0.002;
  pts.push(tip);
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < seg; j++) {
      const j1 = (j + 1) % seg;
      const a = i * seg + j;
      const b = i * seg + j1;
      const c = (i + 1) * seg + j1;
      const dd = (i + 1) * seg + j;
      // rings run down the face (-y); angles go from the front toward +x
      tris.push([a, dd, c], [a, c, b]);
    }
  }
  const last = rows * seg;
  const ci = pts.length - 1;
  for (let j = 0; j < seg; j++) tris.push([ci, last + ((j + 1) % seg), last + j]);
  S.mesh(pts, tris, ink, bind, { face: centre });
}

/** The ears, as the drawing puts them, turned a little forward. */
export function sculptEars(S: Sculptor, head: HeadShape, centre: Vector3, ink: Ink, bind: BindAt) {
  for (const [ex, ey, rx, ry] of head.def.ears ?? []) {
    const side = ex < head.x0 ? -1 : 1;
    const w = head.width(ey);
    const p = head.at(head.x0 + side * (w - rx * 0.3), ey, -w * 0.12 * head.s).add(centre);
    const rot = new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), side * 0.32);
    S.ball(p, new Vector3(rx * 0.32 * head.s, ry * head.s, rx * 0.95 * head.s), ink, bind, { seg: 12, rings: 8, rot });
  }
}

/* ---- hair --------------------------------------------------------------------------------- */

export interface CapSpec {
  /** where the hair stops at each angle round the head (0 the front, +PI/2 the figure's left): a head-frame height */
  edge: (theta: number) => number;
  /** how far the hair stands off the skull, metres, at an angle and a share of the way from the edge (0) to the crown (1) */
  thick: (theta: number, u: number) => number;
  ink: Ink;
  bind: BindAt;
  seg?: number;
  rows?: number;
}

/** The surface direction of the moulding sphere at a latitude and an angle. */
export function dirAt(lat: number, theta: number): Vector3 {
  return new Vector3(Math.cos(lat) * Math.sin(theta), Math.sin(lat), Math.cos(lat) * Math.cos(theta));
}

/** A point on the head, `off` metres out from the skull, in bind-pose space. */
export function onHead(head: HeadShape, centre: Vector3, lat: number, theta: number, off = 0): Vector3 {
  const p = head.mould(dirAt(lat, theta));
  const n = p.clone().normalize();
  return p.addScaledVector(n, off).add(centre);
}

/** A cap of hair moulded on the head, its edge folded into the skin. */
export function hairCap(S: Sculptor, head: HeadShape, centre: Vector3, spec: CapSpec) {
  const seg = spec.seg ?? 48;
  const rows = spec.rows ?? 16;
  const pts: Vector3[] = [];
  const tris: Array<[number, number, number]> = [];
  const crown = onHead(head, centre, Math.PI / 2, 0, spec.thick(0, 1));
  pts.push(crown);
  const edges: number[] = [];
  for (let j = 0; j < seg; j++) edges.push(head.latOf(spec.edge((TAU * j) / seg)));
  for (let i = 1; i <= rows + 2; i++) {
    for (let j = 0; j < seg; j++) {
      const th = (TAU * j) / seg;
      const f = Math.min(1, i / rows);
      const lat = Math.PI / 2 - (Math.PI / 2 - edges[j]) * f;
      const u = 1 - f;
      // past the edge: the fold into the skin, then under it
      const off = i <= rows ? spec.thick(th, u) : i === rows + 1 ? 0.0015 : -0.012;
      pts.push(onHead(head, centre, lat, th, off));
    }
  }
  for (let j = 0; j < seg; j++) tris.push([0, 1 + j, 1 + ((j + 1) % seg)]);
  for (let i = 0; i < rows + 1; i++) {
    for (let j = 0; j < seg; j++) {
      const j1 = (j + 1) % seg;
      const a = 1 + i * seg + j;
      const b = 1 + (i + 1) * seg + j;
      const c = 1 + (i + 1) * seg + j1;
      const d = 1 + i * seg + j1;
      tris.push([a, b, c], [a, c, d]);
    }
  }
  S.mesh(pts, tris, spec.ink, spec.bind);
}

/** A periodic curve through values at angles (radians), for hairlines: smooth, and closed round the head. */
export function round(points: Array<[number, number]>): (theta: number) => number {
  const ps = points.map(([a, v]) => [((a % TAU) + TAU) % TAU, v] as [number, number]).sort((p, q) => p[0] - q[0]);
  return (theta: number) => {
    const a = ((theta % TAU) + TAU) % TAU;
    let k = ps.length - 1;
    for (let i = 0; i < ps.length; i++) if (ps[i][0] <= a) k = i;
    const p0 = ps[(k - 1 + ps.length) % ps.length];
    const p1 = ps[k];
    const p2 = ps[(k + 1) % ps.length];
    const p3 = ps[(k + 2) % ps.length];
    let span = p2[0] - p1[0];
    if (span <= 0) span += TAU;
    let local = a - p1[0];
    if (local < 0) local += TAU;
    const t = local / span;
    // Catmull-Rom through the four neighbours
    const t2 = t * t;
    const t3 = t2 * t;
    return 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);
  };
}

/**
 * A flick of hair (a tuft, a curl over the brow, a swept lock): a flattened tube along `path`,
 * tapering through `widths`, its flat side across `up`.
 */
export function flick(S: Sculptor, path: Vector3[], widths: number[], k: Ink, bind: BindAt, opts: { flat?: number; up?: Vector3 } = {}) {
  const f = opts.flat ?? 0.5;
  S.tube(path, widths.map((w) => [w, w * f] as [number, number]), k, bind, { seg: 10, caps: widths[widths.length - 1] * 0.8 + 0.001, up: opts.up ?? new Vector3(0, 0, 1) });
}

/** Curls laid on the head: [angle, head-frame height, radius (metres), how far out]. */
export function curls(S: Sculptor, head: HeadShape, centre: Vector3, list: Array<[number, number, number, number]>, inks: Ink[], bind: BindAt) {
  list.forEach(([theta, y, r, out], i) => {
    const p = onHead(head, centre, head.latOf(y), theta, out);
    S.ball(p, r, inks[i % inks.length], bind, { seg: 10, rings: 6 });
  });
}

/** A long fall of hair (Romy's, Odile's bob): it hangs from the widest of the head, open at the front for the face. */
export interface FallSpec {
  /** head-frame height where it starts, under the cap */
  top: number;
  /** half the opening at the front, radians from the front */
  open: number;
  /** where it ends at each angle round the head (0 the front): a bind-pose height, metres */
  end: (theta: number) => number;
  /** how thick it is, metres, at an angle and a share of the way down */
  thick: (theta: number, f: number) => number;
  /** what it falls over below the head: half-widths across and through the body at a bind-pose height */
  body?: (y: number) => [number, number] | null;
  /** how far it stands off the head, metres (hair has body) */
  lift?: number;
  /** how far it spreads out by its ends, metres */
  flare?: number;
  /** how far each angle swings forward (+) or back by its end, metres (a lock over the shoulder) */
  sweep?: (theta: number) => number;
  ink: Ink;
  bind: BindAt;
  cols?: number;
  rows?: number;
}

export function hairFall(S: Sculptor, head: HeadShape, centre: Vector3, spec: FallSpec) {
  const cols = spec.cols ?? 40;
  const rows = spec.rows ?? 20;
  const a0 = spec.open;
  const a1 = TAU - spec.open;
  const yTop = centre.y + (head.y0 - spec.top) * head.s;
  const outer: Vector3[] = [];
  const inner: Vector3[] = [];
  for (let j = 0; j <= cols; j++) {
    const th = a0 + ((a1 - a0) * j) / cols;
    const u = new Vector3(Math.sin(th), 0, Math.cos(th));
    const yEnd = spec.end(th);
    const edge = smooth(0, 0.4, Math.min(th - a0, a1 - th));
    // the hang point, head space: it follows the head while the head widens, then falls straight
    let hang: Vector3 | null = null;
    const col: Vector3[] = [];
    for (let i = 0; i <= rows; i++) {
      const f = i / rows;
      const Y = yTop + (yEnd - yTop) * f;
      const yh = head.y0 - (Y - centre.y) / head.s;
      if (yh > head.top && yh < head.bottom) {
        const H = head.mould(dirAt(head.latOf(yh), th));
        if (!hang || H.x * u.x + H.z * u.z >= hang.x * u.x + hang.z * u.z) hang = new Vector3(H.x, 0, H.z);
      }
      const p = hang ? hang.clone() : new Vector3();
      const b = spec.body ? spec.body(Y) : null;
      if (b) {
        // clear the body: its ellipse along this angle, from the body's axis (x = 0, z = 0)
        const rb = 1 / Math.sqrt((u.x / b[0]) ** 2 + (u.z / b[1]) ** 2);
        const bx = rb * u.x - centre.x;
        const bz = rb * u.z - centre.z;
        if (bx * u.x + bz * u.z > p.x * u.x + p.z * u.z) {
          p.x = bx;
          p.z = bz;
        }
      }
      p.addScaledVector(u, (spec.flare ?? 0) * f * f);
      if (spec.sweep) p.z += spec.sweep(th) * f * f;
      p.y = Y - centre.y;
      col.push(p);
    }
    // soften the turn where the head gives way to the body
    for (let pass = 0; pass < 3; pass++) {
      for (let i = rows - 1; i >= 1; i--) {
        const q = col[i];
        q.x = (col[i - 1].x + 2 * q.x + col[i + 1].x) / 4;
        q.z = (col[i - 1].z + 2 * q.z + col[i + 1].z) / 4;
      }
    }
    for (let i = 0; i <= rows; i++) {
      const f = i / rows;
      const t = Math.max(0.004, spec.thick(th, f) * edge * smooth(0, 0.14, f) * (1 - 0.45 * smooth(0.75, 1, f)));
      const p = col[i];
      const lift = spec.lift ?? 0.002;
      inner.push(p.clone().addScaledVector(u, lift).add(centre));
      outer.push(p.clone().addScaledVector(u, lift + t).add(centre));
    }
  }
  const n = (cols + 1) * (rows + 1);
  const pts = outer.concat(inner);
  const tris: Array<[number, number, number]> = [];
  const at = (j: number, i: number) => j * (rows + 1) + i;
  for (let j = 0; j < cols; j++) {
    for (let i = 0; i < rows; i++) {
      const a = at(j, i);
      const b = at(j, i + 1);
      const c = at(j + 1, i + 1);
      const d = at(j + 1, i);
      tris.push([a, b, c], [a, c, d]);
      tris.push([n + a, n + c, n + b], [n + a, n + d, n + c]);
    }
  }
  // close it: the two front edges, the ends and the top
  for (let i = 0; i < rows; i++) {
    for (const j of [0, cols]) {
      const a = at(j, i);
      const b = at(j, i + 1);
      tris.push([a, n + a, n + b], [a, n + b, b]);
    }
  }
  for (let j = 0; j < cols; j++) {
    for (const i of [0, rows]) {
      const a = at(j, i);
      const d = at(j + 1, i);
      tris.push([a, d, n + d], [a, n + d, n + a]);
    }
  }
  S.mesh(pts, tris, spec.ink, spec.bind);
}
