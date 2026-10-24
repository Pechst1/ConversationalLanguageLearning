/**
 * Le Quartier · the sculptor: one person cut into one skinned buffer.
 *
 * The quarter's press (`geo.ts`) cuts static pieces into a single mesh; a person has to bend, so
 * this press writes the same marks (the ink, and the line id the print pass keys on) plus the
 * bones each vertex follows. Everything is built in the bind pose, standing at the origin and
 * facing +z, from a handful of shapes: lofts of rings (a torso, a sleeve, a trouser leg, a coat's
 * skirt), tubes along a path (a scarf, a curl, a cord), balls, slabs cut from a 2D outline (a
 * lapel, a card, an apron), and lathed props. Organic pieces are smooth-shaded, since the
 * three-band light turns a smooth form into the flat planes of a print; props stay faceted.
 *
 *   aInk        rgb the ink, a the line id (pieces that share it print as one shape)
 *   aFace       where the face print lands, and how much of it (the head only; 0 elsewhere)
 *   skinIndex   up to two bones a vertex follows
 *   skinWeight  and how much of each
 */
import { BufferAttribute, BufferGeometry, Matrix4, Quaternion, ShapeUtils, Vector2, Vector3 } from 'three';

import type { Hex } from '../palette';

/** The bones a vertex follows: one bone, or two with the second one's share. */
export type Bind = number | [number, number, number];
/** A bind that can depend on where the vertex is (bind-pose position, metres). */
export type BindAt = Bind | ((p: Vector3) => Bind);

/** Where a point lands on the face print (u, v) and how strongly the print shows there (w). */
export type FaceUv = [number, number, number];
/** The head's face projection: from a head-space point and its outward direction. */
export type FaceProjection = (p: Vector3, d: Vector3) => FaceUv | null;

export interface Ink {
  color: Hex;
  /** the line id, 0–63: the print pass draws a line between neighbours whose ids differ */
  id: number;
}

/** One cross-section of a loft. */
export interface Ring {
  /** centre */
  c: Vector3;
  /** half-widths across (the ring's x) and through it (its front, +z for an upright ring) */
  rx: number;
  rz: number;
  /** the loft's direction here (the ring's normal); +y by default */
  axis?: Vector3;
  /** the ring's "across" direction; world +x made perpendicular to the axis by default */
  across?: Vector3;
  bind: BindAt;
  /** 2 is an ellipse; higher is squarer (a jacket's shoulders, a box-like coat) */
  square?: number;
  /** pushes the front half out (a belly, a chest, a coat's lapels), in metres at the front */
  front?: number;
  /** pushes the back half out (a hunch, a bun), in metres at the back */
  back?: number;
  /** a radius multiplier by angle; theta 0 is the front (+z), PI/2 the +x side */
  shape?: (theta: number) => number;
  /** moves the whole ring along its front direction (a forward-leaning hem) */
  shift?: number;
}

export interface LoftOptions {
  /** points round each ring */
  seg?: number;
  /** close the first and last ring with a fan; a number domes the cap by that many metres */
  capStart?: boolean | number;
  capEnd?: boolean | number;
  /** faceted instead of smooth */
  flat?: boolean;
  /** leave the ring open between these angles (a coat's front opening), radians, front = 0 */
  gap?: [number, number];
}

const TAU = Math.PI * 2;
const tmp = new Vector3();
const tmp2 = new Vector3();

/** One primitive's vertices before they join the person. */
class Piece {
  pos: number[] = [];
  face: number[] = [];
  bind: Bind[] = [];
  idx: number[] = [];
  flat = false;
  vertex(p: Vector3, b: Bind, uv?: FaceUv): number {
    this.pos.push(p.x, p.y, p.z);
    this.face.push(uv ? uv[0] : 0, uv ? uv[1] : 0, uv ? uv[2] : 0);
    this.bind.push(b);
    return this.pos.length / 3 - 1;
  }
  tri(a: number, b: number, c: number) {
    this.idx.push(a, b, c);
  }
  quad(a: number, b: number, c: number, d: number) {
    this.idx.push(a, b, c, a, c, d);
  }
}

function faceAt(piece: Piece, i: number): FaceUv {
  return [piece.face[i * 3], piece.face[i * 3 + 1], piece.face[i * 3 + 2]];
}

