/**
 * WP-79 — the end-of-day recap's own words.
 *
 * WP-82, one language rule: every word here is the app's, so it is written in
 * the screen's one chrome language — the learner's up to A2, French from B1
 * (`chromeLanguage`, `lib/language-rule.ts`). The French on the recap is the
 * content: the keepsake's title, the words learned, the character's line and
 * tomorrow's teaser.
 *
 * Budget: the chrome on the recap stays under 15 words.
 */

import type { ControlLanguage } from '@/types/daily-journey';

type ChromeKey =
  | 'streak_label'
  | 'streak_value'
  | 'streak_value_one'
  | 'keep_seal'
  | 'words_label'
  | 'scene_label'
  | 'steps_value'
  | 'step_value'
  | 'teaser_label'
  | 'level_label'
  | 'mood_warmer'
  | 'mood_colder'
  | 'encore';

const CHROME: Record<ControlLanguage, Record<ChromeKey, string>> = {
  en: {
    streak_label: 'Streak',
    streak_value: '{n} days',
    streak_value_one: '1 day',
    /** WP-D4: the one primary action on a completed day. */
    keep_seal: 'Keep the seal',
    words_label: 'Words',
    scene_label: 'Scene',
    steps_value: '{n} steps',
    step_value: '1 step',
    teaser_label: 'Tomorrow',
    level_label: 'Level',
    mood_warmer: '{name} smiles at you',
    mood_colder: '{name} is a little cross',
    /** WP-L6: the quiet, optional reviews-only block after the Seal. */
    encore: '5 more minutes',
  },
  de: {
    streak_label: 'Serie',
    streak_value: '{n} Tage',
    streak_value_one: '1 Tag',
    keep_seal: 'Siegel behalten',
    words_label: 'Wörter',
    scene_label: 'Szene',
    steps_value: '{n} Schritte',
    step_value: '1 Schritt',
    teaser_label: 'Morgen',
    level_label: 'Niveau',
    mood_warmer: '{name} lächelt Sie an',
    mood_colder: '{name} ist etwas verstimmt',
    encore: 'Noch 5 Minuten',
  },
  fr: {
    streak_label: 'Série',
    streak_value: '{n} jours',
    streak_value_one: '1 jour',
    keep_seal: 'Ranger le sceau',
    words_label: 'Mots',
    scene_label: 'Scène',
    steps_value: '{n} étapes',
    step_value: '1 étape',
    teaser_label: 'La suite demain',
    level_label: 'Niveau',
    mood_warmer: '{name} vous sourit',
    mood_colder: '{name} vous en veut un peu',
    encore: 'Encore 5 minutes',
  },
};

/** The recap's chrome in the screen's chrome language. */
export function recapChrome(language: ControlLanguage | null | undefined): Record<ChromeKey, string> {
  return CHROME[(language ?? 'en') as ControlLanguage] ?? CHROME.en;
}

/** The French table, for a caller that is French by rule (B1+). */
export const RECAP_CHROME = CHROME.fr;

/**
 * WP-L6 «Encore 5 minutes»: the word drill, reviews only — no new words, a
 * five-minute deck. It never touches the story, and the streak is marked at
 * most once per local day (`record_practice_day`), so it cannot count twice.
 */
export const ENCORE_HREF = '/vocabulary/review?encore=1';

type StatusKey =
  | 'freeze_used'
  | 'level_evidence'
  | 'level_evidence_words'
  | 'level_evidence_rules'
  | 'consolidating'
  | 'forecast_line';

const STATUS: Record<ControlLanguage, Record<StatusKey, string>> = {
  en: {
    /** WP-L6 §2.2: the auto-throttle halved new intake until reviews recover. */
    consolidating: 'This week, we consolidate.',
    /** WP-L8: once a week at the Seal, measured forecasts only. */
    forecast_line: 'At this rhythm: {level} around {month}.',
    freeze_used: 'A day off kept your streak.',
    level_evidence: '{w} words and {g} rules mastered.',
    level_evidence_words: '{w} words mastered.',
    level_evidence_rules: '{g} rules mastered.',
  },
  de: {
    consolidating: 'Diese Woche festigen wir.',
    forecast_line: 'In diesem Rhythmus: {level} etwa im {month}.',
    freeze_used: 'Ein Ruhetag hat Ihre Serie gehalten.',
    level_evidence: '{w} Wörter und {g} Regeln sicher.',
    level_evidence_words: '{w} Wörter sicher.',
    level_evidence_rules: '{g} Regeln sicher.',
  },
  fr: {
    consolidating: 'Cette semaine, on consolide.',
    forecast_line: 'À ce rythme : {level} vers {month}.',
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
