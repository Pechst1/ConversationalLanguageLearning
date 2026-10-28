/**
 * Romy Tremblay, la reporter, in the round.
 *
 * From her rig: the long brown hair parted in the middle and falling past her shoulders, its
 * gold glints; the black leather jacket to the hips with its lapels over the deep blue top, its
 * seams and the clip mic; navy trousers and black shoes. The camera is held in front of her in
 * both hands, its strap up round her neck and its red light on, steady.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import { romy as fig } from '@/components/cast/vivant/figures/romy';
import { dots, ellipse } from '@/components/cast/rig-kit';
import type { Pt } from '@/components/cast/vivant/kit';

import { vivantFace } from '../face';
import { flick, hairCap, hairFall, onHead, round } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, bandAt, frontZ, hand, ink, leg, neck, onFront, pelvis, rounded, shoe, sleeve, trunk } from '../kit';
import type { Person } from '../model';
import type { Pose } from '../pose';
import { B, posed } from '../rig';
import { between, smooth } from '../sculpt';

const SKIN = 0xecb896;
const HAIR = 0x4a2e1a;
const PARTING = 0x6b4428;
const GLINT = 0xc49a0a;
const JACKET = 0x1f1b16;
const CUFF = 0x2e2924;
const SEAM = 0x4a4640;
const TOP = 0x1d3a8a;
const TROUSERS = 0x14285f;
const SHOES = 0x14110d;
const CAMERA = 0x14110d;
const LENS = 0x3d3832;
const GLASS = 0x1d3a8a;
const PAPER = 0xf8f3e8;
const TALLY = 0xd8321a;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

const FRECKLES = [[-22, 7], [-26, 10], [-18, 10], [-12, 5], [-8, 9], [-3, 4], [22, 7], [26, 10], [18, 10], [12, 5], [8, 9], [3, 4]] as const;
const NOSE = 'M0,-1 C3,2 5,10 4,13 C2,15.5 -2,15.5 -4,13 C-5,10 -3,2 0,-1 Z';
function lash(c: Pt, side: -1 | 1): string {
  return `M${c[0] - 10.5},${c[1] - 3} Q${c[0]},${c[1] - 15} ${c[0] + 10.5},${c[1] - 3} M${c[0] + side * 10},${c[1] - 4} L${c[0] + side * 14},${c[1] - 6.5}`;
}

/** At rest she holds the camera in front of her in both hands. */
const REST: Pose = {
  armR: [0.32, 0.42, 0.08],
  foreR: [-1.48, 0, 0],
  armL: [0.32, -0.42, -0.08],
  foreL: [-1.48, 0, 0],
};

