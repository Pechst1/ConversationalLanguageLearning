/**
 * WP-82 — one language rule, by the learner's level.
 *
 *   * Up to A2, the app's own words — instructions, status, verdicts, the
 *     buttons and captions around them — are in the learner's language.
 *   * Story content (the scene, a character's line, the words, a letter, a
 *     keepsake's title) and the navigation labels (the tab bar, the names of
 *     places: La Une, Courrier, Feuilleton, Cahier, Lexique) are French.
 *   * From B1, the chrome is French too.
 *   * Never two chrome languages inside one card.
 *
 * `chromeLanguage` is the one switch: it resolves which copy table a screen
 * reads. Everything French that is *content* is French because it arrived as
 * `*_fr` from the server, never because of this function.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from './atelier-v2-copy';

const BANDS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'] as const;
export type LevelBand = (typeof BANDS)[number];

/** «A1.1», «b2», « B1 » → the CEFR band; anything else → `null`. */
export function levelBand(level: unknown): LevelBand | null {
  if (typeof level !== 'string') return null;
  const match = level.trim().toUpperCase().match(/^([ABC][12])/);
  return match && (BANDS as readonly string[]).includes(match[1]) ? (match[1] as LevelBand) : null;
}

/** B1 and above read French chrome. An unknown level is treated as a beginner. */
export function frenchChrome(level: unknown): boolean {
  const band = levelBand(level);
  return band !== null && BANDS.indexOf(band) >= BANDS.indexOf('B1');
}

/** The language a screen's chrome is written in, for this learner at this level. */
export function chromeLanguage(control: unknown, level?: unknown): ControlLanguage {
  return frenchChrome(level) ? 'fr' : normalizeControlLanguage(control);
}

type JourneyLike = {
  controlLanguage?: unknown;
  journey?: { scenario?: { level_band?: string | null } | null } | null;
  envelope?: {
    journey?: { scenario?: { level_band?: string | null } | null } | null;
    available?: { level_band?: string | null } | null;
  } | null;
};

/**
 * The chrome language of a daily-journey screen. The learner's band is the
 * scenario's (the planner deals it at the learner's level); before a journey
 * exists, the offered scenario's.
 */
export function journeyChromeLanguage(controller: JourneyLike): ControlLanguage {
  return chromeLanguage(controller.controlLanguage, journeyLevel(controller));
}

/** The learner's band as the day's journey knows it, or `null` before one exists. */
export function journeyLevel(controller: JourneyLike): string | null {
  return (
    controller.journey?.scenario?.level_band ??
    controller.envelope?.journey?.scenario?.level_band ??
    controller.envelope?.available?.level_band ??
    null
  );
}

/**
 * Server-sent chrome arrives as `{ fr, en, de }` (`app/services/chrome_language.py`).
 * The entry for `language`, else `fallback` (the server's resolved string).
 */
export function pickByLanguage(
  table: Partial<Record<string, unknown>> | null | undefined,
  language: ControlLanguage,
  fallback = '',
): string {
  const value = table && typeof table === 'object' ? table[language] : undefined;
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}
