/**
 * M. Marchand, le propriétaire, in the round.
 *
 * From his rig: small and stooped, the tall bald dome with its shine and its forehead lines, the
 * white tufts standing out over the ears and the fringe round the back, the round gold glasses,
 * the heavy grey brows; the light grey overcoat with its two gold buttons, the green scarf with its
 * gold stripes and fringe, dark trousers, black shoes. One hand is deep in the coat pocket; the
 * other holds the key ring, the keys hanging.
 */
import { Matrix4, Quaternion, Vector3 } from 'three';

import { marchand as fig } from '@/components/cast/vivant/figures/marchand';
import { ellipse } from '@/components/cast/rig-kit';

import type { FaceState, Mark } from '../face';
import { vivantFace } from '../face';
import { flick, hairFall, onHead } from '../head';
import type { Band, Build } from '../kit';
import { PLATE, button, cuff, frontZ, hand, ink, leg, neck, onFront, pelvis, shoe, sleeve, trunk } from '../kit';
import type { Person } from '../model';
import type { Pose } from '../pose';
import { B, posed } from '../rig';
import { between, smooth } from '../sculpt';

const SKIN = 0xe3a98a;
const COAT = 0xa59e8f;
const COAT_DARK = 0x8a8476;
const COAT_LIGHT = 0xc9c2b2;
const SCARF = 0x2c6a5d;
const GOLD = 0xc49a0a;
const TUFT = 0xece7db;
const TROUSERS = 0x4a4338;
const SHOES = 0x14110d;

const v = (x: number, y: number, z: number) => new Vector3(x, y, z);

const NOSE = 'M3,-8 C9,-2 18,16 14,23 C11,28 -1,27 -2,22 C-3,14 0,-2 3,-8 Z';
const PATE = [
  'M-36,-20 C-38,-62 -18,-76 4,-76 C28,-76 42,-62 40,-20 Q4,-42 -36,-20 Z',
  'M-36,-34 C-35,-64 -16,-76 4,-76 C26,-76 41,-64 40,-34 Q4,-58 -36,-34 Z',
];
const forehead = (dy: number) => `M-16,${-44 + dy} Q2,${-48 + dy} 20,${-44 + dy} M-12,${-36 + dy} Q2,${-39 + dy} 16,${-36 + dy}`;

/** What his faces carry beyond the troupe's own: the flushed pate, the moving forehead, the chin. */
function marks(s: FaceState): Mark[] {
  const look = (fig.expressions[s.expression as keyof typeof fig.expressions] ?? fig.expressions.neutre) as { lines?: number; pate?: string; chin?: boolean };
  const out: Mark[] = [];
  if (look.pate) for (const d of PATE) out.push({ d, fill: look.pate, opacity: 0.3 });
  out.push({ d: ellipse(-6, -60, 10, 4.5), fill: '#f0c3a6' });
  out.push({ d: forehead(look.lines ?? 0), stroke: '#c0846a', width: 2 });
  out.push({ d: 'M-8,24 Q-12,33 -8,41 M20,24 Q24,33 20,41', stroke: '#c0846a', width: 2 });
  if (look.chin) out.push({ d: 'M-1,47 Q4.5,44.6 10,47', stroke: '#c0846a', width: 1.8 });
  return out;
}

/** Stooped, one hand in the coat pocket, the keys hanging from the other. */
const REST: Pose = {
  spine: [0.08, 0, 0],
  chest: [0.2, 0, 0],
  neck: [-0.08, 0, 0],
  head: [-0.14, 0, 0],
  armR: [0.15, 0.4, 0.08],
  foreR: [-0.6, 0, 0],
  armL: [0.04, 0, -0.03],
  foreL: [-0.32, 0, 0],
};

