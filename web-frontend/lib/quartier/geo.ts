/**
 * Le Quartier · the press: everything static is cut into one buffer.
 *
 * A street is thousands of small pieces (stones, sills, railings, chimney pots) and a phone
 * draws a few dozen meshes a frame at most, so nothing static is its own object. Each piece is
 * written into a `Press` as plain triangles carrying their ink and a few print marks, and a
 * press becomes one mesh. The marks travel per vertex:
 *
 *   aInk   rgb  the ink (a palette mix), a  the line id: neighbours with different ids are
 *              separated by an ink line in the print pass, the way a printer keys two colours
 *   aMark  r    glow: 1 is a lit window, a lamp, the neon (lit by itself at night)
 *          g    wet: the flat highlight band of zinc, water and rain on stone
 *          b    pattern: cobbles, tiles, planks, stone courses, roof seams (see PATTERN)
 *          a    shade: a baked darkening (the foot of a wall, under a cornice, inside a reveal)
 *
 * Faces are flat-shaded unless a primitive asks for smooth normals (columns, trunks, globes),
 * since the three-band ramp turns a flat face into one clean colour, as a print would.
 */
import { BufferAttribute, BufferGeometry, Matrix3, Matrix4, Vector3 } from 'three';

import type { Hex } from './palette';

export const PATTERN = {
  none: 0,
  /** Paris setts in rows, grey joints */
  cobbles: 1,
  /** café floor: small black-and-white tiles */
  tiles: 2,
  /** floorboards, the stairwell's treads */
  planks: 3,
  /** dressed stone in courses (the ground floors' rustication) */
  courses: 4,
  /** zinc roofing: standing seams */
  seams: 5,
  /** quay paving: big flags */
  flags: 6,
  /** asphalt with a little grit */
  grit: 7,
  /** horizontal ribs: shutters, slats, a closed shop's roller */
  ribs: 8,
  /** a plane tree's bark, peeling in patches */
  mottle: 9,
} as const;

export type PatternId = (typeof PATTERN)[keyof typeof PATTERN];

export interface Paint {
  color: Hex;
  /** the line id, 0–63; pieces that share it print as one shape */
  id?: number;
  glow?: number;
  wet?: number;
  pattern?: PatternId;
  shade?: number;
  /** lit by the room's lamps instead of the sky (Le Mistral, the stairwell) */
  indoor?: boolean;
}

/** Which faces of a box to keep (all by default): skip the ones nobody sees. */
export interface BoxFaces {
  px?: boolean;
  nx?: boolean;
  py?: boolean;
  ny?: boolean;
  pz?: boolean;
  nz?: boolean;
}

let autoId = 1;
/** A fresh line id for a new piece, cycling through 1–63 (0 is the sky). */
export function nextId(): number {
  autoId = (autoId % 63) + 1;
  return autoId;
}

const v3 = () => new Vector3();
const A = v3();
const B = v3();
const C = v3();
const D = v3();
const N = v3();
const E1 = v3();
const E2 = v3();

/** A growable typed array. */
class Grow<T extends Float32Array | Uint8Array> {
  data: T;
  length = 0;
  constructor(private make: (n: number) => T, initial: number) {
    this.data = make(initial);
  }
  reserve(n: number) {
    if (this.length + n <= this.data.length) return;
    let size = this.data.length * 2;
    while (size < this.length + n) size *= 2;
    const next = this.make(size);
    next.set(this.data.subarray(0, this.length) as never);
    this.data = next;
  }
  push3(a: number, b: number, c: number) {
    this.reserve(3);
    const d = this.data;
    d[this.length++] = a;
    d[this.length++] = b;
    d[this.length++] = c;
  }
  push4(a: number, b: number, c: number, e: number) {
    this.reserve(4);
    const d = this.data;
    d[this.length++] = a;
    d[this.length++] = b;
    d[this.length++] = c;
    d[this.length++] = e;
  }
  view(): T {
    return this.data.slice(0, this.length) as T;
  }
}

/** Points of a 2D shape, x then y. */
export type Shape2 = Array<[number, number]>;

