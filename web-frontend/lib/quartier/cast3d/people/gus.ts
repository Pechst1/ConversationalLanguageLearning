/**
 * Augustin de Roncourt, Gus, in the round.
 *
 * From his rig: tall, the cobalt suit cut like an inverted triangle (padded square shoulders, a
 * narrow waist, two brass buttons), dark navy lapels over a white shirt and the red tie, the red
 * and white pocket square, white cuffs, long navy legs and long black shoes, and the brown hair
 * swept up into a quiff with its one curl over the brow. His index cards are in his left hand; he
 * holds his chest high.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import type { MouthValues } from '@/components/cast/vivant/kit';
import { gus as fig } from '@/components/cast/vivant/figures/gus';

import { vivantFace } from '../face';
import { flick, hairCap, onHead, round } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, button, cuff, frontZ, hand, ink, leg, neck, onFront, shoe, sleeve, trunk } from '../kit';
import type { Person } from '../model';
import { B } from '../rig';

const SKIN = 0xe0a985;
const HAIR = 0x3d2817;
const HAIR_LIGHT = 0x8a5a32;
const SUIT = 0x1d3a8a;
const LAPEL = 0x14285f;
const SHIRT = 0xf8f3e8;
const TIE = 0xd8321a;
const KNOT = 0x9c2411;
const BRASS = 0xc49a0a;
const SHOES = 0x14110d;
const CARD_LINE = 0x6f6857;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

/** His own mouth: the open-mouthed indignation of the cross portrait (from his figure). */
const OUTRE: Omit<MouthValues, 'key'> = {
  d: 'M-7,20 Q-5.5,10.5 2,10.5 Q9.5,10.5 11,20 Q2,17.6 -7,20 Z',
  fill: '#14110d',
  teeth: 'M-5.2,15 Q-2.6,11.5 2,11.5 Q6.6,11.5 9.2,15 L8.8,16.4 Q2,13.2 -4.8,16.4 Z',
  tongue: 'M-3.5,19.2 Q2,15.8 7.5,19.2 Q2,18 -3.5,19.2 Z',
  line: '',
};
const own = (m: MouthValues): MouthValues => (m.key === 'outre' ? { key: m.key, ...OUTRE } : m);

