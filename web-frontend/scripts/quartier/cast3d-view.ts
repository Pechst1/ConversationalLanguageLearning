/**
 * Le Quartier · the cast's photo booth: the people in the round, each from a few sides, printed
 * by the quarter's own print pass, tiled into one sheet for `cast3d-sheet.mjs` to save.
 *
 *   window.__CAST = { people, views, tile, expression, ambiance, pose, cell }
 */
import {
  CylinderGeometry,
  Mesh,
  PerspectiveCamera,
  Scene,
  ShaderMaterial,
  Vector3,
  WebGLRenderer,
} from 'three';

import { DEFAULT_AVATAR, normalizeAvatar } from '../../lib/avatar';
import { personAvatar } from '../../lib/quartier/avatars';
import { avatarPerson } from '../../lib/quartier/cast3d/avatar';
import { makeWorld, applyAmbiance } from '../../lib/quartier/materials';
import { AMBIANCES, INKS, rgb } from '../../lib/quartier/palette';
import { PrintPass } from '../../lib/quartier/print';
import { buildModel } from '../../lib/quartier/cast3d/model';
import type { Model } from '../../lib/quartier/cast3d/model';
import { PEOPLE, personFor } from '../../lib/quartier/cast3d/people';
import { applyPose } from '../../lib/quartier/cast3d/pose';
import type { Pose } from '../../lib/quartier/cast3d/pose';
import { GESTURES, ModelFigure } from '../../lib/quartier/cast3d/figure';

interface View {
  /** degrees round the figure, 0 face-on */
  yaw: number;
  pitch?: number;
  dist?: number;
  /** what the camera looks at, as a share of the figure's height */
  at?: number;
  fov?: number;
}

/** A moment of acting, for the acts sheet: a column per act. */
interface Act {
  expression?: string;
  gesture?: string;
  /** how far through the gesture, 0 to 1 */
  u?: number;
  /** walking, at this many seconds into the walk */
  walk?: number;
  talk?: boolean;
  seat?: number;
  /** a bow, this far through it */
  bow?: number;
  hop?: number;
}

/** Someone the avatar kit draws: rolled from `seed` with `look` over it, or without a seed the kit's default record with `look` over it. */
interface AvatarSpec {
  key: string;
  seed?: number;
  look?: Record<string, string | boolean>;
  height?: number;
  /** their lighter body, the one that stands in for them across the square, up close */
  far?: boolean;
}

interface Config {
  acts?: Act[];
  people?: string[];
  avatars?: AvatarSpec[];
  views?: View[];
  tile?: [number, number];
  expression?: string;
  ambiance?: 'matin' | 'nuit' | 'room';
  pose?: 'bind' | 'rest';
  cell?: number;
  variant?: string;
}

declare global {
  interface Window {
    __CAST?: Config;
    __castDone?: { ok: boolean; error?: string; triangles: Record<string, number>; ms: number };
  }
}

const FLOOR = /* glsl */ `
varying vec3 vN;
void main() { vN = normal; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const FLOOR_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uId;
varying vec3 vN;
void main() {
  float band = vN.y > 0.5 ? 2.0 : 1.0;
  gl_FragColor = vec4(uColor * (band > 1.5 ? 1.0 : 0.82), (uId * 4.0 + band) / 255.0);
}
`;

function flat(color: number, id: number) {
  const c = rgb(color);
  return new ShaderMaterial({ uniforms: { uColor: { value: new Vector3(c[0], c[1], c[2]) }, uId: { value: id } }, vertexShader: FLOOR, fragmentShader: FLOOR_FRAG });
}

