/**
 * Les objets de la saison · the drawings (see lib/season-items.ts).
 *
 *   <PlotItem id="cle_cigale" size={76} />
 *
 * Drawn the way the troupe is drawn, so the same object can sit in a card or in a hand
 * (`OfferSlot`, components/cast/vivant/parts.tsx): no outline, flat fills in the cast's own
 * colours, details in a darker or lighter shade of the same colour, thick round-capped strokes
 * for anything metal, ink only where the thing itself is black (a pen, a keyhole, a pan). Each
 * object is drawn at the figures' scale about the point a hand holds it (`grip`), so a figure
 * holds it at its palm with no conversion; the key is Margaux's own, line for line.
 *
 * Each has one small life of its own, in CSS (the key sways and the cicada swings, the Polaroid
 * develops, the padlock snaps): `still`, Reduce Motion or no JavaScript show it at rest.
 */
import React from 'react';
import type { ReactElement } from 'react';

import type { SeasonItemId } from '@/lib/season-items';

type Pt = [number, number];

const INK = '#14110d';
const CREAM = '#f8f3e8';
const PAPER = '#ffffff';
/** the sheet under a sheet: the paper's thickness, never a line */
const UNDER = '#dcd6c8';
const CELL = '#ebe5d8';
const EDGE = '#c9c2b2';
const STEEL = '#a59e8f';
const STEEL_DARK = '#6b6560';
const SOOT = '#3d3832';
const LEATHER = '#2a231c';
const LEATHER_DARK = '#1f1b16';
const RED = '#d8321a';
const YELLOW = '#f3c318';
const NAVY = '#14285f';
const BLUE = '#1d3a8a';
const SKY = '#5b86c8';
const BRASS = '#c49a0a';
const BRASS_DARK = '#a3800a';
const TEAL = '#2c6a5d';
const TEAL_DARK = '#1f4f45';
const KRAFT = '#d6c4a0';
const KRAFT_DARK = '#c0ab82';
const AGED = '#ecdfc3';
const ORANGE = '#d8742a';

/** Somebody's handwriting at a distance: one hump per letter, a tall one now and then. */
function scrawl(x0: number, y: number, words: number[], h = 1.5, step = 1.25): string {
  const tall = [1, 1.7, 1, 1, 2, 1, 1.3];
  let x = x0;
  let i = 0;
  const parts: string[] = [];
  for (const n of words) {
    let d = `M${x.toFixed(2)},${y}`;
    for (let k = 0; k < n; k += 1) {
      const up = h * tall[i % tall.length];
      d += ` q${(step * 0.15).toFixed(2)},${(-up).toFixed(2)} ${(step * 0.55).toFixed(2)},${(-up * 0.55).toFixed(2)} t${(step * 0.45).toFixed(2)},${(up * 0.55).toFixed(2)}`;
      x += step;
      i += 1;
    }
    parts.push(d);
    x += step * 1.1;
  }
  return parts.join(' ');
}

/* «Pour toi.» in Odile's hand: a monoline cursive on a baseline at 0, 30 wide. */
const POUR_TOI = [
  'M1.6,0.2 L2.1,-6.2',
  'M0.6,-5.4 C2.2,-7.2 5.8,-6.9 5.3,-4.7 C4.9,-3.1 2.9,-2.8 1.8,-3.3',
  'M8.7,-3.3 C7.3,-3.8 6,-2.4 6.4,-0.9 C6.8,0.6 9,0.2 9.2,-1.5 C9.3,-2.6 8.9,-3.2 8.7,-3.3 C9.5,-3.1 10.1,-3.3 10.5,-3.7',
  'M10.6,-3.4 C10.4,-1.8 10.2,0 11.4,0 C12.6,0 13.2,-1.6 13.5,-3.4 C13.3,-1.6 13.2,0 14.2,0',
  'M14.2,0 C14.4,-1.2 14.6,-2.4 14.8,-3.6 M14.7,-2.5 C15.4,-3.5 16.3,-3.8 17.2,-3.3',
  'M20.6,-6 C20.4,-4 20,-1.2 20.4,-0.2 C20.7,0.4 21.6,0.1 22.2,-0.6 M19.1,-3.7 L22.3,-3.9',
  'M24.8,-3.3 C23.4,-3.8 22.2,-2.4 22.6,-0.9 C23,0.6 25.2,0.2 25.4,-1.5 C25.5,-2.6 25.1,-3.2 24.8,-3.3 C25.6,-3.1 26.2,-3.3 26.6,-3.6',
  'M26.6,-3.4 C26.4,-2 26.2,-0.6 26.6,0 C26.9,0.3 27.5,0 28,-0.6',
].join(' ');

/* «M.», as written in a calendar square. */
const LETTER_M = 'M0.4,0 C0.8,-2 1,-4.4 1,-6 C1.8,-4.4 2.4,-2.6 3,-1.6 C3.8,-3 4.6,-4.8 5.4,-6.2 C5.4,-4 5.4,-1.6 6,0';