export class Press {
  private pos = new Grow((n) => new Float32Array(n), 3 * 4096);
  private nor = new Grow((n) => new Float32Array(n), 3 * 4096);
  private ink = new Grow((n) => new Uint8Array(n), 4 * 4096);
  private mark = new Grow((n) => new Uint8Array(n), 4 * 4096);
  private matrix = new Matrix4();
  private normalMatrix = new Matrix3();
  private stack: Matrix4[] = [];

  get vertexCount() {
    return this.pos.length / 3;
  }

  /** Everything written until `pop` goes through this transform (composed with the current one). */
  push(m: Matrix4) {
    this.stack.push(this.matrix.clone());
    this.matrix.multiply(m);
    this.normalMatrix.getNormalMatrix(this.matrix);
    return this;
  }

  pop() {
    const m = this.stack.pop();
    if (m) this.matrix.copy(m);
    this.normalMatrix.getNormalMatrix(this.matrix);
    return this;
  }

  /** Translate (and turn about the vertical) for the duration of `draw`. */
  at(x: number, y: number, z: number, rotY: number, draw: () => void) {
    const m = new Matrix4().makeRotationY(rotY).setPosition(x, y, z);
    this.push(m);
    draw();
    this.pop();
  }

  private vertex(p: Vector3, n: Vector3, paint: Paint, id: number) {
    const q = A.copy(p).applyMatrix4(this.matrix);
    const m = N.copy(n).applyMatrix3(this.normalMatrix).normalize();
    this.pos.push3(q.x, q.y, q.z);
    this.nor.push3(m.x, m.y, m.z);
    const c = paint.color;
    this.ink.push4((c >> 16) & 255, (c >> 8) & 255, c & 255, id);
    this.mark.push4(
      Math.round((paint.glow ?? 0) * 255),
      Math.round((paint.wet ?? 0) * 255),
      (paint.pattern ?? 0) + (paint.indoor ? 16 : 0),
      Math.round((paint.shade ?? 0) * 255),
    );
  }

  private idOf(paint: Paint) {
    return paint.id ?? nextId();
  }

  /** One triangle with its own flat normal (counter-clockwise faces out). */
  tri(a: Vector3, b: Vector3, c: Vector3, paint: Paint, id = this.idOf(paint)) {
    E1.subVectors(b, a);
    E2.subVectors(c, a);
    const n = v3().crossVectors(E1, E2).normalize();
    const pa = a.clone();
    const pb = b.clone();
    const pc = c.clone();
    this.vertex(pa, n, paint, id);
    this.vertex(pb, n, paint, id);
    this.vertex(pc, n, paint, id);
  }

  /** A triangle with a normal per corner (smooth pieces). */
  triSmooth(a: Vector3, b: Vector3, c: Vector3, na: Vector3, nb: Vector3, nc: Vector3, paint: Paint, id: number) {
    this.vertex(a.clone(), na, paint, id);
    this.vertex(b.clone(), nb, paint, id);
    this.vertex(c.clone(), nc, paint, id);
  }

  /** A flat quad, corners counter-clockwise seen from the front. */
  quad(a: Vector3, b: Vector3, c: Vector3, d: Vector3, paint: Paint, id = this.idOf(paint)) {
    this.tri(a, b, c, paint, id);
    this.tri(a, c, d, paint, id);
  }

  /** A quad from plain numbers (x, y, z per corner). */
  quadXYZ(c: number[], paint: Paint, id = this.idOf(paint)) {
    A.set(c[0], c[1], c[2]);
    B.set(c[3], c[4], c[5]);
    C.set(c[6], c[7], c[8]);
    D.set(c[9], c[10], c[11]);
    this.quad(A.clone(), B.clone(), C.clone(), D.clone(), paint, id);
  }