async function main() {
  const t0 = performance.now();
  const cfg = window.__CAST ?? {};
  const people = (
    cfg.avatars?.length
      ? cfg.avatars.map((a) => {
          const person = avatarPerson(a.seed === undefined ? normalizeAvatar({ ...DEFAULT_AVATAR, ...a.look }) : personAvatar(a.seed, a.look), { key: a.key, height: a.height, seed: a.seed });
          return a.far ? { ...person, ...person.far, far: undefined } : person;
        })
      : cfg.people?.length
        ? cfg.people.map((k) => personFor(k)).filter((p) => p !== null)
        : PEOPLE
  ) as typeof PEOPLE[number][];
  const views: View[] = cfg.views ?? [{ yaw: 0 }, { yaw: 35 }, { yaw: 90 }, { yaw: 180 }, { yaw: 0, at: 0.86, dist: 1.0, fov: 30 }];
  const [tw, th] = cfg.tile ?? [300, 460];
  const canvas = document.createElement('canvas');
  const W = tw * views.length;
  const H = th * people.length;
  canvas.width = W;
  canvas.height = H;
  canvas.style.width = `${W}px`;
  canvas.style.height = `${H}px`;
  document.body.appendChild(canvas);
  const renderer = new WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, premultipliedAlpha: false });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H, false);
  renderer.autoClear = true;
  // the paper behind them: the sky's id (no lines) in the lit band (no halftone)
  const paper = rgb(0xe9e2d3);
  renderer.setClearColor((Math.round(paper[0] * 255) << 16) | (Math.round(paper[1] * 255) << 8) | Math.round(paper[2] * 255), 2 / 255);
  const world = makeWorld();
  applyAmbiance(world, AMBIANCES[cfg.ambiance === 'nuit' ? 'nuit' : 'matin']);
  const print = new PrintPass(tw, th, { line: 1, idLines: 0.6, halftone: 0.6, grain: 1 });
  print.setSize(tw, th, 1);
  const triangles: Record<string, number> = {};

  if (cfg.acts?.length) {
    const acts = cfg.acts;
    const vw = views[0];
    const W2 = tw * acts.length;
    canvas.width = W2;
    canvas.style.width = `${W2}px`;
    renderer.setSize(W2, H, false);
    for (let row = 0; row < people.length; row++) {
      const person = people[row];
      for (let col = 0; col < acts.length; col++) {
        const act = acts[col];
        const scene = new Scene();
        const floor = new Mesh(new CylinderGeometry(2.2, 2.2, 0.04, 48), flat(INKS.paper, 2));
        floor.position.y = -0.02;
        scene.add(floor);
        const fig = new ModelFigure(world, person, { key: person.key, height: person.body.height }, { variant: cfg.variant });
        triangles[person.key] = fig.model.triangles;
        scene.add(fig.root);
        const height = person.body.height;
        const cam = new PerspectiveCamera(vw.fov ?? 34, tw / th, 0.05, 60);
        const yaw = (vw.yaw * Math.PI) / 180;
        const pitch = ((vw.pitch ?? 4) * Math.PI) / 180;
        const dist = vw.dist ?? 3.9;
        const at = new Vector3(0, height * (vw.at ?? 0.52), 0);
        cam.position.set(Math.sin(yaw) * Math.cos(pitch) * dist, at.y + Math.sin(pitch) * dist, Math.cos(yaw) * Math.cos(pitch) * dist);
        cam.lookAt(at);
        cam.updateMatrixWorld();
        fig.place(new Vector3(0, 0, 0));
        const light: [number, number, number] = [1, 1, 1];
        {
          const l = world.uShade.value.clone().lerp(world.uSun.value, 0.62).add(world.uAmbient.value);
          const lum = l.x * 0.3 + l.y * 0.59 + l.z * 0.11;
          if (lum < 0.62) l.multiplyScalar(0.62 / lum);
          light[0] = l.x;
          light[1] = l.y;
          light[2] = l.z;
        }
        const T = performance.now() / 1000;
        const dt = 1 / 30;
        let now = T;
        // settle into the stance and the mood
        fig.express(act.expression ?? 'neutre', null);
        for (let i = 0; i < 45; i++) fig.update(dt, (now += dt), cam, light);
        if (act.seat) {
          fig.seat = act.seat;
          for (let i = 0; i < 30; i++) fig.update(dt, (now += dt), cam, light);
        }
        let until = now;
        if (act.gesture && GESTURES[act.gesture]) {
          fig.express(act.expression ?? 'neutre', act.gesture);
          // gestures start from the wall clock; run the clock that far
          const start = performance.now() / 1000;
          until = start + (act.u ?? 0.5) * GESTURES[act.gesture].seconds;
          now = start;
        }
        if (act.bow !== undefined) {
          fig.bow(0.6, 1.3);
          const start = performance.now() / 1000;
          until = start + act.bow * 1.3;
          now = start;
        }
        if (act.hop !== undefined) {
          fig.hop();
          const start = performance.now() / 1000;
          until = start + act.hop * 0.42;
          now = start;
        }
        if (act.talk) fig.talk(30);
        if (act.walk !== undefined) {
          const dir = new Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
          fig.walk([dir.clone().multiplyScalar(40)], 1.2);
          until = now + act.walk;
        }
        while (now < until) fig.update(dt, (now += dt), cam, light);
        fig.update(0.0001, now, cam, light);
        if (act.walk !== undefined) fig.root.position.set(0, 0, 0);
        fig.root.updateMatrixWorld(true);
        renderer.setViewport(col * tw, H - (row + 1) * th, tw, th);
        renderer.setScissor(col * tw, H - (row + 1) * th, tw, th);
        renderer.setScissorTest(true);
        print.render(renderer, scene, cam);
        fig.dispose();
      }
    }
    window.__castDone = { ok: true, triangles, ms: Math.round(performance.now() - t0) };
    return;
  }

  for (let row = 0; row < people.length; row++) {
    const person = people[row];
    const scene = new Scene();
    const floor = new Mesh(new CylinderGeometry(2.2, 2.2, 0.04, 48), flat(INKS.paper, 2));
    floor.position.y = -0.02;
    scene.add(floor);
    const model: Model = buildModel(world, person, { variant: cfg.variant, cell: cfg.cell ?? 512 });
    triangles[person.key] = model.triangles;
    model.print.draw(cfg.expression ?? 'neutre');
    const pose: Pose = cfg.pose === 'bind' ? {} : person.manner?.rest ?? {};
    applyPose(model, pose);
    scene.add(model.mesh);
    const u = model.material.uniforms;
    const room = cfg.ambiance === 'room';
    u.uIndoor.value = room ? 1 : 0;
    if (room) {
      const l = world.uIndoorLit.value.clone().multiplyScalar(0.92);
      u.uLight.value.copy(l);
    } else {
      const l = world.uShade.value.clone().lerp(world.uSun.value, 0.62).add(world.uAmbient.value);
      const lum = l.x * 0.3 + l.y * 0.59 + l.z * 0.11;
      if (lum < 0.62) l.multiplyScalar(0.62 / lum);
      u.uLight.value.copy(l);
    }
    const height = person.body.height;
    for (let col = 0; col < views.length; col++) {
      const vw = views[col];
      const cam = new PerspectiveCamera(vw.fov ?? 34, tw / th, 0.05, 60);
      const yaw = (vw.yaw * Math.PI) / 180;
      const pitch = ((vw.pitch ?? 4) * Math.PI) / 180;
      const dist = vw.dist ?? 3.9;
      const at = new Vector3(0, height * (vw.at ?? 0.52), 0);
      cam.position.set(Math.sin(yaw) * Math.cos(pitch) * dist, at.y + Math.sin(pitch) * dist, Math.cos(yaw) * Math.cos(pitch) * dist);
      cam.lookAt(at);
      cam.updateMatrixWorld();
      // the key: from above, a little toward the eye
      const toCam = cam.position.clone().sub(at).setY(0).normalize();
      u.uKey.value.set(0, 1, 0).multiplyScalar(0.62).addScaledVector(toCam, 0.55).add(new Vector3(0.18, 0, 0)).normalize();
      model.mesh.updateMatrixWorld(true);
      renderer.setViewport(col * tw, H - (row + 1) * th, tw, th);
      renderer.setScissor(col * tw, H - (row + 1) * th, tw, th);
      renderer.setScissorTest(true);
      print.render(renderer, scene, cam);
    }
    model.dispose();
  }
  window.__castDone = { ok: true, triangles, ms: Math.round(performance.now() - t0) };
}

main().catch((e: unknown) => {
  window.__castDone = { ok: false, error: e instanceof Error ? `${e.message}\n${e.stack}` : String(e), triangles: {}, ms: 0 };
});
