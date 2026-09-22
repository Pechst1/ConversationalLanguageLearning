/**
 * WP-77 — who is on screen in the daily journey.
 *
 * The scene's speaker and the one who reacts to a recall answer is the day's
 * scenario character; a respond step names its own speaker (a letter day's
 * correspondent first). Pure, so the node harness can check it.
 */

import type { JourneySnapshot, PublicStep } from '@/types/daily-journey';

export type JourneySpeaker = { id: string | null; name: string };

export function journeySpeaker(
  journey: Pick<JourneySnapshot, 'scenario'> | null | undefined,
  step?: PublicStep | null,
): JourneySpeaker | null {
  if (step?.kind === 'respond') {
    const letter = step.prompt.letter;
    if (letter?.correspondent_name) {
      return { id: letter.correspondent_id || null, name: letter.correspondent_name };
    }
    if (step.prompt.character_name) {
      return { id: step.prompt.character_id || null, name: step.prompt.character_name };
    }
  }
  const scenario = journey?.scenario;
  if (scenario?.character_name) {
    return { id: scenario.character_id || null, name: scenario.character_name };
  }
  return null;
}
