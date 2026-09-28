/**
 * WP-76 — every journey state has a haptic (and, where it is news, a sound).
 *
 *   a verdict from the server  → correct / wrong  (silent if the device already
 *                                felt it from the hashed key — `lib/feel`)
 *   the next step opens        → a light tap
 *   a reply mid-conversation   → a light tick, once per turn (WP-89: the
 *                                verdict, its buzz and its sound wait for the
 *                                closing turn)
 *   the day is done            → the success pattern and the arpeggio
 *
 * Only transitions are felt: opening a finished day, or reloading onto a graded
 * step, is not a new event and says nothing.
 */

import { useEffect, useRef } from 'react';

import { feel, verdictAlreadyFelt } from '@/lib/feel';
import { preloadFeelSounds } from '@/lib/sound';

import type { JourneyFeedback, JourneyPhase } from './journey-state';
import { continuesConversation } from './respond-thread';

export type FeelTransition = 'correct' | 'wrong' | 'step' | 'reply' | 'complete' | null;

type FeelBefore = {
  phase: JourneyPhase['kind'] | null;
  stepId: string | null;
  result: unknown;
  /** WP-89: the last continuing-turn result already ticked (one tick per turn). */
  reply?: unknown;
};

/** Pure: what one render-to-render change should feel like. */
export function feelForTransition(
  before: FeelBefore,
  after: {
    phase: JourneyPhase['kind'];
    stepId: string | null;
    feedback: JourneyFeedback;
  },
): FeelTransition {
  const live = before.phase === 'session' || before.phase === 'awaiting_finish';
  if (after.phase === 'finished' && live) return 'complete';
  // WP-89: a reply that carries another turn is the conversation going on —
  // a light tick when it arrives (keyed on the turn's own result, so the
  // staged `replying` → `graded` pair ticks once), never a verdict.
  if (continuesConversation(after.feedback)) {
    const result = (after.feedback as { result: unknown }).result;
    return result !== before.reply && result !== before.result ? 'reply' : null;
  }
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
  const before = useRef<FeelBefore>({
    phase: null,
    stepId: null,
    result: null,
    reply: null,
  });

  useEffect(() => {
    preloadFeelSounds();
  }, []);

  useEffect(() => {
    const continuing = continuesConversation(feedback);
    const answered =
      feedback.kind === 'graded' || feedback.kind === 'replying' ? feedback.result : null;
    const result = feedback.kind === 'graded' && !continuing ? feedback.result : null;
    const reply = continuing ? answered : before.current.reply;
    // A reload that opens on an already graded step is not a new verdict.
    const previous =
      before.current.phase === null ? { ...before.current, result, reply } : before.current;
    const moment = feelForTransition(previous, { phase, stepId, feedback });
    before.current = { phase, stepId, result, reply };
    if (moment) feel(moment);
  }, [phase, stepId, feedback]);
}
