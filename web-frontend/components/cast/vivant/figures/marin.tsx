/* La troupe vivante · Marin Lévêque, le grand cœur.
 *
 * Acting sheet. Big, slow and soft: the face goes first, the arm a beat later, and the whole body
 * follows last, the lean and the weight landing after the hand. He hugs his book; he cries at
 * adverts (both eyes, as his rig has it); his grandmother's proverbs come with one finger up and
 * the eyes shut; he strokes his beard to think; a small fist means «C'est un signe, ça.». Cross is
 * never angry on him: perplexed, one brow up, the look sideways (portrait). His kindness is a bowl
 * of soup. Sources: the rig, the model sheet (the soft smile, the look up, the eyes shut), the four
 * portraits (the sideways glance, the crinkled grin, the knitted brow, smiling through tears).
 *
 * The drawing is the rig's (`../../rigs/marin.tsx`), line for line: the sleeve on the right, one
 * quadratic from shoulder to wrist, is cut in two at the elbow (de Casteljau, so the rest pose draws
 * the same curve; at t = 0.51, a hair past the middle, where the two round caps no longer double an
 * edge pixel against the paper); the left arm was already two strokes meeting at the elbow, and his
 * book rides in that hand, kept upright, between the forearm and the fingers as the rig layers it.
 * The beard is part of the face, so the jaw can drop in it. The bowl (a bol breton) and the
 * handkerchief are new, in the rig's flat colours. */
import React from 'react';
import { circles, curlArcs, INK } from '../../rig-kit';
import { marin as rig } from '../../rigs/marin';
import type { Brow } from '../../rig-kit';
import type { ArmDef, ExpressionDef, FaceValues, FigureDef, GestureDef, GestureId, ExpressionId, Side } from '../kit';
import { ArmLayer, Body, EyeSet, Faces, HandShapes, Head, Mouths, Place, RestHand, Shown, Sway } from '../parts';

const SKIN = '#9a6643';
const SHADE = '#774a2c';
const KNIT = '#2c6a5d';
const CABLE = '#1f4f45';
const HAIR = '#1c1611';
const PAPER = '#f8f3e8';
const BLUE = '#1d3a8a';
const GLAZE = '#ecdfc3';

const BACK = [[-36, -38, 16], [-18, -54, 18], [4, -58, 18], [26, -50, 17], [40, -32, 14], [-46, -16, 12], [48, -14, 11], [-28, -48, 14], [14, -56, 16]] as const;
const FRONT = [[-28, -40, 10], [-11, -45, 11], [7, -46, 11], [24, -41, 10], [37, -32, 8]] as const;
let CABLES = '';
for (const x of [68, 100, 132]) {
  for (let y = 246; y < 344; y += 12) {
    CABLES += `M${x - 7},${y} L${x},${y + 7} L${x + 7},${y} L${x + 7},${y + 5} L${x},${y + 12} L${x - 7},${y + 5} Z `;
  }
}
const CURLS_BACK = circles(BACK);
const CURLS_FRONT = circles(FRONT);
const GLINTS = curlArcs([...BACK, ...FRONT]);

const ARMS: Record<Side, ArmDef> = {
  L: { shoulder: [48, 262], elbow: [38, 320], palm: [73, 292], r: 12 },
  R: { shoulder: [152, 262], elbow: [165.1172, 299.7196], palm: [162, 345], r: 12 },
};

// the rig's mood brows
const B = {
  neutre: [[-30, -23, -19, -27, -8, -29], [10, -29, 21, -27, 32, -23]] as [Brow, Brow],
  ravie: [[-30, -27, -19, -33, -8, -32], [10, -32, 21, -33, 32, -27]] as [Brow, Brow],
  surprise: [[-30, -30, -19, -37, -8, -35], [10, -35, 21, -37, 32, -30]] as [Brow, Brow],
  fachee: [[-30, -28, -19, -26, -8, -20], [10, -20, 21, -26, 32, -28]] as [Brow, Brow],
  emue: [[-30, -20, -19, -24, -8, -33], [10, -33, 21, -24, 32, -20]] as [Brow, Brow],
};

