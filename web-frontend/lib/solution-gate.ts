/**
 * Owner, 2026-11-13: «the user should not see what is right when he then gets another
 * chance to fix it; only afterwards the solution.»
 *
 * The server withholds the solution while a second chance is open
 * (app/services/solution_gate.py): the correction comes with `solution.state ===
 * 'withheld'`, an empty corrected line, and per erratum a `hint` (where and why, never
 * the right form) and a `mark` (the words of the learner's own line that are wrong).
 * The chance is spent by a repair sent or by «Show the solution»; the correction then
 * comes whole, `solution.state === 'shown'` with `revealed_by`.
 *
 * Pure: pinned by lib/solution-gate.test.js.
 */

export type SolutionState = 'withheld' | 'spent' | 'shown' | 'none';

type Correction = Record<string, any> | null | undefined;

/** Where this miss stands. `none`: an old payload that predates the gate. */
export function solutionState(correction: Correction): SolutionState {
  const solution = correction?.solution;
  if (!solution || typeof solution !== 'object') return 'none';
  if (solution.state === 'withheld') return 'withheld';
  if (solution.revealed_by) return 'spent';
  return 'shown';
}

/** The solution is not on this payload: nothing right may be drawn from the item either. */
export function solutionWithheld(correction: Correction): boolean {
  return solutionState(correction) === 'withheld';
}

/**
 * A miss is offered «Try again» only while its chance is open (or on an old payload):
 * once the solution is on screen, a retry would be a copy.
 */
export function retryOffered(correction: Correction): boolean {
  const state = solutionState(correction);
  return state === 'withheld' || state === 'none';
}

export type MarkedSegment = { text: string; marked: boolean };

/**
 * The learner's line cut at the server's marks: the words that are wrong, in place.
 * Marks that do not fit the line (a stale payload) are dropped, never guessed.
 */
export function markedLine(line: string, marks: ReadonlyArray<{ start?: unknown; end?: unknown }> | null | undefined): MarkedSegment[] {
  const text = String(line || '');
  const spans = (marks || [])
    .map((mark) => ({ start: Number(mark?.start), end: Number(mark?.end) }))
    .filter(({ start, end }) => Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && end <= text.length)
    .sort((a, b) => a.start - b.start);
  const segments: MarkedSegment[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start < cursor) continue;
    if (span.start > cursor) segments.push({ text: text.slice(cursor, span.start), marked: false });
    segments.push({ text: text.slice(span.start, span.end), marked: true });
    cursor = span.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), marked: false });
  return segments.length ? segments : [{ text, marked: false }];
}

/**
 * The repair in place before the solution: the learner's line with each marked stretch
 * a gap holding what they wrote. The fix is not known (`fix: ''`), so a gap is sized by
 * what it holds. Null when nothing is marked: that line is answered again whole.
 */
export function withheldRepairParts(
  line: string,
  marks: ReadonlyArray<{ start?: unknown; end?: unknown; erratum?: unknown }> | null | undefined,
): Array<{ text: string } | { wrong: string; fix: string; erratum: number }> | null {
  const segments = markedLine(line, marks);
  if (!segments.some((segment) => segment.marked)) return null;
  let erratum = 0;
  return segments.map((segment) => (segment.marked ? { wrong: segment.text, fix: '', erratum: erratum++ } : { text: segment.text }));
}

/** The hints to read before the second chance: the first is the reason, the rest sit behind «More». */
export function withheldHints(correction: Correction): { reason: string; more: string[]; task: string } {
  const errata: Array<Record<string, any>> = Array.isArray(correction?.errata) ? correction!.errata : [];
  const seen = new Set<string>();
  const say = (value: unknown) => {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) return '';
    seen.add(key);
    return text;
  };
  const isTask = (item: Record<string, any>) => item.task_error_type === 'task_compliance' || item.task_error_type === 'length_compliance';
  const language = errata.filter((item) => !isTask(item)).map((item) => say(item.hint || item.why_wrong)).filter(Boolean);
  const task = errata.filter(isTask).map((item) => say(item.hint || item.why_wrong)).filter(Boolean);
  const [reason = task[0] || '', ...more] = language;
  return { reason, more, task: language.length ? task[0] || '' : task.slice(1)[0] || '' };
}
