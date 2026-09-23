/**
 * Réglages copy — WP-46.
 *
 * The app's chrome is French on every product screen (WP-43, `CHROME_KEYS`):
 * the learner is reading a French publication, and the words on its furniture
 * are part of what they came for. Réglages is the one exception the owner
 * carved out on 2026-09-17, and the reason is that it is not a product screen
 * at all — it is the administrative surface. Nothing here teaches French.
 * Everything here is a consequence a learner has to understand *before* they
 * act: which address the account uses, what "supprimer définitivement" removes,
 * why a save was refused. A learner who cannot yet read «Les modifications
 * n’ont pas pu être classées» must still be able to run their own account.
 *
 * So this table follows the learner's **native language**, not the control
 * language and not the publication's French. `settingsCopy('de')` is the whole
 * screen in German; `settingsCopy('en')` in English; `settingsCopy('fr')` keeps
 * the French the design was written in, verbatim.
 *
 * Three rules this file exists to enforce:
 *
 *  1. **Every learner-facing string on the page is a key here.** Section
 *     titles, row labels and hints, button labels, validation messages, toasts,
 *     confirmations, the `<title>`. If a sentence is rendered, it is in this
 *     table — that is what the source scan in tests/test_settings_language.py
 *     checks.
 *  2. **Nothing here is data.** CEFR codes (`A1`, `B2.1`), the learner's own
 *     name, their email, times, XP numbers and speeds are values, not copy, and
 *     stay exactly as the account holds them. Where a code and a word sit
 *     together the code is interpolated and only the word is translated.
 *  3. **English is the floor.** An account whose `native_language` is Spanish
 *     or unset gets the whole screen in English rather than a half-translated
 *     one.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export const SETTINGS_LANGUAGES: ControlLanguage[] = ['en', 'de', 'fr'];

/**
 * The same normalization `lib/atelier-v2-copy.ts` performs — `de`, `de-DE`,
 * `de_AT`, `DE`, `  fr  ` all resolve to their base language, anything else to
 * English. It is restated here rather than imported because that module pulls
 * the whole journey copy table in at runtime, and this file has to stay
 * requirable on its own by `lib/settings-copy.test.js`.
 */
function normalizeSettingsLanguage(value: unknown): ControlLanguage {
  if (typeof value !== 'string') return 'en';
  const base = value.trim().toLowerCase().replace('_', '-').split('-')[0];
  return (SETTINGS_LANGUAGES as string[]).includes(base) ? (base as ControlLanguage) : 'en';
}

