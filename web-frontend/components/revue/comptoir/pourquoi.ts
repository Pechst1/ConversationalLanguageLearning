/**
 * «Papier · Le pourquoi» (owner 2026-11-20) · the pure parts and the copy, node-tested
 * (pourquoi.test.js). Shared by every player that shows Romy's marks (the comptoir's
 * «Ton avis»; «Le fil» reuses the same fix step).
 *
 * On the fix step each underlined word opens its why (the rule, never the answer), one at a
 * time; once the proof is settled the full why, «Dans l'article : …» and, when the slip has a
 * rule, one quiet line that La Forge will bring it back. Without a why the marks render as
 * before (the switch off is today's screen).
 */

import type { RvComptoirMark, RvComptoirMarkKind, RvComptoirNote, RvLanguage, RvMarkRule } from '@/lib/revue-types';

export type PourquoiCopy = {
  /** The tappable mark's name for a screen reader: «Pourquoi « {span} » ?». */
  why_open: string;
  /** Over the settled notes. */
  notes_label: string;
  /** Before the story's own sentence. */
  in_article: string;
  /** Once, under the notes, when a slip has a rule. */
  forge_line: string;
  /** «La règle» (2026-11-22): the stamp on a mark under the day's rule, and under a recent one. */
  day_rule: string;
  recent_rule: string;
};

export const POURQUOI_COPY: Record<'fr' | 'en' | 'de', PourquoiCopy> = {
  fr: {
    why_open: 'Pourquoi « {span} » ?',
    notes_label: 'Le pourquoi',
    in_article: 'Dans l’article :',
    forge_line: 'Cette règle revient dans La Forge.',
    day_rule: 'règle du jour',
    recent_rule: 'règle de la semaine',
  },
  en: {
    why_open: 'Why “{span}”?',
    notes_label: 'Why',
    in_article: 'In the article:',
    forge_line: 'This rule comes back in La Forge.',
    day_rule: 'today’s rule',
    recent_rule: 'this week’s rule',
  },
  de: {
    why_open: 'Warum „{span}“?',
    notes_label: 'Warum',
    in_article: 'Im Artikel:',
    forge_line: 'Diese Regel kommt in La Forge wieder.',
    day_rule: 'Regel des Tages',
    recent_rule: 'Regel der Woche',
  },
};

export function pourquoiCopy(language: RvLanguage | string | null | undefined): PourquoiCopy {
  return POURQUOI_COPY[(language as 'fr' | 'en' | 'de') in POURQUOI_COPY ? (language as 'fr' | 'en' | 'de') : 'fr'];
}

/** Some mark carries a why: the marks become tappable. */
export function hasWhy(marks: Pick<RvComptoirMark, 'why'>[]): boolean {
  return marks.some((mark) => Boolean(mark.why));
}

/** One open at a time: tapping the open mark closes it, another one moves the panel. */
export function toggleWhy(open: number | null, index: number): number | null {
  return open === index ? null : index;
}

/** The open mark's why, or null (a mark without one, or an index out of range, opens nothing). */
export function openWhy(marks: RvComptoirMark[], open: number | null): { mark: RvComptoirMark; index: number } | null {
  if (open === null || open < 0 || open >= marks.length) return null;
  const mark = marks[open];
  return mark?.why ? { mark, index: open } : null;
}

export type WhySegment = { text: string; kind: RvComptoirMarkKind | null; index: number | null };

/**
 * The draft cut at the marks, each marked run carrying its mark's index (so the word opens
 * that mark's why). Found at its `start`, else at its first occurrence; a mark not in the
 * draft or over another one is dropped — as `markSegments` does.
 */
export function whySegments(text: string, marks: RvComptoirMark[]): WhySegment[] {
  const spans: Array<{ start: number; end: number; kind: RvComptoirMarkKind; index: number }> = [];
  marks.forEach((mark, index) => {
    if (!mark.spanFr) return;
    const at = text.slice(mark.start, mark.start + mark.spanFr.length) === mark.spanFr ? mark.start : text.indexOf(mark.spanFr);
    if (at < 0) return;
    const end = at + mark.spanFr.length;
    if (spans.some((span) => at < span.end && span.start < end)) return;
    spans.push({ start: at, end, kind: mark.kind, index });
  });
  spans.sort((a, b) => a.start - b.start);
  const out: WhySegment[] = [];
  let last = 0;
  for (const span of spans) {
    if (span.start > last) out.push({ text: text.slice(last, span.start), kind: null, index: null });
    out.push({ text: text.slice(span.start, span.end), kind: span.kind, index: span.index });
    last = span.end;
  }
  if (last < text.length) out.push({ text: text.slice(last), kind: null, index: null });
  return out;
}

/** The settled notes worth a line, and whether La Forge's line shows (a slip with a rule). */
export function settledNotes(notes: RvComptoirNote[] | undefined): { rows: RvComptoirNote[]; forge: boolean } {
  const rows = (notes ?? []).filter((note) => note.spanFr && (note.why || note.exampleFr || note.conceptName));
  return { rows, forge: (notes ?? []).some((note) => Boolean(note.ruleId)) };
}

/**
 * «La règle» (2026-11-22): the stamp a mark or a note carries — the day's rule before a recent
 * one — or null (no stamp: a slip under no rule of the day, or the switch off).
 */
export function ruleStamp(mark: RvMarkRule, copy: Pick<PourquoiCopy, 'day_rule' | 'recent_rule'>): { kind: 'day' | 'recent'; label: string } | null {
  if (!mark.conceptId) return null;
  if (mark.isDayRule) return { kind: 'day', label: copy.day_rule };
  if (mark.isRecentRule) return { kind: 'recent', label: copy.recent_rule };
  return null;
}
