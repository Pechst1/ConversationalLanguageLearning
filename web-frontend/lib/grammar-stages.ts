/**
 * WP-130 A — one vocabulary for a grammar unit's state, on every surface.
 *
 * The notebook (Le Cahier: the register, the map, the Relevé) and the level
 * (Le Dossier, the notebook's kicker) name a unit's state with the same three
 * words, counted by the same server function (`concept_life.progress_stage`):
 *
 *   introduced  the rule was read, nothing practised yet
 *   practising  met and practised, not yet held   («en route»)
 *   held        WP-L4's «Tenue» — the only state the level counts
 *
 * German has one word per state: «gefestigt» is «tenue» and nothing else (the
 * score's «solid» is «in der Übung sicher»). A practice score never names the
 * unit: «en route · solide à l’entraînement», never «solide» alone.
 *
 * The table mirrors `concept_life.STAGE_LABELS` (the backend test compares
 * them). Every language has the same keys and `{placeholders}`.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type GrammarStage = 'new' | 'introduced' | 'practising' | 'held';
export type VisibleStage = Exclude<GrammarStage, 'new'>;
export const VISIBLE_STAGES: VisibleStage[] = ['introduced', 'practising', 'held'];

export type StageCounts = Record<VisibleStage, number>;

/** One entry of the server's `held_missing` (`{code, not_before}`). */
export type MissingEvidence = { code?: unknown; not_before?: unknown; [key: string]: unknown };

export type GrammarStageCopy = {
  locale: string;
  /** [singular, plural] — French puts 0 and 1 in the singular. */
  stage: Record<VisibleStage, [string, string]>;
  not_met: string;
  line: string;
  practice_solid: string;
  practice_fragile: string;
  practice_score: string;
  missing: string;
  missing_free_use_first: string;
  missing_free_use_second: string;
  missing_free_use_second_dated: string;
  missing_spaced: string;
  missing_spaced_dated: string;
};

const EN: GrammarStageCopy = {
  locale: 'en-GB',
  stage: {
    introduced: ['introduced', 'introduced'],
    practising: ['practising', 'practising'],
    held: ['held', 'held'],
  },
  not_met: 'not met yet',
  line: 'Grammar: {parts}',
  practice_solid: 'solid in practice',
  practice_fragile: 'shaky in practice',
  practice_score: 'Practice',
  missing: 'Still needed: {items}',
  missing_free_use_first: 'one unaided use in a reply',
  missing_free_use_second: 'a second unaided use, on another day',
  missing_free_use_second_dated: 'a second unaided use, from {date}',
  missing_spaced: 'one successful review',
  missing_spaced_dated: 'one successful review, from {date}',
};

const DE: GrammarStageCopy = {
  locale: 'de-DE',
  stage: {
    introduced: ['eingeführt', 'eingeführt'],
    practising: ['in Übung', 'in Übung'],
    held: ['gefestigt', 'gefestigt'],
  },
  not_met: 'noch nicht kennengelernt',
  line: 'Grammatik: {parts}',
  practice_solid: 'in der Übung sicher',
  practice_fragile: 'in der Übung wackelig',
  practice_score: 'Übung',
  missing: 'Noch nötig: {items}',
  missing_free_use_first: 'eine freie Verwendung in einer Antwort',
  missing_free_use_second: 'eine zweite freie Verwendung an einem anderen Tag',
  missing_free_use_second_dated: 'eine zweite freie Verwendung ab dem {date}',
  missing_spaced: 'eine gelungene Wiederholung',
  missing_spaced_dated: 'eine gelungene Wiederholung ab dem {date}',
};

const FR: GrammarStageCopy = {
  locale: 'fr-FR',
  stage: {
    introduced: ['découverte', 'découvertes'],
    practising: ['en route', 'en route'],
    held: ['tenue', 'tenues'],
  },
  not_met: 'pas encore découverte',
  line: 'Grammaire : {parts}',
  practice_solid: 'solide à l’entraînement',
  practice_fragile: 'fragile à l’entraînement',
  practice_score: 'Entraînement',
  missing: 'Encore : {items}',
  missing_free_use_first: 'un emploi libre dans une réponse',
  missing_free_use_second: 'un 2ᵉ emploi libre, un autre jour',
  missing_free_use_second_dated: 'un 2ᵉ emploi libre à partir du {date}',
  missing_spaced: 'un rappel réussi',
  missing_spaced_dated: 'un rappel réussi à partir du {date}',
};

export const GRAMMAR_STAGE_COPY: Record<ControlLanguage, GrammarStageCopy> = { en: EN, de: DE, fr: FR };

export function grammarStageCopy(language: unknown): GrammarStageCopy {
  return GRAMMAR_STAGE_COPY[normalizeControlLanguage(language)];
}

function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