  /**
   * An axis-aligned box from its centre and size (in the current transform). `faces` drops
   * the sides nobody sees: the bottom of anything on the ground, the back of a wall piece.
   */
  box(cx: number, cy: number, cz: number, sx: number, sy: number, sz: number, paint: Paint, faces: BoxFaces = {}, id = this.idOf(paint)) {
    const x0 = cx - sx / 2;
    const x1 = cx + sx / 2;
    const y0 = cy - sy / 2;
    const y1 = cy + sy / 2;
    const z0 = cz - sz / 2;
    const z1 = cz + sz / 2;
    const q = (pts: number[]) => this.quadXYZ(pts, paint, id);
    if (faces.pz !== false) q([x0, y0, z1, x1, y0, z1, x1, y1, z1, x0, y1, z1]);
    if (faces.nz !== false) q([x1, y0, z0, x0, y0, z0, x0, y1, z0, x1, y1, z0]);
    if (faces.px !== false) q([x1, y0, z1, x1, y0, z0, x1, y1, z0, x1, y1, z1]);
    if (faces.nx !== false) q([x0, y0, z0, x0, y0, z1, x0, y1, z1, x0, y1, z0]);
    if (faces.py !== false) q([x0, y1, z1, x1, y1, z1, x1, y1, z0, x0, y1, z0]);
    if (faces.ny !== false) q([x0, y0, z0, x1, y0, z0, x1, y0, z1, x0, y0, z1]);
  }

  /** A box standing on y = `y0` (the common case). */
  block(cx: number, y0: number, cz: number, sx: number, sy: number, sz: number, paint: Paint, faces: BoxFaces = {}, id?: number) {
    this.box(cx, y0 + sy / 2, cz, sx, sy, sz, paint, { ny: false, ...faces }, id);
  }

  /**
   * A cylinder (or a cone, or a truncated one) standing on y = `y0`, `seg` sides.
   * Smooth normals unless `flat`.
   */
  cylinder(cx: number, y0: number, cz: number, rBottom: number, rTop: number, h: number, seg: number, paint: Paint, opts: { flat?: boolean; caps?: boolean; bottom?: boolean } = {}, id = this.idOf(paint)) {
    const slope = (rBottom - rTop) / h;
    for (let i = 0; i < seg; i++) {
      const a0 = (i / seg) * Math.PI * 2;
      const a1 = ((i + 1) / seg) * Math.PI * 2;
      const c0 = Math.cos(a0);
      const s0 = Math.sin(a0);
      const c1 = Math.cos(a1);
      const s1 = Math.sin(a1);
      const p00 = new Vector3(cx + c0 * rBottom, y0, cz + s0 * rBottom);
      const p01 = new Vector3(cx + c1 * rBottom, y0, cz + s1 * rBottom);
      const p10 = new Vector3(cx + c0 * rTop, y0 + h, cz + s0 * rTop);
      const p11 = new Vector3(cx + c1 * rTop, y0 + h, cz + s1 * rTop);
      if (opts.flat) {
        this.quad(p00, p10, p11, p01, paint, id);
      } else {
        const n0 = new Vector3(c0, slope, s0).normalize();
        const n1 = new Vector3(c1, slope, s1).normalize();
        this.triSmooth(p00, p10, p11, n0, n0, n1, paint, id);
        this.triSmooth(p00, p11, p01, n0, n1, n1, paint, id);
      }
      if (opts.caps !== false && rTop > 0) {
        const top = new Vector3(cx, y0 + h, cz);
        this.tri(top, p11, p10, paint, id);
      }
      if (opts.bottom && rBottom > 0) {
        const bot = new Vector3(cx, y0, cz);
        this.tri(bot, p00, p01, paint, id);
      }
    }
  }

