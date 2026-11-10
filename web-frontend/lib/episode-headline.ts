/**
 * WP-109 «Une seule maison»: today's episode as Home and the Feuilleton headline it
 * (`TodayEnvelope.headline`). Pure: no React, no fetch.
 */

import type { TodayEnvelope } from '@/types/daily-journey';

export type EpisodeHeadline = NonNullable<TodayEnvelope['headline']>;

/** The engine's generic offer title, which names nothing. */
const GENERIC_TITLES = new Set(['Votre prochain chapitre']);

/** One entry into today's episode: starts the day, or resumes it where it is. */
export const TODAY_EPISODE_HREF = '/atelier?start=today';

function join(...parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => (typeof part === 'string' ? part.trim() : ''))
    .filter(Boolean)
    .join(' · ');
}

/**
 * «Nº 7 · La clé d'Odile»: the episode's number and its season; «Nº 7 · Relecture · …»
 * when the day re-reads an earlier page (#314: said where the day is announced).
 */
export function headlineKicker(headline: EpisodeHeadline | null | undefined, language: string | null = 'fr'): string {
  if (!headline) return '';
  const arc = headlineArc(headline, language);
  return join(
    headline.edition_no ? `Nº ${headline.edition_no}` : '',
    headline.reread ? 'Relecture' : null,
    // Red thread: inside a gap that names its destination, the gap and the days left
    // lead; the season's title is on the page's masthead already.
    arc || (headline.season_title_fr ?? null),
  );
}

const WEEKDAYS: Record<string, { de: string; en: string }> = {
  lundi: { de: 'Montag', en: 'Monday' },
  mardi: { de: 'Dienstag', en: 'Tuesday' },
  mercredi: { de: 'Mittwoch', en: 'Wednesday' },
  jeudi: { de: 'Donnerstag', en: 'Thursday' },
  vendredi: { de: 'Freitag', en: 'Friday' },
  samedi: { de: 'Samstag', en: 'Saturday' },
  dimanche: { de: 'Sonntag', en: 'Sunday' },
};

/**
 * «Avant la fête · noch 3 Tage bis Samstag»: where the gap is going and how far it is
 * (`headline.arc`, sent only while `STORY_DAY_CONTRACT` is on). The gap's title stays
 * French, as the story's; the countdown is in the learner's own language.
 */
export function headlineArc(headline: EpisodeHeadline | null | undefined, language: string | null = 'fr'): string {
  const arc = headline?.arc;
  if (!arc || !(arc.days_left >= 1)) return '';
  const lang = language === 'de' || language === 'en' ? language : 'fr';
  const whenFr = String(arc.when_fr || '').trim();
  const day = lang === 'fr' ? whenFr : (WEEKDAYS[whenFr.toLowerCase()]?.[lang] ?? whenFr);
  const n = arc.days_left;
  let countdown: string;
  if (lang === 'de') countdown = n === 1 ? `morgen ist ${day}` : `noch ${n} Tage bis ${day}`;
  else if (lang === 'en') countdown = n === 1 ? `${day} is tomorrow` : `${n} days to ${day}`;
  else countdown = n === 1 ? `demain, c'est ${day}` : `${day}, dans ${n} jours`;
  return join(arc.gap_title_fr, countdown);
}

/**
 * The headline's title: the episode's own title when known; else yesterday's «À
 * suivre…» leads — a generated day has no title until it is written, and the
 * generic «Votre prochain chapitre» says nothing.
 */
export function headlineTitle(headline: EpisodeHeadline | null | undefined, fallback = ''): string {
  const title = String(headline?.title_fr || '').trim();
  if (title) return title;
  const teaser = bareTeaser(headline);
  const generic = !fallback.trim() || GENERIC_TITLES.has(fallback.trim());
  return generic && teaser ? teaser : fallback;
}

/** The teaser without its own closing «À suivre…» (the label already says it). */
function bareTeaser(headline: EpisodeHeadline | null | undefined): string {
  return String(headline?.teaser_fr || '').trim().replace(/\s*À suivre\s*(?:…|\.\.\.)?\s*$/, '').trim();
}

/** The teaser to print under the title — never the title twice. */
export function headlineTeaser(headline: EpisodeHeadline | null | undefined, title: string): string | null {
  const teaser = bareTeaser(headline);
  return teaser && teaser !== title.trim() ? teaser : null;
}
