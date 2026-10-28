/**
 * Marin Lévêque, in the round.
 *
 * From his rig: big and broad in the green cable-knit jumper (three cables down the front, a
 * ribbed hem, cuffs and crew collar in the darker green), the charm on its cord, thick grey-brown
 * trousers and big black shoes, a round face with a full beard, and the tight curls with their
 * ochre glints. He hugs his blue book with the yellow band against his chest.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import { marin as fig } from '@/components/cast/vivant/figures/marin';

import type { FaceState } from '../face';
import { vivantFace } from '../face';
import { hairCap, onHead, round } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, cuff, frontZ, hand, ink, leg, neck, shoe, sleeve, torsoBind, trunk } from '../kit';
import type { Person } from '../model';
import { B } from '../rig';

const SKIN = 0x9a6643;
const HAIR = 0x1c1611;
const GLINT = 0xc49a0a;
const KNIT = 0x2c6a5d;
const RIB = 0x1f4f45;
const TROUSERS = 0x4a4338;
const SHOES = 0x14110d;
const CORD = 0x4a3020;
const CHARM = 0xf8f3e8;
const BOOK = 0x1d3a8a;
const PAGES = 0xf8f3e8;
const BAND = 0xf3c318;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

/** how far the jaw drops in the beard for an open mouth (his figure's own) */
const JAW: Record<string, number> = { bigO: 7, o: 3, yawn: 6, shout: 5 };
const jaw = (s: FaceState) => JAW[s.mouth.key.replace('~', '')] ?? 0;
const BACK_CURLS: Array<[number, number, number]> = [[-36, -38, 16], [-18, -54, 18], [4, -58, 18], [26, -50, 17], [40, -32, 14], [-46, -16, 12], [48, -14, 11], [-28, -48, 14], [14, -56, 16]];
const FRONT_CURLS: Array<[number, number, number]> = [[-28, -40, 10], [-11, -45, 11], [7, -46, 11], [24, -41, 10], [37, -32, 8]];

