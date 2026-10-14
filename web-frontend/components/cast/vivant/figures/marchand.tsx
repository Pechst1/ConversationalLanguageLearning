/* La troupe vivante · M. Marchand, le propriétaire.
 *
 * Acting sheet. Stiff, small, staccato: a move, a stop, the next move; the keys go on jingling
 * after his hand has stopped. He nods slowly, he never waves. His tells are the heavy key ring in
 * his hand, the glasses he pushes down his nose to peer over the rims (model sheet), the glowing
 * phone (model sheet) and procedure: a registered letter, a rent paid on time («À jour.»), the
 * Ferrand estate that is late. His happy, cross and moved portraits give the small closed smile,
 * the shout with the vein, and the pressed lips of a man holding it in.
 *
 * The drawing is the rig's (`../../rigs/marchand.tsx`), line for line: both sleeves are split at
 * the elbow (each quadratic cut in two at its midpoint), the key ring rides in his right hand
 * hanging upright, each key on its own swing; his other hand stays in the coat pocket and its
 * forearm comes out in front of the coat only for a letter or the phone. The tufts, the glasses
 * and the forehead are drawn with each face, so a face can flare, lower or tint them. */
import React from 'react';
import { marchand as rig } from '../../rigs/marchand';
import type { Brow } from '../../rig-kit';
import type { ArmDef, ArmKey, ExpressionDef, ExpressionId, FaceDef, FaceValues, FigureDef, GestureDef, GestureId, Side, VEye } from '../kit';
import { brows, solveArm } from '../kit';
import { ArmLayer, Body, EyeSet, Faces, HandShapes, Head, Mouths, Part, Place, RestHand, Resting, Shown, Sway } from '../parts';

const SKIN = '#e3a98a';
const SHADE = '#c0846a';
const COAT = '#a59e8f';
const COAT_DARK = '#8a8476';
const COAT_LIGHT = '#c9c2b2';
const SCARF = '#2c6a5d';
const GOLD = '#c49a0a';
const TUFT = '#ece7db';
const BROW = '#b5ad9d';
const INK = '#14110d';
const RED = '#d8321a';

const ARMS: Record<Side, ArmDef> = {
  L: { shoulder: [64, 262], elbow: [60.5, 287], palm: [68.5, 310], r: 8 },
  R: { shoulder: [140, 254], elbow: [153, 280.5], palm: [151, 309], r: 8 },
};

/** What his faces carry beyond the kit's: the glasses down the nose, the tufts, the pate. */
interface Look {
  /** the glasses: slid down (x, y) and turned, then drawn over the nose */
  specs?: [number, number, number];
  /** the tufts flare out, degrees */
  tufts?: number;
  /** the forehead lines move with the brows */
  lines?: number;
  /** a tint on the pate */
  pate?: string;
  /** the chin crumpling under pressed lips */
  chin?: boolean;
}
type Face = FaceDef & Look;
const face = (f: Face): FaceDef => f;

// the rig's mood brows
const B = {
  neutre: [[-22, -23, -12, -27, -3, -24], [8, -24, 18, -28, 28, -23]] as [Brow, Brow],
  ravie: [[-22, -26, -12, -31, -3, -27], [8, -27, 18, -31, 28, -26]] as [Brow, Brow],
  surprise: [[-22, -30, -12, -36, -3, -31], [8, -31, 18, -36, 28, -30]] as [Brow, Brow],
  fachee: [[-22, -27, -12, -25, -3, -19], [8, -19, 18, -25, 28, -27]] as [Brow, Brow],
  emue: [[-22, -20, -12, -23, -3, -28], [8, -28, 18, -23, 28, -20]] as [Brow, Brow],
};

