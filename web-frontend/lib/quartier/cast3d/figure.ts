/**
 * Le Quartier · a person in the round, acting.
 *
 * It plays the paper figure's part (`../cast.ts`) with a body: it is placed and walks along a
 * path, talks, bows, hops, takes a face for every mood, sits when the stage seats it, and is
 * lit by the scene. Every frame its pose is built from layers over the person's resting
 * stance: breathing and a little sway at the person's own energy; the body language of the
 * mood (eased in); the walk; talking (the mouth's cells and small nods); a gesture; a bow; a
 * hop; sitting; and the head turning to whoever is speaking, or to you.
 */
import { Euler, Group, Matrix4, Mesh, PlaneGeometry, Sphere, Vector2, Vector3 } from 'three';
import type { Camera } from 'three';

import type { FigureSpec, Seat } from '../cast';
import { blotMaterial } from '../materials';
import type { World } from '../materials';
import { INKS, rgb } from '../palette';

import type { Cell, HeadPose } from './face';
import type { Model, Person } from './model';
import { buildModel, headCentre } from './model';
import type { Pose, Turn } from './pose';
import type { BoneName, Side } from './rig';
import { B, BONES } from './rig';

/* ---- poses as sums of turns --------------------------------------------------------------- */

function add(p: Pose, bone: BoneName, t: Turn, w = 1) {
  if (w === 0) return;
  const c = p[bone] ?? (p[bone] = [0, 0, 0]);
  c[0] += t[0] * w;
  c[1] += t[1] * w;
  c[2] += t[2] * w;
}

function addPose(p: Pose, q: Pose, w = 1) {
  BONES.forEach((b) => {
    const t = q[b];
    if (t) add(p, b, t, w);
  });
}

/** An arm's turns written for the right side, mirrored onto the left. */
function arm(side: Side, bone: 'arm' | 'fore' | 'hand' | 'clav', t: Turn): [BoneName, Turn] {
  const name = `${bone}${side}` as BoneName;
  return [name, side === 'R' ? t : [t[0], -t[1], -t[2]]];
}

function armPose(side: Side, turns: Partial<Record<'arm' | 'fore' | 'hand' | 'clav', Turn>>): Pose {
  const p: Pose = {};
  (['clav', 'arm', 'fore', 'hand'] as const).forEach((k) => {
    const t = turns[k];
    if (t) {
      const [name, turn] = arm(side, k, t);
      p[name] = turn;
    }
  });
  return p;
}

