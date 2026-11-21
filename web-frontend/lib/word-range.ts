/**
 * #574: the word range an item states («7–16 words») is a rule, not a label.
 * Mirrors `check_answer_length` in app/services/atelier.py, which refuses the
 * same lines on the server.
 */
export function wordsOf(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

/**
 * True when the line is not above the item's ceiling; an item without one takes any line.
 * The floor stays a hint («2 more words»): items carry a generic default one, and a
 * short line that is right is still right.
 */
export function withinWordRange(text: string, maxWords?: unknown): boolean {
  const max = Number(maxWords) || 0;
  return !(max > 0 && wordsOf(text) > max);
}

/**
 * #853: the rounds whose typed line is held under its item's ceiling: «Check» waits for
 * it (canSubmit) and the server refuses it (`_RANGED_ROUNDS` in app/services/atelier.py).
 * A spoken transcript's length is the recogniser's; the paragraph (`produce`) has a
 * floor only. Only where the ceiling holds does the screen say so.
 */
export const CEILING_ROUNDS: readonly string[] = ['sentence', 'conversation'];

/** True when this round's line is above its ceiling, so «Check» waits for it. */
export function heldByCeiling(round: string, text: string, maxWords?: unknown): boolean {
  return CEILING_ROUNDS.includes(round) && !withinWordRange(text, maxWords);
}