const EXPRESSIONS: Record<ExpressionId, ExpressionDef & Look> = {
  neutre: { label: 'Neutre', note: 'le visage du rig : paupières lourdes, la tête penchée', eyes: ['heavy', 'heavy'], brows: B.neutre, mouth: 'm', tilt: 6 },
  joie: {
    label: 'Satisfait',
    note: 'un petit sourire fermé, les yeux plissés (portrait)',
    eyes: ['happy', 'happy'],
    brows: B.ravie,
    mouth: 'smile',
    tilt: 0,
    dy: -1,
  },
  malice: {
    label: 'Lunettes',
    note: 'les lunettes au bout du nez, il regarde par-dessus',
    eyes: ['open', 'level'],
    brows: [[-22, -25, -12, -27, -3, -23], [8, -31, 18, -37, 28, -32]],
    mouth: 'smirk',
    tilt: 9,
    dy: 2,
    gaze: [0, -3],
    specs: [0, 10, 0],
    lines: -2,
  },
  fier: {
    label: 'En ordre.',
    note: 'le menton haut, les yeux fermés : tout est en ordre',
    eyes: ['shut', 'shut'],
    brows: brows(B.ravie, [2, 2]),
    mouth: 'soft',
    tilt: -4,
    dy: -3,
  },
  surprise: {
    label: 'Pardon ?',
    note: 'les yeux ronds, les touffes qui se dressent',
    eyes: ['wide', 'wide'],
    brows: brows(B.surprise, [2, 2]),
    mouth: 'o',
    tilt: -2,
    dy: -2,
    tufts: 16,
    lines: -5,
    fx: ['question'],
    pose: { at: 0, headY: -3 },
  },
  panique: {
    label: 'En retard !',
    note: 'pupilles en tête d’épingle, lunettes de travers, la goutte sur le crâne',
    eyes: ['tiny', 'tiny'],
    brows: [[-22, -27, -12, -33, -3, -36], [8, -36, 18, -33, 28, -27]],
    mouth: 'tremble',
    tilt: 3,
    specs: [1, 3, -7],
    tufts: 7,
    lines: -3,
    fx: ['sweat'],
  },
  fache: {
    label: 'Outré',
    note: 'il crie, la veine sur le crâne (portrait)',
    eyes: ['cross', 'cross'],
    brows: [[-22, -29, -12, -27, -3, -17], [8, -17, 18, -27, 28, -29]],
    mouth: 'shout',
    tilt: 8,
    dy: 2,
    lines: 2,
    pate: '#e5604a',
    fx: ['vein'],
    pose: { at: 0, R: { to: [165, 240], tuck: false, h: -10 }, head: -2 },
    hands: { R: 'fist' },
    front: ['R'],
  },
  emu: {
    label: 'Ému',
    note: 'les lèvres pincées, il se retient (portrait)',
    eyes: ['sad', 'sad'],
    brows: B.emue,
    mouth: 'tight',
    tilt: 10,
    gaze: [0, -2],
    lines: -1,
    chin: true,
  },
  amour: {
    label: 'Attendri',
    note: 'les yeux fondent, le crâne rosit',
    eyes: ['happy', 'happy'],
    brows: [[-22, -21, -12, -26, -3, -28], [8, -28, 18, -26, 28, -21]],
    mouth: 'soft',
    tilt: 10,
    pate: '#f07f86',
    fx: ['blush'],
  },
  fatigue: {
    label: 'Sieste',
    note: 'les yeux fermés, les lunettes glissent',
    eyes: ['shut', 'shut'],
    brows: [[-22, -21, -12, -23, -3, -21], [8, -21, 18, -23, 28, -21]],
    mouth: 'o',
    tilt: 13,
    dy: 3,
    specs: [1, 7, 8],
    fx: ['zzz'],
    pose: { at: 0, head: 3, headY: 2, bodyY: 1.5 },
  },
};

/* A key held up in the fist: the bow inside the hand, the blade and its bit above it. */
const keyUp = (shaft: string) => (
  <g>
    <path d="M151,304 L151,279" fill="none" stroke={shaft} strokeWidth={3.4} strokeLinecap="round" />
    <path d="M151,279.5 L157.5,279.5 L157.5,284.5 L151,284.5 Z M151,287 L156,287 L156,291 L151,291 Z" fill={GOLD} />
  </g>
);

/**
 * A target solved here into plain angles, which the joints then turn through evenly. For a fist
 * that keeps its key upright, or turns it a quarter, this is the turn it should make: between two
 * IK keys the kit counts the hand's turn from the other side of the circle when the forearm has
 * come up past the horizontal, and the key would spin round.
 */
const angles = (side: Side, k: ArmKey): ArmKey => {
  const a = solveArm(ARMS[side], k);
  return { u: a.u, f: a.f, h: k.h, reach: k.reach };
};

/* The arm raised stiff, the elbow out: an oath more than a wave. */
const OATH = { to: [171, 212] as [number, number], tuck: false, h: 0 };
/* A key held up at his side, then turned a quarter: clac. */
const KEY = angles('R', { to: [168, 240], tuck: false, h: 0 });
const TURNED = { ...KEY, h: 90 };
/* A key held up by his ear, where he can peer at it over the rims. */
const PEER = angles('R', { to: [170, 212], tuck: false, h: 0 });
const PEER_UP = angles('R', { to: [170, 207], tuck: false, h: 0 });
/* On the way down the elbow drops first, then the forearm: two stiff moves. */
const ELBOW_DOWN = { u: 0, f: PEER_UP.f, h: 0 };
/* The letter held to read. */
const READ = { to: [95, 282] as [number, number], h: 6 };
const READ_UP = { to: [97, 276] as [number, number], h: 6 };
/* The phone held out at arm's length, toward you: his eyes need it far. */
const PHONE_AT = { to: [92, 280] as [number, number], h: 0 };
const FAR = { to: [100, 262] as [number, number], reach: 1.3, h: 0 };
/* The registered letter held out toward you. */
const SHOW = { to: [158, 262] as [number, number], reach: 1.18, h: 0 };
const JAB = { to: [160, 257] as [number, number], reach: 1.3, h: 0 };

