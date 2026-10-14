/* La troupe vivante · Margaux Barman, la patronne.
 *
 * Acting sheet. Economical, slow, deliberate: she moves once and holds it; the head barely moves,
 * one brow does the talking (her right brow is already up in the rig). Tells: she dries a glass
 * that is already dry, the raised index (model sheet), «J'ai rien entendu», the café crème pushed
 * across the counter, the key with the cicada. Her praise is a coffee; her surprise is two brows.
 * Faces from the portraits: happy is narrowed eyes and a closed smile, never a grin; cross is one
 * brow down; moved looks up, glassy.
 *
 * The drawing is the rig's (`../../rigs/margaux.tsx`), line for line: her sleeves are rolled to
 * the elbow, so each arm already breaks where the green sleeve ends and the bare forearm starts
 * (both curves end on the elbow, no cut needed); the towel hangs from her left hand, the glass
 * (or the cup, or the key) rides upright in her right. In front, her left arm comes apart so the
 * towel she dries with hangs behind the glass and the one over her shoulder lies on the sleeve.
 * The three tufts and the gold hoops turn with the head. */
import React from 'react';
import { margaux as rig } from '../../rigs/margaux';
import type { Brow } from '../../rig-kit';
import type { ArmDef, ExpressionDef, FaceDef, FaceValues, FigureDef, GestureDef, GestureId, ExpressionId, Side } from '../kit';
import { ArmLayer, Body, EyeSet, Faces, HandShapes, Head, Mouths, Part, Place, RestHand, Resting, Shown, Sway } from '../parts';

const SKIN = '#cf946a';
const SHADE = '#a96f47';
const SHIRT = '#2c6a5d';
const COLLAR = '#1f4f45';
const APRON = '#2a231c';
const HAIR = '#dcd6c8';
const BRASS = '#c49a0a';
const CREAM = '#f8f3e8';
const RED = '#d8321a';

const ARMS: Record<Side, ArmDef> = {
  L: { shoulder: [72, 240], elbow: [66, 292], palm: [95, 281], r: 8 },
  R: { shoulder: [128, 240], elbow: [138, 290], palm: [126, 318], r: 8 },
};

// the rig's mood brows
const B = {
  neutre: [[-26, -22, -16, -25, -7, -22], [7, -27, 17, -35, 27, -29]] as [Brow, Brow],
  ravie: [[-26, -26, -16, -31, -7, -27], [7, -28, 17, -34, 27, -28]] as [Brow, Brow],
  surprise: [[-26, -30, -16, -37, -7, -32], [7, -32, 17, -38, 27, -30]] as [Brow, Brow],
  fachee: [[-26, -27, -16, -25, -7, -19], [7, -19, 17, -25, 27, -27]] as [Brow, Brow],
  emue: [[-26, -20, -16, -23, -7, -28], [7, -28, 17, -23, 27, -20]] as [Brow, Brow],
};

