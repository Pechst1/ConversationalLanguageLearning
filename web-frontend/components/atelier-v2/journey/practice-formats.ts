/**
 * WP-78 — pure helpers for the practice day's quick formats.
 *
 * Kept apart from the renderers so the node tests can drive them without a
 * DOM: which cards are French and which are meanings, when a matching grid is
 * finished, whether a listen-and-tap item can actually be heard, and how many
 * graded interactions a day holds.
 */

import type { JourneySnapshot, RecallOption, RecallPrompt } from '@/types/daily-journey';

/** The two columns of a matching item, in the order the server laid them out. */
export function matchCards(options: readonly RecallOption[]): {
  fr: RecallOption[];
  native: RecallOption[];
} {
  return {
    fr: options.filter((option) => option.side !== 'native'),
    native: options.filter((option) => option.side === 'native'),
  };
}

/** Every French card is in a settled pair. */
export function pairsComplete(settled: readonly string[], frCount: number): boolean {
  return frCount > 0 && settled.length >= frCount * 2;
}

/**
 * A listen-and-tap item is heard only when the server sent a clip. Without
 * one it is read-and-tap: the phrase is printed and nothing speaks of audio.
 */
export function listenTapHasAudio(prompt: Pick<RecallPrompt, 'task_type' | 'audio_url'>): boolean {
  return prompt.task_type === 'listen_tap' && Boolean(prompt.audio_url);
}

/** Cards whose text is in the learner's language are not marked `lang="fr"`. */
export function optionLang(option: Pick<RecallOption, 'side'>): string | undefined {
  return option.side === 'native' ? undefined : 'fr';
}

/** Recall steps that are not skipped, plus the reply: what the learner answers today. */
export function gradedInteractions(journey: Pick<JourneySnapshot, 'steps'> | null): number {
  if (!journey) return 0;
  return journey.steps.filter(
    (step) => step.kind === 'respond' || (step.kind === 'recall' && step.status !== 'skipped'),
  ).length;
}

/** The first scene step — no longer always `steps[0]` on a practice day. */
export function firstSceneStepId(journey: Pick<JourneySnapshot, 'steps'> | null): string | null {
  return journey?.steps.find((step) => step.kind === 'scene')?.id ?? null;
}
