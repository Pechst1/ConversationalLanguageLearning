/* WP-92 «Rayons X» — the day's rule, marked in the page.
 *
 * The story engine sends, per dialogue line, where the rule's form sits:
 * `grammar_marks: [{ unit_id, start, end }]`, character offsets into the
 * line's `text_fr` as the server wrote it. The reader shows the line trimmed
 * and typeset (`frenchSpacing` adds narrow no-break spaces), and splits it into
 * tappable word buttons. This module carries the offsets across both steps:
 *
 *   * `lineMarkRanges` moves the offsets onto the trimmed line, clamps them,
 *     keeps only the day's unit, and merges what overlaps;
 *   * `markTokens` snaps every mark to whole words — a mark that starts or ends
 *     inside a word takes the whole word, so a word button is never split — and
 *     marks the gap between two words of one mark, so «je suis allé» reads as
 *     one underline;
 *   * `markedForms` is the same span as text, for the screen reader's one
 *     announcement per line.
 *
 * Why word runs and not raw offsets: `frenchSpacing` changes spaces and
 * inserts U+202F before « ? ! ; », which moves every offset after it, but it
 * never touches a letter. The n-th word run of the typeset line is the n-th
 * word run of the server's line, so marks are resolved on runs.
 *
 * Pure module: no React, unit-tested with `node --test`.
 */

import { frenchSpacing } from '@/lib/french-typography';

import { tokenizeFrench, type FrenchToken } from './french-text';

export type MarkRange = { start: number; end: number };

export type MarkedToken = FrenchToken & {
  /** Part of the rule's form (a word of it, or the gap between two of its words). */
  marked: boolean;
};

type MarkSource = { unit_id?: unknown; start?: unknown; end?: unknown } | null | undefined;

// The same word runs `tokenizeFrench` cuts (letters, hyphenated compounds).
const WORD_RE = /[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:-[A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*/g;
const LETTER_RE = /[A-Za-zÀ-ÖØ-öø-ÿŒœ]/;

function wordRuns(text: string): MarkRange[] {
  const runs: MarkRange[] = [];
  WORD_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  // eslint-disable-next-line no-cond-assign
  while ((match = WORD_RE.exec(text)) !== null) {
    runs.push({ start: match.index, end: match.index + match[0].length });
  }
  return runs;
}

function asOffset(value: unknown): number | null {
  const number = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN;
  return Number.isFinite(number) ? Math.floor(number) : null;
}

/**
 * The marks of one line, as ranges into the line the reader shows (`text_fr`
 * trimmed). `unitId`, when given, keeps only that unit's marks — the page's
 * `grammar_focus`. Malformed, empty or out-of-line marks are dropped; what
 * overlaps or touches is merged. Sorted by start.
 */
export function lineMarkRanges(
  rawText: string | null | undefined,
  marks: MarkSource[] | null | undefined,
  unitId?: string | number | null,
): MarkRange[] {
  const raw = String(rawText ?? '');
  if (!Array.isArray(marks) || marks.length === 0 || !raw.trim()) return [];
  const lead = raw.length - raw.replace(/^\s+/, '').length;
  const length = raw.trim().length;
  const wanted = unitId === null || unitId === undefined || unitId === '' ? null : String(unitId);
  const ranges: MarkRange[] = [];
  for (const mark of marks) {
    if (!mark || typeof mark !== 'object') continue;
    if (wanted !== null && mark.unit_id !== undefined && mark.unit_id !== null && String(mark.unit_id) !== wanted) {
      continue;
    }
    const start = asOffset(mark.start);
    const end = asOffset(mark.end);
    if (start === null || end === null) continue;
    const from = Math.max(0, start - lead);
    const to = Math.min(length, end - lead);
    if (to > from) ranges.push({ start: from, end: to });
  }
  ranges.sort((a, b) => a.start - b.start || a.end - b.end);
  const merged: MarkRange[] = [];
  for (const range of ranges) {
    const last = merged[merged.length - 1];
    if (last && range.start <= last.end) last.end = Math.max(last.end, range.end);
    else merged.push({ ...range });
  }
  return merged;
}

/** For each word run of `text`, the indices of the ranges it overlaps. */
function runMarks(text: string, ranges: MarkRange[]): number[][] {
  return wordRuns(text).map((run) =>
    ranges.flatMap((range, index) => (range.start < run.end && range.end > run.start ? [index] : [])),
  );
}

/**
 * The line's tokens as the reader renders them (`frenchSpacing`, then
 * `tokenizeFrench`), each flagged `marked` when it belongs to the rule's form.
 * Marks snap to whole words; a gap is marked only between two words of the
 * same mark. Without ranges it is exactly `tokenizeFrench(frenchSpacing(text))`
 * with every token unmarked.
 */
export function markTokens(text: string, ranges: MarkRange[] | null | undefined, keyPrefix = 't'): MarkedToken[] {
  const source = String(text || '');
  const tokens = tokenizeFrench(frenchSpacing(source), keyPrefix);
  if (!ranges || ranges.length === 0) return tokens.map((token) => ({ ...token, marked: false }));
  const perRun = runMarks(source, ranges);
  const out: MarkedToken[] = [];
  let run = -1;
  tokens.forEach((token, index) => {
    if (LETTER_RE.test(token.text)) {
      run += 1;
      out.push({ ...token, marked: (perRun[run] ?? []).length > 0 });
      return;
    }
    const before = perRun[run] ?? [];
    const nextIsRun = index + 1 < tokens.length && LETTER_RE.test(tokens[index + 1].text);
    const after = nextIsRun ? perRun[run + 1] ?? [] : [];
    out.push({ ...token, marked: before.some((id) => after.includes(id)) });
  });
  return out;
}

/**
 * The rule's form(s) in the line, snapped to whole words and in reading order
 * — «suis allé» — for the one screen-reader announcement per line. A mark that
 * covers no word (punctuation only) says nothing.
 */
export function markedForms(text: string, ranges: MarkRange[] | null | undefined): string[] {
  const source = String(text || '');
  if (!ranges || ranges.length === 0) return [];
  const runs = wordRuns(source);
  const forms: string[] = [];
  for (const range of ranges) {
    const covered = runs.filter((run) => range.start < run.end && range.end > run.start);
    if (!covered.length) continue;
    const form = source.slice(covered[0].start, covered[covered.length - 1].end).trim();
    if (form && !forms.includes(form)) forms.push(form);
  }
  return forms;
}

/**
 * «Rayons X» opens after the first full read of the page — once the learner
 * has reached its last panel — or at once on a replay. Before that the page is
 * a story, not a grammar exercise.
 */
export function rayonsUnlocked({
  furthest,
  lastPanelIndex,
  replay = false,
}: {
  furthest: number;
  lastPanelIndex: number;
  replay?: boolean;
}): boolean {
  if (replay) return true;
  if (!Number.isFinite(lastPanelIndex) || lastPanelIndex < 0) return false;
  return furthest >= lastPanelIndex;
}

/** Remembered per device; off by default. */
export const RAYONS_STORAGE_KEY = 'av2.rayons-x';

export function readRayons(): boolean {
  try {
    return typeof window !== 'undefined' && window.localStorage.getItem(RAYONS_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

export function writeRayons(on: boolean): void {
  try {
    if (typeof window !== 'undefined') window.localStorage.setItem(RAYONS_STORAGE_KEY, on ? '1' : '0');
  } catch {
    /* a private window: the toggle still works for this page */
  }
}
