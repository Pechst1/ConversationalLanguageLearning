/**
 * WP-D1 / WP-D3 — the mark is the day's plan.
 *
 * The logo's four shapes are the day's four parts, and they fill in as the
 * learner goes. This file is the one step → shape mapping both the mark
 * (Home, the session head) and the step tokens (`StepProgress`) read:
 *
 *   scene       blue circle     («Scène»)
 *   recall      yellow square   («Mots»)
 *   respond     red triangle    («Réponse»)
 *   resolution  ink square      («Bouclé» — ink is done, the day's close)
 *
 * Pure: no React, no styling, no transport. It sits beside `journey-state.ts`
 * rather than inside it so the renderers and the node tests share it without
 * touching the controller's state machine.
 */

import type { JourneySnapshot, PublicStep, StepKind } from '@/types/daily-journey';

import type { ShapeKind } from '@/components/atelier-v2/ui/Shapes';

export type DayMarkGroup = StepKind;

/**
 * `done` — every step of the group is resolved; `active` — the learner is in
 * it; `todo` — still ahead; `absent` — today's shape deals none (a «jour
 * court» has no recall). `absent` draws like `todo`, a ghost, never an outline.
 */
export type DayMarkGroupState = 'done' | 'active' | 'todo' | 'absent';

export type DayMarkState = {
  groups: Record<DayMarkGroup, DayMarkGroupState>;
  /** Groups done. */
  done: number;
  /** Groups today's plan actually has (3 on a «jour court», else 4). */
  total: number;
  /** «Aujourd'hui : 2 sur 4 — scène vue, mots revus, réponse en cours, fin à venir» */
  label: string;
};

/** The order the mark and the label row read in. */
export const DAY_MARK_GROUPS: readonly DayMarkGroup[] = ['scene', 'recall', 'respond', 'resolution'];

/** The step → shape mapping (WP-D1, reused by WP-D3's tokens). */
export const STEP_SHAPE: Record<DayMarkGroup, ShapeKind> = {
  scene: 'story',
  recall: 'reward',
  respond: 'action',
  resolution: 'done',
};

/** The word paired with each shape in Home's label row. */
export const DAY_MARK_WORD: Record<DayMarkGroup, string> = {
  scene: 'Scène',
  recall: 'Mots',
  respond: 'Réponse',
  resolution: 'Bouclé',
};

const STATE_PHRASE: Record<DayMarkGroup, Record<'done' | 'active' | 'todo', string>> = {
  scene: { done: 'scène vue', active: 'scène en cours', todo: 'scène à venir' },
  recall: { done: 'mots revus', active: 'mots en cours', todo: 'mots à venir' },
  respond: { done: 'réponse donnée', active: 'réponse en cours', todo: 'réponse à venir' },
  resolution: { done: 'journée bouclée', active: 'fin en cours', todo: 'fin à venir' },
};

const RESOLVED = new Set(['completed', 'skipped']);

function groupState(
  steps: PublicStep[],
  currentStepId: string | null,
  endedEarly: boolean,
): DayMarkGroupState {
  if (steps.length === 0) return 'absent';
  const resolved = steps.every((step) => RESOLVED.has(step.status));
  // An early end marks every unreached step `skipped`. That is not the
  // learner having done it: a group nothing in which was completed stays a
  // ghost, so a day stopped after the words never reads «Bouclé».
  if (resolved && (!endedEarly || steps.some((step) => step.status === 'completed'))) {
    return 'done';
  }
  if (steps.some((step) => step.id === currentStepId || step.status === 'active')) {
    return 'active';
  }
  return 'todo';
}

/** «Aujourd'hui : 2 sur 4 — …». Never colour alone: every state is a word. */
export function dayMarkLabel(groups: Record<DayMarkGroup, DayMarkGroupState>): string {
  const present = DAY_MARK_GROUPS.filter((group) => groups[group] !== 'absent');
  const done = present.filter((group) => groups[group] === 'done').length;
  const parts = present.map((group) => STATE_PHRASE[group][groups[group] as 'done' | 'active' | 'todo']);
  return `Aujourd’hui : ${done} sur ${present.length} — ${parts.join(', ')}`;
}

/**
 * Each group's state for today's journey.
 *
 * No journey yet (the day is offered, not started) is four parts still ahead:
 * the shape is unknown, so nothing is `absent`. A day shape with no recall
 * steps («jour court») marks the recall group `absent`.
 */
export function dayMarkState(journey: JourneySnapshot | null | undefined): DayMarkState {
  const groups = {} as Record<DayMarkGroup, DayMarkGroupState>;
  if (!journey || journey.steps.length === 0) {
    for (const group of DAY_MARK_GROUPS) groups[group] = 'todo';
  } else {
    const endedEarly = journey.status === 'ended_early';
    for (const group of DAY_MARK_GROUPS) {
      groups[group] = groupState(
        journey.steps.filter((step) => step.kind === group),
        journey.current_step_id,
        endedEarly,
      );
    }
  }
  const present = DAY_MARK_GROUPS.filter((group) => groups[group] !== 'absent');
  return {
    groups,
    done: present.filter((group) => groups[group] === 'done').length,
    total: present.length,
    label: dayMarkLabel(groups),
  };
}
