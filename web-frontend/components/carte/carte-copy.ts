/**
 * WP-120 phase C · La Carte's chrome in the learner's language (fr / en / de).
 *
 * What the map *says* stays French whatever the chrome: the place labels, the
 * headlines, the kept words, «La Carte», «Mon quartier», «France», «Semaine 40» and
 * the «toi» on the learner's own words. The chrome around it follows the learner.
 */

import type { CarteLanguage, CarteLevel } from '@/lib/carte-types';

export type CarteCopy = {
  page_title: string;
  level_name: Record<CarteLevel, string>;
  map_label: string;
  zoom_out_france: string;
  zoom_out_label: string;
  count_pins: (n: number) => string;
  elsewhere: (n: number) => string;
  quartier_toggle: string;
  quartier_hint: string;
  quartier_place: string;
  cluster_label: (n: number) => string;
  cluster_list_title: string;
  pin_label: (place: string, week: number | null, headline: string) => string;
  week_fr: (week: number | null) => string;
  kept_words: string;
  contribution: Record<string, string>;
  question_kept: string;
  yours: string;
  relire: string;
  releve: string;
  empty_title: string;
  empty_body: string;
  empty_action: string;
  loading: string;
  error_title: string;
  error_body: string;
  retry: string;
  disabled_title: string;
  disabled_body: string;
  back: string;
  mock_badge: string;
};

const CONTRIBUTION_FR = {
  headline_choice: 'Ton titre',
  headline_write: 'Ton titre',
  reader_question: 'Ta question',
  short_report: 'Ton papier',
};

const week_fr = (week: number | null) => (week == null ? '' : `Semaine ${week}`);
const LEVEL_NAME: Record<CarteLevel, string> = { france: 'La France', idf: 'Île-de-France', paris: 'Paris' };

const FR: CarteCopy = {
  page_title: 'La Carte',
  level_name: LEVEL_NAME,
  map_label: 'La Carte de tes Papiers',
  zoom_out_france: 'France',
  zoom_out_label: 'Revenir à la carte de France',
  count_pins: (n) => (n === 0 ? 'Aucun Papier' : n === 1 ? '1 Papier' : `${n} Papiers`),
  elsewhere: (n) => (n === 1 ? '1 Papier ailleurs en France' : `${n} Papiers ailleurs en France`),
  quartier_toggle: 'Mon quartier',
  quartier_hint: 'Les lieux du feuilleton où tu es déjà allé·e.',
  quartier_place: 'Ici, dans le feuilleton.',
  cluster_label: (n) => `${n} Papiers ici. Agrandir.`,
  cluster_list_title: 'Ici',
  pin_label: (place, week, headline) => [place, week_fr(week), headline].filter(Boolean).join(' · '),
  week_fr,
  kept_words: 'Les mots gardés',
  contribution: CONTRIBUTION_FR,
  question_kept: 'La question gardée',
  yours: 'toi',
  relire: 'Relire',
  releve: 'Dans le Relevé',
  empty_title: 'Ta carte est vide.',
  empty_body: 'Le premier Papier te mettra quelque part.',
  empty_action: 'Ouvrir le Papier',
  loading: 'La carte se déplie…',
  error_title: 'La carte ne s’ouvre pas.',
  error_body: 'Rien n’est perdu. Réessaie dans un instant.',
  retry: 'Réessayer',
  disabled_title: 'La Carte n’est pas encore ouverte.',
  disabled_body: 'Elle arrive avec le Papier de Romy.',
  back: 'Retour',
  mock_badge: 'Démo · données fictives',
};

const EN: CarteCopy = {
  ...FR,
  map_label: 'The map of your Papiers',
  zoom_out_label: 'Back to the map of France',
  count_pins: (n) => (n === 0 ? 'No Papier yet' : n === 1 ? '1 Papier' : `${n} Papiers`),
  elsewhere: (n) => (n === 1 ? '1 Papier elsewhere in France' : `${n} Papiers elsewhere in France`),
  quartier_hint: 'The places of the serial you have already been to.',
  quartier_place: 'Here, in the serial.',
  cluster_label: (n) => `${n} Papiers here. Zoom in.`,
  cluster_list_title: 'Here',
  kept_words: 'Words you kept',
  contribution: { headline_choice: 'Your headline', headline_write: 'Your headline', reader_question: 'Your question', short_report: 'Your report' },
  question_kept: 'The question kept',
  relire: 'Read it again',
  releve: 'In the Relevé',
  empty_title: 'Your map is empty.',
  empty_body: 'Your first Papier will put you somewhere.',
  empty_action: 'Open the Papier',
  loading: 'Unfolding the map…',
  error_title: 'The map won’t open.',
  error_body: 'Nothing is lost. Try again in a moment.',
  retry: 'Try again',
  disabled_title: 'La Carte isn’t open yet.',
  disabled_body: 'It comes with Romy’s Papier.',
  back: 'Back',
  mock_badge: 'Demo · made-up data',
};

const DE: CarteCopy = {
  ...FR,
  map_label: 'Die Karte deiner Papiers',
  zoom_out_label: 'Zurück zur Frankreichkarte',
  count_pins: (n) => (n === 0 ? 'Noch kein Papier' : n === 1 ? '1 Papier' : `${n} Papiers`),
  elsewhere: (n) => (n === 1 ? '1 Papier anderswo in Frankreich' : `${n} Papiers anderswo in Frankreich`),
  quartier_hint: 'Die Orte des Feuilletons, an denen du schon warst.',
  quartier_place: 'Hier, im Feuilleton.',
  cluster_label: (n) => `${n} Papiers hier. Vergrößern.`,
  cluster_list_title: 'Hier',
  kept_words: 'Behaltene Wörter',
  contribution: { headline_choice: 'Deine Schlagzeile', headline_write: 'Deine Schlagzeile', reader_question: 'Deine Frage', short_report: 'Dein Bericht' },
  question_kept: 'Die offene Frage',
  relire: 'Nochmal lesen',
  releve: 'Im Relevé',
  empty_title: 'Deine Karte ist leer.',
  empty_body: 'Dein erstes Papier bringt dich an einen Ort.',
  empty_action: 'Das Papier öffnen',
  loading: 'Die Karte wird aufgefaltet…',
  error_title: 'Die Karte lässt sich nicht öffnen.',
  error_body: 'Nichts ist verloren. Versuch es gleich noch einmal.',
  retry: 'Nochmal versuchen',
  disabled_title: 'La Carte ist noch nicht offen.',
  disabled_body: 'Sie kommt mit Romys Papier.',
  back: 'Zurück',
  mock_badge: 'Demo · erfundene Daten',
};

const COPY: Record<CarteLanguage, CarteCopy> = { fr: FR, en: EN, de: DE };

export function carteCopy(language: string | null | undefined): CarteCopy {
  return COPY[(language as CarteLanguage) in COPY ? (language as CarteLanguage) : 'fr'];
}