const GESTURES: Record<GestureId, GestureDef> = {
  salut: {
    label: 'Bonjour.',
    line: 'Bonjour. Marchand, le propriétaire.',
    note: 'la main levée, raide, le coude dehors ; les clés tintent quand elle s’arrête',
    seconds: 3,
    face: face({ eyes: ['level', 'level'], brows: brows(B.neutre, [2, 2]), mouth: 'flat' }),
    talk: true,
    hands: { R: 'flat' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.6,0,.25,1)' },
      { at: 0.12, ease: 'ease-in-out', R: OATH, parts: { keys: { r: -20 } } },
      { at: 0.18, ease: 'ease-in-out', R: OATH, parts: { keys: { r: 13 } } },
      { at: 0.24, ease: 'ease-in-out', R: OATH, parts: { keys: { r: -6 } } },
      { at: 0.3, ease: 'ease-in-out', R: OATH, parts: { keys: { r: 2 } } },
      { at: 0.38, ease: 'ease-in-out', R: OATH, parts: { keys: { r: 0 } } },
      { at: 0.46, ease: 'ease-in-out', R: OATH },
      { at: 0.58, ease: 'ease-in-out', R: OATH, head: 7, headY: 1 },
      { at: 0.69, ease: 'cubic-bezier(.6,0,.3,1)', R: OATH, head: 0 },
      { at: 0.81, ease: 'ease-in-out', parts: { keys: { r: 18 } } },
      { at: 0.87, ease: 'ease-in-out', parts: { keys: { r: -9 } } },
      { at: 0.93, ease: 'ease-in-out', parts: { keys: { r: 4 } } },
      { at: 1 },
    ],
    peak: 5,
  },
  bravo: {
    label: 'À jour.',
    line: 'À jour.',
    note: 'il lève la clé dorée et la tourne dans le vide : clac, puis le hochement lent',
    seconds: 3.2,
    face: face({ eyes: ['level', 'level'], brows: brows(B.neutre, [3, 3]), mouth: 'm', gaze: [3, 1] }),
    then: [0.46, 'fier'],
    hands: { R: 'fist' },
    front: ['R'],
    show: { upL: [0.07, 0.81] },
    hide: { kL: [0.07, 0.81] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.6,0,.25,1)' },
      { at: 0.14, ease: 'ease-in-out', R: KEY, parts: { keys: { r: -16 } } },
      { at: 0.21, ease: 'ease-in-out', R: KEY, parts: { keys: { r: 8 } } },
      { at: 0.28, ease: 'ease-in-out', R: KEY, parts: { keys: { r: -3 } } },
      { at: 0.4, ease: 'cubic-bezier(.75,0,.4,1)', R: KEY, parts: { keys: { r: 0 } } },
      { at: 0.45, ease: 'ease-in-out', R: TURNED, parts: { keys: { r: 10 } } },
      { at: 0.52, ease: 'ease-in-out', R: TURNED, head: 0, parts: { keys: { r: -4 } } },
      { at: 0.64, ease: 'ease-in-out', R: TURNED, head: 7, headY: 1, parts: { keys: { r: 0 } } },
      { at: 0.76, ease: 'cubic-bezier(.6,0,.3,1)', R: TURNED, head: 0 },
      { at: 0.86, ease: 'ease-in-out', parts: { keys: { r: 14 } } },
      { at: 0.93, ease: 'ease-in-out', parts: { keys: { r: -5 } } },
      { at: 1 },
    ],
    peak: 6,
  },
  oups: {
    label: 'Non. Celle-ci.',
    line: 'Non. Celle-ci.',
    note: 'la clé levée à hauteur d’œil, il la regarde par-dessus ses lunettes : non ; la suivante',
    seconds: 3.6,
    face: face({ eyes: ['open', 'open'], brows: [[-22, -25, -12, -28, -3, -24], [8, -28, 18, -34, 28, -30]], mouth: 'flat', gaze: [3, -3] }),
    then: [0.48, face({ eyes: ['open', 'level'], brows: [[-22, -27, -12, -31, -3, -27], [8, -27, 18, -31, 28, -26]], mouth: 'smirk', gaze: [3, -3] })],
    talk: true,
    hands: { R: 'fist' },
    front: ['R'],
    show: { upM: [0.07, 0.44], upL: [0.44, 0.84], specs: [0.15, 0.8] },
    hide: { kM: [0.07, 0.44], kL: [0.44, 0.84] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.6,0,.25,1)' },
      { at: 0.13, ease: 'cubic-bezier(.6,0,.3,1)', R: PEER, head: -2, parts: { keys: { r: -14 } } },
      { at: 0.19, ease: 'ease-in-out', R: PEER, head: -2, headY: 2, parts: { keys: { r: 7 }, glasses: { y: 7 } } },
      { at: 0.26, ease: 'ease-in-out', R: PEER, head: -2, headY: 2, parts: { keys: { r: -2 }, glasses: { y: 7 } } },
      { at: 0.34, ease: 'cubic-bezier(.6,0,.4,1)', R: PEER, head: -2, headY: 2, parts: { keys: { r: 0 }, glasses: { y: 7 } } },
      { at: 0.38, ease: 'cubic-bezier(.6,0,.4,1)', R: PEER, head: -7, headY: 2, parts: { glasses: { y: 7 } } },
      { at: 0.42, ease: 'cubic-bezier(.6,0,.4,1)', R: PEER, head: 3, headY: 2, parts: { glasses: { y: 7 } } },
      { at: 0.46, ease: 'ease-out', R: PEER, head: -2, headY: 2, parts: { keys: { r: 22 }, glasses: { y: 7 } } },
      { at: 0.52, ease: 'ease-in-out', R: PEER_UP, head: -2, headY: 2, parts: { keys: { r: -11 }, glasses: { y: 7 } } },
      { at: 0.58, ease: 'ease-in-out', R: PEER_UP, head: -2, headY: 2, parts: { keys: { r: 5 }, glasses: { y: 7 } } },
      { at: 0.66, ease: 'ease-in-out', R: PEER_UP, head: 4, headY: 3, parts: { keys: { r: 0 }, glasses: { y: 7 } } },
      { at: 0.76, ease: 'cubic-bezier(.6,0,.3,1)', R: PEER_UP, head: 0, headY: 1, parts: { glasses: { y: 7 } } },
      { at: 0.81, ease: 'cubic-bezier(.6,0,.3,1)', R: ELBOW_DOWN, head: 0, parts: { keys: { r: -10 }, glasses: { y: 0 } } },
      { at: 0.87, ease: 'ease-in-out', parts: { keys: { r: 14 } } },
      { at: 0.93, ease: 'ease-in-out', parts: { keys: { r: -5 } } },
      { at: 1 },
    ],
    peak: 4,
  },
  reflechit: {
    label: 'Voyons…',
    line: 'Voyons… La succession Ferrand est en retard.',
    note: 'la lettre sortie de la poche, les lunettes au bout du nez, il relit',
    seconds: 4,
    face: face({ eyes: ['down', 'down'], brows: [[-22, -25, -12, -28, -3, -22], [8, -22, 18, -28, 28, -25]], mouth: 'flat', gaze: [-3, 2] }),
    then: [0.58, face({ eyes: ['down', 'down'], brows: [[-22, -24, -12, -29, -3, -26], [8, -22, 18, -27, 28, -23]], mouth: 'm', gaze: [3, 2] })],
    hands: { L: 'fist' },
    front: ['L'],
    show: { letter: [0.07, 0.9], specs: [0.31, 0.87] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.6,0,.25,1)' },
      { at: 0.13, ease: 'cubic-bezier(.6,0,.3,1)', L: READ },
      { at: 0.22, ease: 'cubic-bezier(.6,0,.3,1)', L: READ },
      { at: 0.28, ease: 'cubic-bezier(.6,0,.3,1)', L: READ, head: 5, headY: 2 },
      { at: 0.33, ease: 'ease-in-out', L: READ, head: 5, headY: 2, parts: { glasses: { y: 10 } } },
      { at: 0.56, ease: 'cubic-bezier(.6,0,.3,1)', L: READ, head: 5, headY: 2, parts: { glasses: { y: 10 } } },
      { at: 0.61, ease: 'ease-in-out', L: READ_UP, head: 6, headY: 2, parts: { glasses: { y: 10 } } },
      { at: 0.8, ease: 'cubic-bezier(.6,0,.3,1)', L: READ_UP, head: 6, headY: 2, parts: { glasses: { y: 10 } } },
      { at: 0.86, ease: 'cubic-bezier(.6,0,.25,1)', L: READ_UP, head: 0, parts: { glasses: { y: 0 } } },
      { at: 0.95 },
      { at: 1 },
    ],
    peak: 5,
  },
  montre: {
    label: 'Recommandé.',
    line: 'Recommandé. Avec accusé de réception.',
    note: 'il te tend la lettre recommandée, deux petits coups secs',
    seconds: 3.2,
    face: face({ eyes: ['level', 'level'], brows: brows(B.neutre, [3, 3]), mouth: 'flat', gaze: [-1, 0] }),
    talk: true,
    hands: { R: 'fist' },
    front: ['R'],
    show: { envelope: [0.07, 0.81] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.6,0,.25,1)' },
      { at: 0.15, ease: 'ease-in-out', R: SHOW, parts: { keys: { r: -12 } } },
      { at: 0.22, ease: 'ease-in-out', R: SHOW, parts: { keys: { r: 6 } } },
      { at: 0.3, ease: 'cubic-bezier(.7,0,.3,1)', R: SHOW, parts: { keys: { r: 0 } } },
      { at: 0.34, ease: 'cubic-bezier(.6,0,.3,1)', R: JAB, head: 4, parts: { keys: { r: 9 } } },
      { at: 0.43, ease: 'cubic-bezier(.7,0,.3,1)', R: SHOW, head: 0, parts: { keys: { r: -4 } } },
      { at: 0.48, ease: 'cubic-bezier(.6,0,.3,1)', R: JAB, head: 4, parts: { keys: { r: 9 } } },
      { at: 0.58, ease: 'ease-in-out', R: SHOW, head: 0, parts: { keys: { r: -3 } } },
      { at: 0.76, ease: 'cubic-bezier(.6,0,.3,1)', R: SHOW, parts: { keys: { r: 0 } } },
      { at: 0.86, ease: 'ease-in-out', parts: { keys: { r: 14 } } },
      { at: 0.93, ease: 'ease-in-out', parts: { keys: { r: -5 } } },
      { at: 1 },
    ],
    peak: 4,
  },
  signature: {
    label: 'Virement reçu.',
    line: 'Virement reçu.',
    note: 'le téléphone à bout de bras, la tête en arrière ; l’écran s’allume, le petit sourire',
    seconds: 3.6,
    face: face({ eyes: ['level', 'squeeze'], brows: [[-22, -25, -12, -29, -3, -26], [8, -22, 18, -24, 28, -21]], mouth: 'flat', gaze: [-2, 2] }),
    then: [0.5, face({ eyes: ['smug', 'smug'], brows: B.ravie, mouth: 'smile', gaze: [-2, 2] })],
    hands: { L: 'fist' },
    front: ['L'],
    show: { phone: [0.07, 0.9], glow: [0.36, 0.84] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.6,0,.25,1)' },
      { at: 0.13, ease: 'cubic-bezier(.6,0,.25,1)', L: PHONE_AT },
      { at: 0.24, ease: 'cubic-bezier(.6,0,.3,1)', L: FAR, head: -4, headY: -2 },
      { at: 0.36, ease: 'cubic-bezier(.6,0,.3,1)', L: FAR, head: -4, headY: -2 },
      { at: 0.4, ease: 'ease-in-out', L: FAR, head: -3, headY: -2, parts: { keys: { r: 8 } } },
      { at: 0.52, ease: 'ease-in-out', L: FAR, head: -3, headY: -2, parts: { keys: { r: -4 } } },
      { at: 0.64, ease: 'ease-in-out', L: FAR, head: 5, headY: 0, parts: { keys: { r: 0 } } },
      { at: 0.78, ease: 'cubic-bezier(.6,0,.25,1)', L: FAR, head: 0 },
      { at: 0.86, ease: 'cubic-bezier(.6,0,.25,1)', L: PHONE_AT },
      { at: 0.94 },
      { at: 1 },
    ],
    peak: 5,
  },
};

