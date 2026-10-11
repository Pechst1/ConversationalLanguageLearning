/**
 * WP-93 «Plus d'histoire, moins d'exercices» — the READ step, as data.
 *
 * A READ step is a page to read, advanced and never answered, and always
 * optional: «Relecture» (yesterday's page again) or «Coulisses» (the same
 * evening from another cast member's point of view, written in the background).
 * The step itself carries no page — it names one (`scene_id`), which the
 * view fetches from `GET /story-engine/episodes/{scene_id}` and opens in the
 * reader, read-only.
 *
 * While «Coulisses» is still `writing` the controller re-reads the journey
 * snapshot gently (`readPollTarget`, every few seconds, bounded); when it
 * turns `ready` the page opens; `unavailable` is one quiet line. Whatever the
 * state, «Continuer» is enabled.
 *
 * Pure: no React, no fetch — unit-tested with `node --test`.
 */

import type { JourneySnapshot, PublicStep, ReadPrompt, ReadStep, StoryEpisode } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';

/** Gently: a page in the background is not an ending the learner waits on. */
export const READ_POLL_MS = 4_000;
/** About three minutes; after that the step says nothing new and stays skippable. */
export const READ_POLL_LIMIT = 45;

export function isReadStep(step: PublicStep | null | undefined): step is ReadStep {
  return Boolean(step && step.kind === 'read');
}

/** Is this a READ step whose page is still being written? */
export function readStepWriting(step: PublicStep | null | undefined): boolean {
  return isReadStep(step) && step.prompt?.status === 'writing';
}

/** The journey to re-read while its current READ step is being written, else `null`. */
export function readPollTarget(journey: JourneySnapshot | null | undefined): string | null {
  if (!journey || (journey.status !== 'active' && journey.status !== 'paused')) return null;
  const current = journey.steps.find((step) => step.id === journey.current_step_id) ?? null;
  return readStepWriting(current) ? journey.id : null;
}

/** The episode lookup the view holds for the step's `scene_id`. */
export type ReadLookup =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'episode'; episode: StoryEpisode }
  | { kind: 'failed' };

export type ReadView = 'writing' | 'unavailable' | 'loading' | 'reader';

/**
 * What the step shows. The server's status first; a `ready` page with no
 * scene, a page that cannot be fetched, or a page with no panels is
 * `unavailable` — said once, quietly, never an error the learner must clear.
 */
export function readStepView(prompt: Partial<ReadPrompt> | null | undefined, lookup: ReadLookup): ReadView {
  const status = prompt?.status;
  if (status === 'writing') return 'writing';
  if (status !== 'ready') return 'unavailable';
  if (!prompt?.scene_id) return 'unavailable';
  if (lookup.kind === 'idle' || lookup.kind === 'loading') return 'loading';
  if (lookup.kind === 'failed') return 'unavailable';
  return (lookup.episode.panels?.length ?? 0) > 0 ? 'reader' : 'unavailable';
}

/** Whether the view should ask for the page now. */
export function readStepWantsEpisode(prompt: Partial<ReadPrompt> | null | undefined): string | null {
  return prompt?.status === 'ready' && prompt.scene_id ? String(prompt.scene_id) : null;
}

/** Whose evening «Coulisses» tells: the prompt's cast member, else the day's counterpart. */
export function readStepSpeaker(
  prompt: Partial<ReadPrompt> | null | undefined,
  fallback: { id: string | null; name: string } | null = null,
): { id: string | null; name: string } | null {
  const name = typeof prompt?.character_name === 'string' ? prompt.character_name.trim() : '';
  const id = typeof prompt?.character_id === 'string' ? prompt.character_id.trim() : '';
  if (name) return { id: id || null, name };
  if (id) return { id, name: id.split('_')[0].replace(/^./, (c) => c.toUpperCase()) };
  return prompt?.variant === 'coulisses' ? fallback : null;
}

type ReadCopy = Pick<
  JourneyCopy,
  'read_relecture' | 'read_coulisses' | 'read_coulisses_anon' | 'read_writing' | 'read_writing_anon'
>;

/** The kicker: «Relecture · la page d’hier» / «Coulisses · la soirée de Marin». */
export function readStepEyebrow(
  prompt: Partial<ReadPrompt> | null | undefined,
  copy: ReadCopy,
  who: string | null | undefined,
): string {
  if (prompt?.variant !== 'coulisses') return copy.read_relecture;
  const name = String(who || '').trim();
  return name ? copy.read_coulisses.replace('{name}', name) : copy.read_coulisses_anon;
}

/** The line beside the face while «Coulisses» is written. */
export function readStepWritingLine(copy: ReadCopy, who: string | null | undefined): string {
  const name = String(who || '').trim();
  return name ? copy.read_writing.replace('{name}', name) : copy.read_writing_anon;
}
