/**
 * Le Quartier · the passers-by: the neighbourhood going about its evening.
 *
 * A quarter with only the cast in it is a stage set. These are the people of the street, drawn by
 * the app's own avatar kit from a seed (the jointed figures the learner builds a Toi from), so the
 * same evening has the same faces in it. Each one keeps a habit: up and down the quai, across the
 * footbridge, a stop at the canal's edge to look at the water, a turn into the rue de Lancry. They
 * keep to the pavements (`Nav`), carry an umbrella when it rains, and when you pass close one of
 * them may say something: the crowd only says who is near, the director picks the line
 * (`Stage.passerby`). Tap one and they turn to you.
 *
 * They are printed small and after the rest of the quarter, so they never hold up the first
 * frame; the street fills as their cards come out of the press.
 */
import { Group, Vector3 } from 'three';

import { passerbyArt } from './cast-art';
import { Troupe } from './cast';
import type { PaperFigure } from './cast';
import type { Quartier } from './engine';
import { Press, seeded } from './geo';
import type { Rand } from './geo';
import { AMBIANCES, INKS, mix } from './palette';
import type { Hex } from './palette';

/** Where people go, as [x, z] on the quai (`quai.ts` PLAN), and how long some of them stay. */
export interface CrowdSpot {
  at: [number, number];
  /** seconds someone may stand here */
  linger?: [number, number];
}

const SPOTS: CrowdSpot[] = [
  // the quai de Valmy's pavement, north to south, past Le Mistral's door
  { at: [-25.6, -66] },
  { at: [-25.6, -36] },
  { at: [-25.6, -15] },
  { at: [-25.6, 11] },
  { at: [-25.6, 36] },
  { at: [-25.6, 64] },
  // the canal side under the plane trees; at the edge people stop and look at the water
  { at: [-13.4, -60] },
  { at: [-11.3, -28], linger: [5, 11] },
  { at: [-13.4, -4] },
  { at: [-11.3, 24], linger: [6, 13] },
  { at: [-13.4, 50] },
  // the rue de Lancry, both pavements
  { at: [-44, 4.9] },
  { at: [-66, -4.9] },
  // the footbridge, where everyone slows down
  { at: [0, -46], linger: [3, 7] },
  // the quai de Jemmapes, across the water
  { at: [25.6, -32] },
  { at: [25.6, 12] },
  { at: [13.4, 40] },
];

const UMBRELLAS: Hex[] = [INKS.ink, mix(INKS.vermilion, INKS.ink, 0.25), INKS.cobalt, mix(INKS.green, INKS.ink, 0.2), INKS.ochre, mix(INKS.cobalt, INKS.ink, 0.45)];

/**
 * A canopy over the head and its shaft down to the hand, in the print's own inks. It turns with
 * the card, so the shaft stays beside the body, held a little in front of it, never across the face.
 */
function umbrellaPress(color: Hex, height: number) {
  const P = new Press();
  const cloth = { color, id: 61, shade: 0.1 };
  const rod = { color: INKS.ink, id: 62 };
  const x = 0.23;
  const z = 0.07;
  const rim = height + 0.04;
  P.lathe(x * 0.5, rim, z, [[0, 0.3], [0.32, 0.2], [0.52, 0.07], [0.56, 0]], 8, cloth, { flat: true });
  P.lathe(x * 0.5, rim - 0.001, z, [[0.56, 0], [0.4, 0.07], [0, 0.12]], 8, { ...cloth, shade: 0.45 }, { flat: true });
  P.bar(new Vector3(x * 0.5, rim + 0.36, z), new Vector3(x, height * 0.58, z), 0.022, rod);
  return P;
}

interface Walker {
  key: string;
  f: PaperFigure;
  R: Rand;
  /** metres a second */
  pace: number;
  /** seconds left standing where they are */
  wait: number;
  /** how long to stand once they get where they are going */
  then: number;
  walked: boolean;
  umbrella: Group;
  /** a tap: they stop and face you until then */
  heldUntil: number;
}

export interface CrowdOptions {
  /** how many people the street holds */
  count?: number;
  seed?: number;
  /** someone is within reach of you (the director decides whether they speak) */
  onNear?: (key: string) => void;
  /** where people go (a forged place brings its own); the quai's by default */
  spots?: CrowdSpot[];
}

export class Crowd {
  readonly troupe: Troupe;
  private walkers: Walker[] = [];
  private stopTick: (() => void) | null = null;
  private disposed = false;
  private count: number;
  private seed: number;
  private onNear?: (key: string) => void;
  private spots: CrowdSpot[];