/* His key ring, as the rig draws it, hanging from the fist: the ring swings, each key on its own. */
const KEYS = (
  <Part id="keys" at={[152, 313]}>
    <Sway at={[152, 313]} deg={1.5} seconds={2.6}>
      <Sway at={[148, 326]} deg={3} seconds={1.7} delay={-0.5}>
        <Resting id="kL">
          <path d="M148,326 L145,350" fill="none" stroke={GOLD} strokeWidth={3} strokeLinecap="round" />
          <path d="M142,346 L147,346 L146.5,351 L141.5,351 Z" fill={GOLD} />
        </Resting>
      </Sway>
      <Sway at={[158, 325]} deg={3} seconds={1.9} delay={-1.2}>
        <path d="M158,325 L162,348" fill="none" stroke={GOLD} strokeWidth={3} strokeLinecap="round" />
        <path d="M160,344 L165,343 L165.8,348 L160.8,349 Z" fill={GOLD} />
      </Sway>
      <Sway at={[153, 327]} deg={2.5} seconds={2.1}>
        <Resting id="kM">
          <path d="M153,327 L153,352" fill="none" stroke={COAT_DARK} strokeWidth={3} strokeLinecap="round" />
          <path d="M150,348 L156,348 L156,352 L150,352 Z" fill={GOLD} />
        </Resting>
      </Sway>
      <circle cx="153" cy="320" r="7" fill="none" stroke={GOLD} strokeWidth={2.5} />
    </Sway>
  </Part>
);

