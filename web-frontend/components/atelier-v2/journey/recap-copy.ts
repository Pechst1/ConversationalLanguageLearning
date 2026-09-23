/**
 * WP-79 — the end-of-day recap's own words.
 *
 * Two kinds, kept apart on purpose (WP-82, one language rule):
 *   * `RECAP_CHROME` — labels beside French rows (Série · Mots · Scène, «La
 *     suite demain», the mood line). French on every control language.
 *   * `recapStatusCopy(language)` — what is *said to* the learner about their
 *     day (a «jour de relâche» spent, what moved the level). Their language.
 *
 * Budget: the chrome on the recap stays under 15 words.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export const RECAP_CHROME = {
  streak_label: 'Série',
  streak_value: '{n} jours',
  streak_value_one: '1 jour',
  /** WP-D4: the one primary action on a completed day. */
  keep_seal: 'Ranger le sceau',
  words_label: 'Mots',
  scene_label: 'Scène',
  steps_value: '{n} étapes',
  step_value: '1 étape',
  teaser_label: 'La suite demain',
  level_label: 'Niveau',
  mood_warmer: '{name} vous sourit',
  mood_colder: '{name} vous en veut un peu',
  /** WP-L6: the quiet, optional reviews-only block after the Seal. */
  encore: 'Encore 5 minutes',
} as const;

/**
 * WP-L6 «Encore 5 minutes»: the word drill, reviews only — no new words, a
 * five-minute deck. It never touches the story, and the streak is marked at
 * most once per local day (`record_practice_day`), so it cannot count twice.
 */
export const ENCORE_HREF = '/vocabulary/review?encore=1';

type StatusKey = 'freeze_used' | 'level_evidence' | 'level_evidence_words' | 'level_evidence_rules';

const STATUS: Record<ControlLanguage, Record<StatusKey, string>> = {
  en: {
    freeze_used: 'A day off kept your streak.',
    level_evidence: '{w} words and {g} rules mastered.',
    level_evidence_words: '{w} words mastered.',
    level_evidence_rules: '{g} rules mastered.',
  },
  de: {
    freeze_used: 'Ein Ruhetag hat Ihre Serie gehalten.',
    level_evidence: '{w} Wörter und {g} Regeln sicher.',
    level_evidence_words: '{w} Wörter sicher.',
    level_evidence_rules: '{g} Regeln sicher.',
  },
  fr: {
    freeze_used: 'Un jour de relâche a gardé la série.',
    level_evidence: '{w} mots et {g} règles maîtrisés.',
    level_evidence_words: '{w} mots maîtrisés.',
    level_evidence_rules: '{g} règles maîtrisées.',
  },
};

export function recapStatusCopy(language: ControlLanguage | null | undefined): Record<StatusKey, string> {
  return STATUS[(language ?? 'en') as ControlLanguage] ?? STATUS.en;
}

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}
