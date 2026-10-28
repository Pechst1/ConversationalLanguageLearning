/**
 * Camille Marchand, in the round, in both of the rig's variants: `f` with the sleek hair pulled
 * back into a low bun, the pointed locks at the temples and the pearl studs; `m` with the short
 * hair and the beard.
 *
 * From the rig: just in from the rain (drops on the hair, the shoulder and the helmet), the
 * grey-green jacket with its corduroy collar over a white shirt, the pocket flaps and seams, navy
 * trousers, black shoes. The blue folder is held to the chest; the red bike helmet hangs from the
 * other hand by its rim.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import { camille as rig } from '@/components/cast/rigs/camille';
import { ellipse } from '@/components/cast/rig-kit';

import type { FaceLook } from '../face';
import { rigFace } from '../face';
import { flick, hairCap, onHead, round } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, cuff, frontZ, hand, ink, leg, neck, onFront, pelvis, shoe, sleeve, trunk } from '../kit';
import type { Person } from '../model';
import type { Pose } from '../pose';
import { B, posed } from '../rig';

const SKIN = 0xd8a07a;
const HAIR = 0x1f1a16;
const BEARD = '#3a312a';
const JACKET = 0x3e4542;
const CORD = 0x6b4a2a;
const SHIRT = 0xf8f3e8;
const POCKET = 0x2f3533;
const SEAM = 0x59615d;
const TROUSERS = 0x14285f;
const SHOES = 0x14110d;
const HELMET = 0xd8321a;
const VENT = 0x9c2411;
const INK_BLACK = 0x14110d;
const FOLDER = 0x1d3a8a;
const PEARL = 0xd9d4c8;
const RAIN = 0x7f9bd0;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

const NOSE = 'M1,-8 C5,-2 10,14 8,19 C6,22 -2,22 -3,19 C-4,14 -2,-4 1,-8 Z';
const BEARD_D = 'M-37,-2 C-36,30 -20,52 0,54 C20,52 36,30 37,-2 C33,16 24,28 14,28 C8,24 -8,24 -14,28 C-24,28 -33,16 -37,-2 Z';

/** The folder held to the chest, the helmet hanging from the other hand. */
const REST: Pose = {
  armR: [0.36, 0.62, 0.17],
  foreR: [-1.78, 0, 0],
  armL: [0.02, 0, -0.08],
  foreL: [-0.3, 0, 0],
};

function look(variant?: string): FaceLook {
  return {
    skin: '#d8a07a',
    brow: '#1f1a16',
    browWidth: 5,
    lidLine: 2.4,
    arcLine: 4,
    mouth: [-3.4, 4.8, 1.7],
    nose: { d: NOSE, fill: '#b47d58', opacity: 0.5 },
    under: variant === 'm' ? [{ d: BEARD_D, fill: BEARD }, { d: ellipse(0, 33, 13, 8), fill: '#d8a07a' }] : [],
    fx: { cheekL: [-22, 14], cheekR: [22, 14], temple: [30, -36], eyeL: [-14, -6], eyeR: [14, -6] },
    frame: [0, -6, 62],
  };
}