export type SettingsCopyKey =
  // Page furniture
  | 'page_title'
  | 'headline'
  | 'page_label'
  | 'kicker_fallback'
  | 'loading_status'
  | 'jump_label'
  // Sections
  | 'section_profile'
  | 'section_learning'
  | 'section_practice'
  | 'section_notifications'
  | 'section_appearance'
  | 'section_audio'
  | 'section_privacy'
  // Load failure
  | 'load_error_kicker'
  | 'load_error_headline'
  | 'load_error_title'
  | 'load_error_body'
  | 'action_retry'
  // Shared furniture
  | 'switch_on'
  | 'switch_off'
  | 'action_cancel'
  | 'action_confirm'
  | 'action_open'
  // Dossier / profile
  | 'row_account'
  | 'row_display_name'
  | 'display_name_placeholder'
  | 'row_admin'
  | 'row_admin_hint'
  | 'row_change_email'
  | 'row_change_email_hint'
  | 'field_new_email'
  | 'field_current_password'
  | 'action_save_email'
  | 'row_change_password'
  | 'row_change_password_hint'
  | 'field_new_password'
  | 'action_save_password'
  // Langues
  | 'row_native_language'
  | 'row_target_language'
  | 'language_de'
  | 'language_en'
  | 'language_fr'
  | 'language_es'
  | 'language_it'
  | 'row_placement'
  | 'row_placement_hint'
  | 'action_placement'
  | 'row_rehearsal'
  | 'row_rehearsal_hint'
  | 'row_dossier'
  | 'row_dossier_hint'
  | 'row_feedback'
  | 'row_feedback_hint'
  | 'action_feedback'
  | 'row_level'
  | 'level_current'
  | 'level_a1_name'
  | 'level_a1_hint'
  | 'level_a2_name'
  | 'level_a2_hint'
  | 'level_b1_name'
  | 'level_b1_hint'
  | 'level_b2_name'
  | 'level_b2_hint'
  | 'level_c1_name'
  | 'level_c1_hint'
  | 'level_c2_name'
  | 'level_c2_hint'
  | 'row_topics'
  | 'row_topics_hint'
  | 'topic_placeholder'
  | 'action_add_topic'
  | 'topics_selected'
  | 'row_correction'
  | 'correction_strict_hint'
  | 'correction_moderate_hint'
  | 'correction_lenient_hint'
  | 'correction_lenient'
  | 'correction_moderate'
  | 'correction_strict'
  | 'row_explanations'
  | 'row_explanations_hint'
  | 'row_address'
  | 'address_feminine'
  | 'address_masculine'
  | 'address_neutral'
  | 'address_feminine_hint'
  | 'address_masculine_hint'
  | 'address_neutral_hint'
  // Rythme
  | 'rhythm_title'
  | 'rhythm_hint'
  | 'rhythm_line_leger'
  | 'rhythm_line_regulier'
  | 'rhythm_line_soutenu'
  | 'rhythm_line_intensif'
  | 'rhythm_recommended'
  | 'rhythm_forecast'
  | 'minutes_short'
  | 'row_cefr'
  | 'row_cefr_hint'
  | 'row_xp'
  | 'field_other_xp'
  | 'row_new_words'
  | 'row_new_words_hint'
  | 'row_direction'
  | 'row_direction_hint'
  | 'direction_mixed'
  // Notifications
  | 'card_device_title'
  | 'card_device_hint'
  | 'action_link_device'
  | 'notif_practice'
  | 'notif_practice_hint'
  | 'notif_streak'
  | 'notif_streak_hint'
  | 'notif_weekly'
  | 'notif_weekly_hint'
  | 'notif_serial'
  | 'notif_serial_hint'
  | 'row_reminder_time'
  // Apparence
  | 'row_theme'
  | 'row_theme_hint'
  | 'theme_light'
  | 'theme_dark'
  | 'theme_system'
  | 'row_font_size'
  | 'row_font_size_hint'
  | 'font_small'
  | 'font_medium'
  | 'font_large'
  // Voix
  | 'row_voice_input'
  | 'row_voice_input_hint'
  | 'row_tts'
  | 'row_tts_hint'
  | 'row_autoplay'
  | 'row_autoplay_hint'
  | 'row_listen_first'
  | 'row_listen_first_hint'
  | 'row_sounds'
  | 'row_sounds_hint'
  | 'row_tts_speed'
  | 'speed_slow'
  | 'speed_fast'
  | 'speed_valuetext'
  // Données
  | 'row_export'
  | 'row_export_hint'
  | 'action_export'
  | 'pending_export'
  | 'row_signout_all'
  | 'row_signout_all_hint'
  | 'action_signout_all'
  | 'pending_signout_all'
  | 'row_delete'
  | 'row_delete_hint'
  | 'action_delete'
  | 'pending_delete'
  // Saving
  | 'action_save'
  | 'pending_save'
  | 'save_done'
  | 'save_failed'
  | 'save_failed_fields'
  | 'save_blocked'
  // Confirmations and account outcomes
  | 'confirm_delete_account'
  | 'confirm_delete_account_label'
  | 'delete_account_failed'
  | 'confirm_signout_all'
  | 'signout_all_done'
  | 'signout_all_failed'
  | 'password_incomplete'
  | 'password_changed'
  | 'password_failed'
  | 'email_incomplete'
  | 'email_changed'
  | 'email_failed'
  | 'export_ready'
  | 'export_failed'
  // Device notifications
  | 'push_ios_unavailable'
  | 'push_ios_connecting'
  | 'push_ios_linked'
  | 'push_ios_failed'
  | 'push_unsupported'
  | 'push_connecting'
  | 'push_denied'
  | 'push_not_configured'
  | 'push_linked'
  | 'push_failed'
  | 'push_unknown_error';

export type SettingsCopy = Record<SettingsCopyKey, string>;

