/* Ton personnage · the learner's character, drawn the troupe's way.
 *
 * Same frame as every cast member (200 × 420, the head at [100, 150] and drawn about its own
 * centre), same manner: flat fills, no outlines, ink only for the line features (lids, brows,
 * frames), limbs as thick round strokes. Each part is one small function of the record, so the
 * figure (`avatar-figure.tsx`) only decides the layers.
 *
 * Coordinates of the head frame: the face spans x −38…38, y −64 (crown) … 50 (chin); the eyes sit
 * at (±15, −4), the brows near −24, the nose at 0…15, the mouth at 25…43, the ear lobes at
 * (±38, 12). The body: neck 192…222, shoulders at y 238, collar at 214, hem 342, hands at
 * (64, 313) and (136, 313).
 */
import React from 'react';
import type { ReactNode } from 'react';

import { circles, curlArcs, dots } from '@/components/cast/rig-kit';
import { Sway } from '@/components/cast/vivant/parts';
import type { AvatarConfig, HairColour, SkinTone } from '@/lib/avatar';
import { EYE_COLOURS, FABRICS, HAIR_COLOURS, SKINS, deeper, isPale, lighter, mix } from '@/lib/avatar';

export const INK = '#14110d';
export const PAPER = '#f8f3e8';
export const GOLD = '#c49a0a';
export const NAVY = '#14285f';
const RED = '#d8321a';
const WINE = '#9c2411';
const STRAW = '#d6c4a0';

/** Everything a part needs, resolved once per record. */
export interface Look {
  cfg: AvatarConfig;
  tone: SkinTone;
  hair: HairColour;
  iris: string;
  hat: string;
  top: string;
}

export function lookOf(cfg: AvatarConfig): Look {
  return {
    cfg,
    tone: SKINS[cfg.skin] ?? SKINS.s3,
    hair: HAIR_COLOURS[cfg.hairColor] ?? HAIR_COLOURS.chatain,
    iris: EYE_COLOURS[cfg.eyeColor] ?? EYE_COLOURS.bruns,
    hat: FABRICS[cfg.hatColor] ?? FABRICS.rouge,
    top: FABRICS[cfg.topColor] ?? FABRICS.marine,
  };
}

/* ------------------------------------------------------------------------------------------ */
/* Head                                                                                         */

export const FACE_PATHS: Record<string, string> = {
  ovale: 'M-38,-24 C-38,-56 -20,-64 0,-64 C20,-64 38,-56 38,-24 C38,14 22,46 0,50 C-22,46 -38,14 -38,-24 Z',
  rond: 'M-40,-24 C-40,-56 -20,-64 0,-64 C20,-64 40,-56 40,-24 C42,12 30,44 0,48 C-30,44 -42,12 -40,-24 Z',
  carre: 'M-38,-26 C-38,-58 -20,-64 0,-64 C20,-64 38,-58 38,-26 L38,8 C38,34 24,50 0,52 C-24,50 -38,34 -38,8 Z',
};

/** Hair long or full enough to hide the ears. */
export const COVERS_EARS = new Set(['carre', 'mi_long', 'long', 'afro', 'boucles', 'tresses']);
/** Hair that stands above the crown: under a hat it is not drawn. */
const STANDS_UP = new Set(['meche', 'chignon', 'afro']);

const SLICK = 'M-40,-14 C-44,-60 -20,-82 0,-82 C20,-82 44,-60 40,-14 C36,-40 26,-56 0,-58 C-26,-56 -36,-40 -40,-14 Z';
const SHORT_BACK = 'M-42,-18 C-48,-60 -22,-86 2,-86 C28,-86 48,-60 42,-18 L34,-36 L-34,-36 Z';

/** Curls along an arc (degrees, 0 = right, 90 = down) of an ellipse about (cx, cy). */
function ring(cx: number, cy: number, rx: number, ry: number, from: number, to: number, n: number, r: number): Array<[number, number, number]> {
  const out: Array<[number, number, number]> = [];
  for (let i = 0; i < n; i += 1) {
    const a = ((from + ((to - from) * i) / Math.max(1, n - 1)) * Math.PI) / 180;
    const wobble = i % 2 === 0 ? r : r * 0.86;
    out.push([Math.round((cx + rx * Math.cos(a)) * 10) / 10, Math.round((cy + ry * Math.sin(a)) * 10) / 10, wobble]);
  }
  return out;
}

const CURLS_BACK = [...ring(0, -40, 44, 40, 160, 380, 13, 14), [0, -44, 40] as [number, number, number]];
const CURLS_FRONT = ring(0, -50, 34, 12, 190, 350, 8, 9.5);
const AFRO_FRONT = ring(0, -54, 36, 10, 185, 355, 9, 8);

/** The hair behind the head and body (long hair falling down the back), in the figure frame. */
export function HairBehind({ look }: { look: Look }) {
  const { hair } = look;
  switch (look.cfg.hair) {
    case 'long':
      return (
        <path
          d="M46,128 C40,80 70,64 100,64 C130,64 160,80 154,128 C160,160 148,180 156,200 C164,220 152,236 162,252 C150,266 128,262 118,250 L82,250 C72,262 50,266 38,252 C48,236 36,220 44,200 C52,180 40,160 46,128 Z"
          fill={hair.hair}
        />
      );
    case 'mi_long':
      return (
        <path
          d="M50,126 C46,82 70,62 100,62 C130,62 154,82 150,126 C152,160 156,190 150,214 C140,222 126,220 120,210 L80,210 C74,220 60,222 50,214 C44,190 48,160 50,126 Z"
          fill={hair.hair}
        />
      );
    default:
      return null;
  }
}

