/**
 * «Le bilan» — the page's own words, in the learner's chrome language (up to A2 their
 * own, French from B1: `useChromeLanguage`). The place's name stays French in every
 * column, like Le Correcteur and La Revue. The learner's sentences, the rule titles in
 * French, the episodes and the choices are French content and are never translated.
 *
 * Honest on a thin week: one played day gets a short, warm, true page — no praise it
 * did not earn, no guilt for the days it did not play.
 */

import type { BilanLanguage } from '@/lib/bilan-types';

export type BilanCopy = {
  page_title: string;
  back: string;
  week_of: string;
  so_far: string;
  headline_many: string;
  headline_many_current: string;
  headline_one: string;
  headline_none_current: string;
  headline_none: string;
  body_one: string;
  body_none: string;
  days_aria: string;
  lines_title: string;
  lines_note: string;
  listen: string;
  listen_stop: string;
  words_title: string;
  words_new_one: string;
  words_new_many: string;
  words_held_one: string;
  words_held_many: string;
  rules_title: string;
  rule_met: string;
  story_title: string;
  episodes_label: string;
  decisions_label: string;
  next_label: string;
  cta: string;
  previous_week: string;
  next_week: string;
  loading: string;
  error_title: string;
  error_body: string;
  retry: string;
  disabled_title: string;
  disabled_body: string;
  card_title: string;
  card_days_one: string;
  card_days_many: string;
  card_open: string;
  card_dismiss: string;
  releve_this_week: string;
  releve_week: string;
  releve_days_one: string;
  releve_days_many: string;
};

const FR: BilanCopy = {
  page_title: 'Le bilan',
  back: 'Retour au Cahier',
  week_of: 'Semaine du {range}',
  so_far: 'jusqu’ici',
  headline_many: '{n} jours dans l’histoire cette semaine.',
  headline_many_current: '{n} jours dans l’histoire jusqu’ici.',
  headline_one: 'Un jour cette semaine.',
  headline_none_current: 'La semaine commence.',
  headline_none: 'Une semaine calme.',
  body_one: 'Une semaine courte, et vraie. Voici ce qu’elle a laissé.',
  body_none: 'L’histoire t’attend là où tu l’as laissée.',
  days_aria: '{n} jours joués sur 7',
  lines_title: 'Ce que tu sais dire maintenant',
  lines_note: 'Tes phrases de la semaine, telles qu’elles ont été corrigées.',
  listen: 'Écouter',
  listen_stop: 'Arrêter',
  words_title: 'Mots',
  words_new_one: '1 nouveau mot rencontré',
  words_new_many: '{n} nouveaux mots rencontrés',
  words_held_one: '1 mot tenu en révision',
  words_held_many: '{n} mots tenus en révision',
  rules_title: 'Règles',
  rule_met: 'découverte cette semaine',
  story_title: 'L’histoire',
  episodes_label: 'Joué',
  decisions_label: 'Tes choix',
  next_label: 'Encore ouvert',
  cta: 'Retour à l’histoire',
  previous_week: 'Semaine précédente',
  next_week: 'Semaine suivante',
  loading: 'Le bilan se prépare…',
  error_title: 'Le bilan n’a pas pu se charger.',
  error_body: 'Rien n’est perdu. Réessaie dans un instant.',
  retry: 'Réessayer',
  disabled_title: 'Le bilan n’est pas encore ouvert.',
  disabled_body: 'Ta semaine est gardée dans le Cahier.',
  card_title: 'Ta semaine, {range}',
  card_days_one: '1 jour joué',
  card_days_many: '{n} jours joués',
  card_open: 'Lire le bilan',
  card_dismiss: 'Pas maintenant',
  releve_this_week: 'Cette semaine, jusqu’ici',
  releve_week: 'Semaine du {range}',
  releve_days_one: '1 jour',
  releve_days_many: '{n} jours',
};

