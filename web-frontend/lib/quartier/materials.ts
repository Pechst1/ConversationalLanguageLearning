/**
 * Le Quartier · the inks on the plate.
 *
 * Every material here prints the same way: the surface's ink, darkened by one of three light
 * bands (lit, middle, shadow) whose colours come from the ambiance, never from grey. At night
 * the lamps add their pools from a light map baked once for the whole quarter, quantised into
 * hard-edged rings like a second ink pass. Patterns (setts, tiles, boards, stone courses, zinc
 * seams) are drawn from world position, so the quarter needs no image textures at all.
 *
 * Each fragment writes its line id and its band into alpha for the print pass (`print.ts`),
 * which lays the ink lines, the halftone and the paper over everything in one go.
 */
import {
  AdditiveBlending,
  Color,
  CustomBlending,
  DoubleSide,
  FrontSide,
  OneFactor,
  ShaderMaterial,
  SrcAlphaFactor,
  OneMinusSrcAlphaFactor,
  Texture,
  Vector2,
  Vector3,
  Vector4,
  ZeroFactor,
  AddEquation,
  BackSide,
  Matrix4,
} from 'three';

import type { Ambiance } from './palette';
import { rgb } from './palette';

export const MAX_GLINTS = 8;

/** Uniforms every material shares (the same objects, so one write updates the whole plate). */
export interface World {
  uSunDir: { value: Vector3 };
  uSun: { value: Vector3 };
  uShade: { value: Vector3 };
  uAmbient: { value: Vector3 };
  uSkyTop: { value: Vector3 };
  uSkyHorizon: { value: Vector3 };
  uFog: { value: Vector2 };
  uNight: { value: number };
  uRain: { value: number };
  uTime: { value: number };
  uLightMap: { value: Texture | null };
  /** x0, z0, 1/width, 1/depth of the light map's ground rectangle */
  uLightRect: { value: Vector4 };
  uIndoorLit: { value: Vector3 };
  uIndoorShade: { value: Vector3 };
  /** 1 when the street lamps are on */
  uStreetLamps: { value: number };
  /** the colour of the rooms' own lamps */
  uRoomLamp: { value: Vector3 };
  /** the brightest lamps near the eye, for the streaks they leave on wet stone and water */
  uGlintPos: { value: Vector4[] };
  uGlintCol: { value: Vector4[] };
  uGlintCount: { value: number };
}

const vec3Of = (c: [number, number, number]) => new Vector3(c[0], c[1], c[2]);

export function makeWorld(): World {
  return {
    uSunDir: { value: new Vector3(0, 1, 0) },
    uSun: { value: new Vector3(1, 1, 1) },
    uShade: { value: new Vector3(0.6, 0.6, 0.8) },
    uAmbient: { value: new Vector3(0, 0, 0) },
    uSkyTop: { value: new Vector3(0.3, 0.4, 0.7) },
    uSkyHorizon: { value: new Vector3(0.9, 0.9, 0.85) },
    uFog: { value: new Vector2(40, 200) },
    uNight: { value: 0 },
    uRain: { value: 0 },
    uTime: { value: 0 },
    uLightMap: { value: null },
    uLightRect: { value: new Vector4(0, 0, 1, 1) },
    uIndoorLit: { value: new Vector3(1.08, 0.94, 0.74) },
    uIndoorShade: { value: new Vector3(0.62, 0.48, 0.42) },
    uStreetLamps: { value: 1 },
    uRoomLamp: { value: new Vector3(1.0, 0.82, 0.5) },
    uGlintPos: { value: Array.from({ length: MAX_GLINTS }, () => new Vector4()) },
    uGlintCol: { value: Array.from({ length: MAX_GLINTS }, () => new Vector4()) },
    uGlintCount: { value: 0 },
  };
}

/** Pour an ambiance into the shared uniforms. */
export function applyAmbiance(world: World, a: Ambiance) {
  world.uSunDir.value.set(a.sunDir[0], a.sunDir[1], a.sunDir[2]).normalize();
  world.uSun.value.copy(vec3Of(a.sun));
  world.uShade.value.copy(vec3Of(a.shade));
  world.uAmbient.value.copy(vec3Of(a.ambient));
  world.uSkyTop.value.copy(vec3Of(rgb(a.skyTop)));
  world.uSkyHorizon.value.copy(vec3Of(rgb(a.skyHorizon)));
  world.uFog.value.set(a.fogNear, a.fogFar);
  world.uNight.value = a.night;
  world.uRain.value = a.rain ? 1 : 0;
  world.uStreetLamps.value = a.night;
  if (a.night > 0.5) {
    world.uIndoorLit.value.set(1.06, 0.97, 0.84);
    world.uIndoorShade.value.set(0.6, 0.5, 0.48);
  } else {
    world.uIndoorLit.value.set(1.0, 0.95, 0.84);
    world.uIndoorShade.value.set(0.64, 0.6, 0.66);
  }
}

