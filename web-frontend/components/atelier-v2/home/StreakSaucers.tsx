/**
 * The streak's mark: «la pile de soucoupes» (owner, 2026-10-18).
 *
 * In a Paris café the waiter used to stack a saucer under each round, and the
 * pile was the bill. Le Mistral keeps the learner's days the same way: one
 * saucer per day in a row, up to five on the pile, with today's cup on top.
 * Once today is done the cup steams. The number beside it is the count, so the
 * pile never has to be read exactly; it only has to grow.
 *
 * Drawn like the cast (components/cast/rigs): flat fills, no outlines, the
 * details in a darker or lighter shade of the same colour, and the cast's own
 * porcelain, coffee and blue (Margaux's cup is the same cup). Decorative: the
 * streak's link carries the words.
 */
import React from 'react';

/** Saucers drawn for a streak: one a day, five at most. */
export function saucersFor(streak: number): number {
  if (!Number.isFinite(streak) || streak < 1) return 0;
  return Math.min(5, Math.floor(streak));
}

const SAUCER_GAP = 4.5;
const BASE_Y = 50;
/** Drawing units to CSS pixels. */
const SCALE = 0.8;

export function StreakSaucers({ streak, steaming = false }: { streak: number; steaming?: boolean }) {
  const count = saucersFor(streak);
  if (!count) return null;
  // The cup stands on the top saucer; the pile grows upwards, and the room for
  // the steam is kept either way, so the mark does not jump once today is done.
  const lift = (count - 1) * SAUCER_GAP;
  const minY = 6 - lift;
  const height = 58 - minY;
  return (
    <svg
      className="av2-saucers"
      viewBox={`0 ${minY} 48 ${height}`}
      width={48 * SCALE}
      height={height * SCALE}
      aria-hidden="true"
      focusable="false"
      data-saucers={count}
      data-steaming={steaming ? '' : undefined}
    >
      <ellipse cx="24" cy="53.6" rx="17" ry="2.2" fill="#14110d" opacity="0.14" />
      {Array.from({ length: count }, (_, index) => {
        const y = BASE_Y - index * SAUCER_GAP;
        return (
          <g key={index}>
            <path d={`M6,${y} Q24,${y + 6.5} 42,${y} L41,${y + 1.6} Q24,${y + 8} 7,${y + 1.6} Z`} fill="#b5a68b" />
            <path d={`M6,${y} Q24,${y - 3.4} 42,${y} Q24,${y + 4.2} 6,${y} Z`} fill="#f8f3e8" />
            <path d={`M15,${y + 0.2} Q24,${y - 1.4} 33,${y + 0.2} Q24,${y + 1.8} 15,${y + 0.2} Z`} fill="#e6dcc8" />
          </g>
        );
      })}
      <g transform={`translate(0 ${-lift})`}>
        {/* the handle, then the cup, its blue band and the coffee */}
        <circle cx="35" cy="38.5" r="4.2" fill="none" stroke="#d9cdb5" strokeWidth="2.6" />
        <path d="M13,31 L35,31 L33,45 Q24,51 15,45 Z" fill="#f8f3e8" />
        <path d="M13.6,35 L34.4,35 L34,38 L14,38 Z" fill="#1d3a8a" />
        <path d="M27,31 L35,31 L33,45 Q30,47.4 27.4,48 Z" fill="#d9cdb5" />
        <path d="M13,31 Q24,27.4 35,31 Q24,34.6 13,31 Z" fill="#b07a4e" />
        <path d="M17,31 Q24,29.4 31,31 Q24,32.4 17,31 Z" fill="#8a5a36" />
      </g>
      {steaming && (
        <g className="av2-saucers__steam" transform={`translate(0 ${-lift})`}>
          <path d="M20,25 C17,21 23,19 20,14 C18.6,11.6 20,9.4 21.4,8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M27.6,25 C25,21.6 30.4,19.2 27.8,15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </g>
      )}
    </svg>
  );
}

export default StreakSaucers;
