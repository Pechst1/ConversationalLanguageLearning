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
  // WP-120 phase D · the entry points (close screen, Relevé badge, Settings row)
  see_on_map: string;
  badge_label: (n: number) => string;
  settings_row: string;
  settings_hint: string;
  settings_action: string;
  // WP-121 A · Le Palais de mémoire
  due_waiting: (n: number) => string;
  due_pin_label: (n: number) => string;
  review_here: string;
  review_title: string;
  review_progress: (index: number, total: number) => string;
  review_instruction: Record<'match_pairs' | 'word_bank' | 'unscramble' | 'dictation', string>;
  review_check: string;
  review_next: string;
  review_sending: string;
  review_correct: string;
  review_wrong: string;
  review_tiles_empty: string;
  review_remove_last: string;
  review_done_title: string;
  review_done_body: string;
  review_back: string;
  review_empty: string;
  review_error: string;
  // WP-121 B · La Relecture
  relecture_open_question: string;
  relecture_open_headline: string;
  relecture_read: (date: string) => string;
  relecture_title: string;
  relecture_lead_question: string;
  relecture_lead_headline: string;
  relecture_field: string;
  relecture_placeholder: string;
  relecture_send: string;
  relecture_sending: string;
  relecture_flag: Record<'register' | 'grammar', string>;
  relecture_unavailable: string;
  date_short: (iso: string) => string;
};

const CONTRIBUTION_FR = {
  headline_choice: 'Ton titre',
  headline_write: 'Ton titre',
  reader_question: 'Ta question',
  short_report: 'Ton papier',
};

const week_fr = (week: number | null) => (week == null ? '' : `Semaine ${week}`);

