/**
 * WP-96 / WP-97 — the words of «Archives du journal», «Le trombinoscope»,
 * «Précédemment» and the margin notes, by the one language rule
 * (`lib/language-rule.ts`): the learner's language up to A2, French from B1.
 *
 * French in every column, because they are names or printed marks, not
 * chrome: the places («Archives du journal», «Le trombinoscope»), «Tome N»,
 * «Nº N» and the colophon «Fin du chapitre». Everything a character says, a
 * chapter's title, its digest line, the learner's own lines and a margin
 * note's sentence are story and arrive as `*_fr` from the server.
 *
 * `{name}` placeholders are filled with `faFill`.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';

const FR = {
  lang: 'fr',
  // ---- names and printed marks (French in every column)
  archive_title: 'Archives du journal',
  cast_title: 'Le trombinoscope',
  chapter_end: 'Fin du chapitre',
  tome_n: 'Tome {n}',
  edition_n: 'Nº {n}',
  // ---- the archive
  nav_aria: 'Le Feuilleton',
  season_n: 'Saison {n}',
  season_pages_one: 'Saison {season} · une planche',
  season_pages_many: 'Saison {season} · {n} planches',
  pages_one: 'une planche',
  pages_many: '{n} planches',
  chapter_n: 'Chapitre {n}',
  chapter_running: 'en cours',
  tome_aria: 'Tome {n} — saison terminée',
  tome_open: 'Ouvrir le tome',
  archive_loading: 'Ouverture des archives…',
  archive_failed_title: 'Les archives ne répondent pas.',
  archive_failed_body: 'Vos planches sont en sécurité. Réessayez dans un instant.',
  retry: 'Réessayer',
  archive_empty_title: 'Aucune planche classée pour l’instant.',
  archive_empty_body: 'Chaque scène jouée dans la séance est classée ici, avec votre réplique.',
  open_seance: 'Ouvrir la séance',
  today_kicker: 'Aujourd’hui',
  today_open: 'Lire l’épisode du jour',
  // ---- one day, reread
  back_archive: 'Retour aux archives',
  reply_label: 'La réplique de l’abonné·e',
  reply_none: 'Ce jour-là, vous n’avez rien répondu.',
  ending_label: 'Le dénouement',
  to_reply: 'Votre réplique',
  page_unavailable: 'Cette planche ne peut pas être rouverte ici.',
  open_page: 'Ouvrir la planche',
  day_missing: 'Cette planche n’est pas dans les archives.',
  // ---- margin notes
  margin_aria: 'Notes en marge',
  margin_open: 'Ouvrir la planche du {date}',
  // ---- le trombinoscope
  trust_label: 'Confiance',
  trust_aria: 'Confiance : {n} sur 5',
  trust_none: 'Pas encore d’échange',
  register_tu_since: 'tu depuis le {date}',
  register_tu: 'tu',
  register_vous: 'vous',
  known_label: 'Ce que {name} sait de vous',
  known_none: '{name} ne sait encore rien de vous.',
  cast_failed: 'Le trombinoscope ne répond pas.',
  // ---- «Précédemment»
  previously: 'Précédemment',
  previously_aria: 'Précédemment dans le feuilleton',
  read: 'Lire',
  // ---- the recap
  tome_finished: 'La saison {n} est terminée : elle est reliée en tome.',
  // ---- WP-98: a new season is a new volume
  volume_new: 'Nouveau volume',
  volume_first_pages: 'Les premières planches arrivent.',
};

export type ArchiveCopy = { [K in keyof typeof FR]: string };

const EN: ArchiveCopy = {
  lang: 'en',
  archive_title: 'Archives du journal',
  cast_title: 'Le trombinoscope',
  chapter_end: 'Fin du chapitre',
  tome_n: 'Tome {n}',
  edition_n: 'Nº {n}',
  nav_aria: 'Le Feuilleton',
  season_n: 'Season {n}',
  season_pages_one: 'Season {season} · one page',
  season_pages_many: 'Season {season} · {n} pages',
  pages_one: 'one page',
  pages_many: '{n} pages',
  chapter_n: 'Chapter {n}',
  chapter_running: 'in progress',
  tome_aria: 'Tome {n} — season finished',
  tome_open: 'Open the volume',
  archive_loading: 'Opening the archive…',
  archive_failed_title: 'The archive did not answer.',
  archive_failed_body: 'Your pages are safe. Try again in a moment.',
  retry: 'Try again',
  archive_empty_title: 'No pages filed yet.',
  archive_empty_body: 'Every scene you play in the session is filed here, with your reply.',
  open_seance: 'Open the session',
  today_kicker: 'Today',
  today_open: 'Read today’s episode',
  back_archive: 'Back to the archive',
  reply_label: 'Your reply',
  reply_none: 'You did not reply that day.',
  ending_label: 'How it ended',
  to_reply: 'Your reply',
  page_unavailable: 'This page can’t be reopened here.',
  open_page: 'Open the page',
  day_missing: 'This page is not in the archive.',
  margin_aria: 'Margin notes',
  margin_open: 'Open the page of {date}',
  trust_label: 'Trust',
  trust_aria: 'Trust: {n} of 5',
  trust_none: 'No exchange yet',
  register_tu_since: 'tu since {date}',
  register_tu: 'tu',
  register_vous: 'vous · formal',
  known_label: 'What {name} knows about you',
  known_none: '{name} doesn’t know anything about you yet.',
  cast_failed: 'The cast did not load.',
  previously: 'Previously',
  previously_aria: 'Previously in the story',
  read: 'Read',
  tome_finished: 'Season {n} is finished: it is bound as a volume.',
  volume_new: 'New volume',
  volume_first_pages: 'The first pages are on their way.',
};

const DE: ArchiveCopy = {
  lang: 'de',
  archive_title: 'Archives du journal',
  cast_title: 'Le trombinoscope',
  chapter_end: 'Fin du chapitre',
  tome_n: 'Tome {n}',
  edition_n: 'Nº {n}',
  nav_aria: 'Le Feuilleton',
  season_n: 'Staffel {n}',
  season_pages_one: 'Staffel {season} · eine Seite',
  season_pages_many: 'Staffel {season} · {n} Seiten',
  pages_one: 'eine Seite',
  pages_many: '{n} Seiten',
  chapter_n: 'Kapitel {n}',
  chapter_running: 'läuft',
  tome_aria: 'Tome {n} — Staffel abgeschlossen',
  tome_open: 'Band öffnen',
  archive_loading: 'Das Archiv wird geöffnet …',
  archive_failed_title: 'Das Archiv antwortet nicht.',
  archive_failed_body: 'Deine Seiten sind sicher. Versuch es gleich noch einmal.',
  retry: 'Erneut versuchen',
  archive_empty_title: 'Noch keine Seiten abgelegt.',
  archive_empty_body: 'Jede Szene aus der Sitzung wird hier abgelegt, mit deiner Antwort.',
  open_seance: 'Sitzung öffnen',
  today_kicker: 'Heute',
  today_open: 'Die Folge von heute lesen',
  back_archive: 'Zurück zum Archiv',
  reply_label: 'Deine Antwort',
  reply_none: 'An diesem Tag hast du nichts geantwortet.',
  ending_label: 'Wie es ausging',
  to_reply: 'Deine Antwort',
  page_unavailable: 'Diese Seite lässt sich hier nicht wieder öffnen.',
  open_page: 'Seite öffnen',
  day_missing: 'Diese Seite ist nicht im Archiv.',
  margin_aria: 'Randnotizen',
  margin_open: 'Die Seite vom {date} öffnen',
  trust_label: 'Vertrauen',
  trust_aria: 'Vertrauen: {n} von 5',
  trust_none: 'Noch kein Austausch',
  register_tu_since: 'tu seit {date}',
  register_tu: 'tu',
  register_vous: 'vous · förmlich',
  known_label: 'Was {name} über dich weiß',
  known_none: '{name} weiß noch nichts über dich.',
  cast_failed: 'Die Figuren konnten nicht geladen werden.',
  previously: 'Bisher',
  previously_aria: 'Bisher in der Geschichte',
  read: 'Lesen',
  tome_finished: 'Staffel {n} ist abgeschlossen: Sie ist als Band gebunden.',
  volume_new: 'Neuer Band',
  volume_first_pages: 'Die ersten Seiten sind unterwegs.',
};

const TABLES: Record<ControlLanguage, ArchiveCopy> = { en: EN, de: DE, fr: FR as ArchiveCopy };

/** The chrome in the language `chromeLanguage()` resolved; none given keeps French. */
export function archiveCopy(language?: unknown): ArchiveCopy {
  if (language === null || language === undefined || language === '') return TABLES.fr;
  return TABLES[normalizeControlLanguage(language)];
}

