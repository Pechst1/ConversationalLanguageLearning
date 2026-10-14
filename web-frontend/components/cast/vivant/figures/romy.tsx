/* La troupe vivante · Romy Tremblay, la reporter.
 *
 * Acting sheet. Quick and direct: she lands a move and holds it, leans in to ask. One eyebrow
 * does her irony, the 3/4 sideways look of her portraits, a fist under the chin when she thinks
 * (portrait, model sheet). Québec understatement: «C'est pas pire !» is high praise. The camera is
 * always in reach and its red light stays on, steady; switching it off is her kindness (WP-117:
 * the mistake is not on the record). Her microphone comes out when she wants your answer.
 *
 * The drawing is the rig's (`../../rigs/romy.tsx`), line for line: the sleeves are split at the
 * elbow (each quadratic cut in two at its midpoint, so the rest pose draws the same curve), the
 * camera rides in her left hand, the long hair turns with the head. */
import React from 'react';
import { dots } from '../../rig-kit';
import { romy as rig } from '../../rigs/romy';
import type { Brow } from '../../rig-kit';
import type { ArmDef, ExpressionDef, FaceValues, FigureDef, GestureDef, GestureId, ExpressionId, Side } from '../kit';
import { ArmLayer, BehindHead, Body, EyeSet, Faces, HandShapes, Head, Mouths, Place, RestHand, Resting, Shown, Sway } from '../parts';

const SKIN = '#ecb896';
const SHADE = '#d49a76';
const JACKET = '#1f1b16';
const CUFF = '#2e2924';
const HAIR = '#4a2e1a';

const FRECKLES = [[-22, 7], [-26, 10], [-18, 10], [-12, 5], [-8, 9], [-3, 4], [22, 7], [26, 10], [18, 10], [12, 5], [8, 9], [3, 4]] as const;
const FRECKLE_D = dots(FRECKLES, 1.1);
function lash(c: [number, number], side: -1 | 1): string {
  return `M${c[0] - 10.5},${c[1] - 3} Q${c[0]},${c[1] - 15} ${c[0] + 10.5},${c[1] - 3} M${c[0] + side * 10},${c[1] - 4} L${c[0] + side * 14},${c[1] - 6.5}`;
}
const LASHED = new Set(['open', 'wide', 'tiny', 'sparkle']);

const ARMS: Record<Side, ArmDef> = {
  L: { shoulder: [62, 238], elbow: [57, 268.5], palm: [81, 309], r: 8 },
  R: { shoulder: [138, 238], elbow: [143, 268.5], palm: [119, 309], r: 8 },
};

// the rig's mood brows
const B = {
  neutre: [[-24, -21, -15, -26, -6, -22], [6, -22, 15, -26, 24, -21]] as [Brow, Brow],
  ravie: [[-24, -24, -15, -29, -6, -25], [6, -25, 15, -29, 24, -24]] as [Brow, Brow],
  surprise: [[-24, -28, -15, -34, -6, -29], [6, -29, 15, -34, 24, -28]] as [Brow, Brow],
  fachee: [[-24, -24, -15, -22, -6, -16], [6, -16, 15, -22, 24, -24]] as [Brow, Brow],
  emue: [[-24, -18, -15, -21, -6, -25], [6, -25, 15, -21, 24, -18]] as [Brow, Brow],
};

