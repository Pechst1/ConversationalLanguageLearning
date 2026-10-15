/**
 * #143 — the day's progress has one source of truth: the server's plan
 * (`TodayEnvelope.session`: ordered steps, each done / next / todo).
 *
 * Before this file, four things each kept their own idea of «where is the
 * learner»: the page's view state, the URL query (`?mode=forge&from=day`), the
 * device's «words done» tick (`continuePlan`) and each screen's own hand-on
 * (scene end card, La Forge recap, word review). A path that ended a step
 * updated some of them, so Home said «Done for today» after «Stop here»
 * (#153), the scene's end card had no next step after a stop, and the day's
 * order was written three ways (#152).
 *
 * Rule from here on: a screen that needs to know «is the day done», «what is
 * next» or «where does this button go» asks THIS module, with the plan it was
 * given. It never counts steps itself, never reads a device tick when a plan
 * exists, and never builds a step's address by hand.
 *
 * Pure: no React, no transport. Tested by `day-plan.test.js`, which walks every
 * step's exit path.
 */

import { daySessionCopy, sessionStep } from '@/lib/day-session';
import type { ControlLanguage, DaySession, DaySessionStepKind } from '@/types/daily-journey';

/** The steps a learner works through; «finish» is the seal, not work. */
export type DayWorkKind = Exclude<DaySessionStepKind, 'finish'>;

/**
 * How a step was left.
 *  - `finished`: its own completion screen (episode end, deck empty, La Forge recap).
 *  - `stopped`: «Stop here» / Finish early.
 *  - `recap_closed`: the recap's close button, after a finish.
 *  - `back`: the back arrow / X, with the step unfinished.
 */
export type DayExitHow = 'finished' | 'stopped' | 'recap_closed' | 'back';

export type DayHandOn = {
  kind: DaySessionStepKind;
  label: string;
  meta: string;
  href: string;
};

export type DayAfterExit = {
  /** Steps that count as done once this exit has been applied (the plan may predate it). */
  done: DayWorkKind[];
  /** The first step still open, as a button; the seal when none is. */
  next: DayHandOn;
  /** Every working step is done. The only value any screen may call «the day is done». */
  dayDone: boolean;
};

export const WORK_STEPS: readonly DayWorkKind[] = ['scene', 'words', 'grammar'];

/**
 * Does leaving `step` this way finish it? The server marks the scene done on any
 * terminal status, so a stopped scene is done; the words and the grammar are
 * done only when the learner got to their end.
 */
export function exitCompletes(step: DayWorkKind, how: DayExitHow): boolean {
  if (how === 'back') return false;
  if (step === 'scene') return true;
  return how === 'finished' || how === 'recap_closed';
}

/** The plan's own view of the day, before any exit. */
export function dayState(plan: DaySession | null | undefined): {
  done: boolean;
  open: DayWorkKind[];
  next: DaySessionStepKind | null;
} {
  if (!plan) return { done: false, open: [], next: null };
  const open = WORK_STEPS.filter((kind) => {
    const step = sessionStep(plan, kind);
    return step ? step.state !== 'done' : false;
  });
  return { done: open.length === 0, open, next: plan.next_kind };
}

/**
 * The hero says «the day is done» only when no working step is open. The
 * story's own end (a completed or stopped scene) never decides it.
 */
export function dayIsDone(plan: DaySession | null | undefined): boolean {
  return plan ? dayState(plan).done : false;
}

/**
 * Where the day goes after `step` was left `how`. The plan read before the exit
 * is stale about that one step, so the exit is applied to it here; every other
 * step is exactly what the server said.
 */
export function afterExit(
  plan: DaySession | null | undefined,
  step: DayWorkKind,
  how: DayExitHow,
  language: ControlLanguage,
): DayAfterExit | null {
  if (!plan) return null;
  const copy = daySessionCopy(language);
  const done = WORK_STEPS.filter((kind) => {
    if (kind === step && exitCompletes(step, how)) return true;
    return sessionStep(plan, kind)?.state === 'done';
  });
  for (const kind of WORK_STEPS) {
    if (done.includes(kind)) continue;
    const planned = sessionStep(plan, kind);
    // The scene has no address: Home's own button starts it.
    if (!planned || !planned.href) continue;
    return {
      done,
      dayDone: false,
      next: {
        kind,
        label: kind === 'words' ? copy.next_words(Number(planned.count || 0)) : copy.next_grammar,
        meta: planned.minutes > 0 ? copy.minutes(planned.minutes) : '',
        href: planned.href,
      },
    };
  }
  const finish = sessionStep(plan, 'finish');
  return {
    done,
    dayDone: WORK_STEPS.every((kind) => done.includes(kind)),
    next: { kind: 'finish', label: copy.next_finish, meta: '', href: finish?.href || '/fertig' },
  };
}

/** The scene's ending, finished or stopped: where the day goes next. */
export function handOnAfterScene(
  plan: DaySession | null | undefined,
  language: ControlLanguage,
  how: DayExitHow = 'finished',
): DayHandOn | null {
  return afterExit(plan, 'scene', how, language)?.next ?? null;
}

/** La Forge's recap: the words if they are still open, else "Fertig". */
export function handOnAfterGrammar(
  plan: DaySession | null | undefined,
  language: ControlLanguage,
  how: DayExitHow = 'finished',
): DayHandOn | null {
  return afterExit(plan, 'grammar', how, language)?.next ?? null;
}

/** The word deck's end: the grammar if it is still open, else "Fertig". */
export function handOnAfterWords(
  plan: DaySession | null | undefined,
  language: ControlLanguage,
  how: DayExitHow = 'finished',
): DayHandOn | null {
  return afterExit(plan, 'words', how, language)?.next ?? null;
}