/** The hair behind the face, in the head frame. */
export function HairBack({ look, hatted }: { look: Look; hatted: boolean }) {
  const { hair } = look;
  switch (look.cfg.hair) {
    case 'court':
    case 'meche':
      return <path d={SHORT_BACK} fill={hair.hair} />;
    case 'boucles':
      return <path d={circles(CURLS_BACK)} fill={hair.hair} />;
    case 'afro':
      return (
        <>
          <circle cx="0" cy={hatted ? -36 : -42} r={hatted ? 58 : 64} fill={hair.hair} />
          <path d={curlArcs(ring(0, -42, 52, 52, 200, 340, 6, 12))} fill="none" stroke={hair.light} strokeWidth={2.2} strokeLinecap="round" />
        </>
      );
    case 'carre':
      return (
        <path
          d="M-50,-30 C-52,-74 -26,-90 0,-90 C26,-90 52,-74 50,-30 L52,30 C44,38 30,38 22,30 L-22,30 C-30,38 -44,38 -52,30 Z"
          fill={hair.hair}
        />
      );
    case 'queue':
      return (
        <Sway at={[34, -50]} deg={4} seconds={2.8}>
          <path d="M28,-62 C58,-68 74,-40 66,-4 C60,22 68,44 58,66 C50,56 48,42 50,24 C52,0 48,-26 32,-42 Z" fill={hair.hair} />
          <path d="M60,0 C56,20 60,38 56,54" fill="none" stroke={hair.light} strokeWidth={2} strokeLinecap="round" />
          <rect x="40" y="-60" width="9" height="13" rx="4" fill={RED} transform="rotate(-38 44.5 -53.5)" />
        </Sway>
      );
    case 'chignon':
      return hatted ? null : (
        <>
          <circle cx="0" cy="-86" r="19" fill={hair.hair} />
          <path d="M-12,-94 C-6,-102 6,-102 12,-94" fill="none" stroke={hair.light} strokeWidth={2} strokeLinecap="round" />
        </>
      );
    case 'tresses':
      return <path d="M-42,-10 C-46,-58 -22,-84 0,-84 C22,-84 46,-58 42,-10 Z" fill={hair.hair} />;
    default:
      return null;
  }
}

/** The ears, unless the hair hides them. */
export function Ears({ look }: { look: Look }) {
  if (COVERS_EARS.has(look.cfg.hair)) return null;
  const { skin } = look.tone;
  return (
    <>
      <ellipse cx="-38" cy="2" rx="7" ry="11" fill={skin} />
      <ellipse cx="38" cy="2" rx="7" ry="11" fill={skin} />
      <path d="M-39,-3 Q-42,2 -39,7 M39,-3 Q42,2 39,7" fill="none" stroke={look.tone.shade} strokeWidth={1.6} strokeLinecap="round" />
    </>
  );
}

const FRECKLES = [[-22, 7], [-26, 10], [-18, 10], [-12, 5], [-8, 9], [-3, 4], [22, 7], [26, 10], [18, 10], [12, 5], [8, 9], [3, 4]] as const;
export const FRECKLE_D = dots(FRECKLES, 1.1);

/** The face itself, its cheeks and freckles. */
export function Face({ look }: { look: Look }) {
  const { tone, cfg } = look;
  return (
    <>
      <path d={FACE_PATHS[cfg.face] ?? FACE_PATHS.ovale} fill={tone.skin} />
      {cfg.blush ? (
        <>
          <ellipse cx="-22" cy="13" rx="6.5" ry="3.6" fill={tone.cheek} opacity={0.75} />
          <ellipse cx="22" cy="13" rx="6.5" ry="3.6" fill={tone.cheek} opacity={0.75} />
        </>
      ) : null}
      {cfg.freckles ? <path d={FRECKLE_D} fill={mix(tone.shade, '#8f5534', 0.5)} /> : null}
      {cfg.hair === 'chauve' ? <ellipse cx="-10" cy="-52" rx="10" ry="4.5" fill={lighter(tone.skin, 0.35)} /> : null}
    </>
  );
}

