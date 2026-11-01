/**
 * Le Quartier · the troupe, stood up as paper.
 *
 * Each person is their drawing printed onto a card with a margin of white paper round the
 * silhouette, standing on the floor of the scene and always turned to face you, with a soft
 * blot of shadow under the feet. The card takes the scene's light (blue under the moon, amber
 * under the café's globes, red by the neon) and acts the way paper can: it hops when it walks,
 * bounces when it speaks, bows by tipping forward. Faces come from the same drawings the app
 * shows everywhere; a new mood is a new print of the same card.
 */
import {
  CanvasTexture,
  Group,
  LinearFilter,
  LinearMipmapLinearFilter,
  Mesh,
  NoColorSpace,
  PlaneGeometry,
  Vector3,
} from 'three';
import type { Camera, Texture } from 'three';

import { blotMaterial, figureMaterial } from './materials';
import type { World } from './materials';
import { INKS, rgb } from './palette';

export interface Art {
  svg: string;
  aspect: number;
}

/** Where the drawings come from (the React bridge, `cast-art.tsx`). */
export interface ArtSource {
  figure: (key: string, expression: string, gesture: string | null) => Art | null;
  item: (id: string) => Art | null;
}

export interface Printed {
  texture: Texture;
  /** width over height of the printed card, margin included */
  aspect: number;
}

const PAPER = '#f8f3e8';

/**
 * Print an SVG drawing onto a card: rasterise, crop to the drawing, and lay it on a margin of
 * paper the shape of its silhouette (the cut-out's white edge).
 */
export async function printCard(svg: string, heightPx: number, aspect: number, opts: { margin?: number; paper?: string } = {}): Promise<Printed> {
  const margin = opts.margin ?? Math.round(heightPx * 0.012);
  const img = new Image();
  img.decoding = 'async';
  const loaded = new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error('A drawing failed to print'));
  });
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  await loaded;
  const h = heightPx;
  const w = Math.round(h * aspect);
  const raw = document.createElement('canvas');
  raw.width = w;
  raw.height = h;
  const rctx = raw.getContext('2d', { willReadFrequently: true });
  if (!rctx) throw new Error('No 2D canvas');
  rctx.drawImage(img, 0, 0, w, h);
  // crop to what is drawn
  const data = rctx.getImageData(0, 0, w, h).data;
  let x0 = w;
  let y0 = h;
  let x1 = 0;
  let y1 = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (data[(y * w + x) * 4 + 3] > 24) {
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  if (x1 <= x0 || y1 <= y0) {
    x0 = 0;
    y0 = 0;
    x1 = w - 1;
    y1 = h - 1;
  }
  const cw = x1 - x0 + 1 + margin * 2;
  const ch = y1 - y0 + 1 + margin * 2;
  const out = document.createElement('canvas');
  out.width = cw;
  out.height = ch;
  const octx = out.getContext('2d');
  if (!octx) throw new Error('No 2D canvas');
  // the paper: the silhouette, grown by the margin in every direction
  const paper = document.createElement('canvas');
  paper.width = cw;
  paper.height = ch;
  const pctx = paper.getContext('2d');
  if (!pctx) throw new Error('No 2D canvas');
  const steps = 16;
  for (let i = 0; i < steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    pctx.drawImage(raw, x0, y0, x1 - x0 + 1, y1 - y0 + 1, margin + Math.cos(a) * margin, margin + Math.sin(a) * margin, x1 - x0 + 1, y1 - y0 + 1);
  }
  pctx.drawImage(raw, x0, y0, x1 - x0 + 1, y1 - y0 + 1, margin, margin, x1 - x0 + 1, y1 - y0 + 1);
  pctx.globalCompositeOperation = 'source-in';
  pctx.fillStyle = opts.paper ?? PAPER;
  pctx.fillRect(0, 0, cw, ch);
  octx.drawImage(paper, 0, 0);
  octx.drawImage(raw, x0, y0, x1 - x0 + 1, y1 - y0 + 1, margin, margin, x1 - x0 + 1, y1 - y0 + 1);
  const texture = new CanvasTexture(out);
  texture.colorSpace = NoColorSpace;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.magFilter = LinearFilter;
  texture.anisotropy = 4;
  return { texture, aspect: cw / ch };
}