const EXPRESSIONS: Record<ExpressionId, ExpressionDef> = {
  neutre: { label: 'Neutre', note: 'le visage du rig', eyes: ['open', 'open'], brows: B.neutre, mouth: 'smile' },
  joie: { label: 'Ravie', note: 'le grand rire, le menton qui monte', eyes: ['happy', 'happy'], brows: B.ravie, mouth: 'laugh', tilt: -5, dy: -2 },
  malice: {
    label: 'Curieuse',
    note: 'un œil plissé, l’autre sourcil levé',
    eyes: ['level', 'open'],
    brows: [[-24, -19, -15, -22, -6, -19], [6, -29, 15, -36, 24, -31]],
    mouth: 'smirk',
    tilt: 7,
    dx: 2,
    gaze: [3.5, 0],
  },
  fier: {
    label: 'C’est pas pire',
    note: 'paupières mi-closes, sourire fermé, menton haut',
    eyes: ['smug', 'smug'],
    brows: [[-24, -23, -15, -28, -6, -24], [6, -24, 15, -28, 24, -23]],
    mouth: 'smile',
    tilt: -6,
    dy: -3,
  },
  surprise: {
    label: 'Voyons donc !',
    note: 'les yeux grands, la bouche ronde',
    eyes: ['wide', 'wide'],
    brows: [[-24, -30, -15, -37, -6, -31], [6, -31, 15, -37, 24, -30]],
    mouth: 'bigO',
    dy: -2,
    fx: ['shock'],
  },
  panique: {
    label: 'Panique',
    note: 'pupilles minuscules, dents serrées, une goutte',
    eyes: ['tiny', 'tiny'],
    brows: [[-24, -24, -15, -30, -6, -32], [6, -32, 15, -30, 24, -24]],
    mouth: 'grimace',
    tilt: 3,
    fx: ['sweat'],
  },
  fache: {
    label: 'Fâchée',
    note: 'le regard du portrait, bouche pincée, menton baissé',
    eyes: ['cross', 'cross'],
    brows: [[-24, -25, -15, -22, -6, -14], [6, -14, 15, -22, 24, -25]],
    mouth: 'tight',
    dy: 3,
    gaze: [0, -1.5],
  },
  emu: {
    label: 'Émue',
    note: 'une larme, le poing sous le menton (portrait)',
    eyes: ['sad', 'sad'],
    brows: B.emue,
    mouth: 'soft',
    tilt: 6,
    pose: { at: 0, R: { to: [103, 206], tuck: true, h: -10 }, head: 4 },
    hands: { R: 'fist' },
    front: ['R'],
  },
  amour: {
    label: 'Attendrie',
    note: 'les yeux fondent, les joues rosissent',
    eyes: ['happy', 'happy'],
    brows: [[-24, -21, -15, -26, -6, -27], [6, -27, 15, -26, 24, -21]],
    mouth: 'soft',
    tilt: 8,
    fx: ['blush', 'hearts'],
  },
  fatigue: {
    label: 'Crevée',
    note: 'paupières lourdes, la tête qui tombe',
    eyes: ['down', 'down'],
    brows: [[-24, -18, -15, -20, -6, -21], [6, -21, 15, -20, 24, -18]],
    mouth: 'flat',
    tilt: 9,
    dy: 3,
    fx: ['zzz'],
  },
};

/* Where the camera's centre sits from her left palm, and the right hand on its other side. */
const CAM: [number, number] = [19, -2];
const camTo = (x: number, y: number, reach = 1.1) => ({
  L: { to: [x - CAM[0], y - CAM[1]] as [number, number], reach },
  R: { to: [x + 19, y + 2] as [number, number], reach: reach + 0.06 },
});