/** The hair in front of the face, in the head frame. */
export function HairFront({ look, hatted }: { look: Look; hatted: boolean }) {
  const { hair, tone } = look;
  switch (look.cfg.hair) {
    case 'court':
      return (
        <>
          <path
            d="M-41,-16 C-46,-64 -16,-90 6,-86 C32,-84 48,-60 41,-16 C38,-40 28,-52 14,-54 C2,-44 -18,-52 -30,-42 C-36,-36 -39,-28 -41,-16 Z"
            fill={hair.hair}
          />
          <path d="M-22,-72 C-10,-80 8,-82 24,-76" fill="none" stroke={hair.light} strokeWidth={2.4} strokeLinecap="round" />
        </>
      );
    case 'rase':
      return (
        <path
          d="M-39,-22 C-41,-58 -20,-70 0,-70 C20,-70 41,-58 39,-22 C37,-40 30,-52 18,-56 C6,-58 -6,-58 -18,-56 C-30,-52 -37,-40 -39,-22 Z"
          fill={mix(hair.hair, tone.skin, 0.3)}
        />
      );
    case 'meche':
      return (
        <>
          <path d="M-41,-14 C-44,-46 -34,-62 -18,-66 L-20,-50 C-30,-46 -37,-34 -41,-14 Z M41,-14 C44,-46 34,-62 18,-66 L20,-50 C30,-46 37,-34 41,-14 Z" fill={hair.hair} />
          {hatted ? null : (
            <>
              <path
                d="M-38,-50 C-44,-80 -20,-102 6,-100 C30,-98 46,-84 42,-60 C40,-50 36,-46 32,-44 C30,-58 18,-66 4,-64 C-12,-62 -26,-56 -38,-50 Z"
                fill={hair.hair}
              />
              <path d="M-20,-84 C-6,-94 14,-94 28,-84" fill="none" stroke={hair.light} strokeWidth={2.4} strokeLinecap="round" />
            </>
          )}
        </>
      );
    case 'boucles':
      return (
        <>
          <path d={circles(CURLS_FRONT)} fill={hair.hair} />
          <path d={curlArcs(CURLS_FRONT)} fill="none" stroke={hair.light} strokeWidth={1.8} strokeLinecap="round" />
        </>
      );
    case 'afro':
      return (
        <>
          <path d={circles(AFRO_FRONT)} fill={hair.hair} />
          <path d={curlArcs(AFRO_FRONT)} fill="none" stroke={hair.light} strokeWidth={1.6} strokeLinecap="round" />
        </>
      );
    case 'carre':
      return (
        <>
          <path
            d="M-46,30 C-48,0 -46,-40 -40,-58 C-30,-82 -12,-88 2,-88 C22,-88 38,-80 44,-60 C48,-40 48,0 46,30 C42,34 38,34 34,30 C36,6 36,-16 32,-31 L-32,-31 C-36,-16 -36,6 -34,30 C-38,34 -42,34 -46,30 Z"
            fill={hair.hair}
          />
          <path d="M-26,-38 L-24,-62 M-10,-36 L-9,-66 M6,-36 L6,-68 M22,-38 L21,-64" fill="none" stroke={hair.light} strokeWidth={1.6} strokeLinecap="round" />
        </>
      );
    case 'mi_long':
      return (
        <>
          <path
            d="M-42,12 C-46,-40 -30,-84 2,-86 C30,-86 46,-64 44,-30 C40,-44 30,-52 18,-56 C0,-50 -24,-40 -34,-20 C-38,-8 -40,2 -42,12 Z"
            fill={hair.hair}
          />
          <path d="M44,-30 C48,0 46,30 40,52 L34,48 C38,26 38,2 36,-20 Z" fill={hair.hair} />
          <path d="M-30,-60 C-16,-74 6,-78 24,-70" fill="none" stroke={hair.light} strokeWidth={2.2} strokeLinecap="round" />
        </>
      );
    case 'long':
      return (
        <>
          <path d="M0,-80 C-30,-80 -54,-60 -52,-24 C-50,4 -58,28 -52,52 C-48,66 -56,74 -54,82 L-42,80 C-44,64 -39,50 -41,30 C-43,8 -42,-14 -40,-26 Z" fill={hair.hair} />
          <path d="M0,-80 C30,-80 54,-60 52,-24 C50,4 58,28 52,52 C48,66 56,74 54,82 L42,80 C44,64 39,50 41,30 C43,8 42,-14 40,-26 Z" fill={hair.hair} />
          <path
            d="M-41,6 C-44,-40 -26,-80 0,-80 C26,-80 44,-40 41,6 L36,4 C35,-16 30,-36 18,-46 C12,-50 6,-52 2,-53 L0,-57 L-2,-53 C-6,-52 -12,-50 -18,-46 C-30,-36 -35,-16 -36,4 Z"
            fill={hair.hair}
          />
          <path d="M-24,-46 C-30,-38 -33,-28 -34,-16 M24,-46 C30,-38 33,-28 34,-16 M-47,10 C-49,26 -50,42 -48,60 M47,10 C49,26 50,42 48,60" fill="none" stroke={hair.light} strokeWidth={1.8} strokeLinecap="round" />
        </>
      );
    case 'queue':
      return (
        <>
          <path d={SLICK} fill={hair.hair} />
          <path d="M-24,-66 C-10,-74 10,-74 24,-66" fill="none" stroke={hair.light} strokeWidth={2} strokeLinecap="round" />
        </>
      );
    case 'chignon':
      return (
        <>
          <path d={SLICK} fill={hair.hair} />
          {hatted ? null : <path d="M-14,-70 Q0,-75 14,-70 L13,-66 Q0,-70 -13,-66 Z" fill={RED} />}
          <path d="M-26,-64 C-12,-72 12,-72 26,-64" fill="none" stroke={hair.light} strokeWidth={2} strokeLinecap="round" />
        </>
      );
    case 'tresses':
      return (
        <>
          <path d="M-41,-12 C-44,-58 -20,-82 0,-82 C20,-82 44,-58 41,-12 C38,-40 22,-54 2,-56 L0,-58 L-2,-56 C-22,-54 -38,-40 -41,-12 Z" fill={hair.hair} />
          {[-1, 1].map((side) => (
            <g key={side}>
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <ellipse
                  key={i}
                  cx={side * (43 + i * 0.6)}
                  cy={4 + i * 14}
                  rx={8 - i * 0.5}
                  ry={9}
                  fill={i % 2 ? hair.light : hair.hair}
                />
              ))}
              <path d={`M${side * 40},86 L${side * 48},86 L${side * 47},92 L${side * 41},92 Z`} fill={RED} />
              <path d={`M${side * 41},92 L${side * 39},102 M${side * 44},92 L${side * 44},104 M${side * 47},92 L${side * 49},102`} fill="none" stroke={hair.hair} strokeWidth={2.4} strokeLinecap="round" />
            </g>
          ))}
        </>
      );
    default:
      return null;
  }
}

