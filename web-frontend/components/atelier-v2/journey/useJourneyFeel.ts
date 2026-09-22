/**
 * WP-76 — every journey state has a haptic (and, where it is news, a sound).
 *
 *   a verdict from the server  → correct / wrong  (silent if the device already
 *                                felt it from the hashed key — `lib/feel`)
 *   the next step opens        → a light tap
 *   the day is done            → the success pattern and the arpeggio
 *
 * Only transitions are felt: opening a finished day, or reloading onto a graded
 * step, is not a new event and says nothing.
 */

import { useEffect, useRef } from 'react';

import { feel, verdictAlreadyFelt } from '@/lib/feel';
import { preloadFeelSounds } from '@/lib/sound';

import type { JourneyFeedback, JourneyPhase } from './journey-state';

export type FeelTransition = 'correct' | 'wrong' | 'step' | 'complete' | null;

/** Pure: what one render-to-render change should feel like. */
export function feelForTransition(
  before: { phase: JourneyPhase['kind'] | null; stepId: string | null; result: unknown },
  after: {
    phase: JourneyPhase['kind'];
    stepId: string | null;
    feedback: JourneyFeedback;
  },
): FeelTransition {
  const live = before.phase === 'session' || before.phase === 'awaiting_finish';
  if (after.phase === 'finished' && live) return 'complete';
  if (after.feedback.kind === 'graded' && after.feedback.result !== before.result) {
    if (verdictAlreadyFelt(after.stepId)) return null;
    return after.feedback.verdict === 'wrong' ? 'wrong' : 'correct';
  }
  if (
    after.phase === 'session' &&
    before.phase === 'session' &&
    before.stepId &&
    after.stepId &&
    before.stepId !== after.stepId
  ) {
    return 'step';
  }
  return null;
}

export function useJourneyFeel(
  phase: JourneyPhase['kind'],
  stepId: string | null,
  feedback: JourneyFeedback,
): void {
  const before = useRef<{ phase: JourneyPhase['kind'] | null; stepId: string | null; result: unknown }>({
    phase: null,
    stepId: null,
    result: null,
  });

  useEffect(() => {
    preloadFeelSounds();
  }, []);

  useEffect(() => {
    const result = feedback.kind === 'graded' ? feedback.result : null;
    // A reload that opens on an already graded step is not a new verdict.
    const previous = before.current.phase === null ? { ...before.current, result } : before.current;
    const moment = feelForTransition(previous, { phase, stepId, feedback });
    before.current = { phase, stepId, result };
    if (moment) feel(moment);
  }, [phase, stepId, feedback]);
}
