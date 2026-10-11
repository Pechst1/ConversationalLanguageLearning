/**
 * WP-122 A · La Radio — the chrome's words, one language per element (WP-82).
 *
 * The bulletin itself is French; everything around it is the learner's chrome
 * language. «La Radio», «Lire» and «C'est entendu» are the newspaper's own names and
 * stay French in every table, like «Le Papier».
 *
 * The La Une chip prints «La Radio» and says the length in its accessible name
 * («La Radio de Romy, 55 secondes»): the spec's «La Radio · 50 s» is four words, and
 * beside any two-word chip it breaks WP-81's 25-word Home (26 with the Revue chip in
 * `components/radio/radio.test.js`). Le Papier keeps its week in the label the same way.
 */

import type { RadioLanguage } from '@/lib/radio-types';

export type RadioCopy = {
  page_title: string;
  chip_label: string;
  chip_aria: string;
  back: string;
  listen: string;
  pause: string;
  resume: string;
  listen_again: string;
  loading_audio: string;
  read: string;
  read_aria: string;
  listen_first: string;
  progress_aria: string;
  audio_unavailable: string;
  transcript_title: string;
  dictee_title: string;
  dictee_lead: string;
  dictee_words: string;
  dictee_masked: string;
  check: string;
  checking: string;
  dictee_met: string;
  dictee_partial: string;
  dictee_not_yet: string;
  dictee_said: string;
  done: string;
  done_pending: string;
  heard_title: string;
  heard_body: string;
  back_home: string;
  loading: string;
  disabled_title: string;
  disabled_body: string;
  error_title: string;
  error_body: string;
  retry: string;
  nothing_title: string;
  nothing_body: string;
  mock_badge: string;
};

const FR: RadioCopy = {
  page_title: 'La Radio',
  chip_label: 'La Radio',
  chip_aria: 'La Radio de Romy, {s} secondes',
  back: 'Retour à La Une',
  listen: 'Écouter',
  pause: 'Pause',
  resume: 'Reprendre',
  listen_again: 'Réécouter',
  loading_audio: 'Le son arrive…',
  read: 'Lire',
  read_aria: 'Lire le texte maintenant',
  listen_first: 'Écoutez d’abord. Le texte vient après.',
  progress_aria: 'Bulletin écouté à {p} %',
  audio_unavailable: 'Le son ne passe pas pour l’instant. Voici le texte.',
  transcript_title: 'Le bulletin',
  dictee_title: 'Dictée',
  dictee_lead: 'Une phrase du bulletin. Écrivez ce que vous entendez.',
  dictee_words: '{n} mots',
  dictee_masked: 'la phrase de la dictée',
  check: 'Vérifier',
  checking: 'Vérification…',
  dictee_met: 'Exactement ce que Romy a dit.',
  dictee_partial: 'Presque : il ne manque que les accents.',
  dictee_not_yet: 'Réécoutez : voici ce qui a été dit.',
  dictee_said: 'Romy a dit',
  done: 'C’est entendu',
  done_pending: 'Un instant…',
  heard_title: 'C’est entendu.',
  heard_body: 'Le prochain bulletin passe demain.',
  back_home: 'Retour à La Une',
  loading: 'Romy se met au micro',
  disabled_title: 'La Radio se tait',
  disabled_body: 'Le bulletin n’est pas diffusé en ce moment.',
  error_title: 'Le bulletin ne passe pas',
  error_body: 'Nous n’avons pas pu le charger.',
  retry: 'Réessayer',
  nothing_title: 'Tout est entendu',
  nothing_body: 'Vous avez écouté tous les bulletins de la semaine.',
  mock_badge: 'Maquette',
};

