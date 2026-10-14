/* La troupe vivante · Lila Bonnet, l'artiste.
 *
 * Acting sheet. Fast, bouncy, elastic: every move overshoots and springs back, and the hands never
 * stop talking. The sideways glance is her resting face; she thinks with her cheek in her hand
 * and greets with both hands up (model sheet); «Bof» is the eye-roll with the arms crossed (model
 * sheet, portrait); she laughs with a wink (portrait). The red pencil never leaves her hand, the
 * thumb is ochre with paint, and everything gets a grade, on a napkin if need be. Marseille:
 * «Fan de chichourle !»
 *
 * The drawing is the rig's (`../../rigs/lila.tsx`), line for line. The sleeves need no cut: the
 * rig already draws each arm as a yellow sleeve and a bare forearm meeting at the elbow, so the
 * joints sit exactly where the strokes join. The pencil and the ochre thumb are part of her left
 * hand; when that hand opens or makes a fist the pencil goes behind her ear, and the ochre moves
 * to the kit hand's thumb. The hoops and the bow of the headband swing on their own. */
import React from 'react';
import { INK, circles, curlSpirals, dots } from '../../rig-kit';
import { lila as rig } from '../../rigs/lila';
import type { Brow } from '../../rig-kit';
import type { ArmDef, ExpressionDef, FaceDef, FaceValues, FigureDef, GestureDef, GestureId, ExpressionId, HandShape, Key, Pt, Side, VEye } from '../kit';
import { ArmLayer, Blink, Body, Faces, HandShapes, Head, LowerLid, Mouths, Part, Place, RestHand, Shown, Sway } from '../parts';

const SKIN = '#c98a62';
const SHADE = '#a5683f';
const SHIRT = '#f3c318';
const OCHRE = '#c49a0a';
const HAIR = '#2a1a12';
const RED = '#d8321a';
const PAPER = '#f8f3e8';

const BACK = [[-42, -30, 13], [-47, -8, 12], [-44, 14, 11], [-40, 32, 9], [-46, 44, 6.5], [42, -30, 13], [47, -8, 12], [44, 14, 11], [40, 32, 9], [46, 44, 6.5], [-28, -48, 14], [28, -48, 14], [-10, -56, 14], [10, -56, 14]] as const;
const FRONT = [[-34, -36, 9], [34, -36, 9], [-21, -46, 8.5], [21, -46, 8.5], [-40, -20, 7], [40, -20, 7], [-6, -51, 7], [8, -51, 7]] as const;
const BUN = [[0, -82, 20], [-15, -74, 13], [15, -74, 13], [-7, -94, 11], [9, -95, 11]] as const;
const FRECKLES = [[-24, 8], [-28, 12], [-20, 13], [-31, 5], [-25, 16], [24, 8], [28, 12], [20, 13], [31, 5], [25, 16], [-5, 3], [5, 3]] as const;
const CURLS_BACK = circles(BACK);
const CURLS_FRONT = circles(FRONT);
const BUN_D = circles(BUN);
const CURL_LINES = curlSpirals([...BACK, ...FRONT, ...BUN]);
const FRECKLE_D = dots(FRECKLES, 1.3);

const ARMS: Record<Side, ArmDef> = {
  L: { shoulder: [80, 262], elbow: [70, 298], palm: [82, 270], r: 7 },
  R: { shoulder: [120, 262], elbow: [134, 296], palm: [120, 306], r: 7 },
};

// the rig's mood brows
const B = {
  neutre: [[-26, -21, -16, -25, -7, -22], [7, -24, 16, -30, 26, -26]] as [Brow, Brow],
  ravie: [[-26, -25, -16, -31, -7, -27], [7, -27, 16, -32, 26, -26]] as [Brow, Brow],
  surprise: [[-26, -28, -16, -35, -7, -31], [7, -31, 16, -35, 26, -28]] as [Brow, Brow],
  fachee: [[-26, -25, -16, -23, -7, -17], [7, -17, 16, -23, 26, -25]] as [Brow, Brow],
  emue: [[-26, -18, -16, -21, -7, -26], [7, -26, 16, -21, 26, -18]] as [Brow, Brow],
};

