/**
 * WP-76 — one call per moment the learner should *feel*: a haptic and, when
 * sounds are on, a short tone. Every state in the journey has exactly one:
 *
 *   correct  → a medium tap      + the rising third
 *   wrong    → a warning buzz    + the soft falling step
 *   step     → a light tap       (no sound: moving on is not news)
 *   complete → a success pattern + the arpeggio
 *
 * Haptics already stand down under Reduce Motion (`lib/haptics.ts`); sounds
 * follow the Réglages toggle and, in the app, the ringer switch.
 */

import { pulseAppHaptic } from '@/lib/haptics';
import { playFeelSound } from '@/lib/sound';

export type FeelMoment = 'correct' | 'wrong' | 'step' | 'complete';

export function feel(moment: FeelMoment): void {
  switch (moment) {
    case 'correct':
      pulseAppHaptic('correct');
      playFeelSound('correct');
      return;
    case 'wrong':
      pulseAppHaptic('repair');
      playFeelSound('wrong');
      return;
    case 'step':
      pulseAppHaptic('selection');
      return;
    case 'complete':
      pulseAppHaptic('complete');
      playFeelSound('complete');
      return;
    default:
      return;
  }
}

// ---------------------------------------------------------------------------
// One verdict, felt once
// ---------------------------------------------------------------------------

/**
 * The recall step feels its verdict the moment the local key answers; the
 * server's verdict then arrives seconds later. This remembers which steps
 * were already felt so the confirmation is silent — and a server that
 * *disagrees* corrects the colours quietly rather than buzzing twice.
 */
const felt = new Map<string, 'correct' | 'wrong'>();

export function markVerdictFelt(stepId: string, verdict: 'correct' | 'wrong'): void {
  if (stepId) felt.set(stepId, verdict);
}

export function verdictAlreadyFelt(stepId: string | null | undefined): boolean {
  return Boolean(stepId && felt.has(stepId));
}

/** Test seam. */
export function resetFeltVerdicts(): void {
  felt.clear();
}