const smoothstep = (e0: number, e1: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

/** In over the first share, out over the last. */
const envelope = (t: number, rise = 0.18, fall = 0.2) => (t <= 0 || t >= 1 ? 0 : smoothstep(0, rise, t) * (1 - smoothstep(1 - fall, 1, t)));

/* ---- the mood in the body ----------------------------------------------------------------- */

/**
 * What a mood or a gesture does: `body` turns are added to the stance; `arms` are where the
 * arms it moves go, in place of their resting turns (an arm that holds a glass at rest lets go
 * of that pose to wave).
 */
interface Move {
  body: Pose;
  arms: Pose;
}

const move = (): Move => ({ body: {}, arms: {} });

/** How each mood holds the body: the free arm is the one that gestures. */
function moodPose(expression: string, free: Side): Move {
  const m = move();
  const p = m.body;
  switch (expression) {
    case 'joie':
      add(p, 'chest', [-0.06, 0, 0]);
      add(p, 'head', [-0.05, 0, 0]);
      m.arms = armPose(free, { arm: [-0.12, 0, -0.12], fore: [-0.3, 0, 0] });
      break;
    case 'malice':
      add(p, 'chest', [0.02, 0.08, 0]);
      add(p, 'spine', [0, 0.04, 0.02]);
      break;
    case 'fier':
      add(p, 'chest', [-0.1, 0, 0]);
      add(p, 'head', [-0.1, 0, 0]);
      m.arms = armPose(free, { arm: [0.12, 0, 0.05], fore: [-0.1, 0, 0] });
      break;
    case 'surprise':
      add(p, 'chest', [-0.08, 0, 0]);
      add(p, 'head', [-0.06, 0, 0]);
      m.arms = armPose(free, { arm: [-0.35, 0, -0.3], fore: [-0.55, 0, 0], hand: [-0.3, 0, 0] });
      break;
    case 'panique':
      add(p, 'chest', [0.04, 0, 0]);
      add(p, 'clavL', [0, 0, 0.06]);
      add(p, 'clavR', [0, 0, -0.06]);
      m.arms = armPose(free, { arm: [-0.7, 0.2, -0.35], fore: [-1.3, 0, 0] });
      break;
    case 'fache':
      add(p, 'chest', [0.1, 0, 0]);
      add(p, 'head', [0.08, 0, 0]);
      add(p, 'clavL', [0, 0, 0.05]);
      add(p, 'clavR', [0, 0, -0.05]);
      m.arms = armPose(free, { arm: [-0.2, 0, -0.1], fore: [-0.9, 0, 0] });
      break;
    case 'emu':
      add(p, 'chest', [0.06, 0, 0]);
      add(p, 'head', [0.1, 0, 0]);
      m.arms = armPose(free, { arm: [-0.55, 0.55, 0.2], fore: [-2.0, 0, 0], hand: [0.2, 0, 0] });
      break;
    case 'amour':
      add(p, 'chest', [-0.04, 0, 0.03]);
      add(p, 'spine', [0, 0, 0.03]);
      break;
    case 'fatigue':
      add(p, 'spine', [0.1, 0, 0]);
      add(p, 'chest', [0.12, 0, 0]);
      add(p, 'head', [0.16, 0, 0]);
      break;
    default:
      break;
  }
  return m;
}

/* ---- gestures ----------------------------------------------------------------------------- */

interface Gesture {
  seconds: number;
  /** a share of the way through: how much of it shows, and the move for the free arm `g` */
  at: (t: number, g: Side) => Move & { w: number };
}

const GESTURES: Record<string, Gesture> = {
  // a hand up by the temple, a little wave
  salut: {
    seconds: 2.4,
    at: (t, g) => {
      const wave = Math.sin(t * Math.PI * 2 * 3) * smoothstep(0.2, 0.3, t) * (1 - smoothstep(0.7, 0.8, t));
      const m = { w: envelope(t, 0.2, 0.22), ...move() };
      m.arms = armPose(g, { arm: [-1.3, 0.1 + 0.32 * wave, -0.5], fore: [-1.85, 0, 0], hand: [0.2, 0, 0] });
      add(m.body, 'head', [-0.04, 0, 0]);
      return m;
    },
  },
  // a fist up in front, two pumps
  bravo: {
    seconds: 2.2,
    at: (t, g) => {
      const pump = Math.max(0, Math.sin(t * Math.PI * 2 * 2.2)) * smoothstep(0.15, 0.25, t) * (1 - smoothstep(0.7, 0.8, t));
      const m = { w: envelope(t, 0.16, 0.2), ...move() };
      m.arms = armPose(g, { arm: [-0.75, 0.3, 0.05], fore: [-1.75 - 0.25 * pump, 0, 0] });
      add(m.body, 'chest', [-0.05, 0, 0]);
      return m;
    },
  },
  // the hand to the mouth, the head down
  oups: {
    seconds: 2.6,
    at: (t, g) => {
      const m = { w: envelope(t, 0.16, 0.24), ...move() };
      m.arms = armPose(g, { arm: [-0.85, 0.62, 0.22], fore: [-2.2, 0, 0], hand: [0.15, 0, 0] });
      add(m.body, 'head', [0.14, 0, 0]);
      add(m.body, 'chest', [0.06, 0, 0]);
      return m;
    },
  },
  // the fist under the chin, the eyes up
  reflechit: {
    seconds: 3.2,
    at: (t, g) => {
      const m = { w: envelope(t, 0.16, 0.18), ...move() };
      m.arms = armPose(g, { arm: [-0.55, 0.75, 0.28], fore: [-2.35, 0, 0], hand: [0.25, 0, 0] });
      add(m.body, 'head', [-0.1, 0, g === 'R' ? 0.08 : -0.08]);
      add(m.body, 'chest', [0.03, 0, 0]);
      return m;
    },
  },
  // the hand held out to you, palm up
  montre: {
    seconds: 2.8,
    at: (t, g) => {
      const m = { w: envelope(t, 0.16, 0.18), ...move() };
      m.arms = armPose(g, { arm: [-0.95, -0.25, -0.12], fore: [-0.55, 0, 0], hand: [-0.15, 0.7, 0] });
      add(m.body, 'chest', [0.05, 0, 0]);
      return m;
    },
  },
  // the arm open, a flourish
  signature: {
    seconds: 3.0,
    at: (t, g) => {
      const lift = Math.sin(Math.min(1, t / 0.5) * Math.PI) * 0.15;
      const m = { w: envelope(t, 0.2, 0.22), ...move() };
      m.arms = armPose(g, { arm: [-0.55 - lift, -0.3, -0.65], fore: [-0.65, 0, 0], hand: [-0.2, 0.4, 0] });
      add(m.body, 'chest', [-0.07, 0, 0]);
      add(m.body, 'head', [-0.06, 0, 0]);
      return m;
    },
  },
};

/** Put a move's arms in place of what the pose has for them, by `w`. */
function blendArms(p: Pose, arms: Pose, w: number) {
  if (w <= 0) return;
  BONES.forEach((b) => {
    const t = arms[b];
    if (!t) return;
    const c = p[b] ?? (p[b] = [0, 0, 0]);
    c[0] += (t[0] - c[0]) * w;
    c[1] += (t[1] - c[1]) * w;
    c[2] += (t[2] - c[2]) * w;
  });
}

/* ---- the company: who is speaking, for the others to look at ------------------------------ */

interface Company {
  speaker: ModelFigure | null;
  until: number;
  /** everyone in the round in this world (whose seat is whose) */
  members: Set<ModelFigure>;
}
const companies = new WeakMap<World, Company>();
function companyOf(world: World): Company {
  let c = companies.get(world);
  if (!c) {
    c = { speaker: null, until: 0, members: new Set() };
    companies.set(world, c);
  }
  return c;
}

/* ---- the figure --------------------------------------------------------------------------- */

const TALK_CELLS: Cell[] = ['a', 'e', 'o', 'm', 'a', 'own', 'o', 'e', 'm'];
const e = new Euler();
const UP = new Vector3(0, 1, 0);
/** how far off (metres, give or take two) someone with a lighter body changes into it */
const FAR_OFF = 30;

export class ModelFigure {
  readonly key: string;
  readonly root = new Group();
  readonly model: Model;
  readonly person: Person;
  /** where the feet are */
  readonly pos = new Vector3();
  /** extra height (standing on the bench) */
  lift = 0;
  /** 0 standing; told to sit (the card's share sunk below the seat): a slump, or the nearest seat */
  seat = 0;
  /** a tilt in the plane facing you, set from outside (a rocking ride) */
  rock = 0;
  expression = 'neutre';
  gesture: string | null = null;
  visible = true;
  /** inside the café, for the warm shade */
  indoor = false;
  /** turns to face you when you are well off to one side; off, they hold their heading (a turntable) */
  attentive = true;

  private blot: Mesh;
  private scale = 1;
  private top = 1.7;
  private free: Side;
  private hold: Record<Side, number>;
  private rest: Pose;
  private company: Company;
  private path: Vector3[] = [];
  private speed = 1.25;
  private walkPhase = 0;
  private walkBlend = 0;
  private heading = 0;
  private turning = false;
  private talkUntil = 0;
  private leanAt = -10;
  private leanFor = 1.3;
  private leanDepth = 0.55;
  private hopAt = -10;
  private gestureAt = -10;
  private gestureId: string | null = null;
  private phase = Math.random() * 10;
  private blinkAt = 0;
  private blinkUntil = 0;
  private cell: Cell = 'own';
  private cellUntil = 0;
  private cellIndex = 0;
  private headPose: HeadPose = { tilt: 0, dx: 0, dy: 0 };
  /** the slow layers, eased toward their targets */
  private slow: Pose = {};
  private seatNow = 0;
  /** where people sit hereabouts, the one sat on (kept while getting up), and how far down */
  private seats: readonly Seat[];
  private sitOn: Seat | null = null;
  private lastSeat: Seat | null = null;
  private sitNow = 0;
  private sought = false;
  private drop = 0;
  private look = new Vector2();
  private snap = true;
  private away = false;

  /** `cell` is the face print's cell in pixels (smaller for the people of the street) */
  constructor(world: World, person: Person, spec: FigureSpec, opts: { variant?: string; seats?: readonly Seat[]; cell?: number } = {}) {
    this.key = spec.key;
    this.person = person;
    this.seats = opts.seats ?? [];
    this.model = buildModel(world, person, { variant: opts.variant, cell: opts.cell });
    this.company = companyOf(world);
    this.company.members.add(this);
    const geo = this.model.mesh.geometry;
    geo.computeBoundingBox();
    const natural = geo.boundingBox ? geo.boundingBox.max.y : person.body.height;
    this.scale = Math.min(1.12, Math.max(0.9, spec.height / natural));
    this.top = natural * this.scale;
    this.model.mesh.scale.setScalar(this.scale);
    // a sphere round any pose they take, so the renderer can leave out whoever is off screen
    // without skinning them to find out
    this.model.mesh.boundingSphere = new Sphere(new Vector3(0, natural * 0.5, 0), natural * 0.8);
    this.model.mesh.frustumCulled = true;
    this.root.add(this.model.mesh);
    const far = this.model.far;
    if (far) {
      far.scale.setScalar(this.scale);
      far.boundingSphere = this.model.mesh.boundingSphere.clone();
      far.frustumCulled = true;
      this.root.add(far);
    }
    this.blot = new Mesh(new PlaneGeometry(1, 1).rotateX(-Math.PI / 2), blotMaterial(rgb(INKS.ink), 0.5));
    this.blot.renderOrder = 2;
    this.blot.scale.set(0.62 * this.scale, 1, 0.4 * this.scale);
    this.blot.position.y = 0.012;
    this.root.add(this.blot);
    this.rest = person.manner?.rest ?? {};
    // bent arms carry something; the straighter one gestures
    const bend = (s: Side) => Math.abs((this.rest[`fore${s}` as BoneName] ?? [0, 0, 0])[0]);
    this.hold = { L: smoothstep(0.5, 1.1, bend('L')), R: smoothstep(0.5, 1.1, bend('R')) };
    this.free = bend('L') <= bend('R') ? 'L' : 'R';
    if (spec.silhouette) {
      const u = this.model.material.uniforms;
      u.uDark.value = 0.86;
      const s = rgb(INKS.ink);
      u.uSilhouette.value.set(s[0] * 1.2, s[1] * 1.25, s[2] * 1.7);
    }
    this.blinkAt = 1 + Math.random() * 3;
    this.express('neutre', null);
  }

  /** Stand here (or sit, on a seat's spot), turned to you at once. */
  place(p: Vector3) {
    this.pos.copy(p);
    this.path = [];
    this.snap = true;
    return this;
  }

  /** Walk along these points (on the floor). */
  walk(points: Vector3[], speed = 1.25) {
    this.path = points.map((p) => p.clone());
    this.speed = speed;
  }

  get walking() {
    return this.path.length > 0;
  }

  talk(seconds: number) {
    const now = performance.now() / 1000;
    this.talkUntil = now + seconds;
    this.company.speaker = this;
    this.company.until = this.talkUntil;
  }

  /** A bow from the waist; `deep` in radians, as the paper card tips. */
  bow(deep = 0.55, seconds = 1.3) {
    this.leanAt = performance.now() / 1000;
    this.leanFor = seconds;
    this.leanDepth = deep;
  }

  hop() {
    this.hopAt = performance.now() / 1000;
  }

  /** A new face (and maybe a gesture): the print is repainted, the body takes the mood. */
  express(expression: string, gesture: string | null) {
    const changed = expression !== this.expression;
    this.expression = expression;
    this.model.print.draw(expression);
    this.headPose = this.model.print.source.pose(expression);
    if (changed && expression === 'surprise') this.hop();
    if (gesture && gesture !== this.gesture && GESTURES[gesture]) {
      this.gestureId = gesture;
      this.gestureAt = performance.now() / 1000;
    }
    this.gesture = gesture;
  }

  update(dt: number, now: number, camera: Camera, light: [number, number, number]) {
    const P = this.person;
    const J = this.model.J;
    const energy = P.manner?.energy ?? 1;
    // walking along the path, once up from a seat
    let dir: Vector3 | null = null;
    const walking = this.path.length > 0;
    const moving = walking && this.sitNow < 0.3;
    if (moving) {
      const target = this.path[0];
      const d = new Vector3(target.x - this.pos.x, 0, target.z - this.pos.z);
      const dist = d.length();
      const step = this.speed * dt;
      if (dist > 1e-4) dir = d.clone().normalize();
      if (dist <= step) {
        this.pos.set(target.x, target.y, target.z);
        this.path.shift();
      } else {
        d.multiplyScalar(step / dist);
        this.pos.x += d.x;
        this.pos.z += d.z;
        this.pos.y += (target.y - this.pos.y) * Math.min(1, step / dist);
      }
    }
    this.walkBlend += ((moving && this.path.length ? 1 : 0) - this.walkBlend) * (1 - Math.exp(-dt * 7));
    const legLen = J.hips.y * this.scale;
    const stride = (P.manner?.stride ?? 0.62) * legLen;
    if (moving) this.walkPhase += (dt * this.speed * Math.PI) / Math.max(0.2, stride);

    // a seat: sat on when standing still on its spot; told to sit near one, step over to it
    this.sitOn = !walking && this.lift === 0 ? this.seatNear(0.3) : null;
    if (this.sitOn) this.lastSeat = this.sitOn;
    if (this.seat < 0.1) this.sought = false;
    else if (!this.sitOn && !walking && !this.sought) {
      this.sought = true;
      const s = this.seatNear(1.3);
      if (s) this.walk([s.at], 0.8);
    }
    if (this.snap) this.sitNow = this.sitOn ? 1 : 0;
    this.sitNow += ((this.sitOn ? 1 : 0) - this.sitNow) * (1 - Math.exp(-dt * 3.2));

    // facing: the way they walk, otherwise turned to you when you are well off to one side; a
    // seat with a back keeps them facing the room
    const toCam = Math.atan2(camera.position.x - this.pos.x, camera.position.z - this.pos.z);
    let want = this.heading;
    const chair = this.sitOn;
    if (dir && moving) want = Math.atan2(dir.x, dir.z);
    else if (chair && chair.yaw !== undefined) {
      const turn = chair.turn ?? 0.6;
      want = chair.yaw + Math.max(-turn, Math.min(turn, wrap(toCam - chair.yaw)));
    } else if (this.attentive) {
      const off = Math.abs(wrap(toCam - this.heading));
      if (off > 0.75) this.turning = true;
      if (this.turning) want = toCam;
      if (off < 0.08) this.turning = false;
    }
    if (this.snap) {
      this.heading = chair && chair.yaw !== undefined ? want : toCam;
      this.snap = false;
    }
    const dh = wrap(want - this.heading);
    const turnRate = moving ? 6 : 3.2;
    this.heading += Math.sign(dh) * Math.min(Math.abs(dh), Math.abs(dh) * (1 - Math.exp(-dt * turnRate)) + dt * 0.4);

    // the slow layers: the stance, the mood, the face's lean, a slump
    const target: Pose = {};
    addPose(target, this.rest);
    const mood = moodPose(this.expression, this.free);
    addPose(target, mood.body);
    blendArms(target, mood.arms, 1);
    const hp = this.headPose;
    add(target, 'head', [hp.dy * 0.012, hp.dx * 0.01, (-hp.tilt * Math.PI) / 180]);
    const stoop = P.body.stoop ?? 0;
    if (stoop) {
      add(target, 'chest', [stoop, 0, 0]);
      add(target, 'head', [-stoop * 0.6, 0, 0]);
    }
    this.seatNow += (this.seat - this.seatNow) * (1 - Math.exp(-dt * 8));
    const sit = smoothstep(0, 1, this.sitNow);
    const told = smoothstep(0, 0.08, this.seatNow);
    // told to sit with nowhere to: the sag goes deeper
    const sag = told * (1 - sit) * (1 + 0.8 * smoothstep(0.08, 0.2, this.seatNow));
    if (sag > 0) {
      add(target, 'chest', [0.16, 0, 0], sag);
      add(target, 'head', [0.12, 0, 0], told * (1 - sit));
      add(target, 'thighL', [-0.22, 0, 0], sag);
      add(target, 'thighR', [-0.22, 0, 0], sag);
      add(target, 'shinL', [0.4, 0, 0], sag);
      add(target, 'shinR', [0.4, 0, 0], sag);
      add(target, 'footL', [-0.18, 0, 0], sag);
      add(target, 'footR', [-0.18, 0, 0], sag);
    }
    const k = 1 - Math.exp(-dt * 5);
    BONES.forEach((b) => {
      const t = target[b] ?? [0, 0, 0];
      const c = this.slow[b] ?? (this.slow[b] = [0, 0, 0]);
      c[0] += (t[0] - c[0]) * k;
      c[1] += (t[1] - c[1]) * k;
      c[2] += (t[2] - c[2]) * k;
    });

    // the quick layers
    const pose: Pose = {};
    addPose(pose, this.slow);
    // sitting: the hips come down onto the seat (sunk a little into the leather), the feet flat on
    // the floor when the legs reach it, otherwise tucked back under the seat
    this.drop = sag * 0.035 * this.scale;
    const s = this.lastSeat;
    if (sit > 0.001 && s) {
      const hipY = J.hips.y * this.scale;
      const kneeY = J.knee.L.y * this.scale;
      const seated = s.height - 0.03 + 0.09 * this.scale;
      const reach = (seated - kneeY) / (hipY - kneeY);
      const flat = !s.high && reach <= 0.45;
      const th = flat ? Math.acos(Math.max(-0.2, reach)) : 1.3;
      add(pose, 'thighL', [-th, 0, -0.12], sit);
      add(pose, 'thighR', [-th, 0, 0.12], sit);
      add(pose, 'shinL', [flat ? th : th + 0.5, 0, 0], sit);
      add(pose, 'shinR', [flat ? th : th + 0.5, 0, 0], sit);
      add(pose, 'spine', [0.06, 0, 0], sit);
      // told to sit: a little bowed
      add(pose, 'chest', [0.12, 0, 0], sit * told);
      add(pose, 'armL', [-0.25, 0, 0], sit * (1 - this.hold.L));
      add(pose, 'armR', [-0.25, 0, 0], sit * (1 - this.hold.R));
      add(pose, 'foreL', [-0.5, 0, 0], sit * (1 - this.hold.L));
      add(pose, 'foreR', [-0.5, 0, 0], sit * (1 - this.hold.R));
      this.drop += Math.max(-0.2, hipY - seated) * sit;
    }
    const t = now + this.phase;
    // breathing and a little life, more of it in the restless
    add(pose, 'chest', [Math.sin(t * 1.7) * 0.014, 0, 0]);
    add(pose, 'spine', [0, Math.sin(t * 0.41) * 0.025 * energy, Math.sin(t * 0.53) * 0.012 * energy], 1 - this.walkBlend);
    add(pose, 'head', [Math.sin(t * 0.61) * 0.025 * energy, Math.sin(t * 0.37) * 0.05 * energy, 0], 1 - this.walkBlend);
    add(pose, 'hips', [0, 0, Math.sin(t * 0.47) * 0.012 * energy], (1 - this.walkBlend) * (1 - sit));
    // the walk
    let bob = 0;
    if (this.walkBlend > 0.01) {
      const w = this.walkBlend;
      const ph = this.walkPhase;
      const sn = Math.sin(ph);
      const c = Math.cos(ph);
      const amp = 0.42 * Math.min(1.25, 0.7 + this.speed * 0.25);
      add(pose, 'thighL', [-amp * sn, 0, 0], w);
      add(pose, 'thighR', [amp * sn, 0, 0], w);
      // the knee folds as the leg swings through
      add(pose, 'shinL', [0.85 * Math.max(0, c) ** 1.5 + 0.06, 0, 0], w);
      add(pose, 'shinR', [0.85 * Math.max(0, -c) ** 1.5 + 0.06, 0, 0], w);
      add(pose, 'footL', [0.3 * sn - 0.25 * Math.max(0, c), 0, 0], w);
      add(pose, 'footR', [-0.3 * sn - 0.25 * Math.max(0, -c), 0, 0], w);
      add(pose, 'spine', [0.04, 0.07 * sn, 0], w);
      add(pose, 'chest', [0, -0.12 * sn, 0], w);
      add(pose, 'hips', [0, -0.06 * sn, 0.035 * c], w);
      const swing = (P.manner?.swing ?? 1) * 0.36;
      add(pose, 'armL', [swing * sn, 0, 0], w * (1 - this.hold.L));
      add(pose, 'armR', [-swing * sn, 0, 0], w * (1 - this.hold.R));
      add(pose, 'foreL', [-0.2 - 0.18 * Math.max(0, -sn), 0, 0], w * (1 - this.hold.L));
      add(pose, 'foreR', [-0.2 - 0.18 * Math.max(0, sn), 0, 0], w * (1 - this.hold.R));
      bob = (Math.abs(c) - 0.6) * 0.04 * (P.manner?.bounce ?? 1) * w;
    }
    // talking: small nods, now and then a bigger one
    const talking = now < this.talkUntil;
    if (talking) {
      const nod = Math.sin(t * 8.3) * 0.035 + Math.max(0, Math.sin(t * 2.1)) ** 6 * 0.08;
      add(pose, 'head', [nod, Math.sin(t * 1.3) * 0.04, 0]);
      add(pose, 'chest', [Math.sin(t * 4.1) * 0.012, 0, 0]);
    }
    // a gesture
    if (this.gestureId) {
      const g = GESTURES[this.gestureId];
      const u = (now - this.gestureAt) / g.seconds;
      if (u >= 1) this.gestureId = null;
      else if (u >= 0) {
        const m = g.at(u, this.free);
        addPose(pose, m.body, m.w);
        blendArms(pose, m.arms, m.w);
      }
    }
    // a bow from the waist
    const lt = (now - this.leanAt) / this.leanFor;
    if (lt >= 0 && lt <= 1) {
      const d = Math.sin(lt * Math.PI) ** 1.3 * this.leanDepth;
      add(pose, 'spine', [d * 0.55, 0, 0]);
      add(pose, 'chest', [d * 0.35, 0, 0]);
      add(pose, 'head', [d * 0.2, 0, 0]);
    }
    // a hop: down, up, down (seated, only a bounce)
    const ht = (now - this.hopAt) / 0.42;
    let hop = 0;
    if (ht >= 0 && ht <= 1) {
      hop = Math.sin(ht * Math.PI) * 0.085 * (1 - 0.6 * sit);
      const crouch = Math.sin(ht * Math.PI * 2) ** 2 * 0.25 * (1 - sit);
      add(pose, 'thighL', [-crouch, 0, 0]);
      add(pose, 'thighR', [-crouch, 0, 0]);
      add(pose, 'shinL', [crouch * 2, 0, 0]);
      add(pose, 'shinR', [crouch * 2, 0, 0]);
      add(pose, 'footL', [-crouch, 0, 0]);
      add(pose, 'footR', [-crouch, 0, 0]);
    }

    // the head turns to whoever speaks, or to you; not to someone behind them
    const C = this.company;
    const headAt = this.faceLocal();
    let lookAt: Vector3 = camera.position;
    if (C.speaker && C.speaker !== this && now < C.until && C.speaker.visible) lookAt = C.speaker.face();
    const rootPos = new Vector3(this.pos.x, this.pos.y + this.lift, this.pos.z);
    const d = lookAt.clone().sub(rootPos.clone().add(headAt));
    const aside = wrap(Math.atan2(d.x, d.z) - this.heading);
    const reach = 1 - smoothstep(1.3, 2.0, Math.abs(aside));
    const yaw = Math.max(-1.0, Math.min(1.0, aside)) * reach;
    const pitch = Math.max(-0.35, Math.min(0.35, -Math.atan2(d.y, Math.hypot(d.x, d.z)))) * reach;
    const kl = 1 - Math.exp(-dt * 5);
    this.look.x += (yaw - this.look.x) * kl;
    this.look.y += (pitch - this.look.y) * kl;
    add(pose, 'neck', [this.look.y * 0.35, this.look.x * 0.4, 0]);
    add(pose, 'head', [this.look.y * 0.55, this.look.x * 0.6, 0]);

    // into the bones
    const bones = this.model.bones;
    BONES.forEach((name, i) => {
      const bone = bones[i];
      bone.position.copy(this.model.rest[i]);
      const r = pose[name];
      if (r) bone.quaternion.setFromEuler(e.set(r[0], r[1], r[2], 'XYZ'));
      else bone.quaternion.identity();
    });
    bones[B.root].position.y = (bob + hop - this.drop) / this.scale;
    this.root.position.copy(rootPos);
    this.root.rotation.set(0, this.heading, this.rock);
    this.root.visible = this.visible;
    const far = this.model.far;
    if (far) {
      const d = camera.position.distanceTo(rootPos);
      if (this.away ? d < FAR_OFF - 2 : d > FAR_OFF + 2) this.away = !this.away;
      this.model.mesh.visible = !this.away;
      far.visible = this.away;
    }
    this.blot.visible = sit < 0.05 && this.lift === 0;

    // the face: talking cycles the mouth, a blink now and then
    if (now >= this.blinkAt) {
      this.blinkUntil = now + 0.11;
      this.blinkAt = now + (2.2 + Math.random() * 3.6) / Math.max(0.6, energy);
    }
    if (talking) {
      if (now >= this.cellUntil) {
        this.cellIndex = (this.cellIndex + 1 + Math.floor(Math.random() * 3)) % TALK_CELLS.length;
        this.cell = TALK_CELLS[this.cellIndex];
        this.cellUntil = now + 0.075 + Math.random() * 0.07;
      }
    } else this.cell = 'own';
    const cell: Cell = now < this.blinkUntil ? 'blink' : this.cell;
    const u = this.model.material.uniforms;
    this.model.print.offset(cell, u.uFaceCell.value);

    // the light: the scene's at the feet, the key from above and toward you
    u.uLight.value.set(light[0], light[1], light[2]);
    u.uIndoor.value = this.indoor ? 1 : 0;
    const toCamera = camera.position.clone().sub(rootPos).setY(0).normalize();
    u.uKey.value.copy(UP).multiplyScalar(0.62).addScaledVector(toCamera, 0.55).add(new Vector3(0.18, 0, 0)).normalize();
  }

  /** The nearest free seat within `radius` of the feet, on the floor they stand on. */
  private seatNear(radius: number): Seat | null {
    const others = Array.from(this.company.members).filter((m) => m !== this && m.visible);
    let best: Seat | null = null;
    let near = radius;
    for (const s of this.seats) {
      const d = Math.hypot(s.at.x - this.pos.x, s.at.z - this.pos.z);
      if (Math.abs(s.at.y - this.pos.y) > 0.12 || d >= near) continue;
      if (others.some((m) => Math.hypot(s.at.x - m.pos.x, s.at.z - m.pos.z) < 0.3)) continue;
      best = s;
      near = d;
    }
    return best;
  }

  /** The head's middle, from the figure's feet, posed (metres, world-aligned). */
  private faceLocal(): Vector3 {
    const head = this.model.bones[B.head];
    const inv = this.model.mesh.skeleton.boneInverses[B.head];
    this.model.mesh.updateMatrixWorld(true);
    const hc = headCentre(this.model.J);
    const p = hc.applyMatrix4(new Matrix4().multiplyMatrices(head.matrixWorld, inv));
    return p.sub(this.root.position);
  }

  /** The figure's box on screen, for taps: [x0, y0, x1, y1] in normalised device coordinates. */
  screenBox(camera: Camera): [number, number, number, number] | null {
    if (!this.visible) return null;
    const right = new Vector3().setFromMatrixColumn(camera.matrixWorld, 0).normalize();
    const hw = 0.3 * this.scale;
    const y0 = this.root.position.y;
    const y1 = this.root.position.y + this.top - this.drop;
    const base = new Vector3(this.root.position.x, y0, this.root.position.z);
    const top = new Vector3(this.root.position.x, y1, this.root.position.z);
    const pts = [base.clone().addScaledVector(right, -hw), base.clone().addScaledVector(right, hw), top.clone().addScaledVector(right, -hw), top.clone().addScaledVector(right, hw)].map((p) => p.project(camera));
    if (pts.some((p) => p.z > 1 || p.z < -1)) return null;
    return [Math.min(...pts.map((p) => p.x)), Math.min(...pts.map((p) => p.y)), Math.max(...pts.map((p) => p.x)), Math.max(...pts.map((p) => p.y))];
  }

  /** Where to look when this person speaks: the face. */
  face(): Vector3 {
    return this.faceLocal().add(this.root.position);
  }

  dispose() {
    this.model.dispose();
    this.blot.geometry.dispose();
    (this.blot.material as { dispose(): void }).dispose();
    if (this.company.speaker === this) this.company.speaker = null;
    this.company.members.delete(this);
  }
}

function wrap(a: number) {
  let x = a;
  while (x > Math.PI) x -= Math.PI * 2;
  while (x < -Math.PI) x += Math.PI * 2;
  return x;
}

export { GESTURES };
