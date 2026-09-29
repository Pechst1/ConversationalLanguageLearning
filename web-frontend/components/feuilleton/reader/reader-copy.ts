/**
 * The paged reader's own words, under WP-82's one language rule
 * (`lib/language-rule.ts`).
 *
 * Up to A2 the reader's chrome — the buttons, the position, the state lines,
 * the word-help sheet — is in the learner's language; from B1 it is French.
 * The story itself (the panels' lines, captions, the chapter's title, the
 * cliffhanger) is content and stays French whatever this table says.
 *
 * The caller resolves the language: the daily journey passes its screen's
 * chrome language; a caller that passes nothing keeps the French table, which
 * is what the reader printed before it had one.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type ReaderCopy = {
  reader_label: string;
  exit: string;
  progress: string;
  /** «Planche {n} sur {count}» */
  position_panel: string;
  /** «Fin de l’épisode, {n} sur {count}» */
  position_end: string;
  previously: string;
  already_read: string;
  your_turn: string;
  translate_panel: string;
  hide_translation: string;
  translate: string;
  translating: string;
  no_translation: string;
  task_locked: string;
  filed: string;
  nav_label: string;
  go_end: string;
  /** «Aller à la planche {n}» */
  go_panel: string;
  prev_label: string;
  prev: string;
  next: string;
  read_on: string;
  complete: string;
  completing: string;
  episode_end: string;
  to_follow: string;
  plate_alt: string;
  page_alt: string;
  art_printing: string;
  art_missing: string;
  answer_sent: string;
  verdict_branch: string;
  verdict_ok: string;
  verdict_retry: string;
  options_label: string;
  answer_label: string;
  answer_placeholder: string;
  checking: string;
  send: string;
  // Word help
  help_close_label: string;
  help_kicker: string;
  help_close: string;
  help_searching: string;
  help_sentence_only: string;
  /** «Dans la réplique de {name}» */
  help_in_line_of: string;
  help_in_panel: string;
  help_note: string;
  roledescription: string;
  // WP-90 «La planche»
  /** The folio ribbon on a plate whose drawing is still on the press: «Planche {n} · sous presse». */
  art_on_press: string;
  /** The face is the play button: «Écouter {name}». */
  listen_to: string;
  /** A tappable word's label, in the learner's language: «Aide pour « {word} »». */
  word_help: string;
  /** The running head once the headline has folded: «{title} · {n}/{count}». */
  running_head: string;
  /** The finale's eyebrow — the red-triangle last panel. */
  finale_label: string;
  // WP-92 «Rayons X»
  /** The toggle's short word in the bar. */
  rayons: string;
  /** The toggle's name: what it does. */
  rayons_label: string;
  /** The one-line legend while the marks are on: «Aujourd’hui : {title}». */
  rayons_legend: string;
  /** What a screen reader hears once per marked line: «La règle du jour : {form}». */
  rayons_form: string;
  /** Portrait alt text: «{name}, {mood}». Moods follow. */
  portrait_alt: string;
  mood_happy: string;
  mood_happy_f: string;
  mood_cross: string;
  mood_cross_f: string;
  mood_moved: string;
  mood_moved_f: string;
};

