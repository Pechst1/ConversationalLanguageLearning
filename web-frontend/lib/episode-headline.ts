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

/** «Nº 7 · La clé d'Odile»: the episode's number and its season. */
export function headlineKicker(headline: EpisodeHeadline | null | undefined): string {
  if (!headline) return '';
  return join(headline.edition_no ? `Nº ${headline.edition_no}` : '', headline.season_title_fr ?? null);
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