function build(b: Build) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const knit = ink(KNIT, PLATE.top);
  const rib = ink(RIB, PLATE.under);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;

  neck(b, skin2, 0.05);

  // the jumper: broad and round
  const jumper: Band[] = [
    { y: hip - 0.03, rx: 0.205, rz: 0.15, front: 0.02 },
    { y: hip + 0.07, rx: 0.222, rz: 0.162, front: 0.034 },
    { y: hip + 0.19, rx: 0.226, rz: 0.165, front: 0.04 },
    { y: ch, rx: 0.222, rz: 0.152, front: 0.03 },
    { y: ch + 0.1, rx: 0.214, rz: 0.134, front: 0.014 },
    { y: sy - 0.045, rx: 0.205, rz: 0.118, square: 2.4 },
    { y: sy - 0.004, rx: 0.145, rz: 0.088, square: 2.3 },
    { y: sy + 0.024, rx: 0.064, rz: 0.058 },
  ];
  trunk(b, jumper, knit, { seg: 28 });
  // the ribbed hem
  trunk(b, [
    { y: hip - 0.075, rx: 0.2, rz: 0.146, front: 0.018 },
    { y: hip - 0.06, rx: 0.212, rz: 0.156, front: 0.02 },
    { y: hip - 0.01, rx: 0.214, rz: 0.158, front: 0.022 },
    { y: hip + 0.005, rx: 0.205, rz: 0.15, front: 0.02 },
  ], rib, { seg: 28 });
  // the crew collar
  const collar: Vector3[] = [];
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2;
    collar.push(v(Math.sin(a) * 0.066, sy + 0.02 - Math.cos(a) * 0.006, Math.cos(a) * 0.06 - 0.008));
  }
  S.tube(collar, 0.016, rib, torsoBind(J), { seg: 8, closed: true });
  // three cables down the front, chevrons of raised stitch
  for (const x0 of [-0.105, 0, 0.105]) {
    for (let y = sy - 0.075; y > hip + 0.02; y -= 0.05) {
      const pts = [v(x0 - 0.022, y, 0), v(x0, y - 0.024, 0), v(x0 + 0.022, y, 0)];
      for (const p of pts) p.z = frontZ(jumper, p.x, p.y) + 0.002;
      S.tube(pts, 0.0085, rib, torsoBind(J), { seg: 6, caps: true });
    }
  }
  // the charm on its cord
  const cord: Vector3[] = [];
  for (let i = 0; i <= 10; i++) {
    const t = i / 10;
    const x = Math.sin((t - 0.5) * Math.PI) * 0.055;
    const y = sy + 0.01 - Math.sin(t * Math.PI) * 0.1;
    cord.push(v(x, y, frontZ(jumper, x, y) + 0.004));
  }
  S.tube(cord, 0.0028, ink(CORD, PLATE.prop), torsoBind(J), { seg: 5 });
  const cy = sy + 0.01 - 0.1;
  const cz = frontZ(jumper, 0, cy) + 0.008;
  S.tube([v(-0.002, cy, cz), v(-0.008, cy - 0.022, cz + 0.004), v(0.006, cy - 0.038, cz + 0.006)], [0.008, 0.0065, 0.002], ink(CHARM, PLATE.prop), B.chest, { seg: 7, caps: 0.003 });

  // thick sleeves to the wrist, ribbed cuffs
  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, knit, [[0, 0.078], [0.45, 0.07], [1, 0.064], [1.6, 0.058], [1.9, 0.054]], { capEnd: true, lift: 0.02 });
    cuff(b, side, rib, 1.9, 0.056, 0.05);
    hand(b, side, skin2, 1.25);
  }

  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(TROUSERS, PLATE.bottom), { top: 0.096, thigh: 0.09, knee: 0.072, calf: 0.07, hem: 0.068 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.06, height: 0.08 });
  }

  // the curls, close and tight, a few catching the light
  const hairA = ink(HAIR, PLATE.hair);
  const hairB = ink(HAIR, PLATE.under);
  hairCap(S, head, hc, {
    edge: round([
      [0, -40],
      [-0.6, -36],
      [-1.15, -24],
      [-1.5, -10],
      [-1.9, 2],
      [-2.5, 14],
      [Math.PI, 18],
      [2.5, 14],
      [1.9, 2],
      [1.5, -10],
      [1.15, -24],
      [0.6, -36],
    ]),
    thick: (_th, u) => 0.01 + 0.014 * u,
    ink: hairA,
    bind: B.head,
  });
  let k = 0;
  const curl = (theta: number, y: number, r: number, out: number) => {
    const p = onHead(head, hc, head.latOf(y), theta, out);
    S.ball(p, r, k++ % 2 ? hairB : hairA, B.head, { seg: 9, rings: 6 });
    return p;
  };
  const glints: Vector3[] = [];
  for (const [x, y, r] of [...FRONT_CURLS, ...BACK_CURLS]) {
    const w = Math.max(1, head.width(y));
    const th = Math.asin(Math.max(-0.98, Math.min(0.98, (x - head.x0) / w))) * 1.05;
    glints.push(curl(th, y, r * head.s * 0.85, 0.016));
  }
  const rows: Array<[number, number, number, number]> = [
    [-52, 15, 6, 1.9],
    [-34, 14, 9, 1.4],
    [-14, 12, 9, 1.75],
    [4, 10, 8, 2.0],
  ];
  rows.forEach(([y, r, n, start], ri) => {
    for (let i = 0; i < n; i++) {
      const f = n === 1 ? 0.5 : i / (n - 1);
      curl(start + (Math.PI * 2 - 2 * start) * f + (ri % 2 ? 0.14 : 0), y, r * head.s * 0.85, 0.014);
    }
  });
  // ochre glints: short arcs on the upper left of the front curls
  glints.slice(0, 9).forEach((p, i) => {
    if (i % 2) return;
    const r = 0.022;
    const arc = [p.clone().add(v(-r * 0.7, 0.002, r * 0.6)), p.clone().add(v(-r * 0.35, r * 0.6, r * 0.75)), p.clone().add(v(r * 0.2, r * 0.75, r * 0.6))];
    S.tube(arc, 0.003, ink(GLINT, PLATE.prop), B.head, { seg: 4, caps: true });
  });

  // the book, flat against his palm: it stands against his chest when he hugs it
  const palm = J.palm.R.clone().add(v(0.03, -0.01, 0.01));
  const book = new Matrix4().compose(palm, new Quaternion().setFromAxisAngle(v(0, 0, 1), 0.0), v(1, 1, 1));
  S.at(new Vector3(), null, () => {
    const m = book.clone().multiply(new Matrix4().makeTranslation(0, -0.02, 0.03));
    S.box(new Vector3().setFromMatrixPosition(m), v(0.032, 0.2, 0.15), ink(BOOK, PLATE.prop), B.handR);
    S.box(new Vector3().setFromMatrixPosition(m).add(v(-0.001, 0, 0.074)), v(0.026, 0.192, 0.004), ink(PAGES, PLATE.under), B.handR);
    S.box(new Vector3().setFromMatrixPosition(m).add(v(0.0165, 0.05, 0)), v(0.003, 0.014, 0.152), ink(BAND, PLATE.under), B.handR);
  });
}