const EXPRESSIONS: Record<ExpressionId, ExpressionDef> = {
  neutre: { label: 'Neutre', note: 'le visage du rig : le coup d’œil de côté', eyes: ['wry', 'wry'], brows: B.neutre, mouth: 'smirk', tilt: 6 },
  joie: {
    label: 'Rieuse',
    note: 'un clin d’œil et le grand rire (portrait)',
    eyes: ['open', 'squeeze'],
    brows: [[-26, -26, -16, -32, -7, -28], [7, -24, 16, -28, 26, -23]],
    mouth: 'laugh',
    tilt: -4,
    dy: -2,
    gaze: [0.5, 0],
  },
  malice: {
    label: 'Déduction',
    note: 'un sourcil en l’air, l’index levé : elle a compris',
    eyes: ['level', 'wry'],
    brows: [[-26, -20, -16, -21, -7, -19], [7, -30, 16, -38, 26, -33]],
    mouth: 'smirk',
    tilt: 9,
    dx: 1,
    gaze: [4, 0],
    pose: { at: 0, R: { to: [150, 230], reach: 1.15, tuck: false, h: -6 } },
    hands: { R: 'point' },
    front: ['R'],
  },
  fier: {
    label: 'Vingt sur vingt',
    note: 'les poings sur les hanches, le menton haut, les yeux fermés',
    eyes: ['shut', 'shut'],
    brows: [[-26, -27, -16, -33, -7, -29], [7, -29, 16, -34, 26, -28]],
    mouth: 'grin',
    tilt: -7,
    dy: -3,
    fx: ['sparkle'],
    pose: { at: 0, L: { to: [72, 312], tuck: false, h: 150 }, R: { to: [129, 312], reach: 1.15, tuck: false, h: -150 }, bodyY: -1 },
    hands: { L: 'fist', R: 'fist' },
    show: ['earpencil'],
  },
  surprise: {
    label: 'Fan de chichourle !',
    note: 'les yeux ronds, les mains qui sautent en l’air',
    eyes: ['wide', 'wide'],
    brows: [[-26, -30, -16, -38, -7, -33], [7, -33, 16, -38, 26, -30]],
    mouth: 'shout',
    dy: -3,
    fx: ['shock'],
    pose: { at: 0, L: { to: [38, 256], tuck: false, h: -46 }, R: { to: [162, 256], reach: 1.25, tuck: false, h: 46 }, bodyY: -2 },
    hands: { L: 'open', R: 'open' },
    show: ['earpencil'],
    front: ['L', 'R'],
  },
  panique: {
    label: 'Oh non',
    note: 'les mains sur les joues, les pupilles minuscules',
    eyes: ['tiny', 'tiny'],
    brows: [[-26, -24, -16, -30, -7, -34], [7, -34, 16, -30, 26, -24]],
    mouth: 'tremble',
    tilt: 0,
    fx: ['sweat'],
    pose: { at: 0, L: { to: [60, 214], tuck: false, h: 8 }, R: { to: [140, 214], reach: 1.15, tuck: false, h: -8 } },
    hands: { L: 'flat', R: 'flat' },
    show: ['earpencil'],
    front: ['L', 'R'],
  },
  fache: {
    label: 'Bof',
    note: 'les yeux au ciel, les bras croisés (portrait)',
    eyes: ['roll', 'roll'],
    brows: [[-26, -24, -16, -27, -7, -24], [7, -26, 16, -31, 26, -28]],
    mouth: 'side',
    tilt: -5,
    gaze: [3, 0],
    pose: { at: 0, L: { to: [111, 283], h: 80 }, R: { to: [87, 279], h: -80 }, head: -2 },
    hands: { L: 'fist' },
    show: ['earpencil'],
    front: ['R'],
  },
  emu: {
    label: 'Touchée',
    note: 'le regard de côté, les yeux brillants, la main sur le cœur',
    eyes: ['sad', 'sad'],
    brows: B.emue,
    mouth: 'soft',
    tilt: 4,
    gaze: [4, 0.5],
    fx: ['blush'],
    pose: { at: 0, R: { to: [110, 280], reach: 1.3, tuck: false, h: -40 } },
    hands: { R: 'flat' },
  },
  amour: {
    label: 'Coup de cœur',
    note: 'les yeux qui brillent, les mains jointes',
    eyes: ['sparkle', 'sparkle'],
    brows: B.ravie,
    mouth: 'smileOpen',
    tilt: -3,
    gaze: [0, 0],
    fx: ['hearts', 'blush'],
    pose: { at: 0, L: { to: [95, 282], h: 20 }, R: { to: [105, 282], reach: 1.3, tuck: false, h: -20 } },
    hands: { L: 'fist', R: 'fist' },
    show: ['earpencil'],
  },
  fatigue: {
    label: 'Crevée',
    note: 'le bâillement, les yeux plissés, la main devant',
    eyes: ['squeeze', 'squeeze'],
    brows: [[-26, -19, -16, -22, -7, -21], [7, -21, 16, -22, 26, -19]],
    mouth: 'yawn',
    tilt: 9,
    dy: 2,
    fx: ['zzz'],
    pose: { at: 0, R: { to: [121, 230], reach: 1.1, tuck: false, h: -30 } },
    hands: { R: 'flat' },
    front: ['R'],
  },
};

