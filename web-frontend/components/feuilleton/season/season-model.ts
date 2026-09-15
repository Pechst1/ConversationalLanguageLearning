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
 */

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

export type SeasonPayload = {
  thread_id: string | null;
  season_number: number;
  chapter: { number: number; title_fr: string } | null;
  today: SeasonEpisode | null;
  commitments: SeasonCommitment[];
  read_episodes: SeasonEpisode[];
};

/** The eyebrow: «Saison 1 · chapitre 1 · S'installer, avec complications». */
export function seasonStoryLabel(season: SeasonPayload | null | undefined): string {
  if (!season) return '';
  const parts = [`Saison ${Math.max(1, Number(season.season_number) || 1)}`];
  const chapter = season.chapter;
  if (chapter && Number(chapter.number) > 0) parts.push(`chapitre ${chapter.number}`);
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
export function seasonTodayLabel(episode: SeasonEpisode | null | undefined): string {
  if (!episode) return '';
  return `Aujourd’hui · épisode ${episode.number} · se joue dans la séance`;
}

/** A read row's second line: «avec Lila · l'appartement». Empty when neither. */
export function seasonEpisodeMeta(episode: SeasonEpisode | null | undefined): string {
  if (!episode) return '';
  const who = String(episode.character || '').trim();
  const where = String(episode.location || '').trim();
  const parts = [who ? `avec ${who}` : '', where].filter(Boolean);
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