/* The registered letter, gripped by a corner: the red label of the recommandé with its bar code,
 * the stamp, the address. */
const ENVELOPE = (
  <g transform="translate(151 309) rotate(-4)">
    <path d="M-40,-30 L5,-30 L5,-1 L-40,-1 Z" fill="#ffffff" stroke={COAT_DARK} strokeWidth={1.2} strokeLinejoin="round" />
    <path d="M-36,-26.5 L-18,-26.5 L-18,-16.5 L-36,-16.5 Z" fill={RED} />
    <path d="M-33.5,-24.5 L-33.5,-18.5 M-31.5,-24.5 L-31.5,-18.5 M-30,-24.5 L-30,-18.5 M-27.8,-24.5 L-27.8,-18.5 M-26,-24.5 L-26,-18.5 M-23.6,-24.5 L-23.6,-18.5 M-22,-24.5 L-22,-18.5 M-20.2,-24.5 L-20.2,-18.5" fill="none" stroke="#ffffff" strokeWidth={0.9} />
    <path d="M-7,-27 L0.5,-27 L0.5,-18 L-7,-18 Z" fill={SCARF} />
    <path d="M-28,-10 L-8,-10 M-28,-5.5 L-13,-5.5" fill="none" stroke="#6b6560" strokeWidth={1.4} strokeLinecap="round" />
  </g>
);