/** A small cicada, the one on the key ring: wings under a teal body. */
function Cicada({ x, y, s = 1, fill = TEAL, wing = YELLOW, detail = TEAL_DARK }: { x: number; y: number; s?: number; fill?: string; wing?: string; detail?: string }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M-1.5,2 L-8,15 L-2.5,13.5 Z M1.5,2 L8,15 L2.5,13.5 Z" fill={wing} />
      {detail ? <path d="M-2,4.4 L-5.4,12.6 M2,4.4 L5.4,12.6" fill="none" stroke={BRASS} strokeWidth={0.7} strokeLinecap="round" /> : null}
      <path d="M0,0 C3.5,0 5,6 2.6,13.5 C1.9,15.8 -1.9,15.8 -2.6,13.5 C-5,6 -3.5,0 0,0 Z" fill={fill} />
      {detail ? (
        <>
          <path d="M-2.9,3.6 Q0,4.8 2.9,3.6 M-2.6,8.4 Q0,9.4 2.6,8.4 M-2.4,11.4 Q0,12.2 2.4,11.4" fill="none" stroke={detail} strokeWidth={0.8} strokeLinecap="round" />
          <circle cx="-1.7" cy="1.8" r="0.9" fill={detail} />
          <circle cx="1.7" cy="1.8" r="0.9" fill={detail} />
        </>
      ) : null}
    </g>
  );
}

/* ------------------------------------------------------------------------------------------ */

/* T1 · la clé à la cigale. Margaux's key (rigs/margaux.tsx) about its ring: the brass ring, the
 * shaft and its two teeth, and the cicada on its own little ring. */
function CleCigale() {
  return (
    <g className="pi-key">
      <circle r="9" fill="none" stroke={BRASS} strokeWidth={4} />
      <path d="M-8.2,-2.6 A8.6,8.6 0 0 1 -2.4,-8.3" fill="none" stroke={CREAM} strokeWidth={1.3} strokeLinecap="round" opacity={0.55} />
      <path d="M-1.7,9 L1.7,9 L1.7,54 L-1.7,54 Z M1.7,45 L7,45 L7,49 L1.7,49 Z M1.7,50.5 L6,50.5 L6,54 L1.7,54 Z" fill={BRASS} />
      <path d="M-0.6,12 L-0.6,50.5" fill="none" stroke={CREAM} strokeWidth={0.8} strokeLinecap="round" opacity={0.45} />
      <g className="pi-cigale">
        <circle cx="12.5" cy="6" r="2.4" fill="none" stroke={BRASS} strokeWidth={1.5} />
        <Cicada x={16} y={9} />
      </g>
    </g>
  );
}

/* T2 · le calendrier d'Odile. The post-office kind, on its nail upstairs: a picture of the south
 * (a cypress, a mas, the sun), November, the Sundays in red, her notes in the squares, and one
 * Sunday circled, «M.». */
function Calendrier() {
  const wires = [-14, -11.2, -8.4, -5.6, 5.6, 8.4, 11.2, 14];
  const cells: ReactElement[] = [];
  for (let r = 0; r < 5; r += 1) {
    for (let c = 0; c < 7; c += 1) {
      const x = -13.8 + c * 4;
      const y = -22.2 + r * 4.1;
      // the first week is still October's: only the Sunday is November's first
      const before = r === 0 && c < 6;
      cells.push(<rect key={`${r}-${c}`} x={x} y={y} width="3.2" height="3.2" rx="0.4" fill={c === 6 ? '#f1cdbf' : CELL} opacity={before ? 0.45 : 1} />);
    }
  }
  const note = (c: number, r: number) => scrawl(-13.4 + c * 4, -19.8 + r * 4.1, [2], 0.7, 1.1);
  return (
    <g>
      <rect x="-15.8" y="-42.8" width="34" height="44" rx="1.6" fill={UNDER} />
      <path d="M-3.6,-44 L-2.6,-48.4 Q0,-50.6 2.6,-48.4 L3.6,-44 Z" fill={CREAM} />
      <circle cx="0" cy="-47.4" r="1.1" fill={SOOT} />
      <rect x="-17" y="-44" width="34" height="44" rx="1.6" fill={CREAM} />
      <path d={wires.map((x) => `M${x},-45.4 L${x},-42.2`).join(' ')} fill="none" stroke={SOOT} strokeWidth={1.2} strokeLinecap="round" />
      {/* the picture */}
      <rect x="-14" y="-40.6" width="28" height="12" fill={SKY} />
      <circle cx="8.6" cy="-36.6" r="2.4" fill={YELLOW} />
      <path d="M-14,-32 Q-7,-35 0,-32.6 Q7,-30.6 14,-33 L14,-28.6 L-14,-28.6 Z" fill={TEAL} />
      <path d="M-14,-30.6 Q0,-32.4 14,-30.2 L14,-28.6 L-14,-28.6 Z" fill={BRASS} />
      <rect x="1.4" y="-33.4" width="5.4" height="3.4" fill={CREAM} />
      <path d="M0.8,-33.4 L4.1,-35.6 L7.4,-33.4 Z" fill={RED} />
      <rect x="3.5" y="-31.6" width="1.2" height="1.6" fill={SOOT} />
      <path d="M-8.6,-29.4 C-10.6,-32 -10,-36.4 -8.6,-39.2 C-7.2,-36.4 -6.6,-32 -8.6,-29.4 Z M-5.2,-29.6 C-6.4,-31.4 -6,-34 -5.2,-35.6 C-4.4,-34 -4,-31.4 -5.2,-29.6 Z" fill={TEAL_DARK} />
      {/* NOVEMBRE */}
      <rect x="-14" y="-27" width="28" height="3.4" rx="0.4" fill={RED} />
      <path d="M-11.6,-25.3 L-2.4,-25.3 M7.4,-25.3 L11.6,-25.3" fill="none" stroke={CREAM} strokeWidth={1.1} strokeLinecap="round" />
      {cells}
      <path d={[note(2, 1), note(4, 3), note(0, 2), note(1, 4), note(3, 2)].join(' ')} fill="none" stroke={NAVY} strokeWidth={0.5} strokeLinecap="round" />
      {/* dimanche : M. */}
      <path transform="translate(10.6 -11.2) skewX(-14) scale(0.34)" d={LETTER_M} fill="none" stroke={NAVY} strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="13.6" cy="-11.3" r="0.32" fill={NAVY} />
      <path className="pi-circle" d="M15,-14.6 C13.6,-16.4 9.2,-15.6 8.8,-12.6 C8.4,-9.6 13.8,-9 15.2,-11.2 C15.9,-12.4 15.4,-14.8 12.6,-15.2" fill="none" stroke={RED} strokeWidth={0.8} strokeLinecap="round" />
      <path className="pi-curl" d="M17,-6.4 L17,-1.6 Q17,0 15.4,0 L10.6,0 Q14.2,-2.6 17,-6.4 Z" fill={CELL} />
    </g>
  );
}