export const marin: Person = {
  key: 'marin_leveque',
  name: 'Marin',
  skin: SKIN,
  body: { height: 1.76, head: 0.37, neck: 0.04, shoulders: 0.2, hips: 0.1, legs: 0.37, arm: 0.33, hand: 0.13, foot: 0.24, spread: 0.24 },
  head: {
    outline: 'M-46,-14 C-46,-46 -24,-54 0,-54 C24,-54 46,-46 46,-14 C46,20 32,48 0,50 C-32,48 -46,20 -46,-14 Z',
    nose: 'M0,0 C6,0 10,10 8,15 C6,19 -6,19 -8,15 C-10,10 -6,0 0,0 Z',
    noseDepth: 0.62,
    ears: [
      [-46, 0, 8.5, 11],
      [47, 0, 8.5, 11],
    ],
    chin: 12,
    back: 1.05,
    // the beard wraps round the jaw
    wrap: [2.05, 2.6],
  },
  look: {
    skin: '#9a6643',
    brow: '#1c1611',
    browWidth: 7,
    lidLine: 2.4,
    arcLine: 4.5,
    mouth: (s) => [-5, -1 + jaw(s) / 2, 2],
    nose: { d: 'M0,0 C6,0 10,10 8,15 C6,19 -6,19 -8,15 C-10,10 -6,0 0,0 Z', fill: '#774a2c', opacity: 0.5 },
    under: (s) => {
      const j = jaw(s);
      const beard = j
        ? `M-46,-2 C-48,${32 + j / 2} -26,${60 + j} 0,${62 + j} C26,${60 + j} 48,${32 + j / 2} 46,-2 C40,10 30,15 17,13 C8,9 -8,9 -17,13 C-30,15 -40,10 -46,-2 Z`
        : 'M-46,-2 C-48,32 -26,60 0,62 C26,60 48,32 46,-2 C40,10 30,15 17,13 C8,9 -8,9 -17,13 C-30,15 -40,10 -46,-2 Z';
      // the beard runs on past the drawing's edge, round the jaw to the ears
      return [
        { d: 'M-60,-6 L-46,-6 L-46,64 L-60,64 Z M46,-6 L60,-6 L60,64 L46,64 Z M-60,52 L60,52 L60,70 L-60,70 Z', fill: '#1c1611' },
        { d: beard, fill: '#1c1611' },
        { d: `M-20,${33 + j / 2} A19,${12 + j / 2} 0 1 0 18,${33 + j / 2} A19,${12 + j / 2} 0 1 0 -20,${33 + j / 2} Z`, fill: '#9a6643' },
      ];
    },
    over: [{ d: 'M-23,21 C-12,13 10,13 21,21 C10,24 -12,24 -23,21 Z', fill: '#1c1611' }],
    fx: { cheekL: [-30, 8], cheekR: [31, 8], temple: [40, -24], eyeL: [-18, -6], eyeR: [19, -6] },
    frame: [0, -2, 62],
  },
  face: () => vivantFace(fig),
  eyes: [
    [-18, -6],
    [19, -6],
  ],
  build,
  manner: {
    rest: {
      armR: [-0.42, 0, 0.42],
      foreR: [-1.55, 1.0, 0],
      handR: [0, -0.3, 0.1],
      armL: [0.02, 0, -0.03],
      foreL: [-0.18, 0, 0],
    },
    energy: 0.85,
  },
};
