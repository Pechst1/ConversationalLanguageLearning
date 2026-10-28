/**
 * Le Quartier · the tailor's kit: the pieces every person is built from.
 *
 * A person is a neck, a trunk, two sleeves, two hands, two legs and two shoes, each a loft or a
 * tube round the bones of `rig.ts`, then what they wear over it and what they carry. The pieces
 * here know where the joints are and which bones each vertex follows (a sleeve bends at the
 * elbow, a skirt follows the thighs a little at its hem); a person's own file (`people.ts`) says
 * how wide, how long and in which ink.
 *
 * Line ids: the print draws a line wherever two neighbouring pieces have different ids, so a
 * person keeps eight of their own (32 to 39, which the quarter's own pieces skip) and gives
 * touching pieces different ones: the face and the hair, the sleeve and the hand, the shirt and
 * the apron.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import type { Hex } from '../palette';

import type { HeadShape } from './head';
import type { BoneName, Joints, Side } from './rig';
import { B, sx } from './rig';
import type { Bind, BindAt, Ink, Ring, Sculptor } from './sculpt';
import { between, smooth } from './sculpt';

/** A person's eight line ids. */
export const PLATE = {
  /** the face and the head */
  skin: 32,
  /** hands, ears, the neck: skin that meets the face or the sleeves */
  skin2: 33,
  hair: 34,
  /** the outer layer of the upper body */
  top: 35,
  /** what shows under it or over it (a shirt front, an apron, a scarf, a tie) */
  under: 36,
  /** trousers, a skirt */
  bottom: 37,
  shoes: 38,
  /** what they carry */
  prop: 39,
} as const;

export const FIRST_ID = 32;
export const LAST_ID = 39;

export function ink(color: Hex, id: number): Ink {
  return { color, id };
}

/** Everything a piece needs to know about the person it is cut for. */
export interface Build {
  S: Sculptor;
  J: Joints;
  head: HeadShape;
  /** the middle of the head, bind pose */
  hc: Vector3;
}

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

export function bone(name: BoneName): number {
  return B[name];
}

const sideBone = (side: Side, l: BoneName, r: BoneName) => (side === 'L' ? B[l] : B[r]);

/* ---- which bones a vertex follows ---------------------------------------------------------- */

/** The trunk: hips, spine and chest in bands, the shoulders' corners a little on the collarbones. */
export function torsoBind(J: Joints): BindAt {
  const ys = J.spine.y;
  const yc = J.chest.y;
  const yn = J.shoulderY;
  return (p) => {
    const y = p.y;
    if (y < ys - 0.05) return B.hips;
    if (y < ys + 0.05) return between(B.hips, B.spine, smooth(ys - 0.05, ys + 0.05, y));
    if (y < yc - 0.06) return B.spine;
    if (y < yc + 0.06) return between(B.spine, B.chest, smooth(yc - 0.06, yc + 0.06, y));
    const w = smooth(J.clav.L.x, J.shoulder.L.x, Math.abs(p.x)) * smooth(yc, yn, y) * 0.7;
    return w > 0.01 ? between(B.chest, p.x > 0 ? B.clavL : B.clavR, w) : B.chest;
  };
}

/** The trunk below the waist only: the hips, blending into the thighs low down (a coat's skirt). */
export function skirtBind(J: Joints, follow = 0.6): BindAt {
  const top = J.hips.y + 0.04;
  const hem = J.knee.L.y;
  return (p) => {
    const w = smooth(top, hem, p.y) * smooth(0.0, 0.07, Math.abs(p.x)) * follow;
    return w > 0.01 ? between(B.hips, p.x > 0 ? B.thighL : B.thighR, w) : B.hips;
  };
}

/** An arm: the collarbone at the top of the sleeve, the bend shared across the elbow, the hand past the wrist. */
export function armBind(J: Joints, side: Side, hand = true): BindAt {
  const S0 = J.shoulder[side];
  const E = J.elbow[side];
  const W = J.wrist[side];
  const clav = sideBone(side, 'clavL', 'clavR');
  const arm = sideBone(side, 'armL', 'armR');
  const fore = sideBone(side, 'foreL', 'foreR');
  const hb = sideBone(side, 'handL', 'handR');
  const ue = E.clone().sub(S0);
  const lu = ue.length();
  ue.normalize();
  const fw = W.clone().sub(E);
  const lf = fw.length();
  fw.normalize();
  const t = new Vector3();
  return (p) => {
    const a = t.copy(p).sub(S0).dot(ue);
    const b = t.copy(p).sub(E).dot(fw);
    if (hand && b > lf + 0.004) return between(fore, hb, smooth(lf + 0.004, lf + 0.03, b));
    if (a < 0.04) return between(clav, arm, smooth(-0.06, 0.04, a));
    const s = a < lu ? a - lu : b;
    return between(arm, fore, smooth(-0.035, 0.035, s));
  };
}