const EXPRESSIONS: Record<ExpressionId, ExpressionDef> = {
  neutre: { label: 'Neutre', note: 'le visage du rig', eyes: ['open', 'open'], brows: B.neutre, mouth: 'smile', tilt: 4 },
  joie: {
    label: 'Aux anges',
    note: 'les yeux en croissants, il serre son livre contre lui',
    eyes: ['happy', 'happy'],
    brows: [[-30, -28, -19, -35, -8, -34], [10, -34, 21, -35, 32, -28]],
    mouth: 'grin',
    tilt: -7,
    dy: -2,
    fx: ['sparkle'],
    pose: { at: 0, L: { to: [76, 284] }, R: { to: [80, 270], h: -75 }, body: -1.5, bodyY: -2 },
    front: ['R'],
  },
  malice: {
    label: 'Complice',
    note: 'le clin d’œil, il se penche',
    eyes: ['open', 'happy'],
    brows: [[-30, -29, -19, -35, -8, -33], [10, -27, 21, -25, 32, -21]],
    mouth: 'smirk',
    tilt: 9,
    dx: 2,
    gaze: [1, 0],
    pose: { at: 0, body: 2.5, head: 2 },
  },
  fier: {
    label: 'C’est un signe',
    note: 'les yeux qui brillent, le menton haut, le petit poing',
    eyes: ['sparkle', 'sparkle'],
    brows: [[-30, -29, -19, -36, -8, -35], [10, -35, 21, -36, 32, -29]],
    mouth: 'smile',
    tilt: -4,
    dy: -3,
    pose: { at: 0, R: { to: [128, 260], h: -8 }, bodyY: -2, body: -1 },
    hands: { R: 'fist' },
  },
  surprise: {
    label: 'Oh !',
    note: 'la mâchoire tombe dans la barbe, les doigts écartés',
    eyes: ['wide', 'wide'],
    brows: B.surprise,
    mouth: 'bigO',
    tilt: -2,
    dy: -3,
    pose: { at: 0, R: { to: [172, 224], h: 25 }, body: -2, bodyY: -1, head: -2 },
    hands: { R: 'open' },
  },
  panique: {
    label: 'Oh là là',
    note: 'les mains sur les joues, les pupilles minuscules',
    eyes: ['tiny', 'tiny'],
    brows: [[-30, -24, -19, -32, -8, -38], [10, -38, 21, -32, 32, -24]],
    mouth: 'o',
    tilt: 2,
    fx: ['sweat'],
    pose: { at: 0, L: { to: [60, 196], h: 10 }, R: { to: [140, 196], h: -10 }, bodyY: 1 },
    hands: { L: 'flat', R: 'flat' },
    front: ['L', 'R'],
  },
  fache: {
    label: 'Contrarié',
    note: 'perplexe, jamais fâché : un sourcil levé, le regard de côté',
    eyes: ['level', 'open'],
    brows: [[-30, -26, -19, -26, -8, -21], [10, -31, 21, -37, 32, -33]],
    mouth: 'side',
    tilt: -5,
    gaze: [3.5, 0],
    fx: ['question'],
    pose: { at: 0, R: { to: [160, 320], tuck: false, h: 200 }, body: -1.5, head: -2 },
    hands: { R: 'fist' },
  },
  emu: {
    label: 'Ému',
    note: 'les larmes des deux yeux, la main sur le cœur',
    eyes: ['sad', 'sad'],
    brows: B.emue,
    mouth: 'wobble',
    tilt: 7,
    fx: ['tears'],
    pose: { at: 0, R: { to: [122, 272], h: -40 }, head: 2, bodyY: 1 },
    hands: { R: 'flat' },
  },
  amour: {
    label: 'Fondant',
    note: 'la joue dans la main, il fond',
    eyes: ['happy', 'happy'],
    brows: [[-30, -24, -19, -30, -8, -34], [10, -34, 21, -30, 32, -24]],
    mouth: 'soft',
    tilt: 11,
    dy: 1,
    fx: ['blush', 'hearts'],
    pose: { at: 0, R: { to: [140, 214], h: -20 }, body: 2, head: 2 },
    hands: { R: 'flat' },
    front: ['R'],
  },
  fatigue: {
    label: 'Sieste',
    note: 'les yeux fermés, la tête tombe, il ronfle',
    eyes: ['shut', 'shut'],
    brows: [[-30, -20, -19, -22, -8, -23], [10, -23, 21, -22, 32, -20]],
    mouth: 'o',
    tilt: -11,
    dy: 4,
    fx: ['zzz'],
    pose: { at: 0, head: -4, body: -1.5, bodyY: 3 },
  },
};