/** `{name}`-style placeholders filled in; an unknown key is left as written. */
export function faFill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

type PluralStem = 'season_pages' | 'pages';

/** One of a `_one` / `_many` pair, by count. */
export function faPlural(copy: ArchiveCopy, stem: PluralStem, n: number, extra: Record<string, string | number> = {}): string {
  const key = `${stem}_${n === 1 ? 'one' : 'many'}` as keyof ArchiveCopy;
  return faFill(copy[key], { n, ...extra });
}

const MONTHS: Record<ControlLanguage, string[]> = {
  fr: ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  de: ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sept.', 'Okt.', 'Nov.', 'Dez.'],
};

/**
 * «12 sept.» / «12 Sep» / «12. Sept.» from a learner-local `YYYY-MM-DD`.
 * Read as a calendar date, never through `Date` (no timezone can move it).
 * Anything that is not such a date → ''.
 */
export function archiveDate(date: unknown, language?: unknown): string {
  const match = typeof date === 'string' ? date.trim().match(/^(\d{4})-(\d{2})-(\d{2})/) : null;
  if (!match) return '';
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return '';
  const lang = language === null || language === undefined || language === '' ? 'fr' : normalizeControlLanguage(language);
  const name = MONTHS[lang][month - 1];
  return lang === 'de' ? `${day}. ${name}` : `${day} ${name}`;
}

export default archiveCopy;