/** A leg: into the hips at the top, the bend shared across the knee, the foot below the ankle. */
export function legBind(J: Joints, side: Side, foot = false): BindAt {
  const H = J.hip[side];
  const K = J.knee[side];
  const A = J.ankle[side];
  const thigh = sideBone(side, 'thighL', 'thighR');
  const shin = sideBone(side, 'shinL', 'shinR');
  const fb = sideBone(side, 'footL', 'footR');
  return (p) => {
    const y = p.y;
    if (y > H.y - 0.03) return between(B.hips, thigh, smooth(H.y + 0.05, H.y - 0.05, y));
    if (y > K.y + 0.045) return thigh;
    if (y > K.y - 0.045) return between(thigh, shin, smooth(K.y + 0.045, K.y - 0.045, y));
    if (!foot || y > A.y + 0.01) return shin;
    return between(shin, fb, smooth(A.y + 0.01, A.y - 0.03, y));
  };
}

/** The neck: from the chest, through the neck bone, into the head. */
export function neckBind(J: Joints): BindAt {
  const n0 = J.neck.y;
  const h0 = J.skull.y;
  return (p) => {
    const y = p.y;
    if (y < n0 - 0.01) return B.chest;
    if (y < n0 + 0.02) return between(B.chest, B.neck, smooth(n0 - 0.01, n0 + 0.02, y));
    if (y < h0 - 0.015) return B.neck;
    return between(B.neck, B.head, smooth(h0 - 0.015, h0 + 0.02, y));
  };
}

/* ---- pieces -------------------------------------------------------------------------------- */

/** A ring of a trunk: its height, half-widths, and how it bulges. */
export interface Band {
  y: number;
  rx: number;
  rz: number;
  /** the ring's centre, forward of the spine */
  z?: number;
  front?: number;
  back?: number;
  square?: number;
}

/** A trunk (a shirt, a jumper, a coat) through bands from the bottom up. */
export function trunk(b: Build, bands: Band[], k: Ink, opts: { seg?: number; capStart?: boolean | number; capEnd?: boolean | number; bind?: BindAt; gap?: [number, number] } = {}) {
  const bind = opts.bind ?? torsoBind(b.J);
  const rings: Ring[] = bands.map((r) => ({ c: v(0, r.y, r.z ?? 0), rx: r.rx, rz: r.rz, front: r.front, back: r.back, square: r.square, bind }));
  b.S.loft(rings, k, { seg: opts.seg ?? 24, capStart: opts.capStart ?? true, capEnd: opts.capEnd ?? true, gap: opts.gap });
}

/** The neck, a little wider where it meets the shoulders. */
export function neck(b: Build, k: Ink, r: number, opts: { z?: number; top?: number; seg?: number } = {}) {
  const J = b.J;
  const z = opts.z ?? J.neck.z;
  const y0 = J.shoulderY - 0.04;
  const y1 = opts.top ?? J.skull.y + 0.03;
  const bind = neckBind(J);
  const rings: Ring[] = [
    { c: v(0, y0, z - 0.004), rx: r * 1.25, rz: r * 1.12, bind },
    { c: v(0, J.shoulderY + 0.005, z), rx: r * 1.06, rz: r, bind },
    { c: v(0, (J.shoulderY + y1) / 2, z + 0.003), rx: r, rz: r * 0.94, bind },
    { c: v(0, y1, z + 0.008), rx: r * 0.98, rz: r * 0.92, bind },
  ];
  b.S.loft(rings, k, { seg: opts.seg ?? 14, capStart: true, capEnd: true });
}

/** Points along an arm in the bind pose: 0 the shoulder, 1 the elbow, 2 the wrist, 2.5 the palm. */
export function armAt(J: Joints, side: Side, f: number): Vector3 {
  const S0 = J.shoulder[side];
  const E = J.elbow[side];
  const W = J.wrist[side];
  if (f <= 1) return S0.clone().lerp(E, f);
  if (f <= 2) return E.clone().lerp(W, f - 1);
  return W.clone().lerp(J.palm[side], (f - 2) * 2);
}