function resolve(b: BindAt, p: Vector3): Bind {
  return typeof b === 'function' ? b(p) : b;
}

/** A blend of two binds by `t` (0 = a): only plain one-bone binds blend; otherwise a wins. */
export function between(a: number, b: number, t: number): Bind {
  if (t <= 0.001) return a;
  if (t >= 0.999) return b;
  return [a, b, t];
}

/** smoothstep, for weights across a joint */
export function smooth(e0: number, e1: number, x: number) {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}

export class Sculptor {
  private pieces: Array<{ piece: Piece; ink: Ink }> = [];
  private matrix = new Matrix4();
  private stack: Matrix4[] = [];
  /** the head's face print: a projection from head space to the print's square */
  private faceProject: FaceProjection | null = null;

  /** Build what follows inside a transform (props held at an angle, a mirrored earring). */
  push(m: Matrix4) {
    this.stack.push(this.matrix.clone());
    this.matrix.multiply(m);
  }

  pop() {
    const m = this.stack.pop();
    if (m) this.matrix.copy(m);
  }

  at(position: Vector3, rotation: Quaternion | null, draw: () => void, scale?: Vector3) {
    this.push(new Matrix4().compose(position, rotation ?? new Quaternion(), scale ?? new Vector3(1, 1, 1)));
    draw();
    this.pop();
  }

  /** Points of the head get face-print coordinates from this projection while it is set. */
  facePrint(project: FaceProjection | null) {
    this.faceProject = project;
  }

  private add(piece: Piece, ink: Ink) {
    // into the bind pose's space
    if (!this.isIdentity()) {
      const v = new Vector3();
      for (let i = 0; i < piece.pos.length; i += 3) {
        v.set(piece.pos[i], piece.pos[i + 1], piece.pos[i + 2]).applyMatrix4(this.matrix);
        piece.pos[i] = v.x;
        piece.pos[i + 1] = v.y;
        piece.pos[i + 2] = v.z;
      }
      if (this.matrix.determinant() < 0) {
        for (let i = 0; i < piece.idx.length; i += 3) {
          const t = piece.idx[i + 1];
          piece.idx[i + 1] = piece.idx[i + 2];
          piece.idx[i + 2] = t;
        }
      }
    }
    this.pieces.push({ piece, ink });
  }

  private isIdentity() {
    const e = this.matrix.elements;
    return e[0] === 1 && e[5] === 1 && e[10] === 1 && e[12] === 0 && e[13] === 0 && e[14] === 0 && e[1] === 0 && e[2] === 0 && e[4] === 0 && e[6] === 0 && e[8] === 0 && e[9] === 0;
  }

  /** Bind-pose position of a local point (for props that place pieces relative to each other). */
  world(p: Vector3) {
    return p.clone().applyMatrix4(this.matrix);
  }

  /* ---- shapes ------------------------------------------------------------------------------ */