function build(b: Build) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const jacket = ink(JACKET, PLATE.top);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;

  neck(b, skin2, 0.036);

  // the leather jacket, a little flared to the hips
  const coat: Band[] = [
    { y: hip - 0.06, rx: 0.16, rz: 0.114, square: 2.3 },
    { y: hip + 0.04, rx: 0.15, rz: 0.106, square: 2.2 },
    { y: hip + 0.16, rx: 0.136, rz: 0.097 },
    { y: ch - 0.03, rx: 0.14, rz: 0.1, front: 0.012 },
    { y: ch + 0.08, rx: 0.152, rz: 0.097, front: 0.006 },
    { y: sy - 0.045, rx: 0.16, rz: 0.089, square: 2.6 },
    { y: sy - 0.004, rx: 0.12, rz: 0.073, square: 2.4 },
    { y: sy + 0.022, rx: 0.05, rz: 0.046 },
  ];
  trunk(b, coat, jacket);
  // the blue top in the V, the lapels either side
  onFront(b, coat, [[-0.046, sy + 0.014], [0.046, sy + 0.014], [0, sy - 0.1]], ink(TOP, PLATE.under), { lift: 0.002 });
  for (const s of [-1, 1]) {
    const pts: Array<[number, number]> = [[s * 0.046, sy + 0.016], [s * 0.084, sy - 0.006], [s * 0.02, sy - 0.15], [s * 0.001, sy - 0.1]];
    onFront(b, coat, s > 0 ? pts : pts.reverse(), ink(CUFF, PLATE.skin2), { lift: 0.005, depth: 0.006 });
  }
  // the seams down the front
  for (const s of [-1, 1]) {
    const x = s * 0.098;
    onFront(b, coat, [[x - 0.003, sy - 0.11], [x + 0.003, sy - 0.11], [x + 0.003, hip - 0.04], [x - 0.003, hip - 0.04]], ink(SEAM, PLATE.top), { lift: 0.002, depth: 0.003 });
  }
  // the clip mic on her left lapel
  const micY = sy - 0.05;
  const mic = v(0.04, micY, frontZ(coat, 0.04, micY) + 0.012);
  S.ball(mic, v(0.0085, 0.0085, 0.006), ink(CAMERA, PLATE.prop), B.chest, { seg: 10, rings: 6 });
  S.box(mic.clone().add(v(0, -0.012, -0.002)), v(0.006, 0.014, 0.004), ink(CAMERA, PLATE.prop), B.chest);

  // the sleeves to the wrist, a softer black at the cuff
  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, jacket, [[0, 0.056], [0.45, 0.05], [1, 0.047], [1.62, 0.044]], { capEnd: false });
    sleeve(b, side, ink(CUFF, PLATE.under), [[1.6, 0.0445], [1.94, 0.041]], { capStart: false, capEnd: true });
    hand(b, side, skin2, 0.95);
  }

  pelvis(b, ink(TROUSERS, PLATE.bottom), { waist: hip + 0.05, rx: 0.12, rz: 0.09 });
  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(TROUSERS, PLATE.bottom), { top: 0.068, thigh: 0.064, knee: 0.05, calf: 0.047, hem: 0.045 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.044, height: 0.062 });
  }

  // the hair: the cap with its middle parting, then the long fall
  const hairInk = ink(HAIR, PLATE.hair);
  const capThick = (th: number, u: number) => {
    const front = Math.max(0, Math.cos(th));
    return 0.004 + (0.042 - 0.016 * front * (1 - u)) * Math.pow(u, 0.45) + 0.008 * u * u;
  };
  const hairline = round([
      [0, -56],
      [0.08, -53],
      [0.4, -50],
      [0.58, -46],
      [1.0, -36],
      [1.26, -16],
      [1.42, 6],
      [Math.PI / 2, 16],
      [2.3, 34],
      [Math.PI, 40],
      [-2.3, 34],
      [-Math.PI / 2, 16],
      [-1.42, 6],
      [-1.26, -16],
      [-1.0, -36],
      [-0.58, -46],
      [-0.4, -50],
      [-0.08, -53],
  ]);
  hairCap(S, head, hc, {
    edge: hairline,
    thick: capThick,
    ink: hairInk,
    bind: B.head,
  });
  const fallBind = (p: Vector3) => between(B.head, B.chest, smooth(J.chin + 0.03, sy - 0.07, p.y));
  hairFall(S, head, hc, {
    top: -40,
    open: 1.2,
    end: (th) => {
      const back = smooth(1.3, Math.PI, Math.abs(((th + Math.PI) % (Math.PI * 2)) - Math.PI));
      return sy - 0.005 - 0.16 * back;
    },
    thick: (th) => 0.03 + 0.008 * smooth(1.4, Math.PI, Math.abs(((th + Math.PI) % (Math.PI * 2)) - Math.PI)),
    body: (y) => {
      if (y > sy + 0.03) return null;
      const band = bandAt(coat, y);
      // the shoulders and the tops of the sleeves stand out past the jacket's body
      const shoulder = smooth(sy + 0.03, sy - 0.02, y) * (1 - smooth(sy - 0.08, sy - 0.16, y));
      return [band.rx + 0.012 + 0.03 * shoulder, band.rz + 0.012];
    },
    lift: 0.012,
    flare: 0.02,
    ink: hairInk,
    bind: fallBind,
  });
  // the parting, from the hairline back over the crown
  const part: Vector3[] = [];
  const edge0 = head.latOf(hairline(0));
  for (const f of [0.02, 0.2, 0.45, 0.7, 0.92]) {
    const lat = edge0 + (Math.PI / 2 - edge0) * f;
    part.push(onHead(head, hc, lat, 0, capThick(0, f) + 0.0015));
  }
  flick(S, part, [0.0026, 0.003, 0.003, 0.003, 0.0018], ink(PARTING, PLATE.prop), B.head, { flat: 0.5, up: v(0, 1, 0) });
  // gold glints: one over each temple, one down each side of the fall
  for (const s of [-1, 1]) {
    const g0 = onHead(head, hc, head.latOf(-46), s * 0.62, 0.02);
    const g1 = onHead(head, hc, head.latOf(-34), s * 0.95, 0.03);
    const g2 = onHead(head, hc, head.latOf(-18), s * 1.16, 0.032);
    S.tube([g0, g1, g2], 0.0026, ink(GLINT, PLATE.under), B.head, { seg: 5 });
    const k0 = onHead(head, hc, head.latOf(10), s * 1.62, 0.03);
    const k1 = k0.clone().add(v(s * 0.004, -0.05, -0.004));
    const k2 = k0.clone().add(v(s * 0.008, -0.1, -0.006));
    S.tube([k0, k1, k2], 0.0026, ink(GLINT, PLATE.under), fallBind, { seg: 5 });
  }
  // small gold hoops at the jaw
  for (const s of [-1, 1]) {
    const w = head.width(12);
    const p = head.at(head.x0 + s * (w - 1), 14, -0.004).add(hc);
    const r = 4.6 * head.s;
    const ring: Vector3[] = [];
    for (let i = 0; i < 14; i++) {
      const a = (i / 14) * Math.PI * 2;
      ring.push(p.clone().add(v(s * 0.004, -r + Math.cos(a) * r, Math.sin(a) * r)));
    }
    S.tube(ring, 0.0024, ink(GLINT, PLATE.prop), B.head, { seg: 5, closed: true });
  }

  // the camera, built where it sits at rest: between her hands, in front of her, lens out
  const R = posed(J, REST);
  const palmR = J.palm.R.clone().applyMatrix4(R.handR);
  const palmL = J.palm.L.clone().applyMatrix4(R.handL);
  const at = palmR.clone().lerp(palmL, 0.5).add(v(0, 0.004, 0.012));
  const rest = new Matrix4().compose(at, new Quaternion(), v(1, 1, 1));
  S.push(R.handR.clone().invert().multiply(rest));
  const cam = ink(CAMERA, PLATE.prop);
  const W = 0.118;
  const H = 0.084;
  const D = 0.064;
  S.slab(rounded(W, H, 0.012), D, new Matrix4(), cam, B.handR);
  S.box(v(0, H / 2 + 0.008, -0.004), v(0.05, 0.016, 0.034), cam, B.handR);
  const lens = new Matrix4().makeRotationX(Math.PI / 2).setPosition(0, -0.002, D / 2);
  S.lathe([[0, 0.022], [0.03, 0.022], [0.031, 0.006], [0.03, 0]], 14, lens, ink(LENS, PLATE.under), B.handR, { flat: true });
  S.lathe([[0, 0.0235], [0.019, 0.0235], [0.019, 0.02]], 12, lens, ink(GLASS, PLATE.skin), B.handR, { flat: true });
  S.ball(v(-0.007, 0.006, D / 2 + 0.024), 0.0045, ink(PAPER, PLATE.hair), B.handR, { seg: 6, rings: 4 });
  S.ball(v(W / 2 - 0.016, H / 2 - 0.016, D / 2 + 0.002), 0.0055, ink(TALLY, PLATE.shoes), B.handR, { seg: 8, rings: 5 });
  // the strap's ends, to tie the strap to
  const strapR = S.world(v(-W / 2 + 0.01, H / 2 - 0.004, -0.004));
  const strapL = S.world(v(W / 2 - 0.01, H / 2 - 0.004, -0.004));
  S.pop();
  // the strap, from the camera up round her neck: the hand carries one end, the chest the other
  for (const [end, s] of [[strapR, -1], [strapL, 1]] as const) {
    const neckAt = v(s * 0.045, sy + 0.016, -0.01);
    const mid = v(s * 0.06, sy - 0.08, frontZ(coat, s * 0.06, sy - 0.08) + 0.006);
    S.tube([end, end.clone().lerp(mid, 0.5), mid, neckAt], 0.0028, ink(CAMERA, PLATE.prop), [B.handR, [B.handR, B.chest, 0.6], B.chest, B.chest], { seg: 5 });
  }
}

