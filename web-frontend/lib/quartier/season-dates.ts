/**
 * Le Quartier · the season's date tokens (`{date:2026-11-18}`, `{date:2026-11-11|fr-dm}`) for the
 * quarter's own copy of a day, by the server's rule (`app/services/season/dates.py`): the bible's
 * day 1 (Wednesday 11 November 2026) moves by whole weeks to the Wednesday nearest the learner's
 * first day, never earlier. Pages from the engine come rendered; only the bundled copy needs this.
 */

const ANCHOR_UTC = Date.UTC(2026, 10, 11);
const DAY_MS = 86_400_000;
const TOKEN = /\{date:(\d{4})-(\d{2})-(\d{2})(?:\|([a-z-]+))?\}/g;

const WEEKDAYS = {
  fr: ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'],
  en: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
  de: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'],
} as const;
const MONTHS = {
  fr: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
} as const;
const FR_ABBR = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

/** Whole weeks from the bible's day 1 to the Wednesday nearest `start` (a local calendar day). */
export function shiftDays(start: Date | null | undefined): number {
  if (!(start instanceof Date) || Number.isNaN(start.getTime())) return 0;
  const day = Date.UTC(start.getFullYear(), start.getMonth(), start.getDate());
  const weeks = Math.round((day - ANCHOR_UTC) / DAY_MS / 7);
  return Math.max(0, weeks) * 7;
}

export function formatDate(day: Date, fmt = 'fr'): string {
  const [lang, form] = fmt.split('-') as ['fr' | 'en' | 'de', string | undefined];
  const d = day.getUTCDate();
  const m = day.getUTCMonth();
  const w = day.getUTCDay();
  if (lang === 'fr') {
    const n = d === 1 ? '1er' : String(d);
    if (form === 'abbr') return `${n} ${FR_ABBR[m]}`;
    const dm = `${n} ${MONTHS.fr[m]}`;
    if (form === 'dm') return dm;
    const weekday = WEEKDAYS.fr[w];
    return `${form === 'cap' ? weekday[0].toUpperCase() + weekday.slice(1) : weekday} ${dm}`;
  }
  if (lang === 'en') {
    const dm = `${d} ${MONTHS.en[m]}`;
    return form === 'dm' ? dm : `${WEEKDAYS.en[w]} ${dm}`;
  }
  const dm = `${d}. ${MONTHS.de[m]}`;
  return form === 'dm' ? dm : `${WEEKDAYS.de[w]}, ${dm}`;
}

export function renderText(text: string, shift = 0): string {
  if (!text.includes('{date')) return text;
  return text.replace(TOKEN, (_all, y: string, mo: string, d: string, fmt?: string) =>
    formatDate(new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d) + shift)), fmt || 'fr'),
  );
}

/** `value` with every date token rendered (a deep copy of objects and arrays). */
export function renderDates<T>(value: T, shift = 0): T {
  if (typeof value === 'string') return renderText(value, shift) as unknown as T;
  if (Array.isArray(value)) return value.map((item) => renderDates(item, shift)) as unknown as T;
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, renderDates(v, shift)])) as T;
  }
  return value;
}