const EXPRESSIONS: Record<ExpressionId, ExpressionDef> = {
  neutre: { label: 'Neutre', note: 'le visage du rig', eyes: ['wry', 'wry'], brows: B.neutre, mouth: 'smirk', tilt: -4 },
  joie: {
    label: 'Contente',
    note: 'les yeux plissés, le sourire fermé : jamais de dents',
    eyes: ['happy', 'happy'],
    brows: [[-26, -25, -16, -30, -7, -26], [7, -28, 17, -35, 27, -30]],
    mouth: 'smile',
    tilt: 4,
  },
  malice: {
    label: 'Oracle',
    note: 'paupières lourdes, le sourcil qui sait, le coin de la bouche',
    eyes: ['heavy', 'heavy'],
    brows: [[-26, -20, -16, -21, -7, -19], [7, -31, 17, -41, 27, -33]],
    mouth: 'smirk',
    tilt: -7,
    dx: -1,
    gaze: [-1, 0],
  },
  fier: {
    label: 'Évidemment',
    note: 'les yeux fermés, le sourire en coin, le menton haut',
    eyes: ['shut', 'shut'],
    brows: [[-26, -25, -16, -29, -7, -26], [7, -29, 17, -37, 27, -31]],
    mouth: 'smirk',
    tilt: -6,
    dy: -2,
  },
  surprise: {
    label: 'Tiens donc.',
    note: 'les sourcils seulement ; le reste ne bouge pas',
    eyes: ['wry', 'wry'],
    brows: [[-26, -31, -16, -39, -7, -34], [7, -36, 17, -45, 27, -38]],
    mouth: 'smirk',
    tilt: -4,
    dy: -1,
  },
  panique: {
    label: 'Le coup de feu',
    note: 'tout le monde commande en même temps : les yeux qui courent, une goutte',
    eyes: ['wide', 'wide'],
    brows: [[-26, -26, -16, -32, -7, -34], [7, -34, 17, -36, 27, -30]],
    mouth: 'wobble',
    tilt: -2,
    gaze: [-3.5, 0],
    fx: ['sweat'],
  },
  fache: {
    label: 'Non.',
    note: 'un sourcil en bas, l’autre en haut, la bouche pincée',
    eyes: ['cross', 'level'],
    brows: [[-26, -27, -16, -25, -7, -17], [7, -30, 17, -38, 27, -33]],
    mouth: 'frown',
    tilt: -1,
    dy: 2,
    gaze: [0, -1.5],
  },
  emu: {
    label: 'Émue',
    note: 'les yeux en l’air, brillants, le sourire doux (portrait)',
    eyes: ['sparkle', 'sparkle'],
    brows: B.emue,
    mouth: 'soft',
    tilt: -7,
    gaze: [1, -4],
  },
  amour: {
    label: 'Tendresse',
    note: 'les yeux fondent, les joues prennent des couleurs',
    eyes: ['sparkle', 'sparkle'],
    brows: [[-26, -22, -16, -26, -7, -26], [7, -26, 17, -29, 27, -24]],
    mouth: 'soft',
    tilt: 5,
    gaze: [-0.5, 0.5],
    fx: ['blush'],
  },
  fatigue: {
    label: 'Fermeture',
    note: 'la fin du service : un œil déjà fermé, l’autre qui tombe, les épaules aussi',
    eyes: ['shut', 'down'],
    brows: [[-26, -19, -16, -21, -7, -22], [7, -23, 17, -26, 27, -21]],
    mouth: 'flat',
    tilt: -8,
    dy: 3,
    pose: { at: 0, bodyY: 2, body: -0.8 },
  },
};

/* Where the draped towel sits, from the towel in her hand at rest: lifted onto the left shoulder. */
const DRAPE: [number, number] = [-2, -91];
/** the draped towel's offset when it is exactly the towel in a hand at `p` */
const inHand = (p: [number, number]) => ({ x: p[0] - ARMS.R.palm[0] - DRAPE[0], y: p[1] - ARMS.R.palm[1] - DRAPE[1] });

/* Where she dries: the glass a little lower, the towel hand across from her side. */
const DRY = { L: { to: [100, 296] as [number, number] } };
const wipe = (x: number, y: number) => ({ to: [x, y] as [number, number] });
/* On its way to the raised index the forearm comes up on the outside, foreshortened, never
 * across the glass (her upper arm is long, her forearm short: a hand near the face needs this). */
const RISE = { to: [152, 280] as [number, number], reach: 0.8, tuck: true };

/* She says her line once, early, then holds the look without a word: a gesture's face talks,
 * its `then` is the same face, silent. */
const said = (f: FaceDef): FaceDef => ({ ...f, talk: true });