export const romy: Person = {
  key: 'romy_tremblay',
  name: 'Romy',
  skin: SKIN,
  body: { height: 1.66, head: 0.36, neck: 0.07, shoulders: 0.15, hips: 0.074, legs: 0.42, arm: 0.33, hand: 0.115, foot: 0.21 },
  head: {
    outline: 'M-38,-24 C-38,-56 -20,-64 0,-64 C20,-64 38,-56 38,-24 C38,14 22,46 0,50 C-22,46 -38,14 -38,-24 Z',
    nose: NOSE,
    noseDepth: 0.75,
    ears: [],
    chin: 13,
  },
  look: {
    skin: '#ecb896',
    brow: '#5a3a22',
    browWidth: 4.4,
    lidLine: 2.6,
    arcLine: 4,
    iris: '#3b5f9e',
    lash: { states: ['open', 'wide', 'tiny', 'sparkle'], path: lash, at: [[-15, -4], [15, -4]] },
    mouth: [-3.6, 1.8, 1.8],
    nose: { d: NOSE, fill: '#d49a76', opacity: 0.5 },
    under: [
      { d: `${ellipse(-22, 13, 6.5, 3.6)} ${ellipse(22, 13, 6.5, 3.6)}`, fill: '#f1a98f' },
      { d: dots(FRECKLES, 1.1), fill: '#b9755a' },
    ],
    fx: { cheekL: [-22, 13], cheekR: [22, 13], temple: [31, -30], eyeL: [-15, -4], eyeR: [15, -4] },
    frame: [0, -6, 60],
  },
  face: () => vivantFace(fig),
  eyes: [
    [-15, -4],
    [15, -4],
  ],
  build,
  manner: { rest: REST, energy: 1.1 },
};