/* T3 · la pétition. On a kraft clipboard from the mairie: «Sauvons le Mistral» in red, rows of
 * signatures in blue, Gus's own across the bottom in red, and his fountain pen. */
function Petition() {
  return (
    <g>
      <rect x="-17" y="-46" width="34" height="46" rx="2.4" fill={KRAFT} />
      <path d="M-17,-2.6 L17,-2.6 L17,-2.4 Q17,0 14.6,0 L-14.6,0 Q-17,0 -17,-2.4 Z" fill={KRAFT_DARK} />
      <rect x="-13.2" y="-41.2" width="28" height="37.4" fill={UNDER} />
      <rect x="-14" y="-42" width="28" height="37.4" fill={PAPER} />
      <path d="M-8.4,-42.6 L8.4,-42.6 L7.4,-39.6 L-7.4,-39.6 Z" fill={STEEL_DARK} />
      <path d="M-6.4,-47.6 Q-6.4,-49.4 -4.6,-49.4 L4.6,-49.4 Q6.4,-49.4 6.4,-47.6 L7.6,-41.6 L-7.6,-41.6 Z" fill={STEEL} />
      <rect x="-2.6" y="-47.8" width="5.2" height="2" rx="1" fill={STEEL_DARK} />
      <path d="M-5.6,-43.4 L5.6,-43.4" fill="none" stroke={EDGE} strokeWidth={0.9} strokeLinecap="round" />
      <rect x="-11.6" y="-38.6" width="23.2" height="4.4" rx="0.6" fill={RED} />
      <path d="M-9.6,-36.4 L-3.4,-36.4 M-1.6,-36.4 L0.6,-36.4 M2.4,-36.4 L9.6,-36.4" fill="none" stroke={CREAM} strokeWidth={1.3} strokeLinecap="round" />
      <path d="M-7,-31.6 L7,-31.6" fill="none" stroke={EDGE} strokeWidth={0.8} strokeLinecap="round" />
      <path d="M-11.4,-26.6 L11.4,-26.6 M-11.4,-22.6 L11.4,-22.6 M-11.4,-18.6 L11.4,-18.6 M-11.4,-14.6 L11.4,-14.6" fill="none" stroke="#e6e0d3" strokeWidth={0.5} />
      <path
        d="M-10.4,-27.2 c.8,-2.6 2,-2.4 1.6,-.4 s1.4,-1.8 2,-.4 s1.2,-.8 2.2,-.6 m1.6,.2 c1.4,-1.6 2.4,-1.8 2.8,-.6 s1.2,-.4 2.6,-1
           M-10.6,-23.2 c1.4,-.4 1.8,-2.6 .4,-2.4 c-1,.2 -.2,2.8 1.6,2.2 s1.6,-1.6 2.6,-1 s1.6,.2 3,-.6 m1.2,.4 c.6,-.8 1.4,-.8 1.8,0
           M-10.2,-19.2 c.4,-2 .8,-2.4 1.4,-.4 c.4,-1.4 1.2,-1.6 1.4,-.2 c.6,-1.8 1.8,-1.4 1.6,0 s1.8,-.6 3.2,-1.2 m1.4,.8 c.4,-1 1.2,-1.4 1.8,-.4
           M-10.6,-15.4 c2,-.8 3,-2.4 1.4,-2.2 s-.6,2.4 1,2 s2.4,-1.6 3.2,-1.2 s.8,1 2.2,.2 m1.4,-.2 c.8,-1.4 1.8,-1.2 2,.2"
        fill="none"
        stroke={BLUE}
        strokeWidth={0.85}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Augustin de Roncourt, with a flourish */}
      <path
        className="pi-ink"
        d="M-10.4,-8.6 C-9.6,-13.4 -6.6,-13.6 -7.6,-10 C-8.4,-7.4 -5,-8 -3.6,-11.2 C-3,-8.4 -1.2,-8 0.4,-10.8 C1.2,-8.6 2.8,-8.4 4.4,-11 C5.2,-9 7,-9.2 9.4,-12 M-11.2,-6.6 C-4.4,-4.8 3.6,-5.2 11.6,-7.4"
        fill="none"
        stroke={RED}
        strokeWidth={1.05}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <g className="pi-pen">
        <path d="M8.3,-5.4 L4.5,-3.7 L6.5,-7.4 Z" fill={BRASS} />
        <path d="M4.9,-4.1 L6.6,-5.6" fill="none" stroke={BRASS_DARK} strokeWidth={0.4} strokeLinecap="round" />
        <path d="M7.4,-6.4 L18.6,-16.8" fill="none" stroke={INK} strokeWidth={3.4} strokeLinecap="round" />
        <path d="M9.1,-9.1 L13.6,-13.3" fill="none" stroke={CREAM} strokeWidth={0.7} strokeLinecap="round" opacity={0.35} />
        <path d="M14.2,-12.7 L15.2,-13.6" fill="none" stroke={BRASS} strokeWidth={3.6} />
      </g>
    </g>
  );
}