function build(b: Build) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const suit = ink(SUIT, PLATE.top);
  const lapel = ink(LAPEL, PLATE.under);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;

  neck(b, skin2, 0.04);

  // the jacket: square padded shoulders tapering to a narrow waist
  const jacket: Band[] = [
    { y: hip - 0.075, rx: 0.15, rz: 0.104, square: 2.3 },
    { y: hip + 0.04, rx: 0.138, rz: 0.098 },
    { y: hip + 0.17, rx: 0.118, rz: 0.092 },
    { y: ch, rx: 0.158, rz: 0.108, front: 0.012 },
    { y: ch + 0.12, rx: 0.192, rz: 0.104, square: 2.6 },
    { y: sy - 0.035, rx: 0.206, rz: 0.094, square: 3 },
    { y: sy + 0.002, rx: 0.15, rz: 0.074, square: 2.6 },
    { y: sy + 0.026, rx: 0.058, rz: 0.05 },
  ];
  trunk(b, jacket, suit);
  // the shirt's V, the tie, the lapels over them
  const vTop = sy + 0.012;
  const vPoint = hip + 0.2;
  onFront(b, jacket, [[-0.058, vTop], [0, vPoint], [0.058, vTop]], ink(SHIRT, PLATE.skin2), { lift: 0.002 });
  onFront(b, jacket, [[-0.014, vTop - 0.004], [0.014, vTop - 0.004], [0.011, vTop - 0.03], [-0.011, vTop - 0.03]], ink(KNOT, PLATE.under), { lift: 0.006, depth: 0.008 });
  onFront(b, jacket, [[-0.011, vTop - 0.03], [0.011, vTop - 0.03], [0.02, vPoint + 0.03], [0, vPoint + 0.005], [-0.02, vPoint + 0.03]], ink(TIE, PLATE.under), { lift: 0.006 });
  for (const s of [-1, 1]) {
    const pts: Array<[number, number]> = [
      [s * 0.056, vTop + 0.004],
      [s * 0.104, vTop - 0.006],
      [s * 0.016, vPoint - 0.04],
      [s * 0.002, vPoint - 0.004],
    ];
    onFront(b, jacket, s > 0 ? pts : pts.reverse(), lapel, { lift: 0.005, depth: 0.006 });
  }
  // two brass buttons below the V
  for (const y of [vPoint - 0.07, vPoint - 0.15]) button(b, v(0, y, frontZ(jacket, 0, y) + 0.004), 0.009, ink(BRASS, PLATE.prop), B.spine);
  // the pocket square, red over white, on his left breast
  const px = 0.105;
  const py = ch + 0.075;
  onFront(b, jacket, [[px - 0.03, py - 0.012], [px + 0.032, py - 0.016], [px + 0.03, py + 0.004], [px - 0.03, py + 0.006]], ink(LAPEL, PLATE.under), { lift: 0.003 });
  onFront(b, jacket, [[px - 0.026, py], [px - 0.018, py + 0.034], [px - 0.006, py + 0.012], [px + 0.006, py + 0.036], [px + 0.016, py + 0.012], [px + 0.026, py + 0.03], [px + 0.028, py]], ink(TIE, PLATE.prop), { lift: 0.006 });
  onFront(b, jacket, [[px - 0.02, py + 0.004], [px - 0.012, py + 0.026], [px - 0.004, py + 0.006]], ink(SHIRT, PLATE.skin2), { lift: 0.009, depth: 0.003 });

  // sleeves to the wrist, a white cuff showing
  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, suit, [[0, 0.062], [0.4, 0.054], [1, 0.05], [1.6, 0.046], [1.93, 0.045]], { capEnd: true, lift: 0.02 });
    cuff(b, side, ink(SHIRT, PLATE.skin2), 1.95, 0.034, 0.03);
    hand(b, side, skin2, 1.02);
  }

  // long navy legs and long black shoes
  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(LAPEL, PLATE.bottom), { top: 0.07, thigh: 0.066, knee: 0.052, calf: 0.049, hem: 0.047 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.043, height: 0.062 });
  }

  // the hair: swept up into a quiff over the brow, the sides close
  const hairInk = ink(HAIR, PLATE.hair);
  hairCap(S, head, hc, {
    edge: round([
      [0, -47],
      [-0.4, -52],
      [-0.8, -42],
      [-1.15, -30],
      [-1.45, -16],
      [-1.8, -6],
      [-2.4, 10],
      [Math.PI, 16],
      [2.4, 10],
      [1.8, -6],
      [1.45, -18],
      [1.1, -36],
      [0.7, -50],
      [0.3, -53],
    ]),
    thick: (th, u) => {
      // the quiff: high over the front of the crown, swept back
      const front = Math.max(0, Math.cos(th));
      const quiff = 0.11 * Math.pow(Math.sin(Math.min(1, u * 1.2) * Math.PI * 0.6), 1.1) * (0.25 + 0.75 * front * front);
      return 0.009 + 0.024 * Math.pow(u, 0.6) + quiff;
    },
    ink: hairInk,
    bind: B.head,
  });
  // a lighter lock across the quiff
  const lat = (y: number) => head.latOf(y);
  const lockA = onHead(head, hc, lat(-62), -0.55, 0.09);
  const lockB = onHead(head, hc, lat(-72), 0.1, 0.13);
  const lockC = onHead(head, hc, lat(-64), 0.75, 0.1);
  flick(S, [lockA, lockA.clone().lerp(lockB, 0.5).add(v(0, 0.012, 0.01)), lockB, lockC], [0.012, 0.02, 0.02, 0.008], ink(HAIR_LIGHT, PLATE.prop), B.head, { flat: 0.35, up: v(0, 1, 0) });
  // the curl over his brow
  const c0 = onHead(head, hc, lat(-50), 0.18, 0.03);
  const c1 = onHead(head, hc, lat(-40), 0.08, 0.026);
  const c2 = onHead(head, hc, lat(-33), 0.2, 0.018);
  const c3 = onHead(head, hc, lat(-38), 0.32, 0.014);
  flick(S, [c0, c1, c2, c3], [0.014, 0.012, 0.009, 0.004], hairInk, B.head, { flat: 0.6 });

  // the index cards in his left hand
  const palm = J.palm.L.clone().add(v(-0.004, -0.004, 0.03));
  const cards = new Matrix4().compose(palm, new Quaternion().setFromAxisAngle(v(1, 0, 0), Math.PI / 2).multiply(new Quaternion().setFromAxisAngle(v(0, 0, 1), 0.2)), v(1, 1, 1));
  S.slab([[-0.045, -0.03], [0.045, -0.03], [0.045, 0.03], [-0.045, 0.03]], 0.012, cards, ink(SHIRT, PLATE.prop), B.handL);
  for (const [y, w] of [[0.012, 0.07], [0.0, 0.06], [-0.012, 0.066]] as const) {
    const line = cards.clone().multiply(new Matrix4().makeTranslation(-0.008, y, 0));
    S.slab([[-w / 2, -0.0015], [w / 2, -0.0015], [w / 2, 0.0015], [-w / 2, 0.0015]], 0.0135, line, ink(CARD_LINE, PLATE.under), B.handL);
  }
}