/** The beards' outlines, in the head frame (the head in the round prints them too). */
export const BEARD_PATHS = {
  stubble: 'M-37,-2 C-38,26 -22,48 0,51 C22,48 38,26 37,-2 C33,12 26,20 16,20 C8,17 -8,17 -16,20 C-26,20 -33,12 -37,-2 Z',
  goatee: 'M-9,39 Q0,36 9,39 L7,51 Q0,57 -7,51 Z',
  short: 'M-39,-4 C-41,30 -22,58 0,60 C22,58 41,30 39,-4 C34,10 26,15 16,14 C8,11 -8,11 -16,14 C-26,15 -34,10 -39,-4 Z',
  full: 'M-41,-8 C-44,40 -24,76 0,78 C24,76 44,40 41,-8 C36,8 26,14 16,13 C8,10 -8,10 -16,13 C-26,14 -36,8 -41,-8 Z',
  fullLines: 'M-20,52 C-14,62 -6,66 0,66 M20,52 C14,62 6,66 0,66',
  moustache: 'M-19,24 C-11,16 -2,18 0,20.5 C2,18 11,16 19,24 C12,27.5 4,26.5 0,24 C-4,26.5 -12,27.5 -19,24 Z',
};

/** Beards with a moustache over the mouth. */
export const MOUSTACHED = ['moustache', 'bouc', 'courte', 'pleine'];

/** Under the mouth: stubble, goatee or beard (the moustache comes after the mouth). */
export function BeardUnder({ look }: { look: Look }) {
  const { tone, hair, cfg } = look;
  const colour = hair.brow;
  switch (cfg.beard) {
    case 'trois_jours':
      return (
        <path d={BEARD_PATHS.stubble} fill={mix(tone.skin, colour, 0.3)} />
      );
    case 'bouc':
      return <path d={BEARD_PATHS.goatee} fill={colour} />;
    case 'courte':
      return (
        <>
          <path d={BEARD_PATHS.short} fill={colour} />
          <ellipse cx="0" cy="33" rx="14" ry="9.5" fill={tone.skin} />
        </>
      );
    case 'pleine':
      return (
        <>
          <path d={BEARD_PATHS.full} fill={colour} />
          <path d={BEARD_PATHS.fullLines} fill="none" stroke={hair.light} strokeWidth={1.6} strokeLinecap="round" />
          <ellipse cx="0" cy="32" rx="13.5" ry="9" fill={tone.skin} />
        </>
      );
    default:
      return null;
  }
}

/** Over the mouth: the moustache of every beard that has one. */
export function BeardOver({ look }: { look: Look }) {
  if (!MOUSTACHED.includes(look.cfg.beard)) return null;
  return <path d={BEARD_PATHS.moustache} fill={look.hair.brow} />;
}

/** Frames over the eyes (sunglasses hide them). */
export function Glasses({ look }: { look: Look }) {
  switch (look.cfg.glasses) {
    case 'rondes':
      return (
        <path
          d="M-28.5,-4 A13.5,13.5 0 1 0 -1.5,-4 A13.5,13.5 0 1 0 -28.5,-4 Z M1.5,-4 A13.5,13.5 0 1 0 28.5,-4 A13.5,13.5 0 1 0 1.5,-4 Z M-1.5,-7 Q0,-10 1.5,-7 M-28.5,-6 L-38,-3 M28.5,-6 L38,-3"
          fill="none"
          stroke={GOLD}
          strokeWidth={2.4}
          strokeLinecap="round"
        />
      );
    case 'carrees':
      return (
        <path
          d="M-29,-14 Q-29,-17 -26,-17 L-5,-17 Q-2,-17 -2,-14 L-2,4 Q-2,8 -6,8 L-25,8 Q-29,8 -29,4 Z M2,-14 Q2,-17 5,-17 L26,-17 Q29,-17 29,-14 L29,4 Q29,8 25,8 L6,8 Q2,8 2,4 Z M-2,-9 L2,-9 M-29,-12 L-38,-8 M29,-12 L38,-8"
          fill="none"
          stroke={INK}
          strokeWidth={3}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      );
    case 'grandes':
      return (
        <path
          d="M-31,-4 A16,16 0 1 0 1,-4 A16,16 0 1 0 -31,-4 Z M-1,-4 A16,16 0 1 0 31,-4 A16,16 0 1 0 -1,-4 Z M-31,-8 L-39,-5 M31,-8 L39,-5"
          fill="none"
          stroke={RED}
          strokeWidth={3.2}
          strokeLinecap="round"
        />
      );
    case 'soleil':
      return (
        <>
          <path d="M-32,-15 L-3,-15 L-4,1 C-6,10 -26,10 -30,1 Z M32,-15 L3,-15 L4,1 C6,10 26,10 30,1 Z" fill={INK} />
          <path d="M-3,-12 Q0,-14 3,-12 M-32,-14 L-39,-10 M32,-14 L39,-10" fill="none" stroke={INK} strokeWidth={3} strokeLinecap="round" />
          <path d="M-24,-10 L-17,-3 M-20,-11 L-12,-3 M10,-10 L17,-3 M14,-11 L22,-3" fill="none" stroke={PAPER} strokeWidth={1.8} strokeLinecap="round" opacity={0.75} />
        </>
      );
    default:
      return null;
  }
}