export interface FigureSpec {
  key: string;
  /** height of the drawn person in metres (top of the hair to the soles) */
  height: number;
  /** a printed silhouette (Camille in the doorway, not yet in close-up) */
  silhouette?: boolean;
}

/**
 * A place to sit, for the people in the round: standing still on its spot they sit down on it,
 * and told to sit (`seat`) near one they step over to it. A card has no knees and ignores seats.
 */
export interface Seat {
  /** the spot, on the floor: where the hips come down */
  at: Vector3;
  /** the seat's top above that floor */
  height: number;
  /** which way someone sitting there faces (a heading, 0 toward +z), when the seat has a back */
  yaw?: number;
  /** how far they may turn from it */
  turn?: number;
  /** a bar stool: the feet stay on its rung */
  high?: boolean;
}

/** Someone on stage, as the director moves them: a paper card, or a person in the round (`cast3d`). */
export interface Figure {
  readonly key: string;
  readonly root: Group;
  /** where the feet are */
  readonly pos: Vector3;
  /** extra height (standing on the bench) */
  lift: number;
  /** 0 standing, otherwise how far into the seat (a card's share hidden from the bottom) */
  seat: number;
  /** a tilt in the plane facing you, set from outside (a galloping horse's rock) */
  rock: number;
  expression: string;
  gesture: string | null;
  visible: boolean;
  readonly walking: boolean;
  place(p: Vector3): this;
  walk(points: Vector3[], speed?: number): void;
  talk(seconds: number): void;
  bow(deep?: number, seconds?: number): void;
  hop(): void;
  update(dt: number, now: number, camera: Camera, light: [number, number, number]): void;
  screenBox(camera: Camera): [number, number, number, number] | null;
  face(): Vector3;
  dispose(): void;
  /** a person in the round repaints their own face; a card waits for a new print */
  express?(expression: string, gesture: string | null): void;
  /** inside the café, for the warm shade (in the round) */
  indoor?: boolean;
  /** in the round: turns to face you when you are well off to one side; off, they keep their way */
  attentive?: boolean;
}

let figureIds = 40;

export class PaperFigure implements Figure {
  readonly key: string;
  readonly root = new Group();
  private card: Mesh;
  private blot: Mesh;
  readonly material;
  private height: number;
  private aspect = 0.5;
  /** where the feet are */
  readonly pos = new Vector3();
  /** extra height (standing on the bench) */
  lift = 0;
  /** 0 standing, otherwise the share of the card hidden from the bottom (seated) */
  seat = 0;
  /** a tilt of the card in its own plane, set from outside (a galloping horse's rock) */
  rock = 0;
  expression = 'neutre';
  gesture: string | null = null;
  private talkUntil = 0;
  private leanAt = -10;
  private leanFor = 1.2;
  private leanDepth = 0.55;
  private path: Vector3[] = [];
  private speed = 1.25;
  private walkPhase = 0;
  private turnHop = 0;
  private phase = Math.random() * 10;
  /** when the card was last reprinted (for a little flip on a new face) */
  private flipAt = -10;
  visible = true;

  constructor(world: World, spec: FigureSpec, first: Printed) {
    this.key = spec.key;
    this.height = spec.height;
    figureIds = figureIds >= 56 ? 40 : figureIds + 1;
    this.material = figureMaterial(world, first.texture, figureIds);
    if (spec.silhouette) {
      this.material.uniforms.uDark.value = 0.86;
      const s = rgb(INKS.ink);
      this.material.uniforms.uSilhouette.value.set(s[0] * 1.2, s[1] * 1.25, s[2] * 1.7);
    }
    this.card = new Mesh(new PlaneGeometry(1, 1).translate(0, 0.5, 0), this.material);
    this.card.frustumCulled = false;
    this.blot = new Mesh(new PlaneGeometry(1, 1).rotateX(-Math.PI / 2), blotMaterial(rgb(INKS.ink), 0.5));
    this.blot.renderOrder = 2;
    this.root.add(this.card, this.blot);
    this.setPrint(first);
  }

  setPrint(p: Printed) {
    this.material.uniforms.uMap.value = p.texture;
    this.aspect = p.aspect;
    this.card.scale.set(this.height * this.aspect, this.height, 1);
    this.flipAt = performance.now() / 1000;
  }

  place(p: Vector3) {
    this.pos.copy(p);
    this.path = [];
    return this;
  }