/* T4 · le Polaroid. One of Odile's: her kitchen at night, the window, the shelf, the stove, and
 * a flame on the pan climbing the wall; the date in orange in the corner, her caption under it.
 * It develops as you look. */
function Polaroid() {
  return (
    <g transform="rotate(-4 0 -18.5)">
      <rect x="-13.8" y="-35.8" width="30" height="37" rx="1" fill={UNDER} />
      <rect x="-15" y="-37" width="30" height="37" rx="1" fill={PAPER} />
      <rect x="-12.6" y="-34.6" width="25.2" height="25.2" fill={SOOT} />
      <circle cx="6.4" cy="-22.4" r="6" fill={RED} opacity={0.3} />
      <rect x="-10.4" y="-32" width="8.6" height="9.6" fill={NAVY} />
      <circle cx="-8.4" cy="-29.8" r="1.1" fill={CREAM} />
      <path d="M-6.1,-32 L-6.1,-22.4 M-10.4,-27.2 L-1.8,-27.2" fill="none" stroke={SOOT} strokeWidth={0.9} />
      <rect x="1" y="-30.4" width="11.6" height="1.2" fill={STEEL_DARK} />
      <rect x="2.2" y="-32.6" width="2" height="2.2" fill={BRASS} />
      <rect x="5.2" y="-32" width="1.8" height="1.6" fill={CREAM} />
      <rect x="8" y="-33" width="2.4" height="2.6" fill={TEAL} />
      <rect x="-12.6" y="-12.4" width="25.2" height="3" fill={LEATHER} />
      <rect x="0.4" y="-18.6" width="12.2" height="6.6" fill={STEEL_DARK} />
      <rect x="0" y="-19.4" width="12.6" height="1.2" fill={STEEL} />
      <rect x="2" y="-16.8" width="8.8" height="3.8" rx="0.4" fill={SOOT} />
      <path d="M2.6,-19.4 L9.4,-19.4 L8.8,-21.6 L3.2,-21.6 Z" fill={INK} />
      <path d="M9.2,-21 L12.2,-22" fill="none" stroke={INK} strokeWidth={1.1} strokeLinecap="round" />
      <g className="pi-flame">
        <path d="M3.4,-21.6 C2.2,-24.4 4.4,-26 3.8,-29.4 C5.8,-27.4 6.2,-25.6 6.8,-27.2 C8.6,-25.2 9.8,-23.6 8.8,-21.6 Z" fill={RED} />
        <path d="M4.6,-21.6 C4,-23.4 5.4,-24.4 5.2,-26.2 C6.4,-24.8 6.8,-24 7.2,-24.8 C8,-23.6 8.4,-22.6 7.8,-21.6 Z" fill={YELLOW} />
      </g>
      <path d="M6.2,-29.8 C4.4,-31.2 6.6,-32.4 5,-34" fill="none" stroke={STEEL} strokeWidth={1.2} strokeLinecap="round" opacity={0.7} />
      <path d="M5.4,-10.9 L6.4,-10.9 M7.2,-10.9 L8.2,-10.9 M9.4,-10.9 L10.4,-10.9 M11,-10.9 L12,-10.9" fill="none" stroke={ORANGE} strokeWidth={0.6} strokeLinecap="round" />
      <rect className="pi-murk" x="-12.6" y="-34.6" width="25.2" height="25.2" fill="#3c4252" opacity={0} />
      <path d={scrawl(-10.4, -4.2, [3, 4, 2], 1.4, 1.3)} fill="none" stroke={BLUE} strokeWidth={0.75} strokeLinecap="round" strokeLinejoin="round" />
    </g>
  );
}