const GESTURES: Record<GestureId, GestureDef> = {
  salut: {
    label: 'Salut !',
    line: 'Salut !',
    note: 'deux doigts à la tempe, puis la pichenette',
    seconds: 2.6,
    face: 'malice',
    talk: true,
    hands: { R: 'two' },
    keys: [
      { at: 0, ease: 'cubic-bezier(.2,.8,.3,1)' },
      { at: 0.14, R: { to: [150, 170], h: -12 }, head: 4 },
      { at: 0.32, ease: 'cubic-bezier(.3,1.6,.5,1)', R: { to: [151, 168], h: -10 }, head: 4 },
      { at: 0.44, R: { to: [170, 152], reach: 1.18, h: 30 }, head: 2 },
      { at: 0.66, ease: 'ease-in-out', R: { to: [170, 154], reach: 1.18, h: 28 }, head: 2 },
      { at: 0.84 },
      { at: 1 },
    ],
    peak: 3,
  },
  bravo: {
    label: 'C’est pas pire !',
    line: 'C’est pas pire !',
    note: 'le pouce levé, la caméra dans l’autre main',
    seconds: 2.2,
    face: 'joie',
    talk: true,
    hands: { R: 'thumb' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.2,.9,.3,1.2)' },
      { at: 0.16, ease: 'ease-in-out', R: { to: [155, 238], h: -6 }, bodyY: -2 },
      { at: 0.32, ease: 'ease-in-out', R: { to: [153, 229], h: 0 }, head: 4, bodyY: -1 },
      { at: 0.48, ease: 'ease-in-out', R: { to: [155, 238], h: -6 }, head: 0 },
      { at: 0.62, ease: 'ease-in-out', R: { to: [153, 231], h: 0 }, head: 3 },
      { at: 0.82 },
      { at: 1 },
    ],
    peak: 2,
  },
  oups: {
    label: 'C’est off.',
    line: 'On recommence. C’est off.',
    note: 'le pouce éteint la lumière rouge : l’erreur n’est pas enregistrée',
    seconds: 2.8,
    face: { eyes: ['down', 'down'], brows: B.neutre, mouth: 'm', tilt: 2, gaze: [1, 2] },
    then: [0.36, 'malice'],
    hands: { R: 'thumb' },
    hide: { tally: [0.27, 0.93] },
    keys: [
      { at: 0, ease: 'ease-out' },
      { at: 0.16, ease: 'ease-in', R: { to: [123, 292], h: 160 }, head: 3 },
      { at: 0.24, ease: 'ease-out', R: { to: [123, 289], h: 165 }, head: 3 },
      { at: 0.27, ease: 'ease-in-out', R: { to: [122, 293], h: 168 }, head: 4 },
      { at: 0.4, ease: 'ease-in-out', R: { to: [124, 290], h: 160 }, head: 4 },
      { at: 0.56, ease: 'ease-in-out', head: 7, body: 1.5 },
      { at: 0.8, ease: 'ease-in-out', head: 7, body: 1.5 },
      { at: 1 },
    ],
    peak: 3,
  },
  reflechit: {
    label: 'Attends…',
    line: 'Attends… j’ai une question.',
    note: 'le poing sous le menton, les yeux en l’air',
    seconds: 3.2,
    face: {
      eyes: ['open', 'open'],
      brows: [[-24, -25, -15, -30, -6, -26], [6, -21, 15, -24, 24, -20]],
      mouth: 'pout',
      tilt: 5,
      gaze: [-3.5, -3.5],
    },
    hands: { R: 'fist' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.25,.9,.3,1)' },
      { at: 0.16, ease: 'ease-in-out', R: { to: [104, 206], tuck: true, h: -12 }, head: 5, body: 1.5 },
      { at: 0.45, ease: 'ease-in-out', R: { to: [104, 204], tuck: true, h: -12 }, head: 7, body: 1.5 },
      { at: 0.7, ease: 'ease-in-out', R: { to: [104, 206], tuck: true, h: -12 }, head: 5, body: 1.5 },
      { at: 0.86 },
      { at: 1 },
    ],
    peak: 1,
  },
  montre: {
    label: 'Alors ?',
    line: 'Alors ? Je t’écoute.',
    note: 'elle te tend son micro',
    seconds: 2.8,
    face: {
      eyes: ['open', 'open'],
      brows: [[-24, -26, -15, -32, -6, -27], [6, -27, 15, -32, 24, -26]],
      mouth: 'smileOpen',
      tilt: 5,
      gaze: [0, 0],
    },
    talk: true,
    hands: { R: 'fist' },
    show: { mic: true },
    keys: [
      { at: 0, ease: 'cubic-bezier(.2,.9,.3,1.1)' },
      { at: 0.16, ease: 'ease-out', R: { to: [130, 266], reach: 1.2, h: 2 }, head: 3, body: 1.5 },
      { at: 0.3, ease: 'ease-in-out', R: { to: [127, 260], reach: 1.32, h: 4 }, head: 5, body: 2.5 },
      { at: 0.7, ease: 'ease-in-out', R: { to: [128, 262], reach: 1.3, h: 3 }, head: 5, body: 2.5 },
      { at: 0.86 },
      { at: 1 },
    ],
    peak: 2,
  },
  signature: {
    label: 'Clic !',
    line: 'Clic ! Ne bouge plus.',
    note: 'la caméra à l’œil, le flash, puis elle regarde l’écran',
    seconds: 3.4,
    face: { eyes: ['open', 'squeeze'], brows: [[-24, -21, -15, -26, -6, -22], [6, -18, 15, -21, 24, -19]], mouth: 'smirk', tilt: 2 },
    then: [0.6, 'joie'],
    front: ['L', 'R'],
    hide: { strap: [0.06, 0.96] },
    show: { flash: [0.42, 0.48] },
    keys: [
      { at: 0, ease: 'cubic-bezier(.25,.9,.35,1)' },
      { at: 0.2, ease: 'ease-in-out', ...camTo(86, 163), head: 3, headY: 9, body: -1 },
      { at: 0.4, ease: 'ease-out', ...camTo(86, 162), head: 3, headY: 9, body: -1 },
      { at: 0.44, ease: 'ease-in-out', ...camTo(86, 158), head: 2, headY: 8, body: -1.5 },
      { at: 0.56, ease: 'ease-in', ...camTo(86, 162), head: 3, headY: 9, body: -1 },
      { at: 0.63, ease: 'cubic-bezier(.2,.7,.3,1)', ...camTo(98, 236, 1), head: 5, headY: 5, body: -0.5 },
      { at: 0.72, ease: 'ease-in-out', ...camTo(100, 301, 1), head: 7, headY: 2, body: 0 },
      { at: 0.86, ease: 'ease-in-out', ...camTo(100, 303, 1), head: 7, headY: 2 },
      { at: 1 },
    ],
    peak: 3,
  },
};

