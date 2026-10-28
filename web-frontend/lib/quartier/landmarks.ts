/**
 * Le Quartier · the landmarks a forged place is known by, and the small furniture the open data
 * places.
 *
 * The data gives a landmark's footprint and height; the kind is the forge's: a market hall
 * (`halle`: a stone base, posts, tall glazing, a hipped roof with a lantern, walkable inside),
 * a pavilion on a square. The street's small things come from the data point by point: bicycle
 * hoops, the green glass bins, the yellow post boxes. And where the walkable world ends, a
 * site hoarding across the street, the honest edge of a city still being drawn.
 */
import { Matrix4, Vector3 } from 'three';

import { KERB, boxShape, circle, fitText } from './kit';
import type { Build } from './kit';
import { PATTERN, nextId } from './geo';
import type { Paint, Shape2 } from './geo';
import { stall } from './market';
import type { GoodsKind, StallInfo } from './market';
import { INKS, TONES, mix, rgb } from './palette';

export interface LandmarkSpec {
  kind: 'halle' | 'pavillon';
  name: string;
  /** centre, the long axis (unit), length along it, width across */
  c: [number, number];
  u: [number, number];
  len: number;
  wid: number;
  height?: number;
}

export interface LandmarkBuilt {
  kind: LandmarkSpec['kind'];
  name: string;
  /** the room under its roof, if you can go in (x0, z0, x1, z1, axis-aligned, for the rain) */
  room: [number, number, number, number] | null;
  /** its stalls, for the people who keep them */
  stalls: StallInfo[];
  /** the doors, in the world, outside each one */
  doors: Vector3[];
  center: Vector3;
}

/** The frame of a landmark: x along its length, z across, y up, origin at its centre. */
function frameOf(l: LandmarkSpec, y = KERB) {
  const u = new Vector3(l.u[0], 0, l.u[1]).normalize();
  const v = new Vector3(-u.z, 0, u.x);
  return new Matrix4().makeBasis(u, new Vector3(0, 1, 0), v).setPosition(l.c[0], y, l.c[1]);
}

function toWorld(m: Matrix4, x: number, y: number, z: number) {
  return new Vector3(x, y, z).applyMatrix4(m);
}

/** The lettering over a hall's doors: dark capitals on a cream board. */
function nameBoardArt(name: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = '#f1ece1';
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#2c6a5d';
    ctx.lineWidth = Math.max(2, h * 0.06);
    ctx.strokeRect(h * 0.08, h * 0.08, w - h * 0.16, h - h * 0.16);
    ctx.fillStyle = '#14110d';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const t = "700 {s}px AtelierSans, 'Instrument Sans', system-ui, sans-serif";
    const s = fitText(ctx, name.toUpperCase(), w * 0.86, Math.round(h * 0.56), t);
    ctx.font = t.replace('{s}', String(s));
    ctx.fillText(name.toUpperCase(), w / 2, h * 0.54);
  };
}

/** A clock face: white enamel, black hands at a quarter past nine (the market's busy hour). */
function clockArt() {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    const r = Math.min(w, h) / 2;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#14110d';
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#f8f3e8';
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, r * 0.88, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#14110d';
    ctx.lineCap = 'round';
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      ctx.lineWidth = r * (i % 3 === 0 ? 0.07 : 0.035);
      ctx.beginPath();
      ctx.moveTo(w / 2 + Math.sin(a) * r * 0.7, h / 2 - Math.cos(a) * r * 0.7);
      ctx.lineTo(w / 2 + Math.sin(a) * r * 0.8, h / 2 - Math.cos(a) * r * 0.8);
      ctx.stroke();
    }
    const hand = (a: number, len: number, wd: number) => {
      ctx.lineWidth = r * wd;
      ctx.beginPath();
      ctx.moveTo(w / 2, h / 2);
      ctx.lineTo(w / 2 + Math.sin(a) * r * len, h / 2 - Math.cos(a) * r * len);
      ctx.stroke();
    };
    hand(((9 + 15 / 60) / 12) * Math.PI * 2, 0.45, 0.08);
    hand((15 / 60) * Math.PI * 2, 0.68, 0.05);
  };
}

