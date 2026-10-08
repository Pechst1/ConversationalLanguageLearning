/* WP-116 · Toi, variant C. Ported from the Claude Design canvas rig (2026-10-01).
 *
 * WP-119 §8.2 · Toi's torso is drawn per `outfit`, always from behind. The head and
 * tuque, the hands, the legs and shoes, the bag and the head anchor [100, 150] never
 * change, so the crops and the stage sizing of WP-116 phase 3 hold. `coat` (or no
 * outfit) is exactly the drawing above the outfits. Every colour is one the cast
 * already uses (no new colours, owner rule):
 *   #5b5346 coat, #4a4338 its darker tone, #2a231c gloves, #9c2411 scarf,
 *   #1d3a8a / #14285f tuque and trousers, #f8f3e8 pompom (paper)   — this file
 *   #e9e4d8 off-white                                                — odile.tsx
 *   #c9c2b2 pale stone, #a59e8f stone grey                           — marchand.tsx
 *   #f3c318 yellow                                                   — lila.tsx
 * The legs only show below 366; an outfit shorter than the coat adds trousers in the
 * legs' own #14285f so the figure has no gap between hem and knees.
 */
import React from 'react';
import type { ReactNode } from 'react';
import { OUTFITS } from '../rig-kit';
import type { Outfit, RigDef, RigValues } from '../rig-kit';

/** One outfit's pieces, slotted into the drawing in the coat's painting order. */
interface Torso {
  /** under the sleeves and body: trousers where the garment is shorter than the coat */
  under?: ReactNode;
  sleeveL: ReactNode;
  /** body, seams, belt, buttons, bands */
  body: ReactNode;
  sleeveR: ReactNode;
  /** in the head group, under the tuque: the collar and, unless dropped, the scarf */
  neck: ReactNode;
}

const COAT_COLLAR = 'M-30,10 Q0,26 30,10 L34,36 Q0,50 -34,36 Z';
/** The red scarf. A function, not a module-level element: JSX runs only at render time. */
function scarf() {
  return <path d="M-28,20 Q0,34 28,20 L28,28 Q0,42 -28,28 Z" fill="#9c2411" />;
}
const COAT_SLEEVE_L = 'M52,196 Q40,250 46,296';
const COAT_SLEEVE_R = 'M148,196 Q160,250 154,296';
const COAT_BODY = 'M50,190 Q56,168 80,166 L120,166 Q144,168 150,190 L160,360 Q160,372 148,372 L52,372 Q40,372 40,360 Z';
/** a jumper: the coat's shoulders brought in, hem at 350 */
const JUMPER_BODY = 'M54,192 Q60,170 82,168 L118,168 Q140,170 146,192 L150,340 Q150,350 140,350 L60,350 Q50,350 50,340 Z';
const JUMPER_SLEEVE_L = 'M54,198 Q42,250 46,296';
const JUMPER_SLEEVE_R = 'M146,198 Q158,250 154,296';

function sleeve(d: string, colour: string, width: number) {
  return <path d={d} fill="none" stroke={colour} strokeWidth={width} strokeLinecap="round" />;
}

/** Hips and two trouser legs from `top` down to where the legs begin, in the legs' colour. */
function trousers(top: number) {
  return (
    <>
      <path d={`M74,${top} L126,${top} L121,${top + 22} L79,${top + 22} Z`} fill="#14285f" />
      <path d={`M86,${top + 12} L86,368 M114,${top + 12} L114,368`} fill="none" stroke="#14285f" strokeWidth={14} strokeLinecap="round" />
    </>
  );
}

