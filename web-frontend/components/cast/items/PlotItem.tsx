/**
 * Les objets de la saison · the drawings (see lib/season-items.ts).
 *
 *   <PlotItem id="cle_cigale" size={72} />
 *
 * Drawn like the troupe: flat fills in the cast's own colours, one ink line. Each object has
 * one small movement of its own (the key swings on its ring, the Polaroid develops, the padlock
 * jumps), in CSS, so Reduce Motion or `still` shows it at rest.
 */
import React from 'react';

import type { SeasonItemId } from '@/lib/season-items';

const INK = '#14110d';
const PAPER = '#f8f3e8';
const CREAM = '#efe6d2';
const YELLOW = '#f3c318';
const RED = '#d8321a';
const NAVY = '#14285f';
const BRASS = '#c9962a';
const TEAL = '#2e6e60';
const SW = 2;

const DRAWINGS: Record<SeasonItemId, () => React.ReactElement> = {
  cle_cigale: () => (
    <g className="pi-swing">
      <circle cx="32" cy="10" r="7" fill="none" stroke={INK} strokeWidth={SW} />
      {/* the key */}
      <g>
        <circle cx="25" cy="24" r="7" fill={BRASS} stroke={INK} strokeWidth={SW} />
        <circle cx="25" cy="24" r="2.6" fill={PAPER} stroke={INK} strokeWidth="1.4" />
        <path d="M28 30l12 20" stroke={INK} strokeWidth="5.6" strokeLinecap="round" />
        <path d="M28 30l12 20" stroke={BRASS} strokeWidth="2.6" strokeLinecap="round" />
        <path d="M36 44l5-3M38.5 48l4-2.4" stroke={INK} strokeWidth={SW} strokeLinecap="round" />
      </g>
      {/* the cicada */}
      <g className="pi-flutter">
        <path d="M38 14l3 5" stroke={INK} strokeWidth="1.4" />
        <ellipse cx="44" cy="27" rx="4.2" ry="7.5" fill={TEAL} stroke={INK} strokeWidth={SW} />
        <path d="M40 24q-8 2-6 11q5-2 7-8M48 24q8 2 6 11q-5-2-7-8" fill="#cfe6dd" fillOpacity="0.85" stroke={INK} strokeWidth="1.3" strokeLinejoin="round" />
        <circle cx="42.4" cy="21.5" r="1.1" fill={YELLOW} />
        <circle cx="45.6" cy="21.5" r="1.1" fill={YELLOW} />
      </g>
    </g>
  ),
  calendrier: () => (
    <g>
      <rect x="11" y="10" width="42" height="46" rx="3" fill={PAPER} stroke={INK} strokeWidth={SW} />
      <rect x="11" y="10" width="42" height="11" rx="3" fill={RED} stroke={INK} strokeWidth={SW} />
      <text x="32" y="18.6" textAnchor="middle" fontSize="7" fontWeight="700" fill={PAPER} fontFamily="Georgia, serif">NOV.</text>
      <path d="M20 7v7M44 7v7" stroke={INK} strokeWidth="2.6" strokeLinecap="round" />
      {Array.from({ length: 4 }, (_, r) => Array.from({ length: 5 }, (_, c) => (
        <rect key={`${r}-${c}`} x={15 + c * 7} y={25 + r * 6.6} width="5" height="4.2" rx="0.8" fill={CREAM} />
      )))}
      {/* «dimanche : M.» */}
      <ellipse cx="45.5" cy="34.4" rx="5.6" ry="4.6" fill="none" stroke={RED} strokeWidth="1.6" className="pi-circle" />
      <text x="45.5" y="36.4" textAnchor="middle" fontSize="6" fontStyle="italic" fill={NAVY} fontFamily="Georgia, serif">M.</text>
      <path className="pi-corner" d="M53 46v7a3 3 0 0 1-3 3h-7z" fill={CREAM} stroke={INK} strokeWidth="1.4" strokeLinejoin="round" />
    </g>
  ),
  petition: () => (
    <g>
      <rect x="13" y="9" width="36" height="47" rx="3" fill={NAVY} stroke={INK} strokeWidth={SW} />
      <rect x="17" y="14" width="28" height="38" rx="1" fill={PAPER} stroke={INK} strokeWidth="1.4" />
      <rect x="24" y="6" width="14" height="7" rx="2" fill={BRASS} stroke={INK} strokeWidth={SW} />
      <text x="31" y="21.5" textAnchor="middle" fontSize="4.6" fontWeight="700" fill={INK} fontFamily="Georgia, serif" letterSpacing="0.4">PÉTITION</text>
      <path d="M20 27q3-3 6 0t6 0M20 33q2-2 5 0t7-1M20 39q3-2 5 1t5-1t4 0M20 45q2-3 5 0" fill="none" stroke={NAVY} strokeWidth="1.1" strokeLinecap="round" />
      <text x="41" y="48" textAnchor="middle" fontSize="6.4" fontWeight="700" fill={RED} fontFamily="Georgia, serif">187</text>
      {/* Gus's fountain pen, still signing */}
      <g className="pi-sign">
        <path d="M58 24L40 44l-2 5 5-2 18-20z" fill={INK} />
        <path d="M58.5 26.5L56 24" stroke={BRASS} strokeWidth="1.6" />
        <path d="M38 49l1.8-0.8" stroke={BRASS} strokeWidth="1.4" />
      </g>
    </g>
  ),
  polaroid: () => (
    <g transform="rotate(-6 32 32)">
      <rect x="12" y="8" width="40" height="48" rx="1.6" fill="#fdfbf5" stroke={INK} strokeWidth={SW} />
      <rect x="16" y="12" width="32" height="31" fill="#3a3229" stroke={INK} strokeWidth="1.2" />
      {/* the picture comes up out of the dark: a kitchen window, a stove, a glow */}
      <g className="pi-develop">
        <rect x="16" y="12" width="32" height="31" fill="#e6c88f" />
        <rect x="20" y="16" width="11" height="12" fill="#9cc3d6" stroke={INK} strokeWidth="1" />
        <path d="M25.5 16v12M20 22h11" stroke={INK} strokeWidth="0.8" />
        <rect x="33" y="30" width="12" height="13" fill="#7a6a58" stroke={INK} strokeWidth="1" />
        <path d="M36 30q2-5 3-1q2-5 3 1" fill="#f08a3c" stroke={RED} strokeWidth="0.8" />
      </g>
      <path d="M20 50q4-2 8 0t8 0" fill="none" stroke={NAVY} strokeWidth="1.1" strokeLinecap="round" />
    </g>
  ),
  lettre_berlin: () => (
    <g>
      <path d="M9 27l23 16 23-16v27H9z" fill={CREAM} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
      <g className="pi-slide">
        <rect x="15" y="8" width="34" height="34" fill="#fdfbf5" stroke={INK} strokeWidth="1.6" />
        <rect x="15" y="8" width="34" height="7" fill={YELLOW} stroke={INK} strokeWidth="1.6" />
        <text x="32" y="13.4" textAnchor="middle" fontSize="4.4" fontWeight="700" fill={INK} fontFamily="Helvetica, Arial, sans-serif" letterSpacing="0.6">BERLIN</text>
        <path d="M19 21h26M19 26h22M19 31h24" stroke="#a59e8f" strokeWidth="1.2" strokeLinecap="round" />
      </g>
      <path d="M9 54l23-15 23 15" fill="none" stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
      <path d="M9 27l23 16 23-16" fill="none" stroke={INK} strokeWidth="1.4" strokeLinejoin="round" />
    </g>
  ),
  carnet_noir: () => (
    <g>
      <rect x="15" y="8" width="34" height="48" rx="3" fill="#24201b" stroke={INK} strokeWidth={SW} />
      <path d="M49 11v42" stroke={PAPER} strokeWidth="1.6" />
      <rect x="40" y="8" width="3.4" height="48" fill="#4b443b" stroke={INK} strokeWidth="0.8" />
      <path d="M19 12v40" stroke="#3a342d" strokeWidth="1.2" />
      {/* the ribbon */}
      <path className="pi-ribbon" d="M30 55l-1 8 3-2.4 3 2.4-1-8" fill={RED} stroke={INK} strokeWidth="1.2" strokeLinejoin="round" />
      <rect x="23" y="22" width="13" height="8" rx="1" fill={CREAM} stroke={INK} strokeWidth="1" />
      <path d="M25 26h9" stroke={NAVY} strokeWidth="0.9" strokeLinecap="round" />
    </g>
  ),
  chaine: () => (
    <g>
      {/* the chain, coiled on the zinc */}
      {Array.from({ length: 6 }, (_, i) => {
        const a = (i / 6) * Math.PI * 2;
        const x = 24 + Math.cos(a) * 12;
        const y = 38 + Math.sin(a) * 8;
        return (
          <ellipse key={i} cx={x} cy={y} rx="5.6" ry="3.4" fill="none" stroke={INK} strokeWidth="4.2" transform={`rotate(${(a * 180) / Math.PI + 90} ${x} ${y})`} />
        );
      })}
      {Array.from({ length: 6 }, (_, i) => {
        const a = (i / 6) * Math.PI * 2;
        const x = 24 + Math.cos(a) * 12;
        const y = 38 + Math.sin(a) * 8;
        return (
          <ellipse key={i} cx={x} cy={y} rx="5.6" ry="3.4" fill="none" stroke="#9aa3ab" strokeWidth="1.8" transform={`rotate(${(a * 180) / Math.PI + 90} ${x} ${y})`} />
        );
      })}
      {/* the padlock, ready */}
      <g className="pi-jump">
        <path d="M42 26v-7a7 7 0 0 1 14 0v7" fill="none" stroke={INK} strokeWidth="5" />
        <path d="M42 26v-7a7 7 0 0 1 14 0v7" fill="none" stroke="#9aa3ab" strokeWidth="2" />
        <rect x="38" y="25" width="22" height="18" rx="3" fill={BRASS} stroke={INK} strokeWidth={SW} />
        <circle cx="49" cy="32.5" r="2.4" fill={INK} />
        <path d="M49 34v4" stroke={INK} strokeWidth="2" strokeLinecap="round" />
      </g>
    </g>
  ),
  enveloppe: () => (
    <g className="pi-float">
      <rect x="8" y="16" width="48" height="33" rx="2" fill={CREAM} stroke={INK} strokeWidth={SW} />
      <path d="M8 18l24 17 24-17" fill="none" stroke={INK} strokeWidth="1.6" strokeLinejoin="round" />
      <text x="32" y="44.5" textAnchor="middle" fontSize="6.6" fontStyle="italic" fill={NAVY} fontFamily="Georgia, serif">Pour toi.</text>
      {/* the tape it was stuck behind the radiator with */}
      <path className="pi-tape" d="M44 10l12 10-3 3-12-10z" fill="#e8d9a8" fillOpacity="0.9" stroke={INK} strokeWidth="1" strokeLinejoin="round" />
      <circle cx="32" cy="34" r="3.4" fill={RED} stroke={INK} strokeWidth="1.2" />
    </g>
  ),
};