const EN: BilanCopy = {
  page_title: 'Le bilan',
  back: 'Back to the Cahier',
  week_of: 'Week of {range}',
  so_far: 'so far',
  headline_many: '{n} days in the story this week.',
  headline_many_current: '{n} days in the story so far.',
  headline_one: 'One day this week.',
  headline_none_current: 'The week is just starting.',
  headline_none: 'A quiet week.',
  body_one: 'A short week, and a real one. Here is what it left.',
  body_none: 'The story is waiting where you left it.',
  days_aria: '{n} of 7 days played',
  lines_title: 'What you can say now',
  lines_note: 'Your sentences from this week, as they stand corrected.',
  listen: 'Listen',
  listen_stop: 'Stop',
  words_title: 'Words',
  words_new_one: '1 new word met',
  words_new_many: '{n} new words met',
  words_held_one: '1 word held in review',
  words_held_many: '{n} words held in review',
  rules_title: 'Rules',
  rule_met: 'met this week',
  story_title: 'The story',
  episodes_label: 'Played',
  decisions_label: 'Your choices',
  next_label: 'Still open',
  cta: 'Back to the story',
  previous_week: 'Previous week',
  next_week: 'Next week',
  loading: 'Gathering your week…',
  error_title: 'Your week could not be loaded.',
  error_body: 'Nothing is lost. Try again in a moment.',
  retry: 'Try again',
  disabled_title: 'Le bilan is not open yet.',
  disabled_body: 'Your week is kept in the Cahier.',
  card_title: 'Your week, {range}',
  card_days_one: '1 day played',
  card_days_many: '{n} days played',
  card_open: 'Read le bilan',
  card_dismiss: 'Not now',
  releve_this_week: 'This week so far',
  releve_week: 'Week of {range}',
  releve_days_one: '1 day',
  releve_days_many: '{n} days',
};

const DE: BilanCopy = {
  page_title: 'Le bilan',
  back: 'Zurück zum Cahier',
  week_of: 'Woche vom {range}',
  so_far: 'bis jetzt',
  headline_many: '{n} Tage in der Geschichte diese Woche.',
  headline_many_current: '{n} Tage in der Geschichte bis jetzt.',
  headline_one: 'Ein Tag diese Woche.',
  headline_none_current: 'Die Woche fängt gerade an.',
  headline_none: 'Eine stille Woche.',
  body_one: 'Eine kurze Woche, und eine echte. Das ist von ihr geblieben.',
  body_none: 'Die Geschichte wartet dort, wo du sie gelassen hast.',
  days_aria: '{n} von 7 Tagen gespielt',
  lines_title: 'Was du jetzt sagen kannst',
  lines_note: 'Deine Sätze dieser Woche, so wie sie korrigiert stehen.',
  listen: 'Anhören',
  listen_stop: 'Stopp',
  words_title: 'Wörter',
  words_new_one: '1 neues Wort kennengelernt',
  words_new_many: '{n} neue Wörter kennengelernt',
  words_held_one: '1 Wort in der Wiederholung gehalten',
  words_held_many: '{n} Wörter in der Wiederholung gehalten',
  rules_title: 'Regeln',
  rule_met: 'diese Woche kennengelernt',
  story_title: 'Die Geschichte',
  episodes_label: 'Gespielt',
  decisions_label: 'Deine Entscheidungen',
  next_label: 'Noch offen',
  cta: 'Zurück zur Geschichte',
  previous_week: 'Vorige Woche',
  next_week: 'Nächste Woche',
  loading: 'Deine Woche wird zusammengestellt…',
  error_title: 'Deine Woche konnte nicht geladen werden.',
  error_body: 'Nichts ist verloren. Versuch es gleich noch einmal.',
  retry: 'Erneut versuchen',
  disabled_title: 'Le bilan ist noch nicht geöffnet.',
  disabled_body: 'Deine Woche bleibt im Cahier.',
  card_title: 'Deine Woche, {range}',
  card_days_one: '1 Tag gespielt',
  card_days_many: '{n} Tage gespielt',
  card_open: 'Le bilan lesen',
  card_dismiss: 'Nicht jetzt',
  releve_this_week: 'Diese Woche bis jetzt',
  releve_week: 'Woche vom {range}',
  releve_days_one: '1 Tag',
  releve_days_many: '{n} Tage',
};

export function normalizeBilanLanguage(language: unknown): BilanLanguage {
  return language === 'fr' || language === 'de' ? language : 'en';
}

export function bilanCopy(language: unknown): BilanCopy {
  const code = normalizeBilanLanguage(language);
  if (code === 'fr') return FR;
  if (code === 'de') return DE;
  return EN;
}

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? ''));
}

export const BILAN_COPIES = { fr: FR, en: EN, de: DE } as const;
