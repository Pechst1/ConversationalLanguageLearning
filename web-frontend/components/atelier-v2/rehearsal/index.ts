/**
 * WP-31 «Répétition» — public surface.
 *
 * The screen is a renderer over `rehearsal-state.ts`; every decision worth
 * testing lives in the pure module, which is what the node suite exercises.
 */

export { RehearsalScreen } from './RehearsalScreen';
export type { RehearsalScreenProps } from './RehearsalScreen';

export {
  DEBRIEF_CHOICES,
  capSentence,
  eventDateSentence,
  nextSlotSentence,
  nextTurnIndex,
  phaseFor,
  resultSentence,
  turnsRemaining,
} from './rehearsal-state';
export type { DebriefOutcome, RehearsalPhase } from './rehearsal-state';