/* ------------------------------------------------------------------------------------------ */
/* GLSL                                                                                       */
/* ------------------------------------------------------------------------------------------ */

const COMMON = /* glsl */ `
uniform vec3 uSunDir;
uniform vec3 uSun;
uniform vec3 uShade;
uniform vec3 uAmbient;
uniform vec3 uSkyTop;
uniform vec3 uSkyHorizon;
uniform vec2 uFog;
uniform float uNight;
uniform float uRain;
uniform float uTime;
uniform sampler2D uLightMap;
uniform vec4 uLightRect;
uniform vec3 uIndoorLit;
uniform vec3 uIndoorShade;
uniform float uStreetLamps;
uniform vec3 uRoomLamp;

float packMark(float id, float band) { return (id * 4.0 + band) / 255.0; }

float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

float noise2(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x), mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x), u.y);
}

// the three bands of the sun (or the moon); band: 0 shadow, 1 middle, 2 lit
vec3 sunRamp(vec3 n, out float band) {
  float d = dot(n, uSunDir);
  float lit = smoothstep(0.28, 0.34, d);
  float mid = smoothstep(-0.06, 0.0, d);
  band = lit > 0.5 ? 2.0 : (mid > 0.5 ? 1.0 : 0.0);
  vec3 middle = mix(uShade, uSun, 0.56);
  return mix(uShade, mix(middle, uSun, lit), mid);
}

// indoors: light from the globes above, warm bands
vec3 roomRamp(vec3 n, out float band) {
  float d = n.y * 0.7 + 0.3 * dot(n, normalize(vec3(0.3, 0.2, 0.9)));
  float lit = smoothstep(0.32, 0.38, d);
  float mid = smoothstep(-0.2, -0.14, d);
  band = lit > 0.5 ? 2.0 : (mid > 0.5 ? 1.0 : 0.0);
  vec3 middle = mix(uIndoorShade, uIndoorLit, 0.6);
  return mix(uIndoorShade, mix(middle, uIndoorLit, lit), mid);
}

// the lamps' pools, from the baked map, in three hard steps: rgb is the lamp's tint (its
// brightest channel at 1), a the step (0, 0.42, 0.76 or 1.1). Street lamps light the street,
// the café's lamps light the café; a lamp hangs at about four metres, so what is above it is lit
// from below (the underside of a plane tree's crown) and what is below it from above.
vec4 lampPools(vec3 w, vec3 n, int indoor) {
  vec2 uv = (w.xz - uLightRect.xy) * uLightRect.zw;
  if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return vec4(0.0);
  vec4 m = texture2D(uLightMap, uv) * 4.0;
  vec3 l = indoor == 1 ? uRoomLamp * m.a : m.rgb * uStreetLamps;
  float above = smoothstep(3.6, 4.6, w.y);
  float facing = indoor == 1
    ? (n.y < -0.5 ? 0.0 : 0.62 + 0.38 * max(n.y, 0.0))
    : mix(0.45 + 0.55 * max(n.y, 0.0), 0.15 + 0.85 * max(-n.y, 0.0), above);
  float lift = indoor == 1 ? 1.0 : clamp(1.0 - max(w.y - 5.0, 0.0) / 6.0, 0.0, 1.0);
  l *= lift * facing;
  float e = max(max(l.r, l.g), l.b);
  if (e <= 0.0) return vec4(0.0);
  float q = smoothstep(0.07, 0.1, e) * 0.42 + smoothstep(0.32, 0.36, e) * 0.34 + smoothstep(0.7, 0.75, e) * 0.34;
  return vec4(l / e, q);
}

vec3 fogged(vec3 col, vec3 w) {
  float dist = length(w - cameraPosition);
  float f = smoothstep(uFog.x, uFog.y, dist);
  return mix(col, uSkyHorizon, f);
}

// world-space patterns drawn into the ink (setts, tiles, boards, courses, seams, flags, grit)
vec3 pattern(int p, vec3 base, vec3 w, vec3 n) {
  if (p == 0) return base;
  vec3 dark = base * 0.7;
  if (p == 1) {
    vec2 q = w.xz * vec2(1.0 / 0.17, 1.0 / 0.25);
    float row = floor(q.y);
    q.x += mod(row, 2.0) * 0.5;
    vec2 f = fract(q);
    vec2 fw = fwidth(q);
    float fade = clamp(1.4 - max(fw.x, fw.y) * 2.2, 0.0, 1.0);
    float j = max(1.0 - smoothstep(0.06, 0.06 + fw.x, f.x), 1.0 - smoothstep(0.07, 0.07 + fw.y, f.y));
    float v = (hash12(floor(q)) - 0.5) * 0.16;
    vec3 c = base * (1.0 + v * fade);
    return mix(c, dark, j * fade);
  }
  if (p == 2) {
    vec2 q = w.xz / 0.2;
    vec2 f = fract(q) - 0.5;
    vec2 fw = fwidth(q);
    float fade = clamp(1.4 - max(fw.x, fw.y) * 2.0, 0.0, 1.0);
    float cab = smoothstep(0.8, 0.8 + fw.x * 1.5, abs(f.x) + abs(f.y));
    vec3 ink = vec3(0.10, 0.09, 0.08);
    vec3 c = mix(base, ink, cab * fade);
    float j = 1.0 - smoothstep(0.02, 0.02 + fw.x, 0.5 - max(abs(f.x), abs(f.y)));
    return mix(c, base * 0.86, j * fade * (1.0 - cab));
  }
  if (p == 3) {
    vec2 q = vec2(w.x / 0.9, w.z / 0.13);
    q.x += hash12(vec2(floor(q.y), 3.0)) * 3.0;
    vec2 f = fract(q);
    vec2 fw = fwidth(q);
    float fade = clamp(1.4 - max(fw.x, fw.y) * 2.0, 0.0, 1.0);
    float j = max(1.0 - smoothstep(0.015, 0.015 + fw.x, f.x), 1.0 - smoothstep(0.06, 0.06 + fw.y, f.y));
    float v = (hash12(floor(q)) - 0.5) * 0.14;
    return mix(base * (1.0 + v * fade), dark, j * fade);
  }
  if (p == 4) {
    float u = abs(n.x) > abs(n.z) ? w.z : w.x;
    vec2 q = vec2(u / 1.1, w.y / 0.42);
    q.x += mod(floor(q.y), 2.0) * 0.5;
    vec2 f = fract(q);
    vec2 fw = fwidth(q);
    float fade = clamp(1.4 - max(fw.x, fw.y) * 2.0, 0.0, 1.0);
    float j = max(1.0 - smoothstep(0.02, 0.02 + fw.x, f.x), 1.0 - smoothstep(0.07, 0.07 + fw.y, f.y));
    return mix(base, base * 0.76, j * fade);
  }
  if (p == 5) {
    float u = abs(n.x) > abs(n.z) ? w.z : w.x;
    float q = u / 0.55;
    float fw = fwidth(q);
    float fade = clamp(1.4 - fw * 2.0, 0.0, 1.0);
    float s = 1.0 - smoothstep(0.04, 0.04 + fw, fract(q));
    return mix(base, base * 1.18 + 0.04, s * fade);
  }
  if (p == 6) {
    vec2 q = vec2(w.x / 0.62, w.z / 1.0);
    q.y += mod(floor(q.x), 2.0) * 0.5;
    vec2 f = fract(q);
    vec2 fw = fwidth(q);
    float fade = clamp(1.4 - max(fw.x, fw.y) * 2.0, 0.0, 1.0);
    float j = max(1.0 - smoothstep(0.025, 0.025 + fw.x, f.x), 1.0 - smoothstep(0.02, 0.02 + fw.y, f.y));
    float v = (hash12(floor(q)) - 0.5) * 0.1;
    return mix(base * (1.0 + v * fade), base * 0.78, j * fade);
  }
  if (p == 7) {
    float g = hash12(floor(w.xz * 9.0));
    float fade = clamp(1.4 - length(fwidth(w.xz * 9.0)) * 1.5, 0.0, 1.0);
    return base * (1.0 + (step(0.9, g) * 0.16 - step(g, 0.08) * 0.1) * fade);
  }
  if (p == 8) {
    float q = w.y / 0.075;
    float fw = fwidth(q);
    float fade = clamp(1.4 - fw * 2.0, 0.0, 1.0);
    float r = 1.0 - smoothstep(0.12, 0.12 + fw, fract(q));
    return mix(base, base * 0.72, r * fade);
  }
  if (p == 9) {
    float u = atan(n.z, n.x) * 0.5;
    float m = noise2(vec2(u * 3.0 + w.x, w.y * 1.6)) + noise2(vec2(u * 7.0 - w.z, w.y * 3.4)) * 0.5;
    vec3 inner = vec3(0.86, 0.84, 0.66);
    return m > 0.86 ? mix(base, inner, 0.7) : (m < 0.5 ? base * 0.82 : base);
  }
  return base;
}
`;