const EN: SettingsCopy = {
  page_title: 'Account · Settings',
  headline: 'Settings',
  page_label: 'Settings',
  kicker_fallback: 'Reader',
  loading_status: 'Opening your file…',
  jump_label: 'Settings sections',

  section_profile: 'Account',
  section_learning: 'Languages',
  section_practice: 'Pace',
  section_notifications: 'Notifications',
  section_appearance: 'Appearance',
  section_audio: 'Voice',
  section_privacy: 'Data',

  load_error_kicker: 'File unavailable',
  load_error_headline: 'Your settings could not be loaded.',
  load_error_title: 'The file stayed shut.',
  load_error_body: 'Your file could not be loaded. Try again before changing your preferences.',
  action_retry: 'Try again',

  switch_on: 'on',
  switch_off: 'off',
  action_cancel: 'Cancel',
  action_confirm: 'Confirm',
  action_open: 'Open',

  row_account: 'Account',
  row_display_name: 'Display name',
  display_name_placeholder: 'Your name',
  row_admin: 'Operations · cost & quality',
  row_admin_hint: 'Dashboard reserved for the editorial team',
  row_change_email: 'Change your address',
  row_change_email_hint: 'Change your sign-in address.',
  field_new_email: 'New address',
  field_current_password: 'Current password',
  action_save_email: 'Save the new address',
  row_change_password: 'Change your password',
  row_change_password_hint: 'Eight characters at least.',
  field_new_password: 'New password',
  action_save_password: 'Save the new password',

  row_native_language: 'Your own language',
  row_target_language: 'Language you are learning',
  language_de: 'German',
  language_en: 'English',
  language_fr: 'French',
  language_es: 'Spanish',
  language_it: 'Italian',
  row_placement: 'Level check',
  row_placement_hint: 'Five minutes, in French.',
  action_placement: 'Take the check again',
  row_rehearsal: 'Rehearse a real situation',
  row_rehearsal_hint: 'Rehearse a real errand once.',
  row_dossier: 'Your file',
  row_dossier_hint: 'What we know, and why.',
  row_feedback: 'Report a problem',
  row_feedback_hint: 'Tell us about this screen.',
  action_feedback: 'Write',
  row_level: 'Current level',
  level_current: 'current',
  level_a1_name: 'Beginner',
  level_a1_hint: 'Essential phrases and expressions',
  level_a2_name: 'Elementary',
  level_a2_hint: 'Simple everyday exchanges',
  level_b1_name: 'Intermediate',
  level_b1_hint: 'Coping in most situations',
  level_b2_name: 'Independent',
  level_b2_hint: 'Speaking with spontaneity',
  level_c1_name: 'Advanced',
  level_c1_hint: 'Complex texts and discussions',
  level_c2_name: 'Mastery',
  level_c2_hint: 'Close to a native speaker',
  row_topics: 'Subjects for the newsroom',
  row_topics_hint: 'Subjects for your articles.',
  topic_placeholder: 'Add a subject',
  action_add_topic: 'Add',
  topics_selected: 'Kept:',
  row_correction: 'How much is corrected',
  correction_strict_hint: 'Every form will be corrected.',
  correction_moderate_hint: 'Important mistakes will be corrected.',
  correction_lenient_hint: 'Only mistakes that blur meaning.',
  correction_lenient: 'Light',
  correction_moderate: 'Balanced',
  correction_strict: 'Full',
  row_explanations: 'Show the explanations',
  row_explanations_hint: 'A note with every correction.',
  row_address: 'How the story addresses you',
  address_feminine: 'Feminine',
  address_masculine: 'Masculine',
  address_neutral: 'Neutral',
  address_feminine_hint: 'Characters use the feminine.',
  address_masculine_hint: 'Characters use the masculine.',
  address_neutral_hint: 'No gendered forms or pet names.',
  rhythm_title: 'Your rhythm',
  rhythm_hint: 'More practice, never more story.',
  rhythm_line_leger: 'The episode, your reply and a few quick reviews.',
  rhythm_line_regulier: 'Reviews first, the episode with practice, two reply turns.',
  rhythm_line_soutenu: 'Like Régulier, with twice the reviews and practice.',
  rhythm_line_intensif: 'Like Soutenu, with the most reviews and practice.',
  rhythm_recommended: 'recommended',
  // WP-L8: the planning prior, never a promise.
  rhythm_forecast: 'Estimate: {target} in {low}–{high} months at this rhythm.',
  minutes_short: 'min',
  row_cefr: 'CEFR target',
  row_cefr_hint: 'Estimated from your real pace.',
  row_xp: 'Daily XP marker',
  field_other_xp: 'Another marker (10 to 500)',
  row_new_words: 'New words per day',
  row_new_words_hint: '≈ {low}–{high} reviews a day.',
  row_direction: 'Card direction',
  row_direction_hint: 'Glosses: German or English only.',
  direction_mixed: 'Alternating',

  card_device_title: 'Receive the edition on this device',
  card_device_hint: 'Connect this device once.',
  action_link_device: 'Connect this device',
  notif_practice: 'Edition reminder',
  notif_practice_hint: 'A daily reminder, your time.',
  notif_streak: 'Streak in progress',
  notif_streak_hint: 'When your streak can grow.',
  notif_weekly: 'Weekly report',
  notif_weekly_hint: 'A progress summary every week',
  notif_serial: 'Serial',
  notif_serial_hint: 'The next episode, when ready.',
  row_reminder_time: 'Delivery time',

  row_theme: 'Paper',
  row_theme_hint: 'Light, dark, or the device setting',
  theme_light: 'Light',
  theme_dark: 'Dark',
  theme_system: 'System',
  row_font_size: 'Body text',
  row_font_size_hint: 'Applies everywhere, right away.',
  font_small: 'Small',
  font_medium: 'Medium',
  font_large: 'Large',

  row_voice_input: 'Answer out loud',
  row_voice_input_hint: 'Allow spoken practice through the microphone',
  row_tts: 'Read aloud',
  row_tts_hint: 'Hear how words are pronounced',
  row_autoplay: 'Play automatically',
  row_autoplay_hint: 'Play a word’s audio automatically.',
  row_listen_first: 'Listen first',
  row_listen_first_hint: 'Guess, listen, check, then read.',
  row_sounds: 'Sounds',
  row_sounds_hint: 'Tones for right, wrong, done.',
  row_tts_speed: 'Reading speed',
  speed_slow: 'Slow',
  speed_fast: 'Fast',
  speed_valuetext: 'times normal speed',

  row_export: 'Export your archives',
  row_export_hint: 'Words, progress and distinctions.',
  action_export: 'Prepare the JSON archive',
  pending_export: 'Preparing…',
  row_signout_all: 'Close every session',
  row_signout_all_hint: 'Sign out every device.',
  action_signout_all: 'Sign out everywhere',
  pending_signout_all: 'Closing…',
  row_delete: 'Permanent deletion',
  row_delete_hint: 'Everything, forever. No undo.',
  action_delete: 'Delete the account',
  pending_delete: 'Deleting…',

  action_save: 'File the changes',
  pending_save: 'Filing…',
  save_done: 'Changes filed.',
  save_failed: 'The changes could not be filed.',
  save_failed_fields: 'The changes could not be filed:',
  save_blocked: 'Reload the file before filing your changes.',

  confirm_delete_account:
    'Permanently delete this account and all its data? This cannot be undone.',
  confirm_delete_account_label: 'Delete the account',
  delete_account_failed: 'The account could not be deleted. Try again.',
  confirm_signout_all: 'Close every session, including this one?',
  signout_all_done: 'Every session is closed.',
  signout_all_failed: 'The sessions could not be closed.',
  password_incomplete: 'Enter your current password and a new password of at least 8 characters.',
  password_changed: 'Password changed. Sign in again.',
  password_failed: 'The password could not be changed.',
  email_incomplete: 'Enter the new address and your current password.',
  email_changed: 'Address changed. Sign in again.',
  email_failed: 'The address could not be changed.',
  export_ready: 'Archive ready.',
  export_failed: 'The archive could not be prepared.',

  push_ios_unavailable: 'Notifications are not available in this iPhone version.',
  push_ios_connecting: 'Connecting iPhone notifications…',
  push_ios_linked: 'iPhone notifications connected.',
  push_ios_failed: 'iPhone notifications could not be connected.',
  push_unsupported: 'This browser does not support notifications.',
  push_connecting: 'Connecting notifications…',
  push_denied: 'Permission refused. Check this device’s settings.',
  push_not_configured: 'Notifications are not configured yet.',
  push_linked: 'Notifications connected.',
  push_failed: 'Could not connect:',
  push_unknown_error: 'unknown error',
};

