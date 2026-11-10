/**
 * WP-S7 — the grammar map, as data.
 *
 * The syllabus drawn with the mark's shapes (`ruleShape`: triangle for what
 * verbs do, square for what fits a noun, circle for how a sentence is built).
 * Each rule is one shape that fills as the rule lives:
 *
 *   ghost       not met yet        the solid shape in --av2-line (never an outline)
 *   introduced  met, practising    a tint of the shape's colour, no outline
 *   proficient  forge rung ≥ 4     half in the shape's colour, half tint
 *   held        «Tenue»            ink (ink = done)
 *
 * Pure: no React — node tests read it directly.
 */

import type { RuleCardData } from './rule-card';
import { ruleShape, type RuleShape } from './forge-progress';
import { fillMomentum, type MapStage } from './momentum-copy';

export const MAP_STAGES: MapStage[] = ['ghost', 'introduced', 'proficient', 'held'];

export type MapFill = 'ghost' | 'tint' | 'half' | 'ink';

export type GrammarMapRule = {
  concept_id: number;
  external_id?: string | null;
  title_fr: string;
  /** #561: the rule's title in the learner's chrome language (`concept_title`). */
  title_native?: string | null;
  name?: string | null;
  level?: string | null;
  category?: string | null;
  subskill?: string | null;
  stage: MapStage | string;
  rung: number;
  rung_name?: string | null;
  next_due?: string | null;
  due?: boolean;
  tested_out?: boolean;
  rule_card?: RuleCardData | null;
  coach?: { id: string; name?: string | null } | null;
};

/** What a payload carries to name a rule: the map, the Cahier's notebook rows, Éclair's pairs. */
export type RuleTitleSource = {
  title_fr?: string | null;
  /** `concept_title(concept, chrome language)`, the rule card's title (#561). */
  title_native?: string | null;
  display_title?: string | null;
  name?: string | null;
};

/**
 * What the Cahier calls a rule: the title in the learner's chrome language, the same
 * one the rule card shows (#561); the French title only when the server sent none.
 * `lang` is the language the text is in, for the element's `lang` attribute.
 *
 * The one reader of a rule's title on the Cahier's and Éclair's screens: the guard in
 * components/cahiers/cahier-rule-title.test.js fails on a component that reads
 * `title_fr` itself.
 */
export function ruleTitle(rule: RuleTitleSource, language: string): { text: string; lang: string } {
  const french = String(rule.title_fr || '').trim();
  const native = String(rule.title_native || '').trim();
  if (native) return { text: native, lang: native === french ? 'fr' : language };
  if (french) return { text: french, lang: 'fr' };
  return { text: String(rule.display_title || rule.name || '').trim(), lang: language };
}

/** Éclair's «{a} or {b}», each rule named by `ruleTitle`; `lang` is shared when both titles are. */
export function eclairPairLabel(
  rules: ReadonlyArray<RuleTitleSource | null | undefined> | null | undefined,
  template: string,
  language: string,
): { text: string; lang: string } {
  const [a, b] = [rules?.[0], rules?.[1]].map((rule) => (rule ? ruleTitle(rule, language) : { text: '', lang: language }));
  return { text: fillMomentum(template, { a: a.text, b: b.text }), lang: a.lang === b.lang ? a.lang : language };
}

export type GrammarMapBand = { band: string; rules: GrammarMapRule[] };

export type EclairPair = {
  pair: string;
  concept_ids: [number, number] | number[];
  rules: Array<{ concept_id: number; title_fr: string; title_native?: string | null; category?: string | null; subskill?: string | null; name?: string | null }>;
  best: number;
  plays: number;
};

export type GrammarMapFeatures = { combo?: boolean; eclair?: boolean; grammar_map?: boolean; mastery_rewards?: boolean };

export type GrammarMapPayload = {
  catalog?: string;
  bands: GrammarMapBand[];
  counts?: Partial<Record<MapStage, number>>;
  total?: number;
  eclair?: { unlocked: boolean; pairs: EclairPair[] } | null;
  features?: GrammarMapFeatures | null;
};

/** A stage the map knows; anything else draws as a ghost. */
export function mapStageOf(rule: Pick<GrammarMapRule, 'stage'> | null | undefined): MapStage {
  const stage = String(rule?.stage || '') as MapStage;
  return MAP_STAGES.includes(stage) ? stage : 'ghost';
}

const FILL: Record<MapStage, MapFill> = { ghost: 'ghost', introduced: 'tint', proficient: 'half', held: 'ink' };

export function mapFill(stage: MapStage): MapFill {
  return FILL[stage] ?? 'ghost';
}

export function mapRuleShape(rule: Pick<GrammarMapRule, 'category' | 'subskill' | 'name'>): RuleShape {
  return ruleShape({ category: rule.category, subskill: rule.subskill, name: rule.name });
}

/** Counts per stage, from the payload's own counts or the rules. */
export function mapCounts(payload: GrammarMapPayload | null | undefined): Record<MapStage, number> {
  const out: Record<MapStage, number> = { ghost: 0, introduced: 0, proficient: 0, held: 0 };
  for (const band of payload?.bands || []) {
    for (const rule of band.rules || []) out[mapStageOf(rule)] += 1;
  }
  return out;
}

/** The bands that have rules, in the payload's (syllabus) order. */
export function mapBands(payload: GrammarMapPayload | null | undefined): GrammarMapBand[] {
  return (payload?.bands || []).filter((band) => Array.isArray(band.rules) && band.rules.length > 0);
}

/**
 * The bands the map opens on: every band up to the furthest one the learner
 * has met a rule in, plus the next — the rest wait behind «All levels».
 */
export function visibleBands(bands: GrammarMapBand[], expanded: boolean): GrammarMapBand[] {
  if (expanded) return bands;
  let furthest = -1;
  bands.forEach((band, index) => {
    if (band.rules.some((rule) => mapStageOf(rule) !== 'ghost')) furthest = index;
  });
  return bands.slice(0, Math.max(1, furthest + 2));
}

export function findMapRule(payload: GrammarMapPayload | null | undefined, conceptId: number | null | undefined): GrammarMapRule | null {
  if (conceptId == null) return null;
  for (const band of payload?.bands || []) {
    const hit = (band.rules || []).find((rule) => Number(rule.concept_id) === Number(conceptId));
    if (hit) return hit;
  }
  return null;
}

/** Is the map on? The owner's switch; on unless the server says false. */
export function grammarMapEnabled(payload: GrammarMapPayload | null | undefined): boolean {
  return payload?.features?.grammar_map !== false;
}

export function eclairPairs(payload: GrammarMapPayload | null | undefined): EclairPair[] {
  if (payload?.features?.eclair === false) return [];
  return payload?.eclair?.unlocked ? payload.eclair.pairs || [] : [];
}

export function eclairHref(pair: string): string {
  return `/eclair?pair=${encodeURIComponent(pair)}`;
}

/** The forge's own door for one rule (the Cahier's CTA, WP-S4 seats it as today's rule). */
export function forgeHref(conceptId: number): string {
  return `/atelier?mode=practice&concept=${encodeURIComponent(String(conceptId))}`;
}