const INK_VERT = /* glsl */ `
attribute vec4 aInk;
attribute vec4 aMark;
varying vec3 vInk;
varying float vId;
varying vec4 vMark;
varying vec3 vWorld;
varying vec3 vNormal;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  vInk = aInk.rgb;
  vId = floor(aInk.a * 255.0 + 0.5);
  vMark = aMark;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const GLINTS = /* glsl */ `
uniform vec4 uGlintPos[${MAX_GLINTS}];
uniform vec4 uGlintCol[${MAX_GLINTS}];
uniform int uGlintCount;

// the streaks a lamp leaves on a wet horizontal surface at height h: long down the view, thin across
vec3 glints(vec3 w, float h, float across, float along, float broken) {
  vec3 acc = vec3(0.0);
  vec3 v = normalize(w - cameraPosition);
  vec2 vh = normalize(v.xz);
  for (int i = 0; i < ${MAX_GLINTS}; i++) {
    if (i >= uGlintCount) break;
    vec3 L = uGlintPos[i].xyz;
    vec3 Lm = vec3(L.x, 2.0 * h - L.y, L.z);
    vec3 m = normalize(Lm - cameraPosition);
    vec2 mh = normalize(m.xz);
    float az = vh.x * mh.y - vh.y * mh.x;
    float el = v.y - m.y;
    float wob = broken > 0.0 ? (noise2(vec2(w.x * 0.9, w.z * 0.9 + uTime * 0.6)) - 0.5) * 0.05 * broken : 0.0;
    float a = (az + wob) / across;
    float e = el / along;
    float s = exp(-a * a - e * e * e * e);
    if (broken > 0.0) {
      float dash = step(0.36, fract(dot(w.xz - cameraPosition.xz, vh) * 1.6 + noise2(w.xz * 0.7 + uTime * 0.3) * 1.7));
      s *= mix(1.0, dash, broken);
    }
    float q = smoothstep(0.22, 0.26, s) * 0.55 + smoothstep(0.55, 0.6, s) * 0.45;
    acc += uGlintCol[i].rgb * q * uGlintCol[i].a;
  }
  return acc;
}
`;

function inkFragment(opts: { wet: boolean }) {
  return /* glsl */ `