/* T5 · la lettre de Berlin. A par avion envelope cut open along the top, the letter half out
 * (the residency's navy letterhead), a stamp with the Fernsehturm, the postmark across it. */
function LettreBerlin() {
  const perf: ReactElement[] = [];
  for (let i = 0; i <= 6; i += 1) {
    const x = 10.4 + i * 1.4;
    perf.push(<circle key={`t${i}`} cx={x} cy="-22.8" r="0.55" fill={PAPER} />, <circle key={`b${i}`} cx={x} cy="-12.8" r="0.55" fill={PAPER} />);
  }
  for (let i = 0; i <= 7; i += 1) {
    const y = -22.8 + i * 1.43;
    perf.push(<circle key={`l${i}`} cx="10.4" cy={y} r="0.55" fill={PAPER} />, <circle key={`r${i}`} cx="18.8" cy={y} r="0.55" fill={PAPER} />);
  }
  const waves = [-18.4, -15.6, -12.8].map((y) => `M-5,${y} q1.4,-1.2 2.8,0 t2.8,0 t2.8,0 t2.8,0`).join(' ');
  return (
    <g>
      <g className="pi-slide">
        <g transform="rotate(-3 0 -27)">
          <rect x="-17.6" y="-37.4" width="35.2" height="26" fill={PAPER} />
          <rect x="-17.6" y="-37.4" width="35.2" height="4.6" fill={NAVY} />
          <rect x="-15.4" y="-36.3" width="2.4" height="2.4" fill={YELLOW} />
          <path d="M-11.6,-35.1 L-2,-35.1" fill="none" stroke={CREAM} strokeWidth={0.9} strokeLinecap="round" />
          <path d="M-14.6,-30 L8,-30 M-14.6,-27.6 L4,-27.6" fill="none" stroke={EDGE} strokeWidth={0.9} strokeLinecap="round" />
        </g>
      </g>
      <rect x="-23" y="-27" width="46" height="27" rx="1.2" fill={PAPER} />
      <path d="M-22.4,-27 L22.4,-27" fill="none" stroke={UNDER} strokeWidth={1} strokeLinecap="round" />
      <rect x="-21.6" y="-25.6" width="43.2" height="24.2" fill="none" stroke={RED} strokeWidth={1.8} strokeDasharray="2.4 4.8" />
      <rect x="-21.6" y="-25.6" width="43.2" height="24.2" fill="none" stroke={BLUE} strokeWidth={1.8} strokeDasharray="2.4 4.8" strokeDashoffset={-3.6} />
      <rect x="-19.4" y="-23.2" width="10.6" height="3.4" rx="0.4" fill={BLUE} />
      <path d="M-17.8,-21.5 L-10.4,-21.5" fill="none" stroke={CREAM} strokeWidth={0.8} strokeLinecap="round" />
      {/* the stamp: the tower at Alexanderplatz */}
      <rect x="10.4" y="-22.8" width="8.4" height="10" fill={YELLOW} />
      {perf}
      <path d="M14.6,-14.6 L14.6,-21.4" fill="none" stroke={NAVY} strokeWidth={0.7} strokeLinecap="round" />
      <circle cx="14.6" cy="-18.4" r="1.4" fill={NAVY} />
      <path d="M13.4,-13.6 L15.8,-13.6 L15.1,-15 L14.1,-15 Z" fill={NAVY} />
      <path d="M11.8,-21.2 L12.9,-21.2" fill="none" stroke={RED} strokeWidth={0.7} strokeLinecap="round" />
      <circle cx="9.6" cy="-15.2" r="4.2" fill="none" stroke={STEEL_DARK} strokeWidth={0.55} />
      <circle cx="9.6" cy="-15.2" r="3" fill="none" stroke={STEEL_DARK} strokeWidth={0.4} />
      <path d={waves} fill="none" stroke={STEEL_DARK} strokeWidth={0.55} strokeLinecap="round" />
      <path d={`${scrawl(-17, -8.4, [4, 6], 1.3, 1.2)} ${scrawl(-17, -4.4, [5, 3, 4], 1.3, 1.2)}`} fill="none" stroke={NAVY} strokeWidth={0.7} strokeLinecap="round" strokeLinejoin="round" />
    </g>
  );
}

/* T6 · le carnet noir. Her black notebook, the cicada pressed into the cover in gold, the red
 * ribbon out of the bottom, and a Polaroid kept between the pages. */
