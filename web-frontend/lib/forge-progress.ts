/**
 * WP-S6 — La Forge's one human progress, as data.
 *
 * The machine counters («Recognize · Word bank · 1/3», «0/20») are gone. A
 * séance shows two things: the rule's staircase — six steps drawn in the
 * rule's own shape, done steps in ink, the current one in the shape's colour,
 * the rest ghosts — and a quiet «n of N» for the séance. The recap reads each
 * rule's day from the server (`recap.forge.rules`, `app/services/atelier.py`).
 *
 * Pure: no React, so node tests read it directly.
 */

import {
  fillForge,
  forgeRungLabel,
  forgeStageLabel,
  type ForgeCopy,
} from './forge-copy';

export const FORGE_STEPS = 6;

/**
 * A rule's shape, from the four of the mark (`ui/Shapes.tsx`): the red
 * triangle for what verbs do (verbs, tenses, conditionals), the yellow square
 * for the words that fit a noun (articles, determiners, agreement, numbers,
 * comparison, adverbs), the blue circle for how a sentence is built (pronouns,
 * negation, connectors, relatives, prepositions, syntax). The ink square stays
 * «done» and is never a rule's own shape.
 */
export type RuleShape = 'circle' | 'square' | 'triangle';

const TRIANGLE = /verb|tense|temps|condition|subjonct|impérat|imperat|passé|futur|present|présent/i;
const SQUARE = /article|determin|déterm|agree|accord|number|nombre|compar|adverb|adject|gender|genre|partitive|partitif/i;

type ConceptLike = {
  category?: string | null;
  subskill?: string | null;
  name?: string | null;
} | null | undefined;

export function ruleShape(concept: ConceptLike): RuleShape {
  const category = String(concept?.category || '');
  const detail = `${concept?.subskill || ''} ${concept?.name || ''}`;
  if (TRIANGLE.test(category)) return 'triangle';
  if (SQUARE.test(category)) return 'square';
  if (category.trim()) return 'circle';
  if (TRIANGLE.test(detail)) return 'triangle';
  if (SQUARE.test(detail)) return 'square';
  return 'circle';
}

export type StairState = 'done' | 'current' | 'todo';

/** The six steps for a rule on rung `rung` (0-based): ink, colour, ghosts. */
export function staircase(rung: unknown): StairState[] {
  const at = clampRung(rung);
  return Array.from({ length: FORGE_STEPS }, (_, index) => (index < at ? 'done' : index === at ? 'current' : 'todo'));
}

export function clampRung(rung: unknown): number {
  const value = Math.floor(Number(rung));
  return Number.isFinite(value) ? Math.max(0, Math.min(FORGE_STEPS - 1, value)) : 0;
}

type ForgeViewLike = {
  length?: number | null;
  answered?: number | null;
  finished?: boolean | null;
  next?: { position?: number | null; length?: number | null } | null;
} | null | undefined;

/** The séance's quiet «n of N»: the item on screen, of the séance's length. */
export function seanceCount(forge: ForgeViewLike): { n: number; total: number } | null {
  if (!forge) return null;
  const total = Math.max(0, Math.floor(Number(forge.next?.length ?? forge.length) || 0));
  if (total < 1) return null;
  const answered = Math.max(0, Math.floor(Number(forge.answered) || 0));
  const position = Number(forge.next?.position);
  const current = forge.finished || !forge.next
    ? answered
    : Number.isFinite(position) ? position + 1 : answered + 1;
  return { n: Math.max(1, Math.min(total, current)), total };
}

export function seanceCountText(copy: ForgeCopy, forge: ForgeViewLike): string {
  const count = seanceCount(forge);
  return count ? fillForge(copy.count_of, count) : '';
}

/** «Step 3 of 6 · build» — one label, for the head and the recap. */
export function stepText(copy: ForgeCopy, rung: unknown, rungName: string | null | undefined): string {
  return fillForge(copy.step_of, { n: clampRung(rung) + 1, rung: forgeRungLabel(copy, rungName) });
}

export type SeenItem = { position: number; conceptId: number };

/**
 * Did the séance just move to another rule? True on the first item of a rule
 * that follows an item of a different one — never on the séance's first item.
 */
export function ruleChanged(previous: SeenItem | null | undefined, next: SeenItem | null | undefined): boolean {
  if (!previous || !next) return false;
  return next.position !== previous.position && next.conceptId !== previous.conceptId;
}

// ---------------------------------------------------------------------------
// The recap
// ---------------------------------------------------------------------------