export const PLOT_ITEM_CSS = `
.plot-item { display: block; overflow: visible; }
.plot-item .pi-swing { transform-box: view-box; transform-origin: 32px 6px; animation: pi-swing 2.4s ease-in-out infinite alternate; }
.plot-item .pi-flutter { transform-box: fill-box; transform-origin: 50% 20%; animation: pi-flutter 1.2s ease-in-out infinite alternate; }
.plot-item .pi-circle { stroke-dasharray: 40; stroke-dashoffset: 40; animation: pi-draw 900ms 400ms ease-out forwards; }
.plot-item .pi-corner { transform-box: fill-box; transform-origin: 100% 100%; animation: pi-lift 2.2s ease-in-out infinite alternate; }
.plot-item .pi-sign { transform-box: fill-box; transform-origin: 0% 100%; animation: pi-sign 700ms ease-in-out infinite alternate; }
.plot-item .pi-develop { opacity: 0.08; animation: pi-develop 2.6s 300ms ease-out forwards; }
.plot-item .pi-slide { animation: pi-slide 900ms 300ms cubic-bezier(.2,1.4,.4,1) both; }
.plot-item .pi-ribbon { transform-box: fill-box; transform-origin: 50% 0%; animation: pi-sway 1.8s ease-in-out infinite alternate; }
.plot-item .pi-jump { transform-box: fill-box; transform-origin: 50% 100%; animation: pi-jump 1.6s ease-in-out infinite; }
.plot-item .pi-float { transform-box: view-box; animation: pi-float 2.6s ease-in-out infinite alternate; }
.plot-item .pi-tape { transform-box: fill-box; transform-origin: 0% 0%; animation: pi-sway 1.4s ease-in-out infinite alternate; }
@keyframes pi-swing { from { transform: rotate(-9deg); } to { transform: rotate(9deg); } }
@keyframes pi-flutter { from { transform: rotate(-4deg); } to { transform: rotate(5deg); } }
@keyframes pi-draw { to { stroke-dashoffset: 0; } }
@keyframes pi-lift { from { transform: rotate(0); } to { transform: rotate(-10deg); } }
@keyframes pi-sign { from { transform: translate(0, 0); } to { transform: translate(-2px, 2px) rotate(-4deg); } }
@keyframes pi-develop { to { opacity: 1; } }
@keyframes pi-slide { from { transform: translateY(18px); } to { transform: translateY(0); } }
@keyframes pi-sway { from { transform: rotate(-6deg); } to { transform: rotate(6deg); } }
@keyframes pi-jump { 0%, 60%, 100% { transform: translateY(0); } 70% { transform: translateY(-5px) rotate(-6deg); } 80% { transform: translateY(0) rotate(4deg); } }
@keyframes pi-float { from { transform: translateY(1.5px) rotate(-2deg); } to { transform: translateY(-1.5px) rotate(2deg); } }
.plot-item--still *, .plot-item--still { animation: none !important; }
.plot-item--still .pi-develop { opacity: 1; }
.plot-item--still .pi-circle { stroke-dashoffset: 0; }
@media (prefers-reduced-motion: reduce) {
  .plot-item * { animation: none !important; }
  .plot-item .pi-develop { opacity: 1; }
  .plot-item .pi-circle { stroke-dashoffset: 0; }
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
  const Drawing = DRAWINGS[id];
  if (!Drawing) return null;
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={['plot-item', `plot-item--${id}`, still ? 'plot-item--still' : '', className ?? ''].filter(Boolean).join(' ')}
      role={label ? 'img' : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : true}
      focusable="false"
      data-plot-item={id}
    >
      {css === 'scoped' ? <style dangerouslySetInnerHTML={{ __html: PLOT_ITEM_CSS }} /> : null}
      <Drawing />
    </svg>
  );
}

export const PLOT_ITEM_IDS = Object.keys(DRAWINGS) as SeasonItemId[];

export default PlotItem;
