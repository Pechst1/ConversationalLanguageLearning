/**
 * WP-122 B · Le Correcteur — the page's own words, in the learner's chrome language.
 * Romy's draft, her line at the end and the grammar points stay French.
 */

import type { CrLanguage } from '@/lib/correcteur-types';

export type CorrecteurCopy = {
  page_title: string;
  exit: string;
  intro: string;
  intro_one: string;
  how: string;
  field_label: string;
  field_placeholder: string;
  options_label: string;
  mark: string;
  mark_no_fix: string;
  cancel: string;
  marks_title: string;
  marks_empty: string;
  remove: string;
  no_fix: string;
  press: string;
  pending: string;
  result_title: string;
  counts: string;
  repaired: string;
  noticed: string;
  missed: string;
  false_alarm: string;
  false_alarm_body: string;
  errors_title: string;
  releve: string;
  loading: string;
  error_title: string;
  error_body: string;
  retry: string;
  disabled_title: string;
  disabled_body: string;
  empty_title: string;
  empty_body: string;
  back_home: string;
  mock_badge: string;
  status_selected: string;
  status_correct: string;
  status_wrong: string;
};

const FR: CorrecteurCopy = {
  page_title: 'Le Correcteur',
  exit: 'Quitter',
  intro: 'Romy a laissé {n} fautes dans son brouillon.',
  intro_one: 'Romy a laissé une faute dans son brouillon.',
  how: 'Touche un mot, ou glisse sur plusieurs, pour le marquer.',
  field_label: 'Corrige',
  field_placeholder: 'la bonne forme',
  options_label: 'Choisis la bonne forme',
  mark: 'Marquer',
  mark_no_fix: 'Marquer sans corriger',
  cancel: 'Annuler',
  marks_title: 'Marques',
  marks_empty: 'Aucune marque pour l’instant.',
  remove: 'Retirer',
  no_fix: 'à revoir',
  press: 'Bon à tirer',
  pending: 'À l’imprimerie…',
  result_title: 'L’épreuve corrigée',
  counts: '{r} corrigées · {n} repérées · {m} manquées',
  repaired: 'corrigée',
  noticed: 'repérée',
  missed: 'manquée',
  false_alarm: 'celui-là était bon',
  false_alarm_body: 'Pas de souci : mieux vaut une marque de trop.',
  errors_title: 'Les fautes du brouillon',
  releve: 'Dans le Relevé',
  loading: 'Romy relit son brouillon…',
  error_title: 'Le brouillon n’arrive pas',
  error_body: 'La connexion a coupé. Réessaie dans un instant.',
  retry: 'Réessayer',
  disabled_title: 'Le Correcteur est fermé',
  disabled_body: 'Ce bureau n’est pas encore ouvert.',
  empty_title: 'Tout est relu',
  empty_body: 'Tu as corrigé tous les brouillons de la semaine.',
  back_home: 'Retour à La Une',
  mock_badge: 'MAQUETTE',
  status_selected: 'choisie',
  status_correct: 'juste',
  status_wrong: 'fausse',
};

const EN: CorrecteurCopy = {
  ...FR,
  page_title: 'The proofreader',
  exit: 'Leave',
  intro: 'Romy left {n} mistakes in her draft.',
  intro_one: 'Romy left one mistake in her draft.',
  how: 'Tap a word, or drag across several, to mark it.',
  field_label: 'Correct it',
  field_placeholder: 'the right form',
  options_label: 'Pick the right form',
  mark: 'Mark',
  mark_no_fix: 'Mark without fixing',
  cancel: 'Cancel',
  marks_title: 'Marks',
  marks_empty: 'No marks yet.',
  remove: 'Remove',
  no_fix: 'to check',
  pending: 'Off to the printer…',
  result_title: 'The corrected proof',
  counts: '{r} fixed · {n} spotted · {m} missed',
  repaired: 'fixed',
  noticed: 'spotted',
  missed: 'missed',
  false_alarm: 'that one was right',
  false_alarm_body: 'No harm done: one mark too many is better than one too few.',
  errors_title: 'The mistakes in the draft',
  releve: 'In Le Relevé',
  loading: 'Romy is rereading her draft…',
  error_title: 'The draft is not coming through',
  error_body: 'The connection dropped. Try again in a moment.',
  retry: 'Try again',
  disabled_title: 'The proofreader is closed',
  disabled_body: 'This desk is not open yet.',
  empty_title: 'All proofread',
  empty_body: 'You have corrected every draft this week.',
  back_home: 'Back to La Une',
  mock_badge: 'MOCK',
  status_selected: 'selected',
  status_correct: 'right',
  status_wrong: 'wrong',
};

const DE: CorrecteurCopy = {
  ...FR,
  page_title: 'Das Korrektorat',
  exit: 'Verlassen',
  intro: 'Romy hat {n} Fehler in ihrem Entwurf gelassen.',
  intro_one: 'Romy hat einen Fehler in ihrem Entwurf gelassen.',
  how: 'Tippe auf ein Wort oder zieh über mehrere, um es zu markieren.',
  field_label: 'Korrigiere',
  field_placeholder: 'die richtige Form',
  options_label: 'Wähle die richtige Form',
  mark: 'Markieren',
  mark_no_fix: 'Ohne Korrektur markieren',
  cancel: 'Abbrechen',
  marks_title: 'Markierungen',
  marks_empty: 'Noch keine Markierung.',
  remove: 'Entfernen',
  no_fix: 'prüfen',
  pending: 'Ab in die Druckerei…',
  result_title: 'Der korrigierte Abzug',
  counts: '{r} korrigiert · {n} entdeckt · {m} übersehen',
  repaired: 'korrigiert',
  noticed: 'entdeckt',
  missed: 'übersehen',
  false_alarm: 'das war richtig',
  false_alarm_body: 'Kein Problem: lieber eine Markierung zu viel.',
  errors_title: 'Die Fehler im Entwurf',
  releve: 'Im Relevé',
  loading: 'Romy liest ihren Entwurf noch einmal…',
  error_title: 'Der Entwurf kommt nicht an',
  error_body: 'Die Verbindung ist abgebrochen. Versuch es gleich noch einmal.',
  retry: 'Erneut versuchen',
  disabled_title: 'Das Korrektorat ist geschlossen',
  disabled_body: 'Dieser Schreibtisch ist noch nicht geöffnet.',
  empty_title: 'Alles gelesen',
  empty_body: 'Du hast alle Entwürfe dieser Woche korrigiert.',
  back_home: 'Zurück zu La Une',
  mock_badge: 'ATTRAPPE',
  status_selected: 'gewählt',
  status_correct: 'richtig',
  status_wrong: 'falsch',
};

export function correcteurCopy(language: unknown): CorrecteurCopy {
  if (language === 'fr') return FR;
  if (language === 'de') return DE;
  return EN;
}

export function normalizeLanguage(language: unknown): CrLanguage {
  return language === 'fr' || language === 'de' ? language : 'en';
}

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? ''));
}