/**
 * A covered market: stone base, posts, tall glazing, a hipped roof boarded underneath with a
 * louvred lantern down the middle for the light, the name over the doors, a clock on one end.
 * Inside, the floor is rows of counters: one along each wall, then islands of two rows back to
 * back, aisles between them, a cross aisle from door to door.
 */
export function halle(B: Build, l: LandmarkSpec, seed: number): LandmarkBuilt {
  const D = B.dry;
  const m = frameOf(l);
  const L = l.len;
  const Wd = l.wid;
  const H = Math.max(9, l.height ?? 10);
  const eave = Math.min(5.2, H * 0.5);
  const stone: Paint = { color: mix(TONES.stone, INKS.ochre, 0.08), id: nextId(), pattern: PATTERN.courses };
  const post: Paint = { color: mix(INKS.green, INKS.ink, 0.35), id: nextId() };
  const timber: Paint = { color: mix(TONES.wood, INKS.ochre, 0.15), id: nextId() };
  const floor: Paint = { color: mix(TONES.stoneGround, INKS.ink, 0.08), id: nextId(), pattern: PATTERN.flags };
  const doors: Vector3[] = [];
  const blocks: Shape2[] = [];
  D.push(m);
  // the floor inside, a step up from the square
  B.wet.push(m);
  B.wet.quadXYZ([-L / 2, 0.02, Wd / 2, L / 2, 0.02, Wd / 2, L / 2, 0.02, -Wd / 2, -L / 2, 0.02, -Wd / 2], floor, floor.id);
  B.wet.pop();
  // the walls: per side, a door in the middle, bays of glazing on a stone base either side
  const sides: Array<{ a: [number, number]; b: [number, number]; door: number }> = [
    { a: [-L / 2, Wd / 2], b: [L / 2, Wd / 2], door: 3.6 },
    { a: [L / 2, Wd / 2], b: [L / 2, -Wd / 2], door: 4.2 },
    { a: [L / 2, -Wd / 2], b: [-L / 2, -Wd / 2], door: 3.6 },
    { a: [-L / 2, -Wd / 2], b: [-L / 2, Wd / 2], door: 4.2 },
  ];
  const glassId = nextId();
  sides.forEach((s, si) => {
    const dx = s.b[0] - s.a[0];
    const dz = s.b[1] - s.a[1];
    const len = Math.hypot(dx, dz);
    const tx = dx / len;
    const tz = dz / len;
    const nx = -tz;
    const nz = tx;
    const at = (u: number, w = 0): [number, number] => [s.a[0] + tx * u + nx * w, s.a[1] + tz * u + nz * w];
    const bays = Math.max(2, Math.round(len / 4.2));
    const bw = len / bays;
    const mid = len / 2;
    const d0 = mid - s.door / 2;
    const d1 = mid + s.door / 2;
    const postAt = (u: number) => {
      const [px, pz] = at(u);
      D.box(px, eave / 2, pz, 0.36, eave, 0.36, post);
    };
    // the door's own posts, and one at each bay line clear of the door
    postAt(d0 - 0.18);
    postAt(d1 + 0.18);
    for (let i = 0; i < bays; i++) {
      const u0 = i * bw;
      const u1 = (i + 1) * bw;
      if (u0 < d0 - 0.6 || u0 > d1 + 0.6) postAt(u0);
      const doorHere = u0 < d1 && u1 > d0;
      const segs: Array<[number, number]> = doorHere
        ? [
            [u0, Math.max(u0, d0 - 0.36)],
            [Math.min(u1, d1 + 0.36), u1],
          ]
        : [[u0, u1]];
      for (const [g0, g1] of segs) {
        if (g1 - g0 < 0.2) continue;
        const [c0x, c0z] = at((g0 + g1) / 2);
        const angle = Math.atan2(-tz, tx);
        D.at(c0x, 0, c0z, angle, () => {
          D.box(0, 0.55, 0, g1 - g0, 1.1, 0.4, stone);
          D.box(0, 1.15, 0.05, g1 - g0, 0.1, 0.5, { color: mix(TONES.stoneLight, INKS.paper, 0.2), id: stone.id });
          // tall panes in timber frames, from the base to under the eave
          B.glass.push(new Matrix4().makeRotationY(angle).setPosition(c0x, 0, c0z).premultiply(m));
          B.glass.quadXYZ([-(g1 - g0) / 2, 1.2, 0, (g1 - g0) / 2, 1.2, 0, (g1 - g0) / 2, eave - 0.5, 0, -(g1 - g0) / 2, eave - 0.5, 0], { color: mix(INKS.cobalt, INKS.paper, 0.55), id: glassId }, glassId);
          B.glass.pop();
          const mullions = Math.max(1, Math.round((g1 - g0) / 0.9));
          for (let k = 0; k <= mullions; k++) D.box(-(g1 - g0) / 2 + (k * (g1 - g0)) / mullions, (1.2 + eave - 0.5) / 2, 0, 0.08, eave - 1.7, 0.12, timber);
          D.box(0, (eave - 0.5 + 1.2) / 2 + 0.6, 0, g1 - g0, 0.08, 0.12, timber);
          D.box(0, eave - 0.25, 0, g1 - g0, 0.5, 0.3, timber);
        });
        const shape: Shape2 = [at(g0, -0.25), at(g1, -0.25), at(g1, 0.25), at(g0, 0.25)];
        blocks.push(shape);
      }
      if (doorHere && u0 <= mid && u1 > mid) {
        // the lintel over the door, and the name on it
        const [cx, cz] = at(mid);
        const angle = Math.atan2(-tz, tx);
        D.at(cx, 0, cz, angle, () => {
          D.box(0, 3.65, 0, s.door + 0.4, 0.3, 0.42, timber);
          D.box(0, (3.8 + eave) / 2, 0, s.door + 0.4, eave - 3.8, 0.3, { color: mix(TONES.stoneLight, INKS.paper, 0.15), id: stone.id });
        });
        if (l.name) {
          const w = toWorld(m, ...([at(mid, 0.17)[0], 4.45, at(mid, 0.17)[1]] as [number, number, number]));
          const n = new Vector3(nx, 0, nz).transformDirection(m);
          B.signs.push({ key: `halle:${l.name}`, center: w, normal: n, width: Math.min(s.door + 2.4, 5.4), height: 0.62, density: 140, draw: nameBoardArt(l.name) });
        }
        doors.push(toWorld(m, at(mid, 2.2)[0], 0, at(mid, 2.2)[1]));
      }
    }
    void si;
  });
  // the clock over the door at the east end (+x)
  {
    const w = toWorld(m, L / 2 + 0.2, eave + 1.0, 0);
    B.signs.push({ key: 'halle:clock', center: w, normal: new Vector3(1, 0, 0).transformDirection(m), width: 1.1, height: 1.1, density: 160, draw: clockArt() });
    D.box(L / 2 + 0.05, eave + 1.0, 0, 0.2, 1.4, 1.4, { color: mix(TONES.stoneLight, INKS.paper, 0.15), id: stone.id });
  }
  // the roof: four slopes from the eaves up to a lantern of louvres down the ridge, a second
  // little roof on the lantern; boarded underneath, so inside you look up into timber
  const zinc: Paint = { color: mix(TONES.zinc, INKS.ink, 0.12), id: nextId(), pattern: PATTERN.seams };
  const zincTop: Paint = { color: TONES.zincTop, id: zinc.id };
  const boards: Paint = { color: mix(TONES.woodLight, INKS.paper, 0.2), id: nextId(), pattern: PATTERN.planks };
  const over = 0.9;
  const lx = L / 2 + over;
  const lz = Wd / 2 + over;
  const e = eave + 0.1;
  const iz = Math.max(2.2, Wd * 0.12);
  const ix = Math.max(iz, lx - (lz - iz));
  const lh = 1.3;
  const r1 = Math.max(e + 1.6, H - lh - 0.9);
  const slope = (y: number, flip: boolean, p: Paint) => {
    const q = (c: number[]) => D.quadXYZ(flip ? [c[9], c[10], c[11], c[6], c[7], c[8], c[3], c[4], c[5], c[0], c[1], c[2]] : c, p);
    q([-lx, e + y, lz, lx, e + y, lz, ix, r1 + y, iz, -ix, r1 + y, iz]);
    q([lx, e + y, -lz, -lx, e + y, -lz, -ix, r1 + y, -iz, ix, r1 + y, -iz]);
    q([lx, e + y, lz, lx, e + y, -lz, ix, r1 + y, -iz, ix, r1 + y, iz]);
    q([-lx, e + y, -lz, -lx, e + y, lz, -ix, r1 + y, iz, -ix, r1 + y, -iz]);
  };
  slope(0, false, zinc);
  slope(-0.12, true, boards);
  // the eaves' edge, a board you see from the square
  D.sweep(new Vector3(-lx, e - 0.2, lz), new Vector3(lx, e - 0.2, lz), [[0, 0], [0.06, 0], [0.06, 0.26], [0, 0.26]], { color: mix(TONES.woodLight, INKS.ochre, 0.1), id: timber.id }, { caps: true });
  D.sweep(new Vector3(lx, e - 0.2, -lz), new Vector3(-lx, e - 0.2, -lz), [[0, 0], [0.06, 0], [0.06, 0.26], [0, 0.26]], { color: mix(TONES.woodLight, INKS.ochre, 0.1), id: timber.id }, { caps: true });
  // the lantern: louvres outside, the light coming through them inside
  const louvre: Paint = { color: mix(TONES.wood, INKS.ink, 0.1), id: nextId(), pattern: PATTERN.ribs };
  const daylight: Paint = { color: mix(INKS.card, INKS.sunflower, 0.12), id: nextId(), pattern: PATTERN.ribs };
  D.box(0, r1 + lh / 2, 0, ix * 2, lh, iz * 2, louvre, { ny: false, py: false });
  const inner = (pts: number[]) => D.quadXYZ(pts, daylight);
  const y0 = r1 - 0.12;
  const y1 = r1 + lh;
  inner([-ix + 0.05, y0, iz - 0.05, -ix + 0.05, y1, iz - 0.05, ix - 0.05, y1, iz - 0.05, ix - 0.05, y0, iz - 0.05]);
  inner([ix - 0.05, y0, -iz + 0.05, ix - 0.05, y1, -iz + 0.05, -ix + 0.05, y1, -iz + 0.05, -ix + 0.05, y0, -iz + 0.05]);
  inner([ix - 0.05, y0, iz - 0.05, ix - 0.05, y1, iz - 0.05, ix - 0.05, y1, -iz + 0.05, ix - 0.05, y0, -iz + 0.05]);
  inner([-ix + 0.05, y0, -iz + 0.05, -ix + 0.05, y1, -iz + 0.05, -ix + 0.05, y1, iz - 0.05, -ix + 0.05, y0, iz - 0.05]);
  const top = y1;
  const ox = ix + 0.4;
  const oz = iz + 0.4;
  D.quadXYZ([-ox, top, oz, ox, top, oz, ox - 0.3, H, 0, -ox + 0.3, H, 0], zinc);
  D.quadXYZ([ox, top, -oz, -ox, top, -oz, -ox + 0.3, H, 0, ox - 0.3, H, 0], zinc);
  D.tri(new Vector3(ox, top, oz), new Vector3(ox, top, -oz), new Vector3(ox - 0.3, H, 0), zinc);
  D.tri(new Vector3(-ox, top, -oz), new Vector3(-ox, top, oz), new Vector3(-ox + 0.3, H, 0), zinc);
  // the lantern's ceiling, boarded, seen from the floor
  D.quadXYZ([-ox, top - 0.02, -oz, ox, top - 0.02, -oz, ox, top - 0.02, oz, -ox, top - 0.02, oz], boards);
  D.box(0, H, 0, ox * 2 - 0.5, 0.08, 0.14, zincTop);
  // the trusses: a tie beam across, two rafters under the slopes, the struts to the lantern
  const trusses = Math.max(3, Math.round(L / 8));
  for (let k = 0; k <= trusses; k++) {
    const x = -L / 2 + 0.6 + ((L - 1.2) * k) / trusses;
    D.box(x, eave - 0.1, 0, 0.2, 0.25, Wd, timber);
    for (const sz of [-1, 1]) {
      D.bar(new Vector3(x, e - 0.25, sz * (Wd / 2)), new Vector3(x, r1 - 0.25, sz * iz), 0.2, timber);
      D.bar(new Vector3(x, eave - 0.1, sz * (Wd / 4)), new Vector3(x, e - 0.25 + ((r1 - e) * (Wd / 4)) / (Wd / 2 - iz), sz * (Wd / 4)), 0.14, timber);
    }
  }
  D.pop();
  // globes for the dark corners
  for (let k = -2; k <= 2; k += 2) {
    const p = toWorld(m, (k * L) / 6, eave - 0.6, 0);
    D.ball(p.x, p.y, p.z, 0.22, 0.22, 0.22, { color: mix(INKS.sunflower, INKS.card, 0.4), glow: 1, id: nextId() }, 1);
    B.lamps.push({ pos: p, color: rgb(mix(INKS.sunflower, INKS.card, 0.35)), power: 0.8, range: 9, glint: false, indoor: true });
  }
  blocks.forEach((sh) =>
    B.blocks.push(
      sh.map(([x, z]) => {
        const w = toWorld(m, x, 0, z);
        return [w.x, w.z] as [number, number];
      }),
    ),
  );
  // the counters: rows along x; the wall's row faces in, then islands of two rows back to back
  const rows: Array<{ z: number; face: number }> = [];
  for (const side of [-1, 1]) {
    const wall = Wd / 2 - 1.9;
    rows.push({ z: side * wall, face: -side });
    let edge = wall - 0.55;
    for (;;) {
      const outer = edge - 3.2 - 0.55;
      const inner = outer - 2.5;
      // the middle aisle runs from the end doors, so it keeps their width
      if (inner - 0.55 < 1.9) break;
      rows.push({ z: side * outer, face: side });
      rows.push({ z: side * inner, face: -side });
      edge = inner - 0.55;
    }
  }
  const kinds: GoodsKind[] = ['fromages', 'olives', 'legumes', 'fruits', 'fleurs', 'fromages', 'legumes', 'olives', 'fruits'];
  const sw = 3.0;
  // from the cross aisle to an aisle along each end wall
  const half = Math.max(0, Math.floor((L / 2 - 2.4 - 3.4) / sw));
  const stalls: StallInfo[] = [];
  let k = 0;
  rows.forEach((row) => {
    for (const end of [-1, 1]) {
      for (let i = 0; i < half; i++) {
        const x = end * (2.4 + sw / 2 + i * sw);
        const p = toWorld(m, x, 0, row.z);
        const facing = new Vector3(0, 0, row.face).transformDirection(m);
        const rot = Math.atan2(facing.x, facing.z);
        stalls.push(stall(B, p.x, p.z, rot, sw - 0.15, kinds[(seed + k * 5 + Math.abs(Math.round(row.z))) % kinds.length], seed + 100 + k, KERB + 0.02, false, 1));
        k++;
      }
    }
  });
  const corners = [toWorld(m, -L / 2, 0, -Wd / 2), toWorld(m, L / 2, 0, Wd / 2), toWorld(m, -L / 2, 0, Wd / 2), toWorld(m, L / 2, 0, -Wd / 2)];
  const room: [number, number, number, number] = [
    Math.min(...corners.map((c) => c.x)),
    Math.min(...corners.map((c) => c.z)),
    Math.max(...corners.map((c) => c.x)),
    Math.max(...corners.map((c) => c.z)),
  ];
  return { kind: 'halle', name: l.name, room, stalls, doors, center: toWorld(m, 0, 0, 0) };
}