/* A reporter's hand mic: the grille, the station's flag in her blue, the handle in her fist. */
const MIC = (
  <g>
    <path d="M116.2,300 L121.8,300 L120.8,327 Q119,329.4 117.2,327 Z" fill="#14110d" />
    <path d="M117.4,302 L118.4,325" stroke="#3d3832" strokeWidth={0.9} strokeLinecap="round" />
    <path d="M112.6,296 L125.4,296 L124.4,306 L113.6,306 Z" fill="#1d3a8a" />
    <path d="M112.6,296 L125.4,296 L125.2,298 L112.8,298 Z" fill="#2c4fae" />
    <path d="M116.6,303.6 L116.6,299.2 L119.6,299.2 Q121.4,299.2 121.4,300.8 Q121.4,302.2 119.6,302.2 L116.8,302.2 M119.4,302.2 L121.6,304" fill="none" stroke="#f8f3e8" strokeWidth={1.1} strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="119" cy="288" r="8.6" fill="#3d3832" />
    <path d="M110.6,288 L127.4,288 M119,279.6 L119,296.4 M112,283.4 Q119,286.4 126,283.4 M112,292.6 Q119,289.6 126,292.6 M114.4,281.2 Q116.8,288 114.4,294.8 M123.6,281.2 Q121.2,288 123.6,294.8" fill="none" stroke="#6b6560" strokeWidth={0.8} />
    <circle cx="119" cy="288" r="8.6" fill="none" stroke="#14110d" strokeWidth={1.2} />
    <path d="M114,283.6 Q116,281.4 118.8,281" fill="none" stroke="#f8f3e8" strokeWidth={1.3} strokeLinecap="round" opacity={0.55} />
  </g>
);

/* The camera, as the rig draws it, in her left hand; the light now steady (WP-117). */
const CAMERA = (
  <g>
    <path d="M92,286 L108,286 L108,291 L92,291 Z" fill="#14110d" />
    <path d="M80,296 Q80,290 86,290 L114,290 Q120,290 120,296 L120,318 Q120,324 114,324 L86,324 Q80,324 80,318 Z" fill="#14110d" />
    <circle cx="100" cy="307" r="10" fill="#3d3832" />
    <circle cx="100" cy="307" r="6" fill="#1d3a8a" />
    <circle cx="97.6" cy="304.6" r="1.8" fill="#f8f3e8" />
    <Resting id="tally">
      <circle cx="114" cy="295.5" r="2.4" fill="#d8321a" />
    </Resting>
    <Shown id="flash">
      <circle cx="100" cy="307" r="16" fill="#fffbe6" opacity={0.75} />
      <path d="M100,281 L104,302 L126,307 L104,312 L100,333 L96,312 L74,307 L96,302 Z" fill="#ffffff" />
    </Shown>
  </g>
);

