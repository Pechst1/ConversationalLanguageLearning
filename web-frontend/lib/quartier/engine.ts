/**
 * Le Quartier · the engine: one three.js renderer, the quarter, you, and the frame loop.
 *
 * You are a camera at eye height on the walking grid. A thumb (or WASD) walks, a drag looks, a
 * tap walks to where you tapped or touches whoever you tapped. The stage director (`stage.ts`)
 * drives the rest through the methods here: walk you somewhere, turn your head toward a speaker,
 * narrow the lens for a silent panel, open the door, light the neon.
 *
 * Every frame: the canal's mirror at half resolution (only when water is in view), the plate
 * (the scene in colour, line ids and depth), then the print pass to the screen. The resolution
 * follows the phone's frame time, so a hot phone draws fewer pixels rather than fewer frames.
 */
import {
  Box3,
  CanvasTexture,
  Color,
  Frustum,
  Group,
  HalfFloatType,
  InstancedMesh,
  Matrix4,
  Mesh,
  PerspectiveCamera,
  Plane,
  PlaneGeometry,
  Raycaster,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  Vector2,
  Vector3,
  Vector4,
  WebGLRenderTarget,
  WebGLRenderer,
  DoubleSide,
  NoColorSpace,
  Object3D,
} from 'three';

import { Troupe, printCard } from './cast';
import type { ArtSource, Figure } from './cast';
import { roundFigure } from './cast3d';
import { CardPress, LacePress, Press, seeded, tile } from './geo';
import type { Build, Lamp } from './kit';
import { bakeLightMap } from './lightmap';
import type { LightMap } from './lightmap';
import {
  MAX_GLINTS,
  applyAmbiance,
  blotMaterial,
  figureMaterial,
  glassMaterial,
  haloMaterial,
  inkMaterial,
  laceMaterial,
  makeWorld,
  signMaterial,
  skyMaterial,
  waterMaterial,
} from './materials';
import type { World } from './materials';
import { MARKS, ROOM, SEATS, buildMistral, cafeCreme } from './mistral';
import type { MistralParts } from './mistral';
import { Nav } from './nav';
import { STRIDE, WALK_SPEED } from './pace';
import { AMBIANCES, INKS, TONES, mix, rgb } from './palette';
import type { Ambiance, AmbianceId } from './palette';
import { PrintPass } from './print';
import { PLAN, buildQuai } from './quai';
import type { Quai } from './quai';
import { Rain } from './rain';
import { fontsReady, neonTexture, printAtlas } from './signs';
import { buildSite } from './site';
import type { SiteBuilt, SiteSpec } from './site';

export const EYE = 1.62;

export interface Spot {
  id: string;
  pos: Vector3;
  /** how close a tap must land, in metres round the point */
  radius: number;
  enabled: boolean;
}

export type Hit =
  | { kind: 'person'; key: string }
  | { kind: 'spot'; id: string }
  | { kind: 'ground'; point: Vector3 }
  | { kind: 'none' };

export interface Stats {
  fps: number;
  frameMs: number;
  calls: number;
  triangles: number;
  scale: number;
  textures: number;
  geometries: number;
}

export interface QuartierOptions {
  canvas: HTMLCanvasElement;
  art: ArtSource;
  ambiance?: AmbianceId;
  /** `fixed` keeps the resolution (screenshots); `auto` follows the frame time */
  resolution?: 'auto' | 'fixed';
  /** device pixels per CSS pixel to start from */
  scale?: number;
  mirror?: boolean;
  onProgress?: (share: number, label: string) => void;
  /** a place the forge built (`site.ts`); without one, the quai de Valmy and Le Mistral */
  site?: SiteSpec;
  /** the cast in the round, sculpted (`cast3d`), or on `paper` as cut-out cards */
  cast?: 'round' | 'paper';
}

type Listener = (hit: Hit) => void;
type Ticker = (dt: number, now: number) => void;

/** Something the director moves about: an object of the season on the zinc, a cup, a chair. */
export interface Prop {
  object: Object3D;
  /** paper props take the light where they lie */
  material?: ShaderMaterial;
}

/** Thrown out of `load()` when the quarter is disposed while it is still being built. */
export class LoadCancelled extends Error {
  constructor() {
    super('The quarter was closed while it was loading');
    this.name = 'LoadCancelled';
  }
}

export class Quartier {
  readonly renderer: WebGLRenderer;
  readonly scene = new Scene();
  readonly camera = new PerspectiveCamera(60, 1, 0.1, 420);
  readonly world: World = makeWorld();
  readonly troupe: Troupe<Figure>;
  /** other people on stage (the passers-by, `crowd.ts`): lit, drawn and tapped like the cast */
  private extras: Array<Troupe<Figure>> = [];
  nav!: Nav;
  lightMap!: LightMap;
  /** the hand-drawn quarter (absent in a forged place) */
  quai?: Quai;
  parts?: MistralParts;
  /** the forged place, when this is one */
  site?: SiteBuilt;
  ambiance: AmbianceId;

  /* you */
  readonly feet = new Vector3();
  yaw = 0;
  pitch = -0.04;
  /** how high your eyes are above your feet (sitting down lowers them) */
  eyeHeight = EYE;
  private eyeY = EYE;
  private stick = new Vector2();
  private keys = new Set<string>();
  private route: Vector3[] = [];
  private routeSpeed = WALK_SPEED;
  private routeDone: (() => void) | null = null;
  private lookTarget: Vector3 | null = null;
  private lookStrength = 3.2;
  private userLookUntil = 0;
  private fovTarget = 60;
  /** the director can hold you still during a scene (looking stays free) */
  frozen = false;
  /** the haze's near and far, overriding the hour's (the forge's look from above) */
  fogOverride: [number, number] | null = null;

