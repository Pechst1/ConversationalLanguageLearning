/**
 * Odile Ferrand, in the round.
 *
 * From her rig: small, a round face with its laughter lines and rosy cheeks under the white bob
 * and its straight fringe; the moss cardigan with its gold buttons over a white collar, the
 * taupe skirt, grey stockings and black shoes. Her instant camera is in both hands, its rainbow
 * stripe at the side, its strap round her neck.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import { odile as rig } from '@/components/cast/rigs/odile';
import { ellipse } from '@/components/cast/rig-kit';

import { rigFace } from '../face';
import { hairCap, hairFall, onHead, round } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, button, frontZ, hand, ink, leg, neck, onFront, pelvis, rounded, shoe, skirt, sleeve, trunk } from '../kit';
import type { Person } from '../model';
import type { Pose } from '../pose';
import { B, posed } from '../rig';
import { between, smooth } from '../sculpt';

const SKIN = 0xecbfa0;
const HAIR = 0xe9e4d8;
const STRAND = 0xc9c2b2;
const CARDIGAN = 0x5d6e35;
const SEAM = 0x47552a;
const COLLAR = 0xf8f3e8;
const GOLD = 0xc49a0a;
const SKIRT = 0x6f6857;
const STOCKINGS = 0xa59e8f;
const SHOES = 0x14110d;
const CREAM = 0xf8f3e8;
const BLACK = 0x14110d;
const LENS = 0x3d3832;
const RED = 0xd8321a;
const YELLOW = 0xf3c318;
const BLUE = 0x1d3a8a;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

const NOSE = 'M0,2 C5,2 7,9 5,12 C3,15 -3,15 -5,12 C-7,9 -5,2 0,2 Z';

/** A little stooped, the camera held in front of her in both hands. */
const REST: Pose = {
  chest: [0.08, 0, 0],
  head: [-0.06, 0, 0],
  armR: [0.28, 0.36, 0.08],
  foreR: [-1.4, 0, 0],
  armL: [0.28, -0.36, -0.08],
  foreL: [-1.4, 0, 0],
};