function Features({ f }: { f: FaceValues }) {
  const lashL = LASHED.has(f.def.eyes[0]) ? lash([-15, -4], -1) : '';
  const lashR = LASHED.has(f.def.eyes[1]) ? lash([15, -4], 1) : '';
  return (
    <>
      <EyeSet e={f.eL} skin={SKIN} iris="#3b5f9e" arcLine={4} lash={lashL} />
      <EyeSet e={f.eR} skin={SKIN} iris="#3b5f9e" arcLine={4} lash={lashR} />
      <path d={f.browL} fill="none" stroke="#5a3a22" strokeWidth={4.4} strokeLinecap="round" />
      <path d={f.browR} fill="none" stroke="#5a3a22" strokeWidth={4.4} strokeLinecap="round" />
      <path d="M0,-1 C3,2 5,10 4,13 C2,15.5 -2,15.5 -4,13 C-5,10 -3,2 0,-1 Z" fill={SHADE} />
      <Mouths mouths={f.mouths} transform="translate(-3.6 1.8) scale(1.8)" />
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
        upper={<path d={L ? 'M62,238 Q56,254 57,268.5' : 'M138,238 Q144,254 143,268.5'} fill="none" stroke={JACKET} strokeWidth={15} strokeLinecap="round" />}
        fore={
          <>
            <path d={L ? 'M57,268.5 Q58,283 66,296' : 'M143,268.5 Q142,283 134,296'} fill="none" stroke={JACKET} strokeWidth={15} strokeLinecap="round" />
            <path d={L ? 'M66,296 Q76,304 82,306' : 'M134,296 Q124,304 118,306'} fill="none" stroke={CUFF} strokeWidth={13} strokeLinecap="round" />
          </>
        }
        held={L ? CAMERA : <Shown id="mic">{MIC}</Shown>}
        hand={
          <>
            <RestHand side={side}>
              <circle cx={a.palm[0]} cy={a.palm[1]} r="8" fill={SKIN} />
            </RestHand>
            <HandShapes side={side} at={a.palm} r={8} skin={SKIN} shade={SHADE} />
          </>
        }
      />
    </Place>
  );
}