function shortDate(locale: string, iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  try {
    return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(date);
  } catch {
    return date.toISOString().slice(0, 10);
  }
}
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
  see_on_map: 'Voir sur la carte',
  badge_label: (n) => (n === 1 ? 'La Carte · 1 Papier' : `La Carte · ${n} Papiers`),
  settings_row: 'La Carte',
  settings_hint: 'Où chaque Papier t’a mené·e.',
  settings_action: 'Ouvrir',
  due_waiting: (n) => (n === 1 ? '1 mot t’attend ici' : `${n} mots t’attendent ici`),
  due_pin_label: (n) => (n === 1 ? '1 mot à revoir ici' : `${n} mots à revoir ici`),
  review_here: 'Réviser ici',
  review_title: 'Les mots d’ici',
  review_progress: (index, total) => `${index} sur ${total}`,
  review_instruction: {
    match_pairs: 'Relie chaque mot à son sens.',
    word_bank: 'Remets la phrase d’ici dans l’ordre. Un mot est en trop.',
    unscramble: 'Remets la phrase d’ici dans l’ordre.',
    dictation: 'Écoute, et écris ce que tu entends.',
  },
  review_check: 'Vérifier',
  review_next: 'Suivant',
  review_sending: 'Un instant…',
  review_correct: 'Juste',
  review_wrong: 'À revoir',
  review_tiles_empty: 'Touche les mots dans l’ordre.',
  review_remove_last: 'Retirer le dernier mot',
  review_done_title: 'C’est revu.',
  review_done_body: 'Les mots d’ici reviendront plus tard, au bon moment.',
  review_back: 'Retour à la carte',
  review_empty: 'Plus rien à revoir ici pour l’instant.',
  review_error: 'La révision ne s’ouvre pas. Rien n’est perdu.',
  relecture_open_question: 'Relire ta question',
  relecture_open_headline: 'Réécrire ton titre',
  relecture_read: (date) => (date ? `Relue le ${date}` : 'Relue'),
  relecture_title: 'La Relecture',
  relecture_lead_question: 'Tu avais posé cette question avec Romy. Aujourd’hui, qu’est-ce que tu y réponds ?',
  relecture_lead_headline: 'Quel titre donnerais-tu aujourd’hui à cette histoire ?',
  relecture_field: 'Ta réponse, en français · une ou deux phrases',
  relecture_placeholder: 'Je pense que…',
  relecture_send: 'Envoyer',
  relecture_sending: 'Envoi…',
  relecture_flag: { register: 'registre', grammar: 'grammaire' },
  relecture_unavailable: 'Cette relecture n’est pas encore ouverte.',
  date_short: (iso) => shortDate('fr-FR', iso),
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
  see_on_map: 'See it on the map',
  badge_label: (n) => (n === 1 ? 'La Carte · 1 Papier, open the map' : `La Carte · ${n} Papiers, open the map`),
  settings_hint: 'Where each Papier took you.',
  settings_action: 'Open',
  due_waiting: (n) => (n === 1 ? '1 word is waiting for you here' : `${n} words are waiting for you here`),
  due_pin_label: (n) => (n === 1 ? '1 word to review here' : `${n} words to review here`),
  review_here: 'Review here',
  review_title: 'The words from here',
  review_progress: (index, total) => `${index} of ${total}`,
  review_instruction: {
    match_pairs: 'Match each word with its meaning.',
    word_bank: 'Put the sentence from here back in order. One word is extra.',
    unscramble: 'Put the sentence from here back in order.',
    dictation: 'Listen, and write what you hear.',
  },
  review_check: 'Check',
  review_next: 'Next',
  review_sending: 'One moment…',
  review_correct: 'Right',
  review_wrong: 'To review',
  review_tiles_empty: 'Tap the words in order.',
  review_remove_last: 'Remove the last word',
  review_done_title: 'Reviewed.',
  review_done_body: 'The words from here will come back later, at the right time.',
  review_back: 'Back to the map',
  review_empty: 'Nothing left to review here for now.',
  review_error: 'The review won’t open. Nothing is lost.',
  relecture_open_question: 'Answer your question again',
  relecture_open_headline: 'Rewrite your headline',
  relecture_read: (date) => (date ? `Re-read on ${date}` : 'Re-read'),
  relecture_lead_question: 'You asked this question with Romy. What would you answer today?',
  relecture_lead_headline: 'What headline would you give this story today?',
  relecture_field: 'Your answer, in French · one or two sentences',
  relecture_send: 'Send',
  relecture_sending: 'Sending…',
  relecture_flag: { register: 'register', grammar: 'grammar' },
  relecture_unavailable: 'This re-reading isn’t open yet.',
  date_short: (iso) => shortDate('en-GB', iso),
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
  see_on_map: 'Auf der Karte ansehen',
  badge_label: (n) => (n === 1 ? 'La Carte · 1 Papier, Karte öffnen' : `La Carte · ${n} Papiers, Karte öffnen`),
  settings_hint: 'Wohin dich jedes Papier geführt hat.',
  settings_action: 'Öffnen',
  due_waiting: (n) => (n === 1 ? '1 Wort wartet hier auf dich' : `${n} Wörter warten hier auf dich`),
  due_pin_label: (n) => (n === 1 ? '1 Wort hier zu wiederholen' : `${n} Wörter hier zu wiederholen`),
  review_here: 'Hier wiederholen',
  review_title: 'Die Wörter von hier',
  review_progress: (index, total) => `${index} von ${total}`,
  review_instruction: {
    match_pairs: 'Verbinde jedes Wort mit seiner Bedeutung.',
    word_bank: 'Bring den Satz von hier in die richtige Reihenfolge. Ein Wort ist zu viel.',
    unscramble: 'Bring den Satz von hier in die richtige Reihenfolge.',
    dictation: 'Hör zu und schreib, was du hörst.',
  },
  review_check: 'Prüfen',
  review_next: 'Weiter',
  review_sending: 'Einen Moment…',
  review_correct: 'Richtig',
  review_wrong: 'Nochmal ansehen',
  review_tiles_empty: 'Tippe die Wörter der Reihe nach an.',
  review_remove_last: 'Letztes Wort entfernen',
  review_done_title: 'Wiederholt.',
  review_done_body: 'Die Wörter von hier kommen später wieder, zur richtigen Zeit.',
  review_back: 'Zurück zur Karte',
  review_empty: 'Hier gibt es gerade nichts zu wiederholen.',
  review_error: 'Die Wiederholung lässt sich nicht öffnen. Nichts ist verloren.',
  relecture_open_question: 'Deine Frage nochmal beantworten',
  relecture_open_headline: 'Deine Schlagzeile neu schreiben',
  relecture_read: (date) => (date ? `Neu gelesen am ${date}` : 'Neu gelesen'),
  relecture_lead_question: 'Diese Frage hast du mit Romy gestellt. Was antwortest du heute darauf?',
  relecture_lead_headline: 'Welche Schlagzeile würdest du dieser Geschichte heute geben?',
  relecture_field: 'Deine Antwort, auf Französisch · ein oder zwei Sätze',
  relecture_send: 'Senden',
  relecture_sending: 'Wird gesendet…',
  relecture_flag: { register: 'Register', grammar: 'Grammatik' },
  relecture_unavailable: 'Diese Relecture ist noch nicht offen.',
  date_short: (iso) => shortDate('de-DE', iso),
};

const COPY: Record<CarteLanguage, CarteCopy> = { fr: FR, en: EN, de: DE };

export function carteCopy(language: string | null | undefined): CarteCopy {
  return COPY[(language as CarteLanguage) in COPY ? (language as CarteLanguage) : 'fr'];
}
