/**
 * WP-91 «Les voix» — the voice a journey step speaks with.
 *
 * The step's server clips when the day and the step are known
 * (`journeyLineResolver`), the device's French voice otherwise. A screen that
 * already holds a voice passes it as `shared` and this one stays idle, so one
 * line speaks at a time across the whole screen.
 */

import { useMemo } from 'react';

import { journeyLineResolver } from '@/services/daily-journey';

import type { JourneyCopy } from './journey-copy';
import { useLineVoice, type LineVoice } from './useLineVoice';

export function useStepVoice(
  journeyId: string | null | undefined,
  stepId: string | null | undefined,
  shared?: LineVoice | null,
): LineVoice {
  const resolve = useMemo(
    () => (journeyId && stepId ? journeyLineResolver(journeyId, stepId) : undefined),
    [journeyId, stepId],
  );
  const own = useLineVoice({ resolve });
  return shared ?? own;
}

/** «Écouter Margaux», in the learner's language; the line itself when there is no name. */
export function listenLabel(
  copy: Pick<JourneyCopy, 'voice_listen_to' | 'voice_listen_line'>,
  name: string | null | undefined,
): string {
  const who = String(name || '').trim();
  return who ? copy.voice_listen_to.replace('{name}', who) : copy.voice_listen_line;
}