  /**
   * A loft through rings: the workhorse (a torso, a limb, a skirt, a sleeve, a neck). Each ring
   * is a superellipse in the plane across its axis; consecutive rings are stitched with quads.
   */
  loft(rings: Ring[], ink: Ink, opts: LoftOptions = {}) {
    const seg = opts.seg ?? 16;
    const P = new Piece();
    P.flat = !!opts.flat;
    const gap = opts.gap;
    const cols = gap ? seg + 1 : seg;
    const rowStart: number[] = [];
    const centres: Vector3[] = [];
    for (let i = 0; i < rings.length; i++) {
      const r = rings[i];
      const axis = (r.axis ?? new Vector3(0, 1, 0)).clone().normalize();
      const across = (r.across ?? new Vector3(1, 0, 0)).clone();
      across.addScaledVector(axis, -across.dot(axis));
      if (across.lengthSq() < 1e-8) across.set(0, 0, 1).addScaledVector(axis, -axis.z);
      across.normalize();
      const fwd = new Vector3().crossVectors(across, axis).normalize();
      const pw = 2 / (r.square ?? 2);
      const c = r.c.clone().addScaledVector(fwd, r.shift ?? 0);
      centres.push(c);
      rowStart.push(P.pos.length / 3);
      for (let j = 0; j < cols; j++) {
        let th: number;
        if (gap) th = gap[1] + ((TAU - (gap[1] - gap[0])) * j) / seg;
        else th = (TAU * j) / seg;
        const s = Math.sin(th);
        const co = Math.cos(th);
        let x = Math.sign(s) * Math.pow(Math.abs(s), pw);
        let z = Math.sign(co) * Math.pow(Math.abs(co), pw);
        const k = r.shape ? r.shape(th) : 1;
        x *= r.rx * k;
        z *= r.rz * k;
        if (r.front && co > 0) z += r.front * co * co;
        if (r.back && co < 0) z -= r.back * co * co;
        tmp.copy(c).addScaledVector(across, x).addScaledVector(fwd, z);
        P.vertex(tmp, resolve(r.bind, tmp));
      }
    }
    for (let i = 0; i + 1 < rings.length; i++) {
      const a0 = rowStart[i];
      const b0 = rowStart[i + 1];
      const n = gap ? cols - 1 : cols;
      for (let j = 0; j < n; j++) {
        const j1 = gap ? j + 1 : (j + 1) % cols;
        // outward winding: rings go up the axis, angles go from the front toward +x
        P.quad(a0 + j, a0 + j1, b0 + j1, b0 + j);
      }
    }
    const cap = (ri: number, flip: boolean, dome: number) => {
      const r = rings[ri];
      const axis = (r.axis ?? new Vector3(0, 1, 0)).clone().normalize();
      const c = centres[ri].clone().addScaledVector(axis, flip ? -dome : dome);
      const ci = P.vertex(c, resolve(r.bind, c));
      const start = rowStart[ri];
      const n = gap ? cols - 1 : cols;
      for (let j = 0; j < n; j++) {
        const j1 = gap ? j + 1 : (j + 1) % cols;
        if (flip) P.tri(ci, start + j1, start + j);
        else P.tri(ci, start + j, start + j1);
      }
    };
    if (opts.capStart) cap(0, true, typeof opts.capStart === 'number' ? opts.capStart : 0);
    if (opts.capEnd) cap(rings.length - 1, false, typeof opts.capEnd === 'number' ? opts.capEnd : 0);
    this.add(P, ink);
  }

  /**
   * A tube along a path: points with a radius each (or two, across and through), sections kept
   * square to the path by a rotation-minimising frame. Curls, a scarf, a cord, a strap, a rim.
   */
  tube(
    path: Vector3[],
    radius: number | Array<number | [number, number]>,
    ink: Ink,
    bind: BindAt | Bind[],
    opts: { seg?: number; caps?: boolean | number; closed?: boolean; flat?: boolean; up?: Vector3; square?: number } = {},
  ) {
    const n = path.length;
    if (n < 2) return;
    const tangents: Vector3[] = [];
    for (let i = 0; i < n; i++) {
      const a = path[opts.closed ? (i - 1 + n) % n : Math.max(0, i - 1)];
      const b = path[opts.closed ? (i + 1) % n : Math.min(n - 1, i + 1)];
      tangents.push(b.clone().sub(a).normalize());
    }
    // the first frame: across is perpendicular to the tangent, as close to `up` x tangent as possible
    const up = (opts.up ?? new Vector3(0, 1, 0)).clone();
    let across = new Vector3().crossVectors(up, tangents[0]);
    if (across.lengthSq() < 1e-6) across = new Vector3().crossVectors(new Vector3(1, 0, 0), tangents[0]);
    across.normalize();
    const rings: Ring[] = [];
    for (let i = 0; i < n; i++) {
      if (i > 0) {
        // carry the frame along: rotate it by the turn between tangents
        const q = new Quaternion().setFromUnitVectors(tangents[i - 1], tangents[i]);
        across.applyQuaternion(q);
        across.addScaledVector(tangents[i], -across.dot(tangents[i])).normalize();
      }
      const rr = Array.isArray(radius) ? radius[Math.min(i, radius.length - 1)] : radius;
      const [rx, rz] = Array.isArray(rr) ? rr : [rr, rr];
      const b = Array.isArray(bind) ? (bind as Bind[])[Math.min(i, (bind as Bind[]).length - 1)] : bind;
      rings.push({ c: path[i], rx, rz, axis: tangents[i], across: across.clone(), bind: b as BindAt, square: opts.square });
    }
    if (opts.closed) rings.push({ ...rings[0] });
    const caps = opts.caps ?? false;
    this.loft(rings, ink, { seg: opts.seg ?? 8, capStart: opts.closed ? false : caps, capEnd: opts.closed ? false : caps, flat: opts.flat });
  }

