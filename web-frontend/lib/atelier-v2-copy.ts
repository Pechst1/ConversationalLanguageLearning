/**
 * Atelier V2 control-language copy — WP-01.
 *
 * This is the design system's own chrome: the words on buttons, the words that
 * carry a status when colour alone must not, the navigation, and the sheet and
 * dialog furniture. It sits *on top of* `components/atelier-v2/journey/
 * journey-copy.ts`, whose keys are a frozen contract; that table is merged in
 * unchanged and re-exported, so a renderer needs exactly one copy object.
 *
 * Two rules this file exists to enforce:
 *
 *  1. **Action names are localized, not just headings.** A German learner gets
 *     "Prüfen", not an English verb under a German heading. Every label a
 *     learner can press has an entry here in all three languages.
 *  2. **Nothing here is content.** Every sentence about the scene, the task or
 *     the correction comes from the server's `*_native` / `*_fr` fields. This
 *     file never invents French, never names a learner, and never states a
 *     duration or a streak.
 *
 * The design's own copy is French ("Séance", "Lexique", "Continuer"). French is
 * kept verbatim for `fr`, and the same *meaning* — not the French word — is
 * given for `en` and `de`, because a first-time learner must be able to finish
 * the scene without first learning the chrome vocabulary.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { journeyCopy, type JourneyCopy } from '@/components/atelier-v2/journey/journey-copy';

export const CONTROL_LANGUAGES: ControlLanguage[] = ['en', 'de', 'fr'];

/**
 * Accept whatever the account, the browser or a cached envelope actually holds
 * — `de`, `de-DE`, `de_AT`, `DE`, `  fr  ` — and resolve it to a supported
 * control language. Anything unrecognised falls back to English rather than
 * rendering a half-translated screen.
 */
export function normalizeControlLanguage(value: unknown): ControlLanguage {
  if (typeof value !== 'string') return 'en';
  const base = value.trim().toLowerCase().replace('_', '-').split('-')[0];
  return (CONTROL_LANGUAGES as string[]).includes(base) ? (base as ControlLanguage) : 'en';
}

export type AtelierCopyKey =
  // Navigation
  | 'nav_atelier'
  | 'nav_missions'
  | 'nav_serial'
  | 'nav_notebook'
  | 'nav_label'
  // Chrome
  | 'settings'
  | 'close'
  | 'back'
  | 'dismiss'
  | 'more'
  | 'open'
  | 'rule_card'
  | 'today_edition'
  // Session actions — the primary label cycles through these three
  | 'action_check'
  | 'action_continue'
  | 'action_finish'
  | 'action_start'
  | 'action_send'
  | 'action_retry'
  // Recall / respond controls
  | 'choose_one'
  | 'build_sentence'
  | 'remove_last'
  | 'tiles_empty'
  | 'answer_mode_text'
  | 'answer_mode_voice'
  | 'record_start'
  | 'record_stop'
  // Status words — the text half of "status is never colour alone"
  | 'status_selected'
  | 'status_correct'
  | 'status_wrong'
  | 'status_supported'
  | 'status_unscored'
  | 'status_pending'
  | 'status_done'
  | 'status_current'
  | 'status_upcoming'
  | 'status_skipped'
  | 'status_error'
  | 'status_offline'
  // Progress
  | 'step_of'
  | 'progress_none'
  // States
  | 'loading'
  | 'empty_title'
  | 'empty_body'
  | 'error_title'
  | 'artwork_unavailable'
  | 'artwork_decorative';

type Table = Record<AtelierCopyKey, string>;

const EN: Table = {
  nav_atelier: 'Atelier',
  nav_missions: 'Missions',
  nav_serial: 'Serial',
  nav_notebook: 'Notebook',
  nav_label: 'Sections',

  settings: 'Settings',
  close: 'Close',
  back: 'Back',
  dismiss: 'Dismiss',
  more: 'More',
  open: 'Open',
  rule_card: 'The rule',
  today_edition: 'Today',

  action_check: 'Check',
  action_continue: 'Continue',
  action_finish: 'Finish',
  action_start: 'Start',
  action_send: 'Send',
  action_retry: 'Try again',

  choose_one: 'Choose one',
  build_sentence: 'Build the sentence',
  remove_last: 'Remove the last word',
  tiles_empty: 'Tap the words to build your answer.',
  answer_mode_text: 'Type instead',
  answer_mode_voice: 'Speak instead',
  record_start: 'Record',
  record_stop: 'Stop recording',

  status_selected: 'Selected',
  status_correct: 'Correct',
  status_wrong: 'Not yet',
  status_supported: 'Correct, with help',
  status_unscored: 'Not checked',
  status_pending: 'Working',
  status_done: 'Done',
  status_current: 'Now',
  status_upcoming: 'Later',
  status_skipped: 'Skipped',
  status_error: 'Error',
  status_offline: 'Offline',

  step_of: 'Step {n} of {total}',
  progress_none: 'Not started',

  loading: 'Loading',
  empty_title: 'Nothing here yet',
  empty_body: 'There is nothing to show on this screen right now.',
  error_title: 'Something went wrong',
  artwork_unavailable: 'Illustration unavailable',
  artwork_decorative: '',
};