/** A unit's stage: the server's own word, else a conservative reading (never «held»). */
export function stageOf(item: { stage?: string | null; mastery?: number | null; state?: string | null } | null | undefined): GrammarStage {
  const stage = String(item?.stage || '');
  if (stage === 'introduced' || stage === 'practising' || stage === 'held' || stage === 'new') return stage;
  // An older payload has no stage: only the level can say «held», so never guess it.
  return Number(item?.mastery || 0) > 0 ? 'practising' : 'new';
}

/** «en route», «2 tenues» — the word for a stage (with the count when given). */
export function stageWord(stage: GrammarStage, language: unknown, count?: number): string {
  const copy = grammarStageCopy(language);
  if (stage === 'new') return copy.not_met;
  const [one, many] = copy.stage[stage];
  if (count === undefined) return one;
  const french = copy.locale.startsWith('fr');
  const word = (french ? count <= 1 : count === 1) ? one : many;
  return `${count} ${word}`;
}

/** The score's honest qualifier («solide à l’entraînement»), or null. Never for a held unit. */
export function practiceQualifier(state: string | null | undefined, stage: GrammarStage, language: unknown): string | null {
  if (stage === 'held' || stage === 'new') return null;
  const copy = grammarStageCopy(language);
  const s = String(state || '').toLowerCase();
  if (['gefestigt', 'gemeistert', 'solid', 'mastered', 'solide', 'acquis'].includes(s)) return copy.practice_solid;
  if (['ausbaufähig', 'ausbaufahig', 'fragile'].includes(s)) return copy.practice_fragile;
  return null;
}

/** «en route · solide à l’entraînement» — the stage, qualified by the practice score. */
export function stageLabel(item: { stage?: string | null; mastery?: number | null; state?: string | null }, language: unknown): string {
  const stage = stageOf(item);
  return [stageWord(stage, language), practiceQualifier(item.state, stage, language)].filter(Boolean).join(' · ');
}

/** Counts per stage over notebook items (the same function the level's counts use, server side). */
export function countStages(items: Array<{ stage?: string | null; mastery?: number | null }>): StageCounts {
  const counts: StageCounts = { introduced: 0, practising: 0, held: 0 };
  items.forEach((item) => {
    const stage = stageOf(item);
    if (stage !== 'new') counts[stage] += 1;
  });
  return counts;
}

/** «1 découverte · 6 en route · 0 tenue» — «introduced» only when there is one. */
export function stageCountsText(counts: Partial<StageCounts> | null | undefined, language: unknown): string {
  const n = (stage: VisibleStage) => Math.max(0, Math.round(Number(counts?.[stage] || 0)));
  return VISIBLE_STAGES.filter((stage) => stage !== 'introduced' || n(stage) > 0)
    .map((stage) => stageWord(stage, language, n(stage)))
    .join(' · ');
}

/** The level's grammar line: «Grammaire : 6 en route · 0 tenue». */
export function grammarLine(counts: Partial<StageCounts> | null | undefined, language: unknown): string {
  return fill(grammarStageCopy(language).line, { parts: stageCountsText(counts, language) });
}

/** The level's units (`coverage.units`) as stage counts; null when the level sent none. */
export function levelStageCounts(
  units: { held?: number | null; practising?: number | null; introduced?: number | null } | null | undefined,
): StageCounts | null {
  if (!units || typeof units.practising !== 'number') return null;
  return {
    introduced: Number(units.introduced || 0),
    practising: Number(units.practising || 0),
    held: Number(units.held || 0),
  };
}

function shortDay(iso: string, copy: GrammarStageCopy): string {
  const date = new Date(`${iso}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(copy.locale, { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

/** «Encore : un 2ᵉ emploi libre à partir du 12 oct. · un rappel réussi» — or null when nothing is missing. */
export function missingLine(
  missing: MissingEvidence[] | null | undefined,
  language: unknown,
  today: Date = new Date(),
): string | null {
  if (!missing || !missing.length) return null;
  const copy = grammarStageCopy(language);
  const todayIso = today.toISOString().slice(0, 10);
  const items = missing
    .map((entry) => {
      const notBefore = typeof entry.not_before === 'string' ? entry.not_before : '';
      const later = notBefore && notBefore > todayIso ? shortDay(notBefore, copy) : null;
      switch (String(entry.code || '')) {
        case 'free_use_first':
          return copy.missing_free_use_first;
        case 'free_use_second':
          return later ? fill(copy.missing_free_use_second_dated, { date: later }) : copy.missing_free_use_second;
        case 'spaced':
          return later ? fill(copy.missing_spaced_dated, { date: later }) : copy.missing_spaced;
        default:
          return null;
      }
    })
    .filter((item): item is string => Boolean(item));
  return items.length ? fill(copy.missing, { items: items.join(' · ') }) : null;
}