  /** Walk along these points (on the floor), hopping like paper does. */
  walk(points: Vector3[], speed = 1.25) {
    this.path = points.map((p) => p.clone());
    this.speed = speed;
  }

  get walking() {
    return this.path.length > 0;
  }

  talk(seconds: number) {
    this.talkUntil = performance.now() / 1000 + seconds;
  }

  /** A bow: the card tips toward you and comes back. `deep` is in radians. */
  bow(deep = 0.55, seconds = 1.3) {
    this.leanAt = performance.now() / 1000;
    this.leanFor = seconds;
    this.leanDepth = deep;
  }

  /** A small hop on the spot (surprise, a turn of the head). */
  hop() {
    this.turnHop = performance.now() / 1000;
  }

  update(dt: number, now: number, camera: Camera, light: [number, number, number]) {
    // walking
    if (this.path.length) {
      const target = this.path[0];
      const d = new Vector3(target.x - this.pos.x, 0, target.z - this.pos.z);
      const dist = d.length();
      const step = this.speed * dt;
      if (dist <= step) {
        this.pos.x = target.x;
        this.pos.z = target.z;
        this.pos.y = target.y;
        this.path.shift();
      } else {
        d.multiplyScalar(step / dist);
        this.pos.x += d.x;
        this.pos.z += d.z;
        this.pos.y += (target.y - this.pos.y) * Math.min(1, step / dist);
      }
      this.walkPhase += dt * this.speed * 4.2;
    } else {
      this.walkPhase = 0;
    }
    const hop = this.path.length ? Math.abs(Math.sin(this.walkPhase)) * 0.07 : 0;
    const sway = this.path.length ? Math.sin(this.walkPhase) * 0.05 : 0;
    const talking = now < this.talkUntil;
    const bounce = talking ? Math.abs(Math.sin(now * 8.5 + this.phase)) * 0.025 : 0;
    const little = Math.max(0, 1 - (now - this.turnHop) / 0.35);
    const hop2 = Math.sin(little * Math.PI) * 0.09;
    const breathe = 1 + Math.sin(now * 1.6 + this.phase) * 0.006;
    // the lean of a bow, eased in and out
    const t = (now - this.leanAt) / this.leanFor;
    const lean = t >= 0 && t <= 1 ? Math.sin(t * Math.PI) ** 1.3 * this.leanDepth : 0;
    // a quick flip when the face is reprinted, like turning a card
    const ft = Math.min(1, (now - this.flipAt) / 0.18);
    const flip = 0.82 + 0.18 * ft;
    const seatDrop = this.seat > 0 ? -this.seat * this.height : 0;
    this.root.position.set(this.pos.x, this.pos.y + this.lift, this.pos.z);
    this.card.position.y = seatDrop + hop + bounce + hop2;
    this.card.scale.set(this.height * this.aspect * flip, this.height * breathe, 1);
    this.card.rotation.set(0, Math.atan2(camera.position.x - this.root.position.x, camera.position.z - this.root.position.z), sway + this.rock);
    this.material.uniforms.uLean.value = lean;
    this.material.uniforms.uCut.value = this.seat;
    this.material.uniforms.uLight.value.set(light[0], light[1], light[2]);
    this.blot.scale.set(this.height * this.aspect * 0.9, 1, 0.42);
    this.blot.position.y = this.seat > 0 ? -10 : 0.012;
    this.blot.visible = this.seat === 0;
    this.root.visible = this.visible;
  }

  /** The card's box on screen, for taps: [x0, y0, x1, y1] in normalised device coordinates. */
  screenBox(camera: Camera): [number, number, number, number] | null {
    if (!this.visible) return null;
    const right = new Vector3().setFromMatrixColumn(camera.matrixWorld, 0).normalize();
    const hw = (this.height * this.aspect) / 2;
    const y0 = this.root.position.y + this.card.position.y + this.seat * this.height;
    const y1 = this.root.position.y + this.card.position.y + this.height;
    const base = new Vector3(this.root.position.x, y0, this.root.position.z);
    const top = new Vector3(this.root.position.x, y1, this.root.position.z);
    const pts = [
      base.clone().addScaledVector(right, -hw),
      base.clone().addScaledVector(right, hw),
      top.clone().addScaledVector(right, -hw),
      top.clone().addScaledVector(right, hw),
    ].map((p) => p.project(camera));
    if (pts.some((p) => p.z > 1 || p.z < -1)) return null;
    return [Math.min(...pts.map((p) => p.x)), Math.min(...pts.map((p) => p.y)), Math.max(...pts.map((p) => p.x)), Math.max(...pts.map((p) => p.y))];
  }