function CarnetNoir() {
  return (
    <g>
      <g className="pi-peek">
        <g transform="rotate(8 2 -42)">
          <rect x="-4" y="-47.4" width="12" height="9" fill={PAPER} />
          <rect x="-2.8" y="-46.2" width="9.6" height="6" fill={SKY} />
          <circle cx="4.6" cy="-44.4" r="1.3" fill={YELLOW} />
          <path d="M-2.8,-41.2 Q1,-43 6.8,-41.6 L6.8,-40.2 L-2.8,-40.2 Z" fill={TEAL} />
        </g>
      </g>
      <rect x="-14.6" y="-41.6" width="30" height="41.6" rx="3" fill={CREAM} />
      <path d="M14.4,-38 L14.4,-4" fill="none" stroke={UNDER} strokeWidth={0.5} />
      <rect x="-15" y="-42" width="29" height="42" rx="3" fill={LEATHER} />
      <path d="M-12,-42 L-10.4,-42 L-10.4,0 L-12,0 Q-15,0 -15,-3 L-15,-39 Q-15,-42 -12,-42 Z" fill={LEATHER_DARK} />
      <path d="M-7.6,-39.6 Q1,-40.6 11,-39.2" fill="none" stroke={CREAM} strokeWidth={0.9} strokeLinecap="round" opacity={0.16} />
      <rect x="8.4" y="-42" width="1.8" height="42" fill={SOOT} />
      <g transform="translate(-0.6 -31)">
        <path d="M-1.2,2.6 C-4.6,3.2 -7.4,7 -7.2,11.6 C-4.8,10.6 -2.6,7.8 -1.4,4.8 Z M1.2,2.6 C4.6,3.2 7.4,7 7.2,11.6 C4.8,10.6 2.6,7.8 1.4,4.8 Z" fill={BRASS} opacity={0.85} />
        <path d="M0,-0.6 C2,-0.6 2.8,3.4 1.6,8.4 C1.1,9.8 -1.1,9.8 -1.6,8.4 C-2.8,3.4 -2,-0.6 0,-0.6 Z" fill={BRASS} stroke={LEATHER} strokeWidth={0.8} />
        <path d="M-1.6,3 Q0,3.8 1.6,3 M-1.5,5.6 Q0,6.3 1.5,5.6" fill="none" stroke={LEATHER} strokeWidth={0.5} strokeLinecap="round" />
      </g>
      <g className="pi-ribbon">
        <path d="M2.6,-0.6 L2.6,7 L4,5.6 L5.4,7 L5.4,-0.6 Z" fill={RED} />
      </g>
    </g>
  );
}

/* T7 · la chaîne de Gus. His bicycle chain, slung over a hand, both ends locked into a brass
 * padlock: «je ne bouge pas d'ici». */
const CHAIN_D = 'M-5,28.4 C-12.6,18 -11,3.6 0,0.6 C11,3.6 12.6,18 5,28.4';
function Chaine() {
  return (
    <g>
      <g className="pi-chain">
        <path d={CHAIN_D} fill="none" stroke={SOOT} strokeWidth={4.6} strokeLinecap="round" />
        <path d={CHAIN_D} fill="none" stroke={STEEL} strokeWidth={3.2} strokeDasharray="2.8 1.4" />
        <path d={CHAIN_D} fill="none" stroke={STEEL_DARK} strokeWidth={1.5} strokeLinecap="round" strokeDasharray="0 4.2" strokeDashoffset={0.7} />
        <path d={CHAIN_D} fill="none" stroke={EDGE} strokeWidth={0.7} strokeDasharray="1.6 2.6" strokeDashoffset={-0.6} />
      </g>
      <g className="pi-lock">
        <g className="pi-shackle">
          <path d="M-4.6,34.4 L-4.6,30.2 A4.6,4.6 0 0 1 4.6,30.2 L4.6,34.4" fill="none" stroke={STEEL} strokeWidth={2.6} strokeLinecap="round" />
          <path d="M-4.6,32.4 L-4.6,30.2 A4.6,4.6 0 0 1 -1.2,25.8" fill="none" stroke={EDGE} strokeWidth={0.8} strokeLinecap="round" />
        </g>
        <rect x="-7.6" y="33" width="15.2" height="12.6" rx="2.6" fill={BRASS} />
        <path d="M-7.6,42.4 L7.6,42.4 L7.6,43 Q7.6,45.6 5,45.6 L-5,45.6 Q-7.6,45.6 -7.6,43 Z" fill={BRASS_DARK} />
        <path d="M-5.4,35.3 L5.4,35.3" fill="none" stroke={YELLOW} strokeWidth={1.1} strokeLinecap="round" opacity={0.8} />
        <circle cx="0" cy="38.4" r="1.5" fill={LEATHER} />
        <path d="M-0.7,39 L0.7,39 L1.1,42 L-1.1,42 Z" fill={LEATHER} />
      </g>
    </g>
  );
}

/* T8 · l'enveloppe d'Odile. The one from behind the radiator: yellowed, a strip of old tape, the
 * dust and a cobweb, «Pour toi.» in her hand and the rest of the line under it, and a cicada
 * drawn in the corner. */