/** A small pavilion on a square: stone, a door, two windows, a pyramid of zinc and a finial. */
export function pavillon(B: Build, l: LandmarkSpec): LandmarkBuilt {
  const D = B.dry;
  const m = frameOf(l);
  const L = l.len;
  const Wd = l.wid;
  const wallH = 3.3;
  const H = Math.max(wallH + 1.6, l.height ?? 5.5);
  const stone: Paint = { color: mix(TONES.stoneLight, INKS.ochre, 0.06), id: nextId(), pattern: PATTERN.courses };
  D.push(m);
  D.block(0, 0, 0, L, wallH, Wd, stone);
  D.box(0, wallH + 0.12, 0, L + 0.3, 0.24, Wd + 0.3, { color: mix(TONES.stoneLight, INKS.paper, 0.2), id: stone.id }, { ny: false });
  const zinc: Paint = { color: TONES.zinc, id: nextId(), pattern: PATTERN.seams };
  const y0 = wallH + 0.24;
  const ex = L / 2 + 0.2;
  const ez = Wd / 2 + 0.2;
  D.tri(new Vector3(-ex, y0, ez), new Vector3(ex, y0, ez), new Vector3(0, H, 0), zinc);
  D.tri(new Vector3(ex, y0, ez), new Vector3(ex, y0, -ez), new Vector3(0, H, 0), zinc);
  D.tri(new Vector3(ex, y0, -ez), new Vector3(-ex, y0, -ez), new Vector3(0, H, 0), zinc);
  D.tri(new Vector3(-ex, y0, -ez), new Vector3(-ex, y0, ez), new Vector3(0, H, 0), zinc);
  D.cylinder(0, H - 0.05, 0, 0.05, 0.02, 0.6, 6, { color: TONES.iron, id: nextId() }, { flat: true });
  // a door on each long side, windows on the ends
  const wood: Paint = { color: mix(INKS.green, INKS.ink, 0.25), id: nextId() };
  for (const s of [-1, 1]) {
    D.box(0, 1.15, s * (Wd / 2 + 0.01), 1.2, 2.3, 0.04, wood, { nz: s > 0 ? false : true, pz: s > 0 });
    D.box(s * (L / 2 + 0.01), 1.8, 0, 0.04, 1.3, 1.0, { color: TONES.pane, wet: 0.5, id: nextId() });
  }
  D.pop();
  const corners = [toWorld(m, -L / 2, 0, -Wd / 2), toWorld(m, L / 2, 0, -Wd / 2), toWorld(m, L / 2, 0, Wd / 2), toWorld(m, -L / 2, 0, Wd / 2)];
  B.blocks.push(corners.map((c) => [c.x, c.z] as [number, number]));
  return { kind: 'pavillon', name: l.name, room: null, stalls: [], doors: [], center: toWorld(m, 0, 0, 0) };
}

