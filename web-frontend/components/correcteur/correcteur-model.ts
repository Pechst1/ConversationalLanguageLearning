/**
 * WP-122 B · Le Correcteur — the pure half of the page: what a tap or a drag
 * selects, the running marks, and how a sentence splits into runs for the result.
 * `gradeLocally` is the mock's grader: a port of `revue/correcteur.grade` (§4.2).
 */

import type { CrDraft, CrFalseAlarm, CrMark, CrOutcome, CrResult, CrSeedOutcome, CrSpan, CrUnit } from '@/lib/correcteur-types';

export type CrSelection = {
  sentenceIndex: number;
  span: CrSpan;
  text: string;
  /** Three forms to pick from (A1–A2), only when the selection is exactly one unit that has them. */
  options: string[] | null;
};

export const overlaps = (a: CrSpan, b: CrSpan): boolean => a[0] < b[1] && b[0] < a[1];

export function unitsOf(draft: Pick<CrDraft, 'units'>, sentenceIndex: number): CrUnit[] {
  return draft.units.filter((unit) => unit.sentenceIndex === sentenceIndex).sort((a, b) => a.span[0] - b.span[0]);
}

/** A tap (one unit) or a drag (from one unit to another, either direction, same sentence). */
export function selectUnits(
  draft: Pick<CrDraft, 'units' | 'sentences' | 'optionsEnabled'>,
  sentenceIndex: number,
  fromUnit: number,
  toUnit: number = fromUnit,
): CrSelection | null {
  const units = unitsOf(draft, sentenceIndex);
  const a = units[Math.min(fromUnit, toUnit)];
  const b = units[Math.max(fromUnit, toUnit)];
  const sentence = draft.sentences[sentenceIndex];
  if (!a || !b || sentence === undefined) return null;
  const span: CrSpan = [a.span[0], b.span[1]];
  const single = a === b;
  return {
    sentenceIndex,
    span,
    text: sentence.slice(span[0], span[1]),
    options: draft.optionsEnabled && single && a.options ? a.options : null,
  };
}

/** Add a mark; one replaces any earlier mark it overlaps in the same sentence. */
export function upsertMark(marks: CrMark[], mark: CrMark): CrMark[] {
  const kept = marks.filter((other) => other.sentenceIndex !== mark.sentenceIndex || !overlaps(other.span, mark.span));
  return [...kept, mark].sort((x, y) => x.sentenceIndex - y.sentenceIndex || x.span[0] - y.span[0]);
}

export function removeMark(marks: CrMark[], index: number): CrMark[] {
  return marks.filter((_, i) => i !== index);
}

export function markIndexAt(marks: CrMark[], sentenceIndex: number, span: CrSpan): number {
  return marks.findIndex((mark) => mark.sentenceIndex === sentenceIndex && overlaps(mark.span, span));
}

export type CrRun<T> = { text: string; start: number; end: number; tag: T | null };

/** A sentence cut into runs: plain text between the tagged spans (non-overlapping, any order). */
export function runs<T>(sentence: string, tagged: { span: CrSpan; tag: T }[]): CrRun<T>[] {
  const sorted = [...tagged].sort((a, b) => a.span[0] - b.span[0]);
  const out: CrRun<T>[] = [];
  let cursor = 0;
  for (const { span, tag } of sorted) {
    const start = Math.max(cursor, span[0]);
    const end = Math.min(sentence.length, span[1]);
    if (end <= start) continue;
    if (start > cursor) out.push({ text: sentence.slice(cursor, start), start: cursor, end: start, tag: null });
    out.push({ text: sentence.slice(start, end), start, end, tag });
    cursor = end;
  }
  if (cursor < sentence.length) out.push({ text: sentence.slice(cursor), start: cursor, end: sentence.length, tag: null });
  return out;
}

// --- the mock's grader -------------------------------------------------------

export type CrKey = { sentenceIndex: number; span: CrSpan; wrongFr: string; correctFr: string; grammarPoint: string; source: 'errata' | 'classique' };

const foldAnswer = (text: string | null | undefined): string =>
  String(text ?? '')
    .replace(/[’‘‛`´′]/g, "'")
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase('fr')
    .replace(/^[ .,;:!?]+|[ .,;:!?]+$/g, '');

function repairs(sentence: string, seed: CrKey, mark: CrMark): boolean {
  if (!mark.fixFr || !mark.fixFr.trim()) return false;
  if (foldAnswer(mark.fixFr) === foldAnswer(seed.correctFr)) return true;
  const [m0, m1] = mark.span;
  const [s0, s1] = seed.span;
  const u0 = Math.min(m0, s0);
  const u1 = Math.max(m1, s1);
  const learner = sentence.slice(u0, m0) + mark.fixFr + sentence.slice(m1, u1);
  const expected = sentence.slice(u0, s0) + seed.correctFr + sentence.slice(s1, u1);
  return foldAnswer(learner) === foldAnswer(expected);
}

export function romyKey(band: string, counts: { seeded: number; repaired: number; noticed: number }): string {
  const noticed = counts.repaired + counts.noticed;
  if (counts.seeded && counts.repaired === counts.seeded) return 'all_repaired';
  if (counts.seeded && noticed === counts.seeded) return 'all_noticed';
  if (noticed === 0) return 'none';
  return noticed * 2 >= counts.seeded ? 'most' : 'few';
}

export function gradeLocally(
  draft: Pick<CrDraft, 'id' | 'dossierId' | 'sentences' | 'band'>,
  key: CrKey[],
  marks: CrMark[],
  romyLines: Record<string, Record<string, string>>,
): CrResult {
  const used = new Set<number>();
  const outcomes: CrSeedOutcome[] = key.map((seed) => {
    const touching = marks
      .map((mark, index) => ({ mark, index }))
      .filter(({ mark }) => mark.sentenceIndex === seed.sentenceIndex && overlaps(mark.span, seed.span));
    touching.forEach(({ index }) => used.add(index));
    const sentence = draft.sentences[seed.sentenceIndex] ?? '';
    const repairing = touching.find(({ mark }) => repairs(sentence, seed, mark));
    const outcome: CrOutcome = repairing ? 'repaired' : touching.length ? 'noticed' : 'missed';
    const fix = repairing ? repairing.mark.fixFr : touching[0]?.mark.fixFr ?? null;
    return { ...seed, outcome, fixFr: fix ?? null };
  });
  const falseAlarms: CrFalseAlarm[] = marks
    .map((mark, index) => ({ mark, index }))
    .filter(({ index }) => !used.has(index))
    .map(({ mark }) => ({
      sentenceIndex: mark.sentenceIndex,
      span: mark.span,
      textFr: (draft.sentences[mark.sentenceIndex] ?? '').slice(mark.span[0], mark.span[1]),
      fixFr: mark.fixFr,
    }));
  const counts = {
    seeded: outcomes.length,
    repaired: outcomes.filter((o) => o.outcome === 'repaired').length,
    noticed: outcomes.filter((o) => o.outcome === 'noticed').length,
    missed: outcomes.filter((o) => o.outcome === 'missed').length,
    falseAlarms: falseAlarms.length,
  };
  const group = draft.band === 'A1' || draft.band === 'A2' ? 'A' : 'B';
  return {
    id: draft.id,
    dossierId: draft.dossierId,
    sentences: draft.sentences,
    outcomes,
    falseAlarms,
    counts,
    romyLineFr: romyLines[group]?.[romyKey(draft.band, counts)] ?? '',
    releveHref: '/notebook?mode=releve',
  };
}
