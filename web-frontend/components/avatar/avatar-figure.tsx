/* Ton personnage · the learner's character as a jointed figure of la troupe vivante.
 *
 * Acting sheet. The learner is the one person in the troupe who is everyone: no tics of their
 * own, open and warm, a little proud of what they made of themselves. They wave hello, give a
 * thumbs-up, shrug off a slip, think with a fist under the chin, hold out a hand (where the
 * season's objects will land), and «Ta-da !» with both arms up when they are done dressing.
 *
 * Built per record: the body is one drawing (Romy's proportions, hands at the sides) and every
 * part comes from `avatar-art.tsx`. The joints and the motion are the kit's, so it plays exactly
 * like the cast and stops for Reduce Motion. Every record draws as the same figure key (`moi`):
 * the motion never depends on the clothes, so several characters share a page's stylesheet.
 */
import React from 'react';

import type { Brow, EyeParams, RigDef } from '@/components/cast/rig-kit';
import type { ArmDef, ExpressionDef, ExpressionId, FaceValues, FigureDef, GestureDef, GestureId, Side } from '@/components/cast/vivant/kit';
import { ArmLayer, BehindHead, Body, EyeSet, Faces, HandShapes, Head, Mouths, Place, RestHand } from '@/components/cast/vivant/parts';
import type { AvatarConfig } from '@/lib/avatar';
import { DEFAULT_AVATAR, deeper } from '@/lib/avatar';

import type { Look } from './avatar-art';
import {
  BeardOver,
  BeardUnder,
  Earpieces,
  Ears,
  Face,
  Glasses,
  HairBack,
  HairBehind,
  HairFront,
  Hat,
  Legs,
  Neckpiece,
  Pin,
  Wristpiece,
  garmentOf,
  lookOf,
} from './avatar-art';

export const AVATAR_KEY = 'moi';

const ARMS: Record<Side, ArmDef> = {
  L: { shoulder: [62, 238], elbow: [51, 276], palm: [57, 314], r: 8 },
  R: { shoulder: [138, 238], elbow: [149, 276], palm: [143, 314], r: 8 },
};

export const EYES: Record<string, EyeParams> = {
  ronds: { rx: 10.4, ry: 12, pr: 6.4, iris: true },
  amande: { rx: 11.6, ry: 7.4, pr: 5.2, iris: true },
  petits: { rx: 7, ry: 7.8, pr: 4.6, iris: true },
};

export const BROW_WIDTH: Record<string, number> = { fins: 3.2, naturels: 4.6, epais: 6.6 };

/** The nose, in the head frame. */
export const NOSE = 'M0,-1 C3,2 5,10 4,13 C2,15.5 -2,15.5 -4,13 C-5,10 -3,2 0,-1 Z';

const B = {
  neutre: [[-24, -21, -15, -26, -6, -22], [6, -22, 15, -26, 24, -21]] as [Brow, Brow],
  ravie: [[-24, -24, -15, -29, -6, -25], [6, -25, 15, -29, 24, -24]] as [Brow, Brow],
  haut: [[-24, -29, -15, -36, -6, -30], [6, -30, 15, -36, 24, -29]] as [Brow, Brow],
  fache: [[-24, -25, -15, -22, -6, -14], [6, -14, 15, -22, 24, -25]] as [Brow, Brow],
  emue: [[-24, -18, -15, -21, -6, -25], [6, -25, 15, -21, 24, -18]] as [Brow, Brow],
};