/* Faces whose eyes shine wet. */
const GLASSY = new Set<FaceDef>([EXPRESSIONS.emu]);

/* The pencil's tip from her palm at rest, and the palm that puts the tip on `t` with the hand at `h`. */
const TIP: Pt = [16, -30.5];
const tipTo = (t: Pt, h: number): Pt => {
  const a = (h * Math.PI) / 180;
  return [
    Math.round((t[0] - (TIP[0] * Math.cos(a) - TIP[1] * Math.sin(a))) * 10) / 10,
    Math.round((t[1] - (TIP[0] * Math.sin(a) + TIP[1] * Math.cos(a))) * 10) / 10,
  ];
};

/* While her left hand is busy with another shape the pencil sits behind her ear: the same window
 * the kit gives the hand (halfway into its first move, halfway out of its last). */
function earWindow(keys: Key[]): [number, number] {
  const busy = keys.map((k) => Boolean(k.L));
  const first = busy.indexOf(true);
  const last = busy.lastIndexOf(true);
  const from = first > 0 ? (keys[first - 1].at + keys[first].at) / 2 : 0;
  const to = last < keys.length - 1 ? (keys[last].at + keys[last + 1].at) / 2 : 1;
  return [Math.round(from * 100) / 100, Math.round(to * 100) / 100];
}

/* The tick she draws in the air, beside her head: down, then the long stroke up. */
const TICK: [Pt, Pt, Pt] = [[30, 214], [40, 228], [64, 188]];
const TICK_H = -30;

/* Back to rest from a raised hand: a little lift, then the drop. The hand only turns once the rig's
 * own round hand is back (the kit's in-betweens can turn a raised hand a full circle on the way). */
const SNAP = 'cubic-bezier(.6,-.5,.8,.6)';

const SALUT: Key[] = [
  { at: 0, ease: 'cubic-bezier(.3,1.35,.5,1)' },
  { at: 0.14, ease: 'ease-in-out', L: { to: [48, 222], tuck: false, h: -18 }, R: { to: [152, 222], reach: 1.3, tuck: false, h: 18 }, bodyY: -3, head: 3 },
  { at: 0.26, ease: 'ease-in-out', L: { to: [46, 220], tuck: false, h: -34 }, R: { to: [154, 220], reach: 1.3, tuck: false, h: 2 }, bodyY: -1, head: -2 },
  { at: 0.38, ease: 'ease-in-out', L: { to: [48, 222], tuck: false, h: -6 }, R: { to: [152, 222], reach: 1.3, tuck: false, h: 32 }, bodyY: -3, head: 3 },
  { at: 0.5, ease: 'ease-in-out', L: { to: [46, 220], tuck: false, h: -30 }, R: { to: [154, 220], reach: 1.3, tuck: false, h: 4 }, bodyY: -1, head: -1 },
  { at: 0.64, ease: SNAP, L: { to: [48, 222], tuck: false, h: -18 }, R: { to: [152, 222], reach: 1.3, tuck: false, h: 18 }, bodyY: -2, head: 2 },
  { at: 0.84, ease: 'cubic-bezier(.3,1.6,.5,1)', bodyY: 2 },
  { at: 1 },
];