${COMMON}
${opts.wet ? GLINTS : ''}
varying vec3 vInk;
varying float vId;
varying vec4 vMark;
varying vec3 vWorld;
varying vec3 vNormal;
void main() {
  vec3 n = normalize(vNormal);
  if (!gl_FrontFacing) n = -n;
  float glow = vMark.x / 255.0;
  float wet = vMark.y / 255.0;
  int code = int(vMark.z + 0.5);
  int indoor = code >= 16 ? 1 : 0;
  int pat = code - indoor * 16;
  float shade = vMark.w / 255.0;
  vec3 base = pattern(pat, vInk, vWorld, n);
  float band;
  vec3 light = indoor == 1 ? roomRamp(n, band) : sunRamp(n, band);
  vec3 col = base * (light + (indoor == 1 ? uAmbient * 0.25 : uAmbient)) * (1.0 - shade * 0.55);
  // a lamp's pool takes the ink to the lamp's own colour, in rings; inside a ring nothing is in shadow
  vec4 pool = lampPools(vWorld, n, indoor);
  if (pool.a > 0.0) {
    vec3 warm = base * pool.rgb * (0.62 + 0.5 * pool.a) * (1.0 - shade * 0.4);
    col = mix(col, warm, min(pool.a, 0.92) * (indoor == 1 ? 0.5 : 1.0));
    band = max(band, pool.a > 0.6 ? 2.0 : 1.0);
  }
  // the flat highlight band of zinc and wet stone: one pale stripe where the sky would glint
  if (wet > 0.0) {
    vec3 v = normalize(vWorld - cameraPosition);
    vec3 r = reflect(v, n);
    float hi = smoothstep(0.55, 0.6, r.y) * (1.0 - smoothstep(0.82, 0.86, r.y));
    col = mix(col, mix(col, uSkyHorizon * 1.15 + 0.08, 0.5), hi * wet * (0.35 + 0.65 * uNight));
  }
  ${opts.wet ? `
  if (n.y > 0.8 && indoor == 0) {
    float puddle = smoothstep(0.62, 0.66, noise2(vWorld.xz * 0.35));
    col *= mix(1.0, 0.72 - puddle * 0.1, uRain);
    col += glints(vWorld, vWorld.y, 0.0045 + puddle * 0.003, 0.08 + puddle * 0.12, 0.6 - puddle * 0.4) * uRain * (0.28 + puddle * 0.4);
  }` : ''}
  float night = uNight;
  // a lit window by day is glass that shows the sky, with a warm hint of the room behind
  if (indoor == 0 && glow > 0.0) {
    vec3 dayPane = mix(uSkyHorizon * 0.5, vInk * 0.55, 0.22) * (light + uAmbient);
    col = mix(col, dayPane, glow * (1.0 - night));
  }
  vec3 lit = vInk * (0.92 + 0.28 * night);
  col = mix(col, lit, glow * (indoor == 1 ? mix(0.35, 1.0, night) : night));
  if (glow > 0.5 && night > 0.5) band = 3.0;
  col = fogged(col, vWorld);
  gl_FragColor = vec4(col, packMark(vId, band));
}
`;
}

/** The static quarter: one material for nearly everything. */
export function inkMaterial(world: World, opts: { wet?: boolean } = {}) {
  return new ShaderMaterial({
    name: opts.wet ? 'ink-wet' : 'ink',
    uniforms: { ...world },
    vertexShader: INK_VERT,
    fragmentShader: inkFragment({ wet: !!opts.wet }),
    side: DoubleSide,
  });
}

/* ---- water: the canal mirrors the far bank, broken by the wind ---------------------------- */

const WATER_VERT = /* glsl */ `
uniform mat4 uMirrorMatrix;
varying vec3 vWorld;
varying vec4 vMirror;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  vMirror = uMirrorMatrix * w;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const WATER_FRAG = /* glsl */ `
${COMMON}
${GLINTS}
uniform sampler2D uMirror;
uniform float uMirrorOn;
uniform vec3 uWater;
uniform float uLevel;
varying vec3 vWorld;
varying vec4 vMirror;
void main() {
  vec3 v = normalize(vWorld - cameraPosition);
  float fres = clamp(1.0 - abs(v.y) * 1.6, 0.0, 1.0);
  vec3 col = uWater * (uSun * 0.5 + uShade * 0.5 + uAmbient);
  // the wind's grain on the water: bands across the canal
  float rip = noise2(vec2(vWorld.x * 0.6, vWorld.z * 2.2 + uTime * 0.5)) + noise2(vec2(vWorld.x * 1.7 - uTime * 0.3, vWorld.z * 5.0)) * 0.5;
  if (uMirrorOn > 0.5) {
    vec2 uv = vMirror.xy / vMirror.w;
    uv.x += (rip - 0.75) * 0.012;
    uv.y += (noise2(vec2(vWorld.x * 2.0, vWorld.z * 0.4 + uTime * 0.4)) - 0.5) * 0.05;
    vec3 m = texture2D(uMirror, uv).rgb;
    // posterise the reflection a little so it prints in the same few inks
    m = floor(m * 6.0 + 0.5) / 6.0;
    col = mix(col, m * 0.86, 0.55 + 0.3 * fres);
  } else {
    col = mix(col, uSkyHorizon * 0.8, fres * 0.6);
  }
  col += glints(vWorld, uLevel, 0.016, 0.16, 1.0) * 0.9;
  float hi = smoothstep(1.05, 1.15, rip) * (1.0 - uNight) * 0.25;
  col = mix(col, uSkyHorizon * 1.1, hi);
  col = fogged(col, vWorld);
  gl_FragColor = vec4(col, packMark(62.0, 1.0));
}
`;