const GESTURES: Record<GestureId, GestureDef> = {
  salut: {
    label: 'Bonjour !',
    line: 'Ah, bonjour, toi !',
    note: 'le grand salut lent, tout le corps suit',
    seconds: 3.6,
    face: 'joie',
    talk: true,
    hands: { R: 'open' },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.08, ease: 'cubic-bezier(.4,0,.3,1)', head: 1.5, bodyY: 0.8 },
      { at: 0.3, ease: 'ease-in-out', R: { to: [178, 188], h: -12 }, body: -0.5, head: -1, bodyY: -0.5 },
      { at: 0.41, ease: 'ease-in-out', R: { to: [188, 196], h: 24 }, body: -2.5, head: -4, bodyY: -1.5 },
      { at: 0.52, ease: 'ease-in-out', R: { to: [177, 187], h: -14 }, body: -1.8, head: -1.5, bodyY: -1.2 },
      { at: 0.63, ease: 'ease-in-out', R: { to: [188, 196], h: 24 }, body: -2.6, head: -4, bodyY: -1.5 },
      { at: 0.74, ease: 'ease-in-out', R: { to: [180, 190], h: -6 }, body: -2, head: -2, bodyY: -1 },
      { at: 0.95, ease: 'ease-in-out', body: -0.8, head: 0.5 },
      { at: 1 },
    ],
    peak: 3,
  },
  bravo: {
    label: 'C’est un signe',
    line: 'C’est un signe, ça !',
    note: 'le petit poing, deux fois, et le hochement',
    seconds: 3,
    face: 'fier',
    then: [0.62, 'joie'],
    talk: true,
    hands: { R: 'fist' },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.1, ease: 'ease-in', head: 2, bodyY: 0.6 },
      { at: 0.2, ease: 'cubic-bezier(.2,.6,.3,1.15)', R: { to: [126, 276], h: -14 }, head: 1.5, bodyY: 0.3 },
      { at: 0.3, ease: 'ease-in-out', R: { to: [128, 258], h: -8 }, bodyY: -0.5, head: 0 },
      { at: 0.4, ease: 'ease-in-out', R: { to: [128, 270], h: -2 }, bodyY: 0.6, head: 4, body: 0.5 },
      { at: 0.5, ease: 'ease-in-out', R: { to: [128, 257], h: -8 }, bodyY: -1.5, head: 0, body: -0.5 },
      { at: 0.6, ease: 'ease-in-out', R: { to: [128, 270], h: -2 }, bodyY: 0.6, head: 4, body: 0.5 },
      { at: 0.74, ease: 'cubic-bezier(.45,0,.4,1)', R: { to: [128, 259], h: -6 }, bodyY: -1.8, body: -1.2, head: -1 },
      { at: 0.92, ease: 'ease-in-out', bodyY: -0.6, body: -0.6 },
      { at: 1 },
    ],
    peak: 5,
  },
  oups: {
    label: 'Ma grand-mère disait…',
    line: 'Ma grand-mère disait : c’est en forgeant qu’on devient forgeron.',
    note: 'l’index levé, les yeux fermés, puis le sourire',
    seconds: 4,
    face: {
      eyes: ['shut', 'shut'],
      brows: [[-30, -28, -19, -35, -8, -34], [10, -34, 21, -35, 32, -28]],
      mouth: 'smile',
      tilt: -3,
      dy: -2,
    },
    then: [0.76, { eyes: ['open', 'open'], brows: B.ravie, mouth: 'smile', tilt: 3, gaze: [1, 0] }],
    talk: true,
    hands: { R: 'point' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.1, ease: 'cubic-bezier(.45,0,.3,1)', head: -1, bodyY: -0.6 },
      { at: 0.28, ease: 'ease-in-out', R: { to: [164, 212], h: -4 }, body: -0.5, head: -2, bodyY: -1 },
      { at: 0.4, ease: 'ease-in-out', R: { to: [164, 205], h: 2 }, body: -1.8, head: -4, bodyY: -1.8 },
      { at: 0.52, ease: 'ease-in-out', R: { to: [164, 211], h: -6 }, body: -1.4, head: -2.5, bodyY: -1.4 },
      { at: 0.64, ease: 'ease-in-out', R: { to: [164, 205], h: 2 }, body: -1.8, head: -4, bodyY: -1.8 },
      { at: 0.78, ease: 'cubic-bezier(.45,0,.4,1)', R: { to: [164, 214], h: -6 }, body: -1, head: 1, bodyY: -0.8 },
      { at: 0.95, ease: 'ease-in-out', body: 0.4, head: 1.5 },
      { at: 1 },
    ],
    peak: 3,
  },
  reflechit: {
    label: 'Hmm…',
    line: 'Hmm… voyons voir.',
    note: 'il caresse sa barbe, les yeux en l’air',
    seconds: 4.2,
    face: {
      eyes: ['open', 'open'],
      brows: [[-30, -25, -19, -29, -8, -29], [10, -33, 21, -38, 32, -32]],
      mouth: 'm',
      tilt: -4,
      gaze: [2.5, -3.5],
    },
    hands: { R: 'pinch' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.1, ease: 'cubic-bezier(.45,0,.3,1)', head: -1.5 },
      { at: 0.28, ease: 'ease-in-out', R: { to: [106, 232], h: -25 }, body: 0.5, head: -2 },
      { at: 0.42, ease: 'ease-in-out', R: { to: [105, 246], h: -15 }, body: 1.6, head: -3.5, bodyY: 0.5 },
      { at: 0.56, ease: 'ease-in-out', R: { to: [106, 232], h: -25 }, body: 1.2, head: -4 },
      { at: 0.7, ease: 'ease-in-out', R: { to: [105, 246], h: -15 }, body: 1.8, head: -3.5, bodyY: 0.5 },
      { at: 0.8, ease: 'cubic-bezier(.45,0,.4,1)', R: { to: [106, 236], h: -22 }, body: 1.4, head: -2.5 },
      { at: 0.96, ease: 'ease-in-out', body: 0.5, head: -0.5 },
      { at: 1 },
    ],
    peak: 2,
  },
  montre: {
    label: 'Une soupe ?',
    line: 'Une soupe ? Elle est encore chaude.',
    note: 'il te tend un bol fumant',
    seconds: 3.8,
    face: {
      eyes: ['open', 'open'],
      brows: [[-30, -27, -19, -33, -8, -35], [10, -35, 21, -33, 32, -27]],
      mouth: 'smileOpen',
      tilt: 7,
      gaze: [1, 1],
    },
    talk: true,
    show: { bowl: true },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.1, ease: 'cubic-bezier(.4,0,.3,1.1)', head: 1, bodyY: 0.5 },
      { at: 0.3, ease: 'ease-out', R: { to: [138, 286], reach: 1.12 }, body: 1, head: 3 },
      { at: 0.42, ease: 'ease-in-out', R: { to: [126, 284], reach: 1.18 }, body: 2.5, head: 6, bodyY: -0.5 },
      { at: 0.72, ease: 'ease-in-out', R: { to: [127, 286], reach: 1.18 }, body: 2.5, head: 5 },
      { at: 0.88, ease: 'ease-in-out', body: 1, head: 2 },
      { at: 1 },
    ],
    peak: 3,
  },
  signature: {
    label: 'Snif.',
    line: 'Snif. Ça me touche, c’est tout.',
    note: 'le mouchoir sous l’œil, il renifle, puis sourit',
    seconds: 4.2,
    face: 'emu',
    then: [0.7, { eyes: ['happy', 'happy'], brows: B.emue, mouth: 'soft', tilt: 4 }],
    hands: { R: 'fist' },
    front: ['R'],
    show: { mouchoir: true },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.1, ease: 'cubic-bezier(.4,0,.3,1)', head: 2, body: 0.5 },
      { at: 0.3, ease: 'ease-in-out', R: { to: [130, 194], h: -40 }, head: 5, body: 1 },
      { at: 0.4, ease: 'ease-in-out', R: { to: [138, 188], h: -30 }, head: 6, body: 1.5 },
      { at: 0.5, ease: 'ease-in-out', R: { to: [130, 194], h: -40 }, head: 5, body: 1 },
      { at: 0.6, ease: 'ease-in-out', R: { to: [138, 188], h: -30 }, head: 6, body: 1.5 },
      { at: 0.72, ease: 'ease-in-out', R: { to: [142, 250], h: -10 }, head: -2, bodyY: -2.5, body: 0.5 },
      { at: 0.84, ease: 'ease-in-out', R: { to: [152, 300], h: -4 }, head: 2, bodyY: 0.5 },
      { at: 1 },
    ],
    peak: 2,
  },
};

