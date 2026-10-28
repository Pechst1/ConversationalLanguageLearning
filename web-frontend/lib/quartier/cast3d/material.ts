/**
 * Le Quartier · the figures' ink: how a person in the round takes the print.
 *
 * The same rules as the quarter's own materials: every surface is its ink, darkened by one of
 * three light bands, and a band is never grey but the ambiance's own second ink (cobalt under the
 * moon, a warm brown under the café's globes). Two things differ for people. The light a figure
 * takes is the light where it stands (`Quartier.lightAt`: the lamps' pools, kept from falling
 * below a dim print so a face stays readable), so the bands are that light, deepened; and the key
 * comes from above and a little toward you, so a face turned to you is lit and its planes (the
 * brow, the side of the nose, under the chin) fall into the middle and shadow bands the way a
 * poster models a face. The face itself is printed onto the head from a small atlas (`face.ts`):
 * one cell per mouth and blink, chosen by a uniform, so talking and blinking cost nothing.
 *
 * Each fragment writes its line id and band for the print pass, like everything else.
 */
import { DoubleSide, ShaderMaterial, Vector2, Vector3 } from 'three';
import type { Texture } from 'three';

import type { World } from '../materials';
import { CELL_SCALE } from './face';

const VERT = /* glsl */ `
#include <common>
#include <skinning_pars_vertex>
attribute vec4 aInk;
attribute vec3 aFace;
varying vec3 vInk;
varying float vId;
varying vec3 vFace;
varying vec3 vWorld;
varying vec3 vNormal;
void main() {
  #include <skinbase_vertex>
  #include <beginnormal_vertex>
  #include <skinnormal_vertex>
  #include <begin_vertex>
  #include <skinning_vertex>
  vec4 w = modelMatrix * vec4(transformed, 1.0);
  vWorld = w.xyz;
  vNormal = normalize(mat3(modelMatrix) * objectNormal);
  vInk = aInk.rgb;
  vId = floor(aInk.a * 255.0 + 0.5);
  vFace = aFace;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`;

const FRAG = /* glsl */ `
uniform vec3 uShade;
uniform vec3 uIndoorShade;
uniform vec2 uFog;
uniform vec3 uSkyHorizon;
uniform vec3 uLight;
uniform float uIndoor;
uniform vec3 uKey;
uniform sampler2D uFaceMap;
uniform vec2 uFaceCell;
uniform vec2 uFaceScale;
uniform float uHasFace;
uniform vec3 uSilhouette;
uniform float uDark;
varying vec3 vInk;
varying float vId;
varying vec3 vFace;
varying vec3 vWorld;
varying vec3 vNormal;

float packMark(float id, float band) { return (id * 4.0 + band) / 255.0; }

void main() {
  vec3 n = normalize(vNormal);
  if (!gl_FrontFacing) n = -n;
  vec3 base = vInk;
  if (uHasFace > 0.5 && vFace.z > 0.002) {
    vec2 f = clamp(vFace.xy, 0.004, 0.996);
    vec4 t = texture2D(uFaceMap, uFaceCell + f * uFaceScale);
    base = mix(base, t.rgb, t.a * clamp(vFace.z, 0.0, 1.0));
  }
  float d = dot(n, uKey);
  float lit = smoothstep(0.24, 0.3, d);
  float mid = smoothstep(-0.16, -0.1, d);
  float band = lit > 0.5 ? 2.0 : (mid > 0.5 ? 1.0 : 0.0);
  vec3 sh = uIndoor > 0.5 ? uIndoorShade : uShade;
  vec3 hue = sh / max(max(sh.r, sh.g), max(sh.b, 0.001));
  vec3 midLight = uLight * mix(vec3(1.0), hue, 0.42) * 0.85;
  vec3 lowLight = uLight * mix(vec3(1.0), hue, 0.75) * 0.63;
  vec3 col = base * mix(lowLight, mix(midLight, uLight, lit), mid);
  col = mix(col, uSilhouette, uDark);
  float dist = length(vWorld - cameraPosition);
  col = mix(col, uSkyHorizon, smoothstep(uFog.x, uFog.y, dist));
  gl_FragColor = vec4(col, packMark(vId, band));
}
`;

export function figure3dMaterial(world: World, face: Texture | null) {
  return new ShaderMaterial({
    name: 'figure-3d',
    uniforms: {
      uShade: world.uShade,
      uIndoorShade: world.uIndoorShade,
      uFog: world.uFog,
      uSkyHorizon: world.uSkyHorizon,
      uLight: { value: new Vector3(1, 1, 1) },
      uIndoor: { value: 0 },
      uKey: { value: new Vector3(0, 0.8, 0.6).normalize() },
      uFaceMap: { value: face },
      uFaceCell: { value: new Vector2(0, 0) },
      uFaceScale: { value: CELL_SCALE.clone() },
      uHasFace: { value: face ? 1 : 0 },
      uSilhouette: { value: new Vector3(0.08, 0.07, 0.06) },
      uDark: { value: 0 },
    },
    vertexShader: VERT,
    fragmentShader: FRAG,
    side: DoubleSide,
  });
}
