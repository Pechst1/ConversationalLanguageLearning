/**
 * Le Quartier · the forge's camera: one forged place on its own, for a script to photograph.
 * `forge-render.mjs` bundles this, puts the site in the page as `window.__SITE`, and drives it
 * through `window.__forge`: the places to look from are chosen here, from the site itself, so a
 * new place is photographed the same way as the last one.
 */
import { Vector3 } from 'three';

import { figureArt, itemArt } from '../../lib/quartier/cast-art';
import { Course } from '../../lib/quartier/course';
import { Crowd } from '../../lib/quartier/crowd';
import { Quartier } from '../../lib/quartier/engine';
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
}

const site = (window as unknown as { __SITE: SiteSpec }).__SITE;
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
  resolution: 'fixed',
  scale: 1,
});

/** A point you can stand on near (x, z), or the point itself. */
function ground(x: number, z: number) {
  const p = q.nav.nearest(x, z, 8);
  return p ? new Vector3(p[0], 0, p[1]) : new Vector3(x, 0, z);
}

function views(): View[] {
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
    // lived in and the frame's cost counts them all
    const director = q.site?.spec.venue ? new Course(q) : new Visit(q);
    await director.prepare();
    if (director instanceof Visit) await director.full;
    const crowd = new Crowd(q, { count: 24, seed: 1789, spots: q.site?.spec.spots });
    await crowd.load();
    const peopleMs = Math.round(performance.now() - t0) - loadMs;
    const list = views();
    const show = (i: number) => {
      const v = list[i];
      q.eyeHeight = v.eye ?? 1.62;
      q.fogOverride = v.clear ? [900, 2400] : null;
      q.setAmbiance(q.ambiance);
      q.place(v.pos, v.look);
      for (let k = 0; k < 4; k++) q.renderOnce(performance.now() + k * 16);
      return { ...q.stats };
    };
    Object.assign(window, { __forge: { ready: true, loadMs, peopleMs, views: list.map((v) => v.name), show } });
  })
  .catch((e) => {
    Object.assign(window, { __forge: { ready: false, error: e instanceof Error ? `${e.message}\n${e.stack}` : String(e) } });
  });