const BROW_UP: [Brow, Brow] = [[-26, -22, -16, -25, -7, -22], [7, -32, 17, -42, 27, -34]];
const F_SALUT: FaceDef = { eyes: ['wry', 'wry'], brows: BROW_UP, mouth: 'smirk', tilt: -4 };
const F_BOIS: FaceDef = { eyes: ['happy', 'happy'], brows: [[-26, -25, -16, -30, -7, -26], [7, -30, 17, -37, 27, -31]], mouth: 'smile', tilt: -2 };
const F_SOURDE: FaceDef = { eyes: ['level', 'level'], brows: [[-26, -22, -16, -25, -7, -22], [7, -34, 17, -44, 27, -36]], mouth: 'tight', tilt: -2, dx: 1, gaze: [4, -2.5] };
const F_ECOUTE: FaceDef = { eyes: ['heavy', 'heavy'], brows: [[-26, -21, -16, -23, -7, -21], [7, -32, 17, -42, 27, -34]], mouth: 'smirk', tilt: -6, gaze: [-1, 0] };
const F_TIENS: FaceDef = { eyes: ['wry', 'wry'], brows: [[-26, -23, -16, -27, -7, -24], [7, -30, 17, -39, 27, -32]], mouth: 'smile', tilt: -3, gaze: [0, 1] };
const F_LUMIERE: FaceDef = { eyes: ['level', 'wry'], brows: BROW_UP, mouth: 'smirk', tilt: -5, gaze: [-3.5, 4] };