/* The letter he re-reads, a corner in his fist. */
const LETTER = (
  <g transform="translate(68.5 310) rotate(4)">
    <path d="M-6,-42 L24,-42 L24,-1 L-6,-1 Z" fill="#ffffff" stroke={COAT_DARK} strokeWidth={1.2} strokeLinejoin="round" />
    <path d="M-2,-37 L9,-37" fill="none" stroke={RED} strokeWidth={2} strokeLinecap="round" />
    <path d="M-2,-30 L20,-30 M-2,-25 L20,-25 M-2,-20 L18,-20 M-2,-15 L20,-15 M8,-9 L19,-9" fill="none" stroke="#6b6560" strokeWidth={1.3} strokeLinecap="round" />
  </g>
);

/* The phone, its screen lit. */
const PHONE = (
  <g transform="translate(68.5 310)">
    <Shown id="glow">
      <circle cx="0" cy="-15" r="22" fill="#d9f2f7" opacity={0.5} />
      <circle cx="0" cy="-15" r="14" fill="#e9f8fb" opacity={0.6} />
    </Shown>
    <path d="M-8,-29 Q-8,-32 -5,-32 L5,-32 Q8,-32 8,-29 L8,0 Q8,3 5,3 L-5,3 Q-8,3 -8,0 Z" fill={INK} />
    <path d="M-6,-28.5 L6,-28.5 L6,-1 L-6,-1 Z" fill="#bfe6f0" />
    <path d="M-4,-25 L4,-25 L4,-19 L-4,-19 Z" fill="#ffffff" />
    <path d="M-4,-15 L3,-15 M-4,-11.5 L1,-11.5" fill="none" stroke="#5b86c8" strokeWidth={1.3} strokeLinecap="round" />
  </g>
);

/* The rig's glasses: two gold rims, the bridge, the arms to the ears. */
const GLASSES_D = 'M-24,-8 A12,12 0 1 0 0,-8 A12,12 0 1 0 -24,-8 Z M6,-8 A12,12 0 1 0 30,-8 A12,12 0 1 0 6,-8 Z M0,-9 Q3,-12 6,-9 M-24,-9 L-35,-5 M30,-9 L39,-5';

function Glasses({ s }: { s?: [number, number, number] }) {
  return (
    <g transform={s ? `translate(${s[0]} ${s[1]}) rotate(${s[2]} 3 -10)` : undefined}>
      <Part id="glasses" at={[3, -10]}>
        <path d={GLASSES_D} fill="none" stroke={GOLD} strokeWidth={2.2} strokeLinecap="round" />
      </Part>
    </g>
  );
}

const EYE = rig.eye!;
const n2 = (v: number) => Math.round(v * 100) / 100;

/**
 * The kit's blink, its closing line drawn as a filled band instead of a stroke: folded flat on
 * his tilted head, a stroke still leaves a hairline across the eye; a fill leaves nothing.
 */
function Blink({ e }: { e: VEye }) {
  if (!e.blinks) return null;
  const [x, y] = e.blinkTop;
  const cy = y + EYE.ry + 1.5;
  const w = 1.1;
  const [lx, ly, mx, my, rx, ry] = [x - EYE.rx, cy + EYE.ry * 0.55, x, cy + EYE.ry * 0.95, x + EYE.rx, cy + EYE.ry * 0.55].map(n2);
  const line = `M${lx},${n2(ly - w)} Q${mx},${n2(my - w)} ${rx},${n2(ry - w)} A${w},${w} 0 0 1 ${rx},${n2(ry + w)} Q${mx},${n2(my + w)} ${lx},${n2(ly + w)} A${w},${w} 0 0 1 ${lx},${n2(ly - w)} Z`;
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="tv-blink" transform="scale(1 0)">
        <g transform={`translate(${-x} ${-y})`}>
          <path d={e.blinkLid} fill={SKIN} />
          <path d={line} fill={INK} />
        </g>
      </g>
    </g>
  );
}