/**
 * A sleeve (or a bare arm) from `from` to `to` along the arm (0 shoulder, 1 elbow, 2 wrist), with
 * a radius at each station. A sleeve from the shoulder starts with a rounded cap over the joint.
 */
export function sleeve(b: Build, side: Side, k: Ink, stations: Array<[number, number] | [number, number, number]>, opts: { capStart?: boolean | number; capEnd?: boolean | number; hand?: boolean; seg?: number; lift?: number } = {}) {
  const J = b.J;
  const path: Vector3[] = [];
  const radii: Array<[number, number]> = [];
  for (const st of stations) {
    const [f, r, rz] = st;
    const p = armAt(J, side, f);
    // the top of the sleeve sits over the joint, a little up and in
    if (f <= 0.001) p.add(v(-sx(side) * (opts.lift ?? 0.012), opts.lift ?? 0.012, 0));
    path.push(p);
    radii.push([r, rz ?? r]);
  }
  const seg = opts.seg ?? 14;
  b.S.tube(path, radii, k, armBind(J, side, opts.hand ?? false), {
    seg,
    caps: false,
    up: v(0, 0, 1),
  });
  // the tube's own caps are flat; a sleeve wants a dome over the shoulder and a closed cuff
  if (opts.capStart !== false && stations[0][0] <= 0.001) {
    const top = path[0];
    b.S.ball(top, v(radii[0][0] * 1.02, radii[0][0] * 0.9, radii[0][1] * 1.02), k, armBind(J, side, false), { seg, rings: Math.round(seg / 2) });
  }
  if (opts.capEnd) {
    const end = path[path.length - 1];
    const r = radii[radii.length - 1];
    b.S.ball(end, v(r[0] * 0.98, Math.min(r[0], r[1]) * 0.35, r[1] * 0.98), k, armBind(J, side, opts.hand ?? false), { seg, rings: Math.max(3, Math.round((seg * 2) / 7)) });
  }
}

/** A cuff or a rolled sleeve: a short fat ring round the arm at `f`. */
export function cuff(b: Build, side: Side, k: Ink, f: number, r: number, len: number) {
  const J = b.J;
  const c = armAt(J, side, f);
  const dir = armAt(J, side, f + 0.05).sub(armAt(J, side, f - 0.05)).normalize();
  const a = c.clone().addScaledVector(dir, -len / 2);
  const e = c.clone().addScaledVector(dir, len / 2);
  b.S.tube([a, c, e], [[r * 0.94, r * 0.94], [r, r], [r * 0.94, r * 0.94]], k, armBind(J, side, false), { seg: 14, caps: true, up: v(0, 0, 1) });
}

/**
 * A hand: a soft mitten with its thumb, hanging from the wrist, palm toward the thigh. The drawn
 * troupe's hands are round, so these are round too: a palm, the fingers closed into one curve.
 * `seg` sets how round (12; fewer for the people of the street).
 */
export function hand(b: Build, side: Side, k: Ink, size = 1, opts: { curl?: number; seg?: number } = {}) {
  const J = b.J;
  const W = J.wrist[side];
  const P = J.palm[side];
  const down = P.clone().sub(W).normalize();
  const s = sx(side);
  const bind = sideBone(side, 'handL', 'handR');
  const len = J.spec.hand * size;
  const q = new Quaternion().setFromUnitVectors(v(0, -1, 0), down);
  // the inward side of the hand (toward the thigh) is the palm
  const inward = v(-s, 0, 0);
  const curl = opts.curl ?? 0.5;
  const seg = opts.seg ?? 12;
  // the wrist, so the hand never floats free of the sleeve
  b.S.ball(W.clone().addScaledVector(down, len * 0.06), v(0.02 * size, 0.024 * size, 0.026 * size), k, bind, { seg: seg - 2, rings: Math.round((seg - 2) / 2), rot: q });
  // the palm
  const palm = W.clone().addScaledVector(down, len * 0.36);
  b.S.ball(palm, v(0.024 * size, len * 0.32, 0.037 * size), k, bind, { seg, rings: Math.round((seg * 2) / 3), rot: q });
  // the fingers, closed into one rounded mass, curling toward the palm
  const tips = W.clone().addScaledVector(down, len * 0.7).addScaledVector(inward, 0.009 * curl * size);
  const qc = q.clone().multiply(new Quaternion().setFromAxisAngle(v(0, 0, 1), -s * 0.35 * curl));
  b.S.ball(tips, v(0.021 * size, len * 0.27, 0.034 * size), k, bind, { seg, rings: Math.round((seg * 7) / 12), rot: qc });
  // the thumb: on the front edge, angled down and in
  const thumbBase = W.clone().addScaledVector(down, len * 0.2).add(v(-s * 0.004 * size, 0, 0.028 * size));
  const thumbTip = thumbBase.clone().addScaledVector(down, len * 0.34).add(v(-s * 0.014 * size, 0, 0.008 * size));
  b.S.tube([thumbBase, thumbBase.clone().lerp(thumbTip, 0.55), thumbTip], [[0.0135 * size, 0.0135 * size], [0.0125 * size, 0.0125 * size], [0.011 * size, 0.011 * size]], k, bind, { seg: Math.round((seg * 2) / 3), caps: 0.008 * size, up: v(0, 0, 1) });
}

