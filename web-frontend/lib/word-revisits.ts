/**
 * WP-93 — «Revu dans l'épisode du 12 sept.»: the episodes that brought a word
 * back, as the word biography prints them.
 *
 * The payload's `revisited_in: [{ date, scene_title_fr }]` is read defensively
 * (older servers send none). Rows are newest first, one per episode and date,
 * at most three — the biography is a word's story, not a log. The date is
 * printed in the learner's chrome locale; a calendar date («2026-09-12») is a
 * day, not an instant, so it is formatted as that day in every timezone.
 *
 * Pure: no React. Unit-tested with `node --test`.
 */

export type WordRevisit = { date?: unknown; scene_title_fr?: unknown };

export type WordRevisitRow = {
  key: string;
  /** «Revu dans l’épisode du 12 sept.» */
  label: string;
  /** The episode's French title (content), or empty. */
  title: string;
};

export const MAX_REVISIT_ROWS = 3;

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A sortable instant for the entry, or `null` when its date is not a date. */
function instant(value: unknown): { at: number; dateOnly: boolean } | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  const text = value.trim();
  const day = text.match(DATE_ONLY);
  if (day) {
    const at = Date.UTC(Number(day[1]), Number(day[2]) - 1, Number(day[3]));
    return Number.isNaN(at) ? null : { at, dateOnly: true };
  }
  const at = new Date(text).getTime();
  return Number.isNaN(at) ? null : { at, dateOnly: false };
}

/** «12 sept.» / «12 Sep» / «12. Sept.» — day and short month, in `locale`. */
export function formatRevisitDate(value: unknown, locale: string): string {
  const parsed = instant(value);
  if (!parsed) return '';
  const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  if (parsed.dateOnly) options.timeZone = 'UTC';
  try {
    return new Intl.DateTimeFormat(locale, options).format(new Date(parsed.at));
  } catch {
    return new Intl.DateTimeFormat('fr-FR', options).format(new Date(parsed.at));
  }
}

/**
 * The rows to print: dated entries only, newest first, one per (date, title),
 * at most `max`. `template` carries `{date}`.
 */
export function revisitRows(
  entries: WordRevisit[] | null | undefined,
  locale: string,
  template: string,
  max: number = MAX_REVISIT_ROWS,
): WordRevisitRow[] {
  if (!Array.isArray(entries)) return [];
  const dated = entries
    .map((entry, index) => ({ entry, index, parsed: instant(entry?.date) }))
    .filter((item) => item.parsed !== null)
    .sort((a, b) => (b.parsed!.at - a.parsed!.at) || a.index - b.index);
  const seen = new Set<string>();
  const rows: WordRevisitRow[] = [];
  for (const { entry, parsed } of dated) {
    const title = typeof entry.scene_title_fr === 'string' ? entry.scene_title_fr.trim() : '';
    const date = formatRevisitDate(entry.date, locale);
    const key = `${parsed!.at}:${title}`;
    if (!date || seen.has(key)) continue;
    seen.add(key);
    rows.push({ key, label: template.replace('{date}', date), title });
    if (rows.length >= max) break;
  }
  return rows;
}