export function waterMaterial(world: World, water: [number, number, number], level: number) {
  return new ShaderMaterial({
    name: 'water',
    uniforms: {
      ...world,
      uMirror: { value: null as Texture | null },
      uMirrorOn: { value: 0 },
      uMirrorMatrix: { value: new Matrix4() },
      uWater: { value: new Vector3(water[0], water[1], water[2]) },
      uLevel: { value: level },
    },
    vertexShader: WATER_VERT,
    fragmentShader: WATER_FRAG,
  });
}

/* ---- lace: the ironwork of balconies, footbridges and railings, cut from a pattern ------- */

const LACE_VERT = /* glsl */ `
attribute vec2 aRun;
attribute float aKind;
attribute float aId;
varying vec2 vRun;
varying float vKind;
varying float vId;
varying vec3 vWorld;
varying vec3 vNormal;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  vRun = aRun;
  vKind = aKind;
  vId = aId;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const LACE_FRAG = /* glsl */ `
${COMMON}
uniform vec3 uIron;
varying vec2 vRun;
varying float vKind;
varying float vId;
varying vec3 vWorld;
varying vec3 vNormal;

float bars(float x, float period, float width, float fw) {
  float f = abs(fract(x / period) - 0.5) * period;
  return 1.0 - smoothstep(width * 0.5, width * 0.5 + fw, f);
}

