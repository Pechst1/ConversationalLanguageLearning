/**
 * SPEED-1 «Vérification du lexique» — the pure half of the check.
 *
 * A learner placed above A1 should not spend months re-carding words they
 * already read. Each sub-band below their level can be checked in about two
 * minutes (`GET/POST /vocabulary/band-check/{sub_band}`); a pass gives every
 * core word of that sub-band a settled card. This module holds everything the
 * screen decides without the network, so `band-check.test.js` can pin it:
 *
 *  - **sequencing** (WP-127, top-down): the server's ladder
 *    (`GET /vocabulary/band-check/ladder`) names the next band — the highest
 *    uncredited one below the learner's level. A pass stops the ladder (it
 *    credits that band and, by inference, every band below); a miss steps down
 *    one band. A visit is at most two checks; a paused ladder resumes later.
 *    The client mirrors that rule for its own display (`nextBand`) and always
 *    defers to the server's `next`;
 *  - **stop and resume**: a run's answers are kept per `attempt_id` (the
 *    check's persistent identity), so a learner who stops mid-check comes back
 *    to the same words with their answers in place;
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

/** WP-127's candidate rule, 21 of 24; the start payload carries the real one. */
export const DEFAULT_PASS_SHARE = 21 / 24;

/** WP-127: a visit is at most this many checks (2 × 24 = 48 items). */
export const MAX_CHECKS_PER_VISIT = 2;

function rank(subBand: string): number {
  const index = (SUB_BAND_ORDER as readonly string[]).indexOf(subBand);
  return index === -1 ? SUB_BAND_ORDER.length : index;
}

/** The sub-bands still worth checking, highest first (WP-127: top-down). */
export function uncreditedBands(list: BandCheckSubBand[] | null | undefined): BandCheckSubBand[] {
  return (list ?? [])
    .filter((row) => !row.credited && row.words > 0)
    .sort((a, b) => rank(b.sub_band) - rank(a.sub_band));
}

/** Whether any entry point should show at all. */
export function hasUncreditedBand(list: BandCheckSubBand[] | null | undefined): boolean {
  return uncreditedBands(list).length > 0;
}

/**
 * The band to check next, top-down: the highest uncredited band above every
 * credited one that was not missed. After a miss at `after`, the next one
 * *down*. A band just checked is never offered again straight away, and a pass
 * leaves nothing above the floor, so the ladder stops.
 */
export function nextBand(
  list: BandCheckSubBand[] | null | undefined,
  after?: string | null,
): string | null {
  const rows = list ?? [];
  const floor = Math.max(-1, ...rows.filter((row) => row.credited).map((row) => rank(row.sub_band)));
  const ceiling = after ? rank(after) : Number.POSITIVE_INFINITY;
  const next = uncreditedBands(rows).find(
    (row) => rank(row.sub_band) > floor && rank(row.sub_band) < ceiling && !row.missed && row.sub_band !== after,
  );
  return next ? next.sub_band : null;
}

/** After a pass, the list the screen keeps using marks the band credited. */
export function markCredited(list: BandCheckSubBand[], subBand: string): BandCheckSubBand[] {
  return list.map((row) => (row.sub_band === subBand ? { ...row, credited: true } : row));
}

/** After a miss, the band stays uncredited and is marked missed (the ladder steps down). */
export function markMissed(list: BandCheckSubBand[], subBand: string): BandCheckSubBand[] {
  return list.map((row) => (row.sub_band === subBand ? { ...row, missed: true } : row));
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
  /** WP-127: the check's persistent identity, sent back with the answers. */
  attemptId?: string | null;
  /** WP-127: correct answers a pass needs, when the server says (`pass_correct`). */
  passCorrect?: number | null;
  /** The item on screen; `items.length` once every item is answered. */
  index: number;
  /** item id → choice. «Je ne sais pas» is stored as `null`, never left out. */
  answers: Record<string, BandCheckChoice>;
};