function torso(outfit: Outfit): Torso {
  switch (outfit) {
    // suit: the trousers' navy #14285f as a narrower jacket with a centre vent in the
    // tuque blue #1d3a8a, and a paper (#f8f3e8) shirt collar showing above it. No scarf.
    case 'suit':
      return {
        under: trousers(334),
        sleeveL: sleeve('M56,198 Q44,250 47,296', '#14285f', 16),
        body: (
          <>
            <path d="M56,192 Q62,170 82,168 L118,168 Q138,170 144,192 L150,332 Q150,342 140,342 L60,342 Q50,342 50,332 Z" fill="#14285f" />
            <path d="M100,302 L100,342" fill="none" stroke="#1d3a8a" strokeWidth={2} />
          </>
        ),
        sleeveR: sleeve('M144,198 Q156,250 153,296', '#14285f', 16),
        neck: (
          <>
            <path d="M-26,12 Q0,24 26,12 L30,34 Q0,46 -30,34 Z" fill="#14285f" />
            <path d="M-22,8 Q0,19 22,8 L22,12 Q0,23 -22,12 Z" fill="#f8f3e8" />
          </>
        ),
      };
    // apron: a jumper in the coat's darker tone #4a4338 under a long bistro apron in
    // paper #f8f3e8 that wraps round to the back, its waistband in odile's #e9e4d8 and
    // the bow and its two ties in marchand's pale stone #c9c2b2. No scarf.
    case 'apron':
      return {
        sleeveL: sleeve(JUMPER_SLEEVE_L, '#4a4338', 16),
        body: (
          <>
            <path d={JUMPER_BODY} fill="#4a4338" />
            <path d="M47,282 L153,282 L158,372 Q158,382 148,382 L52,382 Q42,382 42,372 Z" fill="#f8f3e8" />
            <path d="M47,282 L153,282 L153.6,290 L46.4,290 Z" fill="#e9e4d8" />
            <path d="M98,289 L91,320 M102,289 L109,320" fill="none" stroke="#c9c2b2" strokeWidth={4} strokeLinecap="round" />
            <path d="M100,286 Q86,276 84,286 Q86,296 100,286 Z M100,286 Q114,276 116,286 Q114,296 100,286 Z" fill="#c9c2b2" />
            <circle cx="100" cy="286" r="3.5" fill="#c9c2b2" />
          </>
        ),
        sleeveR: sleeve(JUMPER_SLEEVE_R, '#4a4338', 16),
        neck: <path d={COAT_COLLAR} fill="#4a4338" />,
      };
    // raincoat: the coat, longer (hem 384), in the tuque blue #1d3a8a with a yoke seam
    // and a back vent in the tuque band's #14285f, collar #14285f. The scarf stays.
    case 'raincoat':
      return {
        sleeveL: sleeve(COAT_SLEEVE_L, '#1d3a8a', 18),
        body: (
          <>
            <path d="M50,190 Q56,168 80,166 L120,166 Q144,168 150,190 L162,372 Q162,384 150,384 L50,384 Q38,384 38,372 Z" fill="#1d3a8a" />
            <path d="M53,214 Q100,226 147,214" fill="none" stroke="#14285f" strokeWidth={2.5} />
            <path d="M100,318 L100,384" fill="none" stroke="#14285f" strokeWidth={2} />
          </>
        ),
        sleeveR: sleeve(COAT_SLEEVE_R, '#1d3a8a', 18),
        neck: (
          <>
            <path d={COAT_COLLAR} fill="#14285f" />
            {scarf()}
          </>
        ),
      };
    // sport: a short track jacket in the scarf red #9c2411 (the scarf is off, its red
    // moves to the jacket), collar and waistband in the trousers' navy #14285f, a
    // paper #f8f3e8 stripe down each sleeve. No scarf.
    case 'sport':
      return {
        under: trousers(330),
        sleeveL: (
          <>
            {sleeve(JUMPER_SLEEVE_L, '#9c2411', 17)}
            {sleeve('M54,200 Q42,250 46,290', '#f8f3e8', 3.5)}
          </>
        ),
        body: (
          <>
            <path d="M54,192 Q60,170 82,168 L118,168 Q140,170 146,192 L150,324 Q150,334 140,334 L60,334 Q50,334 50,324 Z" fill="#9c2411" />
            <path d="M50,320 L150,320 L150,328 Q150,338 140,338 L60,338 Q50,338 50,328 Z" fill="#14285f" />
          </>
        ),
        sleeveR: (
          <>
            {sleeve(JUMPER_SLEEVE_R, '#9c2411', 17)}
            {sleeve('M146,200 Q158,250 154,290', '#f8f3e8', 3.5)}
          </>
        ),
        neck: <path d="M-28,12 Q0,26 28,12 L30,32 Q0,44 -30,32 Z" fill="#14285f" />,
      };
    // scarf_only: no coat. A jumper in the coat's darker tone #4a4338 with a ribbed hem
    // in the gloves' #2a231c; the coat collar's own #4a4338 is the jumper's neck; the
    // red scarf stays.
    case 'scarf_only':
      return {
        under: trousers(346),
        sleeveL: sleeve(JUMPER_SLEEVE_L, '#4a4338', 16),
        body: (
          <>
            <path d={JUMPER_BODY} fill="#4a4338" />
            <path d="M50,340 L150,340 L150,344 Q150,354 140,354 L60,354 Q50,354 50,344 Z" fill="#2a231c" />
          </>
        ),
        sleeveR: sleeve(JUMPER_SLEEVE_R, '#4a4338', 16),
        neck: (
          <>
            <path d={COAT_COLLAR} fill="#4a4338" />
            {scarf()}
          </>
        ),
      };
    // chef: a paper #f8f3e8 jacket to the hip with the double row of buttons in
    // marchand's stone grey #a59e8f, a mandarin collar in odile's #e9e4d8; the red
    // scarf stays, worn as the cook's neckerchief.
    case 'chef':
      return {
        under: trousers(350),
        sleeveL: sleeve(COAT_SLEEVE_L, '#f8f3e8', 18),
        body: (
          <>
            <path d="M52,190 Q58,168 80,166 L120,166 Q142,168 148,190 L154,346 Q154,356 144,356 L56,356 Q46,356 46,346 Z" fill="#f8f3e8" />
            {[214, 242, 270, 298, 326].map((y) => (
              <g key={y}>
                <circle cx="88" cy={y} r="2.6" fill="#a59e8f" />
                <circle cx="112" cy={y} r="2.6" fill="#a59e8f" />
              </g>
            ))}
          </>
        ),
        sleeveR: sleeve(COAT_SLEEVE_R, '#f8f3e8', 18),
        neck: (
          <>
            <path d="M-26,12 Q0,24 26,12 L28,30 Q0,42 -28,30 Z" fill="#e9e4d8" />
            {scarf()}
          </>
        ),
      };
    // hi_vis: the coat cut as a work jacket in lila's yellow #f3c318 (the only yellow
    // in the cast), two reflective bands across the back in paper #f8f3e8, the coat
    // collar #4a4338 and the red scarf kept.
    case 'hi_vis':
      return {
        sleeveL: sleeve(COAT_SLEEVE_L, '#f3c318', 18),
        body: (
          <>
            <path d={COAT_BODY} fill="#f3c318" />
            <path d="M46.5,250 L153.5,250 L154.1,260 L45.9,260 Z M42.9,310 L157.1,310 L157.8,322 L42.2,322 Z" fill="#f8f3e8" />
          </>
        ),
        sleeveR: sleeve(COAT_SLEEVE_R, '#f3c318', 18),
        neck: (
          <>
            <path d={COAT_COLLAR} fill="#4a4338" />
            {scarf()}
          </>
        ),
      };
    // coat: the canon drawing, unchanged since WP-116 phase 1.
    default:
      return {
        sleeveL: sleeve(COAT_SLEEVE_L, '#5b5346', 18),
        body: (
          <>
            <path d={COAT_BODY} fill="#5b5346" />
            <path d="M100,306 L100,372" fill="none" stroke="#4a4338" strokeWidth={2} />
            <path d="M70,288 L130,288 L130,297 L70,297 Z" fill="#4a4338" />
            <circle cx="76" cy="292.5" r="2.4" fill="#2a231c" />
            <circle cx="124" cy="292.5" r="2.4" fill="#2a231c" />
          </>
        ),
        sleeveR: sleeve(COAT_SLEEVE_R, '#5b5346', 18),
        neck: (
          <>
            <path d={COAT_COLLAR} fill="#4a4338" />
            {scarf()}
          </>
        ),
      };
  }
}

