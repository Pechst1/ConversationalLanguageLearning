/* La troupe vivante · Augustin «Gus» de Roncourt, le dandy.
 *
 * Acting sheet. Slow in, big arcs, a touch of overshoot, then he holds like a statue; the chin is
 * always up (the rig carries his head at -7°, and he never lowers it for long). His tells: the
 * hand on the lapel, the open offering palm and the tie tug when the nerves come (model sheet),
 * the index cards he declaims from, superlatives («Magnifique !», «Sublime.»). The portraits give
 * the faces: heavy lids and the smirk, the teeth smile, the open-mouthed indignation with the head
 * thrown back, the misty half-closed eyes.
 *
 * The drawing is the rig's (`../../rigs/gus.tsx`), line for line: both sleeves are split at the
 * elbow (each quadratic cut in two at its midpoint, so the rest pose draws the same curve), the
 * shirt cuff turns with his raised forearm, the index card rides in his left hand; the cards that
 * fall and the fan he opens are his own props, drawn like the rig's card. */
import React from 'react';
import { gus as rig } from '../../rigs/gus';
import type { Brow } from '../../rig-kit';
import { INK, ellipse } from '../../rig-kit';
import type { ArmDef, ExpressionDef, FaceValues, FigureDef, GestureDef, GestureId, ExpressionId, MouthValues, Pt, Side, VEye } from '../kit';
import { ArmLayer, Body, EyeSet, Faces, HandShapes, Head, Mouths, Part, Place, RestHand, Resting, Shown } from '../parts';

const SKIN = '#e0a985';
const SHADE = '#cf956f';
const SUIT = '#1d3a8a';
const LAPEL = '#14285f';
const SHIRT = '#f8f3e8';
const HAIR = '#3d2817';
const CARD_EDGE = '#8a8270';

const ARMS: Record<Side, ArmDef> = {
  L: { shoulder: [54, 224], elbow: [35, 218], palm: [25, 185], r: 8 },
  R: { shoulder: [148, 226], elbow: [159, 259.5], palm: [151, 292], r: 8 },
};

// the rig's mood brows
const B = {
  neutre: [[-26, -24, -16, -31, -6, -26], [7, -26, 18, -32, 29, -25]] as [Brow, Brow],
  ravie: [[-26, -27, -16, -34, -6, -29], [7, -29, 18, -35, 29, -27]] as [Brow, Brow],
  surprise: [[-26, -31, -16, -38, -6, -33], [7, -33, 18, -39, 29, -31]] as [Brow, Brow],
  fachee: [[-26, -28, -16, -26, -6, -19], [7, -19, 18, -26, 29, -28]] as [Brow, Brow],
  emue: [[-26, -20, -16, -24, -6, -29], [7, -29, 18, -24, 29, -20]] as [Brow, Brow],
};