const GESTURES: Record<GestureId, GestureDef> = {
  salut: {
    label: 'Coucou !',
    line: 'Coucou !',
    note: 'les deux mains en l’air qui frétillent, le crayon passe derrière l’oreille',
    seconds: 2.2,
    face: { eyes: ['open', 'open'], brows: B.ravie, mouth: 'smileOpen', gaze: [0, 0] },
    talk: true,
    hands: { L: 'open', R: 'open' },
    front: ['L', 'R'],
    show: { earpencil: earWindow(SALUT) },
    keys: SALUT,
    peak: 1,
  },
  bravo: {
    label: 'Vingt sur vingt !',
    line: 'Vingt sur vingt !',
    note: 'elle trace une coche en l’air avec le crayon rouge',
    seconds: 2.2,
    face: { eyes: ['open', 'open'], brows: B.ravie, mouth: 'smirk', gaze: [-4, -2] },
    then: [0.46, { eyes: ['shut', 'shut'], brows: EXPRESSIONS.fier.brows, mouth: 'grin', fx: ['sparkle'], talk: true }],
    hands: { R: 'open' },
    front: ['L'],
    show: { tick: [0.2, 0.9] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.3,1.3,.5,1)', parts: { tick1: { s: 0 }, tick2: { s: 0 } } },
      { at: 0.16, ease: 'ease-in', L: { to: tipTo(TICK[0], TICK_H), tuck: false, h: TICK_H }, head: -3, parts: { tick1: { s: 0 }, tick2: { s: 0 } } },
      { at: 0.26, ease: 'ease-out', L: { to: tipTo(TICK[1], TICK_H), h: TICK_H }, head: -3, parts: { tick1: { s: 1 }, tick2: { s: 0 } } },
      { at: 0.4, ease: 'ease-in-out', L: { to: tipTo(TICK[2], TICK_H), tuck: false, h: TICK_H }, R: { to: [146, 284], reach: 1.2, tuck: false, h: 36 }, head: -1, parts: { tick2: { s: 1 } } },
      { at: 0.52, ease: 'ease-in-out', L: { to: tipTo(TICK[2], TICK_H), tuck: false, h: TICK_H - 10 }, R: { to: [148, 282], reach: 1.2, tuck: false, h: 48 }, bodyY: -3, head: 4 },
      { at: 0.66, ease: 'ease-in-out', L: { to: tipTo([66, 190], TICK_H), tuck: false, h: TICK_H }, R: { to: [146, 284], reach: 1.2, tuck: false, h: 34 }, bodyY: 0, head: 2 },
      { at: 0.8, ease: 'cubic-bezier(.3,1.4,.5,1)', L: { to: tipTo([66, 190], TICK_H), tuck: false, h: TICK_H - 6 }, R: { to: [147, 283], reach: 1.2, tuck: false, h: 42 }, bodyY: -1, head: 3 },
      { at: 1 },
    ],
    peak: 4,
  },
  oups: {
    label: 'Presque !',
    line: 'Presque !',
    note: 'le pouce et l’index presque collés, un œil plissé',
    seconds: 2.0,
    face: {
      eyes: ['squeeze', 'open'],
      brows: [[-26, -19, -16, -21, -7, -19], [7, -30, 16, -36, 26, -31]],
      mouth: 'teeth',
      gaze: [4, 3],
    },
    talk: true,
    hands: { R: 'pinch' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.3,1.4,.5,1)' },
      { at: 0.14, ease: 'ease-in-out', R: { to: [158, 240], reach: 1.35, tuck: false, h: 4 }, head: 4, body: 1 },
      { at: 0.26, ease: 'ease-in-out', R: { to: [159, 242], reach: 1.35, tuck: false, h: 16 }, head: 5, body: 1 },
      { at: 0.38, ease: 'ease-in-out', R: { to: [158, 240], reach: 1.35, tuck: false, h: 2 }, head: 4, body: 1 },
      { at: 0.5, ease: 'ease-in-out', R: { to: [159, 242], reach: 1.35, tuck: false, h: 14 }, head: 5, body: 1 },
      { at: 0.66, ease: SNAP, R: { to: [158, 240], reach: 1.35, tuck: false, h: 6 }, head: 4, body: 1 },
      { at: 0.86, ease: 'cubic-bezier(.3,1.6,.5,1)', bodyY: 1.5 },
      { at: 1 },
    ],
    peak: 1,
  },
  reflechit: {
    label: 'Hmm…',
    line: 'Hmm…',
    note: 'la joue dans la main, le crayon qui tapote, les yeux en coin',
    seconds: 2.8,
    face: {
      eyes: ['wry', 'open'],
      brows: [[-26, -21, -16, -24, -7, -22], [7, -27, 16, -34, 26, -30]],
      mouth: 'smirk',
      gaze: [4, -3],
    },
    front: ['L'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.3,1.25,.5,1)' },
      { at: 0.16, ease: 'ease-in-out', L: { to: [72, 240], tuck: false, h: -60 }, head: -9, body: -1 },
      { at: 0.34, ease: 'ease-in-out', L: { to: [72, 242], tuck: false, h: -48 }, head: -10, body: -1 },
      { at: 0.44, ease: 'ease-in-out', L: { to: [72, 240], tuck: false, h: -60 }, head: -9, body: -1 },
      { at: 0.54, ease: 'ease-in-out', L: { to: [72, 242], tuck: false, h: -48 }, head: -10, body: -1 },
      { at: 0.78, ease: 'cubic-bezier(.4,0,.5,1.3)', L: { to: [72, 240], tuck: false, h: -60 }, head: -9, body: -1 },
      { at: 1 },
    ],
    peak: 1,
  },
  montre: {
    label: 'Regarde !',
    line: 'Regarde !',
    note: 'elle pointe le crayon, l’autre main ouverte',
    seconds: 2.2,
    face: { eyes: ['open', 'open'], brows: B.ravie, mouth: 'smileOpen', gaze: [-4, -1] },
    talk: true,
    hands: { R: 'open' },
    front: ['L'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.3,1.4,.5,1)' },
      { at: 0.14, ease: 'ease-in-out', L: { to: [36, 244], tuck: false, h: -90 }, R: { to: [134, 270], reach: 1.2, tuck: false, h: 30 }, body: -2, head: -4 },
      { at: 0.26, ease: 'cubic-bezier(.25,1.6,.45,1)', L: { to: [44, 248], tuck: false, h: -84 }, R: { to: [134, 272], reach: 1.2, tuck: false, h: 26 }, body: -1.5, head: -3 },
      { at: 0.38, ease: 'ease-in-out', L: { to: [34, 242], tuck: false, h: -92 }, R: { to: [134, 270], reach: 1.2, tuck: false, h: 32 }, body: -2.5, head: -4 },
      { at: 0.72, ease: 'cubic-bezier(.5,0,.7,1)', L: { to: [36, 244], tuck: false, h: -90 }, R: { to: [134, 271], reach: 1.2, tuck: false, h: 30 }, body: -2, head: -4 },
      { at: 0.86, ease: 'cubic-bezier(.3,1.5,.5,1)', L: { to: [52, 290], tuck: false, h: -20 }, R: { to: [128, 300], tuck: false, h: 10 }, body: 0 },
      { at: 1 },
    ],
    peak: 3,
  },
  signature: {
    label: 'Sept sur vingt.',
    line: 'Sept sur vingt.',
    note: 'elle note la décision sur une serviette en papier, et la montre',
    seconds: 3,
    face: {
      eyes: ['down', 'down'],
      brows: [[-26, -22, -16, -25, -7, -22], [7, -22, 16, -25, 26, -22]],
      mouth: 'pout',
      gaze: [0, 3],
    },
    then: [0.46, {
      eyes: ['level', 'wry'],
      brows: [[-26, -20, -16, -22, -7, -20], [7, -30, 16, -37, 26, -32]],
      mouth: 'side',
      gaze: [3, 0],
      talk: true,
    }],
    front: ['R', 'L'],
    show: { napkin: [0.06, 0.94], grade: [0.36, 0.94] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.25,1.3,.45,1)' },
      { at: 0.12, ease: 'ease-in-out', R: { to: [112, 286], h: 0 }, L: { to: tipTo([110, 266], 20), h: 20 }, head: 6 },
      { at: 0.2, ease: 'ease-in-out', R: { to: [112, 286], h: 0 }, L: { to: tipTo([116, 262], 20), h: 20 }, head: 6 },
      { at: 0.26, ease: 'ease-in-out', R: { to: [112, 286], h: 0 }, L: { to: tipTo([108, 270], 20), h: 20 }, head: 6 },
      { at: 0.32, ease: 'ease-in-out', R: { to: [112, 286], h: 0 }, L: { to: tipTo([118, 266], 20), h: 20 }, head: 6 },
      { at: 0.4, ease: 'cubic-bezier(.3,1.35,.5,1)', R: { to: [112, 286], h: 0 }, L: { to: tipTo([112, 272], 20), h: 20 }, head: 5 },
      { at: 0.52, ease: 'ease-in-out', R: { to: [148, 246], reach: 1.2, tuck: false, h: 0 }, head: -3, body: 1 },
      { at: 0.8, ease: 'cubic-bezier(.4,0,.5,1.3)', R: { to: [148, 248], reach: 1.2, tuck: false, h: 0 }, head: -3, body: 1 },
      { at: 1 },
    ],
    peak: 6,
  },
};