function build(b: Build) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const knit = ink(CARDIGAN, PLATE.top);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;

  neck(b, skin2, 0.036);

  // the cardigan, soft and a little round
  const cardigan: Band[] = [
    { y: hip - 0.03, rx: 0.15, rz: 0.11, square: 2.2 },
    { y: hip + 0.06, rx: 0.148, rz: 0.112 },
    { y: hip + 0.15, rx: 0.14, rz: 0.108, front: 0.014 },
    { y: ch - 0.02, rx: 0.136, rz: 0.104, front: 0.016 },
    { y: ch + 0.06, rx: 0.138, rz: 0.096 },
    { y: sy - 0.04, rx: 0.134, rz: 0.085, square: 2.3 },
    { y: sy - 0.004, rx: 0.1, rz: 0.068, square: 2.2 },
    { y: sy + 0.02, rx: 0.048, rz: 0.044 },
  ];
  trunk(b, cardigan, knit);
  // the white collar in the V, the cardigan's front edge and its buttons
  onFront(b, cardigan, [[-0.034, sy + 0.014], [0.034, sy + 0.014], [0, sy - 0.05]], ink(COLLAR, PLATE.skin2), { lift: 0.002 });
  onFront(b, cardigan, [[-0.002, sy - 0.05], [0.004, sy - 0.05], [0.004, hip - 0.03], [-0.002, hip - 0.03]], ink(SEAM, PLATE.top), { lift: 0.002, depth: 0.003 });
  for (const y of [sy - 0.09, hip + 0.02]) button(b, v(0.012, y, frontZ(cardigan, 0.012, y) + 0.004), 0.008, ink(GOLD, PLATE.prop), B.spine);

  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, knit, [[0, 0.05], [0.45, 0.046], [1, 0.044], [1.9, 0.04]], { capEnd: true });
    hand(b, side, skin2, 0.92);
  }

  // the skirt to below the knee, grey stockings, black shoes
  pelvis(b, ink(SKIRT, PLATE.bottom), { waist: hip + 0.02, rx: 0.12, rz: 0.09 });
  skirt(b, ink(SKIRT, PLATE.bottom), { top: hip + 0.02, hem: J.knee.L.y - 0.07, rxTop: 0.13, rzTop: 0.1, rxHem: 0.16, rzHem: 0.125, follow: 0.5 });
  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(STOCKINGS, PLATE.under), { top: 0.06, thigh: 0.056, knee: 0.046, calf: 0.045, hem: 0.036 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.04, height: 0.054 });
  }

  // the white bob: the cap with its straight fringe, the sides and back to the jaw
  const hairA = ink(HAIR, PLATE.hair);
  const edge = round([[0, -28], [0.6, -28], [1.0, -27], [1.25, -18], [Math.PI / 2, 0], [2.2, 14], [Math.PI, 20], [-2.2, 14], [-Math.PI / 2, 0], [-1.25, -18], [-1.0, -27], [-0.6, -28]]);
  const capThick = (_th: number, u: number) => 0.007 + 0.036 * Math.pow(u, 0.5);
  hairCap(S, head, hc, { edge, thick: capThick, ink: hairA, bind: B.head });
  const jaw = hc.y + (head.y0 - 26) * head.s;
  hairFall(S, head, hc, {
    top: -30,
    open: 1.22,
    end: (th) => jaw + 0.012 * smooth(1.3, Math.PI, Math.abs(((th + Math.PI) % (Math.PI * 2)) - Math.PI)),
    thick: (th) => 0.03 + 0.008 * smooth(1.4, Math.PI, Math.abs(((th + Math.PI) % (Math.PI * 2)) - Math.PI)),
    lift: 0.012,
    flare: -0.006,
    ink: hairA,
    bind: (p) => between(B.head, B.neck, smooth(jaw + 0.04, jaw - 0.02, p.y) * 0.4),
  });
  // the strands of the fringe and the sides
  const strand = ink(STRAND, PLATE.under);
  for (const [th, reach] of [[-0.62, 0.3], [-0.3, 0.42], [0.02, 0.46], [0.32, 0.42], [0.62, 0.3]] as const) {
    const e0 = head.latOf(edge(th));
    const pts: Vector3[] = [];
    for (const u of [0.03, reach / 2, reach]) pts.push(onHead(head, hc, e0 + (Math.PI / 2 - e0) * u, th, capThick(th, u) + 0.0015));
    S.tube(pts, 0.0018, strand, B.head, { seg: 4 });
  }

  // the instant camera, between her hands, its strap round her neck
  const R = posed(J, REST);
  const palmR = J.palm.R.clone().applyMatrix4(R.handR);
  const palmL = J.palm.L.clone().applyMatrix4(R.handL);
  const at = palmR.clone().lerp(palmL, 0.5).add(v(0, 0.006, 0.01));
  S.push(R.handR.clone().invert().multiply(new Matrix4().makeTranslation(at.x, at.y, at.z)));
  const W = 0.122;
  const H = 0.1;
  const D = 0.086;
  S.slab(rounded(W, H, 0.012), D, new Matrix4(), ink(CREAM, PLATE.prop), B.handR);
  S.slab(rounded(W + 0.002, 0.03, 0.01), D + 0.002, new Matrix4().makeTranslation(0, H / 2 - 0.014, 0), ink(BLACK, PLATE.under), B.handR);
  S.box(v(-W / 2 + 0.022, H / 2 - 0.014, D / 2 + 0.002), v(0.022, 0.014, 0.002), ink(CREAM, PLATE.prop), B.handR);
  const lens = new Matrix4().makeRotationX(Math.PI / 2).setPosition(-0.004, -0.012, D / 2);
  S.lathe([[0, 0.016], [0.028, 0.016], [0.029, 0.004], [0.028, 0]], 14, lens, ink(BLACK, PLATE.under), B.handR, { flat: true });
  S.lathe([[0, 0.0175], [0.016, 0.0175], [0.016, 0.014]], 12, lens, ink(LENS, PLATE.skin), B.handR, { flat: true });
  S.ball(v(-0.009, -0.007, D / 2 + 0.018), 0.004, ink(CREAM, PLATE.hair), B.handR, { seg: 6, rings: 4 });
  [RED, YELLOW, BLUE].forEach((c, i) => {
    S.box(v(W / 2 - 0.03 + i * 0.009, -0.016, D / 2 + 0.0015), v(0.0085, 0.05, 0.002), ink(c, i % 2 ? PLATE.shoes : PLATE.bottom), B.handR);
  });
  const strapR = S.world(v(-W / 2 + 0.008, H / 2 - 0.01, -0.01));
  const strapL = S.world(v(W / 2 - 0.008, H / 2 - 0.01, -0.01));
  S.pop();
  for (const [end, s] of [[strapR, -1], [strapL, 1]] as const) {
    const neckAt = v(s * 0.042, sy + 0.016, -0.008);
    const mid = v(s * 0.06, sy - 0.07, frontZ(cardigan, s * 0.06, sy - 0.07) + 0.006);
    S.tube([end, end.clone().lerp(mid, 0.5), mid, neckAt], 0.0026, ink(BLACK, PLATE.prop), [B.handR, [B.handR, B.chest, 0.6], B.chest, B.chest], { seg: 5 });
  }
}

export const odile: Person = {
  key: 'odile_ferrand',
  name: 'Odile',
  skin: SKIN,
  body: { height: 1.5, head: 0.34, neck: 0.05, shoulders: 0.135, hips: 0.075, legs: 0.38, arm: 0.32, hand: 0.105, foot: 0.19 },
  head: {
    outline: 'M-40,-16 C-40,-48 -22,-56 0,-56 C22,-56 40,-48 40,-16 C40,18 24,44 0,46 C-24,44 -40,18 -40,-16 Z',
    nose: NOSE,
    noseDepth: 0.7,
    ears: [],
    chin: 10,
    front: 0.88,
  },
  look: {
    skin: '#ecbfa0',
    brow: '#a59e8f',
    browWidth: 3.6,
    lidLine: 2.4,
    arcLine: 4.4,
    mouth: [-3.6, 1.2, 1.8],
    nose: { d: NOSE, fill: '#c9937a', opacity: 0.5 },
    under: [
      { d: `${ellipse(-24, 14, 7, 4)} ${ellipse(24, 14, 7, 4)}`, fill: '#e9a48a' },
      {
        d: 'M-28,-8 L-34,-12 M-28,-3 L-35,-3 M-28,2 L-34,6 M28,-8 L34,-12 M28,-3 L35,-3 M28,2 L34,6 M-22,9 Q-15,13 -8,9 M8,9 Q15,13 22,9',
        stroke: '#c9937a',
        width: 1.8,
      },
    ],
    fx: { cheekL: [-24, 14], cheekR: [24, 14], temple: [30, -30], eyeL: [-15, -6], eyeR: [15, -6] },
    frame: [0, -4, 58],
  },
  face: () => rigFace(rig),
  eyes: [
    [-15, -6],
    [15, -6],
  ],
  build,
  manner: { rest: REST, energy: 1.25 },
};