void main() {
  float u = vRun.x;   // metres along the run
  float h = vRun.y;   // metres up from the foot
  int kind = int(vKind + 0.5);
  float fu = fwidth(u);
  float fh = fwidth(h);
  float on = 0.0;
  if (kind == 1) {
    // a Haussmann balcony: rails, close bars, a row of rings
    on = max(on, 1.0 - smoothstep(0.035, 0.035 + fh, abs(h - 0.98)));
    on = max(on, 1.0 - smoothstep(0.03, 0.03 + fh, abs(h - 0.06)));
    on = max(on, 1.0 - smoothstep(0.02, 0.02 + fh, abs(h - 0.3)));
    on = max(on, bars(u, 0.115, 0.022, fu) * step(0.3, h) * step(h, 0.98));
    vec2 c = vec2((fract(u / 0.46) - 0.5) * 0.46, h - 0.18);
    float ring = abs(length(c) - 0.085);
    on = max(on, (1.0 - smoothstep(0.016, 0.016 + fu, ring)) * step(h, 0.3));
  } else if (kind == 2) {
    // a footbridge's lattice: two crossing diagonals between rails
    float span = 0.9;
    on = max(on, 1.0 - smoothstep(0.05, 0.05 + fh, abs(h - 1.05)));
    on = max(on, 1.0 - smoothstep(0.05, 0.05 + fh, abs(h - 0.05)));
    on = max(on, bars(u + h, span, 0.05, fu + fh) * step(h, 1.05));
    on = max(on, bars(u - h, span, 0.05, fu + fh) * step(h, 1.05));
    on = max(on, bars(u, span * 2.0, 0.06, fu) * step(h, 1.05));
  } else if (kind == 3) {
    // a plain guard: rails and bars (window guards, the canal's edge)
    on = max(on, 1.0 - smoothstep(0.03, 0.03 + fh, abs(h - 0.96)));
    on = max(on, 1.0 - smoothstep(0.03, 0.03 + fh, abs(h - 0.08)));
    on = max(on, bars(u, 0.13, 0.025, fu) * step(h, 0.96));
  } else {
    on = 1.0;
  }
  if (on < 0.5) discard;
  vec3 n = normalize(vNormal);
  if (!gl_FrontFacing) n = -n;
  float band;
  vec3 light = sunRamp(n, band);
  vec3 col = uIron * (light + uAmbient);
  vec4 pool = lampPools(vWorld, n, 0);
  if (pool.a > 0.0) {
    col = mix(col, uIron * pool.rgb * (0.7 + 0.6 * pool.a), min(pool.a, 0.92));
    band = max(band, pool.a > 0.6 ? 2.0 : 1.0);
  }
  col = fogged(col, vWorld);
  gl_FragColor = vec4(col, packMark(vId, band));
}
`;

export function laceMaterial(world: World, iron: [number, number, number]) {
  return new ShaderMaterial({
    name: 'lace',
    uniforms: { ...world, uIron: { value: new Vector3(iron[0], iron[1], iron[2]) } },
    vertexShader: LACE_VERT,
    fragmentShader: LACE_FRAG,
    side: DoubleSide,
  });
}

/* ---- the sky: a gradient, rain clouds, and the roofs of the rest of Paris on the horizon -- */

const SKY_VERT = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = normalize(position);
  vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  gl_Position = p.xyww;
}
`;