const EXPRESSIONS: Record<ExpressionId, ExpressionDef> = {
  neutre: { label: 'Toi', note: 'ouvert, prêt', eyes: ['open', 'open'], brows: B.neutre, mouth: 'smile' },
  joie: { label: 'Ravi·e', note: 'le grand rire, le menton qui monte', eyes: ['happy', 'happy'], brows: B.ravie, mouth: 'laugh', tilt: -4, dy: -2 },
  malice: {
    label: 'Malin·e',
    note: 'un œil plissé, un sourcil levé',
    eyes: ['level', 'open'],
    brows: [[-24, -19, -15, -22, -6, -19], [6, -29, 15, -36, 24, -31]],
    mouth: 'smirk',
    tilt: 6,
    dx: 2,
    gaze: [3.5, 0],
  },
  fier: {
    label: 'Fier·e',
    note: 'paupières mi-closes, sourire fermé, menton haut',
    eyes: ['smug', 'smug'],
    brows: [[-24, -23, -15, -28, -6, -24], [6, -24, 15, -28, 24, -23]],
    mouth: 'smile',
    tilt: -6,
    dy: -3,
  },
  surprise: { label: 'Oh !', note: 'les yeux grands, la bouche ronde', eyes: ['wide', 'wide'], brows: B.haut, mouth: 'bigO', dy: -2, fx: ['shock'] },
  panique: {
    label: 'Aïe',
    note: 'pupilles minuscules, dents serrées, une goutte',
    eyes: ['tiny', 'tiny'],
    brows: [[-24, -24, -15, -30, -6, -32], [6, -32, 15, -30, 24, -24]],
    mouth: 'grimace',
    tilt: 3,
    fx: ['sweat'],
  },
  fache: { label: 'Grr', note: 'bouche pincée, menton baissé', eyes: ['cross', 'cross'], brows: B.fache, mouth: 'tight', dy: 3, gaze: [0, -1.5] },
  emu: {
    label: 'Ému·e',
    note: 'une larme, le poing sous le menton',
    eyes: ['sad', 'sad'],
    brows: B.emue,
    mouth: 'soft',
    tilt: 6,
    pose: { at: 0, R: { to: [104, 206], tuck: true, h: -10 }, head: 4 },
    hands: { R: 'fist' },
    front: ['R'],
  },
  amour: {
    label: 'Attendri·e',
    note: 'les yeux fondent, les joues rosissent',
    eyes: ['happy', 'happy'],
    brows: [[-24, -21, -15, -26, -6, -27], [6, -27, 15, -26, 24, -21]],
    mouth: 'soft',
    tilt: 8,
    fx: ['blush', 'hearts'],
  },
  fatigue: {
    label: 'Crevé·e',
    note: 'paupières lourdes, la tête qui tombe',
    eyes: ['down', 'down'],
    brows: [[-24, -18, -15, -20, -6, -21], [6, -21, 15, -20, 24, -18]],
    mouth: 'flat',
    tilt: 9,
    dy: 3,
    fx: ['zzz'],
  },
};

