/**
 * WP-128 — one estimate, said the same way everywhere.
 *
 * The server sends `time_estimate` on the today envelope and on the journey:
 * the *core* the chosen rhythm budgets (the story and its practice) and each
 * optional extension with its own minutes — the drill's words, a letter, La
 * Forge, the «Lecture». Home's card, the chips, the plan and the ending all
 * read the core from here, so they print one number; an extension is never
 * folded into it, and never presented as something the day requires.
 *
 * Every word is chrome, in the screen's one chrome language (en/de/fr).
 * Pure: no React, no transport.
 */

import type { ControlLanguage, TodayEnvelope } from '@/types/daily-journey';
import { formatPlannedDuration } from './journey-state';

export type DayTimeEstimate = NonNullable<TodayEnvelope['time_estimate']>;
export type TimeExtensionKind = DayTimeEstimate['extensions'][number]['kind'];

type Copy = {
  /** «+ mots ≈ 4 min» — an optional extension beside the core. */
  extension: string;
  /** The day the story alone makes longer than the rhythm. */
  longer_day: string;
  /** The ending: what was planned, beside what was measured. */
  planned: string;
  kinds: Record<TimeExtensionKind, string>;
};

const COPY: Record<ControlLanguage, Copy> = {
  en: {
    extension: '+ {kind} ≈ {minutes}',
    longer_day: 'A longer day · ≈ {minutes}',
    planned: 'planned {minutes}',
    kinds: { words: 'words', letter: 'letter', forge: 'Forge', reading: 'reading', desk: 'desk' },
  },
  de: {
    extension: '+ {kind} ≈ {minutes}',
    longer_day: 'Ein längerer Tag · ≈ {minutes}',
    planned: 'geplant {minutes}',
    kinds: { words: 'Wörter', letter: 'Brief', forge: 'Forge', reading: 'Lektüre', desk: 'Pult' },
  },
  fr: {
    extension: '+ {kind} ≈ {minutes}',
    longer_day: 'Une journée plus longue · ≈ {minutes}',
    planned: 'prévu {minutes}',
    kinds: { words: 'mots', letter: 'lettre', forge: 'Forge', reading: 'lecture', desk: 'bureau' },
  },
};

function copyFor(language: ControlLanguage): Copy {
  return COPY[language] ?? COPY.en;
}

function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) => values[key] ?? '');
}

/** The core's minutes («10 min»), or the longer-day line when the story alone is longer. */
export function coreEstimateLabel(
  estimate: DayTimeEstimate | null | undefined,
  fallbackSeconds: number | null | undefined,
  language: ControlLanguage,
): string | null {
  const seconds = estimate ? estimate.core_seconds : fallbackSeconds;
  const minutes = formatPlannedDuration(seconds, language);
  if (!minutes) return null;
  if (estimate?.longer_day) return fill(copyFor(language).longer_day, { minutes });
  return minutes;
}

/**
 * Round 3 (walk 2, 17 Nov 2026): the day card's one figure is the sum of the
 * step minutes Home prints under it (`session.minutes_left`, the server's sum of
 * the steps still to do). The card used to print the scene's core and «+ Wörter»
 * beside it, leaving La Forge's minutes out. `null` without a day session: the
 * caller keeps the core and the words' extension.
 */
export function dayTotalLabel(
  session: { minutes_left?: number | null } | null | undefined,
  estimate: DayTimeEstimate | null | undefined,
  language: ControlLanguage,
): string | null {
  const total = Number(session?.minutes_left ?? 0);
  if (!(total > 0)) return null;
  const minutes = formatPlannedDuration(total * 60, language);
  if (!minutes) return null;
  if (estimate?.longer_day) return fill(copyFor(language).longer_day, { minutes });
  return minutes;
}

/** One extension's own minutes, or `null` when the server sent none for it. */
export function extensionSeconds(
  estimate: DayTimeEstimate | null | undefined,
  kind: TimeExtensionKind,
): number | null {
  const found = (estimate?.extensions || []).filter((item) => item.kind === kind);
  if (!found.length) return null;
  const seconds = found.reduce((sum, item) => sum + Math.max(0, Number(item.seconds) || 0), 0);
  return seconds > 0 ? seconds : null;
}

/** «+ mots ≈ 4 min» for one extension, or `null`. */
export function extensionLabel(
  estimate: DayTimeEstimate | null | undefined,
  kind: TimeExtensionKind,
  language: ControlLanguage,
): string | null {
  const minutes = formatPlannedDuration(extensionSeconds(estimate, kind), language);
  if (!minutes) return null;
  const copy = copyFor(language);
  return fill(copy.extension, { kind: copy.kinds[kind], minutes });
}

/**
 * «≈ 4 min» / «≈ 4 Min.»: a chip's minutes, in the chrome's language, or
 * `null`. Every Home chip that prints minutes says them through here (#998:
 * the retell chip once wrote an English «≈ 2 min» beside the letter's «≈ 6 Min.»).
 */
export function approxMinutes(
  seconds: number | null | undefined,
  language: ControlLanguage,
): string | null {
  const minutes = formatPlannedDuration(seconds, language);
  return minutes ? `≈ ${minutes}` : null;
}

/** «≈ 4 min» for a chip that already names its activity, or `null`. */
export function extensionMinutes(
  estimate: DayTimeEstimate | null | undefined,
  kind: TimeExtensionKind,
  language: ControlLanguage,
): string | null {
  return approxMinutes(extensionSeconds(estimate, kind), language);
}

/** The ending: «9 min · prévu 10 min» — measured first, the plan's core beside it. */
export function measuredBesidePlanned(
  measured: string,
  plannedSeconds: number | null | undefined,
  language: ControlLanguage,
): string {
  const planned = formatPlannedDuration(plannedSeconds, language);
  if (!planned || planned === measured) return measured;
  return `${measured} · ${fill(copyFor(language).planned, { minutes: planned })}`;
}