/** The hoarding where the walkable world ends: green boards on concrete feet, a notice now and then. */
export function hoarding(B: Build, pts: Array<[number, number]>, seed: number) {
  const D = B.dry;
  const board: Paint = { color: mix(INKS.green, INKS.ink, 0.28), id: nextId(), pattern: PATTERN.seams };
  const band: Paint = { color: INKS.card, id: board.id };
  const foot: Paint = { color: mix(TONES.curb, INKS.ink, 0.1), id: nextId() };
  let n = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, z0] = pts[i];
    const [x1, z1] = pts[i + 1];
    const len = Math.hypot(x1 - x0, z1 - z0);
    if (len < 0.05) continue;
    const angle = Math.atan2(-(z1 - z0), x1 - x0);
    const panels = Math.max(1, Math.round(len / 2.0));
    for (let k = 0; k < panels; k++) {
      const t = (k + 0.5) / panels;
      const cx = x0 + (x1 - x0) * t;
      const cz = z0 + (z1 - z0) * t;
      const pw = len / panels;
      D.at(cx, KERB, cz, angle, () => {
        D.box(0, 1.15, 0, pw - 0.02, 2.2, 0.05, board);
        D.box(0, 2.18, 0, pw - 0.02, 0.06, 0.07, band);
        D.block(-pw / 2 + 0.2, -KERB, 0, 0.35, 0.2, 0.6, foot);
      });
      if ((n + seed) % 4 === 0 && pw > 1.5) {
        // the same notice on every fourth board, both faces: printed once
        for (const side of [-1, 1]) {
          const nx = Math.sin(angle) * side;
          const nz = Math.cos(angle) * side;
          B.signs.push({ key: 'chantier', center: new Vector3(cx + nx * 0.035, KERB + 1.35, cz + nz * 0.035), normal: new Vector3(nx, 0, nz), width: 1.3, height: 0.74, density: 140, draw: noticeArt() });
        }
      }
      n++;
    }
    B.blocks.push(boxShape((x0 + x1) / 2, (z0 + z1) / 2, len + 0.3, 0.5, angle));
  }
}