export const gus: Person = {
  key: 'augustin_de_roncourt',
  name: 'Gus',
  skin: SKIN,
  body: { height: 1.8, head: 0.4, neck: 0.085, shoulders: 0.172, hips: 0.076, legs: 0.44, arm: 0.33, hand: 0.12, foot: 0.22, stoop: -0.08 },
  head: {
    outline: 'M-38,-28 C-38,-60 -20,-68 2,-68 C24,-68 40,-58 40,-28 L40,8 C40,34 26,54 2,58 C-22,54 -38,34 -38,8 Z',
    nose: 'M1,-10 C5,-6 11,14 10,20 C8,24 -1,24 -3,20 C-3,12 -1,-6 1,-10 Z',
    noseDepth: 0.85,
    ears: [
      [-38, 2, 7, 11],
      [40, 2, 7, 11],
    ],
    chin: 16,
  },
  look: {
    skin: '#e0a985',
    brow: '#3d2817',
    browWidth: 5.5,
    lidLine: 2.6,
    arcLine: 4.2,
    mouth: [-1.6, 7, 1.8],
    nose: { d: 'M1,-10 C5,-6 11,14 10,20 C8,24 -1,24 -3,20 C-3,12 -1,-6 1,-10 Z', fill: '#b97f5c', opacity: 0.5 },
    under: [
      { d: 'M-30,30 Q-14,48 2,51 Q18,48 33,30 Q22,55 2,58 Q-18,55 -30,30 Z', fill: '#cf956f' },
      { d: 'M2,50 L2,56', stroke: '#b97f5c', width: 2 },
    ],
    fx: { cheekL: [-22, 22], cheekR: [26, 22], temple: [33, -36], eyeL: [-15, -6], eyeR: [17, -6] },
    frame: [1, -5, 64],
  },
  face: () => vivantFace(fig, own),
  eyes: [
    [-15, -6],
    [17, -6],
  ],
  build,
  manner: {
    rest: {
      armL: [-0.18, 0, -0.1],
      foreL: [-1.25, -0.35, 0],
      handL: [0.25, 0, -0.1],
      armR: [0.02, 0, 0.04],
      foreR: [-0.3, 0, 0],
      handR: [0.05, 0, 0],
    },
    energy: 1.2,
  },
};
