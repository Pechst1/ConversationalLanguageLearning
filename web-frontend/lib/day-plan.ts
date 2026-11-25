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

import { dayMarkState, type DayMarkState } from '@/components/atelier-v2/journey/day-mark';
import { dayStepOf as dayWorkOfPlayerStep, WORK_STEPS, type DayWorkKind } from '@/lib/day-order';
import { daySessionCopy, sessionMarkState, sessionRows, sessionStep, withScenePlayed } from '@/lib/day-session';
import type { ControlLanguage, DaySession, DaySessionStepKind, JourneySnapshot } from '@/types/daily-journey';

/** The day's order lives in `day-order.ts` (one place, checked against the server's). */
export { WORK_STEPS, type DayWorkKind };

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
 * Where a screen of the plan's step `kind` stands in the day: that step's number
 * and the plan's count of steps — the rows Home lists (Szene, Grammatik, Wörter,
 * Fertig) and the shapes of its mark. Every screen of the scene is the plan's
 * scene step, whatever the scene holds (a page, drills, a rule card, a drill
 * asked once more, an ending read full-screen), so its header can neither grow,
 * skip nor read «N of N» while La Forge and the words are still ahead. `null`
 * without a plan, or when the plan has no such step: the caller keeps its own count.
 */
export function dayStepOf(
  plan: DaySession | null | undefined,
  kind: DaySessionStepKind,
): { position: number; total: number } | null {
  const steps = plan?.steps ?? [];
  const index = steps.findIndex((step) => step.kind === kind);
  return index < 0 ? null : { position: index + 1, total: steps.length };
}

/**
 * The plan step a screen of the journey player counts as, for its number in the
 * day. The player deals more than the story: the day's rule card, the drills on
 * today's rule and a folded La Forge are the plan's grammar step, which Home lists
 * second and the header names («Regel», «La Forge»); counting them as the scene
 * read «Regel · Schritt 1 von 4» while Home called the grammar step 2 (walk of
 * 25 Nov). Everything else the player deals is the scene's: its pages and
 * replies, a rule to review, the learner's own slip, and a word drill (a warm-up
 * of the scene; the plan's words step is the day's deck, which the player never
 * deals). The same mapping names the screen (`day-order.ts`, `stepBlockName`),
 * so the header's name and number can no longer disagree.
 */
export function planStepOfScreen(
  step: { kind?: unknown; prompt?: unknown } | null | undefined,
): 'scene' | 'grammar' {
  return dayWorkOfPlayerStep(step) === 'grammar' ? 'grammar' : 'scene';
}

/**
 * The day as Home's programme lists it (Szene, Grammatik, 15 Wörter, Fertig): the
 * plan's steps, one label each, in the plan's order. Any other screen that lists
 * the day (the onboarding's «Dein erster Tag») takes this list, so its count is
 * the one the session header and the mark count. `null` without a plan: the
 * caller keeps its own list (an older server).
 */
export function dayProgramme(plan: DaySession | null | undefined, language: ControlLanguage): string[] | null {
  if (!plan?.steps?.length) return null;
  return sessionRows(plan, language).map((row) => row.label);
}

/**
 * The logo's four shapes for the day, in Home's head and the session's alike: the
 * plan's four steps (a scene played counts as its step, `withScenePlayed`). Only
 * without a plan (an older server) does the journey's own mark stand in — the one
 * whose ink square («Tag geschafft») fills at the scene's ending.
 */
export function dayMarkOf(
  plan: DaySession | null | undefined,
  journey: JourneySnapshot | null | undefined,
  language: ControlLanguage,
): DayMarkState {
  if (!plan) return dayMarkState(journey ?? null, language);
  return sessionMarkState(withScenePlayed(plan, journey) ?? plan, language);
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

/**
 * #175 — the rule check's own address. It carries `from=day` when it was opened
 * from the day's La Forge, so its end screen asks the plan where to go instead
 * of choosing an exit of its own.
 */
export function ruleCheckPath(sessionId: string, fromDay: boolean): string {
  return `/atelier?testout=${sessionId}${fromDay ? '&from=day' : ''}`;
}

/** Whether the rule check at this address belongs to the day (`?testout=…&from=day`). */
export function ruleCheckIsFromDay(query: { testout?: unknown; from?: unknown } | null | undefined): boolean {
  return Boolean(query?.testout) && String(query?.from || '') === 'day';
}

/**
 * #175 — the rule check («Épreuve de la règle») started from the day's grammar
 * step ends here, not on a screen of its own. Passed: the rule is proven, so the
 * grammar step is done and the plan's next step follows. Not passed: the check
 * leaves the grammar step as it found it, so the plan's own state decides — a
 * grammar step still open stays the next one (La Forge takes over now); one the
 * day already finished (the optional check on its end sheet) hands on to the
 * words, then «Fertig» (#997: a failed extra check reopened a second séance on a
 * forged rule while Home said «Grammatik — erledigt»). Both go through
 * `afterExit`, so no exit picks a step without reading its state. `null` without
 * a plan: the caller keeps its own exit.
 */
export function handOnAfterRuleCheck(
  plan: DaySession | null | undefined,
  passed: boolean,
  language: ControlLanguage,
): DayHandOn | null {
  return afterExit(plan, 'grammar', passed ? 'finished' : 'back', language)?.next ?? null;
}

/**
 * The rule check's exit when the day started it (`from=day`): the plan's next step, or,
 * while the plan is not read yet (a reloaded result page), «Fertig», which says what is
 * left. Never the Cahier: a quick tap before the plan landed lost the day (review of #221).
 */
export function ruleCheckExitFromDay(
  plan: DaySession | null | undefined,
  passed: boolean,
  language: ControlLanguage,
): DayHandOn {
  return handOnAfterRuleCheck(plan, passed, language)
    ?? { kind: 'finish', label: daySessionCopy(language).next_finish, meta: '', href: '/fertig' };
}

/** The scene's ending, finished or stopped: where the day goes next. */
export function handOnAfterScene(
  plan: DaySession | null | undefined,
  language: ControlLanguage,
  how: DayExitHow = 'finished',
): DayHandOn | null {
  return afterExit(plan, 'scene', how, language)?.next ?? null;
}

/** La Forge's recap: the plan's next open step (the words, in the day's order), else "Fertig". */
export function handOnAfterGrammar(
  plan: DaySession | null | undefined,
  language: ControlLanguage,
  how: DayExitHow = 'finished',
): DayHandOn | null {
  return afterExit(plan, 'grammar', how, language)?.next ?? null;
}

/** The word deck's end: any step still open (La Forge, if skipped), else "Fertig". */
export function handOnAfterWords(
  plan: DaySession | null | undefined,
  language: ControlLanguage,
  how: DayExitHow = 'finished',
): DayHandOn | null {
  return afterExit(plan, 'words', how, language)?.next ?? null;
}