const GESTURES: Record<GestureId, GestureDef> = {
  salut: {
    label: 'Salut.',
    line: 'Salut.',
    note: 'un signe de tête, puis le torchon sur l’épaule : elle est à toi',
    seconds: 4,
    face: said(F_SALUT),
    then: [0.3, { ...F_SALUT, eyes: ['heavy', 'wry'], brows: [[-26, -21, -16, -23, -7, -21], [7, -35, 17, -45, 27, -37]] }],
    front: ['R'],
    hide: { torchon: [0.46, 0.96] },
    show: { epaule: [0.46, 0.96] },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.12, ease: 'ease-in-out', head: 1, headY: 2.5 },
      { at: 0.24, ease: 'ease-in-out' },
      { at: 0.4, ease: 'ease-in', R: { to: [126, 264] } },
      { at: 0.46, ease: 'ease-out', R: { to: [124, 260] }, parts: { epaule: inHand([124, 260]) } },
      { at: 0.51, ease: 'ease-out', R: { to: [126, 278] }, parts: { epaule: { x: 3, y: -8, r: -24 } } },
      { at: 0.56, ease: 'ease-in-out', R: { to: [126, 304] }, parts: { epaule: { x: 0, y: 0, r: 0 } } },
      { at: 0.64, ease: 'ease-in-out', R: { to: [126, 318] } },
      { at: 0.8, ease: 'ease-in-out', R: { to: [126, 318] } },
      { at: 0.88, ease: 'ease-in-out', R: { to: [126, 264] }, parts: { epaule: { x: 0, y: 0 } } },
      { at: 0.96, R: { to: [126, 318] }, parts: { epaule: inHand([126, 318]) } },
      { at: 1 },
    ],
    peak: 7,
  },
  bravo: {
    label: 'Bois.',
    line: 'Bois.',
    note: 'elle pousse le café crème vers toi, c’est sa façon de dire bravo',
    seconds: 3.6,
    face: said(F_BOIS),
    then: [0.24, F_BOIS],
    hide: { verre: [0.1, 0.86] },
    show: { tasse: [0.1, 0.86] },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.1, ease: 'ease-out', L: { to: [96, 318] } },
      { at: 0.32, ease: 'ease-in-out', L: { to: [106, 298], reach: 1.32 }, bodyY: 1.5 },
      { at: 0.44, ease: 'ease-in-out', L: { to: [106, 298], reach: 1.32 }, head: 1, headY: 2, bodyY: 1.5 },
      { at: 0.56, ease: 'ease-in-out', L: { to: [106, 298], reach: 1.32 }, bodyY: 1.5 },
      { at: 0.74, ease: 'ease-in-out', L: { to: [106, 298], reach: 1.32 }, bodyY: 1.5 },
      { at: 0.86, ease: 'ease-in-out', L: { to: [96, 318] } },
      { at: 1 },
    ],
    peak: 3,
  },
  oups: {
    label: 'J’ai rien entendu.',
    line: 'J’ai rien entendu.',
    note: 'elle continue d’essuyer, les yeux ailleurs, un sourcil en l’air, et sifflote',
    seconds: 3.8,
    face: said(F_SOURDE),
    then: [0.42, { ...F_SOURDE, mouth: 'whistle' }],
    front: ['L', 'R'],
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.14, ease: 'ease-in-out', ...DRY, R: wipe(108, 264), head: 2, headX: 1 },
      { at: 0.26, ease: 'ease-in-out', ...DRY, R: wipe(105, 258), head: 2, headX: 1 },
      { at: 0.38, ease: 'ease-in-out', ...DRY, R: wipe(109, 255), head: 2, headX: 1 },
      { at: 0.5, ease: 'ease-in-out', ...DRY, R: wipe(111, 261), head: 2, headX: 1 },
      { at: 0.62, ease: 'ease-in-out', ...DRY, R: wipe(106, 265), head: 2, headX: 1 },
      { at: 0.74, ease: 'ease-in-out', ...DRY, R: wipe(109, 258), head: 2, headX: 1 },
      { at: 0.88 },
      { at: 1 },
    ],
    peak: 4,
  },
  reflechit: {
    label: 'Écoute.',
    line: 'Écoute.',
    note: 'l’index levé, les paupières lourdes : la leçon de la patronne',
    seconds: 3.6,
    face: said(F_ECOUTE),
    then: [0.38, F_ECOUTE],
    hands: { R: 'point' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'ease-in' },
      { at: 0.1, ease: 'ease-out', R: RISE },
      { at: 0.22, ease: 'ease-in-out', R: { to: [148, 248], tuck: true, reach: 1.3, h: -6 } },
      { at: 0.4, ease: 'ease-in-out', R: { to: [148, 246], tuck: true, reach: 1.3, h: -12 } },
      { at: 0.48, ease: 'ease-in-out', R: { to: [148, 248], tuck: true, reach: 1.3, h: -4 } },
      { at: 0.78, ease: 'ease-in', R: { to: [148, 248], tuck: true, reach: 1.3, h: -6 } },
      { at: 0.86, ease: 'ease-out', R: RISE },
      { at: 0.94 },
      { at: 1 },
    ],
    peak: 4,
  },
  montre: {
    label: 'Tiens.',
    line: 'Tiens.',
    note: 'la clé à la cigale sort de la poche du tablier',
    seconds: 3.6,
    face: said(F_TIENS),
    then: [0.26, F_TIENS],
    front: ['L'],
    hide: { verre: [0.14, 0.86] },
    show: { cle: [0.14, 0.86] },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.14, ease: 'ease-out', L: { to: [92, 322] } },
      { at: 0.34, ease: 'ease-in-out', L: { to: [106, 270], reach: 1.3 }, parts: { cigale: { r: 22 } } },
      { at: 0.43, ease: 'ease-in-out', L: { to: [106, 270], reach: 1.3 }, parts: { cigale: { r: -14 } } },
      { at: 0.52, ease: 'ease-in-out', L: { to: [106, 270], reach: 1.3 }, parts: { cigale: { r: 8 } } },
      { at: 0.6, ease: 'ease-in-out', L: { to: [106, 270], reach: 1.3 }, parts: { cigale: { r: -3 } } },
      { at: 0.74, ease: 'ease-in-out', L: { to: [106, 270], reach: 1.3 }, parts: { cigale: { r: 0 } } },
      { at: 0.86, ease: 'ease-in-out', L: { to: [92, 322] } },
      { at: 1 },
    ],
    peak: 4,
  },
  signature: {
    label: 'Le verre sec',
    line: 'Hm.',
    note: 'le verre sous le nez : impeccable ; elle l’essuie quand même, en te regardant',
    seconds: 4.6,
    face: F_LUMIERE,
    then: [0.4, 'malice'],
    front: ['L', 'R'],
    show: { eclat: [0.16, 0.34] },
    keys: [
      { at: 0, ease: 'ease-in-out' },
      { at: 0.14, ease: 'ease-in-out', L: { to: [88, 260], reach: 1.2 }, head: -1, headY: 1 },
      { at: 0.32, ease: 'ease-in-out', L: { to: [89, 258], reach: 1.2 }, head: -1, headY: 1 },
      { at: 0.44, ease: 'ease-in-out', ...DRY, R: wipe(108, 265) },
      { at: 0.54, ease: 'ease-in-out', ...DRY, R: wipe(105, 259) },
      { at: 0.64, ease: 'ease-in-out', ...DRY, R: wipe(109, 255) },
      { at: 0.74, ease: 'ease-in-out', ...DRY, R: wipe(111, 261) },
      { at: 0.84, ease: 'ease-in-out', ...DRY, R: wipe(107, 266) },
      { at: 1 },
    ],
    peak: 2,
  },
};

