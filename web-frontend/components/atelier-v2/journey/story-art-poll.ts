/**
 * The reader's panel-art poll, with a late-drawing grace (2026-09-30).
 *
 * The server serves a panel still `rendering` after its timeout as the plate
 * (`setting_reference`) — the wire does not say «timeout». A drawing already in
 * flight can still land afterwards (the server writes it back as ready), so a
 * page that was seen drawing keeps being re-read for another five minutes while
 * it still shows plates. A page that was never seen drawing (art off, an old
 * page) is not polled at all.
 */

import type { StoryEpisode } from '@/types/daily-journey';
import { STORY_ART_POLL_LIMIT, storyArtRendering } from './story-episode-model';

/** Five more minutes at the 6 s cadence. */
export const STORY_ART_LATE_POLLS = 50;

export function storyShowsPlates(episode: StoryEpisode | null | undefined): boolean {
  return Boolean(episode?.panels?.some((panel) => panel.image_status === 'setting_reference'));
}

/**
 * @param sawRendering whether this episode was ever seen with a panel drawing
 * @param polls        re-reads already made
 */
export function shouldPollStoryArtLate(
  episode: StoryEpisode | null | undefined,
  polls: number,
  sawRendering: boolean,
): boolean {
  if (!episode) return false;
  if (storyArtRendering(episode)) return polls < STORY_ART_POLL_LIMIT + STORY_ART_LATE_POLLS;
  return sawRendering && storyShowsPlates(episode) && polls < STORY_ART_POLL_LIMIT + STORY_ART_LATE_POLLS;
}
