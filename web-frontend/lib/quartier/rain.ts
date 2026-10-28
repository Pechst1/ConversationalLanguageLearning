/**
 * Le Quartier · rain, the way a print shows it: thin pale strokes on a slant.
 *
 * A few thousand strokes in a box that travels with you; each stroke stays put in the world
 * while you walk and only wraps round when it leaves the box, so the rain never swims. Strokes
 * inside a room are dropped, so it does not rain in Le Mistral. One draw call.
 */
import {
  AddEquation,
  CustomBlending,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  Mesh,
  OneFactor,
  OneMinusSrcAlphaFactor,
  PlaneGeometry,
  ShaderMaterial,
  SrcAlphaFactor,
  Vector2,
  Vector3,
  Vector4,
  ZeroFactor,
} from 'three';

import { INKS, mix, rgb } from './palette';

const VERT = /* glsl */ `
attribute vec4 aSeed;
uniform vec3 uCenter;
uniform vec3 uBox;
uniform float uTime;
uniform float uSpeed;
uniform vec2 uWind;
uniform vec4 uRoom;
uniform float uLength;
uniform float uWidth;
varying float vA;
varying float vT;
void main() {
  vec3 lo = uCenter - uBox * 0.5;
  float fall = uTime * uSpeed * (0.85 + aSeed.w * 0.3);
  vec3 p;
  p.x = lo.x + mod(aSeed.x * uBox.x - lo.x + uWind.x * fall * 0.12, uBox.x);
  p.z = lo.z + mod(aSeed.y * uBox.z - lo.z + uWind.y * fall * 0.12, uBox.z);
  p.y = lo.y + uBox.y - mod(aSeed.z * uBox.y + fall, uBox.y);
  vec3 dir = normalize(vec3(uWind.x * 0.12, -1.0, uWind.y * 0.12));
  float len = uLength * (0.7 + aSeed.w * 0.6);
  vec3 base = p + dir * (position.y + 0.5) * len;
  vec4 mv = viewMatrix * vec4(base, 1.0);
  mv.x += position.x * uWidth;
  gl_Position = projectionMatrix * mv;
  float inRoom = step(uRoom.x, p.x) * step(p.x, uRoom.z) * step(uRoom.y, p.z) * step(p.z, uRoom.w);
  // strokes fade near the box's edges and right at the eye
  vec3 rel = (p - uCenter) / (uBox * 0.5);
  float edge = 1.0 - smoothstep(0.7, 1.0, max(abs(rel.x), abs(rel.z)));
  float near = smoothstep(0.8, 2.2, length(p - cameraPosition));
  vA = edge * near * (1.0 - inRoom);
  vT = position.y + 0.5;
  if (inRoom > 0.5) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
}
`;

const FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
varying float vA;
varying float vT;
void main() {
  float a = vA * uOpacity * smoothstep(0.0, 0.35, vT) * smoothstep(1.0, 0.6, vT);
  if (a < 0.01) discard;
  gl_FragColor = vec4(uColor, a);
}
`;

export class Rain {
  readonly mesh: Mesh;
  readonly material: ShaderMaterial;

  constructor(count = 2400) {
    const quad = new PlaneGeometry(1, 1);
    const g = new InstancedBufferGeometry();
    g.index = quad.index;
    g.setAttribute('position', quad.getAttribute('position'));
    g.setAttribute('uv', quad.getAttribute('uv'));
    const seeds = new Float32Array(count * 4);
    let s = 987654321;
    const rnd = () => {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 4294967296;
    };
    for (let i = 0; i < seeds.length; i++) seeds[i] = rnd();
    g.setAttribute('aSeed', new InstancedBufferAttribute(seeds, 4));
    g.instanceCount = count;
    const c = rgb(mix(INKS.card, INKS.cobalt, 0.18));
    this.material = new ShaderMaterial({
      name: 'rain',
      uniforms: {
        uCenter: { value: new Vector3() },
        uBox: { value: new Vector3(26, 16, 26) },
        uTime: { value: 0 },
        uSpeed: { value: 9.5 },
        uWind: { value: new Vector2(1.4, 0.6) },
        uRoom: { value: new Vector4(0, 0, -1, -1) },
        uLength: { value: 0.55 },
        uWidth: { value: 0.012 },
        uColor: { value: new Vector3(c[0], c[1], c[2]) },
        uOpacity: { value: 0.5 },
      },
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
    });
    const m = this.material;
    m.blending = CustomBlending;
    m.blendEquation = AddEquation;
    m.blendSrc = SrcAlphaFactor;
    m.blendDst = OneMinusSrcAlphaFactor;
    m.blendSrcAlpha = ZeroFactor;
    m.blendDstAlpha = OneFactor;
    this.mesh = new Mesh(g, m);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 5;
  }

  /** Keep the box round the eye; `room` is a box (x0, z0, x1, z1) where it does not rain. */
  update(time: number, eye: Vector3, room: Vector4) {
    const u = this.material.uniforms;
    u.uTime.value = time;
    u.uCenter.value.set(eye.x, eye.y + 2, eye.z);
    u.uRoom.value.copy(room);
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.material.dispose();
  }
}
