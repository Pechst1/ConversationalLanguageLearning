/**
 * Le Quartier · where you can walk.
 *
 * The quarter is pressed onto a half-metre grid: each cell is walkable or not and has a height
 * (pavement, road, the footbridge's ramp of steps, the café's floor). Walking with the thumb
 * slides along walls; a tap on the ground walks there along the shortest street path (A*,
 * then pulled straight wherever the line of sight is clear).
 */
import { Vector3 } from 'three';

import type { Shape2 } from './geo';
import type { NavShape } from './kit';

const BLOCKED = 0;
const OPEN = 1;

export class Nav {
  readonly cell: number;
  readonly x0: number;
  readonly z0: number;
  readonly w: number;
  readonly h: number;
  private open: Uint8Array;
  private ys: Float32Array;

  constructor(walk: NavShape[], blocks: Shape2[], bounds: { x0: number; z0: number; x1: number; z1: number }, cell = 0.5) {
    this.cell = cell;
    this.x0 = bounds.x0;
    this.z0 = bounds.z0;
    this.w = Math.ceil((bounds.x1 - bounds.x0) / cell);
    this.h = Math.ceil((bounds.z1 - bounds.z0) / cell);
    this.open = new Uint8Array(this.w * this.h);
    this.ys = new Float32Array(this.w * this.h);
    for (const s of walk) this.fill(s.shape, (x, z, k) => {
      this.open[k] = OPEN;
      this.ys[k] = typeof s.y === 'number' ? s.y : ramp(s.y, x, z);
    });
    for (const b of blocks) this.fill(b, (_x, _z, k) => {
      this.open[k] = BLOCKED;
    }, true);
  }

  /** Visit every cell whose centre is inside `shape` (or, if `touch`, that the shape overlaps). */
  private fill(shape: Shape2, visit: (x: number, z: number, k: number) => void, touch = false) {
    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;
    for (const [x, z] of shape) {
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minZ = Math.min(minZ, z);
      maxZ = Math.max(maxZ, z);
    }
    const c = this.cell;
    const pad = touch ? c * 0.5 : 0;
    const ix0 = Math.max(0, Math.floor((minX - pad - this.x0) / c));
    const ix1 = Math.min(this.w - 1, Math.floor((maxX + pad - this.x0) / c));
    const iz0 = Math.max(0, Math.floor((minZ - pad - this.z0) / c));
    const iz1 = Math.min(this.h - 1, Math.floor((maxZ + pad - this.z0) / c));
    for (let iz = iz0; iz <= iz1; iz++) {
      for (let ix = ix0; ix <= ix1; ix++) {
        const x = this.x0 + (ix + 0.5) * c;
        const z = this.z0 + (iz + 0.5) * c;
        if (inside(shape, x, z) || (touch && nearEdge(shape, x, z, c * 0.36))) visit(x, z, iz * this.w + ix);
      }
    }
  }

  private index(x: number, z: number): number {
    const ix = Math.floor((x - this.x0) / this.cell);
    const iz = Math.floor((z - this.z0) / this.cell);
    if (ix < 0 || iz < 0 || ix >= this.w || iz >= this.h) return -1;
    return iz * this.w + ix;
  }

  walkable(x: number, z: number): boolean {
    const k = this.index(x, z);
    return k >= 0 && this.open[k] === OPEN;
  }

  heightAt(x: number, z: number): number {
    // bilinear over the four cells round the point, ignoring blocked ones
    const c = this.cell;
    const fx = (x - this.x0) / c - 0.5;
    const fz = (z - this.z0) / c - 0.5;
    const ix = Math.floor(fx);
    const iz = Math.floor(fz);
    let sum = 0;
    let wsum = 0;
    for (let dz = 0; dz <= 1; dz++) {
      for (let dx = 0; dx <= 1; dx++) {
        const cx = ix + dx;
        const cz = iz + dz;
        if (cx < 0 || cz < 0 || cx >= this.w || cz >= this.h) continue;
        const k = cz * this.w + cx;
        if (this.open[k] !== OPEN) continue;
        const wgt = (dx ? fx - ix : 1 - (fx - ix)) * (dz ? fz - iz : 1 - (fz - iz));
        sum += this.ys[k] * wgt;
        wsum += wgt;
      }
    }
    if (wsum > 0) return sum / wsum;
    const k = this.index(x, z);
    return k >= 0 ? this.ys[k] : 0;
  }

