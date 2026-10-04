/**
 * SPEED-1 «Vérification du lexique» — the pure half of the check.
 *
 * A learner placed above A1 should not spend months re-carding words they
 * already read. Each sub-band below their level can be checked in about two
 * minutes (`GET/POST /vocabulary/band-check/{sub_band}`); a pass gives every
 * core word of that sub-band a settled card. This module holds everything the
 * screen decides without the network, so `band-check.test.js` can pin it:
 *
 *  - **sequencing**: offer the uncredited sub-bands from the lowest upward;
 *    after a result, the next one up (after a pass as the natural next step,
 *    after a miss as an option, never pushed);
 *  - **answering**: one tap records an answer and advances. «Je ne sais pas» is
 *    a real answer (`null` in the payload), recorded exactly like a choice and
 *    never counted or displayed as a failure of its own;
 *  - **scoring display**: what the result card says, from the server's grade.
 *    The server alone holds the answer key; the client never grades.
 */

import type { BandCheckItem, BandCheckResult, BandCheckSubBand } from '@/services/api';

/** The ladder, lowest first — the order the server's sub-band ids sort in. */
export const SUB_BAND_ORDER = [
  'A1.1',
  'A1.2',
  'A2.1',
  'A2.2',
  'B1.1',
  'B1.2',
  'B2.1',
  'B2.2',
  'C1.1',
  'C1.2',
] as const;

/** The default the API documents; the start payload carries the real one. */
export const DEFAULT_PASS_SHARE = 0.9;

function rank(subBand: string): number {
  const index = (SUB_BAND_ORDER as readonly string[]).indexOf(subBand);
  return index === -1 ? SUB_BAND_ORDER.length : index;
}

/** The sub-bands still worth checking, lowest first. */
export function uncreditedBands(list: BandCheckSubBand[] | null | undefined): BandCheckSubBand[] {
  return (list ?? [])
    .filter((row) => !row.credited && row.words > 0)
    .sort((a, b) => rank(a.sub_band) - rank(b.sub_band));
}

/** Whether any entry point should show at all. */
export function hasUncreditedBand(list: BandCheckSubBand[] | null | undefined): boolean {
  return uncreditedBands(list).length > 0;
}

/**
 * The band to offer next: the lowest uncredited one, or — after `after` — the
 * lowest uncredited one *above* it. A band just checked is never offered again
 * straight away, whether it passed or not.
 */
export function nextBand(
  list: BandCheckSubBand[] | null | undefined,
  after?: string | null,
): string | null {
  const floor = after ? rank(after) : -1;
  const next = uncreditedBands(list).find((row) => rank(row.sub_band) > floor && row.sub_band !== after);
  return next ? next.sub_band : null;
}

/** After a pass, the list the screen keeps using marks the band credited. */
export function markCredited(list: BandCheckSubBand[], subBand: string): BandCheckSubBand[] {
  return list.map((row) => (row.sub_band === subBand ? { ...row, credited: true } : row));
}

// ---------------------------------------------------------------------------
// The run: one item at a time, tap to advance
// ---------------------------------------------------------------------------

/** An option index, or `null` for «je ne sais pas». */
export type BandCheckChoice = number | null;

export type BandCheckRun = {
  subBand: string;
  items: BandCheckItem[];
  passShare: number;
  /** The item on screen; `items.length` once every item is answered. */
  index: number;
  /** item id → choice. «Je ne sais pas» is stored as `null`, never left out. */
  answers: Record<string, BandCheckChoice>;
};

export function startRun(subBand: string, items: BandCheckItem[], passShare = DEFAULT_PASS_SHARE): BandCheckRun {
  return { subBand, items, passShare, index: 0, answers: {} };
}

export function currentItem(run: BandCheckRun): BandCheckItem | null {
  return run.items[run.index] ?? null;
}

export function isComplete(run: BandCheckRun): boolean {
  return run.items.length > 0 && run.index >= run.items.length;
}

/**
 * Record the answer to the item on screen and move on. An out-of-range index is
 * ignored (a stale keypress), and a complete run does not change.
 */
export function answer(run: BandCheckRun, choice: BandCheckChoice): BandCheckRun {
  const item = currentItem(run);
  if (!item) return run;
  if (choice !== null && (!Number.isInteger(choice) || choice < 0 || choice >= item.options.length)) {
    return run;
  }
  return { ...run, index: run.index + 1, answers: { ...run.answers, [item.id]: choice } };
}

/** One step back — a mis-tap is corrected, not punished. */
export function undo(run: BandCheckRun): BandCheckRun {
  if (run.index === 0) return run;
  const previous = run.items[run.index - 1];
  const answers = { ...run.answers };
  if (previous) delete answers[previous.id];
  return { ...run, index: run.index - 1, answers };
}

/** The POST body: every item present, unanswered ones as «je ne sais pas». */
export function answersPayload(run: BandCheckRun): Record<string, BandCheckChoice> {
  return Object.fromEntries(
    run.items.map((item) => [item.id, item.id in run.answers ? run.answers[item.id] : null]),
  );
}

export function progressOf(run: BandCheckRun): { done: number; total: number } {
  return { done: Math.min(run.index, run.items.length), total: run.items.length };
}

/**
 * The keyboard: 1–4 choose an option, 0 / `?` / `n` say «je ne sais pas»,
 * Backspace steps back. Anything else is not the check's.
 */
export function keyToChoice(
  key: string,
  optionCount: number,
): { kind: 'choice'; choice: BandCheckChoice } | { kind: 'undo' } | null {
  if (/^[1-9]$/.test(key)) {
    const index = Number(key) - 1;
    return index < optionCount ? { kind: 'choice', choice: index } : null;
  }
  if (key === '0' || key === '?' || key === 'n' || key === 'N') return { kind: 'choice', choice: null };
  if (key === 'Backspace') return { kind: 'undo' };
  return null;
}

// ---------------------------------------------------------------------------
// The result card
// ---------------------------------------------------------------------------

export type BandCheckSummary = {
  tone: 'passed' | 'failed';
  subBand: string;
  correct: number;
  total: number;
  /** Correct answers a pass needs, from the pass share. */
  needed: number;
  /** Words that got a settled card now (0 when the learner had them all already). */
  credited: number;
  /** How many items were missed or answered «je ne sais pas» — they stay in the normal flow. */
  missed: number;
  /** The next band up, still uncredited, or null at the top of the learner's range. */
  next: string | null;
};

export function neededToPass(total: number, passShare = DEFAULT_PASS_SHARE): number {
  return Math.ceil(total * passShare - 1e-9);
}

export function summarize(
  result: BandCheckResult,
  list: BandCheckSubBand[] | null | undefined,
  passShare = DEFAULT_PASS_SHARE,
): BandCheckSummary {
  const after = result.passed ? markCredited(list ?? [], result.sub_band) : list ?? [];
  return {
    tone: result.passed ? 'passed' : 'failed',
    subBand: result.sub_band,
    correct: result.correct,
    total: result.total,
    needed: neededToPass(result.total, passShare),
    credited: result.passed ? result.credited_words : 0,
    missed: result.missed.length,
    next: nextBand(after, result.sub_band),
  };
}