const GESTURES: Record<GestureId, GestureDef> = {
  salut: {
    label: 'Salut !',
    line: 'Salut !',
    note: 'la main levée qui balance',
    seconds: 2.4,
    face: 'joie',
    talk: true,
    hands: { R: 'open' },
    keys: [
      { at: 0, ease: 'cubic-bezier(.2,.8,.3,1)' },
      { at: 0.16, ease: 'ease-in-out', R: { to: [156, 170], h: -16 }, head: -3 },
      { at: 0.3, ease: 'ease-in-out', R: { to: [158, 168], h: 18 }, head: -3 },
      { at: 0.44, ease: 'ease-in-out', R: { to: [156, 170], h: -16 }, head: -2 },
      { at: 0.58, ease: 'ease-in-out', R: { to: [158, 168], h: 18 }, head: -3 },
      { at: 0.72, ease: 'ease-in-out', R: { to: [156, 170], h: -4 }, head: -2 },
      { at: 0.88 },
      { at: 1 },
    ],
    peak: 2,
  },
  bravo: {
    label: 'Bien joué !',
    line: 'Bien joué !',
    note: 'le pouce levé, un petit rebond',
    seconds: 2.2,
    face: 'joie',
    talk: true,
    hands: { R: 'thumb' },
    front: ['R'],
    keys: [
      { at: 0, ease: 'cubic-bezier(.2,.9,.3,1.2)' },
      { at: 0.16, ease: 'ease-in-out', R: { to: [152, 236], h: -6 }, bodyY: -2 },
      { at: 0.32, ease: 'ease-in-out', R: { to: [150, 228], h: 0 }, head: 4, bodyY: -1 },
      { at: 0.48, ease: 'ease-in-out', R: { to: [152, 236], h: -6 }, head: 0 },
      { at: 0.62, ease: 'ease-in-out', R: { to: [150, 230], h: 0 }, head: 3 },
      { at: 0.82 },
      { at: 1 },
    ],
    peak: 2,
  },
  oups: {
    label: 'Oups…',
    line: 'Oups… on recommence.',
    note: 'les épaules qui montent, les paumes ouvertes',
    seconds: 2.6,
    face: { eyes: ['open', 'squeeze'], brows: [[-24, -27, -15, -32, -6, -30], [6, -30, 15, -32, 24, -27]], mouth: 'teeth', tilt: 7 },
    then: [0.56, 'malice'],
    hands: { L: 'open', R: 'open' },
    keys: [
      { at: 0, ease: 'cubic-bezier(.25,.9,.3,1)' },
      { at: 0.18, ease: 'ease-in-out', L: { to: [34, 286], h: -64 }, R: { to: [166, 286], h: 64 }, bodyY: -3, head: 6 },
      { at: 0.4, ease: 'ease-in-out', L: { to: [36, 282], h: -60 }, R: { to: [164, 282], h: 60 }, bodyY: -4, head: 8 },
      { at: 0.62, ease: 'ease-in-out', L: { to: [36, 286], h: -64 }, R: { to: [164, 286], h: 64 }, bodyY: -2, head: 6 },
      { at: 0.84 },
      { at: 1 },
    ],
    peak: 2,
  },
  reflechit: {
    label: 'Voyons…',
    line: 'Voyons voir…',
    note: 'le poing sous le menton, les yeux en l’air',
    seconds: 3,
    face: { eyes: ['open', 'open'], brows: [[-24, -25, -15, -30, -6, -26], [6, -21, 15, -24, 24, -20]], mouth: 'pout', tilt: 5, gaze: [-3.5, -3.5] },
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
    label: 'Tiens !',
    line: 'Tiens, regarde.',
    note: 'la main tendue vers toi, la paume ouverte',
    seconds: 2.6,
    face: { eyes: ['open', 'open'], brows: B.ravie, mouth: 'smileOpen', tilt: 4 },
    talk: true,
    hands: { R: 'open' },
    keys: [
      { at: 0, ease: 'cubic-bezier(.2,.9,.3,1.1)' },
      { at: 0.16, ease: 'ease-out', R: { to: [138, 266], reach: 1.2, h: 8 }, head: 3, body: 1.5 },
      { at: 0.3, ease: 'ease-in-out', R: { to: [136, 260], reach: 1.3, h: 10 }, head: 4, body: 2.5 },
      { at: 0.7, ease: 'ease-in-out', R: { to: [136, 262], reach: 1.28, h: 9 }, head: 4, body: 2.5 },
      { at: 0.86 },
      { at: 1 },
    ],
    peak: 2,
  },
  signature: {
    label: 'Ta-da !',
    line: 'Ta-da ! C’est moi.',
    note: 'les deux bras en l’air, un saut sur place',
    seconds: 2.8,
    face: 'joie',
    talk: true,
    hands: { L: 'open', R: 'open' },
    keys: [
      { at: 0, ease: 'cubic-bezier(.2,.8,.3,1)' },
      { at: 0.14, ease: 'ease-in', L: { to: [46, 270], h: -150 }, R: { to: [154, 270], h: 150 }, bodyY: 2 },
      { at: 0.3, ease: 'cubic-bezier(.3,1.6,.5,1)', L: { to: [30, 192], h: -36 }, R: { to: [170, 192], h: 36 }, bodyY: -6, head: -2 },
      { at: 0.52, ease: 'ease-in-out', L: { to: [32, 196], h: -40 }, R: { to: [168, 196], h: 40 }, bodyY: -2 },
      { at: 0.72, ease: 'ease-in-out', L: { to: [32, 194], h: -38 }, R: { to: [168, 194], h: 38 }, bodyY: -1, head: 3 },
      { at: 0.88 },
      { at: 1 },
    ],
    peak: 2,
  },
};