const FR: ReaderCopy = {
  reader_label: 'Lecteur du feuilleton',
  exit: 'Quitter la lecture',
  progress: 'Avancement dans l’épisode',
  position_panel: 'Planche {n} sur {count}',
  position_end: 'Fin de l’épisode, {n} sur {count}',
  previously: 'Précédemment',
  already_read: 'Déjà lu · vous relisez cette planche',
  your_turn: 'À vous de répondre sur cette planche',
  translate_panel: 'Traduire la case',
  hide_translation: 'Masquer la traduction',
  translate: 'Traduire',
  translating: 'Traduction…',
  no_translation: 'Aucune traduction disponible pour l’instant.',
  task_locked: 'Cette réplique s’ouvre après celle qui la précède dans l’épisode.',
  filed: 'Épisode classé',
  nav_label: 'Navigation dans l’épisode',
  go_end: 'Aller à la fin de l’épisode',
  go_panel: 'Aller à la planche {n}',
  prev_label: 'Planche précédente',
  prev: 'Précédent',
  next: 'Suivant',
  read_on: 'Lire la suite',
  complete: 'Terminer l’épisode',
  completing: 'Classement…',
  episode_end: 'Fin de l’épisode',
  to_follow: 'À suivre',
  plate_alt: 'Planche : {title}',
  page_alt: 'La page illustrée de cette édition',
  art_printing: 'L’illustration de cette planche est encore sous presse. Le texte est complet.',
  art_missing: 'Cette planche est parue sans illustration.',
  answer_sent: 'Votre réponse, déjà envoyée',
  verdict_branch: 'Choix pris en compte',
  verdict_ok: 'Acceptée',
  verdict_retry: 'Reprise classée',
  options_label: 'Répliques possibles',
  answer_label: 'Votre réponse',
  answer_placeholder: 'Écrivez une phrase courte.',
  checking: 'Relecture…',
  send: 'Envoyer',
  help_close_label: 'Fermer l’aide',
  help_kicker: 'Aide au mot',
  help_close: 'Fermer',
  help_searching: 'Recherche…',
  help_sentence_only: 'Pas d’entrée pour ce mot seul — voici la phrase.',
  help_in_line_of: 'Dans la réplique de {name}',
  help_in_panel: 'Dans la planche',
  help_note: 'Consulter l’aide ne compte pas comme une réponse et ne fait pas avancer l’épisode.',
  roledescription: 'planche',
  art_on_press: 'Planche {n} · sous presse',
  listen_to: 'Écouter {name}',
  word_help: 'Aide pour « {word} »',
  running_head: '{title} · {n}/{count}',
  finale_label: 'Case finale',
  rayons: 'Rayons X',
  rayons_label: 'Montrer la règle du jour dans la page',
  rayons_legend: 'Aujourd’hui : {title}',
  rayons_form: 'La règle du jour : {form}',
  portrait_alt: '{name}, {mood}',
  mood_happy: 'ravi',
  mood_happy_f: 'ravie',
  mood_cross: 'fâché',
  mood_cross_f: 'fâchée',
  mood_moved: 'ému',
  mood_moved_f: 'émue',
};

const EN: ReaderCopy = {
  reader_label: 'Story reader',
  exit: 'Leave the reader',
  progress: 'Progress through the episode',
  position_panel: 'Panel {n} of {count}',
  position_end: 'End of the episode, {n} of {count}',
  previously: 'Previously',
  already_read: 'Already read · you are rereading this panel',
  your_turn: 'Your turn to answer on this panel',
  translate_panel: 'Translate the panel',
  hide_translation: 'Hide the translation',
  translate: 'Translate',
  translating: 'Translating…',
  no_translation: 'No translation available yet.',
  task_locked: 'This line opens after the one before it in the episode.',
  filed: 'Episode filed',
  nav_label: 'Episode navigation',
  go_end: 'Go to the end of the episode',
  go_panel: 'Go to panel {n}',
  prev_label: 'Previous panel',
  prev: 'Previous',
  next: 'Next',
  read_on: 'Read on',
  complete: 'Finish the episode',
  completing: 'Filing…',
  episode_end: 'End of the episode',
  to_follow: 'To be continued',
  plate_alt: 'Panel: {title}',
  page_alt: 'This edition’s illustrated page',
  art_printing: 'This panel’s picture is still being drawn. The text is complete.',
  art_missing: 'This panel came out without a picture.',
  answer_sent: 'Your answer, already sent',
  verdict_branch: 'Choice noted',
  verdict_ok: 'Accepted',
  verdict_retry: 'Saved for another try',
  options_label: 'Possible replies',
  answer_label: 'Your answer',
  answer_placeholder: 'Write a short sentence.',
  checking: 'Checking…',
  send: 'Send',
  help_close_label: 'Close word help',
  help_kicker: 'Word help',
  help_close: 'Close',
  help_searching: 'Looking it up…',
  help_sentence_only: 'No entry for this word alone — here is the sentence.',
  help_in_line_of: 'In {name}’s line',
  help_in_panel: 'In the panel',
  help_note: 'Looking a word up is not an answer and does not move the episode on.',
  roledescription: 'panel',
  art_on_press: 'Panel {n} · on the press',
  listen_to: 'Listen to {name}',
  word_help: 'Help with “{word}”',
  running_head: '{title} · {n}/{count}',
  finale_label: 'The last panel',
  rayons: 'X-ray',
  rayons_label: 'Show today’s rule in the page',
  rayons_legend: 'Today: {title}',
  rayons_form: 'Today’s rule: {form}',
  portrait_alt: '{name}, {mood}',
  mood_happy: 'pleased',
  mood_happy_f: 'pleased',
  mood_cross: 'cross',
  mood_cross_f: 'cross',
  mood_moved: 'moved',
  mood_moved_f: 'moved',
};

