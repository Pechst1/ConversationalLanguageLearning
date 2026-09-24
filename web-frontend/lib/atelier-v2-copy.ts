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
  // Microphone and transcription failures. These *explain* a failure, so they
  // follow the learner's language rather than staying in the French chrome
  // voice they were written in (WP-21).
  | 'mic_unavailable'
  | 'mic_denied'
  | 'mic_open_failed'
  | 'transcribing'
  | 'transcription_failed'
  | 'transcription_empty'
  | 'nothing_heard'
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
  | 'artwork_decorative'
  // WP-81 / WP-82 — Home's own status words (the day, the streak, one chip)
  | 'home_label'
  | 'home_plan'
  | 'home_part_done'
  | 'home_part_active'
  | 'home_part_todo'
  | 'home_streak_first'
  | 'home_streak_days'
  | 'home_streak_done'
  | 'home_streak_seals'
  | 'home_level_aria'
  | 'home_letter'
  | 'home_words_one'
  | 'home_practice'
  | 'home_practice_aria'
  | 'home_words_many'
  | 'home_letter_aria'
  | 'home_review_one'
  | 'home_review_many';

type Table = Record<AtelierCopyKey, string>;

const EN: Table = {
  nav_atelier: 'Atelier',
  nav_missions: 'Courrier',
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

  mic_unavailable: 'No microphone is available on this device — type your answer instead.',
  mic_denied: 'The microphone was refused — allow access, or type your answer.',
  mic_open_failed: 'The microphone could not be opened.',
  transcribing: 'Transcribing',
  transcription_failed: 'The transcription failed — try again, or type your answer.',
  transcription_empty: 'Nothing was transcribed — try again.',
  nothing_heard: 'I heard nothing. Tap the microphone, then speak.',

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
  home_label: 'Atelier · today',
  home_plan: 'Today’s plan',
  home_part_done: 'done',
  home_part_active: 'in progress',
  home_part_todo: 'to come',
  home_streak_first: 'day one',
  home_streak_days: 'days',
  home_streak_done: 'day done',
  home_streak_seals: 'your seals',
  home_level_aria: 'Your level: {band}, {percent} % of the way through',
  home_letter: 'New letter',
  home_letter_aria: 'A letter is waiting',
  home_words_one: '1 word',
  home_practice: 'More practice',
  home_practice_aria: 'More practice on today’s rules',
  home_words_many: '{n} words',
  home_review_one: 'Review 1 word',
  home_review_many: 'Review {n} words',
};

const DE: Table = {
  nav_atelier: 'Atelier',
  nav_missions: 'Courrier',
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

  mic_unavailable: 'Auf diesem Gerät gibt es kein Mikrofon — schreibe deine Antwort.',
  mic_denied: 'Das Mikrofon wurde abgelehnt — erlaube den Zugriff, oder schreibe deine Antwort.',
  mic_open_failed: 'Das Mikrofon ließ sich nicht öffnen.',
  transcribing: 'Wird transkribiert',
  transcription_failed: 'Die Transkription ist fehlgeschlagen — versuche es erneut, oder schreibe deine Antwort.',
  transcription_empty: 'Es wurde nichts transkribiert — versuche es erneut.',
  nothing_heard: 'Ich habe nichts gehört. Tippe auf das Mikrofon und sprich dann.',

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
  home_label: 'Atelier · heute',
  home_plan: 'Der Plan für heute',
  home_part_done: 'erledigt',
  home_part_active: 'läuft',
  home_part_todo: 'kommt noch',
  home_streak_first: 'erster Tag',
  home_streak_days: 'Tage',
  home_streak_done: 'Tag geschafft',
  home_streak_seals: 'Ihre Siegel',
  home_level_aria: 'Ihr Niveau: {band}, zu {percent} % geschafft',
  home_letter: 'Neuer Brief',
  home_letter_aria: 'Ein Brief wartet auf Sie',
  home_words_one: '1 Wort',
  home_practice: 'Mehr üben',
  home_practice_aria: 'Mehr üben mit den Regeln von heute',
  home_words_many: '{n} Wörter',
  home_review_one: '1 Wort wiederholen',
  home_review_many: '{n} Wörter wiederholen',
};

const FR: Table = {
  nav_atelier: 'Atelier',
  nav_missions: 'Courrier',
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

  mic_unavailable: 'Aucun micro disponible sur cet appareil — écrivez votre réponse.',
  mic_denied: 'Micro refusé — autorisez l’accès, ou écrivez votre réponse.',
  mic_open_failed: 'Le micro n’a pas pu être ouvert.',
  transcribing: 'Transcription en cours',
  transcription_failed: 'La transcription a échoué — réessayez, ou écrivez votre réponse.',
  transcription_empty: 'Rien n’a été transcrit — réessayez.',
  nothing_heard: 'Je n’ai rien entendu. Touchez le micro, puis parlez.',

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
  home_label: 'Atelier · La Une',
  home_plan: 'Le plan du jour',
  home_part_done: 'fait',
  home_part_active: 'en cours',
  home_part_todo: 'à venir',
  home_streak_first: '1ᵉʳ jour',
  home_streak_days: 'jours de suite',
  home_streak_done: 'journée bouclée',
  home_streak_seals: 'vos sceaux',
  home_level_aria: 'Votre niveau : {band}, parcouru à {percent} %',
  home_letter: 'Nouvelle lettre',
  home_letter_aria: 'Une lettre vous attend',
  home_words_one: '1 mot',
  home_practice: 'Plus de pratique',
  home_practice_aria: 'Plus de pratique sur les règles du jour',
  home_words_many: '{n} mots',
  home_review_one: 'Réviser 1 mot',
  home_review_many: 'Réviser {n} mots',
};

const TABLES: Record<ControlLanguage, Table> = { en: EN, de: DE, fr: FR };

/** The merged table a renderer receives: journey contract keys plus V2 chrome. */
export type AtelierCopy = JourneyCopy & Table;

/**
 * WP-82 — the one language rule (`lib/language-rule.ts`). Only the navigation
 * labels — the names of places — are French on every control language. Every
 * other key follows the language the caller resolved: the learner's own up to
 * A2, French from B1 (`chromeLanguage(control, level)`). This supersedes
 * WP-51's list, which also kept buttons French and so put French buttons
 * under German or English status lines.
 */
export const V2_CHROME_KEYS: readonly AtelierCopyKey[] = [
  'nav_atelier',
  'nav_missions',
  'nav_serial',
  'nav_notebook',
  'nav_label',
];

const V2_CHROME_FR: Partial<Table> = Object.fromEntries(
  V2_CHROME_KEYS.map((key) => [key, FR[key]]),
) as Partial<Table>;

const MERGED: Record<ControlLanguage, AtelierCopy> = {
  en: { ...journeyCopy('en'), ...EN, ...V2_CHROME_FR },
  de: { ...journeyCopy('de'), ...DE, ...V2_CHROME_FR },
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
  return { ...TABLES[normalizeControlLanguage(language)], ...V2_CHROME_FR };
}

export default atelierCopy;