export type RecapRuleIn = {
  concept_id: number;
  rung?: number;
  rung_name?: string;
  stage_before?: string | null;
  stage?: string | null;
  held_today?: boolean;
  tested_out?: boolean;
  next_due?: string | null;
  proof?: Array<{ fr?: string; fixed?: boolean }>;
};

export type RecapRuleRow = {
  conceptId: number;
  title: string;
  shape: RuleShape;
  rung: number;
  step: string;
  change: string;
  changed: boolean;
  due: string;
  proof: Array<{ fr: string; fixed: boolean }>;
};

const LOCALES: Record<string, string> = { en: 'en-GB', de: 'de-DE', fr: 'fr-FR' };

/** «Thu 26 Sept» in the chrome language; «today» when it is due today or earlier. */
export function dueText(copy: ForgeCopy, iso: string | null | undefined, language: string, now: Date = new Date()): string {
  if (!iso) return copy.recap_no_due;
  const due = new Date(iso);
  if (Number.isNaN(due.getTime())) return copy.recap_no_due;
  const endOfToday = new Date(now);
  endOfToday.setHours(23, 59, 59, 999);
  if (due.getTime() <= endOfToday.getTime()) return copy.recap_due_today;
  const date = due.toLocaleDateString(LOCALES[language] || 'en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
  return fillForge(copy.recap_next_due, { date });
}

/** What changed today: «introduced → proficient», «Held from today», «Still held». */
export function changeText(copy: ForgeCopy, rule: RecapRuleIn): { text: string; changed: boolean } {
  if (rule.held_today) {
    return { text: rule.tested_out ? copy.recap_tested_out : copy.recap_held_today, changed: true };
  }
  const after = String(rule.stage || '');
  const before = String(rule.stage_before || after);
  if (before && after && before !== after) {
    return {
      text: fillForge(copy.recap_change, { from: forgeStageLabel(copy, before), to: forgeStageLabel(copy, after) }),
      changed: true,
    };
  }
  return { text: fillForge(copy.recap_unchanged, { stage: forgeStageLabel(copy, after || before) }), changed: false };
}

type TitledConcept = { id: number; category?: string | null; subskill?: string | null; name?: string | null };

/** The recap's rows, one per rule the séance forged, in the séance's order. */
export function recapRuleRows(
  recap: { forge?: { rules?: RecapRuleIn[] } | null } | null | undefined,
  concepts: TitledConcept[],
  titleOf: (concept: TitledConcept) => string,
  copy: ForgeCopy,
  language: string,
  now: Date = new Date(),
): RecapRuleRow[] {
  const rules = Array.isArray(recap?.forge?.rules) ? recap!.forge!.rules! : [];
  return rules
    .filter((rule) => rule && Number.isFinite(Number(rule.concept_id)))
    .map((rule) => {
      const concept = concepts.find((item) => Number(item.id) === Number(rule.concept_id)) || null;
      const change = changeText(copy, rule);
      return {
        conceptId: Number(rule.concept_id),
        title: concept ? titleOf(concept) : '',
        shape: ruleShape(concept),
        rung: clampRung(rule.rung),
        step: stepText(copy, rule.rung, rule.rung_name),
        change: change.text,
        changed: change.changed,
        due: dueText(copy, rule.next_due, language, now),
        proof: (Array.isArray(rule.proof) ? rule.proof : [])
          .map((line) => ({ fr: String(line?.fr || '').trim(), fixed: Boolean(line?.fixed) }))
          .filter((line) => line.fr)
          .slice(0, 2),
      };
    })
    .filter((row) => row.title);
}

/**
 * WP-S6 bug 6: an item's cue in the learner's language when the payload
 * offers one (`prompt_l10n` / `instruction_l10n` from the item bank), else the
 * item's own string. Never mixes: the whole cue comes from one column.
 */
export function localizedCue(
  item: Record<string, any> | null | undefined,
  field: 'prompt' | 'instruction',
  language: string,
): string {
  const own = String(item?.[field] ?? '').trim();
  const table = item?.[`${field}_l10n`];
  if (table && typeof table === 'object') {
    const value = table[language];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return own;
}

/** Is the cue shown the item's own string (French content), or a translation? */
export function cueIsLocalized(item: Record<string, any> | null | undefined, field: 'prompt' | 'instruction', language: string): boolean {
  const table = item?.[`${field}_l10n`];
  return Boolean(table && typeof table === 'object' && typeof table[language] === 'string' && table[language].trim());
}
