/**
 * The Feuilleton tab's season page, as data (WP-44).
 *
 * `GET /api/v1/serial/season` is a projection of state the story already owns:
 * the scenes the learner has read, the one that is waiting in today's séance,
 * and the promises they have made that nobody has kept yet. This module turns
 * that payload into the lines the artboard prints, and nothing else — it
 * fetches nothing, invents no episode, and never fills a gap with a placeholder.
 *
 * Pure, so the composition rules (what the label says, when the page is empty,
 * what a row's second line is) are unit-tested without a browser.
 *
 * WP-82: the labels are chrome, so each takes the screen's chrome language
 * (`chromeLanguage`); none given keeps the French table. The titles, briefs,
 * threads and promises are story and stay French.
 */

import { fbFill, feuilletonCopy } from '@/components/feuilleton/feuilleton-copy';

export type SeasonEpisode = {
  scene_id: string;
  /** The Nth scene of this season, 1-based, as the server counted it. */
  number: number;
  title_fr: string;
  brief_fr: string;
  image_url: string | null;
  /** Display name of the character the learner met, or '' when unknown. */
  character: string;
  /** Display name of the place, or '' when unknown. */
  location: string;
  status: string;
};

export type SeasonCommitment = { id: string; text_fr: string };

/**
 * One of the season's long questions, with the state the story has put it in
 * (WP-63). `open` means nothing has touched it yet, `developing` that a chapter
 * moved it, `closed` that it has been settled — by a chapter or by the finale.
 */
export type SeasonThread = { key: string; text_fr: string; state: string };

export type SeasonPayload = {
  thread_id: string | null;
  season_number: number;
  chapter: { number: number; title_fr: string } | null;
  today: SeasonEpisode | null;
  commitments: SeasonCommitment[];
  /** Absent on a payload served before WP-63; the page then shows no thread list. */
  threads?: SeasonThread[];
  read_episodes: SeasonEpisode[];
};

/** The label a thread's state gets: «en suspens», «ça bouge», «réglé». */
export function seasonThreadLabel(state: string | null | undefined, language?: unknown): string {
  const t = feuilletonCopy(language);
  return (
    ({ open: t.thread_open, developing: t.thread_developing, closed: t.thread_closed } as Record<string, string>)[
      String(state || 'open')
    ] || t.thread_open
  );
}

/**
 * The threads worth printing: the ones with a French line, closed ones last.
 *
 * A season question nobody has touched is still a question, so `open` rows stay —
 * this list is the promise the season made, not a progress bar. What it must never
 * do is claim movement the story did not make, which is why the state comes from
 * the payload and is never inferred here.
 */
export function seasonThreads(season: SeasonPayload | null | undefined): SeasonThread[] {
  const rows = (season?.threads || []).filter((row) => String(row?.text_fr || '').trim());
  const order: Record<string, number> = { developing: 0, open: 1, closed: 2 };
  return rows
    .map((row) => ({ ...row, state: String(row.state || 'open') }))
    .sort((a, b) => (order[a.state] ?? 1) - (order[b.state] ?? 1));
}

/** The eyebrow: «Saison 1 · chapitre 1 · S'installer, avec complications». */
export function seasonStoryLabel(season: SeasonPayload | null | undefined, language?: unknown): string {
  if (!season) return '';
  const t = feuilletonCopy(language);
  const parts = [fbFill(t.season_n, { n: Math.max(1, Number(season.season_number) || 1) })];
  const chapter = season.chapter;
  if (chapter && Number(chapter.number) > 0) parts.push(fbFill(t.chapter_n, { n: chapter.number }));
  if (chapter && String(chapter.title_fr || '').trim()) parts.push(String(chapter.title_fr).trim());
  return parts.join(' · ');
}

/**
 * Today's label: «Aujourd'hui · épisode 4 · se joue dans la séance».
 *
 * The third clause is the honest part. The scene of the day is not opened from
 * this page — it is played in the séance, where the learner answers and the
 * story moves. Saying so here is what keeps the tab a place to look back from
 * rather than a second, silent way to start a day.
 */
export function seasonTodayLabel(episode: SeasonEpisode | null | undefined, language?: unknown): string {
  if (!episode) return '';
  return fbFill(feuilletonCopy(language).season_today, { n: episode.number });
}

/** A read row's second line: «avec Lila · l'appartement». Empty when neither. */
export function seasonEpisodeMeta(
  episode: Pick<SeasonEpisode, 'character' | 'location'> | null | undefined,
  language?: unknown,
): string {
  if (!episode) return '';
  const who = String(episode.character || '').trim();
  const where = String(episode.location || '').trim();
  const parts = [who ? fbFill(feuilletonCopy(language).with_character, { name: who }) : '', where].filter(Boolean);
  return parts.join(' · ');
}

/**
 * True when nothing has been read yet.
 *
 * The page then says one sentence and stops. A season with no episode behind it
 * is not a defect to dress up: it is a learner on their first day, and the only
 * true thing to tell them is where the first scene opens.
 */
export function seasonHasNothingRead(season: SeasonPayload | null | undefined): boolean {
  return !(season?.read_episodes || []).length;
}

/** Whether this learner has a season at all — one open scene, or one read. */
export function seasonHasStory(season: SeasonPayload | null | undefined): boolean {
  if (!season) return false;
  return Boolean(season.today) || (season.read_episodes || []).length > 0;
}
