/**
 * WP-L6 — the learner's rhythm and vocabulary pace, as the client shows them.
 *
 * The server owns both (`app/services/journey_rhythm.py`,
 * `app/services/vocabulary_pace.py`): it sizes the day from the rhythm and
 * the client never sends a budget. This module only mirrors the four choices
 * for Réglages and the honest review-load estimate printed under
 * «Nouveaux mots par jour». Pure, so `lib/rhythm.test.js` can require it.
 */

export type Rhythm = 'leger' | 'regulier' | 'soutenu' | 'intensif';

/**
 * The names are the product's own French words — proper nouns, like
 * «L'Atelier» — so they are data here, not copy in a language table.
 */
export const RHYTHMS: ReadonlyArray<{ id: Rhythm; name: string; minutes: number }> = [
  { id: 'leger', name: 'Léger', minutes: 5 },
  { id: 'regulier', name: 'Régulier', minutes: 10 },
  { id: 'soutenu', name: 'Soutenu', minutes: 20 },
  { id: 'intensif', name: 'Intensif', minutes: 30 },
];

export const DEFAULT_RHYTHM: Rhythm = 'regulier';

export function isRhythm(value: unknown): value is Rhythm {
  return RHYTHMS.some((rhythm) => rhythm.id === value);
}

/** The server's mapping of stored minutes: ≤7 Léger, ≤14 Régulier, ≤25 Soutenu, else Intensif. */
export function rhythmForMinutes(minutes: number | null | undefined): Rhythm {
  if (typeof minutes !== 'number' || !Number.isFinite(minutes) || minutes <= 0) return DEFAULT_RHYTHM;
  if (minutes <= 7) return 'leger';
  if (minutes <= 14) return 'regulier';
  if (minutes <= 25) return 'soutenu';
  return 'intensif';
}

/** Mirrors `vocabulary_pace.review_load_estimate`: 8–10 reviews per new word a day, ~6 s each. */
export const REVIEWS_PER_NEW_WORD: readonly [number, number] = [8, 10];
export const SECONDS_PER_REVIEW = 6;
export const NEW_WORDS_MIN = 1;
export const NEW_WORDS_MAX = 50;

export type ReviewLoad = { low: number; high: number; minLow: number; minHigh: number };

export function reviewLoad(newWordsPerDay: number): ReviewLoad {
  const words = Math.max(0, Math.round(Number(newWordsPerDay) || 0));
  const low = words * REVIEWS_PER_NEW_WORD[0];
  const high = words * REVIEWS_PER_NEW_WORD[1];
  return {
    low,
    high,
    minLow: Math.round((low * SECONDS_PER_REVIEW) / 60),
    minHigh: Math.round((high * SECONDS_PER_REVIEW) / 60),
  };
}

/** Fill `{low}`, `{high}`, `{minLow}`, `{minHigh}` in a copy template. */
export function formatReviewLoad(template: string, newWordsPerDay: number): string {
  const load = reviewLoad(newWordsPerDay);
  return template
    .replace('{low}', String(load.low))
    .replace('{high}', String(load.high))
    .replace('{minLow}', String(load.minLow))
    .replace('{minHigh}', String(load.minHigh));
}

export function clampNewWords(value: number): number {
  if (!Number.isFinite(value)) return 10;
  return Math.min(NEW_WORDS_MAX, Math.max(NEW_WORDS_MIN, Math.round(value)));
}

/**
 * WP-L8 — the honest forecast on each rhythm card: the server's planning
 * prior (`rhythm_priors` in `GET /progress/cefr`, from
 * `app/services/level_forecast.py`) for finishing A1 at that rhythm, as a
 * range in months. Always worded as an estimate, never as a promise.
 */
export type RhythmPrior = {
  rhythm?: string;
  target?: string;
  range_months?: [number, number] | number[];
  range_days?: [number, number] | number[];
};

/** Whole months, the low end rounded down and the high end up; `null` without a range. */
export function priorMonths(prior: RhythmPrior | null | undefined): { low: number; high: number } | null {
  const range = prior?.range_months;
  if (!Array.isArray(range) || range.length < 2) return null;
  const lowRaw = Number(range[0]);
  const highRaw = Number(range[1]);
  if (!Number.isFinite(lowRaw) || !Number.isFinite(highRaw) || lowRaw <= 0) return null;
  const low = Math.max(1, Math.floor(lowRaw));
  const high = Math.max(low, Math.ceil(highRaw));
  return { low, high };
}

/** Fill `{target}`, `{low}`, `{high}` in a copy template; `null` when there is no prior. */
export function formatRhythmForecast(template: string, prior: RhythmPrior | null | undefined): string | null {
  const months = priorMonths(prior);
  if (!months) return null;
  return template
    .replace('{target}', String(prior?.target || 'A1'))
    .replace('{low}', String(months.low))
    .replace('{high}', String(months.high));
}
