/**
 * WP-82 — the La Une press components follow the one language rule.
 *
 * The front page's own words — the ask, the buttons, the stamps, the press and
 * error notices, the aria-labels — are chrome: up to A2 the learner's
 * language, from B1 French (`chromeLanguage`, `lib/language-rule.ts`). The
 * headline, the byline's name, the quote, the recap and the concept arrive as
 * content and stay French. Place names (La Une, Le Feuilleton, Courrier,
 * La Bibliothèque, L’Atelier) are French in every column.
 *
 * No existing table fits: `journey-copy.ts` is the daily journey's step chrome
 * and `lib/atelier-v2-copy.ts` is the Atelier shell's; these components are the
 * newspaper front page's. Same keys and `{placeholders}` in every language.
 */

import type { ControlLanguage } from '@/types/daily-journey';
import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';

export type LaUneCopy = {
  streak_first_day: string;
  streak_days: string;
  filed: string;
  biblio_aria: string;
  biblio_deck: string;
  phrase_head: string;
  by: string;
  kicker_mission: string;
  kicker_episode: string;
  ask_speak: string;
  ask_write: string;
  ask_session: string;
  ask_review: string;
  ask_read: string;
  art_alt: string;
  press_title: string;
  press_body: string;
  late_title: string;
  late_body: string;
  stamp_sent: string;
  stamp_read: string;
  open_mission: string;
  open_episode: string;
  overrun: string;
  continue: string;
  adjust_time: string;
  en_bref: string;
  tomorrow: string;
  tomorrow_episode: string;
  tease: string;
  retry: string;
};

const fr: LaUneCopy = {
  streak_first_day: '1ᵉʳ jour',
  streak_days: '{n} jours de suite',
  filed: 'Bouclé',
  biblio_aria: 'Lire {title}, chapitre {n}',
  biblio_deck: 'Chapitre {n} · lecture du soir, sans exercice.',
  phrase_head: 'La phrase d’hier',
  by: 'par',
  kicker_mission: 'Courrier attendu · Épisode {ep}',
  kicker_episode: 'Le Feuilleton · Épisode {ep}',
  ask_speak: 'À vous de parler : cinq minutes de voix avec {name}.',
  ask_write: 'À vous d’écrire : une réponse à {name}.',
  ask_session: 'À vous de jouer : la séance du jour.',
  ask_review: 'À vous de réviser : le lexique du jour.',
  ask_read: 'À vous de lire : l’épisode du jour.',
  art_alt: 'Illustration — épisode {ep}',
  press_title: 'Sous presses',
  press_body: 'L’illustration de l’épisode {ep} est en cours d’impression.',
  late_title: 'Illustration retardée',
  late_body: 'L’image de cet épisode paraîtra dans une édition ultérieure. Le texte, lui, n’attend pas.',
  stamp_sent: 'Envoyé',
  stamp_read: 'Lu',
  open_mission: 'Répondre à la mission — {headline}',
  open_episode: 'Lire l’épisode — {headline}',
  overrun: 'Plus long que les {n} minutes demandées — vous pouvez vous arrêter quand vous voulez.',
  continue: 'Continuer',
  adjust_time: 'Ajuster le temps de l’édition',
  en_bref: 'En bref',
  tomorrow: 'Demain',
  tomorrow_episode: 'épisode {ep}',
  tease: 'Épisode {ep} : {tease}',
  retry: 'Réessayer',
};

const en: LaUneCopy = {
  streak_first_day: 'Day 1',
  streak_days: '{n} days in a row',
  filed: 'Filed',
  biblio_aria: 'Read {title}, chapter {n}',
  biblio_deck: 'Chapter {n} · evening reading, no exercises.',
  phrase_head: 'Yesterday’s sentence',
  by: 'by',
  kicker_mission: 'Courrier due · Episode {ep}',
  kicker_episode: 'Le Feuilleton · Episode {ep}',
  ask_speak: 'Your turn to speak: five minutes of voice with {name}.',
  ask_write: 'Your turn to write: a reply to {name}.',
  ask_session: 'Your turn: today’s session.',
  ask_review: 'Your turn to review: today’s words.',
  ask_read: 'Your turn to read: today’s episode.',
  art_alt: 'Illustration — episode {ep}',
  press_title: 'On the press',
  press_body: 'The illustration for episode {ep} is being printed.',
  late_title: 'Illustration delayed',
  late_body: 'This episode’s picture will appear in a later edition. The text doesn’t wait.',
  stamp_sent: 'Sent',
  stamp_read: 'Read',
  open_mission: 'Answer the mission — {headline}',
  open_episode: 'Read the episode — {headline}',
  overrun: 'Longer than the {n} minutes you asked for — you can stop whenever you like.',
  continue: 'Continue',
  adjust_time: 'Adjust the edition’s time',
  en_bref: 'In brief',
  tomorrow: 'Tomorrow',
  tomorrow_episode: 'episode {ep}',
  tease: 'Episode {ep}: {tease}',
  retry: 'Try again',
};

const de: LaUneCopy = {
  streak_first_day: 'Tag 1',
  streak_days: '{n} Tage in Folge',
  filed: 'Abgeschlossen',
  biblio_aria: '{title} lesen, Kapitel {n}',
  biblio_deck: 'Kapitel {n} · Abendlektüre, ohne Übungen.',
  phrase_head: 'Der Satz von gestern',
  by: 'von',
  kicker_mission: 'Courrier erwartet · Folge {ep}',
  kicker_episode: 'Le Feuilleton · Folge {ep}',
  ask_speak: 'Sie sind dran: fünf Minuten Sprechen mit {name}.',
  ask_write: 'Sie sind dran: eine Antwort an {name}.',
  ask_session: 'Sie sind dran: die Sitzung des Tages.',
  ask_review: 'Sie sind dran: die Wörter des Tages wiederholen.',
  ask_read: 'Sie sind dran: die Folge des Tages lesen.',
  art_alt: 'Illustration — Folge {ep}',
  press_title: 'In Druck',
  press_body: 'Die Illustration zu Folge {ep} wird gerade gedruckt.',
  late_title: 'Illustration verspätet',
  late_body: 'Das Bild zu dieser Folge erscheint in einer späteren Ausgabe. Der Text wartet nicht.',
  stamp_sent: 'Gesendet',
  stamp_read: 'Gelesen',
  open_mission: 'Auf die Mission antworten — {headline}',
  open_episode: 'Die Folge lesen — {headline}',
  overrun: 'Länger als die gewünschten {n} Minuten — Sie können jederzeit aufhören.',
  continue: 'Weiter',
  adjust_time: 'Zeit der Ausgabe anpassen',
  en_bref: 'Kurz gesagt',
  tomorrow: 'Morgen',
  tomorrow_episode: 'Folge {ep}',
  tease: 'Folge {ep}: {tease}',
  retry: 'Erneut versuchen',
};

export const LAUNE_COPY: Record<ControlLanguage, LaUneCopy> = { en, de, fr };

export function launeCopy(language: unknown): LaUneCopy {
  return LAUNE_COPY[normalizeControlLanguage(language)];
}

/** `fill('{n} jours de suite', { n: 3 })` → `3 jours de suite`. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (hole, key: string) =>
    key in values ? String(values[key]) : hole,
  );
}