/** The eye states the lashes show over. */
export const LASHED = new Set(['open', 'wide', 'tiny', 'sparkle']);
export function lash(c: [number, number], side: -1 | 1, ry: number): string {
  return `M${c[0] - 10.5},${c[1] + 8.5 - ry} Q${c[0]},${c[1] - 3.5 - ry} ${c[0] + 10.5},${c[1] + 8.5 - ry} M${c[0] + side * 10},${c[1] + 7.5 - ry} L${c[0] + side * 14},${c[1] + 5 - ry}`;
}

function Features({ f, look, eye }: { f: FaceValues; look: Look; eye: EyeParams }) {
  const { tone, hair, iris, cfg } = look;
  const lashes = cfg.lashes && cfg.glasses !== 'soleil';
  const width = BROW_WIDTH[cfg.brows] ?? BROW_WIDTH.naturels;
  return (
    <>
      <EyeSet e={f.eL} skin={tone.skin} iris={iris} arcLine={4} lash={lashes && LASHED.has(f.def.eyes[0]) ? lash([-15, -4], -1, eye.ry) : ''} />
      <EyeSet e={f.eR} skin={tone.skin} iris={iris} arcLine={4} lash={lashes && LASHED.has(f.def.eyes[1]) ? lash([15, -4], 1, eye.ry) : ''} />
      <path d={f.browL} fill="none" stroke={hair.brow} strokeWidth={width} strokeLinecap="round" />
      <path d={f.browR} fill="none" stroke={hair.brow} strokeWidth={width} strokeLinecap="round" />
      <path d={NOSE} fill={tone.shade} />
      <Mouths mouths={f.mouths} transform="translate(-3.6 1.8) scale(1.8)" />
      <BeardOver look={look} />
    </>
  );
}

function sleevePaths(side: Side) {
  const L = side === 'L';
  return {
    upper: L ? 'M62,238 Q54,256 51,276' : 'M138,238 Q146,256 149,276',
    short: L ? 'M62,237 Q57,248 55,258' : 'M138,237 Q143,248 145,258',
    fore: L ? 'M51,276 Q50,294 54,304' : 'M149,276 Q150,294 146,304',
    cuff: L ? 'M52.6,298 Q53,302 54.6,305' : 'M147.4,298 Q147,302 145.4,305',
  };
}

function Arm({ side, place, look }: { side: Side; place: 'back' | 'front'; look: Look }) {
  const a = ARMS[side];
  const g = garmentOf(look);
  const p = sleevePaths(side);
  const { skin, shade } = look.tone;
  const shortSleeve = g.fore === skin;
  // a rim in the sleeve's own darker tone keeps an arm readable against a body of the same cloth
  const rim = (d: string, colour: string, width: number) => (
    <>
      <path d={d} fill="none" stroke={deeper(colour, 0.22)} strokeWidth={width + 2.6} strokeLinecap="round" />
      <path d={d} fill="none" stroke={colour} strokeWidth={width} strokeLinecap="round" />
    </>
  );
  const upper = shortSleeve ? (
    <>
      {rim(p.upper, skin, 12)}
      {rim(p.short, g.sleeve, 17)}
    </>
  ) : (
    <>
      {rim(p.upper, g.sleeve, 15)}
      {g.stripes ? <path d={p.upper} fill="none" stroke={g.stripes} strokeWidth={15} strokeDasharray="5 7" /> : null}
    </>
  );
  const fore = (
    <>
      {rim(p.fore, g.fore, shortSleeve ? 12 : 15)}
      {g.stripes ? <path d={p.fore} fill="none" stroke={g.stripes} strokeWidth={15} strokeDasharray="5 7" /> : null}
      {g.cuff ? <path d={p.cuff} fill="none" stroke={g.cuff} strokeWidth={15} strokeLinecap="round" /> : null}
      <Wristpiece look={look} side={side} />
    </>
  );
  return (
    <Place side={side} place={place}>
      <ArmLayer
        side={side}
        arm={a}
        upper={upper}
        fore={fore}
        hand={
          <>
            <RestHand side={side}>
              <circle cx={a.palm[0]} cy={a.palm[1]} r="8" fill={skin} />
            </RestHand>
            <HandShapes side={side} at={a.palm} r={8} skin={skin} shade={shade} />
          </>
        }
      />
    </Place>
  );
}