/* The tick, drawn in the air where the pencil passes: each stroke grows from its start. */
function Tick() {
  const [a, b, c] = TICK;
  return (
    <Shown id="tick">
      <Part id="tick1" at={a}>
        <path d={`M${a[0]},${a[1]} L${b[0]},${b[1]}`} fill="none" stroke={RED} strokeWidth={4.5} strokeLinecap="round" />
      </Part>
      <Part id="tick2" at={b}>
        <path d={`M${b[0]},${b[1]} L${c[0]},${c[1]}`} fill="none" stroke={RED} strokeWidth={4.5} strokeLinecap="round" />
      </Part>
    </Shown>
  );
}

/* The paper napkin, about her right palm, the grade in red pencil. */
function Napkin() {
  const [x, y] = ARMS.R.palm;
  return (
    <Shown id="napkin">
      <g transform={`translate(${x} ${y})`}>
        <path d="M-15,-40 L18,-42 L19,-6 L-14,-4 Z" fill={PAPER} stroke="#d9cfbb" strokeWidth={1} strokeLinejoin="round" />
        <path d="M1.5,-41 L2.5,-5 M-14.5,-22 L18.5,-24" fill="none" stroke="#e6dece" strokeWidth={1} />
        <Shown id="grade">
          <path d="M-11,-31 L-5,-31.5 L-9,-20 M-2.5,-19.5 L1,-32 M3,-29 Q4.5,-32 7,-31.5 Q9.5,-30.5 7.5,-27 L3.5,-21 L9,-21.5 M11.2,-26.2 A2.3,5 0 1 0 15.8,-26.2 A2.3,5 0 1 0 11.2,-26.2 Z M-11,-14 Q2,-17 16,-15" fill="none" stroke={RED} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
        </Shown>
      </g>
    </Shown>
  );
}

