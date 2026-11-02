/**
 * Owner request, 2 Nov 2026 — more new words a day, and why it is worth it.
 *
 * «Zudem solltest du die Möglichkeit geben, noch mehr Wörter pro Tag zu lernen …
 * Gleichzeitig auch dem Lerner sagen, dass man so schneller an sein Sprachziel
 * kommt.»
 *
 * The server owns every number (`GET /vocabulary/new-words`,
 * `app/services/goal_estimate.py`): the learner's daily words, today's extras,
 * and for each choice how many days sooner it covers the words of their goal
 * level (`days_sooner`, `null` when there is no honest figure). This file only
 * words it, in the three chrome languages: du in German, tu in French.
 *
 * The line says «Wortschatz», not the level: grammar has its own clock, which
 * more words do not move. Pure, so `more-words.test.js` reads the same functions.
 */

import { daySessionCopy } from '@/lib/day-session';
import type { ControlLanguage } from '@/types/daily-journey';

type Copy = {
  /** «Mit 20 Wörtern am Tag hast du den Wortschatz für A2 etwa 3 Wochen früher.» */
  sooner: (words: number, level: string, eta: string) => string;
  /** No goal, or no figure worth printing. */
  no_figure: string;
  weeks: (n: number) => string;
  days: (n: number) => string;
  one_day: string;
  /** Réglages: the number input next to the steps. */
  own_number: string;
};

const DE: Copy = {
  sooner: (words, level, eta) => `Mit ${words} Wörtern am Tag hast du den Wortschatz für ${level} etwa ${eta} früher.`,
  no_figure: 'Mehr Wörter am Tag bringen dich schneller ans Ziel.',
  weeks: (n) => `${n} Wochen`,
  days: (n) => `${n} Tage`,
  one_day: 'einen Tag',
  own_number: 'Eigene Zahl',
};

const FR: Copy = {
  sooner: (words, level, eta) => `Avec ${words} mots par jour, tu as le vocabulaire du niveau ${level} environ ${eta} plus tôt.`,
  no_figure: 'Plus de mots par jour te rapprochent plus vite de ton objectif.',
  weeks: (n) => `${n} semaines`,
  days: (n) => `${n} jours`,
  one_day: 'un jour',
  own_number: 'Ton nombre',
};

const EN: Copy = {
  sooner: (words, level, eta) => `At ${words} words a day, you’ll have the ${level} vocabulary about ${eta} sooner.`,
  no_figure: 'More words a day get you to your goal sooner.',
  weeks: (n) => `${n} weeks`,
  days: (n) => `${n} days`,
  one_day: 'a day',
  own_number: 'Your own number',
};

const TABLE: Record<ControlLanguage, Copy> = { de: DE, fr: FR, en: EN };

export function moreWordsCopy(language: ControlLanguage | null | undefined): Copy {
  return TABLE[(language || 'en') as ControlLanguage] ?? EN;
}

/** «3 Wochen» from two weeks on, «10 Tage» below, «einen Tag» for one. */
export function soonerLabel(days: number, language: ControlLanguage | null | undefined): string {
  const copy = moreWordsCopy(language);
  const n = Math.round(days);
  if (n >= 14) return copy.weeks(Math.round(n / 7));
  if (n >= 2) return copy.days(n);
  return copy.one_day;
}

/** A whole level reads «A2» («A2.2» is its end); half a level keeps its band («A2.1»). */
export function goalLabel(goal: string): string {
  const band = String(goal || '').trim().toUpperCase();
  return band.endsWith('.2') ? band.slice(0, 2) : band;
}

export type GoalStep = { words: number; days_sooner?: number | null };

/**
 * The motivation line under a choice of daily words: how much sooner, when the
 * server has a figure; otherwise only that more words get there sooner.
 */
export function goalLine(
  language: ControlLanguage | null | undefined,
  step: GoalStep,
  goal: string | null | undefined,
): string {
  const copy = moreWordsCopy(language);
  const days = Number(step.days_sooner || 0);
  if (!goal || !Number.isFinite(days) || days < 1) return copy.no_figure;
  return copy.sooner(step.words, goalLabel(goal), soonerLabel(days, language));
}

/** «Noch 5 neue Wörter»: the same label as Fertig's (`day-session.ts`). */
export function moreWordsLabel(language: ControlLanguage | null | undefined, n: number): string {
  return daySessionCopy(language).more_words(n);
}

export type NewWordsOffer = {
  step: number;
  can_add_more: boolean;
  goal?: string | null;
  more: GoalStep;
};

/** The «Noch 5» offer: its label and its line, or `null` once the day's extras are spent. */
export function extraWordsOffer(
  pace: NewWordsOffer | null | undefined,
  language: ControlLanguage | null | undefined,
): { label: string; line: string } | null {
  if (!pace || !pace.can_add_more || !(pace.step > 0)) return null;
  return { label: moreWordsLabel(language, pace.step), line: goalLine(language, pace.more, pace.goal) };
}

/**
 * Réglages: the line under the chosen number, against the number the learner has
 * now. Only a faster choice speaks; the same or fewer words say nothing.
 */
export function settingsGoalLine(
  language: ControlLanguage | null | undefined,
  chosen: number,
  pace: { words_per_day: number; goal?: string | null; steps?: GoalStep[] } | null | undefined,
): string | null {
  if (!pace || !(chosen > pace.words_per_day)) return null;
  const step = (pace.steps ?? []).find((item) => item.words === chosen);
  return goalLine(language, step ?? { words: chosen, days_sooner: null }, step ? pace.goal : null);
}
