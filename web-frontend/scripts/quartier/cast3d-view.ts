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

import { makeWorld, applyAmbiance } from '../../lib/quartier/materials';
import { AMBIANCES, INKS, rgb } from '../../lib/quartier/palette';
import { PrintPass } from '../../lib/quartier/print';
import { buildModel } from '../../lib/quartier/cast3d/model';
import type { Model } from '../../lib/quartier/cast3d/model';
import { PEOPLE, personFor } from '../../lib/quartier/cast3d/people';
import { applyPose } from '../../lib/quartier/cast3d/pose';
import type { Pose } from '../../lib/quartier/cast3d/pose';

interface View {
  /** degrees round the figure, 0 face-on */
  yaw: number;
  pitch?: number;
  dist?: number;
  /** what the camera looks at, as a share of the figure's height */
  at?: number;
  fov?: number;
}

interface Config {
  people?: string[];
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
  const people = (cfg.people?.length ? cfg.people.map((k) => personFor(k)).filter((p) => p !== null) : PEOPLE) as typeof PEOPLE[number][];
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
