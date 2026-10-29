/**
 * Le Quartier · the forge's camera: one forged place on its own, for a script to photograph.
 * `forge-render.mjs` bundles this, puts the site (or the room) in the page as `window.__SITE`, and
 * drives it through `window.__forge`: the places to look from are chosen here, from the place
 * itself, so a new place is photographed the same way as the last one. A room is photographed the
 * way the stage walks you through it: in the dark as you come in, lit, from each of its marks to
 * the next, up and down its flights, at its windows and its doors, and the door the story opens,
 * open, as the stage frames it.
 */
import { Vector3 } from 'three';

import { figureArt, itemArt } from '../../lib/quartier/cast-art';
import { Course } from '../../lib/quartier/course';
import { Crowd } from '../../lib/quartier/crowd';
import { Quartier } from '../../lib/quartier/engine';
import type { RoomBuilt, RoomSpec } from '../../lib/quartier/room';
import type { SiteSpec } from '../../lib/quartier/site';
import { Visit } from '../../lib/quartier/visit';

interface View {
  name: string;
  pos: Vector3;
  look: Vector3;
  /** eyes this high above the ground (a look from above, for the plan) */
  eye?: number;
  /** no haze */
  clear?: boolean;
  /** a room's lamps gone out */
  dark?: boolean;
  /** a room's door standing open, by its key */
  open?: string;
  /** the lens, if not the eye's 60 */
  fov?: number;
  /** nothing above this height is drawn (a plan, cut under the ceiling) */
  cut?: number;
}

const forged = (window as unknown as { __SITE: SiteSpec | RoomSpec }).__SITE;
const room = (forged as RoomSpec).kind === 'room' ? (forged as RoomSpec) : undefined;
const site = room ? undefined : (forged as SiteSpec);
const canvas = document.createElement('canvas');
canvas.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;display:block';
document.body.style.margin = '0';
document.body.appendChild(canvas);

const q = new Quartier({
  canvas,
  art: {
    figure: (k, e, g) => figureArt(k, { expression: e as never, gesture: g as never, size: 600 }),
    item: (id) => itemArt(id as never, 512),
  },
  site,
  room,
  resolution: 'fixed',
  scale: 1,
});

/** A point you can stand on near (x, z), or the point itself. */
function ground(x: number, z: number) {
  const p = q.nav.nearest(x, z, 8);
  return p ? new Vector3(p[0], 0, p[1]) : new Vector3(x, 0, z);
}

const STEP: Record<RoomSpec['flights'][number]['dir'], [number, number]> = { 'x+': [1, 0], 'x-': [-1, 0], 'z+': [0, 1], 'z-': [0, -1] };

/** From `p` along `dir`, up to `max` metres, as far as the floor carries you (no wall, no drop). */
function stepBack(p: Vector3, dir: Vector3, max: number) {
  let at = new Vector3(p.x, 0, p.z);
  let y = q.nav.heightAt(p.x, p.z);
  for (let d = 0.1; d <= max + 1e-6; d += 0.1) {
    const c = new Vector3(p.x + dir.x * d, 0, p.z + dir.z * d);
    const h = q.nav.heightAt(c.x, c.z);
    if (!q.nav.walkable(c.x, c.z) || Math.abs(h - y) > 0.25) break;
    at = c;
    y = h;
  }
  return at;
}