/** Hats, in the head frame, over the hair. */
export function Hat({ look }: { look: Look }) {
  const c = look.hat;
  const dark = deeper(c);
  switch (look.cfg.hat) {
    case 'beret':
      return (
        <>
          <path d="M-44,-56 C-52,-82 -14,-98 18,-94 C46,-90 58,-74 48,-58 C30,-66 -16,-66 -44,-56 Z" fill={c} />
          <path d="M-44,-56 C-16,-66 30,-66 48,-58 L46,-52 C30,-60 -16,-60 -42,-50 Z" fill={dark} />
          <path d="M5,-94 L7,-101" fill="none" stroke={dark} strokeWidth={3.4} strokeLinecap="round" />
        </>
      );
    case 'bonnet':
      return (
        <>
          <path d="M-42,-38 C-44,-80 -22,-98 0,-98 C22,-98 44,-80 42,-38 Z" fill={c} />
          <path d="M-45,-48 Q0,-54 45,-48 L46,-32 Q0,-38 -46,-32 Z" fill={dark} />
          <path d="M-33,-50 L-33,-34 M-20,-52 L-20,-36 M-7,-53 L-7,-37 M7,-53 L7,-37 M20,-52 L20,-36 M33,-50 L33,-34" fill="none" stroke={c} strokeWidth={2} />
          <circle cx="0" cy="-102" r="11" fill={isPale(c) ? dark : PAPER} />
        </>
      );
    case 'casquette':
      return (
        <>
          <path d="M-42,-40 C-42,-80 -20,-94 2,-94 C26,-94 42,-80 42,-40 Q0,-48 -42,-40 Z" fill={c} />
          <path d="M2,-94 L2,-46" fill="none" stroke={dark} strokeWidth={1.6} />
          <path d="M-43,-42 Q-4,-52 34,-44 Q58,-40 72,-30 Q60,-25 38,-30 Q-2,-38 -43,-34 Z" fill={dark} />
          <circle cx="2" cy="-93" r="3.4" fill={dark} />
        </>
      );
    case 'bob':
      return (
        <>
          <path d="M-38,-44 C-38,-84 -18,-94 0,-94 C18,-94 38,-84 38,-44 Z" fill={c} />
          <path d="M-56,-36 Q0,-58 56,-36 L61,-27 Q0,-48 -61,-27 Z" fill={dark} />
          <path d="M-36,-52 Q0,-60 36,-52" fill="none" stroke={dark} strokeWidth={1.6} strokeDasharray="3 3" />
        </>
      );
    case 'canotier':
      return (
        <>
          <ellipse cx="0" cy="-52" rx="62" ry="11" fill={deeper(STRAW, 0.18)} />
          <path d="M-34,-54 L-32,-88 Q0,-94 32,-88 L34,-54 Q0,-60 -34,-54 Z" fill={STRAW} />
          <path d="M-34,-66 Q0,-72 34,-66 L34,-55 Q0,-61 -34,-55 Z" fill={c} />
          <ellipse cx="0" cy="-88" rx="32" ry="5" fill={lighter(STRAW, 0.4)} />
          <path d="M-26,-80 L-26,-70 M-12,-82 L-12,-72 M2,-83 L2,-73 M16,-82 L16,-72 M28,-80 L28,-70" fill="none" stroke={deeper(STRAW, 0.12)} strokeWidth={1.4} />
        </>
      );
    default:
      return null;
  }
}

