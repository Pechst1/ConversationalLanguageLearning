/**
 * Margaux Barman, la patronne, in the round.
 *
 * From her rig and her model sheet: the green shirt with its sleeves rolled to the elbow and the
 * dark collar, the long dark bistro apron with its bib, its straps and the two brass buttons, navy
 * trousers, the cropped silver hair swept up and back with its three tufts, the gold hoops. She
 * holds a wine glass up in her right hand (it is always already dry); the striped towel the
 * drawing hangs from her left hand is over her left shoulder here, so that hand is free to talk.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import { margaux as fig } from '@/components/cast/vivant/figures/margaux';

import { vivantFace } from '../face';
import { flick, hairCap, onHead, round } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, bandAt, button, cuff, frontZ, hand, ink, leg, neck, patch, pelvis, shoe, skirt, sleeve, torsoBind, trunk } from '../kit';
import type { Person } from '../model';
import { B } from '../rig';

const SKIN = 0xcf946a;
const SHIRT = 0x2c6a5d;
const COLLAR = 0x1f4f45;
const APRON = 0x2a231c;
const HAIR = 0xdcd6c8;
const BRASS = 0xc49a0a;
const CREAM = 0xf8f3e8;
const RED = 0xd8321a;
const TROUSERS = 0x14285f;
const SHOES = 0x14110d;
const GLASS_BLUE = 0x1d3a8a;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

function build(b: Build) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const shirt = ink(SHIRT, PLATE.top);
  const apron = ink(APRON, PLATE.under);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;

  neck(b, skin2, 0.043);

  // the shirt
  const bands: Band[] = [
    { y: hip - 0.06, rx: 0.125, rz: 0.094 },
    { y: hip + 0.03, rx: 0.13, rz: 0.097 },
    { y: hip + 0.15, rx: 0.121, rz: 0.091 },
    { y: ch - 0.04, rx: 0.137, rz: 0.1, front: 0.014 },
    { y: ch + 0.07, rx: 0.15, rz: 0.098, front: 0.01 },
    { y: sy - 0.05, rx: 0.157, rz: 0.09, square: 2.5 },
    { y: sy - 0.005, rx: 0.118, rz: 0.074, square: 2.4 },
    { y: sy + 0.022, rx: 0.056, rz: 0.05 },
  ];
  trunk(b, bands, shirt);
  // the open collar: a V of skin, the dark collar either side
  const neckFront = 0.072;
  patch(b, [[-0.042, 0.03], [0.042, 0.03], [0, -0.05]], v(0, sy - 0.005, neckFront), skin2, B.chest, { depth: 0.004, bend: 0.09 });
  for (const s of [-1, 1]) {
    patch(b, [[0, 0.03], [s * 0.026, 0.035], [s * 0.05, -0.03], [s * 0.008, -0.058]].map(([x, y]) => [x, y] as [number, number]), v(s * 0.012, sy - 0.006, neckFront + 0.004), ink(COLLAR, PLATE.under), B.chest, { depth: 0.005, bend: 0.1 });
  }

  // sleeves rolled to the elbow, bare forearms
  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, shirt, [[0, 0.054], [0.45, 0.049], [0.97, 0.047]]);
    cuff(b, side, ink(COLLAR, PLATE.under), 0.97, 0.052, 0.05);
    sleeve(b, side, skin2, [[0.95, 0.034], [1.5, 0.031], [1.98, 0.025]], { capStart: false });
    hand(b, side, skin2, 1);
  }

  // trousers and shoes
  pelvis(b, ink(TROUSERS, PLATE.bottom), { waist: hip + 0.13, rx: 0.13, rz: 0.098 });
  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(TROUSERS, PLATE.bottom), { top: 0.074, thigh: 0.07, knee: 0.054, calf: 0.051, hem: 0.048 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.044, height: 0.068 });
  }

  // the apron: a long wrap over the front and sides, open at the back
  skirt(b, apron, { top: hip + 0.15, hem: J.knee.L.y - 0.1, rxTop: 0.13, rzTop: 0.1, rxHem: 0.165, rzHem: 0.125, gap: [Math.PI * 0.64, Math.PI * 1.36], follow: 0.7 });
  // its bib, bent round the chest, and the straps over the shoulders
  const bibTop = ch + 0.07;
  const bibBottom = hip + 0.14;
  const bibZ = 0.104;
  patch(b, [[-0.115, bibBottom - ch], [0.115, bibBottom - ch], [0.1, bibTop - ch], [-0.1, bibTop - ch]], v(0, ch, bibZ), apron, torsoBind(J), { depth: 0.008, bend: 0.17 });
  for (const s of [-1, 1]) {
    const strap = [v(s * 0.092, bibTop - 0.004, bibZ + 0.006), v(s * 0.1, sy - 0.02, 0.075), v(s * 0.104, sy + 0.012, 0.0), v(s * 0.096, sy - 0.03, -0.085), v(s * 0.08, ch, -0.104)];
    S.tube(strap, 0.0085, apron, torsoBind(J), { seg: 6, square: 3 });
    button(b, v(s * 0.092, bibTop - 0.012, bibZ + 0.009), 0.011, ink(BRASS, PLATE.prop), B.chest);
  }

  // the hair: cropped, swept up and back, higher over her left brow
  const hairInk = ink(HAIR, PLATE.hair);
  hairCap(S, head, hc, {
    edge: round([
      [0, -43],
      [-0.42, -40],
      [-0.78, -36],
      [-1.15, -27],
      [-1.42, -15],
      [-1.75, -4],
      [-2.3, 8],
      [Math.PI, 12],
      [2.3, 8],
      [1.75, -4],
      [1.42, -17],
      [1.12, -32],
      [0.75, -43],
      [0.38, -48],
    ]),
    thick: (th, u) => {
      const lift = 0.011 + 0.05 * Math.pow(u, 0.55);
      // fuller over the swept side and the back of the crown
      return lift * (1 + 0.3 * Math.max(0, Math.sin(th)) + 0.25 * Math.max(0, -Math.cos(th)) * u);
    },
    ink: hairInk,
    bind: B.head,
  });
  // the three tufts, flicking up and over to her left (the drawing's flames)
  const lat = (y: number) => head.latOf(y);
  const tufts: Array<[number, number, number, Vector3, number]> = [
    // latitude, angle round the head, base width, direction, length
    [lat(-72), 0.1, 0.05, v(0.55, 1, -0.3), 0.12],
    [lat(-56), 0.95, 0.042, v(1, 0.55, -0.25), 0.095],
    [lat(-58), -0.62, 0.036, v(-0.1, 1, -0.4), 0.08],
    [lat(-50), -1.25, 0.03, v(-1, 0.25, -0.3), 0.06],
    [lat(-30), 2.6, 0.034, v(0.2, -0.3, -1), 0.06],
    [lat(-30), -2.6, 0.034, v(-0.2, -0.3, -1), 0.06],
  ];
  for (const [la, th, w, dir, len] of tufts) {
    const base = onHead(head, hc, la, th, 0.03);
    const d = dir.clone().normalize();
    const bend = v(d.x > 0 ? 1 : 0.3, -0.35, 0).normalize();
    const p1 = base.clone().addScaledVector(d, len * 0.45);
    const p2 = base.clone().addScaledVector(d, len * 0.8).addScaledVector(bend, len * 0.18);
    const p3 = base.clone().addScaledVector(d, len * 0.95).addScaledVector(bend, len * 0.42);
    flick(S, [base.clone().addScaledVector(d, -0.02), base, p1, p2, p3], [w * 0.9, w, w * 0.78, w * 0.45, w * 0.12], hairInk, B.head, { flat: 0.55, up: v(0, 0, 1) });
  }

  // gold hoops in the lobes
  for (const [ex, ey] of [[-42, 15], [43, 15]] as const) {
    const side = ex < 0 ? -1 : 1;
    const p = head.at(ex - side * 1.5, ey, 0).add(hc);
    p.z = hc.z + -head.width(ey) * 0.1 * head.s;
    const r = 4.8 * head.s;
    const ring: Vector3[] = [];
    for (let i = 0; i < 14; i++) {
      const a = (i / 14) * Math.PI * 2;
      ring.push(p.clone().add(v(side * 0.004, -r + Math.cos(a) * r, Math.sin(a) * r)));
    }
    S.tube(ring, 0.0028, ink(BRASS, PLATE.prop), B.head, { seg: 5, closed: true });
  }

  // the glass, held up in her right hand (upright once the forearm is raised)
  const palmR = J.palm.R.clone().add(v(0.004, 0.006, 0.022));
  const up = new Quaternion().setFromAxisAngle(v(1, 0, 0), Math.PI / 2);
  const glass = ink(CREAM, PLATE.prop);
  S.at(palmR, up, () => {
    const m = new Matrix4();
    // foot, stem, bowl (the stem in the fist)
    S.lathe([[0, -0.072], [0.032, -0.07], [0.03, -0.064], [0.006, -0.06], [0.0045, -0.03], [0.0045, 0.012], [0.008, 0.02], [0.03, 0.034], [0.038, 0.06], [0.037, 0.09], [0.033, 0.098]], 14, m, glass, B.handR);
    // the blue gleam in the bowl
    S.lathe([[0.0385, 0.05], [0.0392, 0.062], [0.038, 0.08]], 14, new Matrix4().makeRotationY(-0.3), ink(GLASS_BLUE, PLATE.prop), B.handR);
  });

  // the towel over her left shoulder, down the front and the back: cream with two red stripes
  const x = 0.098;
  const across = (y: number) => {
    const band = bandAt(bands, y);
    return band.rz * Math.sqrt(Math.max(0, 1 - (x / band.rx) ** 2)) + 0.007;
  };
  const path = [
    v(x, sy - 0.2, frontZ(bands, x, sy - 0.2) + 0.008),
    v(x, sy - 0.1, frontZ(bands, x, sy - 0.1) + 0.008),
    v(x, sy - 0.01, across(sy - 0.01) * 0.92),
    v(x, sy + 0.03, 0.02),
    v(x, sy + 0.032, -0.02),
    v(x, sy - 0.01, -across(sy - 0.01) * 0.95),
    v(x, sy - 0.1, -across(sy - 0.1)),
    v(x, sy - 0.18, -across(sy - 0.18)),
  ];
  S.tube(path, [0.046, 0.0045], ink(CREAM, PLATE.prop), B.chest, { seg: 8, up: v(0, 0, 1) });
  // the stripes, standing just off it along its length
  for (const dx of [-0.02, 0.016]) {
    const stripe = path.map((p, i) => {
      const a = path[Math.max(0, i - 1)];
      const c = path[Math.min(path.length - 1, i + 1)];
      const t = c.clone().sub(a).normalize();
      return p.clone().add(v(dx, -t.z * 0.004, t.y * 0.004));
    });
    S.tube(stripe, [0.0065, 0.0022], ink(RED, PLATE.under), B.chest, { seg: 6, up: v(0, 0, 1) });
  }
}

export const margaux: Person = {
  key: 'margaux_barman',
  name: 'Margaux',
  skin: SKIN,
  body: { height: 1.63, head: 0.4, neck: 0.075, shoulders: 0.155, hips: 0.074, legs: 0.4, arm: 0.33, hand: 0.12, foot: 0.2 },
  head: {
    outline: 'M-40,-30 C-40,-62 -22,-70 0,-70 C24,-70 42,-62 42,-30 L42,8 C42,36 22,58 2,58 C-18,58 -40,36 -40,8 Z',
    nose: 'M1,-4 C5,-2 10,12 8,17 C6,21 -2,21 -3,17 C-4,12 -2,-2 1,-4 Z',
    ears: [
      [-41, 0, 7.5, 11],
      [42, 0, 7.5, 11],
    ],
  },
  look: {
    skin: '#cf946a',
    brow: '#6e675b',
    browWidth: 5,
    lidLine: 2.4,
    arcLine: 4.2,
    mouth: [-3.4, 4.8, 1.7],
    nose: { d: 'M1,-4 C5,-2 10,12 8,17 C6,21 -2,21 -3,17 C-4,12 -2,-2 1,-4 Z', fill: '#a96f47', opacity: 0.5 },
    under: [{ d: 'M-30,-4 L-35,-7 M-30,2 L-35,3 M31,-4 L36,-7 M31,2 L36,3 M-32,12 Q-27,20 -21,23 M33,12 Q28,20 22,23', stroke: '#a96f47', width: 2 }],
    fx: { cheekL: [-24, 14], cheekR: [25, 14], temple: [34, -26], eyeL: [-16, -6], eyeR: [16, -6] },
    frame: [1, -6, 64],
  },
  face: () => vivantFace(fig),
  eyes: [
    [-16, -6],
    [16, -6],
  ],
  build,
  manner: {
    rest: {
      armR: [-0.22, 0, 0.08],
      foreR: [-1.78, 0.32, 0],
      handR: [0.2, 0, 0.05],
      armL: [0.03, 0, -0.02],
      foreL: [-0.14, 0, 0],
    },
    energy: 0.7,
  },
};