/** A room, as the stage walks you through it. */
function roomViews(r: RoomBuilt): View[] {
  const s = r.spec;
  const out: View[] = [
    { name: 'arrivee-noir', pos: r.start.pos, look: r.start.look, dark: true },
    { name: 'arrivee', pos: r.start.pos, look: r.start.look },
  ];
  // from each mark you stand on to the next, where they are a few steps apart
  const onGround = (p: Vector3) => Math.abs(p.y - q.nav.heightAt(p.x, p.z)) < 0.3;
  const marks = Object.entries(r.marks);
  marks.forEach(([key, p], i) => {
    const next = marks[i + 1]?.[1];
    if (next && onGround(p) && onGround(next) && Math.hypot(next.x - p.x, next.z - p.z) > 1.5) {
      out.push({ name: key, pos: p, look: new Vector3(next.x, next.y + 1.5, next.z) });
    }
  });
  // what the room's things say (the letterboxes' names), read from a step away
  s.things.forEach((t, i) => {
    if (!t.text?.length || (t.zone ?? 'room') !== 'room') return;
    const at = new Vector3(t.at[0], t.at[1], t.at[2]);
    const facing = new Vector3(Math.sin(t.rot ?? 0), 0, Math.cos(t.rot ?? 0));
    out.push({ name: `${t.kind}-${i}`, pos: stepBack(at.clone().addScaledVector(facing, 0.45), facing, 0.8), look: at });
  });
  // down each flight from its top
  for (const f of s.flights) {
    const [dx, dz] = STEP[f.dir];
    const run = (f.risers - 1) * f.tread;
    out.push({
      name: `${f.key}-haut`,
      pos: new Vector3(f.from[0] + dx * (run + 0.6), f.y1, f.from[1] + dz * (run + 0.6)),
      look: new Vector3(f.from[0] - dx * 0.9, f.y0 + 0.6, f.from[1] - dz * 0.9),
    });
  }
  // at each window of the room itself (a sealed room's are seen through its door), from where
  // your eyes come nearest the middle of the glass
  for (const w of s.windows) {
    const wall = s.walls[w.wall];
    if (!wall || (wall.zone ?? 'room') !== 'room') continue;
    const len = Math.hypot(wall.b[0] - wall.a[0], wall.b[1] - wall.a[1]) || 1;
    const t = [(wall.b[0] - wall.a[0]) / len, (wall.b[1] - wall.a[1]) / len];
    const u = (w.u0 + w.u1) / 2;
    const c = new Vector3(wall.a[0] + t[0] * u, (w.y0 + w.y1) / 2, wall.a[1] + t[1] * u);
    let best: { at: Vector3; miss: number } | null = null;
    for (let d = 0.6; d <= 2.6; d += 0.1) {
      const p = new Vector3(c.x - t[1] * d, 0, c.z + t[0] * d);
      if (!q.nav.walkable(p.x, p.z)) continue;
      const miss = Math.abs(q.nav.heightAt(p.x, p.z) + 1.62 - c.y) + Math.abs(d - 1.6) * 0.2;
      if (!best || miss < best.miss) best = { at: p, miss };
    }
    if (best) out.push({ name: w.key, pos: best.at, look: c });
  }
  // before each door, and the door the story opens standing open, from its threshold
  for (const o of r.openings) {
    const away = o.front.clone().sub(o.centre).setY(0).normalize();
    out.push({ name: o.key, pos: stepBack(o.centre.clone().addScaledVector(away, 0.35), away, 1.0), look: o.centre });
    if (o.opens === 'once') {
      const from = r.marks.threshold ?? o.centre.clone().addScaledVector(away, 0.2);
      const look = r.marks.inside ?? o.centre.clone().addScaledVector(away, -2.5);
      out.push({ name: `${o.key}-ouverte`, pos: from, look, open: o.key, fov: 52 });
    }
  }
  // and a plan of each floor, from above, cut under what is over it (the floor above, a ceiling)
  const seen = s.floors.filter((f) => (f.zone ?? 'room') !== 'out');
  const pts = seen.flatMap((f) => f.shape);
  const xs = pts.map((p) => p[0]);
  const zs = pts.map((p) => p[1]);
  const mid = new Vector3((Math.min(...xs) + Math.max(...xs)) / 2, 0, (Math.min(...zs) + Math.max(...zs)) / 2);
  const reach = (Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs)) / 2 + 0.8) / Math.tan(Math.PI / 6);
  const levels = seen
    .filter((f) => (f.zone ?? 'room') === 'room' && f.walk !== false)
    .map((f) => f.y)
    .filter((y, i, all) => all.indexOf(y) === i)
    .sort((a, b) => a - b);
  const ground = q.nav.heightAt(mid.x, mid.z);
  levels.forEach((y, i) => {
    const over = [...s.ceilings.map((c) => c.y), ...s.floors.map((f) => f.y - 0.4)].filter((h) => h > y + 0.5);
    const cut = Math.min(...over, y + 3.2) - 0.08;
    out.push({ name: `plan-${i}`, pos: mid.clone().add(new Vector3(0, 0, 0.01)), look: mid.clone().setY(y), eye: y + reach - ground, clear: true, cut });
  });
  return out;
}