  /**
   * Turn a profile about the vertical axis: `profile` is [radius, height] from the bottom up.
   * Lamp posts, the Morris column, balusters, bottles, the stool.
   */
  lathe(cx: number, y0: number, cz: number, profile: Array<[number, number]>, seg: number, paint: Paint, opts: { flat?: boolean } = {}, id = this.idOf(paint)) {
    for (let j = 0; j < profile.length - 1; j++) {
      const [r0, h0] = profile[j];
      const [r1, h1] = profile[j + 1];
      const dr = r1 - r0;
      const dh = h1 - h0;
      for (let i = 0; i < seg; i++) {
        const a0 = (i / seg) * Math.PI * 2;
        const a1 = ((i + 1) / seg) * Math.PI * 2;
        const c0 = Math.cos(a0);
        const s0 = Math.sin(a0);
        const c1 = Math.cos(a1);
        const s1 = Math.sin(a1);
        const p00 = new Vector3(cx + c0 * r0, y0 + h0, cz + s0 * r0);
        const p01 = new Vector3(cx + c1 * r0, y0 + h0, cz + s1 * r0);
        const p10 = new Vector3(cx + c0 * r1, y0 + h1, cz + s0 * r1);
        const p11 = new Vector3(cx + c1 * r1, y0 + h1, cz + s1 * r1);
        if (opts.flat || (r0 === 0 && r1 === 0)) {
          if (r0 === 0) this.tri(p00, p10, p11, paint, id);
          else if (r1 === 0) this.tri(p00, p10, p01, paint, id);
          else this.quad(p00, p10, p11, p01, paint, id);
        } else {
          // the side's normal: perpendicular to the profile segment, turned about the axis
          const len = Math.hypot(dr, dh) || 1;
          const nr = dh / len;
          const ny = -dr / len;
          const n0 = new Vector3(c0 * nr, ny, s0 * nr).normalize();
          const n1 = new Vector3(c1 * nr, ny, s1 * nr).normalize();
          if (r0 > 0) this.triSmooth(p00, p10, p11, n0, n0, n1, paint, id);
          if (r1 > 0 || r0 > 0) this.triSmooth(p00, p11, p01, n0, n1, n1, paint, id);
        }
      }
    }
  }

  /** A low, flat-faceted ball (a clump of leaves, a globe lamp, a pigeon's body). */
  ball(cx: number, cy: number, cz: number, rx: number, ry: number, rz: number, paint: Paint, detail = 1, opts: { smooth?: boolean } = {}, id = this.idOf(paint)) {
    const tris = icosphere(detail);
    for (const [a, b, c] of tris) {
      const pa = new Vector3(cx + a.x * rx, cy + a.y * ry, cz + a.z * rz);
      const pb = new Vector3(cx + b.x * rx, cy + b.y * ry, cz + b.z * rz);
      const pc = new Vector3(cx + c.x * rx, cy + c.y * ry, cz + c.z * rz);
      if (opts.smooth) {
        const na = new Vector3(a.x / rx, a.y / ry, a.z / rz).normalize();
        const nb = new Vector3(b.x / rx, b.y / ry, b.z / rz).normalize();
        const nc = new Vector3(c.x / rx, c.y / ry, c.z / rz).normalize();
        this.triSmooth(pa, pb, pc, na, nb, nc, paint, id);
      } else {
        this.tri(pa, pb, pc, paint, id);
      }
    }
  }

  /**
   * Extrude a polygon (in x, z, either winding) between two heights, faces out. Caps are
   * triangulated as a fan, so keep cap polygons convex.
   */
  prism(shape: Shape2, y0: number, y1: number, paint: Paint, opts: { top?: boolean; bottom?: boolean; sides?: boolean } = {}, id = this.idOf(paint)) {
    const s = outward(shape);
    const n = s.length;
    if (opts.sides !== false) {
      for (let i = 0; i < n; i++) {
        const [x0, z0] = s[i];
        const [x1, z1] = s[(i + 1) % n];
        this.quadXYZ([x0, y0, z0, x1, y0, z1, x1, y1, z1, x0, y1, z0], paint, id);
      }
    }
    if (opts.top !== false) {
      for (let i = 1; i < n - 1; i++) {
        this.tri(new Vector3(s[0][0], y1, s[0][1]), new Vector3(s[i][0], y1, s[i][1]), new Vector3(s[i + 1][0], y1, s[i + 1][1]), paint, id);
      }
    }
    if (opts.bottom) {
      for (let i = 1; i < n - 1; i++) {
        this.tri(new Vector3(s[0][0], y0, s[0][1]), new Vector3(s[i + 1][0], y0, s[i + 1][1]), new Vector3(s[i][0], y0, s[i][1]), paint, id);
      }
    }
  }