  /* the print */
  private print: PrintPass;
  private scale: number;
  private resolution: 'auto' | 'fixed';
  private mirrorOn: boolean;
  private mirrorRT: WebGLRenderTarget | null = null;
  private mirrorCam = new PerspectiveCamera();
  private mirrorMatrix = new Matrix4();
  private water?: Mesh;
  private waterBox = new Box3();
  private rain = new Rain(2200);
  /** where it does not rain: Le Mistral, or a forged place's hall */
  private rainRoom = new Vector4(ROOM.x0, ROOM.z0, ROOM.x1, ROOM.z1);
  private neon?: Mesh;
  private neonHalo?: Mesh;
  private halos!: InstancedMesh;
  private dots!: InstancedMesh;
  private doors: Group[] = [];
  private tickers = new Set<Ticker>();
  readonly props = new Map<string, Prop>();
  private ink!: ShaderMaterial;
  private doorOpen = 0;
  private doorTarget = 0;
  private statics: Mesh[] = [];
  /** the façades' small relief, tile by tile, shown only near you */
  private fines: Array<{ mesh: Mesh; center: Vector3; radius: number }> = [];
  private sky!: Mesh;
  private pickables: Object3D[] = [];
  private spots: Spot[] = [];
  private listeners: Listener[] = [];
  private lamps: Lamp[] = [];
  private glints: Lamp[] = [];
  private raf = 0;
  private last = 0;
  private times: number[] = [];
  private lastScaleChange = 0;
  stats: Stats = { fps: 0, frameMs: 0, calls: 0, triangles: 0, scale: 1, textures: 0, geometries: 0 };
  private pointer: { id: number; x: number; y: number; sx: number; sy: number; t: number; moved: boolean } | null = null;
  private disposed = false;
  private started = false;
  private neonState = 1;
  private onProgress?: (share: number, label: string) => void;
  private art: ArtSource;

  constructor(private opts: QuartierOptions) {
    this.renderer = new WebGLRenderer({ canvas: opts.canvas, antialias: false, alpha: false, stencil: false, powerPreference: 'high-performance' });
    this.renderer.info.autoReset = false;
    this.scale = opts.scale ?? Math.min(2, typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1);
    this.resolution = opts.resolution ?? 'auto';
    // a forged place has no canal to mirror
    this.mirrorOn = (opts.mirror ?? true) && !opts.site;
    this.ambiance = opts.ambiance ?? opts.site?.ambiance ?? 'nuit';
    this.art = opts.art;
    this.onProgress = opts.onProgress;
    this.camera.rotation.order = 'YXZ';
    // in the round, the cast sit in Le Mistral's booth and on its stools
    const seats = opts.site ? [] : SEATS;
    this.troupe = new Troupe<Figure>(this.world, opts.art, 840, opts.cast === 'paper' ? undefined : (spec) => roundFigure(this.world, spec, seats));
    this.print = new PrintPass(2, 2, { line: 1, idLines: 0.55, halftone: 0.55, grain: 1 });
    this.scene.add(this.troupe.group);
  }

  on(fn: Listener) {
    this.listeners.push(fn);
    return () => {
      this.listeners = this.listeners.filter((f) => f !== fn);
    };
  }

  /** Run something every frame (the director's tweens and waits); returns the stopper. */
  onTick(fn: Ticker) {
    this.tickers.add(fn);
    return () => {
      this.tickers.delete(fn);
    };
  }

  /**
   * Lay one of the season's objects flat, printed on paper like the cast (the key ring with its
   * cicada, the notary's envelope). `size` is its length in metres; it starts hidden.
   */
  async addItem(key: string, id: string, size: number): Promise<Prop | null> {
    const art = this.art.item(id);
    if (!art) return null;
    const printed = await printCard(art.svg, 384, art.aspect, { margin: 6 });
    if (this.disposed) {
      printed.texture.dispose();
      return null;
    }
    const m = figureMaterial(this.world, printed.texture, 57);
    const plane = new Mesh(new PlaneGeometry(size * printed.aspect, size).rotateX(-Math.PI / 2), m);
    plane.visible = false;
    plane.renderOrder = 3;
    this.scene.add(plane);
    const prop = { object: plane, material: m };
    this.props.set(key, prop);
    return prop;
  }

  /* ---------------------------------------------------------------------------------------- */
  /* building the quarter                                                                     */
  /* ---------------------------------------------------------------------------------------- */

  /**
   * Build the quarter, yielding between the large steps so the progress bar moves. Disposing it
   * meanwhile stops the build at the next step (it throws `LoadCancelled`), so nothing is made
   * after the one disposal pass.
   */
  async load() {
    const site = this.opts.site;
    const step = async (share: number, label: string) => {
      this.alive();
      this.onProgress?.(share, label);
      await new Promise((r) => setTimeout(r, 0));
      this.alive();
    };
    await step(0.02, 'Les encres');
    await fontsReady();
    await step(0.08, site ? site.title.fr : 'Le quai de Valmy');
    const B: Build = {
      dry: new Press(),
      fine: new Press(),
      wet: new Press(),
      lace: new LacePress(),
      glass: new Press(),
      cards: new CardPress(),
      signs: [],
      lamps: [],
      walk: [],
      blocks: [],
      rand: seeded(1102),
    };
    if (site) {
      this.site = buildSite(B, site);
      const room = this.site.landmarks.find((l) => l.room)?.room;
      this.rainRoom.set(room ? room[0] : 0, room ? room[1] : 0, room ? room[2] : -1, room ? room[3] : -1);
    } else {
      const quai = buildQuai(B);
      this.quai = quai;
      await step(0.3, 'Le Mistral');
      this.parts = buildMistral(B, quai.mistral);
    }
    this.lamps = B.lamps;
    this.glints = B.lamps.filter((l) => l.glint);
    await step(0.42, 'Les lampes');
    if (this.site) {
      const r = this.site.spec.radius.build + 10;
      this.lightMap = bakeLightMap(B.lamps, { x0: -r, z0: -r, x1: r, z1: r }, 2.2, this.site.under);
    } else {
      const bounds = { x0: -185, z0: -250, x1: 95, z1: 250 };
      this.lightMap = bakeLightMap(B.lamps, bounds, 2.2, (x, z) => x > ROOM.x0 - 0.3 && x < ROOM.x1 + 0.05 && z > ROOM.z0 - 0.3 && z < ROOM.z1 + 0.05);
    }
    this.world.uLightMap.value = this.lightMap.texture;
    this.world.uLightRect.value.copy(this.lightMap.rect);
    await step(0.5, 'Les rues');
    if (this.site) {
      const r = this.site.spec.radius.walk + 3;
      this.nav = new Nav(B.walk, B.blocks, { x0: -r, z0: -r, x1: r, z1: r });
    } else {
      this.nav = new Nav(B.walk, B.blocks, { x0: -182, z0: -212, x1: 32, z1: 212 });
    }
    await step(0.56, 'L’impression');
    this.assemble(B);
    if (!this.site) {
      await step(0.66, 'La troupe');
      await this.loadCast();
    }
    await step(0.96, 'Le décor');
    applyAmbiance(this.world, this.light());
    this.applyAmbianceExtras();
    if (this.site) this.place(this.site.start.pos, this.site.start.look);
    else this.place(PLAN.start.pos, PLAN.start.look);
    this.resize();
    await step(1, 'Prêt');
  }