function ToiArt({ v }: { v: RigValues }) {
  const t = torso((v.extra.outfit as Outfit) || 'coat');
  return (
    <g>
      <path d="M86,366 L86,392 M114,366 L114,392" fill="none" stroke="#14285f" strokeWidth={13} strokeLinecap="round" />
      <ellipse cx="85" cy="399" rx="12" ry="6" fill="#14110d" />
      <ellipse cx="115" cy="399" rx="12" ry="6" fill="#14110d" />
      {t.under}
      {t.sleeveL}
      <circle cx="46" cy="303" r="8" fill="#2a231c" />
      {t.body}
      {t.sleeveR}
      <path d="M148,312 Q154,300 160,312" fill="none" stroke="#14110d" strokeWidth={3.5} strokeLinecap="round" />
      <path d="M138,312 L182,312 Q186,312 186,316 L186,354 Q186,358 182,358 L138,358 Q134,358 134,354 L134,316 Q134,312 138,312 Z" fill="#8a5a32" />
      <path d="M146,312 L146,358 M174,312 L174,358" fill="none" stroke="#4a3020" strokeWidth={3} />
      <circle cx="154" cy="303" r="8" fill="#2a231c" />
      <g transform={v.headT}>
      <g className="cast-rig__idle">
      {t.neck}
      <path d="M-38,10 C-40,-34 -20,-48 0,-48 C20,-48 40,-34 38,10 Z" fill="#1d3a8a" />
      <path d="M-39,-2 L39,-2 L39,12 L-39,12 Z" fill="#14285f" />
      <path d="M-26,-2 L-26,12 M-13,-2 L-13,12 M0,-2 L0,12 M13,-2 L13,12 M26,-2 L26,12" fill="none" stroke="#1d3a8a" strokeWidth={2} />
      <circle cx="0" cy="-52" r="11" fill="#f8f3e8" />
      </g>
      </g>
    </g>
  );
}

export const toi: RigDef = {
  id: 'user',
  name: 'Toi',
  head: [100, 150],
  crops: { full: [0, 0, 200, 420], bust: [10, 76, 180, 220], head: [40, 84, 120, 120] },
  idle: { kind: 'bob', seconds: 4, amount: 1.4 },
  faceless: true,
  outfits: OUTFITS,
  extra: (p) => ({ outfit: p.outfit && OUTFITS.includes(p.outfit) ? p.outfit : 'coat' }),
  Art: ToiArt,
};