const DE: Table = {
  nav_atelier: 'Atelier',
  nav_missions: 'Missionen',
  nav_serial: 'Feuilleton',
  nav_notebook: 'Heft',
  nav_label: 'Bereiche',

  settings: 'Einstellungen',
  close: 'Schließen',
  back: 'Zurück',
  dismiss: 'Ausblenden',
  more: 'Mehr',
  open: 'Öffnen',
  rule_card: 'Die Regel',
  today_edition: 'Heute',

  action_check: 'Prüfen',
  action_continue: 'Weiter',
  action_finish: 'Beenden',
  action_start: 'Starten',
  action_send: 'Senden',
  action_retry: 'Erneut versuchen',

  choose_one: 'Wähle eine Antwort',
  build_sentence: 'Bilde den Satz',
  remove_last: 'Letztes Wort entfernen',
  tiles_empty: 'Tippe die Wörter an, um deine Antwort zu bilden.',
  answer_mode_text: 'Lieber tippen',
  answer_mode_voice: 'Lieber sprechen',
  record_start: 'Aufnehmen',
  record_stop: 'Aufnahme stoppen',

  status_selected: 'Ausgewählt',
  status_correct: 'Richtig',
  status_wrong: 'Noch nicht',
  status_supported: 'Richtig, mit Hilfe',
  status_unscored: 'Nicht geprüft',
  status_pending: 'Läuft',
  status_done: 'Erledigt',
  status_current: 'Jetzt',
  status_upcoming: 'Später',
  status_skipped: 'Übersprungen',
  status_error: 'Fehler',
  status_offline: 'Offline',

  step_of: 'Schritt {n} von {total}',
  progress_none: 'Noch nicht begonnen',

  loading: 'Wird geladen',
  empty_title: 'Hier ist noch nichts',
  empty_body: 'Auf diesem Bildschirm gibt es gerade nichts zu zeigen.',
  error_title: 'Etwas ist schiefgelaufen',
  artwork_unavailable: 'Illustration nicht verfügbar',
  artwork_decorative: '',
};

const FR: Table = {
  nav_atelier: 'Atelier',
  nav_missions: 'Missions',
  nav_serial: 'Feuilleton',
  nav_notebook: 'Cahier',
  nav_label: 'Sections',

  settings: 'Réglages',
  close: 'Fermer',
  back: 'Retour',
  dismiss: 'Masquer',
  more: 'Plus',
  open: 'Ouvrir',
  rule_card: 'La règle',
  today_edition: 'Aujourd’hui',

  action_check: 'Vérifier',
  action_continue: 'Continuer',
  action_finish: 'Terminer',
  action_start: 'Commencer',
  action_send: 'Envoyer',
  action_retry: 'Réessayer',

  choose_one: 'Choisissez une réponse',
  build_sentence: 'Composez la phrase',
  remove_last: 'Retirer le dernier mot',
  tiles_empty: 'Touchez les mots pour composer votre réponse.',
  answer_mode_text: 'Écrire plutôt',
  answer_mode_voice: 'Parler plutôt',
  record_start: 'Enregistrer',
  record_stop: 'Arrêter l’enregistrement',

  status_selected: 'Sélectionné',
  status_correct: 'Correct',
  status_wrong: 'Pas encore',
  status_supported: 'Correct, avec aide',
  status_unscored: 'Non évalué',
  status_pending: 'En cours',
  status_done: 'Fait',
  status_current: 'Maintenant',
  status_upcoming: 'Plus tard',
  status_skipped: 'Passé',
  status_error: 'Erreur',
  status_offline: 'Hors ligne',

  step_of: 'Étape {n} sur {total}',
  progress_none: 'Pas commencé',

  loading: 'Chargement',
  empty_title: 'Rien ici pour le moment',
  empty_body: 'Il n’y a rien à afficher sur cet écran pour l’instant.',
  error_title: 'Un problème est survenu',
  artwork_unavailable: 'Illustration indisponible',
  artwork_decorative: '',
};

const TABLES: Record<ControlLanguage, Table> = { en: EN, de: DE, fr: FR };

/** The merged table a renderer receives: journey contract keys plus V2 chrome. */
export type AtelierCopy = JourneyCopy & Table;

const MERGED: Record<ControlLanguage, AtelierCopy> = {
  en: { ...journeyCopy('en'), ...EN },
  de: { ...journeyCopy('de'), ...DE },
  fr: { ...journeyCopy('fr'), ...FR },
};

/**
 * Resolve the full copy table. Anything unrecognised — a null, a regional tag,
 * a language we do not ship — falls back to English rather than showing keys.
 */
export function atelierCopy(language: unknown): AtelierCopy {
  return MERGED[normalizeControlLanguage(language)];
}

/** `Step {n} of {total}` with the numbers filled in, in the learner's language. */
export function stepOfLabel(copy: AtelierCopy, index: number, total: number): string {
  return copy.step_of.replace('{n}', String(index)).replace('{total}', String(total));
}

/** The V2-only chrome table, for a surface that does not need the journey keys. */
export function atelierChrome(language: unknown): Table {
  return TABLES[normalizeControlLanguage(language)];
}

export default atelierCopy;