/* The pate's flush rises like a tide, the head's own outline above it. */
const PATE = [
  'M-36,-20 C-38,-62 -18,-76 4,-76 C28,-76 42,-62 40,-20 Q4,-42 -36,-20 Z',
  'M-36,-34 C-35,-64 -16,-76 4,-76 C26,-76 41,-64 40,-34 Q4,-58 -36,-34 Z',
];

/** A tuft standing up from its root above the ear: turned out and a little fuller. */
function flare(deg: number, side: -1 | 1): string | undefined {
  if (!deg) return undefined;
  const [x, y] = side < 0 ? [-38, -12] : [41, -12];
  return `translate(${x} ${y}) rotate(${-side * deg}) scale(${1 + deg / 100}) translate(${-x} ${-y})`;
}

function Features({ f }: { f: FaceValues }) {
  const look = f.def as Face;
  const t = look.tufts ?? 0;
  const down = Boolean(look.specs);
  return (
    <>
      {look.pate ? (
        <>
          <path d={PATE[0]} fill={look.pate} opacity={0.3} />
          <path d={PATE[1]} fill={look.pate} opacity={0.3} />
        </>
      ) : null}
      <ellipse cx="-6" cy="-60" rx="10" ry="4.5" fill="#f0c3a6" />
      <path d="M-16,-44 Q2,-48 20,-44 M-12,-36 Q2,-39 16,-36" transform={look.lines ? `translate(0 ${look.lines})` : undefined} fill="none" stroke={SHADE} strokeWidth={2} strokeLinecap="round" />
      <g transform={flare(t, -1)}>
        <path d="M-35,-30 C-54,-46 -66,-24 -52,-14 C-64,-8 -58,10 -41,3 C-43,-8 -41,-20 -35,-30 Z M-48,-38 L-60,-48 L-44,-34 Z" fill={TUFT} />
      </g>
      <g transform={flare(t, 1)}>
        <path d="M39,-30 C56,-46 68,-24 54,-14 C66,-8 60,10 43,3 C45,-8 43,-20 39,-30 Z M52,-38 L64,-48 L48,-34 Z" fill={TUFT} />
      </g>
      <g transform={flare(t, -1)}>
        <path d="M-50,-22 C-46,-20 -44,-16 -44,-10" fill="none" stroke={COAT_LIGHT} strokeWidth={2} strokeLinecap="round" />
      </g>
      <g transform={flare(t, 1)}>
        <path d="M52,-22 C48,-20 46,-16 46,-10" fill="none" stroke={COAT_LIGHT} strokeWidth={2} strokeLinecap="round" />
      </g>
      <EyeSet e={{ ...f.eL, blinks: false }} skin={SKIN} lidLine={2.2} arcLine={3.6} />
      <Blink e={f.eL} />
      <EyeSet e={{ ...f.eR, blinks: false }} skin={SKIN} lidLine={2.2} arcLine={3.6} />
      <Blink e={f.eR} />
      {down ? null : <Glasses />}
      <path d={f.browL} fill="none" stroke={BROW} strokeWidth={7} strokeLinecap="round" />
      <path d={f.browR} fill="none" stroke={BROW} strokeWidth={7} strokeLinecap="round" />
      <path d="M3,-8 C9,-2 18,16 14,23 C11,28 -1,27 -2,22 C-3,14 0,-2 3,-8 Z" fill={SHADE} />
      <path d="M-8,24 Q-12,33 -8,41 M20,24 Q24,33 20,41" fill="none" stroke={SHADE} strokeWidth={2} strokeLinecap="round" />
      {down ? <Glasses s={look.specs} /> : <Shown id="specs"><Glasses /></Shown>}
      {look.chin ? <path d="M-1,47 Q4.5,44.6 10,47" fill="none" stroke={SHADE} strokeWidth={1.8} strokeLinecap="round" /> : null}
      <Mouths mouths={f.mouths} transform="translate(-1.6 13.4) scale(1.6)" />
    </>
  );
}

const SLEEVE_L = { upper: 'M64,262 Q60,276 60.5,287', fore: 'M60.5,287 Q61,298 66,306' };

/** His left hand lives in the coat pocket; the arm is the rig's, behind the coat. */
function LeftArmBack() {
  return (
    <ArmLayer
      side="L"
      arm={ARMS.L}
      upper={<path d={SLEEVE_L.upper} fill="none" stroke={COAT_DARK} strokeWidth={13} strokeLinecap="round" />}
      fore={
        <Place side="L" place="back">
          <path d={SLEEVE_L.fore} fill="none" stroke={COAT_DARK} strokeWidth={13} strokeLinecap="round" />
        </Place>
      }
    />
  );
}

