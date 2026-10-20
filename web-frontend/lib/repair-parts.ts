/**
 * Owner, 2026-10-19: a long line is repaired by fixing only its wrong parts.
 *
 * The learner's line cut into the text that stays and the wrong stretches to
 * fix in place, from the correction's errata. `null` when a correction cannot
 * be placed in the line (a missing word, a stretch the line does not hold, the
 * whole line): that line is retyped whole, as before. Mirrors
 * `repair_parts` in `app/services/atelier.py`, which accepts the line it builds.
 */

export type RepairPart =
  | { text: string }
  | { wrong: string; fix: string; erratum: number };

type Erratum = { learner_text?: unknown; corrected_target?: unknown; task_error_type?: unknown };

const isWordChar = (char: string | undefined) => !!char && /[0-9A-Za-zÀ-ÖØ-öø-ÿŒœ]/.test(char);

// -1 when absent or there more than once: an erratum carries no offset, so
// «partie» in «Elle est partie et il est partie» could be either, and fixing
// the wrong one must not pass. That line is retyped whole.
function wordFind(folded: string, wrong: string, taken: Array<[number, number]>): number {
  const found: number[] = [];
  let start = folded.indexOf(wrong);
  while (start >= 0) {
    const end = start + wrong.length;
    const bounded = !isWordChar(folded[start - 1]) && !isWordChar(folded[end]);
    if (bounded && taken.every(([a, b]) => end <= a || start >= b)) found.push(start);
    start = folded.indexOf(wrong, start + 1);
  }
  return found.length === 1 ? found[0] : -1;
}

export function repairParts(learner: string, errata: Erratum[] | null | undefined): RepairPart[] | null {
  const line = String(learner || '');
  const folded = line.toLowerCase();
  const spans: Array<{ start: number; end: number; fix: string; erratum: number }> = [];
  const list = errata || [];
  for (let index = 0; index < list.length; index += 1) {
    const erratum = list[index];
    if (!erratum || typeof erratum !== 'object' || erratum.task_error_type === 'task_compliance') continue;
    const wrong = String(erratum.learner_text || '').trim();
    const fix = String(erratum.corrected_target || '').trim();
    if (wrong && wrong === fix) continue;
    if (!wrong || !fix || wrong.toLowerCase() === folded.trim()) return null;
    // Same length as the line: lower-casing French keeps every offset.
    if (wrong.toLowerCase().length !== wrong.length) return null;
    const start = wordFind(folded, wrong.toLowerCase(), spans.map((span) => [span.start, span.end]));
    if (start < 0) return null;
    spans.push({ start, end: start + wrong.length, fix, erratum: index });
  }
  if (!spans.length) return null;
  spans.sort((a, b) => a.start - b.start);
  const parts: RepairPart[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start > cursor) parts.push({ text: line.slice(cursor, span.start) });
    parts.push({ wrong: line.slice(span.start, span.end), fix: span.fix, erratum: span.erratum });
    cursor = span.end;
  }
  if (cursor < line.length) parts.push({ text: line.slice(cursor) });
  return parts;
}

/** The whole line with each gap filled by what the learner typed there. */
export function assembleRepair(parts: RepairPart[], typed: Record<number, string>): string {
  return parts
    .map((part, index) => ('text' in part ? part.text : (typed[index] ?? part.wrong)))
    .join('');
}

/** Typography folded, accents kept: a gap is fixed when it reads as its fix. */
function fold(value: string): string {
  return value
    .normalize('NFC')
    .replace(/[‘’‚‛′´`ʹʻʼ]/g, "'")
    .toLowerCase()
    .replace(/[.,!?;:«»"“”]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function gapIsFixed(typed: string, fix: string): boolean {
  return fold(typed) === fold(fix);
}