function build(b: Build, variant?: string) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const jacket = ink(JACKET, PLATE.top);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;
  const rain = ink(RAIN, PLATE.prop);
  const drop = (p: Vector3, bind: number, s = 1) => S.ball(p, v(0.0055 * s, 0.008 * s, 0.0055 * s), rain, bind, { seg: 6, rings: 4 });

  neck(b, skin2, 0.04);

  // the jacket, straight to the hips
  const coat: Band[] = [
    { y: hip - 0.05, rx: 0.152, rz: 0.108, square: 2.3 },
    { y: hip + 0.04, rx: 0.146, rz: 0.104, square: 2.2 },
    { y: hip + 0.16, rx: 0.136, rz: 0.098 },
    { y: ch - 0.03, rx: 0.144, rz: 0.102, front: 0.012 },
    { y: ch + 0.08, rx: 0.158, rz: 0.098, front: 0.006 },
    { y: sy - 0.045, rx: 0.168, rz: 0.09, square: 2.6 },
    { y: sy - 0.004, rx: 0.124, rz: 0.074, square: 2.4 },
    { y: sy + 0.022, rx: 0.054, rz: 0.048 },
  ];
  trunk(b, coat, jacket);
  // the white shirt in the V, the corduroy collar either side
  onFront(b, coat, [[-0.04, sy + 0.014], [0.04, sy + 0.014], [0, sy - 0.08]], ink(SHIRT, PLATE.skin2), { lift: 0.002 });
  for (const s of [-1, 1]) {
    const pts: Array<[number, number]> = [[s * 0.05, sy + 0.016], [s * 0.084, sy - 0.006], [s * 0.014, sy - 0.1], [s * 0.001, sy - 0.08]];
    onFront(b, coat, s > 0 ? pts : pts.reverse(), ink(CORD, PLATE.under), { lift: 0.005, depth: 0.006 });
  }
  // the pocket flaps and the seams
  for (const s of [-1, 1]) {
    const y = hip + 0.13;
    const a = s * 0.03;
    const c = s * 0.1;
    const pts: Array<[number, number]> = [[a, y + 0.01], [c, y + 0.01], [c, y - 0.008], [a, y - 0.008]];
    onFront(b, coat, s > 0 ? pts.reverse() : pts, ink(POCKET, PLATE.under), { lift: 0.003 });
    const x = s * 0.112;
    onFront(b, coat, [[x - 0.0025, sy - 0.1], [x + 0.0025, sy - 0.1], [x + 0.0025, hip - 0.04], [x - 0.0025, hip - 0.04]], ink(SEAM, PLATE.top), { lift: 0.002, depth: 0.003 });
  }
  drop(v(-0.1, sy + 0.004, 0.06), B.chest);

  // the sleeves to the wrist, a lighter cuff
  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, jacket, [[0, 0.058], [0.45, 0.052], [1, 0.048], [1.88, 0.045]], { capEnd: false });
    cuff(b, side, ink(SEAM, PLATE.under), 1.88, 0.048, 0.03);
    hand(b, side, skin2, 1);
  }

  pelvis(b, ink(TROUSERS, PLATE.bottom), { waist: hip + 0.05, rx: 0.12, rz: 0.09 });
  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(TROUSERS, PLATE.bottom), { top: 0.07, thigh: 0.066, knee: 0.052, calf: 0.049, hem: 0.047 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.045, height: 0.064 });
  }

  // the hair
  const hairA = ink(HAIR, PLATE.hair);
  const hairB = ink(HAIR, PLATE.prop);
  if (variant === 'm') {
    hairCap(S, head, hc, {
      edge: round([[0, -46], [0.5, -42], [1.0, -32], [1.28, -22], [Math.PI / 2, -10], [2.2, 10], [Math.PI, 22], [-2.2, 10], [-Math.PI / 2, -10], [-1.28, -22], [-1.0, -32], [-0.5, -42]]),
      thick: (_th, u) => 0.006 + 0.016 * Math.pow(u, 0.6),
      ink: hairA,
      bind: B.head,
    });
  } else {
    hairCap(S, head, hc, {
      edge: round([[0.08, -50], [0.5, -46], [1.0, -34], [1.3, -16], [Math.PI / 2, -8], [2.1, 14], [Math.PI, 30], [-2.1, 14], [-Math.PI / 2, -8], [-1.3, -16], [-1.0, -34], [-0.45, -45]]),
      thick: (_th, u) => 0.006 + 0.02 * Math.pow(u, 0.55),
      ink: hairA,
      bind: B.head,
    });
    // the pointed locks at the temples
    for (const s of [-1, 1]) {
      const a = onHead(head, hc, head.latOf(-18), s * 1.3, 0.008);
      const m = onHead(head, hc, head.latOf(-4), s * 1.38, 0.008);
      const e = onHead(head, hc, head.latOf(9), s * 1.42, 0.004);
      flick(S, [a, m, e], [0.013, 0.009, 0.002], hairA, B.head, { flat: 0.4, up: v(s, 0, 0.4).normalize() });
    }
    // the low bun at the nape, a little to her right, and its tie
    const bun = onHead(head, hc, head.latOf(22), Math.PI + 0.3, 0.032);
    S.ball(bun, v(0.044, 0.04, 0.036), hairB, B.head, { seg: 14, rings: 9 });
    const tieC = onHead(head, hc, head.latOf(20), Math.PI + 0.26, 0.004);
    const tie: Vector3[] = [];
    for (let i = 0; i < 14; i++) {
      const a = (i / 14) * Math.PI * 2;
      tie.push(tieC.clone().add(v(Math.cos(a) * 0.026, Math.sin(a) * 0.026, 0)));
    }
    S.tube(tie, 0.006, hairA, B.head, { seg: 6, closed: true });
    // pearl studs
    for (const s of [-1, 1]) {
      const w = head.width(13);
      S.ball(head.at(head.x0 + s * (w - 1), 13, -0.006).add(hc).add(v(s * 0.008, 0, 0)), 0.0065, ink(PEARL, PLATE.under), B.head, { seg: 8, rings: 5 });
    }
  }
  // the rain on the hair
  for (const [lat, th] of [[0.95, -0.5], [1.15, 0.4], [0.7, 0.85]] as const) drop(onHead(head, hc, lat, th, variant === 'm' ? 0.022 : 0.026), B.head);

  // what the hands hold, built where they hold it at rest
  const R = posed(J, REST);
  // the blue folder, held to the chest by the right hand
  const palmR = J.palm.R.clone().applyMatrix4(R.handR);
  S.push(R.handR.clone().invert());
  const fz = frontZ(coat, -0.03, ch - 0.03) + 0.026;
  const folder = new Matrix4().compose(v(-0.036, ch - 0.035, Math.max(fz, palmR.z - 0.03)), new Quaternion().setFromAxisAngle(v(0, 0, 1), -0.08), v(1, 1, 1));
  S.slab([[-0.054, -0.08], [0.054, -0.08], [0.054, 0.08], [-0.054, 0.08]], 0.014, folder, ink(FOLDER, PLATE.under), B.handR);
  S.slab([[0.054, -0.078], [0.062, -0.077], [0.062, 0.077], [0.054, 0.078]], 0.011, folder, ink(SHIRT, PLATE.skin2), B.handR);
  for (const [y, w] of [[0.045, 0.07], [0.02, 0.05], [-0.005, 0.072], [-0.03, 0.036]] as const) {
    const line = folder.clone().multiply(new Matrix4().makeTranslation(-0.04 + w / 2, y, 0));
    S.slab([[-w / 2, -0.0022], [w / 2, -0.0022], [w / 2, 0.0022], [-w / 2, 0.0022]], 0.0155, line, ink(SHIRT, PLATE.skin2), B.handR);
  }
  S.pop();
  // the red helmet, held by its rim beside the hip, the dome up
  const palmL = J.palm.L.clone().applyMatrix4(R.handL);
  S.push(R.handL.clone().invert());
  const base = palmL.clone().add(v(0.066, -0.026, 0.01));
  const dome = new Matrix4().compose(base, new Quaternion().setFromAxisAngle(v(0, 0, 1), -0.25), v(1, 1.15, 1.22));
  S.lathe([[0, 0.075], [0.03, 0.071], [0.052, 0.058], [0.068, 0.036], [0.076, 0.012], [0.078, 0], [0.066, 0]], 16, dome, ink(HELMET, PLATE.prop), B.handL);
  // its vents and the dark rim
  for (const a of [-0.55, 0, 0.55]) {
    const q = new Quaternion().setFromAxisAngle(v(1, 0, 0), a);
    const p = v(0, 0.071, 0).applyQuaternion(q);
    const vent = dome.clone().multiply(new Matrix4().compose(p, q, v(1, 1, 1)));
    S.slab([[-0.022, -0.004], [0.022, -0.004], [0.022, 0.004], [-0.022, 0.004]], 0.006, vent.multiply(new Matrix4().makeRotationX(Math.PI / 2)), ink(VENT, PLATE.under), B.handL);
  }
  const rim: Vector3[] = [];
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * Math.PI * 2;
    rim.push(v(Math.cos(a) * 0.077, 0.002, Math.sin(a) * 0.077).applyMatrix4(dome));
  }
  S.tube(rim, 0.005, ink(INK_BLACK, PLATE.under), B.handL, { seg: 5, closed: true });
  drop(v(0.04, 0.062, 0.02).applyMatrix4(dome), B.handL, 0.9);
  drop(v(-0.03, 0.068, -0.025).applyMatrix4(dome), B.handL, 0.9);
  S.pop();
}

export const camille: Person = {
  key: 'camille_marchand',
  name: 'Camille',
  skin: SKIN,
  body: { height: 1.72, head: 0.38, neck: 0.07, shoulders: 0.16, hips: 0.076, legs: 0.42, arm: 0.33, hand: 0.12, foot: 0.22 },
  head: {
    outline: 'M-37,-26 C-37,-58 -20,-66 0,-66 C20,-66 37,-58 37,-26 C37,10 22,48 0,52 C-22,48 -37,10 -37,-26 Z',
    nose: NOSE,
    noseDepth: 0.8,
    ears: [
      [-37, 2, 7, 10],
      [37, 2, 7, 10],
    ],
    chin: 14,
    wrap: [2.0, 2.5],
  },
  look,
  face: (variant) => rigFace(rig, variant),
  eyes: [
    [-14, -6],
    [14, -6],
  ],
  build,
  manner: { rest: REST, energy: 0.9 },
  variants: ['f', 'm'],
};
