/**
 * The day's order, written once on this side (owner, 1 Nov 2026: the scene,
 * then La Forge, then the words, then the seal).
 *
 * The server's `DaySessionStepKind` literal (`app/schemas/daily_journey.py`)
 * is the source; it lays out `TodayEnvelope.session`, and the generated
 * `types/generated/api.ts` union keeps its order. `day-order.test.js` fails
 * when `WORK_STEPS` disagrees with that union, and when any other file writes
 * the order out again. Everything else derives from here: `day-plan.ts`'s
 * hand-ons and the onboarding route's `ROUTE_STAGES` (`first-steps.ts`).
 *
 * Pure: types and constants only, so `first-steps.ts` can import it without
 * pulling in the day session's UI helpers.
 */

import type { DaySessionStepKind } from '@/types/daily-journey';

/** The steps a learner works through; «finish» is the seal, not work. */
export type DayWorkKind = Exclude<DaySessionStepKind, 'finish'>;

/** The working steps in the day's order. */
export const WORK_STEPS: readonly DayWorkKind[] = ['scene', 'grammar', 'words'];

/** The first day's route names the same steps in its own words. */
export type RouteStage = 'story' | 'forge' | 'words';

export const ROUTE_STAGE_OF: Readonly<Record<DayWorkKind, RouteStage>> = {
  scene: 'story',
  grammar: 'forge',
  words: 'words',
};