const EXPRESSIONS: Record<ExpressionId, ExpressionDef> = {
  neutre: { label: 'Neutre', note: 'le visage du rig : paupières lourdes, le sourire en coin', eyes: ['heavy', 'heavy'], brows: B.neutre, mouth: 'smirk', tilt: -7 },
  joie: {
    label: 'Magnifique',
    note: 'le sourire à dents du portrait, le menton qui monte',
    eyes: ['happy', 'happy'],
    brows: B.ravie,
    mouth: 'teeth',
    tilt: -11,
    dy: -2,
    hands: { L: 'open' },
  },
  malice: {
    label: 'Théâtral',
    note: 'les yeux aux cieux, il déclame, la main levée',
    eyes: ['wide', 'wide'],
    brows: [[-26, -31, -16, -41, -6, -34], [7, -35, 18, -43, 29, -33]],
    mouth: 'smileOpen',
    tilt: -10,
    dy: -2,
    gaze: [-2, -4],
    pose: { at: 0, L: { to: [32, 170], reach: 1.1, h: -14 }, head: -2 },
    hands: { L: 'open' },
  },
  fier: {
    label: 'Sublime',
    note: 'menton très haut, paupières mi-closes, la main au revers',
    eyes: ['smug', 'smug'],
    brows: [[-26, -26, -16, -33, -6, -28], [7, -28, 18, -34, 29, -26]],
    mouth: 'smile',
    tilt: -13,
    dy: -3,
    fx: ['sparkle'],
    pose: { at: 0, L: { to: [80, 236], tuck: false, h: 4 }, bodyY: -1 },
    hands: { L: 'thumb' },
  },
  surprise: {
    label: 'Pardon ?!',
    note: 'offusqué : un sourcil au ciel, la tête en arrière, la main sur la poitrine',
    eyes: ['wide', 'wide'],
    brows: [[-26, -32, -16, -41, -6, -35], [7, -22, 18, -29, 29, -31]],
    mouth: 'o',
    tilt: -4,
    dy: -4,
    pose: { at: 0, L: { to: [90, 248], tuck: false, h: 20 }, body: -1.5, headY: -2 },
    hands: { L: 'open' },
  },
  panique: {
    label: 'Le trac',
    note: 'les yeux de côté, il tire sur sa cravate (planche de modèle)',
    eyes: ['open', 'open'],
    brows: [[-26, -22, -16, -27, -6, -32], [7, -32, 18, -27, 29, -22]],
    mouth: 'grimace',
    tilt: -2,
    gaze: [-3.8, -0.5],
    fx: ['sweat'],
    pose: { at: 0, L: { to: [95, 226], tuck: false, h: 10 }, head: 3 },
    hands: { L: 'pinch' },
  },
  fache: {
    label: 'Outré',
    note: 'l’indignation bouche ouverte du portrait, la tête rejetée, l’index levé',
    eyes: ['cross', 'cross'],
    brows: [[-26, -29, -16, -27, -6, -18], [7, -19, 18, -27, 29, -30]],
    mouth: 'outre',
    tilt: 2,
    dy: -3,
    pose: { at: 0, L: { to: [30, 176], h: -4 }, bodyY: -1 },
    hands: { L: 'point' },
  },
  emu: {
    label: 'Ému',
    note: 'les yeux embués, la main sur le cœur',
    eyes: ['sad', 'sad'],
    brows: B.emue,
    mouth: 'soft',
    tilt: 4,
    pose: { at: 0, R: { to: [124, 231], h: -50 }, head: 2 },
    hands: { R: 'flat' },
  },
  amour: {
    label: 'Séducteur',
    note: 'le clin d’œil, le sourire à dents',
    eyes: ['happy', 'smug'],
    brows: [[-26, -22, -16, -26, -6, -23], [7, -30, 18, -38, 29, -31]],
    mouth: 'teeth',
    tilt: -9,
    dx: 1,
    fx: ['hearts'],
  },
  fatigue: {
    label: 'Blasé',
    note: 'le bâillement, poliment derrière la main, le menton toujours haut',
    eyes: ['down', 'down'],
    brows: [[-26, -26, -16, -31, -6, -28], [7, -28, 18, -31, 29, -26]],
    mouth: 'yawn',
    tilt: -10,
    dy: -1,
    pose: { at: 0, L: { to: [91, 176], reach: 1.24, h: 38 }, headX: -4, headY: 3 },
    hands: { L: 'flat' },
    front: ['L'],
  },
};

/* Where his palm is when the cards slip in `oups`: the fallen cards start from the card in hand. */
const FUMBLE: Pt = [140, 262];
const SPILL: Pt = [FUMBLE[0] - ARMS.R.palm[0], FUMBLE[1] - ARMS.R.palm[1]];
const FLOOR = { c1: { x: -4, y: 124, r: 6 }, c2: { x: -22, y: 128, r: -8 }, c3: { x: 30, y: 126, r: 170 } };
const FAN_OPEN = { f1: { r: -50 }, f2: { r: -17 }, f3: { r: 16 }, f4: { r: 49 } };
const FAN_SHUT = { f1: { r: 0 }, f2: { r: 0 }, f3: { r: 0 }, f4: { r: 0 } };