  /**
   * The light of the hour. A forged place ends where its survey ends, so its haze comes closer:
   * the last houses melt into the morning before the edge of the drawn city shows.
   */
  private light(): Ambiance {
    const a = AMBIANCES[this.ambiance];
    if (this.fogOverride) return { ...a, fogNear: this.fogOverride[0], fogFar: this.fogOverride[1] };
    if (!this.site) return a;
    const { walk, build } = this.site.spec.radius;
    // a racecourse is open ground: you see across it to the trees
    const far = Math.min(a.fogFar, this.site.venue ? 260 : build - walk + 55);
    return { ...a, fogFar: far, fogNear: Math.min(a.fogNear, far * 0.3) };
  }

  private assemble(B: Build) {
    const ink = inkMaterial(this.world);
    this.ink = ink;
    const wet = inkMaterial(this.world, { wet: true });
    const addTiles = (g: ReturnType<Press['geometry']>, m: ShaderMaterial, size: number, pick: boolean) => {
      for (const part of tile(g, size)) {
        const mesh = new Mesh(part, m);
        mesh.matrixAutoUpdate = false;
        mesh.layers.enable(1);
        this.scene.add(mesh);
        this.statics.push(mesh);
        if (pick) this.pickables.push(mesh);
      }
      g.dispose();
    };
    addTiles(B.dry.geometry(), ink, 48, true);
    addTiles(B.wet.geometry(), wet, 60, true);
    const fine = B.fine.geometry();
    for (const part of tile(fine, 36)) {
      const mesh = new Mesh(part, ink);
      mesh.matrixAutoUpdate = false;
      part.computeBoundingSphere();
      const bs = part.boundingSphere;
      this.scene.add(mesh);
      this.statics.push(mesh);
      if (bs) this.fines.push({ mesh, center: bs.center.clone(), radius: bs.radius });
    }
    fine.dispose();
    const lace = new Mesh(B.lace.geometry(), laceMaterial(this.world, rgb(TONES.iron)));
    lace.matrixAutoUpdate = false;
    this.scene.add(lace);
    const glass = new Mesh(B.glass.geometry(), glassMaterial(this.world, rgb(mix(INKS.cobalt, INKS.ink, 0.4))));
    glass.renderOrder = 4;
    glass.matrixAutoUpdate = false;
    this.scene.add(glass);
    // lettering
    const atlas = printAtlas(B.signs);
    const cards = new Mesh(atlas.cards.geometry(), signMaterial(this.world, atlas.texture, 60, 0));
    cards.material.side = DoubleSide;
    cards.matrixAutoUpdate = false;
    this.scene.add(cards);
    const parts = this.parts;
    // the canal
    if (parts) {
      const water = new Mesh(new PlaneGeometry(20, PLAN.zMax - PLAN.zMin + 60).rotateX(-Math.PI / 2), waterMaterial(this.world, rgb(TONES.water), PLAN.water));
      water.position.set(0, PLAN.water, 0);
      water.updateMatrixWorld();
      this.water = water;
      this.waterBox.setFromObject(water);
      this.scene.add(water);
    }
    // the sky
    const sky = new Mesh(new SphereGeometry(400, 32, 16), skyMaterial(this.world));
    sky.renderOrder = -10;
    sky.frustumCulled = false;
    sky.layers.enable(1);
    this.sky = sky;
    this.scene.add(sky);
    // the neon: one blade, readable from the quai, reversed from Odile's window
    if (parts) {
      const neon = neonTexture('MISTRAL');
      const n = parts.neon;
      const neonMat = signMaterial(this.world, neon.texture, 59, 1);
      neonMat.side = DoubleSide;
      const blade = new Mesh(new PlaneGeometry(n.width, n.width / neon.aspect), neonMat);
      blade.position.copy(n.center);
      blade.lookAt(n.center.clone().add(new Vector3(-0.707, 0, 0.707)));
      blade.layers.enable(1);
      this.neon = blade;
      this.scene.add(blade);
      const halo = new Mesh(new PlaneGeometry(1, 1), haloMaterial(rgb(INKS.vermilion), 0.55));
      halo.position.copy(n.center);
      halo.scale.set(3.2, 6.2, 1);
      halo.renderOrder = 6;
      this.neonHalo = halo;
      this.scene.add(halo);
    }
    // the lamps' halos in the rain
    const heads = this.lamps.filter((l) => l.glint && l.pos.y > 2.5 && l.color[1] > 0.5);
    const haloMat = haloMaterial(rgb(mix(INKS.sunflower, INKS.card, 0.3)), 0.32);
    haloMat.vertexShader = HALO_INSTANCED_VERT;
    haloMat.uniforms.uSize = { value: 2.2 };
    this.halos = new InstancedMesh(new PlaneGeometry(1, 1), haloMat, heads.length);
    heads.forEach((l, i) => this.halos.setMatrixAt(i, new Matrix4().makeTranslation(l.pos.x, l.pos.y + 0.15, l.pos.z)));
    this.halos.renderOrder = 6;
    this.halos.frustumCulled = false;
    this.scene.add(this.halos);
    // the dotted way to where you are going
    const dotMat = blotMaterial(rgb(mix(INKS.card, INKS.sunflower, 0.35)), 0.95);
    this.dots = new InstancedMesh(new PlaneGeometry(0.16, 0.16).rotateX(-Math.PI / 2), dotMat, 80);
    this.dots.count = 0;
    this.dots.frustumCulled = false;
    this.dots.renderOrder = 3;
    this.scene.add(this.dots);
    if (parts) {
      // the doors
      for (const d of parts.doors) {
        const press = d.userData.press as Press;
        const mesh = new Mesh(press.geometry(), ink);
        d.add(mesh);
        this.scene.add(d);
        this.doors.push(d);
      }
      // the chair Marin pulls out
      const c = parts.chair;
      const press = c.userData.press as Press;
      c.add(new Mesh(press.geometry(), ink));
      this.scene.add(c);
      this.props.set('chair', { object: c });
      // the cup Margaux sets down, hidden until she does
      const cup = new Mesh(cafeCreme().geometry(), ink);
      cup.visible = false;
      this.scene.add(cup);
      this.props.set('cup', { object: cup });
    }
    // the rain
    this.scene.add(this.rain.mesh);
    // the easel's old man: a tiny silhouette at a dim window
    if (this.quai?.easel) this.addEasel(this.quai.easel);
  }

