/**
 * WP-S6 — La Forge's one human progress, as data.
 *
 * The machine counters («Recognize · Word bank · 1/3», «0/20») are gone. A
 * séance shows two things: the rule's level and a quiet «n of N» for the
 * séance. The recap reads each rule's day from the server
 * (`recap.forge.rules`, `app/services/atelier.py`).
 *
 * Owner, 2026-10-18: the staircase of shapes read as decoration, not progress
 * («I don't know what the triangles indicate»). A rule's rung is now its level,
 * 1 to 6, drawn as a plain bar and named «Niveau 3»; a tap says what it means.
 *
 * Pure: no React, so node tests read it directly.
 */

import {
  fillForge,
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
 * «done» and is never a rule's own shape. The grammar map draws rules by it;
 * La Forge no longer does.
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

export function clampRung(rung: unknown): number {
  const value = Math.floor(Number(rung));
  return Number.isFinite(value) ? Math.max(0, Math.min(FORGE_STEPS - 1, value)) : 0;
}

/** The level's bar: one segment per level, lit up to the rule's own. */
export function levelSegments(rung: unknown): boolean[] {
  const at = clampRung(rung);
  return Array.from({ length: FORGE_STEPS }, (_, index) => index <= at);
}

/** «Niveau 3»: a rung (0–5) as the learner's level on the rule (1–6). */
export function levelText(copy: ForgeCopy, rung: unknown): string {
  return fillForge(copy.level, { n: clampRung(rung) + 1 });
}

type ForgeViewLike = {
  length?: number | null;
  answered?: number | null;
  finished?: boolean | null;
  next?: { position?: number | null; length?: number | null; item_id?: string | number | null } | null;
} | null | undefined;

/**
 * The séance's quiet «n of N»: the item on screen, of the séance's length.
 * Walk #90: once an item is answered the server already names the next one;
 * while the answered item is still on screen (its feedback, «Try again») the
 * count stays on it, so a retry no longer reads «2 of 12».
 */
export function seanceCount(
  forge: ForgeViewLike,
  onScreenItemId?: string | null,
): { n: number; total: number } | null {
  if (!forge) return null;
  const total = Math.max(0, Math.floor(Number(forge.next?.length ?? forge.length) || 0));
  if (total < 1) return null;
  const answered = Math.max(0, Math.floor(Number(forge.answered) || 0));
  const position = Number(forge.next?.position);
  const nextId = forge.next?.item_id;
  const behindNext = Boolean(onScreenItemId)
    && nextId != null && String(nextId) !== ''
    && String(nextId) !== String(onScreenItemId);
  const current = forge.finished || !forge.next
    ? answered
    : Number.isFinite(position) ? (behindNext ? position : position + 1) : answered + 1;
  return { n: Math.max(1, Math.min(total, current)), total };
}

export function seanceCountText(copy: ForgeCopy, forge: ForgeViewLike, onScreenItemId?: string | null): string {
  const count = seanceCount(forge, onScreenItemId);
  return count ? fillForge(copy.count_of, count) : '';
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
  rung: number;
  level: string;
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

type TitledConcept = { id: number; name?: string | null };

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
        rung: clampRung(rule.rung),
        level: levelText(copy, rule.rung),
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

const sameTitle = (a: unknown, b: unknown) => {
  const fold = (value: unknown) => String(value ?? '').trim().replace(/\s+/g, ' ').toLowerCase();
  return Boolean(fold(a)) && fold(a) === fold(b);
};

/**
 * Owner, 2026-10-18: the rule's name once per screen. La Forge names the rule
 * in its head, so a correction does not name it again: its card loses the
 * title when it is that rule, and its line loses «Règle : <title>.».
 */
export function correctionAnchor(label: unknown, ruleShown: string | null | undefined): string | undefined {
  const text = String(label ?? '').trim();
  if (!text || (ruleShown && sameTitle(text, ruleShown))) return undefined;
  return text;
}

export function withoutRuleReference(text: string, ruleShown: string | null | undefined): string {
  const value = String(text ?? '');
  const title = String(ruleShown ?? '').trim();
  if (!title) return value;
  const escaped = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
  return value.replace(new RegExp(`\\s*(?:Règle|Rule|Regel)\\s*:\\s*${escaped}\\s*\\.?`, 'giu'), '').trim();
}