const GESTURES: Record<GestureId, GestureDef> = {
  salut: {
    label: 'Mes hommages',
    line: 'Mes hommages.',
    note: 'la main fait un moulinet, se pose sur le ventre, et il s’incline',
    seconds: 3.4,
    face: { eyes: ['heavy', 'heavy'], brows: B.ravie, mouth: 'smile' },
    then: [0.4, { eyes: ['shut', 'shut'], brows: B.ravie, mouth: 'smile' }],
    talk: true,
    hands: { L: 'open' },
    keys: [
      { at: 0, ease: 'cubic-bezier(.55,0,.4,1)' },
      { at: 0.16, ease: 'ease-in-out', L: { to: [38, 168], h: -6 }, head: -3, bodyY: -1 },
      { at: 0.28, ease: 'ease-in-out', L: { to: [10, 190], reach: 1.1, h: -95 }, R: { to: [166, 286], h: 30 }, head: -2 },
      { at: 0.4, ease: 'cubic-bezier(.3,0,.3,1.25)', L: { to: [40, 254], reach: 1.1, h: 160 }, R: { to: [182, 274], h: 115 }, head: 0, bodyY: 1 },
      { at: 0.54, ease: 'ease-in-out', L: { to: [76, 262], h: 95 }, R: { to: [188, 266], h: 125 }, head: 6, headY: 10, body: 1.5, bodyY: 5 },
      { at: 0.76, ease: 'cubic-bezier(.5,0,.4,1)', L: { to: [76, 263], h: 95 }, R: { to: [188, 267], h: 125 }, head: 6, headY: 10, body: 1.5, bodyY: 5 },
      { at: 1 },
    ],
    peak: 4,
  },
  bravo: {
    label: 'Magnifique !',
    line: 'Magnifique !',
    note: 'il rassemble, puis jette les bras grands ouverts, les yeux fermés',
    seconds: 3,
    face: { eyes: ['shut', 'shut'], brows: [[-26, -30, -16, -38, -6, -33], [7, -33, 18, -39, 29, -30]], mouth: 'laugh' },
    talk: true,
    hands: { L: 'open', R: 'open' },
    keys: [
      { at: 0, ease: 'cubic-bezier(.5,0,.5,1)' },
      { at: 0.14, ease: 'cubic-bezier(.4,0,.2,1.3)', L: { to: [62, 210], h: 20 }, R: { to: [130, 262], h: -20 }, head: 3, bodyY: 2 },
      { at: 0.34, ease: 'ease-in-out', L: { to: [12, 186], reach: 1.12, tuck: false, h: -60 }, R: { to: [190, 196], reach: 1.1, tuck: false, h: 60 }, head: -4, headY: -3, bodyY: -3 },
      { at: 0.76, ease: 'cubic-bezier(.5,0,.4,1)', L: { to: [13, 188], reach: 1.12, h: -58 }, R: { to: [189, 198], reach: 1.1, h: 58 }, head: -4, headY: -3, bodyY: -3 },
      { at: 1 },
    ],
    peak: 2,
  },
  oups: {
    label: 'On recommence',
    line: 'On recommence.',
    note: 'il lit sa fiche, les fiches lui glissent des doigts ; il se fige, puis relève le menton',
    seconds: 3.8,
    face: { eyes: ['wide', 'wide'], brows: B.surprise, mouth: 'o', gaze: [0, 4] },
    then: [0.56, { eyes: ['heavy', 'heavy'], brows: B.ravie, mouth: 'smirk', talk: true }],
    hands: { L: 'open' },
    hide: { card: [0.22, 0.9] },
    show: { spill: [0.22, 0.86] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.5,0,.4,1)' },
      { at: 0.12, ease: 'ease-in-out', R: { to: [132, 254], h: -10 }, L: { to: [28, 178], h: -4 }, head: 3 },
      { at: 0.19, ease: 'ease-in', R: { to: [133, 252], h: -10 }, L: { to: [28, 177], h: -4 }, head: 3 },
      { at: 0.22, ease: 'ease-out', R: { to: FUMBLE, h: 0 }, L: { to: [26, 182], h: -4 }, head: 4, parts: { c1: {}, c2: {}, c3: {} } },
      {
        at: 0.3,
        ease: 'linear',
        R: { to: [150, 286], h: 22 },
        L: { to: [26, 183], h: -4 },
        head: 6,
        headY: 2,
        parts: { c1: { x: -8, y: 40, r: 30 }, c2: { x: 10, y: 30, r: -40 }, c3: { x: 16, y: 48, r: 70 } },
      },
      { at: 0.38, ease: 'ease-out', R: { to: [151, 288], h: 18 }, head: 6, headY: 2, parts: { c1: { x: 4, y: 92, r: -12 }, c2: { x: -10, y: 82, r: 24 }, c3: { x: 28, y: 98, r: 120 } } },
      { at: 0.46, ease: 'linear', head: 6, headY: 2, parts: FLOOR },
      { at: 0.58, ease: 'cubic-bezier(.5,0,.3,1.25)', head: 6, headY: 2, parts: FLOOR },
      { at: 0.7, ease: 'ease-in-out', L: { to: [80, 238], tuck: false, h: 10 }, head: -4, headY: -2, bodyY: -1, parts: FLOOR },
      { at: 0.78, ease: 'ease-in-out', L: { to: [80, 238], h: 10 }, head: -4, headY: -2, bodyY: -1, parts: FLOOR },
      { at: 0.84, ease: 'cubic-bezier(.5,0,.4,1)', L: { to: [80, 238], h: 10 }, head: -4, headY: -2, bodyY: -1, parts: { c1: { ...FLOOR.c1, o: 0 }, c2: { ...FLOOR.c2, o: 0 }, c3: { ...FLOOR.c3, o: 0 } } },
      { at: 1 },
    ],
    peak: 4,
  },
  reflechit: {
    label: 'Voyons…',
    line: 'Voyons, voyons…',
    note: 'l’index sur le menton, les yeux au plafond',
    seconds: 3.4,
    face: { eyes: ['open', 'open'], brows: [[-26, -25, -16, -31, -6, -26], [7, -32, 18, -39, 29, -32]], mouth: 'pout', gaze: [3, -4] },
    hands: { L: 'point' },
    front: ['L'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.5,0,.5,1)' },
      { at: 0.1, ease: 'cubic-bezier(.3,0,.3,1.2)', L: { to: [62, 214], h: 20 } },
      { at: 0.24, ease: 'ease-in-out', L: { to: [104, 199], reach: 1.15, h: -6 }, head: -3, body: -1 },
      { at: 0.52, ease: 'ease-in-out', L: { to: [104, 198], reach: 1.15, h: -6 }, head: -5, body: -1 },
      { at: 0.78, ease: 'cubic-bezier(.5,0,.4,1)', L: { to: [104, 199], reach: 1.15, h: -6 }, head: -3, body: -1 },
      { at: 1 },
    ],
    peak: 3,
  },
  montre: {
    label: 'Je vous en prie',
    line: 'Je vous en prie.',
    note: 'la main au revers, l’autre s’ouvre et vous offre la paume',
    seconds: 3.2,
    face: { eyes: ['open', 'open'], brows: B.ravie, mouth: 'teeth' },
    talk: true,
    hands: { L: 'thumb', R: 'open' },
    hide: { card: [0.08, 0.88] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.5,0,.4,1)' },
      { at: 0.16, ease: 'cubic-bezier(.4,0,.3,1.3)', L: { to: [80, 236], tuck: false, h: 4 }, R: { to: [160, 300], h: 10 }, head: -2 },
      { at: 0.38, ease: 'ease-in-out', L: { to: [80, 236], h: 4 }, R: { to: [176, 258], reach: 1.22, h: 78 }, head: 4, body: 1.5 },
      { at: 0.76, ease: 'cubic-bezier(.5,0,.4,1)', L: { to: [80, 236], h: 4 }, R: { to: [175, 259], reach: 1.22, h: 76 }, head: 4, body: 1.5 },
      { at: 1 },
    ],
    peak: 2,
  },
  signature: {
    label: 'Mesdames, messieurs !',
    line: 'Mesdames, messieurs !',
    note: 'il lève ses fiches et les ouvre en éventail, l’autre bras au public',
    seconds: 3.6,
    face: 'malice',
    talk: true,
    hands: { L: 'open' },
    front: ['R'],
    hide: { card: [0.2, 0.88] },
    show: { fan: [0.2, 0.88] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.5,0,.5,1)' },
      { at: 0.12, ease: 'ease-in', R: { to: [156, 298], h: 10 }, L: { to: [40, 206], h: -10 }, bodyY: 2, head: 2 },
      { at: 0.24, ease: 'cubic-bezier(.2,.5,.2,1.4)', R: { to: [190, 240], tuck: false, h: 70 }, L: { to: [24, 210], h: -40 }, bodyY: -1, head: -1 },
      { at: 0.38, ease: 'ease-in-out', R: { to: [172, 166], tuck: false, h: 4 }, L: { to: [16, 200], reach: 1.1, h: -64 }, bodyY: -3, head: -4, headY: -3, parts: FAN_SHUT },
      { at: 0.52, ease: 'ease-in-out', R: { to: [172, 164], h: 2 }, L: { to: [16, 199], reach: 1.1, h: -62 }, bodyY: -3, head: -4, headY: -3, parts: FAN_OPEN },
      { at: 0.76, ease: 'ease-in', R: { to: [172, 165], h: 3 }, L: { to: [16, 200], reach: 1.1, h: -63 }, bodyY: -3, head: -4, headY: -3, parts: FAN_OPEN },
      { at: 0.82, ease: 'cubic-bezier(.4,0,.4,1)', R: { to: [171, 170], h: 4 }, L: { to: [18, 199], reach: 1.08, h: -54 }, bodyY: -2, head: -3, headY: -2, parts: FAN_SHUT },
      { at: 1 },
    ],
    peak: 4,
  },
};