/** Ear pieces: hoops, pearls, a pencil, gold drops. */
export function Earpieces({ look, layer = 'front' }: { look: Look; layer?: 'behind' | 'front' }) {
  // the pencil is tucked behind the ear: drawn before the ear and the face, it peeks out above
  if ((look.cfg.ears === 'crayon') !== (layer === 'behind')) return null;
  switch (look.cfg.ears) {
    case 'anneaux':
      return (
        <path d="M-43,16 A5,5 0 1 0 -33,16 A5,5 0 1 0 -43,16 Z M33,16 A5,5 0 1 0 43,16 A5,5 0 1 0 33,16 Z" fill="none" stroke={GOLD} strokeWidth={2} />
      );
    case 'perles':
      return (
        <>
          {[-38, 38].map((x) => (
            <g key={x}>
              <circle cx={x} cy="14" r="4.4" fill={deeper(PAPER, 0.16)} />
              <circle cx={x - 0.6} cy="13.4" r="3.6" fill={PAPER} />
              <circle cx={x + 0.8} cy="12.2" r="1.2" fill="#ffffff" />
            </g>
          ))}
        </>
      );
    case 'crayon':
      return (
        <g transform="translate(47 -14) rotate(-68)">
          <path d="M-20,-2.8 L14,-2.8 L14,2.8 L-20,2.8 Z" fill="#f3c318" />
          <path d="M-20,-2.8 L14,-2.8 L14,-0.6 L-20,-0.6 Z" fill="#c49a0a" />
          <path d="M14,-2.8 L22,0 L14,2.8 Z" fill="#e6dfcf" />
          <path d="M19.4,-0.9 L22,0 L19.4,0.9 Z" fill={INK} />
          <path d="M-24,-2.8 L-20,-2.8 L-20,2.8 L-24,2.8 Z" fill="#a59e8f" />
          <path d="M-29,-2.8 Q-30,0 -29,2.8 L-24,2.8 L-24,-2.8 Z" fill="#f07f86" />
        </g>
      );
    case 'boucles_or':
      return (
        <>
          {[-38, 38].map((x) => (
            <g key={x}>
              <circle cx={x} cy="13" r="2.4" fill={GOLD} />
              <path d={`M${x},15 C${x + 5},20 ${x + 5},27 ${x},31 C${x - 5},27 ${x - 5},20 ${x},15 Z`} fill={GOLD} />
              <circle cx={x} cy="24" r="2.4" fill={RED} />
            </g>
          ))}
        </>
      );
    default:
      return null;
  }
}

/* ------------------------------------------------------------------------------------------ */
/* Body                                                                                         */

export const BODY = 'M60,232 Q62,216 80,214 L120,214 Q138,216 140,232 L146,330 Q146,342 134,342 L66,342 Q54,342 54,330 Z';
const COAT = 'M58,232 Q60,212 80,212 L120,212 Q140,212 142,232 L150,364 Q150,374 138,374 L62,374 Q50,374 50,364 Z';

/** The body's left and right edge at height y (for stripes and hems). */
function edgeAt(y: number, coat = false): [number, number] {
  // the body flares from the shoulders (y 232: 60…140) to the hem (y 330: 54…146)
  const t = Math.max(0, Math.min(1, (y - 232) / (coat ? 132 : 98)));
  const l = 60 - (coat ? 8 : 6) * t;
  return [l, 200 - l];
}

export interface Garment {
  /** drawn behind the arms and the head: the body of the top and its details */
  body: ReactNode;
  /** sleeve colour (upper arm), forearm colour (skin for short sleeves) */
  sleeve: string;
  fore: string;
  /** a cuff at the wrist, in the sleeve's darker tone */
  cuff?: string;
  /** a dash pattern along the sleeve (the marinière's stripes) */
  stripes?: string;
  /** the coat is longer: less trouser shows */
  long?: boolean;
}

