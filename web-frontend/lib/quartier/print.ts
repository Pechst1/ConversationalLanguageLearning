/**
 * Le Quartier · the print pass.
 *
 * The scene is drawn into an off-screen plate (colour, plus line id and light band in alpha,
 * plus depth), and this one full-screen pass prints it: thin ink lines where depth jumps (the
 * silhouettes) and where two pieces meet, keyed half a pixel off the colour like a plate out of
 * register; a halftone screen in the shadow band; paper fibre and uneven ink over everything.
 * It is the only post-processing the quarter has, so it costs one extra pass a frame.
 */
import {
  BufferAttribute,
  BufferGeometry,
  DataTexture,
  DepthTexture,
  LinearFilter,
  Mesh,
  NearestFilter,
  OrthographicCamera,
  RedFormat,
  RepeatWrapping,
  RGBAFormat,
  Scene,
  ShaderMaterial,
  UnsignedByteType,
  UnsignedIntType,
  Vector2,
  Vector3,
  WebGLRenderTarget,
} from 'three';
import type { Camera, WebGLRenderer } from 'three';

import { INKS, rgb } from './palette';

const VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = position.xy * 0.5 + 0.5;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const FRAG = /* glsl */ `
uniform sampler2D tColor;
uniform sampler2D tDepth;
uniform sampler2D tGrain;
uniform vec2 uRes;
uniform float uNear;
uniform float uFar;
uniform float uLine;
uniform float uIdLines;
uniform vec3 uInk;
uniform vec3 uPaper;
uniform float uHalftone;
uniform float uDot;
uniform float uFogFar;
uniform float uGrain;
uniform float uSeed;
varying vec2 vUv;

float viewDepth(vec2 uv) {
  float d = texture2D(tDepth, uv).x;
  return (uNear * uFar) / (uFar - d * (uFar - uNear));
}

float idOf(vec2 uv) {
  float v = floor(texture2D(tColor, uv).a * 255.0 + 0.5);
  return floor(v / 4.0);
}

void main() {
  vec2 px = 1.0 / uRes;
  vec4 c = texture2D(tColor, vUv);
  float code = floor(c.a * 255.0 + 0.5);
  float id = floor(code / 4.0);
  float band = code - id * 4.0;
  vec3 col = c.rgb;

  // the key plate: lines, set half a pixel off the colour
  vec2 luv = vUv + px * vec2(0.55, -0.45);
  vec2 ox = vec2(px.x * uLine, 0.0);
  vec2 oy = vec2(0.0, px.y * uLine);
  float d0 = viewDepth(luv);
  float dl = viewDepth(luv - ox);
  float dr = viewDepth(luv + ox);
  float du = viewDepth(luv + oy);
  float dd = viewDepth(luv - oy);
  float nearest = min(min(min(dl, dr), min(du, dd)), d0);
  float jump = max(max(dl - nearest, dr - nearest), max(du - nearest, dd - nearest));
  jump = max(jump, d0 - nearest);
  // a jump is a silhouette when it is large for its distance
  float edge = smoothstep(0.035, 0.06, jump / max(nearest, 0.5));
  float i0 = idOf(luv);
  float idEdge = 0.0;
  if (idOf(luv - ox) != i0 || idOf(luv + ox) != i0 || idOf(luv + oy) != i0 || idOf(luv - oy) != i0) idEdge = 1.0;
  edge = max(edge, idEdge * uIdLines);
  // lines thin out into the fog, and never draw on the sky itself
  float fade = 1.0 - smoothstep(uFogFar * 0.25, uFogFar * 0.75, nearest);
  edge *= fade;

  // the halftone screen in the shadow band, at 45 degrees
  if (band < 0.5) {
    vec2 p = gl_FragCoord.xy / uDot;
    p = vec2(p.x + p.y, p.y - p.x) * 0.7071;
    vec2 f = fract(p) - 0.5;
    float r = length(f);
    float dotMask = 1.0 - smoothstep(0.24, 0.3, r);
    col = mix(col, col * 0.72, dotMask * uHalftone);
  }

  // paper: fibre, and ink that never quite covers evenly
  vec2 gp = gl_FragCoord.xy / 256.0;
  float g = texture2D(tGrain, gp + uSeed).r;
  float blot = texture2D(tGrain, gl_FragCoord.xy / 1400.0 + 0.37).r;
  col *= 1.0 - uGrain * (0.09 * g + 0.06 * (blot - 0.5));
  col += uPaper * uGrain * 0.03 * (1.0 - g);

  vec3 ink = mix(uInk, col * 0.35, 0.25);
  col = mix(col, ink, edge * 0.88);

  // the plate's edge darkens a little, as a print does where the roller lifts
  vec2 q = (vUv - 0.5) * vec2(uRes.x / uRes.y, 1.0);
  col *= 1.0 - 0.16 * smoothstep(0.45, 1.05, length(q) * 1.25);
  gl_FragColor = vec4(col, 1.0);
}
`;