const DE: SettingsCopy = {
  page_title: 'Verwaltung · Einstellungen',
  headline: 'Einstellungen',
  page_label: 'Einstellungen',
  kicker_fallback: 'Leser',
  loading_status: 'Ihre Akte wird geöffnet…',
  jump_label: 'Bereiche der Einstellungen',

  section_profile: 'Konto',
  section_learning: 'Sprachen',
  section_practice: 'Rhythmus',
  section_notifications: 'Mitteilungen',
  section_appearance: 'Darstellung',
  section_audio: 'Stimme',
  section_privacy: 'Daten',

  load_error_kicker: 'Akte nicht verfügbar',
  load_error_headline: 'Ihre Einstellungen konnten nicht geladen werden.',
  load_error_title: 'Die Akte blieb geschlossen.',
  load_error_body:
    'Ihre Akte konnte nicht geladen werden. Versuchen Sie es erneut, bevor Sie Einstellungen ändern.',
  action_retry: 'Erneut versuchen',

  switch_on: 'an',
  switch_off: 'aus',
  action_cancel: 'Abbrechen',
  action_confirm: 'Bestätigen',
  action_open: 'Öffnen',

  row_account: 'Konto',
  row_display_name: 'Angezeigter Name',
  display_name_placeholder: 'Ihr Name',
  row_admin: 'Steuerung · Kosten & Qualität',
  row_admin_hint: 'Übersicht nur für die Redaktion',
  row_change_email: 'Adresse ändern',
  row_change_email_hint: 'Ihre Anmeldeadresse ändern.',
  field_new_email: 'Neue Adresse',
  field_current_password: 'Aktuelles Passwort',
  action_save_email: 'Neue Adresse speichern',
  row_change_password: 'Passwort ändern',
  row_change_password_hint: 'Mindestens acht Zeichen.',
  field_new_password: 'Neues Passwort',
  action_save_password: 'Neues Passwort speichern',

  row_native_language: 'Ihre eigene Sprache',
  row_target_language: 'Sprache, die Sie lernen',
  language_de: 'Deutsch',
  language_en: 'Englisch',
  language_fr: 'Französisch',
  language_es: 'Spanisch',
  language_it: 'Italienisch',
  row_placement: 'Einstufung',
  row_placement_hint: 'Fünf Minuten, auf Französisch.',
  action_placement: 'Einstufung wiederholen',
  row_rehearsal: 'Eine echte Situation proben',
  row_rehearsal_hint: 'Einen echten Termin einmal proben.',
  row_dossier: 'Ihre Akte',
  row_dossier_hint: 'Was wir wissen, und warum.',
  row_feedback: 'Ein Problem melden',
  row_feedback_hint: 'Sagen Sie uns Ihre Meinung.',
  action_feedback: 'Schreiben',
  row_level: 'Aktuelles Niveau',
  level_current: 'aktuell',
  level_a1_name: 'Anfang',
  level_a1_hint: 'Wichtige Sätze und Wendungen',
  level_a2_name: 'Grundlagen',
  level_a2_hint: 'Einfache Gespräche des Alltags',
  level_b1_name: 'Mittelstufe',
  level_b1_hint: 'In den meisten Situationen zurechtkommen',
  level_b2_name: 'Selbstständig',
  level_b2_hint: 'Spontan sprechen',
  level_c1_name: 'Fortgeschritten',
  level_c1_hint: 'Komplexe Texte und Diskussionen',
  level_c2_name: 'Beherrschung',
  level_c2_hint: 'Nahe an einer Muttersprachlerin',
  row_topics: 'Themen der Redaktion',
  row_topics_hint: 'Themen für Ihre Artikel.',
  topic_placeholder: 'Thema hinzufügen',
  action_add_topic: 'Hinzufügen',
  topics_selected: 'Gewählt:',
  row_correction: 'Wie viel korrigiert wird',
  correction_strict_hint: 'Jede Form wird korrigiert.',
  correction_moderate_hint: 'Wichtige Fehler werden korrigiert.',
  correction_lenient_hint: 'Nur sinnstörende Fehler.',
  correction_lenient: 'Leicht',
  correction_moderate: 'Ausgewogen',
  correction_strict: 'Vollständig',
  row_explanations: 'Erklärungen anzeigen',
  row_explanations_hint: 'Jeder Korrektur eine ausführliche Notiz beilegen',
  row_address: 'Wie die Erzählung Sie anspricht',
  address_feminine: 'Weiblich',
  address_masculine: 'Männlich',
  address_neutral: 'Neutral',
  address_feminine_hint: 'Die Figuren sprechen weiblich an.',
  address_masculine_hint: 'Die Figuren sprechen männlich an.',
  address_neutral_hint: 'Keine Genderformen, keine Kosenamen.',
  rhythm_title: 'Ihr Rhythmus',
  rhythm_hint: 'Mehr Übung, nie mehr Geschichte.',
  rhythm_line_leger: 'Die Episode, Ihre Antwort und ein paar schnelle Wiederholungen.',
  rhythm_line_regulier: 'Erst Wiederholungen, dann die Episode mit Übungen, zwei Antwortrunden.',
  rhythm_line_soutenu: 'Wie Régulier, mit doppelt so viel Wiederholung und Übung.',
  rhythm_line_intensif: 'Wie Soutenu, mit der meisten Wiederholung und Übung.',
  rhythm_recommended: 'empfohlen',
  rhythm_forecast: 'Schätzung: {target} in {low}–{high} Monaten in diesem Rhythmus.',
  minutes_short: 'Min.',
  row_cefr: 'GER-Ziel',
  row_cefr_hint: 'Geschätzt nach Ihrem echten Tempo.',
  row_xp: 'Täglicher XP-Richtwert',
  field_other_xp: 'Anderer Richtwert (10 bis 500)',
  row_new_words: 'Neue Wörter pro Tag',
  row_new_words_hint: '≈ {low}–{high} Wiederholungen pro Tag.',
  row_direction: 'Richtung der Karten',
  row_direction_hint: 'Übersetzungen: nur Deutsch oder Englisch.',
  direction_mixed: 'Abwechselnd',

  card_device_title: 'Die Ausgabe auf diesem Gerät empfangen',
  card_device_hint: 'Dieses Gerät einmal verbinden.',
  action_link_device: 'Dieses Gerät verbinden',
  notif_practice: 'Erinnerung an die Ausgabe',
  notif_practice_hint: 'Eine tägliche Erinnerung zur gewählten Zeit',
  notif_streak: 'Laufende Serie',
  notif_streak_hint: 'Wenn Ihre Serie wachsen kann.',
  notif_weekly: 'Wochenbericht',
  notif_weekly_hint: 'Eine Bilanz des Fortschritts jede Woche',
  notif_serial: 'Fortsetzungsroman',
  notif_serial_hint: 'Die nächste Folge, sobald fertig.',
  row_reminder_time: 'Zustellzeit',

  row_theme: 'Papier',
  row_theme_hint: 'Hell, dunkel oder wie das Gerät.',
  theme_light: 'Hell',
  theme_dark: 'Dunkel',
  theme_system: 'System',
  row_font_size: 'Schriftgröße',
  row_font_size_hint: 'Gilt sofort überall.',
  font_small: 'Klein',
  font_medium: 'Mittel',
  font_large: 'Groß',

  row_voice_input: 'Laut antworten',
  row_voice_input_hint: 'Sprechen über das Mikrofon erlauben',
  row_tts: 'Vorlesen',
  row_tts_hint: 'Die Aussprache der Wörter hören',
  row_autoplay: 'Automatisch abspielen',
  row_autoplay_hint: 'Wörter automatisch vorlesen.',
  row_listen_first: 'Zuerst hören',
  row_listen_first_hint: 'Raten, hören, prüfen, dann lesen.',
  row_sounds: 'Töne',
  row_sounds_hint: 'Töne für richtig, falsch, geschafft.',
  row_tts_speed: 'Lesegeschwindigkeit',
  speed_slow: 'Langsam',
  speed_fast: 'Schnell',
  speed_valuetext: 'mal die normale Geschwindigkeit',

  row_export: 'Ihre Unterlagen ausgeben',
  row_export_hint: 'Wörter, Fortschritt und Auszeichnungen.',
  action_export: 'JSON-Archiv vorbereiten',
  pending_export: 'Wird vorbereitet…',
  row_signout_all: 'Alle Sitzungen schließen',
  row_signout_all_hint: 'Alle Geräte abmelden.',
  action_signout_all: 'Überall abmelden',
  pending_signout_all: 'Wird geschlossen…',
  row_delete: 'Endgültige Löschung',
  row_delete_hint: 'Alles, für immer. Unwiderruflich.',
  action_delete: 'Konto löschen',
  pending_delete: 'Wird gelöscht…',

  action_save: 'Änderungen ablegen',
  pending_save: 'Wird abgelegt…',
  save_done: 'Änderungen abgelegt.',
  save_failed: 'Die Änderungen konnten nicht abgelegt werden.',
  save_failed_fields: 'Die Änderungen konnten nicht abgelegt werden:',
  save_blocked: 'Laden Sie die Akte neu, bevor Sie Ihre Änderungen ablegen.',

  confirm_delete_account:
    'Dieses Konto und alle seine Daten endgültig löschen? Das lässt sich nicht rückgängig machen.',
  confirm_delete_account_label: 'Konto löschen',
  delete_account_failed: 'Das Konto konnte nicht gelöscht werden. Versuchen Sie es erneut.',
  confirm_signout_all: 'Alle Sitzungen schließen, auch diese?',
  signout_all_done: 'Alle Sitzungen sind geschlossen.',
  signout_all_failed: 'Die Sitzungen konnten nicht geschlossen werden.',
  password_incomplete:
    'Geben Sie Ihr aktuelles Passwort und ein neues Passwort mit mindestens 8 Zeichen ein.',
  password_changed: 'Passwort geändert. Melden Sie sich neu an.',
  password_failed: 'Das Passwort konnte nicht geändert werden.',
  email_incomplete: 'Geben Sie die neue Adresse und Ihr aktuelles Passwort ein.',
  email_changed: 'Adresse geändert. Melden Sie sich neu an.',
  email_failed: 'Die Adresse konnte nicht geändert werden.',
  export_ready: 'Archiv bereit.',
  export_failed: 'Das Archiv konnte nicht vorbereitet werden.',

  push_ios_unavailable: 'Mitteilungen sind in dieser iPhone-Version nicht verfügbar.',
  push_ios_connecting: 'iPhone-Mitteilungen werden verbunden…',
  push_ios_linked: 'iPhone-Mitteilungen verbunden.',
  push_ios_failed: 'Die iPhone-Mitteilungen konnten nicht verbunden werden.',
  push_unsupported: 'Dieser Browser unterstützt keine Mitteilungen.',
  push_connecting: 'Mitteilungen werden verbunden…',
  push_denied: 'Erlaubnis verweigert. Prüfen Sie die Einstellungen dieses Geräts.',
  push_not_configured: 'Mitteilungen sind noch nicht eingerichtet.',
  push_linked: 'Mitteilungen verbunden.',
  push_failed: 'Verbindung nicht möglich:',
  push_unknown_error: 'unbekannter Fehler',
};