  constructor(private q: Quartier, opts: CrowdOptions = {}) {
    this.count = opts.count ?? 10;
    this.seed = opts.seed ?? 1789;
    this.onNear = opts.onNear;
    this.spots = opts.spots && opts.spots.length ? opts.spots : SPOTS;
    this.troupe = new Troupe(q.world, { figure: (key) => passerbyArt(Number(key.split(':')[1]) * 7919 + this.seed, 256), item: () => null }, 420);
    q.addTroupe(this.troupe);
  }

  /** Print the passers-by one at a time, each walking off as soon as their card is ready. */
  async load() {
    const R = seeded(this.seed);
    for (let i = 0; i < this.count && !this.disposed; i++) {
      const key = `passant:${i}`;
      const spots = this.spots;
      const spot = spots[(i * 5 + R.int(0, spots.length - 1)) % spots.length];
      const at = this.ground(spot.at[0] + R.range(-1.5, 1.5), spot.at[1] + R.range(-4, 4));
      if (!at) continue;
      const height = R.range(1.56, 1.9);
      let f: PaperFigure | null = null;
      try {
        f = await this.troupe.add({ key, height }, at);
      } catch {
        continue;
      }
      if (!f || this.disposed) return;
      const umbrella = this.q.inked(umbrellaPress(R.pick(UMBRELLAS), height)) as unknown as Group;
      umbrella.visible = false;
      f.root.add(umbrella);
      this.walkers.push({ key, f, R: seeded(this.seed + i * 131), pace: R.range(0.95, 1.45), wait: R.range(0, 3), then: 0, walked: false, umbrella, heldUntil: 0 });
      if (!this.stopTick) this.stopTick = this.q.onTick((dt, now) => this.update(dt, now));
      // let a frame go by between prints, so the street never stutters
      await new Promise((r) => setTimeout(r, 30));
    }
  }

  /** Tapped: they stop, give a little start, and look at you a moment. */
  hop(key: string) {
    const w = this.walkers.find((x) => x.key === key);
    if (!w) return;
    w.f.hop();
    w.heldUntil = performance.now() + 2600;
    if (w.f.walking) {
      w.f.walk([]);
      w.walked = false;
      w.wait = 2.6;
    }
  }

  dispose() {
    this.disposed = true;
    this.stopTick?.();
    this.q.removeTroupe(this.troupe);
    this.troupe.dispose();
    this.walkers = [];
  }

  private ground(x: number, z: number) {
    const p = this.q.nav.nearest(x, z, 4);
    return p ? new Vector3(p[0], this.q.nav.heightAt(p[0], p[1]), p[1]) : null;
  }

  private update(dt: number, now: number) {
    const rain = AMBIANCES[this.q.ambiance].rain;
    const cam = this.q.camera.position;
    const feet = this.q.feet;
    const clock = performance.now();
    this.walkers.forEach((w) => {
      const f = w.f;
      // arrived: stand a while
      if (w.walked && !f.walking) {
        w.walked = false;
        w.wait = w.then || w.R.range(0.3, 2.2);
      }
      if (!f.walking && clock > w.heldUntil) {
        w.wait -= dt;
        if (w.wait <= 0) this.wander(w);
      }
      // far away, nobody: the card is not drawn
      const d = Math.hypot(f.pos.x - cam.x, f.pos.z - cam.z);
      f.visible = d < 80;
      w.umbrella.visible = rain && f.visible && f.seat === 0;
      if (w.umbrella.visible) w.umbrella.rotation.y = Math.atan2(cam.x - f.pos.x, cam.z - f.pos.z);
      // close to you
      if (f.visible && Math.hypot(f.pos.x - feet.x, f.pos.z - feet.z) < 2.3) this.onNear?.(w.key);
    });
    void now;
  }

  /** Somewhere else to go: a spot not too far, by the pavements. */
  private wander(w: Walker) {
    const f = w.f;
    const near = this.spots.filter((s) => {
      const d = Math.hypot(s.at[0] - f.pos.x, s.at[1] - f.pos.z);
      return d > 6 && d < 70;
    });
    const spot = w.R.pick(near.length ? near : this.spots);
    const to = this.ground(spot.at[0] + w.R.range(-1.2, 1.2), spot.at[1] + w.R.range(-3, 3));
    if (!to) {
      w.wait = 1;
      return;
    }
    const from = this.ground(f.pos.x, f.pos.z) ?? f.pos.clone();
    const path = this.q.nav.path(from, to);
    if (!path || !path.length) {
      w.wait = 1.5;
      return;
    }
    f.walk([from, ...path], w.pace);
    w.walked = true;
    w.then = spot.linger ? w.R.range(spot.linger[0], spot.linger[1]) : 0;
  }
}