function build(b: Build) {
  const { S, J, head, hc } = b;
  const skin2 = ink(SKIN, PLATE.skin2);
  const coatInk = ink(COAT, PLATE.top);
  const hip = J.hips.y;
  const sy = J.shoulderY;
  const ch = J.chest.y;

  neck(b, skin2, 0.044);

  // the overcoat, sloping from the shoulders over a little belly
  const coat: Band[] = [
    { y: hip - 0.08, rx: 0.168, rz: 0.128, square: 2.2 },
    { y: hip + 0.03, rx: 0.162, rz: 0.126 },
    { y: hip + 0.15, rx: 0.156, rz: 0.124, front: 0.02 },
    { y: ch - 0.02, rx: 0.15, rz: 0.112, front: 0.012 },
    { y: ch + 0.08, rx: 0.152, rz: 0.1 },
    { y: sy - 0.05, rx: 0.146, rz: 0.088, square: 2.3 },
    { y: sy - 0.008, rx: 0.106, rz: 0.07, square: 2.2 },
    { y: sy + 0.02, rx: 0.052, rz: 0.048 },
  ];
  trunk(b, coat, coatInk);
  // where it closes, its two gold buttons, the pocket his hand is in
  onFront(b, coat, [[0.001, sy - 0.1], [0.007, sy - 0.1], [0.009, hip - 0.08], [0.003, hip - 0.08]], ink(COAT_DARK, PLATE.top), { lift: 0.002, depth: 0.003 });
  for (const y of [hip + 0.2, hip + 0.1]) button(b, v(0.012, y, frontZ(coat, 0.012, y) + 0.004), 0.009, ink(GOLD, PLATE.prop), B.spine);
  onFront(b, coat, [[-0.14, hip + 0.04], [-0.07, hip + 0.045], [-0.068, hip + 0.02], [-0.138, hip + 0.014]], ink(COAT_DARK, PLATE.under), { lift: 0.004 });
  // the light catching his left shoulder
  onFront(b, coat, [[0.07, sy + 0.006], [0.135, sy - 0.03], [0.14, sy - 0.07], [0.11, sy - 0.04]], ink(COAT_LIGHT, PLATE.top), { lift: 0.002, depth: 0.003 });

  // the scarf: round the neck, one end down his left side, striped and fringed
  const scarf = ink(SCARF, PLATE.under);
  const loop: Vector3[] = [];
  for (let i = 0; i < 20; i++) {
    const a = (i / 20) * Math.PI * 2;
    loop.push(v(Math.sin(a) * 0.078, sy + 0.006 - Math.cos(a) * 0.012, Math.cos(a) * 0.07 - 0.004));
  }
  S.tube(loop, [0.026, 0.02], scarf, B.chest, { seg: 10, closed: true });
  const x0 = 0.045;
  const x1 = 0.098;
  const yb = sy - 0.2;
  onFront(b, coat, [[x0, sy - 0.01], [x1, sy - 0.02], [x1 + 0.006, yb], [x0 + 0.004, yb + 0.004]], scarf, { lift: 0.008, depth: 0.012 });
  for (const y of [yb + 0.05, yb + 0.03]) onFront(b, coat, [[x0 + 0.003, y + 0.006], [x1 + 0.005, y + 0.005], [x1 + 0.005, y - 0.002], [x0 + 0.003, y - 0.001]], ink(GOLD, PLATE.prop), { lift: 0.0145, depth: 0.003 });
  for (let i = 0; i < 6; i++) {
    const x = x0 + 0.008 + (i / 5) * (x1 - x0 - 0.008);
    const z = frontZ(coat, x, yb) + 0.012;
    S.tube([v(x, yb + 0.004, z), v(x + 0.001, yb - 0.016, z + 0.001)], 0.0028, scarf, B.chest, { seg: 4 });
  }

  // the sleeves to the wrist, a darker turn-up
  for (const side of ['L', 'R'] as const) {
    sleeve(b, side, coatInk, [[0, 0.06], [0.45, 0.054], [1, 0.05], [1.85, 0.047]], { capEnd: false });
    cuff(b, side, ink(COAT_DARK, PLATE.under), 1.86, 0.05, 0.035);
    hand(b, side, skin2, 0.98);
  }

  pelvis(b, ink(TROUSERS, PLATE.bottom), { waist: hip + 0.05, rx: 0.13, rz: 0.1 });
  for (const side of ['L', 'R'] as const) {
    leg(b, side, ink(TROUSERS, PLATE.bottom), { top: 0.076, thigh: 0.072, knee: 0.06, calf: 0.058, hem: 0.057 });
    shoe(b, side, ink(SHOES, PLATE.shoes), { width: 0.047, height: 0.064 });
  }

  // the fringe round the back, then the tufts standing out over the ears
  const tuftA = ink(TUFT, PLATE.hair);
  const tuftB = ink(TUFT, PLATE.prop);
  const nape = hc.y + (head.y0 - 24) * head.s;
  const side = hc.y + (head.y0 - 8) * head.s;
  hairFall(S, head, hc, {
    top: -22,
    open: 1.45,
    end: (th) => side + (nape - side) * smooth(1.5, Math.PI, Math.abs(((th + Math.PI) % (Math.PI * 2)) - Math.PI)),
    thick: () => 0.009,
    lift: 0.001,
    ink: tuftA,
    bind: (p) => between(B.head, B.neck, smooth(hc.y - 0.12, hc.y - 0.2, p.y)),
    rows: 8,
    cols: 30,
  });
  // fluffy round the back, where the fringe meets the tufts
  for (let i = 0; i < 9; i++) {
    const th = 1.9 + ((Math.PI * 2 - 3.8) * i) / 8;
    const y = -12 + (i % 2) * 9;
    const p = onHead(head, hc, head.latOf(y), th, 0.006);
    S.ball(p, (8 + (i % 3)) * head.s, i % 2 ? tuftB : tuftA, B.head, { seg: 10, rings: 6 });
  }
  for (const s of [-1, 1]) {
    const w = head.width(-18);
    const out = (dx: number, y: number, z: number) => head.at(head.x0 + s * (w + dx), y, z).add(hc);
    const balls: Array<[number, number, number, number]> = [
      [8, -22, -0.02, 13],
      [14, -6, -0.03, 10],
      [4, -36, -0.022, 9],
      [2, -10, -0.05, 11],
      [9, 4, -0.024, 8],
    ];
    balls.forEach(([dx, y, z, r], i) => {
      S.ball(out(dx, y, z), v(r * head.s * 0.9, r * head.s, r * head.s * 0.95), i % 2 ? tuftB : tuftA, B.head, { seg: 10, rings: 6 });
    });
    // the spike that stands up from the top of each tuft, and a grey stroke through it
    const base = out(6, -34, -0.022);
    flick(S, [base, out(14, -44, -0.024), out(20, -50, -0.026)], [0.012, 0.008, 0.003], tuftA, B.head, { flat: 0.5, up: v(0, 0, 1) });
    S.tube([out(16, -20, -0.004), out(18, -14, -0.002), out(17, -8, -0.004)], 0.0022, ink(COAT_LIGHT, PLATE.under), B.head, { seg: 4 });
  }

  // the round gold glasses, the bridge over his nose, the arms back to the ears
  const gold = ink(GOLD, PLATE.prop);
  const rimAt: Vector3[] = [];
  for (const [ex, ey] of [[-12, -8], [18, -8]] as const) {
    const c = head.at(ex, ey, head.frontAt(ex, ey) + 0.014).add(hc);
    const yaw = ((ex - head.x0) / head.wide) * 0.55;
    const q = new Quaternion().setFromAxisAngle(v(0, 1, 0), yaw);
    const r = 12 * head.s;
    const ring: Vector3[] = [];
    for (let i = 0; i < 20; i++) {
      const a = (i / 20) * Math.PI * 2;
      ring.push(v(Math.cos(a) * r, Math.sin(a) * r, 0).applyQuaternion(q).add(c));
    }
    S.tube(ring, 0.0026, gold, B.head, { seg: 5, closed: true });
    rimAt.push(c);
  }
  const bridgeL = head.at(0, -9, head.frontAt(0, -9) + 0.016).add(hc);
  const bridgeR = head.at(6, -9, head.frontAt(6, -9) + 0.016).add(hc);
  const bridgeTop = head.at(3, -12, head.frontAt(3, -12) + 0.02).add(hc);
  S.tube([bridgeL, bridgeTop, bridgeR], 0.0024, gold, B.head, { seg: 5 });
  for (const [ex, earX] of [[-24, -37], [30, 40]] as const) {
    const sd = ex < head.x0 ? -1 : 1;
    const front = head.at(ex, -9, head.frontAt(ex, -9) + 0.012).add(hc);
    const ear = head.at(earX, -4, -0.004).add(hc);
    const mid = front.clone().lerp(ear, 0.5).add(v(sd * 0.012, 0, 0));
    S.tube([front, mid, ear], 0.0022, gold, B.head, { seg: 4 });
  }

  // the key ring in his left hand, the keys hanging from it
  const R = posed(J, REST);
  const palm = J.palm.L.clone().applyMatrix4(R.handL);
  S.push(R.handL.clone().invert());
  const ringC = palm.clone().add(v(0.006, -0.05, 0.012));
  const ring: Vector3[] = [];
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2;
    ring.push(ringC.clone().add(v(Math.cos(a) * 0.02, Math.sin(a) * 0.02, 0)));
  }
  S.tube(ring, 0.0028, gold, B.handL, { seg: 5, closed: true });
  const keys: Array<[number, number, number]> = [
    // angle from straight down, length, colour
    [-0.35, 0.075, GOLD],
    [0.05, 0.085, COAT_DARK],
    [0.4, 0.07, GOLD],
  ];
  keys.forEach(([a, len, colour], i) => {
    const top = ringC.clone().add(v(Math.sin(a) * 0.02, -Math.cos(a) * 0.02, 0.002 * i));
    const m = new Matrix4().compose(top, new Quaternion().setFromAxisAngle(v(0, 0, 1), a), v(1, 1, 1));
    S.slab([[-0.0035, 0], [0.0035, 0], [0.0035, -len], [-0.0035, -len]], 0.004, m, ink(colour, i % 2 ? PLATE.under : PLATE.prop), B.handL);
    S.slab([[-0.0035, -len + 0.022], [0.012, -len + 0.022], [0.012, -len + 0.006], [-0.0035, -len + 0.006]], 0.0045, m, ink(GOLD, PLATE.prop), B.handL);
  });
  S.pop();
}