/* A bol breton about the right palm: cream with the blue band and its ears, carrot soup, the
 * steam rising in wisps (the effects' float, so `still` and Reduce Motion stop it too). */
const STEAM: Array<[number, number, string]> = [[154, 308, ''], [163, 305, ' tv-fx-late'], [171, 308, ' tv-fx-later']];
const BOWL = (
  <g>
    <path d="M142,315 Q133,314 134,319.5 Q135,324 143,321.5 Z M182,315 Q191,314 190,319.5 Q189,324 181,321.5 Z" fill={GLAZE} />
    <path d="M141,314 Q142,337 154,339 L170,339 Q182,337 183,314 Z" fill={GLAZE} />
    <path d="M142,323 Q162,326 182,323 L181,329 Q162,332 143,329 Z" fill={BLUE} />
    <path d="M147,335 Q162,340 177,335 Q175,339 170,339 L154,339 Q149,339 147,335 Z" fill="#d6c4a0" />
    <ellipse cx="162" cy="314" rx="21" ry="5" fill={PAPER} />
    <ellipse cx="162" cy="314.6" rx="18" ry="3.6" fill="#d8742a" />
    <path d="M150,313.6 Q156,312.4 160,313.4" fill="none" stroke="#f0a050" strokeWidth={1.4} strokeLinecap="round" />
    <g className="tv-fx">
      {STEAM.map(([x, y, late]) => (
        <g key={x} transform={`translate(${x} ${y})`}>
          <path className={`tv-fx-float${late}`} d="M0,0 Q-3.5,-4 0,-8 Q3.5,-12 0,-16" fill="none" stroke="#ffffff" strokeWidth={2.6} strokeLinecap="round" opacity={0.9} />
        </g>
      ))}
    </g>
  </g>
);

