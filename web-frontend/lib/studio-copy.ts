/**
 * WP-82 — Le Studio (the audio page) follows the one language rule.
 *
 * The call's chrome — stages, buttons, the recap's counts, the help sheet —
 * is the learner's language up to A2 and French from B1 (`chromeLanguage`).
 * «Le Studio» is a place name and stays French; the character's lines, the
 * scene titles and the learner's own sentences are French content.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from './atelier-v2-copy';

export type StudioStatus = 'idle' | 'selecting' | 'starting' | 'listening' | 'processing' | 'speaking' | 'ended';

export type StudioCopy = {
  stage: Record<StudioStatus, string>;
  back_home: string;
  loading: string;
  intro_kicker: string;
  intro_lede: string;
  start: string;
  choose_scene: string;
  scenes_kicker: string;
  scene_notes: Record<'bakery' | 'directions' | 'restaurant_order', string>;
  back: string;
  preparing: string;
  your_turn: string;
  composing: string;
  speaks: string;
  someone: string;
  mute: string;
  unmute: string;
  stop_recording: string;
  show_text: string;
  hide_text: string;
  end_call: string;
  filed: string;
  sent: string;
  no_turns: string;
  turns_one: string;
  turns_many: string;
  longest: string;
  words_one: string;
  words_many: string;
  reused_one: string;
  reused_many: string;
  with_errors: string;
  no_errors: string;
  stat_duration: string;
  stat_turns: string;
  stat_produced: string;
  stat_reused: string;
  longest_label: string;
  corrections_label: string;
  tomorrow_label: string;
  new_call: string;
  help_kicker: string;
  help_title: string;
  help_body: string;
  end_title: string;
  end_body: string;
  keep_going: string;
  end_confirm: string;
  help: string;
  online: string;
  free_talk: string;
  start_failed: string;
  send_failed: string;
};

const FR: StudioCopy = {
  stage: {
    idle: 'Appel ouvert',
    selecting: 'Appel ouvert',
    starting: 'Ligne en préparation',
    listening: 'Appel en cours',
    processing: 'Appel en cours',
    speaking: 'Appel en cours',
    ended: 'Appel terminé',
  },
  back_home: 'Retour à La Une',
  loading: 'Chargement du Studio',
  intro_kicker: 'Conversation · 5 minutes',
  intro_lede: 'Votre histoire et vos mots du jour, à voix haute.',
  start: 'Commencer à parler',
  choose_scene: 'Choisir une scène',
  scenes_kicker: 'Autres scènes',
  scene_notes: {
    bakery: 'Commander sans préparer.',
    directions: 'Demander son chemin.',
    restaurant_order: 'Commander avec une contrainte.',
  },
  back: 'Retour',
  preparing: 'La ligne se prépare…',
  your_turn: 'À vous de parler',
  composing: 'La réponse arrive',
  speaks: '{name} parle',
  someone: 'Votre interlocuteur',
  mute: 'Couper le son',
  unmute: 'Rétablir le son',
  stop_recording: 'Arrêter l’enregistrement',
  show_text: 'Afficher le texte',
  hide_text: 'Masquer le texte',
  end_call: 'Terminer l’appel',
  filed: 'Terminé',
  sent: 'Conversation enregistrée.',
  no_turns: 'Aucun tour parlé : l’appel s’est arrêté avant votre première phrase.',
  turns_one: '{n} tour parlé',
  turns_many: '{n} tours parlés',
  longest: 'réponse la plus longue',
  words_one: '{n} mot',
  words_many: '{n} mots',
  reused_one: '{n} mot du jour réemployé',
  reused_many: '{n} mots du jour réemployés',
  with_errors: 'malgré {n} faute(s) de forme',
  no_errors: 'sans faute de forme',
  stat_duration: 'Durée',
  stat_turns: 'Tours',
  stat_produced: 'Mots produits',
  stat_reused: 'Mots repris',
  longest_label: 'Votre plus longue réponse',
  corrections_label: 'Corrections',
  tomorrow_label: 'Pour demain',
  new_call: 'Nouvel appel',
  help_kicker: 'Mode d’emploi',
  help_title: 'Le geste',
  help_body: 'Touchez le micro, parlez, puis touchez le carré. L’œil montre la dernière phrase.',
  end_title: 'Terminer cet appel ?',
  end_body: 'La conversation est ajoutée à votre journée.',
  keep_going: 'Continuer',
  end_confirm: 'Terminer',
  help: 'Aide',
  online: 'En ligne',
  free_talk: 'Conversation libre',
  start_failed: 'L’appel n’a pas pu commencer.',
  send_failed: 'La réponse n’a pas été envoyée. Vous pouvez reprendre.',
};

const EN: StudioCopy = {
  stage: {
    idle: 'Call open',
    selecting: 'Call open',
    starting: 'Connecting',
    listening: 'On a call',
    processing: 'On a call',
    speaking: 'On a call',
    ended: 'Call ended',
  },
  back_home: 'Back to La Une',
  loading: 'Loading Le Studio',
  intro_kicker: 'Conversation · 5 minutes',
  intro_lede: 'Your story and today’s words, out loud.',
  start: 'Start speaking',
  choose_scene: 'Choose a scene',
  scenes_kicker: 'Other scenes',
  scene_notes: {
    bakery: 'Order without preparing.',
    directions: 'Ask the way.',
    restaurant_order: 'Order with a constraint.',
  },
  back: 'Back',
  preparing: 'Connecting…',
  your_turn: 'Your turn to speak',
  composing: 'The reply is coming',
  speaks: '{name} is speaking',
  someone: 'The other person',
  mute: 'Mute',
  unmute: 'Unmute',
  stop_recording: 'Stop recording',
  show_text: 'Show the text',
  hide_text: 'Hide the text',
  end_call: 'End the call',
  filed: 'Done',
  sent: 'Conversation saved.',
  no_turns: 'No turns spoken: the call ended before your first sentence.',
  turns_one: '{n} turn spoken',
  turns_many: '{n} turns spoken',
  longest: 'longest answer',
  words_one: '{n} word',
  words_many: '{n} words',
  reused_one: '{n} word of the day reused',
  reused_many: '{n} words of the day reused',
  with_errors: 'despite {n} form mistake(s)',
  no_errors: 'no form mistakes',
  stat_duration: 'Duration',
  stat_turns: 'Turns',
  stat_produced: 'Words said',
  stat_reused: 'Words reused',
  longest_label: 'Your longest answer',
  corrections_label: 'Corrections',
  tomorrow_label: 'For tomorrow',
  new_call: 'New call',
  help_kicker: 'How it works',
  help_title: 'The gesture',
  help_body: 'Tap the mic, speak, then tap the square. The eye shows the last sentence.',
  end_title: 'End this call?',
  end_body: 'The conversation is added to your day.',
  keep_going: 'Keep going',
  end_confirm: 'End',
  help: 'Help',
  online: 'Online',
  free_talk: 'Free conversation',
  start_failed: 'The call could not start.',
  send_failed: 'Your reply was not sent. You can go on.',
};

const DE: StudioCopy = {
  stage: {
    idle: 'Anruf offen',
    selecting: 'Anruf offen',
    starting: 'Verbindung wird aufgebaut',
    listening: 'Im Gespräch',
    processing: 'Im Gespräch',
    speaking: 'Im Gespräch',
    ended: 'Anruf beendet',
  },
  back_home: 'Zurück zu La Une',
  loading: 'Le Studio wird geladen',
  intro_kicker: 'Gespräch · 5 Minuten',
  intro_lede: 'Deine Geschichte und die Wörter des Tages, laut gesprochen.',
  start: 'Sprechen',
  choose_scene: 'Szene wählen',
  scenes_kicker: 'Andere Szenen',
  scene_notes: {
    bakery: 'Bestellen ohne Vorbereitung.',
    directions: 'Nach dem Weg fragen.',
    restaurant_order: 'Mit einem Sonderwunsch bestellen.',
  },
  back: 'Zurück',
  preparing: 'Verbindung wird aufgebaut…',
  your_turn: 'Du bist dran',
  composing: 'Die Antwort kommt',
  speaks: '{name} spricht',
  someone: 'Dein Gegenüber',
  mute: 'Ton aus',
  unmute: 'Ton an',
  stop_recording: 'Aufnahme stoppen',
  show_text: 'Text zeigen',
  hide_text: 'Text ausblenden',
  end_call: 'Anruf beenden',
  filed: 'Fertig',
  sent: 'Gespräch gespeichert.',
  no_turns: 'Kein Beitrag: Der Anruf endete vor deinem ersten Satz.',
  turns_one: '{n} Beitrag',
  turns_many: '{n} Beiträge',
  longest: 'längste Antwort',
  words_one: '{n} Wort',
  words_many: '{n} Wörter',
  reused_one: '{n} Wort des Tages benutzt',
  reused_many: '{n} Wörter des Tages benutzt',
  with_errors: 'trotz {n} Formfehler(n)',
  no_errors: 'ohne Formfehler',
  stat_duration: 'Dauer',
  stat_turns: 'Beiträge',
  stat_produced: 'Gesagte Wörter',
  stat_reused: 'Benutzte Wörter',
  longest_label: 'Deine längste Antwort',
  corrections_label: 'Korrekturen',
  tomorrow_label: 'Für morgen',
  new_call: 'Neuer Anruf',
  help_kicker: 'So geht’s',
  help_title: 'Die Geste',
  help_body: 'Tippe aufs Mikrofon, sprich, dann tippe aufs Quadrat. Das Auge zeigt den letzten Satz.',
  end_title: 'Anruf beenden?',
  end_body: 'Das Gespräch wird deinem Tag hinzugefügt.',
  keep_going: 'Weitermachen',
  end_confirm: 'Beenden',
  help: 'Hilfe',
  online: 'Online',
  free_talk: 'Freies Gespräch',
  start_failed: 'Der Anruf konnte nicht starten.',
  send_failed: 'Deine Antwort wurde nicht gesendet. Du kannst weitermachen.',
};

const TABLES: Record<ControlLanguage, StudioCopy> = { en: EN, de: DE, fr: FR };

export function studioCopy(language: unknown): StudioCopy {
  return TABLES[normalizeControlLanguage(language)];
}

export function fillStudio(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}