/* Where the thumb ends on each of the kit's hands (viewer's right hand, r = 1): the ochre goes there. */
const THUMB: Record<Exclude<HandShape, 'ball'>, Pt> = {
  fist: [-0.78, -0.45],
  thumb: [-0.3, -1.6],
  point: [-0.62, -0.62],
  two: [-0.62, -0.58],
  pinch: [-1.02, -1.2],
  flat: [-1.22, -0.72],
  open: [-1.55, -0.62],
};

function OchreThumbs({ at, r }: { at: Pt; r: number }) {
  return (
    <g transform={`translate(${at[0]} ${at[1]}) scale(-1 1)`}>
      {(Object.keys(THUMB) as Array<keyof typeof THUMB>).map((s) => (
        <g key={s} className={`tv-hand tv-hand--L-${s}`} opacity={0}>
          <ellipse cx={THUMB[s][0] * r} cy={THUMB[s][1] * r} rx={2.6} ry={2} fill={OCHRE} />
        </g>
      ))}
    </g>
  );
}

/* The kit's eye in her colours; a glassy face adds a wet shine over the lower white, in the gaze. */
function Eye({ e, c, glassy }: { e: VEye; c: Pt; glassy: boolean }) {
  const { rx, ry } = rig.eye!;
  const [x, y] = c;
  return (
    <>
      <path display={e.sD} d={e.sclera} fill="#ffffff" />
      <g className="tv-gaze">
        <path display={e.sD} d={e.pupil} fill={INK} />
        <path display={e.sD} d={e.glint} fill="#ffffff" />
        {e.spark ? <path display={e.sD} d={e.spark} fill="#ffffff" /> : null}
        {glassy ? (
          <>
            <path display={e.sD} d={`M${x - rx * 0.86},${y + ry * 0.3} Q${x},${y + ry * 1.2} ${x + rx * 0.86},${y + ry * 0.3} Q${x},${y + ry * 0.78} ${x - rx * 0.86},${y + ry * 0.3} Z`} fill="#bcd6f0" opacity={0.9} />
            <ellipse display={e.sD} cx={x - rx * 0.3} cy={y + ry * 0.42} rx={1.4} ry={1} fill="#ffffff" />
          </>
        ) : null}
      </g>
      <path d={e.lid} fill={SKIN} />
      <path d={e.lidLine} fill="none" stroke={INK} strokeWidth={2.6} strokeLinecap="round" />
      <LowerLid e={e} skin={SKIN} />
      <path d={e.arc} fill="none" stroke={INK} strokeWidth={4.2} strokeLinecap="round" strokeLinejoin="round" />
      <path d={e.tear} fill="#1d3a8a" />
      <Blink e={e} skin={SKIN} />
    </>
  );
}