export function startRun(
  subBand: string,
  items: BandCheckItem[],
  passShare = DEFAULT_PASS_SHARE,
  attemptId: string | null = null,
): BandCheckRun {
  return { subBand, items, passShare, attemptId, index: 0, answers: {} };
}

/** What a stopped run keeps (per `attempt_id`): the answers so far. */
export type SavedRun = { attemptId: string; answers: Record<string, BandCheckChoice> };

export function savedRunOf(run: BandCheckRun): SavedRun | null {
  return run.attemptId ? { attemptId: run.attemptId, answers: { ...run.answers } } : null;
}

/**
 * Resume a stopped run: the saved answers come back only for the same attempt
 * (the same words, the same key) and only for items that are still on it; the
 * run continues at the first unanswered item.
 */
export function resumeRun(run: BandCheckRun, saved: SavedRun | null | undefined): BandCheckRun {
  if (!saved || !run.attemptId || saved.attemptId !== run.attemptId) return run;
  const answers: Record<string, BandCheckChoice> = {};
  for (const item of run.items) {
    if (!(item.id in saved.answers)) break;
    const choice = saved.answers[item.id];
    if (choice !== null && (!Number.isInteger(choice) || choice < 0 || choice >= item.options.length)) break;
    answers[item.id] = choice;
  }
  return { ...run, answers, index: Object.keys(answers).length };
}

/** The storage key a run's answers live under while it is stopped. */
export function savedRunKey(attemptId: string): string {
  return `atelier.band-check.${attemptId}`;
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
  /** Correct answers a pass needs (the server's `pass_correct`, else from the share). */
  needed: number;
  /** Words that got a settled card now (0 when the learner had them all already). */
  credited: number;
  /** WP-127: of those, words that were on the check and answered right. */
  sampled: number;
  /** WP-127: of those, words credited by inference (not on the check). */
  inferred: number;
  /** WP-127: the lower bands credited by inference from this pass. */
  inferredBands: string[];
  /** How many items were missed or answered «je ne sais pas» — they stay in the normal flow. */
  missed: number;
  /** The next band down to check now, or null (a pass, the bottom, or the visit spent). */
  next: string | null;
  /** WP-127: the ladder after this check — open / paused / done. */
  ladder: 'open' | 'paused' | 'done';
  /** WP-127: when paused, the band the next visit starts with. */
  resumeBand: string | null;
};

export function neededToPass(total: number, passShare = DEFAULT_PASS_SHARE): number {
  return Math.ceil(total * passShare - 1e-9);
}

export function summarize(
  result: BandCheckResult,
  list: BandCheckSubBand[] | null | undefined,
  passShare = DEFAULT_PASS_SHARE,
): BandCheckSummary {
  const after = result.passed ? markCredited(list ?? [], result.sub_band) : markMissed(list ?? [], result.sub_band);
  const status = result.ladder_status;
  // The server's ladder is the authority; an older server without one falls
  // back to the same rule computed here.
  const next = status ? result.next ?? null : result.passed ? null : nextBand(after, result.sub_band);
  const ladder: BandCheckSummary['ladder'] =
    status === 'paused' ? 'paused' : status === 'open' || (!status && next) ? 'open' : 'done';
  const credited = result.passed ? result.credited_words : 0;
  const inferred = result.passed ? result.credited_inferred ?? 0 : 0;
  return {
    tone: result.passed ? 'passed' : 'failed',
    subBand: result.sub_band,
    correct: result.correct,
    total: result.total,
    needed: result.pass_correct ?? neededToPass(result.total, passShare),
    credited,
    sampled: result.passed ? result.credited_sampled ?? Math.max(0, credited - inferred) : 0,
    inferred,
    inferredBands: result.passed ? [...(result.inferred_bands ?? [])] : [],
    missed: result.missed.length,
    next: ladder === 'open' ? next : null,
    ladder,
    resumeBand: ladder === 'paused' ? result.resume_band ?? null : null,
  };
}