/** A trouser leg (or a bare leg, or a stocking) from the hip to just above the ankle. */
export function leg(b: Build, side: Side, k: Ink, radii: { top: number; thigh: number; knee: number; calf: number; hem: number }, opts: { hemY?: number; seg?: number; flare?: number } = {}) {
  const J = b.J;
  const H = J.hip[side];
  const K = J.knee[side];
  const A = J.ankle[side];
  const hemY = opts.hemY ?? A.y + 0.035;
  const s = sx(side);
  const at = (y: number, xin = 0) => {
    // straight from the hip through the knee to the ankle
    const p = y > K.y ? K.clone().lerp(H, (y - K.y) / (H.y - K.y)) : A.clone().lerp(K, (y - A.y) / (K.y - A.y));
    p.x -= s * xin;
    return p;
  };
  // the top tucks in under the trunk (or the pelvis), so only the leg shows below it
  const path = [at(H.y + 0.04, 0.03), at(H.y - 0.05, 0.006), at((H.y + K.y) / 2), at(K.y), at((K.y + A.y) / 2 + 0.03), at(hemY + 0.03), at(hemY)];
  const r = [radii.top * 0.85, radii.top, (radii.thigh + radii.knee) / 2 + 0.006, radii.knee, radii.calf, radii.hem * 0.98, radii.hem];
  b.S.tube(path, r.map((x) => [x, x * 0.96] as [number, number]), k, legBind(J, side), { seg: opts.seg ?? 16, caps: true, up: v(0, 0, 1) });
}

/**
 * The hips in the trousers' ink, from the crotch to the waist, for tops that stop at the waist:
 * the legs hang from inside it.
 */
export function pelvis(b: Build, k: Ink, spec: { waist: number; rx: number; rz: number; seat?: number; seg?: number }) {
  const J = b.J;
  const hip = J.hips.y;
  const w = J.spec.hips + spec.rx * 0.5;
  trunk(b, [
    { y: hip - 0.085, rx: w * 0.62, rz: spec.rz * 0.6 },
    { y: hip - 0.05, rx: w * 0.98, rz: spec.rz * 0.9, back: spec.seat ?? 0.01 },
    { y: hip + 0.02, rx: w, rz: spec.rz, back: spec.seat ?? 0.012 },
    { y: spec.waist, rx: spec.rx, rz: spec.rz * 0.94 },
  ], k, { capStart: 0.02, capEnd: true, seg: spec.seg ?? 22 });
}