  /**
   * An ellipsoid (a curl, a knuckle, the skull's back, a bun), smooth, from latitude rings.
   * `rot` turns it about its centre; `cut` keeps only the part above that height (-1 to 1) of
   * the unit sphere, for caps.
   */
  ball(c: Vector3, r: Vector3 | number, ink: Ink, bind: BindAt, opts: { seg?: number; rings?: number; rot?: Quaternion; cut?: number; flat?: boolean; shape?: (d: Vector3) => number } = {}) {
    const rv = typeof r === 'number' ? new Vector3(r, r, r) : r;
    const seg = opts.seg ?? 12;
    const rows = opts.rings ?? Math.max(4, Math.round(seg / 2));
    const P = new Piece();
    P.flat = !!opts.flat;
    const cut = opts.cut ?? -1;
    const lat0 = Math.asin(Math.max(-1, Math.min(1, cut)));
    const top = P.vertex(this.ballPoint(c, rv, new Vector3(0, 1, 0), opts), resolve(bind, this.ballPoint(c, rv, new Vector3(0, 1, 0), opts)));
    const rowsIdx: number[] = [];
    for (let i = 1; i <= rows; i++) {
      const lat = Math.PI / 2 - ((Math.PI / 2 - lat0) * i) / rows;
      rowsIdx.push(P.pos.length / 3);
      for (let j = 0; j < seg; j++) {
        const th = (TAU * j) / seg;
        const d = new Vector3(Math.cos(lat) * Math.sin(th), Math.sin(lat), Math.cos(lat) * Math.cos(th));
        const p = this.ballPoint(c, rv, d, opts);
        P.vertex(p, resolve(bind, p));
      }
    }
    for (let j = 0; j < seg; j++) P.tri(top, rowsIdx[0] + j, rowsIdx[0] + ((j + 1) % seg));
    for (let i = 0; i + 1 < rowsIdx.length; i++) {
      const a = rowsIdx[i];
      const b = rowsIdx[i + 1];
      for (let j = 0; j < seg; j++) {
        const j1 = (j + 1) % seg;
        P.quad(a + j, b + j, b + j1, a + j1);
      }
    }
    if (cut <= -1) {
      const bottomP = this.ballPoint(c, rv, new Vector3(0, -1, 0), opts);
      const bottom = P.vertex(bottomP, resolve(bind, bottomP));
      const last = rowsIdx[rowsIdx.length - 1];
      for (let j = 0; j < seg; j++) P.tri(bottom, last + ((j + 1) % seg), last + j);
    } else {
      // a flat floor under the cap
      const last = rowsIdx[rowsIdx.length - 1];
      const floorC = this.ballPoint(c, rv, new Vector3(0, cut, 0), { ...opts, shape: undefined });
      const fc = P.vertex(floorC, resolve(bind, floorC));
      for (let j = 0; j < seg; j++) P.tri(fc, last + ((j + 1) % seg), last + j);
    }
    this.add(P, ink);
  }

  private ballPoint(c: Vector3, r: Vector3, d: Vector3, opts: { rot?: Quaternion; shape?: (d: Vector3) => number }) {
    const k = opts.shape ? opts.shape(d) : 1;
    const p = new Vector3(d.x * r.x * k, d.y * r.y * k, d.z * r.z * k);
    if (opts.rot) p.applyQuaternion(opts.rot);
    return p.add(c);
  }