  /** «L.» at his easel: background only, never larger than a thumbnail, never face-on. */
  private addEasel(at: { center: Vector3; normal: Vector3 }) {
    const c = document.createElement('canvas');
    c.width = 128;
    c.height = 160;
    const g = c.getContext('2d');
    if (!g) return;
    g.fillStyle = 'rgba(20,17,13,0.92)';
    // the easel
    g.fillRect(70, 30, 6, 120);
    g.beginPath();
    g.moveTo(73, 30);
    g.lineTo(100, 150);
    g.lineTo(94, 150);
    g.closePath();
    g.fill();
    g.fillRect(56, 40, 40, 52);
    // the old man, seen from behind and to the side, an arm raised to the canvas
    g.beginPath();
    g.arc(34, 52, 11, 0, Math.PI * 2);
    g.fill();
    g.beginPath();
    g.moveTo(20, 66);
    g.lineTo(48, 66);
    g.lineTo(50, 150);
    g.lineTo(16, 150);
    g.closePath();
    g.fill();
    g.save();
    g.translate(46, 72);
    g.rotate(-0.7);
    g.fillRect(0, -3, 26, 6);
    g.restore();
    const t = new CanvasTexture(c);
    t.colorSpace = NoColorSpace;
    const m = signMaterial(this.world, t, 58, 0);
    m.side = DoubleSide;
    const card = new Mesh(new PlaneGeometry(0.56, 0.7), m);
    const p = at.center.clone().addScaledVector(at.normal, -0.75);
    p.y -= 0.35;
    card.position.copy(p);
    card.lookAt(p.clone().add(at.normal));
    this.scene.add(card);
  }

  /** Put another troupe on stage (the passers-by), or take it off. */
  addTroupe(t: Troupe<Figure>) {
    if (this.extras.includes(t)) return;
    this.extras.push(t);
    this.scene.add(t.group);
  }

  removeTroupe(t: Troupe<Figure>) {
    this.extras = this.extras.filter((x) => x !== t);
    this.scene.remove(t.group);
  }

  /** A pressed piece in the print's own ink, to move about (a passer-by's umbrella). */
  inked(press: Press): Mesh {
    return new Mesh(press.geometry(), this.ink);
  }

  private async loadCast() {
    const t = this.troupe;
    const people: Array<[string, number, Vector3]> = [
      ['augustin_de_roncourt', 1.86, MARKS.boothBench],
      ['marin_leveque', 1.8, MARKS.boothMiddle],
      ['lila_bonnet', 1.62, MARKS.boothLeft],
      ['margaux_barman', 1.66, MARKS.zincInside],
    ];
    let done = 0;
    await Promise.all(
      people.map(async ([key, h, at]) => {
        await t.add({ key, height: h }, at);
        done++;
        if (!this.disposed) this.onProgress?.(0.66 + (done / people.length) * 0.24, 'La troupe');
      }),
    );
    this.alive();
    // Camille: a silhouette in the doorway, later
    const camille = this.art.figure('camille_marchand', 'neutre', null);
    if (camille) {
      const f = await t.add({ key: 'camille_marchand', height: 1.72, silhouette: true }, MARKS.doorOut);
      if (f) f.visible = false;
    }
  }

  private alive() {
    if (this.disposed) throw new LoadCancelled();
  }

  /* ---------------------------------------------------------------------------------------- */
  /* the light                                                                                */
  /* ---------------------------------------------------------------------------------------- */

  setAmbiance(id: AmbianceId) {
    this.ambiance = id;
    applyAmbiance(this.world, this.light());
    this.applyAmbianceExtras();
  }