function makeGrain(size = 256): DataTexture {
  // fibre: stretched value noise at two scales, plus a speckle
  const data = new Uint8Array(size * size);
  let s = 1234567;
  const rnd = () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
  const lattice = (n: number) => {
    const g = new Float32Array(n * n);
    for (let i = 0; i < g.length; i++) g[i] = rnd();
    return (x: number, y: number) => {
      const xi = Math.floor(x);
      const yi = Math.floor(y);
      const xf = x - xi;
      const yf = y - yi;
      const at = (a: number, b: number) => g[(((b % n) + n) % n) * n + (((a % n) + n) % n)];
      const u = xf * xf * (3 - 2 * xf);
      const v = yf * yf * (3 - 2 * yf);
      return (at(xi, yi) * (1 - u) + at(xi + 1, yi) * u) * (1 - v) + (at(xi, yi + 1) * (1 - u) + at(xi + 1, yi + 1) * u) * v;
    };
  };
  const coarse = lattice(16);
  const fine = lattice(64);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const fx = x / size;
      const fy = y / size;
      const fibre = fine(fx * 64, fy * 16) * 0.55 + coarse(fx * 16, fy * 16) * 0.3 + rnd() * 0.15;
      data[y * size + x] = Math.max(0, Math.min(255, Math.round(fibre * 255)));
    }
  }
  const tex = new DataTexture(data, size, size, RedFormat, UnsignedByteType);
  tex.wrapS = RepeatWrapping;
  tex.wrapT = RepeatWrapping;
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

export interface PrintOptions {
  /** line width in plate pixels */
  line: number;
  /** strength of the lines between pieces (0 keeps only silhouettes) */
  idLines: number;
  halftone: number;
  grain: number;
}

export class PrintPass {
  readonly plate: WebGLRenderTarget;
  private scene = new Scene();
  private camera = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private material: ShaderMaterial;
  private grain = makeGrain();

  constructor(width: number, height: number, options: PrintOptions) {
    const depth = new DepthTexture(width, height);
    depth.type = UnsignedIntType;
    this.plate = new WebGLRenderTarget(width, height, {
      format: RGBAFormat,
      type: UnsignedByteType,
      minFilter: NearestFilter,
      magFilter: NearestFilter,
      depthBuffer: true,
      depthTexture: depth,
      generateMipmaps: false,
    });
    const paper = rgb(INKS.paper);
    const ink = rgb(INKS.ink);
    this.material = new ShaderMaterial({
      name: 'print',
      uniforms: {
        tColor: { value: this.plate.texture },
        tDepth: { value: depth },
        tGrain: { value: this.grain },
        uRes: { value: new Vector2(width, height) },
        uNear: { value: 0.1 },
        uFar: { value: 500 },
        uLine: { value: options.line },
        uIdLines: { value: options.idLines },
        uInk: { value: new Vector3(ink[0], ink[1], ink[2]) },
        uPaper: { value: new Vector3(paper[0], paper[1], paper[2]) },
        uHalftone: { value: options.halftone },
        uDot: { value: 5 },
        uFogFar: { value: 150 },
        uGrain: { value: options.grain },
        uSeed: { value: 0 },
      },
      vertexShader: VERT,
      fragmentShader: FRAG,
      depthTest: false,
      depthWrite: false,
    });
    const tri = new BufferGeometry();
    tri.setAttribute('position', new BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3));
    const mesh = new Mesh(tri, this.material);
    mesh.frustumCulled = false;
    this.scene.add(mesh);
  }

  setSize(width: number, height: number, pixelScale: number) {
    this.plate.setSize(width, height);
    this.material.uniforms.uRes.value.set(width, height);
    // lines and dots keep their printed size whatever the plate's resolution
    this.material.uniforms.uLine.value = Math.max(1, Math.round(pixelScale * 0.9));
    this.material.uniforms.uDot.value = 3.2 * pixelScale;
  }

  set(options: Partial<PrintOptions> & { fogFar?: number; near?: number; far?: number }) {
    const u = this.material.uniforms;
    if (options.idLines !== undefined) u.uIdLines.value = options.idLines;
    if (options.halftone !== undefined) u.uHalftone.value = options.halftone;
    if (options.grain !== undefined) u.uGrain.value = options.grain;
    if (options.fogFar !== undefined) u.uFogFar.value = options.fogFar;
    if (options.near !== undefined) u.uNear.value = options.near;
    if (options.far !== undefined) u.uFar.value = options.far;
  }

  /** Draw `scene` into the plate, then print the plate to the screen. */
  render(renderer: WebGLRenderer, scene: Scene, camera: Camera & { near: number; far: number }) {
    const u = this.material.uniforms;
    u.uNear.value = camera.near;
    u.uFar.value = camera.far;
    renderer.setRenderTarget(this.plate);
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.plate.depthTexture?.dispose();
    this.plate.dispose();
    this.material.dispose();
    this.grain.dispose();
  }
}