function Features({ f }: { f: FaceValues }) {
  const glassy = GLASSY.has(f.def);
  return (
    <>
      <Eye e={f.eL} c={rig.eyeL!} glassy={glassy} />
      <Eye e={f.eR} c={rig.eyeR!} glassy={glassy} />
      <path d="M-25,-9 L-30,-13 M25,-9 L30,-13" fill="none" stroke={INK} strokeWidth={2.6} strokeLinecap="round" />
      <path d={f.browL} fill="none" stroke={HAIR} strokeWidth={5.5} strokeLinecap="round" />
      <path d={f.browR} fill="none" stroke={HAIR} strokeWidth={5.5} strokeLinecap="round" />
      <path d="M0,4 C4,4 6,10 4,13 C2,15 -3,15 -4,13 C-6,10 -4,4 0,4 Z" fill={SHADE} />
      <Mouths mouths={f.mouths} transform="translate(-3.8 2) scale(1.9)" />
    </>
  );
}

function Arm({ side, place }: { side: Side; place: 'back' | 'front' }) {
  const a = ARMS[side];
  const L = side === 'L';
  return (
    <Place side={side} place={place}>
      <ArmLayer
        side={side}
        arm={a}
        upper={<path d={L ? 'M80,262 Q62,282 70,298' : 'M120,262 Q140,278 134,296'} fill="none" stroke={SHIRT} strokeWidth={11} strokeLinecap="round" />}
        fore={<path d={L ? 'M70,298 Q74,286 80,274' : 'M134,296 Q128,304 122,306'} fill="none" stroke={SKIN} strokeWidth={9} strokeLinecap="round" />}
        held={L ? undefined : <Napkin />}
        hand={
          L ? (
            <>
              <RestHand side="L">
                <path d="M84,268 L95,246" fill="none" stroke={RED} strokeWidth={4.5} />
                <path d="M93.2,245 L97.8,247.2 L98,239.5 Z" fill={INK} />
                <circle cx="82" cy="270" r="7" fill={SKIN} />
                <ellipse cx="77" cy="268" rx="3" ry="2.2" fill={OCHRE} />
              </RestHand>
              <HandShapes side="L" at={a.palm} r={7} skin={SKIN} shade={SHADE} />
              <OchreThumbs at={a.palm} r={7} />
            </>
          ) : (
            <>
              <RestHand side="R">
                <circle cx="120" cy="306" r="7" fill={SKIN} />
              </RestHand>
              <HandShapes side="R" at={a.palm} r={7} skin={SKIN} shade={SHADE} />
            </>
          )
        }
      />
    </Place>
  );
}