/** The hoarding's notice: the city being drawn, in the paper's voice. */
function noticeArt() {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = '#f8f3e8';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#2c6a5d';
    ctx.fillRect(0, 0, w, h * 0.3);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#f8f3e8';
    const sans = "700 {s}px AtelierSans, 'Instrument Sans', system-ui, sans-serif";
    let s = fitText(ctx, 'CHANTIER', w * 0.8, Math.round(h * 0.2), sans);
    ctx.font = sans.replace('{s}', String(s));
    ctx.fillText('CHANTIER', w / 2, h * 0.16);
    ctx.fillStyle = '#14110d';
    const serif = "italic 500 {s}px AtelierSerif, 'EB Garamond', Georgia, serif";
    s = fitText(ctx, 'Ici, la ville se dessine encore.', w * 0.88, Math.round(h * 0.17), serif);
    ctx.font = serif.replace('{s}', String(s));
    ctx.fillText('Ici, la ville se dessine encore.', w / 2, h * 0.52);
    s = fitText(ctx, 'Le Quartier · prochainement', w * 0.8, Math.round(h * 0.11), sans);
    ctx.font = sans.replace('{s}', String(s));
    ctx.fillText('Le Quartier · prochainement', w / 2, h * 0.78);
  };
}

/** A bicycle hoop: one bent tube, set in the pavement. */
export function hoop(B: Build, x: number, z: number, rot: number, y = KERB) {
  const iron: Paint = { color: mix(TONES.iron, INKS.paper, 0.15), id: nextId() };
  B.dry.at(x, y, z, rot, () => {
    B.dry.bar(new Vector3(-0.35, 0, 0), new Vector3(-0.35, 0.65, 0), 0.05, iron);
    B.dry.bar(new Vector3(0.35, 0, 0), new Vector3(0.35, 0.65, 0), 0.05, iron);
    B.dry.bar(new Vector3(-0.38, 0.68, 0), new Vector3(0.38, 0.68, 0), 0.05, iron);
  });
  B.blocks.push(boxShape(x, z, 0.8, 0.2, rot));
}