/**
 * French, kept verbatim from the artboard. A French native reads the screen
 * the designer wrote; nobody else is shown it by default.
 */
const FR: SettingsCopy = {
  page_title: 'L’administration · Réglages',
  headline: 'Réglages',
  page_label: 'Réglages',
  kicker_fallback: 'Lecteur',
  loading_status: 'Ouverture de votre dossier…',
  jump_label: 'Sections des réglages',

  section_profile: 'Dossier',
  section_learning: 'Langues',
  section_practice: 'Rythme',
  section_notifications: 'Notifications',
  section_appearance: 'Apparence',
  section_audio: 'Voix',
  section_privacy: 'Données',

  load_error_kicker: 'Dossier indisponible',
  load_error_headline: 'Vos réglages n’ont pas pu être chargés.',
  load_error_title: 'Le dossier est resté fermé.',
  load_error_body:
    'Votre dossier n’a pas pu être chargé. Réessayez avant de modifier vos préférences.',
  action_retry: 'Réessayer',

  switch_on: 'activé',
  switch_off: 'désactivé',
  action_cancel: 'Annuler',
  action_confirm: 'Confirmer',
  action_open: 'Ouvrir',

  row_account: 'Compte',
  row_display_name: 'Nom affiché',
  display_name_placeholder: 'Votre nom',
  row_admin: 'Pilotage · coût & qualité',
  row_admin_hint: 'Réservé à la rédaction.',
  row_change_email: 'Modifier l’adresse',
  row_change_email_hint: 'Changer votre adresse de connexion.',
  field_new_email: 'Nouvelle adresse',
  field_current_password: 'Mot de passe actuel',
  action_save_email: 'Enregistrer la nouvelle adresse',
  row_change_password: 'Modifier le mot de passe',
  row_change_password_hint: 'Huit caractères au moins.',
  field_new_password: 'Nouveau mot de passe',
  action_save_password: 'Enregistrer le nouveau mot de passe',

  row_native_language: 'Langue d’appui',
  row_target_language: 'Langue apprise',
  language_de: 'Allemand',
  language_en: 'Anglais',
  language_fr: 'Français',
  language_es: 'Espagnol',
  language_it: 'Italien',
  row_placement: 'Bilan de niveau',
  row_placement_hint: 'Cinq minutes, en français.',
  action_placement: 'Refaire le bilan',
  row_rehearsal: 'Répéter une vraie situation',
  row_rehearsal_hint: 'Répéter une vraie démarche.',
  row_dossier: 'Votre dossier',
  row_dossier_hint: 'Ce que nous savons, et pourquoi.',
  row_feedback: 'Signaler un problème',
  row_feedback_hint: 'Dites-nous ce que vous pensez.',
  action_feedback: 'Écrire',
  row_level: 'Niveau actuel',
  level_current: 'actuel',
  level_a1_name: 'Début',
  level_a1_hint: 'Phrases et expressions essentielles',
  level_a2_name: 'Élémentaire',
  level_a2_hint: 'Échanges simples du quotidien',
  level_b1_name: 'Intermédiaire',
  level_b1_hint: 'Se débrouiller presque partout',
  level_b2_name: 'Indépendant',
  level_b2_hint: 'Échanger avec spontanéité',
  level_c1_name: 'Avancé',
  level_c1_hint: 'Textes et discussions complexes',
  level_c2_name: 'Maîtrise',
  level_c2_hint: 'Aisance proche d’un locuteur natif',
  row_topics: 'Sujets de la rédaction',
  row_topics_hint: 'Les sujets de vos articles.',
  topic_placeholder: 'Ajouter un sujet',
  action_add_topic: 'Ajouter',
  topics_selected: 'Retenus :',
  row_correction: 'Intensité des corrections',
  correction_strict_hint: 'Toutes les formes seront corrigées.',
  correction_moderate_hint: 'Les erreurs importantes seront corrigées.',
  correction_lenient_hint: 'Seulement ce qui gêne le sens.',
  correction_lenient: 'Légère',
  correction_moderate: 'Équilibrée',
  correction_strict: 'Complète',
  row_explanations: 'Afficher les explications',
  row_explanations_hint: 'Une note par correction.',
  row_address: 'Comment le récit s’adresse à vous',
  address_feminine: 'Féminin',
  address_masculine: 'Masculin',
  address_neutral: 'Neutre',
  address_feminine_hint: 'Les personnages vous parleront au féminin.',
  address_masculine_hint: 'Les personnages vous parleront au masculin.',
  address_neutral_hint: 'Sans formes genrées ni petits noms.',
  rhythm_title: 'Votre rythme',
  rhythm_hint: 'Plus de pratique, jamais plus d’histoire.',
  rhythm_line_leger: 'L’épisode, votre réponse et quelques rappels rapides.',
  rhythm_line_regulier: 'Des rappels d’abord, l’épisode avec ses exercices, deux tours de réponse.',
  rhythm_line_soutenu: 'Comme Régulier, avec deux fois plus de rappels et d’exercices.',
  rhythm_line_intensif: 'Comme Soutenu, avec le plus de rappels et d’exercices.',
  rhythm_recommended: 'conseillé',
  rhythm_forecast: 'Estimation : {target} en {low} à {high} mois à ce rythme.',
  minutes_short: 'min',
  row_cefr: 'Objectif CECRL',
  row_cefr_hint: 'Estimée selon votre rythme réel.',
  row_xp: 'Repère XP quotidien',
  field_other_xp: 'Autre repère (10 à 500)',
  row_new_words: 'Nouveaux mots par jour',
  row_new_words_hint: '≈ {low}–{high} révisions par jour.',
  row_direction: 'Sens des cartes',
  row_direction_hint: 'Traductions : allemand ou anglais seulement.',
  direction_mixed: 'Alterné',

  card_device_title: 'Recevoir l’édition sur cet appareil',
  card_device_hint: 'Reliez cet appareil une fois.',
  action_link_device: 'Relier cet appareil',
  notif_practice: 'Rappel de l’édition',
  notif_practice_hint: 'Un rappel quotidien à l’heure choisie',
  notif_streak: 'Série en cours',
  notif_streak_hint: 'Quand votre série peut grandir.',
  notif_weekly: 'Relevé hebdomadaire',
  notif_weekly_hint: 'Un bilan de progression chaque semaine',
  notif_serial: 'Feuilleton',
  notif_serial_hint: 'La suite, dès qu’elle paraît.',
  row_reminder_time: 'Heure de livraison',

  row_theme: 'Papier',
  row_theme_hint: 'Clair, sombre ou comme l’appareil.',
  theme_light: 'Clair',
  theme_dark: 'Sombre',
  theme_system: 'Système',
  row_font_size: 'Corps du texte',
  row_font_size_hint: 'S’applique partout, tout de suite.',
  font_small: 'Petit',
  font_medium: 'Moyen',
  font_large: 'Grand',

  row_voice_input: 'Réponses à l’oral',
  row_voice_input_hint: 'Autoriser la pratique parlée au micro',
  row_tts: 'Lecture à voix haute',
  row_tts_hint: 'Écouter la prononciation des mots',
  row_autoplay: 'Lecture automatique',
  row_autoplay_hint: 'Lire le mot automatiquement.',
  row_listen_first: 'Écouter d’abord',
  row_listen_first_hint: 'Deviner, écouter, vérifier, puis lire.',
  row_sounds: 'Sons',
  row_sounds_hint: 'Un son : juste, faux, terminé.',
  row_tts_speed: 'Vitesse de lecture',
  speed_slow: 'Lente',
  speed_fast: 'Rapide',
  speed_valuetext: 'fois la vitesse normale',

  row_export: 'Exporter vos archives',
  row_export_hint: 'Mots, progression et distinctions.',
  action_export: 'Préparer l’archive JSON',
  pending_export: 'Préparation…',
  row_signout_all: 'Fermer toutes les sessions',
  row_signout_all_hint: 'Déconnecter tous les appareils.',
  action_signout_all: 'Tout déconnecter',
  pending_signout_all: 'Fermeture…',
  row_delete: 'Suppression définitive',
  row_delete_hint: 'Tout, pour toujours. Irréversible.',
  action_delete: 'Supprimer le compte',
  pending_delete: 'Suppression…',

  action_save: 'Classer les modifications',
  pending_save: 'Classement…',
  save_done: 'Modifications classées.',
  save_failed: 'Les modifications n’ont pas pu être classées.',
  save_failed_fields: 'Les modifications n’ont pas pu être classées :',
  save_blocked: 'Rechargez le dossier avant de classer les modifications.',

  confirm_delete_account:
    'Supprimer définitivement ce compte et toutes ses données ? Cette action est irréversible.',
  confirm_delete_account_label: 'Supprimer le compte',
  delete_account_failed: 'Le compte n’a pas pu être supprimé. Réessayez.',
  confirm_signout_all: 'Fermer toutes les sessions, y compris celle-ci ?',
  signout_all_done: 'Toutes les sessions sont fermées.',
  signout_all_failed: 'Les sessions n’ont pas pu être fermées.',
  password_incomplete:
    'Saisissez votre mot de passe actuel et un nouveau mot de passe d’au moins 8 caractères.',
  password_changed: 'Mot de passe modifié. Reconnectez-vous.',
  password_failed: 'Le mot de passe n’a pas pu être modifié.',
  email_incomplete: 'Saisissez la nouvelle adresse et votre mot de passe actuel.',
  email_changed: 'Adresse modifiée. Reconnectez-vous.',
  email_failed: 'L’adresse n’a pas pu être modifiée.',
  export_ready: 'Archive prête.',
  export_failed: 'L’archive n’a pas pu être préparée.',

  push_ios_unavailable: 'Les notifications ne sont pas disponibles dans cette version iPhone.',
  push_ios_connecting: 'Connexion des notifications iPhone…',
  push_ios_linked: 'Notifications iPhone reliées.',
  push_ios_failed: 'Les notifications iPhone n’ont pas pu être reliées.',
  push_unsupported: 'Ce navigateur ne prend pas en charge les notifications.',
  push_connecting: 'Connexion des notifications…',
  push_denied: 'Permission refusée. Vérifiez les réglages de cet appareil.',
  push_not_configured: 'Les notifications ne sont pas encore configurées.',
  push_linked: 'Notifications reliées.',
  push_failed: 'Connexion impossible :',
  push_unknown_error: 'erreur inconnue',
};

