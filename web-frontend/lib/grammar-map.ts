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
import type { MapStage } from './momentum-copy';

export const MAP_STAGES: MapStage[] = ['ghost', 'introduced', 'proficient', 'held'];

export type MapFill = 'ghost' | 'tint' | 'half' | 'ink';

export type GrammarMapRule = {
  concept_id: number;
  external_id?: string | null;
  title_fr: string;
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

export type GrammarMapBand = { band: string; rules: GrammarMapRule[] };

export type EclairPair = {
  pair: string;
  concept_ids: [number, number] | number[];
  rules: Array<{ concept_id: number; title_fr: string; category?: string | null; subskill?: string | null; name?: string | null }>;
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