  /** Can a walker of radius `r` stand here? */
  standable(x: number, z: number, r = 0.22): boolean {
    return this.walkable(x, z) && this.walkable(x + r, z) && this.walkable(x - r, z) && this.walkable(x, z + r) && this.walkable(x, z - r);
  }

  /** Move by (dx, dz), sliding along walls; returns the new position. */
  slide(x: number, z: number, dx: number, dz: number, r = 0.22): [number, number] {
    if (this.standable(x + dx, z + dz, r) && this.stepOk(x, z, x + dx, z + dz)) return [x + dx, z + dz];
    if (this.standable(x + dx, z, r) && this.stepOk(x, z, x + dx, z)) return [x + dx, z];
    if (this.standable(x, z + dz, r) && this.stepOk(x, z, x, z + dz)) return [x, z + dz];
    return [x, z];
  }

  /** No climbing a wall: a step up of more than a stair's riser and a bit is refused. */
  private stepOk(x0: number, z0: number, x1: number, z1: number) {
    return Math.abs(this.heightAt(x1, z1) - this.heightAt(x0, z0)) < 0.35;
  }

  /** The nearest walkable point to (x, z) within `maxR` metres, or null. */
  nearest(x: number, z: number, maxR = 6): [number, number] | null {
    if (this.standable(x, z)) return [x, z];
    const c = this.cell;
    for (let r = c; r <= maxR; r += c) {
      const steps = Math.max(8, Math.round((2 * Math.PI * r) / c));
      let best: [number, number] | null = null;
      let bestD = Infinity;
      for (let i = 0; i < steps; i++) {
        const a = (i / steps) * Math.PI * 2;
        const px = x + Math.cos(a) * r;
        const pz = z + Math.sin(a) * r;
        if (this.standable(px, pz)) {
          const d = Math.hypot(px - x, pz - z);
          if (d < bestD) {
            bestD = d;
            best = [px, pz];
          }
        }
      }
      if (best) return best;
    }
    return null;
  }

  /** Is the straight line between two points walkable all along (and without steps)? */
  clear(ax: number, az: number, bx: number, bz: number): boolean {
    const d = Math.hypot(bx - ax, bz - az);
    const n = Math.max(1, Math.ceil(d / (this.cell * 0.5)));
    let py = this.heightAt(ax, az);
    for (let i = 1; i <= n; i++) {
      const t = i / n;
      const x = ax + (bx - ax) * t;
      const z = az + (bz - az) * t;
      if (!this.standable(x, z)) return false;
      const y = this.heightAt(x, z);
      if (Math.abs(y - py) > 0.35) return false;
      py = y;
    }
    return true;
  }