/** The figure for one record. Cheap: a few objects, no drawing until React renders it. */
export function avatarFigure(raw?: AvatarConfig | null, name = 'Moi'): FigureDef {
  const cfg = raw ?? DEFAULT_AVATAR;
  const look = lookOf(cfg);
  const eye = EYES[cfg.eyes] ?? EYES.ronds;
  const hatted = cfg.hat !== 'aucun';
  const garment = garmentOf(look);

  const rig: RigDef = {
    id: AVATAR_KEY,
    name,
    head: [100, 150],
    crops: { full: [0, 0, 200, 420], bust: [10, 50, 180, 220], head: [14, 34, 172, 172] },
    idle: { kind: 'bob', seconds: 4.6, amount: 1.4 },
    brows: { neutre: B.neutre },
    eyeL: [-15, -4],
    eyeR: [15, -4],
    eye,
    mouths: { neutre: 'smile' },
    mouthSet: 'symmetric',
    Art: () => <g />,
  };

  const fig: FigureDef = {
    key: AVATAR_KEY,
    name,
    rig,
    arms: ARMS,
    hips: [100, 338],
    neck: [100, 197],
    skin: look.tone.skin,
    shade: look.tone.shade,
    blink: 4.2,
    idle: { kind: 'bob', seconds: 4.6, amount: 1.4 },
    parts: {},
    expressions: EXPRESSIONS,
    gestures: GESTURES,
    fx: { cheekL: [-22, 13], cheekR: [22, 13], temple: [31, -30], crown: [0, -88], side: [60, -54], eyeL: [-15, -4], eyeR: [15, -4] },
    Art: ({ faces, base }) => (
      <g data-avatar-top={cfg.top} data-avatar-hair={cfg.hair}>
        <Body fig={fig}>
          <BehindHead fig={fig}>
            <HairBehind look={look} />
          </BehindHead>
        </Body>
        <Legs long={garment.long} />
        <Body fig={fig}>
          <path d="M93,192 L107,192 L107,222 L93,222 Z" fill={look.tone.skin} />
          <path d="M93,206 L107,206 L107,214 Q100,218 93,214 Z" fill={deeper(look.tone.skin, 0.12)} />
          {garment.body}
          <Neckpiece look={look} />
          <Pin look={look} />
          <Arm side="L" place="back" look={look} />
          <Arm side="R" place="back" look={look} />
          <Head fig={fig} base={base}>
            <HairBack look={look} hatted={hatted} />
            <Earpieces look={look} layer="behind" />
            <Ears look={look} />
            <Face look={look} />
            <BeardUnder look={look} />
            <HairFront look={look} hatted={hatted} />
            <Faces faces={faces} fig={fig}>
              {(f) => <Features f={f} look={look} eye={eye} />}
            </Faces>
            <Glasses look={look} />
            <Hat look={look} />
            <Earpieces look={look} />
          </Head>
          <Arm side="L" place="front" look={look} />
          <Arm side="R" place="front" look={look} />
        </Body>
      </g>
    ),
  };
  return fig;
}