function views(): View[] {
  if (q.room) return roomViews(q.room);
  const s = q.site;
  if (!s) return [];
  const out: View[] = [{ name: 'arrivee', pos: s.start.pos, look: s.start.look }];
  s.landmarks.forEach((l, i) => {
    const c = l.center;
    if (l.doors.length) {
      // from the square, the hall's front with its name over the door
      const d = l.doors[0];
      const away = d.clone().sub(c).setY(0).normalize();
      out.push({ name: `${l.kind}-${i}-dehors`, pos: ground(d.x + away.x * 12, d.z + away.z * 12), look: new Vector3(c.x, 4.5, c.z) });
    }
    if (l.room) {
      const spec = s.spec.landmarks[i];
      out.push({ name: `${l.kind}-${i}-dedans`, pos: ground(c.x + spec.u[0] * spec.len * 0.3, c.z + spec.u[1] * spec.len * 0.3), look: new Vector3(c.x - spec.u[0] * spec.len, 1.5, c.z - spec.u[1] * spec.len) });
    }
    if (!l.doors.length && !l.room) out.push({ name: `${l.kind}-${i}`, pos: ground(c.x + 9, c.z + 9), look: new Vector3(c.x, 2.5, c.z) });
  });
  const food = s.stalls.filter((x) => ['fruits', 'legumes', 'fleurs', 'olives', 'fromages'].indexOf(x.goods) >= 0);
  if (food.length > 1) {
    const a = food[0].front;
    const b = food[Math.min(food.length - 1, 7)].front;
    out.push({ name: 'marche-rue', pos: ground(a.x, a.z), look: new Vector3(b.x, 1.4, b.z) });
    const m = food[Math.floor(food.length / 2)];
    out.push({ name: 'etal', pos: ground(m.front.x + m.facing.x * 1.2, m.front.z + m.facing.z * 1.2), look: new Vector3(m.front.x - m.facing.x * 0.6, 0.95, m.front.z - m.facing.z * 0.6) });
  }
  const odd = s.stalls.filter((x) => food.indexOf(x) < 0);
  if (odd.length) {
    const m = odd[0];
    out.push({ name: 'brocante', pos: ground(m.front.x + m.facing.x * 2.5, m.front.z + m.facing.z * 2.5), look: new Vector3(m.front.x, 0.9, m.front.z) });
  }
  const fence = s.spec.fences[0];
  if (fence) {
    const mid = fence[Math.floor(fence.length / 2)];
    const r = Math.hypot(mid[0], mid[1]) || 1;
    out.push({ name: 'bord', pos: ground(mid[0] * (1 - 10 / r), mid[1] * (1 - 10 / r)), look: new Vector3(mid[0], 1.6, mid[1]) });
  }
  // and from above, without the haze: the plan as you would never see it walking
  out.push({ name: 'vue-haute', pos: new Vector3(0, 0, 0.5), look: new Vector3(0, 0, 0), eye: 330, clear: true });
  out.push({ name: 'vue-oblique', pos: new Vector3(-95, 0, 120), look: new Vector3(0, 0, 0), eye: 95, clear: true });
  return out;
}

const t0 = performance.now();
q.load()
  .then(async () => {
    const loadMs = Math.round(performance.now() - t0);
    // whoever the place's director stands up (behind the stalls, at the window), as a player
    // finds them, and the people of the place walking its own spots, so the photographs show it
    // lived in and the frame's cost counts them all; a room of the season has nobody yet
    if (q.site) {
      const director = q.site.spec.venue ? new Course(q) : new Visit(q);
      await director.prepare();
      if (director instanceof Visit) await director.full;
      const crowd = new Crowd(q, { count: 24, seed: 1789, spots: q.site.spec.spots });
      await crowd.load();
    }
    const peopleMs = Math.round(performance.now() - t0) - loadMs;
    const list = views();
    const show = (i: number) => {
      const v = list[i];
      q.eyeHeight = v.eye ?? 1.62;
      q.fogOverride = v.clear ? [900, 2400] : null;
      if (q.room) {
        q.setRoomLight(v.dark ? 0 : 1);
        for (const o of q.room.openings) q.openDoor(o.key === v.open, o.key);
      }
      q.setAmbiance(q.ambiance);
      q.lens(v.fov ?? 60);
      q.place(v.pos, v.look);
      // a plan looks straight down, so the near plane is level: it cuts the room under its ceiling
      q.camera.near = v.cut !== undefined ? Math.max(0.1, q.camera.position.y - v.cut) : 0.1;
      q.camera.updateProjectionMatrix();
      // a room's door swings and the lens eases for a second or two: let them settle
      const frames = q.room ? 30 : 4;
      const t = performance.now();
      for (let k = 0; k < frames; k++) q.renderOnce(t + k * (q.room ? 100 : 16));
      return { ...q.stats };
    };
    Object.assign(window, { __forge: { ready: true, loadMs, peopleMs, views: list.map((v) => v.name), show } });
  })
  .catch((e) => {
    Object.assign(window, { __forge: { ready: false, error: e instanceof Error ? `${e.message}\n${e.stack}` : String(e) } });
  });
