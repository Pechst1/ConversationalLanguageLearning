/**
 * «Le bilan» — the page model: what the page says, decided as data so it is tested
 * without a browser (`bilan.test.js`).
 *
 * - The headline is true to the week: several days, one day (short, warm, true), or
 *   none (calm: the story waits). Never praise the numbers did not earn.
 * - A section with nothing in it is not drawn (no «0 words» line, no empty heading).
 * - A rule's move uses the Cahier's own stage words, as the server sends them
 *   (`concept_life.stage_label`, WP-130); a rule met this week says so.
 * - Home's card shows the last closed week until the learner opens it or says «not
 *   now» (one key per week in local storage; a failed storage read shows it).
 */

import type { Bilan, BilanCard, BilanDecision, BilanLanguage, BilanRule } from '@/lib/bilan-types';

import { fill, type BilanCopy } from './bilan-copy';

const LOCALE: Record<BilanLanguage, string> = { en: 'en-GB', de: 'de-DE', fr: 'fr-FR' };

/** A learner-local ISO day read as that calendar day (no zone shift). */
function day(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, (m || 1) - 1, d || 1, 12));
}

function format(iso: string, language: BilanLanguage, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(LOCALE[language], { timeZone: 'UTC', ...options }).format(day(iso));
}

/** «16–22 novembre», «28 Oct – 3 Nov», «29. Dez. – 4. Jan.». */
export function weekRange(start: string, end: string, language: BilanLanguage): string {
  const a = day(start);
  const b = day(end);
  if (a.getUTCMonth() === b.getUTCMonth()) {
    const last = format(end, language, { day: 'numeric', month: 'long' });
    // German writes the first day as an ordinal too: «16.–22. November».
    const first = `${format(start, language, { day: 'numeric' })}${language === 'de' ? '.' : ''}`;
    return `${first}–${last}`;
  }
  const short: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  return `${format(start, language, short)} – ${format(end, language, short)}`;
}

/** The weekday's initial for the days row (M T W… / L M M… / M D M…). */
export function weekdayInitial(iso: string, language: BilanLanguage): string {
  return format(iso, language, { weekday: 'narrow' }).toLocaleUpperCase(LOCALE[language]);
}

export function weekdayName(iso: string, language: BilanLanguage): string {
  return format(iso, language, { weekday: 'long', day: 'numeric', month: 'long' });
}

export type BilanTone = 'full' | 'thin' | 'empty';

export function bilanTone(bilan: Pick<Bilan, 'daysPlayed'>): BilanTone {
  if (bilan.daysPlayed <= 0) return 'empty';
  return bilan.daysPlayed === 1 ? 'thin' : 'full';
}

export function bilanHeadline(bilan: Bilan, copy: BilanCopy): { title: string; body: string | null } {
  const tone = bilanTone(bilan);
  if (tone === 'empty') {
    return { title: bilan.isCurrent ? copy.headline_none_current : copy.headline_none, body: copy.body_none };
  }
  if (tone === 'thin') return { title: copy.headline_one, body: copy.body_one };
  return {
    title: fill(bilan.isCurrent ? copy.headline_many_current : copy.headline_many, { n: bilan.daysPlayed }),
    body: null,
  };
}

export function bilanKicker(bilan: Bilan, copy: BilanCopy): string {
  const range = weekRange(bilan.weekStart, bilan.weekEnd, bilan.language);
  const head = fill(copy.week_of, { range });
  return bilan.isCurrent ? `${head} · ${copy.so_far}` : head;
}

export function wordLines(bilan: Bilan, copy: BilanCopy): string[] {
  const { newCount, heldCount } = bilan.words;
  const lines: string[] = [];
  if (newCount > 0) lines.push(newCount === 1 ? copy.words_new_one : fill(copy.words_new_many, { n: newCount }));
  if (heldCount > 0) lines.push(heldCount === 1 ? copy.words_held_one : fill(copy.words_held_many, { n: heldCount }));
  return lines;
}