const SKY_FRAG = /* glsl */ `
${COMMON}
varying vec3 vDir;
void main() {
  vec3 d = normalize(vDir);
  float h = clamp(d.y, -0.2, 1.0);
  vec3 col = mix(uSkyHorizon, uSkyTop, smoothstep(0.0, 0.55, h));
  // flat cloud bands, lit from below by the city at night
  float az = atan(d.z, d.x);
  float c = noise2(vec2(az * 3.0 + uTime * 0.01, h * 9.0)) * 0.6 + noise2(vec2(az * 8.0, h * 22.0 - uTime * 0.02)) * 0.4;
  float cloud = smoothstep(0.56, 0.6, c) * smoothstep(0.04, 0.12, h) * (1.0 - smoothstep(0.5, 0.7, h));
  vec3 cloudCol = mix(mix(uSkyTop, uSkyHorizon, 0.55), mix(uSkyHorizon, vec3(0.76, 0.54, 0.06), 0.18), uNight);
  col = mix(col, cloudCol, cloud * 0.7);
  // the rest of Paris: roofs and chimneys, one flat ink a shade off the horizon
  float roofs = 0.018 + noise2(vec2(az * 14.0, 1.0)) * 0.03 + step(0.86, noise2(vec2(az * 90.0, 3.0))) * 0.012;
  float city = 1.0 - smoothstep(roofs - 0.002, roofs + 0.002, h);
  col = mix(col, mix(uSkyHorizon, uSkyTop, 0.38), city * 0.8);
  gl_FragColor = vec4(col, packMark(0.0, 3.0));
}
`;

export function skyMaterial(world: World) {
  return new ShaderMaterial({
    name: 'sky',
    uniforms: { ...world },
    vertexShader: SKY_VERT,
    fragmentShader: SKY_FRAG,
    side: BackSide,
    depthWrite: false,
  });
}

/* ---- glass: the café's windows, see-through with a few pale strokes --------------------- */

