/**
 * «Papier · le choix» (2026-11-22): the front page's words. The headlines are French; the line
 * under each says, in the learner's mother tongue, why pedagogy offers that story — from the
 * offer's `why` record only, so it is never a promise the story does not keep.
 */

import type { RvLanguage, RvTopic, RvWhy } from '@/lib/revue-types';

export type ChoixCopy = {
  /** The hint under the section line, in the chrome language. */
  hint: string;
  words: (n: number) => string;
  ruleToday: (name: string) => string;
  ruleWeek: (name: string) => string;
  interest: (label: string) => string;
  topic: Record<RvTopic, string>;
};

const FR: ChoixCopy = {
  hint: 'Trois sujets pour toi ce matin. Choisis le tien.',
  words: (n) => (n === 1 ? 'avec un de tes mots' : `avec ${n} de tes mots`),
  ruleToday: (name) => `règle du jour : ${name}`,
  ruleWeek: (name) => `règle de la semaine : ${name}`,
  interest: (label) => `ton sujet : ${label}`,
  topic: { food: 'cuisine', culture: 'culture', city: 'ville', sport: 'sport', nature: 'nature', work: 'travail', politics: 'politique' },
};

const EN: ChoixCopy = {
  hint: 'Three stories for you this morning. Pick yours.',
  words: (n) => (n === 1 ? 'with one of your words' : `with ${n} of your words`),
  ruleToday: (name) => `today’s rule: ${name}`,
  ruleWeek: (name) => `this week’s rule: ${name}`,
  interest: (label) => `your topic: ${label}`,
  topic: { food: 'food', culture: 'culture', city: 'the city', sport: 'sport', nature: 'nature', work: 'work', politics: 'politics' },
};

const DE: ChoixCopy = {
  hint: 'Drei Geschichten für dich heute Morgen. Wähl deine.',
  words: (n) => (n === 1 ? 'mit einem deiner Wörter' : `mit ${n} deiner Wörter`),
  ruleToday: (name) => `Regel des Tages: ${name}`,
  ruleWeek: (name) => `Regel der Woche: ${name}`,
  interest: (label) => `dein Thema: ${label}`,
  topic: { food: 'Essen', culture: 'Kultur', city: 'Stadt', sport: 'Sport', nature: 'Natur', work: 'Arbeit', politics: 'Politik' },
};

const TABLES: Record<RvLanguage, ChoixCopy> = { fr: FR, en: EN, de: DE };

export function choixCopy(language: unknown): ChoixCopy {
  return TABLES[language as RvLanguage] ?? EN;
}

/** The reasons, each a short phrase in `language`; empty when the story was not picked for one. */
export function whyParts(why: RvWhy | null | undefined, language: unknown): string[] {
  if (!why) return [];
  const copy = choixCopy(language);
  const parts: string[] = [];
  if (why.dueWords.length) parts.push(copy.words(why.dueWords.length));
  if (why.rule && why.rule.name.trim()) parts.push((why.rule.today ? copy.ruleToday : copy.ruleWeek)(why.rule.name.trim()));
  if (why.interest) {
    const label = why.interest.topic ? copy.topic[why.interest.topic as RvTopic] : null;
    const said = label ?? why.interest.word.trim();
    if (said) parts.push(copy.interest(said));
  }
  return parts;
}

/** One honest line: the reasons joined, the first letter set up; `''` when there is none. */
export function whyLine(why: RvWhy | null | undefined, language: unknown): string {
  return capitalised(whyParts(why, language).join(' · '));
}

export function capitalised(text: string): string {
  return text ? text.charAt(0).toLocaleUpperCase() + text.slice(1) : '';
}