/* The glass, the cup and the key, as the rig draws them in her right hand (the viewer's left). */
const GLASS = (
  <g>
    <path d="M84,236 Q84,260 95,261 Q106,260 106,236 Z" fill={CREAM} />
    <path d="M87.5,240 Q88.5,253 92.5,257 L90.5,257 Q86.5,251 86.5,240 Z" fill="#1d3a8a" />
    <path d="M94.2,261 L95.8,261 L95.8,276 L94.2,276 Z" fill={CREAM} />
    <Shown id="eclat">
      <path d="M103,229 Q104,236 111,237 Q104,238 103,245 Q102,238 95,237 Q102,236 103,229 Z" fill="#f3c318" />
      <circle cx="103" cy="237" r="1.6" fill="#ffffff" />
    </Shown>
  </g>
);

const CUP = (
  <g>
    <path d="M80,268 Q95,263 110,268 Q95,273 80,268 Z" fill={CREAM} />
    <circle cx="108" cy="254" r="4.5" fill="none" stroke={CREAM} strokeWidth={3} />
    <path d="M84,246 L106,246 L104,262 Q95,267 86,262 Z" fill={CREAM} />
    <path d="M84,246 Q95,242.5 106,246 Q95,249.5 84,246 Z" fill="#b07a4e" />
  </g>
);

const KEY = (
  <g>
    <circle cx="96" cy="244" r="9" fill="none" stroke={BRASS} strokeWidth={4} />
    <path d="M94.3,253 L97.7,253 L97.7,298 L94.3,298 Z M97.7,289 L103,289 L103,293 L97.7,293 Z M97.7,294.5 L102,294.5 L102,298 L97.7,298 Z" fill={BRASS} />
    <Part id="cigale" at={[106.3, 249]}>
      <circle cx="108.5" cy="250" r="2.4" fill="none" stroke={BRASS} strokeWidth={1.5} />
      <path d="M110.5,255 L104,268 L109.5,266.5 Z M113.5,255 L120,268 L114.5,266.5 Z" fill="#f3c318" />
      <path d="M112,253 C115.5,253 117,259 114.6,266.5 C113.9,268.8 110.1,268.8 109.4,266.5 C107,259 108.5,253 112,253 Z" fill={SHIRT} />
    </Part>
  </g>
);

/* The towel, hanging from her left hand. */
const TOWEL = (
  <g>
    <path d="M116,316 L138,314 L141,356 L119,358 Z" fill={CREAM} />
    <path d="M122,316 L125,316 L125,357 L122,357 Z M129,315 L131.5,315 L132.5,356 L130,356 Z" fill={RED} />
  </g>
);

/* The same towel thrown over her shoulder: the flap on her chest, the fold going over the top. */
const DRAPED = (
  <g transform={`translate(${DRAPE[0]} ${DRAPE[1]})`}>
    {TOWEL}
    <path d="M116,316 Q126,303 138,314 Z" fill="#e6dfcf" />
    <path d="M122,316 Q123.5,312 125,311 L125,316 Z M129,315 L129,309.5 Q130.5,310 131.5,311 L131.5,315 Z" fill={RED} opacity={0.8} />
  </g>
);

function Features({ f }: { f: FaceValues }) {
  return (
    <>
      <EyeSet e={f.eL} skin={SKIN} lidLine={2.4} arcLine={4.2} />
      <EyeSet e={f.eR} skin={SKIN} lidLine={2.4} arcLine={4.2} />
      <path d={f.browL} fill="none" stroke="#6e675b" strokeWidth={5} strokeLinecap="round" />
      <path d={f.browR} fill="none" stroke="#6e675b" strokeWidth={5} strokeLinecap="round" />
      <path d="M1,-4 C5,-2 10,12 8,17 C6,21 -2,21 -3,17 C-4,12 -2,-2 1,-4 Z" fill={SHADE} />
      <Mouths mouths={f.mouths} transform="translate(-3.4 4.8) scale(1.7)" />
    </>
  );
}