const GLASS_VERT = /* glsl */ `
varying vec3 vWorld;
varying vec3 vNormal;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const GLASS_FRAG = /* glsl */ `
${COMMON}
uniform vec3 uTint;
varying vec3 vWorld;
varying vec3 vNormal;
void main() {
  vec3 n = normalize(vNormal);
  float u = abs(n.x) > abs(n.z) ? vWorld.z : vWorld.x;
  float s = u * 1.3 + vWorld.y * 0.9;
  float fw = fwidth(s);
  float stroke = 1.0 - smoothstep(0.025, 0.025 + fw, abs(fract(s * 0.5) - 0.12));
  stroke += 1.0 - smoothstep(0.012, 0.012 + fw, abs(fract(s * 0.5) - 0.2));
  vec3 v = normalize(vWorld - cameraPosition);
  float fres = 1.0 - abs(dot(v, n));
  float a = 0.12 + fres * 0.22 + stroke * 0.32;
  vec3 col = mix(uTint, uSkyHorizon * 1.2 + 0.1, stroke);
  gl_FragColor = vec4(fogged(col, vWorld), a);
}
`;

/** Transparent, and careful to leave the line ids under it untouched. */
function keepMarks(m: ShaderMaterial) {
  m.transparent = true;
  m.blending = CustomBlending;
  m.blendEquation = AddEquation;
  m.blendSrc = SrcAlphaFactor;
  m.blendDst = OneMinusSrcAlphaFactor;
  m.blendSrcAlpha = ZeroFactor;
  m.blendDstAlpha = OneFactor;
  m.depthWrite = false;
  return m;
}

export function glassMaterial(world: World, tint: [number, number, number]) {
  return keepMarks(
    new ShaderMaterial({
      name: 'glass',
      uniforms: { ...world, uTint: { value: new Vector3(tint[0], tint[1], tint[2]) } },
      vertexShader: GLASS_VERT,
      fragmentShader: GLASS_FRAG,
      side: DoubleSide,
    }),
  );
}

/* ---- paper figures: the troupe, cut out and stood up ------------------------------------- */

const FIGURE_VERT = /* glsl */ `
uniform float uLean;
varying vec2 vUv;
varying vec3 vWorld;
void main() {
  vUv = uv;
  vec3 p = position;
  // a bow or a lean: tip the card forward about its feet
  float c = cos(uLean);
  float s = sin(uLean);
  p = vec3(p.x, p.y * c - p.z * s, p.y * s + p.z * c);
  vec4 w = modelMatrix * vec4(p, 1.0);
  vWorld = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const FIGURE_FRAG = /* glsl */ `
${COMMON}
uniform sampler2D uMap;
uniform vec3 uLight;
uniform float uCut;
uniform float uId;
uniform float uFade;
uniform vec3 uSilhouette;
uniform float uDark;
varying vec2 vUv;
varying vec3 vWorld;
void main() {
  if (vUv.y < uCut) discard;
  vec4 t = texture2D(uMap, vUv);
  if (t.a < 0.5) discard;
  vec3 col = t.rgb * uLight;
  col = mix(col, uSilhouette, uDark);
  col = fogged(col, vWorld);
  gl_FragColor = vec4(col, packMark(uId, 3.0));
}
`;

export function figureMaterial(world: World, map: Texture, id: number) {
  return new ShaderMaterial({
    name: 'figure',
    uniforms: {
      ...world,
      uMap: { value: map },
      uLight: { value: new Vector3(1, 1, 1) },
      uCut: { value: 0 },
      uId: { value: id },
      uLean: { value: 0 },
      uFade: { value: 1 },
      uSilhouette: { value: new Vector3(0.08, 0.07, 0.06) },
      uDark: { value: 0 },
    },
    vertexShader: FIGURE_VERT,
    fragmentShader: FIGURE_FRAG,
    side: DoubleSide,
  });
}

/* ---- contact shadows under the figures and the furniture they touch -------------------- */

const BLOT_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const BLOT_FRAG = /* glsl */ `
uniform vec3 uInk;
uniform float uStrength;
varying vec2 vUv;
void main() {
  float d = length(vUv - 0.5) * 2.0;
  float a = (1.0 - smoothstep(0.55, 1.0, d)) * uStrength;
  a = floor(a * 3.0 + 0.5) / 3.0;
  if (a <= 0.0) discard;
  gl_FragColor = vec4(uInk, a);
}
`;

export function blotMaterial(ink: [number, number, number], strength = 0.42) {
  const m = new ShaderMaterial({
    name: 'blot',
    uniforms: { uInk: { value: new Vector3(ink[0], ink[1], ink[2]) }, uStrength: { value: strength } },
    vertexShader: BLOT_VERT,
    fragmentShader: BLOT_FRAG,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
  return keepMarks(m);
}

/* ---- the neon and other lights seen directly: flat, bright, a soft halo ----------------- */

const SIGN_VERT = /* glsl */ `
attribute float aIndoor;
varying vec2 vUv;
varying vec3 vWorld;
varying float vIndoor;
void main() {
  vUv = uv;
  vIndoor = aIndoor;
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const SIGN_FRAG = /* glsl */ `
${COMMON}
uniform sampler2D uMap;
uniform float uGlow;
uniform float uId;
uniform float uFlicker;
varying vec2 vUv;
varying vec3 vWorld;
varying float vIndoor;
void main() {
  vec4 t = texture2D(uMap, vUv);
  if (t.a < 0.5) discard;
  float on = mix(1.0, uFlicker, uGlow);
  // outdoors the sky's two bands, indoors the globes' (a wall card sits in the middle band)
  vec3 light = mix(uSun * 0.5 + uShade * 0.5, mix(uIndoorShade, uIndoorLit, 0.7), vIndoor);
  vec3 lit = t.rgb * mix(light, vec3(1.0), uGlow * uNight) * on;
  gl_FragColor = vec4(fogged(lit, vWorld), packMark(uId, uGlow * uNight > 0.5 ? 3.0 : 1.0));
}
`;

/** A painted or lit sign from a canvas texture (the neon, shop names, posters). */
export function signMaterial(world: World, map: Texture, id: number, glow: number) {
  const m = new ShaderMaterial({
    name: 'sign',
    uniforms: { ...world, uMap: { value: map }, uGlow: { value: glow }, uId: { value: id }, uFlicker: { value: 1 } },
    vertexShader: SIGN_VERT,
    fragmentShader: SIGN_FRAG,
    side: FrontSide,
  });
  // a sign built without the flag (the neon, the easel) is outdoors
  (m.defaultAttributeValues as Record<string, number[]>).aIndoor = [0];
  return m;
}

const HALO_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uStrength;
varying vec2 vUv;
void main() {
  float d = length(vUv - 0.5) * 2.0;
  float a = (1.0 - smoothstep(0.0, 1.0, d));
  a = a * a * uStrength;
  gl_FragColor = vec4(uColor * a, 0.0);
}
`;

/** The soft glow round a lamp or the neon in the rain (additive, ids untouched). */
export function haloMaterial(color: [number, number, number], strength = 0.5) {
  const m = new ShaderMaterial({
    name: 'halo',
    uniforms: { uColor: { value: new Vector3(color[0], color[1], color[2]) }, uStrength: { value: strength } },
    vertexShader: BLOT_VERT,
    fragmentShader: HALO_FRAG,
    transparent: true,
    depthWrite: false,
  });
  m.blending = CustomBlending;
  m.blendEquation = AddEquation;
  m.blendSrc = OneFactor;
  m.blendDst = OneFactor;
  m.blendSrcAlpha = ZeroFactor;
  m.blendDstAlpha = OneFactor;
  return m;
}

export { AdditiveBlending, Color, keepMarks };