  private applyAmbianceExtras() {
    const a = this.light();
    this.renderer.setClearColor(new Color(...rgb(a.skyHorizon)));
    this.rain.mesh.visible = a.rain;
    this.halos.visible = a.night > 0.5;
    if (this.neonHalo) this.neonHalo.visible = a.night > 0.5;
    if (this.neon) (this.neon.material as ShaderMaterial).uniforms.uGlow.value = a.night > 0.5 ? 1 : 0.25;
    this.print.set({ fogFar: a.fogFar, halftone: a.night > 0.5 ? 0.42 : 0.6, idLines: a.night > 0.5 ? 0.45 : 0.6 });
  }

  /** The light someone standing here receives (a card, or a person in the round). */
  lightAt(p: Vector3): [number, number, number] {
    const w = this.world;
    const [r, g, b, room] = this.lightMap.sample(p.x, p.z);
    const inside = this.inRoom(p);
    const base = inside
      ? w.uIndoorLit.value.clone().multiplyScalar(0.92)
      : w.uShade.value.clone().lerp(w.uSun.value, 0.62).add(w.uAmbient.value);
    const street = new Vector3(r, g, b).multiplyScalar(w.uStreetLamps.value);
    const lamp = street.add(w.uRoomLamp.value.clone().multiplyScalar(room));
    const e = Math.max(lamp.x, lamp.y, lamp.z);
    const q = e > 0 ? (e > 0.7 ? 1 : e > 0.32 ? 0.7 : e > 0.08 ? 0.42 : 0) : 0;
    const l = base.add(e > 0 ? lamp.multiplyScalar(q / e) : lamp);
    // faces stay legible: never darker than a dim print
    const lum = l.x * 0.3 + l.y * 0.59 + l.z * 0.11;
    if (lum < 0.62) l.multiplyScalar(0.62 / Math.max(lum, 0.01));
    return [Math.min(l.x, 1.15), Math.min(l.y, 1.15), Math.min(l.z, 1.15)];
  }

  inRoom(p: Vector3) {
    // a forged place's hall is lit by the day, like the street
    if (this.site) return false;
    return p.x > ROOM.x0 && p.x < ROOM.x1 && p.z > ROOM.z0 && p.z < ROOM.z1 && p.x + p.z < -36.3;
  }

  get indoors() {
    return this.inRoom(this.feet);
  }

  /* ---------------------------------------------------------------------------------------- */
  /* you                                                                                      */
  /* ---------------------------------------------------------------------------------------- */

  /** Stand somewhere, looking at something. */
  place(at: Vector3, look?: Vector3) {
    this.feet.set(at.x, this.nav.heightAt(at.x, at.z), at.z);
    this.eyeY = this.feet.y + this.eyeHeight;
    if (look) {
      const d = look.clone().sub(new Vector3(at.x, this.eyeY, at.z));
      this.yaw = Math.atan2(-d.x, -d.z);
      this.pitch = Math.atan2(d.y, Math.hypot(d.x, d.z));
    }
    this.route = [];
    this.updateCamera(0, 0);
  }

  setStick(x: number, y: number) {
    this.stick.set(x, y);
  }

  /** Walk to a point along the streets; resolves on arrival (or false if there is no way). */
  walkTo(to: Vector3, speed = WALK_SPEED): Promise<boolean> {
    const path = this.nav.path(this.feet, to);
    if (!path || !path.length) return Promise.resolve(false);
    this.route = path;
    this.routeSpeed = speed;
    return new Promise((resolve) => {
      const prev = this.routeDone;
      this.routeDone = () => resolve(true);
      prev?.();
    });
  }

  stop() {
    this.route = [];
    const done = this.routeDone;
    this.routeDone = null;
    done?.();
  }

  get walking() {
    return this.route.length > 0;
  }

  /** Turn your head toward a point (eased), or let go with null. */
  look(target: Vector3 | null, strength = 3.2) {
    this.lookTarget = target ? target.clone() : null;
    this.lookStrength = strength;
  }

  /** Widen or narrow the lens (60 is the eye; 45 for a silent panel's close look). */
  lens(fov: number) {
    this.fovTarget = fov;
  }

  openDoor(open: boolean) {
    this.doorTarget = open ? 1 : 0;
  }

  /** The neon: 1 lit, 0 dark; a fraction flickers. */
  setNeon(state: number) {
    this.neonState = state;
  }

  /** Show a dotted way from you to a point on the ground (or clear it). */
  showWay(to: Vector3 | null) {
    if (!to) {
      this.dots.count = 0;
      return;
    }
    const path = this.nav.path(this.feet, to);
    if (!path) {
      this.dots.count = 0;
      return;
    }
    const pts = [this.feet.clone(), ...path];
    const m = new Matrix4();
    let n = 0;
    let carry = 1.2;
    for (let i = 0; i < pts.length - 1 && n < 80; i++) {
      const a = pts[i];
      const b = pts[i + 1];
      const len = a.distanceTo(b);
      let s = carry;
      while (s < len && n < 80) {
        const p = a.clone().lerp(b, s / len);
        m.makeTranslation(p.x, this.nav.heightAt(p.x, p.z) + 0.02, p.z);
        this.dots.setMatrixAt(n++, m);
        s += 0.75;
      }
      carry = s - len;
    }
    this.dots.count = n;
    this.dots.instanceMatrix.needsUpdate = true;
  }

  addSpot(s: Spot) {
    this.spots = this.spots.filter((x) => x.id !== s.id).concat(s);
  }

  enableSpot(id: string, on: boolean) {
    const s = this.spots.find((x) => x.id === id);
    if (s) s.enabled = on;
  }

  /* ---------------------------------------------------------------------------------------- */
  /* touch                                                                                    */
  /* ---------------------------------------------------------------------------------------- */