/** A shoe, built along the foot: a heel, an instep, a rounded toe, flat on the ground. */
export function shoe(b: Build, side: Side, k: Ink, spec: { width?: number; height?: number; toe?: number; heel?: number; sole?: Ink; seg?: number } = {}) {
  const J = b.J;
  const A = J.ankle[side];
  const foot = J.spec.foot;
  const w = spec.width ?? 0.045;
  const h = spec.height ?? 0.075;
  const bind = sideBone(side, 'footL', 'footR');
  const z0 = A.z - foot * 0.26;
  const z1 = A.z + foot * 0.74;
  const x = A.x;
  // stations along the foot: [share of the length, half-width, height, raised toe]
  const st: Array<[number, number, number]> = [
    [0, w * 0.7, h * 0.55],
    [0.08, w * 0.92, h * 0.9],
    [0.3, w * 0.95, h * 1.0],
    [0.55, w * 1.0, h * 0.72],
    [0.78, w * 1.04, h * 0.56],
    [0.93, w * 0.9, h * 0.46],
    [1, w * 0.55, h * 0.3],
  ];
  const across = v(-1, 0, 0);
  const rings: Ring[] = st.map(([f, rx, hh]) => ({
    c: v(x, hh / 2, z0 + (z1 - z0) * f),
    rx,
    rz: hh / 2,
    axis: v(0, 0, 1),
    across,
    square: 2.8,
    bind,
  }));
  b.S.loft(rings, k, { seg: spec.seg ?? 14, capStart: 0.012, capEnd: 0.012 });
  if (spec.sole) {
    const sole: Ring[] = [
      { c: v(x, 0.008, z0 - 0.004), rx: w * 0.72, rz: 0.009, axis: v(0, 0, 1), across, square: 3, bind },
      { c: v(x, 0.008, z0 + (z1 - z0) * 0.5), rx: w * 1.04, rz: 0.009, axis: v(0, 0, 1), across, square: 3, bind },
      { c: v(x, 0.008, z1 + 0.004), rx: w * 0.6, rz: 0.009, axis: v(0, 0, 1), across, square: 3, bind },
    ];
    b.S.loft(sole, spec.sole, { seg: 12, capStart: true, capEnd: true });
  }
}

/** A skirt (or a coat's skirt, or an apron's lower half) from the waist to its hem. */
export function skirt(b: Build, k: Ink, spec: { top: number; hem: number; rxTop: number; rzTop: number; rxHem: number; rzHem: number; z?: number; gap?: [number, number]; follow?: number; front?: number; back?: number; seg?: number; capTop?: boolean }) {
  const bind = skirtBind(b.J, spec.follow ?? 0.6);
  const n = 5;
  const rings: Ring[] = [];
  for (let i = 0; i <= n; i++) {
    const f = i / n;
    const y = spec.top + (spec.hem - spec.top) * f;
    // a little fuller over the hips, then straight
    const ease = Math.sin(f * Math.PI * 0.5);
    rings.push({
      c: v(0, y, (spec.z ?? 0) + (spec.front ?? 0) * f * 0.5),
      rx: spec.rxTop + (spec.rxHem - spec.rxTop) * ease,
      rz: spec.rzTop + (spec.rzHem - spec.rzTop) * ease,
      bind,
    });
  }
  rings.reverse();
  b.S.loft(rings, k, { seg: spec.seg ?? 24, capStart: false, capEnd: spec.capTop ?? true, gap: spec.gap });
}

/** A flat piece laid on the body (a lapel, an apron's bib, a pocket), bent round it. */
export function patch(b: Build, outline: Array<[number, number]>, at: Vector3, k: Ink, bind: BindAt, opts: { depth?: number; bend?: number; rot?: Quaternion } = {}) {
  const m = new Matrix4().compose(at, opts.rot ?? new Quaternion(), v(1, 1, 1));
  b.S.slab(outline, opts.depth ?? 0.006, m, k, bind, { bend: opts.bend });
}

/** A button. */
export function button(b: Build, at: Vector3, r: number, k: Ink, bind: Bind) {
  b.S.ball(at, v(r, r, r * 0.45), k, bind, { seg: 8, rings: 4, flat: true });
}

/** A rounded outline: a rectangle with its corners cut (for cards, pockets, folders). */
export function rounded(w: number, h: number, r: number): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  const corner = (cx: number, cy: number, a0: number) => {
    for (let i = 0; i <= 3; i++) {
      const a = a0 + (i / 3) * (Math.PI / 2);
      out.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
  };
  corner(w / 2 - r, h / 2 - r, 0);
  corner(-w / 2 + r, h / 2 - r, Math.PI / 2);
  corner(-w / 2 + r, -h / 2 + r, Math.PI);
  corner(w / 2 - r, -h / 2 + r, Math.PI * 1.5);
  return out;
}

/** A turn about an axis, for placing props. */
export function turn(x: number, y: number, z: number): Quaternion {
  return new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), x).multiply(new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), y)).multiply(new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), z));
}

