/**
 * WP-80 — the story notices an absence. After two or more missed days the day
 * is WP-66's «jour court», and its header says so: «Reprise en douceur ·
 * 3 min». Chrome, so French on every screen (WP-43). The minutes are the
 * plan's own estimate, and absent when there is no plan yet — never a guess.
 */

export const GENTLE_RETURN_LABEL = 'Reprise en douceur';
/** Two whole days without practice make a return. One is just a missed day. */
export const GENTLE_RETURN_MIN_MISSED_DAYS = 2;

export function gentleReturnLabel({
  missedDays,
  dayShape,
  estimatedSeconds,
}: {
  missedDays: number | null | undefined;
  /** `null` before the day is planned (the offer); the snapshot's shape after. */
  dayShape: string | null | undefined;
  estimatedSeconds: number | null | undefined;
}): string | null {
  if (!missedDays || missedDays < GENTLE_RETURN_MIN_MISSED_DAYS) return null;
  // Once planned, only the short day is labelled: a longer day is not gentle.
  if (dayShape && dayShape !== 'short') return null;
  if (!estimatedSeconds || estimatedSeconds <= 0) return GENTLE_RETURN_LABEL;
  return `${GENTLE_RETURN_LABEL} · ${Math.max(1, Math.round(estimatedSeconds / 60))} min`;
}
