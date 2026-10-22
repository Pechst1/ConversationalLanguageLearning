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

export type SlipSegment = { text: string; slip: boolean };

const WORD_CHAR = /[0-9A-Za-zÀ-ÖØ-öø-ÿŒœ'’-]/;

/**
 * #278: a repair card prints the learner's own sentence with the wrong part marked.
 * `sentence` cut into the text around `slip` and `slip` itself (whole words, any
 * case, the first place it stands), or `null` when the slip is not in the sentence:
 * the card then prints the sentence plain rather than marking a guess.
 */
export function slipSegments(sentence: unknown, slip: unknown): SlipSegment[] | null {
  const line = clean(sentence);
  const wrong = clean(slip);
  if (!line || !wrong) return null;
  const folded = line.toLowerCase();
  const target = wrong.toLowerCase();
  // Same length as the line: lower-casing French keeps every offset.
  if (folded.length !== line.length) return null;
  let at = folded.indexOf(target);
  while (at >= 0) {
    const end = at + target.length;
    if (!WORD_CHAR.test(line[at - 1] ?? '') && !WORD_CHAR.test(line[end] ?? '')) {
      const parts: SlipSegment[] = [];
      if (at > 0) parts.push({ text: line.slice(0, at), slip: false });
      parts.push({ text: line.slice(at, end), slip: true });
      if (end < line.length) parts.push({ text: line.slice(end), slip: false });
      return parts;
    }
    at = folded.indexOf(target, at + 1);
  }
  return null;
}

/**
 * WP-121 A.4: «vu au marché d'Aligre, semaine 41» — the small context line under a
 * recall prompt whose word was kept in a Papier (`prompt.met.place_label_fr`), or null.
 */
export function recallMetLine(prompt: { met?: { place_label_fr?: string | null } | null } | null | undefined): string | null {
  return clean(prompt?.met?.place_label_fr) || null;
}

/** The kinds whose step header is the drill's name, not the day's objective. */
export const DRILL_KINDS = ['recall', 'rule', 'forge'] as const;
export type DrillKind = (typeof DRILL_KINDS)[number];

export function isDrillKind(kind: unknown): kind is DrillKind {
  return (DRILL_KINDS as readonly unknown[]).includes(kind);
}

/** The steps that carry the day's objective: the story and the reply. */
export function stepShowsDayObjective(kind: unknown): boolean {
  return !isDrillKind(kind) && kind !== 'read' && kind !== 'desk';
}

function join(parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => clean(part))
    .filter(Boolean)
    .join(' · ');
}

type DrillNames = Pick<JourneyCopy, 'drill_recall' | 'drill_rule' | 'drill_forge'> &
  Partial<Pick<JourneyCopy, 'drill_warmup' | 'drill_retry'>>;

/** The steps that are the day's story: once one has come, a recall reviews it. */
const STORY_KINDS: readonly unknown[] = ['scene', 'read', 'respond', 'resolution'];

/**
 * Walk 2026-10-12 (#76): a recall before the day's first story step is not a
 * review. On day 1 its words have never been shown («Wiederholung · vendre»
 * right after sign-up); on later days it pre-teaches the scene's words. It is
 * named for what it is: the words before the scene.
 */
export function isBeforeStory(
  steps: ReadonlyArray<{ id?: unknown; kind?: unknown }> | null | undefined,
  stepId: unknown,
): boolean {
  if (!steps || stepId == null) return false;
  for (const step of steps) {
    if (step.id === stepId) return true;
    if (STORY_KINDS.includes(step.kind)) return false;
  }
  return false;
}

type AnswerCards = { options?: Array<{ text_fr?: unknown }> | null };

/**
 * WP-137 C-1: a header topic that an answer card carries, or that carries one,
 * names the answer. Folded the same way the goal line is.
 */
export function revealsAnswer(topic: unknown, prompt: AnswerCards | null | undefined): boolean {
  const name = fold(topic);
  if (!name) return false;
  // Whole words only, and never a bare article or chip («la», «une»).
  const within = (outer: string, inner: string) =>
    inner.length >= 4 && ` ${outer} `.includes(` ${inner} `);
  return (prompt?.options ?? []).some((option) => {
    const card = fold(option?.text_fr);
    return Boolean(card) && (card === name || within(name, card) || within(card, name));
  });
}

/**
 * «Rappel · Genre et nombre». The name follows the chrome language; the topic
 * is the unit's (or the word's) name in the same language — French at B1+,
 * else the learner's own, falling back to the French one.
 */
export function drillHeaderLabel(
  step: PublicStep | null | undefined,
  language: ControlLanguage,
  copy: DrillNames,
  beforeStory = false,
): string | null {
  if (!step || !isDrillKind(step.kind)) return null;
  const french = language === 'fr';
  const pick = (native: unknown, fr: unknown) =>
    french ? clean(fr) || clean(native) : clean(native) || clean(fr);
  if (step.kind === 'recall') {
    // WP-137 C-1: «Wiederholung · verkaufen» above «vendre — Was bedeutet
    // das?» gave the answer away. A word's label is its gloss and an error's
    // is its correction, so only a grammar unit's title is named — and not
    // even that when the item's own answer cards carry it.
    const target = step.prompt.target;
    // Owner 2026-10-17: a drill missed earlier in the set, asked once more.
    const retry = (step.prompt as { retry?: boolean | null }).retry === true;
    const name = (retry && copy.drill_retry) || (beforeStory && copy.drill_warmup) || copy.drill_recall;
    if (target?.kind !== 'grammar') return join([name]);
    const topic = pick(target.label_native, target.label_fr);
    return join([name, revealsAnswer(topic, step.prompt) ? null : topic]);
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
  /** The day's steps in order, to tell a warm-up from a review (#76). */
  steps?: ReadonlyArray<{ id?: unknown; kind?: unknown }> | null;
}): string {
  const { step } = input;
  if (step && isDrillKind(step.kind)) {
    const before = isBeforeStory(input.steps, (step as { id?: unknown }).id);
    return drillHeaderLabel(step, input.language, input.copy, before) ?? '';
  }
  if (step && (step.kind === 'read' || step.kind === 'desk')) return '';
  if (step && step.kind === 'respond') return clean(input.location);
  return join([input.location, input.objective]);
}