function Hand({ side }: { side: Side }) {
  const a = ARMS[side];
  return (
    <>
      <RestHand side={side}>
        <circle cx={a.palm[0]} cy={a.palm[1]} r="8" fill={SKIN} />
      </RestHand>
      <HandShapes side={side} at={a.palm} r={8} skin={SKIN} shade={SHADE} />
    </>
  );
}

/* Her left arm (the viewer's right): green sleeve to the elbow, bare forearm, the towel. Behind,
 * in the rig's order. In front it comes apart: the towel she throws over her shoulder lies on
 * the sleeve, the towel in her hand hangs behind the forearm and behind the glass she dries, and
 * the hand comes last (`under` is drawn before the other arm's front copy, `over` after it). */
const R_SLEEVE = <path d="M128,240 Q142,266 138,290" fill="none" stroke={SHIRT} strokeWidth={13} strokeLinecap="round" />;
const R_FORE = <path d="M138,290 Q136,306 128,314" fill="none" stroke={SKIN} strokeWidth={10} strokeLinecap="round" />;
const R_TOWEL = <Resting id="torchon">{TOWEL}</Resting>;

function ArmR({ place }: { place: 'back' | 'under' | 'over' }) {
  if (place === 'back') {
    return (
      <Place side="R" place="back">
        <ArmLayer side="R" arm={ARMS.R} upper={R_SLEEVE} fore={R_FORE} held={R_TOWEL} hand={<Hand side="R" />} />
      </Place>
    );
  }
  if (place === 'under') {
    return (
      <Place side="R" place="front">
        <ArmLayer side="R" arm={ARMS.R} upper={R_SLEEVE} />
        <Shown id="epaule">
          <Part id="epaule" at={[125, 224]}>
            {DRAPED}
          </Part>
        </Shown>
        <ArmLayer side="R" arm={ARMS.R} held={R_TOWEL} />
      </Place>
    );
  }
  return (
    <Place side="R" place="front">
      <ArmLayer side="R" arm={ARMS.R} fore={R_FORE} hand={<Hand side="R" />} />
    </Place>
  );
}

/* Her right arm (the viewer's left), with whatever she is holding. */
function ArmL({ place }: { place: 'back' | 'front' }) {
  return (
    <Place side="L" place={place}>
      <ArmLayer
        side="L"
        arm={ARMS.L}
        upper={<path d="M72,240 Q58,270 66,292" fill="none" stroke={SHIRT} strokeWidth={13} strokeLinecap="round" />}
        fore={<path d="M66,292 Q80,294 92,284" fill="none" stroke={SKIN} strokeWidth={10} strokeLinecap="round" />}
        held={
          <>
            <Resting id="verre">{GLASS}</Resting>
            <Shown id="tasse">{CUP}</Shown>
            <Shown id="cle">{KEY}</Shown>
          </>
        }
        hand={<Hand side="L" />}
      />
    </Place>
  );
}