/* His handkerchief, pale blue with a darker border, crumpled in the fist and peeking out above it. */
const HANKY = (
  <g>
    <path d="M150,336 Q146,326 152,322 Q156,316 162,320 Q168,318 170,326 Q176,334 170,340 L156,346 Q148,344 150,336 Z" fill="#c9d6ee" />
    <path d="M152,322 Q156,316 162,320 Q168,318 170,326" fill="none" stroke={BLUE} strokeWidth={1.8} strokeLinecap="round" />
    <path d="M155,327 Q159,325 162,329 M163,324 Q166,325 166,329" fill="none" stroke="#ffffff" strokeWidth={1.4} strokeLinecap="round" />
  </g>
);

const BOOK = (
  <g>
    <path d="M50,266 L82,261 L87,303 L55,308 Z" fill={BLUE} />
    <path d="M82,261 L86,262 L91,304 L87,303 Z" fill={PAPER} />
    <path d="M54,272 L80,268 L80.5,272 L54.5,276 Z" fill="#f3c318" />
  </g>
);

const BEARD = 'M-46,-2 C-48,32 -26,60 0,62 C26,60 48,32 46,-2 C40,10 30,15 17,13 C8,9 -8,9 -17,13 C-30,15 -40,10 -46,-2 Z';
/** how far the jaw drops in the beard for an open mouth */
const JAW: Record<string, number> = { bigO: 7, o: 3, yawn: 6, shout: 5 };