/** A glass bin: a green column with a dome and two round mouths. */
export function glassBin(B: Build, x: number, z: number, y = KERB) {
  const p: Paint = { color: mix(INKS.green, INKS.ink, 0.2), id: nextId() };
  B.dry.lathe(x, y, z, [[0.62, 0], [0.62, 1.15], [0.58, 1.3], [0.4, 1.5], [0.12, 1.6], [0, 1.62]], 12, p);
  B.dry.ball(x, y + 1.62, z, 0.08, 0.06, 0.08, { color: INKS.ink, id: nextId() }, 0);
  B.blocks.push(circle(x, z, 0.7));
}

/** A yellow post box on its post. */
export function postBox(B: Build, x: number, z: number, rot: number, y = KERB) {
  const yellow: Paint = { color: INKS.sunflower, id: nextId() };
  B.dry.at(x, y, z, rot, () => {
    B.dry.cylinder(0, 0, -0.05, 0.05, 0.05, 0.9, 6, { color: TONES.iron, id: nextId() }, { flat: true });
    B.dry.box(0, 1.15, 0, 0.42, 0.5, 0.28, yellow);
    B.dry.box(0, 1.42, 0, 0.46, 0.06, 0.32, { color: mix(INKS.sunflower, INKS.ink, 0.2), id: yellow.id });
    B.dry.box(0, 1.26, 0.145, 0.24, 0.03, 0.01, { color: INKS.ink, id: nextId() });
  });
  B.blocks.push(circle(x, z, 0.3));
}
