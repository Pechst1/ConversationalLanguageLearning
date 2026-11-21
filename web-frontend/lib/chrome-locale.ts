/**
 * #694 — the one place a chrome language becomes a locale, and a day becomes words.
 *
 * Dates and numbers on a learner's screen are chrome: they read in the chrome
 * language («11 Nov», «11. Nov.», «11 nov.»), never in a locale a helper picked
 * for itself. Before this module the `{ en: 'en-GB', … }` map was copied into
 * five files, and the helpers that had no copy hard-coded `'fr-FR'` (the seal's
 * «11 nov.», «D’où vient ton or») or no locale at all (La Forge's end card
 * «11 · 11 · 26»). A formatter that needs a locale takes the language and asks here.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export const CHROME_LOCALE: Record<ControlLanguage, string> = { en: 'en-GB', de: 'de-DE', fr: 'fr-FR' };

/** The Intl locale of a chrome language; English for anything unknown (the signup default). */
export function chromeLocale(language: unknown): string {
  return CHROME_LOCALE[language as ControlLanguage] ?? CHROME_LOCALE.en;
}

/**
 * `day` «11 Nov» · `weekday` «Wed 11 Nov» · `heading` «Wednesday 11 Nov» (capitalised,
 * «Mercredi 11 nov.»): the forms a learner's screen dates something in.
 */
export type ChromeDateForm = 'day' | 'weekday' | 'heading';

const FORMS: Record<ChromeDateForm, Intl.DateTimeFormatOptions> = {
  day: { day: 'numeric', month: 'short' },
  weekday: { weekday: 'short', day: 'numeric', month: 'short' },
  // The short month keeps a heading on one line.
  heading: { weekday: 'long', day: 'numeric', month: 'short' },
};

/** A local ISO day («2026-11-11») is read at noon, so no time zone moves it a day. */
function asDate(value: string | Date | null | undefined): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const raw = String(value ?? '').trim();
  if (!raw) return null;
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? new Date(`${raw}T12:00:00`) : new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** A day in the chrome language; `null` for an unreadable date. */
export function chromeDate(
  value: string | Date | null | undefined,
  language: unknown,
  form: ChromeDateForm = 'day',
): string | null {
  const date = asDate(value);
  if (!date) return null;
  try {
    const text = new Intl.DateTimeFormat(chromeLocale(language), FORMS[form]).format(date);
    return form === 'heading' ? text.charAt(0).toUpperCase() + text.slice(1) : text;
  } catch {
    return null;
  }
}