  /**
   * Sweep a cross-section along a straight run from `a` to `b` (both in the current frame).
   * The section is [out, up] pairs, `out` pointing to the run's right-hand side, so a
   * cornice profile along a façade is one call. Open ends unless `caps`.
   */
  sweep(a: Vector3, b: Vector3, section: Array<[number, number]>, paint: Paint, opts: { caps?: boolean; closed?: boolean } = {}, id = this.idOf(paint)) {
    const dir = v3().subVectors(b, a).normalize();
    const up = new Vector3(0, 1, 0);
    const right = v3().crossVectors(dir, up).normalize();
    const at = (base: Vector3, [o, u]: [number, number]) => base.clone().addScaledVector(right, o).addScaledVector(up, u);
    const m = section.length;
    const last = opts.closed ? m : m - 1;
    for (let i = 0; i < last; i++) {
      const s0 = section[i];
      const s1 = section[(i + 1) % m];
      this.quad(at(a, s0), at(b, s0), at(b, s1), at(a, s1), paint, id);
    }
    if (opts.caps) {
      for (let i = 1; i < m - 1; i++) {
        this.tri(at(a, section[0]), at(a, section[i + 1]), at(a, section[i]), paint, id);
        this.tri(at(b, section[0]), at(b, section[i]), at(b, section[i + 1]), paint, id);
      }
    }
  }

  /** A thin bar between two points (a rail, a spar, a chair leg) with a square section. */
  bar(a: Vector3, b: Vector3, w: number, paint: Paint, id = this.idOf(paint)) {
    const dir = v3().subVectors(b, a);
    const len = dir.length();
    if (len < 1e-6) return;
    dir.divideScalar(len);
    const helper = Math.abs(dir.y) > 0.9 ? new Vector3(1, 0, 0) : new Vector3(0, 1, 0);
    const u = v3().crossVectors(dir, helper).normalize().multiplyScalar(w / 2);
    const v = v3().crossVectors(dir, u).normalize().multiplyScalar(w / 2);
    const corners = [
      [u, v],
      [u.clone().negate(), v],
      [u.clone().negate(), v.clone().negate()],
      [u, v.clone().negate()],
    ].map(([p, q]) => p.clone().add(q));
    for (let i = 0; i < 4; i++) {
      const c0 = corners[i];
      const c1 = corners[(i + 1) % 4];
      this.quad(a.clone().add(c0), a.clone().add(c1), b.clone().add(c1), b.clone().add(c0), paint, id);
    }
  }

  /** Close this press into a geometry (the arrays are copied, so the press can be dropped). */
  geometry(): BufferGeometry {
    const g = new BufferGeometry();
    g.setAttribute('position', new BufferAttribute(this.pos.view(), 3));
    g.setAttribute('normal', new BufferAttribute(this.nor.view(), 3));
    g.setAttribute('aInk', new BufferAttribute(this.ink.view(), 4, true));
    g.setAttribute('aMark', new BufferAttribute(this.mark.view(), 4, false));
    g.computeBoundingSphere();
    g.computeBoundingBox();
    return g;
  }
}

export const LACE = {
  solid: 0,
  /** a Haussmann balcony: close bars between rails, a row of rings at the foot */
  balcony: 1,
  /** a footbridge's diagonal lattice */
  lattice: 2,
  /** a plain guard of bars: window guards, the canal's edge */
  guard: 3,
} as const;

export type LaceKind = (typeof LACE)[keyof typeof LACE];

/**
 * Ironwork is not modelled bar by bar: a balcony is one quad, and its bars are cut from a
 * pattern in the shader (`laceMaterial`). Each quad carries metres along the run and up from
 * its foot, so the bars keep their spacing whatever the quad's size.
 */
export class LacePress {
  private pos = new Grow((n) => new Float32Array(n), 3 * 1024);
  private nor = new Grow((n) => new Float32Array(n), 3 * 1024);
  private run = new Grow((n) => new Float32Array(n), 2 * 1024);
  private kind = new Grow((n) => new Float32Array(n), 1024);
  private ids = new Grow((n) => new Float32Array(n), 1024);
  private matrix = new Matrix4();
  private normalMatrix = new Matrix3();
  private stack: Matrix4[] = [];

  push(m: Matrix4) {
    this.stack.push(this.matrix.clone());
    this.matrix.multiply(m);
    this.normalMatrix.getNormalMatrix(this.matrix);
    return this;
  }

  pop() {
    const m = this.stack.pop();
    if (m) this.matrix.copy(m);
    this.normalMatrix.getNormalMatrix(this.matrix);
    return this;
  }