function Enveloppe() {
  return (
    <g>
      <path d="M-21.6,-30 L21.6,-30 Q23,-30 23,-28.6 L23,-6.4 L16.6,0 L-21.6,0 Q-23,0 -23,-1.4 L-23,-28.6 Q-23,-30 -21.6,-30 Z" fill={AGED} />
      <path d="M23,-6.4 L16.6,0 L17.6,-5.4 Z" fill={KRAFT} />
      <ellipse cx="12" cy="-24.4" rx="7.4" ry="3" fill={STEEL} opacity={0.2} />
      <ellipse cx="-15" cy="-3.4" rx="5.4" ry="2" fill={STEEL} opacity={0.16} />
      <g fill={KRAFT}>
        <circle cx="-17" cy="-24.6" r="0.7" />
        <circle cx="-14.2" cy="-26.4" r="0.5" />
        <circle cx="11.6" cy="-4.2" r="0.6" />
        <circle cx="-19.2" cy="-7" r="0.6" />
      </g>
      <path d="M23,-30 L17.4,-30 M23,-30 L23,-24.4 M23,-30 L18.6,-25.6 M19.6,-30 Q20.4,-27.6 23,-27 M18.2,-30 Q19.6,-26.2 23,-25.6" fill="none" stroke={STEEL} strokeWidth={0.35} opacity={0.9} />
      <path d="M-26.4,-24.2 L-16.6,-32.6 L-14.2,-29.8 L-24,-21.4 Z" fill={YELLOW} opacity={0.42} />
      <g transform="translate(-13.6 -14.6) scale(0.84)">
        <path d={POUR_TOI} fill="none" stroke={NAVY} strokeWidth={1.25} strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="27" cy="-5.4" r="0.6" fill={NAVY} />
        <circle cx="29.4" cy="0" r="0.7" fill={NAVY} />
      </g>
      <path d={scrawl(-12.4, -8, [5, 2, 8, 8], 1, 1)} fill="none" stroke={NAVY} strokeWidth={0.55} strokeLinecap="round" strokeLinejoin="round" />
      <g transform="translate(16.4 -20.6) scale(0.42)">
        <path d="M0,0 C3.5,0 5,6 2.6,13.5 C1.9,15.8 -1.9,15.8 -2.6,13.5 C-5,6 -3.5,0 0,0 Z M-1.5,2.4 L-8,15 M1.5,2.4 L8,15 M-2.4,4 Q0,5 2.4,4" fill="none" stroke={NAVY} strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <g className="pi-dust">
        <circle cx="-6" cy="2" r="0.6" fill={STEEL} />
        <circle cx="3" cy="2.6" r="0.45" fill={STEEL} />
        <circle cx="10" cy="1.6" r="0.5" fill={STEEL} />
      </g>
    </g>
  );
}

/* ------------------------------------------------------------------------------------------ */

export type ItemArt = {
  /** the card's square view of it */
  box: [number, number, number, number];
  /** where a hand holds it (the origin of its drawing) */
  grip: Pt;
  Art: () => ReactElement;
};

export const ITEM_ART: Record<SeasonItemId, ItemArt> = {
  cle_cigale: { box: [-31.5, -16, 76, 76], grip: [0, 0], Art: CleCigale },
  calendrier: { box: [-27, -52, 56, 56], grip: [0, 0], Art: Calendrier },
  petition: { box: [-27.2, -53.7, 58, 58], grip: [0, 0], Art: Petition },
  polaroid: { box: [-26, -44.5, 52, 52], grip: [0, 0], Art: Polaroid },
  lettre_berlin: { box: [-27.5, -46, 55, 55], grip: [0, 0], Art: LettreBerlin },
  carnet_noir: { box: [-29, -49.3, 58, 58], grip: [0, 0], Art: CarnetNoir },
  chaine: { box: [-27, -4.8, 54, 54], grip: [0, 0], Art: Chaine },
  enveloppe: { box: [-29, -43.4, 54, 54], grip: [0, 0], Art: Enveloppe },
};

/** The drawing alone, in its own frame: what a card shows and a hand holds. */
export function ItemDrawing({ id, still = false }: { id: SeasonItemId; still?: boolean }) {
  const art = ITEM_ART[id];
  if (!art) return null;
  const { Art } = art;
  return (
    <g className={['pi-art', `pi-art--${id}`, still ? 'pi-art--still' : ''].filter(Boolean).join(' ')} data-plot-item={id}>
      <Art />
    </g>
  );
}

/* Every moving piece is its own group with no transform of its own (a CSS transform would
 * replace it), turning about its own box. */
