/**
 * A server timestamp as the learner's own clock reads it («08 h 12»).
 *
 * The API stores UTC. A stamp with no zone («2026-10-24T02:06:00») is still
 * UTC, but `new Date()` would read it as the device's local time and print the
 * UTC hour («02 h 06» at 04:06 in Berlin). So a zoneless ISO string is given
 * its `Z` before it is parsed, and the hours and minutes are then read in the
 * device's time zone.
 */

const HAS_ZONE = /(?:Z|[+-]\d{2}(?::?\d{2})?)$/i;
const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/;

/** Parse a server timestamp; a zoneless ISO date-time is UTC. `null` when it is not a date. */
export function parseServerTime(raw: unknown): Date | null {
  if (raw instanceof Date) return Number.isNaN(raw.getTime()) ? null : raw;
  if (typeof raw !== 'string' && typeof raw !== 'number') return null;
  let value: string | number = raw;
  if (typeof value === 'string') {
    value = value.trim();
    if (!value) return null;
    if (ISO_DATE_TIME.test(value) && !HAS_ZONE.test(value)) value = `${value.replace(' ', 'T')}Z`;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** «08 h 12» in the device's time zone, or `undefined` when there is no usable timestamp. */
export function clockTime(raw: unknown): string | undefined {
  const date = parseServerTime(raw);
  if (!date) return undefined;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getHours())} h ${pad(date.getMinutes())}`;
}
