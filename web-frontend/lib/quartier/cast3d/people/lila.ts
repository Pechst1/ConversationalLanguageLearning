/**
 * Lila Bonnet, in the round.
 *
 * From her rig: a round face with its freckles under a crown of tight black curls, the high bun
 * on top tied with the ochre scarf (its bow over her left ear, the ends hanging), big gold hoops,
 * the sunflower shirt with short sleeves and an ochre collar, blue trousers and red shoes with a
 * white sole. Her pencil is in her right hand, ready.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import { lila as fig } from '@/components/cast/vivant/figures/lila';
import { dots } from '@/components/cast/rig-kit';

import { vivantFace } from '../face';
import { flick, hairCap, onHead, round } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, hand, ink, leg, neck, onFront, pelvis, shoe, sleeve, trunk } from '../kit';
import type { Person } from '../model';
import { B } from '../rig';

const SKIN = 0xc98a62;
const HAIR = 0x2a1a12;
const SHIRT = 0xf3c318;
const OCHRE = 0xc49a0a;
const OCHRE_DARK = 0xa7830a;
const TROUSERS = 0x1d3a8a;
const SHOES = 0xd8321a;
const SOLE = 0xf8f3e8;
const PENCIL = 0xd8321a;
const INK_BLACK = 0x14110d;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

const FRECKLES: Array<[number, number]> = [[-24, 8], [-28, 12], [-20, 13], [-31, 5], [-25, 16], [24, 8], [28, 12], [20, 13], [31, 5], [25, 16], [-5, 3], [5, 3]];
/** the drawing's curls round the face (x, y, r in the head frame) */
const FRONT_CURLS: Array<[number, number, number]> = [[-34, -36, 9], [34, -36, 9], [-21, -46, 8.5], [21, -46, 8.5], [-40, -20, 7], [40, -20, 7], [-6, -51, 7], [8, -51, 7]];
const BUN: Array<[number, number, number]> = [[0, -82, 20], [-15, -74, 13], [15, -74, 13], [-7, -94, 11], [9, -95, 11]];