/** The trunk's surface at a height: its band, interpolated. */
export function bandAt(bands: Band[], y: number): Band {
  if (y <= bands[0].y) return bands[0];
  for (let i = 0; i + 1 < bands.length; i++) {
    const a = bands[i];
    const c = bands[i + 1];
    if (y <= c.y) {
      const t = (y - a.y) / (c.y - a.y);
      const l = (p: number | undefined, q: number | undefined, d = 0) => (p ?? d) + ((q ?? d) - (p ?? d)) * t;
      return { y, rx: l(a.rx, c.rx), rz: l(a.rz, c.rz), z: l(a.z, c.z), front: l(a.front, c.front), back: l(a.back, c.back), square: l(a.square, c.square, 2) };
    }
  }
  return bands[bands.length - 1];
}

/** How far forward the trunk's surface is at (x, y): for laying things on its front. */
export function frontZ(bands: Band[], x: number, y: number): number {
  const b = bandAt(bands, y);
  const n = b.square ?? 2;
  const u = Math.min(0.999, Math.abs(x) / b.rx);
  // the superellipse's front at this x, and the bulge, which fades toward the sides
  const zf = b.rz * Math.pow(1 - Math.pow(u, n), 1 / n);
  const c = zf / b.rz;
  return (b.z ?? 0) + zf + (b.front ?? 0) * c * c;
}

/**
 * A flat piece laid on the trunk's front: its outline in (x, y) metres, lifted `lift` off the
 * surface. `rings` stands rings between its middle and its edge on the surface too, so a wide
 * piece (a shirt's V, a lapel) follows the chest's curve instead of cutting into it.
 */
export function onFront(b: Build, bands: Band[], outline: Array<[number, number]>, k: Ink, opts: { lift?: number; depth?: number; bind?: BindAt; rings?: number } = {}) {
  // stand each point on the surface, then build a thin shell between the two faces
  const lift = opts.lift ?? 0.003;
  const depth = opts.depth ?? 0.005;
  const R = Math.max(1, Math.round(opts.rings ?? 1));
  const n = outline.length;
  const cx = outline.reduce((s, p) => s + p[0], 0) / n;
  const cy = outline.reduce((s, p) => s + p[1], 0) / n;
  const centre = new Vector3(cx, cy, frontZ(bands, cx, cy) + lift + depth * 0.5);
  const all: Vector3[] = [centre];
  for (let r = 1; r <= R; r++) {
    const f = r / R;
    for (const [x0, y0] of outline) {
      const x = r === R ? x0 : cx + (x0 - cx) * f;
      const y = r === R ? y0 : cy + (y0 - cy) * f;
      all.push(new Vector3(x, y, frontZ(bands, x, y) + lift + depth * 0.5 * (1 - f)));
    }
  }
  const pts = all.slice(1 + (R - 1) * n);
  const backC = centre.clone().add(new Vector3(0, 0, -depth));
  all.push(backC, ...pts.map((p) => p.clone().add(new Vector3(0, 0, -depth))));
  const tris: Array<[number, number, number]> = [];
  const fb = 1 + R * n;
  const edge = 1 + (R - 1) * n;
  // which way round the outline goes decides the winding
  let area = 0;
  for (let i = 0; i < n; i++) {
    const p = outline[i];
    const q = outline[(i + 1) % n];
    area += p[0] * q[1] - q[0] * p[1];
  }
  const ccw = area > 0;
  for (let i = 0; i < n; i++) {
    const i1 = (i + 1) % n;
    if (ccw) tris.push([0, 1 + i, 1 + i1]);
    else tris.push([0, 1 + i1, 1 + i]);
    for (let r = 1; r < R; r++) {
      const ia = 1 + (r - 1) * n;
      const oa = 1 + r * n;
      if (ccw) tris.push([ia + i, oa + i, oa + i1], [ia + i, oa + i1, ia + i1]);
      else tris.push([ia + i, oa + i1, oa + i], [ia + i, ia + i1, oa + i1]);
    }
    const a = edge + i;
    const c = edge + i1;
    const ba = fb + 1 + i;
    const bc = fb + 1 + i1;
    if (ccw) tris.push([fb, bc, ba]);
    else tris.push([fb, ba, bc]);
    // the rim
    if (ccw) tris.push([a, ba, bc], [a, bc, c]);
    else tris.push([a, bc, ba], [a, c, bc]);
  }
  b.S.mesh(all, tris, k, opts.bind ?? torsoBind(b.J), { flat: true });
}