const EN: RadioCopy = {
  page_title: 'La Radio',
  chip_label: 'La Radio',
  chip_aria: 'Romy’s radio bulletin, {s} seconds',
  back: 'Back to La Une',
  listen: 'Listen',
  pause: 'Pause',
  resume: 'Resume',
  listen_again: 'Listen again',
  loading_audio: 'Getting the sound…',
  read: 'Lire',
  read_aria: 'Read the text now',
  listen_first: 'Listen first. The text comes after.',
  progress_aria: '{p} % of the bulletin heard',
  audio_unavailable: 'The sound can’t be played right now. Here is the text.',
  transcript_title: 'The bulletin',
  dictee_title: 'Dictée',
  dictee_lead: 'One sentence from the bulletin. Write what you hear.',
  dictee_words: '{n} words',
  dictee_masked: 'the dictée sentence',
  check: 'Check',
  checking: 'Checking…',
  dictee_met: 'Exactly what Romy said.',
  dictee_partial: 'Almost: only the accents are missing.',
  dictee_not_yet: 'Listen again: this is what was said.',
  dictee_said: 'Romy said',
  done: 'C’est entendu',
  done_pending: 'One moment…',
  heard_title: 'C’est entendu.',
  heard_body: 'The next bulletin is on tomorrow.',
  back_home: 'Back to La Une',
  loading: 'Romy is getting to the microphone',
  disabled_title: 'La Radio is off the air',
  disabled_body: 'The bulletin isn’t broadcasting right now.',
  error_title: 'The bulletin didn’t load',
  error_body: 'We couldn’t fetch it.',
  retry: 'Try again',
  nothing_title: 'All heard',
  nothing_body: 'You have heard every bulletin this week.',
  mock_badge: 'Mock',
};

const DE: RadioCopy = {
  page_title: 'La Radio',
  chip_label: 'La Radio',
  chip_aria: 'Romys Radiobulletin, {s} Sekunden',
  back: 'Zurück zu La Une',
  listen: 'Anhören',
  pause: 'Pause',
  resume: 'Weiter',
  listen_again: 'Noch einmal',
  loading_audio: 'Der Ton wird geladen…',
  read: 'Lire',
  read_aria: 'Den Text jetzt lesen',
  listen_first: 'Erst hören. Der Text kommt danach.',
  progress_aria: '{p} % des Bulletins gehört',
  audio_unavailable: 'Der Ton lässt sich gerade nicht abspielen. Hier ist der Text.',
  transcript_title: 'Das Bulletin',
  dictee_title: 'Dictée',
  dictee_lead: 'Ein Satz aus dem Bulletin. Schreib, was du hörst.',
  dictee_words: '{n} Wörter',
  dictee_masked: 'der Diktatsatz',
  check: 'Prüfen',
  checking: 'Wird geprüft…',
  dictee_met: 'Genau, was Romy gesagt hat.',
  dictee_partial: 'Fast: nur die Akzente fehlen.',
  dictee_not_yet: 'Hör noch einmal hin: Das wurde gesagt.',
  dictee_said: 'Romy hat gesagt',
  done: 'C’est entendu',
  done_pending: 'Einen Moment…',
  heard_title: 'C’est entendu.',
  heard_body: 'Das nächste Bulletin läuft morgen.',
  back_home: 'Zurück zu La Une',
  loading: 'Romy geht ans Mikrofon',
  disabled_title: 'La Radio schweigt',
  disabled_body: 'Das Bulletin wird gerade nicht gesendet.',
  error_title: 'Das Bulletin lädt nicht',
  error_body: 'Wir konnten es nicht abrufen.',
  retry: 'Erneut versuchen',
  nothing_title: 'Alles gehört',
  nothing_body: 'Du hast alle Bulletins dieser Woche gehört.',
  mock_badge: 'Attrappe',
};

const TABLES: Record<RadioLanguage, RadioCopy> = { fr: FR, en: EN, de: DE };

export function radioCopy(language: unknown): RadioCopy {
  return TABLES[language === 'fr' || language === 'de' ? language : 'en'];
}

/** `{name}` placeholders filled; unknown ones left as they are. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}