export const marchand: Person = {
  key: 'landlord_marchand',
  name: 'M. Marchand',
  skin: SKIN,
  body: { height: 1.6, head: 0.42, neck: 0.05, shoulders: 0.155, hips: 0.08, legs: 0.37, arm: 0.32, hand: 0.115, foot: 0.22 },
  head: {
    outline: 'M-36,-20 C-38,-62 -18,-76 4,-76 C28,-76 42,-62 40,-20 L40,10 C40,36 26,52 4,54 C-20,52 -36,36 -36,10 Z',
    nose: NOSE,
    noseDepth: 0.8,
    ears: [
      [-37, 4, 9, 14],
      [40, 4, 8, 13],
    ],
    chin: 12,
    back: 1.08,
  },
  look: {
    skin: '#e3a98a',
    brow: '#b5ad9d',
    browWidth: 7,
    lidLine: 2.2,
    arcLine: 3.6,
    mouth: [-1.6, 13.4, 1.6],
    nose: { d: NOSE, fill: '#c0846a', opacity: 0.5 },
    under: marks,
    fx: { cheekL: [-17, 12], cheekR: [26, 12], temple: [22, -58], eyeL: [-12, -8], eyeR: [18, -8] },
    frame: [2, -12, 70],
  },
  face: () => vivantFace(fig),
  eyes: [
    [-12, -8],
    [18, -8],
  ],
  build,
  manner: { rest: REST, energy: 0.6 },
};