  /**
   * A vertical panel of ironwork from `a` to `b` (its foot), `h` tall, starting `u0` metres
   * into the pattern so a run of panels lines up. The foot may slope (a stair's parapet).
   */
  panel(a: Vector3, b: Vector3, h: number, kind: LaceKind, id: number, u0 = 0) {
    const len = a.distanceTo(b);
    const up = new Vector3(0, h, 0);
    const corners = [a.clone(), b.clone(), b.clone().add(up), a.clone().add(up)];
    const runs: Array<[number, number]> = [
      [u0, 0],
      [u0 + len, 0],
      [u0 + len, h],
      [u0, h],
    ];
    const n = new Vector3().subVectors(b, a).cross(new Vector3(0, 1, 0)).normalize();
    const order = [0, 1, 2, 0, 2, 3];
    for (const i of order) {
      const p = corners[i].clone().applyMatrix4(this.matrix);
      const q = n.clone().applyMatrix3(this.normalMatrix).normalize();
      this.pos.push3(p.x, p.y, p.z);
      this.nor.push3(q.x, q.y, q.z);
      this.run.reserve(2);
      this.run.data[this.run.length++] = runs[i][0];
      this.run.data[this.run.length++] = runs[i][1];
      this.kind.reserve(1);
      this.kind.data[this.kind.length++] = kind;
      this.ids.reserve(1);
      this.ids.data[this.ids.length++] = id;
    }
  }

  get vertexCount() {
    return this.pos.length / 3;
  }

  geometry(): BufferGeometry {
    const g = new BufferGeometry();
    g.setAttribute('position', new BufferAttribute(this.pos.view(), 3));
    g.setAttribute('normal', new BufferAttribute(this.nor.view(), 3));
    g.setAttribute('aRun', new BufferAttribute(this.run.view(), 2));
    g.setAttribute('aKind', new BufferAttribute(this.kind.view(), 1));
    g.setAttribute('aId', new BufferAttribute(this.ids.view(), 1));
    g.computeBoundingSphere();
    return g;
  }
}

/**
 * Flat cards that carry a picture from an atlas: shop names, street plaques, posters.
 * Position, normal, uv and whether the card hangs indoors; the sign material does the rest.
 */
export class CardPress {
  private pos = new Grow((n) => new Float32Array(n), 3 * 256);
  private nor = new Grow((n) => new Float32Array(n), 3 * 256);
  private uvs = new Grow((n) => new Float32Array(n), 2 * 256);
  private room = new Grow((n) => new Float32Array(n), 256);

  /**
   * A card centred on `c`, facing `n` (horizontal), `w` × `h`, showing atlas rect
   * [u0, v0, u1, v1] (v up). An indoor card is lit by the room, not by the sky.
   */
  card(c: Vector3, n: Vector3, w: number, h: number, rect: [number, number, number, number], tilt = 0, indoor = false) {
    const right = new Vector3(0, 1, 0).cross(n).normalize();
    const up = new Vector3().crossVectors(n, right).normalize();
    if (tilt) up.applyAxisAngle(right, tilt);
    const hw = right.clone().multiplyScalar(w / 2);
    const hh = up.clone().multiplyScalar(h / 2);
    const corners = [
      c.clone().sub(hw).sub(hh),
      c.clone().add(hw).sub(hh),
      c.clone().add(hw).add(hh),
      c.clone().sub(hw).add(hh),
    ];
    const [u0, v0, u1, v1] = rect;
    const uv: Array<[number, number]> = [
      [u0, v0],
      [u1, v0],
      [u1, v1],
      [u0, v1],
    ];
    for (const i of [0, 1, 2, 0, 2, 3]) {
      this.pos.push3(corners[i].x, corners[i].y, corners[i].z);
      this.nor.push3(n.x, n.y, n.z);
      this.uvs.reserve(2);
      this.uvs.data[this.uvs.length++] = uv[i][0];
      this.uvs.data[this.uvs.length++] = uv[i][1];
      this.room.reserve(1);
      this.room.data[this.room.length++] = indoor ? 1 : 0;
    }
  }

  get vertexCount() {
    return this.pos.length / 3;
  }

  geometry(): BufferGeometry {
    const g = new BufferGeometry();
    g.setAttribute('position', new BufferAttribute(this.pos.view(), 3));
    g.setAttribute('normal', new BufferAttribute(this.nor.view(), 3));
    g.setAttribute('uv', new BufferAttribute(this.uvs.view(), 2));
    g.setAttribute('aIndoor', new BufferAttribute(this.room.view(), 1));
    g.computeBoundingSphere();
    return g;
  }
}