/* The rig's index card, as it draws it under his left hand. */
function Card({ dx = 0, dy = 0, edge }: { dx?: number; dy?: number; edge?: boolean }) {
  return (
    <g transform={dx || dy ? `translate(${dx} ${dy})` : undefined}>
      <path d="M145,296 L163,292 L165,306 L147,310 Z" fill={SHIRT} stroke={edge ? CARD_EDGE : undefined} strokeWidth={edge ? 0.9 : undefined} strokeLinejoin="round" />
      <path d="M149,300 L160,297.6 M149.6,304 L158,302" fill="none" stroke="#6f6857" strokeWidth={1.2} />
    </g>
  );
}

/* The fan: four cards standing on his palm, opened by turning each about it. */
const FAN = ['f1', 'f2', 'f3', 'f4'];
function Fan() {
  const [x, y] = ARMS.R.palm;
  return (
    <Shown id="fan">
      {FAN.map((id) => (
        <Part key={id} id={id} at={ARMS.R.palm}>
          <path d={`M${x - 7.5},${y - 3} L${x - 7.5},${y - 27} L${x + 7.5},${y - 27} L${x + 7.5},${y - 3} Z`} fill={SHIRT} stroke={CARD_EDGE} strokeWidth={0.9} strokeLinejoin="round" />
          <path d={`M${x - 4},${y - 22} L${x + 4},${y - 22} M${x - 4},${y - 18} L${x + 2.5},${y - 18}`} fill="none" stroke="#6f6857" strokeWidth={1.2} />
        </Part>
      ))}
    </Shown>
  );
}

