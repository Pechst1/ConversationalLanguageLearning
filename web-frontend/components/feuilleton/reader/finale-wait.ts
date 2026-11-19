/**
 * P11 · the last panel never waits without a way on.
 *
 * 17 Nov walk: while the ending was being written («La suite s’écrit…») the reader
 * drew nothing where «Continuer» sits, with no timeout, and a learner was left on
 * that screen. From the first second the slot says the ending is being written,
 * with the pending indicator; after {@link FINALE_ESCAPE_MS} it is the continue
 * button again, with a line that the ending will be there next time. The journey
 * keeps polling meanwhile and the server heals a dead lane with the authored ending.
 *
 * Framework-free, so the node harness pins it.
 */

/** How long the last panel waits for its ending before it lets the learner go on. */
export const FINALE_ESCAPE_MS = 30_000;

/**
 * What the nav slot under the last panel shows.
 *
 * - `normal`: the reader's own button (next, complete, read on).
 * - `writing`: the ending is being written; the pending line, no button yet.
 * - `continue_late`: still being written after {@link FINALE_ESCAPE_MS}; the
 *   continue button, with the line «the ending will be there next time».
 */
export type FinaleNav = 'normal' | 'writing' | 'continue_late';

export function finaleNav({
  isLast,
  waiting,
  filed,
  waitedMs,
}: {
  isLast: boolean;
  waiting: boolean;
  filed: boolean;
  /** How long this ending has been awaited on screen; `null` before the wait began. */
  waitedMs: number | null;
}): FinaleNav {
  if (!isLast || !waiting || filed) return 'normal';
  return waitedMs !== null && waitedMs >= FINALE_ESCAPE_MS ? 'continue_late' : 'writing';
}

/** Has an ending awaited since `since` waited long enough to let the learner on? */
export function finaleWaitOver(since: number | null, now: number): boolean {
  return since !== null && now - since >= FINALE_ESCAPE_MS;
}
