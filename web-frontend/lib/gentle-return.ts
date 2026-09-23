/**
 * WP-80 — the story notices an absence. After two or more missed days the day
 * is WP-66's «jour court», and its header says so: «Reprise en douceur ·
 * 3 min». WP-82: it is status, so it is written in the card's chrome language
 * (the learner's up to A2, French from B1). The minutes are the plan's own
 * estimate, and absent when there is no plan yet — never a guess.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export const GENTLE_RETURN_LABEL = 'Reprise en douceur';
const GENTLE_RETURN: Record<ControlLanguage, string> = {
  en: 'Easing back in',
  de: 'Sanfter Wiedereinstieg',
  fr: GENTLE_RETURN_LABEL,
};
/** Two whole days without practice make a return. One is just a missed day. */
export const GENTLE_RETURN_MIN_MISSED_DAYS = 2;

export function gentleReturnLabel({
  missedDays,
  dayShape,
  estimatedSeconds,
  language = 'fr',
}: {
  missedDays: number | null | undefined;
  /** `null` before the day is planned (the offer); the snapshot's shape after. */
  dayShape: string | null | undefined;
  estimatedSeconds: number | null | undefined;
  /** The card's chrome language. */
  language?: ControlLanguage;
}): string | null {
  if (!missedDays || missedDays < GENTLE_RETURN_MIN_MISSED_DAYS) return null;
  // Once planned, only the short day is labelled: a longer day is not gentle.
  if (dayShape && dayShape !== 'short') return null;
  const label = GENTLE_RETURN[language] ?? GENTLE_RETURN.en;
  if (!estimatedSeconds || estimatedSeconds <= 0) return label;
  return `${label} · ${Math.max(1, Math.round(estimatedSeconds / 60))} min`;
}