/* The cards that slip in `oups`: they start where the card in hand is at the fumble. */
function Spill() {
  const c: Pt = [155 + SPILL[0], 301 + SPILL[1]];
  return (
    <Shown id="spill">
      {['c3', 'c2', 'c1'].map((id) => (
        <Part key={id} id={id} at={c}>
          <Card dx={SPILL[0]} dy={SPILL[1]} edge />
        </Part>
      ))}
    </Shown>
  );
}

/**
 * The kit's blink, its closed line drawn as a filled band (under his tilted head a stroke squashed
 * to nothing, the lid at rest, still leaves a dot of ink on the eye) and its lid a little larger,
 * so it covers a wide eye too.
 */
function Blink({ e }: { e: VEye }) {
  if (!e.blinks) return null;
  const { rx, ry } = rig.eye!;
  const [x, y] = e.blinkTop;
  const cy = y + ry + 1.5;
  const [y1, y2, w] = [cy + ry * 0.55, cy + ry * 0.95, 1.3];
  const band = `M${x - rx},${y1 - w} Q${x},${y2 - w} ${x + rx},${y1 - w} A${w},${w} 0 0 1 ${x + rx},${y1 + w} Q${x},${y2 + w} ${x - rx},${y1 + w} A${w},${w} 0 0 1 ${x - rx},${y1 - w} Z`;
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="tv-blink" transform="scale(1 0)">
        <g transform={`translate(${-x} ${-y})`}>
          <path d={ellipse(x, cy - 0.6, rx + 2, ry + 2.4)} fill={SKIN} />
          <path d={band} fill={INK} />
        </g>
      </g>
    </g>
  );
}