/** The same forearm out of the pocket, in front of the coat, with a hand and what it holds. */
function LeftArmFront() {
  const a = ARMS.L;
  return (
    <Place side="L" place="front">
      <ArmLayer
        side="L"
        arm={a}
        fore={<path d={SLEEVE_L.fore} fill="none" stroke={COAT_DARK} strokeWidth={13} strokeLinecap="round" />}
        held={
          <>
            <Shown id="letter">{LETTER}</Shown>
            <Shown id="phone">{PHONE}</Shown>
          </>
        }
        hand={
          <>
            <RestHand side="L">
              <circle cx={a.palm[0]} cy={a.palm[1]} r="8" fill={SKIN} />
            </RestHand>
            <HandShapes side="L" at={a.palm} r={8} skin={SKIN} shade={SHADE} />
          </>
        }
      />
    </Place>
  );
}

function RightArm({ place }: { place: 'back' | 'front' }) {
  const a = ARMS.R;
  return (
    <Place side="R" place={place}>
      <ArmLayer
        side="R"
        arm={a}
        upper={<path d="M140,254 Q150,268 153,280.5" fill="none" stroke={COAT} strokeWidth={14} strokeLinecap="round" />}
        fore={<path d="M153,280.5 Q156,293 152,304" fill="none" stroke={COAT} strokeWidth={14} strokeLinecap="round" />}
        held={
          <>
            {KEYS}
            <Shown id="envelope">{ENVELOPE}</Shown>
          </>
        }
        hand={
          <>
            <Shown id="upL">{keyUp(GOLD)}</Shown>
            <Shown id="upM">{keyUp(COAT_DARK)}</Shown>
            <RestHand side="R">
              <circle cx="151" cy="309" r="8" fill={SKIN} />
            </RestHand>
            <HandShapes side="R" at={a.palm} r={8} skin={SKIN} shade={SHADE} />
          </>
        }
      />
    </Place>
  );
}

function MarchandArt({ faces, base }: { faces: Array<{ id: string; values: FaceValues }>; base: ExpressionId }) {
  return (
    <g>
      <path d="M86,352 L84,392 M116,352 L120,392" fill="none" stroke="#4a4338" strokeWidth={13} strokeLinecap="round" />
      <ellipse cx="82" cy="400" rx="13" ry="6.5" fill={INK} />
      <ellipse cx="123" cy="400" rx="13" ry="6.5" fill={INK} />
      <Body fig={marchand}>
        <LeftArmBack />
        <path d="M104,216 L122,216 L124,236 L102,236 Z" fill={SKIN} />
        <path d="M58,262 C52,236 70,222 96,222 L124,226 Q144,232 146,252 L144,346 Q144,358 130,358 L70,358 Q58,358 58,346 Z" fill={COAT} />
        <path d="M62,250 C64,236 76,228 92,226 C80,232 70,240 66,256 Z" fill={COAT_LIGHT} />
        <path d="M101,262 L103,350" fill="none" stroke={COAT_DARK} strokeWidth={2} />
        <circle cx="102" cy="292" r="2.6" fill={GOLD} />
        <circle cx="102.5" cy="318" r="2.6" fill={GOLD} />
        <path d="M82,228 Q112,246 142,230 L140,246 Q112,262 84,244 Z" fill={SCARF} />
        <path d="M116,244 L132,244 L136,306 L118,308 Z" fill={SCARF} />
        <path d="M117.2,284 L134.8,283 L135,287 L117.4,288 Z M117.6,292 L135.3,291 L135.5,294 L117.8,295 Z" fill={GOLD} />
        <path d="M119,308 L119,314 M123,308 L123,314 M127,308 L127,313 M131,307 L131,313 M135,306 L135,312" fill="none" stroke={SCARF} strokeWidth={1.8} strokeLinecap="round" />
        <RightArm place="back" />
        <Head fig={marchand} base={base}>
          <ellipse cx="-37" cy="4" rx="9" ry="14" fill={SKIN} />
          <ellipse cx="40" cy="4" rx="8" ry="13" fill={SKIN} />
          <path d="M-36,-20 C-38,-62 -18,-76 4,-76 C28,-76 42,-62 40,-20 L40,10 C40,36 26,52 4,54 C-20,52 -36,36 -36,10 Z" fill={SKIN} />
          <Faces faces={faces} fig={marchand}>
            {(f) => <Features f={f} />}
          </Faces>
        </Head>
        <LeftArmFront />
        <RightArm place="front" />
      </Body>
    </g>
  );
}

export const marchand: FigureDef = {
  key: 'marchand',
  name: 'M. Marchand',
  rig,
  arms: ARMS,
  hips: [101, 352],
  neck: [113, 226],
  skin: SKIN,
  shade: SHADE,
  blink: 5.6,
  idle: { kind: 'nod', seconds: 5.2, amount: 3 },
  parts: { keys: [152, 313], glasses: [3, -10] },
  expressions: EXPRESSIONS,
  gestures: GESTURES,
  fx: { cheekL: [-17, 12], cheekR: [26, 12], temple: [22, -58], crown: [2, -80], side: [45, -64], eyeL: [-12, -8], eyeR: [18, -8] },
  Art: MarchandArt,
};