function LilaArt({ faces, base }: { faces: Array<{ id: string; values: FaceValues }>; base: ExpressionId }) {
  return (
    <g>
      <path d="M90,326 L87,390 M110,326 L114,390" fill="none" stroke="#1d3a8a" strokeWidth={14} strokeLinecap="round" />
      <ellipse cx="84" cy="399" rx="12" ry="6.5" fill={RED} />
      <ellipse cx="117" cy="399" rx="12" ry="6.5" fill={RED} />
      <path d="M73,402 L95,402 M106,402 L128,402" fill="none" stroke={PAPER} strokeWidth={2.2} strokeLinecap="round" />
      <Body fig={lila}>
        <path d="M93,234 L107,234 L107,256 L93,256 Z" fill={SKIN} />
        <path d="M78,264 Q78,252 90,252 L110,252 Q122,252 122,264 L126,318 Q126,330 114,330 L86,330 Q74,330 74,318 Z" fill={SHIRT} />
        <path d="M93,252 L100,262 L107,252 Z" fill={SKIN} />
        <path d="M92,252 L84,256 L96,270 L100,262 Z M108,252 L116,256 L104,270 L100,262 Z" fill={OCHRE} />
        <Arm side="R" place="back" />
        <Arm side="L" place="back" />
        <Head fig={lila} base={base}>
          <path d={CURLS_BACK} fill={HAIR} />
          <path d={BUN_D} fill={HAIR} />
          <path d="M-24,-64 Q0,-56 24,-64 L22,-55 Q0,-47 -22,-55 Z" fill={OCHRE} />
          <path d="M-20,-60 Q0,-53 20,-60" fill="none" stroke={SHIRT} strokeWidth={1.6} />
          <Sway at={[22, -61]} deg={5} seconds={1.3}>
            <path d="M18,-58 C22,-44 20,-32 26,-20 L20,-18 C14,-32 14,-46 18,-58 Z" fill="#a7830a" />
            <path d="M22,-62 C28,-80 44,-80 40,-66 C38,-62 30,-60 22,-62 Z M22,-62 C38,-60 46,-48 38,-44 C32,-42 26,-52 22,-62 Z" fill={OCHRE} />
          </Sway>
          <circle cx="22" cy="-61" r="5" fill="#a7830a" />
          <path d="M-42,-14 C-42,-46 -22,-54 0,-54 C22,-54 42,-46 42,-14 C42,16 26,44 0,48 C-26,44 -42,16 -42,-14 Z" fill={SKIN} />
          <path d={CURLS_FRONT} fill={HAIR} />
          <path d={CURL_LINES} fill="none" stroke="#5a3a26" strokeWidth={1.6} strokeLinecap="round" />
          <Shown id="earpencil">
            <path d="M-64,-22 L-41,-8" fill="none" stroke={RED} strokeWidth={4.5} />
            <path d="M-42.2,-6 L-39.8,-10 L-35.4,-4.6 Z" fill={INK} />
          </Shown>
          <Sway at={[-40, 11]} deg={6} seconds={1.1}>
            <circle cx="-40" cy="20" r="9" fill="none" stroke={OCHRE} strokeWidth={3.2} />
          </Sway>
          <Sway at={[40, 11]} deg={6} seconds={1.1} delay={-0.5}>
            <circle cx="40" cy="20" r="9" fill="none" stroke={OCHRE} strokeWidth={3.2} />
          </Sway>
          <path d={FRECKLE_D} fill="#8f5534" />
          <Faces faces={faces} fig={lila}>
            {(f) => <Features f={f} />}
          </Faces>
        </Head>
        <Tick />
        <Arm side="R" place="front" />
        <Arm side="L" place="front" />
      </Body>
    </g>
  );
}

export const lila: FigureDef = {
  key: 'lila',
  name: 'Lila',
  rig,
  arms: ARMS,
  hips: [100, 326],
  neck: [100, 236],
  skin: SKIN,
  shade: SHADE,
  blink: 3.6,
  idle: { kind: 'bounce', seconds: 2.8, amount: 2.6 },
  parts: { tick1: TICK[0], tick2: TICK[1] },
  expressions: EXPRESSIONS,
  gestures: GESTURES,
  fx: { cheekL: [-25, 12], cheekR: [25, 12], temple: [34, -28], crown: [0, -108], side: [62, -58], eyeL: [-16, -4], eyeR: [16, -4] },
  Art: LilaArt,
};