function Features({ f }: { f: FaceValues }) {
  const j = JAW[f.def.mouth.replace('~', '')] ?? 0;
  const beard = j
    ? `M-46,-2 C-48,${32 + j / 2} -26,${60 + j} 0,${62 + j} C26,${60 + j} 48,${32 + j / 2} 46,-2 C40,10 30,15 17,13 C8,9 -8,9 -17,13 C-30,15 -40,10 -46,-2 Z`
    : BEARD;
  return (
    <>
      <EyeSet e={f.eL} skin={SKIN} lidLine={2.4} arcLine={4.5} />
      <EyeSet e={f.eR} skin={SKIN} lidLine={2.4} arcLine={4.5} />
      <path d={f.browL} fill="none" stroke={HAIR} strokeWidth={7} strokeLinecap="round" />
      <path d={f.browR} fill="none" stroke={HAIR} strokeWidth={7} strokeLinecap="round" />
      <path d={beard} fill={HAIR} />
      <ellipse cx="-1" cy={33 + j / 2} rx="19" ry={12 + j / 2} fill={SKIN} />
      <Mouths mouths={f.mouths} transform={`translate(-5 ${-1 + j / 2}) scale(2)`} />
      <path d="M-23,21 C-12,13 10,13 21,21 C10,24 -12,24 -23,21 Z" fill={HAIR} />
      <path d="M0,0 C6,0 10,10 8,15 C6,19 -6,19 -8,15 C-10,10 -6,0 0,0 Z" fill={SHADE} />
    </>
  );
}

const sleeve = (d: string, w: number) => <path d={d} fill="none" stroke={KNIT} strokeWidth={w} strokeLinecap="round" />;

function RightArm({ place }: { place: 'back' | 'front' }) {
  const a = ARMS.R;
  return (
    <Place side="R" place={place}>
      <ArmLayer
        side="R"
        arm={a}
        upper={sleeve('M152,262 Q162.2,281.38 165.1172,299.7196', 22)}
        fore={sleeve('M165.1172,299.7196 Q167.92,317.34 164,334', 22)}
        held={<Shown id="bowl">{BOWL}</Shown>}
        hand={
          <>
            <Shown id="mouchoir">{HANKY}</Shown>
            <RestHand side="R">
              <circle cx={a.palm[0]} cy={a.palm[1]} r="12" fill={SKIN} />
            </RestHand>
            <HandShapes side="R" at={a.palm} r={12} skin={SKIN} shade={SHADE} />
          </>
        }
      />
    </Place>
  );
}

const L_HAND = (
  <>
    <RestHand side="L">
      <circle cx="73" cy="292" r="12" fill={SKIN} />
      <circle cx="62" cy="286" r="5.5" fill={SKIN} />
    </RestHand>
    <HandShapes side="L" at={ARMS.L.palm} r={12} skin={SKIN} shade={SHADE} />
  </>
);