/* His own mouth, in the kit's mouth frame: the open-mouthed indignation of the cross portrait. */
const OWN_MOUTHS: Record<string, Omit<MouthValues, 'key'>> = {
  outre: {
    d: 'M-7,20 Q-5.5,10.5 2,10.5 Q9.5,10.5 11,20 Q2,17.6 -7,20 Z',
    fill: INK,
    teeth: 'M-5.2,15 Q-2.6,11.5 2,11.5 Q6.6,11.5 9.2,15 L8.8,16.4 Q2,13.2 -4.8,16.4 Z',
    tongue: 'M-3.5,19.2 Q2,15.8 7.5,19.2 Q2,18 -3.5,19.2 Z',
    line: '',
  },
};
const own = (m: MouthValues): MouthValues => (OWN_MOUTHS[m.key] ? { key: m.key, ...OWN_MOUTHS[m.key] } : m);

function Features({ f }: { f: FaceValues }) {
  return (
    <>
      <EyeSet e={{ ...f.eL, blinks: false }} skin={SKIN} lidLine={2.6} arcLine={4.2} />
      <Blink e={f.eL} />
      <EyeSet e={{ ...f.eR, blinks: false }} skin={SKIN} lidLine={2.6} arcLine={4.2} />
      <Blink e={f.eR} />
      <path d={f.browL} fill="none" stroke={HAIR} strokeWidth={5.5} strokeLinecap="round" />
      <path d={f.browR} fill="none" stroke={HAIR} strokeWidth={5.5} strokeLinecap="round" />
      <path d="M1,-10 C5,-6 11,14 10,20 C8,24 -1,24 -3,20 C-3,12 -1,-6 1,-10 Z" fill="#b97f5c" />
      <Mouths mouths={f.mouths.map(own)} transform="translate(-1.6 7) scale(1.8)" />
    </>
  );
}

function Arm({ side, place }: { side: Side; place: 'back' | 'front' }) {
  const a = ARMS[side];
  if (side === 'R') {
    return (
      <Place side="R" place={place}>
        <ArmLayer
          side="R"
          arm={a}
          upper={<path d="M148,226 Q158,244 159,259.5" fill="none" stroke={SUIT} strokeWidth={14} strokeLinecap="round" />}
          fore={<path d="M159,259.5 Q160,275 152,288" fill="none" stroke={SUIT} strokeWidth={14} strokeLinecap="round" />}
          hand={
            <>
              <Fan />
              <Resting id="card">
                <Card />
              </Resting>
              <RestHand side="R">
                <circle cx="151" cy="292" r="8" fill={SKIN} />
              </RestHand>
              <HandShapes side="R" at={a.palm} r={8} skin={SKIN} shade={SHADE} />
            </>
          }
        />
      </Place>
    );
  }
  return (
    <Place side="L" place={place}>
      <ArmLayer
        side="L"
        arm={a}
        upper={<path d="M54,224 Q42,225 35,218" fill="none" stroke={SUIT} strokeWidth={14} strokeLinecap="round" />}
        fore={
          <>
            <path d="M35,218 Q28,211 26,196" fill="none" stroke={SUIT} strokeWidth={14} strokeLinecap="round" />
            <path d="M20,200 L32,195" fill="none" stroke={SHIRT} strokeWidth={5} strokeLinecap="round" />
          </>
        }
        hand={
          <>
            <RestHand side="L">
              <ellipse cx="25" cy="185" rx="9.5" ry="7.5" fill={SKIN} />
              <circle cx="34" cy="188" r="3.6" fill={SKIN} />
            </RestHand>
            <HandShapes side="L" at={a.palm} r={8} skin={SKIN} shade={SHADE} />
          </>
        }
      />
    </Place>
  );
}