  /** Where to look when this person speaks: the face. */
  face(): Vector3 {
    return new Vector3(this.root.position.x, this.root.position.y + this.card.position.y + this.height * 0.88, this.root.position.z);
  }

  dispose() {
    this.card.geometry.dispose();
    this.blot.geometry.dispose();
    this.material.dispose();
  }
}

/**
 * The cast on stage: prints the faces it needs (once each), keeps the cards, and lights
 * them from the light map every frame. Given `round`, it stands up in the round whoever that
 * returns a figure for and prints the rest, so its people are `Figure`s of either kind.
 */
export class Troupe<F extends Figure = PaperFigure> {
  readonly group = new Group();
  readonly people = new Map<string, F>();
  private prints = new Map<string, Promise<Printed>>();
  private specs = new Map<string, FigureSpec>();
  private disposed = false;

  constructor(
    private world: World,
    private art: ArtSource,
    private heightPx = 840,
    private round?: (spec: FigureSpec) => F | null,
  ) {}

  private printKey(key: string, expression: string, gesture: string | null) {
    return `${key}:${expression}:${gesture ?? '-'}`;
  }

  print(key: string, expression = 'neutre', gesture: string | null = null): Promise<Printed> {
    const k = this.printKey(key, expression, gesture);
    let p = this.prints.get(k);
    if (!p) {
      const art = this.art.figure(key, expression, gesture);
      p = art ? printCard(art.svg, this.heightPx, art.aspect) : Promise.reject(new Error(`No drawing for ${key}`));
      this.prints.set(k, p);
    }
    return p;
  }

  /** Stand someone at `at` (printed first, on paper); null when the troupe was disposed meanwhile. */
  async add(spec: FigureSpec, at: Vector3): Promise<F | null> {
    this.specs.set(spec.key, spec);
    if (this.round) {
      // one person sculpted at a time, so a loading bar moves between them
      await new Promise((r) => setTimeout(r, 0));
      if (this.disposed) return null;
    }
    let f = this.round?.(spec) ?? null;
    if (!f) {
      const first = await this.print(spec.key);
      // its print's texture goes with the others in `dispose`
      if (this.disposed) return null;
      // without `round` F is PaperFigure; with it, Figure
      f = new PaperFigure(this.world, spec, first) as unknown as F;
    }
    f.place(at);
    this.people.set(spec.key, f);
    this.group.add(f.root);
    return f;
  }

  get(key: string) {
    return this.people.get(key) ?? null;
  }

  /** Take someone off the stage, to stand them up again otherwise (Camille, out of the doorway's shadow). */
  remove(key: string) {
    const f = this.people.get(key);
    if (!f) return;
    this.group.remove(f.root);
    f.dispose();
    this.people.delete(key);
    this.specs.delete(key);
  }

  /** Change someone's face (and gesture): in the round at once, a card when its print is ready. */
  async face(key: string, expression: string, gesture: string | null = null) {
    const f = this.people.get(key);
    if (!f) return;
    if (f.express) {
      f.express(expression, gesture);
      return;
    }
    f.expression = expression;
    f.gesture = gesture;
    try {
      const p = await this.print(key, expression, gesture);
      if (f instanceof PaperFigure && f.expression === expression && f.gesture === gesture) f.setPrint(p);
    } catch {
      // keep the face it has
    }
  }

  /** `indoorAt` tells the people in the round when they stand inside (the café's warm shade). */
  update(dt: number, now: number, camera: Camera, lightAt: (p: Vector3) => [number, number, number], indoorAt?: (p: Vector3) => boolean) {
    this.people.forEach((f) => {
      if (indoorAt && f.indoor !== undefined) f.indoor = indoorAt(f.pos);
      f.update(dt, now, camera, lightAt(f.pos));
    });
  }

  dispose() {
    this.disposed = true;
    this.people.forEach((f) => f.dispose());
    this.prints.forEach((p) => p.then((x) => x.texture.dispose()).catch(() => undefined));
  }
}
