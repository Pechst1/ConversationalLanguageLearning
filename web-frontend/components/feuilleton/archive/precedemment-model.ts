/**
 * WP-96 «Précédemment» — when the small box above a new scene is shown.
 *
 * Before a new scene's first panel, the chronicle's last lines
 * (`prompt.previously_fr`, at most three) are printed in a small editorial
 * box with one «Lire» to go on. It is a reminder, never a gate: nothing is
 * shown on the first day (there is no before), none when the server sent no
 * line, and never twice for the same scene once the learner has read on.
 */

export const PRECEDEMMENT_MAX_LINES = 3;

/** The lines worth printing: trimmed, non-empty, at most three, in the server's order. */
export function precedemmentLines(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((line) => (typeof line === 'string' ? line.trim() : ''))
    .filter(Boolean)
    .slice(0, PRECEDEMMENT_MAX_LINES);
}

/** The lines to show now, or `null` when the box is not shown. */
export function precedemmentView({
  lines,
  firstDay,
  dismissed,
}: {
  lines: unknown;
  /** The learner's first journey (the cast is being introduced): there is no «before». */
  firstDay: boolean;
  /** «Lire» was pressed for this scene already. */
  dismissed: boolean;
}): string[] | null {
  if (firstDay || dismissed) return null;
  const printed = precedemmentLines(lines);
  return printed.length ? printed : null;
}

/** The per-scene memory key: a box read once stays read on a reload. */
export function precedemmentKey(journeyId: string, stepId: string): string {
  return `atelier:precedemment:${journeyId}:${stepId}`;
}

export function readPrecedemmentDismissed(journeyId: string, stepId: string): boolean {
  try {
    return window.sessionStorage.getItem(precedemmentKey(journeyId, stepId)) === '1';
  } catch {
    return false;
  }
}

export function writePrecedemmentDismissed(journeyId: string, stepId: string): void {
  try {
    window.sessionStorage.setItem(precedemmentKey(journeyId, stepId), '1');
  } catch {
    /* a private window: the box simply shows again on a reload */
  }
}