/* The left arm in the rig's order (sleeve, book, hand); the book is a layer of its own so it stays
 * behind the head when the hand goes to his cheek. */
function LeftArm({ place }: { place: 'back' | 'front' }) {
  const a = ARMS.L;
  const upper = sleeve('M48,262 Q28,296 38,320', 22);
  const fore = sleeve('M38,320 Q54,310 64,296', 18);
  if (place === 'front') {
    return (
      <Place side="L" place="front">
        <ArmLayer side="L" arm={a} upper={upper} fore={fore} hand={L_HAND} />
      </Place>
    );
  }
  return (
    <>
      <Place side="L" place="back">
        <ArmLayer side="L" arm={a} upper={upper} fore={fore} />
      </Place>
      <ArmLayer side="L" arm={a} held={BOOK} />
      <Place side="L" place="back">
        <ArmLayer side="L" arm={a} hand={L_HAND} />
      </Place>
    </>
  );
}

function MarinArt({ faces, base }: { faces: Array<{ id: string; values: FaceValues }>; base: ExpressionId }) {
  return (
    <g>
      <path d="M80,360 L80,390 M120,360 L120,390" fill="none" stroke="#4a4338" strokeWidth={20} strokeLinecap="round" />
      <ellipse cx="76" cy="400" rx="17" ry="8" fill={INK} />
      <ellipse cx="124" cy="400" rx="17" ry="8" fill={INK} />
      <Body fig={marin}>
        <path d="M44,262 Q48,232 76,228 L124,228 Q152,232 156,262 L170,338 Q172,366 144,368 L56,368 Q28,366 30,338 Z" fill={KNIT} />
        <path d={CABLES} fill={CABLE} />
        <path d="M31,350 L169,350 Q168,366 144,368 L56,368 Q32,366 31,350 Z" fill={CABLE} />
        <path d="M74,226 Q100,242 126,226 L128,236 Q100,254 72,236 Z" fill={CABLE} />
        <path d="M82,238 Q88,262 100,268 Q112,262 118,238" fill="none" stroke="#4a3020" strokeWidth={1.8} />
        <Sway at={[100, 267]} deg={5} seconds={2.6}>
          <path d="M97,266 C94,276 100,284 106,280 C103,278.5 100.5,274 101.5,268 Z" fill={PAPER} />
        </Sway>
        <RightArm place="back" />
        <LeftArm place="back" />
        <Head fig={marin} base={base}>
          <path d={CURLS_BACK} fill={HAIR} />
          <ellipse cx="-46" cy="0" rx="8.5" ry="11" fill={SKIN} />
          <ellipse cx="47" cy="0" rx="8.5" ry="11" fill={SKIN} />
          <path d="M-46,-14 C-46,-46 -24,-54 0,-54 C24,-54 46,-46 46,-14 C46,20 32,48 0,50 C-32,48 -46,20 -46,-14 Z" fill={SKIN} />
          <path d={CURLS_FRONT} fill={HAIR} />
          <path d={GLINTS} fill="none" stroke="#c49a0a" strokeWidth={2.4} strokeLinecap="round" />
          <Faces faces={faces} fig={marin}>
            {(f) => <Features f={f} />}
          </Faces>
        </Head>
        <LeftArm place="front" />
        <RightArm place="front" />
      </Body>
    </g>
  );
}

export const marin: FigureDef = {
  key: 'marin',
  name: 'Marin',
  rig,
  arms: ARMS,
  hips: [100, 362],
  neck: [100, 224],
  skin: SKIN,
  shade: SHADE,
  blink: 5.2,
  idle: { kind: 'bob', seconds: 4.8, amount: 2.2 },
  parts: {},
  expressions: EXPRESSIONS,
  gestures: GESTURES,
  fx: { cheekL: [-30, 8], cheekR: [31, 8], temple: [40, -24], crown: [0, -76], side: [58, -50], eyeL: [-18, -6], eyeR: [19, -6] },
  Art: MarinArt,
};