function build(b: Build) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const shirt = ink(SHIRT, PLATE.top);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;

  neck(b, skin2, 0.038);

  const top: Band[] = [
    { y: hip - 0.035, rx: 0.124, rz: 0.093 },
    { y: hip + 0.06, rx: 0.124, rz: 0.092 },
    { y: hip + 0.15, rx: 0.115, rz: 0.086 },
    { y: ch - 0.02, rx: 0.128, rz: 0.094, front: 0.012 },
    { y: ch + 0.06, rx: 0.136, rz: 0.092, front: 0.006 },
    { y: sy - 0.04, rx: 0.142, rz: 0.084, square: 2.4 },
    { y: sy - 0.002, rx: 0.106, rz: 0.068, square: 2.3 },
    { y: sy + 0.02, rx: 0.05, rz: 0.046 },
  ];
  trunk(b, top, shirt);
  // the ochre collar either side of a small V
  onFront(b, top, [[-0.034, sy + 0.012], [0.034, sy + 0.012], [0, sy - 0.04]], skin2, { lift: 0.002 });
  for (const s of [-1, 1]) {
    const pts: Array<[number, number]> = [[s * 0.036, sy + 0.014], [s * 0.068, sy + 0.0], [s * 0.012, sy - 0.062], [s * 0.002, sy - 0.04]];
    onFront(b, top, s > 0 ? pts : pts.reverse(), ink(OCHRE, PLATE.under), { lift: 0.004 });
  }

  // short sleeves, bare forearms
  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, shirt, [[0, 0.05], [0.5, 0.046], [0.95, 0.045]], { capEnd: true });
    sleeve(b, side, skin2, [[0.9, 0.031], [1.5, 0.029], [1.98, 0.024]], { capStart: false });
    hand(b, side, skin2, 0.95);
  }

  pelvis(b, ink(TROUSERS, PLATE.bottom), { waist: hip + 0.02, rx: 0.108, rz: 0.082 });
  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(TROUSERS, PLATE.bottom), { top: 0.066, thigh: 0.064, knee: 0.05, calf: 0.047, hem: 0.045 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.044, height: 0.062, sole: ink(SOLE, PLATE.prop) });
  }

  // the curls: a close cap, then curls all round it, two inks so each curl keeps its outline
  const hairA = ink(HAIR, PLATE.hair);
  const hairB = ink(HAIR, PLATE.skin2);
  hairCap(S, head, hc, {
    edge: round([
      [0, -44],
      [-0.6, -40],
      [-1.1, -26],
      [-1.45, -6],
      [-1.8, 14],
      [-2.4, 30],
      [Math.PI, 36],
      [2.4, 30],
      [1.8, 14],
      [1.45, -6],
      [1.1, -26],
      [0.6, -40],
    ]),
    thick: (_th, u) => 0.012 + 0.012 * u,
    ink: hairA,
    bind: B.head,
  });
  const curl = (theta: number, y: number, r: number, out: number, k: number) => {
    const p = onHead(head, hc, head.latOf(y), theta, out);
    S.ball(p, r, k % 2 ? hairB : hairA, B.head, { seg: 10, rings: 6 });
  };
  let k = 0;
  // round the face, where the drawing puts them
  for (const [x, y, r] of FRONT_CURLS) {
    const w = Math.max(1, head.width(y));
    const th = Math.asin(Math.max(-0.98, Math.min(0.98, (x - head.x0) / w))) * 1.08;
    curl(th, y, r * head.s * 1.05, 0.014, k++);
  }
  // the sides and the back, in rows, each row turned half a step
  const rows: Array<[number, number, number, number]> = [
    // head-frame height, radius (units), count, angular range from the side to the back
    [-50, 13, 7, 2.1],
    [-30, 13, 10, 1.55],
    [-8, 12.5, 11, 1.5],
    [14, 11.5, 11, 1.55],
    [32, 9.5, 9, 1.7],
    [44, 7, 7, 1.9],
  ];
  rows.forEach(([y, r, n, start], ri) => {
    for (let i = 0; i < n; i++) {
      const f = n === 1 ? 0.5 : i / (n - 1);
      const th = start + (Math.PI * 2 - 2 * start) * f + (ri % 2 ? 0.12 : 0);
      curl(th, y, r * head.s, 0.016, k++);
    }
  });
  // the bun, up on top, a little back
  for (const [x, y, r] of BUN) {
    const p = head.at(x, y, -0.03).add(hc);
    S.ball(p, r * head.s * 1.05, k++ % 2 ? hairB : hairA, B.head, { seg: 12, rings: 7 });
  }
  // the scarf round the bun's base, its bow over her left ear, the ends hanging
  const scarf = ink(OCHRE, PLATE.under);
  const band: Vector3[] = [];
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * Math.PI * 2;
    band.push(head.at(Math.sin(a) * 24, -62 + Math.cos(a) * 1.5, Math.cos(a) * 0.075 - 0.03).add(hc));
  }
  S.tube(band, [0.012, 0.022], scarf, B.head, { seg: 8, closed: true });
  const knot = head.at(22, -61, 0.02).add(hc);
  S.ball(knot, 0.016, ink(OCHRE_DARK, PLATE.prop), B.head, { seg: 10, rings: 6 });
  for (const [dx, dy] of [[0.05, 0.05], [0.06, -0.012]] as const) {
    const tip = knot.clone().add(v(dx, dy, -0.01));
    flick(S, [knot, knot.clone().lerp(tip, 0.5).add(v(0, dy * 0.4, 0.02)), tip, tip.clone().add(v(-dx * 0.25, -0.02, -0.02))], [0.012, 0.022, 0.02, 0.008], scarf, B.head, { flat: 0.35, up: v(0, 0, 1) });
  }
  const tailTop = knot.clone().add(v(0.006, -0.01, -0.004));
  flick(S, [tailTop, tailTop.clone().add(v(0.012, -0.05, -0.006)), tailTop.clone().add(v(0.02, -0.1, -0.012))], [0.01, 0.012, 0.009], ink(OCHRE_DARK, PLATE.prop), B.head, { flat: 0.3, up: v(0, 0, 1) });

  // big gold hoops
  for (const ex of [-40, 40]) {
    const side = ex < 0 ? -1 : 1;
    const w = head.width(12);
    const p = head.at(head.x0 + side * (w + 4), 12, 0.012).add(hc);
    const r = 9 * head.s;
    const ring: Vector3[] = [];
    for (let i = 0; i < 18; i++) {
      const a = (i / 18) * Math.PI * 2;
      ring.push(p.clone().add(v(side * 0.006, -r + Math.cos(a) * r, Math.sin(a) * r)));
    }
    S.tube(ring, 0.0032, ink(OCHRE, PLATE.prop), B.head, { seg: 5, closed: true });
  }

  // the pencil in her right hand, point up once the hand is raised
  const palm = J.palm.R.clone().add(v(0.006, 0.0, 0.024));
  const q = new Quaternion().setFromAxisAngle(v(1, 0, 0), Math.PI / 2).multiply(new Quaternion().setFromAxisAngle(v(0, 0, 1), -0.35));
  S.at(palm, q, () => {
    S.lathe([[0, -0.06], [0.0055, -0.058], [0.0055, 0.07], [0, 0.07]], 6, new Matrix4(), ink(PENCIL, PLATE.prop), B.handR, { flat: true });
    S.lathe([[0.0055, 0.07], [0.0015, 0.088], [0, 0.092]], 6, new Matrix4(), ink(INK_BLACK, PLATE.under), B.handR, { flat: true });
  });
}