  /** The shortest walk from `a` to `b`, as points on the ground (null if there is none). */
  path(a: Vector3, b: Vector3, maxCells = 60000): Vector3[] | null {
    const start = this.index(a.x, a.z);
    const goalPt = this.nearest(b.x, b.z, 4);
    if (start < 0 || !goalPt) return null;
    const goal = this.index(goalPt[0], goalPt[1]);
    if (goal < 0) return null;
    if (this.clear(a.x, a.z, goalPt[0], goalPt[1])) {
      return [new Vector3(goalPt[0], this.heightAt(goalPt[0], goalPt[1]), goalPt[1])];
    }
    const W = this.w;
    const gx = goal % W;
    const gz = Math.floor(goal / W);
    const g = new Map<number, number>();
    const came = new Map<number, number>();
    const heap = new MinHeap();
    const hOf = (k: number) => {
      const dx = Math.abs((k % W) - gx);
      const dz = Math.abs(Math.floor(k / W) - gz);
      return Math.max(dx, dz) + 0.4142 * Math.min(dx, dz);
    };
    g.set(start, 0);
    heap.push(start, hOf(start));
    const closed = new Set<number>();
    const dirs: Array<[number, number, number]> = [
      [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
      [1, 1, 1.4142], [1, -1, 1.4142], [-1, 1, 1.4142], [-1, -1, 1.4142],
    ];
    let found = false;
    while (heap.size > 0 && closed.size < maxCells) {
      const k = heap.pop();
      if (k === goal) {
        found = true;
        break;
      }
      if (closed.has(k)) continue;
      closed.add(k);
      const kx = k % W;
      const kz = Math.floor(k / W);
      const gk = g.get(k) ?? 0;
      for (const [dx, dz, cost] of dirs) {
        const nx = kx + dx;
        const nz = kz + dz;
        if (nx < 0 || nz < 0 || nx >= W || nz >= this.h) continue;
        const nk = nz * W + nx;
        if (this.open[nk] !== OPEN || closed.has(nk)) continue;
        // no cutting corners past a wall
        if (dx && dz && (this.open[kz * W + nx] !== OPEN || this.open[nz * W + kx] !== OPEN)) continue;
        if (Math.abs(this.ys[nk] - this.ys[k]) > 0.35) continue;
        const ng = gk + cost;
        if (ng < (g.get(nk) ?? Infinity)) {
          g.set(nk, ng);
          came.set(nk, k);
          heap.push(nk, ng + hOf(nk));
        }
      }
    }
    if (!found) return null;
    const cells: number[] = [];
    let k: number | undefined = goal;
    while (k !== undefined && k !== start) {
      cells.push(k);
      k = came.get(k);
    }
    cells.reverse();
    const pts = cells.map((c) => {
      const x = this.x0 + ((c % W) + 0.5) * this.cell;
      const z = this.z0 + (Math.floor(c / W) + 0.5) * this.cell;
      return new Vector3(x, this.ys[c], z);
    });
    pts[pts.length - 1] = new Vector3(goalPt[0], this.heightAt(goalPt[0], goalPt[1]), goalPt[1]);
    // pull the path straight wherever the way is clear
    const out: Vector3[] = [];
    let from = a.clone();
    let i = 0;
    while (i < pts.length) {
      let j = pts.length - 1;
      while (j > i && !this.clear(from.x, from.z, pts[j].x, pts[j].z)) j--;
      out.push(pts[j]);
      from = pts[j];
      i = j + 1;
    }
    return out;
  }
}

function ramp(r: { from: [number, number]; to: [number, number]; y0: number; y1: number }, x: number, z: number) {
  const dx = r.to[0] - r.from[0];
  const dz = r.to[1] - r.from[1];
  const len2 = dx * dx + dz * dz || 1;
  const t = Math.max(0, Math.min(1, ((x - r.from[0]) * dx + (z - r.from[1]) * dz) / len2));
  return r.y0 + (r.y1 - r.y0) * t;
}

export function inside(shape: Shape2, x: number, z: number): boolean {
  let c = false;
  for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
    const [xi, zi] = shape[i];
    const [xj, zj] = shape[j];
    if (zi > z !== zj > z && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
}

function nearEdge(shape: Shape2, x: number, z: number, r: number): boolean {
  for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
    const [ax, az] = shape[j];
    const [bx, bz] = shape[i];
    const dx = bx - ax;
    const dz = bz - az;
    const len2 = dx * dx + dz * dz || 1;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / len2));
    if (Math.hypot(x - (ax + dx * t), z - (az + dz * t)) < r) return true;
  }
  return false;
}

class MinHeap {
  private keys: number[] = [];
  private pri: number[] = [];
  get size() {
    return this.keys.length;
  }
  push(k: number, p: number) {
    this.keys.push(k);
    this.pri.push(p);
    let i = this.keys.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (this.pri[parent] <= this.pri[i]) break;
      this.swap(i, parent);
      i = parent;
    }
  }
  pop(): number {
    const top = this.keys[0];
    const lastK = this.keys.pop() as number;
    const lastP = this.pri.pop() as number;
    if (this.keys.length > 0) {
      this.keys[0] = lastK;
      this.pri[0] = lastP;
      let i = 0;
      for (;;) {
        const l = i * 2 + 1;
        const r = l + 1;
        let m = i;
        if (l < this.keys.length && this.pri[l] < this.pri[m]) m = l;
        if (r < this.keys.length && this.pri[r] < this.pri[m]) m = r;
        if (m === i) break;
        this.swap(i, m);
        i = m;
      }
    }
    return top;
  }
  private swap(a: number, b: number) {
    [this.keys[a], this.keys[b]] = [this.keys[b], this.keys[a]];
    [this.pri[a], this.pri[b]] = [this.pri[b], this.pri[a]];
  }
}