  /** Wire the canvas: drag to look, tap to walk or touch. Returns the unbinder. */
  bindInput() {
    const el = this.opts.canvas;
    const down = (e: PointerEvent) => {
      if (this.pointer) return;
      el.setPointerCapture?.(e.pointerId);
      this.pointer = { id: e.pointerId, x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: performance.now(), moved: false };
    };
    const move = (e: PointerEvent) => {
      const p = this.pointer;
      if (!p || p.id !== e.pointerId) return;
      const dx = e.clientX - p.x;
      const dy = e.clientY - p.y;
      p.x = e.clientX;
      p.y = e.clientY;
      if (Math.hypot(e.clientX - p.sx, e.clientY - p.sy) > 8) p.moved = true;
      if (p.moved) {
        const k = 0.0052;
        this.yaw += dx * k;
        this.pitch = Math.max(-1.15, Math.min(1.05, this.pitch + dy * k));
        this.userLookUntil = performance.now() / 1000 + 2.4;
      }
    };
    const up = (e: PointerEvent) => {
      const p = this.pointer;
      if (!p || p.id !== e.pointerId) return;
      this.pointer = null;
      if (!p.moved && performance.now() - p.t < 450) {
        const r = el.getBoundingClientRect();
        const x = ((e.clientX - r.left) / r.width) * 2 - 1;
        const y = -((e.clientY - r.top) / r.height) * 2 + 1;
        const hit = this.pick(x, y);
        this.listeners.forEach((fn) => fn(hit));
      }
    };
    const key = (e: KeyboardEvent, on: boolean) => {
      const k = e.key.toLowerCase();
      if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright', 'z', 'q'].includes(k)) {
        if (on) this.keys.add(k);
        else this.keys.delete(k);
      }
    };
    const kd = (e: KeyboardEvent) => key(e, true);
    const ku = (e: KeyboardEvent) => key(e, false);
    el.addEventListener('pointerdown', down);
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    window.addEventListener('keydown', kd);
    window.addEventListener('keyup', ku);
    return () => {
      el.removeEventListener('pointerdown', down);
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointercancel', up);
      window.removeEventListener('keydown', kd);
      window.removeEventListener('keyup', ku);
    };
  }

  /** What is under this point of the screen (normalised device coordinates)? */
  pick(x: number, y: number): Hit {
    this.camera.updateMatrixWorld();
    // people first: their cards' boxes on screen
    let best: { key: string; d: number } | null = null;
    const people = [this.troupe, ...this.extras].reduce<Array<[string, Figure]>>((all, t) => all.concat(Array.from(t.people)), []);
    for (const [key, f] of people) {
      const box = f.screenBox(this.camera);
      if (!box) continue;
      if (x >= box[0] && x <= box[2] && y >= box[1] && y <= box[3]) {
        const d = this.camera.position.distanceTo(f.pos);
        if (d < 14 && (!best || d < best.d)) best = { key, d };
      }
    }
    if (best) return { kind: 'person', key: best.key };
    // then the spots
    const aspect = this.camera.aspect;
    for (const s of this.spots) {
      if (!s.enabled) continue;
      const p = s.pos.clone().project(this.camera);
      if (p.z > 1) continue;
      const d = this.camera.position.distanceTo(s.pos);
      const r = (s.radius / Math.max(d, 0.5)) / Math.tan((this.camera.fov * Math.PI) / 360);
      if (Math.hypot((p.x - x) * aspect, p.y - y) < Math.max(r, 0.09)) return { kind: 'spot', id: s.id };
    }
    // then the ground
    const ray = new Raycaster();
    ray.setFromCamera(new Vector2(x, y), this.camera);
    ray.far = 90;
    const hits = ray.intersectObjects(this.pickables, false);
    if (!hits.length) return { kind: 'none' };
    const h = hits[0];
    const point = h.point.clone();
    const n = h.face?.normal ?? new Vector3(0, 1, 0);
    if (Math.abs(n.y) < 0.6) point.addScaledVector(n.clone().setY(0).normalize().multiplyScalar(Math.sign(n.dot(ray.ray.direction)) || 1), -0.7);
    return { kind: 'ground', point };
  }

  /* ---------------------------------------------------------------------------------------- */
  /* the frame                                                                                */
  /* ---------------------------------------------------------------------------------------- */

  start() {
    if (this.started) return;
    this.started = true;
    this.last = performance.now();
    const loop = (t: number) => {
      if (this.disposed) return;
      this.raf = requestAnimationFrame(loop);
      this.frame(t);
    };
    this.raf = requestAnimationFrame(loop);
  }

  pause() {
    cancelAnimationFrame(this.raf);
    this.started = false;
  }

  /** Draw one frame now (tests, screenshots). */
  renderOnce(t = performance.now()) {
    this.frame(t);
  }

  resize() {
    const c = this.opts.canvas;
    const w = Math.max(1, c.clientWidth || c.width);
    const h = Math.max(1, c.clientHeight || c.height);
    this.renderer.setPixelRatio(this.scale);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    const pw = Math.round(w * this.scale);
    const ph = Math.round(h * this.scale);
    this.print.setSize(pw, ph, this.scale);
    if (this.mirrorOn && this.water) {
      const mw = Math.max(64, Math.round(pw / 2));
      const mh = Math.max(64, Math.round(ph / 2));
      if (!this.mirrorRT) {
        this.mirrorRT = new WebGLRenderTarget(mw, mh, { type: HalfFloatType, depthBuffer: true });
        const wm = this.water.material as ShaderMaterial;
        wm.uniforms.uMirror.value = this.mirrorRT.texture;
        wm.uniforms.uMirrorOn.value = 1;
      } else {
        this.mirrorRT.setSize(mw, mh);
      }
    }
  }

  private frame(t: number) {
    const now = t / 1000;
    const dt = Math.min(0.1, Math.max(0, (t - this.last) / 1000));
    this.last = t;
    this.renderer.info.reset();
    this.updateCamera(dt, now);
    this.world.uTime.value = now;
    this.tickers.forEach((fn) => fn(dt, now));
    const indoorAt = (p: Vector3) => this.inRoom(p);
    this.troupe.update(dt, now, this.camera, (p) => this.lightAt(p), indoorAt);
    this.extras.forEach((t) => t.update(dt, now, this.camera, (p) => this.lightAt(p), indoorAt));
    this.props.forEach((p) => {
      if (p.material && p.object.visible) {
        const l = this.lightAt(p.object.position);
        p.material.uniforms.uLight.value.set(l[0], l[1], l[2]);
      }
    });
    const room = this.indoors;
    this.rain.update(now, this.camera.position, this.rainRoom);
    this.updateGlints();
    this.updateNeon(now);
    this.updateDoors(dt);
    if (this.mirrorOn && this.mirrorRT && !room) this.renderMirror();
    this.print.render(this.renderer, this.scene, this.camera);
    this.measure(t, dt);
  }

  private updateCamera(dt: number, now = performance.now() / 1000) {
    // walking: a route, the thumb, or the keys
    let mx = 0;
    let mz = 0;
    if (!this.frozen) {
      const k = this.keys;
      const fwd = (k.has('w') || k.has('z') || k.has('arrowup') ? 1 : 0) - (k.has('s') || k.has('arrowdown') ? 1 : 0);
      const side = (k.has('d') || k.has('arrowright') ? 1 : 0) - (k.has('a') || k.has('q') || k.has('arrowleft') ? 1 : 0);
      const sx = this.stick.x + side;
      const sy = -this.stick.y + fwd;
      if (Math.hypot(sx, sy) > 0.08) {
        if (this.route.length) this.stop();
        const len = Math.min(1, Math.hypot(sx, sy));
        const a = Math.atan2(sx, sy);
        const dir = this.yaw + -a;
        // up to a stroll for most of the thumb's travel, then a stride toward the rim
        const pace = len < 0.7 ? (WALK_SPEED * len) / 0.7 : WALK_SPEED + ((STRIDE - WALK_SPEED) * (len - 0.7)) / 0.3;
        mx = -Math.sin(dir) * pace * dt;
        mz = -Math.cos(dir) * pace * dt;
      }
    }
    if (this.route.length && !this.frozen) {
      const target = this.route[0];
      const d = new Vector3(target.x - this.feet.x, 0, target.z - this.feet.z);
      const dist = d.length();
      const step = this.routeSpeed * dt;
      if (dist <= Math.max(step, 0.02)) {
        this.feet.x = target.x;
        this.feet.z = target.z;
        this.route.shift();
        if (!this.route.length) {
          const done = this.routeDone;
          this.routeDone = null;
          done?.();
        }
      } else {
        mx = (d.x / dist) * step;
        mz = (d.z / dist) * step;
        // the head turns toward the way, gently, unless you are looking about
        if (now > this.userLookUntil && !this.lookTarget) {
          const want = Math.atan2(-d.x, -d.z);
          this.yaw = turnToward(this.yaw, want, dt * 2.2);
          this.pitch += (-0.06 - this.pitch) * Math.min(1, dt * 2);
        }
      }
    }
    if (mx || mz) {
      const [nx, nz] = this.route.length ? [this.feet.x + mx, this.feet.z + mz] : this.nav.slide(this.feet.x, this.feet.z, mx, mz);
      this.feet.x = nx;
      this.feet.z = nz;
    }
    const ground = this.nav.heightAt(this.feet.x, this.feet.z);
    this.feet.y = ground;
    this.eyeY += (ground + this.eyeHeight - this.eyeY) * Math.min(1, dt * 9 || 1);
    // the director's look, unless your thumb is looking
    if (this.lookTarget && now > this.userLookUntil) {
      const d = this.lookTarget.clone().sub(new Vector3(this.feet.x, this.eyeY, this.feet.z));
      const wantYaw = Math.atan2(-d.x, -d.z);
      const wantPitch = Math.atan2(d.y, Math.hypot(d.x, d.z));
      const k = Math.min(1, dt * this.lookStrength);
      this.yaw = turnToward(this.yaw, wantYaw, k * Math.PI);
      this.pitch += (wantPitch - this.pitch) * k;
    }
    const fov = this.camera.fov + (this.fovTarget - this.camera.fov) * Math.min(1, dt * 2.5 || 1);
    // nothing is drawn past the fog (or, indoors, past what the windows show)
    const far = this.inRoom(this.feet) ? 90 : this.light().fogFar + 12;
    if (Math.abs(fov - this.camera.fov) > 0.01 || far !== this.camera.far) {
      this.camera.fov = fov;
      this.camera.far = far;
      this.camera.updateProjectionMatrix();
    }
    this.camera.position.set(this.feet.x, this.eyeY, this.feet.z);
    this.camera.rotation.set(this.pitch, this.yaw, 0);
    this.camera.updateMatrixWorld();
    if (this.sky) this.sky.position.copy(this.camera.position);
    const reach = this.inRoom(this.feet) ? 30 : 64;
    for (const f of this.fines) f.mesh.visible = f.center.distanceTo(this.camera.position) - f.radius < reach;
  }

  private updateGlints() {
    const w = this.world;
    const on = w.uStreetLamps.value > 0.5 && !this.indoors;
    if (!on) {
      w.uGlintCount.value = 0;
      return;
    }
    const eye = this.camera.position;
    const near = this.glints
      .map((l) => ({ l, d: l.pos.distanceTo(eye) }))
      .filter((x) => x.d < 75)
      .sort((a, b) => a.d - b.d)
      .slice(0, MAX_GLINTS);
    near.forEach(({ l, d }, i) => {
      w.uGlintPos.value[i].set(l.pos.x, l.pos.y, l.pos.z, l.range);
      const fade = 1 - Math.max(0, Math.min(1, (d - 50) / 25));
      const neon = l.color[0] > 0.7 && l.color[1] < 0.35 ? this.neonState : 1;
      w.uGlintCol.value[i].set(l.color[0], l.color[1], l.color[2], fade * neon * Math.min(1, l.power));
    });
    w.uGlintCount.value = near.length;
  }

  private updateNeon(now: number) {
    if (!this.neon || !this.neonHalo) return;
    // a neon breathes: a flicker now and then, and the letters' slight hum
    const m = this.neon.material as ShaderMaterial;
    const night = this.world.uNight.value > 0.5;
    const blink = Math.sin(now * 37.0) > 0.985 || (Math.sin(now * 0.7) > 0.995 && Math.sin(now * 53.0) > 0);
    const f = (night ? (blink ? 0.6 : 1) : 1) * this.neonState;
    m.uniforms.uFlicker.value = f;
    (this.neonHalo.material as ShaderMaterial).uniforms.uStrength.value = 0.55 * f;
    // the halo faces you
    this.neonHalo.quaternion.copy(this.camera.quaternion);
  }

  private updateDoors(dt: number) {
    this.doorOpen += (this.doorTarget - this.doorOpen) * Math.min(1, dt * 5);
    for (const d of this.doors) {
      const sign = d.userData.sign as number;
      const leaf = d.children[0];
      if (leaf) leaf.rotation.y = sign * this.doorOpen * 1.35;
    }
  }

  private renderMirror() {
    const water = this.water;
    if (!water) return;
    const cam = this.camera;
    const frustum = new Frustum().setFromProjectionMatrix(new Matrix4().multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
    if (!frustum.intersectsBox(this.waterBox)) return;
    const h = PLAN.water;
    const mc = this.mirrorCam;
    mc.fov = cam.fov;
    mc.aspect = cam.aspect;
    mc.near = cam.near;
    mc.far = cam.far;
    mc.position.set(cam.position.x, 2 * h - cam.position.y, cam.position.z);
    const dir = new Vector3();
    cam.getWorldDirection(dir);
    const target = cam.position.clone().add(dir);
    target.y = 2 * h - target.y;
    mc.up.set(0, 1, 0).applyQuaternion(cam.quaternion);
    mc.up.y *= -1;
    mc.lookAt(target);
    mc.updateProjectionMatrix();
    mc.updateMatrixWorld();
    mc.matrixWorldInverse.copy(mc.matrixWorld).invert();
    this.mirrorMatrix.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
    this.mirrorMatrix.multiply(mc.projectionMatrix).multiply(mc.matrixWorldInverse);
    // clip everything below the water with an oblique near plane
    const plane = new Plane(new Vector3(0, 1, 0), -h).applyMatrix4(mc.matrixWorldInverse);
    const clip = new Vector4(plane.normal.x, plane.normal.y, plane.normal.z, plane.constant);
    const pm = mc.projectionMatrix;
    const q = new Vector4(
      (Math.sign(clip.x) + pm.elements[8]) / pm.elements[0],
      (Math.sign(clip.y) + pm.elements[9]) / pm.elements[5],
      -1.0,
      (1.0 + pm.elements[10]) / pm.elements[14],
    );
    clip.multiplyScalar(2.0 / clip.dot(q));
    pm.elements[2] = clip.x;
    pm.elements[6] = clip.y;
    pm.elements[10] = clip.z + 1.0 - 0.003;
    pm.elements[14] = clip.w;
    const wm = water.material as ShaderMaterial;
    wm.uniforms.uMirrorMatrix.value.copy(this.mirrorMatrix);
    water.visible = false;
    this.rain.mesh.visible = false;
    this.troupe.group.visible = false;
    this.extras.forEach((t) => (t.group.visible = false));
    this.dots.visible = false;
    const halosWere = this.halos.visible;
    this.renderer.setRenderTarget(this.mirrorRT);
    this.renderer.render(this.scene, mc);
    this.renderer.setRenderTarget(null);
    water.visible = true;
    this.rain.mesh.visible = AMBIANCES[this.ambiance].rain;
    this.troupe.group.visible = true;
    this.extras.forEach((t) => (t.group.visible = true));
    this.dots.visible = true;
    this.halos.visible = halosWere;
  }

  private measure(t: number, dt: number) {
    this.times.push(dt * 1000);
    if (this.times.length > 40) this.times.shift();
    const avg = this.times.reduce((s, x) => s + x, 0) / this.times.length;
    const info = this.renderer.info;
    this.stats = {
      fps: avg > 0 ? 1000 / avg : 0,
      frameMs: avg,
      calls: info.render.calls,
      triangles: info.render.triangles,
      scale: this.scale,
      textures: info.memory.textures,
      geometries: info.memory.geometries,
    };
    if (this.resolution !== 'auto' || this.times.length < 40 || t - this.lastScaleChange < 1500) return;
    const max = Math.min(2, window.devicePixelRatio || 1);
    if (avg > 21 && this.scale > 0.75) {
      this.scale = Math.max(0.75, this.scale - 0.15);
      this.lastScaleChange = t;
      this.resize();
    } else if (avg < 14.5 && this.scale < max) {
      this.scale = Math.min(max, this.scale + 0.1);
      this.lastScaleChange = t;
      this.resize();
    }
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.scene.traverse((o) => {
      const m = o as Mesh;
      if (m.geometry) m.geometry.dispose();
      const mat = m.material as ShaderMaterial | ShaderMaterial[] | undefined;
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
      else mat?.dispose();
    });
    this.troupe.dispose();
    this.print.dispose();
    this.mirrorRT?.dispose();
    this.lightMap?.texture.dispose();
    this.renderer.dispose();
  }
}

/** Turn an angle toward another by at most `max` radians, the short way round. */
export function turnToward(a: number, b: number, max: number) {
  let d = b - a;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return a + Math.max(-max, Math.min(max, d));
}

const HALO_INSTANCED_VERT = /* glsl */ `
uniform float uSize;
varying vec2 vUv;
void main() {
  vUv = uv;
  vec4 c = modelViewMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
  c.xy += position.xy * uSize;
  gl_Position = projectionMatrix * c;
}
`;