  /**
   * A slab cut from a 2D outline (x right, y up) and given `depth` through local z, centred on
   * z = 0, placed by `m`: a lapel, a pocket square, an index card, an apron's bib, a key's bit.
   * `bend` curves the slab round the local y axis by that radius (an apron round a belly).
   */
  slab(outline: Array<[number, number]>, depth: number, m: Matrix4, ink: Ink, bind: BindAt, opts: { bend?: number } = {}) {
    const P = new Piece();
    P.flat = true;
    const pts = outline.map(([x, y]) => new Vector2(x, y));
    if (ShapeUtils.isClockWise(pts)) pts.reverse();
    const tris = ShapeUtils.triangulateShape(pts, []);
    const place = (x: number, y: number, z: number) => {
      let px = x;
      let pz = z;
      if (opts.bend) {
        // wrap round a cylinder of radius `bend` whose axis is local y, behind the slab
        const a = x / opts.bend;
        px = Math.sin(a) * (opts.bend + z);
        pz = Math.cos(a) * (opts.bend + z) - opts.bend;
      }
      return new Vector3(px, y, pz).applyMatrix4(m);
    };
    const n = pts.length;
    const front: number[] = [];
    const back: number[] = [];
    for (let i = 0; i < n; i++) {
      const p = place(pts[i].x, pts[i].y, depth / 2);
      front.push(P.vertex(p, resolve(bind, p)));
    }
    for (let i = 0; i < n; i++) {
      const p = place(pts[i].x, pts[i].y, -depth / 2);
      back.push(P.vertex(p, resolve(bind, p)));
    }
    for (const t of tris) {
      P.tri(front[t[0]], front[t[1]], front[t[2]]);
      P.tri(back[t[0]], back[t[2]], back[t[1]]);
    }
    if (depth > 0) {
      // sides, each quad its own vertices so the edge stays crisp
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        const a = place(pts[i].x, pts[i].y, depth / 2);
        const b = place(pts[j].x, pts[j].y, depth / 2);
        const c = place(pts[j].x, pts[j].y, -depth / 2);
        const d = place(pts[i].x, pts[i].y, -depth / 2);
        const ia = P.vertex(a, resolve(bind, a));
        const ib = P.vertex(b, resolve(bind, b));
        const ic = P.vertex(c, resolve(bind, c));
        const id = P.vertex(d, resolve(bind, d));
        P.quad(ia, id, ic, ib);
      }
    }
    this.add(P, ink);
  }

  /** A box (a camera, a folder, a suitcase), faceted, centred on `c`, turned by `rot`. */
  box(c: Vector3, size: Vector3, ink: Ink, bind: BindAt, rot?: Quaternion) {
    const P = new Piece();
    P.flat = true;
    const h = size.clone().multiplyScalar(0.5);
    const corner = (sx: number, sy: number, sz: number) => {
      const p = new Vector3(sx * h.x, sy * h.y, sz * h.z);
      if (rot) p.applyQuaternion(rot);
      return p.add(c);
    };
    const faces: Array<[number[], number[], number[], number[]]> = [
      [[1, -1, -1], [1, 1, -1], [1, 1, 1], [1, -1, 1]],
      [[-1, -1, 1], [-1, 1, 1], [-1, 1, -1], [-1, -1, -1]],
      [[-1, 1, 1], [1, 1, 1], [1, 1, -1], [-1, 1, -1]],
      [[-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]],
      [[-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]],
      [[1, -1, -1], [-1, -1, -1], [-1, 1, -1], [1, 1, -1]],
    ];
    for (const f of faces) {
      const ids = f.map((k) => {
        const p = corner(k[0], k[1], k[2]);
        return P.vertex(p, resolve(bind, p));
      });
      P.quad(ids[0], ids[1], ids[2], ids[3]);
    }
    this.add(P, ink);
  }

  /** A lathed piece about a local y axis (a glass, a button, a hoop's bead), placed by `m`. */
  lathe(profile: Array<[number, number]>, seg: number, m: Matrix4, ink: Ink, bind: BindAt, opts: { flat?: boolean } = {}) {
    const P = new Piece();
    P.flat = opts.flat ?? false;
    const rows: number[] = [];
    for (let i = 0; i < profile.length; i++) {
      rows.push(P.pos.length / 3);
      const [r, y] = profile[i];
      for (let j = 0; j < seg; j++) {
        const th = (TAU * j) / seg;
        const p = new Vector3(Math.sin(th) * r, y, Math.cos(th) * r).applyMatrix4(m);
        P.vertex(p, resolve(bind, p));
      }
    }
    for (let i = 0; i + 1 < profile.length; i++) {
      for (let j = 0; j < seg; j++) {
        const j1 = (j + 1) % seg;
        P.quad(rows[i] + j, rows[i] + j1, rows[i + 1] + j1, rows[i + 1] + j);
      }
    }
    this.add(P, ink);
  }

  /**
   * The head: a sphere moulded by `mould` (which moves a unit direction to a point of the head,
   * in head space), with the face print's coordinates from the projection set by `facePrint`.
   */
  moulded(centre: Vector3, mould: (d: Vector3) => Vector3, ink: Ink, bind: BindAt, opts: { seg?: number; rings?: number } = {}) {
    const seg = opts.seg ?? 28;
    const rows = opts.rings ?? 18;
    const P = new Piece();
    const pts: Vector3[] = [];
    const dirs: Vector3[] = [];
    const push = (d: Vector3) => {
      const p = mould(d).add(centre);
      pts.push(p);
      dirs.push(d.clone());
      return P.vertex(p, resolve(bind, p));
    };
    const top = push(new Vector3(0, 1, 0));
    const rowIdx: number[] = [];
    for (let i = 1; i < rows; i++) {
      const lat = Math.PI / 2 - (Math.PI * i) / rows;
      rowIdx.push(P.pos.length / 3);
      for (let j = 0; j < seg; j++) {
        const th = (TAU * j) / seg;
        push(new Vector3(Math.cos(lat) * Math.sin(th), Math.sin(lat), Math.cos(lat) * Math.cos(th)));
      }
    }
    const bottom = push(new Vector3(0, -1, 0));
    for (let j = 0; j < seg; j++) P.tri(top, rowIdx[0] + j, rowIdx[0] + ((j + 1) % seg));
    for (let i = 0; i + 1 < rowIdx.length; i++) {
      for (let j = 0; j < seg; j++) {
        const j1 = (j + 1) % seg;
        P.quad(rowIdx[i] + j, rowIdx[i + 1] + j, rowIdx[i + 1] + j1, rowIdx[i] + j1);
      }
    }
    const last = rowIdx[rowIdx.length - 1];
    for (let j = 0; j < seg; j++) P.tri(bottom, last + ((j + 1) % seg), last + j);
    // face print coordinates, from the head-space position and the outward direction
    if (this.faceProject) {
      for (let i = 0; i < pts.length; i++) {
        const uv = this.faceProject(pts[i].clone().sub(centre), dirs[i]);
        if (uv) P.face.splice(i * 3, 3, uv[0], uv[1], uv[2]);
      }
    }
    this.add(P, ink);
  }

  /** Raw triangles from another builder, with one bind (a nose wedge, an ear). */
  mesh(points: Vector3[], tris: Array<[number, number, number]>, ink: Ink, bind: BindAt, opts: { flat?: boolean; face?: Vector3 } = {}) {
    const P = new Piece();
    P.flat = !!opts.flat;
    const ids = points.map((p) => P.vertex(p, resolve(bind, p)));
    for (const t of tris) P.tri(ids[t[0]], ids[t[1]], ids[t[2]]);
    // `face` is the head's centre: these points take the print too (a nose)
    if (opts.face && this.faceProject) {
      for (let i = 0; i < points.length; i++) {
        const local = points[i].clone().sub(opts.face);
        const uv = this.faceProject(local, local.clone().normalize());
        if (uv) P.face.splice(i * 3, 3, uv[0], uv[1], uv[2]);
      }
    }
    this.add(P, ink);
  }

  get triangles() {
    return this.pieces.reduce((n, p) => n + p.piece.idx.length / 3, 0);
  }

  /**
   * Close the person into one geometry. Smooth pieces share their vertices and average their
   * normals; flat pieces are split so every face keeps its own normal.
   */
  geometry(): BufferGeometry {
    const pos: number[] = [];
    const nor: number[] = [];
    const ink: number[] = [];
    const face: number[] = [];
    const si: number[] = [];
    const sw: number[] = [];
    const index: number[] = [];
    const put = (p: Vector3, n: Vector3, b: Bind, k: Ink, uv: FaceUv) => {
      pos.push(p.x, p.y, p.z);
      nor.push(n.x, n.y, n.z);
      const c = k.color;
      ink.push((c >> 16) & 255, (c >> 8) & 255, c & 255, k.id);
      face.push(uv[0], uv[1], uv[2]);
      if (typeof b === 'number') {
        si.push(b, 0, 0, 0);
        sw.push(1, 0, 0, 0);
      } else {
        si.push(b[0], b[1], 0, 0);
        sw.push(1 - b[2], b[2], 0, 0);
      }
      return pos.length / 3 - 1;
    };
    const A = new Vector3();
    const B = new Vector3();
    const C = new Vector3();
    for (const { piece, ink: k } of this.pieces) {
      const vcount = piece.pos.length / 3;
      const P = (i: number, out: Vector3) => out.set(piece.pos[i * 3], piece.pos[i * 3 + 1], piece.pos[i * 3 + 2]);
      if (piece.flat) {
        for (let t = 0; t < piece.idx.length; t += 3) {
          const ia = piece.idx[t];
          const ib = piece.idx[t + 1];
          const ic = piece.idx[t + 2];
          P(ia, A);
          P(ib, B);
          P(ic, C);
          const n = tmp2.subVectors(C, B).cross(tmp.subVectors(A, B)).normalize();
          const fa = put(A, n, piece.bind[ia], k, faceAt(piece, ia));
          const fb = put(B, n, piece.bind[ib], k, faceAt(piece, ib));
          const fc = put(C, n, piece.bind[ic], k, faceAt(piece, ic));
          index.push(fa, fb, fc);
        }
        continue;
      }
      const acc = new Float32Array(vcount * 3);
      for (let t = 0; t < piece.idx.length; t += 3) {
        const ia = piece.idx[t];
        const ib = piece.idx[t + 1];
        const ic = piece.idx[t + 2];
        P(ia, A);
        P(ib, B);
        P(ic, C);
        // area-weighted face normal
        const n = tmp2.subVectors(C, B).cross(tmp.subVectors(A, B));
        for (const i of [ia, ib, ic]) {
          acc[i * 3] += n.x;
          acc[i * 3 + 1] += n.y;
          acc[i * 3 + 2] += n.z;
        }
      }
      // vertices at the same place (a loft's seam, a ball's poles) share their normal
      const weld = new Map<string, number[]>();
      for (let i = 0; i < vcount; i++) {
        const key = `${Math.round(piece.pos[i * 3] * 1e4)}:${Math.round(piece.pos[i * 3 + 1] * 1e4)}:${Math.round(piece.pos[i * 3 + 2] * 1e4)}`;
        const list = weld.get(key);
        if (list) list.push(i);
        else weld.set(key, [i]);
      }
      weld.forEach((list) => {
        if (list.length < 2) return;
        let x = 0;
        let y = 0;
        let z = 0;
        for (const i of list) {
          x += acc[i * 3];
          y += acc[i * 3 + 1];
          z += acc[i * 3 + 2];
        }
        for (const i of list) {
          acc[i * 3] = x;
          acc[i * 3 + 1] = y;
          acc[i * 3 + 2] = z;
        }
      });
      const base = pos.length / 3;
      const n = new Vector3();
      for (let i = 0; i < vcount; i++) {
        n.set(acc[i * 3], acc[i * 3 + 1], acc[i * 3 + 2]);
        if (n.lengthSq() < 1e-12) n.set(0, 1, 0);
        n.normalize();
        put(P(i, A), n, piece.bind[i], k, faceAt(piece, i));
      }
      for (const i of piece.idx) index.push(base + i);
    }
    const g = new BufferGeometry();
    g.setAttribute('position', new BufferAttribute(new Float32Array(pos), 3));
    g.setAttribute('normal', new BufferAttribute(new Float32Array(nor), 3));
    g.setAttribute('aInk', new BufferAttribute(new Uint8Array(ink), 4, true));
    g.setAttribute('aFace', new BufferAttribute(new Float32Array(face), 3));
    g.setAttribute('skinIndex', new BufferAttribute(new Uint16Array(si), 4));
    g.setAttribute('skinWeight', new BufferAttribute(new Float32Array(sw), 4));
    const count = pos.length / 3;
    g.setIndex(new BufferAttribute(count > 65535 ? new Uint32Array(index) : new Uint16Array(index), 1));
    g.computeBoundingBox();
    g.computeBoundingSphere();
    return g;
  }
}
