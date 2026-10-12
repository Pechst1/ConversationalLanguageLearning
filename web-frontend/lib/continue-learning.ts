/**
 * CONTINUE (owner, 2026-10-12): «the learner can always press on one button in
 * the main screen to continue / start learning, first with the episode of the
 * day, then with la forge and the vocab learning. but also if he comes back he
 * can just press continue and will work toward learning more so that he can
 * achieve his targets even faster (that should also be displayed).»
 *
 * One model for Home's one button, on every day:
 *
 *   1. the story (today's episode; the journey card opens it);
 *   2. La Forge, unless the rhythm folds it into the story (Soutenu, Intensif);
 *   3. the words due;
 *   4. then «more»: another La Forge round, which always has a rule to work on
 *      and brings the next band closer.
 *
 * And one line for the target: the next band, what is still missing for it,
 * and the server's forecast when it has one. Pure functions; the page reads
 * the server and the device and passes plain values in.
 */

import type { CEFRProgress } from '@/services/api';
import { ROUTE_STAGES, type KeyValueStore, type RouteStage } from '@/lib/first-steps';

type Language = 'de' | 'en' | 'fr';

export type ContinueStage = RouteStage | 'more';

export interface ContinueInputs {
  /** Today's journey is completed (not ended early). */
  storyDone: boolean;
  /** The server's forge entry: `null` when there is none. */
  forge: { href: string | null; folded: boolean; blocksToday: number } | null;
  /** Word cards due now. */
  wordsDue: number;
  /** The word deck was finished on this device today. */
  wordsDoneToday: boolean;
  /** On the first day the words are new ones, never «nothing due»: only the device tick counts. */
  firstDay: boolean;
  /** Stages this device ticked off on the first day's route. */
  routeDone?: readonly RouteStage[];
  /** «Plus de pratique»: the drill loop, when there is no forge entry. */
  practiceHref?: string | null;
}

export interface ContinuePlan {
  done: RouteStage[];
  next: ContinueStage;
  /** Where the button goes; `null` for the story, which the journey card opens. */
  href: string | null;
}

export const WORDS_HREF = '/vocabulary/review';

export function continuePlan(input: ContinueInputs): ContinuePlan {
  const ticked = new Set<RouteStage>(input.routeDone ?? []);
  const forgeHref = input.forge?.href || input.practiceHref || null;
  const done = ROUTE_STAGES.filter((stage) => {
    if (ticked.has(stage)) return true;
    if (stage === 'story') return input.storyDone;
    if (stage === 'forge') {
      if (!input.forge) return !forgeHref;
      // Folded (Soutenu, Intensif): La Forge is a step of the story itself.
      if (input.forge.folded) return input.storyDone;
      return input.forge.blocksToday > 0;
    }
    if (input.wordsDoneToday) return true;
    return !input.firstDay && input.wordsDue <= 0;
  });
  const next = ROUTE_STAGES.find((stage) => !done.includes(stage)) ?? 'more';
  const href = next === 'story' ? null : next === 'words' ? WORDS_HREF : forgeHref;
  return { done: [...done], next, href };
}

// ---------------------------------------------------------------------------
// The words, ticked on this device when the deck is finished today
// ---------------------------------------------------------------------------

const WORDS_DAY_KEY = 'atelier.continue.wordsDone';

export function markWordsDoneToday(store: KeyValueStore | null, localDate: string): void {
  try {
    store?.setItem(WORDS_DAY_KEY, localDate);
  } catch {
    // Not remembered: the button offers the words once more. Harmless.
  }
}

export function wordsDoneToday(store: KeyValueStore | null, localDate: string | null | undefined): boolean {
  if (!store || !localDate) return false;
  try {
    return store.getItem(WORDS_DAY_KEY) === localDate;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// The target
// ---------------------------------------------------------------------------

export interface TargetView {
  /** The band the learner is working towards, e.g. «A1.2». */
  band: string;
  /** 0–100: how much of the way there, from the server's coverage. */
  percent: number;
  wordsLeft: number;
  rulesLeft: number;
  /** «December» or «November–December»; `null` without a forecast. */
  when: string | null;
}

function monthName(iso: string, language: Language): string | null {
  const date = new Date(`${iso}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(language, { month: 'long', timeZone: 'UTC' }).format(date);
}

export function targetView(cefr: CEFRProgress | null | undefined, language: Language): TargetView | null {
  const coverage = cefr?.coverage;
  if (!cefr || !coverage) return null;
  const band = String(cefr.forecast?.target || cefr.next_level || '').trim();
  if (!band) return null;
  const wordsLeft = Math.max(0, Number(coverage.words?.required || 0) - Number(coverage.words?.known || 0));
  const rulesLeft = Math.max(0, Number(coverage.units?.required || 0) - Number(coverage.units?.held || 0));
  const dates = cefr.forecast?.projected_dates ?? [];
  let when: string | null = null;
  if (dates.length === 2 && !cefr.forecast?.capped) {
    const [low, high] = [monthName(dates[0], language), monthName(dates[1], language)];
    when = low && high ? (low === high ? low : `${low}–${high}`) : null;
  }
  return {
    band,
    percent: Math.max(0, Math.min(100, Math.round(Number(coverage.percent || 0)))),
    wordsLeft,
    rulesLeft,
    when,
  };
}

// ---------------------------------------------------------------------------
// Copy (German says du)
// ---------------------------------------------------------------------------

type ContinueCopy = {
  today: string;
  more: string;
  more_hint: string;
  target_left: string;
  target_reached: string;
  target_when: string;
};

const COPY: Record<Language, ContinueCopy> = {
  de: {
    today: 'Heute',
    more: 'Weiter lernen',
    more_hint: 'Noch eine Runde La Forge bringt dich schneller zu {band}.',
    target_left: 'Ziel {band}: noch {words} Wörter und {rules} Regeln',
    target_reached: 'Ziel {band}: alles beisammen, die Prüfung kommt in der Geschichte',
    target_when: 'bei deinem Tempo etwa im {when}',
  },
  en: {
    today: 'Today',
    more: 'Keep learning',
    more_hint: 'One more La Forge round gets you to {band} sooner.',
    target_left: 'Goal {band}: {words} words and {rules} rules to go',
    target_reached: 'Goal {band}: all there, the test comes in the story',
    target_when: 'at your pace, around {when}',
  },
  fr: {
    today: 'Aujourd’hui',
    more: 'Continuer',
    more_hint: 'Encore une forge, et {band} arrive plus vite.',
    target_left: 'Objectif {band} : encore {words} mots et {rules} règles',
    target_reached: 'Objectif {band} : tout y est, l’épreuve viendra dans l’histoire',
    target_when: 'à ton rythme, vers {when}',
  },
};

function languageOf(language: unknown): Language {
  return language === 'de' || language === 'fr' ? language : 'en';
}

export function continueCopy(language: unknown): ContinueCopy {
  return COPY[languageOf(language)];
}

function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? ''));
}

/** The target as one or two short lines. */
export function targetLines(target: TargetView, language: unknown): { goal: string; when: string | null } {
  const copy = continueCopy(language);
  const reached = target.wordsLeft === 0 && target.rulesLeft === 0;
  return {
    goal: fill(reached ? copy.target_reached : copy.target_left, {
      band: target.band,
      words: target.wordsLeft,
      rules: target.rulesLeft,
    }),
    when: target.when && !reached ? fill(copy.target_when, { when: target.when }) : null,
  };
}

export function moreHint(target: TargetView | null, language: unknown): string | null {
  return target ? fill(continueCopy(language).more_hint, { band: target.band }) : null;
}