const DE: ReaderCopy = {
  reader_label: 'Geschichte lesen',
  exit: 'Lesen beenden',
  progress: 'Fortschritt in der Folge',
  position_panel: 'Bild {n} von {count}',
  position_end: 'Ende der Folge, {n} von {count}',
  previously: 'Bisher',
  already_read: 'Schon gelesen · du liest dieses Bild noch einmal',
  your_turn: 'Du bist dran: antworte zu diesem Bild',
  translate_panel: 'Bild übersetzen',
  hide_translation: 'Übersetzung ausblenden',
  translate: 'Übersetzen',
  translating: 'Wird übersetzt…',
  no_translation: 'Noch keine Übersetzung verfügbar.',
  task_locked: 'Diese Zeile öffnet sich nach der vorherigen in der Folge.',
  filed: 'Folge abgelegt',
  nav_label: 'Navigation in der Folge',
  go_end: 'Zum Ende der Folge',
  go_panel: 'Zu Bild {n}',
  prev_label: 'Vorheriges Bild',
  prev: 'Zurück',
  next: 'Weiter',
  read_on: 'Weiterlesen',
  complete: 'Folge beenden',
  completing: 'Wird abgelegt…',
  episode_end: 'Ende der Folge',
  to_follow: 'Fortsetzung folgt',
  plate_alt: 'Bild: {title}',
  page_alt: 'Die illustrierte Seite dieser Ausgabe',
  art_printing: 'Das Bild zu dieser Szene wird noch gezeichnet. Der Text ist vollständig.',
  art_missing: 'Dieses Bild ist ohne Illustration erschienen.',
  answer_sent: 'Deine Antwort, schon gesendet',
  verdict_branch: 'Wahl übernommen',
  verdict_ok: 'Angenommen',
  verdict_retry: 'Für später vorgemerkt',
  options_label: 'Mögliche Antworten',
  answer_label: 'Deine Antwort',
  answer_placeholder: 'Schreib einen kurzen Satz.',
  checking: 'Wird geprüft…',
  send: 'Senden',
  help_close_label: 'Worthilfe schließen',
  help_kicker: 'Worthilfe',
  help_close: 'Schließen',
  help_searching: 'Wird gesucht…',
  help_sentence_only: 'Kein Eintrag für dieses Wort allein — hier ist der Satz.',
  help_in_line_of: 'In der Zeile von {name}',
  help_in_panel: 'Im Bild',
  help_note: 'Nachschlagen zählt nicht als Antwort und bringt die Folge nicht weiter.',
  roledescription: 'Bild',
  art_on_press: 'Bild {n} · in Druck',
  listen_to: '{name} anhören',
  word_help: 'Hilfe zu „{word}“',
  running_head: '{title} · {n}/{count}',
  finale_label: 'Das letzte Bild',
  rayons: 'Röntgen',
  rayons_label: 'Die Regel des Tages im Text zeigen',
  rayons_legend: 'Heute: {title}',
  rayons_form: 'Regel des Tages: {form}',
  portrait_alt: '{name}, {mood}',
  mood_happy: 'froh',
  mood_happy_f: 'froh',
  mood_cross: 'verärgert',
  mood_cross_f: 'verärgert',
  mood_moved: 'gerührt',
  mood_moved_f: 'gerührt',
};

const TABLES: Record<ControlLanguage, ReaderCopy> = { en: EN, de: DE, fr: FR };

/** The reader's chrome in `language`; French when none is given. */
export function readerCopy(language?: ControlLanguage | null): ReaderCopy {
  return (language && TABLES[language]) || FR;
}

/** Fill `{name}` placeholders. */
export function fillReaderCopy(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}

/** The drawn cast members written in the feminine (French adjectives agree). */
const FEMININE_CAST = new Set(['romy_tremblay', 'lila_bonnet', 'margaux_barman']);

/**
 * WP-90: a portrait's alt text — «Margaux, ravie», «Gus, fâché», or the bare
 * name for a neutral face. In the reader's chrome language; French agrees with
 * the drawn cast member's gender and falls back to the masculine form for
 * anyone else.
 */
export function portraitAlt(
  t: ReaderCopy,
  name: string,
  mood: string | null | undefined,
  castId?: string | null,
): string {
  const who = String(name || '').trim();
  if (!who) return '';
  const feminine = Boolean(castId && FEMININE_CAST.has(castId));
  const word =
    mood === 'happy'
      ? feminine ? t.mood_happy_f : t.mood_happy
      : mood === 'cross'
        ? feminine ? t.mood_cross_f : t.mood_cross
        : mood === 'moved'
          ? feminine ? t.mood_moved_f : t.mood_moved
          : '';
  return word ? fillReaderCopy(t.portrait_alt, { name: who, mood: word }) : who;
}