export function garmentOf(look: Look): Garment {
  const c = look.top;
  const dark = deeper(c);
  const { skin } = look.tone;
  switch (look.cfg.top) {
    case 'tshirt':
      return {
        sleeve: c,
        fore: skin,
        body: (
          <>
            <path d={BODY} fill={c} />
            <path d="M84,214 Q100,232 116,214 L112,214 Q100,226 88,214 Z" fill={dark} />
          </>
        ),
      };
    case 'chemise':
      return {
        sleeve: c,
        fore: c,
        cuff: lighter(c, 0.35),
        body: (
          <>
            <path d={BODY} fill={c} />
            <path d="M93,214 L100,230 L107,214 Z" fill={skin} />
            <path d="M86,211 L100,230 L93,240 L80,220 Z M114,211 L100,230 L107,240 L120,220 Z" fill={lighter(c, 0.35)} />
            <path d="M100,232 L100,342" fill="none" stroke={dark} strokeWidth={1.6} />
            {[252, 276, 300, 324].map((y) => (
              <circle key={y} cx="104" cy={y} r="2" fill={isPale(c) ? dark : lighter(c, 0.6)} />
            ))}
            <path d="M70,250 L84,250 L84,262 L70,262 Z" fill="none" stroke={dark} strokeWidth={1.4} />
          </>
        ),
      };
    case 'veste':
      return {
        sleeve: c,
        fore: c,
        cuff: dark,
        body: (
          <>
            <path d={BODY} fill={c} />
            <path d="M85,214 L100,252 L115,214 Z" fill={PAPER} />
            <path d="M85,214 L74,220 L94,264 L100,252 Z M115,214 L126,220 L106,264 L100,252 Z" fill={dark} />
            <path d="M63,252 Q60,290 64,322 M137,252 Q140,290 136,322" fill="none" stroke={dark} strokeWidth={2.2} strokeLinecap="round" />
            <circle cx="104" cy="282" r="2.6" fill={dark} />
            <circle cx="104" cy="304" r="2.6" fill={dark} />
          </>
        ),
      };
    case 'sweat':
      return {
        sleeve: c,
        fore: c,
        cuff: dark,
        body: (
          <>
            <path d={BODY} fill={c} />
            <path d="M74,216 Q100,240 126,216 Q126,200 100,198 Q74,200 74,216 Z" fill={dark} />
            <path d="M86,214 Q100,226 114,214" fill="none" stroke={c} strokeWidth={3} />
            <path d="M94,224 L92,256 M106,224 L108,256" fill="none" stroke={PAPER} strokeWidth={2} strokeLinecap="round" />
            <path d="M76,290 L124,290 L130,322 L70,322 Z" fill={dark} />
            <path d="M54,326 L146,326 L146,330 Q146,342 134,342 L66,342 Q54,342 54,330 Z" fill={dark} />
          </>
        ),
      };
    case 'manteau':
      return {
        sleeve: c,
        fore: c,
        cuff: dark,
        long: true,
        body: (
          <>
            <path d={COAT} fill={c} />
            <path d="M80,212 Q100,232 120,212 L124,226 Q100,246 76,226 Z" fill={dark} />
            <path d="M100,236 L100,374" fill="none" stroke={dark} strokeWidth={2} />
            <path d="M62,300 L138,300 L139,310 L61,310 Z" fill={dark} />
            <path d="M96,298 L104,298 L104,312 L96,312 Z" fill="none" stroke={GOLD} strokeWidth={1.8} />
            {[252, 276].map((y) => (
              <g key={y}>
                <circle cx="92" cy={y} r="2.4" fill={dark} />
                <circle cx="108" cy={y} r="2.4" fill={dark} />
              </g>
            ))}
          </>
        ),
      };
    case 'mariniere': {
      // the Breton top: cream, stripes in the chosen colour, a boat neck
      const stripes: string[] = [];
      for (let y = 240; y <= 334; y += 12) {
        const [l, r] = edgeAt(y);
        const [l2, r2] = edgeAt(y + 5);
        stripes.push(`M${l},${y} L${r},${y} L${r2},${y + 5} L${l2},${y + 5} Z`);
      }
      return {
        sleeve: PAPER,
        fore: PAPER,
        stripes: c,
        body: (
          <>
            <path d={BODY} fill={PAPER} />
            <path d={stripes.join(' ')} fill={c} />
            <path d="M80,214 Q100,222 120,214 L120,217 Q100,225 80,217 Z" fill={lighter(c, 0.5)} />
          </>
        ),
      };
    }
    default: // pull
      return {
        sleeve: c,
        fore: c,
        cuff: dark,
        body: (
          <>
            <path d={BODY} fill={c} />
            <path d="M83,214 Q100,230 117,214 L113,213 Q100,224 87,213 Z" fill={dark} />
            <path d="M54,326 L146,326 L146,330 Q146,342 134,342 L66,342 Q54,342 54,330 Z" fill={dark} />
            <path d="M64,328 L64,340 M76,328 L76,341 M88,328 L88,341 M100,328 L100,341 M112,328 L112,341 M124,328 L124,341 M136,328 L136,340" fill="none" stroke={c} strokeWidth={1.4} />
          </>
        ),
      };
  }
}

/** Legs and shoes: the troupe's navy trousers; under the coat, less of them. */
export function Legs({ long }: { long?: boolean }) {
  return (
    <>
      <path d={`M88,${long ? 368 : 340} L87,392 M112,${long ? 368 : 340} L113,392`} fill="none" stroke={NAVY} strokeWidth={14} strokeLinecap="round" />
      <ellipse cx="84" cy="399" rx="12" ry="6.5" fill={INK} />
      <ellipse cx="116" cy="399" rx="12" ry="6.5" fill={INK} />
    </>
  );
}

