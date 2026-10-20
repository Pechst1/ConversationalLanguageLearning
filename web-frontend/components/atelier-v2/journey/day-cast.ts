/**
 * Les apparitions, tied to the day: who is on today's page, and which part of the season it is.
 *
 * The cameo layer draws its walk-ons from `dayCast` (the people who speak on the day's page and
 * in its steps), so a drill after the scene is visited by somebody the learner has just read,
 * and `chapterReached` names the part of the season once its page has been read, so the object
 * that part turns on can be handed over (lib/season-items).
 */
import { castIdFor } from '@/lib/cast-faces';
import type { SeasonPart } from '@/lib/season-items';
import type { JourneySnapshot, StoryEpisode } from '@/types/daily-journey';

import { journeySpeaker } from './journey-faces';

type DayJourney = Pick<JourneySnapshot, 'scenario' | 'steps'>;

/** The cameo cast ids of today's page: its panels' speakers, then every step's face. */
export function dayCast(journey: DayJourney | null | undefined, episode?: Pick<StoryEpisode, 'panels'> | null): string[] {
  if (!journey) return [];
  const ids: Array<string | null> = [];
  for (const panel of episode?.panels ?? []) {
    for (const line of panel?.dialogue ?? []) ids.push(castIdFor(line.character_id, line.character_name));
  }
  for (const step of journey.steps ?? []) {
    const speaker = journeySpeaker(journey, step);
    if (speaker) ids.push(castIdFor(speaker.id, speaker.name));
  }
  return Array.from(new Set(ids.filter((id): id is string => !!id)));
}

/** The season part of the day's page, once that page has been read; `null` before, or off a season. */
export function chapterReached(journey: DayJourney | null | undefined): SeasonPart | null {
  const scene = (journey?.steps ?? []).find((step) => step.kind === 'scene');
  if (!scene || scene.kind !== 'scene' || scene.status !== 'completed') return null;
  const part = scene.prompt.season_part;
  return part && part.season_id && part.segment ? part : null;
}