export const PLOT_ITEM_CSS = `
.plot-item { display: block; overflow: visible; }
.pi-art .pi-key, .pi-art .pi-cigale, .pi-art .pi-curl, .pi-art .pi-pen, .pi-art .pi-flame, .pi-art .pi-slide,
.pi-art .pi-peek, .pi-art .pi-ribbon, .pi-art .pi-chain, .pi-art .pi-shackle, .pi-art .pi-dust { transform-box: fill-box; }
.pi-art .pi-key { transform-origin: 31% 0%; animation: pi-sway 2.6s ease-in-out infinite alternate; }
.pi-art .pi-cigale { transform-origin: 28% 0%; animation: pi-swing 1.3s ease-in-out infinite alternate; }
.pi-art .pi-circle { stroke-dasharray: 26; stroke-dashoffset: 26; animation: pi-draw 900ms 500ms ease-out forwards; }
.pi-art .pi-curl { transform-origin: 100% 100%; animation: pi-curl 2.4s ease-in-out infinite alternate; }
.pi-art .pi-ink { stroke-dasharray: 96; stroke-dashoffset: 96; animation: pi-draw 1.4s 300ms ease-in-out forwards; }
.pi-art .pi-pen { transform-origin: 0% 100%; animation: pi-write 260ms ease-in-out 6 alternate both; }
.pi-art .pi-murk { opacity: 1; animation: pi-develop 2.8s 200ms ease-in forwards; }
.pi-art .pi-flame { transform-origin: 50% 100%; animation: pi-flicker 420ms ease-in-out infinite alternate; }
.pi-art .pi-slide { animation: pi-rise 900ms 250ms cubic-bezier(.2,1.4,.4,1) both; }
.pi-art .pi-peek { animation: pi-peek 3.2s ease-in-out infinite alternate; }
.pi-art .pi-ribbon { transform-origin: 50% 0%; animation: pi-sway 1.9s ease-in-out infinite alternate; }
.pi-art .pi-chain { transform-origin: 50% 0%; animation: pi-sway 2.2s ease-in-out infinite alternate; }
.pi-art .pi-shackle { animation: pi-snap 2.4s ease-in-out infinite; }
.pi-art .pi-dust { animation: pi-fall 2.6s ease-in infinite; }
@keyframes pi-sway { from { transform: rotate(-4deg); } to { transform: rotate(4deg); } }
@keyframes pi-swing { from { transform: rotate(-12deg); } to { transform: rotate(10deg); } }
@keyframes pi-draw { to { stroke-dashoffset: 0; } }
@keyframes pi-curl { from { transform: scale(0.55); } to { transform: scale(1); } }
@keyframes pi-write { from { transform: translate(0, 0) rotate(0); } to { transform: translate(-1.2px, 0.6px) rotate(-3deg); } }
@keyframes pi-develop { to { opacity: 0; } }
@keyframes pi-flicker { from { transform: scale(1, 0.86); } to { transform: scale(0.94, 1.08); } }
@keyframes pi-rise { from { transform: translateY(8px); } to { transform: translateY(0); } }
@keyframes pi-peek { from { transform: translateY(1.5px); } to { transform: translateY(-1px); } }
@keyframes pi-snap { 0%, 55%, 100% { transform: translateY(0); } 64% { transform: translateY(-2.6px); } 72% { transform: translateY(0); } 78% { transform: translateY(-0.8px); } 84% { transform: translateY(0); } }
@keyframes pi-fall { from { transform: translateY(-1px); opacity: 0.9; } to { transform: translateY(7px); opacity: 0; } }
.pi-art--still, .pi-art--still *, .tv--still .pi-art, .tv--still .pi-art * { animation: none !important; }
.pi-art--still .pi-murk, .pi-art--still .pi-dust, .tv--still .pi-art .pi-murk, .tv--still .pi-art .pi-dust { opacity: 0; }
.pi-art--still .pi-circle, .pi-art--still .pi-ink, .tv--still .pi-art .pi-circle, .tv--still .pi-art .pi-ink { stroke-dashoffset: 0; }
@media (prefers-reduced-motion: reduce) {
  .pi-art, .pi-art * { animation: none !important; }
  .pi-art .pi-murk, .pi-art .pi-dust { opacity: 0; }
  .pi-art .pi-circle, .pi-art .pi-ink { stroke-dashoffset: 0; }
}
`;

export function PlotItem({
  id,
  size = 64,
  still = false,
  label,
  className,
  css = 'scoped',
}: {
  id: SeasonItemId;
  size?: number;
  still?: boolean;
  /** what a screen reader hears; none when the name is printed beside it */
  label?: string;
  className?: string;
  /** `none` when the page already carries PLOT_ITEM_CSS */
  css?: 'scoped' | 'none';
}) {
  const art = ITEM_ART[id];
  if (!art) return null;
  return (
    <svg
      viewBox={art.box.join(' ')}
      width={size}
      height={size}
      className={['plot-item', `plot-item--${id}`, className ?? ''].filter(Boolean).join(' ')}
      role={label ? 'img' : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {css === 'scoped' ? <style dangerouslySetInnerHTML={{ __html: PLOT_ITEM_CSS }} /> : null}
      <ItemDrawing id={id} still={still} />
    </svg>
  );
}

export const PLOT_ITEM_IDS = Object.keys(ITEM_ART) as SeasonItemId[];

export default PlotItem;