/** Around the neck: a scarf, a silk foulard, Margaux's key on a cord, a press card. */
export function Neckpiece({ look }: { look: Look }) {
  switch (look.cfg.neck) {
    case 'echarpe': {
      const c = look.cfg.topColor === 'bordeaux' || look.cfg.topColor === 'rouge' ? '#e9e4d8' : WINE;
      return (
        <>
          <path d="M78,208 Q100,226 122,208 L124,222 Q100,240 76,222 Z" fill={c} />
          <path d="M106,222 L116,280 L103,283 L96,226 Z" fill={c} />
          <path d="M104,280 L105,288 M108,279 L109,288 M112,278 L114,287" fill="none" stroke={c} strokeWidth={2} strokeLinecap="round" />
          <path d="M84,218 L86,230 M94,222 L95,234" fill="none" stroke={deeper(c, 0.2)} strokeWidth={1.4} strokeLinecap="round" />
        </>
      );
    }
    case 'foulard':
      return (
        <>
          <path d="M83,211 Q100,224 117,211 L113,222 Q100,234 87,222 Z" fill={RED} />
          <path d="M98,229 L90,250 L100,243 Z M102,229 L111,249 L104,242 Z" fill={RED} />
          <circle cx="100" cy="229" r="4.6" fill={deeper(RED, 0.2)} />
          <path d={dots([[90, 217], [100, 221], [110, 217], [95, 240], [106, 239]], 1.3)} fill={PAPER} />
        </>
      );
    case 'collier_cle':
      return (
        <>
          <path d="M86,214 Q100,262 114,214" fill="none" stroke={INK} strokeWidth={1.4} />
          <g transform="translate(100 247)">
            <circle cx="0" cy="0" r="5.6" fill={GOLD} />
            <circle cx="0" cy="0" r="2.2" fill={look.top} />
            <path d="M-1.6,5 L1.6,5 L1.6,22 L-1.6,22 Z" fill={GOLD} />
            <path d="M1.6,15 L6,15 L6,18 L1.6,18 Z M1.6,19.5 L4.6,19.5 L4.6,22 L1.6,22 Z" fill={GOLD} />
          </g>
        </>
      );
    case 'badge_presse':
      return (
        <>
          <path d="M84,214 L95,264 M116,214 L105,264" fill="none" stroke="#1d3a8a" strokeWidth={3} strokeLinecap="round" />
          <path d="M86,262 L114,262 Q116,262 116,264 L116,294 Q116,296 114,296 L86,296 Q84,296 84,294 L84,264 Q84,262 86,262 Z" fill={PAPER} />
          <path d="M84,264 Q84,262 86,262 L114,262 Q116,262 116,264 L116,271 L84,271 Z" fill={RED} />
          <text x="100" y="269.4" textAnchor="middle" fontSize="6" fontWeight="700" fill={PAPER} fontFamily="Helvetica, Arial, sans-serif" letterSpacing="0.6">PRESSE</text>
          <path d="M88,275 L98,275 L98,289 L88,289 Z" fill={look.tone.skin} />
          <path d="M101,278 L112,278 M101,283 L110,283 M101,288 L108,288" fill="none" stroke={INK} strokeWidth={1.4} strokeLinecap="round" />
        </>
      );
    default:
      return null;
  }
}

/** On the chest: a flower, the Atelier's enamel pin. */
export function Pin({ look }: { look: Look }) {
  switch (look.cfg.pin) {
    case 'fleur':
      return (
        <g transform="translate(80 248)">
          <path d={circles([[0, -4.5, 3.6], [4.3, -1.4, 3.6], [2.7, 3.6, 3.6], [-2.7, 3.6, 3.6], [-4.3, -1.4, 3.6]])} fill={isPale(look.top) ? RED : PAPER} />
          <circle r="2.6" fill="#f3c318" />
          <path d="M1,6 L4,16" fill="none" stroke="#2c6a5d" strokeWidth={1.8} strokeLinecap="round" />
        </g>
      );
    case 'pins_atelier':
      return (
        <g transform="translate(80 250)">
          <circle r="8" fill={GOLD} />
          <circle r="6.4" fill={RED} />
          <path d="M0,-4.2 Q0.7,-0.7 4.2,0 Q0.7,0.7 0,4.2 Q-0.7,0.7 -4.2,0 Q-0.7,-0.7 0,-4.2 Z" fill={PAPER} />
        </g>
      );
    default:
      return null;
  }
}

/** On the wrist: a gold bangle, a watch, the woven bracelet of l'entraide. */
export function Wristpiece({ look, side }: { look: Look; side: 'L' | 'R' }) {
  // the watch goes on the left wrist, everything else on the right
  const piece = look.cfg.wrist;
  const wanted = piece === 'montre' ? 'L' : 'R';
  if (piece === 'aucun' || side !== wanted) return null;
  const at: [number, number] = side === 'L' ? [54.4, 305] : [145.6, 305];
  const tilt = side === 'L' ? -14 : 14;
  const t = `translate(${at[0]} ${at[1]}) rotate(${tilt})`;
  switch (piece) {
    case 'jonc':
      return (
        <g transform={t}>
          <ellipse rx="8.6" ry="3.4" fill="none" stroke={GOLD} strokeWidth={2.6} />
        </g>
      );
    case 'montre':
      return (
        <g transform={t}>
          <path d="M-8.4,-2.6 L8.4,-2.6 L8.4,2.6 L-8.4,2.6 Z" fill={INK} />
          <circle r="4.6" fill={GOLD} />
          <circle r="3.4" fill={PAPER} />
          <path d="M0,0 L0,-2.4 M0,0 L1.6,0.6" fill="none" stroke={INK} strokeWidth={0.9} strokeLinecap="round" />
        </g>
      );
    case 'bracelet':
      return (
        <g transform={t}>
          <path d="M-9.6,-4.4 Q0,-6 9.6,-4.4 L9.6,4.4 Q0,6 -9.6,4.4 Z" fill={RED} />
          <path d="M-9.6,-1.3 Q0,-2.2 9.6,-1.3 L9.6,1.3 Q0,2.2 -9.6,1.3 Z" fill="#f3c318" />
          <path d="M-7,-4.8 L-3.4,4.8 M-1.4,-5.2 L2.2,5.2 M4.2,-5 L7.8,4.6" fill="none" stroke="#1d3a8a" strokeWidth={1.6} />
          <circle cx="9.4" cy="0" r="2.2" fill="#f3c318" />
        </g>
      );
    default:
      return null;
  }
}