function GusArt({ faces, base }: { faces: Array<{ id: string; values: FaceValues }>; base: ExpressionId }) {
  return (
    <g>
      <path d="M90,336 L88,392 M110,336 L113,392" fill="none" stroke="#14285f" strokeWidth={14} strokeLinecap="round" />
      <path d="M72,398 Q76,391 92,393 L96,398 Q96,404 90,404 L74,404 Q69,402 72,398 Z M128,398 Q124,391 108,393 L104,398 Q104,404 110,404 L126,404 Q131,402 128,398 Z" fill="#14110d" />
      <Body fig={gus}>
        <path d="M93,176 L107,176 L107,214 L93,214 Z" fill={SKIN} />
        <path d="M46,228 Q48,212 68,210 L132,210 Q152,212 154,228 L126,332 Q124,340 116,340 L84,340 Q76,340 74,332 Z" fill={SUIT} />
        <path d="M84,210 L100,262 L116,210 Z" fill={SHIRT} />
        <path d="M96,213 L104,213 L102,222 L98,222 Z" fill="#9c2411" />
        <path d="M98,222 L102,222 L106,256 L100,264 L94,256 Z" fill="#d8321a" />
        <path d="M84,210 L70,214 L96,270 L100,262 Z M116,210 L130,214 L104,270 L100,262 Z" fill={LAPEL} />
        <circle cx="100" cy="290" r="2.6" fill="#c49a0a" />
        <circle cx="100" cy="306" r="2.6" fill="#c49a0a" />
        <path d="M121,238 L127,221 L132,223 L126,240 Z M125,238 L135,223 L139,226 L129,241 Z" fill={SHIRT} />
        <path d="M119,240 L140,235 L137,247 L123,249 Z M123,240 L127,231 L132,239 Z M131,238 L137,230 L139,236 Z" fill="#d8321a" />
        <Spill />
        <Arm side="R" place="back" />
        <Arm side="L" place="back" />
        <Head fig={gus} base={base}>
          <path d="M-42,-20 C-50,-60 -20,-92 14,-88 C44,-86 54,-58 44,-22 L30,-40 L-30,-40 Z" fill={HAIR} />
          <ellipse cx="-38" cy="2" rx="7" ry="11" fill={SKIN} />
          <ellipse cx="40" cy="2" rx="7" ry="11" fill={SKIN} />
          <path d="M-38,-28 C-38,-60 -20,-68 2,-68 C24,-68 40,-58 40,-28 L40,8 C40,34 26,54 2,58 C-22,54 -38,34 -38,8 Z" fill={SKIN} />
          <path d="M-30,30 Q-14,48 2,51 Q18,48 33,30 Q22,55 2,58 Q-18,55 -30,30 Z" fill={SHADE} />
          <path d="M2,50 L2,56" fill="none" stroke="#b97f5c" strokeWidth={2} strokeLinecap="round" />
          <path d="M-42,-22 C-50,-64 -14,-96 18,-90 C46,-86 54,-58 44,-24 C40,-42 30,-52 16,-54 C4,-46 -18,-54 -30,-42 C-36,-36 -40,-30 -42,-22 Z" fill={HAIR} />
          <path d="M-24,-70 C-10,-82 10,-84 26,-78 C10,-78 -6,-74 -18,-64 Z M20,-72 C32,-70 42,-62 44,-50 C38,-58 30,-64 20,-66 Z" fill="#8a5a32" />
          <path d="M6,-52 C0,-42 6,-32 14,-34 C9,-37 8,-43 12,-50 Z" fill={HAIR} />
          <Faces faces={faces} fig={gus}>
            {(f) => <Features f={f} />}
          </Faces>
        </Head>
        <Arm side="R" place="front" />
        <Arm side="L" place="front" />
      </Body>
    </g>
  );
}

export const gus: FigureDef = {
  key: 'gus',
  name: 'Gus',
  rig,
  arms: ARMS,
  hips: [100, 334],
  neck: [101, 184],
  skin: SKIN,
  shade: SHADE,
  blink: 5.2,
  idle: { kind: 'sway', seconds: 3.6, amount: -2.5 },
  parts: {
    c1: [144, 271],
    c2: [144, 271],
    c3: [144, 271],
    f1: ARMS.R.palm,
    f2: ARMS.R.palm,
    f3: ARMS.R.palm,
    f4: ARMS.R.palm,
  },
  expressions: EXPRESSIONS,
  gestures: GESTURES,
  fx: { cheekL: [-22, 22], cheekR: [26, 22], temple: [33, -36], crown: [2, -96], side: [62, -56], eyeL: [-15, -6], eyeR: [17, -6] },
  Art: GusArt,
};