function MargauxArt({ faces, base }: { faces: Array<{ id: string; values: FaceValues }>; base: ExpressionId }) {
  return (
    <g>
      <path d="M90,366 L89,394 M110,366 L111,394" fill="none" stroke="#14285f" strokeWidth={12} strokeLinecap="round" />
      <ellipse cx="86" cy="401" rx="12" ry="6" fill="#14110d" />
      <ellipse cx="114" cy="401" rx="12" ry="6" fill="#14110d" />
      <Body fig={margaux}>
        <path d="M92,196 L108,196 L108,232 L92,232 Z" fill={SKIN} />
        <path d="M70,236 Q70,226 82,226 L118,226 Q130,226 130,236 L134,330 Q134,340 124,340 L76,340 Q66,340 66,330 Z" fill={SHIRT} />
        <path d="M90,226 L100,242 L110,226 Z" fill={SKIN} />
        <path d="M88,226 L81,230 L96,250 L100,242 Z M112,226 L119,230 L104,250 L100,242 Z" fill={COLLAR} />
        <path d="M78,256 Q78,250 84,250 L116,250 Q122,250 122,256 L126,364 Q126,370 120,370 L80,370 Q74,370 74,364 Z" fill={APRON} />
        <path d="M81,252 L86,252 L92,228 L87,228 Z M114,252 L119,252 L113,228 L108,228 Z" fill={APRON} />
        <circle cx="83.5" cy="253" r="3.4" fill={BRASS} />
        <circle cx="116.5" cy="253" r="3.4" fill={BRASS} />
        <ArmR place="back" />
        <ArmL place="back" />
        <Head fig={margaux} base={base}>
          <path d="M-46,-14 C-50,-56 -22,-84 8,-82 C40,-80 54,-56 48,-14 L30,-34 L-30,-34 Z" fill={HAIR} />
          <Sway at={[-1, -76]} deg={1.2} seconds={3.6}>
            <path d="M-10,-76 C-4,-96 16,-100 26,-92 C16,-90 10,-84 8,-76 Z" fill={HAIR} />
          </Sway>
          <Sway at={[26, -67]} deg={1.6} seconds={3.1} delay={-1.2}>
            <path d="M18,-72 C30,-88 48,-86 52,-74 C44,-75 38,-71 33,-64 Z" fill={HAIR} />
          </Sway>
          <Sway at={[-23, -68]} deg={1.4} seconds={3.4} delay={-2.1}>
            <path d="M-28,-66 C-32,-80 -22,-88 -14,-86 C-19,-82 -20,-76 -18,-70 Z" fill={HAIR} />
          </Sway>
          <ellipse cx="-41" cy="0" rx="7.5" ry="11" fill={SKIN} />
          <ellipse cx="42" cy="0" rx="7.5" ry="11" fill={SKIN} />
          <path d="M-40,-30 C-40,-62 -22,-70 0,-70 C24,-70 42,-62 42,-30 L42,8 C42,36 22,58 2,58 C-18,58 -40,36 -40,8 Z" fill={SKIN} />
          <Sway at={[-42, 10.5]} deg={5} seconds={2.8}>
            <circle cx="-42" cy="15" r="4.5" fill="none" stroke={BRASS} strokeWidth={2.4} />
          </Sway>
          <Sway at={[43, 10.5]} deg={5} seconds={2.8} delay={-1.3}>
            <circle cx="43" cy="15" r="4.5" fill="none" stroke={BRASS} strokeWidth={2.4} />
          </Sway>
          <path d="M-42,-24 C-44,-58 -16,-78 10,-76 C34,-76 50,-60 48,-34 C40,-46 28,-50 16,-48 C6,-40 -12,-44 -24,-38 C-34,-36 -40,-30 -42,-24 Z" fill={HAIR} />
          <path d="M-26,-62 C-12,-72 8,-74 24,-68 C8,-68 -6,-64 -18,-56 Z M26,-58 C36,-56 44,-48 46,-40 C40,-46 34,-50 26,-52 Z" fill="#a59e8f" />
          <path d="M-30,-4 L-35,-7 M-30,2 L-35,3 M31,-4 L36,-7 M31,2 L36,3 M-32,12 Q-27,20 -21,23 M33,12 Q28,20 22,23" fill="none" stroke={SHADE} strokeWidth={2} strokeLinecap="round" />
          <Faces faces={faces} fig={margaux}>
            {(f) => <Features f={f} />}
          </Faces>
        </Head>
        <ArmR place="under" />
        <ArmL place="front" />
        <ArmR place="over" />
      </Body>
    </g>
  );
}

export const margaux: FigureDef = {
  key: 'margaux',
  name: 'Margaux',
  rig,
  arms: ARMS,
  hips: [100, 366],
  neck: [100, 204],
  skin: SKIN,
  shade: SHADE,
  blink: 5.2,
  idle: { kind: 'bob', seconds: 4.2, amount: 1.6 },
  parts: { cigale: [106.3, 249], epaule: [125, 224] },
  expressions: EXPRESSIONS,
  gestures: GESTURES,
  fx: { cheekL: [-24, 14], cheekR: [25, 14], temple: [34, -26], crown: [4, -96], side: [62, -52], eyeL: [-16, -6], eyeR: [16, -6] },
  Art: MargauxArt,
};