function RomyArt({ faces, base }: { faces: Array<{ id: string; values: FaceValues }>; base: ExpressionId }) {
  return (
    <g>
      <Body fig={romy}>
        <BehindHead fig={romy}>
          <path d="M46,128 C40,80 70,64 100,64 C130,64 160,80 154,128 C160,160 148,180 156,200 C164,220 152,236 162,252 C150,266 128,262 118,250 L82,250 C72,262 50,266 38,252 C48,236 36,220 44,200 C52,180 40,160 46,128 Z" fill={HAIR} />
        </BehindHead>
      </Body>
      <path d="M88,340 L87,392 M112,340 L113,392" fill="none" stroke="#14285f" strokeWidth={14} strokeLinecap="round" />
      <ellipse cx="84" cy="399" rx="12" ry="6.5" fill="#14110d" />
      <ellipse cx="116" cy="399" rx="12" ry="6.5" fill="#14110d" />
      <Body fig={romy}>
        <path d="M93,192 L107,192 L107,222 L93,222 Z" fill={SKIN} />
        <path d="M60,232 Q62,216 80,214 L120,214 Q138,216 140,232 L146,330 Q146,342 134,342 L66,342 Q54,342 54,330 Z" fill={JACKET} />
        <path d="M85,214 L100,250 L115,214 Z" fill="#1d3a8a" />
        <path d="M85,214 L74,220 L94,262 L100,250 Z M115,214 L126,220 L106,262 L100,250 Z" fill={CUFF} />
        <path d="M63,250 Q60,288 64,322 M137,250 Q140,288 136,322" fill="none" stroke="#4a4640" strokeWidth={2.5} strokeLinecap="round" />
        <circle cx="106" cy="232" r="2.4" fill="#14110d" />
        <path d="M105,234 L107,234 L107,239 L105,239 Z" fill="#14110d" />
        <Resting id="strap">
          <path d="M84,292 L89,224 M116,292 L111,224" fill="none" stroke="#14110d" strokeWidth={2} />
        </Resting>
        <Arm side="L" place="back" />
        <Arm side="R" place="back" />
        <Head fig={romy} base={base}>
          <path d="M-38,-24 C-38,-56 -20,-64 0,-64 C20,-64 38,-56 38,-24 C38,14 22,46 0,50 C-22,46 -38,14 -38,-24 Z" fill={SKIN} />
          <ellipse cx="-22" cy="13" rx="6.5" ry="3.6" fill="#f1a98f" />
          <ellipse cx="22" cy="13" rx="6.5" ry="3.6" fill="#f1a98f" />
          <Sway at={[-37, 8.6]} deg={7} seconds={2.4}>
            <circle cx="-37" cy="12" r="3.4" fill="none" stroke="#c49a0a" strokeWidth={1.8} />
          </Sway>
          <Sway at={[37, 8.6]} deg={7} seconds={2.4} delay={-1.1}>
            <circle cx="37" cy="12" r="3.4" fill="none" stroke="#c49a0a" strokeWidth={1.8} />
          </Sway>
          <Sway at={[0, -80]} deg={1.3} seconds={3.8}>
            <path d="M0,-80 C-30,-80 -54,-60 -52,-24 C-50,4 -58,28 -52,52 C-48,66 -56,74 -54,82 L-42,80 C-44,64 -39,50 -41,30 C-43,8 -42,-14 -40,-26 Z" fill={HAIR} />
            <path d="M-47,10 C-49,26 -50,42 -48,60" fill="none" stroke="#c49a0a" strokeWidth={1.8} strokeLinecap="round" />
          </Sway>
          <Sway at={[0, -80]} deg={1.3} seconds={3.8} delay={-1.9}>
            <path d="M0,-80 C30,-80 54,-60 52,-24 C50,4 58,28 52,52 C48,66 56,74 54,82 L42,80 C44,64 39,50 41,30 C43,8 42,-14 40,-26 Z" fill={HAIR} />
            <path d="M47,10 C49,26 50,42 48,60" fill="none" stroke="#c49a0a" strokeWidth={1.8} strokeLinecap="round" />
          </Sway>
          <path d="M-41,6 C-44,-40 -26,-80 0,-80 C26,-80 44,-40 41,6 L36,4 C35,-16 30,-36 18,-46 C12,-50 6,-52 2,-53 L0,-57 L-2,-53 C-6,-52 -12,-50 -18,-46 C-30,-36 -35,-16 -36,4 Z" fill={HAIR} />
          <path d="M-1,-56 L-1,-78" fill="none" stroke="#6b4428" strokeWidth={1.4} strokeLinecap="round" />
          <path d="M-24,-46 C-30,-38 -33,-28 -34,-16 M24,-46 C30,-38 33,-28 34,-16" fill="none" stroke="#c49a0a" strokeWidth={1.8} strokeLinecap="round" />
          <path d={FRECKLE_D} fill="#b9755a" />
          <Faces faces={faces} fig={romy}>
            {(f) => <Features f={f} />}
          </Faces>
        </Head>
        <Arm side="L" place="front" />
        <Arm side="R" place="front" />
      </Body>
    </g>
  );
}

export const romy: FigureDef = {
  key: 'romy',
  name: 'Romy',
  rig,
  arms: ARMS,
  hips: [100, 338],
  neck: [100, 197],
  skin: SKIN,
  shade: SHADE,
  blink: 4.4,
  idle: { kind: 'bob', seconds: 5, amount: 1.4 },
  parts: {},
  expressions: EXPRESSIONS,
  gestures: GESTURES,
  fx: { cheekL: [-22, 13], cheekR: [22, 13], temple: [31, -30], crown: [0, -84], side: [58, -52], eyeL: [-15, -4], eyeR: [15, -4] },
  Art: RomyArt,
};
