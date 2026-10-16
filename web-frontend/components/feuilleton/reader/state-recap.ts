/* Root cause #145 / #168: the engine's scene recap is internal state, never story text.
 *
 * The scene ledger keeps «what the learner said and what is established» as notes
 * («The learner says they will have coffee with Lila…»). Those notes once reached the
 * reader as the ending's beat, in English, under a French story. The reader asks this
 * module before it prints a hook or ending line; a note that talks about «the learner»
 * is dropped, in any UI language the engine writes notes in.
 *
 * Pure, no React: tested with `node --test`.
 */

const RECAP_MARKERS = [
  /\bthe\s+learner\b/i,
  /\blearner\s+(?:says|said|wrote|will|has)\b/i,
  /\bder\s+lernende\b|\bdie\s+lernende\b|\bdie\s+lernerin\b/i,
  /\bl['’]apprenant(?:e)?\b|\ble\s+learner\b/i,
  /\bel\s+(?:alumno|estudiante)\b/i,
];

export function isStateRecap(text: unknown): boolean {
  const value = String(text ?? '');
  return RECAP_MARKERS.some((pattern) => pattern.test(value));
}

/** The text when it is story text, else the empty string. */
export function storyTextOnly(text: unknown): string {
  const value = String(text ?? '').trim();
  return isStateRecap(value) ? '' : value;
}
