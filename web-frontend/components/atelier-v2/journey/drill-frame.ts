/**
 * WP-103 T3 — a drill says what it is, and what it asks for.
 *
 * The owner's test: «Build the sentence. Some chips are not needed.» with no
 * idea *which* sentence, under a header still showing the day's reply
 * objective («Le Mistral · Ask Romy…»). Two rules come out of it, both pure so
 * the renderers and the node suite share them:
 *
 *   * **the goal line** — every drill shows what to produce (`goal_native`, in
 *     the learner's language: «Build: "A small white table is in the kitchen."»),
 *     or, when the server sent none, the scene line the item is cut from
 *     (`source_fr`). The goal is never printed twice: a line the headline or the
 *     instruction already carries is not repeated.
 *   * **the header** — the step header of a drill names the drill («Rappel ·
 *     Genre et nombre»). The day's objective belongs to the scene and the reply
 *     only.
 *
 * Read defensively: an older server sends neither field, and the drill then
 * renders exactly as it did.
 */

import type { ControlLanguage, PublicStep } from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';

export type DrillGoal = {
  /** `goal`: what to produce, in the learner's language. `source`: a French scene line. */
  kind: 'goal' | 'source';
  text: string;
};

type GoalPrompt = {
  goal_native?: unknown;
  source_fr?: unknown;
  instruction_native?: unknown;
  prompt_fr?: unknown;
};

function clean(value: unknown): string {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
}

/** Same words, whatever the case, the quotes, the spacing or the final stop. */
function fold(value: unknown): string {
  return clean(value)
    .replace(/[“”«»„"]/g, '')
    .replace(/[‘’ʼ]/g, "'")
    .replace(/\s+/g, ' ')
    .replace(/[.!?…:;,\s]+$/g, '')
    .trim()
    .toLowerCase();
}

/**
 * The line a drill states under its instruction, or `null` when there is none
 * to state (an older payload) or the screen already says it.
 */
export function drillGoalLine(prompt: GoalPrompt | null | undefined): DrillGoal | null {
  if (!prompt) return null;
  const shown = [fold(prompt.instruction_native), fold(prompt.prompt_fr)].filter(Boolean);
  const goal = clean(prompt.goal_native);
  if (goal) return shown.includes(fold(goal)) ? null : { kind: 'goal', text: goal };
  const source = clean(prompt.source_fr);
  if (source) return shown.includes(fold(source)) ? null : { kind: 'source', text: source };
  return null;
}

/** The kinds whose step header is the drill's name, not the day's objective. */
export const DRILL_KINDS = ['recall', 'rule', 'forge'] as const;
export type DrillKind = (typeof DRILL_KINDS)[number];

export function isDrillKind(kind: unknown): kind is DrillKind {
  return (DRILL_KINDS as readonly unknown[]).includes(kind);
}

/** The steps that carry the day's objective: the story and the reply. */
export function stepShowsDayObjective(kind: unknown): boolean {
  return !isDrillKind(kind) && kind !== 'read';
}

function join(parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => clean(part))
    .filter(Boolean)
    .join(' · ');
}

type DrillNames = Pick<JourneyCopy, 'drill_recall' | 'drill_rule' | 'drill_forge'>;

/**
 * «Rappel · Genre et nombre». The name follows the chrome language; the topic
 * is the unit's (or the word's) name in the same language — French at B1+,
 * else the learner's own, falling back to the French one.
 */
export function drillHeaderLabel(
  step: PublicStep | null | undefined,
  language: ControlLanguage,
  copy: DrillNames,
): string | null {
  if (!step || !isDrillKind(step.kind)) return null;
  const french = language === 'fr';
  const pick = (native: unknown, fr: unknown) =>
    french ? clean(fr) || clean(native) : clean(native) || clean(fr);
  if (step.kind === 'recall') {
    const target = step.prompt.target;
    return join([copy.drill_recall, pick(target?.label_native, target?.label_fr)]);
  }
  if (step.kind === 'rule') {
    return join([copy.drill_rule, pick(step.prompt.title_native, step.prompt.title_fr)]);
  }
  if (step.kind === 'forge') {
    return join([copy.drill_forge, pick(step.prompt.title_native, step.prompt.title_fr)]);
  }
  return null;
}

/**
 * The caption above a step: the drill's name on a drill, the place and the
 * day's objective on the scene and the reply, nothing on a page to read (which
 * carries its own kicker).
 */
export function stepHeaderLine(input: {
  step: PublicStep | null | undefined;
  language: ControlLanguage;
  copy: DrillNames;
  location?: string | null;
  objective?: string | null;
}): string {
  const { step } = input;
  if (step && isDrillKind(step.kind)) return drillHeaderLabel(step, input.language, input.copy) ?? '';
  if (step && step.kind === 'read') return '';
  if (step && step.kind === 'respond') return clean(input.location);
  return join([input.location, input.objective]);
}