const TABLES: Record<ControlLanguage, SettingsCopy> = { en: EN, de: DE, fr: FR };

export const SETTINGS_COPY_KEYS = Object.keys(EN) as SettingsCopyKey[];

/**
 * The administrative screen in the learner's own language.
 *
 * Anything unrecognised — Spanish, `null`, a locale we do not have a table for
 * — resolves to English, never to a half-translated screen and never to the
 * publication's French.
 */
export function settingsCopy(language: unknown): SettingsCopy {
  return TABLES[normalizeSettingsLanguage(language)];
}

/**
 * Which language the screen should speak, in the order the owner decided:
 * the account's `native_language` first, then whatever control language the
 * page already resolved, then English.
 *
 * `null` for the first argument is the honest value *before* the account has
 * answered — and it resolves to English, not to French, so a screen can never
 * paint French and then swap.
 */
export function resolveSettingsLanguage(
  nativeLanguage: unknown,
  controlLanguage?: unknown,
): ControlLanguage {
  if (typeof nativeLanguage === 'string' && nativeLanguage.trim()) {
    return normalizeSettingsLanguage(nativeLanguage);
  }
  if (typeof controlLanguage === 'string' && controlLanguage.trim()) {
    return normalizeSettingsLanguage(controlLanguage);
  }
  return 'en';
}