export const lila: Person = {
  key: 'lila_bonnet',
  name: 'Lila',
  skin: SKIN,
  body: { height: 1.47, head: 0.33, neck: 0.06, shoulders: 0.14, hips: 0.072, legs: 0.4, arm: 0.33, hand: 0.11, foot: 0.2 },
  head: {
    outline: 'M-42,-14 C-42,-46 -22,-54 0,-54 C22,-54 42,-46 42,-14 C42,16 26,44 0,48 C-26,44 -42,16 -42,-14 Z',
    nose: 'M0,4 C4,4 6,10 4,13 C2,15 -3,15 -4,13 C-6,10 -4,4 0,4 Z',
    noseDepth: 0.7,
    ears: [],
    chin: 10,
    front: 0.86,
    back: 1.06,
  },
  look: {
    skin: '#c98a62',
    brow: '#2a1a12',
    browWidth: 5.5,
    lidLine: 2.6,
    arcLine: 4.2,
    glassy: ['emu'],
    mouth: [-3.8, 2, 1.9],
    nose: { d: 'M0,4 C4,4 6,10 4,13 C2,15 -3,15 -4,13 C-6,10 -4,4 0,4 Z', fill: '#a5683f', opacity: 0.5 },
    under: [{ d: dots(FRECKLES, 1.3), fill: '#8f5534' }],
    over: [{ d: 'M-25,-9 L-30,-13 M25,-9 L30,-13', stroke: '#14110d', width: 2.6 }],
    fx: { cheekL: [-25, 12], cheekR: [25, 12], temple: [34, -28], eyeL: [-16, -4], eyeR: [16, -4] },
    frame: [0, -3, 56],
  },
  face: () => vivantFace(fig),
  eyes: [
    [-16, -4],
    [16, -4],
  ],
  build,
  manner: {
    rest: {
      armR: [-0.3, 0, 0.12],
      foreR: [-1.95, 0.45, 0],
      handR: [0.25, 0, 0.1],
      armL: [0.05, 0, -0.15],
      foreL: [-0.55, 0.2, 0],
      handL: [0, 0, -0.2],
    },
    energy: 1.35,
  },
};