/** «met this week · practising» or «practising → held», in the Cahier's words. */
export function ruleMove(rule: BilanRule, copy: BilanCopy): string {
  const now = rule.stageLabel ?? '';
  if (rule.fromStage === 'new' || !rule.fromLabel) return now ? `${copy.rule_met} · ${now}` : copy.rule_met;
  return now ? `${rule.fromLabel} → ${now}` : rule.fromLabel;
}

/**
 * The story as it reads: each episode with the «Le choix» cards tapped that day (a card
 * alone — «Personne» — says nothing without its scene), then what is left: the
 * commitments and the chapter answers the story filed, and any card of a day with no
 * title.
 */
export function storyRows(bilan: Bilan): {
  episodes: { episode: Bilan['story']['episodes'][number]; choices: BilanDecision[] }[];
  rest: BilanDecision[];
} {
  const used = new Set<BilanDecision>();
  const episodes = bilan.story.episodes.map((episode) => {
    const choices = bilan.story.decisions.filter((d) => d.kind === 'choice' && d.date === episode.date && !used.has(d));
    choices.forEach((choice) => used.add(choice));
    return { episode, choices };
  });
  return { episodes, rest: bilan.story.decisions.filter((d) => !used.has(d)) };
}

export type BilanSections = { lines: boolean; words: boolean; rules: boolean; story: boolean };

/** Which sections have something true to say. */
export function bilanSections(bilan: Bilan): BilanSections {
  const story = bilan.story;
  return {
    lines: bilan.lines.length > 0,
    words: bilan.words.newCount > 0 || bilan.words.heldCount > 0,
    rules: bilan.rules.length > 0,
    story: story.episodes.length > 0 || story.decisions.length > 0 || Boolean(story.nextFr),
  };
}

// ---------------------------------------------------------------------------
// Home's card
// ---------------------------------------------------------------------------

export const BILAN_SEEN_PREFIX = 'atelier.bilan.seen.';

export type SeenStore = { get: (key: string) => string | null; set: (key: string, value: string) => void };

export function browserSeenStore(): SeenStore {
  return {
    get: (key) => {
      try {
        return window.localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    set: (key, value) => {
      try {
        window.localStorage.setItem(key, value);
      } catch {
        // Private mode: the card simply shows again next time.
      }
    },
  };
}

export function markBilanSeen(weekStart: string, store: SeenStore): void {
  store.set(`${BILAN_SEEN_PREFIX}${weekStart}`, '1');
}

/** The week Home's card leads to, or null: a played closed week not yet opened. */
export function cardWeek(card: BilanCard | null | undefined, store: SeenStore): string | null {
  if (!card || !card.weekStart || card.daysPlayed <= 0) return null;
  return store.get(`${BILAN_SEEN_PREFIX}${card.weekStart}`) ? null : card.weekStart;
}

/** «Ta semaine, 16–22 novembre» and «4 jours joués». */
export function cardLines(card: BilanCard, language: BilanLanguage, copy: BilanCopy): { title: string; meta: string } {
  const start = card.weekStart ?? '';
  const end = start ? new Date(day(start).getTime() + 6 * 86400000).toISOString().slice(0, 10) : '';
  return {
    title: fill(copy.card_title, { range: start ? weekRange(start, end, language) : '' }),
    meta: card.daysPlayed === 1 ? copy.card_days_one : fill(copy.card_days_many, { n: card.daysPlayed }),
  };
}

/** The Relevé's row for one week. */
export function weekRow(
  weekStart: string,
  daysPlayed: number,
  isCurrent: boolean,
  language: BilanLanguage,
  copy: BilanCopy,
): { label: string; meta: string } {
  const end = new Date(day(weekStart).getTime() + 6 * 86400000).toISOString().slice(0, 10);
  return {
    label: isCurrent ? copy.releve_this_week : fill(copy.releve_week, { range: weekRange(weekStart, end, language) }),
    meta: daysPlayed === 1 ? copy.releve_days_one : fill(copy.releve_days_many, { n: daysPlayed }),
  };
}
