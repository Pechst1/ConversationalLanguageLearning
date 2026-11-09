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

/**
 * Which step of the day a step of the journey player belongs to (#469).
 *
 * The player deals its own kinds (`rule`, `recall`, `respond` …); the day is
 * `WORK_STEPS`. A screen that names itself, the first-time sticker and the
 * header's part, takes the name from the day step the player's step belongs to,
 * never from its kind: a `recall` is «the words» only when its target is a word.
 * A drill on a rule (its target is grammar) is the rule in use, and the rule
 * card itself is grammar. Before this, `recall` said «Die Wörter» on the first
 * grammar drill and the header said «Szene» over the rule card, because both
 * were written for the day as it was before #463 reordered it.
 *
 * `null` for something that is not a step of the player.
 */
export function dayStepOf(step: { kind?: unknown; prompt?: unknown } | null | undefined): DayWorkKind | null {
  switch (step?.kind) {
    case 'scene':
    case 'respond':
    case 'resolution':
    case 'read':
    case 'desk':
      return 'scene';
    case 'rule':
    case 'forge':
      return 'grammar';
    case 'recall':
      return (step.prompt as { target?: { kind?: unknown } | null } | null | undefined)?.target?.kind === 'grammar'
        ? 'grammar'
        : 'words';
    default:
      return null;
  }
}
