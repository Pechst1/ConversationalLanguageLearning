/**
 * WP-98 / WP-99 — the words of «Pendant votre absence», the season's front
 * page and the interlude, by the one language rule (`lib/language-rule.ts`):
 * the learner's language up to A2, French from B1.
 *
 * French in every column, because they are printed marks and names, not
 * chrome: «Entre-temps», «Saison {n}», «La Forge», «Le Courrier». Everything
 * a character says, a meanwhile line, a season's title and logline and the
 * interlude's reason are story and arrive as `*_fr` from the server.
 *
 * `{name}` placeholders are filled with `srFill`.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';

const FR = {
  lang: 'fr',
  // ---- printed marks (French in every column)
  entre_temps_mark: 'Entre-temps',
  season_n: 'Saison {n}',
  forge_name: 'La Forge',
  courrier_name: 'Le Courrier',
  // ---- «Pendant votre absence» (WP-99)
  absence_title: 'Pendant votre absence',
  absence_days_one: 'Un jour sans vous',
  absence_days_many: '{n} jours sans vous',
  absence_lines_aria: 'Ce qui s’est passé entre-temps',
  lapsed_title: 'Courrier en souffrance',
  lapsed_line: 'La lettre de {name}',
  lapsed_open: 'Ouvrir la lettre de {name} dans le Courrier',
  lapsed_line_anon: 'Une lettre restée sans réponse',
  lapsed_open_anon: 'Ouvrir la lettre dans le Courrier',
  absence_resume: 'Reprendre l’histoire',
  absence_skip: 'Passer',
  // ---- «Nouvelle saison» (WP-98)
  premiere_kicker: 'Nouvelle saison',
  premiere_open: 'Ouvrir la saison',
  premiere_poster_alt: 'La première planche de la saison {n}',
  premiere_aria: 'Saison {n} — {title}',
  // ---- the interlude (WP-98)
  interlude_kicker: 'Entre deux saisons',
  interlude_returns: 'L’histoire reprend le {date}.',
  interlude_paused: 'Le feuilleton fait une pause.',
  interlude_meanwhile: 'En attendant',
  interlude_forge_hint: 'La règle du jour, en exercices',
  interlude_courrier_hint: 'Vos lettres',
  interlude_relecture: 'Relire les archives',
  interlude_relecture_hint: 'Les planches de la saison passée',
  // ---- «La suite demain» on Home
  teaser_label: 'La suite demain',
};

export type SeasonReturnCopy = { [K in keyof typeof FR]: string };

const EN: SeasonReturnCopy = {
  lang: 'en',
  entre_temps_mark: 'Entre-temps',
  season_n: 'Saison {n}',
  forge_name: 'La Forge',
  courrier_name: 'Le Courrier',
  absence_title: 'While you were away',
  absence_days_one: 'One day without you',
  absence_days_many: '{n} days without you',
  absence_lines_aria: 'What happened in the meantime',
  lapsed_title: 'Letters left waiting',
  lapsed_line: 'The letter from {name}',
  lapsed_open: 'Open the letter from {name} in the Courrier',
  lapsed_line_anon: 'A letter left unanswered',
  lapsed_open_anon: 'Open the letter in the Courrier',
  absence_resume: 'Back to the story',
  absence_skip: 'Skip',
  premiere_kicker: 'New season',
  premiere_open: 'Open the season',
  premiere_poster_alt: 'The first panel of season {n}',
  premiere_aria: 'Season {n} — {title}',
  interlude_kicker: 'Between two seasons',
  interlude_returns: 'The story comes back on {date}.',
  interlude_paused: 'The serial is taking a break.',
  interlude_meanwhile: 'Until then',
  interlude_forge_hint: 'Today’s rule, as exercises',
  interlude_courrier_hint: 'Your letters',
  interlude_relecture: 'Reread the archive',
  interlude_relecture_hint: 'The pages of last season',
  teaser_label: 'Tomorrow',
};

const DE: SeasonReturnCopy = {
  lang: 'de',
  entre_temps_mark: 'Entre-temps',
  season_n: 'Saison {n}',
  forge_name: 'La Forge',
  courrier_name: 'Le Courrier',
  absence_title: 'Während du weg warst',
  absence_days_one: 'Ein Tag ohne dich',
  absence_days_many: '{n} Tage ohne dich',
  absence_lines_aria: 'Was in der Zwischenzeit geschah',
  lapsed_title: 'Liegengebliebene Post',
  lapsed_line: 'Der Brief von {name}',
  lapsed_open: 'Den Brief von {name} im Courrier öffnen',
  lapsed_line_anon: 'Ein unbeantworteter Brief',
  lapsed_open_anon: 'Den Brief im Courrier öffnen',
  absence_resume: 'Zurück zur Geschichte',
  absence_skip: 'Überspringen',
  premiere_kicker: 'Neue Staffel',
  premiere_open: 'Staffel öffnen',
  premiere_poster_alt: 'Die erste Seite von Staffel {n}',
  premiere_aria: 'Staffel {n} — {title}',
  interlude_kicker: 'Zwischen zwei Staffeln',
  interlude_returns: 'Die Geschichte geht am {date} weiter.',
  interlude_paused: 'Die Fortsetzungsgeschichte macht eine Pause.',
  interlude_meanwhile: 'Bis dahin',
  interlude_forge_hint: 'Die Regel des Tages, als Übungen',
  interlude_courrier_hint: 'Deine Briefe',
  interlude_relecture: 'Das Archiv nachlesen',
  interlude_relecture_hint: 'Die Seiten der letzten Staffel',
  teaser_label: 'Morgen',
};

const TABLES: Record<ControlLanguage, SeasonReturnCopy> = { en: EN, de: DE, fr: FR as SeasonReturnCopy };

export const SEASON_RETURN_TABLES = TABLES;

/** The chrome in the language `chromeLanguage()` resolved; none given keeps French. */
export function seasonReturnCopy(language?: unknown): SeasonReturnCopy {
  if (language === null || language === undefined || language === '') return TABLES.fr;
  return TABLES[normalizeControlLanguage(language)];
}

/** `{name}`-style placeholders filled in; an unknown key is left as written. */
export function srFill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

export default seasonReturnCopy;