/** Twice the signed area of a polygon in (x, z). */
export function area2(shape: Shape2): number {
  let a = 0;
  for (let i = 0; i < shape.length; i++) {
    const [x0, z0] = shape[i];
    const [x1, z1] = shape[(i + 1) % shape.length];
    a += x0 * z1 - x1 * z0;
  }
  return a;
}

/** The winding whose side walls face out (negative signed area in x, z). */
export function outward(shape: Shape2): Shape2 {
  return area2(shape) > 0 ? shape.slice().reverse() : shape;
}

let icoCache: Map<number, Array<[Vector3, Vector3, Vector3]>> | null = null;

/** Triangles of a unit icosphere (0 = the plain icosahedron). */
function icosphere(detail: number): Array<[Vector3, Vector3, Vector3]> {
  icoCache = icoCache ?? new Map();
  const hit = icoCache.get(detail);
  if (hit) return hit;
  const t = (1 + Math.sqrt(5)) / 2;
  const vs = [
    [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
    [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
    [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
  ].map(([x, y, z]) => new Vector3(x, y, z).normalize());
  const fs = [
    [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
    [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
    [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
    [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
  ];
  let tris: Array<[Vector3, Vector3, Vector3]> = fs.map(([a, b, c]) => [vs[a], vs[b], vs[c]]);
  for (let d = 0; d < detail; d++) {
    const next: Array<[Vector3, Vector3, Vector3]> = [];
    for (const [a, b, c] of tris) {
      const ab = a.clone().add(b).normalize();
      const bc = b.clone().add(c).normalize();
      const ca = c.clone().add(a).normalize();
      next.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]);
    }
    tris = next;
  }
  icoCache.set(detail, tris);
  return tris;
}

/** A tiny seeded random (mulberry32), so the quarter is the same street on every phone. */
export function seeded(seed: number) {
  let s = seed >>> 0;
  const next = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    range: (a: number, b: number) => a + (b - a) * next(),
    int: (a: number, b: number) => Math.floor(a + (b - a + 1) * next()),
    pick: <T,>(xs: readonly T[]): T => xs[Math.floor(next() * xs.length) % xs.length],
    chance: (p: number) => next() < p,
  };
}

export type Rand = ReturnType<typeof seeded>;

/**
 * Cut a pressed geometry into tiles of `size` metres (by each triangle's centre), so the
 * renderer can skip the tiles behind you and a tap tests only the tiles it crosses.
 */
export function tile(g: BufferGeometry, size: number): BufferGeometry[] {
  const names = Object.keys(g.attributes);
  const pos = g.getAttribute('position');
  const tris = pos.count / 3;
  const buckets = new Map<string, number[]>();
  for (let t = 0; t < tris; t++) {
    const i = t * 3;
    const cx = (pos.getX(i) + pos.getX(i + 1) + pos.getX(i + 2)) / 3;
    const cz = (pos.getZ(i) + pos.getZ(i + 1) + pos.getZ(i + 2)) / 3;
    const key = `${Math.floor(cx / size)}:${Math.floor(cz / size)}`;
    let b = buckets.get(key);
    if (!b) {
      b = [];
      buckets.set(key, b);
    }
    b.push(t);
  }
  const out: BufferGeometry[] = [];
  for (const list of Array.from(buckets.values())) {
    const part = new BufferGeometry();
    for (const name of names) {
      const src = g.getAttribute(name) as BufferAttribute;
      const n = src.itemSize;
      const Ctor = (src.array as Float32Array).constructor as { new (len: number): Float32Array | Uint8Array };
      const arr = new Ctor(list.length * 3 * n);
      let o = 0;
      for (const t of list) {
        const start = t * 3 * n;
        for (let k = 0; k < 3 * n; k++) arr[o++] = (src.array as ArrayLike<number>)[start + k];
      }
      part.setAttribute(name, new BufferAttribute(arr, n, src.normalized));
    }
    part.computeBoundingSphere();
    part.computeBoundingBox();
    out.push(part);
  }
  return out;
}

